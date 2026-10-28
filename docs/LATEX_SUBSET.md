# Supported LaTeX

`eact` reads the LaTeX found in exercise sheets and class notes. It does **not** run TeX: macros are
not expanded and packages are not loaded. Every input either has a mapping below, or produces a
diagnostic ([DIAGNOSTICS.md](DIAGNOSTICS.md)). Nothing is dropped silently.

Run `eact symbols --latex` for the full live list. `eact check --eam file.tex` shows exactly what
your file turns into.

## Document structure

| LaTeX | Result on the calculator |
|---|---|
| `\documentclass`, `\usepackage`, other preamble lines | ignored. Only `\begin{document}…\end{document}` is converted; with no `document` environment the whole input is converted |
| `\title{…}` | default eActivity title (8 characters, W006 if shortened) |
| `\maketitle` | the full title as the first line |
| `\section{X}` / `\chapter{X}` | blank line, then `==X==` |
| `\subsection{X}` | blank line, then `=X=` |
| `\subsubsection{X}`, `\paragraph{X}` | blank line, then `X:` |
| a paragraph (text up to a blank line) | **one** calculator line; the calculator wraps it |
| `\\`, `\newline`, `\par` | new line |
| `\medskip`, `\bigskip`, `\vspace{…}` | one blank line |
| `itemize` | `- item` lines (indented one space per nesting level) |
| `enumerate` | `1) item`; nested lists use `a)` |
| `description`, `\item[label]` | `label: item` |
| `tabular` | one line per row, cells joined by ` \| ` (W003) |
| `center`, `flushleft`, `quote`, `minipage`, … | transparent |
| `verbatim`, `lstlisting` | lines copied as text |
| `figure`, `tikzpicture`, `\includegraphics` | dropped (W005) |
| `theorem`, `ejercicio`, any unknown environment | `Name: content` (W005, once per environment name) |
| `\footnote{x}` | ` (x)` inline (W003) |
| `\textbf`, `\emph`, `\textit`, `\underline` | plain text (W004) |
| `\label`, `\vspace`, `\noindent`, `\centering`, sizes | ignored |
| `\ref`, `\cite` | `?` (W005) |
| `%` comments | removed |

### Text characters

* UTF-8 input is supported directly: `á é í ó ú ñ ü ¿ ¡ ç`, Greek and Cyrillic.
* Classic accent macros: `\'a \`a \^a \"u \~n \c{c} \v{c} \H{o} \k{a} \r{a} \u{a} \=a \.z`.
* `\% \& \$ \# \_ \{ \}`, `\textasciicircum \textasciigrave \textbackslash`, `\ss \o \ae \oe \l \aa`, `\ldots`, `\S`, `\copyright`, `\euro`, `\textdegree`.
* ``` `` ``` → `“`, `''` → `”`, `` ` `` → `‘`, `--` and `---` → `-`, `~` → space.
* Characters with no CASIO glyph:
  * If an accent-free version exists, it is used instead (`ǵ` → `g`, W001).
  * Otherwise the character is an error (E002).

## Math

`$…$` and `\(…\)` are inline. `\[…\]`, `$$…$$`, `equation`, `align`, `gather`, `multline`
(with or without `*`) and `eqnarray` are display math. Each `\\` row becomes its own line, and
`&` alignment points are dropped. An `aligned`/`gathered`/`split` block that fills a whole
display is split into rows as well.

### Native CASIO templates (exact)

| LaTeX | Calculator template |
|---|---|
| `\frac{a}{b}`, `\dfrac`, `\tfrac`, `\cfrac`, `\frac12` | fraction |
| `\sqrt{x}` | square root |
| `\sqrt[3]{x}` (any digits) | superscript index + √ |
| `x^{2}`, `x^2`, `e^{-x}` | power |
| `x_1`, `x_{n+1}`, `a_{ij}` | subscript glyphs (A–Z, a–z, 0–9, +, − only) |
| `\sum_{k=0}^{n} expr` | Σ(expr, k, 0, n). The summand runs to the next `+ − = < > , ;` or relation at the same parenthesis level |
| `\int_a^b f(x)\,dx` | definite integral. The integrand runs up to `dx` |
| `\log_b x`, `\log_{b}(x+1)` | log with base |
| `\|x\|`, `\left\| x \right\|`, `\lvert…\rvert`, `\abs{x}` | absolute value |
| `pmatrix`, `bmatrix`, `Bmatrix`, `matrix`, `smallmatrix`, `array` | matrix |
| `\diff{f}{a}`, `\diff2{f}{a}` (eact extensions) | d/dx f, or d²/dx² f, evaluated at x=a |

### Symbols

* Greek letters: `\alpha … \omega`, `\Gamma … \Omega`, `\varepsilon \vartheta \varphi \varrho \varsigma \varpi`.
* Relations and operators: `\le \ge \ne \approx \equiv \cong \sim \propto \pm \mp \times \div \cdot`.
* Sets and logic: `\in \notin \ni \subset \subseteq \supset \supseteq \cup \cap \emptyset \exists \forall \neg \land \lor`.
* Arrows: `\to \rightarrow \leftarrow \uparrow \downarrow \Rightarrow \implies \Leftrightarrow \iff` and the diagonal arrows.
* Other: `\infty \partial \nabla \angle \perp \parallel \therefore \because \ldots \cdots \prime`,
  `\bullet \square \bigcirc \blacktriangleright \blacktriangleleft \blacktriangle \blacktriangledown \blacklozenge`,
  and `\% \{ \} \# \$ \&`.
