import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from draft_tool.config import QualityConfig, TargetConfig
from draft_tool.quality_gate import validate_product


class QualityGateTests(unittest.TestCase):
    def make_product(self, root: Path) -> Path:
        main = root / "main.jpg"
        detail = root / "detail.jpg"
        Image.new("RGB", (800, 800), "white").save(main)
        Image.new("RGB", (800, 800), "white").save(detail)
        product = {
            "source": {"offer_id": "123456789"},
            "title": "合格商品标题",
            "validation": {"passed": True},
            "price": {"primary": 10},
            "stock": {"total_observed": 3},
            "assets": [{"status": "saved", "path": str(main)}],
            "detail_assets": [{"status": "saved", "path": str(detail)}],
            "skus": [{"sku_id": "1", "name": "白色", "properties": {"颜色": "白色"}, "price": 10, "stock": 3}],
        }
        path = root / "product.json"
        path.write_text(json.dumps(product, ensure_ascii=False), encoding="utf-8")
        return path

    def target(self) -> TargetConfig:
        return TargetConfig("100", "玩具", "测试店铺", "测试地址", "默认运费模板", "48小时发货", 1000)

    def test_valid_product_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            result = validate_product(self.make_product(Path(folder)), self.target(), QualityConfig())
            self.assertTrue(result["passed"], result["issues"])

    def test_missing_runtime_configuration_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            result = validate_product(self.make_product(Path(folder)), TargetConfig(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertIn("未确认目标叶子类目 category_id", result["issues"])

    def test_long_title_is_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_product(Path(folder))
            product = json.loads(path.read_text(encoding="utf-8"))
            product["title"] = "长" * 61
            path.write_text(json.dumps(product, ensure_ascii=False), encoding="utf-8")
            result = validate_product(path, self.target(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertTrue(any("禁止静默截断" in item for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()
