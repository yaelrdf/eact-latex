"""IR -> LaTeX: the inverse of latex.py.

Turns any decoded eActivity (made by eact, by EactMaker or on the calculator)
into a LaTeX document that

* compiles with a normal LaTeX installation (the preamble defines the eact
  extensions ``\\note``, ``\\diff``, ``\\casio`` and ``\\raw`` when they are used), and
* converts back with ``eact build`` to the same calculator content.  The
  exceptions are listed in docs/LATEX_OUTPUT.md (spaces next to operators
  inside formulas, superscript glyphs, ASCII '-' inside formulas, ...).

The file format does not mark which characters were math, so a line is
split into words and each word is classified:

* a word with a 2-D structure, a math glyph (Greek, ≤, subscripts, ...) or an
  operator (= + − < > ...) is math;
* a single lower-case consonant (``x``, ``n``) is math; a vowel (``a``, ``y``)
  is not, because ``a``/``y``/``o``/``e`` are Spanish words, and neither is a
  capital (``A`` alone is more often a label than a matrix);
* a math word joins its neighbour across a space when an operator sits at
  the boundary (``f(x) = x`` is one formula) and the neighbour is not a word;
* a function name joins the formula that follows it (``sin x``), so the
  Spanish word "sin" stays text in "sin embargo";
* trailing punctuation (``.,;:!?``) is moved out of the formula.

A line that is one formula becomes display math ``\\[ … \\]``.
"""
from __future__ import annotations

import re

from . import __version__
from . import charmap as _charmap
from . import latex
from .diagnostics import Reporter
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Node, Note, Pow, Sqrt, Sum, TextLine

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

# Unicode -> math command.  Built from the parser's own tables so that every
# command written here is one latex.py reads back to the same glyph.
_SKIP = {"imath", "jmath", "ast", "colon", "prime", "degree", "mid", "vert", "lbrace", "rbrace",
         "S", "copyright", "pounds", "euro", "yen", "cent", "backslash"}
MATH_COMMANDS: dict[str, str] = {}
for _name, _ch in {**latex.GREEK, **latex.SYMBOLS}.items():
    if _name.isalpha() and _name not in _SKIP:
        MATH_COMMANDS.setdefault(_ch, _name)
MATH_COMMANDS.update({"ε": "varepsilon", "→": "to", "←": "leftarrow", "⇒": "Rightarrow",
                      "⇔": "Leftrightarrow", "∥": "parallel", "|": "vert", "∧": "land", "∨": "lor",
                      "…": "ldots", "·": "cdot", "□": "square", "◇": "diamond"})

MATH_ESCAPES = {"{": r"\{", "}": r"\}", "%": r"\%", "$": r"\$", "#": r"\#", "&": r"\&", "_": r"\_",
                "\\": r"\backslash", "−": "-", "-": "-", "′": "'", "″": "''", "°": r"^{\circ}",
                "^": r"\text{\textasciicircum}", "`": r"\text{\textasciigrave}"}
TEXT_ESCAPES = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "%": r"\%", "&": r"\&",
                "#": r"\#", "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
                "`": r"\textasciigrave{}"}
# Integral glyphs without limits; \int read back alone is the glyph.
INTEGRALS = {"∫": "int", "∬": "iint", "∮": "oint"}

# Characters that are text even though they are not letters.
TEXT_SAFE = set("¡¿«»“”‘’…§©ª®º£¤¥¢€ƒ°")
# Operators and relations: they glue the words around them into one formula.
OPERATORS = set("=<>+−×÷±∓·≤≥≠≈≡≢≅∝→⇒⇔∈∉⊂⊆⊃⊇∪∩")
PUNCTUATION = set(".,;:!?")
VOWELS = set("aeiouy")
FUNCTION_NAMES = latex.FUNCTIONS | latex.LIMIT_FUNCTIONS | {"log"}

# Statistics glyphs that LaTeX accents restore (latex.py maps them back).
ACCENTED = {"xbar": r"\bar{x}", "ybar": r"\bar{y}", "xcirc": r"\hat{x}", "ycirc": r"\hat{y}",
            "pcirc": r"\hat{p}"}

