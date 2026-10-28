"""LaTeX front-end: each case is checked through its EactMaker markup, which
maps 1:1 onto bytes (tested in test_format.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from eact import convert, eam  # noqa: E402


def conv(tex):
    doc, rep = convert.load_text(tex, "latex", "t.tex", title="T")
    return eam.write_content(doc, "\n"), [d.code for d in rep.items]


class TestMath(unittest.TestCase):
    cases = {
        r"$\frac{a}{b}$": r"\frac{a}{b}",
        r"$\frac12$": r"\frac{1}{2}",
        r"$\sqrt{x+1}$": r"\sqrt{x+1}",
        r"$\sqrt[3]{8}$": r"³\sqrt{8}",
        r"$x^2 + x^{10}$": r"x^{2}+x^{10}",
        r"$a - b$": "a−b",
        r"$x_1 + x_{n-1}$": "x₁+x_n₋₁",
        r"$\sum_{k=0}^{n} k^2$": r"\sum{n}{k}{0}{k^{2}}",
        r"$\sum_{i=1}^{n} \frac{1}{i} = H_n$": r"\sum{n}{i}{1}{\frac{1}{i}}=H_n",
        r"$\int_0^1 x^2\,dx$": r"\int{1}{0}{x^{2}}",
        r"$\int_{a}^{b} f(x) dx = F$": r"\int{b}{a}{f(x)}=F",
        r"$\int x\,dx$": "∫x dx",
        r"$\log_2 8$": r"\log{2}{8}",
        r"$\log_{b}(x+1)$": r"\log{b}{x+1}",
        r"$\log x$": "log x",
        r"$|x-1|$": r"\abs{x−1}",
        r"$\left| x \right|$": r"\abs{x}",
        r"$\begin{pmatrix}1&2\\3&4\end{pmatrix}$": r"\mat{1&2}{3&4}",
        r"$\alpha\beta\Gamma$": "αβΓ",
        r"$a \le b \ne c \approx d$": "a≤b≠c≈d",
        r"$\bar{x}, \hat{p}$": r"\xbar;,\pcirc;",
        r"$90^\circ$": "90°",
        r"$f'(x)$": "f′(x)",
        r"$\sin x + \cos(x)$": "sin x+cos(x)",
        r"$\diff{x^2}{3}$": r"\diff{x^{2}}{3}",
        r"$\frac{\sqrt{a}}{b^{2}}$": r"\frac{\sqrt{a}}{b^{2}}",
    }

    def test_cases(self):
        for tex, expected in self.cases.items():
            with self.subTest(tex=tex):
                out, codes = conv(tex)
                self.assertEqual(out, expected)
                self.assertEqual([c for c in codes if c[0] in "EW"], [], codes)


class TestText(unittest.TestCase):
    def test_paragraphs_and_breaks(self):
        out, _ = conv("uno\ndos\n\ntres\\\\cuatro")
        self.assertEqual(out, "uno dos\ntres\ncuatro")

    def test_accents_and_spanish(self):
        out, codes = conv(r"\'a \~n ¿qué? Método")
        self.assertEqual(out, "á ñ ¿qué? Método")
        self.assertEqual(codes, [])

    def test_sections_and_lists(self):
        out, _ = conv("\\section{A}\nx\n\\begin{enumerate}\\item p\\item q\\end{enumerate}"
                      "\\begin{itemize}\\item r\\end{itemize}")
        self.assertEqual(out, "==A==\nx\n1) p\n2) q\n- r")

    def test_display_math_rows(self):
        out, _ = conv("\\begin{align*} a &= 1 \\\\ b &= 2 \\end{align*}")
        self.assertEqual(out, "a=1\nb=2")

    def test_body_only(self):
        out, _ = conv("\\documentclass{article}\\title{X}\\begin{document}hola\\end{document}")
        self.assertEqual(out, "hola")

    def test_note(self):
        out, _ = conv("\\note{Tip}{uno\\\\$x^2$}")
        self.assertEqual(out, "\\note{Tip}{uno\nx^{2}}")

    def test_comments_removed(self):
        out, _ = conv("a % hidden\nb")
        self.assertEqual(out, "a b")

    def test_escapes(self):
        out, codes = conv(r"50\% \& \_ \$")
        self.assertEqual(out, "50% & \\_ $")
        self.assertEqual(codes, [])


class TestDiagnostics(unittest.TestCase):
    def assertCodes(self, tex, *codes):
        _, got = conv(tex)
        for c in codes:
            self.assertIn(c, got, f"{tex!r}: expected {c}, got {got}")

    def test_unknown_command(self):
        self.assertCodes(r"$\fracc{1}{2}$", "E001")
        self.assertCodes(r"\foo", "E001")

    def test_no_glyph(self):
        self.assertCodes("😀", "E002")

    def test_lookalike(self):
        self.assertCodes("ǵ", "W001")
        self.assertCodes(r"$\hbar$", "W001")

    def test_unbalanced(self):
        self.assertCodes(r"$\frac{1}{$", "E004")
        self.assertCodes(r"$x", "E004")
        self.assertCodes(r"\begin{itemize}\item a", "E004")

    def test_missing_argument(self):
        self.assertCodes(r"$\frac{1}$", "E003")

    def test_subscript_fallback(self):
        self.assertCodes(r"$x_{\alpha}$", "W002")

    def test_approximations(self):
        self.assertCodes(r"$\lim_{x\to 0} x$", "W003")
        self.assertCodes(r"$\vec{v}$", "W003")
        self.assertCodes(r"$\int_0^1 t\,dt$", "W008")
        self.assertCodes(r"\textbf{x}", "W004")

    def test_empty(self):
        self.assertCodes("% nothing", "E008")

    def test_positions(self):
        doc, rep = convert.load_text("ok\n  😀", "latex", "f.tex", title="T")
        d = rep.errors[0]
        self.assertEqual((d.line, d.col, d.file), (2, 3, "f.tex"))

    def test_title(self):
        doc, rep = convert.load_text("x", "latex", "f.tex", title="Métodos numéricos")
        self.assertEqual(doc.title, "METODOS")
        self.assertIn("W006", [d.code for d in rep.items])


if __name__ == "__main__":
    unittest.main()
