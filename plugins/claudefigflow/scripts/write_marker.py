"""Write an output marker and render its HTML report inline.

Each claudefigflow operation invokes this script at its final-report phase.
The marker is a small JSON file at
`${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-<op>-<name>/marker.json` that points
at the structured artifacts the operation produced (audit.md, benchmark.json,
diff summaries, staging paths) and carries free-form rationale text the
orchestrator captures from the architect's context.

After writing the marker, this script invokes the renderer in-process
(`generate_output.process_marker`) to write a sibling `index.html`. There is
no Stop hook — non-claudefigflow sessions pay zero overhead. If the inline
render fails (corrupt marker, unwritable dir), the marker is preserved on
disk and can be re-rendered later via:
    python ${CLAUDE_PLUGIN_ROOT}/scripts/generate_output.py

Usage (positional args avoided — every field is a flag for legibility from
skill invocations):

    python write_marker.py \
        --plugin-data-dir ${CLAUDE_PLUGIN_DATA} \
        --operation create \
        --artifact-type skill \
        --artifact-name code-quality-checker \
        --artifact-path /abs/path/SKILL.md \
        --benchmark-json /abs/eval/benchmark.json \
        --destination-paths /abs/skill.md,/abs/refs/foo.md \
        --rationale-json '{"additions": [...], "mode": "targeted", ...}'

`--rationale-json` accepts a JSON string OR a path to a JSON file. Keys are
merged into the marker's `summary` block verbatim. This is the channel
skills use to pass architect-context narrative ("what changed and why")
that has no canonical on-disk source.

Exit codes:
    0 — marker written
    1 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def plugin_data_dir(override: str | None = None) -> tuple[Path, str]:
    """Resolve where output directories should live.

    Resolution order:

    1. Explicit --plugin-data-dir flag (most reliable, used by Skill prompts).
    2. CLAUDE_PLUGIN_DATA env var — NOT guaranteed when this script is invoked
       as a Bash subprocess from inside a Claude Code session, since subprocess
       shells don't always inherit it.
    3. A workshop-repo fallback. Manual-recovery (`generate_output.py`) won't
       find markers here under the canonical plugin-data path; we warn.

    Returns (path, source) where source ∈ {"flag", "env", "fallback"} so the
    caller can warn on fallback use.
    """
    if override:
        return Path(override), "flag"
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env), "env"
    plugin_root = Path(__file__).resolve().parent.parent
    return plugin_root.parent.parent / ".claudefigflow-data", "fallback"


def outputs_dir(override: str | None = None) -> tuple[Path, str]:
    data_dir, source = plugin_data_dir(override)
    return data_dir / "outputs", source


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")


def safe_token(s: str) -> str:
    """Filename-safe slug. Strips path separators and dots so a malicious
    artifact-name argument can't escape the outputs directory."""
    cleaned = _SAFE_NAME_RE.sub("-", s.strip()).strip("-")
    return cleaned[:60] or "unnamed"


def parse_rationale(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    if raw.endswith(".json") and Path(raw).is_file():
        try:
            return json.loads(Path(raw).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARN: could not load rationale file {raw}: {e}", file=sys.stderr)
            return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"WARN: --rationale-json was not valid JSON: {e}", file=sys.stderr)
        return {}


def split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a claudefigflow output marker")
    parser.add_argument("--operation", required=True, choices=["create", "modify", "audit", "workflow-eval"])
    parser.add_argument("--artifact-type", default=None, choices=[None, "skill", "command", "subagent", "hook"])
    parser.add_argument("--artifact-name", required=True, help="Short name (kebab-case preferred)")
    parser.add_argument("--artifact-path", default=None, help="Absolute path to the artifact file or directory")
    parser.add_argument("--started-at", default=None, help="UTC ISO 8601 start timestamp (defaults to now)")
    parser.add_argument("--completed-at", default=None, help="UTC ISO 8601 completion timestamp (defaults to now)")
    parser.add_argument(
        "--plugin-data-dir",
        default=None,
        help=(
            "Absolute path to ${CLAUDE_PLUGIN_DATA}. Skill prompts should pass this "
            "explicitly because Bash subprocesses don't reliably inherit the env var. "
            "Falls back to $CLAUDE_PLUGIN_DATA, then to a workshop-local dir "
            "(a warning is emitted in that case)."
        ),
    )
    # Data-source flags — all optional; the renderer tolerates missing files.
    parser.add_argument("--audit-report-md", default=None)
    parser.add_argument("--audit-summary-json", default=None)
    parser.add_argument("--eval-workspace", default=None)
    parser.add_argument("--benchmark-json", default=None)
    parser.add_argument("--staging-dir", default=None)
    parser.add_argument("--backup-path", default=None)
    parser.add_argument("--diff-summary-json", default=None)
    parser.add_argument("--destination-paths", default=None, help="Comma-separated absolute paths")
    parser.add_argument("--rationale-json", default=None, help="Inline JSON string OR path to a JSON file with the summary block")
    args = parser.parse_args()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    completed_at = args.completed_at or now_iso
    started_at = args.started_at or completed_at

    marker = {
        "marker_version": 1,
        "operation": args.operation,
        "artifact_type": args.artifact_type,
        "artifact_name": args.artifact_name,
        "artifact_path": args.artifact_path,
        "started_at": started_at,
        "completed_at": completed_at,
        "data_sources": {
            "audit_report_md": args.audit_report_md,
            "audit_summary_json": args.audit_summary_json,
            "eval_workspace": args.eval_workspace,
            "benchmark_json": args.benchmark_json,
            "staging_dir": args.staging_dir,
            "backup_path": args.backup_path,
            "diff_summary_json": args.diff_summary_json,
            "destination_paths": split_csv(args.destination_paths) or None,
        },
        "summary": parse_rationale(args.rationale_json),
    }

    base_outputs, source = outputs_dir(args.plugin_data_dir)
    if source == "fallback":
        print(
            f"WARN: CLAUDE_PLUGIN_DATA not set and --plugin-data-dir not passed; "
            f"marker and HTML will land at {base_outputs} (workshop-local fallback) "
            f"rather than the canonical plugin-data path. "
            f"Pass --plugin-data-dir ${{CLAUDE_PLUGIN_DATA}} from the Skill prompt.",
            file=sys.stderr,
        )

    ts_safe = re.sub(r"[^0-9A-Za-z]", "", completed_at)[:20] or now_iso.replace("-", "").replace(":", "")
    dir_name = f"{ts_safe}-{safe_token(args.operation)}-{safe_token(args.artifact_name)}"
    out_dir = base_outputs / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "marker.json"

    try:
        out_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"ERROR: could not write marker: {e}", file=sys.stderr)
        return 1

    # Render inline. Python auto-adds this script's directory to sys.path
    # when invoked as `python write_marker.py`, so the sibling import below
    # resolves without any sys.path manipulation. Narrow exception list:
    # programmer errors (AttributeError, NameError, etc.) should surface,
    # not silently degrade every run.
    html_path: Path | None = None
    try:
        from generate_output import process_marker
        html_path = process_marker(out_path, marker=marker)
    except (ImportError, OSError, ValueError, KeyError) as e:
        print(f"WARN: inline render failed; marker preserved at {out_path}: {e}", file=sys.stderr)

    result: dict[str, Any] = {"marker_path": str(out_path), "output_dir": str(out_dir)}
    if html_path:
        result["html_path"] = str(html_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
