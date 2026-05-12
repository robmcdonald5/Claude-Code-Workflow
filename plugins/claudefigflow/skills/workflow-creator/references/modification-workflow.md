# Modification workflow

Detailed phase reference for **modify mode** of the `workflow-creator` skill. Use this file when the user invokes `/claudefigflow:modify` or when intent capture sets `operation_type = "modify"`.

Modify mode shares Phases 3 (research) and 6 (validation) with creation mode. It differs in load, intent, architect, write, and eval phases. The numbering below mirrors the creation pipeline so cross-references stay clean.

## Phase 0 — Operation type detection

Set at intent capture in Phase 1. If the user invoked `/claudefigflow:modify`, `operation_type` is fixed to `"modify"`. Otherwise the intent interviewer asks once during Phase 1.

## Phase 1 — Intent capture (modify variant)

Engage `cfgflow-intent-interviewer` with `operation_type = "modify"`. The interviewer collects:

- **Artifact path** — already supplied if the user came via `/claudefigflow:modify`. Otherwise ask.
- **Change intent** — what should be different after the modification? Examples: "make the description trigger on phrase X too", "add a hook script", "tighten the agent's tool list", "fix a bug in Phase 4 of this skill".
- **Scope** — frontmatter only? body only? both? bundled resources?
- **Reversibility expectation** — is this an experimental tweak (default: yes, keep backup) or a major rewrite (still keep backup, but warn about scope)?

The output intent JSON adds these fields to the standard shape:

```json
{
  "operation_type": "modify",
  "artifact_path": "/absolute/path",
  "change_intent": "one-paragraph description",
  "scope_hint": "frontmatter" | "body" | "both" | "bundled-resources",
  "reversibility": "experimental" | "major-rewrite"
}
```

## Phase 2 — Load existing artifact

Engage `cfgflow-existing-artifact-loader` with `artifact_path`. Returns the structured baseline (frontmatter, body sections, bundled resources, path classification). The architect consumes this directly.

If load fails (path not found, type ambiguous), surface to user before continuing.

## Phase 2.5 — Mode resolution (path-only)

Already handled by the loader's `path_classification` output. No additional user prompts in modify mode unless the architect needs to write to a different location (rare; flag and ask).

## Phase 3 — Research (parallel)

Identical to creation mode. The pattern researcher pulls current canonical patterns so the modification respects whatever new conventions have landed since the artifact was authored. Skip `cfgflow-target-context-fetcher` unless the artifact's path classification is `production-target` — i.e., only fetch target context when the artifact lives in an external target repo.

`cfgflow-existing-workflow-scanner` is also useful: scan for related artifacts that the user's change might affect. Example: if changing a skill description, scan for other skills with overlapping triggers.

## Phase 4 — Architect (modify variant)

Engage `cfgflow-architect` with:

- Intent JSON (with `operation_type: "modify"`)
- Loaded baseline from Phase 2
- Research findings from Phase 3

The architect produces a **modified candidate** at `${CLAUDE_PLUGIN_DATA}/staging/<session-id>/<artifact-name>/`. Same staging discipline as creation.

In modify mode, the architect:

1. **Identifies which parts to change** based on intent + research.
2. **Preserves untouched parts verbatim** — including comments, whitespace conventions, and section ordering — unless the change explicitly affects them.
3. **Computes a structured change summary** via `python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py summary <original> <staged-candidate>`. Includes: frontmatter fields changed, body sections added/removed/changed, line/byte delta.
4. **Presents a unified diff** to the user via `python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py diff <original> <staged-candidate>`.
5. **Gates on approval** — never proceed without explicit user OK.

