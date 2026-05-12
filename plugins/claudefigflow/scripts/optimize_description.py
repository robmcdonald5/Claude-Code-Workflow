"""Deterministic helpers for the description-optimization loop.

The actual LLM-level "would this description trigger on this query?" judgments
are performed by cfgflow-description-optimizer (it has the model in context).
This script handles:

  - Scoring trigger-results.json into precision/recall/F1.
  - Tracking iteration-over-iteration improvement.
  - Writing the winning description back to an artifact's frontmatter (with
    a backup of the original).
  - Computing originality / regression-risk diagnostics.

Usage:
    python optimize_description.py score <workspace>/iteration-N/
    python optimize_description.py compare <workspace>/iteration-A/ <workspace>/iteration-B/
    python optimize_description.py finalize <workspace> <artifact-path>

Exit codes:
    0 — success
    1 — finalize chose NOT to update (no improvement)
    2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def score_results(results_path: Path) -> dict[str, Any]:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    per_query = data.get("results", [])

    tp = sum(1 for r in per_query if r["category"] == "positive" and r["would_trigger"])
    fp = sum(1 for r in per_query if r["category"] == "distractor" and r["would_trigger"])
    fn = sum(1 for r in per_query if r["category"] == "positive" and not r["would_trigger"])
    tn = sum(1 for r in per_query if r["category"] == "distractor" and not r["would_trigger"])

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(per_query) if per_query else 0.0

    return {
        "total": len(per_query),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def score(iteration_dir: Path) -> int:
    results_path = iteration_dir / "trigger-results.json"
    if not results_path.exists():
        print(f"ERROR: trigger-results.json not found in {iteration_dir}", file=sys.stderr)
        return 2
    metrics = score_results(results_path)
    out_path = iteration_dir / "iteration-metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


def compare(iter_a: Path, iter_b: Path) -> int:
    def load_metrics(p: Path) -> dict[str, Any]:
        mpath = p / "iteration-metrics.json"
        if not mpath.exists():
            mpath = p / "trigger-results.json"
            if mpath.exists():
                return score_results(mpath)
            raise FileNotFoundError(f"no metrics in {p}")
        return json.loads(mpath.read_text(encoding="utf-8"))

    a = load_metrics(iter_a)
    b = load_metrics(iter_b)
    delta = {
        "precision_delta": round(b["precision"] - a["precision"], 4),
        "recall_delta": round(b["recall"] - a["recall"], 4),
        "f1_delta": round(b["f1"] - a["f1"], 4),
        "accuracy_delta": round(b["accuracy"] - a["accuracy"], 4),
        "winner": "b" if b["f1"] > a["f1"] else "a" if a["f1"] > b["f1"] else "tie",
    }
    print(json.dumps({"a": a, "b": b, "delta": delta}, indent=2))
    return 0


def find_best_iteration(workspace: Path) -> tuple[int, dict[str, Any]] | None:
    best_idx = -1
    best_metrics: dict[str, Any] | None = None
    for d in sorted(workspace.glob("iteration-*")):
        if not d.is_dir():
            continue
        mpath = d / "iteration-metrics.json"
        if not mpath.exists():
            continue
        metrics = json.loads(mpath.read_text(encoding="utf-8"))
        if best_metrics is None or metrics["f1"] > best_metrics["f1"]:
            best_metrics = metrics
            try:
                best_idx = int(d.name.split("-")[1])
            except (IndexError, ValueError):
                continue
    if best_metrics is None:
        return None
    return best_idx, best_metrics


def replace_description_in_frontmatter(file_path: Path, new_description: str) -> str:
    text = file_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("file does not have frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("frontmatter not terminated")
    fm_raw = parts[1]
    body = parts[2]

    lines = fm_raw.split("\n")
    out_lines: list[str] = []
    in_desc_block = False
    block_style: str | None = None
    indent = "  "
    replaced = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("description:"):
            suffix = stripped[len("description:"):].strip()
            in_desc_block = suffix in (">", "|")
            if in_desc_block:
                block_style = suffix
                out_lines.append(f"description: {block_style}")
                if block_style == ">":
                    wrapped = " ".join(new_description.split())
                    out_lines.append(f"{indent}{wrapped}")
                else:
                    for nl in new_description.split("\n"):
                        out_lines.append(f"{indent}{nl}")
                replaced = True
                continue
            else:
                out_lines.append(f"description: {new_description}")
                replaced = True
                continue
        if in_desc_block:
            if line.startswith(" ") or line == "":
                continue
            in_desc_block = False
            block_style = None
        out_lines.append(line)

    if not replaced:
        raise ValueError("could not find description field in frontmatter")

    return "---" + "\n".join(out_lines) + "---" + body


def finalize(workspace: Path, artifact_path: Path) -> int:
    best = find_best_iteration(workspace)
    if best is None:
        print(json.dumps({"finalized": False, "reason": "no iterations found with metrics"}, indent=2))
        return 1
    best_idx, best_metrics = best

    iter_dir = workspace / f"iteration-{best_idx}"
    desc_path = iter_dir / "description-candidate.txt"
    if not desc_path.exists():
        print(json.dumps({"finalized": False, "reason": f"no description-candidate.txt in {iter_dir}"}, indent=2))
        return 1
    new_description = desc_path.read_text(encoding="utf-8").strip()

    baseline_dir = workspace / "iteration-1"
    baseline_metrics_path = baseline_dir / "iteration-metrics.json"
    if baseline_metrics_path.exists() and best_idx != 1:
        baseline_metrics = json.loads(baseline_metrics_path.read_text(encoding="utf-8"))
        if best_metrics["f1"] <= baseline_metrics["f1"]:
            summary = {
                "finalized": False,
                "reason": "best iteration did not beat baseline",
                "baseline_f1": baseline_metrics["f1"],
                "best_f1": best_metrics["f1"],
                "best_iteration": best_idx,
            }
            (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 1

    backup = artifact_path.with_suffix(artifact_path.suffix + ".pre-optimize.bak")
    shutil.copy2(artifact_path, backup)

    updated = replace_description_in_frontmatter(artifact_path, new_description)
    artifact_path.write_text(updated, encoding="utf-8")

    summary = {
        "finalized": True,
        "best_iteration": best_idx,
        "best_f1": best_metrics["f1"],
        "best_precision": best_metrics["precision"],
        "best_recall": best_metrics["recall"],
        "artifact_path": str(artifact_path),
        "backup_path": str(backup),
        "new_description_length": len(new_description),
    }
    (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="claudefigflow description optimizer helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_s = sub.add_parser("score")
    p_s.add_argument("iteration_dir")
    p_c = sub.add_parser("compare")
    p_c.add_argument("iter_a")
    p_c.add_argument("iter_b")
    p_f = sub.add_parser("finalize")
    p_f.add_argument("workspace")
    p_f.add_argument("artifact_path")
    args = parser.parse_args()

    if args.cmd == "score":
        return score(Path(args.iteration_dir))
    if args.cmd == "compare":
        return compare(Path(args.iter_a), Path(args.iter_b))
    if args.cmd == "finalize":
        return finalize(Path(args.workspace), Path(args.artifact_path))
    return 2


if __name__ == "__main__":
    sys.exit(main())
