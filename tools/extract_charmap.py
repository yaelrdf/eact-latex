#!/usr/bin/env python3
"""Regenerate ``src/eact/data/charmap.json`` from the EactMaker palette probe.

The probe (``tests/fixtures/eactmaker/palette_probe.*``) is a G2E file produced
by EactMaker from an input that has exactly one palette token per line,
wrapped in ``Q…Q`` so that every line can be cut out unambiguously.  Zipping
the input tokens with the output lines gives the byte sequence of every
symbol EactMaker knows about.

Run from the repository root::

    python3 tools/extract_charmap.py            # writes src/eact/data/charmap.json
    python3 tools/extract_charmap.py --check    # fails if the committed file is stale
"""
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from eact import container  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "eactmaker"
OUT = ROOT / "src" / "eact" / "data" / "charmap.json"

# English descriptions (and a Unicode look-alike used by the preview) for the
# palette entries that EactMaker only exposes as ``\name;`` commands.
FUNC_INFO = {
    "i": ("imaginary unit i", "i"),
    "s10": ("small 10 (x10^ exponent marker)", "⏨"),
    "sE": ("small E (exponent marker, same as x10^)", "ᴇ"),
    "xbar": ("x bar (mean of x)", "x̄"),
    "ybar": ("y bar (mean of y)", "ȳ"),
    "xcirc": ("x hat (estimated x)", "x̂"),
    "ycirc": ("y hat (estimated y)", "ŷ"),
    "pcirc": ("p hat (estimated proportion)", "p̂"),
    "sslash": ("double slash", "⫽"),
    "supm1": ("superscript -1", "⁻¹"),
    "supr3": ("small superscript 3 (cube-root index)", "³"),
    "subm1": ("subscript -1", "₋₁"),
    "subs0": ("small subscript 0 (alternative glyph)", "₀"),
    "subs1": ("small subscript 1 (alternative glyph)", "₁"),
    "subs2": ("small subscript 2 (alternative glyph)", "₂"),
    "subsn": ("subscript n", "ₙ"),
    "asterisk": ("asterisk", "*"),
    "negB": ("inverted (white on black) B", "B"),
    "negR": ("inverted R", "R"),
    "negL": ("inverted L", "L"),
    "negEq": ("inverted =", "="),
    "negLe": ("inverted <", "<"),
    "negGr": ("inverted >", ">"),
    "negLE": ("inverted ≤", "≤"),
    "negGE": ("inverted ≥", "≥"),
    "lgComma": ("large comma", ","),
    "bolde": ("bold e (Euler's number)", "e"),
    "boldP": ("bold P (permutation nPr)", "P"),
    "boldr": ("bold r (correlation coefficient)", "r"),
    "boldX": ("bold X", "X"),
    "boldY": ("bold Y", "Y"),
    "hookn": ("engineering prefix n (nano)", "n"),
    "hookM": ("engineering prefix M (mega)", "M"),
    "serifG": ("engineering prefix G (giga)", "G"),
    "serifT": ("engineering prefix T (tera)", "T"),
    "serifP": ("engineering prefix P (peta)", "P"),
    "serifE": ("engineering prefix E (exa)", "E"),
    "hyphen": ("negative sign (-)", "-"),
    "supsquare": ("small superscript square", "▫"),
    "supr": ("superscript r (radians)", "ʳ"),
    "serifr": ("r (polar radius)", "r"),
    "seCorner": ("fraction corner (a⌟b⌟c)", "⌟"),
    "supg": ("superscript g (grads)", "ᵍ"),
}

