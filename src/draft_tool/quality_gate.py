from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from .config import QualityConfig, TargetConfig
from .sku_adapter import normalize_sku_model


def _resolve_asset_path(product_path: Path, raw: Path) -> Path | None:
    if raw.is_absolute() and raw.is_file():
        return raw.resolve()
    candidates = [Path.cwd() / raw, product_path.parent / raw]
    candidates.extend(parent / raw for parent in product_path.parents)
    return next((item.resolve() for item in candidates if item.is_file()), None)


def _saved_paths(product_path: Path, product: dict[str, Any], key: str) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    issues: list[str] = []
    for item in product.get(key) or []:
        if not isinstance(item, dict) or item.get("status") != "saved":
            continue
        raw = Path(str(item.get("path") or ""))
        candidate = _resolve_asset_path(product_path, raw)
        if candidate:
            paths.append(candidate)
        else:
            issues.append(f"素材不存在: {raw}")
    return paths, issues


def _check_images(paths: list[Path], quality: QualityConfig, label: str, min_width: int, min_height: int) -> tuple[list[Path], list[str]]:
    valid: list[Path] = []
    rejected: list[str] = []
    for path in paths:
        try:
            reasons: list[str] = []
            if path.stat().st_size > quality.max_image_bytes:
                reasons.append("超过大小限制")
            with Image.open(path) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    reasons.append("格式不支持")
                if image.width < min_width or image.height < min_height:
                    reasons.append(f"尺寸不足({image.width}x{image.height})")
            if reasons:
                rejected.append(f"{label}候选已过滤: {path.name} ({','.join(reasons)})")
            else:
                valid.append(path)
        except Exception as exc:
            rejected.append(f"{label}候选已过滤: {path.name} ({type(exc).__name__})")
    return valid, rejected


def validate_product(product_path: Path, target: TargetConfig, quality: QualityConfig) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    try:
        product = json.loads(product_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"passed": False, "issues": [f"无法读取 product.json: {type(exc).__name__}"], "warnings": []}
    if not isinstance(product, dict):
        return {"passed": False, "issues": ["product.json 必须是对象"], "warnings": []}
    offer_id = str((product.get("source") or {}).get("offer_id") or "").strip()
    title = str(product.get("title") or "").strip()
    if not offer_id:
        issues.append("缺少 source.offer_id")
    if not title:
        issues.append("缺少商品标题")
    elif len(title) > quality.max_title_chars:
        issues.append(f"标题超过 {quality.max_title_chars} 字符，禁止静默截断")
    if not bool((product.get("validation") or {}).get("passed")):
        issues.append("采集结果 validation.passed=false")
    if not target.category_id:
        issues.append("未确认目标叶子类目 category_id")
    if not target.store_identity_text:
        issues.append("未配置店铺身份校验文本")
    if not target.shipping_address:
        issues.append("未配置发货地址")
    if not target.freight_template_text:
        issues.append("未配置运费模板")
    if not target.delivery_promise:
        issues.append("未配置发货承诺")
    if not target.package_weight_grams or target.package_weight_grams <= 0:
        issues.append("未配置有效包裹重量")
    main_paths, main_issues = _saved_paths(product_path, product, "assets")
    detail_paths, detail_issues = _saved_paths(product_path, product, "detail_assets")
    issues.extend(main_issues + detail_issues)
    valid_main, rejected_main = _check_images(
        main_paths, quality, "主图", quality.min_image_width, quality.min_image_height
    )
    valid_detail, rejected_detail = _check_images(
        detail_paths, quality, "详情图", quality.min_detail_width, quality.min_detail_height
    )
    warnings.extend(rejected_main + rejected_detail)
    if len(valid_main) < quality.min_main_images:
        issues.append(f"合规主图不足: {len(valid_main)}/{quality.min_main_images}")
    if len(valid_main) > quality.max_main_images:
        warnings.append(f"合规主图将按平台上限处理: {len(valid_main)}>{quality.max_main_images}")
    if quality.require_detail_images and not valid_detail:
        issues.append("缺少详情图")
    price = (product.get("price") or {}).get("primary")
    try:
        valid_price = price is not None and float(price or 0) > 0
    except (TypeError, ValueError):
        valid_price = False
    if not valid_price:
        issues.append("主价格必须大于 0")
    sku_model = normalize_sku_model(product.get("skus") or [])
    if sku_model.get("source_count") and not sku_model.get("valid", True):
        issues.extend(str(item) for item in sku_model.get("warnings") or [])
    if sku_model.get("warnings"):
        warnings.extend(str(item) for item in sku_model["warnings"])
    try:
        total_stock = int((product.get("stock") or {}).get("total_observed") or 0)
    except (TypeError, ValueError):
        total_stock = -1
    if not sku_model.get("source_count") and total_stock < 0:
        issues.append("库存不能为负数")
    return {
        "passed": not issues,
        "issues": list(dict.fromkeys(issues)),
        "warnings": list(dict.fromkeys(warnings)),
        "summary": {
            "offer_id": offer_id,
            "title": title,
            "main_images": len(valid_main),
            "detail_images": len(valid_detail),
            "sku_count": int(sku_model.get("source_count") or 0),
            "target": asdict(target),
        },
    }


def write_runtime_product(product_path: Path, output_path: Path) -> Path:
    """Write a run-local manifest with absolute asset paths for launcher-safe execution."""
    product = json.loads(product_path.read_text(encoding="utf-8"))
    for key in ("assets", "detail_assets"):
        for item in product.get(key) or []:
            if not isinstance(item, dict) or item.get("status") != "saved":
                continue
            resolved = _resolve_asset_path(product_path, Path(str(item.get("path") or "")))
            if resolved:
                item["path"] = str(resolved)
    output_path.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
