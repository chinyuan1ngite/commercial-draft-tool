"""Platform-neutral SKU normalization and validation.

The seller page is a UI adapter, not the source of truth. This module keeps
source SKU rows in a deterministic shape and identifies cases that cannot be
represented safely by a 1688 sale-property matrix.
"""
from __future__ import annotations

import html
import re
from decimal import Decimal, InvalidOperation
from typing import Any


STATUS_SUFFIX = re.compile(r"\s*(?:>|＞|/|｜|\|)\s*(?:现货|预售|缺货|售罄)\s*$", re.I)
PLACEHOLDER_VALUES = {"无规格", "无", "默认", "标准", "不分规格"}
MAX_PRICE = Decimal("99999999.99")
MAX_STOCK = 2_147_483_647


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def is_valid_sku_price(value: Any) -> bool:
    """Return whether a value can be represented by the seller price field."""
    parsed = _decimal(value)
    return parsed is not None and Decimal("0") < parsed <= MAX_PRICE


def _valid_stock(value: Any) -> bool:
    parsed = _decimal(value)
    return parsed is not None and parsed == parsed.to_integral_value() and 0 <= parsed <= MAX_STOCK


def clean_sku_value(value: Any) -> str:
    text = html.unescape(re.sub(r"\s+", " ", str(value or ""))).strip()
    text = STATUS_SUFFIX.sub("", text).strip()
    return text[:160]


def _properties(row: dict[str, Any]) -> dict[str, str]:
    candidate = row.get("properties") or row.get("specProps") or row.get("skuProps")
    result: dict[str, str] = {}
    if isinstance(candidate, dict):
        for key, value in candidate.items():
            key_text, value_text = clean_sku_value(key), clean_sku_value(value)
            if key_text and value_text:
                result[key_text] = value_text
    elif isinstance(candidate, list):
        for item in candidate:
            if not isinstance(item, dict):
                continue
            key = item.get("name") or item.get("propName") or item.get("label")
            value = item.get("value") or item.get("valueName") or item.get("text")
            key_text, value_text = clean_sku_value(key), clean_sku_value(value)
            if key_text and value_text:
                result[key_text] = value_text
    return result


def normalize_sku_model(skus: list[dict[str, Any]] | None, max_dimensions: int = 2) -> dict[str, Any]:
    """Build dimensions, rows and validation warnings for a collected listing.

    Rows without explicit source properties intentionally use one ``规格``
    dimension. Explicit dimensions are retained only when every row has the
    same complete key set; mixed structures are flattened to avoid silently
    assigning one row's value to another dimension.
    """
    source_rows = [row for row in (skus or []) if isinstance(row, dict)]
    if not source_rows:
        return {"mode": "none", "dimensions": [], "rows": [], "source_count": 0, "warnings": [], "valid": True}

    normalized: list[dict[str, Any]] = []
    explicit = []
    for index, row in enumerate(source_rows, start=1):
        name = clean_sku_value(row.get("name") or row.get("sku_name") or row.get("skuName"))
        props = _properties(row)
        if not props:
            props = {"规格": name}
        explicit.append(bool(row.get("properties") or row.get("specProps") or row.get("skuProps")))
        price = row.get("price")
        stock = row.get("stock")
        normalized.append({
            "source_index": index,
            "sku_id": str(row.get("sku_id") or row.get("skuId") or f"local-{index}"),
            "name": name,
            "properties": props,
            "price": price,
            "stock": stock,
        })

    key_sets = [set(row["properties"].keys()) for row in normalized]
    same_keys = bool(key_sets) and all(keys == key_sets[0] for keys in key_sets)
    warnings: list[str] = []
    if not same_keys:
        warnings.append("源 SKU 规格维度不一致，已降级为单一规格维度")
        for row in normalized:
            row["properties"] = {"规格": row["name"]}
        dimension_names = ["规格"]
    else:
        # Keep the first row's order, while comparing subsequent rows as sets.
        dimension_names = list(normalized[0]["properties"].keys())
        if not all(explicit):
            # A rendered-only row has no trustworthy dimension labels.
            warnings.append("部分 SKU 缺少结构化规格，已降级为单一规格维度")
            for row in normalized:
                row["properties"] = {"规格": row["name"]}
            dimension_names = ["规格"]

    # Some source listings expose a synthetic second dimension such as
    # ``规格=无规格`` for every row. It is not a real sale property and often
    # cannot be represented by a destination category that has one slot.
    # Drop only dimensions whose complete value set is an explicit placeholder;
    # real multi-dimension matrices remain unchanged.
    if len(dimension_names) > 1:
        removable = [
            name for name in dimension_names
            if all(clean_sku_value(row["properties"].get(name)) in PLACEHOLDER_VALUES for row in normalized)
        ]
        if removable and len(removable) < len(dimension_names):
            for row in normalized:
                for name in removable:
                    row["properties"].pop(name, None)
            dimension_names = [name for name in dimension_names if name not in removable]
            warnings.append(f"已折叠占位规格维度: {','.join(removable)}")

    if len(dimension_names) > max_dimensions:
        warnings.append(f"源商品有 {len(dimension_names)} 个规格维度，目标页面最多安全适配 {max_dimensions} 个")

    dimensions = [
        {"name": name, "values": list(dict.fromkeys(row["properties"].get(name, "") for row in normalized if row["properties"].get(name)))}
        for name in dimension_names
    ]
    combinations = [tuple(row["properties"].get(name, "") for name in dimension_names) for row in normalized]
    duplicate_combinations = len(combinations) != len(set(combinations))
    if duplicate_combinations:
        warnings.append("源 SKU 存在重复规格组合")
    if any(not row["name"] or not is_valid_sku_price(row["price"]) or not _valid_stock(row["stock"]) for row in normalized):
        warnings.append("SKU 存在空名称、非法价格或库存（含 NaN、Infinity、小数库存、负数或溢出）")

    expected_matrix = 1
    for dimension in dimensions:
        expected_matrix *= max(1, len(dimension["values"]))
    # A sparse source matrix is legal; it is still important to expose it for
    # page verification instead of inventing unavailable combinations.
    mode = "single" if len(dimension_names) == 1 else "multi"
    return {
        "mode": mode,
        "dimensions": dimensions,
        "rows": normalized,
        "source_count": len(normalized),
        "expected_matrix_count": expected_matrix,
        "warnings": warnings,
        "valid": not warnings or not any("最多安全适配" in item or "重复规格" in item or "非法价格" in item for item in warnings),
    }


