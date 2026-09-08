"""Runtime paths that remain stable for source and packaged execution."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .security import atomic_write


APP_DIR_NAME = "Commercial1688DraftTool"


def application_data_dir() -> Path:
    override = os.environ.get("DRAFT_TOOL_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (base / APP_DIR_NAME).resolve()


def bundled_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


def default_config_payload(data_dir: Path) -> dict:
    return {
        "version": 1,
        "profile_dir": str(data_dir / "profiles" / "seller"),
        "output_root": str(data_dir / "drafts"),
        "target": {
            "category_id": None,
            "category_name": None,
            "store_identity_text": None,
            "shipping_address": None,
            "freight_template_text": None,
            "delivery_promise": None,
            "package_weight_grams": None,
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
            "require_sku_images": False,
        },
        "media": {
            "collect_sku_images": True,
            "configure_sku_images": True,
        },
        "category_rules": {"by_category": {}},
    }


def initialize_runtime() -> dict[str, Path]:
    root = application_data_dir()
    paths = {
        "root": root,
        "config": root / "config" / "settings.local.json",
        "products": root / "products",
        "buyer_profile": root / "profiles" / "buyer",
        "seller_profile": root / "profiles" / "seller",
        "drafts": root / "drafts",
        "logs": root / "logs",
    }
    for key in ("products", "buyer_profile", "seller_profile", "drafts", "logs"):
        paths[key].mkdir(parents=True, exist_ok=True)
    if not paths["config"].is_file():
        atomic_write(paths["config"], json.dumps(default_config_payload(root), ensure_ascii=False, indent=2))
    return paths
