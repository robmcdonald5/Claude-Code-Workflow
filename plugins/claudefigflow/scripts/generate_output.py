"""Render claudefigflow operation markers into self-contained HTML reports.

Normally invoked in-process by `write_marker.py` (the renderer runs inline
once a marker is written, so the HTML is ready by the time the operation
finishes its next-steps print). Can also be invoked standalone to recover
any output directories that have `marker.json` but no `index.html` — useful
if an inline render previously crashed or the operation was interrupted.

Layout it produces / scans:
    ${CLAUDE_PLUGIN_DATA}/outputs/<UTC-ts>-<op>-<name>/
        marker.json     (written by write_marker.py)
        index.html      (written here)

The renderer is permissive — missing optional fields render as "(not captured)"
rather than errors. The point is to never let a partially-populated marker
block the operation.

Usage:
    python generate_output.py                 # scan outputs/ for pending dirs
    python generate_output.py --marker <path> # render a specific marker
    python generate_output.py --dry-run       # print plan, write nothing

Exit code is always 0 — a render failure must not break the caller.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any

TOP_EVAL_COUNT = 3
DECISION_CLASS = {
    "accept": "decision-accept",
    "accept-with-warning": "decision-warn",
    "reject": "decision-reject",
}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def plugin_data_dir() -> Path:
    """Return ${CLAUDE_PLUGIN_DATA} or a local fallback.

    When the hook fires under Claude Code, ${CLAUDE_PLUGIN_DATA} is set. When
    this script is invoked manually for testing, fall back to a sibling
    directory of the plugin root so behavior stays inspectable.
    """
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env)
    plugin_root = Path(__file__).resolve().parent.parent
    return plugin_root.parent.parent / ".claudefigflow-data"


def outputs_dir() -> Path:
    return plugin_data_dir() / "outputs"


# ---------------------------------------------------------------------------
# Shared HTML scaffolding
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  --muted: #6b6b6b;
  --border: #e3e3e3;
  --card: #ffffff;
  --code-bg: #f3f3f3;
  --accent: #2a5d9f;
  --high: #1d7a4f;
  --high-bg: #e6f4ec;
  --medium: #a86512;
  --medium-bg: #fbf0d8;
  --low: #5f5f5f;
  --low-bg: #ececec;
  --add: #1d7a4f;
  --add-bg: #e6f4ec;
  --del: #a32a2a;
  --del-bg: #fbe6e6;
  --warn: #a86512;
  --warn-bg: #fbf0d8;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.55;
  font-size: 15px;
}
main { max-width: 960px; margin: 0 auto; padding: 32px 24px 80px; }
header.hdr {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 16px;
  border-bottom: 1px solid var(--border);
}
header.hdr h1 { margin: 8px 0 4px; font-size: 28px; font-weight: 600; }
header.hdr p.meta { margin: 0; color: var(--muted); font-size: 13px; }
.op-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--accent);
  color: #fff;
}
.op-badge.op-create { background: #2a8f5e; }
.op-badge.op-modify { background: #a86512; }
.op-badge.op-audit { background: #2a5d9f; }
.op-badge.op-workflow-eval { background: #5a3a8a; }
.op-badge.op-unknown { background: #6b6b6b; }
section {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 20px 24px;
  margin: 18px 0;
}
section h2 { margin-top: 0; font-size: 18px; font-weight: 600; }
section h3 { font-size: 15px; font-weight: 600; margin-top: 18px; margin-bottom: 6px; }
.kv { display: grid; grid-template-columns: 160px 1fr; row-gap: 6px; column-gap: 16px; font-size: 14px; }
.kv .k { color: var(--muted); }
.kv .v { word-break: break-word; }
code, pre {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
}
code { background: var(--code-bg); padding: 1px 5px; border-radius: 3px; }
pre {
  background: var(--code-bg);
  border-radius: 4px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 8px 0;
}
.copyable {
  position: relative;
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  margin: 6px 0 14px;
  white-space: pre;
  overflow-x: auto;
}
.tier-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}
.tier-high { background: var(--high-bg); color: var(--high); }
.tier-medium { background: var(--medium-bg); color: var(--medium); }
.tier-low { background: var(--low-bg); color: var(--low); }
.type-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: #ececec;
  color: #444;
  text-transform: lowercase;
}
.opp {
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 14px 18px;
  margin: 12px 0;
  background: #fdfdfd;
}
.opp .opp-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.opp .opp-head h3 { margin: 0; font-size: 16px; }
.opp p { margin: 6px 0; }
.opp ul { margin: 4px 0 4px 18px; padding: 0; }
.opp ul li { margin: 2px 0; font-size: 13px; }
.opp .build-cmd-label { color: var(--muted); font-size: 12px; margin-top: 10px; text-transform: uppercase; letter-spacing: 0.4px; font-weight: 600; }
.muted { color: var(--muted); }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 14px; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { font-weight: 600; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.3px; }
.diff-add { background: var(--add-bg); color: var(--add); }
.diff-del { background: var(--del-bg); color: var(--del); }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 12px 0; }
.metric {
  background: #fdfdfd;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px 14px;
}
.metric .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }
.metric .value { font-size: 22px; font-weight: 600; margin-top: 2px; }
.metric .delta { font-size: 12px; color: var(--muted); }
.decision-accept { color: var(--high); font-weight: 600; }
.decision-warn { color: var(--medium); font-weight: 600; }
.decision-reject { color: var(--del); font-weight: 600; }
.notice {
  border-left: 3px solid var(--accent);
  background: #f5f8fc;
  padding: 10px 14px;
  border-radius: 0 4px 4px 0;
  margin: 12px 0;
  font-size: 14px;
}
.notice.warn { border-color: var(--medium); background: var(--warn-bg); }
footer {
  max-width: 960px;
  margin: 32px auto 0;
  padding: 16px 24px 32px;
  color: var(--muted);
  font-size: 12px;
  border-top: 1px solid var(--border);
}
.empty { color: var(--muted); font-style: italic; }
"""


