import unittest
from unittest.mock import patch

from draft_tool.browser_actions import is_seller_login_url, open_seller_page


class FakeLoginPage:
    def __init__(self):
        self.urls = iter([
            "https://login.taobao.com/member/login.jhtml",
            "https://login.taobao.com/member/login.jhtml",
            "https://offer.1688.com/home.htm",
            "https://offer-new.1688.com/popular/publish.htm?catId=1",
            "https://offer-new.1688.com/popular/publish.htm?catId=1",
        ])
        self.opened = []

    def get(self, url):
        self.opened.append(url)

    @property
    def url(self):
        return next(self.urls)


class LoginWaitTests(unittest.TestCase):
    def test_known_login_hosts_are_detected(self):
        self.assertTrue(is_seller_login_url("https://login.taobao.com/member/login.jhtml"))
        self.assertTrue(is_seller_login_url("https://passport.1688.com/"))
        self.assertFalse(is_seller_login_url("https://offer-new.1688.com/popular/publish.htm"))
        self.assertFalse(is_seller_login_url("not a url"))

    @patch("draft_tool.browser_actions.time.sleep", return_value=None)
    def test_seller_page_is_reopened_after_login(self, _sleep):
        page = FakeLoginPage()
        target = "https://offer-new.1688.com/popular/publish.htm?catId=1"

        result = open_seller_page(page, target, login_timeout_seconds=0, settle_seconds=0)

        self.assertEqual(result, "ready")
        self.assertEqual(page.opened, [target, target])

    @patch("draft_tool.browser_actions.navigate_with_alert_recovery")
    def test_navigation_failure_is_returned_as_workflow_status(self, navigate):
        navigate.side_effect = RuntimeError("No such target id")
        page = type("Page", (), {"url": "https://offer-new.1688.com/"})()

        result = open_seller_page(
            page, "https://offer-new.1688.com/popular/publish.htm",
            login_timeout_seconds=0, settle_seconds=0,
        )

        self.assertEqual(result, "navigation_error:RuntimeError")


if __name__ == "__main__":
    unittest.main()
