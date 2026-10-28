# eact-latex

**Open-source converter from LaTeX to CASIO eActivity files (`.g2e`)** for the fx-9750GIII
(and other fx-9860G-family calculators that read `.g2e`/`.g1e`).

It replaces the closed web tool [EactMaker](https://tools.planet-casio.com/EactMaker/):

* **LaTeX in.** Write notes and exercises in normal LaTeX: `$\frac{a}{b}$`, `\sum_{k=0}^{n}`,
  `\int_0^1 … dx`, matrices, Greek, Spanish accents.
* **Real calculator math.** Fractions, roots, powers, Σ, ∫, log and matrices become the
  calculator's own 2-D templates, not text.
* **Honest errors.** Anything that cannot be shown is reported with a stable code, the line and
  column, and a hint. Nothing is dropped silently. `--json` output makes it scriptable and usable
  by AI agents (see [AGENTS.md](AGENTS.md)).
* **Byte-exact.** Given the same markup, the output is byte-for-byte identical to EactMaker's;
  the test suite checks this.
* **And back.** `eact dump FILE.g2e --as latex` turns any eActivity, including EactMaker and
  calculator files, into a LaTeX document that compiles and that `eact build` turns back into the
  same file.
* **No dependencies.** Python ≥ 3.10, standard library only.

## Quick start

```bash
git clone <this repo> eact-latex && cd eact-latex
./eact build examples/ejercicio.tex --title BISECCIO --preview
```

Then copy `examples/BISECCIO.g2e` to the calculator: connect the USB cable, choose
*USB Flash* on the calculator, and copy the file onto the drive. Open it from the **e-ACT** menu.

To install the `eact` command:

```bash
pip install -e .
eact --help
```

## Example

```latex
\section{Bisección}
Sea $f(x) = x^3 - 2x - 5$ y $c = \frac{a+b}{2}$.
\[ |x_n - r| \le \frac{b-a}{2^{n}} \]
\begin{align*}
  S &= \sum_{k=0}^{n} \frac{1}{k!} \\
  I &= \int_0^1 x^2 \, dx
\end{align*}
\note{Tip}{Detente si $|b-a| < \varepsilon$.}
```

`eact check ex.tex --preview` prints the approximate screen. Structures are shown in linear form:

```
+---------------------+
|======EX      =======|
|==Bisección==        |
|Sea f(x)=x^3−2x−5 y c|
|=(a+b)/2.            |
||xₙ−r|≤(b−a)/(2^n)   |
|S=Σ(1/(k!),k,0,n)    |
|I=∫[0→1](x^2)dx      |
|▸ Tip           NOTES|
|│Detente si |b−a|<ε. |
+---------------------+
```

## Commands

| Command | What it does |
|---|---|
| `eact build IN.tex [-o OUT.g2e] [--title T] [--format g2e\|g1e]` | convert. Refuses to write when there are errors |
| `eact check IN.tex [--json] [--strict] [--preview] [--eam]` | report problems only |
| `eact dump FILE.g2e [--as eam\|latex\|preview\|json\|structure] [--fragment]` | decode an eActivity, including ones made by EactMaker or the calculator. `--as latex` writes a LaTeX document ([docs/LATEX_OUTPUT.md](docs/LATEX_OUTPUT.md)) |
| `eact symbols [--latex] [--json] [--category greek]` | list every supported character and command |

The input can be `.tex` (LaTeX), `.eam` (EactMaker project or markup), `.g2e`, or `-` (stdin).
Exit codes: `0` ok, `1` warnings under `--strict`, `2` errors.

## How it works

```
 .tex ──latex.py──┐                       ┌──encoder.py──────▶ .g2e
                  ├──▶  IR (ir.py)  ──────┼──latex_writer.py─▶ .tex
 .eam ──eam.py────┘        ▲              └──preview.py──────▶ text preview
                           └──decoder.py◀── .g2e
```

* `container.py`: the binary layout (header, line directory, alignment)
* `charmap.py` + `data/charmap.json`: the 546-symbol CASIO character table
* `encoder.py`/`decoder.py`: characters and 2-D structures ↔ bytes
* `latex.py`: the LaTeX front-end, a hand-written tokenizer and parser
* `latex_writer.py`: IR → LaTeX, the inverse of `latex.py`
* `eam.py`: the EactMaker markup front-end and writer
* `diagnostics.py`: diagnostic codes and the JSON report
* `convert.py`: the high-level Python API. `cli.py` is the command line

## Documentation

| Document | Contents |
|---|---|
| [docs/LATEX_SUBSET.md](docs/LATEX_SUBSET.md) | which LaTeX is supported and what each construct becomes |
| [docs/LATEX_OUTPUT.md](docs/LATEX_OUTPUT.md) | `.g2e` → LaTeX: what is written, and what does not come back exactly |
| [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md) | every error, warning and info code, and the JSON format |
| [docs/FORMAT.md](docs/FORMAT.md) | byte-level specification of `.g2e`/`.g1e` eActivity files |
| [docs/CHARMAP.md](docs/CHARMAP.md) | the calculator character table (generated) |
| [docs/EAM_SYNTAX.md](docs/EAM_SYNTAX.md) | EactMaker markup |
| [docs/REVERSE_ENGINEERING_LOG.md](docs/REVERSE_ENGINEERING_LOG.md) | how the format was worked out, step by step |
| [AGENTS.md](AGENTS.md) | how AI agents (and scripts) should drive `eact` |

## Status

| | |
|---|---|
| G2E container, characters, all EactMaker structures, notes | ✅ byte-identical to EactMaker (golden tests) |
| Round trip `.g2e → .eam → .g2e` | ✅ lossless on every fixture |
| Round trip `.g2e → .tex → .g2e` | ✅ byte-identical for files built from LaTeX and for most EactMaker fixtures; known differences are listed in LATEX_OUTPUT.md |
| LaTeX written by `dump --as latex`, compiled with a TeX engine | ⏳ not tested yet (no TeX installation was available) |
| LaTeX front-end | ✅ unit-tested; see LATEX_SUBSET.md for its limits |
| Files built by `eact` from LaTeX, checked on a real fx-9750GIII | ⏳ **pending**: the bytes use only constructs verified against EactMaker, but a hardware check is still to do |
| G1E | ⚠️ header verified; not tested on hardware |
| Other strip types (graph, table…) and G3E | ❌ not supported |

## Development

```bash
python3 -m unittest discover -s tests     # 51 tests, ~3 s
python3 tools/extract_charmap.py          # regenerate the charmap from the probe fixture
python3 tools/gen_charmap_doc.py          # regenerate docs/CHARMAP.md
python3 tools/bmp2png.py shot.bmp         # convert calculator screen captures
```

## Credits

* Simon Lothar's documentation of the fx-9860G eActivity format.
* EactMaker by Helder7 and Ziqumu (Casiopeia / Planète Casio): the reference outputs and the
  `\name;` command names. No EactMaker code is used.
* The Cahute project's documentation of CASIO text encodings.

## License

MIT. See [LICENSE](LICENSE).
