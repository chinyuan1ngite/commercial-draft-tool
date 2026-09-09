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


def dismiss_unexpected_popups(page: Any, max_native: int = 3) -> list[str]:
    """Dismiss stale native dialogs and close unrelated seller-page overlays.

    Native alert/confirm/prompt dialogs block the next CDP call until they are
    accepted, so they are drained before touching the page DOM. Common modal
    close controls are then clicked, except for the picture picker and the
    description schema editor, which may be legitimately open mid-flow.
    """
    dismissed: list[str] = []
    for _ in range(max_native):
        try:
            text = page.handle_alert(accept=True, timeout=0.2)
        except Exception:
            break
        if not text:
            break
        dismissed.append(str(text or "").strip())
    try:
        page.run_js(
            """
            const active = node =>
              Boolean(node.closest('.ibank-picker-dialog')) ||
              Boolean(node.closest('.ant-modal')?.querySelector('iframe[src*="schema"]'));
            Array.from(document.querySelectorAll(
              '.next-dialog-close, .ant-modal-close, .ui-dialog-close, .window-action-close'
            )).forEach(node => {
              if (!active(node)) node.click();
            });
            """
        )
    except Exception:
        pass
    return [text for text in dismissed if text]


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
