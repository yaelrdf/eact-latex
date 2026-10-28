"""Command-line interface: ``eact build | check | dump | symbols``.

Exit codes (stable; agents rely on them):
    0  success
    1  only warnings, but --strict was given
    2  errors (conversion refused, unreadable input, bad usage)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, charmap, container, convert, decoder, eam, latex, preview
from .diagnostics import CODES

EXIT_OK, EXIT_STRICT, EXIT_ERROR = 0, 1, 2


def _report(rep, args, extra: dict) -> int:
    if args.json:
        print(rep.to_json(**extra))
    else:
        for d in rep.items:
            print(d.format(), file=sys.stderr)
        if extra.get("preview"):
            print(extra["preview"])
        summary = f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)"
        if extra.get("output"):
            summary += f"; wrote {extra['output']} ({extra['stats'].get('bytes', 0)} bytes)"
        print(summary, file=sys.stderr)
    if rep.errors:
        return EXIT_ERROR
    if args.strict and rep.warnings:
        return EXIT_STRICT
    return EXIT_OK


def _load(args):
    try:
        return convert.load(args.input, kind=args.source, title=args.title)
    except (OSError, container.FormatError, UnicodeDecodeError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "fatal": str(exc)}))
        else:
            print(f"eact: {exc}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def cmd_check(args) -> int:
    doc, rep = _load(args)
    convert.check_format(doc, rep, args.format)
    extra = {"stats": convert.stats(doc)}
    if args.preview:
        extra["preview"] = preview.render(doc)
    if args.eam:
        extra["eam"] = eam.write_content(doc, "\n")
        if not args.json:
            print(extra.pop("eam"))
    return _report(rep, args, extra)


def cmd_build(args) -> int:
    doc, rep = _load(args)
    convert.check_format(doc, rep, args.format)
    extra = {"stats": convert.stats(doc), "output": None}
    if args.preview:
        extra["preview"] = preview.render(doc)
    if rep.errors and not args.force:
        return _report(rep, args, extra)
    if args.strict and rep.warnings:
        return _report(rep, args, extra)
    data = convert.build(doc, args.format)
    if args.output == "-":
        sys.stdout.buffer.write(data)
        return EXIT_OK
    out = Path(args.output) if args.output else \
        (Path(args.input).parent if args.input != "-" else Path(".")) / f"{doc.title.replace(' ', '_')}.{args.format}"
    out.write_bytes(data)
    if args.eam_out:
        Path(args.eam_out).write_text(eam.write_file_text(doc, args.format), encoding="utf-8", newline="")
    extra["output"] = str(out)
    extra["stats"] = convert.stats(doc, data)
    code = _report(rep, args, extra)
    return EXIT_OK if args.force and code == EXIT_ERROR else code


def cmd_dump(args) -> int:
    try:
        data = Path(args.input).read_bytes()
        if args.as_ == "structure":
            eact = container.parse(data)
            print(f"version {eact.version.hex(' ')}, {len(eact.lines)} lines")
            for k, ln in enumerate(eact.lines):
                print(f"{k:3d} type 0x{ln.type:02X} {len(ln.data):4d} bytes  {ln.data[:24].hex(' ')}"
                      + (" …" if len(ln.data) > 24 else ""))
            return EXIT_OK
        doc = decoder.decode(data)
    except (OSError, container.FormatError) as exc:
        print(f"eact: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.as_ == "eam":
        text = eam.write_file_text(doc) if args.project else eam.write_content(doc, "\n")
    elif args.as_ == "preview":
        text = preview.render(doc)
    else:
        text = json.dumps({"title": doc.title, "stats": convert.stats(doc, data),
                           "eam": eam.write_content(doc, "\n"), "preview": preview.render(doc)},
                          ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="")
    else:
        print(text)
    return EXIT_OK


def symbol_table() -> dict:
    cm = charmap.default()
    return {
        "characters": [
            {"bytes": s.code.hex().upper(), "eam": s.eam, "unicode": list(s.unicode),
             "preview": s.preview, "name": s.name, "category": s.category}
            for s in cm.symbols
        ],
        "latex": {
            "greek": latex.GREEK,
            "symbols": latex.SYMBOLS,
            "approximated_symbols": latex.LOOKALIKES,
            "text_functions": sorted(latex.FUNCTIONS | latex.LIMIT_FUNCTIONS | {"log"}),
            "structures": {
                "\\frac{a}{b}": "fraction", "\\sqrt{x}": "square root", "\\sqrt[n]{x}": "n-th root",
                "x^{n}": "power", "x_{i}": "subscript glyphs (A-Z a-z 0-9 + -)",
                "\\sum_{k=a}^{b} expr": "summation template", "\\int_a^b f\\,dx": "definite integral template",
                "\\log_b(x)": "log with base", "|x|, \\left|x\\right|, \\abs{x}": "absolute value",
                "\\begin{pmatrix}..\\end{pmatrix}": "matrix (also bmatrix, matrix, vmatrix, cases)",
                "\\diff{f}{a}, \\diff2{f}{a}": "d/dx f |x=a template (eact extension)",
                "\\note{title}{content}": "collapsible NOTES strip (eact extension)",
                "\\raw{hex}": "raw bytes (eact extension)",
            },
        },
        "diagnostic_codes": {k: {"severity": v[0], "title": v[1]} for k, v in CODES.items()},
    }


def cmd_symbols(args) -> int:
    table = symbol_table()
    if args.json:
        print(json.dumps(table, ensure_ascii=False, indent=1))
        return EXIT_OK
    if args.latex:
        lt = table["latex"]
        for k, v in sorted({**lt["greek"], **lt["symbols"]}.items()):
            print(f"\\{k:<16} {v}")
        print("\n# approximated (warning W001):")
        for k, v in sorted(lt["approximated_symbols"].items()):
            print(f"\\{k:<16} -> {v}")
        print("\n# structures:")
        for k, v in lt["structures"].items():
            print(f"{k:<36} {v}")
        return EXIT_OK
    for s in table["characters"]:
        if args.category and s["category"] != args.category:
            continue
        uni = "".join(s["unicode"])
        print(f"{s['bytes']:>4}  {s['eam']:<14} {uni:<4} {s['name']}")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eact", description="LaTeX / EactMaker markup -> CASIO eActivity (.g2e)")
    ap.add_argument("--version", action="version", version=f"eact {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("input", help="source file (.tex, .eam, .g2e) or '-' for stdin")
        p.add_argument("--from", dest="source", choices=["latex", "eam", "g2e"],
                       help="source syntax (default: from the file extension; stdin = latex)")
        p.add_argument("--title", help="eActivity title / file name (max 8 chars)")
        p.add_argument("--format", choices=convert.FORMATS, default="g2e", help="output format (default g2e)")
        p.add_argument("--json", action="store_true", help="machine-readable report on stdout")
        p.add_argument("--strict", action="store_true", help="treat warnings as failures (exit 1)")
        p.add_argument("--preview", action="store_true", help="include a text preview of the screen")

    p = sub.add_parser("check", help="parse and report problems; write nothing")
    common(p)
    p.add_argument("--eam", action="store_true", help="also print the EactMaker markup it converts to")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="convert to .g2e")
    common(p)
    p.add_argument("-o", "--output", help="output file ('-' = stdout); default TITLE.g2e next to the input")
    p.add_argument("--eam-out", help="also save the .eam project (loadable in EactMaker)")
    p.add_argument("--force", action="store_true", help="write the file even if there are errors")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("dump", help="decode a .g2e/.g1e file")
    p.add_argument("input")
    p.add_argument("--as", dest="as_", choices=["eam", "preview", "json", "structure"], default="eam")
    p.add_argument("--project", action="store_true", help="with --as eam: write a full .eam project file")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("symbols", help="list supported characters and LaTeX commands")
    p.add_argument("--json", action="store_true")
    p.add_argument("--latex", action="store_true", help="list LaTeX commands instead of calculator characters")
    p.add_argument("--category", choices=["ascii", "math", "misc", "subscript", "greek", "latin", "cyrillic"])
    p.set_defaults(func=cmd_symbols)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
