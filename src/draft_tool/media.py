from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def specification_key(value: Any) -> str:
    if isinstance(value, list):
        normalized_list = [
            {
                str(item.get("name") or item.get("propName") or item.get("label")): str(
                    item.get("value") or item.get("valueName") or item.get("text") or ""
                ).strip()
            }
            for item in value if isinstance(item, dict)
        ]
        value = {key: val for item in normalized_list for key, val in item.items() if key and val}
    if not isinstance(value, dict):
        return ""
    normalized = {
        str(key).strip(): " ".join(str(item).split())
        for key, item in value.items()
        if str(key).strip() and " ".join(str(item).split())
    }
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if normalized else ""


def _safe_path(product_path: Path, raw: str) -> Path | None:
    path = Path(raw)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return None
    root = (product_path.parent / "sku-assets").resolve()
    lexical = product_path.parent / path
    if lexical.is_symlink():
        return None
    candidate = lexical.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def resolve_sku_image_paths(product_path: Path, product: dict[str, Any]) -> tuple[dict[str, Path], list[str]]:
    """Resolve each source SKU by ID first, then one unique specification."""
    result: dict[str, Path] = {}
    issues: list[str] = []
    manifest = product.get("media_manifest")
    if manifest is None:
        return result, issues
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        return result, [f"不支持的媒体清单版本: {manifest.get('version') if isinstance(manifest, dict) else None!r}"]
    by_id: dict[str, list[Path]] = {}
    by_spec: dict[str, list[Path]] = {}
    item_by_ref: dict[str, Path] = {}
    items = manifest.get("items")
    if not isinstance(items, list):
        return result, ["media_manifest.items 必须是数组"]
    for item in items:
        if not isinstance(item, dict) or item.get("role") != "sku_image" or item.get("status") != "saved":
            continue
        path = _safe_path(product_path, str(item.get("local_path") or ""))
        if not path:
            issues.append(f"SKU 图片路径越界或不存在: {item.get('local_path')!s}")
            continue
        media_id = str(item.get("id") or "").strip()
        if media_id:
            item_by_ref[media_id] = path
        identities = item.get("sku_identities")
        if not isinstance(identities, list):
            issues.append("SKU 图片缺少 sku_identities")
            continue
        for identity in identities:
            if not isinstance(identity, dict):
                continue
            sku_id = str(identity.get("sku_id") or "").strip()
            spec = specification_key(identity.get("specification"))
            if sku_id:
                by_id.setdefault(sku_id, []).append(path)
            if spec:
                by_spec.setdefault(spec, []).append(path)
    for sku in product.get("skus") or []:
        key = str(sku.get("sku_id") or "").strip()
        candidates = [item_by_ref[str(sku.get("image_ref"))] for _ in [0] if str(sku.get("image_ref") or "") in item_by_ref]
        if not candidates:
            candidates = by_id.get(key, [])
        if not candidates:
            candidates = by_spec.get(specification_key(sku.get("properties") or sku.get("specProps")), [])
        unique = list(dict.fromkeys(candidates))
        if len(unique) == 1:
            result[key or specification_key(sku.get("properties"))] = unique[0]
        elif len(unique) > 1:
            issues.append(f"SKU 图片身份冲突: {key or specification_key(sku.get('properties'))}")
    return result, issues
