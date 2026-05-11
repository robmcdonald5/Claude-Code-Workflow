# CLAUDE.md

## Repo Purpose

This repository is focused on Claude Code workflows and automation patterns. It serves as a foundation for developing and testing Claude Code capabilities, agent workflows, creating *.md files for Claude to use, and automation scripts.

### General Guideline

All prompts here will be related to making custom workflows within .claude\ (agents, custom commands, skills, etc).

### Claude File Templates

.claude/templates/ is where we store templates for different styles of Claude files that may be re-used to make similar type files in the future.

### Naming for local storage

When building new files for Claude, stage them in this repo in their coresponding file organization locations with mock names. For example, `custom-command-example.md` should be stored locally in this repo and called `custom-command-example-mock.md`. These mock files will have the `mock` suffix removed from them and stored globally or locally in other repos when they are deemed to be production ready.

### Best References For Building Files

- `code.claude.com/docs/en/`
- `https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview`
- `docs.anthropic.com/en/docs/claude-code/claude_code_docs_map.md`
- `https://www.anthropic.com/engineering`
- `https://github.com/anthropics/`

## claudefigflow plugin

This repo is both a workshop (with `.claude/` as the dev source of truth) and a marketplace hosting the `claudefigflow` plugin (under `plugins/claudefigflow/`). The plugin automates the creation of Claude Code workflows (skills, commands, subagents, hooks) either against an external target repo or as `-mock` staging files here.

### Plugin-development workflow (dual structure)

- **`.claude/` at repo root** — workshop dev source of truth. Edit templates here, edit MCP-argument reference docs here, stage mock artifacts here.
- **`plugins/claudefigflow/`** — the published plugin. Its own `skills/`, `commands/`, `agents/`, `hooks/`, `scripts/`, `references/` directories.
- **`plugins/claudefigflow/skills/workflow-creator/references/{templates,mcp}/`** — *synced copies* of `.claude/templates/` and `.claude/mcp-arguments/`. Never edit these directly; edit the masters and run `python plugins/claudefigflow/scripts/sync_refs.py` (or `/claudefigflow:sync-refs`).

### Mock convention (extended for plugin context)

Apply the `-mock` suffix to every artifact type when staging in this workshop repo for later promotion:

| Type | Mock path |
|---|---|
| skill | `.claude/skills/<name>-mock/SKILL.md` (suffix on the directory) |
| command | `.claude/commands/<name>-mock.md` |
| subagent | `.claude/agents/<name>-mock.md` |
| hook | `.claude/hooks/<name>-mock-hooks.json` |

Drop the `-mock` suffix when promoting to a production destination (target repo's `.claude/`, global `~/.claude/`, or the plugin's own resources). The frontmatter `name` field never carries the `-mock` suffix — only the filesystem path does.

### Local plugin testing

```
# Once per workspace
claude plugin marketplace add C:/Users/McDon/Repos/Claude-Code-Workflow
claude plugin install claudefigflow@claude-code-workflow

# After editing plugin files
claude plugin marketplace update
# then reinstall to refresh the cache
```

### Sync invariant

After any change in `.claude/templates/` or `.claude/mcp-arguments/`, run:

```
python plugins/claudefigflow/scripts/sync_refs.py
```

Then commit both the masters and the synced plugin copies in the same commit.

A pre-commit gate enforces this. It is wired through the [`pre-commit`](https://pre-commit.com) framework via `.pre-commit-config.yaml` at the repo root. The hook only fires when sync-relevant paths are staged; on drift it exits non-zero with recovery instructions.

To activate after a fresh clone:

```
python -m pip install --user pre-commit
python -m pre_commit install
```

Bypass intentionally (rare): `git commit --no-verify`.

### Subagent location rule

All plugin subagents live at `plugins/claudefigflow/agents/` with the `cfgflow-` prefix. Never nest subagent `.md` files inside a skill directory — Claude Code's plugin auto-discovery does not register nested files, so they would not be spawnable via the Task tool.

### No baked-in repo paths

Generated artifacts and the plugin's SKILL.md must reference `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` — never absolute paths like `C:/Users/McDon/...`. Forward slashes only in path strings inside markdown / JSON.

### V1 scope

Tier A: skill + command + subagent + hook generation **and modification**. Two operations:

- **Create** (`/claudefigflow:workflow`) — author a new artifact from scratch. Modes: targeted (write to external repo) or standalone (mock staging here).
- **Modify** (`/claudefigflow:modify <path>`) — edit an existing artifact. Loads baseline, architect computes a diff, differential evals measure lift (post-mod vs pre-mod), atomic apply with `.pre-modify.bak` rollback. Negative lift rejects the modification.

Out of scope for v1: full plugin scaffold (composite), MCP server stubs, public GitHub publication.