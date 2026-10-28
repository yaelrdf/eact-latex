# The G2E / G1E eActivity file format

This is the byte-level description that `eact` implements. Every statement here
comes from one of three sources:
- [Simon Lothar's eActivity notes](https://media.taricorp.net/prizm/simon_chm/fx_legacy_eactivityformat.htm);
- files produced by EactMaker, kept in `tests/fixtures/`;
- comparing EactMaker outputs that differ in a single feature.

Statements marked **(verified)** are checked by the test suite against those files.
Statements marked **(assumed)** are not verified.
[REVERSE_ENGINEERING_LOG.md](REVERSE_ENGINEERING_LOG.md) explains how each fact was found.

All integers are **big-endian**. Offsets are hexadecimal.

## 1. File overview

```
+-----------------------------+ 0x00
| StandardHeader (0x20 bytes) |   CASIO container header, bit-inverted
+-----------------------------+ 0x20
| eActivity header            |   size, setup-area length, version
| setup area (template)       |   calculator settings saved with the file
+-----------------------------+ 0x30+LS
| "@EACT" block header        |
| "EACT1" block header        |
| line count + line directory |
+-----------------------------+
| lines (4-byte aligned)      |   text lines, heading, note strips
+-----------------------------+ EOF
```

`LS` (the length of the setup area) is `0x38` in every file we have seen, so the fixed
offsets below are given both symbolically and for `LS = 0x38`.

## 2. StandardHeader (0x00–0x1F) (verified)

This is the same 32-byte header that every CASIO fx-9860G-family file uses (`.g1m`, `.g2m`, `.g1e`…).
Bytes 0x00–0x14 are stored **bit-inverted** (`byte ^ 0xFF`). Bytes 0x15–0x1F are plain zeros.

| Offset | Size | Plain value | Stored as | Meaning |
|---|---|---|---|---|
| 00 | 8 | `"USBPower"` | `AA AC BD AF 90 88 9A 8D` | magic |
| 08 | 1 | `0x49` | `B6` | file type: eActivity |
| 09 | 5 | `00 10 00 10 00` | `FF EF FF EF FF` | magic |
| 0E | 1 | `(size & 0xFF) + 0x41` | inverted | control byte 1 |
| 0F | 1 | `0x01` | `FE` | |
| 10 | 4 | file size | inverted | total file size in bytes |
| 14 | 1 | `(size & 0xFF) + 0xB8` | inverted | control byte 2 |
| 15 | 11 | zeros | zeros | (item count etc.; unused here) |

Example: `TEST.g2e` is 1920 = `0x780` bytes. Control byte 1 is `0x80 + 0x41 = 0xC1`, stored as `0x3E`.
Control byte 2 is `0x80 + 0xB8 = 0x138 → 0x38`, stored as `0xC7`.
There is **no checksum**; the two control bytes are the only integrity check.

## 3. eActivity header and line directory (verified)

| Offset | LS=0x38 | Size | Value | Meaning |
|---|---|---|---|---|
| 20 | 20 | 4 | file size | same as in the header, not inverted |
| 24 | 24 | 4 | `LS` | setup-area length (`0x38`) |
| 28 | 28 | 8 | version | G2E: `00 01 02 00 02 02 02 01`; G1E: `00 01 01 00 50 61 63 6B` (`"Pack"`) |
| 30 | 30 | LS−0x10 | setup area | see below |
| 20+LS | 58 | 0x10 | zeros | |
| 30+LS | 68 | 8 | `"@EACT\0\0\0"` | |
| 38+LS | 70 | 4 | `1` | |
| 3C+LS | 74 | 4 | `size − 0x40 − LS` | bytes from `"EACT1"` to EOF |
| 40+LS | 78 | 8 | `"EACT1\0\0\0"` | |
| 48+LS | 80 | 4 | `0x14` | |
| 4C+LS | 84 | 4 | `size − 0x54 − LS` | bytes from the line count to EOF |
| 50+LS | 88 | 4 | `D4 00 00 66` | constant (meaning unknown) |
| 54+LS | 8C | 4 | `LC` | number of lines, including the heading |
| 58+LS | 90 | 4·LC | line directory | see below |
| … | | 4 | zeros | |
| … | | … | lines | |

**Line directory entry** (4 bytes): `[type: 1 byte][offset: 3 bytes]`. The offset is relative to the line-count field (`0x54+LS`, so `0x8C`).

| Type | Meaning |
|---|---|
| `0x07` | heading. EactMaker always writes line 0 as `"======" + title padded to 8 + "======="` |
| `0x81` | text line (plain text **and** 2-D math; see §5) |
| `0x82` | text line that contains `0x00` bytes. Lothar documents it; EactMaker never writes it. `eact` uses it only for `\raw{00}` |
| `0x06` | strip. EactMaker uses it for `\note` (§6) |

**Lines** follow the directory in order. Each line is followed by at least one `0x00`
byte and then padded with zeros to a multiple of 4. An empty line is therefore `00 00 00 00`.
Lothar notes that the calculator itself fills the padding with random bytes; readers must
use the directory offsets rather than searching for the terminator.

### Setup area (assumed: copied as a template)

This is a snapshot of the calculator's SETUP menu. Lothar explains that it is a bit
directory followed by the values that are not zero. `eact` copies EactMaker's bytes verbatim:

```
00 00 00 00 10 00 14 2A 3F 02 C0 00 00 00 28 30
00 00 00 00 01 02 01 01 01 03 01 01 01 01 01 01
01 01 01 01 01 01 00 00
```

EactMaker's "font" (regular/bold) and "password" options **do not change any byte** of a G2E
(verified with `bold`/`pw` probes). G3E output from EactMaker reuses the G2E setup data with a
`0x2C` directory size, which looks wrong, so `eact` does not offer G3E.

## 4. Characters and 2-D math inside a line

### 4.1 Characters (verified)

Text uses CASIO's own multi-byte character set, which the community calls FONTCHARACTER.
Most bytes are one character. A **lead byte**, `7F`, `E5`, `E6` or `E7` (and `F7`/`F9` on the
calculator), starts a 2-byte character. Notable mappings:

| Character | Bytes | Notes |
|---|---|---|
| ASCII `!`…`~` | same | except `+` and `~` |
| `+` | `89` | EactMaker writes CASIO's "plus" for every `+`, even in plain text |
| `~` | `E6 B5` | |
| `−` (U+2212) | `99` | CASIO subtraction. ASCII `-` stays `2D` |
| `×` `÷` | `A9` `B9` | |
| `≤ ≠ ≥ ⇒` | `10 11 12 13` | control-range bytes are glyphs here |
| Greek | `E540–E558`, `E640–E658` | |
| accented Latin | `E501–E535`, `E601–E635` | covers Spanish: á é í ó ú ñ ü ¿ ¡ |
| Cyrillic | `E560–E582`, `E660–E682` | |
| subscript A–Z, a–z | `E741–E75A`, `E761–E77A` | |
| subscript 0–9, ₊, ₋ | `E5D0–E5D9`, `E5DB`, `E5DC` | |
| superscript ⁰–⁹ | `E5C0–E5C9` | |

The complete table of 546 symbols is in [CHARMAP.md](CHARMAP.md).

### 4.2 Structures (verified)

2-D math is stored inline, inside an ordinary `0x81` line, using five marker bytes:

| Byte | Role |
|---|---|
| `1A` | open argument |
| `1B` | close argument |
| `1C` | separate arguments (function-call style) |
| `1D` | begin a 2-D block |
| `1E` | end a 2-D block |

| Structure | Encoding | EactMaker markup |
|---|---|---|
| fraction | `BB 1D 1A num 1B 1A den 1B 1E` | `\frac{num}{den}` |
| square root | `86 1D 1A x 1B 1E` | `\sqrt{x}` |
| absolute value | `97 1D 1A x 1B 1E` | `\abs{x}` |
| power | `A8 1A exp 1B` (follows the base) | `^{exp}` or `^c` |
| Σ | `7F 29 1A expr 1C var 1C start 1C end 1B` | `\sum{end}{var}{start}{expr}` |
| log with base | `7F 85 1A base 1C x 1B` | `\log{base}{x}` |
| d/dx at a point | `7F 26 1A f 1C a 1B` | `\diff{f}{a}` |
| d²/dx² at a point | `7F 27 1A f 1C a 1B` | `\diff2{f}{a}` |
| definite integral | `8D 1A f 1C lower 1C upper 1B` | `\int{upper}{lower}{f}` |
| matrix | `7F 5D A4 (A4 cell (1C cell)* B4)* B4` | `\mat{a&b}{c&d}` |

Structures nest freely. For example, `\frac{\sqrt{a}}{b^{2}}` becomes
`BB 1D 1A 86 1D 1A 61 1B 1E 1B 1A 62 A8 1A 32 1B 1B 1E`.

**About EactMaker's `\int`.** EactMaker's button reads "∫ from a to b of c", but
`\int{a}{b}{c}` is stored as `∫(c, b, a)`. On the calculator it displays as ∫ from **b** to **a**
(see `docs/img/calculator/Common_expressions4.png`). The calculator's order is
`∫(f, lower, upper)`, so the first `.eam` argument is the **upper** limit. `eact`'s LaTeX
front-end uses `\int_{lower}^{upper}` and places the limits correctly.

The bare tokens (`BB`, `86`, `97`, `8D`, `7F 29`…) are also ordinary characters when they are
not followed by their markers. For example, `BB` alone is the fraction-corner glyph `⌟` and
`86` alone is `√`. The decoder falls back to a character whenever a structure is malformed.

## 5. Line wrapping (observed)

A 131-character text line is stored as a single line (fixture `long`); the calculator
wraps it on screen. Lines that contain 2-D structures are rendered two-dimensionally. A
structure wider than the screen (21 columns of 6 px on the 128×64 display) scrolls
horizontally. `eact` reports this with `I001`.

## 6. Note strips (`\note`, type 0x06) (verified)

A note is a collapsible strip shown as `title ……… NOTES`. The strip's entry in the main
directory points to this blob:

```
"@EACT\0\0\0"                    8
00 00 00 00                      4
00 0A 00 00                      4   strip kind (0x0A = NOTES)  (assumed)
title, NUL-terminated, padded    4n
AB CD EF 89                      4   magic
inner size                       4   = bytes from here (after this field) to the end of the blob
00 00 00 38                      4   LS
00 01 02 00 02 00 02 00          8   version (different from the main file!)
note setup area                  0x28 (template, see encoder.NOTE_SETUP)
zeros                            0x10
"@RUNMAT\0"                      8
00 00 00 01                      4
len1                             4   = bytes from "TEXT1" to the last line (excl. trailing 4 zeros)
"TEXT1\0\0\0"                    8
00 00 00 14                      4
len2                             4   = bytes from the line count to the last line
D4 00 00 03                      4   constant
line count                       4
line directory                   4·n (offsets relative to the line count, like the main file)
00 00 00 00                      4
lines                            (NUL-terminated, 4-aligned)
00 00 00 00                      4   trailer
```

The content lines use the same character and structure encoding as the main file.

## 7. Open questions

| Question | Status | How to settle it |
|---|---|---|
| Meaning of the individual setup-area bytes | template | change one SETUP setting on the calculator, save an eActivity, and diff |
| `D4 00 00 66` / `D4 00 00 03` | constant | compare with files saved by the calculator |
| Other strip types (graph, table, run-matrix) | unsupported | save strips on the calculator and dump them with `eact dump --as structure` |
| Notes in G1E | `I002` | test on an fx-9860G (the fx-9750GIII reads G2E) |
| Maximum file or line size accepted by the calculator | unknown | build large files and load them |
| Line type `0x82` written by `eact` | untested on hardware | only `\raw{..00..}` produces it |
