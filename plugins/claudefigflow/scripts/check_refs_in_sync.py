"""Pre-commit gate: fail if repo masters and plugin references have drifted.

Thin wrapper around `sync_refs.py --check`. Designed to be wired into a git
pre-commit hook in this repo (NOT a Claude Code plugin hook). If drift is
detected, the commit is blocked with a message telling the user to run
`python plugins/claudefigflow/scripts/sync_refs.py` and stage the changes.

Usage:
    python check_refs_in_sync.py

Exit codes:
    0 — in sync
    1 — drift detected (block commit)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    sync_script = Path(__file__).parent / "sync_refs.py"
    result = subprocess.run(
        [sys.executable, str(sync_script), "--check"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("┌─ claudefigflow refs drift detected ────────────────────────────────┐", file=sys.stderr)
        print("│ Master files under .claude/templates/ or .claude/mcp-arguments/    │", file=sys.stderr)
        print("│ have changed without syncing into plugins/claudefigflow/.          │", file=sys.stderr)
        print("│                                                                    │", file=sys.stderr)
        print("│ To fix:                                                            │", file=sys.stderr)
        print("│   python plugins/claudefigflow/scripts/sync_refs.py                │", file=sys.stderr)
        print("│   git add plugins/claudefigflow/                                   │", file=sys.stderr)
        print("│   git commit --amend --no-edit  (or retry your commit)             │", file=sys.stderr)
        print("└────────────────────────────────────────────────────────────────────┘", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
