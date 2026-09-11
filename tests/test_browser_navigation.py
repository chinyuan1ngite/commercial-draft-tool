import unittest

from draft_tool.browser_navigation import PopupRecoveryError, navigate_with_alert_recovery


class BrowserNavigationTests(unittest.TestCase):
    def test_failed_navigation_does_not_report_success(self):
        class BrowserAdapter:
            def handle_alert(self, **kwargs):
                return False

            def get(self, url):
                return False

        with self.assertRaisesRegex(PopupRecoveryError, 'navigation_not_completed'):
            navigate_with_alert_recovery(BrowserAdapter(), 'https://detail.1688.com/offer/1.html')
