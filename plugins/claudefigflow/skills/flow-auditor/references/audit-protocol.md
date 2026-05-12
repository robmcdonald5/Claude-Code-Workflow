# Audit protocol

Specification for `claudefigflow`'s audit operation: classification rules, tier heuristics, output format. Both `cfgflow-opportunity-synthesizer` and `flow-auditor`'s SKILL.md read against this file.

This file is to the audit operation what `references/artifact-formats.md` is to the create operation: the single source of truth that subagents and validators read against. If a future change to artifact definitions lands in `artifact-formats.md`, mirror it here.

## Canonical artifact-type decision table

Source: `https://code.claude.com/docs/en/features-overview` (Anthropic's canonical "when to use which" comparison) plus `https://code.claude.com/docs/en/best-practices`.

| Trigger condition | Artifact type | Rationale |
|---|---|---|
| You keep typing the same multi-step prompt; Claude should decide HOW to apply the steps | **Skill** | Autonomous, on-demand, reusable; Claude exercises judgment within the procedure |
| Same multi-step procedure pasted repeatedly, knowledge over script | **Skill** | Knowledge encoding |
| Explicit shortcut for a known procedure the user invokes deliberately (`/foo`) | **Command** | User-typed; runs autonomously after invocation |
| Specialized recurring task type that floods the main conversation context | **Subagent** | Context isolation; orchestrator delegates |
| Side task with bounded scope where main flow needs an independent answer | **Subagent** | Independent reasoning |
| Something must happen every time, no exceptions, no LLM judgment | **Hook** | Deterministic, event-driven |
| Format-on-save, lint-on-save, post-X-to-Slack, sound on completion | **Hook** | Deterministic side effect |
| Guardrail that MUST hold (never edit `.env`, never `rm -rf`) | **Hook** | Enforcement, not a request |
| Convention Claude keeps getting wrong twice | **CLAUDE.md entry** | Always-on context |
| Codebase fact Claude should know before any work | **CLAUDE.md entry** | Static knowledge |
| Bridge to an external system (DB, API, service) not yet integrated | **MCP-flag** | Tool/data bridge — flagged only; build is out of audit scope |
| Reuse across multiple repos | Plugin (composite) | Out of audit scope — flag only |

### Disambiguation rules

When two rows match, prefer in this order:

1. **Hook beats skill** when the user says "must happen every time" — explicit invariants always become hooks, not skills with prohibitions. (Anthropic best-practices: "An instruction like 'never edit .env' in CLAUDE.md or a skill is a request, not a guarantee. A PreToolUse hook is enforcement.")
2. **Subagent beats skill** when context-isolation is the primary value — long-running specialist work belongs in a subagent.
3. **Command beats skill** when the user explicitly wants to type `/something` — commands are for deliberate triggers, skills are for ambient ones.
4. **CLAUDE.md beats skill** when the artifact would be a one-liner ("we use Tailwind, not Bootstrap") — that's CLAUDE.md, not a skill.
5. **MCP-flag, never auto-build.** MCP recommendations always go in the report as "flag for human review" — never auto-classified into a buildable artifact.

## Tier heuristics

### High

ALL of:

- ≥3 supporting signal occurrences, OR aligns with an explicit CLAUDE.md/README value statement.
- Reduces friction on a *frequent* activity (referenced multiple times in the codebase or docs).
- No existing artifact in `.claude/` covers it.
- Implementable as v0 in ≤3 hours of authoring.

### Medium

SOME of:

- 1-2 supporting signals.
- Helpful but not critical to the team's workflow.
- Partial overlap with existing automation (e.g., a CI step does part of it).
- Authoring is straightforward but not trivial.

### Low

ANY of:

- Single-signal or speculative.
- Marginal value — the team probably hasn't hit this pain point yet.
- Hard to author well without more domain context.
- Included for transparency, not advocacy.

### Tier-downgrade triggers (apply AFTER initial assignment)

Downgrade one tier when ANY apply:

- The target-context-fetcher's inventory shows a behavioral overlap with an existing artifact.
- The repo is very young (no CI, no `CLAUDE.md`, sparse docs) — the team may not yet know what they need.
- The recommendation depends on an external service (MCP) that isn't already wired in the repo.
- The opportunity is platform-specific (PowerShell-only, macOS-only) and the repo shows cross-platform activity.

Apply downgrades cumulatively — two downgrade triggers stack to a two-tier drop.

### Tier-suppression rule

A recommendation that would land below "Low" after downgrades is dropped entirely. Move it to "Patterns observed but not classified" or omit if it adds nothing.

## Suggested-name rules

Each opportunity must propose a kebab-case name. Rules:

- Lowercase, hyphen-separated.
- No leading/trailing hyphens, no consecutive hyphens.
- ≤40 chars (leaves room for plugin namespacing later).
- Action-oriented for **commands** (`format-pr`, `bump-version`, `seed-db`).
- Noun-phrase for **skills** (`api-route-scaffolder`, `migration-reviewer`, `release-notes-writer`).
- Worker-role for **subagents** (`security-reviewer`, `data-validator`, `accessibility-auditor`).
- Event-prefixed for **hooks** (`pre-commit-format`, `post-write-prettier`, `pre-tool-use-block-prod-writes`).
- Topic-prefixed for **CLAUDE.md** entries (`claude-md-conventions-section`, `claude-md-stack-overview`).

When a proposed name collides with an existing artifact (from the target-context-fetcher's inventory), suffix the proposal with `-2` or rephrase, and note the conflict in the rationale.

## Suggested-trigger rules

By artifact type, propose the *initial trigger surface* the architect would later refine:

| Type | Trigger surface to propose |
|---|---|
| Skill | 4-8 verbatim phrases the user might type (third person, no first-/second-person) |
| Command | Slash invocation pattern (`/foo`, `/foo <arg>`) + one-line argument-hint |
| Subagent | 2-3 example contexts where the orchestrator should delegate |
| Hook | Event name + matcher regex + one-line "fires when..." |
| CLAUDE.md entry | The exact text to add and which section/heading to place it under |
| MCP-flag | Service name + integration shape (read-only, write-capable, event-stream) |

## Suggested-effort rules

| Effort | Authoring time | Examples |
|---|---|---|
| **S** | ≤1 hour | Description tweak, single-section addition, simple hook with no script |
| **M** | 1-3 hours | Full skill body, multi-section subagent, hook with custom PowerShell/bash script |
| **L** | 3+ hours | Skill with bundled references and sub-scripts, multi-event hook system, subagent with eval suite |

Effort estimates assume the author has `claudefigflow` installed and uses `/claudefigflow:workflow`. Without `claudefigflow`, double the estimate.

## Output Markdown template

Use this exact template (substitute `<...>` placeholders; preserve section ordering):

```markdown
# Audit report: <repo-name>

**Generated:** <UTC ISO 8601 timestamp>
**Target:** <absolute path>
**Focus:** <comma-separated artifact types covered>
**Depth:** <quick | standard | deep>
**Existing .claude/ artifacts:** <count> (<S skills, C commands, A agents, H hooks>)

---

## Summary

<2-3 sentences describing the most important takeaways. Highlight the highest-leverage opportunity by ID.>

| Tier | Skills | Commands | Subagents | Hooks | CLAUDE.md | MCP-flag |
|---|---|---|---|---|---|---|
| High | <n> | <n> | <n> | <n> | <n> | <n> |
| Medium | <n> | <n> | <n> | <n> | <n> | <n> |
| Low | <n> | <n> | <n> | <n> | <n> | <n> |

---

## High-value opportunities

### H1. [<artifact-type>] <opportunity-name>

**Decision criterion:** "<verbatim row from the decision table above>"

**Rationale:** <one paragraph: why this would help, what friction it removes, how often the underlying activity occurs.>

**Evidence:**
- `<relative/file/path:line>` — <≤80 char observation>
- `<relative/file/path:line>` — <≤80 char observation>

**Suggested name:** `<kebab-case-name>`
**Suggested trigger:** <per the Suggested-trigger rules above, formatted by type>
**Estimated effort:** <S | M | L>

**Build command:** (for buildable types only — see "Build-command / Next-step rendering rules" below for the `claude_md` / `mcp` variant)

    /claudefigflow:workflow <type> for <opportunity-name>

---

### H2. ...

---

## Medium-value opportunities

(same template structure; replace `H` prefix with `M`)

---

## Low-value opportunities

(same template structure; replace `H` prefix with `L`)

---

## Already covered (skipped)

<bulleted list of opportunities that overlap with existing `.claude/` artifacts>

- `<existing-name>` already covers <opportunity description>; no action needed.

---

## Patterns observed but not classified

<signals the synthesizer saw but couldn't classify into any artifact type, with brief rationale for why>

---

## Files scanned

<bulleted list, cap at 30 entries; add `+ N more` footer if truncated>

- <path 1>
- <path 2>
...
```

### Build-command / Next-step rendering rules

Per-opportunity, the final block in each entry has one of two labels depending on artifact type.

#### Buildable types — `skill`, `command`, `subagent`, `hook`

Use the `Build command:` label with a literal code block (four-space indent or backtick-fenced) so the user can copy-paste verbatim:

    **Build command:**

        /claudefigflow:workflow <type> for <opportunity-name>

The `<type>` and `<opportunity-name>` come from the cluster's classification — no quoting needed since suggested names are already kebab-case.

#### Non-buildable types — `claude_md`, `mcp`

Use the `Next step:` label with manual-action text. No `/claudefigflow:workflow` invocation exists for these.

**CLAUDE.md additions:**

    **Next step:** Add the following to `<repo>/CLAUDE.md` under the `<section>` heading:

        <proposed CLAUDE.md text, in a code block>

**MCP-flag:**

    **Next step:** Evaluate `<service-name>` for MCP server integration. Out of v1 build scope — implement manually or wait for a future MCP-server-stub generator.

The synthesizer chooses the label based on the cluster's artifact type; the user sees the appropriate one without having to know there's a conditional.

## JSON summary schema (orchestrator consumption)

Alongside the Markdown report, the synthesizer emits a single JSON object on stdout:

```json
{
  "report_path": "<absolute-path-to-markdown>",
  "target": "<absolute-path>",
  "focus": ["skill", "command", "subagent", "hook", "claude_md", "mcp"],
  "depth": "quick|standard|deep",
  "tier_counts": {"high": 0, "medium": 0, "low": 0},
  "by_type": {
    "skill": 0,
    "command": 0,
    "subagent": 0,
    "hook": 0,
    "claude_md": 0,
    "mcp": 0
  },
  "skipped_existing": 0,
  "candidates_for_workflow_queue": [
    {
      "id": "H1",
      "name": "<kebab>",
      "type": "skill|command|subagent|hook",
      "tier": "high|medium|low",
      "suggested_intent": "<one-line summary used as $ARGUMENTS for /claudefigflow:workflow>"
    }
  ],
  "warnings": []
}
```

`candidates_for_workflow_queue` only includes items whose `type` is one of the four buildable types — `claude_md` and `mcp` are excluded (they aren't `/claudefigflow:workflow`-buildable).

## Path discipline

- Relative paths in the report are relative to `target_path`.
- All `file` values use forward slashes.
- The report itself lives at `${CLAUDE_PLUGIN_DATA}/audit-reports/<repo-name>-<UTC-ts>/audit.md`.
- The report's path is recorded in the JSON summary so the orchestrator can re-read it.

## Compatibility with existing claudefigflow vocabulary

- The audit's "tier" terminology (High/Medium/Low) parallels `cfgflow-existing-workflow-scanner`'s collision-severity language. They are not the same axis — collision severity is a hazard; tier is an opportunity priority.
- The audit's "build command" recommendations use the exact `/claudefigflow:workflow` syntax so a user can copy-paste without translation.
- The audit *never* invokes `workflow-creator`. The audit and create operations are intentionally separate. Discovery, then a deliberate decision, then a build.
