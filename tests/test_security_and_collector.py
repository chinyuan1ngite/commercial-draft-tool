import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from draft_tool.collector import is_product_image, parse_images
from draft_tool.security import DraftLedger, hostname_allowed, profile_lock


class SecurityAndCollectorTests(unittest.TestCase):
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
