"""Opt-in browser regressions: set DRAFT_BROWSER_TESTS=1 to run in isolated Chrome."""
import json
import base64
import tempfile
from io import BytesIO
import os
from pathlib import Path
import shutil
import time
import unittest
from urllib.parse import quote

from DrissionPage import ChromiumOptions, ChromiumPage
from PIL import Image

from draft_tool.browser_actions import add_sale_dimensions, fill_package_weights, fill_prop, fill_sku_rows, selected_prop_value
from draft_tool.browser_navigation import PopupRecoveryError, dismiss_pending_alert, dismiss_unexpected_popups
from draft_tool.browser_actions import configure_sku_images, sku_image_block_reason, fill_legacy_description_editor, verify_sku_images


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
        self.page.wait.doc_loaded(timeout=5)
        time.sleep(.1)

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

    def test_unexpected_confirmation_is_cancelled(self):
        self.load('<html><body>dialog fixture</body></html>')
        self.page.run_js("setTimeout(()=>window.accepted=confirm('Discard changes?'),20)")
        time.sleep(.1)
        dismiss_unexpected_popups(self.page)
        self.assertIs(self.page.run_js('return window.accepted'), False)

    def test_empty_alert_and_prompt_are_dismissed_without_acceptance(self):
        self.load('<html><body>dialog fixture</body></html>')
        self.page.run_js("setTimeout(()=>{alert(''); window.answer=prompt(''); window.finished=true;},20)")
        time.sleep(.1)
        self.assertEqual(len(dismiss_unexpected_popups(self.page)), 2)
        self.assertIsNone(self.page.run_js('return window.answer'))
        self.assertIs(self.page.run_js('return window.finished'), True)

    def test_navigation_recovery_also_cancels_confirmation(self):
        self.load('<html><body>dialog fixture</body></html>')
        self.page.run_js("setTimeout(()=>window.accepted=confirm('discard'),20)")
        time.sleep(.1)
        dismiss_pending_alert(self.page)
        self.assertIs(self.page.run_js('return window.accepted'), False)

    def test_continuous_native_dialogs_fail_within_limit(self):
        self.load('<html><body>dialog fixture</body></html>')
        self.page.run_js("setTimeout(()=>{for(let i=0;i<4;i++) confirm('discard')},20)")
        time.sleep(.1)
        started=time.monotonic()
        try:
            with self.assertRaises(PopupRecoveryError):
                dismiss_unexpected_popups(self.page, max_native=2)
            self.assertLess(time.monotonic()-started, 4)
        finally:
            dismiss_unexpected_popups(self.page, max_native=5)

    def test_overlay_recovery_preserves_active_and_hidden_controls(self):
        self.load('''<div class="next-dialog"><button class="next-dialog-close" onclick="this.parentNode.remove()">close</button></div>
          <button class="ant-modal-close" style="display:none" onclick="window.hiddenClicked=true">hidden</button>
          <div class="ibank-picker-dialog"><button class="next-dialog-close" onclick="window.pickerClosed=true">picker</button></div>
          <div class="ant-modal"><iframe src="about:blank#schema"></iframe><button class="ant-modal-close" onclick="window.editorClosed=true">editor</button></div>''')
        self.assertEqual(dismiss_unexpected_popups(self.page), ['unrelated_overlays_closed:1'])
        self.assertEqual(self.page.run_js('return Boolean(window.hiddenClicked || window.pickerClosed || window.editorClosed)'), False)

    def test_optional_image_failure_allows_real_weight_and_detail_steps(self):
        self.load('''<div id="guid-title"><input></div><div id="guid-skuTable"><table data-codex-sku-table="1"><tbody>
          <tr data-sku-id="A"><td>No image control</td></tr></tbody></table></div>
          <div id="guid-officialLogistics"><table><thead><tr><th>Weight(g)</th></tr></thead>
          <tbody><tr><td><input></td><td><input></td><td><input></td><td><input placeholder="重量" oninput="this.setAttribute('value',this.value)"></td></tr></tbody></table></div>
          <iframe id="tinyMCE-0_ifr" srcdoc="<body contenteditable='true'></body>"></iframe>''')
        images = configure_sku_images(self.page, [{'sku_id':'A'}], {'A': Path('missing.jpg')})
        self.assertIsNone(sku_image_block_reason(images))
        self.assertEqual(sku_image_block_reason(images, required=True), 'blocked_sku_images_not_confirmed')
        weight = fill_package_weights(self.page, {}, 1000)
        detail = fill_legacy_description_editor(self.page, {'detail_text':'Fixture detail'})
        self.assertEqual(weight['status'], 'filled', weight)
        self.assertEqual(detail['preview'], 'Fixture detail', detail)
        self.assertEqual(self.page.get_frame('css:#tinyMCE-0_ifr').ele('tag:body').text, 'Fixture detail')

    def test_file_image_readback_reacquires_recreated_row(self):
        self.load('''<div id="guid-skuTable"><table data-codex-sku-table="1"><tbody>
          <tr data-sku-id="A"><td><input type="file" onchange="
            const reader=new FileReader(); reader.onload=()=>{const row=this.closest('tr').cloneNode(true);
            row.removeAttribute('data-codex-image-row'); const img=document.createElement('img');
            img.src=reader.result; row.append(img); this.closest('tr').replaceWith(row);};
            reader.readAsDataURL(this.files[0]);"></td></tr></tbody></table></div>''')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pixel.png'
            path.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7V0AAAAASUVORK5CYII='))
            result = configure_sku_images(self.page, [{'sku_id':'A'}], {'A':path})
        self.assertEqual(result['status'], 'confirmed', result)
        self.assertEqual(self.page.run_js('return document.querySelectorAll("tr img").length'), 1)

    def test_correct_existing_image_is_reused_without_upload(self):
        payload = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7V0AAAAASUVORK5CYII='
        self.load('''<div id="guid-skuTable"><table data-codex-sku-table="1"><tbody>
          <tr data-sku-id="A"><td><input type="file" onchange="window.uploaded=true"><img src="data:image/png;base64,'''+payload+'''"></td>
          </tr></tbody></table></div>''')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pixel.png'
            path.write_bytes(base64.b64decode(payload))
            result = configure_sku_images(self.page, [{'sku_id':'A'}], {'A':path})
        self.assertEqual(result['status'], 'confirmed', result)
        self.assertFalse(self.page.run_js('return Boolean(window.uploaded)'))

    def test_correct_existing_image_does_not_require_upload_control(self):
        data, correct = self.image_data('red')
        self.image_fixture({}, skus=['A'])
        self.page.run_js('window.commit("A",[arguments[0]]);document.querySelector("tr button").remove()', correct)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pixel.png'; path.write_bytes(data)
            result=configure_sku_images(self.page,[{'sku_id':'A'}],{'A':path})
        self.assertEqual(result['status'],'confirmed',result)
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'),[0,0])

    def image_fixture(self, options, records=None, skus=None):
        self.load((Path(__file__).parent / 'fixtures/sku-images.html').read_text(encoding='utf-8'))
        self.page.run_js('window.setup(...JSON.parse(arguments[0]))', json.dumps([options, records or [], skus or ['A']]))

    def image_data(self, color):
        buffer = BytesIO()
        Image.new('RGB', (2, 2), color).save(buffer, format='PNG')
        return buffer.getvalue(), 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')

    def test_picker_rejects_name_collisions_and_clears_stale_pool(self):
        data, correct = self.image_data('red')
        _, wrong = self.image_data('blue')
        old = {'title':'pixel.png', 'src':wrong, 'id':'old'}
        self.image_fixture({'staleSelection':old, 'staleCount':3, 'delay':100},
                           [old, {'title':'pixel.png-extra','src':wrong,'id':'prefix'}])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pixel.png'; path.write_bytes(data)
            first = configure_sku_images(self.page, [{'sku_id':'A'}], {'A':path})
            second = configure_sku_images(self.page, [{'sku_id':'A'}], {'A':path})
        self.assertEqual(first['status'], 'confirmed', first)
        self.assertEqual(second['status'], 'confirmed', second)
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'), [1,1])
        self.assertEqual(self.page.run_js('return document.querySelector("tr img").src'), correct)
        self.assertEqual(self.page.run_js('return document.querySelector("tr img").naturalWidth'), 2)
        self.assertEqual(self.page.run_js('return document.querySelectorAll(".ibank-picker-dialog").length'), 0)

    def test_picker_reuses_only_content_verified_album_image(self):
        data, correct = self.image_data('red')
        self.image_fixture({}, [{'title':'pixel.png','src':correct,'id':'known'}])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pixel.png'; path.write_bytes(data)
            result = configure_sku_images(self.page, [{'sku_id':'A'}], {'A':path})
        self.assertEqual(result['status'], 'confirmed', result)
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'), [0,1])

    def test_image_replacement_and_reopen_use_identity_not_counts(self):
        red, red_src = self.image_data('red'); blue, blue_src = self.image_data('blue')
        self.image_fixture({'direct':True, 'recreate':True}, skus=['B','A'])
        self.page.run_js('window.commit("B",[arguments[0]]);window.commit("A",[arguments[1]])', red_src, blue_src)
        # Restoring fixture handlers simulates the framework binding the rebuilt nodes.
        self.page.run_js('''document.querySelectorAll('input').forEach(input=>input.onchange=()=>{
          window.uploads++; const reader=new FileReader(); const sku=input.closest('tr').dataset.skuId;
          reader.onload=()=>commit(sku,[reader.result]); reader.readAsDataURL(input.files[0]);});''')
        sources = [{'sku_id':'A'}, {'sku_id':'B'}]
        with tempfile.TemporaryDirectory() as folder:
            red_path=Path(folder)/'red.png'; red_path.write_bytes(red)
            blue_path=Path(folder)/'blue.png'; blue_path.write_bytes(blue)
            result=configure_sku_images(self.page,sources,{'A':red_path,'B':blue_path})
        self.assertEqual(result['status'],'confirmed',result)
        self.page.run_js('const body=document.querySelector("tbody");body.append(body.firstElementChild)')
        self.assertTrue(verify_sku_images(self.page,sources,result)['verified'])
        self.page.run_js('const images=document.querySelectorAll("tr img");const first=images[0].src;images[0].src=images[1].src;images[1].src=first;')
        self.assertFalse(verify_sku_images(self.page,sources,result)['verified'])
        self.assertEqual(self.page.run_js('return document.querySelectorAll("tr img").length'),2)

    def test_old_upload_success_does_not_confirm_stalled_upload(self):
        data, _ = self.image_data('red')
        self.image_fixture({'stall':True, 'staleCount':9})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pixel.png'; path.write_bytes(data)
            result=configure_sku_images(self.page,[{'sku_id':'A'}],{'A':path})
        self.assertEqual(result['status'],'indeterminate',result)
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'),[1,0])
        self.assertEqual(sku_image_block_reason(result),'blocked_sku_image_transaction')

    def test_image_count_growth_with_wrong_content_is_not_confirmed(self):
        data, _ = self.image_data('red'); _, wrong = self.image_data('blue')
        self.image_fixture({'direct':True,'corrupt':wrong})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pixel.png'; path.write_bytes(data)
            result=configure_sku_images(self.page,[{'sku_id':'A'}],{'A':path})
        self.assertEqual(result['status'],'indeterminate',result)
        self.assertEqual(self.page.run_js('return document.querySelectorAll("tr img").length'),1)

    def test_picker_refuses_extra_pool_item_before_submit(self):
        data, correct = self.image_data('red'); _, wrong = self.image_data('blue')
        self.image_fixture({'extraSelection':{'title':'other','src':wrong}},
                           [{'title':'pixel.png','src':correct,'id':'known'}])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pixel.png'; path.write_bytes(data)
            result=configure_sku_images(self.page,[{'sku_id':'A'}],{'A':path})
        self.assertEqual(result['status'],'unsupported',result)
        self.assertEqual(result['failed'][0]['reason'],'selection_pool_identity_mismatch')
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'),[0,0])

    def test_picker_reuses_same_content_across_different_source_filenames(self):
        data, correct=self.image_data('red')
        self.image_fixture({},skus=['A','B'])
        with tempfile.TemporaryDirectory() as folder:
            first=Path(folder)/'first.png'; first.write_bytes(data)
            second=Path(folder)/'second.png'; second.write_bytes(data)
            result=configure_sku_images(self.page,[{'sku_id':'A'},{'sku_id':'B'}],{'A':first,'B':second})
        self.assertEqual(result['status'],'confirmed',result)
        self.assertEqual(self.page.run_js('return [window.uploads,window.commits]'),[1,2])
        self.assertEqual(self.page.run_js('return [...document.querySelectorAll("tr img")].map(e=>e.src)'),[correct,correct])


if __name__ == "__main__":
    unittest.main()
