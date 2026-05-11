"""Synthetic-input validator for claudefigflow hook artifacts.

Replaces the LLM eval pipeline for hooks. Generates fixtures matching the
hook event schema, executes the hook command with each fixture piped to
stdin, validates output JSON shape and exit code semantics, runs security
lints, and optionally tunes the matcher regex against a tool-name corpus.

Usage:
    python test_hook.py <hooks.json> [<fixtures-dir>]
    python test_hook.py <hooks.json> --tune-matcher [--corpus <file>]
    python test_hook.py <hooks.json> --generate-fixtures <out-dir>

Exit codes:
    0 — all fixtures passed
    1 — one or more fixtures failed
    2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

EVENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "PreToolUse": {
        "tool_name": "string",
        "tool_input": "object",
        "session_id": "string",
        "transcript_path": "string",
    },
    "PostToolUse": {
        "tool_name": "string",
        "tool_input": "object",
        "tool_output": "object",
        "session_id": "string",
        "transcript_path": "string",
    },
    "UserPromptSubmit": {
        "prompt": "string",
        "session_id": "string",
        "transcript_path": "string",
    },
    "SessionStart": {
        "session_id": "string",
        "hook_event_name": "string",
    },
    "SessionEnd": {
        "session_id": "string",
        "transcript_path": "string",
    },
    "Stop": {
        "session_id": "string",
        "transcript_path": "string",
    },
    "SubagentStop": {
        "session_id": "string",
        "subagent_type": "string",
    },
    "Notification": {
        "message": "string",
        "session_id": "string",
    },
    "PreCompact": {
        "session_id": "string",
        "transcript_path": "string",
    },
}

SECURITY_PATTERNS = [
    (re.compile(r"\beval\s+"), "use of `eval` is unsafe in shell hooks"),
    (re.compile(r"\$\([^)]*\$\{[^}]*\}"), "nested command substitution with unquoted variable"),
    (re.compile(r"\.\./\.\."), "path traversal pattern"),
    (re.compile(r"rm\s+-rf\s+"), "destructive rm -rf command"),
]


def generate_fixtures(event: str, matcher: str | None) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    schema = EVENT_SCHEMAS.get(event)
    if not schema:
        return fixtures

    base = {
        "session_id": "test-session-001",
        "transcript_path": "/tmp/transcript.txt",
    }

    if event in ("PreToolUse", "PostToolUse"):
        hit_name = "Write"
        if matcher:
            try:
                test_names = ["Write", "Edit", "Read", "Bash", "Grep", "Glob"]
                hits = [n for n in test_names if re.search(matcher, n)]
                hit_name = hits[0] if hits else "Write"
                misses = [n for n in test_names if not re.search(matcher, n)]
                miss_name = misses[0] if misses else "Read"
            except re.error:
                miss_name = "Read"
        else:
            miss_name = "Read"

        fixtures.append({
            "fixture_id": "matcher-hit",
            "expected": "matcher_should_hit",
            "stdin": {**base, "tool_name": hit_name, "tool_input": {"file_path": "/tmp/test.txt", "content": "test"}, **({"tool_output": {"success": True}} if event == "PostToolUse" else {})},
        })
        fixtures.append({
            "fixture_id": "matcher-miss",
            "expected": "matcher_should_miss",
            "stdin": {**base, "tool_name": miss_name, "tool_input": {"file_path": "/tmp/test.txt"}, **({"tool_output": {"success": True}} if event == "PostToolUse" else {})},
        })

    elif event == "UserPromptSubmit":
        fixtures.append({
            "fixture_id": "normal-prompt",
            "expected": "normal_processing",
            "stdin": {**base, "prompt": "Hello, can you help me with a coding task?"},
        })
        fixtures.append({
            "fixture_id": "empty-prompt",
            "expected": "graceful_handling",
            "stdin": {**base, "prompt": ""},
        })

    else:
        fixtures.append({
            "fixture_id": "default",
            "expected": "normal_processing",
            "stdin": base,
        })

    fixtures.append({
        "fixture_id": "malformed-empty",
        "expected": "graceful_handling",
        "stdin": {},
    })

    return fixtures


def resolve_command(cmd_template: str, plugin_root: str | None = None) -> str:
    root = plugin_root or os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    data = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    return cmd_template.replace("${CLAUDE_PLUGIN_ROOT}", root).replace("${CLAUDE_PLUGIN_DATA}", data)


def run_hook(command: str, stdin_payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    stdin_json = json.dumps(stdin_payload)
    try:
        is_windows = platform.system() == "Windows"
        result = subprocess.run(
            command if is_windows else shlex.split(command),
            shell=is_windows,
            input=stdin_json,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"timed out after {timeout}s", "timed_out": True}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "timed_out": False}


def validate_output_shape(stdout: str, event: str) -> list[str]:
    issues: list[str] = []
    if not stdout.strip():
        return issues
    try:
        out = json.loads(stdout)
    except json.JSONDecodeError as e:
        issues.append(f"stdout is not valid JSON: {e}")
        return issues
    if event == "PreToolUse":
        if "permissionDecision" in out:
            valid = {"allow", "deny", "ask"}
            if out["permissionDecision"] not in valid:
                issues.append(f"permissionDecision '{out['permissionDecision']}' not in {sorted(valid)}")
    if "decision" in out:
        if out["decision"] not in {"block", "approve"}:
            issues.append(f"decision '{out['decision']}' not in {{block, approve}}")
    return issues


def security_lint(command: str) -> list[str]:
    findings: list[str] = []
    for pat, msg in SECURITY_PATTERNS:
        if pat.search(command):
            findings.append(msg)
    return findings


def run_test_suite(hooks_config_path: Path) -> dict[str, Any]:
    config = json.loads(hooks_config_path.read_text(encoding="utf-8"))
    hooks_root = config.get("hooks", {})
    plugin_root = str(hooks_config_path.parent.parent.parent.resolve())

    results: list[dict[str, Any]] = []
    overall_pass = True

    for event, entries in hooks_root.items():
        for entry_idx, entry in enumerate(entries):
            matcher = entry.get("matcher")
            for h_idx, h in enumerate(entry.get("hooks", [])):
                cmd_template = h.get("command", "")
                resolved_cmd = resolve_command(cmd_template, plugin_root)
                fixtures = generate_fixtures(event, matcher)
                sec_findings = security_lint(cmd_template)
                if sec_findings:
                    overall_pass = False

                for fx in fixtures:
                    exec_result = run_hook(resolved_cmd, fx["stdin"])
                    shape_issues = validate_output_shape(exec_result["stdout"], event)
                    fixture_pass = (
                        not shape_issues
                        and not exec_result["timed_out"]
                        and exec_result["exit_code"] in (0, 2)
                    )
                    if not fixture_pass:
                        overall_pass = False
                    results.append(
                        {
                            "event": event,
                            "entry_idx": entry_idx,
                            "hook_idx": h_idx,
                            "matcher": matcher,
                            "command": cmd_template,
                            "fixture_id": fx["fixture_id"],
                            "expected": fx["expected"],
                            "execution": exec_result,
                            "shape_issues": shape_issues,
                            "security_findings": sec_findings if (entry_idx == 0 and h_idx == 0 and fx["fixture_id"] == fixtures[0]["fixture_id"]) else [],
                            "pass": fixture_pass and not sec_findings,
                        }
                    )

    return {
        "config_path": str(hooks_config_path),
        "results": results,
        "total_fixtures": len(results),
        "passing": sum(1 for r in results if r["pass"]),
        "overall_pass": overall_pass,
    }


def tune_matcher(hooks_config_path: Path, corpus: list[str] | None = None) -> dict[str, Any]:
    if corpus is None:
        corpus = [
            "Read", "Write", "Edit", "Glob", "Grep", "Bash", "PowerShell",
            "WebFetch", "WebSearch", "TodoWrite", "TaskCreate", "MultiEdit",
            "NotebookEdit", "ExitPlanMode", "Skill",
        ]
    config = json.loads(hooks_config_path.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = []
    for event, entries in config.get("hooks", {}).items():
        for entry_idx, entry in enumerate(entries):
            matcher = entry.get("matcher")
            if not matcher:
                continue
            try:
                hits = [name for name in corpus if re.search(matcher, name)]
                misses = [name for name in corpus if not re.search(matcher, name)]
            except re.error as e:
                findings.append({"event": event, "entry_idx": entry_idx, "error": f"matcher regex invalid: {e}"})
                continue
            findings.append(
                {
                    "event": event,
                    "entry_idx": entry_idx,
                    "matcher": matcher,
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": len(hits) / len(corpus) if corpus else 0,
                    "suggestion": "consider narrower matcher" if len(hits) > len(corpus) * 0.5 else "matcher looks reasonable",
                }
            )
    return {"corpus_size": len(corpus), "matcher_analysis": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description="claudefigflow hook synthetic-input validator")
    parser.add_argument("hooks_config", help="Path to hooks.json or settings.json with hooks key")
    parser.add_argument("--generate-fixtures", metavar="OUT_DIR", help="Generate fixture files and exit")
    parser.add_argument("--tune-matcher", action="store_true", help="Analyze matchers against a tool-name corpus")
    parser.add_argument("--corpus", metavar="FILE", help="Newline-separated tool names for matcher tuning")
    args = parser.parse_args()

    hooks_path = Path(args.hooks_config)
    if not hooks_path.exists():
        print(f"ERROR: hooks config not found: {hooks_path}", file=sys.stderr)
        return 2

    if args.generate_fixtures:
        out_dir = Path(args.generate_fixtures)
        out_dir.mkdir(parents=True, exist_ok=True)
        config = json.loads(hooks_path.read_text(encoding="utf-8"))
        for event, entries in config.get("hooks", {}).items():
            for entry in entries:
                fixtures = generate_fixtures(event, entry.get("matcher"))
                for fx in fixtures:
                    fname = f"{event}-{fx['fixture_id']}.json"
                    (out_dir / fname).write_text(json.dumps(fx["stdin"], indent=2))
        print(json.dumps({"generated_in": str(out_dir)}, indent=2))
        return 0

    if args.tune_matcher:
        corpus = None
        if args.corpus:
            corpus = Path(args.corpus).read_text(encoding="utf-8").splitlines()
            corpus = [c.strip() for c in corpus if c.strip()]
        result = tune_matcher(hooks_path, corpus)
        print(json.dumps(result, indent=2))
        return 0

    result = run_test_suite(hooks_path)
    print(json.dumps(result, indent=2))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
