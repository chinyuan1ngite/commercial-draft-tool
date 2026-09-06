from __future__ import annotations

import json
import shutil
from decimal import Decimal, InvalidOperation
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from .config import QualityConfig, TargetConfig
from .sku_adapter import normalize_sku_model
from .security import atomic_write


def _resolve_asset_path(product_path: Path, raw: Path, directory: str) -> Path | None:
    if raw.is_absolute() or not raw.parts or ".." in raw.parts:
        return None
    root = (product_path.parent / directory).resolve()
    lexical = product_path.parent / raw
    if lexical.is_symlink():
        return None
    candidate = lexical.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _saved_paths(product_path: Path, product: dict[str, Any], key: str) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    issues: list[str] = []
    for item in product.get(key) or []:
        if not isinstance(item, dict) or item.get("status") != "saved":
            continue
        raw = Path(str(item.get("path") or ""))
        directory = "assets" if key == "assets" else "detail-assets"
        candidate = _resolve_asset_path(product_path, raw, directory)
        if candidate:
            paths.append(candidate)
        else:
            issues.append(f"素材路径越界、为符号链接或不存在: {raw}")
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
                if image.width * image.height > quality.max_image_pixels:
                    reasons.append("像素总量超过限制")
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
    if not str(target.category_id or "").strip():
        issues.append("未确认目标叶子类目 category_id")
    if not str(target.store_identity_text or "").strip():
        issues.append("未配置店铺身份校验文本")
    if not str(target.shipping_address or "").strip():
        issues.append("未配置发货地址")
    if not str(target.freight_template_text or "").strip():
        issues.append("未配置运费模板")
    if not str(target.delivery_promise or "").strip():
        issues.append("未配置发货承诺")
    if (isinstance(target.package_weight_grams, bool) or not isinstance(target.package_weight_grams, int)
            or not 0 < target.package_weight_grams <= 1_000_000):
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
        parsed_price = Decimal(str(price).strip())
        valid_price = parsed_price.is_finite() and Decimal("0") < parsed_price <= Decimal("99999999.99")
    except (InvalidOperation, ValueError, AttributeError):
        valid_price = False
    if not valid_price:
        issues.append("主价格必须大于 0")
    sku_model = normalize_sku_model(product.get("skus") or [])
    if sku_model.get("source_count") and not sku_model.get("valid", True):
        issues.extend(str(item) for item in sku_model.get("warnings") or [])
    if sku_model.get("warnings"):
        warnings.extend(str(item) for item in sku_model["warnings"])
    raw_stock = (product.get("stock") or {}).get("total_observed")
    try:
        total_stock = Decimal(str(raw_stock).strip())
        valid_stock = total_stock.is_finite() and total_stock == total_stock.to_integral_value() and 0 <= total_stock <= 2_147_483_647
    except (InvalidOperation, ValueError, AttributeError):
        valid_stock = False
    if (raw_stock is not None or not sku_model.get("source_count")) and not valid_stock:
        issues.append("库存必须是范围内的非负整数")
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
    """Copy approved assets into the run and write a self-contained manifest."""
    product = json.loads(product_path.read_text(encoding="utf-8"))
    for key in ("assets", "detail_assets"):
        directory = "assets" if key == "assets" else "detail-assets"
        target_dir = output_path.parent / directory
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in product.get(key) or []:
            if not isinstance(item, dict) or item.get("status") != "saved":
                continue
            resolved = _resolve_asset_path(product_path, Path(str(item.get("path") or "")), directory)
            if resolved:
                destination = target_dir / resolved.name
                shutil.copyfile(resolved, destination)
                item["path"] = str(Path(directory) / destination.name)
    atomic_write(output_path, json.dumps(product, ensure_ascii=False, indent=2))
    return output_path