def validate_target_rows(model: dict[str, Any], target_rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Compare rendered target rows with the normalized source model."""
    rows = target_rows or []
    expected = int(model.get("source_count") or 0)
    issues: list[str] = []
    if len(rows) != expected:
        issues.append(f"目标页面生成 {len(rows)}/{expected} 个 SKU 行")
    dimension_names = [str(item.get("name") or "") for item in model.get("dimensions") or []]
    combinations: list[tuple[str, ...]] = []
    expected_by_combo = {
        tuple(clean_sku_value(row.get("properties", {}).get(name)) for name in dimension_names): row
        for row in model.get("rows") or []
    }
    for index, row in enumerate(rows, start=1):
        props = row.get("properties") or {}
        missing = [name for name in dimension_names if not clean_sku_value(props.get(name))]
        if missing:
            issues.append(f"第 {index} 行缺少规格: {','.join(missing)}")
        combination = tuple(clean_sku_value(props.get(name)) for name in dimension_names)
        combinations.append(combination)
        expected_row = expected_by_combo.get(combination)
        if expected_row is None:
            issues.append(f"第 {index} 行规格组合不属于源商品")
            continue
        price = _decimal(row.get("price"))
        expected_price = _decimal(expected_row.get("price"))
        if price is None or expected_price is None or price != expected_price:
            issues.append(f"第 {index} 行价格与源数据不一致")
        stock = _decimal(row.get("stock"))
        expected_stock = _decimal(expected_row.get("stock"))
        if stock is None or expected_stock is None or stock != expected_stock or stock != stock.to_integral_value():
            issues.append(f"第 {index} 行库存与源数据不一致")
        # The visible seller field is a merchant code. The platform may keep
        # its internal SKU identity in a hidden attribute or regenerate it
        # after dimensions are added, so only compare IDs when that identity
        # was actually exposed by the target page.
        if row.get("sku_identity_available", True):
            expected_sku_id = clean_sku_value(expected_row.get("sku_id"))
            if clean_sku_value(row.get("sku_id")) != expected_sku_id:
                issues.append(f"第 {index} 行平台 SKU 标识与源数据不一致")
    if len(combinations) != len(set(combinations)):
        issues.append("目标页面存在重复规格组合")
    return {"valid": not issues, "expected_rows": expected, "actual_rows": len(rows), "issues": issues}
