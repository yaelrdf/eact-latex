# Diagnostics

Every problem `eact` finds has a **stable code**. Scripts and AI agents should match on the
code, not on the message text.

| Severity | Effect |
|---|---|
| `error` (E…) | the output would be wrong. `eact build` writes nothing and exits **2** (`--force` writes anyway) |
| `warning` (W…) | a fallback was used, so the output differs from the source. Exit 0, or **1** with `--strict` |
| `info` (I…) | worth knowing; nothing was changed |

Each diagnostic carries `file`, `line`, `col` (1-based; `0` means "whole document"),
`message` and an optional `hint`.

## Errors

| Code | Meaning | Typical cause | Fix |
|---|---|---|---|
| E001 | unknown command | `\fracc`, a custom macro, an unsupported package command | use a supported command (`eact symbols --latex`), or expand the macro |
| E002 | character has no CASIO glyph | emoji, CJK, rare symbols (`ℏ`, `ℵ`) | remove it or pick a supported symbol (`eact symbols`) |
| E003 | missing argument | `\frac{1}`, `x^` at the end, `\note{t}` | supply every `{…}` argument |
| E004 | unbalanced braces/delimiters | unclosed `{`, `$`, `\(`, `\begin{…}` without `\end{…}`, a stray `}` | close it |
| E006 | invalid `\raw{…}` | non-hex text in `\raw` | write hex byte pairs: `\raw{7F 50}` |
| E007 | structure not allowed here | a math command in text mode (`\frac` outside `$…$`), a nested `\note`, a line break inside an `.eam` argument | wrap math in `$…$`; un-nest |
| E008 | empty document | everything is commented out, or content sits outside `\begin{document}` | add content |
| E009 | invalid title | (reserved) | |

## Warnings

| Code | Meaning | Example | What `eact` does |
|---|---|---|---|
| W001 | character replaced by a look-alike | `ǵ`, `\hbar`, `\langle`, `\circ` | writes the closest glyph (`g`, `h`, `<`, `○`) |
| W002 | subscript without a glyph | `x_{\alpha}`, `x_{i,j}` | writes the characters that have subscript glyphs as subscripts and the rest inline after `_` |
| W003 | LaTeX construct approximated | `\lim_{x\to0}`, `\vec v`, `\prod_{i=1}^n`, `cases`, `\binom`, `\sqrt[n]` with a letter index, a table, a footnote, `\int` without `dx` | writes the closest calculator form (see LATEX_SUBSET.md) |
| W004 | formatting ignored | `\textbf`, `\emph`, `\mathbb` | keeps the text and drops the style (reported once per command) |
| W005 | command or environment ignored | `\cite`, `\ref`, figures, `tikzpicture`, `\newcommand`, unknown environments | drops it, writes `?`, or keeps the content under a label |
| W006 | title adjusted | a title longer than 8 characters or with accents | uppercases, transliterates, and cuts to 8 characters |
| W007 | tab replaced by space | a tab in `.eam` | |
| W008 | integration variable is not x | `\int_0^1 t\,dt` | the calculator always shows `dx`. Rename the variable to keep the meaning |
| W009 | no LaTeX form; written as `\raw` | `eact dump --as latex` meets a glyph with neither a Unicode character nor a palette name (byte `E7`) | writes `\raw{E7}`, which eact reads back exactly; LaTeX prints `[E7]` |

## Info

| Code | Meaning |
|---|---|
| I001 | one 2-D formula is wider than the screen (21 columns in linear form); the calculator will scroll it horizontally |
| I002 | the document has notes and the target is G1E, which has not been verified on hardware |

## JSON shape

`eact check --json` and `eact build --json` print:

```json
{
  "ok": false,
  "errors": 1,
  "warnings": 0,
  "diagnostics": [
    {"code": "E001", "message": "unknown math command \\fracc", "line": 3, "col": 7,
     "hint": "did you mean \\frac?", "file": "ex.tex", "severity": "error"}
  ],
  "stats": {"title": "EX1", "lines": 12, "notes": 0, "note_lines": 0, "bytes": 640},
  "output": "EX1.g2e",
  "preview": "…only with --preview…"
}
```

`eact dump FILE.g2e --as latex` prints its W009 warnings to stderr; `--as json` puts them in
`latex_diagnostics`.

When the input cannot be read at all (missing file, corrupt `.g2e`), the output is
`{"ok": false, "fatal": "<reason>"}` and the exit code is 2.
