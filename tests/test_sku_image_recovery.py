"""Faults at the browser boundary exercise the real image transaction."""
import unittest
import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from draft_tool.browser_actions import configure_sku_images


class SkuImageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'red.jpg'
        self.path.write_bytes(b'fixture image')
        self.src = 'data:image/png;base64,' + base64.b64encode(b'fixture image').decode('ascii')

    def browser(self):
        page = MagicMock()
        row = MagicMock()
        page.ele.return_value = row
        page.handle_alert.return_value = False
        def run_js(script, *args):
            if 'const table = ' in script:
                return [{"sku_id": "A", "properties": {"Color": "red"}, "row_token": "a"}]
            return script == 'return Boolean(document.documentElement)'
        page.run_js.side_effect = run_js
        row.eles.return_value = []
        row.run_js.return_value = []
        return page, row

    def configure(self, page):
        return configure_sku_images(page, [{"sku_id": "A", "properties": {"Color": "red"}}], {"A": self.path})

    def test_control_lookup_failure_is_recorded_and_later_sku_is_attempted(self):
        page = MagicMock()
        page.handle_alert.return_value = False
        rows = [MagicMock(), MagicMock()]
        rows[0].ele.side_effect = RuntimeError("control detached")
        rows[1].ele.return_value = None
        page.ele.side_effect = rows
        page.run_js.return_value = [
            {"sku_id": "A", "properties": {"Color": "red"}, "row_token": "a"},
            {"sku_id": "B", "properties": {"Color": "blue"}, "row_token": "b"},
        ]
        source = [{"sku_id": "A", "properties": {"Color": "red"}},
                  {"sku_id": "B", "properties": {"Color": "blue"}}]
        result = configure_sku_images(page, source, {"A": Path("red.jpg"), "B": Path("blue.jpg")}, rows)
        self.assertEqual([item["sku_id"] for item in result["failed"]], ["A", "B"])
        self.assertEqual(result["failed"][0]["stage"], "control_lookup")
        self.assertIn("control detached", result["failed"][0]["error"])
        self.assertTrue(result["safe_to_continue"])
        rows[1].ele.assert_called()

    def test_row_resolution_failure_is_reported(self):
        page, row = self.browser()
        page.run_js.side_effect = RuntimeError("table detached")
        result = self.configure(page)
        self.assertEqual(result['failed'][0]['stage'], 'row_resolution')
        row.ele.assert_not_called()

    @patch('draft_tool.browser_actions.time.sleep', return_value=None)
    def test_picker_click_and_frame_failures_are_cleaned_up(self, _sleep):
        for stage in ('click', 'frame_acquisition'):
            with self.subTest(stage=stage):
                page, row = self.browser()
                button = MagicMock()
                row.ele.side_effect = [None, button, button]
                if stage == 'click':
                    button.click.side_effect = RuntimeError('click detached')
                else:
                    page.get_frame.side_effect = RuntimeError('frame detached')
                result = self.configure(page)
                failure = result['failed'][0]
                self.assertEqual(failure['stage'], stage)
                self.assertEqual(failure['recovery'], 'picker_closed')
                self.assertTrue(result['safe_to_continue'])
                self.assertFalse(result['indeterminate'])

    def test_upload_failure_is_indeterminate_and_not_retried(self):
        page, row = self.browser()
        upload = MagicMock()
        upload.input.side_effect = TimeoutError('upload result unknown')
        row.ele.return_value = upload
        result = self.configure(page)
        self.assertEqual(result['status'], 'indeterminate')
        self.assertEqual(result['failed'][0]['stage'], 'upload')
        upload.input.assert_called_once()

    @patch('draft_tool.browser_actions.time.sleep', return_value=None)
    def test_cleanup_failure_preserves_original_error_and_stops_continuation(self, _sleep):
        page, row = self.browser()
        button = MagicMock()
        row.ele.side_effect = [None, button, button]
        page.get_frame.side_effect = RuntimeError('frame detached')
        original = page.run_js.side_effect
        def run_js(script, *args):
            if 'ambiguous picker cleanup' in script:
                raise RuntimeError('close detached')
            return original(script, *args)
        page.run_js.side_effect = run_js
        result = self.configure(page)
        failure = result['failed'][0]
        self.assertIn('frame detached', failure['error'])
        self.assertIn('close detached', failure['cleanup_error'])
        self.assertFalse(result['safe_to_continue'])

    @patch('draft_tool.browser_actions.time.sleep', return_value=None)
    def test_submit_failure_is_indeterminate(self, _sleep):
        page, row = self.browser()
        button = MagicMock()
        row.ele.side_effect = [None, button, button]
        frame = page.get_frame.return_value
        def run_js(script, *args):
            if '.ib-footer.action' in script:
                raise TimeoutError('submit result unknown')
            if 'codexImageChoice' in script:
                return [{'title':'red','src':self.src,'token':'c1','id':'remote'}]
            if "'.insert-pool li')).map" in script:
                return [{'src':self.src}]
            if "querySelectorAll('.insert-pool li').length" in script:
                return 0 if not getattr(self, 'selected', False) else 1
            if 'node.click()' in script:
                self.selected = True
                return True
            return 1
        frame.run_js.side_effect = run_js
        result = self.configure(page)
        self.assertEqual(result['status'], 'indeterminate')
        self.assertEqual(result['failed'][0]['stage'], 'submit')

    def test_readback_reacquisition_failure_is_indeterminate(self):
        page, row = self.browser()
        page.ele.side_effect = [row, RuntimeError('row replaced')]
        result = self.configure(page)
        self.assertEqual(result['status'], 'indeterminate')
        self.assertEqual(result['failed'][0]['stage'], 'readback')
