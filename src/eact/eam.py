"""EactMaker markup (.eam) <-> IR.

This is the markup typed into https://tools.planet-casio.com/EactMaker/ and
saved in its ``.eam`` project files (``g2e\\x1eTITLE\\x1ePASSWORD\\x1eCONTENT``).
Supporting it lets us check our encoder byte-for-byte against EactMaker and
gives agents a precise, low-level target language.  See docs/EAM_SYNTAX.md.

Argument order follows EactMaker, which is not always the natural one:

    \\sum{end}{var}{start}{expr}     \\int{upper}{lower}{body}     \\log{base}{arg}

Extension (not in EactMaker): ``\\raw{8D 1A}`` inserts raw bytes.
"""
from __future__ import annotations

import re

from . import charmap as _charmap
from .diagnostics import Reporter
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Node, Note, Pow, Sqrt, Sum, TextLine

ESCAPES = {"\\": b"\x5c", "{": b"\x7b", "}": b"\x7d", "_": b"\x5f", "^": b"\x5e", "&": b"\x26"}
# name -> number of {} arguments (None = variable, for \mat)
STRUCTURES = {"sqrt": 1, "frac": 2, "abs": 1, "sum": 4, "log": 2, "diff": 2, "diff2": 2,
              "int": 3, "mat": None, "note": 2, "raw": 1}
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


