import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from draft_tool.collector import (
    _normalize_sku_name,
    _navigate_with_alert_recovery,
    is_product_image,
    parse_attributes,
    parse_embedded_skus,
    parse_images,
    parse_package_weights,
)
from draft_tool.security import DraftLedger, hostname_allowed, profile_lock


class SecurityAndCollectorTests(unittest.TestCase):
    def test_navigation_recovers_from_pending_alert(self):
        class PendingAlertPage:
            def __init__(self):
                self.attempts = 0
                self.alerts = 0

            def handle_alert(self, accept=True, timeout=0.5):
                self.alerts += 1
                if self.alerts == 1:
                    return "旧页面提示"
                raise RuntimeError("no alert")

            def get(self, url):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("AlertExistsError: 存在未处理的提示框")

        page = PendingAlertPage()
        self.assertEqual(_navigate_with_alert_recovery(page, "https://detail.1688.com/offer/1.html"), None)
        self.assertEqual(page.attempts, 2)

    def test_sku_name_cleanup_keeps_embedded_color_word(self):
        self.assertEqual(_normalize_sku_name("颜色 红色"), "红色")
        self.assertEqual(_normalize_sku_name("颜色随机款"), "颜色随机款")
        self.assertEqual(_normalize_sku_name("大沙车5件套（颜色随机）"), "大沙车5件套（颜色随机）")

    def test_hostname_validation_is_exact_and_https_only(self):
        self.assertTrue(hostname_allowed("https://cbu01.alicdn.com/a.jpg"))
        self.assertFalse(hostname_allowed("http://cbu01.alicdn.com/a.jpg"))
        self.assertFalse(hostname_allowed("https://alicdn.com.evil.test/a.jpg"))
        self.assertFalse(is_product_image("http://127.0.0.1/alicdn.com/private.jpg"))

    def test_only_structured_gallery_is_collected(self):
        html = '''<html><img src="https://cbu01.alicdn.com/tracker.jpg">
        <script>window.x={"mainImage":["https://cbu01.alicdn.com/product.jpg"]};</script></html>'''
        result = parse_images(BeautifulSoup(html, "html.parser"), html)
        self.assertEqual(result, ["https://cbu01.alicdn.com/product.jpg"])

    def test_unstructured_images_are_not_guessed(self):
        html = '<html><img src="https://cbu01.alicdn.com/untrusted.jpg"></html>'
        self.assertEqual(parse_images(BeautifulSoup(html, "html.parser"), html), [])

    def test_structured_decision_attributes_are_collected(self):
        html = '''<html><div class="decision-attributes-list">
          <li><p>材质</p><p>塑料/塑胶</p></li>
          <li><p>功能</p><p>益智</p></li>
          <li><p>包装方式</p><p>网袋</p></li>
        </div></html>'''
        attrs = parse_attributes(BeautifulSoup(html, "html.parser"))
        self.assertEqual(attrs["材质"], "塑料/塑胶")
        self.assertEqual(attrs["功能"], "益智")
        self.assertEqual(attrs["包装方式"], "网袋")

    def test_legacy_material_label_is_canonicalized(self):
        html = '''<html><h1>商品属性</h1><table><tr><th>玩具材质</th><td>塑胶</td></tr></table></html>'''
        attrs = parse_attributes(BeautifulSoup(html, "html.parser"))
        self.assertEqual(attrs["玩具材质"], "塑胶")
        self.assertEqual(attrs["材质"], "塑胶")

    def test_package_weights_are_collected_with_sku_mapping(self):
        html = '<script>window.x={"pieceWeightScaleInfo":[{"skuId": "9", "weight": 420}, {"weight": 0}]}</script>'
        self.assertEqual(parse_package_weights(html), [{"weight_grams": 420, "source": "collected", "sku_id": "9"}])

    def test_package_weights_decode_html_escaped_embedded_payload(self):
        html = '<script>window.x={&quot;pieceWeightScaleInfo&quot;:[{&quot;skuId&quot;:&quot;9&quot;,&quot;weight&quot;:420}]}</script>'
        self.assertEqual(parse_package_weights(html), [{"weight_grams": 420, "source": "collected", "sku_id": "9"}])

    def test_package_weight_defaults_when_source_is_missing(self):
        self.assertEqual(parse_package_weights("<html></html>"), [])

    def test_package_weights_accept_nested_payload_after_embedded_array(self):
        html = '<script>window.x={"pieceWeightScaleInfo":[{"skuId":"9","weight":420}],"other":[1,2]}</script>'
        self.assertEqual(parse_package_weights(html), [{"weight_grams": 420, "source": "collected", "sku_id": "9"}])

    def test_package_weights_reject_fractional_values(self):
        html = '<script>window.x={"pieceWeightScaleInfo":[{"skuId":"9","weight":420.5}]}</script>'
        self.assertEqual(parse_package_weights(html), [])

    def test_embedded_skus_keep_individual_prices(self):
        html = '<script>window.x={"skuMap":[{"skuId":"1","specAttrs":"红","canBookCount":3,"price":"5.20"},{"skuId":"2","specAttrs":"蓝","canBookCount":4,"price":"12.60"}]}</script>'
        skus = parse_embedded_skus(html, default_price=1.9)
        self.assertEqual([item["price"] for item in skus], [5.2, 12.6])

    def test_embedded_skus_read_prices_from_sku_info_map(self):
        html = '<script>window.x={"skuMap":[{"skuId":"1","specAttrs":"红","canBookCount":3},{"skuId":"2","specAttrs":"蓝","canBookCount":4}],"skuInfoMap":{"红":{"skuId":1,"price":"5.20"},"蓝":{"skuId":2,"discountPrice":"12.60"}}}</script>'
        skus = parse_embedded_skus(html, default_price=1.9)
        self.assertEqual([item["price"] for item in skus], [5.2, 12.6])

    def test_multi_sku_missing_price_is_not_replaced_by_product_price(self):
        html = '<script>window.x={"skuMap":[{"skuId":"1","specAttrs":"红","canBookCount":3,"price":"5.20"},{"skuId":"2","specAttrs":"蓝","canBookCount":4}]}</script>'
        skus = parse_embedded_skus(html, default_price=1.9)
        self.assertEqual([item["price"] for item in skus], [5.2, None])

    def test_escaped_sku_info_map_and_invalid_stock_are_handled(self):
        html = '<script>window.x={&quot;skuMap&quot;:[{&quot;skuId&quot;:&quot;1&quot;,&quot;specAttrs&quot;:&quot;红&quot;,&quot;canBookCount&quot;:3}],&quot;skuInfoMap&quot;:{&quot;red&quot;:{&quot;skuId&quot;:1,&quot;price&quot;:&quot;5.20&quot;}}}</script>'
        self.assertEqual(parse_embedded_skus(html)[0]["price"], 5.2)
        invalid_stock = '<script>window.x={"skuMap":[{"skuId":"1","specAttrs":"红","canBookCount":1.5}]}</script>'
        self.assertEqual(parse_embedded_skus(invalid_stock), [])

    def test_ledger_key_is_store_and_offer(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = DraftLedger(Path(folder) / "ledger.sqlite3")
            ledger.put("店铺甲", "100", "D1", Path(folder) / "run")
            self.assertEqual(ledger.get("店铺甲", "100")["draft_id"], "D1")
            self.assertIsNone(ledger.get("店铺乙", "100"))
            self.assertIsNone(ledger.get("店铺甲", "101"))

    def test_profile_lock_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder)
            with profile_lock(profile):
                with self.assertRaises(RuntimeError):
                    with profile_lock(profile):
                        pass


if __name__ == "__main__":
    unittest.main()
