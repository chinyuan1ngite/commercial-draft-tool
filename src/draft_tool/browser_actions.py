"""Fill a 1688 seller form and optionally save it as a draft.

The script never clicks the publish button. It also installs browser-side guards
that reject clicks on #submitFormButton and requests ending in /submit.htm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from DrissionPage import ChromiumOptions, ChromiumPage
from PIL import Image

from .sku_adapter import normalize_sku_model, validate_target_rows
from .security import atomic_write


PUBLISH_URL = "https://offer-new.1688.com/popular/publish.htm"
DRAFT_INDEX_URL = "https://offer.1688.com/offer/draft_index.htm"
SELLER_LOGIN_HOSTS = frozenset({
    "login.taobao.com",
    "login.1688.com",
    "passport.1688.com",
    "passport.alibaba.com",
    "login.alibaba.com",
})


def is_seller_login_url(value: Any) -> bool:
    try:
        hostname = (urlparse(str(value)).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return hostname in SELLER_LOGIN_HOSTS


def wait_for_seller_login(
    page: ChromiumPage,
    timeout_seconds: int,
    poll_seconds: float = 2.0,
) -> str:
    """Wait until interactive seller login completes or the browser is closed."""
    deadline = None if timeout_seconds <= 0 else time.monotonic() + timeout_seconds
    while True:
        try:
            current_url = str(page.url)
        except Exception:
            return "browser_closed"
        if not is_seller_login_url(current_url):
            return "authenticated"
        if deadline is not None and time.monotonic() >= deadline:
            return "login_timeout"
        delay = poll_seconds
        if deadline is not None:
            delay = min(delay, max(0.01, deadline - time.monotonic()))
        time.sleep(delay)


def open_seller_page(
    page: ChromiumPage,
    url: str,
    login_timeout_seconds: int,
    settle_seconds: float,
) -> str:
    """Open a seller page, pausing for interactive login before retrying it."""
    deadline = None if login_timeout_seconds <= 0 else time.monotonic() + login_timeout_seconds
    announced = False
    while True:
        try:
            page.get(url)
        except Exception:
            return "browser_closed"
        time.sleep(2)
        try:
            current_url = str(page.url)
        except Exception:
            return "browser_closed"
        if not is_seller_login_url(current_url):
            time.sleep(max(0.0, settle_seconds - 2))
            try:
                current_url = str(page.url)
            except Exception:
                return "browser_closed"
            if not is_seller_login_url(current_url):
                return "ready"
        if not announced:
            wait_text = "不限时" if deadline is None else f"最多 {login_timeout_seconds} 秒"
            print(f"检测到卖家登录页，程序将{wait_text}等待人工完成登录，请勿关闭浏览器。", flush=True)
            announced = True
        if deadline is not None:
            remaining = int(deadline - time.monotonic())
            if remaining <= 0:
                return "login_timeout"
        else:
            remaining = 0
        status = wait_for_seller_login(page, remaining)
        if status != "authenticated":
            return status
        # Login can land on an account home page. Loop and reopen the exact
        # seller URL, then verify it no longer redirects to authentication.


def load_product(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_paths(product_path: Path, product: dict[str, Any], key: str, directory: str) -> tuple[list[Path], list[str]]:
    root = (product_path.parent / directory).resolve()
    paths: list[Path] = []
    errors: list[str] = []
    for entry in product.get(key) or []:
        if not isinstance(entry, dict) or str(entry.get("status") or "") != "saved":
            continue
        raw = Path(str(entry.get("path") or ""))
        if raw.is_absolute() or ".." in raw.parts:
            errors.append(f"素材路径不允许绝对路径或目录穿越: {raw}")
            continue
        lexical = product_path.parent / raw
        if lexical.is_symlink():
            errors.append(f"素材为符号链接: {raw}")
            continue
        resolved = lexical.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"素材不属于 {directory} 目录: {raw}")
            continue
        if not resolved.is_file():
            errors.append(f"素材不存在或为符号链接: {raw}")
            continue
        paths.append(resolved)
    return paths, errors


def resolve_product_asset_paths(product_path: Path, product: dict[str, Any]) -> tuple[list[Path], list[str]]:
    """Resolve only the images recorded by this product's collection manifest.

    The old implementation scanned ``product_path.parent/assets``. That made
    it possible to combine one product.json with a stale or copied assets
    directory. The collector already records the exact local path for every
    downloaded image, so publishing should use that manifest as the source of
    truth.
    """
    entries = product.get("assets") or []
    if not entries:
        return [], ["product.json 没有 assets 清单"]
    paths, errors = _manifest_paths(product_path, product, "assets", "assets")
    if not paths:
        errors.append("没有可用的已下载主图")
    return paths, errors


def resolve_detail_asset_paths(product_path: Path, product: dict[str, Any]) -> tuple[list[Path], list[str]]:
    """Resolve detail images from the same collection manifest."""
    return _manifest_paths(product_path, product, "detail_assets", "detail-assets")


def image_info(path: Path) -> dict[str, Any]:
    """Read image dimensions without trusting a .jpg extension."""
    data = path.read_bytes()
    info: dict[str, Any] = {"path": str(path), "bytes": len(data), "format": "unknown"}
    if data.startswith(b"\x89PNG") and len(data) >= 24:
        info.update(format="png", width=struct.unpack(">I", data[16:20])[0], height=struct.unpack(">I", data[20:24])[0])
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        info["format"] = "webp"
        if data[12:16] == b"VP8X" and len(data) >= 30:
            info["width"] = 1 + int.from_bytes(data[24:27], "little")
            info["height"] = 1 + int.from_bytes(data[27:30], "little")
        elif data[12:16] == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            info["width"] = (bits & 0x3FFF) + 1
            info["height"] = ((bits >> 14) & 0x3FFF) + 1
    elif data[:2] == b"\xff\xd8":
        info["format"] = "jpeg"
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                break
            size = int.from_bytes(data[i:i + 2], "big")
            if marker in range(0xC0, 0xC4) or marker in range(0xC5, 0xC8) or marker in range(0xC9, 0xCC) or marker in range(0xCD, 0xD0):
                if i + 7 <= len(data):
                    info["height"] = int.from_bytes(data[i + 3:i + 5], "big")
                    info["width"] = int.from_bytes(data[i + 5:i + 7], "big")
                break
            i += max(size, 2)
    # Some WebP files use the lossy VP8 container, which has no dimensions in
    # the simple header fields above. Pillow is the authoritative fallback for
    # all supported image encodings.
    if not info.get("width") or not info.get("height"):
        try:
            with Image.open(path) as image:
                info.update(
                    format=(image.format or info.get("format") or "unknown").lower(),
                    width=image.width,
                    height=image.height,
                )
        except Exception:
            pass
    return info


def select_main_images(
    paths: list[Path], output_dir: Path, namespace: str = ""
) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted, accepted_meta, rejected = [], [], []
    seen: set[tuple[int, int, bytes]] = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        try:
            meta = image_info(path)
            valid = meta.get("format") in {"jpeg", "png", "webp"} and meta.get("width", 0) >= 800 and meta.get("height", 0) >= 800 and meta["bytes"] <= 5 * 1024 * 1024
            meta["status"] = "accepted" if valid else "rejected"
            if valid and len(accepted) < 4:
                with Image.open(path) as image:
                    rgb = image.convert("RGB")
                    signature = (rgb.width, rgb.height, rgb.resize((16, 16)).tobytes())
                    if signature in seen:
                        meta.update(status="rejected", reason="duplicate image")
                        rejected.append(meta)
                        continue
                    seen.add(signature)
                    prefix = re.sub(r"[^0-9A-Za-z_-]+", "-", namespace).strip("-") or "offer"
                    target = output_dir / f"{prefix}-main-{len(accepted) + 1:02d}-{signature[2][:8].hex()}.jpg"
                    rgb.save(target, format="JPEG", quality=92, optimize=True)
                    accepted.append(target)
                    meta["normalized_path"] = str(target)
                    accepted_meta.append(meta)
            else:
                if not valid:
                    meta["reason"] = "requires JPEG/PNG/WebP, at least 800x800, no more than 5MB"
                else:
                    meta.update(status="rejected", reason="exceeds the four-image upload limit")
                rejected.append(meta)
        except Exception as exc:
            rejected.append({"path": str(path), "status": "rejected", "reason": str(exc)})
    return accepted, accepted_meta, rejected


def prepare_detail_images(
    paths: list[Path], output_dir: Path, max_height: int = 4000, namespace: str = ""
) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    """Combine source detail images into a small ordered set of safe long images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    loaded: list[tuple[Path, Image.Image]] = []
    rejected: list[dict[str, Any]] = []
    for path in paths:
        try:
            with Image.open(path) as source:
                loaded.append((path, source.convert("RGB")))
        except Exception as exc:
            rejected.append({"path": str(path), "reason": str(exc)})

    groups: list[list[tuple[Path, Image.Image]]] = []
    current: list[tuple[Path, Image.Image]] = []
    current_height = 0
    for item in loaded:
        height = item[1].height
        if current and current_height + height > max_height:
            groups.append(current)
            current = []
            current_height = 0
        current.append(item)
        current_height += height
    if current:
        groups.append(current)

    prepared: list[Path] = []
    metadata: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        width = max(image.width for _, image in group)
        height = sum(image.height for _, image in group)
        canvas = Image.new("RGB", (width, height), "white")
        top = 0
        for _, image in group:
            canvas.paste(image, ((width - image.width) // 2, top))
            top += image.height
        prefix = re.sub(r"[^0-9A-Za-z_-]+", "-", namespace).strip("-") or "offer"
        digest = hashlib.sha256(
            b"".join(image.tobytes() for _, image in group)
        ).hexdigest()[:12]
        target = output_dir / f"{prefix}-detail-page-{index:02d}-{digest}.jpg"
        canvas.save(target, format="JPEG", quality=90, optimize=True)
        prepared.append(target)
        metadata.append({
            "path": str(target),
            "width": width,
            "height": height,
            "bytes": target.stat().st_size,
            "source_files": [path.name for path, _ in group],
        })
    return prepared, metadata, rejected


def _picker_select_titles(frame: Any, titles: list[str]) -> int:
    """Select exact image titles from the current picture-manager album."""
    # DrissionPage cannot serialize a Python list as a frame.run_js argument.
    # Pass JSON text and parse it inside the picker frame instead.
    return int(frame.run_js(
        """
        const wanted = JSON.parse(arguments[0]);
        const norm = value => String(value || '').trim().replace(/[.](?:jpe?g|png|webp)$/i, '');
        const links = Array.from(document.querySelectorAll('a[title], a img[alt], a[data-name], a[data-file-name]'))
          .map(node => node.matches('a') ? node : node.closest('a'))
          .filter(Boolean)
          .filter(e => {
            if (e.offsetParent === null) return false;
            const values = [e.title, e.getAttribute('data-name'), e.getAttribute('data-file-name'), e.querySelector('img')?.alt]
              .map(norm).filter(Boolean);
            return wanted.some(target => {
              const requested = norm(target);
              return values.some(value => value === requested || value.startsWith(requested) || requested.startsWith(value));
            });
          });
        const seen = new Set();
        let count = 0;
        for (const link of links) {
          if (seen.has(link.title)) continue;
          seen.add(link.title);
          link.click();
          count += 1;
        }
        return count;
        """,
        json.dumps(titles, ensure_ascii=False),
    ) or 0)


def _picker_available_titles(frame: Any, titles: list[str]) -> list[str]:
    """Return requested titles that are visible in the current album page."""
    return list(frame.run_js(
        """
        const requested = JSON.parse(arguments[0]);
        const norm = value => String(value || '').trim().replace(/[.](?:jpe?g|png|webp)$/i, '');
        const available = Array.from(document.querySelectorAll('a[title], a img[alt], a[data-name], a[data-file-name]'))
          .map(node => node.matches('a') ? node : node.closest('a')).filter(Boolean)
          .filter(e => e.offsetParent !== null)
          .flatMap(e => [e.title, e.getAttribute('data-name'), e.getAttribute('data-file-name'), e.querySelector('img')?.alt].map(norm));
        return requested.filter(title => {
          const wanted = norm(title);
          return available.some(value => value === wanted || value.startsWith(wanted) || wanted.startsWith(value));
        });
        """,
        json.dumps(titles, ensure_ascii=False),
    ) or [])


def _picker_search_title(frame: Any, title: str) -> bool:
    return bool(frame.run_js(
        """
        const input = document.querySelector('input.album-search');
        const button = document.querySelector('input.album-btn');
        if (!input || !button) return false;
        input.value = arguments[0];
        input.dispatchEvent(new Event('input', {bubbles: true}));
        input.dispatchEvent(new Event('change', {bubbles: true}));
        button.click();
        return true;
        """,
        title,
    ))


def _picker_pool_count(frame: Any) -> int:
    return int(frame.run_js(
        "return document.querySelectorAll('.insert-pool li').length;"
    ) or 0)


def _picker_clear_pool(frame: Any) -> int:
    """Remove selections left by an interrupted previous picker transaction."""
    initial = _picker_pool_count(frame)
    deadline = time.time() + 5
    while _picker_pool_count(frame) > 0 and time.time() < deadline:
        changed = bool(frame.run_js(
            """
            const pool = document.querySelector('.insert-pool');
            if (!pool) return false;
            const controls = Array.from(pool.querySelectorAll('a,button,[role="button"],i,span,em'));
            const remove = controls.find(node => {
              const value = [node.className, node.title, node.getAttribute('aria-label'), node.innerText]
                .filter(Boolean).join(' ');
              return /删除|移除|remove|delete|close/i.test(value);
            });
            if (!remove) return false;
            remove.click();
            return true;
            """
        ))
        if not changed:
            break
        time.sleep(.25)
    remaining = _picker_pool_count(frame)
    if remaining:
        raise RuntimeError(f"cannot clear stale selection pool ({remaining}/{initial})")
    return initial


def _picker_pool_records(frame: Any) -> list[dict[str, str]]:
    """Read the images currently staged for the picker commit."""
    return list(frame.run_js(
        """
        return Array.from(document.querySelectorAll('.insert-pool li')).map(li => {
          const link = li.querySelector('a');
          const img = li.querySelector('img');
          return {
            title: String(link?.title || img?.alt || ''),
            src: String(img?.src || img?.getAttribute('data-src') || '')
          };
        });
        """
    ) or [])


def _picker_upload_success_count(frame: Any) -> int:
    """Read the upload counter instead of treating stale success text as new."""
    return int(frame.run_js(
        """
        const text = document.body?.innerText || '';
        const match = text.match(/上传成功[^0-9]*(\\d+)\\s*张/);
        return match ? Number(match[1]) : 0;
        """
    ) or 0)


def _picker_image_records(frame: Any, titles: list[str]) -> list[dict[str, str]]:
    """Return visible album records for this run, including remote URLs."""
    return list(frame.run_js(
        """
        const wanted = JSON.parse(arguments[0]);
        const norm = value => String(value || '').trim().replace(/[.](?:jpe?g|png|webp)$/i, '');
        return Array.from(document.querySelectorAll('a[title], a img[alt], a[data-name], a[data-file-name]'))
          .map(node => node.matches('a') ? node : node.closest('a'))
          .filter(Boolean)
          .filter(e => e.offsetParent !== null)
          .map(e => {
            const title = e.title || e.getAttribute('data-name') || e.getAttribute('data-file-name') || e.querySelector('img')?.alt || '';
            const img = e.querySelector('img');
            return {
              title: String(title),
              src: String(img?.src || e.getAttribute('data-src') || ''),
              id: String(e.getAttribute('data-id') || e.getAttribute('data-image-id') || '')
            };
          })
          .filter(item => wanted.some(target => {
            const a = norm(item.title), b = norm(target);
            return a === b || a.startsWith(b) || b.startsWith(a);
          }));
        """,
        json.dumps(titles, ensure_ascii=False),
    ) or [])


def _main_image_records(page: ChromiumPage) -> list[dict[str, str]]:
    return list(page.run_js(
        """
        return Array.from(document.querySelectorAll('#guid-primaryPicture .module-picture-cover-wrapper:not(.cover-empty) img'))
          .map(img => ({src: String(img.src || img.getAttribute('data-src') || ''), alt: String(img.alt || '')}));
        """
    ) or [])


def _picker_submit(frame: Any) -> bool:
    pool_count = _picker_pool_count(frame)
    if pool_count < 1:
        return False
    return bool(frame.run_js(
        """
        const node = Array.from(document.querySelectorAll('.ib-footer.action .button.submit'))
          .find(e => e.offsetParent !== null);
        if (!node) return false;
        node.click();
        return true;
        """
    ))


def _description_preview_image_count(page: ChromiumPage) -> int:
    return int(page.run_js(
        """
        const frames = Array.from(
          document.querySelectorAll('#guid-description iframe.new-editor-preview-content')
        );
        return Math.max(0, ...frames.map(frame => {
          try { return frame.contentDocument?.querySelectorAll('img').length || 0; }
          catch (error) { return 0; }
        }));
        """
    ) or 0)


def install_publish_guards(page: ChromiumPage) -> None:
    page.run_js(
        r"""
        (() => {
          if (window.__commercialDraftGuardsInstalled) return;
          window.__commercialDraftGuardsInstalled = true;
          window.__commercialDraftGuardEvents = [];
          const formal = value => /(?:submitFormButton|正式发布|立即发布|\/submit\.htm)(?:[?#]|$)?/i.test(String(value || '')) && !/draftSubmit\.htm/i.test(String(value || ''));
          const block = (kind, value) => {
            window.__commercialDraftGuardEvents.push({kind, value: String(value), blocked: true, at: new Date().toISOString()});
            throw new Error('Formal publishing is disabled by the draft-only guard.');
          };
          document.addEventListener('click', event => {
            const target = event.target && event.target.closest ? event.target.closest('button,a,input[type=submit]') : null;
            const evidence = target ? [target.id, target.name, target.value, target.innerText, target.formAction, target.href].join(' ') : '';
            if (formal(evidence)) {
              event.preventDefault();
              event.stopImmediatePropagation();
              block('click', evidence);
            }
          }, true);
          document.addEventListener('submit', event => {
            const evidence = [event.target?.action, event.submitter?.id, event.submitter?.innerText].join(' ');
            if (formal(evidence)) { event.preventDefault(); event.stopImmediatePropagation(); block('form', evidence); }
          }, true);
          const originalFetch = window.fetch;
          window.fetch = function(input, init) {
            const url = typeof input === 'string' ? input : (input && input.url) || '';
            if (formal(url)) {
              window.__commercialDraftGuardEvents.push({kind: 'fetch', value: String(url), blocked: true, at: new Date().toISOString()});
              return Promise.reject(new Error('Formal publish request blocked.'));
            }
            return originalFetch.apply(this, arguments);
          };
          const originalOpen = XMLHttpRequest.prototype.open;
          XMLHttpRequest.prototype.open = function(method, url) {
            if (formal(url)) {
              block('xhr', url);
            }
            return originalOpen.apply(this, arguments);
          };
          const originalBeacon = navigator.sendBeacon?.bind(navigator);
          if (originalBeacon) navigator.sendBeacon = function(url, data) {
            if (formal(url)) block('sendBeacon', url);
            return originalBeacon(url, data);
          };
          const originalOpenWindow = window.open;
          window.open = function(url) { if (formal(url)) block('window.open', url); return originalOpenWindow.apply(this, arguments); };
        })();
        """
    )


def read_publish_guard_events(page: ChromiumPage) -> list[dict[str, Any]]:
    try:
        return list(page.run_js("return window.__commercialDraftGuardEvents || [];") or [])
    except Exception:
        return []


def input_value(page: ChromiumPage, selector: str, value: str) -> bool:
    ele = page.ele(f"css:{selector}", timeout=3)
    if not ele:
        return False
    ele.input(value, clear=True)
    return True


def upload_file(page: ChromiumPage, path: Path) -> bool:
    """Upload a main image through the seller page's picture manager.

    The seller form does not insert a local file directly. It opens the picture
    manager, uploads the file, selects an image from the manager, and then
    inserts it into the main-image slot.
    """
    if not path.exists():
        return False
    try:
        before = int(page.run_js(
            "return document.querySelectorAll('#guid-primaryPicture "
            ".module-picture-cover-wrapper:not(.cover-empty)').length;"
        ) or 0)
        triggers = page.eles("css:#guid-primaryPicture .cover-empty .picture-cover-content")
        trigger = triggers[0] if triggers else None
        if not trigger:
            return False
        trigger.click()
        time.sleep(2)
        frame = page.get_frame("css:iframe.picker-frame", timeout=5)
        if not frame:
            return False
        # Reuse an exact same-title upload when present. This also avoids an
        # unnecessary iframe reload on retry after a transient picker failure.
        if _picker_select_titles(frame, [path.stem]) > 0 and _picker_submit(frame):
            time.sleep(2)
            deadline = time.time() + 8
            after = before
            while time.time() < deadline and after <= before:
                after = int(page.run_js(
                    "return document.querySelectorAll('#guid-primaryPicture "
                    ".module-picture-cover-wrapper:not(.cover-empty)').length;"
                ) or 0)
                time.sleep(.4)
            return after > before
        frame.run_js("document.querySelector('li.tab-upload')?.click();")
        time.sleep(.8)
        file_input = frame.ele('css:input[type="file"]', timeout=3)
        if not file_input:
            return False
        file_input.input(str(path.resolve()))
        deadline = time.time() + 15
        while time.time() < deadline:
            body = frame.ele("tag:body")
            text = (body.text or "") if body else ""
            if "上传成功" in text:
                break
            time.sleep(.5)
    # The album search does not index the local filename reliably. After an
    # upload, the first visible album item is the deterministic fallback; the
    # selected item and resulting platform URL are recorded in the report.
        album_clicked = frame.run_js(
            "const n=document.querySelector('li.tab-album'); if(n){n.click(); return true;} return false;"
        )
        if album_clicked:
            time.sleep(2)
        selected = _picker_select_titles(frame, [path.stem])
        time.sleep(.6)
        if selected < 1:
            return False
        submitted = _picker_submit(frame)
        if not submitted:
            return False
        deadline = time.time() + 8
        after = before
        while time.time() < deadline and after <= before:
            after = int(page.run_js(
                "return document.querySelectorAll('#guid-primaryPicture "
                ".module-picture-cover-wrapper:not(.cover-empty)').length;"
            ) or 0)
            time.sleep(.4)
        return after > before
    except Exception:
        return False
    finally:
        # A failed picker operation must not leave its modal overlay over the
        # description editor or prevent the remaining fields from being saved.
        try:
            page.run_js("""
              document.querySelector('.ibank-picker-dialog .close')?.click();
              document.querySelector('.ui-dialog-overlay')?.remove();
            """)
        except Exception:
            pass


def _close_picture_picker(page: ChromiumPage) -> None:
    try:
        page.run_js("""
          document.querySelector('.ibank-picker-dialog .close')?.click();
          document.querySelector('.ui-dialog-overlay')?.remove();
        """)
    except Exception:
        pass


def _open_main_picture_picker(page: ChromiumPage) -> Any:
    triggers = page.eles("css:#guid-primaryPicture .cover-empty .picture-cover-content")
    trigger = triggers[0] if triggers else None
    if not trigger:
        return None
    trigger.click()
    time.sleep(1.5)
    return page.get_frame("css:iframe.picker-frame", timeout=5)


def upload_main_images_two_phase(page: ChromiumPage, paths: list[Path]) -> dict[str, Any]:
    """Upload, verify, multi-select, and insert the main images as one batch.

    The picker keeps the newly uploaded album state in the current iframe. A
    previous implementation closed that iframe after every upload and then
    relied on a delayed filename search, which frequently left the selection
    pool empty. This implementation keeps one picker session open, returns to
    the album after each upload, verifies the new item is visible, and submits
    the accumulated pool exactly once.
    """
    result: dict[str, Any] = {
        "requested": len(paths), "uploaded": [], "upload_failed": [],
        "upload_records": [], "selected": [], "selected_records": [],
        "select_failed": [], "selection_submitted_once": False,
    }
    frame = None
    try:
        before = len(_main_image_records(page))
        frame = _open_main_picture_picker(page)
        if not frame:
            raise RuntimeError("picture picker unavailable")
        result["pool_count_before"] = _picker_pool_count(frame)
        result["pool_cleared"] = _picker_clear_pool(frame)
        result["pool_count_after_clear"] = _picker_pool_count(frame)

        for path in paths:
            if not path.exists():
                result["upload_failed"].append({"path": str(path), "reason": "missing"})
                continue
            try:
                frame.run_js("document.querySelector('li.tab-upload')?.click();")
                time.sleep(.7)
                file_input = frame.ele('css:input[type="file"]', timeout=3)
                if not file_input:
                    raise RuntimeError("upload input unavailable")
                previous_count = _picker_upload_success_count(frame)
                file_input.input(str(path.resolve()))
                deadline = time.time() + 20
                while time.time() < deadline and _picker_upload_success_count(frame) <= previous_count:
                    time.sleep(.4)
                current_count = _picker_upload_success_count(frame)
                if current_count <= previous_count:
                    raise RuntimeError("upload did not report a new success")
                result["uploaded"].append(str(path))

                # Stay in this iframe and wait for the item to enter the album index.
                frame.run_js("document.querySelector('li.tab-album')?.click();")
                time.sleep(1)
                records: list[dict[str, str]] = []
                album_deadline = time.time() + 15
                while time.time() < album_deadline and not records:
                    records = _picker_image_records(frame, [path.stem])
                    if not records:
                        time.sleep(.5)
                if not records:
                    raise RuntimeError("uploaded image not visible in album")
                result["upload_records"].append({"path": str(path), **records[0]})
            except Exception as exc:
                result["upload_failed"].append({
                    "path": str(path), "reason": type(exc).__name__, "message": str(exc)
                })

        uploaded_paths = [path for path in paths if str(path) in result["uploaded"]]
        if len(uploaded_paths) != len(paths):
            raise RuntimeError(f"only {len(uploaded_paths)}/{len(paths)} images uploaded")

        # Uploading through the main-image picker often stages the new image
        # automatically. Read the pool first; clicking an already staged item
        # would toggle it off and was the direct cause of the previous failure.
        result["pool_count_before_selection"] = _picker_pool_count(frame)
        selected_records: list[dict[str, str]] = []
        pool_records = _picker_pool_records(frame)
        for path in uploaded_paths:
            records = _picker_image_records(frame, [path.stem])
            if not records:
                if _picker_search_title(frame, path.stem):
                    time.sleep(1.2)
                    records = _picker_image_records(frame, [path.stem])
            if not records:
                raise RuntimeError(f"uploaded image not selectable: {path.stem}")
            record = records[0]
            already_staged = any(
                (record.get("src") and item.get("src") == record.get("src"))
                or (record.get("title") and item.get("title") == record.get("title"))
                for item in pool_records
            )
            if not already_staged:
                before_pool = _picker_pool_count(frame)
                clicked = _picker_select_titles(frame, [record["title"]])
                deadline = time.time() + 4
                after_pool = before_pool
                while time.time() < deadline and after_pool <= before_pool and clicked:
                    time.sleep(.25)
                    after_pool = _picker_pool_count(frame)
                if after_pool <= before_pool:
                    raise RuntimeError(f"selection pool did not increase for {path.stem}")
                pool_records = _picker_pool_records(frame)
            selected_records.append({"path": str(path), **record})
        result["selected_records"] = selected_records
        result["pool_count_after"] = _picker_pool_count(frame)
        if result["pool_count_after"] != len(uploaded_paths):
            raise RuntimeError(
                f"selection pool contains {result['pool_count_after']}/{len(uploaded_paths)} images"
            )
        if not _picker_submit(frame):
            raise RuntimeError("picture selection batch submit failed")
        result["selection_submitted_once"] = True

        deadline = time.time() + 12
        after = before
        while time.time() < deadline and after < before + len(uploaded_paths):
            after = len(_main_image_records(page))
            time.sleep(.4)
        result["main_slots_before"] = before
        result["main_slots_after"] = after
        result["main_image_records"] = _main_image_records(page)
        if after < before + len(uploaded_paths):
            raise RuntimeError(f"main-image slots contain {after - before}/{len(uploaded_paths)} images")
        result["selected"] = [str(path) for path in uploaded_paths]
    except Exception as exc:
        result["error"] = {"reason": type(exc).__name__, "message": str(exc)}
        result["select_failed"] = [
            {"path": str(path), "reason": type(exc).__name__, "message": str(exc)}
            for path in paths if str(path) not in result["selected"]
        ]
    finally:
        _close_picture_picker(page)
        time.sleep(.5)
    result["uploaded_count"] = len(result["uploaded"])
    result["selected_count"] = len(result["selected"])
    return result


def selected_prop_value(page: ChromiumPage, prop_id: str) -> str:
    return str(page.run_js(
        """
        const box = document.querySelector(`[cat-prop-id="${arguments[0]}"]`);
        if (!box) return '';
        const values = box.querySelector('.next-select-values');
        return (values?.innerText || values?.textContent || '').trim();
        """,
        prop_id,
    ) or "").strip()


def fill_delivery_time(page: ChromiumPage, value: str) -> str:
    """Select an exact delivery promise and return the displayed value."""
    shown = page.run_js(
        """
        const box = document.querySelector('#guid-deliveryTime');
        if (!box) return false;
        box.style.display = 'block';
        const control = box.querySelector('.next-select-trigger');
        if (!control) return false;
        control.click();
        return true;
        """
    )
    if not shown:
        return ""
    time.sleep(.5)
    if not click_visible_text(page, value):
        return ""
    time.sleep(.5)
    return str(page.run_js(
        """
        const box = document.querySelector('#guid-deliveryTime');
        const input = box?.querySelector('input[role="combobox"]');
        const values = box?.querySelector('.next-select-values');
        return (values?.innerText || input?.getAttribute('aria-valuetext') || input?.value || '').trim();
        """
    ) or "").strip()


def fill_buyer_protection_delivery(page: ChromiumPage, preferred: str) -> str:
    """Fill the mandatory first-row dispatch promise in buyer protection."""
    selector = page.ele("css:#guid-buyerProtection tbody tr .ant-select-selector", timeout=3)
    if not selector:
        return ""
    time.sleep(.2)
    try:
        open_state = str(page.run_js(
            "return document.querySelector('#guid-buyerProtection tbody tr .ant-select')?.className || '';"
        ) or "")
        if "ant-select-open" not in open_state:
            selector.click()
    except Exception:
        return ""
    time.sleep(.8)
    # Ant Design renders the menu in a portal. Restrict matching to the open
    # dropdown; hidden virtual-list options otherwise look like duplicates.
    option_title = page.run_js(
        """
        const norm = value => String(value || '').replace(/\\s+/g, '');
        const dropdown = Array.from(document.querySelectorAll('.ant-select-dropdown'))
          .find(e => !e.classList.contains('ant-select-dropdown-hidden') && e.offsetParent !== null);
        if (!dropdown) return '';
        const nodes = Array.from(dropdown.querySelectorAll('.ant-select-item-option'))
          .filter(e => e.offsetParent !== null);
        const preferred = nodes.filter(e => norm(e.innerText || e.textContent).includes(norm(arguments[0])));
        const node = preferred
          .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];
        if (!node) return '';
        return node.getAttribute('title') || (node.innerText || node.textContent || '').trim();
        """
        , preferred,
    ) or ""
    selected = ""
    if option_title:
        # Use a real element click so rc-select receives the same mouse event
        # sequence as a user click; HTMLElement.click() alone can leave the
        # React value unchanged on this page.
        option = page.ele(
            f'css:.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option[title="{option_title}"]',
            timeout=3,
        )
        if option:
            try:
                option.click()
                selected = option_title
            except Exception:
                selected = ""
    if not selected:
        # A virtual-list can be opened before its options are painted. Retry
        # once after closing/reopening the same control.
        try:
            selector = page.ele("css:#guid-buyerProtection tbody tr .ant-select-selector", timeout=2)
            selector.click()
            time.sleep(.8)
            option_title = page.run_js(
                """
                const norm = value => String(value || '').replace(/\\s+/g, '');
                const wanted = norm(arguments[0]);
                const node = Array.from(document.querySelectorAll('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option'))
                  .find(e => e.offsetParent !== null && norm(e.innerText || e.textContent).includes(wanted));
                return node?.getAttribute('title') || '';
                """,
                preferred,
            ) or ''
            if option_title:
                option = page.ele(
                    f'css:.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option[title="{option_title}"]', timeout=2
                )
                if option:
                    option.click()
                    selected = str(option.attr('title') or option_title)
        except Exception:
            pass
    if selected:
        time.sleep(.7)
        confirmed = str(page.run_js(
            """
            const box = document.querySelector('#guid-buyerProtection');
            const row = Array.from(box?.querySelectorAll('tr') || [])
              .find(r => r.querySelector('.ant-select'));
            return (row?.querySelector('.ant-select-selection-item')?.innerText || '').trim();
            """
        ) or "").strip()
        if confirmed and confirmed != '请选择':
            return confirmed
    return ""


def _compact_text(value: Any) -> str:
    """Normalize address/option text for matching across inconsistent spacing."""
    return re.sub(r"\s+", "", str(value or "")).strip()


def fill_shipping_address(page: ChromiumPage, preferred: str) -> dict[str, Any]:
    """Select the requested saved shipping address from the seller dropdown."""
    result: dict[str, Any] = {
        "requested": preferred,
        "displayed": "",
        "status": "not_found",
    }
    box = page.ele("css:#guid-cbuSendAddress", timeout=3)
    if not box:
        result["status"] = "control_missing"
        return result
    current = str(page.run_js(
        "return document.querySelector('#guid-cbuSendAddress .ant-select-selection-item')?.innerText || '';"
    ) or "").strip()
    if current and _compact_text(preferred) in _compact_text(current):
        result.update(displayed=current, status="selected")
        return result
    selector = box.ele("css:.ant-select-selector", timeout=2)
    if not selector:
        result["status"] = "selector_missing"
        return result
    selector.click()
    time.sleep(.8)
    selected = bool(page.run_js(
        """
        const wanted = String(arguments[0] || '').replace(/\\s+/g, '');
        const selectors = [
          '.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option',
          '.ant-select-dropdown:not(.ant-select-dropdown-hidden) [role="option"]',
          '[role="listbox"] [role="option"]'
        ];
        const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
        const node = nodes.find(e => e.offsetParent !== null &&
          String(e.innerText || e.textContent || '').replace(/\\s+/g, '').includes(wanted));
        if (!node) return false;
        node.click();
        return true;
        """,
        preferred,
    ))
    time.sleep(.8)
    displayed = str(page.run_js(
        "return document.querySelector('#guid-cbuSendAddress .ant-select-selection-item')?.innerText || '';"
    ) or "").strip()
    result["displayed"] = displayed
    if selected and displayed and _compact_text(preferred) in _compact_text(displayed):
        result["status"] = "selected"
    elif selected:
        result["status"] = "selected_text_mismatch"
    return result


def fill_freight_template(page: ChromiumPage, preferred: str) -> dict[str, Any]:
    """Select an explicitly configured existing freight template."""
    result: dict[str, Any] = {"requested": preferred, "displayed": "", "status": "not_found"}
    box = page.ele("css:#guid-freight", timeout=3)
    if not box:
        result["status"] = "control_missing"
        return result
    current = str(page.run_js(
        "return document.querySelector('#guid-freight .ant-select-selection-item')?.innerText || '';"
    ) or "").strip()
    if current and _compact_text(preferred) in _compact_text(current):
        result.update(displayed=current, status="selected")
        return result
    selector = box.ele("css:.ant-select-selector", timeout=2)
    if not selector:
        result["status"] = "selector_missing"
        return result
    selector.click()
    time.sleep(.8)
    selected = click_best_visible_option(page, preferred)
    time.sleep(.8)
    displayed = str(page.run_js(
        "return document.querySelector('#guid-freight .ant-select-selection-item')?.innerText || '';"
    ) or "").strip()
    result["displayed"] = displayed
    if selected and displayed and _compact_text(preferred) in _compact_text(displayed):
        result["status"] = "selected"
    elif selected:
        result["status"] = "selected_text_mismatch"
    return result


def fill_default_package_weight(page: ChromiumPage, weight_grams: int) -> dict[str, Any]:
    """Fill a default weight for every SKU row when source dimensions are absent.

    The official logistics module stores weight in grams. Dimensions remain blank
    because inventing length/width/height would be less reliable than leaving
    those fields for later manual confirmation.
    """
    result: dict[str, Any] = {
        "source": "default",
        "value": weight_grams / 1000,
        "unit": "kg",
        "page_unit": "g",
        "rows": 0,
        "filled": 0,
        "dimensions_filled": 0,
        "status": "control_missing",
    }
    module = page.ele("css:#guid-officialLogistics", timeout=3)
    if not module:
        return result
    rows = module.eles("css:tbody tr")
    result["rows"] = len(rows)
    # The module provides a batch field which commits all rows through its
    # React state, avoiding the occasional last-row loss seen with direct input.
    batch_input = module.ele('css:.measured-image-batch-bar__input input[placeholder="重量"]', timeout=1)
    batch_submit = module.ele('css:.measured-image-batch-bar__submit', timeout=1)
    if batch_input and batch_submit:
        batch_input.input(str(weight_grams), clear=True)
        batch_submit.click()
        time.sleep(.5)
    for row in rows:
        inputs = row.eles("tag:input")
        if len(inputs) < 4:
            continue
        # Inputs are ordered as length, width, height, weight (g).
        value = str(inputs[3].attr('value') or '')
        if value != str(weight_grams):
            inputs[3].input(str(weight_grams), clear=True)
            page.ele('css:#guid-title input', timeout=1).click()
            time.sleep(.15)
            value = str(inputs[3].attr('value') or '')
        if value == str(weight_grams):
            result["filled"] += 1
    result["status"] = "filled" if result["filled"] else "no_rows"
    return result


def insert_detail_images(
    page: ChromiumPage, paths: list[Path], allow_retry: bool = True
) -> dict[str, Any]:
    """Upload and insert detail images through the editor's image component."""
    result: dict[str, Any] = {"requested": len(paths), "inserted": 0, "batches": []}
    # One image per picker transaction avoids the editor dropping part of an
    # asynchronously inserted multi-image batch.
    for path in paths:
        batch = [path] if path.exists() else []
        batch_result: dict[str, Any] = {
            "files": [path.name for path in batch], "uploaded": False, "selected": 0, "submitted": False
        }
        result["batches"].append(batch_result)
        if not batch:
            continue
        try:
            preview_before = _description_preview_image_count(page)
            batch_result["preview_before"] = preview_before
            trigger = page.ele('css:#guid-description button[data-click="插图片"]', timeout=4)
            if not trigger:
                break
            trigger.click()
            time.sleep(1.5)
            frame = page.get_frame("css:iframe.picker-frame", timeout=5)
            if not frame:
                break
            batch_result["pool_cleared"] = _picker_clear_pool(frame)
            frame.run_js("document.querySelector('li.tab-album')?.click();")
            time.sleep(.8)
            record: dict[str, str] | None = None
            existing_deadline = time.time() + 3
            while time.time() < existing_deadline and not record:
                records = _picker_image_records(frame, [path.stem])
                record = records[0] if records else None
                if not record:
                    time.sleep(.4)
            if not record:
                frame.run_js("document.querySelector('li.tab-upload')?.click();")
                time.sleep(.5)
                file_input = frame.ele('css:input[type="file"]', timeout=3)
                if not file_input:
                    raise RuntimeError("detail upload input unavailable")
                previous_count = _picker_upload_success_count(frame)
                file_input.input(str(path.resolve()))
                deadline = time.time() + 20
                while time.time() < deadline and _picker_upload_success_count(frame) <= previous_count:
                    time.sleep(.4)
                if _picker_upload_success_count(frame) <= previous_count:
                    raise RuntimeError("detail upload did not report a new success")
                batch_result["uploaded_files"] = [path.name]
                frame.run_js("document.querySelector('li.tab-album')?.click();")
                time.sleep(.8)
                visible_deadline = time.time() + 15
                while time.time() < visible_deadline and not record:
                    records = _picker_image_records(frame, [path.stem])
                    record = records[0] if records else None
                    if not record:
                        time.sleep(.5)
                if not record:
                    raise RuntimeError("detail image not visible in album")
            pool_records = _picker_pool_records(frame)
            already_staged = any(
                (record.get("src") and item.get("src") == record.get("src"))
                or (record.get("title") and item.get("title") == record.get("title"))
                for item in pool_records
            )
            if not already_staged:
                before_pool = _picker_pool_count(frame)
                clicked = _picker_select_titles(frame, [record["title"]])
                deadline = time.time() + 4
                after_pool = before_pool
                while time.time() < deadline and after_pool <= before_pool and clicked:
                    time.sleep(.25)
                    after_pool = _picker_pool_count(frame)
                if after_pool <= before_pool:
                    raise RuntimeError("detail image was not added to selection pool")
            batch_result["selected"] = _picker_pool_count(frame)
            batch_result["record"] = record
            batch_result["uploaded"] = bool(batch_result.get("uploaded_files")) or "reused"
            batch_result["submitted"] = _picker_submit(frame)
            if batch_result["submitted"]:
                deadline = time.time() + 10
                while time.time() < deadline:
                    if _description_preview_image_count(page) > preview_before:
                        break
                    time.sleep(.5)
                preview_after = _description_preview_image_count(page)
                batch_result["preview_after"] = preview_after
                result["inserted"] += max(0, preview_after - preview_before)
        except Exception as exc:
            batch_result["error"] = type(exc).__name__
            batch_result["error_message"] = str(exc)
        finally:
            try:
                page.run_js("""
                  document.querySelector('.ibank-picker-dialog .close')?.click();
                  document.querySelector('.ui-dialog-overlay')?.remove();
                """)
            except Exception:
                pass
    return result


def fill_legacy_description_editor(
    page: ChromiumPage, product: dict[str, Any]
) -> dict[str, Any]:
    """Fallback for intermittent schema-editor iframe replacement.

    The publish page keeps a TinyMCE-compatible rich-text iframe even when the
    newer component editor cannot be opened. It is same-page content and can
    be populated without holding a fragile cross-frame target. Detail image
    URLs come from this product manifest, never from another local folder.
    """
    result: dict[str, Any] = {"text_component": False, "saved": False, "preview": "", "fallback": "legacy"}
    try:
        frame = page.get_frame("css:#tinyMCE-0_ifr", timeout=4)
        if not frame:
            return result
        body = frame.ele("tag:body", timeout=3)
        if not body:
            return result
        description = product.get("description") or {}
        text = str(description.get("text") or product.get("detail_text") or product.get("title") or "").strip()
        image_urls = [str(url).strip() for url in (description.get("images") or []) if str(url).strip()]
        html = "".join(f"<p>{line.strip()}</p>" for line in text.splitlines() if line.strip())
        html += "".join(f'<p><img src="{url}" /></p>' for url in image_urls[:50])
        # Prefer TinyMCE's own API so the parent React form receives its
        # model-change event; fall back to the iframe body for older builds.
        api_set = bool(page.run_js(
            """
            const html = arguments[0];
            const editor = window.tinymce?.get('tinyMCE-0');
            if (!editor) return false;
            editor.setContent(html);
            editor.fire('change');
            editor.fire('input');
            return true;
            """,
            html,
        ))
        if not api_set:
            body.run_js(
            """
            const html = arguments[0];
            this.innerHTML = html;
            this.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: html}));
            this.dispatchEvent(new Event('change', {bubbles: true}));
            this.dispatchEvent(new Event('blur', {bubbles: true}));
            return this.innerHTML;
            """,
                html,
            )
        time.sleep(1)
        result["text_component"] = bool(text)
        result["saved"] = bool(text or image_urls)
        result["preview"] = str(frame.run_js("return (document.body?.innerText || '').trim();") or "").strip()
        result["images"] = {"requested": len(image_urls), "inserted": len(image_urls), "fallback": True}
    except Exception as exc:
        result["error"] = type(exc).__name__
    return result


def fill_description_components(
    page: ChromiumPage, product: dict[str, Any], detail_paths: list[Path]
) -> dict[str, Any]:
    """Use the new editor's actual text component and persist it via its iframe."""
    result: dict[str, Any] = {"text_component": False, "saved": False, "preview": ""}
    button = page.ele('css:#guid-description button[data-click="插文本"]', timeout=3)
    if not button:
        return result
    button.click()
    frame = None
    deadline = time.time() + 10
    while time.time() < deadline and not frame:
        try:
            frame = page.get_frame('css:.ant-modal iframe[src*="schema/1829"]', timeout=2)
        except Exception:
            frame = None
        if not frame:
            time.sleep(.5)
    if not frame:
        return result
    # The editor initially attaches an iframe and then replaces its document
    # during startup. Wait and reacquire it before reading controls.
    time.sleep(2.5)
    try:
        frame = page.get_frame('css:.ant-modal iframe[src*="schema/1829"]', timeout=2)
        guide = frame.ele("text:确认", timeout=1)
        if guide:
            guide.click()
            time.sleep(.6)
    except Exception:
        frame = None
    text_node = None
    deadline = time.time() + 8
    while time.time() < deadline and not text_node:
        try:
            frame = page.get_frame('css:.ant-modal iframe[src*="schema/1829"]', timeout=1)
            text_node = frame.ele('css:.item[title="点击插入文字"]', timeout=1)
        except Exception:
            frame = None
            text_node = None
        if not text_node:
            time.sleep(.4)
    if not text_node:
        return result
    text_node.click()
    # Selecting the text component rebuilds the iframe document. Reacquire the
    # frame after that React transition; retaining the old target is the source
    # of intermittent ContextLost/empty-detail results.
    frame = None
    deadline = time.time() + 8
    while time.time() < deadline and not frame:
        try:
            frame = page.get_frame('css:.ant-modal iframe[src*="schema/1829"]', timeout=1)
        except Exception:
            frame = None
        if not frame:
            time.sleep(.5)
    editor = None
    deadline = time.time() + 8
    while time.time() < deadline and not editor:
        try:
            frame = page.get_frame('css:.ant-modal iframe[src*="schema/1829"]', timeout=1)
            editor = frame.ele("css:.ql-editor[contenteditable=true]", timeout=1)
        except Exception:
            frame = None
            editor = None
        if not editor:
            time.sleep(.4)
    if not editor:
        return result
    description = product.get("description") or {}
    detail_text = str(description.get("text") or product.get("detail_text") or "").strip()
    if not detail_text:
        detail_text = str(product.get("title") or "").strip()
    editor.run_js(
        """
        const html = arguments[0];
        this.innerHTML = html;
        this.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: html}));
        this.dispatchEvent(new Event('change', {bubbles: true}));
        this.dispatchEvent(new Event('blur', {bubbles: true}));
        return this.innerHTML;
        """,
        "".join(f"<p>{line.strip()}</p>" for line in detail_text.splitlines() if line.strip()),
    )
    save = frame.ele('css:button.ant-btn-primary', timeout=3)
    if not save:
        return result
    save.click()
    time.sleep(1)
    confirmed = bool(page.run_js(
        """
        const button = Array.from(document.querySelectorAll('.ant-modal button.ant-btn-primary'))
          .find(e => e.offsetParent !== null);
        if (!button) return false;
        button.click();
        return true;
        """
    ))
    if confirmed:
        time.sleep(1)
    result["text_component"] = True
    result["saved"] = True
    result["images"] = insert_detail_images(page, detail_paths)
    result["images"]["preview_count"] = _description_preview_image_count(page)
    result["preview"] = str(page.run_js(
        "return document.querySelector('#guid-description iframe.new-editor-preview-content')?.contentDocument?.body?.innerText || '';"
    ) or "").strip()
    return result


def click_visible_text(page: ChromiumPage, value: str) -> bool:
    return bool(page.run_js(
        """
        const wanted = arguments[0].trim();
        const selectors = [
          '.next-menu-item', '.next-menu-item-inner',
          '.ant-select-item-option', '[role="option"]'
        ];
        const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
        const node = nodes.find(e => e.offsetParent !== null &&
          (e.innerText || e.textContent || '').trim() === wanted);
        if (!node) return false;
        node.click();
        return true;
        """,
        value,
    ))


def click_best_visible_option(page: ChromiumPage, value: str) -> str:
    """Click an option that exactly or semantically matches a property value."""
    return str(page.run_js(
        """
        const wanted = (arguments[0] || '').trim();
        const normalize = value => (value || '').replace(/[\\s\\/\\-_,，、]/g, '').toLowerCase();
        const selectors = ['.next-menu-item', '.next-menu-item-inner', '.ant-select-item-option', '[role="option"]'];
        const options = Array.from(document.querySelectorAll(selectors.join(',')))
          .filter(e => e.offsetParent !== null)
          .map(e => ({node: e, text: (e.innerText || e.textContent || '').trim()}))
          .filter(item => item.text);
        const exact = options.find(item => item.text === wanted);
        const normalizedWanted = normalize(wanted);
        const related = options
          .filter(item => {
            const candidate = normalize(item.text);
            return candidate && normalizedWanted &&
              (candidate.includes(normalizedWanted) || normalizedWanted.includes(candidate));
          })
          .sort((a, b) => Math.abs(a.text.length - wanted.length) - Math.abs(b.text.length - wanted.length));
        const chosen = exact || related[0];
        if (!chosen) return '';
        chosen.node.click();
        return chosen.text;
        """,
        value,
    ) or '').strip()


def click_first_visible_option(page: ChromiumPage, preferred: list[str] | None = None) -> str:
    """Choose a usable visible option for an unresolved required select."""
    return str(page.run_js(
        """
        const preferred = JSON.parse(arguments[0] || '[]')
          .map(value => (value || '').trim()).filter(Boolean);
        const selectors = ['.next-menu-item', '.next-menu-item-inner', '.ant-select-item-option', '[role="option"]'];
        const options = Array.from(document.querySelectorAll(selectors.join(',')))
          .filter(e => e.offsetParent !== null && e.getAttribute('aria-disabled') !== 'true' && !e.classList.contains('next-disabled'))
          .map(e => ({node: e, text: (e.innerText || e.textContent || '').trim()}))
          .filter(item => item.text && !/请选择|请输入|申请添加/.test(item.text));
        const chosen = preferred.map(value => options.find(item => item.text === value || item.text.includes(value))).find(Boolean)
          || options.find(item => /^(其它|其他|否)$/.test(item.text))
          || options[0];
        if (!chosen) return '';
        chosen.node.click();
        return chosen.text;
        """,
        json.dumps(preferred or [], ensure_ascii=False),
    ) or '').strip()


def select_text(page: ChromiumPage, selector: str, value: str) -> bool:
    """Select a visible option from an Ant/Next select by its displayed text."""
    control = page.ele(f"css:{selector}", timeout=3)
    if not control:
        return False
    control.click()
    time.sleep(.5)
    if not click_visible_text(page, value):
        return False
    time.sleep(.5)
    return True


def fill_prop(page: ChromiumPage, prop_id: str, value: str) -> bool:
    box = page.ele(f'css:[cat-prop-id="{prop_id}"]', timeout=3)
    if not box:
        return False
    select = box.ele("tag:select", timeout=1)
    if select:
        return select.select.by_text(value)
    inp = box.ele("tag:input", timeout=1)
    if not inp:
        return False
    prop_type = str(box.attr("cat-prop-type") or "").lower()
    requested_values = [part.strip() for part in re.split(r"[,，、/]", str(value or "")) if part.strip()]
    if prop_type == "checkbox" and len(requested_values) > 1:
        selected = 0
        for requested in requested_values:
            inp.click()
            time.sleep(.25)
            if click_visible_text(page, requested) or click_best_visible_option(page, requested):
                selected += 1
                time.sleep(.25)
        if selected:
            return selected == len(requested_values)
    inp.click()
    time.sleep(.4)
    if click_visible_text(page, value):
        return True
    if click_best_visible_option(page, value):
        return True
    # Customizable fields accept direct text; blur commits the value.
    inp.input(value, clear=True)
    page.ele("css:#guid-title input", timeout=2).click()
    return True


def add_sale_values(page: ChromiumPage, placeholder: str, values: list[str]) -> int:
    """Add custom sale-property values and let the page generate the SKU rows."""
    if not values:
        return 0
    selector = f'#guid-saleProp input[placeholder="{placeholder}"]'
    value_script = """
        return Array.from(document.querySelectorAll('#guid-saleProp input'))
          .filter(e => (e.getAttribute('placeholder') || '').includes('请输入或选择'))
          .map(e => (e.value || '').trim()).filter(Boolean);
    """
    for value in values:
        deadline = time.time() + 8
        while time.time() < deadline:
            current_values = list(page.run_js(value_script) or [])
            if value in current_values:
                break
            inputs = page.eles(f"css:{selector}")
            if not inputs:
                break
            target = inputs[-1]
            target.click()
            target.input(value, clear=True)
            page.ele("css:#guid-title input", timeout=2).click()
            time.sleep(.6)
            if value in list(page.run_js(value_script) or []):
                break
            time.sleep(.4)
    # React regenerates the SKU table asynchronously. Wait for both the
    # committed sale values and the corresponding rows before continuing.
    deadline = time.time() + 10
    while time.time() < deadline:
        committed = list(page.run_js(value_script) or [])
        table_state = discover_sku_table(page)
        rows = int((table_state.get("selected") or {}).get("row_count") or 0)
        if len(committed) >= len(values) and rows >= len(values):
            break
        time.sleep(.5)
    return len(list(page.run_js(value_script) or []))


def discover_sale_property_slots(page: ChromiumPage) -> list[dict[str, Any]]:
    """Discover visible sale-property inputs without relying on a category ID."""
    return list(page.run_js(
        """
        return Array.from(document.querySelectorAll('#guid-saleProp input'))
          .filter(input => input.offsetParent !== null &&
            (input.getAttribute('placeholder') || '').includes('请输入或选择'))
          .map((input, index) => {
            const owner = input.closest('.next-form-item, .ant-form-item, li, tr, .next-row');
            return {
              index,
              placeholder: input.getAttribute('placeholder') || '',
              label: (owner?.innerText || '').split('请输入或选择')[0].replace('*', '').trim()
            };
          });
        """
    ) or [])


def add_sale_dimensions(page: ChromiumPage, model: dict[str, Any]) -> dict[str, Any]:
    """Add source dimensions conservatively and report what the page accepted.

    A single custom sale-property input is common on the publish page. Multiple
    dimensions are only attempted when the page exposes the same number of
    independent inputs; otherwise the caller blocks saving instead of merging
    values into the wrong dimension.
    """
    dimensions = list(model.get("dimensions") or [])
    if not dimensions:
        return {"status": "no_sku", "dimensions": [], "accepted_values": 0}
    slots = discover_sale_property_slots(page)
    if len(slots) < len(dimensions):
        return {
            "status": "unsupported",
            "reason": f"页面仅发现 {len(slots)} 个销售属性输入，源商品需要 {len(dimensions)} 个",
            "dimensions": dimensions,
            "slots": slots,
            "accepted_values": 0,
        }
    results = []
    for index, dimension in enumerate(dimensions):
        values = [str(value) for value in dimension.get("values") or [] if str(value).strip()]
        # Reuse the proven input/blur sequence for the first slot. For a second
        # slot, temporarily scope the same helper to that input's placeholder;
        # if placeholders are identical, use the positional element directly.
        placeholder = str(slots[index].get("placeholder") or "")
        if index == 0 or len({str(item.get("placeholder") or "") for item in slots}) > 1:
            accepted = add_sale_values(page, placeholder, values)
        else:
            accepted = 0
            for value in values:
                inputs = page.eles('css:#guid-saleProp input[placeholder*="请输入或选择"]')
                if len(inputs) <= index:
                    break
                target = inputs[index]
                target.click()
                target.input(value, clear=True)
                page.ele("css:#guid-title input", timeout=2).click()
                time.sleep(.6)
                accepted += 1
        results.append({"name": dimension.get("name"), "requested": values, "accepted": accepted})
    return {
        "status": "filled",
        "dimensions": results,
        "slots": slots,
        "accepted_values": sum(int(item["accepted"]) for item in results),
    }


def sale_property_placeholder(page: ChromiumPage) -> str:
    return str(page.run_js(
        """
        return document.querySelector('#guid-saleProp input[placeholder*="请输入或选择"]')?.getAttribute('placeholder') || '';
        """
    ) or "").strip()


def source_property_map(page: ChromiumPage, source_attrs: dict[str, Any]) -> dict[str, str]:
    """Match collected attributes to the current category's visible property IDs."""
    normalized = {_compact_text(key): str(value) for key, value in source_attrs.items() if value not in (None, "")}
    visible = list(page.run_js(
        """
        return Array.from(document.querySelectorAll('[cat-prop-id]')).map(box => ({
          id: box.getAttribute('cat-prop-id') || '',
          label: (box.querySelector('.cat-prop-label')?.innerText || '').replace('*', '').trim()
        }));
        """
    ) or [])
    return {
        str(item.get('id')): normalized[_compact_text(item.get('label'))]
        for item in visible
        if item.get('id') and _compact_text(item.get('label')) in normalized
    }


def discover_sku_table(page: ChromiumPage) -> dict[str, Any]:
    """Find the SKU matrix inside its module.

    The seller page renders ``guid-skuTable`` as two synchronized tables: a
    header-only table and a body table. Looking at every table on the page can
    select the interval-price table instead, so discovery is scoped to the SKU
    module and explicitly joins the header and body tables.
    """
    return dict(page.run_js(
        """
        const module = document.querySelector('#guid-skuTable');
        if (!module) return {selected: {index: -1, headers: [], row_count: 0, input_count: 0, score: 0}, candidates: []};
        const tables = Array.from(module.querySelectorAll('table'));
        const headerTable = tables.find(table => {
          const headers = Array.from(table.querySelectorAll('thead th, thead td')).map(e => (e.innerText || '').trim());
          return headers.some(h => /可售数量|单品货号|是否上架/.test(h));
        });
        const headers = headerTable
          ? Array.from(headerTable.querySelectorAll('thead th, thead td')).map(e => (e.innerText || '').trim())
          : [];
        const candidates = tables.map((table, index) => {
          const rows = Array.from(table.querySelectorAll('tbody tr')).filter(e => e.offsetParent !== null);
          const inputCount = table.querySelectorAll('tbody input').length;
          const isHeader = table === headerTable;
          const score = rows.length * 10 + inputCount + (isHeader ? 1 : 0);
          return {index, headers: isHeader ? headers : [], row_count: rows.length, input_count: inputCount, score};
        }).filter(item => item.row_count || item.index === tables.indexOf(headerTable));
        const bodyIndex = candidates
          .filter(item => item.index !== tables.indexOf(headerTable) && item.row_count > 0)
          .sort((a, b) => b.row_count - a.row_count || b.input_count - a.input_count)[0];
        const selected = bodyIndex || {
          index: tables.indexOf(headerTable), headers, row_count: 0, input_count: 0, score: 0
        };
        document.querySelectorAll('table[data-codex-sku-table]').forEach(e => e.removeAttribute('data-codex-sku-table'));
        if (bodyIndex) {
          const table = tables[bodyIndex.index];
          table.setAttribute('data-codex-sku-table', '1');
          table.querySelectorAll('tbody tr').forEach(row => {
            const cells = Array.from(row.querySelectorAll('td'));
            row.querySelectorAll('input').forEach(input => {
              const column = cells.indexOf(input.closest('td'));
              input.setAttribute('data-codex-field', headers[column] || '');
            });
          });
        }
        return {selected: {...selected, headers}, candidates};
        """
    ) or {})


def _set_input_value(input_element: Any, value: Any) -> None:
    input_element.input(str(value), clear=True)
    try:
        input_element.run_js("this.dispatchEvent(new Event('change', {bubbles:true}));")
    except Exception:
        pass


def read_sku_table_rows(page: ChromiumPage) -> list[dict[str, Any]]:
    """Read current values from the dynamically selected SKU table."""
    return list(page.run_js(
        """
        const table = document.querySelector('table[data-codex-sku-table="1"]');
        if (!table) return [];
        const headerTable = Array.from(document.querySelectorAll('#guid-skuTable table'))
          .find(table => table.querySelector('thead th, thead td'));
        const headers = headerTable
          ? Array.from(headerTable.querySelectorAll('thead th, thead td')).map(e => (e.innerText || '').trim())
          : [];
        return Array.from(table.querySelectorAll('tbody tr')).filter(row => row.offsetParent !== null).map(row => {
          const cells = Array.from(row.querySelectorAll('td'));
          const inputs = Array.from(row.querySelectorAll('input')).map(input => ({
            value: input.value || '',
            name: input.name || '',
            placeholder: input.placeholder || '',
            type: input.type || 'text',
            column: cells.indexOf(input.closest('td')),
            header: input.getAttribute('data-codex-field') || headers[cells.indexOf(input.closest('td'))] || ''
          }));
          const values = {};
          cells.forEach(cell => {
            const label = (cell.querySelector('[class*="sku"], [class*="spec"]')?.innerText || '').trim();
            if (label) values[label] = label;
          });
           const codeInput = inputs.find(item => /单品货号|货号|商家编码|编码|sku/i.test([item.name, item.placeholder, item.header].join(' ')));
           return {text: (row.innerText || '').trim(), inputs, sku_id: codeInput?.value || '', properties: values, headers};
        });
        """
    ) or [])


def fill_sku_rows(page: ChromiumPage, skus: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill price, stock and merchant code using semantic input hints."""
    table = discover_sku_table(page)
    selected = table.get("selected") or {}
    rows = page.eles('css:table[data-codex-sku-table="1"] tbody tr') if int(selected.get("row_count") or 0) else []
    count = min(len(rows), len(skus))
    for row, sku in zip(rows, skus):
        inputs = row.eles("tag:input")
        if not inputs:
            continue
        def input_hint(item: Any) -> str:
            return " ".join(
                str(item.attr(key) or "")
                for key in ("name", "placeholder", "data-codex-field")
            )

        price_input = next((item for item in inputs if re.search(r"price|价格|售价", input_hint(item), re.I)), None)
        stock_input = next((item for item in inputs if re.search(r"可售数量|库存|stock", input_hint(item), re.I)), None)
        if stock_input is None:
            stock_input = next((item for item in inputs if re.search(r"数量", input_hint(item), re.I)), None)
        code_input = next((item for item in inputs if re.search(r"单品货号|货号|商家编码|编码|sku", input_hint(item), re.I)), None)
        # Only unnamed legacy matrices get positional price/stock fallback.
        # The current seller matrix has stock + cargo-number inputs, so its
        # first input must never be mistaken for a price field.
        if stock_input is None and code_input is None and len(inputs) >= 2:
            price_input = price_input or inputs[0]
            stock_input = inputs[1]
        if stock_input is None and code_input is not None:
            stock_input = next((item for item in inputs if item is not code_input), None)
        if price_input is not None:
            _set_input_value(price_input, sku.get("price", 0))
        if stock_input is not None:
            _set_input_value(stock_input, sku.get("stock", 0))
        if code_input is not None:
            _set_input_value(code_input, sku.get("sku_id", ""))
    time.sleep(1)
    rendered = read_sku_table_rows(page)
    return {"count": count, "table": table, "rendered": rendered}


def fill_number_inputs(page: ChromiumPage, module_id: str, values: list[str]) -> int:
    module = page.ele(f"css:#{module_id}", timeout=2)
    if not module:
        return 0
    visible = bool(page.run_js(
        f"""
        const node = document.querySelector('#{module_id}');
        if (!node) return false;
        const style = window.getComputedStyle(node);
        return style.display !== 'none' && style.visibility !== 'hidden';
        """
    ))
    if not visible:
        return 0
    inputs = module.eles("tag:input")
    for inp, value in zip(inputs, values):
        _set_input_value(inp, value)
    return min(len(inputs), len(values))


def fill_price_range(page: ChromiumPage, quantity: Any, price: Any) -> int:
    """Fill interval pricing by column semantics, never by global input order."""
    module = page.ele("css:#guid-priceRange", timeout=2)
    if not module:
        return 0
    table = module.ele("tag:table", timeout=2)
    if not table:
        return 0
    headers = [str(cell.text or "").strip() for cell in table.eles("css:thead th, thead td")]
    rows = table.eles("css:tbody tr")
    if not rows:
        return 0
    cells = rows[0].eles("tag:td")
    values = {"购买数量": quantity, "单价": price}
    filled = 0
    for label, value in values.items():
        try:
            column = next(index for index, header in enumerate(headers) if label in header)
        except StopIteration:
            continue
        if column >= len(cells):
            continue
        inp = cells[column].ele("tag:input", timeout=1)
        if inp:
            _set_input_value(inp, value)
            filled += 1
    return filled


def read_price_range(page: ChromiumPage) -> dict[str, str]:
    """Read interval pricing by its semantic columns and preview text."""
    return dict(page.run_js(
        """
        const module = document.querySelector('#guid-priceRange');
        const table = module?.querySelector('tbody tr');
        if (!table) return {quantity: '', price: '', preview: ''};
        const cells = Array.from(table.querySelectorAll('td'));
        const inputValue = index => cells[index]?.querySelector('input')?.value || '';
        return {quantity: inputValue(1), price: inputValue(2), preview: cells[3]?.innerText?.trim() || ''};
        """
    ) or {})


def read_price_range_preview(page: ChromiumPage) -> str:
    return str(read_price_range(page).get("preview") or "").strip()


def displayed_price(value: Any) -> str:
    """Extract price only from target-page text, never from source data."""
    text = str(value or "")
    match = re.search(r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if match:
        return match.group(1)
    return text.strip() if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text.strip()) else ""


def same_number(left: Any, right: Any) -> bool:
    try:
        first, second = Decimal(str(left).strip()), Decimal(str(right).strip())
        return first.is_finite() and second.is_finite() and first == second
    except (InvalidOperation, ValueError):
        return False


def inspect_state(page: ChromiumPage) -> dict[str, Any]:
    body = page.ele("tag:body")
    body_text = (body.text or "") if body else ""
    return {
        "url": str(page.url),
        "title": str(page.title),
        "logged_in": not is_seller_login_url(page.url),
        "save_draft_present": bool(page.ele("css:#saveDraftButton", timeout=2)),
        "publish_present": bool(page.ele("css:#submitFormButton", timeout=2)),
        "product_title_value": str(page.run_js(
            "return document.querySelector('#guid-title input')?.value || '';"
        ) or "").strip(),
        "category_id_value": str(page.run_js(
            "return document.querySelector('input[name=catId], input[name=categoryId]')?.value || '';"
        ) or "").strip(),
        "main_image_count": int(page.run_js(
            "return document.querySelectorAll('#guid-primaryPicture .module-picture-cover-wrapper:not(.cover-empty)').length;"
        ) or 0),
        "price_range_preview": read_price_range_preview(page),
        "errors": [
            line.strip() for line in body_text.splitlines()
            if any(marker in line for marker in ("错误", "不能为空", "请填写", "请选择", "请上传"))
        ][:20],
        "delivery_time_value": str(page.run_js(
            """
            const row = Array.from(document.querySelectorAll('#guid-buyerProtection tbody tr'))
              .find(r => r.querySelector('.ant-select'));
            return row?.querySelector('.ant-select-selection-item')?.innerText
              || row?.querySelector('.ant-select-selection-placeholder')?.innerText
              || document.querySelector('#guid-deliveryTime .next-select-values')?.innerText || '';
            """
        ) or "").strip(),
        "shipping_address_value": str(page.run_js(
            "return document.querySelector('#guid-cbuSendAddress .ant-select-selection-item')?.innerText || "
            "document.querySelector('#guid-cbuSendAddress .ant-select-selection-placeholder')?.innerText || '';"
        ) or "").strip(),
        "freight_template_value": str(page.run_js(
            "return document.querySelector('#guid-freight .ant-select-selection-item')?.innerText || '';"
        ) or "").strip(),
        "package_weight_values": list(page.run_js(
            """
            return Array.from(document.querySelectorAll('#guid-officialLogistics tbody tr'))
              .map(row => Array.from(row.querySelectorAll('input')).map(input => input.value || ''))
              .filter(values => values.length);
            """
        ) or []),
        "description_textarea_length": int(page.run_js(
            "return (document.querySelector('#tinyMCE-0')?.value || '').length;"
        ) or 0),
        "blocked_publish_attempts": page.run_js(
            "return window.__commercialDraftGuardEvents || [];"
        ),
    }


def inspect_description_state(page: ChromiumPage) -> dict[str, Any]:
    """Inspect persisted description content across all editor preview frames."""
    frames = list(page.run_js(
        """
        return Array.from(document.querySelectorAll('#guid-description iframe')).map(frame => {
          try {
            const doc = frame.contentDocument;
            return {
              class_name: frame.className || '',
              src: frame.getAttribute('src') || '',
              text: (doc?.body?.innerText || '').trim(),
              images: doc?.querySelectorAll('img').length || 0
            };
          } catch (error) {
            return {class_name: frame.className || '', src: frame.src || '', text: '', images: 0};
          }
        });
        """
    ) or [])
    return {
        "frames": frames,
        "max_text_length": max((len(str(item.get("text") or "")) for item in frames), default=0),
        "max_iframe_images": max((int(item.get("images") or 0) for item in frames), default=0),
        "total_iframe_images": sum(int(item.get("images") or 0) for item in frames),
    }


def draft_records(page: ChromiumPage) -> list[dict[str, str]]:
    """Read draft rows from the current draft list without relying on row order."""
    return list(page.run_js(
        """
        return Array.from(document.querySelectorAll('tr[data-row-key]')).map(row => {
          const cells = Array.from(row.querySelectorAll('td')).map(cell => (cell.innerText || '').trim());
          const link = row.querySelector('a[href*="offerDraftId="]');
          return {
            id: row.getAttribute('data-row-key') || '',
            title: (row.querySelector('.product-title')?.innerText || '').trim(),
            saved_at: cells.find(value => /20\\d{2}[-/]\\d{1,2}[-/]\\d{1,2}/.test(value)) || '',
            url: link?.href || ''
          };
        }).filter(item => item.id);
        """
    ) or [])


def read_draft_records_background(page: ChromiumPage) -> list[dict[str, str]]:
    """Read the draft list in a background tab so the form tab is not torn down."""
    tab = None
    try:
        tab = page.new_tab(DRAFT_INDEX_URL, background=True)
        time.sleep(8)
        return draft_records(tab)
    except Exception:
        return []
    finally:
        if tab:
            try:
                page.close_tabs(tab)
            except Exception:
                pass


def save_artifacts(page: ChromiumPage, output_dir: Path, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        atomic_write(output_dir / "page.html", page.html)
    except Exception as exc:
        report.setdefault("artifact_warnings", []).append(f"page_html_unavailable:{type(exc).__name__}")
    try:
        page.get_screenshot(path=str(output_dir), name="page.png", full_page=True)
    except Exception as exc:
        report.setdefault("artifact_warnings", []).append(f"page_screenshot_unavailable:{type(exc).__name__}")
    atomic_write(output_dir / "report.json", json.dumps(report, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product",
        type=Path,
        required=True,
        help="要发布的商品采集文件 product.json；必须明确指定，避免误用旧商品",
    )
    parser.add_argument("--profile-dir", type=Path, default=Path("data/seller-browser-profile"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/draft-transfer-validation"))
    parser.add_argument("--category-id", required=True)
    parser.add_argument("--store-identity-text", required=True)
    parser.add_argument("--shipping-address", default="")
    parser.add_argument("--freight-template-text", default="")
    parser.add_argument("--delivery-promise", default="")
    parser.add_argument("--package-weight-grams", type=int)
    parser.add_argument("--category-rules", type=Path, required=True)
    parser.add_argument("--preview-only", action="store_true")
    parser.add_argument("--save-draft", action="store_true")
    parser.add_argument("--existing-draft-id", default="")
    parser.add_argument(
        "--login-timeout-seconds",
        type=int,
        default=600,
        help="等待卖家登录的秒数；0 表示不限时，直到登录完成或手动关闭浏览器",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="验证结束后保留浏览器页面，不关闭自动化连接",
    )
    args = parser.parse_args(argv)
    if args.preview_only and args.save_draft:
        parser.error("--preview-only and --save-draft are mutually exclusive")
    if args.login_timeout_seconds < 0:
        parser.error("--login-timeout-seconds 不能小于 0")

    args.product = args.product.resolve()
    product = load_product(args.product)
    if not bool((product.get("validation") or {}).get("passed")):
        raise SystemExit("product.json 未通过采集质量校验")
    category_rules = json.loads(args.category_rules.read_text(encoding="utf-8"))
    source_offer_id = str((product.get("source") or {}).get("offer_id") or "").strip()
    if not source_offer_id:
        raise SystemExit("product.json 缺少 source.offer_id，无法确认商品素材归属")
    main_asset_paths, main_asset_errors = resolve_product_asset_paths(args.product, product)
    detail_asset_paths, detail_asset_errors = resolve_detail_asset_paths(args.product, product)
    if main_asset_errors:
        raise SystemExit("商品主图素材校验失败：" + "；".join(main_asset_errors))
    category_id = str(args.category_id).strip()
    if not category_id:
        raise SystemExit("目标类目未确认")
    options = ChromiumOptions()
    options.set_user_data_path(str(args.profile_dir.resolve()))
    options.headless(False)
    page = ChromiumPage(options)
    report: dict[str, Any] = {
        "source_offer_id": product.get("source", {}).get("offer_id"),
        "category_id": category_id,
        "mode": "save_draft" if args.save_draft else "preview_only",
        "publish_clicked": None,
        "publish_guard_events": [],
        "existing_draft_id": str(args.existing_draft_id or "").strip() or None,
        "draft_save_clicked": False,
        "keep_open": bool(args.keep_open),
        "fields": {},
        "asset_manifest": {
            "product_file": str(args.product),
            "source_offer_id": source_offer_id,
            "main_images": [str(path) for path in main_asset_paths],
            "detail_images": [str(path) for path in detail_asset_paths],
            "detail_asset_warnings": detail_asset_errors,
        },
    }
    try:
        report["draft_snapshot_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        # Snapshot the list before opening the form so a same-title old draft
        # cannot be mistaken for the result of this run.
        try:
            login_status = open_seller_page(
                page, DRAFT_INDEX_URL, args.login_timeout_seconds, settle_seconds=8
            )
            if login_status != "ready":
                report["result"] = (
                    "seller_login_timeout"
                    if login_status == "login_timeout"
                    else "seller_browser_closed_during_login"
                )
                report["login_wait"] = {
                    "status": login_status,
                    "timeout_seconds": args.login_timeout_seconds or None,
                }
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 2
            report["draft_records_before"] = draft_records(page)
            report["draft_snapshot_ok"] = True
        except Exception:
            report["draft_records_before"] = []
            report["draft_snapshot_ok"] = False
        existing_record = next((item for item in report["draft_records_before"] if str(item.get("id")) == str(args.existing_draft_id)), None)
        same_title = [item for item in report["draft_records_before"] if item.get("title") == str(product.get("title") or "")]
        if args.save_draft and not report["draft_snapshot_ok"]:
            report["result"] = "blocked_draft_snapshot_unavailable"
            save_artifacts(page, args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        if args.save_draft and args.existing_draft_id and not existing_record:
            report["result"] = "blocked_ledger_draft_not_found"
            report.setdefault("warnings", []).append("台账草稿 ID 在当前店铺不可见，已阻止新建")
            save_artifacts(page, args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        if args.save_draft and not args.existing_draft_id and same_title:
            report["result"] = "blocked_existing_same_title_draft"
            report.setdefault("warnings", []).append("发现同标题历史草稿但没有本地幂等台账，已阻止重复创建")
            save_artifacts(page, args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4
        url = existing_record.get("url") if existing_record and existing_record.get("url") else (
            f"{PUBLISH_URL}?catId={category_id}"
            "&saleChannel=default&channelType=pcDefault&operator=new"
        )
        login_status = open_seller_page(
            page, url, args.login_timeout_seconds, settle_seconds=12
        )
        if login_status != "ready":
            report["result"] = (
                "seller_login_timeout"
                if login_status == "login_timeout"
                else "seller_browser_closed_during_login"
            )
            report["login_wait"] = {
                "status": login_status,
                "timeout_seconds": args.login_timeout_seconds or None,
            }
            save_artifacts(page, args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2

        body = page.ele("tag:body")
        body_text = (body.text or "") if body else ""
        report["store_identity"] = {
            "expected": args.store_identity_text,
            "matched": args.store_identity_text in body_text,
        }
        if not report["store_identity"]["matched"]:
            report["result"] = "blocked_store_identity_mismatch"
            save_artifacts(page, args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 4

        install_publish_guards(page)
        report["fields"]["title"] = input_value(
            page, "#guid-title input", str(product.get("title") or "")
        )

        # Upload up to four source main images. The source files are local and
        # are sent through the seller page's own uploader.
        image_paths, accepted_image_meta, rejected_images = select_main_images(
            main_asset_paths, args.output_dir / "normalized-images", namespace=source_offer_id
        )
        main_upload = upload_main_images_two_phase(page, image_paths)
        report["fields"]["main_images_upload"] = main_upload
        report["fields"]["main_images"] = main_upload["selected_count"]
        report["fields"]["main_images_expected"] = len(image_paths)
        report["fields"]["main_images_accepted"] = accepted_image_meta
        report["fields"]["main_images_rejected"] = rejected_images

        source_attrs = product.get("attributes") or {}
        prop_map = source_property_map(page, source_attrs)
        # A collected listing does not always expose every mandatory property
        # required by the destination category. Use conservative category
        # defaults for those fields so the draft is structurally complete.
        required_defaults = dict(category_rules.get("labels") or {})
        defaulted_attributes: list[dict[str, str]] = []
        category_props = list(page.run_js(
            """
            return Array.from(document.querySelectorAll('[cat-prop-id]')).map(box => ({
              id: box.getAttribute('cat-prop-id') || '',
              label: (box.querySelector('.cat-prop-label')?.innerText || '').replace('*', '').trim(),
              required: Boolean(box.querySelector('.cat-prop-label em'))
            }));
            """
        ) or [])
        required_prop_ids = {
            str(item.get("id") or "").strip()
            for item in category_props
            if item.get("required") and str(item.get("id") or "").strip()
        }
        required_prop_ids.update(str(item) for item in category_rules.get("manual_required") or [])
        for item in category_props:
            label = str(item.get("label") or "").strip()
            prop_id = str(item.get("id") or "").strip()
            if prop_id and prop_id not in prop_map and label in required_defaults:
                value = required_defaults[label]
                prop_map[prop_id] = value
                defaulted_attributes.append({
                    "property_id": prop_id,
                    "label": label,
                    "value": value,
                    "reason": "源商品未采集到该必填属性，使用目标类目有效默认选项",
                })
        prop_map.update({str(key): str(value) for key, value in (category_rules.get("properties") or {}).items()})
        report["fields"]["attributes"] = {}
        report["fields"]["attribute_defaults"] = defaulted_attributes
        for pid, value in prop_map.items():
            try:
                filled = fill_prop(page, pid, value)
                displayed = selected_prop_value(page, pid)
                confirmed = bool(displayed) and displayed not in {"请选择", "如无合适选项可直接输入填写（可多选）"}
                report["fields"]["attributes"][pid] = {
                    "attempted": filled,
                    "displayed": displayed,
                    "requested": value,
                    "source": "default" if any(item["property_id"] == pid for item in defaulted_attributes) else "collected",
                    "status": "confirmed" if confirmed else "manual_confirmation_required",
                }
                if not confirmed:
                    report.setdefault("warnings", []).append(
                        f"attribute {pid} was not confirmed by page display"
                    )
            except Exception as exc:
                report["fields"]["attributes"][pid] = False
                report.setdefault("warnings", []).append(
                    f"attribute {pid} failed: {type(exc).__name__}"
                )
        # Missing required values are never guessed. Record them for review and
        # let the save gate stop the run until configuration is explicit.
        for item in category_props:
            prop_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            if not item.get("required") or not prop_id or prop_id in report["fields"]["attributes"]:
                continue
            report["fields"]["attributes"][prop_id] = {
                "attempted": False,
                "displayed": selected_prop_value(page, prop_id),
                "requested": None,
                "source": "missing_required_value",
                "status": "manual_confirmation_required",
            }
            report.setdefault("warnings", []).append(
                f"required attribute {label or prop_id} has no configured value"
            )
        report["fields"]["attribute_defaults"] = defaulted_attributes
        for prop_id in category_rules.get("manual_required") or []:
            report["fields"]["attributes"][str(prop_id)] = {
                "attempted": False,
                "displayed": selected_prop_value(page, str(prop_id)),
                "requested": None,
                "status": "manual_confirmation_required",
            }

        sku_model = normalize_sku_model(product.get("skus") or [])
        report["fields"]["sku_model"] = sku_model
        report["fields"]["sku_dimensions"] = add_sale_dimensions(page, sku_model)
        time.sleep(2)
        normalized_sku_rows = list(sku_model.get("rows") or [])
        sku_result = fill_sku_rows(page, normalized_sku_rows) if sku_model.get("source_count") else {
            "count": 0,
            "table": {"selected": {"row_count": 0}},
            "rendered": [],
        }
        report["fields"]["sku_rows"] = sku_result["count"]
        report["fields"]["sku_table"] = sku_result.get("table")
        report["fields"]["sku_rendered_rows"] = sku_result.get("rendered")
        report["fields"]["sku_value_mapping"] = {
            "可售数量": "source skus[].stock",
            "单品货号": "source skus[].sku_id",
            "说明": "源商品未提供独立商家货号时，使用1688 SKU ID作为草稿货号",
        }
        # Build a comparable view from the rendered rows. The page can expose
        # the values as plain cell text, so use each row text as a fallback for
        # its sole source dimension and rely on the strict row/value checks.
        rendered_for_validation = []
        dimensions = list(sku_model.get("dimensions") or [])
        for index, rendered in enumerate(sku_result.get("rendered") or []):
            source = normalized_sku_rows[index] if index < len(normalized_sku_rows) else {}
            row_text = str(rendered.get("text") or "")
            source_props = dict(source.get("properties") or {})
            # Treat the rendered row as evidence. A source value is accepted
            # only when it is visibly present in that row; otherwise the target
            # property is marked missing and the save gate will stop the run.
            props = {
                str(dimension.get("name")): (
                    str(source_props.get(str(dimension.get("name"))) or "")
                    if str(source_props.get(str(dimension.get("name"))) or "") in row_text
                    else ""
                )
                for dimension in dimensions
            }
            inputs = rendered.get("inputs") or []
            values = {
                " ".join(str(item.get(key) or "") for key in ("name", "placeholder", "header")): str(item.get("value") or "")
                for item in inputs
            }
            price_value = next((value for key, value in values.items() if re.search(r"price|价格|售价", key, re.I)), "")
            stock_value = next((value for key, value in values.items() if re.search(r"stock|库存|数量", key, re.I)), "")
            rendered_for_validation.append({"properties": props, "price": price_value, "stock": stock_value, "sku_id": rendered.get("sku_id") or ""})
        report["fields"]["sku_validation"] = validate_target_rows(sku_model, rendered_for_validation)
        if sku_model.get("source_count") and (
            report["fields"]["sku_dimensions"].get("status") != "filled"
            or not report["fields"]["sku_validation"].get("valid")
        ):
            report.setdefault("warnings", []).extend(sku_model.get("warnings") or [])
            report.setdefault("warnings", []).extend(report["fields"]["sku_validation"].get("issues") or [])
            report.setdefault("warnings", []).append(
                str(report["fields"]["sku_dimensions"].get("reason") or "销售属性或 SKU 表未完整生成")
            )
        report["fields"]["price_range"] = fill_price_range(
            page, "1", str(product.get("price", {}).get("primary", 0))
        )
        report["fields"]["total_sales"] = fill_number_inputs(
            page, "guid-totalSales", [str(product.get("stock", {}).get("total_observed", 0))]
        )
        time.sleep(.5)
        report["fields"]["price_range_values"] = read_price_range(page)
        report["fields"]["price_range_preview"] = read_price_range_preview(page)
        page_price = str(report["fields"]["price_range_values"].get("price") or "").strip()
        if not page_price:
            page_price = displayed_price(report["fields"]["price_range_preview"])
        if page_price and rendered_for_validation:
            for row in rendered_for_validation:
                if not row.get("price"):
                    row["price"] = page_price
            report["fields"]["sku_validation"] = validate_target_rows(sku_model, rendered_for_validation)
        expected_price = str(product.get("price", {}).get("primary", 0))
        if not same_number(page_price, expected_price):
            report.setdefault("warnings", []).append(
                f"区间报价回显异常，期望单价 {expected_price}，实际 {page_price or report['fields']['price_range_preview']}"
            )

        # The source explicitly promises 48-hour dispatch. Select that exact
        # value from the seller form; do not fall back to the first option.
        selected = (
            fill_buyer_protection_delivery(page, args.delivery_promise)
            if args.delivery_promise else None
        )
        report["fields"]["delivery_time"] = selected or None
        if args.delivery_promise and not selected:
            report.setdefault("warnings", []).append(
                f"delivery time {args.delivery_promise} is unavailable in the seller account"
            )
        elif args.delivery_promise and _compact_text(args.delivery_promise) not in _compact_text(selected):
            report.setdefault("warnings", []).append(
                f"{args.delivery_promise} unavailable; selected platform option {selected}"
            )
        report["fields"]["shipping_address"] = (
            fill_shipping_address(page, args.shipping_address)
            if args.shipping_address else {"status": "skipped", "reason": "not_configured"}
        )
        report["fields"]["freight_template"] = (
            fill_freight_template(page, args.freight_template_text)
            if args.freight_template_text else {"status": "skipped", "reason": "not_configured"}
        )
        report["fields"]["package_dimensions"] = (
            fill_default_package_weight(page, args.package_weight_grams)
            if args.package_weight_grams is not None else {"status": "skipped", "reason": "not_configured"}
        )
        if (args.package_weight_grams is not None
                and report["fields"]["package_dimensions"]["status"] != "filled"):
            report.setdefault("warnings", []).append("件重尺默认重量未能写入规格行")

        source_detail_paths = detail_asset_paths
        detail_paths, prepared_detail_meta, rejected_detail_images = prepare_detail_images(
            source_detail_paths,
            args.output_dir / "normalized-detail-images",
            namespace=source_offer_id,
        )
        report["fields"]["description_source_images"] = len(source_detail_paths)
        report["fields"]["description_prepared_images"] = prepared_detail_meta
        report["fields"]["description_rejected_images"] = rejected_detail_images
        try:
            report["fields"]["description"] = fill_description_components(
                page, product, detail_paths
            )
            if not report["fields"]["description"].get("saved"):
                # The editor iframe can be replaced by the page after an
                # upload/attribute update. Close any half-open dialog and give
                # the editor one clean second attempt before declaring the
                # detail field empty.
                try:
                    page.run_js("document.querySelector('.ant-modal .window-action-close')?.click();")
                    time.sleep(1)
                except Exception:
                    pass
                report["fields"]["description_retry"] = fill_description_components(
                    page, product, detail_paths
                )
                if report["fields"]["description_retry"].get("saved"):
                    report["fields"]["description"] = report["fields"]["description_retry"]
                else:
                    # Last-resort same-page editor path. This avoids treating
                    # an iframe replacement as a valid empty description.
                    report["fields"]["description_fallback"] = fill_legacy_description_editor(
                        page, product
                    )
                    if report["fields"]["description_fallback"].get("saved"):
                        report["fields"]["description"] = report["fields"]["description_fallback"]
        except Exception as exc:
            report["fields"]["description"] = {
                "text_component": False,
                "saved": False,
                "preview": "",
                "error": type(exc).__name__,
            }
            report.setdefault("warnings", []).append(
                f"description editor interrupted: {type(exc).__name__}"
            )
        time.sleep(3)
        report["fields"]["description"]["state_before_save"] = inspect_description_state(page)
        report["state_before_save"] = inspect_state(page)

        if args.save_draft:
            unconfirmed_attributes = [
                prop_id for prop_id, value in (report["fields"].get("attributes") or {}).items()
                if prop_id in required_prop_ids
                and (not isinstance(value, dict) or value.get("status") != "confirmed")
            ]
            if unconfirmed_attributes:
                report["result"] = "blocked_unconfirmed_required_attributes"
                report.setdefault("warnings", []).append(
                    "必填属性未确认: " + ",".join(unconfirmed_attributes)
                )
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            runtime_configuration_ok = all((
                not args.shipping_address
                or report["fields"].get("shipping_address", {}).get("status") == "selected",
                not args.freight_template_text
                or report["fields"].get("freight_template", {}).get("status") == "selected",
                not args.delivery_promise
                or _compact_text(args.delivery_promise) in _compact_text(report["fields"].get("delivery_time")),
                args.package_weight_grams is None
                or report["fields"].get("package_dimensions", {}).get("status") == "filled",
            ))
            if not runtime_configuration_ok:
                report["result"] = "blocked_runtime_store_configuration"
                report.setdefault("warnings", []).append("店铺物流配置未完整回显，已阻止保存草稿")
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            state_errors = [
                item for item in (report.get("state_before_save") or {}).get("errors") or []
                if re.search(r"(?:^|\s)\d+\s*错误|错误\s*\(\d+\)|不能为空|请(?:选择|填写|上传)", item)
            ]
            if state_errors:
                report["result"] = "blocked_page_validation_errors"
                report.setdefault("warnings", []).append("发布页仍显示校验错误，已阻止保存草稿")
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            expected_main_images = int(report["fields"].get("main_images_expected") or 0)
            actual_main_images = int(report["fields"].get("main_images") or 0)
            if expected_main_images and actual_main_images < expected_main_images:
                report["result"] = "blocked_incomplete_main_images"
                report.setdefault("warnings", []).append(
                    f"主图未完整插入（{actual_main_images}/{expected_main_images}），已阻止保存草稿"
                )
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            sku_validation = report["fields"].get("sku_validation") or {}
            if sku_model.get("source_count") and (
                not sku_model.get("valid", True)
                or
                report["fields"].get("sku_dimensions", {}).get("status") != "filled"
                or not sku_validation.get("valid")
            ):
                report["result"] = "blocked_invalid_sku_mapping"
                report.setdefault("warnings", []).append("SKU 映射未通过保存前校验，已阻止保存草稿")
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            # Saving an empty required detail field only updates/creates a
            # broken draft and makes later verification misleading.
            description_state = report["fields"]["description"]["state_before_save"]
            description_placeholder = "请点击右侧“上传图片”或“高级编辑”开始"
            description_text_present = description_state["max_text_length"] > 0 and not any(
                description_placeholder in str(item.get("text") or "")
                for item in description_state.get("frames", [])
            )
            if not description_text_present or description_state["max_iframe_images"] <= 0:
                report["result"] = "blocked_empty_description"
                report.setdefault("warnings", []).append("商品详情未写入，已阻止保存草稿")
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            report["publish_guard_events"] = read_publish_guard_events(page)
            if report["publish_guard_events"]:
                report["publish_clicked"] = True
                report["result"] = "blocked_formal_publish_attempt"
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            button = page.ele("css:#saveDraftButton", timeout=5)
            if not button:
                report["result"] = "save_draft_button_missing"
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 3
            button.click()
            report["draft_save_clicked"] = True
            time.sleep(10)
            report["publish_guard_events"] = read_publish_guard_events(page)
            if report["publish_guard_events"]:
                report["publish_clicked"] = True
                report["result"] = "blocked_formal_publish_attempt"
                save_artifacts(page, args.output_dir, report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 4
            try:
                report["alert_text"] = page.handle_alert(accept=True, timeout=2)
            except Exception:
                report["alert_text"] = None
            report["state_after_save"] = inspect_state(page)
            draft_url = str(page.url)
            report["draft_url"] = draft_url if "draftId=" in draft_url else None
            try:
                page.get(DRAFT_INDEX_URL)
            except Exception:
                try:
                    report["navigation_alert_text"] = page.handle_alert(
                        accept=True, timeout=2
                    )
                except Exception:
                    report["navigation_alert_text"] = None
                page.get(DRAFT_INDEX_URL)
            time.sleep(8)
            body = page.ele("tag:body")
            draft_text = (body.text or "") if body else ""
            report["draft_list_contains_title"] = str(product.get("title") or "") in draft_text
            report["draft_records_after"] = draft_records(page)
            before_ids = {str(item.get("id") or "") for item in report.get("draft_records_before", [])}
            title = str(product.get("title") or "")
            matching = [item for item in report["draft_records_after"] if item.get("title") == title]
            new_matching = [item for item in matching if item.get("id") not in before_ids]
            if not new_matching:
                # Draft indexing can lag the save response by a few seconds.
                time.sleep(5)
                page.get(DRAFT_INDEX_URL)
                time.sleep(6)
                report["draft_records_after_retry"] = draft_records(page)
                report["draft_records_after"] = report["draft_records_after_retry"]
                matching = [item for item in report["draft_records_after"] if item.get("title") == title]
                new_matching = [item for item in matching if item.get("id") not in before_ids]
            if args.existing_draft_id:
                chosen = next((item for item in matching if str(item.get("id")) == str(args.existing_draft_id)), None)
            else:
                chosen = new_matching[0] if len(new_matching) == 1 else None
            report["draft_record_selected"] = chosen
            if chosen:
                report["draft_id"] = chosen.get("id")
                report["draft_url"] = chosen.get("url") or report.get("draft_url")
            report["draft_identity_verified"] = bool(
                chosen and (
                    (args.existing_draft_id and str(chosen.get("id")) == str(args.existing_draft_id))
                    or (not args.existing_draft_id and chosen.get("id") not in before_ids)
                )
            )
            report["description_reopen_verified"] = False
            if report["draft_url"]:
                page.get(report["draft_url"])
                # Draft form hydrates logistics controls after the main React
                # tree; allow that second request to finish before checking.
                time.sleep(20)
                install_publish_guards(page)
                reopened_description = inspect_description_state(page)
                report["description_after_reopen"] = reopened_description
                expected_images = int(
                    report["fields"]["description"].get("images", {}).get("requested", 0)
                )
                expected_text = str((product.get("description") or {}).get("text") or "").strip()
                report["description_reopen_verified"] = (
                    reopened_description["max_text_length"] > 0
                    and reopened_description["max_iframe_images"] >= expected_images
                    and (not expected_text or expected_text[:20] in "\n".join(
                        str(item.get("text") or "") for item in reopened_description["frames"]
                    ))
                )
                report["state_after_reopen"] = inspect_state(page)
                discover_sku_table(page)
                reopened_rows = read_sku_table_rows(page)
                reopened_for_validation = []
                reopened_page_price = str((read_price_range(page).get("price") or "")).strip()
                if not reopened_page_price:
                    reopened_page_price = displayed_price(report["state_after_reopen"].get("price_range_preview"))
                dimensions = list(sku_model.get("dimensions") or [])
                for index, rendered in enumerate(reopened_rows):
                    source = normalized_sku_rows[index] if index < len(normalized_sku_rows) else {}
                    row_text = str(rendered.get("text") or "")
                    props = {
                        str(dimension.get("name")): (
                            str((source.get("properties") or {}).get(str(dimension.get("name"))) or "")
                            if str((source.get("properties") or {}).get(str(dimension.get("name"))) or "") in row_text else ""
                        ) for dimension in dimensions
                    }
                    inputs = rendered.get("inputs") or []
                    values = {
                        " ".join(str(item.get(key) or "") for key in ("name", "placeholder", "header")): str(item.get("value") or "")
                        for item in inputs
                    }
                    reopened_for_validation.append({
                        "properties": props,
                        "price": next((v for k, v in values.items() if re.search(r"price|价格|售价", k, re.I)), reopened_page_price),
                        "stock": next((v for k, v in values.items() if re.search(r"stock|库存|数量", k, re.I)), ""),
                        "sku_id": rendered.get("sku_id") or "",
                    })
                report["sku_reopen_validation"] = validate_target_rows(sku_model, reopened_for_validation)
                initial_attributes = report["fields"].get("attributes") or {}
                report["attributes_after_reopen"] = {
                    prop_id: selected_prop_value(page, prop_id) for prop_id in initial_attributes
                }
            reopened = report.get("state_after_reopen") or {}
            expected_skus = len(product.get("skus") or [])
            weights = reopened.get("package_weight_values") or []
            report["field_reopen_checks"] = {
                "draft_identity": bool(report.get("draft_identity_verified")),
                "description": bool(report["description_reopen_verified"]),
                "title": reopened.get("product_title_value") == str(product.get("title") or ""),
                "category": reopened.get("category_id_value") == category_id or f"catId={category_id}" in str(reopened.get("url") or ""),
                "main_images": int(reopened.get("main_image_count") or 0) >= int(report["fields"].get("main_images_expected") or 0),
                "sku_values": bool((report.get("sku_reopen_validation") or {}).get("valid")),
                "price": same_number(displayed_price(reopened.get("price_range_preview")), expected_price),
                "attributes": all(
                    bool(item.get("displayed")) and report.get("attributes_after_reopen", {}).get(prop_id) == item.get("displayed")
                    for prop_id, item in (report["fields"].get("attributes") or {}).items() if isinstance(item, dict)
                ),
                "publish_not_clicked": not read_publish_guard_events(page),
            }
            optional_reopen_checks = {
                "shipping_address": (
                    not args.shipping_address
                    or _compact_text(args.shipping_address) in _compact_text(reopened.get("shipping_address_value"))
                ),
                "delivery_time": (
                    not args.delivery_promise
                    or _compact_text(args.delivery_promise) in _compact_text(reopened.get("delivery_time_value"))
                ),
                "freight_template": (
                    not args.freight_template_text
                    or _compact_text(args.freight_template_text) in _compact_text(reopened.get("freight_template_value"))
                ),
                "package_weights": (
                    args.package_weight_grams is None
                    or (len(weights) == expected_skus and all(
                        len(row) >= 4 and str(row[3]) == str(args.package_weight_grams) for row in weights
                    ))
                ),
            }
            report["field_reopen_checks"].update(optional_reopen_checks)
            report["result"] = (
                "draft_saved_and_reopened_verified"
                if report["draft_list_contains_title"]
                and all(report["field_reopen_checks"].values())
                else "draft_save_not_verified"
            )
        else:
            report["result"] = "preview_filled"

        report["publish_guard_events"] = read_publish_guard_events(page)
        report["publish_clicked"] = any(bool(item.get("blocked")) for item in report["publish_guard_events"] if isinstance(item, dict))
        if report["publish_clicked"]:
            report["result"] = "blocked_formal_publish_attempt"
        save_artifacts(page, args.output_dir, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["result"] in {
            "preview_filled", "draft_saved_and_reopened_verified"
        } else 4
    finally:
        # Keep the user profile intact while closing the automation connection.
        if not args.keep_open:
            try:
                page.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
