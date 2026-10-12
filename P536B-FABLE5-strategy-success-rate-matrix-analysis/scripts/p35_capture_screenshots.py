#!/usr/bin/env python3
"""
P35 Screenshot Capture Script
Captures real browser screenshots for all display-only catalog lifecycle modes.
Uses mocked API routes (same as test_replay_browser_smoke.py playwright test).
No DB write, no backfill, no production API calls.
"""

from __future__ import annotations

import json
import os
import socketserver
import sys
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay" / "screenshots" / "p35"

# ─── Local HTTP server ────────────────────────────────────────────────────────
@contextmanager
def _serve_repo(root: Path):
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.allow_reuse_address = True
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


# ─── Mock API payloads ────────────────────────────────────────────────────────
def _mock_json(route, payload):
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False),
    )


def _freshness_payload():
    return {
        "generated_at": "2026-05-12T00:00:00Z",
        "coverage_mode": "LIMITED",
        "total_rows": 460,
        "total_predicted": 420,
        "total_replay_error": 40,
        "legacy_error_count": 40,
        "has_legacy_errors": True,
        "lottery_types": ["BIG_LOTTO"],
        "latest_run_id": 1,
        "latest_run_status": "DONE",
        "per_lottery_latest_run": [
            {
                "lottery_type": "BIG_LOTTO",
                "replay_run_id": 1,
                "status": "DONE",
                "coverage_mode": "LIMITED",
                "row_count": 1,
                "predicted_count": 1,
                "error_count": 0,
            }
        ],
        "disclaimer": "本頁為歷史預測回放，用於稽核，不代表提高中獎率。",
    }


def _strategies_payload(lifecycle_status: str):
    if lifecycle_status == "ONLINE":
        return {
            "strategies": [
                {
                    "strategy_id": "biglotto_triple_strike",
                    "strategy_name": "大樂透 Triple Strike",
                    "strategy_version": "v0.1",
                    "supported_lottery_types": ["BIG_LOTTO"],
                    "min_history": 100,
                    "status": "ONLINE",
                    "lifecycle_status": "ONLINE",
                    "strategy_lifecycle_status": "ONLINE",
                }
            ],
            "count": 1,
            "filter_lottery_type": "BIG_LOTTO",
            "filter_lifecycle_status": lifecycle_status,
            "filter": "BIG_LOTTO",
        }
    if lifecycle_status in ("REJECTED", "RETIRED", "OBSERVATION"):
        return {
            "strategies": [
                {
                    "strategy_id": f"example_{lifecycle_status.lower()}_01",
                    "strategy_name": f"Catalog Example ({lifecycle_status})",
                    "strategy_version": "v0.1",
                    "supported_lottery_types": ["BIG_LOTTO"],
                    "min_history": 100,
                    "status": lifecycle_status,
                    "lifecycle_status": lifecycle_status,
                    "strategy_lifecycle_status": lifecycle_status,
                }
            ],
            "count": 1,
            "filter_lottery_type": "BIG_LOTTO",
            "filter_lifecycle_status": lifecycle_status,
            "filter": "BIG_LOTTO",
        }
    # OFFLINE — no entries
    return {
        "strategies": [],
        "count": 0,
        "filter_lottery_type": "BIG_LOTTO",
        "filter_lifecycle_status": lifecycle_status,
        "filter": "BIG_LOTTO",
    }


def _summary_payload(lifecycle_status: str):
    return {
        "lottery_type": "BIG_LOTTO",
        "filter": {"strategy_id": None, "date_from": None, "date_to": None},
        "filter_lifecycle_status": lifecycle_status,
        "summaries": [] if lifecycle_status != "ONLINE" else [
            {
                "strategy_id": "biglotto_triple_strike",
                "strategy_name": "大樂透 Triple Strike",
                "total_rows": 1,
                "predicted_count": 1,
                "avg_hit_count": 3,
                "hit_3plus_count": 1,
                "special_hit_count": 0,
                "rejected_count": 0,
                "insufficient_count": 0,
                "error_count": 0,
            }
        ],
        "disclaimer": "本摘要為歷史預測回放統計，只用於查詢與稽核；不代表提高中獎率，也不保證任何回放結果。",
        "data_scope": "ALL_REPLAY_ROWS",
        "legacy_error_count": 0,
        "has_legacy_errors": False,
        "scope_note": None,
    }


