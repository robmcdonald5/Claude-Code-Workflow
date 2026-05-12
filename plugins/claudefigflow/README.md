# claudefigflow

Interactive, agentic **creator and auditor** for Claude Code workflows. Authors **skills**, **commands**, **subagents**, and **hooks** either against an external target repo or as `-mock` staging files in a workshop repo, and audits target repos to surface workflow opportunities worth building.

Models its eval pipeline on `anthropics/skills/skill-creator`: interactive intent capture, parallel research subagents, structural validation, paired with-artifact / baseline eval runs, grader subagent, and a description-optimization loop for trigger reliability. Its audit pipeline mirrors `skills/skill-creator/agents/analyzer.md`'s tiered-priority pattern: read-only repo scan, signal extraction, classification against the canonical `code.claude.com/docs/en/features-overview` decision criteria, evidence-cited Markdown report.

## What it creates

| Type | Output |
|---|---|
| Skill | `skills/<name>/SKILL.md` with optional `references/`, `scripts/`, `assets/` |
| Command | `commands/<name>.md` (flat) |
| Subagent | `agents/<name>.md` (flat) |
| Hook | `settings.json` merge + optional `hooks/scripts/<name>.{ps1,sh}` |

## Operations & modes

Three operations:

- **Create** — author a new artifact from scratch (template + intent + research + write + eval).
- **Modify** — edit an existing artifact (load + diff + differential evals).
- **Audit** — scan a target repo to recommend artifacts worth building. **Read-only.** Produces a tiered Markdown opportunity report with file:line evidence and suggested build commands; never writes to the target.

Two modes (create only):

- **Targeted** — write into an external repo at `<target>/.claude/{skills,commands,agents,hooks}/`. The user supplies a path (bare name resolves under `~/Repos/`, or relative, or absolute).
- **Standalone** — stage in the workshop repo's `.claude/<type-dir>/` with `-mock` suffix; promote manually when ready.

In modify mode, the destination IS the loaded artifact's location — no targeted/standalone selection needed. The `-mock` suffix discipline carries through: edits to `<name>-mock` files write back to the same `-mock` path.

In audit mode, there is no "destination" — the report lives at `${CLAUDE_PLUGIN_DATA}/audit-reports/<repo>-<UTC-ts>/audit.md`. The target repo is never modified.

A common end-to-end flow is **audit → create**: discover what to build with `/claudefigflow:flowaudit`, then build the chosen opportunities one at a time with `/claudefigflow:workflow`.

## Install (local marketplace, current setup)

From inside the workshop repo:

```
claude plugin marketplace add .
claude plugin install claudefigflow@claude-code-workflow
```

After editing plugin files, refresh the install cache:

```
claude plugin marketplace update
# then reinstall to pick up changes
```

## Usage

Once installed, invoke one of:

- `/claudefigflow:workflow` — guaranteed entry point for the **create** operation; loads the `workflow-creator` skill and begins intent capture.
- `/claudefigflow:modify <path>` — guaranteed entry point for the **modify** operation; loads the existing artifact and runs the diff + differential-evals flow.
- `/claudefigflow:flowaudit [<target-path>] [--depth ...] [--focus ...]` — guaranteed entry point for the **audit** operation; loads the `flow-auditor` skill and produces a tiered opportunity report.
- Natural language — phrases like "I want to create a skill", "build me a hook for X", "update this skill's description", "audit this repo for workflow ideas", "what hooks would help this project" auto-trigger the appropriate skill (workflow-creator or flow-auditor).

Optional commands:

- `/claudefigflow:workflow-eval <artifact-path>` — re-run evals on an existing artifact without re-generating or modifying it.
- `/claudefigflow:sync-refs` — sync the workshop's `.claude/templates/` and `.claude/mcp-arguments/` into the plugin's bundled references.

**Full command reference and end-to-end workflow examples: [`USAGE.md`](./USAGE.md).**

## Pipeline phases

Create flow:

