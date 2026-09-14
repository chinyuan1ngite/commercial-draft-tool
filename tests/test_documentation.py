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
        markdown_files.extend((root / ".github").rglob("*.md"))
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

    def test_github_collaboration_files_are_present_and_least_privilege(self):
        root = Path(__file__).parents[1]
        required = [
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/platform_feature.yml",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/pull_request_template.md",
            ".github/workflows/ci.yml",
            ".github/workflows/browser-regression.yml",
            ".github/workflows/release-package.yml",
        ]
        missing = [name for name in required if not (root / name).is_file()]
        self.assertEqual(missing, [])
        for workflow in (root / ".github" / "workflows").glob("*.yml"):
            content = workflow.read_text(encoding="utf-8")
            self.assertIn("contents: read", content, workflow)
            self.assertNotIn("pull_request_target", content, workflow)


if __name__ == "__main__":
    unittest.main()
