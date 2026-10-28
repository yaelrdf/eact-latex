"""IR -> LaTeX (latex_writer.py).

The main property: the LaTeX that eact writes reads back to the same bytes.
It holds exactly for documents made from LaTeX, and for EactMaker files up to
the losses listed in docs/LATEX_OUTPUT.md.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "src"))

from eact import convert, decoder, eam  # noqa: E402
from eact.diagnostics import Reporter  # noqa: E402


def load(tex):
    doc, rep = convert.load_text(tex, "latex", "t.tex", title="T")
    return doc, [d.code for d in rep.items]


def to_tex(tex):
    """LaTeX -> IR -> LaTeX body."""
    return convert.to_latex(load(tex)[0], standalone=False).strip()


class TestRoundTrip(unittest.TestCase):
    def assertRoundTrip(self, doc):
        tex = convert.to_latex(doc)
        doc2, rep = convert.load_text(tex, "latex", "t.tex")
        self.assertEqual([d.code for d in rep.errors], [], tex)
        self.assertEqual(doc2.title, doc.title)
        self.assertEqual(eam.write_content(doc2, "\n"), eam.write_content(doc, "\n"), tex)
        self.assertEqual(convert.build(doc2), convert.build(doc))
        self.assertEqual(convert.to_latex(doc2), tex, "writing is not idempotent")

    def test_example_document(self):
        doc, rep = convert.load(str(ROOT / "examples" / "ejercicio.tex"), title="BISECCIO")
        self.assertRoundTrip(decoder.decode(convert.build(doc)))

    def test_eactmaker_fixtures(self):
        # Exact except where the documented losses apply.
        lossy = {"palette_probe", "intnest"}
        for f in sorted((FIX / "eactmaker").glob("*.g2e")):
            if f.stem in lossy:
                continue
            with self.subTest(f.name):
                self.assertRoundTrip(decoder.decode(f.read_bytes()))

    def test_lossy_files_are_stable(self):
        """After one pass through LaTeX, a second pass changes nothing."""
        for f in (FIX / "TEST.g2e", FIX / "eactmaker" / "palette_probe.g2e", FIX / "eactmaker" / "intnest.g2e"):
            with self.subTest(f.name):
                tex = convert.to_latex(decoder.decode(f.read_bytes()))
                doc2, rep = convert.load_text(tex, "latex", "t.tex")
                self.assertEqual(rep.errors, [])
                self.assertEqual(convert.to_latex(doc2), tex)
                self.assertRoundTrip(doc2)

    def test_snippets(self):
        for tex in [r"$\sum_{k=0}^{n} (a+b) + 1$", r"$\sum_{k=0}^{n} {a+b}$", r"${\sum_{k=0}^{n} a}b$",
                    r"$\int_0^1 {x=1}\,dx$", r"$\int_0^1 x\,dx y$", r"$\left| |a| - 1 \right|$",
                    r"$x^{a}{}^{b}$", r"$f''(x) + g'(x)^2$", r"$\sin x + \cos(2x)$", r"$\log_2((x))$",
                    r"\note{T}{a\\ b $\frac12$}", r"$\casio{i}^{2}=-1$", r"$\diff2{x^3}{1}$",
                    r"$\begin{pmatrix}1&2\\3&4\end{pmatrix}^{-1}$", r"$x$ -- y '' z", r"$\int_a f$",
                    r"$a^\circ$ 30° 50\% \& \# \_ \{x\} \textasciicircum \textasciigrave",
                    "\\section{Uno}\nTexto.\n\n\\medskip\n\n\\begin{enumerate}\\item a \\item b\\end{enumerate}"]:
            with self.subTest(tex):
                self.assertRoundTrip(load(tex)[0])


class TestOutput(unittest.TestCase):
    cases = {
        r"Sea $f(x) = x^3 - 2x - 5$ y $c = \frac{a+b}{2}$.":
            r"Sea $f(x)=x^{3}-2x-5$ y $c=\frac{a+b}{2}$.",
        r"\[ |x_n - r| \le \frac{b-a}{2^{n}} \]": r"\[ |x_{n}-r|\le\frac{b-a}{2^{n}} \]",
        r"$\sum_{k=0}^{n} \frac{1}{k!}$": r"\[ \sum_{k=0}^{n} \frac{1}{k!} \]",
        r"$\int_0^1 x^2 \, dx$": r"\[ \int_{0}^{1} x^{2}\,dx \]",
        r"$\log_2(8)$, $\sqrt[3]{27}$": r"$\log_{2}(8)$, $\sqrt[3]{27}$",
        r"$\bar{x}$ y $\hat{p}$": r"$\bar{x}$ y $\hat{p}$",
        r"$\alpha \approx 0.5$": r"\[ \alpha\approx0.5 \]",
        r"sin embargo": "sin embargo",                       # Spanish word, not \sin
        r"$\sin x$": r"\[ \sin x \]",
        r"de $n$ pasos": r"de $n$ pasos",                    # lone consonant -> math
        r"$\varepsilon_{mach}$": r"\[ \varepsilon_{mach} \]",
        r"\section{Método}": r"\section{Método}",
        r"\note{Tip}{Hola}": "\\note{Tip}{\n  Hola\n}",
        r"$\casio{s10}$": r"\[ \casio{s10} \]",
    }

    def test_cases(self):
        for tex, want in self.cases.items():
            with self.subTest(tex):
                self.assertEqual(to_tex(tex), want)

    def test_lists(self):
        out = to_tex(r"\begin{enumerate}\item $x=1$ \item dos\end{enumerate}")
        self.assertEqual(out, "\\begin{enumerate}\n  \\item $x=1$\n  \\item dos\n\\end{enumerate}")
        # numbering that does not start at 1 is kept as plain text
        doc, _ = convert.load_text("2) uno", "eam", "t.eam", title="T")
        self.assertEqual(convert.to_latex(doc, standalone=False).strip(), "2) uno")

    def test_preamble_defines_used_extensions(self):
        doc, _ = load(r"\note{N}{$\diff{x}{1}$ $\casio{i}$}")
        tex = convert.to_latex(doc)
        for macro in (r"\providecommand{\note}", r"\providecommand{\diff}", r"\providecommand{\casio}",
                      r"\@namedef{eact@casio@i}"):
            self.assertIn(macro, tex)
        self.assertNotIn(r"\providecommand{\raw}", tex)
        self.assertTrue(tex.rstrip().endswith(r"\end{document}"))

    def test_raw_fallback_warns(self):
        doc, _ = convert.load_text(r"\raw{E7}", "eam", "t.eam", title="T")   # glyph with no LaTeX form
        rep = Reporter()
        tex = convert.to_latex(doc, rep)
        self.assertIn(r"\raw{E7}", tex)
        self.assertIn(r"\providecommand{\raw}", tex)
        self.assertEqual([d.code for d in rep.items], ["W009"])


class TestParserAdditions(unittest.TestCase):
    """LaTeX input features added so that the writer's output reads back."""

    def test_casio(self):
        doc, codes = load(r"$\casio{i}$ \casio{negB}")
        self.assertEqual(eam.write_content(doc, "\n"), r"\i; \negB;")
        self.assertEqual(codes, [])
        self.assertEqual(load(r"x $\casio{nope}$")[1], ["E001"])

    def test_double_prime(self):
        self.assertEqual(eam.write_content(load("$f''(x)$")[0], "\n"), "f″(x)")

    def test_new_symbols(self):
        self.assertEqual(eam.write_content(load(r"$\blacktriangleright\bigcirc$")[0], "\n"), "▶○")


if __name__ == "__main__":
    unittest.main()
