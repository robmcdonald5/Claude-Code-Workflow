---
description: Audit a target repository for Claude Code workflow opportunities — surfaces skills, commands, subagents, and hooks worth building. Read-only; does not author artifacts.
argument-hint: [target-path] [--depth quick|standard|deep] [--focus skill,command,subagent,hook,claude_md,mcp]
---

## Your task

Invoke the `flow-auditor` skill from this plugin to scan a target repository and produce an opportunity report. The skill is registered at `${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/SKILL.md`; load and follow its phase pipeline.

Parse `$ARGUMENTS` as:

- **First positional token** (optional) → target path. Bare names resolve under `~/Repos/<name>`; relative paths resolve against the current working directory; absolute paths are used as-is.
- **`--depth quick|standard|deep`** (optional, default `standard`) → audit depth. `quick` ≤2 min; `standard` ≤5 min; `deep` ≤10 min, broader traversal.
- **`--focus <comma-separated-types>`** (optional, default all) → restrict scope to listed artifact types. Allowed values: `skill`, `command`, `subagent`, `hook`, `claude_md`, `mcp`.

Examples:

- `/claudefigflow:flowaudit` → fully interactive; the skill asks for path, scope, and depth.
- `/claudefigflow:flowaudit myapp` → scans `~/Repos/myapp` at standard depth, all types.
- `/claudefigflow:flowaudit ./ --depth deep` → scans the current directory with deep traversal.
- `/claudefigflow:flowaudit myapp --focus skill,hook` → restricts to skill and hook recommendations.
- `/claudefigflow:flowaudit ~/Repos/myapp --depth deep --focus hook` → deep scan, hooks only.

If `$ARGUMENTS` is empty, begin the skill's Phase 1 dialog from scratch.

Do not ask permission to load the skill — that's the purpose of this command. Hand off control directly.

This operation is **read-only**. The audit produces a Markdown report at `${CLAUDE_PLUGIN_DATA}/audit-reports/<repo>-<UTC-ts>/audit.md` and prints it to chat. It never writes to the target repo. To actually build any recommended artifact, run `/claudefigflow:workflow` afterward — audit and create are intentionally separate operations.
