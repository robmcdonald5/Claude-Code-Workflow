# Eval protocol

JSON contracts for the eval pipeline (Phases 7–10 of `workflow-creator`). All eval-related files live under `${CLAUDE_PLUGIN_DATA}/eval-workspaces/<artifact-name>-<UTC-timestamp>/`.

Workspace layout:

```
<artifact-name>-2026-05-11T142301Z/
├── iteration-1/
│   ├── evals.json              # input test prompts + assertions
│   ├── eval-001/
│   │   ├── with_artifact.json  # cfgflow-eval-runner output (with artifact in context)
│   │   ├── baseline.json       # cfgflow-eval-runner output (control)
│   │   └── grading.json        # cfgflow-grader output
│   ├── eval-002/
│   ├── ...
│   └── benchmark.json          # aggregate across all evals in this iteration
└── iteration-2/                # only when Phase 10 description optimization runs
    └── ...
```

## `evals.json` — input

```json
{
  "artifact_name": "code-quality-checker",
  "artifact_type": "skill",
  "eval_mode": "creation",
  "iteration": 1,
  "created_at": "2026-05-11T14:23:01Z",
  "evals": [
    {
      "id": "eval-001",
      "category": "positive",
      "description": "User explicitly asks for the skill's behavior",
      "prompt": "Check this file for code quality issues: src/auth.ts",
      "assertions": [
        {
          "type": "triggers_artifact",
          "expected": true,
          "weight": 2.0
        },
        {
          "type": "response_contains",
          "value": "quality",
          "weight": 0.5
        },
        {
          "type": "tool_invocation",
          "tool": "Read",
          "expected": true,
          "weight": 1.0
        },
        {
          "type": "qualitative",
          "rubric": "Does the response identify at least one specific issue and explain why it's a problem?",
          "weight": 2.0
        }
      ]
    },
    {
      "id": "eval-002",
      "category": "negative",
      "description": "User asks an unrelated question; skill should NOT trigger",
      "prompt": "What's the weather like today?",
      "assertions": [
        {
          "type": "triggers_artifact",
          "expected": false,
          "weight": 2.0
        }
      ]
    }
  ]
}
```

### `eval_mode` values

- **`"creation"`** — paired runs are (treatment = new artifact loaded, control = no artifact loaded). Lift measures whether the artifact provides value vs nothing.
- **`"differential"`** — paired runs are (treatment = post-modification artifact loaded, control = pre-modification artifact loaded). Lift measures whether the modification improved the artifact. Used by modify mode (Phase 8 of `modification-workflow.md`).

Same JSON schema in both modes; only the semantics of `with_artifact.json` vs `baseline.json` differ. The grader records `eval_mode` in each `grading.json`.

### `category` values

- `positive` — the artifact should activate and behave correctly.
- `negative` — the artifact should NOT activate (false-positive guard).
- `edge` — boundary case (ambiguous phrasing, partial overlap with other artifacts).

### `assertion.type` values

| Type | Value/Field | Semantics |
|---|---|---|
| `triggers_artifact` | `expected: bool` | Did the model load/use the artifact? Inferred from `tool_calls` (for skills: presence of Skill tool call; for commands/agents: explicit invocation; for hooks: hook fired). |
| `response_contains` | `value: string`, `case_sensitive: bool` | Substring match against `response` field. |
| `response_regex` | `pattern: string` | Regex match against `response`. |
| `tool_invocation` | `tool: string`, `expected: bool`, `min_count: int` | Count of tool calls matching. |
| `tool_not_invoked` | `tool: string` | Negative tool assertion. |
| `qualitative` | `rubric: string` | Free-form rubric judged by `cfgflow-grader`. |
| `output_shape` | `schema: object` | JSON-schema-style check against `response`. |

`weight` is optional, default 1.0. Higher weight = more impact on the eval's score.

## `with_artifact.json` / `baseline.json` — runner output

Identical schema for both:

```json
{
  "eval_id": "eval-001",
  "mode": "with_artifact",
  "artifact_path": "${CLAUDE_PLUGIN_DATA}/staging/<session>/code-quality-checker/SKILL.md",
  "prompt": "Check this file for code quality issues: src/auth.ts",
  "response": "<full model response text>",
  "tool_calls": [
    {
      "name": "Read",
      "input": {"file_path": "src/auth.ts"},
      "output_excerpt": "first 200 chars of result"
    }
  ],
  "artifact_loaded": true,
  "duration_ms": 4321,
  "errors": null,
  "metadata": {
    "model": "claude-opus-4-7",
    "timestamp": "2026-05-11T14:24:15Z"
  }
}
```

