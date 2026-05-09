"""Lifecycle filter browser E2E for Replay Lifecycle UI.

This test uses Playwright when available and skips cleanly when browser tooling
is unavailable in the current workspace.
"""
from __future__ import annotations

import json
import socketserver
import sys
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

PLAYWRIGHT = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright browser tooling unavailable",
)
from playwright.sync_api import sync_playwright  # type: ignore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


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


def _mock_json(route, payload):
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False),
    )


def _freshness_payload():
    return {
        "generated_at": "2026-05-09T00:00:00Z",
        "coverage_mode": "LIMITED",
        "total_rows": 2,
        "total_predicted": 2,
        "total_replay_error": 0,
        "legacy_error_count": 0,
        "has_legacy_errors": False,
        "lottery_types": ["BIG_LOTTO"],
        "latest_run_id": 1,
        "latest_run_status": "DONE",
        "per_lottery_latest_run": [
            {
                "lottery_type": "BIG_LOTTO",
                "replay_run_id": 1,
                "status": "DONE",
                "coverage_mode": "LIMITED",
            }
        ],
        "disclaimer": "本頁為歷史預測回放，用於稽核，不代表提高中獎率。",
    }


def _summary_payload():
    return {
        "lottery_type": "BIG_LOTTO",
        "summaries": [
            {
                "strategy_id": "biglotto_triple_strike",
                "strategy_name": "大樂透 Triple Strike",
                "error_count": 0,
                "total_draws": 1,
                "avg_hit_count": 3,
            }
        ],
        "disclaimer": "本資料為歷史預測回放資料，不代表提高中獎率。",
        "data_scope": "ALL_REPLAY_ROWS",
        "legacy_error_count": 0,
        "has_legacy_errors": False,
    }


def _strategies_payload():
    return {
        "strategies": [
            {
                "strategy_id": "biglotto_triple_strike",
                "strategy_name": "大樂透 Triple Strike",
                "strategy_version": "v0.1",
                "supported_lottery_types": ["BIG_LOTTO"],
                "min_history": 100,
                "status": "ONLINE",
                "strategy_lifecycle_status": "ONLINE",
            },
            {
                "strategy_id": "biglotto_shadow_x",
                "strategy_name": "大樂透 Shadow X",
                "strategy_version": "v0.1",
                "supported_lottery_types": ["BIG_LOTTO"],
                "min_history": 100,
                "status": "OBSERVATION",
                "strategy_lifecycle_status": "OBSERVATION",
            },
        ],
        "count": 2,
        "filter_lottery_type": None,
        "filter_lifecycle_status": None,
        "filter": None,
    }


def _history_payload(lifecycle_status: str = "REJECTED"):
    return {
        "total": 1,
        "page": 1,
        "page_size": 50,
        "pages": 1,
        "filter_lifecycle_status": lifecycle_status,
        "records": [
            {
                "id": 1,
                "lottery_type": "BIG_LOTTO",
                "target_draw": 20260509,
                "target_date": "2026-05-09",
                "strategy_id": "biglotto_triple_strike",
                "strategy_name": "大樂透 Triple Strike",
                "strategy_version": "v0.1",
                "history_cutoff": 20260508,
                "replay_status": "PREDICTED",
                "reject_reason": "",
                "predicted_numbers": [1, 2, 3, 4, 5, 6],
                "predicted_special": None,
                "actual_numbers": [1, 2, 3, 8, 9, 10],
                "actual_special": None,
                "hit_numbers": [1, 2, 3],
                "hit_count": 3,
                "special_hit": False,
                "replay_run_id": 1,
                "generated_at": "2026-05-09T00:00:00Z",
                "strategy_lifecycle_status": lifecycle_status,
            }
        ],
    }


@pytest.mark.skipif(not INDEX_HTML.exists(), reason="index.html not found")
def test_lifecycle_filter_browser_e2e():
    with _serve_repo(REPO_ROOT) as base_url:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # pragma: no cover - depends on local browser tooling
                pytest.skip(f"Playwright browser unavailable: {exc}")
            page = browser.new_page()

            def route_handler(route):
                url = route.request.url
                parsed_url = urlparse(url)
                if url.endswith("/api/replay/freshness"):
                    return _mock_json(route, _freshness_payload())
                if url.endswith("/api/replay/summary"):
                    return _mock_json(route, _summary_payload())
                if parsed_url.path.endswith("/api/replay/history"):
                    query = parse_qs(parsed_url.query)
                    lifecycle_status = query.get("lifecycle_status", ["REJECTED"])[0]
                    return _mock_json(route, _history_payload(lifecycle_status))
                if url.endswith("/api/replay/strategies"):
                    return _mock_json(route, _strategies_payload())
                return route.continue_()

            page.route("**/api/replay/**", route_handler)
            page.goto(f"{base_url}/index.html?rp_lc=REJECTED", wait_until="load")
            page.wait_for_selector('#rp-lifecycle-select', state='attached')

            lifecycle_select = page.locator('#rp-lifecycle-select')
            assert lifecycle_select.count() == 1
            assert lifecycle_select.input_value() == 'REJECTED'

            page.locator('#rp-query-btn').evaluate('(el) => el.click()')
            page.wait_for_selector('th:has-text("生命週期")', state='attached')

            header = page.locator('th:has-text("生命週期")')
            assert header.count() >= 1

            first_row_lifecycle = page.locator('#rp-hist-body tr:not(.rp-detail-row) td').nth(3)
            assert '拒絕' in (first_row_lifecycle.text_content() or '')
            assert page.locator('#rp-hist-body tr:not(.rp-detail-row) td').nth(4).text_content() is not None

            browser.close()