# How the preamble draws palette symbols that have no Unicode character.
# Each is written \casio{name}; eact reads that back as the \name; symbol.
CASIO_LATEX = {
    "i": r"\mathrm{i}", "s10": r"\mathrm{E}", "sE": r"\mathrm{E}",
    "hookn": r"\mathrm{n}", "hookM": r"\mathrm{M}", "serifG": r"\mathrm{G}", "serifT": r"\mathrm{T}",
    "serifP": r"\mathrm{P}", "serifE": r"\mathrm{E}", "serifr": r"\mathrm{r}", "hyphen": "{-}",
    "supsquare": r"^{\square}", "supr": r"^{\mathrm{r}}", "supg": r"^{\mathrm{g}}",
    "seCorner": r"\lrcorner", "bolde": r"\mathbf{e}", "boldP": r"\mathbf{P}", "boldr": r"\mathbf{r}",
    "boldX": r"\mathbf{X}", "boldY": r"\mathbf{Y}", "negB": r"\boxed{\mathrm{B}}",
    "negR": r"\boxed{\mathrm{R}}", "negL": r"\boxed{\mathrm{L}}", "negEq": r"\boxed{=}",
    "negLe": r"\boxed{<}", "negGr": r"\boxed{>}", "negLE": r"\boxed{\le}", "negGE": r"\boxed{\ge}",
    "lgComma": ",", "supm1": "^{-1}", "subs0": "_{0}", "subs1": "_{1}", "subs2": "_{2}",
    "subm1": "_{-1}", "subsn": "_{n}", "supr3": "^{3}", "sslash": r"/\!/",
}

SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7",
                "⁸": "8", "⁹": "9", "⁺": "+", "⁻": "-"}

_CONTROL_WORD_END = re.compile(r"\\[A-Za-z]+$")


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class _Out:
    """Collects LaTeX pieces; keeps control words apart from following letters
    and stops two scripts of the same kind from touching (x^{a}{}^{b})."""

    def __init__(self):
        self.parts: list[str] = []
        self.last_script = None

    def put(self, s: str):
        if not s:
            return
        if self.parts and s[0].isalpha() and _CONTROL_WORD_END.search(self.parts[-1]):
            self.parts.append(" ")
        self.parts.append(s)
        self.last_script = None

    def script(self, kind: str, body: str):
        if not self.parts or self.last_script == kind or (kind == "^" and self.last_script == "'"):
            self.parts.append("{}")
        self.parts.append(f"{kind}{{{body}}}")
        self.last_script = kind

    def text(self) -> str:
        return "".join(self.parts)


