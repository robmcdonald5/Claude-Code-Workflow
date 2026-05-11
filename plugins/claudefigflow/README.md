# claudefigflow

Interactive, agentic creator for Claude Code workflows. Authors **skills**, **commands**, **subagents**, and **hooks** either against an external target repo or as `-mock` staging files in a workshop repo.

Models its eval pipeline on `anthropics/skills/skill-creator`: interactive intent capture, parallel research subagents, structural validation, paired with-artifact / baseline eval runs, grader subagent, and a description-optimization loop for trigger reliability.

## What it creates

| Type | Output |
|---|---|
| Skill | `skills/<name>/SKILL.md` with optional `references/`, `scripts/`, `assets/` |
| Command | `commands/<name>.md` (flat) |
| Subagent | `agents/<name>.md` (flat) |
| Hook | `settings.json` merge + optional `hooks/scripts/<name>.{ps1,sh}` |

## Operations & modes

Two operations:

- **Create** — author a new artifact from scratch (template + intent + research).
- **Modify** — edit an existing artifact (load + diff + differential evals).

Two modes (create only):

- **Targeted** — write into an external repo at `<target>/.claude/{skills,commands,agents,hooks}/`. The user supplies a path (bare name resolves under `~/Repos/`, or relative, or absolute).
- **Standalone** — stage in the workshop repo's `.claude/<type-dir>/` with `-mock` suffix; promote manually when ready.

In modify mode, the destination IS the loaded artifact's location — no targeted/standalone selection needed. The `-mock` suffix discipline carries through: edits to `<name>-mock` files write back to the same `-mock` path.

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

Once installed, invoke either:

- `/claudefigflow:workflow` — guaranteed entry point for **create** operation; loads the `workflow-creator` skill and begins intent capture.
- `/claudefigflow:modify <path>` — guaranteed entry point for **modify** operation; loads the existing artifact and runs the diff + differential-evals flow.
- Natural language — phrases like "I want to create a skill", "build me a hook for X", "update this skill's description", "tune this hook's matcher", "tighten this agent's tool list" auto-trigger the same skill in the appropriate mode.

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

## Architecture

```
claudefigflow/
├── .claude-plugin/plugin.json
├── skills/
│   └── workflow-creator/
│       ├── SKILL.md                    # 11-phase orchestrator
│       ├── references/
│       │   ├── artifact-formats.md     # frontmatter spec per type
│       │   ├── path-resolution.md      # destination rules
│       │   ├── creation-workflow.md    # phase-by-phase reference
│       │   ├── eval-protocol.md        # eval JSON shapes + rubric
│       │   ├── templates/              # synced from workshop's .claude/templates/
│       │   └── mcp/                    # synced from workshop's .claude/mcp-arguments/
│       └── scripts/                    # (no scripts here; all live at plugin root)
├── agents/                             # 10 plugin subagents, cfgflow-* prefix
│   ├── cfgflow-intent-interviewer.md
│   ├── cfgflow-existing-artifact-loader.md   # modify mode only
│   ├── cfgflow-anthropic-pattern-researcher.md
│   ├── cfgflow-target-context-fetcher.md
│   ├── cfgflow-existing-workflow-scanner.md
│   ├── cfgflow-architect.md
│   ├── cfgflow-structural-validator.md
│   ├── cfgflow-eval-runner.md
│   ├── cfgflow-grader.md
│   └── cfgflow-description-optimizer.md
├── commands/
│   ├── workflow.md                     # /claudefigflow:workflow (create)
│   ├── modify.md                       # /claudefigflow:modify (modify)
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
