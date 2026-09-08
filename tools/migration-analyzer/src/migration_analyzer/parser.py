"""Lightweight, regex-based scanning of Jenkinsfile text.

This is not a Groovy parser. It strips comments and string contents where they would cause false
positives, then exposes the cleaned lines plus a few structural extractions (stage names, step
calls, credential IDs) that the rule engine and report use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(^|[^:'\"])//.*$")
_SHEBANG = re.compile(r"^#!.*$", re.MULTILINE)
_STAGE = re.compile(r"\bstage\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
_LIBRARY = re.compile(r"@Library\s*\(\s*['\"]([^'\"@]+)(?:@[^'\"]+)?['\"]\s*\)")
_CREDENTIALS = re.compile(r"\bcredentials\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
_CREDENTIALS_ID = re.compile(r"credentialsId\s*:\s*['\"]([^'\"]+)['\"]")
# A step-style call at the start of a statement (line start, or after `{` / `;`):
# `name(...)`, `name key: value`, or `name 'literal'`.
_STEP_CALL = re.compile(
    r"(?:^|[{;])\s*([A-Za-z_][A-Za-z0-9_]*)(?:\s*\(|\s+[A-Za-z_][A-Za-z0-9_]*\s*:|\s+['\"])"
)
_DEF = re.compile(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


@dataclass
class Scanned:
    original_lines: list[str]
    lines: list[str]  # comment-stripped, same length as original_lines
    stages: list[str] = field(default_factory=list)
    shared_library: str | None = None
    credential_ids: list[str] = field(default_factory=list)
    step_calls: dict[str, list[int]] = field(default_factory=dict)  # name -> 1-based lines
    local_defs: set[str] = field(default_factory=set)


def strip_comments(text: str) -> str:
    """Remove block and line comments while preserving line count."""
    text = _SHEBANG.sub("", text)

    def _blank_keep_newlines(m: re.Match[str]) -> str:
        return "\n" * m.group(0).count("\n")

    text = _BLOCK_COMMENT.sub(_blank_keep_newlines, text)
    return "\n".join(_LINE_COMMENT.sub(r"\1", line) for line in text.split("\n"))


def scan(text: str) -> Scanned:
    original = text.split("\n")
    cleaned = strip_comments(text).split("\n")
    assert len(cleaned) == len(original)

    s = Scanned(original_lines=original, lines=cleaned)
    joined = "\n".join(cleaned)

    s.stages = _STAGE.findall(joined)
    lib = _LIBRARY.search(joined)
    s.shared_library = lib.group(1) if lib else None

    seen: dict[str, None] = {}
    for m in _CREDENTIALS.finditer(joined):
        seen.setdefault(m.group(1))
    for m in _CREDENTIALS_ID.finditer(joined):
        seen.setdefault(m.group(1))
    s.credential_ids = list(seen)

    s.local_defs = set(_DEF.findall(joined))

    for i, line in enumerate(cleaned, start=1):
        for m in _STEP_CALL.finditer(line):
            s.step_calls.setdefault(m.group(1), []).append(i)
    return s
