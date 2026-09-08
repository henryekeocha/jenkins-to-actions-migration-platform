"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from migration_analyzer import __version__
from migration_analyzer.analyzer import analyze, analyze_text
from migration_analyzer.model import Category
from migration_analyzer.report import render


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="migration-analyzer",
        description="Scan a Jenkinsfile and produce a GitHub Actions migration checklist.",
    )
    p.add_argument("jenkinsfile", nargs="?", default="Jenkinsfile", help="path, or - for stdin")
    p.add_argument("-f", "--format", choices=["markdown", "json", "text"], default="markdown")
    p.add_argument("-o", "--output", type=Path, help="write the report here instead of stdout")
    p.add_argument(
        "--fail-on",
        choices=[c.value for c in Category],
        help="exit 2 if any finding of this category (or more severe) exists; "
        "severity order is manual > review > auto > drop",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


_SEVERITY = {Category.MANUAL: 3, Category.REVIEW: 2, Category.AUTO: 1, Category.DROP: 0}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.jenkinsfile == "-":
        report = analyze_text(sys.stdin.read(), source="<stdin>")
    else:
        path = Path(args.jenkinsfile)
        if not path.is_file():
            print(f"migration-analyzer: {path}: no such file", file=sys.stderr)
            return 1
        report = analyze(path)

    text = render(report, args.format)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    if args.fail_on:
        threshold = _SEVERITY[Category(args.fail_on)]
        if any(_SEVERITY[f.category] >= threshold for f in report.findings):
            return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
