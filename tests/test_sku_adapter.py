import unittest

from draft_tool.sku_adapter import normalize_sku_model, validate_target_rows


class SkuAdapterTests(unittest.TestCase):
    def test_fallback_single_dimension_is_conservative(self):
        model = normalize_sku_model([
            {"sku_id": "1", "name": "红色>现货", "price": 8, "stock": 3},
            {"sku_id": "2", "name": "蓝色>现货", "price": 9, "stock": 4},
        ])
        self.assertEqual(model["mode"], "single")
        self.assertEqual(model["dimensions"][0]["name"], "规格")

    def test_drops_uniform_placeholder_dimension(self):
        rows = [
            {"properties": {"颜色": "红色", "规格": "无规格"}, "price": 1, "stock": 2},
            {"properties": {"颜色": "蓝色", "规格": "无规格"}, "price": 1, "stock": 3},
        ]
        model = normalize_sku_model(rows)
        self.assertEqual([item["name"] for item in model["dimensions"]], ["颜色"])
        self.assertTrue(all(list(row["properties"]) == ["颜色"] for row in model["rows"]))
        self.assertTrue(any("占位规格" in warning for warning in model["warnings"]))
        self.assertEqual(model["dimensions"][0]["values"], ["红色", "蓝色"])
        self.assertEqual(model["rows"][0]["properties"], {"颜色": "红色"})

    def test_preserves_complete_multi_dimension_matrix(self):
        model = normalize_sku_model([
            {"sku_id": "1", "name": "红-L", "properties": {"颜色": "红", "尺寸": "L"}, "price": 8, "stock": 3},
            {"sku_id": "2", "name": "蓝-M", "properties": {"颜色": "蓝", "尺寸": "M"}, "price": 9, "stock": 4},
        ])
        self.assertEqual(model["mode"], "multi")
        self.assertEqual([item["name"] for item in model["dimensions"]], ["颜色", "尺寸"])
        self.assertTrue(model["valid"])

    def test_rejects_duplicate_and_missing_target_rows(self):
        model = normalize_sku_model([
            {"sku_id": "1", "name": "红", "properties": {"颜色": "红"}, "price": 8, "stock": 3},
            {"sku_id": "2", "name": "蓝", "properties": {"颜色": "蓝"}, "price": 9, "stock": 4},
        ])
        result = validate_target_rows(model, [
            {"properties": {"颜色": "红"}, "price": "8", "stock": "3"},
        ])
        self.assertFalse(result["valid"])
        self.assertIn("目标页面生成 1/2 个 SKU 行", result["issues"])

    def test_rejects_non_finite_fractional_and_overflow_values(self):
        for price, stock in (("nan", 1), ("Infinity", 1), (1, "1.2"), (1, 2_147_483_648)):
            with self.subTest(price=price, stock=stock):
                model = normalize_sku_model([{"name": "红", "price": price, "stock": stock}])
                self.assertFalse(model["valid"])

    def test_target_rows_must_exactly_match_values_and_sku_id(self):
        model = normalize_sku_model([{
            "sku_id": "SKU-1", "name": "红", "properties": {"颜色": "红"}, "price": "8.00", "stock": 3,
        }])
        valid = validate_target_rows(model, [{
            "sku_id": "SKU-1", "properties": {"颜色": "红"}, "price": "8", "stock": "3",
        }])
        self.assertTrue(valid["valid"], valid["issues"])
        invalid = validate_target_rows(model, [{
            "sku_id": "OTHER", "properties": {"颜色": "红"}, "price": "8.01", "stock": "4",
        }])
        self.assertFalse(invalid["valid"])
        self.assertEqual(len(invalid["issues"]), 3)

    def test_visible_merchant_code_does_not_stand_in_for_hidden_sku_identity(self):
        model = normalize_sku_model([{
            "sku_id": "SOURCE-1", "name": "红", "properties": {"颜色": "红"}, "price": 8, "stock": 3,
        }])
        result = validate_target_rows(model, [{
            "sku_id": "", "sku_identity_available": False,
            "properties": {"颜色": "红"}, "price": 8, "stock": 3,
        }])
        self.assertTrue(result["valid"], result["issues"])


if __name__ == "__main__":
    unittest.main()
