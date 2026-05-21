"""Deterministic structural validator for claudefigflow artifacts.

Usage:
    python validate_artifact.py <path> --type <skill|command|subagent|hook>

Exit codes:
    0  — pass
    1  — validation errors found
    2  — usage / I/O error

Output:
    JSON report on stdout. Warnings printed to stderr.

This validator handles the deterministic checks listed in
references/artifact-formats.md (rules 1–10 are errors; 11–12 are warnings).
The LLM-level cfgflow-structural-validator handles semantic checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
ABS_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"/root/"),
]
BACKSLASH_IN_PATH = re.compile(r"[A-Za-z0-9_./-]+\\[A-Za-z0-9_./-]+")


def block_scalar_style(val: str) -> str | None:
    """Return the base YAML block-scalar style ('>' or '|') if `val` is a block
    header, else None.

    A block header is the indicator ('>' folded or '|' literal) optionally
    followed by a chomping indicator ('-' strip / '+' keep) and/or an explicit
    indentation digit, plus an optional trailing comment. The base style drives
    the fold-vs-preserve-newlines decision, so chomping/indent indicators are
    accepted but collapse to their base. Recognizes: '>', '|', '>-', '>+',
    '|-', '|+', '>2', '|-2', '|  # note'. Returns None for plain scalars.
    """
    if not val:
        return None
    head = val.split("#", 1)[0].strip()
    if not head or head[0] not in (">", "|"):
        return None
    if all(c in "-+0123456789" for c in head[1:]):
        return head[0]
    return None


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, list[str]]:
    """Return (frontmatter_dict, body, errors).

    Lightweight YAML parser supporting only:
      - Flat `key: value` scalars
      - `>` (folded) and `|` (literal) block scalars

    NOT supported (will silently skip or misparse):
      - List values (`- item`)
      - Nested objects / mappings
      - Anchors (`&`) and aliases (`*`)
      - Multiline scalars without explicit `>` / `|` style indicator
      - Quoted strings spanning multiple lines

    Sufficient for the current artifact frontmatter surface. If any of the
    above become necessary, migrate to PyYAML rather than extending here.
    """
    errors: list[str] = []
    if not text.startswith("---"):
        errors.append("frontmatter not present (file must start with '---')")
        return {}, text, errors
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append("frontmatter not terminated (need closing '---')")
        return {}, text, errors
    raw = parts[1].strip("\n")
    body = parts[2].lstrip("\n")

    fm: dict[str, Any] = {}
    current_key: str | None = None
    block_lines: list[str] = []
    block_style: str | None = None
    for line in raw.split("\n"):
        if not line.strip() and current_key and block_style:
            block_lines.append("")
            continue
        if line.startswith(" ") and current_key and block_style:
            block_lines.append(line.lstrip() if block_style == ">" else line)
            continue
        if current_key and block_style:
            joiner = " " if block_style == ">" else "\n"
            fm[current_key] = joiner.join(l for l in block_lines if l != "").strip()
            current_key = None
            block_lines = []
            block_style = None
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        style = block_scalar_style(val)
        if style is not None:
            current_key = key
            block_style = style
            block_lines = []
        else:
            fm[key] = val.strip()
    if current_key and block_style:
        joiner = " " if block_style == ">" else "\n"
        fm[current_key] = joiner.join(l for l in block_lines if l != "").strip()

    return fm, body, errors


def check_no_absolute_paths(body: str) -> list[str]:
    findings: list[str] = []
    for pat in ABS_PATH_PATTERNS:
        for m in pat.finditer(body):
            findings.append(f"absolute path detected at offset {m.start()}: '{m.group()}'")
    return findings


def check_no_backslashes(body: str) -> list[str]:
    findings: list[str] = []
    for m in BACKSLASH_IN_PATH.finditer(body):
        snippet = m.group()
        if "\\\\" in snippet or "\\n" in snippet or "\\t" in snippet:
            continue
        findings.append(f"backslash in path at offset {m.start()}: '{snippet}'")
    return findings


def validate_skill(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    skill_md = path / "SKILL.md" if path.is_dir() else path
    if not skill_md.exists():
        return {"pass": False, "errors": [f"SKILL.md not found at {skill_md}"], "warnings": []}

    text = skill_md.read_text(encoding="utf-8")
    fm, body, fm_errors = parse_frontmatter(text)
    errors.extend(fm_errors)

    for required in ("name", "description"):
        if required not in fm or not fm[required]:
            errors.append(f"frontmatter.{required} is required")
    if "name" in fm:
        if not NAME_RE.match(fm["name"]):
            errors.append(f"frontmatter.name '{fm['name']}' violates ^[a-z][a-z0-9-]*[a-z0-9]$")
        if len(fm["name"]) > 64:
            errors.append("frontmatter.name exceeds 64 chars")
        expected_dir = path.name.removesuffix("-mock")
        if path.is_dir() and fm["name"] != expected_dir:
            errors.append(f"frontmatter.name '{fm['name']}' must match directory '{expected_dir}'")
    if "description" in fm and len(fm["description"]) > 1024:
        errors.append(f"frontmatter.description exceeds 1024 chars ({len(fm['description'])})")

    errors.extend(check_no_absolute_paths(body))
    errors.extend(check_no_backslashes(body))

    line_count = body.count("\n") + 1
    if line_count > 500:
        warnings.append(f"body is {line_count} lines (>500); consider splitting into references/")
    if "description" in fm and re.search(r"\b(I|you|your|you're|I'll)\b", fm["description"]):
        warnings.append("description contains second-person/first-person language; prefer third person")

    return {"pass": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_command(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, body, fm_errors = parse_frontmatter(text)
    errors.extend(fm_errors)

    if "description" not in fm or not fm["description"]:
        errors.append("frontmatter.description is required")
    if "description" in fm and len(fm["description"]) > 200:
        warnings.append(f"description is {len(fm['description'])} chars; slash-menu favors ≤200")

    if "## Your task" not in body:
        errors.append("body must contain '## Your task' section")

    errors.extend(check_no_absolute_paths(body))
    errors.extend(check_no_backslashes(body))

    return {"pass": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_subagent(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    fm, body, fm_errors = parse_frontmatter(text)
    errors.extend(fm_errors)

    for required in ("name", "description"):
        if required not in fm or not fm[required]:
            errors.append(f"frontmatter.{required} is required")
    if "name" in fm:
        if not NAME_RE.match(fm["name"]):
            errors.append(f"frontmatter.name '{fm['name']}' violates kebab-case rule")
        expected_name = path.stem.removesuffix("-mock")
        if fm["name"] != expected_name:
            errors.append(f"frontmatter.name '{fm['name']}' must match filename '{expected_name}'")

    desc = fm.get("description", "")
    example_count = desc.count("<example>")
    if example_count < 2:
        warnings.append(f"description has {example_count} <example> blocks; ≥2 recommended")
    if example_count > 4:
        warnings.append(f"description has {example_count} <example> blocks; ≤3 recommended for brevity")

    for required_section in ("# Purpose", "## Constraints"):
        if required_section not in body:
            warnings.append(f"body missing recommended section '{required_section}'")

    errors.extend(check_no_absolute_paths(body))
    errors.extend(check_no_backslashes(body))

    return {"pass": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_hook(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"pass": False, "errors": [f"hooks.json invalid JSON: {e}"], "warnings": []}

    if "hooks" not in data:
        errors.append("missing top-level 'hooks' key")
        return {"pass": False, "errors": errors, "warnings": warnings}

    valid_events = {
        "PreToolUse", "PostToolUse", "UserPromptSubmit",
        "SessionStart", "SessionEnd", "Stop", "SubagentStop",
        "Notification", "PreCompact",
    }
    for event, entries in data["hooks"].items():
        if event not in valid_events:
            errors.append(f"unknown event '{event}'; valid: {sorted(valid_events)}")
        if not isinstance(entries, list):
            errors.append(f"hooks.{event} must be a list")
            continue
        for i, entry in enumerate(entries):
            if "matcher" in entry:
                try:
                    re.compile(entry["matcher"])
                except re.error as e:
                    errors.append(f"hooks.{event}[{i}].matcher regex invalid: {e}")
            if "hooks" not in entry or not isinstance(entry["hooks"], list):
                errors.append(f"hooks.{event}[{i}].hooks must be a list")
                continue
            for j, h in enumerate(entry["hooks"]):
                if h.get("type") != "command":
                    warnings.append(f"hooks.{event}[{i}].hooks[{j}].type should be 'command'")
                if not h.get("command"):
                    errors.append(f"hooks.{event}[{i}].hooks[{j}].command is required")
                cmd = h.get("command", "")
                if "C:\\" in cmd or "/Users/" in cmd or "/home/" in cmd:
                    errors.append(f"hooks.{event}[{i}].hooks[{j}].command contains absolute path; use ${{CLAUDE_PLUGIN_ROOT}}")

    return {"pass": len(errors) == 0, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a claudefigflow artifact")
    parser.add_argument("path", help="Path to the artifact (skill directory or file)")
    parser.add_argument(
        "--type",
        required=True,
        choices=["skill", "command", "subagent", "hook"],
        help="Artifact type",
    )
    args = parser.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(json.dumps({"pass": False, "errors": [f"path does not exist: {p}"], "warnings": []}))
        return 2

    if args.type == "skill":
        result = validate_skill(p)
    elif args.type == "command":
        result = validate_command(p)
    elif args.type == "subagent":
        result = validate_subagent(p)
    elif args.type == "hook":
        result = validate_hook(p)
    else:
        print(json.dumps({"pass": False, "errors": [f"unknown type: {args.type}"], "warnings": []}))
        return 2

    print(json.dumps(result, indent=2))
    for w in result.get("warnings", []):
        print(f"WARNING: {w}", file=sys.stderr)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
