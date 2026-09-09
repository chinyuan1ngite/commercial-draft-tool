import tempfile
import unittest
from pathlib import Path

from draft_tool.media import resolve_sku_image_paths, specification_key


class MediaTests(unittest.TestCase):
    def test_resolves_unique_full_specification_without_sku_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sku-assets").mkdir()
            image = root / "sku-assets" / "red.jpg"
            image.write_bytes(b"image")
            product = {
                "skus": [{"sku_id": "", "properties": {"颜色": "红", "尺寸": "大"}}],
                "media_manifest": {"version": 1, "items": [{
                    "id": "sha256:red", "role": "sku_image", "status": "saved",
                    "local_path": "sku-assets/red.jpg",
                    "sku_identities": [{"sku_id": None, "specification": {"尺寸": "大", "颜色": "红"}}],
                }]},
            }
            paths, issues = resolve_sku_image_paths(root / "product.json", product)
            self.assertEqual(paths[specification_key(product["skus"][0]["properties"])], image)
            self.assertEqual(issues, [])

    def test_duplicate_sku_identity_with_different_images_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sku-assets").mkdir()
            for name in ("one.jpg", "two.jpg"):
                (root / "sku-assets" / name).write_bytes(name.encode())
            items = [{
                "id": f"sha256:{name}", "role": "sku_image", "status": "saved",
                "local_path": f"sku-assets/{name}", "sku_identities": [{"sku_id": "1"}],
            } for name in ("one.jpg", "two.jpg")]
            paths, issues = resolve_sku_image_paths(
                root / "product.json", {"skus": [{"sku_id": "1"}], "media_manifest": {"version": 1, "items": items}}
            )
            self.assertNotIn("1", paths)
            self.assertTrue(any("身份冲突" in issue for issue in issues))

    def test_resolves_one_property_image_for_each_matching_full_sku(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sku-assets").mkdir()
            image = root / "sku-assets" / "red.jpg"
            image.write_bytes(b"image")
            product = {
                "skus": [
                    {"sku_id": "A", "properties": {"颜色": "红", "尺寸": "大"}},
                    {"sku_id": "B", "properties": {"颜色": "红", "尺寸": "小"}},
                ],
                "media_manifest": {"version": 1, "items": [{
                    "id": "sha256:red", "role": "sku_image", "status": "saved",
                    "local_path": "sku-assets/red.jpg",
                    "sku_identities": [{"sku_id": None, "specification": {"颜色": "红"}}],
                }]},
            }

            paths, issues = resolve_sku_image_paths(root / "product.json", product)

            self.assertEqual(paths, {"A": image, "B": image})
            self.assertEqual(issues, [])

    def test_conflicting_partial_specification_images_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sku-assets").mkdir()
            for name in ("red.jpg", "large.jpg"):
                (root / "sku-assets" / name).write_bytes(name.encode())
            product = {
                "skus": [{"sku_id": "A", "properties": {"颜色": "红", "尺寸": "大"}}],
                "media_manifest": {"version": 1, "items": [
                    {
                        "id": "sha256:red", "role": "sku_image", "status": "saved",
                        "local_path": "sku-assets/red.jpg",
                        "sku_identities": [{"sku_id": None, "specification": {"颜色": "红"}}],
                    },
                    {
                        "id": "sha256:large", "role": "sku_image", "status": "saved",
                        "local_path": "sku-assets/large.jpg",
                        "sku_identities": [{"sku_id": None, "specification": {"尺寸": "大"}}],
                    },
                ]},
            }

            paths, issues = resolve_sku_image_paths(root / "product.json", product)

            self.assertNotIn("A", paths)
            self.assertTrue(any("身份冲突" in issue for issue in issues))

    def test_list_specification_is_normalized(self):
        self.assertEqual(
            specification_key([{"propName": "颜色", "valueName": "红"}]),
            specification_key({"颜色": "红"}),
        )


if __name__ == "__main__":
    unittest.main()
