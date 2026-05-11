---
name: workflow-creator
description: This skill should be used when the user asks to "create a skill", "build a new skill", "make a slash command", "create a command", "add a command for X", "write an agent", "make me an agent", "add a hook", "create a hook for Y", "create a Claude Code workflow", "generate a SKILL.md", OR when the user asks to "modify this skill", "update this command", "edit this agent", "tune this hook", "improve this skill's description", "add a phase to this skill", "tighten this agent's tool list", "change the matcher on this hook", or otherwise requests authoring OR editing a Claude Code artifact (skill, command, subagent, or hook). Handles create mode (new artifact, targeted-repo or standalone-mock) and modify mode (existing artifact with diff + differential evals). Runs interactive intent capture, parallel research subagents, structural validation, automated evals with grader subagents, and description optimization for trigger reliability.
version: 0.1.0
---

# workflow-creator

Orchestrates the end-to-end authoring of a new Claude Code artifact (skill, command, subagent, or hook) using parallel research, structural validation, and evaluation loops modeled on `anthropics/skills/skill-creator`.

## When to engage

Activate when the user expresses intent to create a new Claude Code artifact. Trigger phrases include but are not limited to those listed in `description`. Engage even if the user phrases the request loosely (e.g., "I want Claude to do X automatically when Y happens" → likely a hook; "Build me something that helps with Z when I ask about Z" → likely a skill).

If unsure which artifact type the user wants, ask in Phase 1; do not assume.

## Path conventions

All paths in this skill follow the rules in `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/path-resolution.md`. Never embed absolute repo paths in artifact bodies — only the placeholders `${CLAUDE_PLUGIN_ROOT}` (read-only resources) and `${CLAUDE_PLUGIN_DATA}` (writable state: staging, eval workspaces).

## Reference files (load on demand)

- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/artifact-formats.md` — frontmatter spec and required body sections for each of the 4 artifact types. Load when drafting frontmatter or validating output.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/path-resolution.md` — target-path resolution, `-mock` suffix rules, staging and eval-workspace locations. Load at Phase 2.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/creation-workflow.md` — detailed phase-by-phase reference for create mode. Load when uncertain how a phase should proceed in create mode.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/modification-workflow.md` — detailed phase-by-phase reference for modify mode (load existing → diff → differential evals → apply edit). Load at Phase 0 when `operation_type == "modify"`.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/eval-protocol.md` — JSON shape for eval inputs/outputs, grader rubric. Load at Phase 7.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/templates/` — synced master templates for each artifact type (researcher-agent-template.md, developer-agent-template.md, basic-single-action-command.md, etc.). Load at Phase 4 when selecting a base template.
- `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/mcp/` — MCP tool argument references (github, playwright, ref, semgrep, shadcn-ui-svelte). Load at Phase 1 when the user mentions MCP-backed workflows.

## Subagent roster

All subagents are registered at `plugins/claudefigflow/agents/` with the `cfgflow-` prefix:

- `cfgflow-intent-interviewer` — runs Phase 1 dialog (operation type, artifact type, scope, behavior)
- `cfgflow-existing-artifact-loader` — modify mode only; reads and parses the artifact being edited (Phase 2)
- `cfgflow-anthropic-pattern-researcher` — fetches current Anthropic patterns (Phase 3, parallel)
- `cfgflow-target-context-fetcher` — scans target repo when in targeted mode (Phase 3, parallel)
- `cfgflow-existing-workflow-scanner` — checks naming collisions and similar artifacts (Phase 3, parallel)
- `cfgflow-architect` — designs files (create) or computes a diff (modify); drafts frontmatter; selects base template (Phase 4)
- `cfgflow-structural-validator` — frontmatter/body/path validation (Phase 6)
- `cfgflow-eval-runner` — spawned twice in parallel per test prompt (Phase 8)
- `cfgflow-grader` — grades eval outputs against assertions; differential mode for modify (Phase 9)
- `cfgflow-description-optimizer` — runs description-tuning loop (Phase 10)

Spawn subagents via the Task tool with `subagent_type` matching the registered agent name (without the file extension). For Phase 3 and Phase 8 specifically, spawn all subagents in a single turn for parallelism.

## Pipeline

### Phase 0 — Operation type

Determine `operation_type`:

- If the user invoked `/claudefigflow:modify` → `operation_type = "modify"` (path may also be set from `$ARGUMENTS`).
- If the user invoked `/claudefigflow:workflow` or matched on create-flavored trigger phrases ("create a skill", "build a new command", etc.) → `operation_type = "create"`.
- If matched on modify-flavored phrases ("update this skill", "edit this hook", etc.) → `operation_type = "modify"`.
- If ambiguous → ask once in Phase 1: "Creating a new artifact or modifying an existing one?"

