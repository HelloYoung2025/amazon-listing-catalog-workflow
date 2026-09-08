"""Distribution tests use only isolated temporary installations and synthetic files."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_package import NAMES, verify
from install import install


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.dest = self.base / "skills"

    def test_source_complete(self):
        self.assertEqual(verify(ROOT / "skills"), [])

    def test_fresh_install_and_validator_imports(self):
        self.assertIsNone(install(self.dest))
        self.assertEqual(verify(self.dest), [])
        self.assertEqual({p.name for p in self.dest.iterdir()}, set(NAMES))
        gate = self.dest / NAMES[2] / "tools"
        # Both validators' actual imports must work outside the repository.
        import subprocess
        for component, script in (("listing", "validate_listing_package.py"), ("aplus", "validate_bundle.py")):
            result = subprocess.run([sys.executable, "-B", str(gate / component / "scripts" / script), "--help"],
                                    cwd=self.base, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_companion_is_detected(self):
        install(self.dest)
        (self.dest / NAMES[1]).rename(self.base / "removed-aplus")
        errors = verify(self.dest)
        self.assertTrue(any(NAMES[1] in e and "Missing" in e for e in errors), errors)

    def test_missing_reference_is_detected(self):
        install(self.dest)
        target = self.dest / NAMES[0] / "references/01-recon-and-fact-ledger.md"
        target.rename(self.base / "removed-reference.md")
        errors = verify(self.dest)
        self.assertTrue(any("01-recon-and-fact-ledger.md" in e for e in errors), errors)

    def test_corrupt_asset_is_detected(self):
        install(self.dest)
        target = self.dest / NAMES[1] / "assets/full-width-report-shell.html"
        target.write_text("damaged synthetic test", encoding="utf-8")
        self.assertTrue(any("SHA-256 mismatch" in e for e in verify(self.dest)))

    def test_existing_target_refuses_before_installing_others(self):
        existing = self.dest / NAMES[0]
        existing.mkdir(parents=True)
        (existing / "user-note.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Nothing changed"):
            install(self.dest)
        self.assertEqual(list(self.dest.iterdir()), [existing])
        self.assertEqual((existing / "user-note.txt").read_text(), "preserve")

    def test_replace_backs_up_old_clone_and_preserves_other_skills(self):
        old = self.dest / NAMES[0]
        (old / ".git").mkdir(parents=True)
        (old / ".git/config").write_text("synthetic old clone", encoding="utf-8")
        (old / "user-note.txt").write_text("my changes", encoding="utf-8")
        other = self.dest / "unrelated-skill"
        other.mkdir()
        (other / "note.txt").write_text("unrelated", encoding="utf-8")
        backup = install(self.dest, replace=True)
        self.assertEqual((backup / NAMES[0] / "user-note.txt").read_text(), "my changes")
        self.assertTrue((backup / NAMES[0] / ".git/config").is_file())
        self.assertEqual((other / "note.txt").read_text(), "unrelated")
        self.assertEqual(verify(self.dest), [])

    def test_mid_install_error_restores_old_directories(self):
        install(self.dest)
        old_file = self.dest / NAMES[0] / "user-note.txt"
        old_file.write_text("keep after failure", encoding="utf-8")
        rename = Path.rename
        def failing_rename(source, target):
            if source.name == NAMES[1] and source.parent.name.startswith("amazon-skills-stage-"):
                raise OSError("injected disk error")
            return rename(source, target)
        with patch.object(Path, "rename", failing_rename):
            with self.assertRaisesRegex(OSError, "injected"):
                install(self.dest, replace=True)
        self.assertEqual(old_file.read_text(), "keep after failure")
        for name in NAMES:
            self.assertTrue((self.dest / name / "SKILL.md").is_file())

    def test_symlink_target_refused(self):
        self.dest.mkdir()
        other = self.base / "outside"
        other.mkdir()
        (self.dest / NAMES[0]).symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            install(self.dest, replace=True)
        self.assertEqual(list(other.iterdir()), [])

    def test_user_interrupt_restores_previous_installation(self):
        install(self.dest)
        rename = Path.rename
        def interrupted_rename(source, target):
            if source.name == NAMES[1] and source.parent.name.startswith("amazon-skills-stage-"):
                raise KeyboardInterrupt()
            return rename(source, target)
        with patch.object(Path, "rename", interrupted_rename):
            with self.assertRaises(KeyboardInterrupt):
                install(self.dest, replace=True)
        self.assertEqual(verify(self.dest), [])


if __name__ == "__main__":
    unittest.main()
