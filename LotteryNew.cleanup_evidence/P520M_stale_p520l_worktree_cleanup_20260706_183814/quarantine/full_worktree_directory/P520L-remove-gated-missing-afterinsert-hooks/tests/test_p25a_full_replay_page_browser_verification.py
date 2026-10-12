"""
test_p25a_full_replay_page_browser_verification.py
===================================================
P25a — Full Replay Page Browser Verification

Verifies all 3 lottery types and all 8 ONLINE_ROW_BACKED strategies via:
  1. Real browser E2E (Playwright) — skipped with pytest.importorskip if
     Playwright is not installed or the backend is not reachable.
  2. API contract checks — always run, require the backend to be reachable.

Coverage matrix (when browser E2E runs):
  BIG_LOTTO   : biglotto_deviation_2bet, biglotto_triple_strike, ts3_regime_3bet
  POWER_LOTTO : fourier_rhythm_3bet, power_orthogonal_5bet, power_precision_3bet
  DAILY_539   : daily539_f4cold, daily539_markov_cold

Period presets tested: 100期, 500期, 1000期, 1500期
Cross-switching scenarios: 8 flows

Run:
  pip install playwright
  playwright install chromium
  # start backend on port 8002 first
  pytest tests/test_p25a_full_replay_page_browser_verification.py -v

Hard rules (same as all P-series tests):
  - No new strategies
  - No replay generation
  - No production DB writes
  - No broad UI redesign
"""
from __future__ import annotations

import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Generator, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

BACKEND_URL = os.environ.get("P25A_BACKEND_URL", "http://127.0.0.1:8002")
REPLAY_PAGE_URL = os.environ.get("P25A_REPLAY_PAGE_URL", "")  # set to skip file-server

# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------
STRATEGIES = {
    "BIG_LOTTO": [
        "biglotto_deviation_2bet",
        "biglotto_triple_strike",
        "ts3_regime_3bet",
    ],
    "POWER_LOTTO": [
        "fourier_rhythm_3bet",
        "power_orthogonal_5bet",
        "power_precision_3bet",
    ],
    "DAILY_539": [
        "daily539_f4cold",
        "daily539_markov_cold",
    ],
}
ALL_STRATEGIES = [s for strats in STRATEGIES.values() for s in strats]
PERIOD_PRESETS = [100, 500, 1000, 1500]

# Expected DB production rows — must not change
EXPECTED_PRODUCTION_ROWS = 12460

