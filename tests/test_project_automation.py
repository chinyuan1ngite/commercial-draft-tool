import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile


ROOT = Path(__file__).parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_repository_versions_match(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_version.py")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn((ROOT / "VERSION").read_text(encoding="utf-8").strip(), result.stdout)


class ReleaseVerificationTests(unittest.TestCase):
    version = "9.8.7"

    def _archive(self, folder: Path, extra: dict[str, bytes] | None = None) -> Path:
        executable = b"synthetic executable"
        files = {
            "Commercial1688DraftTool.exe": executable,
            "VERSION": self.version.encode(),
            "README.md": b"readme",
            "CHANGELOG.md": b"changelog",
            "SHA256SUMS.txt": (
                hashlib.sha256(executable).hexdigest().upper()
                + "  Commercial1688DraftTool.exe\n"
            ).encode("ascii"),
            "docs/操作说明.md": b"manual",
            "docs/环境配置.md": b"environment",
            "docs/compatibility.md": b"compatibility",
            f"docs/版本说明-{self.version}.md": b"release notes",
        }
        files.update(extra or {})
        archive = folder / "release.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for name, content in files.items():
                zipped.writestr(name, content)
        return archive

    def _run(self, archive: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_release.py"),
                "--archive",
                str(archive),
                "--expected-version",
                self.version,
                "--output",
                str(output),
                "--skip-executable-smoke",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_synthetic_release_structure_and_hash_pass(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            output = folder / "verification.json"
            result = self._run(self._archive(folder), output)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["version"], self.version)
            self.assertEqual(summary["crc"], "passed")
            self.assertEqual(summary["smoke"], "skipped")

    def test_archive_with_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            result = self._run(self._archive(folder, {"../secret.txt": b"secret"}), folder / "result.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe archive path", result.stderr)

    def test_archive_with_runtime_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            result = self._run(self._archive(folder, {"profiles/Default/Cookies": b"cookie"}), folder / "result.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime/private directory", result.stderr)

    def test_archive_with_windows_alternate_stream_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            result = self._run(self._archive(folder, {"README.md:secret": b"secret"}), folder / "result.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe Windows archive path", result.stderr)


if __name__ == "__main__":
    unittest.main()
