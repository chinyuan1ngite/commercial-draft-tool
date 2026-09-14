"""Generate deterministic, account-free inputs for handover verification."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_image(path: Path, color: tuple[int, int, int], accent: tuple[int, int, int], size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    margin = min(size) // 8
    draw.rectangle((margin, margin, size[0] - margin, size[1] - margin), outline=accent, width=16)
    draw.line((margin, margin, size[0] - margin, size[1] - margin), fill=accent, width=12)
    draw.line((size[0] - margin, margin, margin, size[1] - margin), fill=accent, width=12)
    image.save(path, format="PNG", optimize=False)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_example(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_specs = {
        "assets/main.png": ((238, 244, 248), (25, 90, 125), (800, 800)),
        "detail-assets/detail.png": ((248, 246, 238), (92, 74, 45), (800, 1000)),
        "sku-assets/red.png": ((244, 226, 226), (170, 34, 34), (800, 800)),
        "sku-assets/blue.png": ((224, 235, 246), (35, 91, 160), (800, 800)),
    }
    for relative, (color, accent, size) in image_specs.items():
        write_image(output_dir / relative, color, accent, size)

    red_hash = digest(output_dir / "sku-assets/red.png")
    blue_hash = digest(output_dir / "sku-assets/blue.png")
    product = {
        "schema_version": "1.0",
        "status": "ok",
        "source": {
            "platform": "1688",
            "offer_id": "synthetic-1688-001",
            "url": "https://detail.1688.com/offer/000000000000.html",
            "collected_at": "2026-09-15T00:00:00+08:00",
        },
        "category": {
            "top_id": 100000,
            "second_id": 100100,
            "leaf_id": 100101,
            "leaf_name": "合成测试类目",
        },
        "title": "合成交接样例玩具",
        "seller": "合成来源商家",
        "price": {"primary": 12.5, "observed": [12.5, 13.5], "min_order": "1件起批"},
        "stock": {"total_observed": 12, "sku_values": [7, 5]},
        "package_weights": [],
        "attributes": {"材质": "合成材料", "适用年龄": "3岁以上"},
        "skus": [
            {
                "sku_id": "synthetic-red",
                "name": "红色",
                "properties": {"颜色": "红色"},
                "price": 12.5,
                "stock": 7,
                "image_ref": f"sha256:{red_hash}",
            },
            {
                "sku_id": "synthetic-blue",
                "name": "蓝色",
                "properties": {"颜色": "蓝色"},
                "price": 13.5,
                "stock": 5,
                "image_ref": f"sha256:{blue_hash}",
            },
        ],
        "images": ["https://cbu01.alicdn.com/img/ibank/synthetic-main.png"],
        "assets": [{"status": "saved", "path": "assets/main.png"}],
        "detail_text": "这是完全离线生成的交接样例。",
        "description": {
            "source_url": "",
            "html": "",
            "text": "这是完全离线生成的交接样例。",
            "images": ["https://cbu01.alicdn.com/img/ibank/synthetic-detail.png"],
        },
        "detail_assets": [{"status": "saved", "path": "detail-assets/detail.png"}],
        "media_manifest": {
            "version": 1,
            "items": [
                {
                    "id": f"sha256:{red_hash}",
                    "type": "image",
                    "role": "sku_image",
                    "source_url": "https://cbu01.alicdn.com/img/ibank/synthetic-red.png",
                    "local_path": "sku-assets/red.png",
                    "sha256": red_hash,
                    "status": "saved",
                    "source_evidence": "synthetic_fixture",
                    "sku_identities": [{"sku_id": "synthetic-red", "specification": {"颜色": "红色"}}],
                },
                {
                    "id": f"sha256:{blue_hash}",
                    "type": "image",
                    "role": "sku_image",
                    "source_url": "https://cbu01.alicdn.com/img/ibank/synthetic-blue.png",
                    "local_path": "sku-assets/blue.png",
                    "sha256": blue_hash,
                    "status": "saved",
                    "source_evidence": "synthetic_fixture",
                    "sku_identities": [{"sku_id": "synthetic-blue", "specification": {"颜色": "蓝色"}}],
                },
            ],
        },
        "validation": {"passed": True, "checks": {"synthetic_fixture": True}},
        "warnings": ["synthetic_fixture_not_for_live_pages"],
        "raw": {"page_title": "合成交接样例", "body_length": 0, "image_source": "synthetic_fixture"},
    }
    write_json(output_dir / "product.json", product)

    invalid = deepcopy(product)
    invalid["title"] = ""
    write_json(output_dir / "product-invalid.json", invalid)

    settings = {
        "version": 1,
        "profile_dir": "runtime/profiles/seller",
        "output_root": "runtime/drafts",
        "target": {
            "category_id": "synthetic-category-001",
            "category_name": "合成测试类目",
            "store_identity_text": "SYNTHETIC_STORE_DO_NOT_USE",
            "shipping_address": None,
            "freight_template_text": None,
            "delivery_promise": None,
            "package_weight_grams": 1000,
        },
        "quality": {
            "max_title_chars": 60,
            "min_main_images": 1,
            "max_main_images": 4,
            "require_detail_images": True,
            "max_image_bytes": 5 * 1024 * 1024,
            "min_image_width": 800,
            "min_image_height": 800,
            "min_detail_width": 300,
            "min_detail_height": 100,
            "max_image_pixels": 40_000_000,
            "require_sku_images": True,
        },
        "media": {"collect_sku_images": True, "configure_sku_images": True},
        "category_rules": {"by_category": {}},
    }
    write_json(output_dir / "settings.example.json", settings)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成不含账号和真实商品数据的离线交接样例")
    default_output = Path(__file__).resolve().parents[1] / ".local" / "handover-example"
    parser.add_argument("--output-dir", type=Path, default=default_output)
    args = parser.parse_args()
    build_example(args.output_dir.resolve())
    print(args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