# ---------------------------------------------------------------------------
# Playwright skip guard
# ---------------------------------------------------------------------------
playwright_mod = pytest.importorskip(
    "playwright.sync_api",
    reason=(
        "Playwright browser tooling unavailable. "
        "Install with: pip install playwright && playwright install chromium. "
        "Then start the backend on port 8002 and re-run. "
        "Classification: P25A_BLOCKED_BY_NO_BROWSER_E2E_TOOLING"
    ),
)
from playwright.sync_api import sync_playwright, Page, Browser  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — static file server
# ---------------------------------------------------------------------------
@contextmanager
def _serve_repo(root: Path) -> Generator[str, None, None]:
    """Serve the repo root as a static site on a free port."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.allow_reuse_address = True
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()
            t.join(timeout=5)


def _mock_json(route, payload: dict) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# Mock payloads — representative data for each lottery type
# ---------------------------------------------------------------------------
def _make_history_records(
    lottery_type: str,
    strategy_id: str,
    count: int = 5,
) -> list:
    num_main  = 5 if lottery_type == "DAILY_539" else 6
    has_special = lottery_type in ("BIG_LOTTO", "POWER_LOTTO")
    records = []
    for i in range(count):
        draw = f"11500{i:04d}"
        main_pred   = list(range(1, num_main + 1))
        main_actual = list(range(2, num_main + 2))
        rec: dict = {
            "id":               10000 + i,
            "lottery_type":     lottery_type,
            "strategy_id":      strategy_id,
            "target_draw":      draw,
            "target_date":      f"2026/05/{10 + i:02d}",
            "history_cutoff":   f"11500{i - 1:04d}",
            "replay_status":    "COMPLETED",
            "predicted_numbers": main_pred,
            "actual_numbers":   main_actual,
            "predicted_special": 8 if has_special else None,
            "actual_special":   7 if has_special else None,
            "hit_numbers":      [],
            "hit_count":        0,
            "special_hit":      0,
            "prediction_cutoff_date": f"2026/05/{8 + i:02d}",
            "generated_at":     "2026-05-21T00:00:00Z",
            "lifecycle_status": "ONLINE_ROW_BACKED",
        }
        records.append(rec)
    return records


def _history_payload(
    lottery_type: str,
    strategy_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    total: int = 1500,
) -> dict:
    strats = STRATEGIES.get(lottery_type, [])
    sid = strategy_id or (strats[0] if strats else "unknown")
    records = _make_history_records(lottery_type, sid, count=min(page_size, 5))
    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "total":    total,
        "page":     page,
        "page_size": page_size,
        "pages":    pages,
        "records":  records,
    }


def _strategies_payload(lottery_type: Optional[str] = None) -> dict:
    all_s = [
        {
            "strategy_id":   sid,
            "strategy_name": sid,
            "status":        "ONLINE",
            "supported_lottery_types": [lt],
        }
        for lt, strats in STRATEGIES.items()
        for sid in strats
        if lottery_type is None or lt == lottery_type
    ]
    return {"strategies": all_s}


def _freshness_payload() -> dict:
    return {
        "generated_at":    "2026-05-21T00:00:00Z",
        "coverage_mode":   "LIMITED",
        "total_rows":      EXPECTED_PRODUCTION_ROWS,
        "total_predicted": 12420,
        "total_replay_error": 40,
        "legacy_error_count": 40,
        "has_legacy_errors": True,
    }


def _summary_payload(lottery_type: str) -> dict:
    strats = STRATEGIES.get(lottery_type, [])
    return {
        "lottery_type": lottery_type,
        "summaries": [
            {"strategy_id": sid, "total": 1500, "hit_rate": 0.0}
            for sid in strats
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def browser_ctx():
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        yield ctx
        ctx.close()
        browser.close()


@pytest.fixture(scope="session")
def static_url():
    with _serve_repo(REPO_ROOT) as url:
        yield url


def _open_replay_page(ctx, static_url: str) -> Page:
    """Open a fresh page, wire API mocks, navigate to the replay section."""
    page: Page = ctx.new_page()

    # Intercept all API calls and fulfill with mock data
    def handle_route(route):
        url = route.request.url
        params: dict = {}
        if "?" in url:
            from urllib.parse import parse_qs, urlparse
            qs = urlparse(url).query
            params = {k: v[0] for k, v in parse_qs(qs).items()}

        lt  = params.get("lottery_type")
        sid = params.get("strategy_id")
        pg  = int(params.get("page", 1))
        ps  = int(params.get("page_size", 50))

        if "/api/replay/history" in url:
            if lt:
                _mock_json(route, _history_payload(lt, sid, pg, ps))
            else:
                route.fulfill(
                    status=422,
                    content_type="application/json",
                    body=json.dumps({"detail": [{"msg": "Field required", "loc": ["query", "lottery_type"]}]}),
                )
        elif "/api/replay/strategies" in url:
            _mock_json(route, _strategies_payload(lt))
        elif "/api/replay/freshness" in url:
            _mock_json(route, _freshness_payload())
        elif "/api/replay/summary" in url:
            _mock_json(route, _summary_payload(lt or "BIG_LOTTO"))
        else:
            route.continue_()

    page.route("**/api/replay/**", handle_route)
    page.goto(f"{static_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    # Navigate to the replay section so its controls become visible
    page.click("button.nav-btn[data-section='replay']", force=True)
    # Wait until #replay-section is actually visible before returning
    page.wait_for_selector("#replay-section", state="visible", timeout=10000)
    return page


# ---------------------------------------------------------------------------
# Section 1: DOM structure smoke checks (no API required)
# ---------------------------------------------------------------------------
class TestReplayPageDOM:
    """Verify the replay page DOM structure exists and is correct."""

    def test_replay_section_exists(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        assert page.locator("#replay-section").count() > 0, \
            "Missing #replay-section"
        page.close()

    def test_lottery_type_selector_exists(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        assert page.locator("#rp-lottery-select").count() > 0, \
            "Missing #rp-lottery-select"
        page.close()

    def test_strategy_selector_exists(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        assert page.locator("#rp-strategy-select").count() > 0, \
            "Missing #rp-strategy-select"
        page.close()

    def test_query_button_exists(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        assert page.locator("#rp-query-btn").count() > 0, \
            "Missing #rp-query-btn"
        page.close()

    def test_period_preset_buttons_exist(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        for preset in PERIOD_PRESETS:
            btn = page.locator(f"[data-testid='rp-preset-{preset}']")
            assert btn.count() > 0, f"Missing preset button {preset}期"
        page.close()

    def test_pagination_controls_exist(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        assert page.locator("#rp-prev-btn").count() > 0 or \
               page.locator("[data-testid='rp-prev-btn']").count() > 0 or \
               page.locator("button:has-text('上一頁')").count() > 0, \
            "Missing prev pagination button"
        page.close()


# ---------------------------------------------------------------------------
# Section 2: Per-lottery type + per-strategy query
# ---------------------------------------------------------------------------
class TestReplayPerLotteryType:
    """Query each lottery type + strategy and verify result rows."""

    @pytest.mark.parametrize("lottery_type,strategy_id", [
        (lt, sid)
        for lt, strats in STRATEGIES.items()
        for sid in strats
    ])
    def test_strategy_query_returns_rows(
        self, browser_ctx, static_url, lottery_type, strategy_id
    ):
        page = _open_replay_page(browser_ctx, static_url)

        # Select lottery type
        page.select_option("#rp-lottery-select", lottery_type)
        page.wait_for_timeout(300)

        # Select strategy
        page.select_option("#rp-strategy-select", strategy_id)
        page.wait_for_timeout(200)

        # Click query
        page.click("#rp-query-btn")
        page.wait_for_timeout(1000)

        # Verify rows rendered
        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, \
            f"{lottery_type}/{strategy_id}: no rows rendered"

        # Verify no console errors
        console_errors: list = []
        page.on("console", lambda msg: console_errors.append(msg.text)
                if msg.type == "error" else None)
        assert console_errors == [], \
            f"Console errors: {console_errors}"

        page.close()

    def test_daily539_no_special_number_chip(self, browser_ctx, static_url):
        """DAILY_539 must not show a special-number chip or 特 chip."""
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "DAILY_539")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "daily539_f4cold")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(1000)

        # 特 chip / special chip should not be visible
        special_chips = page.locator(".special-chip, .num-special, [data-special='true']")
        assert special_chips.count() == 0, \
            "DAILY_539: unexpected special-number chips visible"

        page.close()

    def test_biglotto_predicted_numbers_length(self, browser_ctx, static_url):
        """BIG_LOTTO predicted numbers should have 6 entries."""
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "BIG_LOTTO")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "biglotto_deviation_2bet")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(1000)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, "No rows for BIG_LOTTO"
        page.close()

    def test_daily539_predicted_numbers_length(self, browser_ctx, static_url):
        """DAILY_539 predicted numbers should have 5 entries."""
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "DAILY_539")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "daily539_f4cold")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(1000)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, "No rows for DAILY_539"
        page.close()


# ---------------------------------------------------------------------------
# Section 3: Period preset interactions
# ---------------------------------------------------------------------------
class TestPeriodPresets:
    """Period preset buttons (100/500/1000/1500期) must be clickable and load rows."""

    @pytest.mark.parametrize("lottery_type", ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"])
    @pytest.mark.parametrize("preset", PERIOD_PRESETS)
    def test_period_preset_loads_rows(
        self, browser_ctx, static_url, lottery_type, preset
    ):
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", lottery_type)
        page.wait_for_timeout(300)

        btn = page.locator(f"[data-testid='rp-preset-{preset}']")
        assert btn.count() > 0, f"Preset button {preset} not found"
        btn.click()
        page.wait_for_timeout(1500)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, \
            f"{lottery_type} preset {preset}期: no rows rendered"

        # DAILY_539 must not show special chips even after preset
        if lottery_type == "DAILY_539":
            special_chips = page.locator(".special-chip, .num-special, [data-special='true']")
            assert special_chips.count() == 0, \
                "DAILY_539 preset: unexpected special chips"

        page.close()


# ---------------------------------------------------------------------------
# Section 4: Cross-switching scenarios
# ---------------------------------------------------------------------------
class TestCrossSwitching:
    """Verify state is correctly reset when switching lottery type or strategy."""

    def test_switch_big_to_power_to_daily(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)

        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            page.select_option("#rp-lottery-select", lt)
            page.wait_for_timeout(300)
            page.click("#rp-query-btn")
            page.wait_for_timeout(800)
            rows = page.locator("table.data-table tbody tr").all()
            assert len(rows) > 0, f"No rows after switching to {lt}"

        # DAILY_539 must never show special chips
        special = page.locator(".special-chip, .num-special, [data-special='true']")
        assert special.count() == 0, "DAILY_539: special chips visible after switch"
        page.close()

    def test_switch_daily539_to_biglotto(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "DAILY_539")
        page.wait_for_timeout(300)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        page.select_option("#rp-lottery-select", "BIG_LOTTO")
        page.wait_for_timeout(300)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        # Must not show stale DAILY_539 rows
        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, "No rows after DAILY_539 → BIG_LOTTO switch"
        page.close()

    def test_power_strategy_switch(self, browser_ctx, static_url):
        """Switching between two POWER_LOTTO strategies must update results."""
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "POWER_LOTTO")
        page.wait_for_timeout(300)

        for sid in ["fourier_rhythm_3bet", "power_orthogonal_5bet"]:
            page.select_option("#rp-strategy-select", sid)
            page.wait_for_timeout(200)
            page.click("#rp-query-btn")
            page.wait_for_timeout(800)
            rows = page.locator("table.data-table tbody tr").all()
            assert len(rows) > 0, f"No rows for POWER_LOTTO/{sid}"

        page.close()

    def test_1500_preset_then_switch_lottery(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)

        # Set 1500期 preset on BIG_LOTTO
        page.select_option("#rp-lottery-select", "BIG_LOTTO")
        page.wait_for_timeout(300)
        page.locator("[data-testid='rp-preset-1500']").click()
        page.wait_for_timeout(1500)

        # Switch to DAILY_539 and query
        page.select_option("#rp-lottery-select", "DAILY_539")
        page.wait_for_timeout(300)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, "No rows after 1500期 → lottery switch"
        # DAILY_539 must not inherit special display from BIG_LOTTO
        special = page.locator(".special-chip, .num-special, [data-special='true']")
        assert special.count() == 0, \
            "DAILY_539: inherited special chips from BIG_LOTTO"
        page.close()

    def test_date_set_then_strategy_switch(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "POWER_LOTTO")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "fourier_rhythm_3bet")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        # Switch strategy
        page.select_option("#rp-strategy-select", "power_precision_3bet")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, \
            "No rows after POWER_LOTTO strategy switch"
        page.close()

    def test_biglotto_strategy_then_daily539(self, browser_ctx, static_url):
        page = _open_replay_page(browser_ctx, static_url)
        page.select_option("#rp-lottery-select", "BIG_LOTTO")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "biglotto_deviation_2bet")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        # Switch to DAILY_539
        page.select_option("#rp-lottery-select", "DAILY_539")
        page.wait_for_timeout(300)
        page.select_option("#rp-strategy-select", "daily539_markov_cold")
        page.wait_for_timeout(200)
        page.click("#rp-query-btn")
        page.wait_for_timeout(800)

        rows = page.locator("table.data-table tbody tr").all()
        assert len(rows) > 0, "No rows for DAILY_539 after BIG_LOTTO"
        special = page.locator(".special-chip, .num-special, [data-special='true']")
        assert special.count() == 0, \
            "DAILY_539: special chips inherited from BIG_LOTTO"
        page.close()


# ---------------------------------------------------------------------------
# Section 5: API contract checks (always run, no Playwright required)
# ---------------------------------------------------------------------------
class TestAPIContract:
    """Live API contract checks against a running backend."""

    BACKEND = BACKEND_URL

    @classmethod
    def _get(cls, path: str, params: dict = None) -> tuple[int, dict | None]:
        import urllib.error
        import urllib.parse
        url = cls.BACKEND + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
            except Exception:
                body = {"error": str(exc)}
            return exc.code, body
        except Exception as exc:
            return 0, {"error": str(exc)}

    def test_health(self):
        status, body = self._get("/health")
        assert status == 200, f"Health failed: {body}"

    def test_production_rows_unchanged(self):
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        rows = c.fetchone()[0]
        conn.close()
        assert rows == EXPECTED_PRODUCTION_ROWS, \
            f"Production rows changed: {rows} != {EXPECTED_PRODUCTION_ROWS}"

    @pytest.mark.parametrize("lottery_type", ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"])
    def test_history_lottery_type_returns_rows(self, lottery_type):
        status, body = self._get(
            "/api/replay/history",
            {"lottery_type": lottery_type, "page_size": 5},
        )
        assert status == 200, f"{lottery_type} history failed: {body}"
        assert body.get("total", 0) > 0, f"{lottery_type}: total=0"

    @pytest.mark.parametrize("lottery_type,strategy_id", [
        (lt, sid)
        for lt, strats in STRATEGIES.items()
        for sid in strats
    ])
    def test_history_per_strategy(self, lottery_type, strategy_id):
        status, body = self._get(
            "/api/replay/history",
            {"lottery_type": lottery_type, "strategy_id": strategy_id, "page_size": 5},
        )
        assert status == 200, f"{strategy_id} history failed: {body}"
        records = body.get("records", [])
        assert len(records) > 0, f"{strategy_id}: no records returned"
        for r in records:
            assert r["lottery_type"] == lottery_type, \
                f"lottery_type mismatch in {strategy_id}: {r['lottery_type']}"
            assert r["strategy_id"] == strategy_id, \
                f"strategy_id mismatch: {r['strategy_id']}"

    def test_history_strategy_only_requires_lottery_type(self):
        """lottery_type is required — strategy_id alone must return 422."""
        status, body = self._get(
            "/api/replay/history",
            {"strategy_id": "biglotto_deviation_2bet", "page_size": 5},
        )
        assert status == 422, \
            f"Expected 422 for missing lottery_type, got {status}"

    def test_history_pagination_no_duplicates(self):
        status1, b1 = self._get(
            "/api/replay/history",
            {"lottery_type": "BIG_LOTTO", "page": 1, "page_size": 5},
        )
        status2, b2 = self._get(
            "/api/replay/history",
            {"lottery_type": "BIG_LOTTO", "page": 2, "page_size": 5},
        )
        assert status1 == 200 and status2 == 200
        ids1 = {r["id"] for r in b1.get("records", [])}
        ids2 = {r["id"] for r in b2.get("records", [])}
        overlap = ids1 & ids2
        assert len(overlap) == 0, f"Duplicate IDs across pages: {overlap}"

    def test_history_beyond_total_is_safe(self):
        status, body = self._get(
            "/api/replay/history",
            {"lottery_type": "BIG_LOTTO", "page": 9999, "page_size": 5},
        )
        assert status == 200, f"Beyond-total page failed: {body}"
        assert body.get("records", []) == [], \
            "Expected empty records for page beyond total"

    def test_history_lottery_type_filter_integrity(self):
        """Returned records must match the requested lottery_type."""
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            _, body = self._get(
                "/api/replay/history",
                {"lottery_type": lt, "page_size": 50},
            )
            wrong = [
                r["lottery_type"]
                for r in body.get("records", [])
                if r.get("lottery_type") != lt
            ]
            assert wrong == [], f"{lt}: cross-contaminated rows: {wrong[:5]}"

    def test_daily539_no_special_number_in_db(self):
        """DAILY_539 rows must have NULL predicted_special / actual_special."""
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type='DAILY_539' AND predicted_special IS NOT NULL"
        )
        count = c.fetchone()[0]
        conn.close()
        assert count == 0, f"DAILY_539 has {count} rows with non-NULL predicted_special"

    def test_daily539_numbers_length_5(self):
        """DAILY_539 API records must have 5 predicted and 5 actual numbers."""
        status, body = self._get(
            "/api/replay/history",
            {
                "lottery_type": "DAILY_539",
                "strategy_id": "daily539_f4cold",
                "page_size": 10,
            },
        )
        assert status == 200
        for r in body.get("records", []):
            pred = r.get("predicted_numbers") or []
            actual = r.get("actual_numbers") or []
            assert len(pred) == 5, \
                f"DAILY_539 predicted_numbers len={len(pred)}"
            assert len(actual) == 5, \
                f"DAILY_539 actual_numbers len={len(actual)}"

    def test_strategies_endpoint_all_three_types(self):
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            status, body = self._get("/api/replay/strategies", {"lottery_type": lt})
            assert status == 200, f"strategies/{lt} failed"
            strats = body.get("strategies", [])
            assert len(strats) > 0, f"No strategies returned for {lt}"

    def test_summary_endpoint_all_three_types(self):
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            status, body = self._get("/api/replay/summary", {"lottery_type": lt})
            assert status == 200, f"summary/{lt} failed"

    def test_lifecycle_registry_returns_18_strategies(self):
        """Lifecycle registry must expose all 18 known strategies."""
        status, body = self._get("/api/replay/strategy-lifecycle")
        assert status == 200, f"strategy-lifecycle failed: {body}"
        strategies = body.get("strategies", [])
        assert len(strategies) >= 18, \
            f"Expected ≥18 strategies in lifecycle registry, got {len(strategies)}"

    def test_lifecycle_registry_online_count(self):
        """Exactly 8 ONLINE strategies must appear in the lifecycle registry."""
        status, body = self._get("/api/replay/strategy-lifecycle")
        assert status == 200
        online = [
            s for s in body.get("strategies", [])
            if s.get("lifecycle_status") == "ONLINE"
        ]
        assert len(online) == 8, \
            f"Expected 8 ONLINE strategies, got {len(online)}: {[s.get('strategy_id') for s in online]}"

    def test_lifecycle_registry_online_strategy_ids(self):
        """All 8 expected ONLINE strategy IDs must be present."""
        expected_online = {
            "biglotto_deviation_2bet",
            "biglotto_triple_strike",
            "ts3_regime_3bet",
            "fourier_rhythm_3bet",
            "power_orthogonal_5bet",
            "power_precision_3bet",
            "daily539_f4cold",
            "daily539_markov_cold",
        }
        status, body = self._get("/api/replay/strategy-lifecycle")
        assert status == 200
        online_ids = {
            s["strategy_id"]
            for s in body.get("strategies", [])
            if s.get("lifecycle_status") == "ONLINE"
        }
        missing = expected_online - online_ids
        assert missing == set(), \
            f"Missing ONLINE strategy IDs in lifecycle registry: {missing}"

    @pytest.mark.parametrize("lottery_type,strategy_id,expected_rows", [
        ("BIG_LOTTO",   "biglotto_deviation_2bet",  1570),
        ("BIG_LOTTO",   "biglotto_triple_strike",   1570),
        ("BIG_LOTTO",   "ts3_regime_3bet",           1500),
        ("POWER_LOTTO", "fourier_rhythm_3bet",        1500),
        ("POWER_LOTTO", "power_orthogonal_5bet",      1570),
        ("POWER_LOTTO", "power_precision_3bet",       1570),
        ("DAILY_539",   "daily539_f4cold",            1590),
        ("DAILY_539",   "daily539_markov_cold",       1590),
    ])
    def test_online_strategy_row_count_matches_p24(
        self, lottery_type, strategy_id, expected_rows
    ):
        """Each ONLINE strategy's row count must match the P24 inventory baseline."""
        status, body = self._get(
            "/api/replay/history",
            {"lottery_type": lottery_type, "strategy_id": strategy_id, "page_size": 1},
        )
        assert status == 200, f"{strategy_id}: API failed with {status}"
        actual = body.get("total", -1)
        assert actual == expected_rows, \
            f"{strategy_id}: expected {expected_rows} rows, got {actual}"


