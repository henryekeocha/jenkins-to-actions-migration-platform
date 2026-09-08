"""Data model for analyzer output."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Category(StrEnum):
    """How much human work a construct needs to migrate.

    AUTO   - has a direct GitHub Actions equivalent; the mapping is mechanical.
    REVIEW - has an equivalent but something must be configured outside the workflow file
             (a secret, an environment, a marketplace action) or semantics differ slightly.
    MANUAL - no equivalent; someone has to decide what to do.
    DROP   - Jenkins-only plumbing that simply goes away.
    """

    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"
    DROP = "drop"


@dataclass(frozen=True)
class Finding:
    rule: str
    category: Category
    line: int
    snippet: str
    title: str
    actions_equivalent: str
    note: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class Report:
    source: str
    findings: list[Finding] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    credential_ids: list[str] = field(default_factory=list)
    shared_library: str | None = None
    shared_library_steps: list[str] = field(default_factory=list)
    plugin_steps: list[str] = field(default_factory=list)
    lines: int = 0

    def count(self, category: Category) -> int:
        return sum(1 for f in self.findings if f.category is category)

    @property
    def summary(self) -> dict[str, int]:
        return {c.value: self.count(c) for c in Category}

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "lines": self.lines,
            "summary": self.summary,
            "stages": self.stages,
            "shared_library": self.shared_library,
            "shared_library_steps": self.shared_library_steps,
            "plugin_steps": self.plugin_steps,
            "credential_ids": self.credential_ids,
            "findings": [f.to_dict() for f in self.findings],
        }