def html_doc(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        f"  <meta charset=\"utf-8\">\n"
        f"  <title>{escape(title)}</title>\n"
        f"  <style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def header_html(marker: dict[str, Any]) -> str:
    op = marker.get("operation", "unknown")
    name = marker.get("artifact_name") or "(unnamed)"
    art_type = marker.get("artifact_type") or "—"
    started = marker.get("started_at")
    completed = marker.get("completed_at")
    duration_str = ""
    if started and completed:
        try:
            s = datetime.fromisoformat(started.replace("Z", "+00:00"))
            c = datetime.fromisoformat(completed.replace("Z", "+00:00"))
            secs = (c - s).total_seconds()
            if secs >= 60:
                duration_str = f" • duration {int(secs // 60)}m {int(secs % 60)}s"
            else:
                duration_str = f" • duration {secs:.1f}s"
        except (ValueError, TypeError):
            pass
    completed_label = completed or "—"

    title_label = {
        "create": "Workflow built",
        "modify": "Workflow modified",
        "audit": "Workflow opportunities surfaced",
        "workflow-eval": "Workflow re-evaluated",
    }.get(op, "Workflow report")

    badge_op = op if op in RENDERERS else "unknown"
    return (
        "<header class=\"hdr\">\n"
        f"  <span class=\"op-badge op-{badge_op}\">{escape(op)}</span>\n"
        f"  <h1>{escape(title_label)}: {escape(name)}</h1>\n"
        f"  <p class=\"meta\">{escape(art_type)} &middot; completed {escape(completed_label)}{escape(duration_str)}</p>\n"
        "</header>\n"
    )


def footer_html(marker_path: Path, html_path: Path) -> str:
    return (
        "<footer>\n"
        f"  <p>Generated by claudefigflow &middot; marker: <code>{escape(str(marker_path))}</code></p>\n"
        f"  <p>HTML: <code>{escape(str(html_path))}</code></p>\n"
        "</footer>\n"
    )


def kv_block(rows: list[tuple[str, str]]) -> str:
    parts = ["<div class=\"kv\">"]
    for k, v in rows:
        parts.append(f"  <div class=\"k\">{escape(k)}</div>")
        parts.append(f"  <div class=\"v\">{escape(v) if v else '<span class=\"empty\">—</span>'}</div>")
    parts.append("</div>")
    return "\n".join(parts)


def safe_load_json(path: Any) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        p = Path(path)
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def safe_load_text(path: Any) -> str | None:
    if not path:
        return None
    try:
        p = Path(path)
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def metric_grid(wa: float, bl: float, lift: float, passes: bool | None = None,
                wa_label: str = "With artifact", bl_label: str = "Baseline") -> str:
    tiles = [
        ("label", wa_label, f"{wa:.2f}"),
        ("label", bl_label, f"{bl:.2f}"),
        ("label", "Lift", f"{lift:+.2f}"),
    ]
    if passes is not None:
        tiles.append(("label", "Done definition", "PASS" if passes else "FAIL"))
    cells = "\n".join(
        f"  <div class=\"metric\"><div class=\"label\">{escape(label)}</div><div class=\"value\">{escape(value)}</div></div>"
        for _, label, value in tiles
    )
    return f"<div class=\"metric-grid\">\n{cells}\n</div>"


def _eval_row(e: dict[str, Any]) -> str:
    return (
        f"<tr><td><code>{escape(str(e.get('eval_id', '')))}</code></td>"
        f"<td>{escape(str(e.get('category', '')))}</td>"
        f"<td>{e.get('with_artifact', 0):.2f}</td>"
        f"<td>{e.get('baseline', 0):.2f}</td>"
        f"<td>{e.get('lift', 0):+.2f}</td></tr>"
    )


def eval_tables(per_eval: list[dict[str, Any]]) -> str:
    """Top-N strongest and weakest eval tables. Skips weakest when set is too small."""
    scored = [e for e in per_eval if isinstance(e.get("lift"), (int, float))]
    scored_sorted = sorted(scored, key=lambda e: e.get("lift", 0), reverse=True)
    top = scored_sorted[:TOP_EVAL_COUNT]
    bottom = scored_sorted[-TOP_EVAL_COUNT:][::-1] if len(scored_sorted) > TOP_EVAL_COUNT else []
    header = "<tr><th>ID</th><th>Category</th><th>With artifact</th><th>Baseline</th><th>Lift</th></tr>"
    out: list[str] = []
    if top:
        out.append("<h3>Strongest evals</h3>\n<table>\n" + header + "\n" + "\n".join(_eval_row(e) for e in top) + "\n</table>")
    if bottom:
        out.append("<h3>Weakest evals</h3>\n<table>\n" + header + "\n" + "\n".join(_eval_row(e) for e in bottom) + "\n</table>")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Renderers — one per operation
# ---------------------------------------------------------------------------

def render_rationale_list(items: Any, empty_label: str) -> str:
    if not isinstance(items, list) or not items:
        return f"<p class=\"empty\">{escape(empty_label)}</p>"
    parts = ["<ul>"]
    for it in items:
        if isinstance(it, dict):
            path_s = it.get("path", "")
            what_s = it.get("what", "")
            why_s = it.get("why", "")
            line = ""
            if path_s:
                line += f"<code>{escape(path_s)}</code>"
            if what_s:
                line += (" — " if line else "") + escape(what_s)
            if why_s:
                line += f" <span class=\"muted\">({escape(why_s)})</span>"
            parts.append(f"  <li>{line}</li>")
        else:
            parts.append(f"  <li>{escape(str(it))}</li>")
    parts.append("</ul>")
    return "\n".join(parts)


def render_create(marker: dict[str, Any]) -> str:
    sources = marker.get("data_sources", {}) or {}
    summary = marker.get("summary", {}) or {}
    benchmark = safe_load_json(sources.get("benchmark_json"))

    sections: list[str] = []

    rows = [
        ("Artifact type", marker.get("artifact_type") or "—"),
        ("Name", marker.get("artifact_name") or "—"),
        ("Mode", summary.get("mode") or "—"),
        ("Destination", summary.get("destination") or marker.get("artifact_path") or "—"),
    ]
    sections.append(
        "<section>\n"
        "  <h2>What was built</h2>\n"
        f"  {kv_block(rows)}\n"
        "</section>"
    )

    dest_paths = sources.get("destination_paths") or []
    additions = summary.get("additions") or []
    file_parts = ["<section>", "  <h2>Files added</h2>"]
    if dest_paths:
        file_parts.append("  <h3>Destination paths</h3>\n  <ul>")
        for p in dest_paths:
            file_parts.append(f"    <li><code>{escape(str(p))}</code></li>")
        file_parts.append("  </ul>")
    if additions:
        file_parts.append("  <h3>What and why</h3>")
        file_parts.append(f"  {render_rationale_list(additions, 'No file-level rationale captured.')}")
    if not dest_paths and not additions:
        file_parts.append("  <p class=\"empty\">No file paths recorded in the marker.</p>")
    file_parts.append("</section>")
    sections.append("\n".join(file_parts))

    if benchmark:
        wa = benchmark.get("with_artifact_aggregate", 0.0)
        bl = benchmark.get("baseline_aggregate", 0.0)
        lift = benchmark.get("lift", wa - bl)
        passes = benchmark.get("passes_done_definition", False)
        summary_text = benchmark.get("summary", "")
        sections.append(
            "<section>\n"
            "  <h2>Evaluation</h2>\n"
            f"  {metric_grid(wa, bl, lift, passes)}\n"
            + (f"  <p>{escape(summary_text)}</p>\n" if summary_text else "")
            + f"  {eval_tables(benchmark.get('per_eval', []) or [])}\n"
            "</section>"
        )

    next_steps = summary.get("next_steps")
    if next_steps:
        sections.append(
            "<section>\n"
            "  <h2>Next steps</h2>\n"
            f"  <pre>{escape(next_steps)}</pre>\n"
            "</section>"
        )

    return "\n".join(sections)


def render_modify(marker: dict[str, Any]) -> str:
    sources = marker.get("data_sources", {}) or {}
    summary = marker.get("summary", {}) or {}
    diff_summary = safe_load_json(sources.get("diff_summary_json"))
    benchmark = safe_load_json(sources.get("benchmark_json"))

    sections: list[str] = []

    rows = [
        ("Artifact path", marker.get("artifact_path") or "—"),
        ("Backup", sources.get("backup_path") or "—"),
        ("Change intent", summary.get("change_intent") or "—"),
        ("Scope", summary.get("scope_hint") or "—"),
    ]
    sections.append(
        "<section>\n"
        "  <h2>Modification overview</h2>\n"
        f"  {kv_block(rows)}\n"
        "</section>"
    )

    rationale_parts = ["<section>", "  <h2>What changed and why</h2>"]
    rationale_parts.append("  <h3>Added</h3>")
    rationale_parts.append(f"  {render_rationale_list(summary.get('additions'), 'No additions captured.')}")
    rationale_parts.append("  <h3>Removed</h3>")
    rationale_parts.append(f"  {render_rationale_list(summary.get('removals'), 'No removals captured.')}")
    rationale_parts.append("  <h3>Modified</h3>")
    rationale_parts.append(f"  {render_rationale_list(summary.get('modifications'), 'No modifications captured.')}")
    rationale_parts.append("</section>")
    sections.append("\n".join(rationale_parts))

    if diff_summary:
        ds_parts = ["<section>", "  <h2>Structural diff</h2>"]
        line_delta = diff_summary.get("line_delta", 0)
        byte_delta = diff_summary.get("byte_delta", 0)
        ds_parts.append(
            "  <div class=\"metric-grid\">\n"
            f"    <div class=\"metric\"><div class=\"label\">Line delta</div><div class=\"value\">{line_delta:+d}</div></div>\n"
            f"    <div class=\"metric\"><div class=\"label\">Byte delta</div><div class=\"value\">{byte_delta:+d}</div></div>\n"
            "  </div>"
        )
        fm_diff = diff_summary.get("frontmatter_diff", {}) or {}
        if fm_diff:
            ds_parts.append("  <h3>Frontmatter</h3>")
            ds_parts.append("  <table><tr><th>Field</th><th>Before</th><th>After</th></tr>")
            for field, ba in fm_diff.items():
                before = ba.get("before", "")
                after = ba.get("after", "")
                ds_parts.append(
                    f"    <tr><td><code>{escape(field)}</code></td>"
                    f"<td class=\"diff-del\">{escape(before) if before else '(empty)'}</td>"
                    f"<td class=\"diff-add\">{escape(after) if after else '(empty)'}</td></tr>"
                )
            ds_parts.append("  </table>")
        added_secs = diff_summary.get("sections_added", []) or []
        removed_secs = diff_summary.get("sections_removed", []) or []
        changed_secs = diff_summary.get("sections_changed", []) or []
        if added_secs or removed_secs or changed_secs:
            ds_parts.append("  <h3>Body sections</h3>")
            ds_parts.append("  <ul>")
            for s in added_secs:
                ds_parts.append(f"    <li class=\"diff-add\">+ {escape(s)}</li>")
            for s in removed_secs:
                ds_parts.append(f"    <li class=\"diff-del\">− {escape(s)}</li>")
            for s in changed_secs:
                ds_parts.append(f"    <li>~ {escape(s)}</li>")
            ds_parts.append("  </ul>")
        if diff_summary.get("is_noop"):
            ds_parts.append("  <p class=\"notice warn\">Diff is a no-op — structural shape unchanged.</p>")
        ds_parts.append("</section>")
        sections.append("\n".join(ds_parts))

    if benchmark:
        wa = benchmark.get("with_artifact_aggregate", 0.0)
        bl = benchmark.get("baseline_aggregate", 0.0)
        lift = benchmark.get("lift", wa - bl)
        decision = benchmark.get("decision") or summary.get("decision") or ""
        decision_class = DECISION_CLASS.get(decision, "")
        sections.append(
            "<section>\n"
            "  <h2>Differential evaluation</h2>\n"
            f"  {metric_grid(wa, bl, lift, wa_label='Post-modification', bl_label='Pre-modification')}\n"
            + (f"  <p>Decision: <span class=\"{decision_class}\">{escape(decision.upper())}</span></p>\n" if decision else "")
            + (f"  <p>{escape(benchmark.get('summary', ''))}</p>\n" if benchmark.get("summary") else "")
            + "</section>"
        )

    backup = sources.get("backup_path")
    if backup:
        sections.append(
            "<section>\n"
            "  <h2>Rollback</h2>\n"
            "  <p>To revert this modification, restore the backup:</p>\n"
            f"  <pre class=\"copyable\">cp {escape(str(backup))} {escape(str(marker.get('artifact_path') or '<original>'))}</pre>\n"
            "</section>"
        )

    return "\n".join(sections)


_OPP_BLOCK_RE = re.compile(
    r"^### ([HML]\d+)\.\s*\[([^\]]+)\]\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_audit_report(md: str) -> list[dict[str, Any]]:
    """Extract opportunity entries from the synthesizer's Markdown report.

    Returns a list of {id, type, name, raw_body, build_command} dicts.
    Lenient by design — the synthesizer's template can drift slightly and we
    still want to render whatever was emitted.
    """
    opps: list[dict[str, Any]] = []
    matches = list(_OPP_BLOCK_RE.finditer(md))
    for i, m in enumerate(matches):
        opp_id = m.group(1)
        opp_type = m.group(2).strip()
        opp_name = m.group(3).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        rest = md[body_start:body_end]
        nxt_section = re.search(r"^---\s*$|^## ", rest, re.MULTILINE)
        if nxt_section:
            rest = rest[: nxt_section.start()]
        opps.append(
            {
                "id": opp_id,
                "type": opp_type,
                "name": opp_name,
                "body": rest.strip(),
            }
        )
    return opps


# Field labels we know we'll be slicing the body against. Any of these (or
# a `---` / `## ` separator, or end-of-body) terminates a captured field.
_OPP_FIELD_LABELS = (
    "Decision criterion",
    "Rationale",
    "Evidence",
    "Suggested name",
    "Suggested trigger",
    "Estimated effort",
    "Build command",
    "Next step",
)


@lru_cache(maxsize=16)
def _field_pattern(label: str) -> re.Pattern[str]:
    """Compile (once per label) a regex that captures `**<label>:** ...` until
    the next recognized field label or section break."""
    labels = "|".join(re.escape(l) for l in _OPP_FIELD_LABELS)
    terminator = rf"(?:\n\*\*(?:{labels}):\*\*|\n---\s*\n|\n## )"
    return re.compile(rf"\*\*{re.escape(label)}:\*\*\s*([\s\S]*?)(?={terminator}|\Z)")


def extract_field(body: str, label: str) -> str | None:
    m = _field_pattern(label).search(body)
    if not m:
        return None
    return m.group(1).strip()


def extract_evidence(body: str) -> list[str]:
    """Pull bulleted evidence lines after **Evidence:**."""
    raw = extract_field(body, "Evidence")
    if not raw:
        return []
    return [ln.lstrip("- ").rstrip() for ln in raw.splitlines() if ln.startswith("- ")]


def _dedent_code_block(text: str) -> str:
    """Strip a leading 4-space indent from every line; pass others through."""
    lines = text.splitlines()
    out = []
    for ln in lines:
        if ln.startswith("    "):
            out.append(ln[4:])
        elif ln.strip() == "":
            out.append("")
        else:
            out.append(ln)
    return "\n".join(out).strip()


def extract_build_command(body: str) -> str | None:
    """Pull the build-command body — indented block or fenced block."""
    raw = extract_field(body, "Build command")
    if not raw:
        return None
    fenced = re.match(r"^```[a-z]*\n([\s\S]+?)\n```", raw)
    if fenced:
        return fenced.group(1).strip()
    return _dedent_code_block(raw)


def extract_next_step(body: str) -> str | None:
    """Pull the full Next-step block (description + any following code block)."""
    raw = extract_field(body, "Next step")
    if not raw:
        return None
    lines = raw.splitlines()
    descr_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False
    for ln in lines:
        if not in_code and ln.startswith("    "):
            in_code = True
        if in_code:
            code_lines.append(ln[4:] if ln.startswith("    ") else ln)
        else:
            descr_lines.append(ln)
    descr = "\n".join(descr_lines).strip()
    code = "\n".join(code_lines).strip()
    if code:
        return f"{descr}\n\n{code}" if descr else code
    return descr


def render_opportunity(opp: dict[str, Any]) -> str:
    body = opp["body"]
    rationale = extract_field(body, "Rationale") or ""
    suggested_name = extract_field(body, "Suggested name") or ""
    suggested_trigger = extract_field(body, "Suggested trigger") or ""
    effort = extract_field(body, "Estimated effort") or ""
    decision_criterion = extract_field(body, "Decision criterion") or ""
    evidence = extract_evidence(body)
    build_command = extract_build_command(body)
    next_step = extract_next_step(body)

    tier_class = "tier-low"
    prefix = opp["id"][:1] if opp["id"] else "L"
    if prefix == "H":
        tier_class = "tier-high"
        tier_label = "high"
    elif prefix == "M":
        tier_class = "tier-medium"
        tier_label = "medium"
    else:
        tier_label = "low"

    parts = ["<div class=\"opp\">"]
    parts.append("  <div class=\"opp-head\">")
    parts.append(f"    <span class=\"tier-badge {tier_class}\">{escape(tier_label)}</span>")
    parts.append(f"    <span class=\"type-badge\">{escape(opp['type'])}</span>")
    parts.append(f"    <h3>{escape(opp['id'])}. {escape(opp['name'])}</h3>")
    parts.append("  </div>")
    if decision_criterion:
        parts.append(f"  <p><em>Decision criterion: {escape(decision_criterion.strip('\"'))}</em></p>")
    if rationale:
        parts.append(f"  <p>{escape(rationale)}</p>")
    if evidence:
        parts.append("  <p><strong>Evidence</strong></p>\n  <ul>")
        for ev in evidence:
            # Evidence lines often look like `path/file:line — observation`
            parts.append(f"    <li>{escape(ev)}</li>")
        parts.append("  </ul>")
    meta_rows: list[tuple[str, str]] = []
    if suggested_name:
        meta_rows.append(("Suggested name", suggested_name.strip("`")))
    if suggested_trigger:
        meta_rows.append(("Suggested trigger", suggested_trigger))
    if effort:
        meta_rows.append(("Effort", effort))
    if meta_rows:
        parts.append(f"  {kv_block(meta_rows)}")
    if build_command:
        parts.append("  <div class=\"build-cmd-label\">Build command (copy-paste)</div>")
        parts.append(f"  <pre class=\"copyable\">{escape(build_command)}</pre>")
    elif next_step:
        parts.append("  <div class=\"build-cmd-label\">Next step</div>")
        parts.append(f"  <pre class=\"copyable\">{escape(next_step)}</pre>")
    parts.append("</div>")
    return "\n".join(parts)


def render_audit(marker: dict[str, Any]) -> str:
    sources = marker.get("data_sources", {}) or {}
    summary = marker.get("summary", {}) or {}
    audit_summary = safe_load_json(sources.get("audit_summary_json"))
    audit_md = safe_load_text(sources.get("audit_report_md")) or ""

    sections: list[str] = []

    target = summary.get("target") or marker.get("artifact_path") or "—"
    focus = summary.get("focus") or "all"
    depth = summary.get("depth") or "standard"
    rows: list[tuple[str, str]] = [
        ("Target", str(target)),
        ("Focus", str(focus)),
        ("Depth", str(depth)),
    ]
    if audit_summary:
        tc = audit_summary.get("tier_counts", {}) or {}
        rows.append(
            ("Tier counts",
             f"high {tc.get('high', 0)} • medium {tc.get('medium', 0)} • low {tc.get('low', 0)}")
        )
        rows.append(("Skipped (already covered)", str(audit_summary.get("skipped_existing", 0))))
        warnings = audit_summary.get("warnings") or []
        if warnings:
            rows.append(("Warnings", "; ".join(warnings)))
    rows.append(("Markdown report", str(sources.get("audit_report_md") or "—")))
    sections.append(
        "<section>\n"
        "  <h2>Audit overview</h2>\n"
        f"  {kv_block(rows)}\n"
        "</section>"
    )

    if audit_summary:
        by_type = audit_summary.get("by_type", {}) or {}
        if by_type:
            sections.append(
                "<section>\n"
                "  <h2>By artifact type</h2>\n"
                "  <table>\n"
                "    <tr><th>Type</th><th>Count</th></tr>\n"
                + "".join(
                    f"    <tr><td>{escape(k)}</td><td>{v}</td></tr>\n"
                    for k, v in by_type.items()
                )
                + "  </table>\n"
                "</section>"
            )

    opps = parse_audit_report(audit_md)
    if not opps and len(audit_md) > 200 and "### " in audit_md:
        # Non-trivial Markdown that yielded no opportunities — the synthesizer
        # template likely drifted from the `### H1. [<type>] <name>` shape.
        print(
            f"WARN: audit report at {sources.get('audit_report_md')!r} contains "
            "`### ` headings but no opportunities matched the expected "
            "`### [HML]\\d+\\. [<type>] <name>` pattern. Renderer will show "
            "the empty-state placeholder.",
            file=sys.stderr,
        )
    high = [o for o in opps if o["id"].startswith("H")]
    medium = [o for o in opps if o["id"].startswith("M")]
    low = [o for o in opps if o["id"].startswith("L")]

    for label, lst in [("High-value", high), ("Medium-value", medium), ("Low-value", low)]:
        if not lst:
            continue
        sec_parts = ["<section>", f"  <h2>{escape(label)} opportunities</h2>"]
        for opp in lst:
            sec_parts.append(render_opportunity(opp))
        sec_parts.append("</section>")
        sections.append("\n".join(sec_parts))

    if not opps:
        sections.append(
            "<section>\n"
            "  <h2>Opportunities</h2>\n"
            "  <p class=\"empty\">No opportunities parsed from the report. Inspect the source Markdown directly.</p>\n"
            "</section>"
        )

    return "\n".join(sections)


def render_workflow_eval(marker: dict[str, Any]) -> str:
    sources = marker.get("data_sources", {}) or {}
    summary = marker.get("summary", {}) or {}

    sections: list[str] = []

    rows = [
        ("Artifact path", marker.get("artifact_path") or "—"),
        ("Workspace", sources.get("eval_workspace") or "—"),
        ("Iterations run", str(summary.get("iterations_run", 1))),
    ]
    sections.append(
        "<section>\n"
        "  <h2>Re-evaluation overview</h2>\n"
        f"  {kv_block(rows)}\n"
        "</section>"
    )

    iters = summary.get("iterations") or []
    if not iters and sources.get("benchmark_json"):
        # Synthesize a single-iteration record from the bare benchmark.json
        # so workflow-eval marker shapes without an explicit `iterations` list
        # still render.
        b = safe_load_json(sources.get("benchmark_json"))
        if b:
            iters = [{"iteration": b.get("iteration", 1), "benchmark_path": sources.get("benchmark_json"), "benchmark": b}]

    if iters:
        for it in iters:
            n = it.get("iteration", "?")
            b = it.get("benchmark") or safe_load_json(it.get("benchmark_path"))
            if not b:
                continue
            wa = b.get("with_artifact_aggregate", 0.0)
            bl = b.get("baseline_aggregate", 0.0)
            lift = b.get("lift", wa - bl)
            passes = b.get("passes_done_definition", False)

            per_eval = b.get("per_eval", []) or []
            sections.append(
                "<section>\n"
                f"  <h2>Iteration {escape(str(n))}</h2>\n"
                f"  {metric_grid(wa, bl, lift, passes)}\n"
                + (f"  <p>{escape(b.get('summary', ''))}</p>\n" if b.get("summary") else "")
                + f"  {eval_tables(per_eval)}\n"
                "</section>"
            )

    conclusions = summary.get("conclusions")
    if conclusions:
        sections.append(
            "<section>\n"
            "  <h2>Conclusions</h2>\n"
            f"  <pre>{escape(conclusions)}</pre>\n"
            "</section>"
        )

    if not iters and not conclusions:
        sections.append(
            "<section>\n"
            "  <h2>Results</h2>\n"
            "  <p class=\"empty\">No benchmark or conclusions captured in marker.</p>\n"
            "</section>"
        )

    return "\n".join(sections)


RENDERERS = {
    "create": render_create,
    "modify": render_modify,
    "audit": render_audit,
    "workflow-eval": render_workflow_eval,
}


def compose_html(marker: dict[str, Any], marker_path: Path, html_path: Path) -> str:
    op = marker.get("operation", "")
    renderer = RENDERERS.get(op)
    if renderer is None:
        body_main = (
            "<main>\n"
            "<section>\n"
            f"  <h2>Unknown operation: {escape(op)}</h2>\n"
            f"  <pre>{escape(json.dumps(marker, indent=2))}</pre>\n"
            "</section>\n"
            "</main>\n"
        )
    else:
        body_main = f"<main>\n{renderer(marker)}\n</main>\n"

    title = f"claudefigflow {op}: {marker.get('artifact_name') or 'unnamed'}"
    body = header_html(marker) + body_main + footer_html(marker_path, html_path)
    return html_doc(title, body)


def process_marker(
    marker_path: Path,
    dry_run: bool = False,
    marker: dict[str, Any] | None = None,
) -> Path | None:
    """Render `<output-dir>/marker.json` into a sibling `index.html`.

    Callers that already have the marker dict in memory (e.g. write_marker.py
    after writing it) can pass `marker=` to skip the disk read + JSON parse.
    Standalone CLI callers leave it None; the file is read from `marker_path`.

    An output dir is "pending" iff it contains marker.json without an
    index.html; "rendered" once both exist. Atomic-write via tmp+rename so
    a crashed render never leaves a partially-written index.html behind.
    """
    html_path = marker_path.with_name("index.html")

    if dry_run:
        print(f"DRY-RUN: would render {marker_path} -> {html_path}")
        return None

    if marker is None:
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"WARN: skipping unreadable marker {marker_path}: {e}", file=sys.stderr)
            return None

    # PID-suffixed tmp so two processes never share the same staging file.
    # Concurrent renders are rare now that rendering is inline (one render
    # per operation), but kept for defense-in-depth in manual-recovery runs.
    tmp = html_path.with_suffix(html_path.suffix + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(compose_html(marker, marker_path, html_path), encoding="utf-8")
        tmp.replace(html_path)
    except OSError as e:
        print(f"WARN: could not write {html_path}: {e}", file=sys.stderr)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    return html_path


def find_pending_markers(base: Path) -> list[Path]:
    """Return marker.json paths under base whose sibling index.html is absent."""
    if not base.is_dir():
        return []
    pending: list[Path] = []
    for marker in sorted(base.glob("*/marker.json")):
        if not (marker.parent / "index.html").exists():
            pending.append(marker)
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description="Render claudefigflow operation markers to HTML")
    parser.add_argument("--marker", help="Path to a specific marker.json (default: scan outputs/ for pending dirs)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    args = parser.parse_args()

    if args.marker:
        markers = [Path(args.marker)]
    else:
        markers = find_pending_markers(outputs_dir())

    if not markers:
        return 0

    rendered: list[Path] = []
    for m in markers:
        out = process_marker(m, dry_run=args.dry_run)
        if out:
            rendered.append(out)

    if rendered and not args.dry_run:
        print(json.dumps({"rendered": [str(p) for p in rendered]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