* Primes and degrees: `f'(x)` → `f′(x)`, `f''(x)` → `f″(x)` (one glyph), and `90^\circ` → `90°`.
* Means and estimates: `\bar{x} \bar{y} \hat{x} \hat{y} \hat{p}` (also `\overline`/`\widehat`) map to the calculator's statistics glyphs.
* Function names: `\sin \cos \tan \ln \exp \det …` are written as text, as on the calculator.
  `\sin x` keeps a space; `\sin(x)` does not.
* Spacing: `\, \: \; \quad \qquad` become one space; `\!` and `\displaystyle` are ignored.
* Font commands: `\mathrm \mathbf \text{…} \operatorname{…}` keep their content.
  `\mathbb \mathcal` keep the letter (W004).

### Approximations (warning W003, W001 or W008)

| LaTeX | Written as |
|---|---|
| `\lim_{x\to a} f` (also `\max \min \sup \inf`) | `lim(x→a) f` |
| `\prod_{i=1}^{n}`, `\sum` without both limits | `Π`/`Σ` glyph, then subscript and power |
| `\int` without limits, `\iint`, `\oint` | `∫`/`∬`/`∮` glyph followed by the expression (exact for indefinite integrals) |
| `\int … dt` (a variable other than x) | integral template; the calculator shows `dx` (W008) |
| `\sqrt[n]{x}` with a letter index | `(x)^(1/n)` |
| `\binom{n}{k}` | `nCk` |
| `cases`, `vmatrix` | matrix |
| `\vec \dot \ddot \tilde \underbrace …` | the content without the accent |
| `\langle \rangle \lfloor \lceil \circ \ell \hbar …` | look-alikes (W001) |

### Not supported (error)

* Custom macros: `\newcommand` warns (W005), and each use of the macro is an E001.
* Commands not listed here: E001, with a "did you mean" hint.
* Characters outside the CASIO table: E002.

## eact extensions (work in LaTeX too)

| Command | Meaning |
|---|---|
| `\note{title}{content}` | a collapsible NOTES strip. The content may contain paragraphs, `\\` and math. Cannot be nested |
| `\abs{x}` | absolute value template |
| `\diff{f}{a}`, `\diff2{f}{a}` | derivative templates evaluated at x = a |
| `\casio{name}` | a palette symbol that has no Unicode character, by its EactMaker name without `\` and `;`: `\casio{i}` (imaginary unit), `\casio{s10}` (×10 exponent), `\casio{negB}`. The names are in [CHARMAP.md](CHARMAP.md) |
| `\raw{7F 50}` | insert raw calculator bytes (for glyphs with no LaTeX name; see [CHARMAP.md](CHARMAP.md)) |

`eact dump --as latex` writes these extensions, and its preamble defines them, so its output also
compiles with LaTeX. See [LATEX_OUTPUT.md](LATEX_OUTPUT.md).