def _history_payload(lifecycle_status: str):
    if lifecycle_status != "ONLINE":
        return {
            "total": 0, "page": 1, "page_size": 50, "pages": 1,
            "filter_lifecycle_status": lifecycle_status, "records": []
        }
    return {
        "total": 1, "page": 1, "page_size": 50, "pages": 1,
        "filter_lifecycle_status": lifecycle_status,
        "records": [
            {
                "id": 1,
                "lottery": "BIG_LOTTO",
                "lottery_type": "BIG_LOTTO",
                "target_draw": "99000105",
                "target_date": "2010/12/31",
                "strategy_id": "biglotto_triple_strike",
                "strategy_name": "大樂透 Triple Strike",
                "strategy_version": "v0.1",
                "history_cutoff": "99000104",
                "replay_status": "PREDICTED",
                "reject_reason": "",
                "predicted_numbers": [3, 8, 22, 35, 38, 43],
                "predicted_special": None,
                "actual_numbers": [4, 9, 27, 36, 38, 39],
                "actual_special": None,
                "hit_numbers": [38],
                "hit_count": 1,
                "special_hit": False,
                "replay_run_id": 1,
                "generated_at": "2026-05-12T00:00:00Z",
                "lifecycle_status": lifecycle_status,
                "strategy_lifecycle_status": lifecycle_status,
            }
        ],
    }


def route_handler(route):
    parsed_url = urlparse(route.request.url)
    query = parse_qs(parsed_url.query)

    if parsed_url.path.endswith("/api/replay/freshness"):
        return _mock_json(route, _freshness_payload())
    if parsed_url.path.endswith("/api/replay/summary"):
        lc = query.get("lifecycle_status", ["ONLINE"])[0]
        return _mock_json(route, _summary_payload(lc))
    if parsed_url.path.endswith("/api/replay/history"):
        lc = query.get("lifecycle_status", ["ONLINE"])[0]
        return _mock_json(route, _history_payload(lc))
    if parsed_url.path.endswith("/api/replay/strategies"):
        lc = query.get("lifecycle_status", ["ONLINE"])[0]
        return _mock_json(route, _strategies_payload(lc))
    return route.continue_()


def wait_for_query_result(page, lifecycle: str, timeout_ms: int = 8000):
    """Wait for the replay result area to update after clicking query."""
    if lifecycle == "ONLINE":
        page.wait_for_function(
            "() => document.querySelector('#rp-hist-body').innerText.includes('PREDICTED')",
            timeout=timeout_ms,
        )
    elif lifecycle == "OFFLINE":
        page.wait_for_function(
            "() => document.querySelector('#rp-hist-body').innerText.includes('coming soon')",
            timeout=timeout_ms,
        )
    else:
        # REJECTED / RETIRED / OBSERVATION
        page.wait_for_function(
            "() => document.querySelector('#rp-hist-body').innerText.includes('無歷史回放資料')",
            timeout=timeout_ms,
        )


