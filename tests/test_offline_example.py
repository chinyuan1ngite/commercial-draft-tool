import json
from contextlib import redirect_stdout
from io import StringIO
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from draft_tool.config import AppConfig
from draft_tool.cli import main as cli_main
from draft_tool.quality_gate import validate_product


class OfflineExampleTests(unittest.TestCase):
    def test_generated_handover_example_has_one_clear_success_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "example"
            script = Path(__file__).parents[1] / "examples" / "make_offline_example.py"
            result = subprocess.run(
                [sys.executable, str(script), "--output-dir", str(output)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            config = AppConfig.from_file(output / "settings.example.json")
            valid_product = json.loads((output / "product.json").read_text(encoding="utf-8"))
            target = config.effective_target({}, valid_product["category"])
            valid = validate_product(output / "product.json", target, config.quality)
            invalid = validate_product(output / "product-invalid.json", target, config.quality)

            self.assertTrue(valid["passed"], valid)
            self.assertEqual(
                {key: valid["summary"][key] for key in ("main_images", "detail_images", "sku_count", "sku_images")},
                {"main_images": 1, "detail_images": 1, "sku_count": 2, "sku_images": 2},
            )
            self.assertFalse(invalid["passed"], invalid)
            self.assertEqual(invalid["issues"], ["缺少商品标题"])

            valid_output = StringIO()
            with redirect_stdout(valid_output):
                valid_exit = cli_main([
                    "--product", str(output / "product.json"),
                    "--config", str(output / "settings.example.json"),
                    "--validate-only",
                ])
            invalid_output = StringIO()
            with redirect_stdout(invalid_output):
                invalid_exit = cli_main([
                    "--product", str(output / "product-invalid.json"),
                    "--config", str(output / "settings.example.json"),
                    "--validate-only",
                ])

            self.assertEqual(valid_exit, 0)
            self.assertTrue(json.loads(valid_output.getvalue())["passed"])
            self.assertEqual(invalid_exit, 4)
            self.assertEqual(json.loads(invalid_output.getvalue())["issues"], ["缺少商品标题"])


if __name__ == "__main__":
    unittest.main()
