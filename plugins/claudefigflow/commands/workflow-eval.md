---
description: Re-run the claudefigflow eval pipeline on an existing artifact without re-generating it. Useful for regression testing after edits or for measuring lift on artifacts created outside claudefigflow.
argument-hint: <path-to-artifact> [--iterations N]
---

## Your task

Re-run the claudefigflow evaluation pipeline (Phases 7–10 of `workflow-creator`) on an existing artifact at the path supplied via `$ARGUMENTS`. Do NOT re-run the authoring phases.

### Step 1 — Parse arguments

Treat `$ARGUMENTS` as the path to the artifact. Acceptable forms:
- Skill directory: `.claude/skills/my-skill/` or `plugins/<plugin>/skills/my-skill/` → eval `SKILL.md` inside.
- Command file: `.claude/commands/my-cmd.md`
- Subagent file: `.claude/agents/my-agent.md`
- Hook config: `.claude/settings.json` (with a `--hook-event` and `--hook-name` clarifier the user can supply inline)

If `$ARGUMENTS` is empty, ask the user for the path.

### Step 2 — Detect artifact type

Inspect frontmatter (or JSON shape for hooks) to determine type. If type is hook, run the hook-specific substitution (`test_hook.py` flow); otherwise run the standard skill/command/subagent eval pipeline.

### Step 3 — Load `references/eval-protocol.md`

Read `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/eval-protocol.md` for the contract shapes.

### Step 4 — Generate or reuse evals.json

If the artifact has an existing eval workspace at `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-*/`, offer the user the option to:
- Re-run the most recent iteration's `evals.json` (regression test).
- Generate a fresh set of test prompts (best for newly-edited artifacts).

If no existing workspace, generate fresh evals.json by:
1. Inferring 6 test prompts from the artifact's description and intent (4 positive, 2 negative minimum).
2. Asking the user to add or refine before proceeding.

### Step 5 — Run the eval pipeline

Execute Phases 8 and 9 from `workflow-creator` SKILL.md:
- Spawn `cfgflow-eval-runner` in parallel (with_artifact + baseline per eval, all in one turn).
- Spawn `cfgflow-grader` after runs complete.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate_benchmark.py <iteration-workspace>`.

For hooks, instead run:
- `python ${CLAUDE_PLUGIN_ROOT}/scripts/test_hook.py <hook-path> <fixtures-dir>`.

### Step 6 — Report

First **write an output marker**. `write_marker.py` writes the marker JSON then renders the sibling `index.html` inline — the HTML report lands at `${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-workflow-eval-<name>/index.html`:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/write_marker.py \
  --plugin-data-dir ${CLAUDE_PLUGIN_DATA} \
  --operation workflow-eval \
  --artifact-type <skill|command|subagent|hook> \
  --artifact-name <name-from-artifact-frontmatter> \
  --artifact-path <absolute-path-to-artifact> \
  --benchmark-json <workspace>/iteration-1/benchmark.json \
  --eval-workspace <workspace> \
  --rationale-json '<inline-json>'
```

`--plugin-data-dir ${CLAUDE_PLUGIN_DATA}` is **required** — Bash subprocesses don't reliably inherit `CLAUDE_PLUGIN_DATA`, so the command prompt must pass the resolved path explicitly. Omitting it lands marker and HTML in a workshop-local fallback dir, not in the canonical plugin-data location.

The `--rationale-json` payload is an object with `iterations_run` (count), `iterations` (list of `{iteration, benchmark_path}` objects — one per iteration when `--iterations N > 1`), and `conclusions` (free-form text covering pass/fail status, top strengths, top weaknesses, and the recommended next action).

For hooks, omit `--benchmark-json` and instead pass a `--rationale-json` whose conclusions describe the `test_hook.py` fixture pass/fail tallies. The renderer falls back gracefully when benchmark data is absent.

Then print:
- Workspace path.
- Aggregate scores (with-artifact vs baseline vs lift).
- Pass/fail against the done-definition (≥0.80 aggregate AND positive lift AND no false positives).
- Top 3 strongest evals (positive lift) and top 3 weakest (low or negative lift).
- HTML report path (the `html_path` value from the `write_marker.py` stdout JSON). If `html_path` was absent (inline render failed), say "HTML report: not rendered — run python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_output.py to retry".
- Suggestion: "if pass — done; if fail — recommend re-running architect on the weakest evals' areas".

### Optional flag — `--iterations N`

If `--iterations N` is present in `$ARGUMENTS` and `N > 1`, repeat Steps 4–6 N times with fresh evals.json each iteration. Useful for stability measurement. Report variance across iterations.

## Constraints

- Do not modify the artifact. This command is read-only on the artifact itself.
- Do not re-architect. If evals reveal problems, surface them — do not silently fix.
- All eval data goes to `${CLAUDE_PLUGIN_DATA}/eval-workspaces/`, never to the repo or to `~/.claude/plugins/cache/`.