0. **Operation type** — set to "create" by entry point or trigger phrase.
1. **Intent capture** (interactive) — type, name, behavior, triggers, MCP deps.
2. **Mode resolution** — targeted vs standalone; resolve target path if applicable.
3. **Research (parallel)** — anthropic-pattern-researcher, target-context-fetcher (targeted only), existing-workflow-scanner.
4. **Architect** — designs file tree, drafts frontmatter, selects base template.
5. **Write** — atomic write from staging to destination.
6. **Structural validation** — `validate_artifact.py` + `cfgflow-structural-validator`.
7. **Eval setup** (eval_mode=creation) — auto-generate test prompts (+ user refinements).
8. **Parallel eval runs** — `cfgflow-eval-runner` × 2 per eval (with-artifact + baseline), all in one turn.
9. **Grade & aggregate** — `cfgflow-grader` + `aggregate_benchmark.py`.
10. **Description optimization** — `cfgflow-description-optimizer` runs ≤5 iterations on a 60/40 train/test corpus.
11. **Package / install instructions** — print next steps.

Modify flow (divergences from create):

- **Phase 1** — captures `change_intent` instead of `what_it_does`; locks `name` to existing.
- **Phase 2** — `cfgflow-existing-artifact-loader` loads the baseline; no targeted/standalone choice.
- **Phase 4** — architect computes a diff against the loaded baseline; never drafts greenfield. Emits a modification plan with unified diff.
- **Phase 5** — `diff_artifact.py apply` does atomic write with `.pre-modify.bak` rollback.
- **Phase 7-9** — `eval_mode = "differential"`; treatment = post-modification, control = pre-modification. Negative lift → modification rejected (offer rollback).
- **Phase 10** — only runs if the modification touched the description field.
- **Phase 11** — modification report instead of install instructions; includes rollback hint.

See `skills/workflow-creator/references/modification-workflow.md` for the full modify-mode reference.

For **hooks**, phases 7–10 are replaced with synthetic-input fixture generation, hook execution via `test_hook.py`, output-shape and exit-code validation, and matcher tuning (both create and modify modes).

Audit flow (separate skill — `flow-auditor`):

0. **Operation type** — set to "audit" by entry point or trigger phrase.
1. **Intent capture** (interactive) — target path, optional `focus` filter (artifact types), `depth` (`quick` / `standard` / `deep`), free-form `hints` (soft weighting bias).
2. **Target acquisition** — resolve and validate the target path (targeted-mode rules); compute report output path.
3. **Signal collection (parallel)** — `cfgflow-target-context-fetcher` (lightweight context + existing `.claude/` inventory) and `cfgflow-repo-signal-scout` (deep opportunity-signal extraction).
4. **Synthesis** — `cfgflow-opportunity-synthesizer` clusters signals, applies the canonical decision table, assigns High/Medium/Low tiers, writes the Markdown report and emits a JSON summary.
5. **Display** — print the full report (or its High-tier section + offer to print Medium/Low) to chat.
6. **Triage** (optional) — offer the user a queue: "want to build any of these now?". Prints `/claudefigflow:workflow ...` commands but does not auto-invoke.
7. **Next steps** — report path, totals, re-audit hint.

The audit has no eval phase. Recommendation quality is judged by the user reading the evidence-cited report. See `skills/flow-auditor/references/audit-protocol.md` for the classification decision table and Markdown output template.

## Architecture

