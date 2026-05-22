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
    0 — success (description updated)
    1 — no improvement: evaluated but kept the current description (best
        iteration did not beat baseline F1)
    2 — could not finalize: usage / I/O error, or an unusable candidate
        (missing / empty / over-limit) or a frontmatter rewrite that failed
        or would be malformed. The `reason` field explains.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
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


def block_scalar_style(val: str) -> str | None:
    """Return the base YAML block-scalar style ('>' or '|') if `val` is a block
    header — the indicator optionally followed by a chomping indicator ('-'/'+')
    and/or an explicit indentation digit, plus an optional trailing comment.
    Returns None for plain scalars. Recognizes '>', '|', '>-', '|+', '>2',
    '|  # note', etc.
    """
    if not val:
        return None
    head = val.split("#", 1)[0].strip()
    if not head or head[0] not in (">", "|"):
        return None
    if all(c in "-+0123456789" for c in head[1:]):
        return head[0]
    return None


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
    indent = "  "
    replaced = False
    for line in lines:
        # Match only a top-level (column-0) description key. A nested
        # `description:` (e.g. under `metadata:`) is preserved verbatim rather
        # than lifted to column 0 and re-wrapped.
        if line.startswith("description:"):
            suffix = line[len("description:"):].strip()
            base_style = block_scalar_style(suffix)
            in_desc_block = base_style is not None
            if in_desc_block:
                # Preserve the original block header verbatim (including any
                # chomping indicator like '>-'); re-emit the new description.
                out_lines.append(f"description: {suffix}")
                if base_style == ">":
                    folded = " ".join(new_description.split())
                    # Never split a token across lines: a folded ('>') scalar
                    # turns a mid-token line break into a space, corrupting it
                    # (e.g. "documentation-update- reviewer", or a split URL).
                    # break_on_hyphens guards hyphenated terms; break_long_words
                    # guards long tokens like URLs.
                    for wl in textwrap.wrap(
                        folded, width=76, break_on_hyphens=False, break_long_words=False
                    ) or [""]:
                        out_lines.append(f"{indent}{wl}")
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
        out_lines.append(line)

    if not replaced:
        raise ValueError("could not find description field in frontmatter")

    # Guarantee a newline before the closing fence. When the description block
    # is the LAST frontmatter field, the in-block skip loop above consumes the
    # trailing blank line; without this the closing '---' would jam onto the
    # final description line and corrupt the frontmatter.
    fm_joined = "\n".join(out_lines)
    if not fm_joined.endswith("\n"):
        fm_joined += "\n"
    return "---" + fm_joined + "---" + body


def finalize(workspace: Path, artifact_path: Path) -> int:
    best = find_best_iteration(workspace)
    if best is None:
        print(json.dumps({"finalized": False, "reason": "no iterations found with metrics"}, indent=2))
        return 2
    best_idx, best_metrics = best

    iter_dir = workspace / f"iteration-{best_idx}"
    desc_path = iter_dir / "description-candidate.txt"
    if not desc_path.exists():
        print(json.dumps({"finalized": False, "reason": f"no description-candidate.txt in {iter_dir}"}, indent=2))
        return 2
    new_description = desc_path.read_text(encoding="utf-8").strip()
    if not new_description:
        summary = {"finalized": False, "reason": "winning description-candidate.txt is empty"}
        (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2
    if len(new_description) > 1024:
        summary = {
            "finalized": False,
            "reason": f"winning description is {len(new_description)} chars (>1024 limit)",
        }
        (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2

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

    try:
        updated = replace_description_in_frontmatter(artifact_path, new_description)
    except ValueError as e:
        # Bad/unsupported artifact (no frontmatter, unterminated, or no
        # top-level description key). Fail with structured JSON, not a crash.
        summary = {"finalized": False, "reason": f"could not rewrite frontmatter: {e}"}
        (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2
    # Post-rewrite structural check: never persist malformed frontmatter. A
    # well-formed result starts with '---' and the frontmatter block (between
    # the first two fences) ends with a newline before the closing fence.
    fm_parts = updated.split("---", 2)
    if not updated.startswith("---") or len(fm_parts) < 3 or not fm_parts[1].endswith("\n"):
        summary = {
            "finalized": False,
            "reason": "rewrite produced malformed frontmatter; artifact left unchanged",
        }
        (workspace / "optimization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 2

    backup = artifact_path.with_suffix(artifact_path.suffix + ".pre-optimize.bak")
    shutil.copy2(artifact_path, backup)
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