class _Parser:
    def __init__(self, text: str, rep: Reporter, cmap):
        self.s = text
        self.i = 0
        self.rep = rep
        self.cmap = cmap
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    # -- helpers ------------------------------------------------------------
    def pos(self, i=None):
        i = self.i if i is None else i
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= i:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, i - self.line_starts[lo] + 1

    def err(self, code, msg, i=None, hint=""):
        line, col = self.pos(i)
        self.rep.add(code, msg, line, col, hint)

    def peek(self, k=0):
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def at_newline(self):
        return self.peek() in ("\n", "\r")

    def skip_newline(self):
        if self.peek() == "\r":
            self.i += 1
        if self.peek() == "\n":
            self.i += 1

    # -- characters ---------------------------------------------------------
    def char(self, ch: str, i: int) -> list[Node]:
        if ch == "\t":
            self.err("W007", "tab replaced by a space", i)
            return [Char(b" ", " ")]
        code = self.cmap.encode_char(ch)
        if code is not None:
            return [Char(code, ch)]
        fb = self.cmap.fallback(ch)
        if fb:
            self.err("W001", f"'{ch}' (U+{ord(ch):04X}) has no CASIO glyph; written as '{fb[1]}'", i)
            return [Char(fb[0], fb[1])]
        self.err("E002", f"'{ch}' (U+{ord(ch):04X}) has no CASIO glyph", i,
                 "remove it or replace it with a supported symbol (see `eact symbols`)")
        return []

    # -- groups -------------------------------------------------------------
    def group(self, what: str, stops: str = "", allow_newlines=False) -> list[Node] | None:
        """Parse '{ ... }' and return its nodes; None if there is no '{'."""
        if self.peek() != "{":
            return None
        start = self.i
        self.i += 1
        nodes = self.inline(stops="}" + stops, allow_newlines=allow_newlines)
        if self.peek() != "}":
            self.err("E004", f"unclosed '{{' in {what}", start, "add the missing '}'")
            return nodes
        self.i += 1
        return nodes

    def args(self, name: str, n: int, start: int) -> list[list[Node]] | None:
        out = []
        for k in range(n):
            g = self.group(f"argument {k + 1} of \\{name}")
            if g is None:
                self.err("E003", f"\\{name} needs {n} {{}} arguments, found {k}", start,
                         f"write \\{name}" + "{…}" * n)
                return None
            out.append(g)
        return out

    def inline(self, stops: str = "", allow_newlines=False, in_arg=None) -> list[Node]:
        """Parse until a stop character, end of input, or (by default) a newline.

        ``in_arg`` says whether we are inside a command argument (where a line
        break is an error); it defaults to "there are stop characters".
        """
        if in_arg is None:
            in_arg = bool(stops)
        nodes: list[Node] = []
        while self.i < len(self.s):
            ch = self.peek()
            if ch in stops:
                break
            if ch in "\r\n":
                if not allow_newlines:
                    if in_arg:
                        self.err("E007", "line break inside a command argument")
                    break
                nodes.append(_NEWLINE)
                self.skip_newline()
                continue
            start = self.i
            if ch == "\\":
                nodes.extend(self.command())
            elif ch == "^":
                self.i += 1
                g = self.group("^")
                if g is None:
                    c = self.peek()
                    if not c or c in "\r\n":
                        self.err("E003", "'^' needs an exponent", start)
                        continue
                    self.i += 1
                    g = self.char(c, start + 1)
                nodes.append(Pow(g))
            elif ch == "_":
                self.i += 1
                nodes.extend(self.subscript(start))
            elif ch == "{":
                # Bare braces are literal text in EactMaker.
                self.i += 1
                nodes.append(Char(b"{", "{"))
                nodes.extend(self.inline(stops="}" + stops.replace("}", ""), allow_newlines=allow_newlines,
                                         in_arg=in_arg))
                if self.peek() == "}":
                    self.i += 1
                    nodes.append(Char(b"}", "}"))
            else:
                self.i += 1
                nodes.extend(self.char(ch, start))
        return nodes

    def subscript(self, start: int) -> list[Node]:
        if self.peek() == "{":
            self.i += 1
            chars = []
            while self.peek() and self.peek() != "}":
                if self.at_newline():
                    break
                chars.append((self.peek(), self.i))
                self.i += 1
            if self.peek() == "}":
                self.i += 1
            else:
                self.err("E004", "unclosed '{' in subscript", start)
        else:
            c = self.peek()
            if not c or c in "\r\n":
                self.err("E003", "'_' needs a character", start)
                return []
            chars = [(c, self.i)]
            self.i += 1
        out: list[Node] = []
        for c, i in chars:
            code = self.cmap.subscript(c)
            if code:
                out.append(Char(code, "_" + c))
            else:
                self.err("W002", f"no subscript glyph for '{c}'; written inline after '_'", i,
                         "only A-Z, a-z, 0-9, + and - have subscript glyphs")
                out.append(Char(b"_", "_"))
                out.extend(self.char(c, i))
        return out

    def command(self) -> list[Node]:
        start = self.i
        self.i += 1  # backslash
        c = self.peek()
        if c in ESCAPES:
            self.i += 1
            return [Char(ESCAPES[c], c)]
        m = NAME_RE.match(self.s, self.i)
        if not m:
            self.err("E001", "lone '\\'", start, "write \\\\ for a literal backslash")
            return [Char(b"\\", "\\")]
        name = m.group(0)
        self.i = m.end()
        if self.peek() == ";":
            sym = self.cmap.func(name)
            if sym:
                self.i += 1
                return [Char(sym.code, f"\\{name};")]
        if name in STRUCTURES and self.peek() == "{":
            return self.structure(name, start)
        # A digit can end a structure name (\diff2) or belong to a symbol name.
        self.err("E001", f"unknown command \\{name}", start, _suggest(name, self.cmap))
        return [Char(b"\\", "\\")] + [n for ch in name for n in self.char(ch, start)]

    def structure(self, name: str, start: int) -> list[Node]:
        if name == "mat":
            rows = []
            while self.peek() == "{":
                self.i += 1
                row, cell = [], []
                while self.peek() and self.peek() != "}":
                    cell = self.inline(stops="&}")
                    row.append(cell)
                    if self.peek() == "&":
                        self.i += 1
                    elif self.at_newline() or not self.peek():
                        break
                if self.peek() != "}":
                    self.err("E004", "unclosed matrix row", start)
                else:
                    self.i += 1
                rows.append(row or [[]])
            widths = {len(r) for r in rows}
            if len(widths) > 1:
                self.err("E004", f"matrix rows have different lengths {sorted(widths)}", start)
            return [Matrix(rows)]
        if name == "note":
            self.err("E007", "\\note must start its own line", start)
            return []
        if name == "raw":
            g_start = self.i
            self.i += 1
            end = self.s.find("}", self.i)
            if end < 0:
                self.err("E004", "unclosed \\raw{", start)
                return []
            hexs = self.s[self.i:end]
            self.i = end + 1
            try:
                return [Char(bytes.fromhex(hexs), f"\\raw{{{hexs}}}")]
            except ValueError:
                self.err("E006", f"\\raw{{{hexs}}} is not a hex byte sequence", g_start)
                return []
        a = self.args(name, STRUCTURES[name], start)
        if a is None:
            return []
        if name == "sqrt":
            return [Sqrt(a[0])]
        if name == "frac":
            return [Frac(a[0], a[1])]
        if name == "abs":
            return [Abs(a[0])]
        if name == "sum":
            return [Sum(expr=a[3], var=a[1], start=a[2], end=a[0])]
        if name == "log":
            return [Log(a[0], a[1])]
        if name in ("diff", "diff2"):
            return [Diff(a[0], a[1], 2 if name == "diff2" else 1)]
        if name == "int":
            return [Integral(body=a[2], lower=a[1], upper=a[0])]
        raise AssertionError(name)

    # -- document -----------------------------------------------------------
    def document(self) -> list:
        blocks = []
        while self.i <= len(self.s):
            if self.s.startswith("\\note{", self.i):
                blocks.append(self.note())
                # The rest of the line after the note (normally empty) is dropped
                # by EactMaker; we keep any text as its own line.
                rest_start = self.i
                rest = self.inline()
                if rest:
                    blocks.append(TextLine(rest, self.pos(rest_start)[0]))
            else:
                line_no = self.pos()[0]
                blocks.append(TextLine(self.inline(), line_no))
            if self.i >= len(self.s):
                break
            self.skip_newline()
        return blocks

    def note(self) -> Note:
        start = self.i
        line_no = self.pos()[0]
        self.i += len("\\note")
        title = self.group("\\note title") or []
        if self.peek() != "{":
            self.err("E003", "\\note needs {title}{content}", start)
            return Note(title, [], line_no)
        body = self.group("\\note content", allow_newlines=True) or []
        lines, cur = [], []
        for n in body:
            if n is _NEWLINE:
                lines.append(TextLine(cur))
                cur = []
            else:
                cur.append(n)
        lines.append(TextLine(cur))
        return Note(title, lines, line_no)


