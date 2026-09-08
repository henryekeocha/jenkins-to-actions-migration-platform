"""Render a Report as markdown, plain text, or JSON."""

from __future__ import annotations

import json

from migration_analyzer.model import Category, Report

_ORDER = [Category.MANUAL, Category.REVIEW, Category.AUTO, Category.DROP]
_HEADING = {
    Category.MANUAL: "Needs a decision (no direct equivalent)",
    Category.REVIEW: "Has an equivalent, needs configuration or review",
    Category.AUTO: "Mechanical mapping",
    Category.DROP: "Goes away",
}


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)


def to_markdown(report: Report) -> str:
    out: list[str] = []
    out.append(f"# Migration checklist: `{report.source}`")
    out.append("")
    s = report.summary
    out.append(
        f"{report.lines} lines, {len(report.stages)} stages, "
        f"{len(report.findings)} findings: "
        f"**{s['manual']} manual**, {s['review']} review, {s['auto']} auto, {s['drop']} drop."
    )
    out.append("")

    if report.stages:
        out.append("## Stages")
        out.append("")
        out.extend(f"- {name}" for name in report.stages)
        out.append("")

    if report.shared_library or report.shared_library_steps:
        out.append("## Shared library")
        out.append("")
        if report.shared_library:
            out.append(f"Imports `{report.shared_library}`.")
        if report.shared_library_steps:
            out.append("Steps that need composite actions:")
            out.extend(f"- `{name}`" for name in report.shared_library_steps)
        out.append("")

    if report.credential_ids:
        out.append("## Secrets to create")
        out.append("")
        out.append("| Jenkins credential ID | GitHub secret | Scope |")
        out.append("|---|---|---|")
        for cid in report.credential_ids:
            out.append(f"| `{cid}` | `{_secret_name(cid)}` | repo / environment / org (decide) |")
        out.append("")

    if report.plugin_steps:
        out.append("## Plugin steps in use")
        out.append("")
        out.extend(f"- `{name}`" for name in report.plugin_steps)
        out.append("")

    for cat in _ORDER:
        items = [f for f in report.findings if f.category is cat]
        if not items:
            continue
        out.append(f"## {_HEADING[cat]} ({len(items)})")
        out.append("")
        for f in items:
            box = "[ ]" if cat in (Category.MANUAL, Category.REVIEW) else "[x]"
            title = f.title if not f.detail else f"{f.title}: `{f.detail}`"
            out.append(f"- {box} **L{f.line}** {title}")
            out.append(f"  - Actions: {f.actions_equivalent}")
            if f.note:
                out.append(f"  - Note: {f.note}")
            out.append(f"  - `{_truncate(f.snippet)}`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def to_text(report: Report) -> str:
    out: list[str] = [f"{report.source}: {len(report.findings)} findings {report.summary}"]
    for f in report.findings:
        title = f.title if not f.detail else f"{f.title}: {f.detail}"
        out.append(f"L{f.line:<4} {f.category.value:<6} {f.rule:<22} {title}")
    return "\n".join(out) + "\n"


def render(report: Report, fmt: str) -> str:
    if fmt == "json":
        return to_json(report)
    if fmt == "text":
        return to_text(report)
    return to_markdown(report)


def _secret_name(credential_id: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in credential_id).upper()


def _truncate(s: str, n: int = 100) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
