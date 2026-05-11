# Creation workflow (detailed phase reference)

Extended reference for the 11-phase pipeline in `SKILL.md`. Load this when uncertain how a specific phase should proceed.

## Phase 1 — Intent capture

**Goal:** produce a complete intent JSON the architect can build from.

Engage `cfgflow-intent-interviewer` with the original user prompt. The interviewer is opinionated: it limits itself to 5–8 questions and refuses to keep digging once it has enough.

**Expected output:** intent JSON matching the schema in `cfgflow-intent-interviewer.md`. If the interviewer surfaces ambiguity it cannot resolve, surface it to the user before continuing.

**Common pitfalls:**

- User wants two artifacts at once → split into a queue; do one first.
- User can't name the artifact → suggest 2-3 candidates derived from their description.
- "Make a plugin" → out of scope for v1; recommend deferring to v2 or hand-rolling the manifest.

## Phase 2 — Mode resolution

**Goal:** lock the destination path before research starts (so the existing-workflow-scanner knows where to look).

### Targeted path resolution

When the user gives a bare name (e.g., `myapp`), resolve under `~/Repos/` — this user keeps all repos there. Use `os.path.expanduser("~")` to find the home dir.

When the user gives `./` or `../`, resolve against `os.getcwd()`.

When the user gives an absolute path, use as-is.

Always normalize to forward slashes for storage; convert at filesystem-call time.

### Targeted validation

- Path exists? If not, ask whether to create.
- Is a directory?
- Has `.git/`? Warn if not.
- Has `.claude/`? If yes, use it. If not, offer to scaffold the four standard subdirs.
- Has `CLAUDE.md`? Read it for context; do not auto-edit.

### Standalone

No path questions. Destination is this repo's `.claude/<type-dir>/` with `-mock` suffix per `references/path-resolution.md`.

## Phase 3 — Research (parallel)

**Goal:** gather all the external context the architect needs in one turn.

Spawn three subagents in a single Task batch:

1. `cfgflow-anthropic-pattern-researcher` — always.
2. `cfgflow-target-context-fetcher` — only if mode is targeted.
3. `cfgflow-existing-workflow-scanner` — always; checks all destinations.

Wait for all three; do not proceed until you have all reports.

**Antipattern:** running the three subagents in sequence. Parallel is critical for latency.

**Output:** three structured reports. The architect consumes all three.

## Phase 4 — Architect

**Goal:** turn intent + research into a complete authoring plan, present to user.

Engage `cfgflow-architect`. Provide it with:
- Intent JSON
- Pattern researcher report
- Target context report (if targeted)
- Existing-workflow-scanner JSON

The architect:
1. Selects a base template (or chooses greenfield with justification).
2. Drafts frontmatter (using `artifact-formats.md` as the spec).
3. Designs body structure.
4. Lists bundled resources (skills only).
5. Writes staging files to `${CLAUDE_PLUGIN_DATA}/staging/<session-id>/<artifact-name>/`.
6. Emits a file-tree plan.

Present the plan to the user. Iterate as needed.

**Gate:** do not proceed without explicit user approval. Even if the plan looks right.

## Phase 5 — Write

**Goal:** move staged files to the final destination.

Operations:
1. Read each staged file from `${CLAUDE_PLUGIN_DATA}/staging/<session>/`.
2. For `settings.json` / `hooks.json`: merge with existing — do not overwrite.
3. Write to the destination from Phase 2.
4. Use atomic write (write to `<dest>.tmp`, rename to `<dest>`).
5. Do not delete the staging copy — keep it for one session in case the user rolls back.

## Phase 6 — Structural validation

**Goal:** catch structural defects before evals start.

Two parallel checks:
- `python validate_artifact.py <path> --type <type>` — deterministic.
- `cfgflow-structural-validator` — LLM-level semantic check.

If either fails (errors, not warnings), return to Phase 4. Warnings are surfaced but do not block.

## Phase 7 — Eval setup (skill / command / subagent)

**Goal:** generate test prompts + assertions.

Auto-generate a minimum of 6 evals per `eval-protocol.md`:
- 4 positive (should trigger / produce correct output)
- 2 negative (should NOT trigger)
- Optionally 1-2 edge cases

Show the auto-generated set to the user. Ask: "Add or refine any?"

Save to `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact>-<UTC-ts>/iteration-1/evals.json`.

Validate with `python run_eval.py validate <workspace>`.

## Phase 8 — Parallel eval runs (skill / command / subagent)

**Goal:** generate paired with-artifact and baseline responses.

For each eval in `evals.json`, spawn TWO `cfgflow-eval-runner` instances in the **same turn** (single Task batch):
- One with `mode: with_artifact` and `artifact_path` set.
- One with `mode: baseline` and `artifact_path: null`.

All N×2 spawns go in one turn. Wait for all to complete.

**Antipattern:** spawning sequentially or in separate turns. Parallelism is essential and the eval timing is part of the measurement.

## Phase 9 — Grade & aggregate

**Goal:** produce per-eval grading.json and aggregate benchmark.json.

1. Spawn `cfgflow-grader` once with the iteration workspace path. Grader produces per-eval `grading.json`.
2. Run `python aggregate_benchmark.py <iteration-workspace>`.

Output: `benchmark.json` with aggregate scores and pass/fail against done-definition.

## Phase 10 — Description optimization (skill / command / subagent only)

**Goal:** maximize trigger F1 of the description field.

Engage `cfgflow-description-optimizer`. The optimizer runs up to 5 iterations of generate-test-keep-best on a 60/40 train/test corpus.

`python optimize_description.py finalize <workspace> <artifact-path>` writes the winning description back to the frontmatter and saves `optimization-summary.json`.

If no iteration beats baseline F1, the artifact is untouched.

## Phase 11 — Package / install instructions

**Goal:** tell the user exactly what to do next.

Print the install instructions per the SKILL.md template. Cover:
- Path of the written artifact.
- Path of the eval workspace.
- Final scores.
- Mode-specific next steps:
  - Targeted: restart Claude Code in the target repo.
  - Standalone: drop `-mock` suffix when ready; move to production destination.
- Plugin cache reminder: `/plugin marketplace update` + reinstall after sync_refs changes.

## Hook substitution summary

For artifact type `hook`, Phases 7–10 are replaced as follows:

| Standard phase | Hook substitution |
|---|---|
| 7 — Eval setup | Generate synthetic input fixtures matching the event schema |
| 8 — Parallel runs | `test_hook.py` executes the hook with each fixture |
| 9 — Grade | Validate output JSON shape, exit-code semantics, security lints |
| 10 — Description opt | Matcher tuning against tool-name corpus (regex precision/recall) |

See `test_hook.py` and `cfgflow-eval-runner` for the hook-mode flows.
