#!/usr/bin/env python3
"""Render the Backstage skeleton with placeholder values so its contents can be linted.

Mimics the two things the scaffolder's fetch:template action does that matter for validation:
substitute `${{ values.* }}` in file contents and in path segments, and turn a quoted literal
`${{ '...' }}` into the literal (that is how the skeleton emits GitHub `${{ github.ref }}`
expressions). Not the real Nunjucks engine; enough for actionlint, helm lint and go vet.

Usage: hack/render-skeleton.py SKELETON_DIR OUT_DIR
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

VALUES = {
    "name": "example-svc",
    "description": "Example service",
    "owner": "group:default/team-a",
    "goVersion": "1.22",
    "healthUrlStaging": "",
    "repoUrl": "github.com?owner=example-org&repo=example-svc",
    "destination.owner": "example-org",
    "destination.repo": "example-svc",
}
_LITERAL = re.compile(r"\$\{\{\s*'((?:[^']|'')*)'\s*\}\}")
_VALUE = re.compile(r"\$\{\{\s*values\.([a-zA-Z0-9_.]+)\s*\}\}")


def render(text: str) -> str:
    text = _LITERAL.sub(lambda m: m.group(1).replace("''", "'"), text)
    return _VALUE.sub(lambda m: VALUES.get(m.group(1), "placeholder"), text)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src, out = Path(argv[1]), Path(argv[2])
    if out.exists():
        shutil.rmtree(out)
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = Path(render(str(path.relative_to(src))))
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(path.read_text()))
    print(f"rendered {src} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
