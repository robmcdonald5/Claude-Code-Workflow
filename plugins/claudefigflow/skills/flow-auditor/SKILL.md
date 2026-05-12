---
name: flow-auditor
description: This skill should be used when the user asks to "audit this repo for workflow ideas", "what skills would help this codebase", "scan this repo for automation opportunities", "find Claude Code workflow opportunities", "audit my repo", "what hooks would help this project", "what could be automated here", "give me ideas for workflows", "run a workflow audit", "flow audit", "look at this repo and tell me what to build", "discover workflow opportunities", or otherwise asks for an opportunity-mining scan of a target repository to surface candidate Claude Code skills, commands, subagents, and hooks WITHOUT building them. Produces a tiered Markdown opportunity report with file:line evidence and suggested build commands.
version: 0.1.0
---

# flow-auditor

Scans a target repository to recommend which Claude Code artifacts (skills, commands, subagents, hooks, CLAUDE.md additions, MCP integrations) would add value — without building any of them. Produces a tiered Markdown opportunity report with file:line evidence and suggested build commands.

This skill is the **discovery** counterpart to the workshop's `workflow-creator` skill (which handles authoring). Audit first to find out *what* to build, then run `/claudefigflow:workflow` to actually build it.

## When to engage

Activate when the user expresses intent to *discover* opportunities, not author them. Trigger phrases include those listed in `description`. Engage on loose paraphrases too — "what could we automate here?", "ideas for skills?", "look at this repo and tell me what to build".

Do NOT engage when:

- The user has already named a specific artifact they want to build → use `workflow-creator` via `/claudefigflow:workflow`.
- The user wants to modify an existing artifact → use `workflow-creator` modify mode via `/claudefigflow:modify`.
- The user asks for a code review, security audit, or refactor recommendation — those are different audits. This audit is specifically about *Claude Code workflow opportunities*.

If unsure between audit-discovery vs create-with-vague-intent, ask once: "Do you want me to scan the repo and recommend what to build, or do you already have a specific artifact in mind?"

## Path conventions

All paths follow the targeted-mode resolution rules in `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/path-resolution.md`. The audit *never* writes to the target repo.

The audit report is written to:

```
${CLAUDE_PLUGIN_DATA}/audit-reports/<repo-name>-<UTC-timestamp>/audit.md
```

The JSON summary is captured by the orchestrator from the synthesizer's stdout.

## Reference files (load on demand)

- `${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/references/audit-protocol.md` — classification decision table, tier heuristics, output Markdown template, JSON summary schema. **Load at Phase 4** when the synthesizer is engaged.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/path-resolution.md` — targeted-mode path resolution. Load at Phase 2.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/artifact-formats.md` — frontmatter spec per artifact type. Load only when proposed-trigger validation is needed.

## Subagent roster

All subagents are registered at `plugins/claudefigflow/agents/`:

- `cfgflow-target-context-fetcher` (reused) — lightweight context: language, framework, existing `.claude/` inventory, CLAUDE.md takeaways, platform conventions. (Phase 3, parallel)
- `cfgflow-repo-signal-scout` (new) — deeper opportunity-signal extraction beyond what the context-fetcher does. (Phase 3, parallel)
- `cfgflow-opportunity-synthesizer` (new) — applies the decision table, assigns tiers, writes the Markdown report. (Phase 4)

Spawn the two Phase 3 subagents in a single Task batch for parallelism.

## Pipeline

### Phase 0 — Operation type

If the user invoked `/claudefigflow:flowaudit` → `operation_type = "audit"`.

If the user matched on an audit-flavored trigger phrase from `description`, infer `operation_type = "audit"` and proceed.

