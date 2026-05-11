# Artifact formats

Frontmatter spec and body requirements for each of the 4 Claude Code artifact types `claudefigflow` can author. This file is the single source of truth — `cfgflow-architect` writes against it, `cfgflow-structural-validator` and `scripts/validate_artifact.py` read against it.

## 1. Skill — `skills/<name>/SKILL.md`

### Directory layout

```
skills/<name>/
├── SKILL.md                # required
├── references/             # optional — on-demand docs
├── scripts/                # optional — helper scripts
├── agents/                 # OPTIONAL but discouraged — only loaded as prompt files; not auto-registered
└── assets/                 # optional — non-text resources
```

When the artifact is a skill inside a *plugin*, prefer hoisting any subagents to the plugin-root `agents/` directory rather than nesting them inside the skill — Claude Code's auto-discovery does not register nested subagent files.

### Frontmatter (YAML)

| Field | Required | Constraints | Notes |
|---|---|---|---|
| `name` | yes | lowercase kebab-case, ≤64 chars, must match directory name, no consecutive hyphens, no leading/trailing hyphens | Identity. |
| `description` | yes | ≤1024 chars | The trigger mechanism. Write in third person with verbatim phrase examples. |
| `version` | recommended | semver | Pin during active development to control update timing. |
| `license` | no | string | License name or path to a bundled `LICENSE.txt`. |
| `compatibility` | no | ≤500 chars | Tool/env requirements (e.g., "requires Node ≥18"). |
| `metadata` | no | object | Arbitrary key-value (author, tags). |
| `allowed-tools` | no | space-separated | Pre-approved tools (experimental; rarely needed). |
| `disable-model-invocation` | no | bool, default false | If true, skill only loads via explicit slash command. |

### Description rules (most important field)

- **Third person.** "This skill should be used when..." — NOT "I will help you...".
- **List verbatim trigger phrases.** Repeat the actual phrases users type. Fuzzy matching is real but listing exact phrases anchors it.
- **State scope clearly.** "Handles X, Y, Z" not vague "general assistance".
- **Lightly pushy.** Counteract Claude's tendency to under-trigger; phrase as "should be used when" not "may be used when".
- **No second person.** Do not address the user as "you".

### Body structure

Aim for ≤500 lines. Order:

1. **One-line overview** — what this skill orchestrates.
2. **When to engage** — extension of `description`; covers edge cases.
3. **Path conventions** (if it writes files) — `${CLAUDE_PLUGIN_ROOT}` vs `${CLAUDE_PLUGIN_DATA}`.
4. **Reference files** — pointers to on-demand resources with one-line "load when..." each.
5. **Subagent roster** (if it spawns subagents).
6. **Pipeline / procedure** — numbered phases. Each phase has: action, inputs, outputs, completion criterion.
7. **Style rules** (if it generates content).
8. **Failure modes** — what to do when X fails.
9. **Done definition** — concrete completion criteria.

Use imperative form. Explain *why* rather than shouting `ALWAYS`/`NEVER`.

---

## 2. Command — `commands/<name>.md`

Single flat markdown file. No directory.

### Frontmatter (YAML)

| Field | Required | Constraints | Notes |
|---|---|---|---|
| `description` | yes | ≤200 chars | Shown in `/help` and slash-menu. |
| `allowed-tools` | no | comma-separated, can scope with `(pattern:*)` | Restricts which tools the command may invoke. Example: `Read, Write, Bash(git:*)`. |
| `argument-hint` | no | string | Displayed next to the command in the slash menu. Example: `<file-path>`. |
| `model` | no | model id | Override default model for this command. |

### Body

The command body becomes the prompt when invoked. Variables:

- `$ARGUMENTS` — the raw string after the command name.
- `!<bash-command>` — shells out before the prompt is sent (use sparingly).

### Required body sections

1. **`## Your task`** — clear, autonomous instructions. The body must be runnable without further user input.
2. **Reference `$ARGUMENTS`** explicitly when the command takes input. Document what shape `$ARGUMENTS` should have.
3. **No ambiguity.** Commands run autonomously after invocation; the body cannot ask questions or wait for input (unlike a skill).

### Optional body sections

- **`## Context`** — pre-flight context gathering (e.g., `!git status`).
- **`## Examples`** — example invocations with expected outcomes.

---

## 3. Subagent — `agents/<name>.md`

Single flat markdown file. No directory.

### Frontmatter (YAML)

| Field | Required | Constraints | Notes |
|---|---|---|---|
| `name` | yes | lowercase kebab-case, must match filename | Used as `subagent_type` when spawning via Task. |
| `description` | yes | multi-line description with `<example>` blocks recommended | Used by orchestrator to decide delegation. |
| `tools` | no | comma-separated tool names | If omitted, subagent inherits parent's tools. Restrict for safety. |
| `model` | no | `sonnet` \| `opus` \| `haiku` \| specific id | Override; default inherits. |
| `color` | no | named color | Display tint in UI. |