def capture_lifecycle(page, base_url: str, lifecycle: str, filename: str) -> dict:
    """Navigate to lifecycle, query, screenshot. Returns result dict."""
    print(f"  → Capturing {lifecycle}...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / filename

    try:
        page.goto(f"{base_url}/index.html?rp_lc={lifecycle}", wait_until="load")
        page.wait_for_selector('#rp-lifecycle-select', state='attached', timeout=8000)

        # Click into replay section
        replay_nav = page.locator('[data-section="replay"]')
        if replay_nav.count() > 0:
            replay_nav.evaluate('(el) => el.click()')

        page.wait_for_selector('#rp-query-btn', state='visible', timeout=5000)
        page.select_option('#rp-lifecycle-select', lifecycle)
        page.locator('#rp-query-btn').click()
        wait_for_query_result(page, lifecycle)

        # Scroll replay section into view
        page.locator('#rp-hist-body').scroll_into_view_if_needed()
        page.wait_for_timeout(400)  # slight settle

        page.screenshot(path=str(out_path), full_page=False, clip=None)
        body_text = page.locator('#rp-hist-body').inner_text()
        print(f"    ✅ {filename} captured. body text snippet: {body_text[:120]!r}")
        return {"status": "CAPTURED", "file": str(out_path), "body_snippet": body_text[:200]}
    except Exception as e:
        print(f"    ❌ FAILED: {e}")
        return {"status": "BLOCKED", "file": None, "error": str(e)}


def capture_fixture_mode(page, base_url: str) -> tuple[dict, dict]:
    """Capture fixture mode ON and OFF screenshots."""
    print("  → Capturing fixture mode ON...")
    on_path = OUTPUT_DIR / "06_fixture_mode_on_banner.png"
    off_path = OUTPUT_DIR / "07_fixture_mode_off_clean.png"

    on_result = {"status": "BLOCKED", "file": None}
    off_result = {"status": "BLOCKED", "file": None}

    try:
        # Fixture mode ON via URL param
        page.goto(f"{base_url}/index.html?rp_lc=REJECTED&rp_fixture_mode=1", wait_until="load")
        page.wait_for_selector('#rp-lifecycle-select', state='attached', timeout=8000)

        replay_nav = page.locator('[data-section="replay"]')
        if replay_nav.count() > 0:
            replay_nav.evaluate('(el) => el.click()')

        page.wait_for_selector('#rp-query-btn', state='visible', timeout=5000)
        page.locator('#rp-query-btn').click()

        # Try to detect fixture banner
        page.wait_for_timeout(2000)
        page.screenshot(path=str(on_path), full_page=False)
        page_text = page.locator('body').inner_text()
        fixture_indicator = any(kw in page_text.lower() for kw in ['fixture', 'synthetic', 'demo', '合成', '模擬'])
        print(f"    fixture indicator found: {fixture_indicator}")
        on_result = {
            "status": "CAPTURED",
            "file": str(on_path),
            "fixture_indicator_in_body": fixture_indicator,
            "body_snippet": page_text[:300],
        }
    except Exception as e:
        print(f"    ❌ fixture ON FAILED: {e}")
        on_result = {"status": "BLOCKED", "file": None, "error": str(e)}

    try:
        print("  → Capturing fixture mode OFF...")
        page.goto(f"{base_url}/index.html?rp_lc=REJECTED", wait_until="load")
        page.wait_for_selector('#rp-lifecycle-select', state='attached', timeout=8000)

        replay_nav = page.locator('[data-section="replay"]')
        if replay_nav.count() > 0:
            replay_nav.evaluate('(el) => el.click()')

        page.wait_for_selector('#rp-query-btn', state='visible', timeout=5000)
        page.locator('#rp-query-btn').click()
        wait_for_query_result(page, "REJECTED")
        page.wait_for_timeout(400)

        page.screenshot(path=str(off_path), full_page=False)
        print(f"    ✅ {off_path.name} captured.")
        off_result = {"status": "CAPTURED", "file": str(off_path)}
    except Exception as e:
        print(f"    ❌ fixture OFF FAILED: {e}")
        off_result = {"status": "BLOCKED", "file": None, "error": str(e)}

    return on_result, off_result


def main():
    from playwright.sync_api import sync_playwright

    print(f"=== P35 Screenshot Capture ===")
    print(f"REPO_ROOT: {REPO_ROOT}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")
    print(f"index.html: {INDEX_HTML.exists()}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    with _serve_repo(REPO_ROOT) as base_url:
        print(f"Server: {base_url}")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.route("**/api/replay/**", route_handler)

            scenarios = [
                ("ONLINE",      "01_replay_online_production.png"),
                ("REJECTED",    "02_replay_rejected_display_only.png"),
                ("RETIRED",     "03_replay_retired_display_only.png"),
                ("OBSERVATION", "04_replay_observation_display_only.png"),
                ("OFFLINE",     "05_replay_offline_coming_soon.png"),
            ]
            for lifecycle, filename in scenarios:
                results[filename] = capture_lifecycle(page, base_url, lifecycle, filename)

            on_r, off_r = capture_fixture_mode(page, base_url)
            results["06_fixture_mode_on_banner.png"] = on_r
            results["07_fixture_mode_off_clean.png"] = off_r

            browser.close()

    print("\n=== Summary ===")
    captured = sum(1 for r in results.values() if r["status"] == "CAPTURED")
    blocked  = sum(1 for r in results.values() if r["status"] == "BLOCKED")
    print(f"CAPTURED: {captured} / 7")
    print(f"BLOCKED:  {blocked} / 7")
    for name, r in results.items():
        status = r["status"]
        print(f"  {status:10s}  {name}")

    # Write summary JSON for evidence report
    summary_path = OUTPUT_DIR / "capture_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "captured": captured, "blocked": blocked}, f, ensure_ascii=False, indent=2)
    print(f"\nSummary written: {summary_path}")

    return 0 if blocked == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
