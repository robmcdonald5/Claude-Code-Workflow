"""Sync repo-level master references into the plugin's references/ directory.

The workshop repo keeps the canonical templates and MCP-argument docs under
`.claude/templates/` and `.claude/mcp-arguments/` at the repo root. The plugin
needs a self-contained copy so it works when installed outside this repo.
This script copies (not symlinks — Windows hostile to symlinks) the masters
into:

    plugins/claudefigflow/skills/workflow-creator/references/templates/
    plugins/claudefigflow/skills/workflow-creator/references/mcp/

It runs as a manual build step, not at plugin runtime. After running, commit
both sides together. The companion `check_refs_in_sync.py` is invoked by a
git pre-commit hook to enforce that masters and plugin copies stay aligned.

Usage:
    python sync_refs.py                    # sync from default paths
    python sync_refs.py --check            # exit 1 if out of sync (no copy)
    python sync_refs.py --repo-root <path> # override repo root detection

Exit codes:
    0 — sync completed (or already in sync with --check)
    1 — drift detected with --check, or partial copy failure
    2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

SYNC_PAIRS: list[tuple[str, str]] = [
    (".claude/templates", "plugins/claudefigflow/skills/workflow-creator/references/templates"),
    (".claude/mcp-arguments", "plugins/claudefigflow/skills/workflow-creator/references/mcp"),
]


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for _ in range(8):
        if (p / ".git").exists() or (p / ".claude-plugin" / "marketplace.json").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise FileNotFoundError("Could not find repo root (no .git or marketplace.json found upward)")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compare_trees(src: Path, dst: Path) -> dict[str, list[str]]:
    drift: dict[str, list[str]] = {
        "missing_in_dst": [],
        "extra_in_dst": [],
        "content_differs": [],
    }
    if not src.exists():
        return drift
    src_files = {p.relative_to(src).as_posix(): p for p in src.rglob("*") if p.is_file()}
    dst_files = {p.relative_to(dst).as_posix(): p for p in dst.rglob("*") if p.is_file()} if dst.exists() else {}

    for rel, src_p in src_files.items():
        if rel not in dst_files:
            drift["missing_in_dst"].append(rel)
            continue
        if file_sha256(src_p) != file_sha256(dst_files[rel]):
            drift["content_differs"].append(rel)

    for rel in dst_files:
        if rel not in src_files:
            drift["extra_in_dst"].append(rel)

    return drift


def sync_pair(src: Path, dst: Path) -> dict[str, int]:
    stats = {"copied": 0, "removed": 0, "skipped": 0}
    if not src.exists():
        print(f"WARN: source {src} does not exist; skipping", file=sys.stderr)
        return stats
    dst.mkdir(parents=True, exist_ok=True)

    src_files = {p.relative_to(src).as_posix(): p for p in src.rglob("*") if p.is_file()}
    dst_files = {p.relative_to(dst).as_posix(): p for p in dst.rglob("*") if p.is_file()} if dst.exists() else {}

    for rel, src_p in src_files.items():
        dst_p = dst / rel
        if rel in dst_files and file_sha256(src_p) == file_sha256(dst_files[rel]):
            stats["skipped"] += 1
            continue
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dst_p)
        stats["copied"] += 1

    for rel, dst_p in dst_files.items():
        if rel not in src_files:
            dst_p.unlink()
            stats["removed"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync repo-level masters into plugin references")
    parser.add_argument("--check", action="store_true", help="Check drift only; do not copy")
    parser.add_argument("--repo-root", help="Override repo root path")
    args = parser.parse_args()

    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path(__file__).parent)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    overall_pass = True
    report: dict[str, dict] = {}

    for src_rel, dst_rel in SYNC_PAIRS:
        src = repo_root / src_rel
        dst = repo_root / dst_rel
        if args.check:
            drift = compare_trees(src, dst)
            has_drift = any(v for v in drift.values())
            if has_drift:
                overall_pass = False
            report[src_rel] = {"drift": drift, "in_sync": not has_drift}
        else:
            stats = sync_pair(src, dst)
            report[src_rel] = {"stats": stats}

    print(__import__("json").dumps({"repo_root": str(repo_root), "pairs": report, "pass": overall_pass}, indent=2))

    if args.check and not overall_pass:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