If the architect determines the requested change is a no-op (diff summary's `is_noop: true`), surface to the user and stop. The user may have a different intent than what they articulated.

## Phase 5 — Apply edit

Replaces "Write" in creation mode. Run:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py apply <original> <staged-candidate>
```

The script:
1. Creates `<original>.pre-modify.bak` (rollback artifact).
2. Atomically replaces `<original>` with the candidate contents (write `.tmp`, rename).

For hooks (which live inside `settings.json`/`hooks.json`), the architect re-reads the parent settings file, replaces only the targeted hook entry (matching event + matcher + index), and writes back. Never overwrite unrelated entries.

## Phase 6 — Validation

Identical to creation mode. `validate_artifact.py` checks the *modified* file. Both deterministic and semantic checks apply. Failure → revert to backup and return to Phase 4.

## Phase 7 — Eval setup (differential mode, for skill/command/subagent)

For modify mode, evals measure lift of **post-modification vs pre-modification** on the same prompts. The eval workspace gets `eval_mode: "differential"` in `evals.json`. The runner is told to load:

- **Treatment run** (`with_artifact.json` in the file naming, for schema compatibility) → the modified version.
- **Control run** (`baseline.json`) → the pre-modification version (the `.pre-modify.bak` file or a copy preserved at staging time).

If the change is a description-only edit, the eval can be skipped or replaced with the trigger F1 measurement from Phase 10 (description-optimization-style).

For hooks, run `test_hook.py` on the post-modification config; compare exit codes and output shapes to the pre-modification fixtures. No LLM grader; structural diff is the signal.

## Phase 8 — Differential eval runs (skill/command/subagent only)

Same parallel-spawn pattern as creation mode: per eval, spawn one `cfgflow-eval-runner` with treatment loaded and one with control loaded. Both runs use the same prompt.

## Phase 9 — Grade & aggregate (differential)

`cfgflow-grader` operates in differential mode:

- `with_artifact_score` = treatment (post-modification) score.
- `baseline_score` = control (pre-modification) score.
- `lift` = treatment - control. **Negative lift means the modification made things worse.**

Decision rule:

- `lift > 0` and `treatment >= max(baseline, 0.75)` → modification accepted.
- `lift > 0` but `treatment < 0.75` → modification accepted with a warning ("improvement but artifact is still below quality threshold").
- `lift <= 0` → modification rejected. Offer rollback: restore from `.pre-modify.bak`.

The aggregate `benchmark.json` adds a `decision` field: `"accept" | "accept-with-warning" | "reject"`.

## Phase 10 — Description optimization (skip unless description changed)

Only run if the modification touched the `description` field. Otherwise skip — the description was already tuned (or wasn't, depending on prior history).

## Phase 11 — Report

Before printing the modification report, **write an output marker**. `write_marker.py` writes the marker JSON then renders the sibling `index.html` inline — the HTML report lands at `${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-modify-<name>/index.html`. The marker carries the architect's rationale (what was added, what was removed, what was changed, and **why**) which is not otherwise captured on disk.

Invoke:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/write_marker.py \
  --plugin-data-dir ${CLAUDE_PLUGIN_DATA} \
  --operation modify \
  --artifact-type <skill|command|subagent|hook> \
  --artifact-name <kebab-name> \
  --artifact-path <absolute-path-to-modified-file> \
  --benchmark-json <eval-workspace>/iteration-1/benchmark.json \
  --diff-summary-json <staging-dir>/diff-summary.json \
  --backup-path <original>.pre-modify.bak \
  --rationale-json '<inline-json>'
```

`--plugin-data-dir ${CLAUDE_PLUGIN_DATA}` is **required** — Bash subprocesses don't reliably inherit `CLAUDE_PLUGIN_DATA`, so the Skill prompt must pass the resolved path explicitly. Omitting it lands marker and HTML in a workshop-local fallback dir, not in the canonical plugin-data location.

The `--rationale-json` payload is an object with `change_intent` (verbatim from Phase 1), `scope_hint`, `decision` (`accept`|`accept-with-warning`|`reject` per Phase 9), and three rationale lists — `additions`, `removals`, `modifications` — each a list of `{path, what, why}` objects. `path` may be a file path OR a structural locator like `Section 'Phase 4'` or `frontmatter.description`. The `why` field is non-optional in modify mode: the user explicitly wants to see why each change was made.

To persist the `diff-summary.json`, run `python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py summary <original> <staged-candidate> > <staging-dir>/diff-summary.json` before the apply step (Phase 5) so the file exists when the marker is written. Otherwise pass `--diff-summary-json` empty.

Then print:

```
✓ Artifact modified: <final-path>
✓ Backup preserved: <original>.pre-modify.bak
✓ Differential lift: +<lift>% (treatment <score>, baseline <score>)
✓ Decision: <accept|accept-with-warning|reject>
✓ HTML report: <html-path-from-write_marker-stdout>

Changes:
  - Frontmatter fields: <list>
  - Body sections changed: <list>
  - Lines: <delta> (was N, now M)

Rollback: cp <backup-path> <original-path>
```

The `<html-path-from-write_marker-stdout>` is the `html_path` value emitted in the JSON `write_marker.py` just printed. If the JSON did not include `html_path` (inline render failed), print `✓ HTML report: not rendered — run python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_output.py to retry` instead.

## Differences summary (create vs modify)

| Phase | Creation | Modification |
|---|---|---|
| 0 | n/a | Operation-type detection |
| 1 | Intent + name + behavior | Intent + change scope (path already supplied) |
| 2 | Mode resolution (target/standalone path) | Load existing artifact + path classification |
| 3 | Research (parallel) | Research (same, skip target-context when not targeted-prod) |
| 4 | Architect drafts from template | Architect computes diff against loaded baseline |
| 5 | Write new files | Apply edit (atomic, with .pre-modify.bak) |
| 6 | Validate | Validate (identical) |
| 7 | Generate eval prompts | Generate eval prompts (mode = differential) |
| 8 | with_artifact vs no_artifact | post_modification vs pre_modification |
| 9 | Grader: lift measures novelty value | Grader: lift measures change value; negative → reject |
| 10 | Description optimization | Description optimization (only if description changed) |
| 11 | Install instructions | Modification report + rollback hint |

## Failure modes specific to modify

- **No-op detected** — architect's diff summary returned `is_noop: true`. Stop and ask user to clarify intent.
- **Negative lift** — modification accepted by architect but evals show regression. Reject; offer rollback.
- **Backup write fails** — abort before applying. Never apply without a recoverable backup.
- **Hook entry not found** — loader returned candidates; ask user to disambiguate. Do not modify any hook entry without an exact match.
- **Frontmatter field unknown** — architect tried to add a field not in the spec. Validator catches this; return to Phase 4.
