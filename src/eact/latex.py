"""LaTeX subset -> IR.

A small hand-written parser for the LaTeX people actually write in exercise
sheets and class notes, mapped onto what an fx-9750GIII eActivity can show.
The full list of supported commands is in docs/LATEX_SUBSET.md; the guiding
rules are:

* Text becomes text lines.  A paragraph (or ``\\\\``) becomes one calculator
  line; the calculator wraps long lines itself.
* ``$…$``/``\\(…\\)`` math is inline; ``\\[…\\]``, ``$$…$$`` and display
  environments become their own lines, one per ``\\\\`` row.
* Constructs with a native CASIO template (fractions, roots, powers, Σ with
  limits, definite ∫, log with base, |x|, matrices) use that template.
* Everything else is approximated *with a warning*, or rejected *with an
  error*.  Nothing is dropped silently.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

from . import charmap as _charmap
from .diagnostics import Reporter
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Node, Note, Pow, Sqrt, Sum, TextLine

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "θ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "omicron": "ο", "pi": "π", "varpi": "π",
    "rho": "ρ", "varrho": "ρ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

# Math symbols with a direct CASIO glyph.
SYMBOLS = {
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "approx": "≈",
    "equiv": "≡", "cong": "≅", "simeq": "≅", "sim": "~", "propto": "∝", "doteq": "≒",
    "infty": "∞", "pm": "±", "mp": "∓", "times": "×", "div": "÷", "cdot": "·", "cdotp": "·",
    "ast": "*", "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←", "uparrow": "↑",
    "downarrow": "↓", "Rightarrow": "⇒", "implies": "⇒", "Leftrightarrow": "⇔", "iff": "⇔",
    "nearrow": "↗", "searrow": "↘", "nwarrow": "↖", "swarrow": "↙",
    "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "subseteq": "⊆", "supset": "⊃",
    "supseteq": "⊇", "nsubseteq": "⊈", "nsupseteq": "⊉", "cup": "∪", "cap": "∩",
    "emptyset": "∅", "varnothing": "∅", "exists": "∃", "forall": "∀", "neg": "¬", "lnot": "¬",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨", "oplus": "⊕", "ominus": "⊖",
    "otimes": "⊗", "oslash": "⊘", "perp": "⊥", "parallel": "∥", "nparallel": "∦",
    "nabla": "∇", "partial": "∂", "angle": "∠", "measuredangle": "∡", "therefore": "∴",
    "because": "∵", "ldots": "…", "dots": "…", "cdots": "…", "dotsc": "…", "dotsb": "…",
    "prime": "′", "degree": "°", "mid": "|", "vert": "|", "colon": ":", "backslash": "\\",
    "lbrace": "{", "rbrace": "}", "bullet": "●", "square": "□", "blacksquare": "■",
    "Box": "□", "diamond": "◇", "lozenge": "◇", "S": "§", "copyright": "©", "pounds": "£",
    "euro": "€", "yen": "¥", "cent": "¢", "imath": "i", "jmath": "j",
    "%": "%", "$": "$", "#": "#", "&": "&", "_": "_", "{": "{", "}": "}", "|": "∥",
}

# Symbols without a glyph: (replacement, explanation) -> warning W001.
LOOKALIKES = {
    "Leftarrow": "←", "impliedby": "←", "leftrightarrow": "⇔", "longrightarrow": "→",
    "Longrightarrow": "⇒", "longleftarrow": "←", "mapsto": "→", "langle": "<", "rangle": ">",
    "lfloor": "[", "rfloor": "]", "lceil": "[", "rceil": "]", "vdots": "…", "ddots": "…",
    "circ": "○", "ell": "l", "Re": "R", "Im": "I", "triangle": "▲", "star": "*", "setminus": "\\",
    "ll": "<<", "gg": ">>", "leqslant": "≤", "geqslant": "≥", "lesssim": "≤", "gtrsim": "≥",
    "subsetneq": "⊂", "supsetneq": "⊃", "nexists": "¬∃", "top": "T", "bot": "⊥",
    "hbar": "h", "aleph": "N", "wp": "P", "dagger": "+", "checkmark": "√",
}

# Operator names written as plain text (like EactMaker does for sin(x)).
FUNCTIONS = {
    "sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh",
    "tanh", "coth", "ln", "lg", "exp", "det", "gcd", "deg", "dim", "ker", "arg", "hom", "Pr",
}
LIMIT_FUNCTIONS = {"lim", "max", "min", "sup", "inf", "liminf", "limsup", "argmax", "argmin"}

SPACES = {",", ":", ";", " ", "quad", "qquad", "enspace", "thinspace", "medspace", "thickspace"}
IGNORED_MATH = {"displaystyle", "textstyle", "scriptstyle", "limits", "nolimits", "nonumber",
                "notag", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl",
                "biggr", "Biggl", "Biggr", "!", "middle", "allowbreak", "mathstrut", "strut"}
TEXT_FONT = {"text", "textrm", "textnormal", "mbox", "hbox", "textup", "textmd"}
MATH_FONT = {"mathrm", "mathit", "mathbf", "mathsf", "mathtt", "mathcal", "mathbb", "mathfrak",
             "boldsymbol", "bm", "mathscr", "operatorname"}
STYLED_TEXT = {"textbf", "textit", "emph", "underline", "texttt", "textsf", "textsc", "textsl",
               "uline"}
ACCENT_DROPPED = {"vec", "dot", "ddot", "tilde", "widetilde", "check", "breve", "acute", "grave",
                  "mathring", "overrightarrow", "overleftarrow", "underline", "underbrace",
                  "overbrace", "boxed", "cancel"}

TEXT_ACCENTS = {"'": "́", "`": "̀", "^": "̂", '"': "̈", "~": "̃",
                "=": "̄", ".": "̇", "u": "̆", "v": "̌", "H": "̋",
                "c": "̧", "k": "̨", "r": "̊"}
TEXT_SYMBOLS = {
    "%": "%", "&": "&", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}", "textbackslash": "\\",
    "ldots": "…", "dots": "…", "textellipsis": "…", "S": "§", "copyright": "©", "pounds": "£",
    "euro": "€", "textdegree": "°", "degree": "°", "textquestiondown": "¿", "textexclamdown": "¡",
    "ss": "ß", "o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "l": "ł",
    "L": "Ł", "aa": "å", "AA": "Å", "i": "i", "j": "j", "textasciitilde": "~",
    "textasciicircum": "^", "textbar": "|", "textless": "<", "textgreater": ">",
    "LaTeX": "LaTeX", "TeX": "TeX", "textendash": "-", "textemdash": "-", "textbullet": "●",
    "guillemotleft": "«", "guillemotright": "»", "textquotedblleft": "“", "textquotedblright": "”",
}
TEXT_IGNORED = {"noindent", "indent", "centering", "raggedright", "raggedleft", "maketitle_",
                "newpage", "clearpage", "pagebreak", "linebreak", "nolinebreak", "small", "large",
                "Large", "LARGE", "huge", "Huge", "tiny", "scriptsize", "footnotesize",
                "normalsize", "bfseries", "itshape", "rmfamily", "sffamily", "ttfamily",
                "normalfont", "tableofcontents", "hfill", "vfill", "null", "selectfont",
                "protect", "relax", "par_", "displaystyle", "hline", "toprule", "midrule",
                "bottomrule", "phantom_", "frenchspacing", "sloppy", "-", "/", "@"}
# commands whose {} argument(s) are skipped
TEXT_SKIP_ARGS = {"label": 1, "vspace": 1, "hspace": 1, "setlength": 2, "addtolength": 2,
                  "setcounter": 2, "pagestyle": 1, "thispagestyle": 1, "usepackage": 1,
                  "documentclass": 1, "author": 1, "date": 1, "cline": 1, "phantom": 1,
                  "hphantom": 1, "vphantom": 1,
                  "geometry": 1, "bibliographystyle": 1, "bibliography": 1, "input": 1,
                  "include": 1, "includegraphics": 1, "caption": 1, "color": 1}
VSPACE = {"medskip", "bigskip", "smallskip", "vspace", "vfill"}

SECTIONS = {"section": ("==", "=="), "subsection": ("=", "="), "subsubsection": ("", ":"),
            "paragraph": ("", ":"), "subparagraph": ("", ":"), "chapter": ("==", "==")}

LIST_ENVS = {"itemize", "enumerate", "description"}
DISPLAY_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline",
                "multline*", "eqnarray", "eqnarray*", "displaymath", "math", "flalign",
                "flalign*", "alignat", "alignat*"}
TRANSPARENT_ENVS = {"document", "center", "flushleft", "flushright", "quote", "quotation", "verse",
                    "minipage", "small", "footnotesize", "large", "multicols", "enumerate*",
                    "itemize*", "spacing", "singlespace", "onehalfspace", "doublespace"}
DROPPED_ENVS = {"figure", "figure*", "tikzpicture", "picture", "comment", "thebibliography",
                "table*", "wrapfigure"}
MATRIX_ENVS = {"matrix": None, "pmatrix": None, "bmatrix": None, "Bmatrix": None,
               "vmatrix": "vmatrix", "Vmatrix": "vmatrix", "smallmatrix": None, "array": None,
               "cases": "cases", "dcases": "cases", "rcases": "cases"}
INNER_ALIGN_ENVS = {"aligned", "gathered", "split", "alignedat"}
# Stop characters / commands that end a term (the summand of Σ, body of ∫).
RELATIONS = {"le", "leq", "ge", "geq", "ne", "neq", "approx", "equiv", "to", "rightarrow",
             "Rightarrow", "implies", "iff", "Leftrightarrow", "in", "notin", "subset", "subseteq",
             "cong", "sim", "simeq", "propto", "quad", "qquad", "pm", "mp", "cdots", "ldots",
             "text", "\\"}

SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass
class Tok:
    kind: str   # 'cmd', 'char', 'space', 'nl', 'par'
    val: str
    pos: int


def tokenize(s: str) -> list[Tok]:
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == "%":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "\\":
            if i + 1 < n and s[i + 1].isascii() and s[i + 1].isalpha():
                j = i + 1
                while j < n and s[j].isascii() and s[j].isalpha():
                    j += 1
                toks.append(Tok("cmd", s[i + 1:j], i))
                while j < n and s[j] in " \t":
                    j += 1
                i = j
            elif i + 1 < n:
                toks.append(Tok("cmd", s[i + 1], i))
                i += 2
            else:
                toks.append(Tok("char", "\\", i))
                i += 1
            continue
        if c in " \t\n":
            j, newlines = i, 0
            while j < n and s[j] in " \t\n":
                newlines += s[j] == "\n"
                j += 1
            toks.append(Tok("par" if newlines >= 2 else "nl" if newlines else "space", " ", i))
            i = j
            continue
        toks.append(Tok("char", c, i))
        i += 1
    return toks


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class LatexParser:
    def __init__(self, src: str, rep: Reporter, cmap=None):
        self.src = src.replace("\r\n", "\n").replace("\r", "\n")
        self.rep = rep
        self.cmap = cmap or _charmap.default()
        self.toks = tokenize(self.src)
        self.i = 0
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", self.src)]
        self.blocks: list = []
        self.cur: list[Node] = []
        self.cur_line = 0
        self.lists: list[list] = []      # stack of [env, counter]
        self.title: str | None = None
        self.full_title: str | None = None
        self._warned: set = set()
        self.in_note = False

    # -- positions & diagnostics ------------------------------------------
    def lc(self, pos: int):
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, pos - self.line_starts[lo] + 1

    def diag(self, code, msg, pos, hint="", once_key=None):
        if once_key is not None:
            if once_key in self._warned:
                return
            self._warned.add(once_key)
        line, col = self.lc(pos)
        self.rep.add(code, msg, line, col, hint)

    def pos_of(self, k):
        return self.toks[k].pos if k < len(self.toks) else len(self.src)

    # -- token helpers ----------------------------------------------------
    def tok(self, k=None):
        k = self.i if k is None else k
        return self.toks[k] if k < len(self.toks) else None

    def is_char(self, k, ch):
        t = self.tok(k)
        return t is not None and t.kind == "char" and t.val == ch

    def is_cmd(self, k, name):
        t = self.tok(k)
        return t is not None and t.kind == "cmd" and t.val == name

    def skip_ws(self, end, newlines=True):
        kinds = ("space", "nl") if newlines else ("space",)
        while self.i < end and self.toks[self.i].kind in kinds:
            self.i += 1

    def match_brace(self, k, end, open_="{", close="}"):
        """Index of the token closing the group opened at k, or None."""
        depth = 0
        for j in range(k, end):
            t = self.toks[j]
            if t.kind == "char" and t.val == open_:
                depth += 1
            elif t.kind == "char" and t.val == close:
                depth -= 1
                if depth == 0:
                    return j
        return None

    def read_group(self, end, what="argument"):
        """Read '{…}'.  Returns (start, stop) of the inner tokens, or None."""
        self.skip_ws(end)
        if not self.is_char(self.i, "{"):
            return None
        j = self.match_brace(self.i, end)
        if j is None:
            self.diag("E004", f"unclosed '{{' in {what}", self.pos_of(self.i), "add the missing '}'")
            s = self.i + 1
            self.i = end
            return s, end
        s = self.i + 1
        self.i = j + 1
        return s, j

    def read_arg(self, end, what="argument"):
        """A {group} or a single token (TeX's undelimited argument)."""
        self.skip_ws(end)
        if self.i >= end:
            return None
        if self.is_char(self.i, "{"):
            return self.read_group(end, what)
        s = self.i
        self.i += 1
        return s, s + 1

    def read_optional(self, end):
        self.skip_ws(end, newlines=False)
        if not self.is_char(self.i, "["):
            return None
        j = self.match_brace(self.i, end, "[", "]")
        if j is None:
            return None
        s = self.i + 1
        self.i = j + 1
        return s, j

    def raw_text(self, s, e) -> str:
        if s >= e:
            return ""
        return self.src[self.toks[s].pos:self.pos_of(e)]

    def find_end(self, env, start, end):
        """Index of the \\end{env} token matching an already-consumed \\begin{env}."""
        depth = 1
        k = start
        while k < end:
            t = self.toks[k]
            if t.kind == "cmd" and t.val in ("begin", "end"):
                if self.env_name_at(k, end) == env:
                    depth += 1 if t.val == "begin" else -1
                    if depth == 0:
                        return k
            k += 1
        return None

    def env_body(self, env, end, begin_pos):
        """After '\\begin{env}' has been read: return (s, e) and move past \\end{env}."""
        e = self.find_end(env, self.i, end)
        if e is None:
            self.diag("E004", f"\\begin{{{env}}} has no matching \\end{{{env}}}", begin_pos)
            s = self.i
            self.i = end
            return s, end
        s = self.i
        self.i = e + 1
        self.read_group(end)  # {env}
        return s, e

    def env_name_at(self, k, end=None):
        """Name in the {…} group right after token k (for \\begin / \\end)."""
        save = self.i
        self.i = k + 1
        g = self.read_group(end or len(self.toks))
        self.i = save
        return self.raw_text(*g).strip() if g else ""

    def find_env_cmd(self, cmd, env, start):
        for k in range(start, len(self.toks)):
            if self.is_cmd(k, cmd) and self.env_name_at(k) == env:
                return k
        return None

    # -- characters -------------------------------------------------------
    def chars(self, text: str, pos: int, math=False) -> list[Node]:
        out = []
        for ch in text:
            out.extend(self.char(ch, pos, math))
        return out

    def char(self, ch: str, pos: int, math=False) -> list[Node]:
        if math:
            ch = {"-": "−", "'": "′"}.get(ch, ch)
        code = self.cmap.encode_char(ch)
        if code is not None:
            return [Char(code, ch)]
        fb = self.cmap.fallback(ch)
        if fb:
            self.diag("W001", f"'{ch}' (U+{ord(ch):04X}) has no CASIO glyph; written as '{fb[1]}'", pos)
            return [Char(fb[0], fb[1])]
        self.diag("E002", f"'{ch}' (U+{ord(ch):04X}) has no CASIO glyph", pos,
                  "remove it or use a supported symbol (see `eact symbols`)")
        return []

    def space(self) -> Char:
        return Char(b" ", " ")

    # -- output lines -----------------------------------------------------
    def add(self, nodes: list[Node], pos: int):
        if not nodes:
            return
        if not self.cur:
            self.cur_line = self.lc(pos)[0]
            if all(isinstance(n, Char) and n.src == " " for n in nodes):
                return
        self.cur.extend(nodes)

    def add_space(self, pos):
        if self.cur and not (isinstance(self.cur[-1], Char) and self.cur[-1].src == " "):
            self.cur.append(self.space())

    def flush(self, keep_empty=False):
        while self.cur and isinstance(self.cur[-1], Char) and self.cur[-1].src == " ":
            self.cur.pop()
        if self.cur or keep_empty:
            self.blocks.append(TextLine(self.cur, self.cur_line))
        self.cur = []

    def blank_line(self):
        self.flush()
        self.blocks.append(TextLine([], 0))

    # -- text mode --------------------------------------------------------
    def text_range(self, s, e):
        save = self.i
        self.i = s
        self.text_seq(e)
        self.i = save

    def text_inline(self, s, e) -> list[Node]:
        """Parse a text range into nodes without touching the current line."""
        saved = self.cur, self.cur_line, self.blocks
        self.cur, self.blocks = [], []
        self.text_range(s, e)
        nodes = [n for b in self.blocks for n in (b.nodes if isinstance(b, TextLine) else [])] + self.cur
        self.cur, self.cur_line, self.blocks = saved
        while nodes and isinstance(nodes[-1], Char) and nodes[-1].src == " ":
            nodes.pop()
        while nodes and isinstance(nodes[0], Char) and nodes[0].src == " ":
            nodes.pop(0)
        return nodes

    def text_seq(self, end):
        while self.i < end:
            t = self.toks[self.i]
            if t.kind in ("space", "nl"):
                self.i += 1
                self.add_space(t.pos)
            elif t.kind == "par":
                self.i += 1
                self.flush()
            elif t.kind == "char":
                self.text_char(t, end)
            else:
                self.i += 1
                self.text_command(t, end)

    def text_char(self, t: Tok, end):
        c = t.val
        self.i += 1
        if c in "{}":
            return
        if c == "$":
            if self.is_char(self.i, "$"):
                self.i += 1
                close = self.find_dollar(end, double=True)
                self.display_math(self.i, close, t.pos)
                self.i = min(close + 2, end)
            else:
                close = self.find_dollar(end, double=False)
                self.add(self.math_range(self.i, close), t.pos)
                self.i = min(close + 1, end)
            return
        if c == "~":
            self.add_space(t.pos)
            return
        if c == "-" and self.is_char(self.i, "-"):
            self.i += 1
            if self.is_char(self.i, "-"):
                self.i += 1
            self.add(self.chars("-", t.pos), t.pos)
            return
        if c == "`":
            if self.is_char(self.i, "`"):
                self.i += 1
                self.add(self.chars("“", t.pos), t.pos)
            else:
                self.add(self.chars("‘", t.pos), t.pos)
            return
        if c == "'" and self.is_char(self.i, "'"):
            self.i += 1
            self.add(self.chars("”", t.pos), t.pos)
            return
        if c == "&":
            return  # alignment outside a table: ignore
        self.add(self.char(c, t.pos), t.pos)

    def find_dollar(self, end, double):
        k = self.i
        while k < end:
            if self.is_char(k, "$") and (not double or self.is_char(k + 1, "$")):
                return k
            k += 1
        self.diag("E004", "unclosed $ math", self.pos_of(self.i - 1), "add the closing $")
        return end

    def find_cmd(self, name, end):
        k = self.i
        while k < end:
            if self.is_cmd(k, name):
                return k
            k += 1
        return None

    def text_command(self, t: Tok, end):
        name = t.val
        if name in ("(", "["):
            close = self.find_cmd(")" if name == "(" else "]", end)
            if close is None:
                self.diag("E004", f"\\{name} without matching \\{')' if name == '(' else ']'}", t.pos)
                close = end
            if name == "(":
                self.add(self.math_range(self.i, close), t.pos)
            else:
                self.display_math(self.i, close, t.pos)
            self.i = min(close + 1, end)
            return
        if name in ("\\", "newline", "par", "linebreak"):
            if name == "\\":
                self.read_optional(end)
                if self.is_char(self.i, "*"):
                    self.i += 1
            self.flush()
            return
        if name in SECTIONS:
            if self.is_char(self.i, "*"):
                self.i += 1
            self.read_optional(end)
            g = self.read_group(end, f"\\{name}")
            if g is None:
                self.diag("E003", f"\\{name} needs a {{title}}", t.pos)
                return
            pre, post = SECTIONS[name]
            self.flush()
            if self.blocks:
                self.blocks.append(TextLine([], 0))
            self.cur_line = self.lc(t.pos)[0]
            self.cur = self.chars(pre, t.pos) + self.text_inline(*g) + self.chars(post, t.pos)
            self.flush()
            return
        if name == "title":
            self.read_optional(end)
            g = self.read_group(end, "\\title")
            if g:
                nodes = self.text_inline(*g)
                self.full_title = "".join(n.src for n in nodes if isinstance(n, Char))
                self._title_nodes = nodes
            return
        if name == "maketitle":
            if getattr(self, "_title_nodes", None):
                self.flush()
                self.cur_line = self.lc(t.pos)[0]
                self.cur = list(self._title_nodes)
                self.flush()
            return
        if name == "begin":
            self.begin_env(t, end)
            return
        if name == "end":
            g = self.read_group(end)
            self.diag("E004", f"\\end{{{self.raw_text(*g) if g else ''}}} without \\begin", t.pos)
            return
        if name == "item":
            self.item(t, end)
            return
        if name == "note":
            self.note(t, end)
            return
        if name in VSPACE:
            if name == "vspace":
                if self.is_char(self.i, "*"):
                    self.i += 1
                self.read_group(end)
            self.blank_line()
            return
        if name in ("newcommand", "renewcommand", "providecommand", "def", "DeclareMathOperator"):
            self.diag("W005", f"\\{name}: custom macros are not expanded; uses of the macro will be errors",
                      t.pos, "replace the macro by its definition")
            if self.is_char(self.i, "*"):
                self.i += 1
            self.read_arg(end)
            self.read_optional(end)
            self.read_optional(end)
            self.read_group(end)
            return
        if name in TEXT_SKIP_ARGS:
            if self.is_char(self.i, "*"):
                self.i += 1
            self.read_optional(end)
            for _ in range(TEXT_SKIP_ARGS[name]):
                self.read_group(end)
            if name in ("hspace",):
                self.add_space(t.pos)
            if name in ("includegraphics",):
                self.diag("W005", "image dropped (\\includegraphics)", t.pos)
            return
        if name in TEXT_FONT or name in STYLED_TEXT:
            g = self.read_group(end, f"\\{name}")
            if name in STYLED_TEXT:
                self.diag("W004", f"\\{name}: the calculator has no bold/italic/underline; text kept plain",
                          t.pos, once_key=("W004", name))
            if g:
                self.text_range(*g)
                self.i = max(self.i, g[1] + 1)
            return
        if name == "footnote":
            g = self.read_group(end)
            if g:
                self.diag("W003", "footnote written inline in parentheses", t.pos, once_key="footnote")
                self.add(self.chars(" (", t.pos), t.pos)
                self.text_range(*g)
                self.i = g[1] + 1
                self.add(self.chars(")", t.pos), t.pos)
            return
        if name in ("ref", "eqref", "cite", "pageref", "url", "href"):
            g = self.read_group(end)
            if name == "href":
                g = self.read_group(end) or g
            if name in ("url", "href") and g:
                self.text_range(*g)
                self.i = g[1] + 1
            else:
                self.diag("W005", f"\\{name} has no meaning on the calculator; written as '?'", t.pos)
                self.add(self.chars("?", t.pos), t.pos)
            return
        if name in TEXT_ACCENTS:
            self.text_accent(name, t, end)
            return
        if name in TEXT_SYMBOLS:
            self.add(self.chars(TEXT_SYMBOLS[name], t.pos), t.pos)
            return
        if name in (" ", ",", ";", ":", "quad", "qquad", "enspace", "thinspace"):
            self.add_space(t.pos)
            return
        if name in TEXT_IGNORED or name in ("today", "thanks"):
            if name in ("thanks",):
                self.read_group(end)
            return
        if name == "raw":
            self.add(self.raw(t, end), t.pos)
            return
        if name in ("abs", "diff"):
            self.diag("E007", f"\\{name} is a math command; put it inside $…$", t.pos)
            return
        if name in GREEK or name in SYMBOLS or name in FUNCTIONS or name in ("frac", "sqrt", "sum", "int"):
            self.diag("E007", f"\\{name} is a math command; put it inside $…$", t.pos,
                      f"write ${self.raw_text(self.i - 1, self.i)}…$")
            return
        self.diag("E001", f"unknown command \\{name}", t.pos, suggest(name))

    def text_accent(self, name, t, end):
        arg = self.read_arg(end)
        base = ""
        if arg:
            s, e = arg
            if e - s == 1 and self.toks[s].kind == "cmd" and self.toks[s].val in ("i", "j"):
                base = self.toks[s].val
            else:
                base = self.raw_text(s, e).strip()
        if not base:
            self.diag("E003", f"accent \\{name} needs a letter", t.pos)
            return
        composed = unicodedata.normalize("NFC", base[0] + TEXT_ACCENTS[name]) + base[1:]
        self.add(self.chars(composed, t.pos), t.pos)

    def item(self, t, end):
        self.flush()
        label = self.read_optional(end)
        if not self.lists:
            self.diag("E004", "\\item outside a list environment", t.pos)
            prefix = "- "
        else:
            env, count = self.lists[-1]
            self.lists[-1][1] += 1
            depth = len(self.lists) - 1
            if label is not None:
                text = "".join(n.src for n in self.text_inline(*label) if isinstance(n, Char))
                prefix = text + (": " if env == "description" else " ")
            elif env == "enumerate":
                n = count + 1
                prefix = (f"{n})" if depth % 2 == 0 else f"{chr(ord('a') + (n - 1) % 26)})") + " "
            else:
                prefix = "- "
            prefix = " " * depth + prefix
        self.cur_line = self.lc(t.pos)[0]
        self.cur = self.chars(prefix, t.pos)
        self.skip_ws(end)

    def note(self, t, end):
        if self.in_note:
            self.diag("E007", "\\note cannot be nested", t.pos)
            return
        tg = self.read_group(end, "\\note title")
        cg = self.read_group(end, "\\note content")
        if tg is None or cg is None:
            self.diag("E003", "\\note needs {title}{content}", t.pos)
            return
        self.flush()
        title = self.text_inline(*tg)
        saved = self.blocks, self.cur, self.lists
        self.blocks, self.cur, self.lists = [], [], []
        self.in_note = True
        self.text_range(*cg)
        self.flush()
        self.in_note = False
        lines = [b for b in _tidy(self.blocks) if isinstance(b, TextLine)]
        self.blocks, self.cur, self.lists = saved
        self.blocks.append(Note(title, lines or [TextLine([])], self.lc(t.pos)[0]))

    def begin_env(self, t, end):
        g = self.read_group(end, "\\begin")
        env = self.raw_text(*g).strip() if g else ""
        if env in ("document",):
            return
        if env in LIST_ENVS:
            self.read_optional(end)
            s, e = self.env_body(env, end, t.pos)
            self.flush()
            self.lists.append([env, 0])
            self.text_range(s, e)
            self.flush()
            self.lists.pop()
            return
        if env in DISPLAY_ENVS or env in INNER_ALIGN_ENVS:
            if env.startswith("alignat"):
                self.read_group(end)
            s, e = self.env_body(env, end, t.pos)
            self.display_math(s, e, t.pos)
            return
        if env in ("tabular", "tabular*", "tabularx", "longtable", "array"):
            if env in ("tabular*", "tabularx"):
                self.read_group(end)
            self.read_optional(end)
            self.read_group(end)
            s, e = self.env_body(env, end, t.pos)
            self.tabular(s, e, t.pos)
            return
        if env in ("table",):
            self.read_optional(end)
            s, e = self.env_body(env, end, t.pos)
            self.text_range(s, e)
            return
        if env in DROPPED_ENVS:
            self.read_optional(end)
            self.env_body(env, end, t.pos)
            self.diag("W005", f"environment '{env}' cannot be shown on the calculator and was dropped", t.pos)
            return
        if env in ("verbatim", "lstlisting", "minted"):
            s, e = self.env_body(env, end, t.pos)
            self.flush()
            for line in self.raw_text(s, e).strip("\n").split("\n"):
                self.cur_line = self.lc(t.pos)[0]
                self.cur = self.chars(line.replace("\t", "  "), t.pos)
                self.flush(keep_empty=True)
            return
        if env in TRANSPARENT_ENVS:
            if env == "minipage":
                self.read_optional(end)
                self.read_group(end)
            if env == "multicols":
                self.read_group(end)
            s, e = self.env_body(env, end, t.pos)
            self.text_range(s, e)
            self.flush()
            return
        # Theorem-like or unknown environment: keep the content, label it.
        opt = self.read_optional(end)
        s, e = self.env_body(env, end, t.pos)
        self.diag("W005", f"environment '{env}' is not known; its content is kept under a '{env.capitalize()}:' label",
                  t.pos, once_key=("env", env))
        self.flush()
        self.cur_line = self.lc(t.pos)[0]
        label = env.rstrip("*").capitalize()
        self.cur = self.chars(label, t.pos)
        if opt:
            self.cur += self.chars(" (", t.pos) + self.text_inline(*opt) + self.chars(")", t.pos)
        self.cur += self.chars(": ", t.pos)
        self.text_range(s, e)
        self.flush()

    def tabular(self, s, e, pos):
        self.diag("W003", "table written as one line per row, cells separated by ' | '", pos, once_key="tabular")
        self.flush()
        for row in self.split(s, e, "\\"):
            cells = self.split(*row, "&")
            nodes = []
            for k, cell in enumerate(cells):
                if k:
                    nodes += self.chars(" | ", pos)
                nodes += self.text_inline(*cell)
            if any(not (isinstance(n, Char) and n.src in " |") for n in nodes):
                self.cur_line = self.lc(self.pos_of(row[0]))[0]
                self.cur = nodes
                self.flush()

    def split(self, s, e, sep):
        """Split token range at top level on '\\\\' (sep='\\') or '&'."""
        parts, depth, env_depth, start = [], 0, 0, s
        k = s
        while k < e:
            t = self.toks[k]
            if t.kind == "char" and t.val == "{":
                depth += 1
            elif t.kind == "char" and t.val == "}":
                depth -= 1
            elif t.kind == "cmd" and t.val == "begin":
                env_depth += 1
            elif t.kind == "cmd" and t.val == "end":
                env_depth -= 1
            elif depth == 0 and env_depth == 0:
                if (sep == "\\" and t.kind == "cmd" and t.val in ("\\", "cr")) or \
                        (sep == "&" and t.kind == "char" and t.val == "&"):
                    parts.append((start, k))
                    start = k + 1
                    if sep == "\\":  # skip [2mm] after \\
                        save = self.i
                        self.i = start
                        if self.read_optional(e):
                            start = self.i
                        self.i = save
            k += 1
        parts.append((start, e))
        return parts

    # -- math mode --------------------------------------------------------
    def display_math(self, s, e, pos):
        self.flush()
        rows = self.split(s, e, "\\")
        # Rows inside aligned/gathered/split are hidden from split(): flatten them.
        for rs, re_ in rows:
            inner = self.inner_align(rs, re_)
            for a, b in inner:
                nodes = self.math_range(a, b)
                if nodes:
                    self.cur_line = self.lc(self.pos_of(a))[0]
                    self.cur = nodes
                    self.flush()

    def inner_align(self, s, e):
        """A display row that is exactly \\begin{aligned}…\\end{aligned} is split
        into that environment's rows; any other row is returned unchanged."""
        k = s
        while k < e and self.toks[k].kind in ("space", "nl"):
            k += 1
        if k < e and self.is_cmd(k, "begin") and self.env_name_at(k, e) in INNER_ALIGN_ENVS:
            env = self.env_name_at(k, e)
            save = self.i
            self.i = k + 1
            self.read_group(e)
            if env == "alignedat":
                self.read_group(e)
            body = self.i
            stop = self.find_end(env, body, e)
            after = None
            if stop is not None:
                self.i = stop + 1
                self.read_group(e)
                after = self.i
            self.i = save
            if after is not None and all(t.kind in ("space", "nl") for t in self.toks[after:e]):
                return self.split(body, stop, "\\")
        return [(s, e)]

    def math_range(self, s, e) -> list[Node]:
        """Parse a token range as math.  Spaces at both ends (from \\, etc.) are trimmed."""
        save = self.i
        self.i = s
        nodes = self.math_seq(e)
        self.i = save
        while nodes and isinstance(nodes[-1], Char) and nodes[-1].src == " ":
            nodes.pop()
        while nodes and isinstance(nodes[0], Char) and nodes[0].src == " ":
            nodes.pop(0)
        return nodes

    def math_seq(self, end, stop=None) -> list[Node]:
        nodes: list[Node] = []
        depth = 0
        while self.i < end:
            t = self.toks[self.i]
            if stop and depth == 0 and nodes and stop(t):
                break
            if t.kind == "char" and t.val in "([":
                depth += 1
            elif t.kind == "char" and t.val in ")]":
                depth = max(0, depth - 1)
            nodes.extend(self.math_atom(end))
        return nodes

    @staticmethod
    def term_stop(t: Tok) -> bool:
        if t.kind == "char":
            return t.val in "+-=<>,;&"
        if t.kind == "cmd":
            return t.val in RELATIONS
        return False

    def math_atom(self, end) -> list[Node]:
        t = self.toks[self.i]
        if t.kind in ("space", "nl", "par"):
            self.i += 1
            return []
        if t.kind == "char":
            c = t.val
            if c == "{":
                g = self.read_group(end)
                return self.math_range(*g) if g else []
            self.i += 1
            if c == "}":
                self.diag("E004", "unmatched '}'", t.pos)
                return []
            if c == "^":
                return self.superscript(t, end)
            if c == "_":
                return self.subscript(t, end)
            if c == "|":
                return self.bars(t, end)
            if c in "&$":
                return []
            if c == "~":
                return [self.space()]
            return self.char(c, t.pos, math=True)
        self.i += 1
        return self.math_command(t, end)

    def superscript(self, t, end) -> list[Node]:
        arg = self.read_arg(end, "^")
        if arg is None:
            self.diag("E003", "'^' needs an exponent", t.pos)
            return []
        s, e = arg
        inner = [k for k in range(s, e) if self.toks[k].kind not in ("space", "nl")]
        if inner and all(self.is_cmd(k, "circ") for k in inner):
            return self.chars("°" * len(inner), t.pos)
        if inner and all(self.is_cmd(k, "prime") for k in inner):
            return self.chars("′" * len(inner), t.pos)
        return [Pow(self.math_range(s, e))]

    def subscript(self, t, end) -> list[Node]:
        arg = self.read_arg(end, "_")
        if arg is None:
            self.diag("E003", "'_' needs a subscript", t.pos)
            return []
        nodes = self.math_range(*arg)
        out, inline = [], False
        for n in nodes:
            code = self.cmap.subscript(n.src) if isinstance(n, Char) and len(n.src) == 1 else None
            if code:
                out.append(Char(code, "_" + n.src))
            else:
                inline = True
                out.append(n)
        if inline:
            self.diag("W002", "subscript contains characters without a subscript glyph; written inline",
                      t.pos, "only A-Z, a-z, 0-9, + and - exist as subscripts")
            first = next((k for k, n in enumerate(out) if not (isinstance(n, Char) and n.src.startswith("_"))), 0)
            out = out[:first] + [Char(b"_", "_")] + out[first:]
        return out

    def bars(self, t, end) -> list[Node]:
        """|x| -> Abs when a matching bar exists at this level."""
        depth = 0
        for k in range(self.i, end):
            tk = self.toks[k]
            if tk.kind == "char" and tk.val == "{":
                depth += 1
            elif tk.kind == "char" and tk.val == "}":
                depth -= 1
            elif depth == 0 and tk.kind == "char" and tk.val == "|":
                body = self.math_range(self.i, k)
                self.i = k + 1
                return [Abs(body)]
        return self.char("|", t.pos)

    def math_command(self, t: Tok, end) -> list[Node]:
        name = t.val
        pos = t.pos
        if name in GREEK:
            return self.char(GREEK[name], pos)
        if name in SYMBOLS:
            return self.char(SYMBOLS[name], pos, math=False)
        if name in SPACES:
            return [self.space()]
        if name in IGNORED_MATH:
            return []
        if name in LOOKALIKES:
            rep = LOOKALIKES[name]
            self.diag("W001", f"\\{name} has no CASIO glyph; written as '{rep}'", pos)
            return self.chars(rep, pos)
        if name in FUNCTIONS:
            return self.function_name(name, pos)
        if name == "log":
            return self.log(t, end)
        if name in LIMIT_FUNCTIONS:
            out = self.chars(name, pos)
            self.skip_ws(end)
            if self.is_cmd(self.i, "limits"):
                self.i += 1
                self.skip_ws(end)
            if self.is_char(self.i, "_"):
                self.i += 1
                arg = self.read_arg(end, f"\\{name}_")
                if arg:
                    self.diag("W003", f"\\{name}_{{…}}: limit written inline as {name}(…)", pos,
                              once_key=("lim", name))
                    out += self.chars("(", pos) + self.math_range(*arg) + self.chars(")", pos)
            return out
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            a = self.read_arg(end, f"\\{name} numerator")
            b = self.read_arg(end, f"\\{name} denominator")
            if a is None or b is None:
                self.diag("E003", f"\\{name} needs {{numerator}}{{denominator}}", pos)
                return []
            return [Frac(self.math_range(*a), self.math_range(*b))]
        if name == "binom":
            a = self.read_arg(end)
            b = self.read_arg(end)
            if a is None or b is None:
                self.diag("E003", "\\binom needs two arguments", pos)
                return []
            self.diag("W003", "\\binom{n}{k} written as nCk", pos, once_key="binom")
            return self.math_range(*a) + self.chars("C", pos) + self.math_range(*b)
        if name == "sqrt":
            return self.sqrt(t, end)
        if name == "sum":
            return self.sum(t, end)
        if name == "prod":
            return self.big_glyph("Π", "product", t, end)
        if name in ("int", "iint", "iiint", "oint"):
            return self.integral(t, end)
        if name in ("left", "right"):
            return self.delimiter(t, end)
        if name in TEXT_FONT or name in MATH_FONT:
            g = self.read_arg(end, f"\\{name}")
            if g is None:
                return []
            if name in TEXT_FONT or name == "operatorname":
                nodes = self.text_inline(*g)
            else:
                nodes = self.math_range(*g)
            if name in ("mathbb", "mathcal", "mathfrak", "mathscr"):
                self.diag("W004", f"\\{name}: blackboard/calligraphic letters written plain", pos,
                          once_key=("W004", name))
            return nodes
        if name in ("bar", "overline", "hat", "widehat"):
            g = self.read_arg(end, f"\\{name}")
            if g is None:
                return []
            nodes = self.math_range(*g)
            src = "".join(n.src for n in nodes if isinstance(n, Char)) if all(isinstance(n, Char) for n in nodes) else ""
            glyph = {("bar", "x"): "xbar", ("bar", "y"): "ybar", ("hat", "x"): "xcirc",
                     ("hat", "y"): "ycirc", ("hat", "p"): "pcirc"}.get(
                ({"overline": "bar", "widehat": "hat"}.get(name, name), src))
            if glyph:
                sym = self.cmap.func(glyph)
                return [Char(sym.code, f"\\{glyph};")]
            self.diag("W003", f"\\{name}{{{src or '…'}}}: only x̄, ȳ, x̂, ŷ, p̂ exist; accent dropped", pos)
            return nodes
        if name in ACCENT_DROPPED:
            g = self.read_arg(end, f"\\{name}")
            if name in ("underbrace", "overbrace"):
                # drop the annotation that follows (_{…} / ^{…})
                pass
            self.diag("W003", f"\\{name}: accent/decoration not available; content kept", pos,
                      once_key=("accent", name))
            return self.math_range(*g) if g else []
        if name == "begin":
            return self.math_env(t, end)
        if name == "end":
            self.read_group(end)
            self.diag("E004", "\\end without \\begin", pos)
            return []
        if name == "abs":
            g = self.read_arg(end, "\\abs")
            return [Abs(self.math_range(*g))] if g else []
        if name == "diff":
            order = 1
            if self.is_char(self.i, "2"):
                self.i += 1
                order = 2
            a = self.read_group(end, "\\diff")
            b = self.read_group(end, "\\diff")
            if a is None or b is None:
                self.diag("E003", "\\diff needs {f(x)}{x-value}", pos)
                return []
            return [Diff(self.math_range(*a), self.math_range(*b), order)]
        if name == "raw":
            return self.raw(t, end)
        if name in ("label", "tag", "tag*"):
            self.read_group(end)
            return []
        if name == "\\":
            return [self.space()]
        self.diag("E001", f"unknown math command \\{name}", pos, suggest(name))
        return []

    def function_name(self, name, pos) -> list[Node]:
        """'sin' etc. as text; "\\sin x" -> "sin x" but "\\sin(x)" stays "sin(x)"."""
        out = self.chars(name, pos)
        nxt = self.tok()
        if nxt is not None and nxt.kind == "space":
            nxt = self.tok(self.i + 1)
        if nxt is not None and ((nxt.kind == "char" and nxt.val.isalnum()) or
                                (nxt.kind == "cmd" and (nxt.val in GREEK or nxt.val in FUNCTIONS))):
            out.append(self.space())
        return out

    def raw(self, t, end) -> list[Node]:
        g = self.read_group(end, "\\raw")
        if g is None:
            self.diag("E003", "\\raw needs {hex bytes}", t.pos)
            return []
        text = self.raw_text(*g)
        try:
            return [Char(bytes.fromhex(text), f"\\raw{{{text}}}")]
        except ValueError:
            self.diag("E006", f"\\raw{{{text}}} is not a hex byte sequence", t.pos)
            return []

    def log(self, t, end) -> list[Node]:
        self.skip_ws(end)
        if not self.is_char(self.i, "_"):
            return self.function_name("log", t.pos)
        self.i += 1
        base = self.read_arg(end, "\\log base")
        if base is None:
            self.diag("E003", "\\log_ needs a base", t.pos)
            return self.chars("log", t.pos)
        arg = self.function_argument(end)
        if arg is None:
            self.diag("E003", "\\log_b needs an argument", t.pos)
            return self.chars("log", t.pos) + self.subscript_nodes(self.math_range(*base))
        return [Log(self.math_range(*base), arg)]

    def subscript_nodes(self, nodes):
        return [Char(self.cmap.subscript(n.src), "_" + n.src)
                if isinstance(n, Char) and len(n.src) == 1 and self.cmap.subscript(n.src) else n
                for n in nodes]

    def function_argument(self, end):
        """The argument of a function: (…), \\left(…\\right), {…} or one atom."""
        self.skip_ws(end)
        if self.is_char(self.i, "("):
            j = self.match_brace(self.i, end, "(", ")")
            if j is not None:
                nodes = self.math_range(self.i + 1, j)
                self.i = j + 1
                return nodes
        if self.is_cmd(self.i, "left") and self.is_char(self.i + 1, "("):
            k, depth = self.i, 0
            while k < end:
                if self.is_cmd(k, "left"):
                    depth += 1
                elif self.is_cmd(k, "right"):
                    depth -= 1
                    if depth == 0:
                        nodes = self.math_range(self.i + 2, k)
                        self.i = k + 2
                        return nodes
                k += 1
        if self.i < end:
            return self.math_atom(end)
        return None

    def sqrt(self, t, end) -> list[Node]:
        n = self.read_optional(end)
        body = self.read_arg(end, "\\sqrt")
        if body is None:
            self.diag("E003", "\\sqrt needs an argument", t.pos)
            return []
        inner = self.math_range(*body)
        if n is None:
            return [Sqrt(inner)]
        index = self.raw_text(*n).strip()
        if index.isdigit():
            if index == "2":
                return [Sqrt(inner)]
            sup = "".join(SUPERSCRIPT_DIGITS[int(d)] for d in index)
            return self.chars(sup, t.pos) + [Sqrt(inner)]
        self.diag("W003", f"\\sqrt[{index}]: non-numeric root index written as a power 1/{index}", t.pos)
        return (self.chars("(", t.pos) + inner + self.chars(")", t.pos)
                + [Pow([Frac(self.chars("1", t.pos), self.math_range(*n))])])

    def limits(self, end):
        lower = upper = None
        for _ in range(2):
            self.skip_ws(end)
            if self.is_cmd(self.i, "limits") or self.is_cmd(self.i, "nolimits"):
                self.i += 1
                self.skip_ws(end)
            if self.is_char(self.i, "_") and lower is None:
                self.i += 1
                lower = self.read_arg(end, "lower limit")
            elif self.is_char(self.i, "^") and upper is None:
                self.i += 1
                upper = self.read_arg(end, "upper limit")
        return lower, upper

    def sum(self, t, end) -> list[Node]:
        lower, upper = self.limits(end)
        if lower is None or upper is None:
            return self.big_glyph("Σ", "sum", t, end, lower, upper)
        # split "k=0" into var and start
        eq = next((k for k in range(*lower) if self.is_char(k, "=")), None)
        if eq is None:
            self.diag("W003", "\\sum lower limit has no 'var=start'; Σ written without a template",
                      t.pos, "write \\sum_{k=0}^{n}")
            return self.big_glyph("Σ", "sum", t, end, lower, upper)
        self.skip_ws(end)
        expr = self.math_seq(end, stop=self.term_stop)
        if not expr:
            self.diag("E003", "\\sum has no summand", t.pos)
        return [Sum(expr, self.math_range(lower[0], eq), self.math_range(eq + 1, lower[1]),
                    self.math_range(*upper))]

    def big_glyph(self, glyph, what, t, end, lower=None, upper=None) -> list[Node]:
        if lower is None and upper is None:
            lower, upper = self.limits(end)
        out = self.chars(glyph, t.pos)
        if lower or upper:
            self.diag("W003", f"{what} limits written inline ({glyph}_…^…)", t.pos, once_key=("big", what))
        if lower:
            out += self.subscript_nodes(self.math_range(*lower))
        if upper:
            out += [Pow(self.math_range(*upper))]
        return out

    def integral(self, t, end) -> list[Node]:
        glyph = {"int": "∫", "iint": "∬", "iiint": "∬", "oint": "∮"}[t.val]
        lower, upper = self.limits(end)
        if t.val != "int" or lower is None or upper is None:
            out = self.chars(glyph, t.pos)
            if lower or upper:
                self.diag("W003", "only definite single integrals have a CASIO template; limits written inline",
                          t.pos, once_key="intlimits")
                if lower:
                    out += self.subscript_nodes(self.math_range(*lower))
                if upper:
                    out += [Pow(self.math_range(*upper))]
            return out
        d = self.find_differential(end)
        if d is None:
            self.diag("W003", "no 'dx' found after the integral; body taken up to the next operator",
                      t.pos, "end the integrand with \\,dx")
            body = self.math_seq(end, stop=self.term_stop)
        else:
            k, var = d
            body = self.math_range(self.i, k)
            self.i = k + 2
            if var != "x":
                self.diag("W008", f"the calculator always shows 'dx'; integration variable '{var}' is lost",
                          t.pos, f"rename {var} to x in the integrand")
        return [Integral(body, self.math_range(*lower), self.math_range(*upper))]

    def find_differential(self, end):
        depth = 0
        for k in range(self.i, end - 1):
            tk = self.toks[k]
            if tk.kind == "char" and tk.val == "{":
                depth += 1
            elif tk.kind == "char" and tk.val == "}":
                depth -= 1
            elif depth == 0 and tk.kind == "char" and tk.val in "=<>":
                return None
            elif depth == 0 and tk.kind == "cmd" and tk.val in RELATIONS - {"quad", "qquad", "cdots", "ldots", "text"}:
                return None
            if depth == 0 and tk.kind == "char" and tk.val == "d":
                nxt = self.tok(k + 1)
                if nxt and nxt.kind == "char" and nxt.val.isalpha() and nxt.val.isascii():
                    prev = self.tok(k - 1) if k > self.i else None
                    after = self.tok(k + 2)
                    prev_ok = prev is None or not (prev.kind == "char" and prev.val.isalpha())
                    after_ok = after is None or k + 2 >= end or not (after.kind == "char" and after.val.isalpha())
                    if prev_ok and after_ok:
                        return k, nxt.val
        return None

    def delimiter(self, t, end) -> list[Node]:
        """\\left X … \\right Y.  \\left| … \\right| becomes Abs."""
        tk = self.tok()
        if tk is None:
            return []
        self.i += 1
        val = tk.val
        if t.val == "left" and val == "|" or (t.val == "left" and tk.kind == "cmd" and val in ("lvert", "vert")):
            depth, k = 1, self.i
            while k < end:
                if self.is_cmd(k, "left"):
                    depth += 1
                elif self.is_cmd(k, "right"):
                    depth -= 1
                    if depth == 0:
                        body = self.math_range(self.i, k)
                        self.i = k + 2
                        return [Abs(body)]
                k += 1
        if val == ".":
            return []
        if tk.kind == "cmd":
            if val in ("{", "}", "lbrace", "rbrace"):
                return self.chars("{" if val in ("{", "lbrace") else "}", tk.pos)
            if val in SYMBOLS:
                return self.char(SYMBOLS[val], tk.pos)
            if val in LOOKALIKES:
                return self.chars(LOOKALIKES[val], tk.pos)
            if val in ("lvert", "rvert", "vert"):
                return self.chars("|", tk.pos)
            return []
        return self.char(val, tk.pos)

    def math_env(self, t, end) -> list[Node]:
        g = self.read_group(end, "\\begin")
        env = self.raw_text(*g).strip() if g else ""
        if env == "array":
            self.read_optional(end)
            self.read_group(end)
        if env in INNER_ALIGN_ENVS:
            if env == "alignedat":
                self.read_group(end)
            s, e = self.env_body(env, end, t.pos)
            self.diag("W003", f"'{env}' inside inline math: rows joined with ', '", t.pos, once_key="inneralign")
            out = []
            for k, (a, b) in enumerate(self.split(s, e, "\\")):
                nodes = self.math_range(a, b)
                if nodes:
                    out += (self.chars(", ", t.pos) if out else []) + nodes
            return out
        if env not in MATRIX_ENVS:
            s, e = self.env_body(env, end, t.pos)
            self.diag("W005", f"math environment '{env}' is not known; content kept", t.pos)
            return self.math_range(s, e)
        s, e = self.env_body(env, end, t.pos)
        rows = []
        for rs, re_ in self.split(s, e, "\\"):
            cells = [self.math_range(a, b) for a, b in self.split(rs, re_, "&")]
            if len(cells) == 1 and not cells[0]:
                continue  # trailing \\
            rows.append(cells)
        if not rows:
            self.diag("E003", f"empty {env}", t.pos)
            return []
        width = max(len(r) for r in rows)
        if any(len(r) != width for r in rows):
            self.diag("W003", f"{env}: rows padded to {width} columns", t.pos)
            rows = [r + [[] for _ in range(width - len(r))] for r in rows]
        kind = MATRIX_ENVS[env]
        if kind == "cases":
            self.diag("W003", "cases written as a matrix (value | condition)", t.pos, once_key="cases")
        elif kind == "vmatrix":
            self.diag("W003", f"{env} (determinant bars) written as a plain matrix", t.pos, once_key="vmatrix")
        return [Matrix(rows)]


def suggest(name: str) -> str:
    known = (set(GREEK) | set(SYMBOLS) | set(LOOKALIKES) | FUNCTIONS | LIMIT_FUNCTIONS
             | {"frac", "sqrt", "sum", "int", "log", "left", "right", "begin", "end", "text",
                "abs", "diff", "note", "raw", "section", "subsection", "item", "textbf", "emph"}
             | set(TEXT_SYMBOLS))
    close = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.75)
    if close:
        return "did you mean " + ", ".join("\\" + c for c in close) + "?"
    return "see docs/LATEX_SUBSET.md or `eact symbols --latex`"


def _tidy(blocks):
    """Collapse runs of empty lines and trim them at both ends."""
    out = []
    for b in blocks:
        empty = isinstance(b, TextLine) and not b.nodes
        if empty and (not out or (isinstance(out[-1], TextLine) and not out[-1].nodes)):
            continue
        out.append(b)
    while out and isinstance(out[-1], TextLine) and not out[-1].nodes:
        out.pop()
    return out


def parse(src: str, rep: Reporter) -> tuple[list, str | None]:
    """Parse LaTeX source.  Returns (blocks, text of \\title or None).

    When the source has ``\\begin{document}`` only the body is converted; the
    preamble is only scanned for ``\\title``.  A bare fragment (no
    ``\\begin{document}``) is converted as a whole.
    """
    p = LatexParser(src, rep)
    begin = p.find_env_cmd("begin", "document", 0)
    end = len(p.toks)
    if begin is not None:
        for k in range(begin):
            if p.is_cmd(k, "title"):
                p.i = k + 1
                p.text_command(p.toks[k], begin)
        p.i = begin + 1
        p.read_group(end)
        stop = p.find_env_cmd("end", "document", p.i)
        end = stop if stop is not None else end
    p.text_seq(end)
    p.flush()
    return _tidy(p.blocks), p.full_title
