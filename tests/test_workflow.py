import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from draft_tool.config import AppConfig, TargetConfig
from draft_tool.workflow import run_save_draft


class WorkflowTests(unittest.TestCase):
    def test_optional_logistics_arguments_are_omitted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            product_path = root / "product.json"
            product_path.write_text("{}", encoding="utf-8")
            config = AppConfig(
                target=TargetConfig(category_id="100", store_identity_text="测试店铺"),
                profile_dir=root / "seller-profile",
                output_root=root / "drafts",
            )
            gate = {"passed": True, "issues": [], "warnings": [], "summary": {"offer_id": "123"}}
            captured: list[str] = []

            def browser_main(argv: list[str]) -> int:
                captured.extend(argv)
                return 0

            with (
                patch("draft_tool.workflow.validate_product", return_value=gate),
                patch("draft_tool.workflow.write_runtime_product", return_value=product_path),
                patch("draft_tool.browser_actions.main", side_effect=browser_main),
            ):
                result = run_save_draft(
                    product_path, config, config.target, root / "run", preview_only=True
                )

            self.assertEqual(result, 0)
            for option in (
                "--shipping-address",
                "--freight-template-text",
                "--delivery-promise",
                "--package-weight-grams",
            ):
                self.assertNotIn(option, captured)
            self.assertIn("--store-identity-text", captured)
            self.assertNotIn("None", captured)


if __name__ == "__main__":
    unittest.main()
