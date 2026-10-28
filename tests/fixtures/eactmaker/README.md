# EactMaker reference outputs

Every `NAME.txt` here was sent to the EactMaker converter
(`https://tools.planet-casio.com/EactMaker/system/converter.php`, format `g2e`,
font regular, empty password). The response bytes are stored as `NAME.g2e`.
`PAL` is the title of `palette_probe`; every other file used the title `A`.

These files are the ground truth for the golden tests in `tests/test_golden.py`
and for `tools/extract_charmap.py`.

| file | what it shows |
|---|---|
| `palette_probe.*` | one palette token per line, wrapped in `Q…Q`; the source of `charmap.json` |
| `out` | minimal file: one text line `x` |
| `twolines`, `blank` | line splitting on CRLF, empty lines |
| `nest` | structures nest freely (`\frac{\sqrt{a}}{b^{2}}`) |
| `textmath` | text and structures mix on one line; ASCII `+` becomes 0x89 |
| `sin` | function names are plain ASCII text |
| `esc` | escapes `\\ \{ \} \_ \^ \&`, literal braces, `_x` subscript |
| `note2`, `twonotes` | `\note` strips: multi-line content and several strips |
| `sub2` | `_{ab}` subscripts each char, `_{1}`/`_1` digits |
| `pow2` | `^{…}` and `^x` power structure |
| `intnest` | every structure with nested arguments |
| `mat3` | 2×3 matrix layout |
| `long` | a 131-char line is stored as-is (the calculator wraps it) |
| `g1e_x.g1e` | same as `out` in G1E format: only the version bytes differ |
