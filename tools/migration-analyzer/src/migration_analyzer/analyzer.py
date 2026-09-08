"""Apply the rule table to a scanned Jenkinsfile and build a Report."""

from __future__ import annotations

from pathlib import Path

from migration_analyzer.model import Category, Finding, Report
from migration_analyzer.parser import scan
from migration_analyzer.rules import KNOWN_STEPS, PLUGIN_STEPS, RULES


def analyze_text(text: str, source: str = "<stdin>") -> Report:
    scanned = scan(text)
    report = Report(source=source, lines=len(scanned.lines))
    report.stages = scanned.stages
    report.shared_library = scanned.shared_library
    report.credential_ids = scanned.credential_ids

    findings: list[Finding] = []
    for rule in RULES:
        for lineno, line in enumerate(scanned.lines, start=1):
            m = rule.pattern.search(line)
            if not m:
                continue
            detail = m.group(1) if m.groups() and m.group(1) else ""
            findings.append(
                Finding(
                    rule=rule.id,
                    category=rule.category,
                    line=lineno,
                    snippet=scanned.original_lines[lineno - 1].strip(),
                    title=rule.title,
                    actions_equivalent=rule.actions_equivalent,
                    note=rule.note,
                    detail=detail,
                )
            )
            if rule.once:
                break

    # Step-style calls that are neither built-in, plugin-provided, nor defined in the file are
    # assumed to come from the shared library. Each is a composite action to write.
    library_steps = sorted(
        name
        for name in scanned.step_calls
        if name not in KNOWN_STEPS and name not in scanned.local_defs and not name[0].isupper()
    )
    report.shared_library_steps = library_steps
    for name in library_steps:
        first = scanned.step_calls[name][0]
        findings.append(
            Finding(
                rule="shared-library-step",
                category=Category.MANUAL,
                line=first,
                snippet=scanned.original_lines[first - 1].strip(),
                title=f"Shared-library step `{name}`",
                actions_equivalent=f"A composite action `.github/actions/{_kebab(name)}`.",
                note=f"Called {len(scanned.step_calls[name])} time(s).",
                detail=name,
            )
        )

    report.plugin_steps = sorted(n for n in scanned.step_calls if n in PLUGIN_STEPS)

    findings.sort(key=lambda f: (f.line, f.rule))
    report.findings = findings
    return report


def analyze(path: str | Path) -> Report:
    p = Path(path)
    return analyze_text(p.read_text(encoding="utf-8"), source=str(p))


def _kebab(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper():
            out.append("-" + ch.lower())
        else:
            out.append(ch)
    return "".join(out).lstrip("-")