`artifact_loaded` is `true` when:
- (skill) The Skill tool was invoked with the artifact's name.
- (command) The slash command appeared in the user message.
- (subagent) The Agent tool was invoked with `subagent_type` matching the artifact's name.
- (hook) The hook fired (inferred from synthetic stdin processed correctly).

For `mode: baseline`, `artifact_loaded` should always be `false`. If `true` in baseline, that's a leak (the baseline accidentally had artifact context) and the eval is invalid.

## `grading.json` — grader output (one per eval)

```json
{
  "eval_id": "eval-001",
  "with_artifact_score": 0.92,
  "baseline_score": 0.31,
  "lift": 0.61,
  "max_possible_score": 5.5,
  "assertion_results": [
    {
      "assertion_idx": 0,
      "assertion_type": "triggers_artifact",
      "weight": 2.0,
      "with_artifact": {"passed": true, "evidence": "Skill tool invoked at message index 1"},
      "baseline": {"passed": false, "evidence": "No skill invocation"}
    },
    {
      "assertion_idx": 3,
      "assertion_type": "qualitative",
      "weight": 2.0,
      "with_artifact": {"passed": true, "score": 0.9, "notes": "identified type-narrowing issue and explained the implication"},
      "baseline": {"passed": false, "score": 0.2, "notes": "generic advice, no specific issue identified"}
    }
  ],
  "qualitative_summary": "Strong positive signal; with-artifact response was specific and actionable, baseline was generic."
}
```

Scoring:
- Each assertion contributes `weight × pass_score` to that eval's total (pass_score is 1.0 for boolean, 0.0–1.0 for qualitative).
- Eval score = `sum(contribution) / max_possible_score`, in [0, 1].
- Lift = `with_artifact_score - baseline_score`.

## `benchmark.json` — aggregate (one per iteration)

```json
{
  "artifact_name": "code-quality-checker",
  "artifact_type": "skill",
  "iteration": 1,
  "completed_at": "2026-05-11T14:35:00Z",
  "total_evals": 10,
  "positive_evals": 6,
  "negative_evals": 3,
  "edge_evals": 1,
  "with_artifact_aggregate": 0.85,
  "baseline_aggregate": 0.32,
  "lift": 0.53,
  "per_category": {
    "positive": {"with_artifact": 0.91, "baseline": 0.28, "lift": 0.63},
    "negative": {"with_artifact": 0.83, "baseline": 0.45, "lift": 0.38},
    "edge":     {"with_artifact": 0.70, "baseline": 0.30, "lift": 0.40}
  },
  "per_eval": [
    {"eval_id": "eval-001", "with_artifact": 0.92, "baseline": 0.31, "lift": 0.61},
    ...
  ],
  "summary": "Artifact passes done-definition (≥0.80 aggregate, positive lift). Weakest area: edge cases.",
  "passes_done_definition": true
}
```

`passes_done_definition` is `true` when:
- `with_artifact_aggregate >= 0.80`
- `lift > 0` (with-artifact beats baseline)
- No `negative_evals` had `with_artifact_score > 0.5` for `triggers_artifact: false` assertions (no false positives)

## Grader rubric (for `qualitative` assertions)

`cfgflow-grader` applies these scoring bands:

| Score | Meaning |
|---|---|
| 1.0 | Fully meets the rubric; nothing missing. |
| 0.75 | Meets the rubric with minor gaps. |
| 0.5 | Partial credit; demonstrates understanding but missed core points. |
| 0.25 | Weak; touches on the topic but misses the rubric's intent. |
| 0.0 | Does not meet the rubric at all. |

Grader must cite specific evidence from the response when assigning scores. Pure vibes-based grades are forbidden — every score has a one-sentence justification in the `notes` field.

## Description-optimization iteration data

When Phase 10 runs description optimization, each iteration's workspace gains:

```
iteration-N/
├── trigger-evals.json          # 20 positive + 20 distractor queries
├── trigger-results.json        # per-query: did it activate?
└── description-candidate.txt   # the description used in this iteration
```

`trigger-evals.json` and `trigger-results.json` follow the same evals/grader shapes but with a single assertion type (`triggers_artifact`). The optimizer ranks descriptions by F1 score over trigger results.
