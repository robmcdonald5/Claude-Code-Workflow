---
description: Sync repo-level master template and MCP-argument files into the claudefigflow plugin's references/ directory. Run before committing changes to .claude/templates/ or .claude/mcp-arguments/.
argument-hint: [--check]
---

## Your task

Run the claudefigflow refs-sync script. If `$ARGUMENTS` contains `--check`, run in check-only mode (no copy; exit non-zero on drift); otherwise perform the sync.

### Step 1 — Locate the script

The script lives at `${CLAUDE_PLUGIN_ROOT}/scripts/sync_refs.py`.

### Step 2 — Run it

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/sync_refs.py $ARGUMENTS
```

### Step 3 — Report

If the run succeeded:
- Show the JSON summary (copied/skipped/removed counts per pair).
- If anything was copied or removed, remind the user to `git add plugins/claudefigflow/skills/workflow-creator/references/` and commit.

If the run failed (check mode, drift detected):
- Show which files drifted.
- Recommend running without `--check` to sync.

### Step 4 — Caveat

After syncing and committing, the plugin's installed cache may be stale until `/plugin marketplace update` runs. Mention this if the user is testing locally.

## Constraints

- Do not edit `.claude/templates/` or `.claude/mcp-arguments/` here — those are masters; edits happen elsewhere.
- Do not modify the script behavior; this command is a thin wrapper.
