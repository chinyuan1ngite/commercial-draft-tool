"""Small security primitives shared by collection and draft execution."""
from __future__ import annotations

import ipaddress
import os
import sqlite3
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


IMAGE_HOSTS = {"alicdn.com", "1688.com", "tmall.com"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 40 * 1024 * 1024


def hostname_allowed(url: str, allowed_hosts: set[str] | None = None) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    try:
        if parsed.port not in (None, 443):
            return False
    except ValueError:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if allowed_hosts is None:
        allowed_hosts = IMAGE_HOSTS
    if not any(host == item or host.endswith("." + item) for item in allowed_hosts):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)


def atomic_write(path: Path, data: str, encoding: str = "utf-8") -> Path:
    """Write a complete file and replace the destination atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return path


def download_image(url: str, destination: Path, *, max_bytes: int = MAX_IMAGE_BYTES) -> int:
    """Download one image with allowlisted HTTPS redirects and bounded memory."""
    current = str(url or "").strip()
    total = 0
    class SafeRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not hostname_allowed(newurl):
                raise ValueError("图片重定向目标不在允许列表")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    if not hostname_allowed(current):
        raise ValueError("图片 URL 主机不在 1688 允许列表或不是 HTTPS")
    request = Request(current, headers={"User-Agent": "commercial-draft-tool/0.2"})
    with build_opener(SafeRedirectHandler()).open(request, timeout=20) as response:
            if not hostname_allowed(response.geturl()):
                raise ValueError("图片最终 URL 不在允许列表")
            content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
            if not content_type.startswith("image/"):
                raise ValueError(f"图片响应类型不受支持: {content_type}")
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError("图片响应超过大小限制")
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=str(destination.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("图片响应超过大小限制")
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, destination)
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
            return total


def read_allowlisted_url(url: str, allowed_hosts: set[str], *, max_bytes: int = 8 * 1024 * 1024) -> tuple[bytes, object]:
    """Read a bounded HTTPS response while validating every redirect."""
    class SafeRedirectHandler(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not hostname_allowed(newurl, allowed_hosts):
                raise ValueError("重定向目标不在允许列表")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    if not hostname_allowed(url, allowed_hosts):
        raise ValueError("URL 主机不在允许列表或不是 HTTPS")
    request = Request(url, headers={"User-Agent": "commercial-draft-tool/0.2"})
    with build_opener(SafeRedirectHandler()).open(request, timeout=20) as response:
        if not hostname_allowed(response.geturl(), allowed_hosts):
            raise ValueError("最终 URL 不在允许列表")
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("响应超过大小限制")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("响应超过大小限制")
        return data, response.headers


@contextmanager
def profile_lock(profile_dir: Path, timeout: float = 0.0):
    """Cross-process lock for one seller profile, using an exclusive lock file."""
    profile_dir.mkdir(parents=True, exist_ok=True)
    lock_path = profile_dir / ".commercial-draft.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        import msvcrt
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + timeout
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if timeout <= 0 or time.monotonic() >= deadline:
                    raise RuntimeError("卖家 Profile 正在被另一个任务使用")
                time.sleep(0.1)
        yield
    finally:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        handle.close()


class DraftLedger:
    """Persistent idempotency ledger, scoped to the isolated project."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS drafts (
            store_identity TEXT NOT NULL, source_offer_id TEXT NOT NULL,
            draft_id TEXT, output_dir TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(store_identity, source_offer_id)
        )""")
        return connection

    def get(self, store_identity: str, offer_id: str):
        with closing(self._connect()) as db:
            row = db.execute("SELECT draft_id, output_dir FROM drafts WHERE store_identity=? AND source_offer_id=?", (store_identity, offer_id)).fetchone()
            return {"draft_id": row[0], "output_dir": row[1]} if row else None

    def put(self, store_identity: str, offer_id: str, draft_id: str | None, output_dir: Path):
        with closing(self._connect()) as db:
            with db:
                db.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(store_identity, source_offer_id) DO UPDATE SET draft_id=excluded.draft_id, output_dir=excluded.output_dir, updated_at=excluded.updated_at", (store_identity, offer_id, draft_id, str(output_dir)))
