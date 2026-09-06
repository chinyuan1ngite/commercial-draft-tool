import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from draft_tool.config import AppConfig
from draft_tool.runtime import initialize_runtime


class RuntimeTests(unittest.TestCase):
    def test_initializes_isolated_launcher_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"DRAFT_TOOL_HOME": folder}):
                paths = initialize_runtime()
            self.assertEqual(paths["root"], Path(folder).resolve())
            self.assertTrue(paths["buyer_profile"].is_dir())
            self.assertTrue(paths["seller_profile"].is_dir())
            self.assertNotEqual(paths["buyer_profile"], paths["seller_profile"])
            config = AppConfig.from_file(paths["config"])
            self.assertEqual(config.profile_dir, paths["seller_profile"])
            self.assertEqual(config.output_root, paths["drafts"])

    def test_does_not_overwrite_existing_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path = root / "config" / "settings.local.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text('{"sentinel": true}', encoding="utf-8")
            with patch.dict(os.environ, {"DRAFT_TOOL_HOME": folder}):
                initialize_runtime()
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), {"sentinel": True})


if __name__ == "__main__":
    unittest.main()
