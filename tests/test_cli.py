"""The CLI contract that agents rely on: exit codes and JSON shape."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"


def run(*args, stdin=None):
    env = {"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, "-m", "eact", *args], input=stdin, capture_output=True,
                          text=True, env=env, cwd=ROOT)


class TestCLI(unittest.TestCase):
    def test_check_ok_json(self):
        r = run("check", "-", "--title", "T", "--json", stdin="hola $x^2$")
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = json.loads(r.stdout)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["stats"]["lines"], 1)

    def test_check_error_exit_2(self):
        r = run("check", "-", "--title", "T", "--json", stdin="$\\nope$")
        self.assertEqual(r.returncode, 2)
        rep = json.loads(r.stdout)
        self.assertFalse(rep["ok"])
        d = rep["diagnostics"][0]
        self.assertEqual((d["code"], d["severity"], d["line"]), ("E001", "error", 1))

    def test_strict_warning_exit_1(self):
        r = run("check", "-", "--title", "T", "--strict", stdin="\\textbf{x}")
        self.assertEqual(r.returncode, 1)
        r = run("check", "-", "--title", "T", stdin="\\textbf{x}")
        self.assertEqual(r.returncode, 0)

    def test_build_refuses_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "X.g2e"
            r = run("build", "-", "--title", "X", "-o", str(out), stdin="😀")
            self.assertEqual(r.returncode, 2)
            self.assertFalse(out.exists())

    def test_build_and_dump(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "X.g2e"
            r = run("build", "-", "--title", "X", "-o", str(out), stdin="$\\frac{1}{2}$")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = run("dump", str(out))
            self.assertEqual(r.stdout.strip(), "\\frac{1}{2}")

    def test_build_eam_matches_reference(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "T.g2e"
            r = run("build", str(FIX / "TEST.g2e.eam"), "-o", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_bytes(), (FIX / "TEST.g2e").read_bytes())

    def test_symbols_json(self):
        r = run("symbols", "--json")
        table = json.loads(r.stdout)
        self.assertGreater(len(table["characters"]), 500)
        self.assertIn("alpha", table["latex"]["greek"])
        self.assertIn("E001", table["diagnostic_codes"])


if __name__ == "__main__":
    unittest.main()
