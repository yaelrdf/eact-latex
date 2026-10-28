# eActivity → LaTeX (`eact dump --as latex`)

`eact` also works in the other direction. It turns any `.g2e`/`.g1e` into a LaTeX document,
whether `eact` made the file, EactMaker made it, or it was typed on the calculator:

```bash
eact dump NOTES.g2e --as latex -o notes.tex       # full document
eact dump NOTES.g2e --as latex --fragment         # only the body, to paste into another file
```

In Python:

```python
from eact import convert, decoder
doc = decoder.decode(open("NOTES.g2e", "rb").read())
tex = convert.to_latex(doc)                       # standalone=False for the body only
```

The output is meant to be both:

1. **real LaTeX.** It compiles with `pdflatex`, `xelatex` or `lualatex`. The preamble loads
   `amsmath`/`amssymb` and defines every eact extension the body uses (`\note`, `\diff`,
   `\casio`, `\raw`), so no eact-specific package is needed.
2. **an exact source.** Running `eact build notes.tex` on it gives back the same calculator
   content. For files that `eact` built from LaTeX, the result is byte-identical. The test suite
   checks this on every fixture (`tests/test_latex_writer.py`).

## What each part becomes

| On the calculator | LaTeX written |
|---|---|
| title (the `=====TITLE=====` line) | `\title{TITLE}` in the preamble. `eact build` uses it as the title again. There is no `\maketitle`, because that would add a line |
| `==Text==` / `=Text=` | `\section{Text}` / `\subsection{Text}`. The blank line before a section is implied |
| `- item` lines | `itemize` |
| `1) …`, `2) …` lines numbered from 1 | `enumerate` |
| a blank line | `\medskip` |
| any other line | one paragraph. A line that is one formula becomes `\[ … \]`; formulas inside text become `$…$` |
| NOTES strip | `\note{title}{…}`, with one paragraph per line |
| fraction, √, power, Σ, ∫, log, \|x\|, matrix | `\frac`, `\sqrt` (`\sqrt[3]` for a ³ glyph before √), `^{…}`, `\sum_{k=0}^{n}`, `\int_{a}^{b} … \,dx`, `\log_{b}(…)`, `\|…\|` (`\left\|…\right\|` when nested), `bmatrix` |
| d/dx templates | `\diff{f}{a}`, `\diff2{f}{a}` |
| subscript glyphs `x₁`, `εₘₐ꜀ₕ` | `x_{1}`, `\varepsilon_{mach}` |
| Greek, ≤, ±, →, ∈ … | `\alpha`, `\le`, `\pm`, `\to`, `\in` … (the same names the LaTeX reader accepts) |
| `x̄ ȳ x̂ ŷ p̂` | `\bar{x} \bar{y} \hat{x} \hat{y} \hat{p}` |
| palette symbols with no Unicode character (`\i;`, `\s10;`, `\negB;` …) | `\casio{i}`, `\casio{s10}` … The preamble draws each one (`\mathrm{i}`, `\mathrm{E}`, a boxed B …) |
| `sin`, `cos`, `ln`, … followed by an argument | `\sin x`, `\cos(2x)` |
| words inside a formula | `\text{…}` |
| accented and Cyrillic letters | UTF-8, as they are |
| anything else (only byte `E7` so far) | `\raw{E7}` with warning **W009** |

## How text and math are told apart

The file format does not record which characters were math, so `eact` guesses. Each line is
split at spaces into words, and the rules are applied in this order:

1. A word containing a 2-D structure, a math glyph (Greek, subscripts, ≤, ∞ …) or an operator
   (`= + − < > × ÷ ± ≤ ≠ ∈ …`) is math.
2. A lone lower-case consonant (`x`, `n`, `f`) is math. Vowels are not, because `a`, `e`, `o`
   and `y` are Spanish words. Neither are capitals.
3. When an operator sits at the space between two words, a formula takes in the neighbouring
   word unless that word is a real word (two letters in a row). `f(x) = x` becomes one formula;
   in `el error es = 5`, the word `es` stays text.
4. A function name joins the formula after it: `sin x` → `$\sin x$`. The Spanish word in
   `sin embargo` stays text.
5. Trailing `.,;:!?`, unbalanced parentheses, and a leading `¿¡` are moved out of the
   formula, so the result is `$c=\frac{a+b}{2}$.`

The rules only affect how the LaTeX looks. They never affect the round trip: text and math
read back to the same bytes either way.

## What does not come back exactly

These differences only appear for files that were not made from LaTeX (for example EactMaker
or calculator files). After one pass through LaTeX the output is stable: a second
`dump --as latex` / `build` cycle changes nothing.

| In the eActivity | After `dump --as latex` + `build` | Why |
|---|---|---|
| spaces around an operator inside a formula (`x = 1`) | `x=1` | LaTeX math ignores spaces |
| trailing spaces, leading spaces, two spaces in a row | dropped / one space | LaTeX ignores them |
| two or more blank lines in a row; a blank line at the start or end | one / none | `\medskip` adds one blank line |
| no blank line before a `==Section==` line | a blank line is added | `\section` always adds one |
| superscript glyphs `x²`, `⁺`, `⁻` | the power template `x^{2}` | `^{2}` is what LaTeX means by it |
| ASCII `-` inside a formula | minus sign `−` (0x99) | `-` in LaTeX math is a minus |
| `sinx` with no space, inside a formula (`y=sinx`) | `sin x` | `\sin x` reads back with a space |

## Compiling the output

* **pdflatex:** works for Latin text, accents and all the math above. A few exotic glyphs (`※`,
  `【`, `☒`, capital Greek letters that look like Latin ones such as `Α`) are written as Unicode in
  `\text{…}`. pdflatex rejects them; use `xelatex` or `lualatex` with a Unicode font. Cyrillic
  text makes the preamble load the `T2A` font encoding.
* `\casio{name}` with a name the preamble does not know prints the name in typewriter type.
* `\raw{…}` prints its bytes as `[E7]`.

No TeX installation was available while this was written, so compiling the output with a real
TeX engine has not been tested yet. Round-tripping through `eact` is fully tested.
