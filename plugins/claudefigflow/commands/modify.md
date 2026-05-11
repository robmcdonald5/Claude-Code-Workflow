---
description: Modify an existing Claude Code artifact (skill, command, subagent, or hook) via the workflow-creator skill in modify mode. Computes a diff, validates, runs differential evals to measure lift.
argument-hint: [path-to-artifact]
---

## Your task

Invoke the `workflow-creator` skill in **modify mode** to edit an existing Claude Code artifact rather than create one from scratch.

### Step 1 — Resolve target

Treat `$ARGUMENTS` as a path to the artifact. Acceptable forms:

- Skill directory: `path/to/.claude/skills/<name>/` (the `SKILL.md` inside is the target).
- Command file: `path/to/.claude/commands/<name>.md`.
- Subagent file: `path/to/.claude/agents/<name>.md`.
- Hook reference: path to a `settings.json` or `hooks.json` plus a clarifier the user supplies inline (`--event PostToolUse --matcher "Write|Edit"` or `--event PostToolUse --index 0`).

If `$ARGUMENTS` is empty, ask the user for the path and accept any of:

- Bare name → resolve under `~/Repos/<name>/.claude/<type-dir>/` if possible; otherwise ask which workshop/target.
- Absolute path.
- "Browse" → list candidates by globbing this workshop's `.claude/` plus `~/Repos/*/.claude/`.

### Step 2 — Hand off to the workflow-creator skill

Set the skill's intent variables to:

- `operation_type = "modify"`
- `artifact_path = <resolved-path>`
- `change_intent = <to-be-captured in Phase 1>`

Then invoke the skill at `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/SKILL.md`. The skill will follow the modification flow described in `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/modification-workflow.md`:

1. Load the existing artifact via `cfgflow-existing-artifact-loader`.
2. Capture the desired change (Phase 1, modify variant).
3. Research current patterns (Phase 3 — same as creation).
4. Architect computes a diff against the loaded baseline.
5. Validate the modified version.
6. Run **differential evals** — pre-modification vs post-modification on the same prompts.
7. Optional description optimization if the change touched the description.
8. Apply the edit; print before/after summary.

### Step 3 — Do not bypass the modification flow

Do not edit the artifact directly even if the change seems trivial. The diff + eval pipeline catches structural regressions and ensures the change actually helps. The shortest path for a one-line description tweak is still through the skill.

## Constraints

- Do not change the artifact's `name` field unless the user explicitly asks. Renaming has downstream consequences (slash command paths, delegation triggers, file locations).
- Do not modify files outside the loaded artifact's directory tree.
- Preserve any prior `-mock` suffix during edit — promotion is a separate step.
- After the skill completes, the original file's prior contents are preserved as `<file>.pre-modify.bak` for one session.
