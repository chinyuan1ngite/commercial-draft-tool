import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links_resolve(self):
        root = Path(__file__).parents[1]
        markdown_files = [root / name for name in ("README.md", "CONTRIBUTING.md", "ROADMAP.md")]
        markdown_files.extend((root / "docs").rglob("*.md"))
        markdown_files.extend((root / "examples").rglob("*.md"))
        missing = []

        for document in markdown_files:
            text = document.read_text(encoding="utf-8")
            for raw_target in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", text):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or urlparse(target).scheme:
                    continue
                resolved = (document.parent / unquote(target)).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(root)} -> {raw_target}")

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
