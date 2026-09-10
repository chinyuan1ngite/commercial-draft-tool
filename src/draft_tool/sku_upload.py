"""Transaction-scoped image upload receipts; never persist request headers."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
import uuid
from email.parser import Parser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .security import MAX_IMAGE_BYTES, hostname_allowed


UPLOAD_ENDPOINT = 'https://picman.1688.com/album/ajax/image_upload_ajax.json'


def _receipt(packet: Any, filename: str, digest: str) -> dict[str, str]:
    parsed = urlparse(str(packet.url))
    if (parsed.scheme + '://' + parsed.netloc + parsed.path != UPLOAD_ENDPOINT
            or packet.method != 'POST' or packet.is_failed or packet.response.status != 200):
        raise RuntimeError('sku_upload_response_failed')
    # CDP omits binary file bytes, but preserves the multipart file name. A
    # unique temporary name ties this request to the validated local copy.
    content_type = str(packet.request.headers.get('Content-Type') or '')
    body = packet.request.postData
    if not content_type.lower().startswith('multipart/form-data') or not isinstance(body, str):
        raise RuntimeError('sku_upload_request_identity_unconfirmed')
    message = Parser().parsestr('Content-Type: ' + content_type + '\r\n\r\n' + body)
    names = [part.get_filename() for part in message.walk() if part.get_filename() is not None]
    if names != [filename]:
        raise RuntimeError('sku_upload_request_identity_unconfirmed')
    raw = packet.response.raw_body
    if not isinstance(raw, str) or len(raw) > 65536:
        raise RuntimeError('sku_upload_response_invalid')
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        raise RuntimeError('sku_upload_response_invalid') from None
    if not isinstance(result, dict) or result.get('result') != 'success':
        raise RuntimeError('sku_upload_response_failed')
    lists = [result.get(key) for key in ('dataList', 'imgUrls', 'miniImgUrls')]
    if any(not isinstance(items, list) or len(items) != 1 for items in lists):
        raise RuntimeError('sku_upload_response_ambiguous')
    media_id, original, thumbnail = (items[0] for items in lists)
    if (isinstance(media_id, bool) or not re.fullmatch(r'[1-9][0-9]*', str(media_id))
            or any(not isinstance(url, str) or not hostname_allowed(url, {'alicdn.com'})
                   or urlparse(url).query or urlparse(url).fragment for url in (original, thumbnail))):
        raise RuntimeError('sku_upload_response_invalid')
    return {'sha256': digest, 'id': str(media_id), 'original_url': original,
            'thumbnail_url': thumbnail, 'evidence': 'correlated_upload_response'}


def upload_with_receipt(frame: Any, file_input: Any, path: Path, digest: str,
                        transaction: dict[str, Any], progress: Any) -> dict[str, str] | None:
    """Observe only one picker POST, linked to an immutable local upload copy."""
    listener = frame.listen
    if listener.listening is True:
        raise RuntimeError('sku_upload_listener_already_active')
    try:
        listener.start(targets='^' + re.escape(UPLOAD_ENDPOINT) + r'(?:\?|$)', is_regex=True, method='POST')
        with tempfile.TemporaryDirectory(prefix='sku-upload-') as folder:
            with path.open('rb') as source:
                content = source.read(MAX_IMAGE_BYTES + 1)
            if not content or len(content) > MAX_IMAGE_BYTES or hashlib.sha256(content).hexdigest() != digest:
                raise RuntimeError('local_media_identity_mismatch')
            staged = Path(folder) / ('sku-' + uuid.uuid4().hex + path.suffix)
            staged.write_bytes(content)
            transaction['upload_filename'] = staged.name
            before = progress(frame)
            transaction.update(stage='upload', side_effect_possible=True)
            file_input.input(str(staged))
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                packet = listener.wait(timeout=.1, raise_err=False)
                if packet:
                    break
                if progress(frame) > before:
                    transaction['upload_progress_verified'] = True
                    # Allow a short response-delivery lag. An unsupported upload
                    # transport may still use the original-byte verification path.
                    packet = listener.wait(timeout=1, raise_err=False)
                    if packet:
                        break
                    return None
            else:
                raise RuntimeError('upload_completion_unconfirmed')
            transaction['stage'] = 'upload_response'
            receipt = _receipt(packet, staged.name, digest)
            if not listener.wait_silent(timeout=1, targets_only=True) or listener.wait(timeout=.1, raise_err=False):
                raise RuntimeError('sku_upload_response_ambiguous')
            transaction['upload_progress_verified'] = progress(frame) > before
            return receipt
    finally:
        if listener.listening is True:
            listener.stop()


def matches_receipt(record: dict[str, Any], digest: str, receipt: dict[str, Any] | None) -> bool:
    if not receipt or receipt.get('sha256') != digest or receipt.get('evidence') != 'correlated_upload_response':
        return False
    if record.get('loaded') is False or not receipt.get('id'):
        return False
    if record.get('id') and str(record['id']) != receipt['id']:
        return False
    return bool(record.get('src')) and record['src'] in (receipt.get('original_url'), receipt.get('thumbnail_url'))
