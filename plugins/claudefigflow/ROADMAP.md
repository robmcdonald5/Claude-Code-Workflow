# claudefigflow — Roadmap

Collected future-feature ideas that are **tracked but not scheduled** for immediate implementation. Each section describes a single idea: the motivation, the proposed shape, why it's deferred, and what would trigger reconsideration.

When implementing one of these, move its section to a `## Shipped` log at the bottom of this file (with the shipping date and PR reference) — or delete the section if a more detailed reference now lives elsewhere.

---

## Audit eval fixtures (regression test corpus for `flow-auditor`)

**Status:** documented, not scheduled.
**Filed:** 2026-05-12
**Origin:** code-review feedback on the initial `/claudefigflow:flowaudit` PR.

### Motivation

The audit pipeline's correctness is currently judged only by human review of the generated Markdown report. There is no automated check that `cfgflow-opportunity-synthesizer` applies the canonical decision table correctly for a given set of signals. A future change to the decision table in `audit-protocol.md` — or to the synthesizer's prompt — could silently regress classification quality, and we'd only notice when a user complained.

The rest of the plugin pipeline catches structural regressions deterministically (`validate_artifact.py`) and behavioral regressions via paired with-artifact / baseline evals (`run_eval.py` + `cfgflow-grader`). The audit operation has neither by intentional v1 design — recommendation quality is squishy to grade, and `/claudefigflow:flowaudit` does not produce LLM-comparable artifacts the way a skill/command/subagent does.

A *signal-fixture* test would land a useful middle ground: deterministic inputs (a frozen `signals.json` and `target-context.json` pair), a runnable synthesizer pass, and a textual diff against an expected report. This is closer to a golden-master test than a true eval — and that's the point.

### Proposed shape

A new `plugins/claudefigflow/tests/audit/` directory with one or more fixture pairs:

```
plugins/claudefigflow/tests/audit/
├── fixtures/
│   ├── case-01-mature-react-monorepo/
│   │   ├── signals.json              # the scout's output for a synthetic repo
│   │   ├── target-context.json       # the target-context-fetcher's output
│   │   └── expected-report.md        # the synthesizer's expected Markdown
│   ├── case-02-young-greenfield/
│   │   └── ...
│   └── case-03-already-saturated/
│       └── ...
├── run_audit_tests.py                # harness
└── README.md                         # how to add new fixtures
```

`run_audit_tests.py` would:

1. Load each fixture's `signals.json` + `target-context.json`.
2. Invoke `cfgflow-opportunity-synthesizer` (via the same Task spawn pattern the SKILL uses) with the fixture as input and a temp `output_path`.
3. Diff the produced report against `expected-report.md`.
4. Score on three axes:
   - **Classification accuracy** — does each opportunity's `[type]` label match the expected label? Binary per opportunity.
   - **Tier accuracy** — does each tier assignment match within 1 tier of expected? (Exact match scored higher; off-by-one is partial credit.)
   - **Citation fidelity** — does every cited `file:line` in the produced report appear in the input `signals.json`? Binary per citation.
5. Emit a per-fixture pass/fail report and an aggregate score.

Suggested fixture seeds:

| Case | Synthetic repo profile | Tests |
|---|---|---|
| case-01-mature-react-monorepo | Existing `.claude/` with 3 skills + 1 hook; rich CI; 50 components | Skip-existing detection; tier-downgrade on behavioral overlap |
| case-02-young-greenfield | Single Python file, no CI, no `CLAUDE.md` | Tier-downgrade on "young repo" rule; sparse signals → mostly Low tier |
| case-03-already-saturated | 15 existing skills, 8 commands, 4 hooks | High `skipped_existing` count; correctly recommends nothing in covered areas |
| case-04-ambiguous-classification | Signals that match both "skill" and "hook" rows | Disambiguation rule applied; hook wins for "must-happen" framings |
| case-05-mcp-flag-only | External services referenced but no integration | MCP-flag emitted with the "Manual step" label, no build command |

### Why deferred

- The audit operation in v1 has no eval pipeline by design — the user judges recommendations directly. Adding a deterministic test corpus *before* there's runtime evidence of regression is premature optimization.
- Maintaining hand-crafted `expected-report.md` files has a real cost: every protocol tweak (decision-table refinement, tier-rule edit, template change) forces a fixture refresh, which would discourage iteration on the protocol itself.
- The full claudefigflow eval pipeline (`/claudefigflow:workflow-eval` on the `flow-auditor` skill) already provides one path to grading the auditor — that's the lighter-weight option for v1.
- The audit's value proposition is *discovery*, not *deterministic output*. Locking in expected reports might over-fit the synthesizer to the test fixtures and reduce its ability to surface novel opportunities.

### Revisit triggers

Re-prioritize implementing this if any of the following become true:

- The decision table in `audit-protocol.md` is edited more than once per release cycle — signals that regressions are likely.
- A user reports an audit produced an obviously miscategorized recommendation — signals that the synthesizer prompt has drifted from the protocol.
- The plugin is adopted by external teams whose CI gates require deterministic test coverage.
- The synthesizer model is changed (e.g., from sonnet to a different tier) — golden-master tests catch model-version regressions cheaply.

### Estimated effort

- **M (1–3 hours)** for the harness + 1 fixture (case-01).
- **+30 min – 1 hour** per additional fixture, depending on signal complexity.
- **+1 hour** for `tests/audit/README.md` documenting how to add a new fixture.

Cumulative: 4–8 hours for a usable 5-fixture corpus.

### Dependencies

None. The harness can be built against the current synthesizer interface without any other plugin changes. Deferred on cost/benefit grounds, not technical blockers.

### Implementation notes (for the future implementer)

- Reuse `plugins/claudefigflow/scripts/run_eval.py`'s spawn pattern as a starting model — though this is a different beast (no with-artifact / baseline pairing, no grader).
- The diff in step 3 should be tolerant of timestamp lines in the report header (`Generated: <UTC ISO 8601>`) — match the *shape* of the timestamp, not the exact value.
- Fixtures should be generated initially by running the synthesizer on hand-crafted `signals.json` files and copying the output to `expected-report.md`, then hand-tuning. This bootstraps from real behavior rather than imagining the expected output cold.

---

## Shipped

(none yet)
