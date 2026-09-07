import unittest
from unittest.mock import patch

from draft_tool.category_capture import read_category_snapshot


class FakePage:
    url = "https://offer-new.1688.com/popular/publish.htm?catId=123456"
    html = '<input name="catId" value="123456"><div class="category-path">玩具 > 解压玩具 > 指尖陀螺</div>'

    def run_js(self, _script):
        return {
            "ids": [{"value": "123456", "selector": "input[name=catId]"}],
            "names": [{"value": "玩具 > 解压玩具 > 指尖陀螺", "selector": ".category-path"}],
            "title": "发布商品",
            "body": "已选类目 玩具 > 解压玩具 > 指尖陀螺",
        }


class ConflictPage(FakePage):
    html = '<input name="catId" value="999999"><script>catId=123456</script>'

    def run_js(self, _script):
        return {"ids": [{"value": "999999", "selector": "input[name=catId]"}], "names": [], "title": "发布商品", "body": ""}


class CategoryCaptureTests(unittest.TestCase):
    def test_snapshot_prefers_consistent_url_and_dom_evidence(self):
        snapshot = read_category_snapshot(FakePage())
        self.assertEqual(snapshot["category_id"], "123456")
        self.assertEqual(snapshot["category_name"], "玩具 > 解压玩具 > 指尖陀螺")
        self.assertFalse(snapshot["evidence_conflict"])
        self.assertTrue(snapshot["on_publish_page"])

    def test_snapshot_marks_conflicting_evidence(self):
        snapshot = read_category_snapshot(ConflictPage())
        self.assertTrue(snapshot["evidence_conflict"])


if __name__ == "__main__":
    unittest.main()
