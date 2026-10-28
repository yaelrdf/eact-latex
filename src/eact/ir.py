"""Intermediate representation shared by every front-end and back-end.

    LaTeX  --latex.py-->  \\
                           Doc  --encoder.py-->  .g2e bytes
    .eam   --eam.py---->  /     <--decoder.py--

A :class:`Doc` is a title plus a list of blocks.  A block is a text line or a
note strip.  A text line is a list of inline nodes; structure nodes (Frac,
Sqrt, ...) hold their arguments as nested node lists, so structures nest
freely, exactly as they do in the file format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Char:
    """One calculator character, already encoded.  ``src`` is for previews/dumps."""
    code: bytes
    src: str = ""


@dataclass
class Frac:
    num: "Nodes"
    den: "Nodes"


@dataclass
class Sqrt:
    body: "Nodes"


@dataclass
class Pow:
    """Superscript/exponent applied to whatever precedes it."""
    exp: "Nodes"


@dataclass
class Abs:
    body: "Nodes"


@dataclass
class Sum:
    """Σ(expr, var, start, end)."""
    expr: "Nodes"
    var: "Nodes"
    start: "Nodes"
    end: "Nodes"


@dataclass
class Integral:
    """∫ from lower to upper of body dx (the calculator always shows 'dx')."""
    body: "Nodes"
    lower: "Nodes"
    upper: "Nodes"


@dataclass
class Log:
    """log_base(arg)."""
    base: "Nodes"
    arg: "Nodes"


@dataclass
class Diff:
    """d/dx(body)|x=at, or d²/dx² when order == 2."""
    body: "Nodes"
    at: "Nodes"
    order: int = 1


@dataclass
class Matrix:
    rows: list[list["Nodes"]]


Node = Union[Char, Frac, Sqrt, Pow, Abs, Sum, Integral, Log, Diff, Matrix]
Nodes = list[Node]


@dataclass
class TextLine:
    nodes: Nodes = field(default_factory=list)
    src_line: int = 0


@dataclass
class Note:
    """A collapsible note strip: a title plus its own text lines."""
    title: Nodes
    lines: list[TextLine] = field(default_factory=list)
    src_line: int = 0


Block = Union[TextLine, Note]


@dataclass
class Doc:
    title: str = "NOTES"
    blocks: list[Block] = field(default_factory=list)
