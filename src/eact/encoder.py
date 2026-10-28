"""IR -> bytes.

Structure encodings (verified byte-for-byte against EactMaker output, see
docs/FORMAT.md §4)::

    Frac      BB 1D 1A num 1B 1A den 1B 1E
    Sqrt      86 1D 1A body 1B 1E
    Abs       97 1D 1A body 1B 1E
    Pow       A8 1A exp 1B
    Sum       7F 29 1A expr 1C var 1C start 1C end 1B
    Log       7F 85 1A base 1C arg 1B
    Diff      7F 26 1A body 1C at 1B          (7F 27 for the 2nd derivative)
    Integral  8D 1A body 1C lower 1C upper 1B
    Matrix    7F 5D A4 { A4 cell {1C cell} B4 } B4
"""
from __future__ import annotations

import struct

from . import container
from .container import EActivity, Line
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Node, Note, Pow, Sqrt, Sum, TextLine

OPEN, CLOSE, SEP, BEGIN_2D, END_2D = b"\x1a", b"\x1b", b"\x1c", b"\x1d", b"\x1e"
MAT_OPEN, MAT_CLOSE = b"\xa4", b"\xb4"

TOKEN_FRAC = b"\xbb"
TOKEN_SQRT = b"\x86"
TOKEN_ABS = b"\x97"
TOKEN_POW = b"\xa8"
TOKEN_SUM = b"\x7f\x29"
TOKEN_LOG = b"\x7f\x85"
TOKEN_DIFF = b"\x7f\x26"
TOKEN_DIFF2 = b"\x7f\x27"
TOKEN_INT = b"\x8d"
TOKEN_MAT = b"\x7f\x5d"

# Header block of a note strip, between the inner size field and "@RUNMAT".
NOTE_VERSION = bytes.fromhex("0001020002000200")
NOTE_SETUP = bytes.fromhex(
    "00000000" "00001c2a" "3f02c000" "00002830" "00000000"
    "01010201" "01010301" "01010101" "01010101" "01010100"
)
NOTE_KIND = bytes.fromhex("000a0000")  # 0x0A: the "NOTES" strip type


def encode_nodes(nodes: list[Node]) -> bytes:
    out = bytearray()
    for n in nodes:
        out += encode_node(n)
    return bytes(out)


def _args(*groups) -> bytes:
    return OPEN + SEP.join(encode_nodes(g) for g in groups) + CLOSE


def encode_node(n: Node) -> bytes:
    if isinstance(n, Char):
        return n.code
    if isinstance(n, Frac):
        return TOKEN_FRAC + BEGIN_2D + _args(n.num) + _args(n.den) + END_2D
    if isinstance(n, Sqrt):
        return TOKEN_SQRT + BEGIN_2D + _args(n.body) + END_2D
    if isinstance(n, Abs):
        return TOKEN_ABS + BEGIN_2D + _args(n.body) + END_2D
    if isinstance(n, Pow):
        return TOKEN_POW + _args(n.exp)
    if isinstance(n, Sum):
        return TOKEN_SUM + _args(n.expr, n.var, n.start, n.end)
    if isinstance(n, Log):
        return TOKEN_LOG + _args(n.base, n.arg)
    if isinstance(n, Diff):
        return (TOKEN_DIFF2 if n.order == 2 else TOKEN_DIFF) + _args(n.body, n.at)
    if isinstance(n, Integral):
        return TOKEN_INT + _args(n.body, n.lower, n.upper)
    if isinstance(n, Matrix):
        rows = b"".join(MAT_OPEN + SEP.join(encode_nodes(c) for c in row) + MAT_CLOSE for row in n.rows)
        return TOKEN_MAT + MAT_OPEN + rows + MAT_CLOSE
    raise TypeError(f"cannot encode {n!r}")


def _line(nodes) -> Line:
    data = encode_nodes(nodes)
    return Line(container.LINE_TEXT_NUL if b"\x00" in data else container.LINE_TEXT, data)


def heading(title: str) -> bytes:
    """The first line EactMaker always generates: '======TITLE    ======='."""
    return b"======" + title.ljust(8).encode("ascii") + b"======="


def note_blob(note: Note) -> bytes:
    """Serialise a note strip (line type 0x06)."""
    lines = [_line(l.nodes) for l in note.lines]
    count = len(lines)
    directory, body = bytearray(), bytearray()
    offset = 4 + 4 * count + 4
    for ln in lines:
        blob = container.pad_line(ln.data)
        directory += bytes([ln.type]) + offset.to_bytes(3, "big")
        body += blob
        offset += len(blob)
    table = struct.pack(">I", count) + directory + bytes(4) + body   # starts at "line count"
    text1 = b"TEXT1\x00\x00\x00" + struct.pack(">II", 0x14, len(table)) + b"\xd4\x00\x00\x03"
    run =(b"@RUNMAT\x00" + struct.pack(">II", 1, len(text1) + len(table))
           + text1 + table + bytes(4))
    inner = (struct.pack(">I", container.SETUP_LS) + NOTE_VERSION + NOTE_SETUP + bytes(0x10) + run)
    outer = (b"@EACT\x00\x00\x00" + bytes(4) + NOTE_KIND
             + container.pad_line(encode_nodes(note.title))
             + b"\xab\xcd\xef\x89" + struct.pack(">I", len(inner)) + inner)
    return outer


def encode_doc(doc: Doc, fmt: str = "g2e") -> bytes:
    """Encode a whole document into a .g2e (or .g1e) file."""
    lines = [Line(container.LINE_HEADING, heading(doc.title))]
    for block in doc.blocks:
        if isinstance(block, Note):
            lines.append(Line(container.LINE_STRIP, note_blob(block)))
        elif isinstance(block, TextLine):
            lines.append(_line(block.nodes))
        else:
            raise TypeError(f"unknown block {block!r}")
    return container.build(EActivity(lines=lines, version=container.FORMATS[fmt]))
