from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig, TargetConfig
from .quality_gate import validate_product, write_runtime_product
from .security import DraftLedger, atomic_write, profile_lock


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
    atomic_write(output_dir / "quality-gate.json", json.dumps(gate, ensure_ascii=False, indent=2))
    config.write_runtime_record(output_dir, target)
    if not gate["passed"]:
        print(json.dumps({"result": "blocked_quality_gate", **gate}, ensure_ascii=False, indent=2))
        return 4
    rules_path = output_dir / "category-rules.json"
    atomic_write(rules_path, json.dumps(config.rules_for(target.category_id), ensure_ascii=False, indent=2))
    runtime_product = write_runtime_product(product_path, output_dir / "runtime-product.json")
    from . import browser_actions

    offer_id = str((gate.get("summary") or {}).get("offer_id") or "")
    store_identity = str(target.store_identity_text or "").strip()
    ledger = DraftLedger(config.output_root / "draft-ledger.sqlite3")
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
    try:
        with profile_lock(config.profile_dir):
            existing = ledger.get(store_identity, offer_id)
            run_argv = argv + ["--existing-draft-id", str((existing or {}).get("draft_id") or "")]
            result = browser_actions.main([item for item in run_argv if item])
            report_path = output_dir / "report.json"
            if result == 0 and not preview_only and report_path.is_file():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if report.get("draft_id"):
                    ledger.put(store_identity, offer_id, str(report["draft_id"]), output_dir)
    except RuntimeError as exc:
        atomic_write(output_dir / "lock-error.json", json.dumps({"result": "blocked_profile_in_use", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 5
    return result