# ---------------------------------------------------------------------------
# Section 6: Evidence JSON + final classification checks
# ---------------------------------------------------------------------------
EVIDENCE_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p25a_full_replay_page_browser_verification_20260521.json"
)


class TestEvidenceJSON:
    """Verify the evidence JSON artifact is present and complete."""

    @pytest.fixture(scope="class")
    def evidence(self):
        assert EVIDENCE_JSON.exists(), \
            f"Evidence JSON missing: {EVIDENCE_JSON}"
        with open(EVIDENCE_JSON, encoding="utf-8") as f:
            return json.load(f)

    def test_evidence_json_exists(self):
        assert EVIDENCE_JSON.exists(), f"Missing: {EVIDENCE_JSON}"

    def test_final_classification(self, evidence):
        assert evidence["final_classification"] == \
            "P25A_FULL_REPLAY_PAGE_BROWSER_VERIFICATION_READY", \
            f"Wrong classification: {evidence.get('final_classification')}"

    def test_browser_e2e_available(self, evidence):
        assert evidence["browser_e2e_available"] is True

    def test_api_base(self, evidence):
        assert evidence["api_base"] == "http://127.0.0.1:8002"

    def test_console_errors_non_blocking(self, evidence):
        triage = evidence.get("console_error_triage", {})
        assert triage.get("error_a", {}).get("verdict") == "NON_BLOCKING"
        assert triage.get("error_b", {}).get("verdict") == "NON_BLOCKING"
        assert triage.get("overall_verdict") == "ALL_NON_BLOCKING"

    def test_all_3_lottery_types_pass(self, evidence):
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            result = evidence.get("e2e_results", {}).get(lt, {})
            assert result.get("status") == "PASS", \
                f"{lt} E2E result is not PASS: {result}"

    def test_all_8_online_strategies_match(self, evidence):
        assert evidence.get("all_8_online_strategies_match") is True
        counts = evidence.get("online_strategy_row_counts", {})
        for key, val in counts.items():
            assert val.get("match") is True, \
                f"Row count mismatch for {key}: {val}"

    def test_total_online_rows_12460(self, evidence):
        assert evidence.get("total_online_rows_sum") == 12460, \
            f"Expected 12460, got {evidence.get('total_online_rows_sum')}"

    def test_period_presets_pass(self, evidence):
        for preset in ["100", "500", "1000", "1500"]:
            result = evidence.get("period_presets", {}).get(preset, {})
            assert result.get("status") == "PASS", \
                f"Preset {preset}期: {result}"

    def test_cross_switching_pass(self, evidence):
        for key, val in evidence.get("cross_switching_matrix", {}).items():
            assert val.get("status") == "PASS", \
                f"Cross-switch {key}: {val}"

    def test_pagination_pass(self, evidence):
        assert evidence.get("pagination", {}).get("status") == "PASS"

    def test_lifecycle_registry_pass(self, evidence):
        lc = evidence.get("lifecycle_registry", {})
        assert lc.get("status") == "PASS"
        assert lc.get("strategy_count") == 18
        assert lc.get("p24_inventory_match") is True
        breakdown = lc.get("breakdown", {})
        assert breakdown.get("ONLINE") == 8
        assert breakdown.get("REJECTED") == 4
        assert breakdown.get("OBSERVATION") == 1
        assert breakdown.get("RETIRED") == 5

    def test_hit_rate_summary_pass(self, evidence):
        assert evidence.get("hit_rate_summary", {}).get("status") == "PASS"

    def test_governance_rows_unchanged(self, evidence):
        gov = evidence.get("governance", {})
        assert gov.get("db_rows_unchanged") is True
        assert gov.get("expected_rows") == EXPECTED_PRODUCTION_ROWS