If ambiguous (e.g., "look at this repo and tell me what to do" — could be audit OR could be a request to run Claude Code's `/init` for CLAUDE.md scaffolding), ask once: "Do you want a workflow opportunity scan, or something else?"

### Phase 1 — Intent capture

Collect interactively, in at most 3-5 questions:

- **Target path** (required) — bare name resolves under `~/Repos/`, relative path resolves against `cwd`, absolute path used as-is.
- **Focus** (optional, default `all`) — which artifact types to consider. Allowed: `skill`, `command`, `subagent`, `hook`, `claude_md`, `mcp`. Multi-select.
- **Depth** (optional, default `standard`) — `quick` (≤2 min), `standard` (≤5 min), `deep` (≤10 min, broader).
- **Hints** (optional) — free-form bias text: "CI-related opportunities", "anything PR-review-flavored", "we have a lot of repetitive frontend work". Passed to both subagents as a soft weighting bias; not a hard filter.

If the user invoked `/claudefigflow:flowaudit <path>` (or with flags), the target path / depth / focus are already supplied; confirm and only ask about anything still missing.

Do not ask further questions before Phase 3 — the scan subagents are opinionated about what to look for.

### Phase 2 — Target acquisition

Resolve the target path per `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/path-resolution.md` (targeted-mode resolution algorithm).

Validate:

1. Path exists. If not, ask for a corrected path and re-validate.
2. Path is a directory.
3. Has `.git/`. Warn if not (still proceed).

The audit does *not* require an existing `.claude/` directory — that's the whole point.

If the user is auditing the current workshop repo (self-audit), allow it but warn: "You're auditing the workshop repo itself. Recommendations may overlap with in-flight artifacts." Proceed on confirmation.

Compute the report output path:

```
${CLAUDE_PLUGIN_DATA}/audit-reports/<repo-basename>-<UTC-timestamp>/audit.md
```

where `<repo-basename>` is `os.path.basename(target_path)` and `<UTC-timestamp>` is ISO 8601 compressed, e.g., `2026-05-12T142301Z`. The synthesizer will create the parent directory.

### Phase 3 — Signal collection (parallel)

Spawn two subagents in a single Task batch. They will run in parallel:

1. **`cfgflow-target-context-fetcher`** with:
   - `target_path = <resolved>`
   - `artifact_type = "audit"` (informational string; the fetcher accepts any value here)

   Returns the lightweight context report including the existing `.claude/` inventory.

2. **`cfgflow-repo-signal-scout`** with:
   - `target_path = <resolved>`
   - `depth = <quick|standard|deep>`
   - `focus = <list-or-"all">`
   - `focus_hints = <free-form-string-from-Phase-1 or null>`
   - `existing_artifacts_summary = ""` (passed empty initially; the synthesizer will cross-reference against the target-context-fetcher's inventory in Phase 4)

   Returns structured JSON of raw signals.

Wait for both to return before Phase 4.

**Antipattern:** spawning them sequentially. Parallel is critical for wall-clock budget.

### Phase 4 — Synthesis

Engage `cfgflow-opportunity-synthesizer` with:

- `signals_json` = output of `cfgflow-repo-signal-scout`
- `target_context_json` = output of `cfgflow-target-context-fetcher`
- `focus` = the user's artifact-type filter (or `"all"`)
- `focus_hints` = the user's free-form hints from Phase 1 (or null)
- `output_path` = the report path computed in Phase 2
- `target_path` = the resolved target path (for evidence verification)
- `tier_filter` = null (include all tiers in v1 — let the user filter visually)

The synthesizer:

1. Loads `${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/references/audit-protocol.md`.
2. Clusters signals, classifies each cluster against the decision table, assigns tiers.
3. Cross-references against the existing `.claude/` inventory to mark `skip_existing` clusters.
4. Verifies each cited `file:line` exists.
5. Writes the Markdown report to `output_path`.
6. Emits the JSON summary on stdout.

### Phase 5 — Display report

After the synthesizer returns:

1. Read the Markdown report from `output_path`.
2. Print it in full to the chat. **Do not summarize away the body** — the user wants to see the evidence-cited recommendations inline. If the report is very long (>500 lines), print the top-level structure and the High-value section in full, then offer to print Medium/Low on request.
3. Print the JSON summary's tier counts and the `candidates_for_workflow_queue` list as a compact preview (one line per candidate).

### Phase 6 — Triage (optional interactive step)

Ask the user: "Want to queue any of these for `/claudefigflow:workflow` now? Reply with the opportunity IDs (e.g., `H1, M3`), or `no` to skip."

Parse the reply leniently. Extract opportunity IDs by regex `[HML]\d+` against the full reply text — loose phrasing like "build H1 and M3 please", "yeah H1 sounds good", or "queue H1, the format hook (M2), and L1" should all work. If the reply contains no matching IDs AND no clear negative ("no", "skip", "nope", "not now"), ask once more for clarification rather than guessing.

If the user picks any:

- For each selected ID, print the corresponding `/claudefigflow:workflow ...` build command verbatim from the report.
- **Do not invoke `workflow-creator` automatically.** The user must explicitly run the command in a fresh prompt — audit and build are intentionally separate operations. Auto-invoking would dissolve the "discover, then deliberate" boundary that gives the audit its value.

If the user says `no`, skip silently.

### Phase 7 — Next steps

Before printing the next-steps block, **write an output marker**. `write_marker.py` writes the marker JSON then renders the sibling `index.html` inline — the HTML report lands at `${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-audit-<name>/index.html` and renders the Markdown report's opportunities as styled cards, with copy-pastable `/claudefigflow:workflow ...` build commands for each buildable opportunity.

The synthesizer already wrote both `audit.md` and `summary.json` into `<report-dir>` during Phase 4 — no extra persistence step is needed. Invoke:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/write_marker.py \
  --plugin-data-dir ${CLAUDE_PLUGIN_DATA} \
  --operation audit \
  --artifact-name <repo-basename> \
  --artifact-path <resolved-target-path> \
  --audit-report-md <report-dir>/audit.md \
  --audit-summary-json <report-dir>/summary.json \
  --rationale-json '<inline-json>'
```

`--plugin-data-dir ${CLAUDE_PLUGIN_DATA}` is **required** — Bash subprocesses don't reliably inherit `CLAUDE_PLUGIN_DATA`, so the Skill prompt must pass the resolved path explicitly. Omitting it lands marker and HTML in a workshop-local fallback dir, not in the canonical plugin-data location.

The `--rationale-json` payload is an object with `target` (resolved absolute path), `focus` (the user's filter, default `"all"`), and `depth` (`quick|standard|deep`). The HTML renderer parses the Markdown report directly to recover each opportunity's tier, type, rationale, evidence, suggested name/trigger/effort, and build command — no need to duplicate that in the marker.

Then print exactly:

```
✓ Audit report: <report-path>
✓ Target: <target-path>
✓ Opportunities surfaced: <total> (<high> high, <medium> medium, <low> low)
✓ Already covered: <skipped_existing> (existing artifacts)

Next steps:
- Inspect the report; recommendations are evidence-cited (file:line).
- To build any opportunity: /claudefigflow:workflow <type> for <opportunity-name>
- To re-audit with different depth: /claudefigflow:flowaudit <path> --depth <quick|standard|deep>
- Reports persist under ${CLAUDE_PLUGIN_DATA}/audit-reports/. Not auto-pruned.
- HTML report rendered inline alongside the marker at ${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-audit-<name>/index.html.
```

## Style rules

Apply only to the report body the synthesizer produces (not this SKILL.md):

- Evidence over rhetoric. Every recommendation cites `file:line`. No bare assertions.
- Conservative tiers. When uncertain, downgrade.
- Imperative form in rationales.
- No invented file paths. Every citation must trace back to a signal-scout entry.
- Forward slashes everywhere; never absolute paths in the report body except in the header's `Target:` line.

## Failure modes

- **Target path invalid** → return to Phase 1 to re-prompt; do not write a report.
- **All Phase 3 subagents return empty** → the repo is too small or sparse for signal extraction; print a friendly "no opportunities surfaced; try a larger codebase or `--depth deep`" message and skip Phase 4-7.
- **Synthesizer can't classify any signals** → still produce a report with a "Patterns observed but not classified" section; do not omit the report file.
- **Synthesizer reports `cited file doesn't exist`** → warn the user; the JSON summary's `warnings` array surfaces it.
- **Report path's parent directory missing** → the synthesizer creates it; no error.
- **User aborts mid-Phase-1** → no files written; the audit is purely interactive until Phase 4.

## Constraints

- **Read-only on the target.** No writes to the target repo, ever. Even if the user asks for a copy of the report in their `.claude/`, refuse politely — they can copy the report file manually.
- **Recommend, do not author.** This skill does NOT engage `workflow-creator`. If the user wants to build, they invoke `/claudefigflow:workflow` themselves.
- **Evidence-required.** Every recommendation must cite `file:line`. The synthesizer enforces this.
- **Bounded scan.** Honor the depth setting. Don't let `deep` mean "unbounded".
- **No external network calls.** All work is local filesystem.
- **No baked-in absolute paths** in the report body. Use forward slashes; relative paths relative to `target_path` for evidence.
- **One report per run.** Do not overwrite prior audit reports — the timestamped directory naming ensures uniqueness.

## Done definition

An audit is "done" when:

1. The Markdown report exists at `${CLAUDE_PLUGIN_DATA}/audit-reports/<repo>-<ts>/audit.md`.
2. The report was printed (in full or with explicit deferral of Medium/Low) to chat in Phase 5.
3. The Phase 7 next-steps block was printed.
4. (Optional) Phase 6 triage was offered and either honored or declined.

There is no Phase 8/9 eval equivalent. Recommendation quality is judged by the user reading the report and deciding to build (or not). For meta-evaluation of the audit operation itself, the user can run `/claudefigflow:workflow-eval ${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/` to grade this skill as any other.
