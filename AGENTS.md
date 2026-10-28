# AGENTS.md: using eact from an AI agent

`eact` converts LaTeX into CASIO fx-9750GIII eActivity files (`.g2e`). It is designed to be driven
in a loop by an agent: every problem is reported as a structured diagnostic with a stable code,
a position, and a hint.

## Setup

No dependencies; Python ≥ 3.10. From a checkout:

```bash
./eact --help                 # wrapper script, no install needed
pip install -e .              # or install the `eact` command
```

## The loop

1. Write LaTeX into `file.tex`. A fragment is fine; it does not need `\documentclass`.
2. Run `eact check file.tex --title NAME --json`.
3. If `ok` is false, fix each diagnostic with `severity == "error"` at its `line`/`col`, using its `hint`.
   Re-check.
4. Review the warnings (`W…`). Each one means the output differs from the LaTeX. Accept them, or
   rewrite the source (see the table below). Use `--strict` to make warnings fail.
5. Run `eact build file.tex --title NAME -o NAME.g2e --json`.
6. Optional: `eact check file.tex --preview` shows an approximate 21-column screen, and
   `eact check file.tex --eam` shows the exact low-level form.

Exit codes: `0` ok; `1` warnings with `--strict`; `2` errors, bad input or bad usage.
`build` writes **nothing** when there are errors (unless `--force`).

## Fixing common diagnostics

| Code | Do this |
|---|---|
| E001 unknown command | use a command from `eact symbols --latex` (JSON: `eact symbols --json` → `latex`). Expand custom macros by hand |
| E002 no glyph | remove the character, or choose one listed by `eact symbols` |
| E003 / E004 | add the missing argument, brace, `$` or `\end{…}` |
| E007 | put math commands inside `$…$` |
| W002 subscript | subscripts only exist for A–Z, a–z, 0–9, +, −. Write `x_{a}` rather than `x_{\alpha}`, or accept the inline form |
| W003 lim/prod/cases | acceptable in most notes. For exact layout, use the native templates: `\frac \sqrt ^ _ \sum_{k=a}^{b} \int_a^b … dx \log_b \|x\| pmatrix` |
| W008 | rename the integration variable to `x` |
| I001 | the formula is wider than the screen; split it if readability matters |

## Writing LaTeX that converts well

* The screen is 21 characters × 8 rows. Keep formulas short, and give each one its own display
  line (`\[ … \]` or `align*` rows).
* A paragraph becomes one wrapped line, and a blank line starts a new one.
  `\section` produces `==Title==`.
* Prefer `\sum_{k=0}^{n}` with **both** limits and `k=start` form, and `\int_a^b … \,dx` with
  `dx` written. Those become real calculator templates.
* Use `\note{Title}{…}` for hints or solutions that should start collapsed.
* The title is at most 8 characters, `A–Z 0–9`; pass it with `--title`.

## Python API

```python
from eact import convert
doc, rep = convert.load_text(latex_source, "latex", file="ex.tex", title="EX1")
for d in rep.items:
    print(d.code, d.line, d.col, d.message, d.hint)
if not rep.errors:
    open("EX1.g2e", "wb").write(convert.build(doc))
```

## Reference

* [docs/LATEX_SUBSET.md](docs/LATEX_SUBSET.md): every supported construct
* [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md): every code
* [docs/CHARMAP.md](docs/CHARMAP.md): every calculator character
* [docs/FORMAT.md](docs/FORMAT.md): the binary format

## Working on the code

* Tests: `python3 -m unittest discover -s tests`. All of them must pass. The golden tests compare
  against real EactMaker output byte-for-byte.
* After changing `tools/extract_charmap.py`, run it, then run `tools/gen_charmap_doc.py`.
* Diagnostic codes are an API: never renumber them. Add new ones to `diagnostics.CODES`
  **and** `docs/DIAGNOSTICS.md`.