### Description rules

- Include 2–3 `<example>` blocks per the developer-agent-template pattern: `<example>Context: ... user: '...' assistant: 'I'll use the X to ...'</example>`.
- State the agent's specialty in the first sentence ("specialized in X", "expert at Y").
- List trigger contexts in third person.

### Body structure

1. **Purpose** — one paragraph: "You are an expert X specializing in Y."
2. **Core Expertise / Capabilities** — bulleted list.
3. **Methodology / Principles** — how the agent approaches its work.
4. **Output Format** — explicit template the agent must produce.
5. **Constraints** — what it must NOT do (scope limits, output discipline).
6. **Rules** (optional) — invariants like "always cite sources" or "write summaries to .claude/research/".

---

## 4. Hook — `hooks/hooks.json` (+ optional `hooks/scripts/<name>.{ps1,sh}`)

### `hooks.json` schema

```json
{
  "hooks": {
    "<EventName>": [
      {
        "matcher": "<regex or literal>",
        "hooks": [
          {
            "type": "command",
            "command": "<shell-command-string>",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### Event names (Claude Code)

| Event | When | Stdin payload |
|---|---|---|
| `PreToolUse` | Before any tool call. Can block. | `{ tool_name, tool_input, session_id, transcript_path }` |
| `PostToolUse` | After tool call completes. | `{ tool_name, tool_input, tool_output, session_id, transcript_path }` |
| `UserPromptSubmit` | When user submits a prompt. Can modify context. | `{ prompt, session_id, transcript_path }` |
| `SessionStart` | Session start. Can inject context. | `{ session_id, hook_event_name }` |
| `SessionEnd` | Session end. | `{ session_id, transcript_path }` |
| `Stop` | When Claude finishes responding. | `{ session_id, transcript_path }` |
| `SubagentStop` | When a subagent finishes. | `{ session_id, subagent_type }` |
| `Notification` | UI notification. | `{ message, session_id }` |
| `PreCompact` | Before context compaction. | `{ session_id, transcript_path }` |

### Matcher rules

- For `PreToolUse`/`PostToolUse`: matches against `tool_name`. Use regex for `OR` (e.g., `Write|Edit`).
- For other events: matcher is usually omitted (all-match).
- Avoid catch-all matchers (`.*`) — too noisy.

### Hook output (stdout JSON)

```json
{
  "permissionDecision": "allow" | "deny" | "ask",
  "decision": "block" | "approve",
  "systemMessage": "string shown to Claude"
}
```

Or no output (exit 0 = allow, continue).

### Exit code semantics

- `0` = allow / continue. Stdout JSON may further refine.
- `2` = block. Stderr is shown to Claude as feedback.
- Anything else = error. Logged, hook ignored.

### Script-based hooks (when prompt-based isn't enough)

On Windows (this user's platform), default to PowerShell:

```json
{
  "type": "command",
  "command": "pwsh -NoProfile -File \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<name>.ps1\""
}
```

The script reads stdin as a JSON string:

```powershell
$input = [Console]::In.ReadToEnd()
$payload = $input | ConvertFrom-Json

# do work

# emit JSON or exit code
@{ permissionDecision = "allow" } | ConvertTo-Json
exit 0
```

For cross-platform (when targeted at a non-Windows repo), prefer:

```json
{
  "type": "command",
  "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<name>.sh\""
}
```

with a corresponding `.sh` reading via `cat - | jq ...`. The architect must ask the user for platform during intent capture in v1.

### Prompt-based hooks (preferred default)

```json
{
  "type": "command",
  "command": "claude --print 'Inspect the JSON on stdin and respond with {\"permissionDecision\":\"allow\"} unless the tool input contains <forbidden patterns>.'"
}
```

Lets Claude itself be the responder. Eliminates platform shell issues. Slower (round-trip to Claude) but vastly simpler.

---

## Validation rules (deterministic, enforced by `scripts/validate_artifact.py`)

Apply to all artifact types unless noted:

1. Frontmatter present and parses as valid YAML.
2. All required fields per the type above are present and non-empty.
3. `name` field (where required) matches `^[a-z][a-z0-9-]*[a-z0-9]$` and ≤64 chars.
4. `name` field matches the directory or filename.
5. `description` is ≤1024 chars (skill) / ≤200 chars (command) / no upper bound (subagent, but warn if >2000).
6. Body contains the expected required sections per type.
7. No absolute paths (`C:\\`, `/Users/`, `/home/`) anywhere in body.
8. No backslashes in paths inside body — forward slashes only.
9. (Hook only) `hooks.json` parses as valid JSON; all required schema fields present.
10. (Hook only) Matcher regex compiles.
11. (Skill only) `description` contains third-person language; warn (not fail) on second-person leaks.
12. (Skill only) Body ≤500 lines; warn if longer.

A validation failure on any rule 1-10 returns non-zero exit; warnings (11, 12) return zero but print to stderr.
