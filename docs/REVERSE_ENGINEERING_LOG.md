# Reverse-engineering log

This log records how the format in [FORMAT.md](FORMAT.md) was worked out, so that every claim can be
traced to evidence and reproduced. Dates are 2026-10-27.

## Starting material

* `tests/fixtures/TEST.g2e` was produced by EactMaker from `tests/fixtures/TEST.g2e.eam`.
  The `.eam` project file was written by hand by clicking every palette button.
* `docs/img/palettes/*.png` are screenshots of the EactMaker palettes.
* `docs/img/calculator/*.png` are screen captures from a real **fx-9750GIII** showing `TEST.g2e`.
  The original 1-bit BMPs were converted with `tools/bmp2png.py`.
* Simon Lothar's notes:
  <https://media.taricorp.net/prizm/simon_chm/fx_legacy_eactivityformat.htm>.
* EactMaker itself: <https://tools.planet-casio.com/EactMaker/>. The conversion runs on the
  server (`system/converter.php`, PHP), so its source is **not** available. The client file
  `formats/g2e.js` only describes the editor palette: symbol order, names such as `\i;`, and
  insert actions. No EactMaker code is copied into this project; we only reuse the public
  command names so that `.eam` files stay compatible.

## Step 1: the container

* `od -t x1` of `TEST.g2e` showed the inverted `"USBPower"` magic (`AA AC BD AF…`), which is the
  standard CASIO header. Inverting byte 8 gives `0x49`, the eActivity type in Lothar's notes.
* Every field in Lothar's table matched `TEST.g2e`: file size `0x780` at `0x20`, `LS=0x38`,
  `@EACT`, `EACT1`, `length1 = 0x780 − 0x40 − 0x38 = 0x708`,
  `length2 = 0x780 − 0x54 − 0x38 = 0x6F4`, and `D4 00 00 66`.
* Line count `0x31 = 49`. Offsets are relative to `0x8C`. For example, the first entry
  `07 0000CC` points to `0x158`, which is `"======TEST    ======="`.
* **Result:** `container.build(container.parse(x)) == x` for every fixture (`test_parse_build_is_identity`).

## Step 2: the character set

* The `.eam` file is plain UTF-8: `g2e␞TEST␞␞<markup>`. Its symbol lines line up
  token-for-token with the `.g2e` lines. For example, `Α Β Γ` maps to `E540 E541 E542`.
* To make this exact and complete, we sent one more request to EactMaker. Every palette token
  from `g2e.js`, plus every printable ASCII character and every escape, went on its own line,
  wrapped as `Q<token>Q` so the boundaries are unambiguous
  (`tests/fixtures/eactmaker/palette_probe.*`).
* `tools/extract_charmap.py` zips the tokens with the output lines and writes
  `src/eact/data/charmap.json`, which has 546 symbols. `test_charmap_is_up_to_date` checks that
  the committed file matches the fixture.
* Surprises the probe revealed:
  * ASCII `+` becomes `89`, CASIO's plus sign, everywhere.
  * ASCII `~` becomes `E6B5`.
  * A raw `^` superscripts the next character, and a raw `_` subscripts it.
  * A tab is dropped silently. `eact` turns it into a space and reports `W007`.
  * An unknown `\cmd` is written literally, and an emoji is dropped silently. `eact` reports
    both as errors (`E001`, `E002`).
  * The `.eam` in `TEST` contains Θ twice and leaves out ⊇ and ö. The decoder reproduces this
    faithfully, which confirms that the alignment is exact.

## Step 3: 2-D structures

* The "Common math expressions" line of `TEST.g2e` contains every structure once. The marker
  bytes `1A/1B/1C/1D/1E` were identified by lining up each structure with its markup.
* Single-feature probes were sent to EactMaker. Each is stored as `NAME.txt` (input) and
  `NAME.g2e` (output) in `tests/fixtures/eactmaker/`:

  | Probe | Finding |
  |---|---|
  | `nest` | structures nest; arguments can contain structures |
  | `intnest` | the argument order of Σ, ∫, log, diff and matrix |
  | `mat3` | 2×3 matrix: cells separated by `1C`, rows wrapped in `A4…B4` |
  | `pow2` | `^{a+b}` and `^2` use the same `A8 1A … 1B` form |
  | `sub2` | `_{ab}` becomes two subscript glyphs; `_1` and `_{1}` become `E5D1` |
  | `textmath` | text and structures share one `0x81` line |
  | `esc` | `\\ \{ \} \_ \^ \&` and literal `{a}` |

* The calculator screenshot `Common_expressions4.png` shows `\int{a}{b}{c}` displayed with
  **b** as the lower limit. That fixes the meaning of the integral's arguments (FORMAT.md §4.2).

## Step 4: notes

* `TEST.g2e` contains one note. The probes `note2` (multi-line content containing a fraction)
  and `twonotes` (two notes) let us separate the constant bytes from the variable ones.
* The size field after `AB CD EF 89` changes by exactly the content growth:
  `0x7C` for "one", `0x94` for two lines. It counts every byte to the end of the blob.
* `len1` and `len2` inside `@RUNMAT/TEXT1` follow the same rules as the main file's
  `length1` and `length2`.
* **Result:** notes are rebuilt byte-identically, which `test_eam_to_g2e` checks.

## Step 5: format options

* `bold` and `pw` (password) probes: identical to the baseline output. The options have no effect on G2E.
* `g1e_x.g1e`: differs only in the version bytes at `0x28–0x2F` (`test_g1e_differs_only_in_version`).
* An empty title makes EactMaker return an empty response. `eact` falls back to `NOTES`.
* The title is padded to 8 characters inside `======…=======`.

## Reproducing the probes

```bash
curl -s -o out.g2e -X POST https://tools.planet-casio.com/EactMaker/system/converter.php \
  --data-urlencode titre=A --data-urlencode format=g2e --data-urlencode font=0 \
  --data-urlencode additional= --data-urlencode texte@input.txt
```

Be gentle with the server. Every probe this project needs is already in `tests/fixtures/`.