For `operation_type = "modify"`, load `${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/references/modification-workflow.md` for the modify-specific phase details. The rest of this SKILL.md describes the create flow; modify diverges at Phases 2, 4, 5, 7-9 per that reference.

### Phase 1 — Intent capture

Engage `cfgflow-intent-interviewer` (or run directly if the dialog is straightforward). Collect:

- **Operation type:** confirmed in Phase 0; the interviewer carries it forward.
- **Artifact type:** `skill` | `command` | `subagent` | `hook`. If unclear, ask. Reference `references/artifact-formats.md` to explain each. In modify mode, infer from the artifact at `artifact_path` (the loader will confirm).
- **Name (create mode):** lowercase kebab-case, no consecutive hyphens, ≤64 chars. **In modify mode** the name is locked to the existing artifact's `name` unless the user explicitly asks to rename (warn about downstream consequences).
- **What it does (create mode) / change intent (modify mode):** one paragraph. In create mode, used for `description` engineering. In modify mode, describes the delta — "make it trigger on phrase X too", "fix bug in Phase 4", etc.
- **Trigger conditions:** verbatim phrases or scenarios that should activate it. Critical for skills (autonomous trigger) and subagents (delegation matching).
- **Expected output / behavior:** what the user expects to see when it runs.
- **MCP dependencies:** does it call any MCP tools? If yes, which? Load `references/mcp/<server>.md` for relevant parameter shapes.
- **Hook-only:** event type (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, `SessionStart`, `SessionEnd`, `Notification`, `SubagentStop`), matcher pattern, and whether prompt-based (default) or script-based.
- **Modify-mode only:** `artifact_path` (resolved), `scope_hint` (frontmatter | body | both | bundled-resources), `reversibility` (experimental | major-rewrite).

### Phase 2 — Mode resolution / Load existing

#### Create mode

Ask the user: **targeted** (write into an external repo) or **standalone** (stage in this workshop repo with `-mock` suffix)?

