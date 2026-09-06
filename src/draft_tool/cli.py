from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from .config import AppConfig
from .quality_gate import validate_product
from .workflow import run_save_draft


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="1688 自动保存草稿工具（不执行正式上架）")
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, help="运行输出根目录；实际结果仍按 商品ID/运行ID 隔离")
    parser.add_argument("--category-id")
    parser.add_argument("--category-name")
    parser.add_argument("--store-identity-text")
    parser.add_argument("--shipping-address")
    parser.add_argument("--freight-template-text")
    parser.add_argument("--delivery-promise")
    parser.add_argument("--package-weight-grams", type=int)
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    config = AppConfig.from_file(args.config.resolve())
    target = config.effective_target({
        "category_id": args.category_id,
        "category_name": args.category_name,
        "store_identity_text": args.store_identity_text,
        "shipping_address": args.shipping_address,
        "freight_template_text": args.freight_template_text,
        "delivery_promise": args.delivery_promise,
        "package_weight_grams": args.package_weight_grams,
    })
    gate = validate_product(args.product.resolve(), target, config.quality)
    if args.validate_only:
        print(json.dumps(gate, ensure_ascii=False, indent=2))
        return 0 if gate["passed"] else 4
    offer_id = str((gate.get("summary") or {}).get("offer_id") or "unknown")
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    output_base = args.output_dir or config.output_root
    output_dir = (output_base / offer_id / run_id).resolve()
    return run_save_draft(args.product.resolve(), config, target, output_dir, args.preview_only, args.keep_open)


if __name__ == "__main__":
    raise SystemExit(main())