_NEWLINE = Char(b"", "\n")


def _suggest(name: str, cmap) -> str:
    import difflib
    names = list(STRUCTURES) + [s.eam[1:-1] for s in cmap.symbols if s.eam.startswith("\\") and s.eam.endswith(";")]
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.75)
    return ("did you mean " + ", ".join("\\" + c for c in close) + "?") if close else \
        "see `eact symbols --eam` for the list of commands"


def parse_content(text: str, rep: Reporter, cmap=None) -> list:
    """Parse EactMaker markup into IR blocks."""
    return _Parser(text, rep, cmap or _charmap.default()).document()


def parse_file_text(text: str, rep: Reporter, default_title: str = "NOTES") -> Doc:
    """Parse a .eam project file, or bare markup if it has no .eam header."""
    title = default_title
    if "\x1e" in text:
        parts = text.split("\x1e", 3)
        if len(parts) == 4:
            _fmt, title, _password, text = parts
    return Doc(title=title, blocks=parse_content(text, rep))


# -- IR -> markup ------------------------------------------------------------

def _w(nodes, cmap) -> str:
    out = []
    for n in nodes:
        if isinstance(n, Char):
            sym = cmap.lookup(n.code)
            out.append(sym.eam if sym else "\\raw{" + n.code.hex(" ").upper() + "}")
        elif isinstance(n, Frac):
            out.append(f"\\frac{{{_w(n.num, cmap)}}}{{{_w(n.den, cmap)}}}")
        elif isinstance(n, Sqrt):
            out.append(f"\\sqrt{{{_w(n.body, cmap)}}}")
        elif isinstance(n, Abs):
            out.append(f"\\abs{{{_w(n.body, cmap)}}}")
        elif isinstance(n, Pow):
            out.append(f"^{{{_w(n.exp, cmap)}}}")
        elif isinstance(n, Sum):
            out.append("\\sum" + "".join("{" + _w(g, cmap) + "}" for g in (n.end, n.var, n.start, n.expr)))
        elif isinstance(n, Integral):
            out.append("\\int" + "".join("{" + _w(g, cmap) + "}" for g in (n.upper, n.lower, n.body)))
        elif isinstance(n, Log):
            out.append(f"\\log{{{_w(n.base, cmap)}}}{{{_w(n.arg, cmap)}}}")
        elif isinstance(n, Diff):
            out.append(f"\\diff{'2' if n.order == 2 else ''}{{{_w(n.body, cmap)}}}{{{_w(n.at, cmap)}}}")
        elif isinstance(n, Matrix):
            out.append("\\mat" + "".join("{" + "&".join(_w(c, cmap) for c in row) + "}" for row in n.rows))
        else:
            raise TypeError(n)
    return "".join(out)


def write_content(doc: Doc, newline: str = "\r\n") -> str:
    cmap = _charmap.default()
    out = []
    for b in doc.blocks:
        if isinstance(b, Note):
            body = newline.join(_w(l.nodes, cmap) for l in b.lines)
            out.append(f"\\note{{{_w(b.title, cmap)}}}{{{body}}}")
        else:
            out.append(_w(b.nodes, cmap))
    return newline.join(out)


def write_file_text(doc: Doc, fmt: str = "g2e") -> str:
    """A .eam project file that EactMaker's 'Load' button can open."""
    return f"{fmt}\x1e{doc.title}\x1e\x1e" + write_content(doc)
