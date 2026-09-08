"""Shared browser navigation recovery for seller and source pages."""
from __future__ import annotations

import time
from typing import Any


def dismiss_pending_alert(page: Any) -> str | None:
    """Accept a stale dialog before the next CDP navigation call."""
    try:
        text = page.handle_alert(accept=True, timeout=0.5)
    except Exception:
        return None
    return str(text or "").strip() or None


def is_alert_exists_error(exc: BaseException) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    return "alertexists" in message or "alert exists" in message or "未处理的提示框" in str(exc)


def navigate_with_alert_recovery(page: Any, url: str) -> str | None:
    """Navigate once, retrying only a confirmed pending-dialog failure."""
    last_error: BaseException | None = None
    for attempt in range(2):
        dismiss_pending_alert(page)
        try:
            page.get(url)
            return dismiss_pending_alert(page)
        except Exception as exc:
            last_error = exc
            if not is_alert_exists_error(exc) or attempt:
                raise
            dismiss_pending_alert(page)
            time.sleep(0.5)
    if last_error:
        raise last_error
    return None
