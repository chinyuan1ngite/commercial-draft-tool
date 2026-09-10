"""Opt-in browser regressions: set DRAFT_BROWSER_TESTS=1 to run in isolated Chrome."""
import json
import os
from pathlib import Path
import shutil
import unittest
from urllib.parse import quote

from DrissionPage import ChromiumOptions, ChromiumPage

from draft_tool.browser_actions import add_sale_dimensions, fill_package_weights, fill_prop, fill_sku_rows, selected_prop_value


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

    def test_search_text_without_committed_option_is_not_success(self):
        self.load('''<div id="guid-title"><input></div>
          <div cat-prop-id="material" cat-prop-type="select">
            <div class="next-select-trigger next-has-search">
              <span class="next-select-values"></span><input placeholder="Search">
            </div>
          </div>''')
        self.assertFalse(fill_prop(self.page, "material", "ABS"))
        self.assertEqual(selected_prop_value(self.page, "material"), "")

    def test_async_enum_commits_option_and_excludes_search_mirror(self):
        self.load('''<div id="guid-title"><input></div>
          <div cat-prop-id="material" cat-prop-type="select">
            <div class="next-select-trigger next-has-search"><span class="next-select-values">
              <em id="chosen"></em><span class="next-select-trigger-search"><input placeholder="Search">
                <span aria-hidden="true">ABBA</span></span>
            </span></div>
          </div><div role="option" id="option" style="display:none">ABBA</div>
          <script>
            document.querySelector('input[placeholder]').addEventListener('input', () =>
              setTimeout(() => document.querySelector('#option').style.display='block', 100));
            document.querySelector('#option').onclick = () => {
              document.querySelector('#chosen').textContent='ABBA';
              document.querySelector('input[placeholder]').value='';
              document.querySelector('#option').style.display='none';
            };
          </script>''')
        self.assertTrue(fill_prop(self.page, "material", "ABBA"))
        self.assertEqual(selected_prop_value(self.page, "material"), "ABBA")
        self.assertEqual(self.page.run_js("return document.querySelector('#chosen').textContent"), "ABBA")

    def test_plain_text_and_textarea_commit_without_enum_search(self):
        for tag in ("input", "textarea"):
            with self.subTest(tag=tag):
                self.load(f'<div id="guid-title"><input></div><div cat-prop-id="code" cat-prop-type="{tag}"><{tag}></{tag}></div>')
                self.assertTrue(fill_prop(self.page, "code", "11223344"))
                self.assertEqual(selected_prop_value(self.page, "code"), "11223344")

    def test_multi_select_removes_old_values_and_commits_requested_tags(self):
        self.load('''<div id="guid-title"><input></div>
          <div cat-prop-id="features" cat-prop-type="multiselect">
            <div class="next-select-trigger next-select-tag"><input>
              <span class="next-tag"><span class="next-tag-body">old</span>
                <button class="next-tag-close-btn" onclick="this.parentNode.remove()">close</button></span>
            </div>
          </div><div role="option">red</div><div role="option">blue</div>
          <script>document.querySelectorAll('[role=option]').forEach(option => option.onclick = () => {
            const tag=document.createElement('span'); tag.className='next-tag-body'; tag.textContent=option.textContent;
            document.querySelector('.next-select-trigger').append(tag);
          });</script>''')
        self.assertTrue(fill_prop(self.page, "features", "red,blue"))
        self.assertEqual(selected_prop_value(self.page, "features"), "red,blue")

    def test_custom_attribute_commits_after_blur(self):
        self.load('''<div id="guid-title"><input></div>
          <div cat-prop-id="custom" cat-prop-type="select"><div class="next-select-trigger next-has-search">
            <span class="next-select-values"> <span class="next-select-trigger-search">
              <input placeholder="如无合适选项可直接输入填写"></span> </span>
          </div></div>''')
        self.assertTrue(fill_prop(self.page, "custom", "ABBA"))
        self.assertEqual(selected_prop_value(self.page, "custom"), "ABBA")

    def logistics_form(self, headers, rows):
        from html import escape
        heading = ''.join('<th>' + escape(name) + '</th>' for name in headers)
        body = ''.join('<tr>' + ''.join('<td class="sku-field-prop">'+escape(value)+'</td>' for value in row) +
                       '<td><input></td><td><input></td><td><input></td><td><input placeholder="weight" oninput="this.setAttribute(\'value\',this.value)"></td></tr>' for row in rows)
        self.load('<div id="guid-title"><input></div><div id="guid-officialLogistics"><table><thead><tr>'+heading+
                  '</tr></thead><tbody>'+body+'</tbody></table></div>')

    def test_weights_follow_named_dimensions_not_column_order(self):
        self.logistics_form(['Second', 'First'], [['y','x'], ['x','y']])
        result = fill_package_weights(self.page, [{'sku_id':'A','weight_grams':100}, {'sku_id':'B','weight_grams':200}], source_skus=[
            {'sku_id':'A','properties':{'First':'x','Second':'y'}},
            {'sku_id':'B','properties':{'First':'y','Second':'x'}},
        ])
        self.assertEqual(result['status'], 'filled', result)
        self.assertEqual(self.page.run_js("return [...document.querySelectorAll('input[placeholder=weight]')].map(i=>i.value)"), ['100','200'])

    def test_missing_weight_uses_fallback_and_reopen_verifies_identity(self):
        self.logistics_form(['Color'], [['red'], ['blue'], ['green']])
        weights = [{'sku_id':'A','weight_grams':300}, {'sku_id':'B','weight_grams':500}]
        skus = [{'sku_id':identity,'properties':{'Color':color}}
                for identity,color in [('A','red'),('B','blue'),('C','green')]]
        result = fill_package_weights(self.page, weights, source_skus=skus)
        self.assertEqual(result['status'], 'filled', result)
        self.assertEqual(result['expected_weights'], [300,500,1000])
        self.assertEqual(result['expected_rows'][2]['source'], 'default')
        result = fill_package_weights(self.page, weights, 1500, source_skus=skus)
        self.assertEqual(result['expected_weights'], [300,500,1500])
        self.page.run_js("const body=document.querySelector('tbody'); body.replaceChildren(...[...body.children].reverse());")
        self.assertEqual(fill_package_weights(self.page, weights, 1500, source_skus=skus, verify_only=True)['status'], 'filled')
        self.page.run_js("const input=document.querySelector('input[placeholder=weight]'); input.value='300'; input.setAttribute('value','300');")
        self.assertEqual(fill_package_weights(self.page, weights, 1500, source_skus=skus, verify_only=True)['status'], 'partial')
        self.assertEqual(self.page.run_js("return document.querySelector('input[placeholder=weight]').value"), '300')

    def test_ambiguous_weights_do_not_write(self):
        self.logistics_form(['Color'], [['same'], ['same']])
        result = fill_package_weights(self.page, [{'sku_id':'A','weight_grams':100}, {'sku_id':'B','weight_grams':200}],
                                      source_skus=[{'sku_id':sid,'properties':{'Color':'same'}} for sid in ['A','B']])
        self.assertEqual(result['status'], 'mapping_ambiguous')
        self.assertEqual(self.page.run_js("return [...document.querySelectorAll('input[placeholder=weight]')].map(i=>i.value)"), ['',''])

    def test_fully_missing_weights_use_uniform_default(self):
        self.logistics_form(['Color'], [['red'], ['blue']])
        result=fill_package_weights(self.page, [])
        self.assertEqual(result['status'], 'filled')
        self.assertEqual(result['expected_weights'], [1000,1000])

    def test_conflicting_source_weights_are_rejected(self):
        self.logistics_form(['Color'], [['red']])
        result=fill_package_weights(self.page, [{'sku_id':'A','weight_grams':100}, {'sku_id':'A','weight_grams':200}],
                                    source_skus=[{'sku_id':'A','properties':{'Color':'red'}}])
        self.assertEqual(result['status'], 'mapping_ambiguous')


if __name__ == "__main__":
    unittest.main()