- If **targeted**:
  - Prompt for target path. Accept a bare name (e.g., `myapp` → resolves under `~/Repos/myapp` on this user's system) or an absolute path.
  - Verify the target exists. Verify it is a git repo (warn if not). Check for existing `.claude/` (use if present; offer to create if not).
  - Output destination: `<target>/.claude/{skills,commands,agents,hooks}/`.
- If **standalone**:
  - Output destination is this repo's `.claude/{skills,commands,agents,hooks}/` with `-mock` suffix on the artifact name.
  - For skills: `-mock` suffix on the directory (e.g., `my-skill-mock/SKILL.md`).
  - For commands, agents: `-mock` suffix on the filename.
  - For hooks: stage as `.claude/hooks/<name>-mock-hooks.json` and any scripts as `.claude/hooks/scripts/<name>-mock.ps1`.

Read `references/path-resolution.md` for the exact rules.

#### Modify mode

Skip target/standalone selection — the destination IS the loaded artifact's location.

Engage `cfgflow-existing-artifact-loader` with `artifact_path`. It returns the structured baseline (frontmatter, body sections, bundled resources, path classification). The architect consumes this baseline directly in Phase 4.

If the loader returns an error (path not found, type ambiguous, hook entry not found), surface to the user and stop. Do not proceed without a valid load.

### Phase 3 — Research (parallel)

Spawn the following subagents in a single turn (they will run in parallel):

1. `cfgflow-anthropic-pattern-researcher` — instructed with the chosen artifact type. Returns current canonical patterns from official Anthropic sources.
2. `cfgflow-target-context-fetcher` (only if Phase 2 chose targeted) — scans the target repo's structure, existing `.claude/`, CLAUDE.md, language/framework markers. Returns context summary.
3. `cfgflow-existing-workflow-scanner` — checks the chosen destination for naming collisions and surveys similar existing artifacts (target + global `~/.claude/` + this workshop repo). Returns: name-collision flag, list of similar artifacts.

Wait for all three to complete before Phase 4.

### Phase 4 — Architect

Engage `cfgflow-architect` with: artifact type, intent capture results, research findings, destination path, AND (modify mode only) the loaded baseline from Phase 2.

#### Create mode

Architect:

1. Selects a base template from `references/templates/`.
2. Drafts the artifact's frontmatter (using `references/artifact-formats.md` as the spec).
3. Designs the body / structure.
4. Lists bundled resources (if any — only relevant for skills).
5. Produces a complete file-tree plan with file paths and approximate contents.

#### Modify mode

Architect:

1. Identifies which parts of the loaded baseline to change based on `change_intent` + research findings.
2. Preserves untouched parts verbatim (whitespace, ordering, comments) unless the change explicitly affects them.
3. Writes a modified candidate to `${CLAUDE_PLUGIN_DATA}/staging/<session-id>/<artifact-name>/`.
4. Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py summary <original> <staged-candidate>` for the structured change summary.
5. Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py diff <original> <staged-candidate>` for the unified diff display.
6. If the summary says `is_noop: true`, stop and ask the user to clarify intent.

Present the plan/diff to the user for approval. Iterate if requested.

### Phase 5 — Write / Apply edit

#### Create mode (write)

Generate the actual files. Write to `${CLAUDE_PLUGIN_DATA}/staging/<session-id>/` first as a dry-run staging step; show the user a diff against the final destination; then on approval move files to the final destination from Phase 2.

Rules:
- Forward slashes only in all file content (never `\\`).
- When writing into an existing `.claude/settings.json` or `hooks/hooks.json`, **merge** with the existing contents (read, merge, write) — never overwrite.
- Generated artifacts must use `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` placeholders, not absolute paths, when referring to plugin-shipped resources (rare in user-generated artifacts but enforced for consistency).

#### Modify mode (apply edit)

After user approval of the diff:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/diff_artifact.py apply <original-path> <staged-candidate-path>
```

The script creates `<original>.pre-modify.bak` (rollback artifact) then atomically replaces the original. For hooks inside `settings.json`/`hooks.json`, re-read the parent file, replace only the targeted entry (matching event + matcher + index), and write back; never touch unrelated entries.

### Phase 6 — Structural validation

Run two checks in parallel:

1. `cfgflow-structural-validator` (LLM-based semantic check): does the body cover required sections? Is the description well-engineered for triggering? Are examples present and useful?
2. `python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/scripts/validate_artifact.py <artifact-path>` (deterministic check): frontmatter required fields present, name conventions (lowercase kebab-case, length), max-length compliance, path-separator hygiene, no absolute paths in body, settings.json merge correctness.

If either fails, return to Phase 4 with the issues; do not proceed.

### Phase 7 — Eval setup (skill / command / subagent only)

For artifact type **`hook`**, skip to "Phase 7-eq" below.

Engage the user briefly: "I'll generate 6 test prompts to evaluate this artifact. Want to add or override any?" Auto-generate test prompts from intent capture data — at least 3 positive (should trigger / produce correct output) and 3 negative (should NOT trigger / should refuse / should be ignored).

Save evals to:
```
${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-<UTC-timestamp>/iteration-1/evals.json
```

Format defined in `references/eval-protocol.md`.

### Phase 8 — Parallel eval runs (skill / command / subagent only)

For each test prompt in `evals.json`, spawn `cfgflow-eval-runner` **twice in the same turn**. The treatment vs control assignment differs by `operation_type`:

- **Create mode (`eval_mode: "creation"`):**
  - `mode: with_artifact` — the new artifact loaded into context.
  - `mode: baseline` — control, no artifact.
- **Modify mode (`eval_mode: "differential"`):**
  - `mode: with_artifact` (treatment) — the POST-modification version loaded.
  - `mode: baseline` (control) — the PRE-modification version loaded (from `<original>.pre-modify.bak` or the staging snapshot).

Both runs receive the same prompt. Save outputs to:
```
${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-<ts>/iteration-1/eval-<id>/
  with_artifact.json
  baseline.json
```

Spawning all runs in a single turn is required for parallelism; do not stagger.

### Phase 9 — Grade & aggregate (skill / command / subagent only)

Engage `cfgflow-grader` once with the full eval workspace path. Grader:

1. Reads each `with_artifact.json` and `baseline.json` pair.
2. Scores each against the assertions defined in `evals.json`.
3. Writes `grading.json` per eval.

Then run:
```
python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/scripts/aggregate_benchmark.py \
  ${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-<ts>/iteration-1/
```

Output: aggregate score, lift over baseline, per-eval breakdown.

**Modify-mode decision rule** (in addition to creation's done-definition):

- `lift > 0` and `treatment >= max(baseline, 0.75)` → modification accepted.
- `lift > 0` but `treatment < 0.75` → modification accepted with a warning ("improvement but artifact below quality threshold").
- `lift <= 0` → modification REJECTED. Offer rollback: `cp <backup> <original>`.

The aggregate `benchmark.json` adds a `decision` field for modify-mode runs.

### Phase 10 — Description optimization (skill / command / subagent only, separate loop)

Only run if the user wants to optimize trigger reliability (ask). Engage `cfgflow-description-optimizer`:

1. Generate 20 realistic trigger queries (should activate) and 20 distractors (should NOT activate). Use a 60/40 train/test split.
2. Run `python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/scripts/optimize_description.py` for up to 5 iterations.
3. Per iteration: re-write the `description` field, re-run trigger evals, score precision/recall.
4. Keep the best-scoring description. Write back to the artifact frontmatter.

### Phase 11 — Package / install instructions

Print exactly:

```
✓ Artifact written: <final-path>
✓ Eval workspace: <eval-workspace-path> (skill/command/agent only)
✓ Score: <score>/100, lift over baseline: <lift>% (skill/command/agent only)

Next steps:
- (targeted mode) Restart Claude Code in <target-repo> to load the new artifact.
- (standalone mode) To promote: drop the `-mock` suffix and move to <production-destination>.
- (plugin authors) Run `/plugin marketplace update` then reinstall claudefigflow to refresh the cache.
```

---

## Hook-specific substitution (replaces Phases 7–10 for `hook` artifact type)

Hooks have no LLM behavior to grade. Substitute:

### Phase 7-eq — Synthetic input generation

Generate one synthetic JSON input fixture per hook-event variation, matching the event schema (load `references/artifact-formats.md` for the schema). Cover: tool-name matcher hit, tool-name matcher miss, malformed payload, empty payload. Save to `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<hook-name>-<ts>/fixtures/`.

### Phase 8-eq — Execute hook with fixtures

Run `python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/scripts/test_hook.py <hook-config-path> <fixtures-dir>`. The script:

1. Reads the hook configuration.
2. For each fixture, invokes the hook command (e.g., `pwsh -NoProfile -File <script.ps1>` on Windows) with the fixture piped to stdin.
3. Captures stdout, stderr, exit code.
4. Writes results to `<eval-workspace>/results/<fixture-id>.json`.

### Phase 9-eq — Shape and exit-code validation

The same `test_hook.py` script then validates:

- Output JSON shape: required keys (`permissionDecision` for `PreToolUse`, `decision` for any blocker, optional `systemMessage`).
- Exit code semantics: `0` = allow, `2` = block with stderr-as-feedback, anything else = error.
- Security lints: no `eval`, no unquoted variable expansion, no path traversal patterns.
- Output: `summary.json` with per-fixture pass/fail and aggregate.

### Phase 10-eq — Matcher tuning

For hooks with regex matchers, ask: "Run matcher tuning?". If yes, run `python ${CLAUDE_PLUGIN_ROOT}/skills/workflow-creator/scripts/test_hook.py --tune-matcher <hook-config-path>` against a corpus of tool names — measures precision/recall and suggests refinements.

**Default new hooks to prompt-based** (use Claude itself as the responder) wherever the use case permits. This avoids the Bash-vs-PowerShell platform problem entirely. Only fall back to script-based when the action is genuinely deterministic (file moves, lint runs, shell-only operations).

---

## Per-artifact-type branching

Phases 1–6 are universal. Phases 7–10 differ:

| Artifact | Phase 7  | Phase 8  | Phase 9   | Phase 10 |
|----------|----------|----------|-----------|----------|
| skill    | LLM eval | parallel | grader    | description optimizer |
| command  | LLM eval | parallel | grader    | description optimizer (lighter) |
| subagent | LLM eval | parallel | grader    | description optimizer |
| hook     | synthetic input fixtures | `test_hook.py` execute | shape + exit-code validation | matcher tuning |

For **commands**, description optimization tunes the `description` frontmatter field for slash-menu discoverability — less impactful than for skills (commands are explicit), but still useful.

For **subagents**, description optimization tunes for delegation-trigger reliability when the orchestrator decides whether to dispatch.

---

## Style rules for generated artifact bodies

These apply to the content the architect writes for the new artifact, not to this SKILL.md:

- Imperative form for instructions.
- Explain *why* rather than shouting `ALWAYS`/`NEVER`.
- Output format blocks use explicit templates introduced with "Use this exact template:".
- Examples use labeled `Input:` / `Output:` pairs.
- Keep under 500 lines; if longer, split body across `references/<topic>.md` files.
- All "when to use" information belongs in `description`, not the body.

---

## Failure modes and recovery

- **Activation does not trigger** on test phrases → return to Phase 10 (description optimization).
- **Validation fails repeatedly** → re-engage `cfgflow-intent-interviewer` to re-clarify intent; the architect may be working from a wrong premise.
- **Eval scores are low** → inspect grader output for systematic issues; iterate Phase 4 → 8 with refined architecture.
- **Hook execution errors on fixtures** → most likely a path or shell-escaping issue; check forward-slash discipline.
- **`settings.json` merge conflict** → never overwrite; surface conflict to user and ask which entry wins.

---

## Done definition

An artifact is "done" when:

1. Files exist at the destination from Phase 2.
2. `validate_artifact.py` exits 0.
3. (skill/command/subagent) Aggregate eval score ≥ 80/100 with positive lift over baseline.
4. (hook) All synthetic-input fixtures pass shape and exit-code checks.
5. Phase 11 install instructions have been printed.

Anything short of all five is in-progress.
