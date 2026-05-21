"""Compute and apply diffs between an existing artifact and a modified candidate.

Used by the workflow-creator modification flow. Treats Markdown artifacts as
frontmatter (YAML) + body (text); produces three artifacts:

  - A unified diff (for user review).
  - A structured change summary (which frontmatter fields, which sections).
  - Atomic apply — write `<file>.pre-modify.bak`, then write the new content.

Usage:
    python diff_artifact.py diff <original> <candidate>
    python diff_artifact.py summary <original> <candidate>
    python diff_artifact.py apply <original> <candidate>

Exit codes:
    0 — success (no changes, or apply succeeded)
    1 — usage / I/O error
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1], parts[2]


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


def parse_yaml_flat(raw: str) -> dict[str, str]:
    fm: dict[str, str] = {}
    current_key: str | None = None
    block_lines: list[str] = []
    for line in raw.split("\n"):
        if current_key:
            if line.startswith(" ") or not line.strip():
                block_lines.append(line.lstrip() if line.strip() else "")
                continue
            fm[current_key] = " ".join(l for l in block_lines if l).strip()
            current_key = None
            block_lines = []
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if block_scalar_style(val) is not None:
            current_key = key
            block_lines = []
        else:
            fm[key] = val
    if current_key:
        fm[current_key] = " ".join(l for l in block_lines if l).strip()
    return fm


def section_map(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading = "__preamble__"
    current_lines: list[str] = []
    for line in body.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            sections[current_heading] = "\n".join(current_lines).rstrip()
            current_heading = m.group(2).strip()
            current_lines = []
            continue
        current_lines.append(line)
    sections[current_heading] = "\n".join(current_lines).rstrip()
    return sections


def diff(original: Path, candidate: Path) -> int:
    if not original.exists():
        print(f"ERROR: original does not exist: {original}", file=sys.stderr)
        return 1
    if not candidate.exists():
        print(f"ERROR: candidate does not exist: {candidate}", file=sys.stderr)
        return 1

    o_text = original.read_text(encoding="utf-8")
    c_text = candidate.read_text(encoding="utf-8")
    diff_lines = difflib.unified_diff(
        o_text.splitlines(keepends=True),
        c_text.splitlines(keepends=True),
        fromfile=str(original),
        tofile=str(candidate),
        n=3,
    )
    sys.stdout.writelines(diff_lines)
    return 0


def summary(original: Path, candidate: Path) -> int:
    if not original.exists() or not candidate.exists():
        print(f"ERROR: paths must exist", file=sys.stderr)
        return 1

    o_text = original.read_text(encoding="utf-8")
    c_text = candidate.read_text(encoding="utf-8")
    o_fm_raw, o_body = split_frontmatter(o_text)
    c_fm_raw, c_body = split_frontmatter(c_text)
    o_fm = parse_yaml_flat(o_fm_raw)
    c_fm = parse_yaml_flat(c_fm_raw)

    fm_changed: dict[str, dict[str, str]] = {}
    for k in set(o_fm) | set(c_fm):
        if o_fm.get(k) != c_fm.get(k):
            fm_changed[k] = {"before": o_fm.get(k, ""), "after": c_fm.get(k, "")}

    o_sections = section_map(o_body)
    c_sections = section_map(c_body)
    sections_added = sorted(set(c_sections) - set(o_sections))
    sections_removed = sorted(set(o_sections) - set(c_sections))
    sections_changed: list[str] = []
    for k in set(o_sections) & set(c_sections):
        if o_sections[k].strip() != c_sections[k].strip():
            sections_changed.append(k)

    o_lines = o_text.count("\n") + 1
    c_lines = c_text.count("\n") + 1

    result = {
        "original_path": str(original),
        "candidate_path": str(candidate),
        "line_delta": c_lines - o_lines,
        "byte_delta": len(c_text.encode("utf-8")) - len(o_text.encode("utf-8")),
        "frontmatter_changed_fields": sorted(fm_changed.keys()),
        "frontmatter_diff": fm_changed,
        "sections_added": sections_added,
        "sections_removed": sections_removed,
        "sections_changed": sorted(sections_changed),
        "is_noop": not (fm_changed or sections_added or sections_removed or sections_changed),
    }
    print(json.dumps(result, indent=2))
    return 0


def apply(original: Path, candidate: Path) -> int:
    if not original.exists():
        print(f"ERROR: original does not exist: {original}", file=sys.stderr)
        return 1
    if not candidate.exists():
        print(f"ERROR: candidate does not exist: {candidate}", file=sys.stderr)
        return 1

    backup = original.with_suffix(original.suffix + ".pre-modify.bak")
    shutil.copy2(original, backup)

    tmp = original.with_suffix(original.suffix + ".tmp")
    shutil.copy2(candidate, tmp)
    tmp.replace(original)

    print(json.dumps({
        "applied": True,
        "original_path": str(original),
        "backup_path": str(backup),
        "bytes_written": original.stat().st_size,
    }, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff and apply Claude Code artifact modifications")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_d = sub.add_parser("diff")
    p_d.add_argument("original")
    p_d.add_argument("candidate")
    p_s = sub.add_parser("summary")
    p_s.add_argument("original")
    p_s.add_argument("candidate")
    p_a = sub.add_parser("apply")
    p_a.add_argument("original")
    p_a.add_argument("candidate")
    args = parser.parse_args()

    if args.cmd == "diff":
        return diff(Path(args.original), Path(args.candidate))
    if args.cmd == "summary":
        return summary(Path(args.original), Path(args.candidate))
    if args.cmd == "apply":
        return apply(Path(args.original), Path(args.candidate))
    return 1


if __name__ == "__main__":
    sys.exit(main())
