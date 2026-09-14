import importlib
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]


class Alibaba1688NamespaceTests(unittest.TestCase):
    def test_legacy_modules_alias_canonical_implementations(self):
        names = (
            "collector",
            "browser_actions",
            "browser_navigation",
            "category_capture",
        )
        for name in names:
            with self.subTest(name=name):
                legacy = importlib.import_module(f"draft_tool.{name}")
                canonical = importlib.import_module(f"draft_tool.platforms.alibaba1688.{name}")
                self.assertIs(legacy, canonical)

    def test_legacy_patch_paths_modify_the_canonical_module(self):
        collector = importlib.import_module("draft_tool.platforms.alibaba1688.collector")
        marker = object()
        with patch("draft_tool.collector.download_image", marker):
            self.assertIs(collector.download_image, marker)

        browser_actions = importlib.import_module("draft_tool.platforms.alibaba1688.browser_actions")
        with patch("draft_tool.browser_actions.ChromiumPage", marker):
            self.assertIs(browser_actions.ChromiumPage, marker)

    def test_legacy_collector_module_entry_point_remains_available(self):
        result = subprocess.run(
            [sys.executable, "-m", "draft_tool.collector", "--help"],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--source-url", result.stdout)


if __name__ == "__main__":
    unittest.main()
