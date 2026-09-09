import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from draft_tool.config import QualityConfig, TargetConfig
from draft_tool.config import AppConfig
from draft_tool.quality_gate import validate_product


class QualityGateTests(unittest.TestCase):
    def test_null_configured_weight_uses_unified_1000g_default(self):
        config = AppConfig(target=TargetConfig(store_identity_text="店铺", package_weight_grams=None))
        target = config.effective_target({}, {})
        self.assertEqual(target.package_weight_grams, 1000)

    def test_source_leaf_category_is_default_but_explicit_target_wins(self):
        config = AppConfig(target=TargetConfig(store_identity_text="店铺"))
        source = {"leaf_id": 123648007, "leaf_name": "戏水玩具"}
        target = config.effective_target({}, source)
        self.assertEqual(target.category_id, 123648007)
        self.assertEqual(target.category_name, "戏水玩具")
        explicit = config.effective_target({"category_id": "1045531", "category_name": "目标类目"}, source)
        self.assertEqual(explicit.category_id, "1045531")
        self.assertEqual(explicit.category_name, "目标类目")
        explicit_id_only = config.effective_target({"category_id": "1045531"}, source)
        self.assertEqual(explicit_id_only.category_id, "1045531")
        self.assertIsNone(explicit_id_only.category_name)

    def make_product(self, root: Path) -> Path:
        (root / "assets").mkdir()
        (root / "detail-assets").mkdir()
        main = root / "assets" / "main.jpg"
        detail = root / "detail-assets" / "detail.jpg"
        Image.new("RGB", (800, 800), "white").save(main)
        Image.new("RGB", (800, 800), "white").save(detail)
        product = {
            "source": {"offer_id": "123456789"},
            "title": "合格商品标题",
            "validation": {"passed": True},
            "price": {"primary": 10},
            "stock": {"total_observed": 3},
            "assets": [{"status": "saved", "path": "assets/main.jpg"}],
            "detail_assets": [{"status": "saved", "path": "detail-assets/detail.jpg"}],
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

    def test_optional_logistics_configuration_does_not_block(self):
        with tempfile.TemporaryDirectory() as folder:
            target = TargetConfig(
                category_id="100", category_name="玩具", store_identity_text="测试店铺"
            )
            result = validate_product(self.make_product(Path(folder)), target, QualityConfig())
            self.assertTrue(result["passed"], result["issues"])

    def test_long_title_is_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_product(Path(folder))
            product = json.loads(path.read_text(encoding="utf-8"))
            product["title"] = "长" * 61
            path.write_text(json.dumps(product, ensure_ascii=False), encoding="utf-8")
            result = validate_product(path, self.target(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertTrue(any("禁止静默截断" in item for item in result["issues"]))

    def test_absolute_and_traversal_asset_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.make_product(root)
            product = json.loads(path.read_text(encoding="utf-8"))
            product["assets"][0]["path"] = str((root / "assets" / "main.jpg").resolve())
            product["detail_assets"][0]["path"] = "../detail-assets/detail.jpg"
            path.write_text(json.dumps(product), encoding="utf-8")
            result = validate_product(path, self.target(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertTrue(any("路径越界" in issue for issue in result["issues"]))

    def test_nan_price_and_fractional_stock_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_product(Path(folder))
            product = json.loads(path.read_text(encoding="utf-8"))
            product["price"]["primary"] = "NaN"
            product["skus"][0]["stock"] = "1.5"
            path.write_text(json.dumps(product), encoding="utf-8")
            result = validate_product(path, self.target(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertIn("主价格必须大于 0", result["issues"])
            self.assertTrue(any("非法价格或库存" in issue for issue in result["issues"]))

    def test_whitespace_runtime_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = TargetConfig(" ", "玩具", " ", " ", " ", " ", 1)
            result = validate_product(self.make_product(Path(folder)), target, QualityConfig())
            self.assertFalse(result["passed"])
            self.assertIn("未确认目标叶子类目 category_id", result["issues"])

    def test_optional_missing_sku_image_warns_but_required_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_product(Path(folder))
            optional = validate_product(path, self.target(), QualityConfig(require_sku_images=False))
            self.assertTrue(optional["passed"], optional["issues"])
            self.assertTrue(any("缺少图片" in item for item in optional["warnings"]))
            required = validate_product(path, self.target(), QualityConfig(require_sku_images=True))
            self.assertFalse(required["passed"])
            self.assertTrue(any("SKU 图片不足" in item for item in required["issues"]))

    def test_malformed_media_manifest_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.make_product(Path(folder))
            product = json.loads(path.read_text(encoding="utf-8"))
            product["media_manifest"] = {"version": 99, "items": []}
            path.write_text(json.dumps(product), encoding="utf-8")
            result = validate_product(path, self.target(), QualityConfig())
            self.assertFalse(result["passed"])
            self.assertTrue(any("媒体清单版本" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
