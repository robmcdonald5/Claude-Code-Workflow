# Claude-Code-Workflow

A workshop and marketplace for building Claude Code workflows.

This repo serves two purposes:

1. **Workshop** — a context-rich environment for authoring Claude Code artifacts (skills, commands, subagents, hooks). Templates and MCP-argument reference docs live under `.claude/`; mock artifacts staged here use the `-mock` suffix convention before promotion to production destinations.
2. **Marketplace** — hosts the [`claudefigflow`](./plugins/claudefigflow/) plugin, an interactive, agentic creator that automates the workflow-authoring pipeline modeled on `anthropics/skills/skill-creator`.

See [`CLAUDE.md`](./CLAUDE.md) for the full development workflow.

## Quick start

```
# Add this repo as a Claude Code marketplace
claude plugin marketplace add C:/Users/McDon/Repos/Claude-Code-Workflow

# Install the claudefigflow plugin
claude plugin install claudefigflow@claude-code-workflow

# In a new Claude Code session, either:
/claudefigflow:workflow
# ...or just type: "I want to create a skill for X"
```

## Contributor setup (one-time per clone)

The repo enforces a sync invariant between `.claude/templates/` (workshop masters) and the plugin's bundled `references/` copies. A pre-commit hook blocks commits on drift. Install it via:

```
python -m pip install --user pre-commit
python -m pre_commit install
```

After any change to a master, run `python plugins/claudefigflow/scripts/sync_refs.py` and stage the synced copies in the same commit.
