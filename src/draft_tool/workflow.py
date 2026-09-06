from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig, TargetConfig
from .quality_gate import validate_product, write_runtime_product


def run_save_draft(
    product_path: Path,
    config: AppConfig,
    target: TargetConfig,
    output_dir: Path,
    preview_only: bool = False,
    keep_open: bool = False,
) -> int:
    gate = validate_product(product_path, target, config.quality)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "quality-gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    config.write_runtime_record(output_dir, target)
    if not gate["passed"]:
        print(json.dumps({"result": "blocked_quality_gate", **gate}, ensure_ascii=False, indent=2))
        return 4
    rules_path = output_dir / "category-rules.json"
    rules_path.write_text(json.dumps(config.rules_for(target.category_id), ensure_ascii=False, indent=2), encoding="utf-8")
    runtime_product = write_runtime_product(product_path, output_dir / "runtime-product.json")
    from . import browser_actions

    argv = [
        "--product", str(runtime_product.resolve()),
        "--profile-dir", str(config.profile_dir.resolve()),
        "--output-dir", str(output_dir.resolve()),
        "--category-id", str(target.category_id),
        "--store-identity-text", str(target.store_identity_text),
        "--shipping-address", str(target.shipping_address),
        "--freight-template-text", str(target.freight_template_text),
        "--delivery-promise", str(target.delivery_promise),
        "--package-weight-grams", str(target.package_weight_grams),
        "--category-rules", str(rules_path.resolve()),
        "--keep-open" if keep_open else "",
        "--preview-only" if preview_only else "--save-draft",
    ]
    return browser_actions.main([item for item in argv if item])
