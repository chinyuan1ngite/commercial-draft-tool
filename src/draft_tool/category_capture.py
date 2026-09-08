"""Interactive capture of a seller-side target leaf category."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from DrissionPage import ChromiumOptions, ChromiumPage

from .browser_actions import open_seller_page, is_seller_login_url
from .security import atomic_write, profile_lock


SELECT_CATEGORY_URL = "https://offer.1688.com/offer/post/choose_category.vm?file=choose_category.vm"
CAT_ID_RE = re.compile(r"(?i)(?:catId|categoryId)\s*[=:]\s*[\"']?(\d{3,})")


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def read_category_snapshot(page: ChromiumPage) -> dict[str, Any]:
    """Read category evidence without trusting a single mutable page field."""
    url = str(page.url)
    try:
        html = str(page.html or "")
    except Exception:
        html = ""
    query = parse_qs(urlparse(url).query)
    query_id = next(
        (str(query[key][0]).strip() for key in ("catId", "categoryId", "catid") if query.get(key)),
        "",
    )
    try:
        dom = page.run_js(
            """
        const idSelectors = [
          'input[name="catId"]', 'input[name="categoryId"]',
          'input#catId', 'input#categoryId', '[data-cat-id]', '[data-category-id]'
        ];
        const nameSelectors = [
          '#guid-category', '.category-path', '.categoryPath',
          '.selected-category', '.selectedCategory', '.category-name',
          '[class*="category-path"]', '[class*="categoryPath"]',
          '[class*="category-name"]', '[class*="categoryName"]',
          '[data-category-name]'
        ];
        const ids = idSelectors.flatMap(selector => Array.from(document.querySelectorAll(selector)).map(node => ({
          value: node.value || node.getAttribute('data-cat-id') || node.getAttribute('data-category-id') || '',
          selector
        }))).filter(item => item.value);
        const names = nameSelectors.flatMap(selector => Array.from(document.querySelectorAll(selector)).map(node => ({
          value: (node.innerText || node.textContent || node.getAttribute('data-category-name') || '').replace(/\\s+/g, ' ').trim(),
          selector
        }))).filter(item => item.value && item.value.length <= 300);
        return {ids, names, title: document.title || '', body: document.body?.innerText || ''};
            """
        ) or {}
    except Exception:
        dom = {}
    dom_ids = [str(item.get("value") or "").strip() for item in dom.get("ids") or []]
    id_candidates = [query_id, *dom_ids]
    html_candidates = CAT_ID_RE.findall(html)
    html_ids = [str(item).strip() for item in html_candidates]
    valid_ids = [item for item in id_candidates if re.fullmatch(r"\d{3,}", item)]
    unique_dom_ids = list(dict.fromkeys(item for item in dom_ids if re.fullmatch(r"\d{3,}", item)))
    unique_html_ids = list(dict.fromkeys(item for item in html_ids if re.fullmatch(r"\d{3,}", item)))
    evidence_sets = [set(item for item in (query_id, *unique_dom_ids) if item)]
    evidence_sets = [item for item in evidence_sets if item]
    conflicts = len(set().union(*evidence_sets)) > 1 if evidence_sets else False
    category_id = query_id or (unique_dom_ids[0] if len(unique_dom_ids) == 1 else "")
    if not category_id and len(unique_html_ids) == 1:
        category_id = unique_html_ids[0]
    if category_id and unique_dom_ids and category_id not in unique_dom_ids:
        conflicts = True
    if category_id and len(unique_html_ids) == 1 and unique_html_ids[0] != category_id:
        conflicts = True

    names = [
        _text(item.get("value")) for item in dom.get("names") or []
        if _text(item.get("value"))
    ]
    # The selected category path is usually the longest visible candidate.
    category_name = max(names, key=len, default="")
    if not category_name:
        body_lines = [_text(line) for line in str(dom.get("body") or "").splitlines()]
        category_lines = [
            line for line in body_lines
            if "类目" in line and 2 <= len(line) <= 300
            and not re.fullmatch(r"(?:选择|确认|发布)?类目", line)
        ]
        category_name = max(category_lines, key=len, default="")
    page_path = urlparse(url).path.lower()
    on_publish_page = any(marker in page_path for marker in (
        "/fillproductinfo", "/popular/publish", "/offer/publish"
    )) or bool(query_id)
    return {
        "category_id": category_id,
        "category_name": category_name or None,
        "url": url,
        "title": _text(dom.get("title")),
        "id_candidates": valid_ids,
        "html_id_candidates": unique_html_ids,
        "evidence_conflict": conflicts,
        "name_candidates": names,
        "on_publish_page": on_publish_page,
    }


def _write_capture_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "category-capture.json"
    atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2))
    return path


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="人工选择并捕获卖家目标叶子类目")
    parser.add_argument("--profile-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--login-timeout-seconds", type=int, default=0)
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args(argv)
    if args.login_timeout_seconds < 0:
        parser.error("--login-timeout-seconds 不能小于 0")

    options = ChromiumOptions()
    options.set_user_data_path(str(args.profile_dir.resolve()))
    options.headless(False)
    page = ChromiumPage(options)
    report: dict[str, Any] = {
        "result": None,
        "mode": "capture_target_category",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile_dir": str(args.profile_dir.resolve()),
        "select_url": SELECT_CATEGORY_URL,
        "login_timeout_seconds": args.login_timeout_seconds or None,
        "instruction": "请在浏览器中选择最终叶子类目，并点击确认类目/继续完善。",
    }
    try:
        with profile_lock(args.profile_dir):
            status = open_seller_page(
                page, SELECT_CATEGORY_URL, args.login_timeout_seconds, settle_seconds=5
            )
            if status != "ready":
                report["result"] = (
                    "seller_login_timeout" if status == "login_timeout"
                    else "seller_navigation_failed"
                    if str(status).startswith("navigation_error:")
                    else "seller_browser_closed_during_login"
                )
                report["login_wait_status"] = status
                path = _write_capture_report(args.output_dir, report)
                report["report_path"] = str(path)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 2
            print("请在卖家浏览器中选择最终叶子类目，并点击‘确认类目/继续完善’。", flush=True)
            deadline = None if args.login_timeout_seconds <= 0 else time.monotonic() + args.login_timeout_seconds
            snapshot: dict[str, Any] = {}
            while True:
                try:
                    current_url = str(page.url)
                except Exception:
                    report["result"] = "seller_browser_closed_during_category_capture"
                    break
                if is_seller_login_url(current_url):
                    report["result"] = "seller_login_required_again"
                    break
                try:
                    snapshot = read_category_snapshot(page)
                except Exception as exc:
                    report["result"] = "category_capture_read_failed"
                    report["error"] = type(exc).__name__
                    break
                if (
                    snapshot.get("category_id")
                    and snapshot.get("on_publish_page")
                    and not snapshot.get("evidence_conflict")
                ):
                    report["result"] = "category_captured"
                    report["captured"] = snapshot
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    report["result"] = "category_capture_timeout"
                    report["last_snapshot"] = snapshot
                    if snapshot.get("evidence_conflict"):
                        report["result"] = "category_id_evidence_conflict"
                    break
                time.sleep(2)
            report["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            path = _write_capture_report(args.output_dir, report)
            report["report_path"] = str(path)
            # Rewrite once so report_path is included in the artifact itself.
            _write_capture_report(args.output_dir, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["result"] == "category_captured" else 2
    except RuntimeError as exc:
        report["result"] = "blocked_profile_in_use"
        report["error"] = str(exc)
        path = _write_capture_report(args.output_dir, report)
        report["report_path"] = str(path)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 5
    finally:
        if not args.keep_open:
            try:
                page.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
