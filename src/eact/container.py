"""Binary container for CASIO eActivity files (.g1e / .g2e).

Layout (all integers big-endian; see docs/FORMAT.md for the full description)::

    0x00  0x20  StandardHeader  ("USBPower" inverted, type 0x49, inverted size, control bytes)
    0x20  4     file size
    0x24  4     LS = length of the setup area (0x38 in every file we have seen)
    0x28  8     version bytes   (G2E: 00 01 02 00 02 02 02 01, G1E: 00 01 01 00 'Pack')
    0x30  ...   setup area      (template, copied verbatim)
    0x20+LS 0x10 zeros
    0x30+LS 8   "@EACT\\0\\0\\0"
    0x38+LS 4   1
    0x3C+LS 4   length1 = size - 0x40 - LS
    0x40+LS 8   "EACT1\\0\\0\\0"
    0x48+LS 4   0x14
    0x4C+LS 4   length2 = size - 0x54 - LS
    0x50+LS 4   D4 00 00 66
    0x54+LS 4   line count LC
    0x58+LS 4*LC line directory: [type:1][offset:3], offset relative to 0x54+LS
    ...     4   zeros
    ...         lines, each NUL-terminated and padded with zeros to a multiple of 4

The module only knows about bytes; turning text into bytes is the encoder's job.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

STANDARD_HEADER_SIZE = 0x20
EACT_FILE_TYPE = 0x49

# Line (entry) types found in the line directory.
LINE_HEADING = 0x07   # the auto-generated "======TITLE    =======" row
LINE_TEXT = 0x81      # text, including 2-D math (as long as it contains no NUL)
LINE_TEXT_NUL = 0x82  # text mixed with tokens that contain 0x00 bytes
LINE_STRIP = 0x06     # an embedded strip (EactMaker's \note)

VERSION_G2E = bytes.fromhex("0001020002020201")
VERSION_G1E = b"\x00\x01\x01\x00Pack"

# Setup area copied from files written by EactMaker (bytes 0x30 .. 0x20+LS).
# Meaning of individual entries is only partly known; see docs/FORMAT.md.
SETUP_LS = 0x38
SETUP_AREA = bytes.fromhex(
    "00000000" "1000142a" "3f02c000" "00002830"
    "00000000" "01020101" "01030101" "01010101"
    "01010101" "01010000"
)
assert len(SETUP_AREA) == SETUP_LS - 0x10

FORMATS = {"g2e": VERSION_G2E, "g1e": VERSION_G1E}


class FormatError(ValueError):
    """Raised when a file does not look like an eActivity."""


def _invert(data: bytes) -> bytes:
    return bytes(b ^ 0xFF for b in data)


def standard_header(file_size: int, file_type: int = EACT_FILE_TYPE) -> bytes:
    """Build the 32-byte CASIO StandardHeader (stored bit-inverted)."""
    lsb = file_size & 0xFF
    plain = (
        b"USBPower"
        + bytes([file_type])
        + b"\x00\x10\x00\x10\x00"
        + bytes([(lsb + 0x41) & 0xFF])
        + b"\x01"
        + struct.pack(">I", file_size)
        + bytes([(lsb + 0xB8) & 0xFF])
    )
    # Bytes 0x15..0x1F are stored as zeros (not inverted).
    return _invert(plain) + bytes(STANDARD_HEADER_SIZE - len(plain))


def parse_standard_header(data: bytes) -> dict:
    """Decode and validate a StandardHeader. Returns {'type', 'size'}."""
    if len(data) < STANDARD_HEADER_SIZE:
        raise FormatError("file too short for a CASIO header")
    plain = _invert(data[:0x15])
    if plain[:8] != b"USBPower":
        raise FormatError("missing 'USBPower' magic: not a CASIO file")
    size = struct.unpack(">I", plain[0x10:0x14])[0]
    lsb = size & 0xFF
    if plain[0x0E] != (lsb + 0x41) & 0xFF or plain[0x14] != (lsb + 0xB8) & 0xFF:
        raise FormatError("header control bytes do not match the file size")
    return {"type": plain[8], "size": size}


def pad_line(payload: bytes) -> bytes:
    """NUL-terminate and zero-pad a line payload to a multiple of 4 bytes."""
    out = payload + b"\x00"
    return out + bytes(-len(out) % 4)


@dataclass
class Line:
    """One entry of the line directory.

    ``data`` is the raw bytes of the entry *without* trailing NUL padding for
    text lines, and the complete blob for strips.
    """
    type: int
    data: bytes


@dataclass
class EActivity:
    lines: list[Line] = field(default_factory=list)
    version: bytes = VERSION_G2E
    setup: bytes = SETUP_AREA


def build(eact: EActivity) -> bytes:
    """Serialise an :class:`EActivity` into a complete .g1e/.g2e file."""
    ls = len(eact.setup) + 0x10
    count = len(eact.lines)
    base = 0x54 + ls
    directory = bytearray()
    body = bytearray()
    offset = 4 + 4 * count + 4  # LC field + directory + zero word, relative to base
    for line in eact.lines:
        blob = line.data if line.type == LINE_STRIP else pad_line(line.data)
        if len(blob) % 4:
            raise ValueError("strip blobs must be 4-byte aligned")
        directory += bytes([line.type]) + offset.to_bytes(3, "big")
        body += blob
        offset += len(blob)
    size = base + offset

    out = bytearray(standard_header(size))
    out += struct.pack(">II", size, ls)
    out += eact.version
    out += eact.setup
    out += bytes(0x10)
    out += b"@EACT\x00\x00\x00" + struct.pack(">II", 1, size - 0x40 - ls)
    out += b"EACT1\x00\x00\x00" + struct.pack(">II", 0x14, size - 0x54 - ls)
    out += b"\xd4\x00\x00\x66"
    out += struct.pack(">I", count) + directory + bytes(4) + body
    assert len(out) == size
    return bytes(out)


def parse(data: bytes) -> EActivity:
    """Parse a .g1e/.g2e file into an :class:`EActivity`.

    Raises :class:`FormatError` with a descriptive message on malformed input.
    """
    hdr = parse_standard_header(data)
    if hdr["type"] != EACT_FILE_TYPE:
        raise FormatError(f"file type 0x{hdr['type']:02X} is not an eActivity (0x49)")
    if hdr["size"] != len(data):
        raise FormatError(f"header says {hdr['size']} bytes but file has {len(data)}")
    size, ls = struct.unpack_from(">II", data, 0x20)
    version = data[0x28:0x30]
    setup = data[0x30:0x20 + ls]
    p = 0x30 + ls
    if data[p:p + 5] != b"@EACT":
        raise FormatError(f"expected '@EACT' at 0x{p:X}")
    p = 0x40 + ls
    if data[p:p + 5] != b"EACT1":
        raise FormatError(f"expected 'EACT1' at 0x{p:X}")
    base = 0x54 + ls
    count = struct.unpack_from(">I", data, base)[0]
    entries = []
    for i in range(count):
        raw = data[base + 4 + 4 * i: base + 8 + 4 * i]
        entries.append((raw[0], base + int.from_bytes(raw[1:], "big")))
    lines = []
    for i, (typ, start) in enumerate(entries):
        end = entries[i + 1][1] if i + 1 < count else len(data)
        chunk = data[start:end]
        if typ == LINE_STRIP:
            lines.append(Line(typ, chunk))
        elif typ == LINE_TEXT_NUL:
            lines.append(Line(typ, chunk.rstrip(b"\x00")))
        else:
            lines.append(Line(typ, chunk.split(b"\x00", 1)[0]))
    return EActivity(lines=lines, version=version, setup=setup)
