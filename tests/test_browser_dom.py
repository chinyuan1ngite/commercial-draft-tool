"""Opt-in browser regressions: set DRAFT_BROWSER_TESTS=1 to run in isolated Chrome."""
import json
import os
from pathlib import Path
import shutil
import unittest
from urllib.parse import quote

from DrissionPage import ChromiumOptions, ChromiumPage

from draft_tool.browser_actions import add_sale_dimensions, fill_sku_rows


@unittest.skipUnless(os.environ.get("DRAFT_BROWSER_TESTS") == "1", "set DRAFT_BROWSER_TESTS=1")
class BrowserDomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("CHROME_BINARY") or shutil.which("chrome")
        if not binary:
            binary = str(Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) /
                         "Google/Chrome/Application/chrome.exe")
        cls.page = ChromiumPage(ChromiumOptions().set_browser_path(binary).auto_port().headless())

    @classmethod
    def tearDownClass(cls):
        cls.page.quit()

    def load(self, html):
        self.page.get("data:text/html;charset=utf-8," + quote(html))

    def sale_form(self, dimensions, placeholders=None, delay=0):
        self.load((Path(__file__).parent / "fixtures/sale-properties.html").read_text(encoding="utf-8"))
        self.page.run_js("window.setup(...JSON.parse(arguments[0]));",
                         json.dumps([dimensions, placeholders, delay]))

    def test_two_dimensions_commit_four_values(self):
        self.sale_form(["Color", "Size"])
        model = {"dimensions": [{"name": "Color", "values": ["red", "blue"]},
                                {"name": "Size", "values": ["small", "large"]}]}
        result = add_sale_dimensions(self.page, model)
        self.assertEqual(result["status"], "filled", result)
        self.assertEqual(result["accepted_values"], 4)
        self.assertEqual(self.page.run_js("return window.combinations"),
                         [["red", "small"], ["red", "large"],
                          ["blue", "small"], ["blue", "large"]])

    def test_reordered_dimensions_with_equal_values_and_placeholders_are_idempotent(self):
        self.sale_form(["Size", "Color"], ["Choose", "Choose"], delay=100)
        model = {"dimensions": [{"name": "Color", "values": ["x", "y"]},
                                {"name": "Size", "values": ["y", "z"]}]}
        first = add_sale_dimensions(self.page, model)
        second = add_sale_dimensions(self.page, model)
        self.assertEqual((first["status"], second["status"]), ("filled", "filled"))
        self.assertEqual(second["accepted_values"], 4)
        self.assertEqual(self.page.run_js("return window.combinations"),
                         [["y", "x"], ["y", "y"], ["z", "x"], ["z", "y"]])

    def test_ambiguous_dimensions_do_not_write(self):
        self.sale_form(["Color", "Color"])
        result = add_sale_dimensions(self.page, {"dimensions": [{"name": "Color", "values": ["red"]}]})
        self.assertEqual(result["status"], "unsupported")
        self.assertEqual(self.page.run_js("return [...document.querySelectorAll('input')].some(i => i.value)"), False)

    def test_single_dimension_rejects_conflicting_prefill(self):
        self.sale_form(["Color"])
        self.assertEqual(add_sale_dimensions(self.page, {"dimensions": [{"name": "Color", "values": ["red"]}]})["status"], "filled")
        result = add_sale_dimensions(self.page, {"dimensions": [{"name": "Color", "values": ["blue"]}]})
        self.assertEqual(result["status"], "partial")

    def test_generated_rows_keep_prices_and_stock_after_reorder(self):
        self.sale_form(["Color"])
        model = {"dimensions": [{"name": "Color", "values": ["red", "blue"]}]}
        self.assertEqual(add_sale_dimensions(self.page, model)["status"], "filled")
        self.page.run_js("const rows=document.querySelector('#rows'); rows.replaceChildren(...[...rows.children].reverse());")
        fill_sku_rows(self.page, [
            {"sku_id": "A", "properties": {"Color": "red"}, "price": 10, "stock": 2},
            {"sku_id": "B", "properties": {"Color": "blue"}, "price": 20, "stock": 3},
        ])
        self.assertEqual(self.page.run_js("return [...document.querySelectorAll('#rows tr')].map(r=>[...r.querySelectorAll('input')].map(i=>i.value))"),
                         [["20", "3", "B"], ["10", "2", "A"]])

    def test_named_two_dimensional_rows_keep_their_prices(self):
        self.sale_form(["Size", "Color"], ["Choose", "Choose"])
        model = {"dimensions": [{"name": "Color", "values": ["x", "y"]},
                                {"name": "Size", "values": ["x", "y"]}]}
        self.assertEqual(add_sale_dimensions(self.page, model)["status"], "filled")
        self.page.run_js("const rows=document.querySelector('#rows'); rows.replaceChildren(...[...rows.children].reverse());")
        fill_sku_rows(self.page, [
            {"sku_id": "A", "properties": {"Color": "x", "Size": "x"}, "price": 10, "stock": 1},
            {"sku_id": "B", "properties": {"Color": "x", "Size": "y"}, "price": 20, "stock": 2},
            {"sku_id": "C", "properties": {"Color": "y", "Size": "x"}, "price": 30, "stock": 3},
            {"sku_id": "D", "properties": {"Color": "y", "Size": "y"}, "price": 40, "stock": 4},
        ])
        self.assertEqual(self.page.run_js("return [...document.querySelectorAll('#rows tr')].map(r=>[...r.querySelectorAll('input')].map(i=>i.value))"),
                         [["40", "4", "D"], ["20", "2", "B"], ["30", "3", "C"], ["10", "1", "A"]])


if __name__ == "__main__":
    unittest.main()
