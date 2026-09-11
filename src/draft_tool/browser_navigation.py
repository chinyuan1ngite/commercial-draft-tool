"""Shared browser navigation recovery for seller and source pages."""
from __future__ import annotations

import time
from typing import Any


class PopupRecoveryError(RuntimeError):
    """The page remains blocked after bounded dialog recovery."""


def _dismiss_native_dialogs(page: Any, limit: int) -> list[str]:
    dismissed = []
    for attempt in range(limit + 1):
        # A non-boolean argument reads the dialog without DrissionPage's
        # unbounded post-close wait. CDP performs a bounded cancellation.
        try:
            text = page.handle_alert(accept="get", timeout=.2)
        except Exception as exc:
            raise PopupRecoveryError("native_dialog_probe_failed") from exc
        if text is False or text is None:
            return dismissed
        if attempt == limit:
            raise PopupRecoveryError("native_dialog_limit_exceeded")
        try:
            page.run_cdp("Page.handleJavaScriptDialog", accept=False, _timeout=1)
        except Exception as exc:
            raise PopupRecoveryError("native_dialog_cancellation_failed") from exc
        dismissed.append("native_dialog_cancelled")
        time.sleep(.05)
    return dismissed


def dismiss_pending_alert(page: Any) -> str | None:
    """Cancel unknown dialogs before navigating away from a page."""
    dismissed = _dismiss_native_dialogs(page, 3)
    return dismissed[-1] if dismissed else None


def dismiss_unexpected_popups(page: Any, max_native: int = 3) -> list[str]:
    """Dismiss stale native dialogs and close unrelated seller-page overlays.

    Native dialogs are cancelled before touching the page DOM. Common modal
    close controls are then clicked, except for the picture picker and the
    description schema editor, which may be legitimately open mid-flow.
    """
    dismissed = _dismiss_native_dialogs(page, max_native)
    try:
        closed = page.run_js(
            r"""
            const active = node =>
              Boolean(node.closest('.ibank-picker-dialog')) ||
              Boolean(node.closest('.ant-modal, .next-dialog, .ui-dialog')?.querySelector('iframe.picker-frame, iframe[src*="schema"]'));
            const visible = node => node.getClientRects().length &&
              getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none';
            let count = 0;
            const propertyDialogs = [...document.querySelectorAll('.cat-prop-apply-modal')]
              .filter(node => visible(node) && !active(node));
            let propertyCancelled = 0;
            for (const dialog of propertyDialogs) {
              const cancel = [...dialog.querySelectorAll('button')].filter(button =>
                visible(button) && !button.disabled && button.getAttribute('aria-disabled') !== 'true' &&
                button.innerText.replace(/\s/g, '') === '取消');
              if (cancel.length === 1) { cancel[0].click(); propertyCancelled++; }
            }
            Array.from(document.querySelectorAll(
              '.next-dialog-close, .ant-modal-close, .ui-dialog-close, .window-action-close'
            )).forEach(node => {
              if (visible(node) && !active(node)) { node.click(); count++; }
            });
            return {closed: count, property_seen: propertyDialogs.length, property_cancelled: propertyCancelled};
            """
        )
        if isinstance(closed, dict):
            if closed.get('property_seen'):
                deadline = time.monotonic() + 2
                while page.run_js("""
                    return [...document.querySelectorAll('.cat-prop-apply-modal')].some(node =>
                        node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden' &&
                        !node.querySelector('iframe.picker-frame, iframe[src*="schema"]'));
                """):
                    if time.monotonic() >= deadline:
                        raise PopupRecoveryError('property_application_dialog_still_open')
                    time.sleep(.1)
            if closed.get('property_cancelled'):
                dismissed.append(f"property_application_cancelled:{closed['property_cancelled']}")
            closed = closed.get('closed', 0)
        if isinstance(closed, int) and closed:
            dismissed.append(f"unrelated_overlays_closed:{closed}")
    except PopupRecoveryError:
        raise
    except Exception as exc:
        raise PopupRecoveryError("overlay_recovery_failed") from exc
    return dismissed


def is_alert_exists_error(exc: BaseException) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    return "alertexists" in message or "alert exists" in message or "未处理的提示框" in str(exc)


def navigate_with_alert_recovery(page: Any, url: str) -> str | None:
    """Navigate once, retrying only a confirmed pending-dialog failure."""
    last_error: BaseException | None = None
    for attempt in range(2):
        dismiss_pending_alert(page)
        try:
            if page.get(url) is False:
                raise PopupRecoveryError('navigation_not_completed')
            return dismiss_pending_alert(page)
        except Exception as exc:
            last_error = exc
            if not is_alert_exists_error(exc):
                raise
            dismiss_pending_alert(page)
            if attempt:
                raise PopupRecoveryError('navigation_blocked_by_native_dialog') from exc
            time.sleep(0.5)
    if last_error:
        raise last_error
    return None
