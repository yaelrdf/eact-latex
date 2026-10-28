"""Binary format tests: everything here is checked against real EactMaker output."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from eact import container, decoder, eam, encoder  # noqa: E402
from eact.diagnostics import Reporter  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
EM = FIX / "eactmaker"


def golden_pairs():
    yield FIX / "TEST.g2e.eam", FIX / "TEST.g2e", None
    for txt in sorted(EM.glob("*.txt")):
        if txt.stem == "palette_probe":
            continue
        yield txt, txt.with_suffix(".g2e"), "A"


class TestContainer(unittest.TestCase):
    def test_standard_header_matches_reference(self):
        data = (FIX / "TEST.g2e").read_bytes()
        self.assertEqual(container.standard_header(len(data)), data[:0x20])

    def test_parse_build_is_identity(self):
        for f in [FIX / "TEST.g2e", *EM.glob("*.g2e"), EM / "g1e_x.g1e"]:
            data = f.read_bytes()
            with self.subTest(file=f.name):
                self.assertEqual(container.build(container.parse(data)), data)

    def test_test_file_layout(self):
        eact = container.parse((FIX / "TEST.g2e").read_bytes())
        self.assertEqual(len(eact.lines), 49)
        self.assertEqual(eact.lines[0].type, container.LINE_HEADING)
        self.assertEqual(eact.lines[0].data, b"======TEST    =======")
        self.assertEqual(sum(1 for l in eact.lines if l.type == container.LINE_STRIP), 1)

    def test_rejects_garbage(self):
        with self.assertRaises(container.FormatError):
            container.parse(b"not a casio file at all, definitely not" * 2)

    def test_detects_truncation(self):
        data = (FIX / "TEST.g2e").read_bytes()
        with self.assertRaises(container.FormatError):
            container.parse(data[:-4])

    def test_g1e_differs_only_in_version(self):
        g1e = (EM / "g1e_x.g1e").read_bytes()
        g2e = (EM / "out.g2e").read_bytes()
        diff = [i for i in range(len(g1e)) if g1e[i] != g2e[i]]
        self.assertTrue(all(0x28 <= i < 0x30 for i in diff), diff)


class TestGolden(unittest.TestCase):
    """Our encoder must reproduce EactMaker byte-for-byte."""

    def test_eam_to_g2e(self):
        for src, ref, title in golden_pairs():
            with self.subTest(file=src.name):
                rep = Reporter()
                doc = eam.parse_file_text(src.read_text(encoding="utf-8"), rep, default_title=title or "X")
                self.assertEqual(rep.errors, [])
                self.assertEqual(encoder.encode_doc(doc), ref.read_bytes())

    def test_g1e(self):
        rep = Reporter()
        doc = eam.parse_file_text("x", rep, default_title="A")
        self.assertEqual(encoder.encode_doc(doc, "g1e"), (EM / "g1e_x.g1e").read_bytes())


class TestRoundTrip(unittest.TestCase):
    def test_decode_encode(self):
        for f in [FIX / "TEST.g2e", *sorted(EM.glob("*.g2e"))]:
            data = f.read_bytes()
            with self.subTest(file=f.name):
                self.assertEqual(encoder.encode_doc(decoder.decode(data)), data)

    def test_decode_dump_parse_encode(self):
        for f in [FIX / "TEST.g2e", *sorted(EM.glob("*.g2e"))]:
            data = f.read_bytes()
            with self.subTest(file=f.name):
                doc = decoder.decode(data)
                rep = Reporter()
                again = eam.parse_file_text(eam.write_file_text(doc), rep)
                self.assertEqual(rep.errors, [])
                self.assertEqual(encoder.encode_doc(again), data)

    def test_unknown_bytes_survive_as_raw(self):
        rep = Reporter()
        doc = eam.parse_file_text("a\\raw{F7 01}b", rep, default_title="A")
        data = encoder.encode_doc(doc)
        self.assertIn("\\raw{F7 01}", eam.write_content(decoder.decode(data)))


class TestCharmap(unittest.TestCase):
    def test_charmap_is_up_to_date(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "extract_charmap.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_known_codes(self):
        from eact import charmap
        cm = charmap.default()
        cases = {"α": "e640", "Σ": "e551", "+": "89", "−": "99", "×": "a9", "÷": "b9", "≤": "10",
                 "∞": "7f53", "é": "e60a", "ñ": "e612", "¿": "e591", "~": "e6b5", "_": "5f"}
        for ch, code in cases.items():
            with self.subTest(ch=ch):
                self.assertEqual(cm.encode_char(ch).hex(), code)
        self.assertEqual(cm.subscript("a").hex(), "e761")
        self.assertEqual(cm.subscript("1").hex(), "e5d1")
        self.assertIsNone(cm.subscript("α"))
        self.assertIsNone(cm.encode_char("😀"))


if __name__ == "__main__":
    unittest.main()