UNICODE_SUBSCRIPTS = dict(zip("aehijklmnoprstuvx", "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))

# Byte sequences that several inputs produce: which input the decoder should
# print.  Characters that are syntax in .eam markup use their escape.
CANONICAL = {
    "5c": "\\\\", "5e": "\\^", "5f": "\\_", "7b": "\\{", "7d": "\\}", "26": "&",
    "89": "+", "2a": "*", "e6b5": "~", "7c": "|", "13": "⇒", "bb": "\\seCorner;",
    "2f": "/", "60": "`",
}


def char_name(ch: str) -> str:
    try:
        return unicodedata.name(ch).lower()
    except ValueError:
        return f"U+{ord(ch):04X}"


def extract():
    tokens = json.loads((FIXTURES / "palette_probe_tokens.json").read_text(encoding="utf-8"))
    eact = container.parse((FIXTURES / "palette_probe.g2e").read_bytes())
    lines = eact.lines[1:]  # skip the auto-generated title heading
    if len(lines) != len(tokens):
        raise SystemExit(f"probe has {len(lines)} lines but {len(tokens)} tokens")

    by_bytes: dict[str, dict] = {}
    for tok, line in zip(tokens, lines):
        data = line.data
        if tok["kind"] == "escape" and tok["input"] in ("a b", "\t"):
            continue  # documented in FORMAT.md; not symbols
        if not (data.startswith(b"Q") and data.endswith(b"Q")):
            # Raw '^' turns into a power structure around the closing Q:
            # it is syntax, not a character.
            continue
        code = data[1:-1].hex()
        entry = by_bytes.setdefault(code, {"bytes": code, "inputs": [], "category": tok["category"],
                                           "func": None})
        entry["inputs"].append(tok["input"])
        if tok["kind"] in ("func",) and not entry["func"]:
            entry["func"] = tok["func"]

    entries = []
    for code, e in by_bytes.items():
        inputs = list(dict.fromkeys(e["inputs"]))
        eam = CANONICAL.get(code, inputs[0])
        # A real Unicode character that maps to these bytes (for LaTeX / plain text input).
        unicode_chars = [s for s in inputs if len(s) == 1 and s not in "\\{}^_&"]
        if code == "5c":
            unicode_chars = ["\\"]
        elif code == "7b":
            unicode_chars = ["{"]
        elif code == "7d":
            unicode_chars = ["}"]
        elif code == "5e":
            unicode_chars = ["^"]
        elif code == "26":
            unicode_chars = ["&"]
        elif code == "5f":
            unicode_chars = ["_"]
        func = e["func"]
        if func:
            name, look = FUNC_INFO.get(func, (func, None))
        else:
            look = unicode_chars[0] if unicode_chars else None
            name = char_name(look) if look else eam
        entries.append({
            "bytes": code,
            "eam": eam,
            "aliases": [s for s in inputs if s != eam],
            "unicode": unicode_chars,
            "preview": look or eam,
            "name": name,
            "category": e["category"],
        })
    # Subscript glyphs: preview with real Unicode subscripts where they exist,
    # and accept those Unicode characters as input too.
    for e in entries:
        if e["eam"].startswith("_") and len(e["eam"]) == 2:
            uni = UNICODE_SUBSCRIPTS.get(e["eam"][1])
            if uni:
                e["preview"] = uni
                e["unicode"] = [uni]
    # Space and the subscript forms produced by '_' + char are not palette
    # entries of their own but are verified by fixtures (esc, sub2).
    entries.append({"bytes": "20", "eam": " ", "aliases": [], "unicode": [" "], "preview": " ",
                    "name": "space", "category": "ascii"})
    entries.sort(key=lambda e: (len(e["bytes"]), e["bytes"]))
    return {
        "comment": "Generated by tools/extract_charmap.py from tests/fixtures/eactmaker/palette_probe.*. "
                   "Do not edit by hand.",
        "lead_bytes": ["7f", "e5", "e6", "e7", "f7", "f9"],
        "entries": entries,
    }


def main():
    data = extract()
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != text:
            raise SystemExit("charmap.json is stale: run tools/extract_charmap.py")
        print("charmap.json is up to date")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(data['entries'])} symbols)")


if __name__ == "__main__":
    main()
