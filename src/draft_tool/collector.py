"""Collect and normalize one 1688 product detail page into local files.

The collector is intentionally local-first. It uses a persistent Chromium profile
for a user-authorized 1688 session, saves the raw page for reproducibility, and
keeps the parser usable in an offline HTML-fixture mode.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .sku_adapter import normalize_sku_model
from .security import MAX_TOTAL_IMAGE_BYTES, atomic_write, download_image, hostname_allowed, read_allowlisted_url


ALLOWED_HOSTS = {"detail.1688.com", "www.1688.com", "1688.com"}
BLOCK_MARKERS = (
    "punish",
    "验证码",
    "安全验证",
    "滑块",
    "访问被拒绝",
    "请完成验证",
)
IMAGE_SKIP_MARKERS = (".svg", "tps-", "rate.jpg", "logo", "icon")


class CollectionError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def extract_offer_id(value: str) -> str:
    match = re.search(r"/offer/(\d+)", value) or re.search(r"(?:offerId=|^)(\d{6,})", value)
    if not match:
        raise CollectionError(f"无法识别 offer_id: {value}")
    return match.group(1)


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        raise CollectionError("只允许采集 detail.1688.com 或 1688.com 商品链接")
    return url


def normalize_image_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    return url


def is_product_image(url: str) -> bool:
    lowered = url.lower()
    return (
        hostname_allowed(url, {"alicdn.com", "1688.com"})
        and not any(marker in lowered for marker in IMAGE_SKIP_MARKERS)
        and any(ext in lowered for ext in (".jpg", ".jpeg", ".png", ".webp"))
    )


def parse_title(soup: BeautifulSoup) -> str:
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    title = re.sub(r"\s*[-|｜]\s*(阿里巴巴|1688).*$", "", title).strip()
    if title and title not in {"阿里巴巴", "1688"}:
        return title

    candidates = [clean_text(node.get_text(" ", strip=True)) for node in soup.find_all(["h1", "h2"])]
    candidates = [c for c in candidates if len(c) >= 6 and "商品详情" not in c]
    return max(candidates, key=len, default="")


def parse_seller(body: str) -> str:
    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9（）()·]{4,50})\s+关注(?:\s+客服)?", body)
    return match.group(1).strip() if match else ""


def parse_attributes(soup: BeautifulSoup) -> dict[str, str]:
    attributes: dict[str, str] = {}
    # The detail page has later tables for packaging and recommendations. Prefer
    # the first table following the 商品属性 heading so those rows do not leak
    # into the product attribute map.
    heading = next(
        (node for node in soup.find_all(["h1", "h2", "h3", "h4"]) if "商品属性" in clean_text(node.get_text(" ", strip=True))),
        None,
    )
    tables = [heading.find_next("table")] if heading and heading.find_next("table") else soup.find_all("table")
    for row in tables[0].find_all("tr") if tables else []:
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 4 and len(cells) % 2 == 0:
            for index in range(0, len(cells), 2):
                key, value = cells[index], cells[index + 1]
                if key and value and key not in {"颜色", "重量(g)"}:
                    attributes[key] = value
        elif len(cells) == 2 and cells[0] not in {"颜色", "重量(g)"}:
            attributes[cells[0]] = cells[1]

    # Newer 1688 pages render the three decision attributes (and sometimes
    # the complete attribute set) as div/list blocks instead of a table.  The
    # visible labels are the source of truth; do not infer values from title
    # text or SKU names.  Keep this after the table parser so an explicit table
    # value wins when both renderings are present.
    structured_pairs: list[tuple[str, str]] = []
    for item in soup.select(".decision-attributes-list li"):
        parts = [clean_text(node.get_text(" ", strip=True)) for node in item.find_all(["p", "span"])]
        parts = [part for part in parts if part]
        if len(parts) >= 2:
            structured_pairs.append((parts[0], parts[1]))
    for item in soup.select(".cpv-attr-item"):
        label = item.select_one(".cpv-attr-label")
        value = item.select_one(".cpv-attr-value")
        if label and value:
            structured_pairs.append((clean_text(label.get_text(" ", strip=True)), clean_text(value.get_text(" ", strip=True))))
    for key, value in structured_pairs:
        if key and value and key not in {"颜色", "重量(g)"} and key not in attributes:
            attributes[key] = value

    # A few older templates call the same property “玩具材质”.  Preserve the
    # original key while exposing the canonical label used by seller forms.
    if "材质" not in attributes:
        for key, value in attributes.items():
            if "材质" in key and value:
                attributes["材质"] = value
                break
    return attributes


def _normalize_sku_name(value: str) -> str:
    # Embedded specAttrs is sometimes HTML-escaped (for example ``&gt;``).
    # Decode it before applying status/quantity cleanup so the same source SKU
    # has a stable value regardless of which rendering path supplied it.
    name = clean_text(html_lib.unescape(value))
    # Rendered rows may start with the UI label ``颜色`` (for example
    # ``颜色 红色``), but a real SKU value can also contain that word in a
    # suffix such as ``大沙车5件套（颜色随机）``.  Only remove the label when
    # it is a standalone prefix; the previous non-greedy expression removed
    # everything through the last matching word and collapsed distinct SKUs
    # to the same value (often just ``随机）``).
    name = re.sub(r"^(?:颜色|商品详情|加采购车)(?:\s+|$)", "", name).strip()
    name = re.sub(r"^(?:盒|件|个)\s*", "", name).strip()
    # "现货", "预售" and similar suffixes describe fulfillment, not a sale
    # property. Keeping them as part of the value creates duplicate or invalid
    # target properties on categories that do not expose them.
    name = re.sub(r"\s*(?:>|＞|/|｜|\|)\s*(?:现货|预售|缺货|售罄)\s*$", "", name, flags=re.I)
    return name


def _sku_properties(name: str, item: dict[str, Any] | None = None) -> dict[str, str]:
    """Return a portable property map for one source SKU.

    1688 exposes structured property paths on some pages and only a display
    string on others. Preserve structured fields when present; otherwise use a
    single neutral ``规格`` dimension. This is deliberately conservative: it is
    safer to publish one explicit dimension than to guess that words such as
    "红" or "大" belong to a platform-specific property.
    """
    item = item or {}
    candidates = item.get("properties") or item.get("specProps") or item.get("skuProps")
    properties: dict[str, str] = {}
    if isinstance(candidates, dict):
        properties = {
            clean_text(html_lib.unescape(str(key))): clean_text(html_lib.unescape(str(value)))
            for key, value in candidates.items()
            if clean_text(str(key)) and clean_text(str(value))
        }
    elif isinstance(candidates, list):
        for prop in candidates:
            if not isinstance(prop, dict):
                continue
            key = prop.get("name") or prop.get("propName") or prop.get("label")
            value = prop.get("value") or prop.get("valueName") or prop.get("text")
            if key and value:
                properties[clean_text(str(key))] = clean_text(html_lib.unescape(str(value)))
    if not properties and isinstance(item.get("__sale_properties"), list):
        # skuModel.skuProps is present on many pages even when skuMap rows only
        # expose the concatenated specAttrs string. Match only exact candidate
        # values supplied by the source page; never infer a value from a word
        # such as "红" or "大" on its own.
        clean_name = _normalize_sku_name(name)
        for dimension in item["__sale_properties"]:
            if not isinstance(dimension, dict):
                continue
            label = clean_text(str(dimension.get("name") or ""))
            values = [clean_text(str(value)) for value in dimension.get("values") or []]
            matches = sorted((value for value in values if value and value in clean_name), key=len, reverse=True)
            if label and matches:
                properties[label] = matches[0]
    return properties or {"规格": _normalize_sku_name(name)}


def _embedded_sale_properties(html: str) -> list[dict[str, Any]]:
    """Extract seller-provided sale-property labels and candidate values."""
    marker = '"skuModel":'
    start = html.find(marker)
    if start < 0:
        return []
    object_start = html.find("{", start + len(marker))
    if object_start < 0:
        return []
    try:
        model, _ = json.JSONDecoder().raw_decode(html[object_start:])
    except (json.JSONDecodeError, TypeError):
        return []
    result = []
    for prop in (model.get("skuProps") if isinstance(model, dict) else []) or []:
        if not isinstance(prop, dict):
            continue
        label = clean_text(str(prop.get("prop") or prop.get("name") or ""))
        values = []
        for item in prop.get("value") or prop.get("values") or []:
            if isinstance(item, dict):
                value = item.get("name") or item.get("valueName")
            else:
                value = item
            if value:
                values.append(clean_text(html_lib.unescape(str(value))))
        if label and values:
            result.append({"name": label, "values": unique(values)})
    return result


def _make_sku(index: int, name: str, price: float, stock: int, sku_id: str | None = None, raw_item: dict[str, Any] | None = None) -> dict[str, Any] | None:
    name = _normalize_sku_name(name)
    if not name or len(name) > 160:
        return None
    return {
        "sku_id": sku_id or f"local-{index}",
        "name": name,
        "properties": _sku_properties(name, raw_item),
        "price": float(price),
        "stock": int(stock),
    }


def parse_skus(body: str) -> list[dict[str, Any]]:
    """Parse the rendered SKU rows, which vary across login/render states."""
    patterns = (
        # Normal rendered row: name + ¥/￥ + price + stock.
        re.compile(r"([^¥￥]{2,160}?)\s*[¥￥]\s*([0-9]+(?:\.[0-9]+)?)\s*库存\s*([0-9]+)"),
        # Some pages omit the currency symbol from the rendered text.
        re.compile(r"([\u4e00-\u9fffA-Za-z0-9【】（）()\[\]<>+\-_/·，,。 ]{2,160}?)\s+([0-9]+(?:\.[0-9]+)?)\s*库存\s*([0-9]+)"),
    )
    skus: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for pattern in patterns:
        for match in pattern.finditer(body):
            item = _make_sku(len(skus) + 1, match.group(1), float(match.group(2)), int(match.group(3)))
            if not item:
                continue
            key = (item["name"], item["stock"])
            if key not in seen:
                skus.append(item)
                seen.add(key)
    return skus


def parse_embedded_skus(html: str, default_price: float | None = None) -> list[dict[str, Any]]:
    """Read the stable SKU map embedded in window.context on current 1688 pages."""
    marker = '"skuMap":'
    start = html.find(marker)
    if start < 0:
        return []
    array_start = html.find("[", start + len(marker))
    if array_start < 0:
        return []
    try:
        payload, _ = json.JSONDecoder().raw_decode(html[array_start:])
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, list):
        return []
    if default_price is None:
        price_match = re.search(r'"skuPriceScale"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"', html)
        default_price = float(price_match.group(1)) if price_match else 0.0

    sale_properties = _embedded_sale_properties(html)
    skus: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("specAttrs") or item.get("skuName") or ""
        stock = item.get("canBookCount")
        sku_id = item.get("skuId")
        if not name or not isinstance(stock, (int, float)):
            continue
        item_with_properties = dict(item)
        item_with_properties["__sale_properties"] = sale_properties
        parsed = _make_sku(len(skus) + 1, str(name), default_price or float(item.get("price", 0) or 0), int(stock), str(sku_id) if sku_id else None, item_with_properties)
        if parsed:
            skus.append(parsed)
    return skus


def _structured_image_urls(html: str) -> list[str]:
    """Extract only seller-provided gallery fields, never arbitrary page images."""
    values: list[str] = []
    for marker in ('"mainImage":', '"mainImageList":', '"offerImgList":', '"imageList":'):
        start = html.find(marker)
        if start < 0:
            continue
        begin = html.find("[", start + len(marker))
        if begin < 0:
            continue
        try:
            payload, _ = json.JSONDecoder().raw_decode(html[begin:])
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            candidate = item if isinstance(item, str) else (item.get("fullPathImageURI") or item.get("imageURI") or item.get("url") if isinstance(item, dict) else "")
            candidate = normalize_image_url(str(candidate or ""))
            if is_product_image(candidate):
                values.append(candidate)
        if values:
            break
    return unique(values)[:50]


def parse_images(soup: BeautifulSoup, source_html: str = "") -> list[str]:
    return _structured_image_urls(source_html) if source_html else []


def parse_detail_text(body: str) -> str:
    start = body.find("商品详情")
    if start < 0:
        return ""
    tail = body[start + len("商品详情"):]
    end_markers = [tail.find(marker) for marker in ("同款推荐", "搭配组货", "热门推荐") if tail.find(marker) >= 0]
    end = min(end_markers) if end_markers else len(tail)
    return clean_text(tail[:end])[:12000]


def extract_detail_url(page_html: str) -> str:
    """Extract the product-description endpoint embedded in the offer page."""
    match = re.search(
        r"https?://itemcdn\.tmall\.com/(?:desc|1688offer)/[^\"'<>\\ ]+",
        html_lib.unescape(page_html),
        re.I,
    )
    return match.group(0) if match else ""


def parse_detail_response(payload: str, source_url: str = "") -> dict[str, Any]:
    """Normalize the JavaScript-wrapped HTML returned by the detail endpoint."""
    raw_html = payload
    # Current endpoints return JSON-shaped `offer_details` while older ones
    # return a single-quoted JavaScript variable. Decode both forms.
    object_start = re.search(r"\bvar\s+offer_details\s*=\s*", payload)
    if object_start:
        try:
            parsed, _ = json.JSONDecoder().raw_decode(payload[object_start.end():].lstrip())
            if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
                raw_html = parsed["content"]
        except (json.JSONDecodeError, TypeError):
            pass
    if raw_html == payload:
        match = re.match(r"\s*var\s+\w+\s*=\s*'(.*)'\s*;?\s*$", payload, re.S)
        raw_html = match.group(1) if match else payload
        raw_html = raw_html.replace("\r\\\n", "").replace("\\\n", "")
        raw_html = raw_html.replace("\\'", "'").replace("\\/", "/")
    soup = BeautifulSoup(raw_html, "html.parser")
    images = unique([
        normalize_image_url(image.get("src") or image.get("data-src") or "")
        for image in soup.find_all("img")
        if is_product_image(normalize_image_url(image.get("src") or image.get("data-src") or ""))
    ])
    return {
        "source_url": source_url,
        "html": raw_html,
        "text": clean_text(soup.get_text(" ", strip=True)),
        "images": images,
    }


def fetch_detail(page_html: str) -> dict[str, Any]:
    detail_url = extract_detail_url(page_html)
    if not detail_url:
        return {"source_url": "", "html": "", "text": "", "images": []}
    data, headers = read_allowlisted_url(detail_url, {"itemcdn.tmall.com"})
    charset = headers.get_content_charset() or "gb18030"
    payload = data.decode(charset, errors="replace")
    return parse_detail_response(payload, detail_url)


def parse_html(
    html: str,
    source_url: str,
    collected_at: str | None = None,
    body_text_override: str | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    body = clean_text(body_text_override or (soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)))
    title = parse_title(soup)
    prices = [float(value) for value in re.findall(r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", body)]
    prices = unique([str(value) for value in prices])
    primary_match = re.search(r"商品复购率.*?[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", body)
    primary_price = float(primary_match.group(1)) if primary_match else (float(prices[0]) if prices else None)
    if primary_price is None:
        embedded_price = re.search(r'"skuPriceScale"\s*:\s*"([0-9]+(?:\.[0-9]+)?)"', html)
        primary_price = float(embedded_price.group(1)) if embedded_price else None
    stock_values = [int(value) for value in re.findall(r"库存\s*([0-9]+)", body)]
    warnings = unique([
        clean_text(match.group(0))
        for match in re.finditer(r"(?:提醒您|专供外贸|不符合境内产品标准|禁止向)[^。]{0,180}", body)
    ])
    offer_id = extract_offer_id(source_url)
    begin_amount = re.search(r"[\"']beginAmount[\"']\s*:\s*(\d+)", html)
    min_order_match = re.search(r"(\d+)\s*(件|盒|个)起批", body)
    min_order = min_order_match.group(0) if min_order_match else (f"{begin_amount.group(1)}件起批" if begin_amount else "")
    parsed_skus = parse_embedded_skus(html, primary_price) or parse_skus(body)
    gallery_images = parse_images(soup, html)
    product = {
        "schema_version": "1.0",
        "status": "blocked" if is_blocked(source_url, soup.title.get_text(" ", strip=True) if soup.title else "", body) else "ok",
        "source": {
            "platform": "1688",
            "offer_id": offer_id,
            "url": source_url,
            "collected_at": collected_at or now_iso(),
        },
        "category": {
            "top_id": int(match.group(1)) if (match := re.search(r'\"topCategoryId\"\s*:\s*(\d+)', html)) else None,
            "second_id": int(match.group(1)) if (match := re.search(r'\"secondCategoryId\"\s*:\s*(\d+)', html)) else None,
            "leaf_id": int(match.group(1)) if (match := re.search(r'\"leafCategoryId\"\s*:\s*(\d+)', html)) else None,
            "leaf_name": (match.group(1) if (match := re.search(r'\"leafCategoryName\"\s*:\s*\"([^\"]+)\"', html)) else ""),
        },
        "title": title,
        "seller": parse_seller(body),
        "price": {
            "primary": primary_price,
            "observed": [float(value) for value in prices],
            "min_order": min_order,
            "freight_from": float(re.search(r"运费\s*[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", body).group(1)) if re.search(r"运费\s*[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", body) else None,
        },
        "stock": {
            "total_observed": sum(stock_values) if stock_values else None,
            "sku_values": stock_values,
        },
        "attributes": parse_attributes(soup),
        # The embedded map carries the source skuId; rendered text is the fallback
        # for pages where the map is missing or has not loaded yet.
        "skus": parsed_skus,
        # Keep a page-independent SKU contract in the collection itself. The
        # browser publisher may still revalidate against the live target page,
        # but it no longer has to reinterpret raw display names.
        "sku_model": normalize_sku_model(parsed_skus),
        "images": gallery_images,
        "detail_text": parse_detail_text(body),
        "description": {"source_url": "", "html": "", "text": "", "images": []},
        "warnings": warnings,
        "raw": {
            "page_title": clean_text(soup.title.get_text(" ", strip=True) if soup.title else ""),
            "body_length": len(body),
            "image_source": "structured_gallery" if gallery_images else "untrusted_or_missing",
        },
    }
    product["validation"] = validate_product(product)
    return product


def is_blocked(url: str, title: str, body: str) -> bool:
    haystack = " ".join((url, title, body)).lower()
    return any(marker.lower() in haystack for marker in BLOCK_MARKERS)


def validate_product(product: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "offer_id": bool(product["source"].get("offer_id")),
        "title": bool(product.get("title")) and not re.fullmatch(r"TOP\s*\d+", product.get("title", ""), re.I),
        "images": bool(product.get("images")),
        "structured_gallery": product.get("raw", {}).get("image_source") == "structured_gallery",
        "attributes": bool(product.get("attributes")),
        "sku_or_price": bool(product.get("skus")) or product.get("price", {}).get("primary") is not None,
        "not_blocked": product.get("status") != "blocked",
    }
    return {"passed": all(checks.values()), "checks": checks}


def detect_blocked_page(page: Any) -> bool:
    try:
        url = str(page.url)
    except Exception:
        url = ""
    try:
        title = str(page.title)
    except Exception:
        title = ""
    try:
        body = page.ele("tag:body").text
    except Exception:
        body = ""
    return is_blocked(url, title, body)


def collect_with_browser(url: str, profile_dir: Path, wait_seconds: int) -> tuple[str, str, str]:
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError as exc:
        raise CollectionError("缺少 DrissionPage，请先安装 requirements-1688.txt") from exc

    profile_dir.mkdir(parents=True, exist_ok=True)
    options = ChromiumOptions()
    options.set_user_data_path(str(profile_dir.resolve()))
    options.headless(False)
    page = ChromiumPage(options)
    try:
        page.get(validate_url(url))
        try:
            page.wait.load_start()
        except Exception:
            pass
        time.sleep(3)
        if detect_blocked_page(page) and wait_seconds != 0:
            deadline = None if wait_seconds < 0 else time.time() + wait_seconds
            while (deadline is None or time.time() < deadline) and detect_blocked_page(page):
                time.sleep(2)
        html = page.html
        try:
            body_text = page.ele("tag:body").text
        except Exception:
            body_text = ""
        return str(page.url), html, body_text
    finally:
        try:
            page.quit()
        except Exception:
            pass


def download_images(
    urls: list[str], asset_dir: Path, prefix: str = "image", namespace: str = "", max_total_bytes: int = MAX_TOTAL_IMAGE_BYTES
) -> list[dict[str, Any]]:
    asset_dir.mkdir(parents=True, exist_ok=True)
    results = []
    total_bytes = 0
    for index, url in enumerate(urls, start=1):
        suffix = ".jpg"
        match = re.search(r"\.(jpg|jpeg|png|webp)(?:[?_]|$)", url, re.I)
        if match:
            suffix = "." + match.group(1).lower()
        # 1688's picture manager identifies uploaded assets by filename. A
        # fixed name such as image-01 causes a later product to reuse an older
        # upload. Include both the offer ID and URL fingerprint in every local
        # filename so different products cannot collide.
        safe_namespace = re.sub(r"[^0-9A-Za-z_-]+", "-", namespace).strip("-") or "offer"
        fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        path = asset_dir / f"{safe_namespace}-{prefix}-{index:02d}-{fingerprint}{suffix}"
        item = {"url": url, "path": str(path), "status": "pending"}
        try:
            if not is_product_image(url):
                raise ValueError("图片 URL 未通过 1688 图库主机校验")
            remaining = max_total_bytes - total_bytes
            if remaining <= 0:
                raise ValueError("商品图片总量超过限制")
            bytes_written = download_image(url, path, max_bytes=min(5 * 1024 * 1024, remaining))
            total_bytes += bytes_written
            if total_bytes > MAX_TOTAL_IMAGE_BYTES:
                raise ValueError("商品图片总量超过限制")
            item["status"] = "saved"
        except Exception as exc:  # network failures should not discard the product record
            item["status"] = "failed"
            item["error"] = str(exc)
        results.append(item)
    return results


def save_collection(product: dict[str, Any], html: str, output_dir: Path, download: bool) -> Path:
    offer_id = product["source"]["offer_id"]
    target = output_dir / offer_id
    target.mkdir(parents=True, exist_ok=True)
    atomic_write(target / "raw.html", html)
    if download:
        product["assets"] = download_images(
            product.get("images", []), target / "assets", namespace=offer_id
        )
        main_bytes = sum(Path(item["path"]).stat().st_size for item in product["assets"] if item.get("status") == "saved")
        for item in product["assets"]:
            if item.get("path"):
                item["path"] = str(Path("assets") / Path(item["path"]).name)
        product["detail_assets"] = download_images(
            product.get("description", {}).get("images", []),
            target / "detail-assets",
            "detail",
            namespace=offer_id,
            max_total_bytes=max(0, MAX_TOTAL_IMAGE_BYTES - main_bytes),
        )
        for item in product["detail_assets"]:
            if item.get("path"):
                item["path"] = str(Path("detail-assets") / Path(item["path"]).name)
    else:
        product["assets"] = []
        product["detail_assets"] = []
    atomic_write(target / "product.json", json.dumps(product, ensure_ascii=False, indent=2))
    return target


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="本地采集并保存一个 1688 商品详情")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="1688 商品详情页 URL")
    source.add_argument("--html", type=Path, help="离线解析 HTML 文件")
    parser.add_argument("--source-url", help="离线 HTML 对应的原始 1688 商品链接")
    parser.add_argument("--output-dir", type=Path, default=Path("data/1688-products"))
    parser.add_argument("--profile-dir", type=Path, default=Path(".local/1688-browser"))
    parser.add_argument(
        "--wait-for-challenge", type=int, default=0,
        help="检测到登录/验证页后等待用户处理的秒数；负数表示不限时",
    )
    parser.add_argument("--no-download-images", action="store_true")
    args = parser.parse_args(argv)

    try:
        body_text = None
        if args.html:
            source_url = validate_url(args.source_url) if args.source_url else ""
            if not source_url:
                raise CollectionError("--html 模式必须同时提供 --source-url")
            html = args.html.read_text(encoding="utf-8")
            final_url = source_url
        else:
            source_url = validate_url(args.url)
            final_url, html, body_text = collect_with_browser(source_url, args.profile_dir, args.wait_for_challenge)

        product = parse_html(html, final_url or source_url, body_text_override=body_text)
        if not args.html:
            try:
                product["description"] = fetch_detail(html)
                product["detail_text"] = product["description"]["text"]
            except Exception as exc:
                product.setdefault("warnings", []).append(f"详情接口采集失败: {exc}")
        target = save_collection(product, html, args.output_dir, not args.no_download_images)
        print(json.dumps({
            "status": product["status"],
            "offer_id": product["source"]["offer_id"],
            "title": product["title"],
            "sku_count": len(product["skus"]),
            "image_count": len(product["images"]),
            "validation": product["validation"],
            "saved_to": str(target.resolve()),
        }, ensure_ascii=False, indent=2))
        return 0 if product["validation"]["passed"] else 2
    except (CollectionError, OSError, ValueError) as exc:
        print(f"采集失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
