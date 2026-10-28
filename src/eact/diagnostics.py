"""Diagnostics: every problem the converter finds, with a stable code.

Codes are documented in docs/DIAGNOSTICS.md and must never be renumbered:
agents and scripts match on them.

Severity:
* ``error``   -- the output would be wrong; ``eact build`` refuses to write it.
* ``warning`` -- the output is written but differs from the source (a fallback
  was used); ``--strict`` turns these into failures.
* ``info``    -- worth knowing, nothing was changed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

# code -> (severity, short title).  Keep in sync with docs/DIAGNOSTICS.md.
CODES = {
    "E001": ("error", "unknown command"),
    "E002": ("error", "character has no CASIO glyph"),
    "E003": ("error", "missing argument"),
    "E004": ("error", "unbalanced braces or delimiters"),
    "E006": ("error", "invalid \\raw byte sequence"),
    "E007": ("error", "structure not allowed here"),
    "E008": ("error", "empty document"),
    "E009": ("error", "invalid title"),
    "W001": ("warning", "character replaced by a look-alike"),
    "W002": ("warning", "subscript has no glyph; written inline"),
    "W003": ("warning", "LaTeX construct approximated"),
    "W004": ("warning", "formatting ignored"),
    "W005": ("warning", "command ignored"),
    "W006": ("warning", "title adjusted"),
    "W007": ("warning", "tab replaced by space"),
    "W008": ("warning", "integration variable is not x"),
    "W009": ("warning", "no LaTeX form; written as \\raw"),
    "I001": ("info", "line wider than the screen (wraps or scrolls on the calculator)"),
    "I002": ("info", "notes in G1E files are untested"),
}


@dataclass
class Diagnostic:
    code: str
    message: str
    line: int = 0
    col: int = 0
    hint: str = ""
    file: str = ""
    severity: str = field(init=False)

    def __post_init__(self):
        self.severity = CODES[self.code][0]

    def format(self) -> str:
        where = f"{self.file or '<input>'}:{self.line}:{self.col}"
        text = f"{where}: {self.severity} {self.code}: {self.message}"
        if self.hint:
            text += f"\n    hint: {self.hint}"
        return text


class Reporter:
    """Collects diagnostics while parsing/encoding."""

    def __init__(self, file: str = ""):
        self.file = file
        self.items: list[Diagnostic] = []

    def add(self, code: str, message: str, line: int = 0, col: int = 0, hint: str = "") -> None:
        self.items.append(Diagnostic(code, message, line, col, hint, self.file))

    def extend(self, other: "Reporter") -> None:
        self.items.extend(other.items)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.items if d.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.items if d.severity == "warning"]

    def to_json(self, **extra) -> str:
        payload = {
            "ok": not self.errors,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "diagnostics": [asdict(d) for d in self.items],
        }
        payload.update(extra)
        return json.dumps(payload, ensure_ascii=False, indent=2)
