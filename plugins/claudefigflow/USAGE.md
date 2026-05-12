# claudefigflow — Usage

Complete reference for the plugin's commands, auto-trigger phrases, and end-to-end workflows.

## Quick reference

| Command | Purpose | Mode |
|---|---|---|
| `/claudefigflow:workflow` | Create a new artifact (skill, command, subagent, or hook) | Interactive |
| `/claudefigflow:modify <path>` | Edit an existing artifact with diff + differential evals | Interactive |
| `/claudefigflow:flowaudit [<path>]` | Audit a target repo for workflow opportunities; read-only | Interactive |
| `/claudefigflow:workflow-eval <path>` | Re-run evals on an existing artifact (read-only) | Interactive |
| `/claudefigflow:sync-refs [--check]` | Sync workshop masters into plugin references | One-shot |

Plus two autonomous skills:

- `workflow-creator` — handles **create** and **modify**; auto-triggers from natural-language authoring/editing phrases.
- `flow-auditor` — handles **audit**; auto-triggers from natural-language discovery/opportunity-mining phrases.

See [Auto-trigger phrases](#auto-trigger-phrases) for the trigger surfaces.

---

## `/claudefigflow:workflow` — Create a new artifact

### Synopsis

```
/claudefigflow:workflow
/claudefigflow:workflow <short intent description>
```

Hands control to the `workflow-creator` skill in **create mode**. Runs the full 11-phase pipeline: intent capture → mode resolution → parallel research → architect → write → validation → evals → description optimization → install instructions.

### When to use

You want to author a brand-new Claude Code artifact from scratch. The artifact will be either:

- Written into an external target repo's `.claude/` (targeted mode), or
- Staged in this workshop repo's `.claude/` with `-mock` suffix for later promotion (standalone mode).

The skill asks targeted-vs-standalone interactively — no flag needed.

### Arguments

`$ARGUMENTS` is optional. If supplied, it becomes a hint for Phase 1 intent capture. Examples:

```
/claudefigflow:workflow                              # full interactive flow
/claudefigflow:workflow skill for code reviews       # pre-seeds artifact type + intent
/claudefigflow:workflow hook on PostToolUse          # pre-seeds artifact type + event
```

### What it will ask you

In order, the intent-interviewer collects:

1. **Artifact type** — skill, command, subagent, or hook (if not inferable from args).
2. **Name** — lowercase-kebab-case, ≤64 chars. The interviewer validates and re-prompts on invalid names.
3. **What it does** — one paragraph; used for description engineering and base-template selection.
4. **Trigger phrases / conditions** — verbatim phrases users will type (skills), `<example>` block contexts (subagents), or slash-menu invocation (commands).
5. **Expected output** — what the user expects to see when it runs.
6. **MCP dependencies** — optional; references `.claude/mcp-arguments/` if any.
7. **Mode** — targeted (external repo path) or standalone (`-mock` here).
8. **Hook-only fields** — event type, matcher, prompt-based vs script-based.

### What it produces

- Generated files in the resolved destination (target/.claude/ or this repo's .claude/ with `-mock`).
- Eval workspace at `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact>-<UTC-ts>/` with `evals.json`, per-eval `with_artifact.json` + `baseline.json` + `grading.json`, and aggregate `benchmark.json`.
- Optimized description (if Phase 10 ran) written back to the artifact's frontmatter.
- Installation/promotion instructions printed at the end.

### Done definition

An artifact is considered done when:

1. Files exist at destination.
2. `validate_artifact.py` exits 0.
3. (skill/command/subagent) Aggregate eval score ≥ 0.80, positive lift over baseline, no false positives on negative evals.
4. (hook) All synthetic-input fixtures pass shape + exit-code checks.
5. Phase 11 install instructions printed.

### Common pitfalls

- **Description too vague** — Phase 10 description optimizer can fix some of this, but starting with strong verbatim trigger phrases in your intent saves iterations.
- **Name collision** — `cfgflow-existing-workflow-scanner` flags conflicts in Phase 3; rename early to avoid wasted work.
- **MCP dependency forgotten** — surface it in Phase 1 so the architect bundles the right `references/mcp/<server>.md` excerpt.

---

## `/claudefigflow:modify` — Edit an existing artifact

### Synopsis

```
/claudefigflow:modify <path>
/claudefigflow:modify <path> --event PostToolUse --matcher "Write|Edit"   # for hooks inside settings.json
/claudefigflow:modify                                                       # ask interactively for the path
```

Hands control to the `workflow-creator` skill in **modify mode**. Loads the existing artifact, computes a diff against a modified candidate, runs differential evals (post-mod vs pre-mod on the same prompts), atomically applies on approval with a `.pre-modify.bak` rollback artifact.

### When to use

You want to change something about an artifact that already exists. Common cases:

- Add a new trigger phrase to a skill's description.
- Tighten a subagent's `tools` list.
- Add or refine a body section.
- Change a hook's matcher regex.
- Fix a bug in a procedural step.
- Add a bundled reference file alongside a skill.

If you want to drop the `-mock` suffix and promote to production, that's a manual move; use modify for content changes.

### Arguments

`<path>` accepts:

- Skill directory: `path/to/.claude/skills/<name>/` → modifies the `SKILL.md` inside.
- Command file: `path/to/.claude/commands/<name>.md`.
- Subagent file: `path/to/.claude/agents/<name>.md`.
- Hook reference: a `settings.json` or `hooks.json` path plus `--event <EventName>` and optionally `--matcher "<regex>"` or `--index <int>` to disambiguate which hook entry.

Bare names (no slashes) are resolved as `~/Repos/<name>/.claude/...` when context allows; otherwise the interviewer asks.

### What it will ask you

1. **Change intent** — one paragraph describing the delta. Not "what does it do" — what should be different after the edit.
2. **Scope hint** — frontmatter only, body only, both, or bundled resources.
3. **Reversibility expectation** — experimental tweak (default) or major rewrite.
4. **Hook clarifiers** — if multiple hook entries match, you'll be asked which to target.

The artifact path is locked at invocation; the interviewer does not ask you to re-supply it.

### What it produces

- **A unified diff** and a **structured change summary** (frontmatter fields changed, body sections added/removed/changed, line delta) shown before any write.
- **`<file>.pre-modify.bak`** — verbatim copy of the original, preserved for one session.
- **Modified file** at the original path (atomic rename after staging).
- **Differential eval workspace** at `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact>-<UTC-ts>/iteration-1/` with `eval_mode: "differential"`.
- **Modification report** with accept/reject decision and rollback hint.

### Decision rule (modify mode)

The grader's verdict on each modification:

| Condition | Decision |
|---|---|
| Lift > 0 AND treatment ≥ max(baseline, 0.75) | **accept** |
| Lift > 0 but treatment < 0.75 | **accept-with-warning** (improvement but still below quality bar) |
| Lift ≤ 0 | **reject** (offer rollback) |

For hooks, evals are replaced with `test_hook.py` shape + exit-code validation on synthetic input fixtures.

### Rollback

After any modification:

```
cp <file>.pre-modify.bak <file>
```

The backup is preserved for the session. Rename it to keep longer-term, or commit before the next modify run if you want git to be your rollback.

### Common pitfalls

- **Renaming via modify** — if you change the `name` field, downstream paths (slash command paths, delegation triggers, file locations) shift. Modify mode warns you; consider creating a new artifact and deleting the old one instead.
- **No-op detected** — the architect ran the diff and found nothing changed. Usually means the change intent was too vague; clarify what specifically should differ.
- **Hook entry not found** — multiple `hooks.json` entries match your matcher pattern; supply `--index <int>` to disambiguate.
- **Forgetting to stage the bundled resource** — if you ask the architect to add a new reference file alongside a skill, the apply step needs to write that file too, not just SKILL.md. The architect handles this; verify in the diff before approving.

---

## `/claudefigflow:flowaudit` — Audit a target repo for workflow opportunities

### Synopsis

```
/claudefigflow:flowaudit
/claudefigflow:flowaudit <target-path>
/claudefigflow:flowaudit <target-path> --depth quick|standard|deep
/claudefigflow:flowaudit <target-path> --focus skill,command,subagent,hook,claude_md,mcp
```

Hands control to the `flow-auditor` skill. Scans the target repo with two parallel subagents (`cfgflow-target-context-fetcher` and `cfgflow-repo-signal-scout`), then synthesizes a tiered Markdown opportunity report via `cfgflow-opportunity-synthesizer`. **Read-only on the target.** Produces recommendations only — does not build anything.

### When to use

You want to discover what Claude Code artifacts a repo could benefit from before knowing exactly what to build. Common cases:

- New codebase you've just adopted — what should the team standardize via Claude Code?
- Mature repo with growing manual procedures — what should be automated?
- Pre-onboarding step before running `/claudefigflow:workflow` on specific opportunities.
- Health-check on a repo that already has some `.claude/` content — what's missing? what's redundant?

If you already know exactly which artifact you want to build, skip the audit and use `/claudefigflow:workflow` directly.

### Arguments

- **`<target-path>`** (optional) — bare name resolves under `~/Repos/<name>`; relative path resolves against the current working directory; absolute path used as-is. If omitted, the skill asks interactively.
- **`--depth quick|standard|deep`** (optional, default `standard`) — controls scan exhaustiveness:
  - `quick`: ≤2 min, repo root + 2 levels deep, 5 high-signal files read end-to-end.
  - `standard`: ≤5 min, 4 levels deep, 15 files end-to-end.
  - `deep`: ≤10 min, 6 levels deep, 40 files end-to-end, broader grep coverage.
- **`--focus <comma-separated-types>`** (optional, default all) — restrict to listed artifact types. Allowed: `skill`, `command`, `subagent`, `hook`, `claude_md`, `mcp`.

### What it will ask you

In order, the auditor collects (in 3-5 questions, fewer when arguments are supplied):

1. **Target path** — if not in `$ARGUMENTS`.
2. **Focus** — which artifact types to consider; default `all`. Matches the `--focus` flag.
3. **Depth** — `quick`, `standard`, or `deep`; default `standard`.
4. **Hints** (optional) — free-form bias text like "CI-related opportunities", "anything PR-review-flavored", "repetitive frontend work". Soft weighting on which signal categories the scout spends extra time on and the synthesizer's tier-boost rule.

### What it produces

- **Markdown report** at `${CLAUDE_PLUGIN_DATA}/audit-reports/<repo-basename>-<UTC-ts>/audit.md`. Tiered (High / Medium / Low) by impact, with file:line evidence and suggested `/claudefigflow:workflow` build commands.
- **JSON summary** captured by the orchestrator: tier counts, by-type counts, and a `candidates_for_workflow_queue` list of buildable opportunities.
- **Inline chat display** of the report (full report for short ones; structured + High-tier for long ones, with offer to print Medium/Low on request).
- **Optional triage prompt** — asks if you'd like to queue any opportunities for `/claudefigflow:workflow`; prints the build commands verbatim but does not auto-invoke.

### Classification

Each opportunity is classified against the canonical Anthropic decision table (from `code.claude.com/docs/en/features-overview`), enumerated verbatim in `${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/references/audit-protocol.md`. The shortest version:

| Trigger condition | Artifact type |
|---|---|
| Repeated multi-step prompt-pasting; Claude decides HOW | Skill |
| Explicit shortcut for a known procedure (`/foo`) | Command |
| Specialized recurring task that floods main context | Subagent |
| Rule that must hold every time, no exceptions | Hook |
| Convention Claude keeps getting wrong twice | CLAUDE.md addition |
| Bridge to an external system not yet integrated | MCP (flag only; out of v1 build scope) |

Disambiguation rules (also in `audit-protocol.md`) handle ambiguous cases — e.g., "must happen every time" always lands as a hook, not a skill.

### Tier rules

- **High** — ≥3 signal occurrences OR aligns with explicit CLAUDE.md value; frequent activity; no existing artifact covers it; buildable in ≤3 hours.
- **Medium** — 1-2 signals; helpful but not critical; partial overlap with existing automation acceptable.
- **Low** — single-signal or speculative; included for transparency.

Tier downgrades apply when behavioral overlap with an existing artifact exists, the repo is very young, or the recommendation depends on an external service.

### Output Markdown structure

The report has a fixed top-level structure:

1. Header (target, focus, depth, timestamp, existing-artifact count).
2. Summary (2-3 sentences + tier × type counts table).
3. High-value opportunities (one entry per cluster: decision criterion, rationale, evidence, suggested name/trigger/effort, build command).
4. Medium-value opportunities (same template).
5. Low-value opportunities (same template).
6. Already covered (skipped) — opportunities that overlap with existing `.claude/` artifacts.
7. Patterns observed but not classified.
8. Files scanned (capped at 30).

Full template in `${CLAUDE_PLUGIN_ROOT}/skills/flow-auditor/references/audit-protocol.md`.

### Decision rule

There is no automatic accept/reject decision. The audit produces recommendations; you decide whether to build. The Phase 6 triage step lets you queue opportunities by ID (e.g., `H1, M3`) — the auditor prints the corresponding `/claudefigflow:workflow ...` commands but never auto-invokes them.

### Read-only guarantees

- No writes to the target repo. Ever.
- No reading of `.env*` file contents (filenames only — may contain secrets).
- No external network calls beyond what the target-context-fetcher already does.
- The report lives in plugin data, not the target's working tree.

### Common pitfalls

- **Audit recommends something already covered** — check the "Already covered (skipped)" section; the target-context-fetcher detected the overlap but the synthesizer still emitted the cluster for transparency. The "skip_existing" marker tells you it's a duplicate, not a new opportunity.
- **High-value list is empty** — usually means the repo is too young (no CI, sparse docs, no CLAUDE.md). Try `--depth deep` or add a `--focus` hint based on what you know about the team's pain points.
- **Citations point at the wrong line** — the signal scout aggregates frequency across files; the cited line is one example. Check sibling lines in the same file for context.
- **Re-audit doesn't surface new opportunities** — the report directory is timestamped, so re-runs produce fresh reports. If the repo hasn't changed, the recommendations will be similar; that's expected, not a bug.
- **Audit asks to build something out of v1 scope** (full plugin, MCP server) — these are "flag-only" recommendations. They land in the report but don't get buildable commands. You'd implement them by hand.

### Re-auditing

Each invocation creates a new timestamped report; older reports persist. To compare two audits (e.g., before and after building some recommended skills), diff the Markdown reports manually. The plugin does not currently auto-track audit history.

---

## `/claudefigflow:workflow-eval` — Re-run evals on an existing artifact

### Synopsis

```
/claudefigflow:workflow-eval <path-to-artifact>
/claudefigflow:workflow-eval <path-to-artifact> --iterations 3
```

Read-only on the artifact. Runs Phases 7–9 (eval setup + parallel runs + grade + aggregate) without touching the artifact's contents. Useful for:

- **Regression testing** after a manual edit.
- **Measuring lift** on an artifact created outside claudefigflow.
- **Verifying** that a description still triggers reliably after the surrounding skill ecosystem changes.

### Arguments

Same path forms as `/claudefigflow:modify`. Plus:

- `--iterations N` (optional) — repeat the eval cycle N times with fresh `evals.json` each iteration. Useful for stability measurement; reports variance across iterations.

### What it will ask you

1. **Reuse existing evals or generate fresh?** — if the artifact has a prior eval workspace, you can re-run that exact eval set (regression test) or generate new prompts (stability test).
2. **Eval prompt refinements** — auto-generated set is shown; you can add/edit/remove before the runs spawn.

### What it produces

- New eval workspace at `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact>-<ts>/`.
- Per-eval `with_artifact.json` + `baseline.json` + `grading.json`.
- Aggregate `benchmark.json` with done-definition pass/fail.
- Top-3 strongest evals (positive lift) and top-3 weakest (low or negative lift) printed to chat.

### Differences from modify mode

| Aspect | `/claudefigflow:modify` | `/claudefigflow:workflow-eval` |
|---|---|---|
| Modifies artifact? | Yes (on approval) | Never |
| Eval mode | `differential` (post vs pre) | `creation` (with vs baseline) |
| Decision rule | Accept/reject based on lift | Pass/fail against done-definition |
| Backup created? | Yes (`.pre-modify.bak`) | No (no changes) |

### Common pitfalls

- **Eval workspace clutter** — workspaces accumulate under `${CLAUDE_PLUGIN_DATA}/eval-workspaces/`. Periodic cleanup is your responsibility; the plugin does not auto-prune.
- **Same-prompt reuse pitfall** — re-using an old `evals.json` produces stable comparison, but doesn't catch issues only a fresh prompt set would expose. Mix periodically.

---

## `/claudefigflow:sync-refs` — Sync workshop masters into plugin references

### Synopsis

```
/claudefigflow:sync-refs
/claudefigflow:sync-refs --check
```

Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/sync_refs.py $ARGUMENTS`. Copies:

- `.claude/templates/*.md` → `plugins/claudefigflow/skills/workflow-creator/references/templates/`
- `.claude/mcp-arguments/*.md` → `plugins/claudefigflow/skills/workflow-creator/references/mcp/`

### When to use

After you edit any file under `.claude/templates/` or `.claude/mcp-arguments/`. Run it before commit; the repo's pre-commit hook will block the commit otherwise.

### Arguments

- `--check` — exits non-zero on drift without copying. Useful for CI or manual verification.

### What it produces

JSON summary of files copied / removed / skipped per pair. After running, stage the synced files with `git add plugins/claudefigflow/skills/workflow-creator/references/`.

### Plugin cache caveat

The installed plugin lives in a cache directory (`~/.claude/plugins/cache/...`) separate from this repo. After syncing and committing, run:

```
/plugin marketplace update
```

then reinstall claudefigflow to refresh the cache. Otherwise the running plugin keeps using stale references.

### Common pitfalls

- **Forgetting to commit the synced copies** — masters and copies must commit together; the pre-commit hook is your safety net. Don't bypass with `--no-verify` casually.
- **Editing the synced copies directly** — they're regenerated on every sync. Treat them as build artifacts; edit masters.

---

## Auto-trigger phrases

Both `workflow-creator` and `flow-auditor` skills activate on natural language without needing a slash command. Their descriptions are engineered with verbatim trigger phrases; loose paraphrases also work via fuzzy matching.

### Create-mode triggers (workflow-creator)

- "create a skill"
- "build a new skill"
- "make a slash command"
- "create a command"
- "add a command for X"
- "write an agent"
- "make me an agent"
- "add a hook"
- "create a hook for Y"
- "create a Claude Code workflow"
- "generate a SKILL.md"

### Modify-mode triggers (workflow-creator)

- "modify this skill"
- "update this command"
- "edit this agent"
- "tune this hook"
- "improve this skill's description"
- "add a phase to this skill"
- "tighten this agent's tool list"
- "change the matcher on this hook"

### Audit triggers (flow-auditor)

- "audit this repo for workflow ideas"
- "what skills would help this codebase"
- "scan this repo for automation opportunities"
- "find Claude Code workflow opportunities"
- "audit my repo"
- "what hooks would help this project"
- "what could be automated here"
- "give me ideas for workflows"
- "run a workflow audit"
- "flow audit"
- "look at this repo and tell me what to build"
- "discover workflow opportunities"

The intent-interviewer disambiguates if your phrasing is borderline between create, modify, and audit.

### When auto-trigger is unreliable

If a skill consistently fails to activate on phrases that should trigger it, two fixes:

1. Use the slash command explicitly (`/claudefigflow:workflow`, `/claudefigflow:modify`, or `/claudefigflow:flowaudit`) — guaranteed entry point.
2. Re-run description optimization on the relevant skill (via `/claudefigflow:modify` on `plugins/claudefigflow/skills/<skill-name>/`).

---

## End-to-end workflows

### Scenario 1: Create a new skill in standalone mode

```
> /claudefigflow:workflow
< Engaging workflow-creator skill. What artifact type?
> skill
< Name (lowercase-kebab-case)?
> code-quality-reviewer
< One-paragraph summary of what it does and when to use it?
> Scans a file or directory for code quality issues — type narrowing,
  unhandled errors, missing tests — and reports findings with severity.
< Targeted (external repo) or standalone (mock here)?
> standalone
< Any MCP dependencies?
> no
< [Phase 3: spawning 2 parallel research subagents...]
< [Phase 4: architect drafts file tree, presents plan]
< [Phase 5: writes staged file]
< [Phase 6: validation passes]
< [Phase 7: 6 eval prompts auto-generated, ready to refine]
> looks good, proceed
< [Phase 8: 12 parallel eval runs (6 evals × 2 modes)]
< [Phase 9: grader computes lift]
< Aggregate score: 0.87 / 1.0, lift +0.51 over baseline
< [Phase 10: run description optimization? y/n]
> y
< [5 iterations, best F1 = 0.91 on test split, description updated]
< ✓ Artifact at .claude/skills/code-quality-reviewer-mock/SKILL.md
```

To promote: drop the `-mock` suffix and move to `~/.claude/skills/` or a target repo's `.claude/skills/`.

### Scenario 2: Modify an existing skill's description

```
> /claudefigflow:modify .claude/skills/code-quality-reviewer-mock/
< Loading artifact... type=skill, path classification=mock-workshop
< What's the change intent?
> Add trigger phrases for "lint my code" and "review this PR for issues"
< Scope: frontmatter only? Yes
< [Phase 3: pattern researcher confirms description engineering rules]
< [Phase 4: architect computes diff]
<
< ## Modification plan
< ### Change summary
< - Frontmatter fields changed: description
< - Body sections changed: none
< - Line delta: 0
<
< ### Unified diff
< ---
< -description: This skill should be used when "scan code", "find issues"...
< +description: This skill should be used when "scan code", "find issues",
< +"lint my code", "review this PR for issues"...
<
> approve
< [Phase 5: diff_artifact.py apply — backup written, atomic write]
< [Phase 6: validation passes]
< [Phase 7-9: differential evals on 20 trigger queries]
< Aggregate lift: +0.18 on positive triggers, no regression on negatives
< Decision: ACCEPT
< ✓ Modified .claude/skills/code-quality-reviewer-mock/SKILL.md
< ✓ Backup: .claude/skills/code-quality-reviewer-mock/SKILL.md.pre-modify.bak
```

### Scenario 3: Create a hook in a target repo

```
> /claudefigflow:workflow hook on PostToolUse
< What should the hook do?
> Run prettier on any TS/JS file written by Write or Edit tools
< Targeted or standalone?
> targeted
< Target path?
> myapp                                  # resolves to ~/Repos/myapp
< Verified: ~/Repos/myapp exists, is git repo, has .claude/
< Event: PostToolUse, matcher: "Write|Edit". Prompt-based or script?
> script-based, PowerShell since this is a Windows-first repo
< [Phase 4: architect designs hook entry + .ps1 script]
< [Phase 5: writes to ~/Repos/myapp/.claude/settings.json (merged) and
<           ~/Repos/myapp/.claude/hooks/scripts/prettier-on-write.ps1]
< [Phase 6: validate_artifact.py + test_hook.py with synthetic fixtures]
< All fixtures pass shape + exit-code checks
< [Phase 10: matcher tuning against tool-name corpus]
< Matcher "Write|Edit" hit rate 33% on standard corpus, looks reasonable
< ✓ Hook written. Restart Claude Code in ~/Repos/myapp to load.
```

### Scenario 4: Regression-test an existing artifact

```
> /claudefigflow:workflow-eval ~/.claude/skills/code-reviewer/
< Loading... type=skill, path classification=production-global
< Existing eval workspace found from 2026-04-02. Reuse evals or fresh?
> fresh, things have changed
< [Auto-generates 6 eval prompts, asks for refinements]
> add one for "review this PR for security issues" specifically
< [Phase 8: parallel runs, eval_mode=creation]
< [Phase 9: grader]
< Aggregate: 0.79 / 1.0 (below done-definition threshold of 0.80)
< Weakest eval: security-PR review — with_artifact 0.4, baseline 0.4 (no lift)
< Recommendation: consider modifying to add security review guidance
```

### Scenario 5: Audit a target repo to discover opportunities

```
> /claudefigflow:flowaudit myapp --depth standard
< Engaging flow-auditor skill on ~/Repos/myapp.
< Target validated: exists, is git repo, .claude/ present with 2 skills + 1 hook.
< [Phase 3: spawning cfgflow-target-context-fetcher + cfgflow-repo-signal-scout in parallel]
< [Phase 4: cfgflow-opportunity-synthesizer classifies signals against the decision table]
<
< # Audit report: myapp
< **Generated:** 2026-05-12T142301Z
< **Target:** /Users/McDon/Repos/myapp
< **Focus:** skill, command, subagent, hook, claude_md, mcp
< **Depth:** standard
< **Existing .claude/ artifacts:** 3
<
< ## Summary
< Strong signals around PR-review workflows and pre-commit formatting. The
< highest-leverage opportunity (H1) is a "review-pr" skill — three CI workflows
< and the CONTRIBUTING.md all reference a 7-step PR review procedure.
<
< | Tier | Skills | Commands | Subagents | Hooks | CLAUDE.md | MCP-flag |
< |---|---|---|---|---|---|---|
< | High   | 1 | 0 | 1 | 1 | 0 | 0 |
< | Medium | 1 | 2 | 0 | 1 | 1 | 0 |
< | Low    | 0 | 1 | 0 | 0 | 0 | 1 |
<
< ## High-value opportunities
<
< ### H1. [skill] review-pr
< **Decision criterion:** "Repeated multi-step prompt-pasting; Claude should decide HOW"
< **Rationale:** CONTRIBUTING.md documents a 7-step PR review procedure; CI
< workflow comments reference it; team has paste-the-checklist habit per docs.
< **Evidence:**
< - `CONTRIBUTING.md:42` — "## PR review checklist (7 steps)"
< - `.github/workflows/ci.yml:88` — "# See CONTRIBUTING.md PR review"
< - `docs/runbooks/release.md:15` — "Run the PR review steps before tagging"
< **Suggested name:** `review-pr`
< **Suggested trigger:** "review this PR", "PR review", "check this PR for ..."
< **Estimated effort:** M
< **Build command:** /claudefigflow:workflow skill for review-pr
<
< ### H2. [hook] pre-commit-format
< ...
<
< Want to queue any of these for /claudefigflow:workflow? (e.g., H1, M2) > H1
< Queued: /claudefigflow:workflow skill for review-pr
< (run that in a new prompt when you're ready)
<
< ✓ Audit report: ~/.claude/plugins/data/claudefigflow/audit-reports/myapp-2026-05-12T142301Z/audit.md
< ✓ Target: /Users/McDon/Repos/myapp
< ✓ Opportunities surfaced: 8 (3 high, 4 medium, 1 low)
< ✓ Already covered: 0
```

### Scenario 6: Edit workshop masters and ship

```
> # edit .claude/templates/researcher-agent-template.md in your editor
> /claudefigflow:sync-refs
< 1 file copied to plugins/claudefigflow/skills/workflow-creator/references/templates/
> git add .claude/templates/researcher-agent-template.md plugins/claudefigflow/skills/workflow-creator/references/templates/
> git commit -m "tighten researcher-agent template's output format section"
< pre-commit gate: in sync ✓
< commit accepted
> /plugin marketplace update
> /plugin install claudefigflow@claude-code-workflow --force
< (or restart Claude Code to pick up the refreshed cache)
```

---

## HTML output reports

Every claudefigflow operation (`workflow`, `modify`, `flowaudit`, `workflow-eval`) writes a marker JSON at its final-report phase. The same script renders the sibling `index.html` inline — no hook fires on every Stop event, so sessions not using claudefigflow pay zero overhead. Output lands at:

```
${CLAUDE_PLUGIN_DATA}/outputs/<UTC-timestamp>-<operation>-<name>/index.html
```

Per-operation HTML content:

- **`workflow` (create):** what was built, destination paths, file-by-file rationale, aggregate eval scores, top/weak evals, next steps.
- **`modify`:** change intent, what was added / removed / modified with the **why** for each, structural diff (frontmatter and section delta), differential eval scores, rollback command.
- **`flowaudit`:** tier counts, per-tier opportunity cards with evidence and a **copy-pastable `/claudefigflow:workflow ...` build command** for each buildable opportunity.
- **`workflow-eval`:** aggregate scores per iteration, top/weak evals, conclusions text.

The marker (`marker.json`) and the rendered HTML (`index.html`) sit side-by-side. `write_marker.py` produces both — first the marker, then it calls the renderer in-process. Re-runs are idempotent: a directory with both files is "done"; a directory with only `marker.json` is treated as pending by the manual-recovery path. Outputs are not auto-pruned; delete old `outputs/<ts>-*` directories whenever you like.

To re-render any pending dirs (e.g., after a render that crashed):

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_output.py
```

---

## Troubleshooting

### "Skill not triggering on natural language"

Use the slash command explicitly. If the description has drifted from what's actually canonical for trigger language, run `/claudefigflow:modify` on the `workflow-creator` skill to tune its own description.

### "Eval workspace not persisting between sessions"

`${CLAUDE_PLUGIN_DATA}` is managed by Claude Code and survives plugin updates. If you set a custom data dir or the env var is unset, sessions might write to different locations. Verify with `echo $CLAUDE_PLUGIN_DATA` inside Claude Code's Bash tool.

### "Pre-commit hook blocks every commit"

Run `python plugins/claudefigflow/scripts/sync_refs.py` and stage the synced files. If you're certain the drift is intentional (rare), `git commit --no-verify` bypasses. Don't make a habit of this.

### "Generated hook script doesn't run on Windows"

Default is PowerShell on Windows; verify the hook's `command` field uses `pwsh -NoProfile -File "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<name>.ps1"`. If the script has CRLF line endings, `sh.exe`-style invocation fails — use the explicit pwsh form.

### "I get a name collision warning"

The `cfgflow-existing-workflow-scanner` checks all known destinations. Pick a different name in Phase 1 — re-naming an in-flight artifact is cheap; re-naming after writing is expensive.

### "Modify mode says my change is a no-op"

The architect ran `diff_artifact.py summary` and got `is_noop: true`. Usually means your change intent was too vague ("make it better"). Restate as a concrete delta ("add the verbatim phrase 'lint my code' to the description's trigger list").

### "Differential eval says reject"

The modification produced negative lift — the new version performed worse than the old. Roll back:

```
cp <file>.pre-modify.bak <file>
```

Then reconsider the change. The pre-modification version is preserved for the session.

### "I don't see an HTML report after running an operation"

Check `${CLAUDE_PLUGIN_DATA}/outputs/` — each operation creates a `<UTC-ts>-<op>-<name>/` directory with both `marker.json` and `index.html` inside. If the directory exists but `index.html` is missing, the inline render failed. To force generation:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_output.py
```

Common causes: the operation aborted before its final phase (no marker was written), or the renderer hit a permission error on `outputs/`. If you don't see ANY `<ts>-<op>-<name>/` dir for the run you just finished, check that the skill prompt passed `--plugin-data-dir ${CLAUDE_PLUGIN_DATA}` — without it, marker and HTML land in the workshop-local fallback (`<workshop>/.claudefigflow-data/outputs/`).

---

## See also

- [`README.md`](./README.md) — plugin architecture and install instructions.
- [`skills/workflow-creator/references/artifact-formats.md`](./skills/workflow-creator/references/artifact-formats.md) — frontmatter spec per artifact type.
- [`skills/workflow-creator/references/path-resolution.md`](./skills/workflow-creator/references/path-resolution.md) — destination rules.
- [`skills/workflow-creator/references/creation-workflow.md`](./skills/workflow-creator/references/creation-workflow.md) — phase-by-phase reference for create mode.
- [`skills/workflow-creator/references/modification-workflow.md`](./skills/workflow-creator/references/modification-workflow.md) — phase-by-phase reference for modify mode.
- [`skills/workflow-creator/references/eval-protocol.md`](./skills/workflow-creator/references/eval-protocol.md) — eval JSON schemas + grader rubric.
- [`../../CLAUDE.md`](../../CLAUDE.md) — workshop conventions and contributor setup.
