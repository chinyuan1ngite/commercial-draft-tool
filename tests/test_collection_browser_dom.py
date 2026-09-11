"""Isolated browser regression at the collection boundary."""
import base64
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from DrissionPage import ChromiumOptions, ChromiumPage
from draft_tool.collector import collect_with_browser


@unittest.skipUnless(os.environ.get('DRAFT_BROWSER_TESTS') == '1', 'set DRAFT_BROWSER_TESTS=1')
class CollectionBrowserTests(unittest.TestCase):
    def test_collection_navigates_new_tab_despite_restored_beforeunload(self):
        binary = os.environ.get('CHROME_BINARY') or shutil.which('chrome') or str(
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe')
        page = ChromiumPage(ChromiumOptions().set_browser_path(binary).auto_port().headless())
        page.set.timeouts(page_load=2)
        page.get('data:text/html,' + quote('<button id="start">Start</button>'))
        page.run_js('''document.querySelector('#start').onclick = () => {
            window.onbeforeunload = event => { event.preventDefault(); event.returnValue = ''; };
        };''')
        page.ele('css:#start').click()
        original_new_tab = page.browser.new_tab

        def routed_tab(*args, **kwargs):
            tab = original_new_tab(*args, **kwargs)
            def fulfill(**event):
                tab.run_cdp('Fetch.fulfillRequest', requestId=event['requestId'], responseCode=200,
                    responseHeaders=[{'name': 'Content-Type', 'value': 'text/html; charset=utf-8'}],
                    body=base64.b64encode(b'<title>Collected fixture</title><p>Collection arrived</p>').decode())
            tab.driver.set_callback('Fetch.requestPaused', fulfill)
            tab.run_cdp('Fetch.enable', patterns=[{'urlPattern': 'https://detail.1688.com/*'}])
            return tab

        try:
            # Browser construction and network responses are external boundaries;
            # navigation, dialogs and tab lifecycle use a real isolated browser.
            with tempfile.TemporaryDirectory() as directory, \
                    patch('DrissionPage.ChromiumPage', return_value=page) as connect, \
                    patch.object(page.browser, 'new_tab', side_effect=routed_tab):
                url, html, body = collect_with_browser('https://detail.1688.com/offer/1.html', Path(directory), 0)
                self.assertEqual(url, 'https://detail.1688.com/offer/1.html')
                self.assertIn('Collection arrived', html)
                self.assertIn('Collection arrived', body)
                self.assertNotEqual(connect.call_args.args[0].address, '127.0.0.1:9222')
                self.assertEqual(Path(connect.call_args.args[0].user_data_path), Path(directory).resolve())
        finally:
            try:
                page.quit()
            except Exception:
                pass
