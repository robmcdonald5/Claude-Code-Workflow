---
description: Author a new Claude Code artifact (skill, command, subagent, or hook) via the workflow-creator skill. Asks targeted-vs-standalone interactively.
argument-hint: [optional: artifact type or one-line intent]
---

## Your task

Invoke the `workflow-creator` skill from this plugin to create a new Claude Code artifact. The skill is registered at `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/SKILL.md`; load and follow its phase pipeline.

If `$ARGUMENTS` is non-empty, treat it as a hint for the intent-capture phase (e.g., the user typed `/claudefigflow:workflow skill for code reviews` — pass the rest as initial intent).

If `$ARGUMENTS` is empty, begin the skill's Phase 1 dialog from scratch.

Do not ask permission to load the skill — that's the purpose of this command. Hand off control directly.
