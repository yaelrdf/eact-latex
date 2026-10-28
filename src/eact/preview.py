"""Plain-text approximation of how a document looks on the calculator.

The fx-9750GIII screen shows 21 characters x 8 rows in the eActivity app.
Text lines wrap at 21 columns.  2-D structures are drawn in *linear*
notation here (√(x), (a)/(b), Σ(expr,k,0,n), ...) and are therefore shorter
or longer than on the real screen: the preview tells you *what* is in the
file, not exactly *where* it lands.  Width checks use the linear form.
"""
from __future__ import annotations

from . import charmap as _charmap
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Note, Pow, Sqrt, Sum, TextLine

SCREEN_COLS = 21


def _paren(s: str) -> str:
    return s if len(s) <= 1 else f"({s})"


def linear(nodes, cmap=None) -> str:
    cmap = cmap or _charmap.default()
    out = []
    for n in nodes:
        if isinstance(n, Char):
            sym = cmap.lookup(n.code)
            out.append(sym.preview if sym else "¿")
        elif isinstance(n, Frac):
            out.append(f"{_paren(linear(n.num, cmap))}/{_paren(linear(n.den, cmap))}")
        elif isinstance(n, Sqrt):
            out.append("√" + _paren(linear(n.body, cmap)))
        elif isinstance(n, Abs):
            out.append(f"|{linear(n.body, cmap)}|")
        elif isinstance(n, Pow):
            out.append("^" + _paren(linear(n.exp, cmap)))
        elif isinstance(n, Sum):
            args = ",".join(linear(g, cmap) for g in (n.expr, n.var, n.start, n.end))
            out.append(f"Σ({args})")
        elif isinstance(n, Integral):
            out.append(f"∫[{linear(n.lower, cmap)}→{linear(n.upper, cmap)}]({linear(n.body, cmap)})dx")
        elif isinstance(n, Log):
            out.append(f"log_{_paren(linear(n.base, cmap))}({linear(n.arg, cmap)})")
        elif isinstance(n, Diff):
            d = "d²/dx²" if n.order == 2 else "d/dx"
            out.append(f"{d}({linear(n.body, cmap)})|x={linear(n.at, cmap)}")
        elif isinstance(n, Matrix):
            out.append("[" + "".join("[" + ",".join(linear(c, cmap) for c in row) + "]" for row in n.rows) + "]")
    return "".join(out)


def has_structure(nodes) -> bool:
    return any(not isinstance(n, Char) for n in nodes)


def wrap(text: str, cols: int = SCREEN_COLS) -> list[str]:
    if not text:
        return [""]
    return [text[i:i + cols] for i in range(0, len(text), cols)]


def render(doc: Doc, cols: int = SCREEN_COLS) -> str:
    """Return the preview as text, framed to the screen width."""
    cmap = _charmap.default()
    rows = []
    title = "======" + doc.title.ljust(8) + "======="
    rows += wrap(title, cols)
    for b in doc.blocks:
        if isinstance(b, Note):
            rows.append(("▸ " + linear(b.title, cmap)).ljust(cols - 5)[:cols - 5] + "NOTES")
            for line in b.lines:
                rows += ["│" + r for r in wrap(linear(line.nodes, cmap), cols - 1)]
        elif isinstance(b, TextLine):
            rows += wrap(linear(b.nodes, cmap), cols)
    border = "+" + "-" * cols + "+"
    return "\n".join([border] + ["|" + r.ljust(cols) + "|" for r in rows] + [border])
