# Path resolution

How `claudefigflow` resolves filesystem destinations across the two operating modes. Every subagent that touches the filesystem reads this file.

## The two modes

### Targeted mode

The user wants the artifact to live in an **external repo**. Output destination is inside that repo's `.claude/` tree.

**Resolution algorithm:**

1. Ask the user for a target path.
2. Accept any of:
   - **Bare repo name** (e.g., `myapp`) → resolves to `~/Repos/myapp`. This user keeps all repos under `~/Repos` (i.e., `C:\Users\McDon\Repos\` on Windows; resolve via `os.path.expanduser("~")` in scripts).
   - **Relative path** (e.g., `./myapp` or `../sibling-repo`) → resolves against the current working directory.
   - **Absolute path** (e.g., `C:\Users\McDon\Repos\myapp` or `/c/Users/McDon/Repos/myapp`) → used as-is.
3. Normalize separators to forward slashes for storage; convert back to native separators only at filesystem-call time.
4. Validate:
   - Path exists. (If not, ask: create the directory? abort?)
   - Path is a directory.
   - Path contains a `.git/` subdirectory. (Warn if not — proceed if user confirms.)
5. Detect or create `.claude/`:
   - If `<target>/.claude/` exists → use it.
   - If not → ask user: create it? (Default yes.) If yes, create the four standard subdirs as needed (`skills/`, `commands/`, `agents/`, `hooks/`).
6. Detect `CLAUDE.md`:
   - If exists → leave it alone (the architect may suggest amendments, but never auto-edits).
   - If absent → offer to create a stub.

**Output destinations by artifact type:**

| Type | Destination |
|---|---|
| skill | `<target>/.claude/skills/<name>/SKILL.md` (+ optional siblings: `references/`, `scripts/`, `assets/`) |
| command | `<target>/.claude/commands/<name>.md` |
| subagent | `<target>/.claude/agents/<name>.md` |
| hook | `<target>/.claude/settings.json` (hook entry merged) + `<target>/.claude/hooks/scripts/<name>.{ps1,sh}` if script-based |

Hooks specifically: hooks live in `<target>/.claude/settings.json` under the `hooks` key — NOT a standalone `hooks.json`. Read the existing `settings.json`, deep-merge the new hook entry under `hooks.<EventName>[]`, write back. Never overwrite.

### Standalone mode

The user wants the artifact staged in this workshop repo for later promotion. Output destination is this repo's `.claude/` tree, with `-mock` suffix applied.

**Resolution algorithm:** No questions needed. Destination is always `${CLAUDE_PROJECT_DIR}/.claude/` where `${CLAUDE_PROJECT_DIR}` is this workshop repo's root. (When the plugin runs from inside this repo, `${CLAUDE_PROJECT_DIR}` is set automatically; when run from elsewhere, fall back to `os.getcwd()` and warn.)

**`-mock` suffix application by artifact type:**

| Type | Path with `-mock` |
|---|---|
| skill | `.claude/skills/<name>-mock/SKILL.md` (suffix on the directory) |
| command | `.claude/commands/<name>-mock.md` (suffix on the filename, before `.md`) |
| subagent | `.claude/agents/<name>-mock.md` (suffix on the filename, before `.md`) |
| hook | `.claude/hooks/<name>-mock-hooks.json` (standalone file, not merged into settings.json for staging) + `.claude/hooks/scripts/<name>-mock.ps1` if script-based |

For hooks in standalone mode, write a self-contained `<name>-mock-hooks.json` instead of merging into a real `settings.json`. This way the user can inspect it in isolation before promoting (at promotion time, the entry is merged into the final destination's `settings.json`).

The `name` field *inside* the frontmatter does **not** carry the `-mock` suffix — only the filename/directory does. The suffix exists purely as a "not yet production" marker on the filesystem. When the user promotes (drops `-mock`), the file moves but the frontmatter does not change.

## Staging directory

Before files are written to the final destination in either mode, the architect writes a dry-run copy to:

```
${CLAUDE_PLUGIN_DATA}/staging/<session-id>/<artifact-name>/
```

where `<session-id>` is a UTC timestamp like `2026-05-11T142301Z`. This lets the user see a full diff before committing to the destination. After approval, files move from staging to the resolved destination atomically (write to temp, rename).

`${CLAUDE_PLUGIN_DATA}` is a Claude-Code-managed directory that survives plugin updates. Resolve it from the env var at runtime; never hard-code.

## Eval workspace

Eval transcripts and intermediate scoring artifacts live at:

```
${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-<UTC-timestamp>/
  iteration-1/
    evals.json              # input test prompts + assertions
    eval-<id>/
      with_artifact.json
      baseline.json
      grading.json
    benchmark.json          # aggregate across all evals in this iteration
  iteration-2/              # only if Phase 10 description optimization runs additional iterations
    ...
```

Do **not** write eval workspaces inside the plugin install cache (`~/.claude/plugins/cache/...`) — that directory is wiped on `/plugin update`. Do **not** write them inside the target repo — pollutes the user's working tree. `${CLAUDE_PLUGIN_DATA}` is the only correct location.

## Path-discipline rules (enforced by validator)

Generated artifacts must obey these rules. The validator (`scripts/validate_artifact.py`) checks them deterministically:

1. **No absolute repo paths** in artifact body. No `C:\\Users\\...`, `/Users/...`, `/home/...`.
2. **Forward slashes only**. No `\\` in paths inside markdown bodies, JSON values, or shell commands. Native separators are used only at OS-call time in scripts.
3. **Use placeholders for plugin-shipped resources**. `${CLAUDE_PLUGIN_ROOT}` for read-only files inside the plugin, `${CLAUDE_PLUGIN_DATA}` for writable state. Never hard-code `~/.claude/plugins/cache/...`.
4. **Target-repo references use relative paths.** Inside an artifact written to `<target>/.claude/`, references to files in the target repo use paths relative to the target's root (e.g., `src/auth/login.ts` not `<target>/src/auth/login.ts`).

## In-place editing (modify mode)

When `operation_type == "modify"`, the destination is the artifact's existing location — no targeted-vs-standalone decision. The flow is:

1. **Stage the modified candidate** at `${CLAUDE_PLUGIN_DATA}/staging/<session-id>/<artifact-name>/`. Same staging discipline as create mode.
2. **Compute diff** via `scripts/diff_artifact.py summary` (structured) and `diff_artifact.py diff` (unified). Both run against the existing file.
3. **User-approves the diff.** Required gate.
4. **Apply atomically** via `scripts/diff_artifact.py apply <original> <staged>`:
   - Creates `<original>.pre-modify.bak`.
   - Writes candidate to `<original>.tmp`.
   - Atomic rename: `<original>.tmp` → `<original>`.
5. **Backup is preserved for one session.** Rollback: `cp <original>.pre-modify.bak <original>`.

For hooks living inside a parent `settings.json` or `hooks.json`, the apply step is different:
- Re-read the parent file.
- Locate the targeted hook entry (matching event + matcher + index — supplied by the loader).
- Replace only that entry in memory; preserve all other entries verbatim.
- Write back the parent file.
- The `.pre-modify.bak` is of the entire parent file, not just the hook entry.

The `-mock` suffix discipline is preserved across modifications: a modify operation on `.claude/skills/my-skill-mock/SKILL.md` writes back to the same path (still has `-mock` suffix). Promotion (drop the suffix) is a separate explicit step.

## Settings.json merge contract

When writing a hook (or any other settings change) into an existing `settings.json`:

1. Read the existing file.
2. Parse as JSON. (If the file does not exist, treat as `{}`.)
3. Deep-merge the new entry under the appropriate top-level key (e.g., `hooks.<EventName>[]` — append, do not replace the array).
4. Validate: no duplicate hook entries (same `matcher` + same `command`). If duplicate detected, surface to user; ask which to keep.
5. Write back with 2-space indentation and trailing newline.

Never use `JSON.stringify(merged, null, 4)` (4-space) — Claude Code's own config tooling uses 2-space and we want byte-clean diffs.

Never overwrite without merging. Never delete keys the user added by hand.

## Path-related failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Plugin install fails after running locally | Marketplace relative path doesn't resolve in cache | Document `/plugin marketplace update` and re-install. |
| Artifact written to wrong location | `${CLAUDE_PROJECT_DIR}` not set | Fall back to `os.getcwd()` and warn user. |
| Eval workspace disappears between runs | Path used `~/.claude/plugins/cache/` instead of `${CLAUDE_PLUGIN_DATA}` | Always use the env var. |
| Hook fires but Claude ignores output | Shape mismatch — likely `permissionDecision` typo or wrong key | `test_hook.py` should have caught this; re-run validation. |
| Generated file has backslashes | Architect violated forward-slash rule | Validator should fail; if not, add the path to validator's regex. |
