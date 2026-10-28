#!/usr/bin/env python3
"""Convert 1-bit Windows BMP screenshots (as produced by the CASIO
screen-capture feature, 384x192x1) to PNG using only the standard library.

Usage: python3 tools/bmp2png.py IN.bmp [IN2.bmp ...] [-o OUTDIR]

Only uncompressed 1/8/24-bit BMPs are supported; that is all we need for
the calculator captures in docs/img/calculator/.
"""
import struct
import sys
import zlib
from pathlib import Path


def read_bmp(data: bytes):
    """Return (width, height, rows) where rows is a list of lists of RGB tuples, top row first."""
    if data[:2] != b"BM":
        raise ValueError("not a BMP file")
    pix_off = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if compression != 0:
        raise ValueError("compressed BMPs are not supported")
    hdr_size = struct.unpack_from("<I", data, 14)[0]
    palette = []
    if bpp <= 8:
        ncolors = struct.unpack_from("<I", data, 46)[0] or (1 << bpp)
        pal_off = 14 + hdr_size
        for i in range(ncolors):
            b, g, r, _ = data[pal_off + 4 * i: pal_off + 4 * i + 4]
            palette.append((r, g, b))
    bottom_up = height > 0
    height = abs(height)
    stride = ((width * bpp + 31) // 32) * 4
    rows = []
    for y in range(height):
        row_off = pix_off + y * stride
        row = []
        for x in range(width):
            if bpp == 1:
                byte = data[row_off + x // 8]
                row.append(palette[(byte >> (7 - x % 8)) & 1])
            elif bpp == 8:
                row.append(palette[data[row_off + x]])
            elif bpp == 24:
                b, g, r = data[row_off + 3 * x: row_off + 3 * x + 3]
                row.append((r, g, b))
            else:
                raise ValueError(f"unsupported bpp {bpp}")
        rows.append(row)
    if bottom_up:
        rows.reverse()
    return width, height, rows


def write_png(path: Path, width: int, height: int, rows) -> None:
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def main(argv):
    out_dir = None
    if "-o" in argv:
        i = argv.index("-o")
        out_dir = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    for name in argv:
        src = Path(name)
        w, h, rows = read_bmp(src.read_bytes())
        dst = (out_dir or src.parent) / (src.stem + ".png")
        dst.parent.mkdir(parents=True, exist_ok=True)
        write_png(dst, w, h, rows)
        print(f"{src} -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1:])
