"""Package the claudefigflow plugin for distribution.

Bundles plugin files into a single tar.gz suitable for sharing. Excludes
development-only artifacts (__pycache__, .pyc, .DS_Store, eval workspaces).
Output goes to dist/claudefigflow-<version>.tar.gz at the repo root.

Usage:
    python package_plugin.py
    python package_plugin.py --version 0.1.1   # override plugin.json version
    python package_plugin.py --dry-run          # list files, no archive

Exit codes:
    0 — packaged successfully
    1 — drift in references (refs not synced)
    2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
from pathlib import Path

EXCLUDE_PATTERNS = (
    "__pycache__",
    ".pyc",
    ".DS_Store",
    ".pytest_cache",
    "eval-workspaces",
    "staging",
    ".bak",
    ".tmp",
    ".pre-optimize.bak",
)


def should_exclude(p: Path) -> bool:
    s = p.as_posix()
    return any(pat in s for pat in EXCLUDE_PATTERNS)


def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for _ in range(8):
        if (p / ".git").exists() or (p / ".claude-plugin" / "marketplace.json").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise FileNotFoundError("Could not find repo root")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package claudefigflow plugin")
    parser.add_argument("--version", help="Override plugin version (default: from plugin.json)")
    parser.add_argument("--dry-run", action="store_true", help="List files only")
    parser.add_argument("--skip-sync-check", action="store_true", help="Skip the refs-in-sync check (dangerous)")
    args = parser.parse_args()

    try:
        repo_root = find_repo_root(Path(__file__).parent)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    plugin_root = repo_root / "plugins" / "claudefigflow"
    if not plugin_root.exists():
        print(f"ERROR: plugin not found at {plugin_root}", file=sys.stderr)
        return 2

    if not args.skip_sync_check:
        check_script = plugin_root / "scripts" / "check_refs_in_sync.py"
        if check_script.exists():
            result = subprocess.run([sys.executable, str(check_script)], capture_output=True, text=True)
            if result.returncode != 0:
                print("ERROR: refs not in sync; run sync_refs.py first or use --skip-sync-check", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1

    plugin_json_path = plugin_root / ".claude-plugin" / "plugin.json"
    plugin_meta = json.loads(plugin_json_path.read_text(encoding="utf-8"))
    version = args.version or plugin_meta.get("version", "0.0.0")
    name = plugin_meta.get("name", "claudefigflow")

    files: list[tuple[Path, str]] = []
    for p in plugin_root.rglob("*"):
        if p.is_file() and not should_exclude(p):
            arcname = p.relative_to(plugin_root.parent).as_posix()
            files.append((p, arcname))

    if args.dry_run:
        for _, arcname in sorted(files, key=lambda x: x[1]):
            print(arcname)
        print(f"\nTotal files: {len(files)}")
        return 0

    dist_dir = repo_root / "dist"
    dist_dir.mkdir(exist_ok=True)
    archive_path = dist_dir / f"{name}-{version}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        for p, arcname in files:
            tar.add(p, arcname=arcname)

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(json.dumps({
        "archive": str(archive_path),
        "size_mb": round(size_mb, 3),
        "file_count": len(files),
        "version": version,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
