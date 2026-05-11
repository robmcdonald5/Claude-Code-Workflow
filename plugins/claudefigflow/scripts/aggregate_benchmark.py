"""Aggregate per-eval grading.json files into a single benchmark.json.

Usage:
    python aggregate_benchmark.py <iteration-workspace>

Reads:  <workspace>/evals.json, <workspace>/eval-*/grading.json
Writes: <workspace>/benchmark.json

Exit codes:
    0 — benchmark generated successfully (regardless of pass/fail of artifact)
    1 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def aggregate(workspace: Path) -> dict[str, Any]:
    evals_path = workspace / "evals.json"
    if not evals_path.exists():
        raise FileNotFoundError(f"evals.json not found at {evals_path}")
    evals_data = json.loads(evals_path.read_text(encoding="utf-8"))

    per_eval: list[dict[str, Any]] = []
    with_artifact_scores: list[tuple[float, str]] = []
    baseline_scores: list[tuple[float, str]] = []
    category_buckets: dict[str, dict[str, list[float]]] = {}
    false_positives: list[str] = []

    for ev in evals_data["evals"]:
        eval_id = ev["id"]
        category = ev.get("category", "positive")
        eval_dir = workspace / f"eval-{eval_id.removeprefix('eval-')}"
        grading_path = eval_dir / "grading.json"
        if not grading_path.exists():
            per_eval.append({"eval_id": eval_id, "missing": True})
            continue
        grading = json.loads(grading_path.read_text(encoding="utf-8"))
        if grading.get("errors"):
            per_eval.append({"eval_id": eval_id, "errors": grading["errors"]})
            continue

        wa = grading["with_artifact_score"]
        bl = grading["baseline_score"]
        per_eval.append(
            {
                "eval_id": eval_id,
                "category": category,
                "with_artifact": wa,
                "baseline": bl,
                "lift": grading["lift"],
            }
        )
        with_artifact_scores.append((wa, category))
        baseline_scores.append((bl, category))
        category_buckets.setdefault(category, {"with_artifact": [], "baseline": []})
        category_buckets[category]["with_artifact"].append(wa)
        category_buckets[category]["baseline"].append(bl)

        if category == "negative":
            for ar in grading.get("assertion_results", []):
                if (
                    ar.get("assertion_type") == "triggers_artifact"
                    and ar.get("with_artifact", {}).get("passed") is False
                    and ar.get("with_artifact", {}).get("score", 0) > 0.5
                ):
                    false_positives.append(eval_id)
                    break

    def safe_mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    wa_agg = safe_mean([x for x, _ in with_artifact_scores])
    bl_agg = safe_mean([x for x, _ in baseline_scores])

    per_category = {
        cat: {
            "with_artifact": safe_mean(buck["with_artifact"]),
            "baseline": safe_mean(buck["baseline"]),
            "lift": safe_mean(buck["with_artifact"]) - safe_mean(buck["baseline"]),
            "count": len(buck["with_artifact"]),
        }
        for cat, buck in category_buckets.items()
    }

    passes = (
        wa_agg >= 0.80
        and (wa_agg - bl_agg) > 0
        and len(false_positives) == 0
    )

    summary_parts = []
    if wa_agg < 0.80:
        summary_parts.append(f"with-artifact aggregate {wa_agg:.2f} below 0.80 threshold")
    if (wa_agg - bl_agg) <= 0:
        summary_parts.append(f"no lift over baseline (Δ={wa_agg - bl_agg:.2f})")
    if false_positives:
        summary_parts.append(f"{len(false_positives)} false positives on negative evals: {false_positives}")
    if not summary_parts:
        summary_parts.append("Artifact passes done-definition.")
    summary = " ".join(summary_parts)

    return {
        "artifact_name": evals_data.get("artifact_name"),
        "artifact_type": evals_data.get("artifact_type"),
        "iteration": evals_data.get("iteration", 1),
        "total_evals": len(evals_data["evals"]),
        "positive_evals": sum(1 for ev in evals_data["evals"] if ev.get("category") == "positive"),
        "negative_evals": sum(1 for ev in evals_data["evals"] if ev.get("category") == "negative"),
        "edge_evals": sum(1 for ev in evals_data["evals"] if ev.get("category") == "edge"),
        "with_artifact_aggregate": round(wa_agg, 4),
        "baseline_aggregate": round(bl_agg, 4),
        "lift": round(wa_agg - bl_agg, 4),
        "per_category": per_category,
        "per_eval": per_eval,
        "false_positives": false_positives,
        "passes_done_definition": passes,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate claudefigflow eval gradings")
    parser.add_argument("workspace", help="Path to iteration-N/ directory")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        print(f"ERROR: not a directory: {workspace}", file=sys.stderr)
        return 1

    result = aggregate(workspace)
    out_path = workspace / "benchmark.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
