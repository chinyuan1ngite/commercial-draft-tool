"""Bounded, credential-free content verification for rendered platform images."""
from __future__ import annotations

import base64
import hashlib
from typing import Any

from .security import IMAGE_HOSTS, MAX_IMAGE_BYTES, read_allowlisted_url
from .sku_upload import matches_receipt


def verified_image(record: dict[str, Any], digest: str, cache: dict[str, str | None],
                   receipt: dict[str, Any] | None = None) -> bool:
    if record.get("loaded") is False:
        return False
    src = str(record.get("src") or "")
    if not src:
        return False
    if matches_receipt(record, digest, receipt):
        return True
    if src not in cache:
        try:
            if src.startswith("data:image/"):
                header, payload = src.split(",", 1)
                if not header.endswith(";base64") or len(payload) > (MAX_IMAGE_BYTES * 4 // 3 + 4):
                    return False
                data = base64.b64decode(payload, validate=True)
            else:
                data, headers = read_allowlisted_url(src, IMAGE_HOSTS, max_bytes=MAX_IMAGE_BYTES, timeout=3)
                if not str(headers.get("Content-Type") or "").lower().startswith("image/"):
                    return False
            if len(data) > MAX_IMAGE_BYTES:
                return False
            cache[src] = hashlib.sha256(data).hexdigest()
        except Exception:
            # A processing URL can briefly be unavailable. The caller's bounded
            # readback loop may retry it; only actual content is cacheable.
            return False
    return cache.get(src) == digest