```
claudefigflow/
├── .claude-plugin/plugin.json
├── skills/
│   ├── workflow-creator/
│   │   ├── SKILL.md                    # 11-phase orchestrator (create + modify)
│   │   ├── references/
│   │   │   ├── artifact-formats.md     # frontmatter spec per type
│   │   │   ├── path-resolution.md      # destination rules
│   │   │   ├── creation-workflow.md    # phase-by-phase reference (create)
│   │   │   ├── modification-workflow.md# phase-by-phase reference (modify)
│   │   │   ├── eval-protocol.md        # eval JSON shapes + rubric
│   │   │   ├── templates/              # synced from workshop's .claude/templates/
│   │   │   └── mcp/                    # synced from workshop's .claude/mcp-arguments/
│   │   └── scripts/                    # (no scripts here; all live at plugin root)
│   └── flow-auditor/
│       ├── SKILL.md                    # 7-phase audit orchestrator
│       └── references/
│           └── audit-protocol.md       # decision table + tier heuristics + output template
├── agents/                             # 12 plugin subagents, cfgflow-* prefix
│   ├── cfgflow-intent-interviewer.md
│   ├── cfgflow-existing-artifact-loader.md   # modify mode only
│   ├── cfgflow-anthropic-pattern-researcher.md
│   ├── cfgflow-target-context-fetcher.md     # reused by audit Phase 3
│   ├── cfgflow-existing-workflow-scanner.md
│   ├── cfgflow-architect.md
│   ├── cfgflow-structural-validator.md
│   ├── cfgflow-eval-runner.md
│   ├── cfgflow-grader.md
│   ├── cfgflow-description-optimizer.md
│   ├── cfgflow-repo-signal-scout.md          # audit Phase 3
│   └── cfgflow-opportunity-synthesizer.md    # audit Phase 4
├── commands/
│   ├── workflow.md                     # /claudefigflow:workflow (create)
│   ├── modify.md                       # /claudefigflow:modify (modify)
│   ├── flowaudit.md                    # /claudefigflow:flowaudit (audit)
│   ├── workflow-eval.md                # /claudefigflow:workflow-eval
│   └── sync-refs.md                    # /claudefigflow:sync-refs
└── scripts/
    ├── sync_refs.py                    # workshop masters -> plugin references
    ├── check_refs_in_sync.py           # pre-commit gate
    ├── validate_artifact.py            # deterministic structural check
    ├── run_eval.py                     # eval workspace prep + validation
    ├── aggregate_benchmark.py          # per-iteration aggregation
    ├── optimize_description.py         # iteration scoring + finalize
    ├── test_hook.py                    # hook synthetic-input validator
    ├── diff_artifact.py                # modify-mode diff + apply
    └── package_plugin.py               # distribution archive builder
```

### Subagent location rule

All subagents live at `plugins/claudefigflow/agents/`, prefixed `cfgflow-`. They are auto-discovered by Claude Code when the plugin is enabled. Subagent prompt files nested inside a skill directory would NOT be auto-discovered as spawnable subagents — Claude Code scans only the plugin root's `agents/`.

### Path discipline

All file references in artifacts use:

- `${CLAUDE_PLUGIN_ROOT}` for read-only plugin resources.
- `${CLAUDE_PLUGIN_DATA}` for writable state (staging, eval workspaces).
- Forward slashes everywhere in markdown / JSON bodies.

No absolute repo paths anywhere — generated artifacts must remain portable.

## Done definition

An artifact is "done" when:

1. Files exist at the destination from Phase 2.
2. `validate_artifact.py` exits 0.
3. (skill/command/subagent) Aggregate eval score ≥0.80 with positive lift over baseline AND no false positives on negative evals.
4. (hook) All synthetic-input fixtures pass shape and exit-code checks.
5. Phase 11 install instructions have been printed.

## Out of scope (v1)

- Full plugin scaffold (composite multi-artifact generator)
- MCP server stubs
- Public marketplace publication
- LLM-graded hook evals (substituted with deterministic shape validation)
- Auto-detection of target platform for hook script language
- Evals on the audit operation itself (`/claudefigflow:flowaudit` produces recommendations the user judges directly; meta-eval is possible via `/claudefigflow:workflow-eval` on the `flow-auditor` skill but not run automatically)
- Auto-execution of audit recommendations (audit and create are intentionally separate; the user must invoke `/claudefigflow:workflow` deliberately)
- Audit coverage of globally-installed artifacts (`~/.claude/`) and other plugin caches (`~/.claude/plugins/cache/`). The audit currently inventories only `<target>/.claude/` via `cfgflow-target-context-fetcher`. A v2 enhancement could engage `cfgflow-existing-workflow-scanner` in an audit-mode variant to detect cross-repo and cross-plugin overlap.
