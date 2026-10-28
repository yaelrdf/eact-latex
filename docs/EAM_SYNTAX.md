# EactMaker markup (`.eam`)

This is the markup used by the [EactMaker](https://tools.planet-casio.com/EactMaker/) web editor.
`eact` reads and writes it so that you can:

* open EactMaker projects (`eact build project.eam`) and get byte-identical output;
* see the exact low-level form of a LaTeX conversion (`eact check --eam file.tex`);
* decode any `.g2e` back to editable text (`eact dump file.g2e`). For LaTeX instead, use
  `eact dump file.g2e --as latex` ([LATEX_OUTPUT.md](LATEX_OUTPUT.md)).

The markup maps **1:1 to bytes**, which makes it a precise target for tools and agents.

## File format

A `.eam` project file is UTF-8: `FORMAT ␞ TITLE ␞ PASSWORD ␞ CONTENT`, where `␞` is the
byte `0x1E`. For example: `g2e␞TEST␞␞==Hello==\r\n…`. A file without `0x1E` separators is
treated as bare content. Lines end with CRLF in files EactMaker saves; `eact` accepts LF too.

## Content

* Each line of content becomes one calculator line. Empty lines are kept.
* Any character in [CHARMAP.md](CHARMAP.md) can be typed directly (`α`, `≤`, `é`).
* Palette symbols with no Unicode equivalent are written `\name;`, for example `\i;` `\xbar;` `\s10;`.

| Markup | Meaning |
|---|---|
| `\frac{a}{b}` | fraction |
| `\sqrt{a}` | square root |
| `^{a}` or `^c` | power applied to what precedes it |
| `_{ab}` or `_c` | subscript glyphs (each character; A–Z a–z 0–9 + − only) |
| `\sum{end}{var}{start}{expr}` | Σ(expr, var, start, end) |
| `\int{upper}{lower}{f}` | ∫ from lower to upper of f dx. **Watch the order**: see FORMAT.md §4.2 |
| `\log{base}{x}` | log with base |
| `\abs{a}` | absolute value |
| `\diff{f}{a}`, `\diff2{f}{a}` | d/dx f and d²/dx² f, evaluated at x = a |
| `\mat{a&b}{c&d}` | matrix: one `{}` per row, cells separated by `&` |
| `\note{title}{content}` | NOTES strip. Must start a line; the content may span lines |
| `\\ \{ \} \_ \^ \&` | literal characters |
| `{text}` | literal braces (EactMaker keeps them) |
| `\raw{7F 50}` | **eact only**: raw bytes |

## Differences from EactMaker

| Input | EactMaker | eact |
|---|---|---|
| unknown `\cmd` | written literally | error E001 (still written literally, so a forced build matches) |
| emoji or other character with no glyph | dropped silently | error E002 |
| tab | dropped silently | space + W007 |
| `_c` where c has no subscript glyph | undefined | `_` + c inline, W002 |
| text after `\note{…}{…}` on the same line | dropped | kept as its own line |
