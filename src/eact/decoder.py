"""bytes -> IR: read any .g1e/.g2e eActivity back into a :class:`~eact.ir.Doc`.

Used by ``eact dump`` and by the round-trip tests.  Anything that is not
understood is kept as raw characters (``\\raw{..}`` in the .eam dump), so
decoding never loses bytes.
"""
from __future__ import annotations

import re
import struct

from . import charmap as _charmap
from . import container, encoder as E
from .ir import Abs, Char, Diff, Doc, Frac, Integral, Log, Matrix, Node, Note, Pow, Sqrt, Sum, TextLine

OPEN, CLOSE, SEP, B2D, E2D = 0x1A, 0x1B, 0x1C, 0x1D, 0x1E
MAT_OPEN, MAT_CLOSE = 0xA4, 0xB4

HEADING_RE = re.compile(rb"^=+(.*?)=+$")


class _Malformed(Exception):
    pass


class _Reader:
    def __init__(self, codes: list[bytes]):
        self.c = codes
        self.i = 0

    def peek(self, k=0) -> bytes:
        j = self.i + k
        return self.c[j] if j < len(self.c) else b""

    def expect(self, byte: int):
        if self.peek() != bytes([byte]):
            raise _Malformed
        self.i += 1

    def seq(self, stops: set[int]) -> list[Node]:
        nodes: list[Node] = []
        while self.i < len(self.c):
            cur = self.peek()
            if len(cur) == 1 and cur[0] in stops:
                break
            nodes.append(self.node())
        return nodes

    def args(self, n: int) -> list[list[Node]]:
        self.expect(OPEN)
        out = [self.seq({SEP, CLOSE})]
        for _ in range(n - 1):
            self.expect(SEP)
            out.append(self.seq({SEP, CLOSE}))
        self.expect(CLOSE)
        return out

    def wrapped(self, n: int) -> list[list[Node]]:
        self.expect(B2D)
        out = []
        for _ in range(n):
            self.expect(OPEN)
            out.append(self.seq({CLOSE, SEP}))
            self.expect(CLOSE)
        self.expect(E2D)
        return out

    def node(self) -> Node:
        start = self.i
        cur = self.peek()
        nxt = self.peek(1)
        self.i += 1
        try:
            if cur == E.TOKEN_FRAC and nxt == E.BEGIN_2D:
                a = self.wrapped(2)
                return Frac(a[0], a[1])
            if cur == E.TOKEN_SQRT and nxt == E.BEGIN_2D:
                return Sqrt(self.wrapped(1)[0])
            if cur == E.TOKEN_ABS and nxt == E.BEGIN_2D:
                return Abs(self.wrapped(1)[0])
            if cur == E.TOKEN_POW and nxt == E.OPEN:
                return Pow(self.args(1)[0])
            if cur == E.TOKEN_SUM and nxt == E.OPEN:
                a = self.args(4)
                return Sum(*a)
            if cur == E.TOKEN_LOG and nxt == E.OPEN:
                a = self.args(2)
                return Log(*a)
            if cur in (E.TOKEN_DIFF, E.TOKEN_DIFF2) and nxt == E.OPEN:
                a = self.args(2)
                return Diff(a[0], a[1], 2 if cur == E.TOKEN_DIFF2 else 1)
            if cur == E.TOKEN_INT and nxt == E.OPEN:
                a = self.args(3)
                return Integral(*a)
            if cur == E.TOKEN_MAT and nxt == E.MAT_OPEN:
                return self.matrix()
        except _Malformed:
            self.i = start + 1  # not a well-formed structure: keep the token as a character
        return Char(cur)

    def matrix(self) -> Matrix:
        self.expect(MAT_OPEN)
        rows = []
        while self.peek() == bytes([MAT_OPEN]):
            self.i += 1
            row = [self.seq({SEP, MAT_CLOSE})]
            while self.peek() == bytes([SEP]):
                self.i += 1
                row.append(self.seq({SEP, MAT_CLOSE}))
            self.expect(MAT_CLOSE)
            rows.append(row)
        self.expect(MAT_CLOSE)
        return Matrix(rows)


def decode_nodes(data: bytes, cmap=None) -> list[Node]:
    cmap = cmap or _charmap.default()
    return _Reader(cmap.split(data)).seq(set())


def _cstr(data: bytes, at: int) -> bytes:
    end = data.index(b"\x00", at)
    return data[at:end]


def decode_note(blob: bytes, cmap=None) -> Note:
    """Decode a type-0x06 strip produced by EactMaker's \\note."""
    title = _cstr(blob, 16)
    run = blob.find(b"@RUNMAT")
    text1 = blob.find(b"TEXT1", run)
    if run < 0 or text1 < 0:
        raise container.FormatError("strip is not a NOTES strip (no @RUNMAT/TEXT1)")
    base = text1 + 20  # the line-count field; offsets are relative to it
    count = struct.unpack_from(">I", blob, base)[0]
    offsets = [int.from_bytes(blob[base + 5 + 4 * k: base + 8 + 4 * k], "big") for k in range(count)]
    lines = [TextLine(decode_nodes(_cstr(blob, base + off), cmap)) for off in offsets]
    return Note(decode_nodes(title, cmap), lines)


def decode(data: bytes) -> Doc:
    """Decode a whole .g1e/.g2e file."""
    eact = container.parse(data)
    cmap = _charmap.default()
    doc = Doc(title="")
    for k, line in enumerate(eact.lines):
        if k == 0 and line.type == container.LINE_HEADING:
            m = HEADING_RE.match(line.data)
            doc.title = (m.group(1) if m else line.data).decode("ascii", "replace").strip()
            continue
        if line.type == container.LINE_STRIP:
            doc.blocks.append(decode_note(line.data, cmap))
        else:
            doc.blocks.append(TextLine(decode_nodes(line.data, cmap)))
    return doc
