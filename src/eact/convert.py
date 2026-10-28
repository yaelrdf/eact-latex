"""High-level API: load a source, check it, build the binary.

This is what the CLI uses and what Python callers (or agents writing
Python) should use::

    from eact import convert
    doc, rep = convert.load("exercise.tex")
    if not rep.errors:
        data = convert.build(doc)
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import decoder, eam, encoder, latex, preview
from .diagnostics import Reporter
from .ir import Doc, Note, TextLine

FORMATS = ("g2e", "g1e")
SOURCE_KINDS = ("latex", "eam", "g2e")


def normalize_title(raw: str | None, rep: Reporter, fallback: str = "NOTES") -> str:
    """Make a valid eActivity title: up to 8 chars of A-Z, 0-9, space, '-', '_', '.'.

    The title is uppercased (the calculator's file list is uppercase).  W006 is
    reported when characters had to be dropped or the title was cut.
    """
    if not raw or not raw.strip():
        return fallback
    ascii_ = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9 _.\-]", "", ascii_).strip().upper()
    title = cleaned[:8].rstrip()
    if not title:
        rep.add("W006", f"title {raw!r} has no usable characters; using {fallback!r}",
                hint="pass --title with up to 8 letters/digits")
        return fallback
    if title != raw.strip().upper():
        rep.add("W006", f"title {raw!r} shortened to {title!r} (max 8 chars: A-Z 0-9 space - _ .)",
                hint="pass --title to choose it")
    return title


def detect_kind(path: str | None, data: bytes | None = None) -> str:
    if data is not None and data[:8] == bytes(b ^ 0xFF for b in b"USBPower"):
        return "g2e"
    suffix = Path(path or "").suffix.lower()
    if suffix in (".g2e", ".g1e"):
        return "g2e"
    if suffix == ".eam":
        return "eam"
    return "latex"


def load_text(text: str, kind: str = "latex", file: str = "", title: str | None = None) -> tuple[Doc, Reporter]:
    """Parse source text of the given kind ('latex' or 'eam')."""
    rep = Reporter(file)
    stem = Path(file).stem if file else None
    if kind == "eam":
        doc = eam.parse_file_text(text, rep, default_title=stem or "NOTES")
        doc.title = normalize_title(title or doc.title, rep)
    elif kind == "latex":
        blocks, tex_title = latex.parse(text, rep)
        doc = Doc(title=normalize_title(title or tex_title or stem, rep), blocks=blocks)
    else:
        raise ValueError(f"unknown source kind {kind!r}")
    check(doc, rep)
    return doc, rep


def load(path: str, kind: str | None = None, title: str | None = None) -> tuple[Doc, Reporter]:
    """Load a .tex/.eam/.g2e file ('-' reads stdin as text)."""
    import sys
    if path == "-":
        text = sys.stdin.read()
        return load_text(text, kind or "latex", "<stdin>", title)
    data = Path(path).read_bytes()
    kind = kind or detect_kind(path, data)
    if kind == "g2e":
        rep = Reporter(path)
        doc = decoder.decode(data)
        if title:
            doc.title = normalize_title(title, rep)
        check(doc, rep)
        return doc, rep
    text = data.decode("utf-8-sig")
    return load_text(text, kind, path, title)


def check(doc: Doc, rep: Reporter) -> None:
    """Document-level checks that do not depend on the source syntax."""
    if not any((isinstance(b, TextLine) and b.nodes) or isinstance(b, Note) for b in doc.blocks):
        rep.add("E008", "the document has no content", hint="is the text inside \\begin{document}…\\end{document}?")
    for b in doc.blocks:
        lines = b.lines if isinstance(b, Note) else [b]
        for ln in lines:
            # Plain text wraps on the calculator; a single 2-D structure cannot.
            for node in ln.nodes:
                if preview.has_structure([node]):
                    width = len(preview.linear([node]))
                    if width > preview.SCREEN_COLS:
                        rep.add("I001", f"formula '{preview.linear([node])[:30]}…' is ~{width} chars wide; "
                                        "the calculator will scroll it horizontally",
                                ln.src_line or b.src_line, 1,
                                "split it into smaller formulas if it is hard to read")


def check_format(doc: Doc, rep: Reporter, fmt: str) -> None:
    """Checks that depend on the output format."""
    if fmt == "g1e" and any(isinstance(b, Note) for b in doc.blocks):
        rep.add("I002", "notes in G1E files have not been verified on a calculator")


def build(doc: Doc, fmt: str = "g2e") -> bytes:
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {FORMATS}")
    return encoder.encode_doc(doc, fmt)


def stats(doc: Doc, data: bytes | None = None) -> dict:
    notes = [b for b in doc.blocks if isinstance(b, Note)]
    out = {
        "title": doc.title,
        "lines": sum(1 for b in doc.blocks if isinstance(b, TextLine)),
        "notes": len(notes),
        "note_lines": sum(len(n.lines) for n in notes),
    }
    if data is not None:
        out["bytes"] = len(data)
    return out