class LatexWriter:
    def __init__(self, rep: Reporter | None = None, cmap=None):
        self.rep = rep or Reporter()
        self.cmap = cmap or _charmap.default()
        self.line = 0
        self.used: set[str] = set()       # eact macros the body uses
        self.casio_names: set[str] = set()
        self.cyrillic = False
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"
        self.sub = {self.cmap.subscript(c): c for c in letters if self.cmap.subscript(c)}
        self.sup = {self.cmap.encode_char(u): d for u, d in SUPERSCRIPTS.items() if self.cmap.encode_char(u)}

    # -- characters -------------------------------------------------------
    def uni(self, n: Char) -> str | None:
        sym = self.cmap.lookup(n.code)
        return sym.unicode[0] if sym and sym.unicode else None

    def palette_name(self, n: Char) -> str | None:
        sym = self.cmap.lookup(n.code)
        if sym and sym.eam.startswith("\\") and sym.eam.endswith(";"):
            return sym.eam[1:-1]
        return None

    def raw(self, n: Char) -> str:
        hexs = n.code.hex(" ").upper()
        self.used.add("raw")
        self.rep.add("W009", f"bytes {hexs} have no LaTeX form; written as \\raw{{{hexs}}}", self.line, 0,
                     "eact reads \\raw back exactly; LaTeX prints the bytes as a placeholder")
        return f"\\raw{{{hexs}}}"

    def kind(self, n: Node) -> str:
        """'op', 'math' or 'text' for one node (see the module docstring)."""
        if not isinstance(n, Char):
            return "math"
        u = self.uni(n)
        if u is None:
            return "text" if n.code == b" " else "math"
        if u in OPERATORS:
            return "op"
        if n.code in self.sub or n.code in self.sup:
            return "math"
        sym = self.cmap.lookup(n.code)
        if u.isascii() or u in TEXT_SAFE or sym.category in ("latin", "cyrillic"):
            return "text"
        if u in MATH_COMMANDS or sym.category in ("math", "greek", "subscript"):
            return "math"
        return "text"

    def is_letter(self, n: Node) -> bool:
        if not isinstance(n, Char):
            return False
        u = self.uni(n)
        sym = self.cmap.lookup(n.code)
        return bool(u and u.isalpha() and sym.category in ("ascii", "latin", "cyrillic"))

    # -- math mode --------------------------------------------------------
    def math(self, nodes: list[Node]) -> str:
        out = _Out()
        i = 0
        while i < len(nodes):
            i = self.math_node(nodes, i, out)
        return out.text()

    def math_node(self, nodes, i, out: _Out) -> int:
        n = nodes[i]
        nxt = nodes[i + 1] if i + 1 < len(nodes) else None
        if isinstance(n, Char):
            if n.code in self.sub:
                j = i
                while j < len(nodes) and isinstance(nodes[j], Char) and nodes[j].code in self.sub:
                    j += 1
                out.script("_", "".join(self.sub[c.code] for c in nodes[i:j]))
                return j
            if n.code in self.sup:
                j = i
                while j < len(nodes) and isinstance(nodes[j], Char) and nodes[j].code in self.sup:
                    j += 1
                digits = "".join(self.sup[c.code] for c in nodes[i:j])
                if digits.isdigit() and j < len(nodes) and isinstance(nodes[j], Sqrt):
                    out.put(f"\\sqrt[{digits}]{{{self.math(nodes[j].body)}}}")
                    return j + 1
                out.script("^", digits)
                return j
            if self.is_letter(n):
                return self.math_letters(nodes, i, out)
            u = self.uni(n)
            if n.code == b" ":
                out.put("\\ ")
            elif u is None:
                name = self.palette_name(n)
                if name in ACCENTED:
                    out.put(ACCENTED[name])
                elif name:
                    self.used.add("casio")
                    self.casio_names.add(name)
                    out.put(f"\\casio{{{name}}}")
                else:
                    out.put(self.raw(n))
            elif u in ("′", "″"):
                if out.last_script in ("^", "'"):
                    out.parts.append("{}")   # x^{2}' and '' + ' would merge
                out.put(MATH_ESCAPES[u])
                out.last_script = "'"
            elif u in INTEGRALS:
                # followed by a script, \int would take it as its limits
                scripted = isinstance(nxt, Pow) or (isinstance(nxt, Char) and nxt.code in self.sub)
                out.put(("{\\%s}" if scripted else "\\%s") % INTEGRALS[u])
            elif u in MATH_ESCAPES:
                out.put(MATH_ESCAPES[u])
            elif u in MATH_COMMANDS:
                out.put("\\" + MATH_COMMANDS[u])
            elif u.isascii():
                out.put(u)
            else:
                j = i
                while j < len(nodes) and isinstance(nodes[j], Char) and self.uni(nodes[j]) \
                        and not self.uni(nodes[j]).isascii() and self.uni(nodes[j]) not in MATH_COMMANDS \
                        and self.uni(nodes[j]) not in MATH_ESCAPES and nodes[j].code not in self.sub \
                        and nodes[j].code not in self.sup:
                    j += 1
                out.put("\\text{" + self.text_chars(nodes[i:j]) + "}")
                return j
            return i + 1
        if isinstance(n, Frac):
            out.put(f"\\frac{{{self.math(n.num)}}}{{{self.math(n.den)}}}")
        elif isinstance(n, Sqrt):
            out.put(f"\\sqrt{{{self.math(n.body)}}}")
        elif isinstance(n, Pow):
            out.script("^", self.math(n.exp))
        elif isinstance(n, Abs):
            body = self.math(n.body)
            if any(isinstance(c, Abs) for c in n.body):
                out.put(f"\\left|{body}\\right|")
            else:
                out.put(f"|{body}|")
        elif isinstance(n, Sum):
            expr = self.math(n.expr)
            if not n.expr or self.has_stop(n.expr):
                expr = "{" + expr + "}"
            s = f"\\sum_{{{self.math(n.var)}={self.math(n.start)}}}^{{{self.math(n.end)}}} {expr}"
            # The summand runs to the next operator; anything else after the
            # Σ would be read into it, so close the Σ with a group.
            if nxt is not None and not self.is_stop(nxt):
                s = "{" + s + "}"
            out.put(s)
        elif isinstance(n, Integral):
            body = self.math(n.body)
            if self.has_relation(n.body) or self.has_differential(n.body):
                body = "{" + body + "}"
            out.put(f"\\int_{{{self.math(n.lower)}}}^{{{self.math(n.upper)}}} {body}\\,dx")
            if nxt is not None and self.is_letter(nxt):
                out.parts.append(" ")
        elif isinstance(n, Log):
            arg = self.math(n.arg)
            opens = sum(1 for c in n.arg if isinstance(c, Char) and c.code == b"(")
            closes = sum(1 for c in n.arg if isinstance(c, Char) and c.code == b")")
            out.put(f"\\log_{{{self.math(n.base)}}}" + (f"({arg})" if opens == closes else f"{{{arg}}}"))
        elif isinstance(n, Diff):
            self.used.add("diff")
            out.put(f"\\diff{'2' if n.order == 2 else ''}{{{self.math(n.body)}}}{{{self.math(n.at)}}}")
        elif isinstance(n, Matrix):
            rows = " \\\\ ".join(" & ".join(self.math(c) for c in row) for row in n.rows)
            out.put(f"\\begin{{bmatrix}} {rows} \\end{{bmatrix}}")
        else:
            raise TypeError(n)
        return i + 1

    def math_letters(self, nodes, i, out: _Out) -> int:
        """A run of letters: a function name, a variable or a word."""
        j = i
        while j < len(nodes) and self.is_letter(nodes[j]):
            j += 1
        run = "".join(self.uni(c) for c in nodes[i:j])
        prev_letter = i > 0 and self.is_letter(nodes[i - 1])
        if not prev_letter and run in FUNCTION_NAMES:
            out.put("\\" + run)
            return j
        if not prev_letter and run.isascii():
            # "sinx" -> \sin x
            head = next((f for f in sorted(FUNCTION_NAMES, key=len, reverse=True)
                         if run.startswith(f) and len(run) - len(f) == 1), None)
            if head:
                out.put("\\" + head)
                out.put(run[len(head):])
                return j
        if not run.isascii() or len(run) >= 3:
            out.put("\\text{" + self.text_chars(nodes[i:j]) + "}")
        else:
            out.put(run)
        return j

    def is_stop(self, n: Node) -> bool:
        """Does this node end a Σ summand when latex.py reads it back?"""
        if not isinstance(n, Char):
            return False
        u = self.uni(n)
        return u is not None and (u in "+−-=<>,;&" or u in OPERATORS or u in "…")

    def has_stop(self, nodes) -> bool:
        depth = 0
        for n in nodes:
            if isinstance(n, Char) and n.code in (b"(", b"["):
                depth += 1
            elif isinstance(n, Char) and n.code in (b")", b"]"):
                depth = max(0, depth - 1)
            elif depth == 0 and self.is_stop(n):
                return True
        return False

    def has_relation(self, nodes) -> bool:
        return any(isinstance(n, Char) and self.uni(n) in OPERATORS - set("+−·×÷±∓") for n in nodes)

    def has_differential(self, nodes) -> bool:
        """A top-level 'd' + letter would be taken for the integral's dx."""
        for a, b in zip(nodes, nodes[1:]):
            if isinstance(a, Char) and a.code == b"d" and self.is_letter(b):
                return True
        return False

    # -- text mode --------------------------------------------------------
    def text_chars(self, nodes: list[Node]) -> str:
        """Characters that are known to be text (no structures)."""
        out = []
        prev = ""
        for n in nodes:
            u = self.uni(n)
            if u is None:
                out.append(self.raw(n))
                prev = ""
                continue
            if u in TEXT_ESCAPES:
                out.append(TEXT_ESCAPES[u])
            elif (u, prev) in (("-", "-"), ("'", "'")):
                out.append("{}" + u)   # stop -- and '' turning into dashes/quotes
            else:
                out.append(u)
            if self.cmap.lookup(n.code).category == "cyrillic":
                self.cyrillic = True
            prev = u
        return "".join(out)

    def chunks(self, nodes) -> list[list[Node]]:
        """Split a line at spaces (runs of spaces count once)."""
        out, cur = [], []
        for n in nodes:
            if isinstance(n, Char) and n.code == b" ":
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(n)
        if cur:
            out.append(cur)
        return out

    def is_word(self, chunk) -> bool:
        """Text with two letters in a row: a real word, never pulled into a formula."""
        letters = 0
        for n in chunk:
            if self.kind(n) != "text":
                return False
            letters = letters + 1 if self.is_letter(n) else 0
            if letters >= 2:
                return True
        return False

    def is_function(self, chunk) -> bool:
        return all(self.is_letter(n) for n in chunk) and \
            "".join(self.uni(n) for n in chunk) in FUNCTION_NAMES

    def is_call(self, chunk) -> bool:
        """'sin(x)': a function name directly followed by '('."""
        k = 0
        while k < len(chunk) and self.is_letter(chunk[k]):
            k += 1
        return 0 < k < len(chunk) and isinstance(chunk[k], Char) and chunk[k].code == b"(" and \
            "".join(self.uni(n) for n in chunk[:k]) in FUNCTION_NAMES

    def core(self, c) -> tuple[int, int]:
        """Bounds of a word without its outer punctuation and unbalanced parentheses."""
        a, b = 0, len(c)

        def ch(k):
            return c[k].code if isinstance(c[k], Char) else None
        while b - a > 1:
            depth = _balance(c[a:b])
            if ch(b - 1) is not None and self.uni(c[b - 1]) in PUNCTUATION:
                b -= 1
            elif ch(b - 1) == b")" and depth < 0:
                b -= 1
            elif ch(a) == b"(" and depth > 0:
                a += 1
            elif ch(a) is not None and self.uni(c[a]) in ("¿", "¡"):
                a += 1
            else:
                break
        return a, b

    def inline(self, nodes: list[Node], display_ok: bool = False) -> str:
        """One line of mixed text and math."""
        chunks = self.chunks(nodes)
        if not chunks:
            return ""
        bounds = [self.core(c) for c in chunks]
        math = []
        for c, (a, b) in zip(chunks, bounds):
            core = c[a:b]
            single = len(core) == 1 and self.is_letter(core[0]) and self.uni(core[0]).isascii() \
                and self.uni(core[0]).islower() and self.uni(core[0]) not in VOWELS
            math.append(any(self.kind(n) != "text" for n in c) or single or self.is_call(core))

        def op_at(k):   # an operator touches the space between chunk k and k+1
            return self.kind(chunks[k][-1]) == "op" or self.kind(chunks[k + 1][0]) == "op"

        changed = True
        while changed:
            changed = False
            for k in range(len(chunks) - 1):
                if op_at(k):
                    for x, y in ((k, k + 1), (k + 1, k)):
                        if math[x] and not math[y] and not self.is_word(chunks[y]):
                            math[y] = changed = True
        for k in range(len(chunks) - 1):
            if not math[k] and self.is_function(chunks[k]) and math[k + 1]:
                math[k] = True

        # segments: [kind, payload, space_before]; a math payload is a list of
        # chunks that are written as one formula, separated by spaces.
        segs: list[list] = []
        for k, c in enumerate(chunks):
            if not math[k]:
                segs.append(["text", c, k > 0])
                continue
            a, b = bounds[k]
            head, core, tail = c[:a], c[a:b], c[b:]
            if head:
                segs.append(["text", head, k > 0])
            prev = segs[-1] if segs else None
            if (prev is not None and prev[0] == "math" and not head
                    and (op_at(k - 1) or self.is_function(prev[1][-1]))):
                prev[1].append(core)
            else:
                segs.append(["math", [core], k > 0 and not head])
            if tail:
                segs.append(["text", tail, False])

        if display_ok and len(segs) == 1 and segs[0][0] == "math":
            return "\\[ " + " ".join(self.math(c) for c in segs[0][1]) + " \\]"
        text = ""
        for kind, payload, space in segs:
            piece = ("$" + " ".join(self.math(c) for c in payload) + "$") if kind == "math" \
                else self.text_chars(payload)
            text += (" " if space else "") + piece
        return text

    # -- document ---------------------------------------------------------
    HEADING_RE = re.compile(r"^(==?)([^=].*?)\1$")
    ITEM_RE = re.compile(r"^(- |(\d+)\) )")

    def plain(self, line: TextLine) -> str | None:
        """The line as a plain string, or None if it holds structures/specials."""
        out = []
        for n in line.nodes:
            u = self.uni(n) if isinstance(n, Char) else None
            if u is None:
                return None
            out.append(u)
        return "".join(out)

    def heading(self, line: TextLine):
        """'==Title==' -> ('section', nodes), '=Title=' -> ('subsection', nodes)."""
        s = self.plain(line)
        m = self.HEADING_RE.match(s) if s else None
        if not m:
            return None
        k = len(m.group(1))
        inner = line.nodes[k:len(line.nodes) - k]
        if self.uni(inner[0]) == " " or self.uni(inner[-1]) == " ":
            return None
        return ("section" if k == 2 else "subsection"), inner

    def item(self, line: TextLine):
        """('itemize', None, rest) / ('enumerate', n, rest) for list-shaped lines."""
        prefix = []
        for n in line.nodes[:6]:
            u = self.uni(n) if isinstance(n, Char) else None
            if u is None:
                break
            prefix.append(u)
        m = self.ITEM_RE.match("".join(prefix))
        if not m or len(line.nodes) == len(m.group(1)):
            return None
        rest = line.nodes[len(m.group(1)):]
        if m.group(2):
            return "enumerate", int(m.group(2)), rest
        return "itemize", None, rest

    def lines(self, lines: list[TextLine], indent: str = "") -> list[str]:
        """Paragraphs for a sequence of text lines (the body or a note)."""
        out: list[str] = []
        k = 0
        pending_blank = False
        while k < len(lines):
            ln = lines[k]
            self.line = ln.src_line or self.line
            if not ln.nodes:
                pending_blank = bool(out)
                k += 1
                continue
            h = self.heading(ln)
            if h:
                # latex.py puts an empty line before every section that is not first.
                out.append(f"\\{h[0]}{{{self.inline(h[1])}}}")
                pending_blank = False
                k += 1
                continue
            if pending_blank:
                out.append("\\medskip")
                pending_blank = False
            it = self.item(ln)
            if it:
                env, items = it[0], []
                while k < len(lines):
                    nxt = self.item(lines[k]) if lines[k].nodes else None
                    if not nxt or nxt[0] != env or (env == "enumerate" and nxt[1] != len(items) + 1):
                        break
                    items.append(nxt[2])
                    k += 1
                if env == "enumerate" and items == []:
                    out.append(self.inline(ln.nodes, display_ok=True))
                    k += 1
                    continue
                body = []
                for rest in items:
                    text = self.inline(rest)
                    body.append(f"  \\item {'{}' if text.startswith('[') else ''}{text}")
                out.append(f"\\begin{{{env}}}\n" + "\n".join(body) + f"\n\\end{{{env}}}")
                continue
            out.append(self.inline(ln.nodes, display_ok=True))
            k += 1
        return out

    def body(self, doc: Doc) -> str:
        parts: list[str] = []
        run: list[TextLine] = []

        def flush():
            parts.extend(self.lines(run))
            run.clear()
        for k, b in enumerate(doc.blocks):
            if isinstance(b, Note):
                # An empty line just before a note is kept as \medskip by lines().
                flush()
                self.line = b.src_line or self.line
                title = self.inline(b.title)
                self.used.add("note")
                inner = "\n\n".join("  " + p.replace("\n", "\n  ") for p in self.lines(b.lines))
                parts.append(f"\\note{{{title}}}{{\n{inner}\n}}" if inner else f"\\note{{{title}}}{{}}")
            else:
                if not run:
                    self.line = k + 1
                run.append(b)
        flush()
        return "\n\n".join(parts)

    def preamble(self, doc: Doc, source: str = "") -> str:
        out = [f"% Converted from {source or 'an eActivity'} by eact {__version__} (eact dump --as latex).",
               "% `eact build` turns this file back into the same eActivity; see docs/LATEX_OUTPUT.md.",
               "\\documentclass{article}",
               "\\usepackage{iftex}",
               "\\ifPDFTeX",
               "  \\usepackage[utf8]{inputenc}",
               "  \\usepackage[" + ("T2A," if self.cyrillic else "") + "T1]{fontenc}",
               "\\else",
               "  \\usepackage{fontspec}",
               "\\fi",
               "\\usepackage{amsmath,amssymb}",
               "\\setlength{\\parindent}{0pt}",
               "\\setlength{\\parskip}{0.6ex}"]
        if self.used:
            out.append("% eact extensions, defined so that the file also compiles with LaTeX:")
        if "note" in self.used:
            out.append("\\providecommand{\\note}[2]{\\par\\smallskip\\noindent\\fbox{\\begin{minipage}"
                       "{\\dimexpr\\linewidth-2\\fboxsep-2\\fboxrule}\\textbf{#1}\\par\\smallskip #2"
                       "\\end{minipage}}\\par\\smallskip}")
        if "diff" in self.used or "casio" in self.used:
            out.append("\\makeatletter")
        if "diff" in self.used:
            out += ["\\providecommand{\\diff}{\\@ifnextchar2{\\eact@diffii}{\\eact@diffi}}",
                    "\\def\\eact@diffi#1#2{\\left.\\frac{d}{dx}\\left(#1\\right)\\right|_{x=#2}}",
                    "\\def\\eact@diffii2#1#2{\\left.\\frac{d^{2}}{dx^{2}}\\left(#1\\right)\\right|_{x=#2}}"]
        if "casio" in self.used:
            out.append("\\providecommand{\\casio}[1]{\\ifcsname eact@casio@#1\\endcsname"
                       "\\csname eact@casio@#1\\endcsname\\else\\mbox{\\texttt{#1}}\\fi}")
            for name in sorted(self.casio_names):
                if name in CASIO_LATEX:
                    out.append(f"\\@namedef{{eact@casio@{name}}}{{\\ensuremath{{{CASIO_LATEX[name]}}}}}")
        if "diff" in self.used or "casio" in self.used:
            out.append("\\makeatother")
        if "raw" in self.used:
            out.append("\\providecommand{\\raw}[1]{\\mbox{\\texttt{[#1]}}}")
        out.append(f"\\title{{{doc.title}}}")
        return "\n".join(out)

    def document(self, doc: Doc, standalone: bool = True, source: str = "") -> str:
        body = self.body(doc)
        if not standalone:
            return body + "\n"
        return (self.preamble(doc, source) + "\n\\begin{document}\n\n" + body
                + "\n\n\\end{document}\n")


def _balance(nodes) -> int:
    return sum(1 for n in nodes if isinstance(n, Char) and n.code == b"(") - \
        sum(1 for n in nodes if isinstance(n, Char) and n.code == b")")


def write(doc: Doc, rep: Reporter | None = None, standalone: bool = True, source: str = "") -> str:
    """LaTeX for a document.  Diagnostics (W009) go to ``rep``."""
    return LatexWriter(rep).document(doc, standalone, source)
