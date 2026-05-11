"""Eval runner orchestration helper for claudefigflow.

This script does NOT execute LLM evals itself — those are run by spawning
cfgflow-eval-runner subagents via the Task tool from the workflow-creator
SKILL.md. This script prepares the workspace, generates the directory
structure, validates the evals.json shape, and emits a manifest the
orchestrator can use to spawn runners.

Usage:
    python run_eval.py prepare <evals.json>
    python run_eval.py validate <workspace>
    python run_eval.py manifest <workspace>

Outputs:
    prepare  — creates eval-<id> directories under <workspace>/iteration-N/
    validate — checks evals.json shape, prints issues to stderr, exit 1 if invalid
    manifest — emits a JSON manifest listing every (eval_id, mode) tuple to spawn
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

VALID_ASSERTION_TYPES = {
    "triggers_artifact",
    "response_contains",
    "response_regex",
    "tool_invocation",
    "tool_not_invoked",
    "qualitative",
    "output_shape",
}

VALID_CATEGORIES = {"positive", "negative", "edge"}


def load_evals(workspace: Path) -> dict[str, Any]:
    evals_path = workspace / "evals.json"
    if not evals_path.exists():
        raise FileNotFoundError(f"evals.json not found at {evals_path}")
    return json.loads(evals_path.read_text(encoding="utf-8"))


def validate_evals(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for required in ("artifact_name", "artifact_type", "evals"):
        if required not in data:
            errors.append(f"missing top-level field '{required}'")

    if "evals" not in data or not isinstance(data["evals"], list):
        return errors

    seen_ids: set[str] = set()
    for i, ev in enumerate(data["evals"]):
        prefix = f"evals[{i}]"
        if "id" not in ev:
            errors.append(f"{prefix}.id is required")
            continue
        if ev["id"] in seen_ids:
            errors.append(f"{prefix}.id '{ev['id']}' is duplicated")
        seen_ids.add(ev["id"])

        if ev.get("category") not in VALID_CATEGORIES:
            errors.append(f"{prefix}.category must be one of {sorted(VALID_CATEGORIES)}")

        if not ev.get("prompt"):
            errors.append(f"{prefix}.prompt is required")

        for j, a in enumerate(ev.get("assertions", [])):
            aprefix = f"{prefix}.assertions[{j}]"
            if a.get("type") not in VALID_ASSERTION_TYPES:
                errors.append(f"{aprefix}.type must be one of {sorted(VALID_ASSERTION_TYPES)}")
            if a.get("type") == "response_regex":
                try:
                    re.compile(a.get("pattern", ""))
                except re.error as e:
                    errors.append(f"{aprefix}.pattern regex invalid: {e}")

    return errors


def prepare(evals_path: Path) -> int:
    workspace = evals_path.parent
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    errors = validate_evals(data)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for ev in data["evals"]:
        d = workspace / f"eval-{ev['id'].removeprefix('eval-')}"
        d.mkdir(exist_ok=True)
    print(json.dumps({"workspace": str(workspace), "eval_count": len(data["evals"])}, indent=2))
    return 0


def validate_cmd(workspace: Path) -> int:
    data = load_evals(workspace)
    errors = validate_evals(data)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"valid": True, "eval_count": len(data["evals"])}, indent=2))
    return 0


def manifest(workspace: Path) -> int:
    data = load_evals(workspace)
    entries = []
    for ev in data["evals"]:
        for mode in ("with_artifact", "baseline"):
            entries.append(
                {
                    "eval_id": ev["id"],
                    "mode": mode,
                    "prompt": ev["prompt"],
                    "category": ev.get("category", "positive"),
                    "output_path": str(workspace / f"eval-{ev['id'].removeprefix('eval-')}" / f"{mode}.json"),
                }
            )
    print(
        json.dumps(
            {
                "artifact_name": data.get("artifact_name"),
                "artifact_type": data.get("artifact_type"),
                "iteration": data.get("iteration", 1),
                "spawn_count": len(entries),
                "entries": entries,
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="claudefigflow eval orchestration helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("evals", help="Path to evals.json")
    p_val = sub.add_parser("validate")
    p_val.add_argument("workspace", help="Path to iteration-N/ directory")
    p_man = sub.add_parser("manifest")
    p_man.add_argument("workspace", help="Path to iteration-N/ directory")
    args = parser.parse_args()

    if args.cmd == "prepare":
        return prepare(Path(args.evals))
    if args.cmd == "validate":
        return validate_cmd(Path(args.workspace))
    if args.cmd == "manifest":
        return manifest(Path(args.workspace))
    return 2


if __name__ == "__main__":
    sys.exit(main())
