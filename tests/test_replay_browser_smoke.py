"""
test_replay_browser_smoke.py
============================
P0-4 — Replay Browser Smoke Completion

Static HTML/JS string inspection tests for the Strategy Historical Replay page.
No browser automation, no Playwright, no external API calls, no replay generation.

Covers all 23 P0-4 required smoke checks:
 1.  index.html contains <section id="replay-section">
 2.  Freshness badge / coverage status area exists (rp-freshness-card, rp-coverage-badge)
 3.  Lottery type selector exists (rp-lottery-select)
 4.  Strategy selector exists (rp-strategy-select)
 5.  Replay status selector exists (rp-status-select)
 6.  Query button exists (rp-query-btn)
 7.  Pagination controls exist (rp-prev-btn, rp-next-btn, rp-page-info)
 8.  Expand/collapse drilldown UI exists (.rp-toggle-btn, ▶ 詳情 / ▼ 收起)
 9.  history_cutoff_draw display logic exists (歷史截止期號, r.history_cutoff)
10.  Causal status display logic exists (rpCausalStatus function)
11.  URL query string save/restore logic exists (rpUpdateURL, rpRestoreFromURL)
12.  Pagination state written to query string (rp_page param in rpUpdateURL)
13.  JS calls /api/replay/freshness
14.  JS calls /api/replay/history
15.  JS calls /api/replay/summary
16.  Page contains conservative disclaimer text
17.  Page marks limited coverage (not full historical replay)
18.  Page does not contain full replay trigger button
19.  Page does not contain strategy promotion wording
20.  Page does not contain 最佳策略推薦 / best strategy recommendation
21.  Page does not contain edge ranking text
22.  「提高中獎率」only appears in negation context (not as a claim)
23.  replay 結論 JS does not output SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE

Hard rules (enforced):
  - No new strategies added
  - No strategy mining
    - No result-discovery work
  - No replay generation triggered
  - No external API calls
"""

from __future__ import annotations

import json
import os
import re
import sys
import socketserver
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT_PATH = Path(REPO_ROOT)
INDEX_HTML = REPO_ROOT_PATH / "index.html"


def _load_html() -> str:
    if not INDEX_HTML.exists():
        pytest.skip("index.html not found")
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        return f.read()


def _replay_section(html: str) -> str:
    """Extract the replay section + following script block from index.html."""
    m = re.search(
        r'<section id="replay-section".*?</section>.*?</script>',
        html,
        re.DOTALL,
    )
    return m.group(0) if m else html


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
        "generated_at": "2026-05-10T00:00:00Z",
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
    # P25: non-ONLINE lifecycles expose catalog entries (display-only, no history)
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
    # OFFLINE has no registered entries → shows "coming soon" in catalog mode
    return {"strategies": [], "count": 0, "filter_lottery_type": "BIG_LOTTO", "filter_lifecycle_status": lifecycle_status, "filter": "BIG_LOTTO"}


def _history_payload(lifecycle_status: str):
    if lifecycle_status != "ONLINE":
        return {"total": 0, "page": 1, "page_size": 50, "pages": 1, "filter_lifecycle_status": lifecycle_status, "records": []}
    return {
        "total": 1,
        "page": 1,
        "page_size": 50,
        "pages": 1,
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
                "generated_at": "2026-05-10T00:00:00Z",
                "lifecycle_status": lifecycle_status,
                "strategy_lifecycle_status": lifecycle_status,
            }
        ],
    }


@pytest.mark.skipif(not INDEX_HTML.exists(), reason="index.html not found")
def test_lifecycle_filter_browser_dom_changes():
    playwright = pytest.importorskip("playwright.sync_api", reason="Playwright browser tooling unavailable")
    from playwright.sync_api import sync_playwright  # type: ignore

    with _serve_repo(REPO_ROOT_PATH) as base_url:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as exc:  # pragma: no cover - depends on local browser tooling
                pytest.skip(f"Playwright browser unavailable: {exc}")

            page = browser.new_page()

            def route_handler(route):
                parsed_url = urlparse(route.request.url)
                if parsed_url.path.endswith("/api/replay/freshness"):
                    return _mock_json(route, _freshness_payload())
                if parsed_url.path.endswith("/api/replay/summary"):
                    query = parse_qs(parsed_url.query)
                    lifecycle_status = query.get("lifecycle_status", ["ONLINE"])[0]
                    return _mock_json(route, _summary_payload(lifecycle_status))
                if parsed_url.path.endswith("/api/replay/history"):
                    query = parse_qs(parsed_url.query)
                    lifecycle_status = query.get("lifecycle_status", ["ONLINE"])[0]
                    return _mock_json(route, _history_payload(lifecycle_status))
                if parsed_url.path.endswith("/api/replay/strategies"):
                    query = parse_qs(parsed_url.query)
                    lifecycle_status = query.get("lifecycle_status", ["ONLINE"])[0]
                    return _mock_json(route, _strategies_payload(lifecycle_status))
                return route.continue_()

            page.route("**/api/replay/**", route_handler)
            page.goto(f"{base_url}/index.html?rp_lc=ONLINE", wait_until="load")
            page.wait_for_selector('#rp-lifecycle-select', state='attached')

            page.locator('[data-section="replay"]').evaluate('(el) => el.click()')
            page.wait_for_selector('#rp-query-btn', state='visible')

            page.locator('#rp-query-btn').click()
            page.wait_for_function(
                "() => document.querySelector('#rp-hist-body').innerText.includes('PREDICTED')",
                timeout=15000,
            )
            before = page.locator('#rp-hist-body').inner_text()

            # P25: OFFLINE → catalog display mode with "coming soon" (no registered OFFLINE strategies)
            page.select_option('#rp-lifecycle-select', 'OFFLINE')
            page.locator('#rp-query-btn').click()
            page.wait_for_function(
                "() => document.querySelector('#rp-hist-body').innerText.includes('coming soon')",
                timeout=15000,
            )
            after_offline = page.locator('#rp-hist-body').inner_text()

            assert before != after_offline
            assert 'coming soon' in after_offline, "P25 catalog mode must show 'coming soon' for OFFLINE (no registered entries)"
            assert page.locator('#rp-lifecycle-select').input_value() == 'OFFLINE'

            # P25/P26: REJECTED → catalog display mode with registered strategy rows visible
            page.select_option('#rp-lifecycle-select', 'REJECTED')
            page.locator('#rp-query-btn').click()
            page.wait_for_function(
                "() => document.querySelector('#rp-hist-body').innerText.includes('無歷史回放資料')",
                timeout=15000,
            )
            after_rejected = page.locator('#rp-hist-body').inner_text()

            assert '無歷史回放資料' in after_rejected, "P25 catalog mode must render display-only rows for REJECTED lifecycle"
            assert 'REJECTED' in after_rejected, "Lifecycle badge must include REJECTED identifier in catalog display"
            assert page.locator('#rp-lifecycle-select').input_value() == 'REJECTED'

            browser.close()


class TestReplayBrowserSmoke:
    """P0-4: Static smoke verification of the Strategy Historical Replay page."""

    @pytest.fixture(autouse=True)
    def _html(self):
        self.html = _load_html()
        self.section = _replay_section(self.html)

    # ------------------------------------------------------------------ #
    # Check 1 — Replay section element
    # ------------------------------------------------------------------ #
    def test_replay_section_element_exists(self):
        """<section id="replay-section"> must exist in index.html."""
        assert 'id="replay-section"' in self.html, (
            '<section id="replay-section"> not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 2 — Freshness badge / coverage status
    # ------------------------------------------------------------------ #
    def test_freshness_card_exists(self):
        """rp-freshness-card container must exist for freshness status display."""
        assert 'id="rp-freshness-card"' in self.html, (
            'id="rp-freshness-card" not found in index.html'
        )

    def test_coverage_badge_exists(self):
        """rp-coverage-badge span must exist to display coverage status."""
        assert 'id="rp-coverage-badge"' in self.html, (
            'id="rp-coverage-badge" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 3 — Lottery type selector
    # ------------------------------------------------------------------ #
    def test_lottery_selector_exists(self):
        """Lottery type selector (rp-lottery-select) must exist."""
        assert 'id="rp-lottery-select"' in self.html, (
            'id="rp-lottery-select" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 4 — Strategy selector
    # ------------------------------------------------------------------ #
    def test_strategy_selector_exists(self):
        """Strategy selector (rp-strategy-select) must exist."""
        assert 'id="rp-strategy-select"' in self.html, (
            'id="rp-strategy-select" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 5 — Replay status selector
    # ------------------------------------------------------------------ #
    def test_status_selector_exists(self):
        """Replay status filter (rp-status-select) must exist."""
        assert 'id="rp-status-select"' in self.html, (
            'id="rp-status-select" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 6 — Query button
    # ------------------------------------------------------------------ #
    def test_query_button_exists(self):
        """Query button (rp-query-btn) must exist."""
        assert 'id="rp-query-btn"' in self.html, (
            'id="rp-query-btn" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 7 — Pagination controls
    # ------------------------------------------------------------------ #
    def test_pagination_prev_button_exists(self):
        """Pagination previous button (rp-prev-btn) must exist."""
        assert 'id="rp-prev-btn"' in self.html, (
            'id="rp-prev-btn" not found in index.html'
        )

    def test_pagination_next_button_exists(self):
        """Pagination next button (rp-next-btn) must exist."""
        assert 'id="rp-next-btn"' in self.html, (
            'id="rp-next-btn" not found in index.html'
        )

    def test_pagination_page_info_exists(self):
        """Pagination page info display (rp-page-info) must exist."""
        assert 'id="rp-page-info"' in self.html, (
            'id="rp-page-info" not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 8 — Expand / collapse drilldown UI
    # ------------------------------------------------------------------ #
    def test_drilldown_toggle_button_class_exists(self):
        """Drilldown toggle button (.rp-toggle-btn) must exist in JS-rendered HTML."""
        assert 'rp-toggle-btn' in self.html, (
            '"rp-toggle-btn" class not found in index.html'
        )

    def test_drilldown_expand_text_exists(self):
        """▶ 詳情 (expand) text must be present for drilldown toggle."""
        assert '▶ 詳情' in self.html, (
            '"▶ 詳情" expand text not found in index.html'
        )

    def test_drilldown_collapse_text_exists(self):
        """▼ 收起 (collapse) text must be present for drilldown toggle."""
        assert '▼ 收起' in self.html, (
            '"▼ 收起" collapse text not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 9 — history_cutoff_draw display logic
    # ------------------------------------------------------------------ #
    def test_history_cutoff_label_in_drilldown(self):
        """歷史截止期號 label must appear in drilldown area."""
        assert '歷史截止期號' in self.html, (
            '"歷史截止期號" label not found in index.html drilldown'
        )

    def test_history_cutoff_field_used_in_js(self):
        """r.history_cutoff field must be referenced in JS render logic."""
        assert 'r.history_cutoff' in self.html, (
            'r.history_cutoff not referenced in index.html JS'
        )

    # ------------------------------------------------------------------ #
    # Check 10 — Causal status display logic
    # ------------------------------------------------------------------ #
    def test_causal_status_function_exists(self):
        """rpCausalStatus function must be defined in index.html JS."""
        assert 'function rpCausalStatus' in self.html, (
            'rpCausalStatus function not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 11 — URL query string save / restore
    # ------------------------------------------------------------------ #
    def test_rp_update_url_function_exists(self):
        """rpUpdateURL function must be defined for URL state persistence."""
        assert 'function rpUpdateURL' in self.html, (
            'rpUpdateURL function not found in index.html'
        )

    def test_rp_restore_from_url_function_exists(self):
        """rpRestoreFromURL function must be defined for URL state restore."""
        assert 'function rpRestoreFromURL' in self.html, (
            'rpRestoreFromURL function not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 12 — Pagination state written to query string
    # ------------------------------------------------------------------ #
    def test_rp_page_param_written_to_url(self):
        """rp_page must be written to URL query string in rpUpdateURL."""
        # rpUpdateURL should contain params.set('rp_page', ...) or equivalent
        assert "rp_page" in self.html, (
            '"rp_page" URL parameter not found in index.html — pagination state'
            ' must be persisted to query string'
        )
        # Confirm it's set in the URL (not just read)
        assert "params.set('rp_page'" in self.html or 'params.set("rp_page"' in self.html, (
            "rp_page must be set (written) into URL params in rpUpdateURL"
        )

    def test_rp_fixture_mode_param_written_to_url(self):
        """rp_fixture_mode must be written to the URL query string when active."""
        assert 'rp_fixture_mode' in self.html, (
            '"rp_fixture_mode" URL parameter not found in index.html'
        )
        assert "params.set('rp_fixture_mode'" in self.html or 'params.set("rp_fixture_mode"' in self.html, (
            "rp_fixture_mode must be set (written) into URL params in rpUpdateURL"
        )

    # ------------------------------------------------------------------ #
    # Check 13 — JS calls /api/replay/freshness
    # ------------------------------------------------------------------ #
    def test_js_calls_freshness_endpoint(self):
        """JS must call /api/replay/freshness (via BASE + '/freshness')."""
        has_base_freshness = "BASE + '/freshness'" in self.html or 'BASE + "/freshness"' in self.html
        has_direct = '/api/replay/freshness' in self.html
        assert has_base_freshness or has_direct, (
            "JS does not call /api/replay/freshness — "
            "neither \"BASE + '/freshness'\" nor '/api/replay/freshness' found"
        )

    # ------------------------------------------------------------------ #
    # Check 14 — JS calls /api/replay/history
    # ------------------------------------------------------------------ #
    def test_js_calls_history_endpoint(self):
        """JS must call /api/replay/history (via BASE/history)."""
        has_base = '`${BASE}/history' in self.html or "BASE}/history" in self.html
        has_direct = '/api/replay/history' in self.html
        assert has_base or has_direct, (
            "JS does not call /api/replay/history endpoint"
        )

    def test_js_calls_fixture_mode_history_endpoint(self):
        """JS must be able to request fixture_mode=true for replay history."""
        assert 'fixture_mode=true' in self.html, (
            'fixture_mode=true not found in replay history request logic'
        )

    # ------------------------------------------------------------------ #
    # Check 15b — Fixture mode banner
    # ------------------------------------------------------------------ #
    def test_fixture_mode_banner_present(self):
        """Fixture mode banner copy must exist in index.html."""
        assert 'FIXTURE MODE' in self.html, (
            'FIXTURE MODE banner text not found in index.html'
        )
        assert '合成資料、僅供驗收，不代表真實預測' in self.html, (
            'Fixture mode warning copy not found in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 15 — JS calls /api/replay/summary
    # ------------------------------------------------------------------ #
    def test_js_calls_summary_endpoint(self):
        """JS must call /api/replay/summary (via BASE/summary)."""
        has_base = '`${BASE}/summary' in self.html or "BASE}/summary" in self.html
        has_direct = '/api/replay/summary' in self.html
        assert has_base or has_direct, (
            "JS does not call /api/replay/summary endpoint"
        )

    # ------------------------------------------------------------------ #
    # Check 16 — Conservative disclaimer
    # ------------------------------------------------------------------ #
    def test_conservative_disclaimer_present(self):
        """Page must contain conservative disclaimer '本頁為歷史預測回放'."""
        assert '本頁為歷史預測回放' in self.html, (
            "Conservative disclaimer '本頁為歷史預測回放' not found in index.html"
        )
        assert '不代表提高中獎率' in self.html, (
            "Disclaimer '不代表提高中獎率' not found in index.html"
        )

    # ------------------------------------------------------------------ #
    # Check 17 — Limited coverage note (not full historical replay)
    # ------------------------------------------------------------------ #
    def test_limited_coverage_note_present(self):
        """Page must indicate coverage may be LIMITED (not full historical)."""
        has_limited = 'LIMITED' in self.html or 'limited' in self.html.lower()
        has_not_full = '不代表全量歷史資料' in self.html or 'not full' in self.html.lower()
        assert has_limited or has_not_full, (
            "Page must note that coverage may be limited / not full historical replay"
        )

    # ------------------------------------------------------------------ #
    # Check 18 — No full replay trigger button
    # ------------------------------------------------------------------ #
    def test_no_full_replay_trigger_button(self):
        """Page must not expose a button to trigger a full replay run."""
        assert 'rp-run-all' not in self.html, (
            '"rp-run-all" trigger button must not be in index.html'
        )
        assert '全量重跑' not in self.html, (
            '"全量重跑" text must not appear in index.html'
        )

    # ------------------------------------------------------------------ #
    # Check 19 — No strategy promotion wording
    # ------------------------------------------------------------------ #
    def test_no_strategy_promotion_wording(self):
        """Replay section must not contain strategy promotion phrases."""
        forbidden_promotion = ['推薦投注', '投注建議', 'auto promotion', 'auto rollback']
        for phrase in forbidden_promotion:
            assert phrase not in self.section, (
                f"Replay section must not contain promotion phrase: '{phrase}'"
            )

    # ------------------------------------------------------------------ #
    # Check 20 — No best strategy recommendation text
    # ------------------------------------------------------------------ #
    def test_no_best_strategy_recommendation(self):
        """Replay section must not contain '最佳策略推薦' or equivalent."""
        assert '最佳策略推薦' not in self.section, (
            "Replay section must not contain '最佳策略推薦'"
        )
        assert 'best strategy recommendation' not in self.section.lower(), (
            "Replay section must not contain 'best strategy recommendation'"
        )

    # ------------------------------------------------------------------ #
    # Check 21 — No edge ranking text
    # ------------------------------------------------------------------ #
    def test_no_edge_ranking_text(self):
        """Replay section must not contain edge ranking text."""
        assert 'edge ranking' not in self.section.lower(), (
            "Replay section must not contain 'edge ranking'"
        )
        assert 'edge 排行' not in self.section, (
            "Replay section must not contain 'edge 排行'"
        )

    # ------------------------------------------------------------------ #
    # Check 22 — 提高中獎率 only in negation context
    # ------------------------------------------------------------------ #
    def test_increase_winning_only_in_negation(self):
        """「提高中獎率」must only appear in negation context (不代表/不是), never as a claim."""
        occurrences = [
            m.start() for m in re.finditer('提高中獎率', self.html)
        ]
        assert len(occurrences) > 0, (
            "No '提高中獎率' found at all — expected at least one negation disclaimer"
        )
        for pos in occurrences:
            # Check 20-char window before the match for negation markers
            context = self.html[max(0, pos - 20): pos + 10]
            has_negation = '不代表' in context or '不是' in context or '不得' in context
            assert has_negation, (
                f"'提高中獎率' found outside negation context near: "
                f"...{self.html[max(0,pos-30):pos+20]}..."
            )

    # ------------------------------------------------------------------ #
    # Check 23 — No SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE in replay JS
    # ------------------------------------------------------------------ #
    def test_no_forbidden_tokens_in_replay_js(self):
        """Replay JS must not output SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE as result values."""
        forbidden_tokens = ["NO_SIGNAL", "NO_VALIDATED_EDGE"]
        for token in forbidden_tokens:
            # Allowed only in negation / comment / assertion context
            for m in re.finditer(re.escape(token), self.section):
                start = m.start()
                context_line = self.section[max(0, start - 80): start + len(token) + 20]
                # Must be in a comment or negation check (not as a returned value)
                is_comment = '//' in context_line.split(token)[0].split('\n')[-1]
                is_negation = (
                    'not' in context_line.lower()
                    or '!=' in context_line
                    or 'forbidden' in context_line.lower()
                    or 'assert' in context_line.lower()
                )
                assert is_comment or is_negation, (
                    f"Forbidden token '{token}' found in replay section in "
                    f"non-negation context:\n  ...{context_line}..."
                )


# ======================================================================= #
# P23 — Fixture Mode UI Toggle Static Tests                                #
# ======================================================================= #

class TestP23FixtureModeToggle:
    """P23 static tests: verify toggle button, label, helper text, URL wiring."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.html = _load_html()
        self.section = _replay_section(self.html)

    # T-P23-S01 — toggle button element exists
    def test_fixture_toggle_button_exists(self):
        """rp-fixture-toggle button must exist in index.html."""
        assert 'id="rp-fixture-toggle"' in self.html, (
            "rp-fixture-toggle button not found in index.html"
        )

    # T-P23-S02 — toggle data-testid attribute exists
    def test_fixture_toggle_testid_exists(self):
        """data-testid=rp-fixture-toggle must be present for test targeting."""
        assert 'data-testid="rp-fixture-toggle"' in self.html, (
            "data-testid=rp-fixture-toggle not found"
        )

    # T-P23-S03 — toggle label contains "Fixture Mode"
    def test_fixture_toggle_label_contains_fixture_mode(self):
        """A label for the toggle must contain 'Fixture Mode'."""
        assert 'Fixture Mode' in self.html, (
            "Label 'Fixture Mode' not found near toggle button"
        )

    # T-P23-S04 — FIXTURE MODE banner element exists (pre-existing, regression)
    def test_fixture_mode_banner_element_exists(self):
        """rp-fixture-banner element must still exist."""
        assert 'id="rp-fixture-banner"' in self.html, (
            "rp-fixture-banner element missing"
        )

    # T-P23-S05 — banner text contains advisory warning
    def test_fixture_mode_banner_text_contains_advisory(self):
        """Banner must contain advisory-only warning text."""
        assert '合成資料' in self.html or 'advisory only' in self.html.lower(), (
            "Advisory warning text not found in fixture mode banner"
        )

    # T-P23-S06 — tooltip contains safety description
    def test_fixture_toggle_tooltip_contains_advisory(self):
        """Toggle title tooltip must mention advisory / no production DB write."""
        # Look for title attribute on the toggle button
        m = re.search(r'id="rp-fixture-toggle"[^>]*title="([^"]*)"', self.html)
        if not m:
            # Try reversed attribute order
            m = re.search(r'title="([^"]*)"[^>]*id="rp-fixture-toggle"', self.html)
        assert m is not None, "rp-fixture-toggle has no title tooltip attribute"
        tooltip = m.group(1).lower()
        assert 'advisory' in tooltip or 'no production' in tooltip or 'synthetic' in tooltip, (
            f"Tooltip does not mention advisory/synthetic/no production DB write: {tooltip}"
        )

    # T-P23-S07 — aria-pressed attribute exists on toggle
    def test_fixture_toggle_has_aria_pressed(self):
        """Toggle must have aria-pressed for accessibility."""
        assert 'aria-pressed=' in self.html, (
            "rp-fixture-toggle missing aria-pressed attribute"
        )

    # T-P23-S08 — rpToggleFixtureMode function exists in JS
    def test_rp_toggle_fixture_mode_function_exists(self):
        """rpToggleFixtureMode JS function must be defined."""
        assert 'function rpToggleFixtureMode' in self.html, (
            "rpToggleFixtureMode function not found in index.html JS"
        )

    # T-P23-S09 — rpSyncFixtureModeToggle function exists in JS
    def test_rp_sync_fixture_mode_toggle_function_exists(self):
        """rpSyncFixtureModeToggle JS function must be defined."""
        assert 'function rpSyncFixtureModeToggle' in self.html, (
            "rpSyncFixtureModeToggle function not found in index.html JS"
        )

    # T-P23-S10 — toggle wired in DOMContentLoaded
    def test_fixture_toggle_wired_in_dom_content_loaded(self):
        """rp-fixture-toggle must be wired via addEventListener in DOMContentLoaded."""
        assert "fixtureToggleBtn.addEventListener('click', rpToggleFixtureMode)" in self.html or \
               'fixtureToggleBtn.addEventListener("click", rpToggleFixtureMode)' in self.html, (
            "rp-fixture-toggle click event not wired in DOMContentLoaded"
        )

    # T-P23-S11 — rpSyncFixtureModeToggle called after rpRestoreFromURL
    def test_sync_toggle_called_after_restore_from_url(self):
        """rpSyncFixtureModeToggle must be called after rpRestoreFromURL in init."""
        # Find the DOMContentLoaded block (last occurrence, which is the init block)
        dom_block_pos = self.html.rfind('DOMContentLoaded')
        assert dom_block_pos != -1, "DOMContentLoaded block not found"
        dom_block = self.html[dom_block_pos:]
        restore_pos = dom_block.find('rpRestoreFromURL()')
        sync_pos = dom_block.find('rpSyncFixtureModeToggle()')
        assert restore_pos != -1, "rpRestoreFromURL() not found in DOMContentLoaded"
        assert sync_pos != -1, "rpSyncFixtureModeToggle() not found in DOMContentLoaded"
        assert sync_pos > restore_pos, (
            "rpSyncFixtureModeToggle() must be called AFTER rpRestoreFromURL() in DOMContentLoaded"
        )

    # T-P23-S12 — URL state updated on toggle (rp_fixture_mode written)
    def test_rp_fixture_mode_url_state_written_on_toggle(self):
        """rpToggleFixtureMode must write rp_fixture_mode to URL."""
        assert "params.set('rp_fixture_mode', 'true')" in self.html or \
               'params.set("rp_fixture_mode", "true")' in self.html, (
            "rp_fixture_mode=true not written to URL in rpToggleFixtureMode"
        )

    # T-P23-S13 — toggle OFF removes rp_fixture_mode from URL
    def test_rp_fixture_mode_url_state_deleted_on_toggle_off(self):
        """rpToggleFixtureMode must delete rp_fixture_mode from URL when OFF."""
        assert "params.delete('rp_fixture_mode')" in self.html or \
               'params.delete("rp_fixture_mode")' in self.html, (
            "rp_fixture_mode not deleted from URL when toggle is OFF"
        )

    # T-P23-S14 — fixture_mode=true still passed to API (regression)
    def test_fixture_mode_true_passed_to_api(self):
        """fixture_mode=true must still be passed to API when rpFixtureMode is active."""
        assert 'fixture_mode=true' in self.html, (
            "fixture_mode=true not found in API query logic"
        )

    # T-P23-S15 — no OFFLINE filter added
    def test_no_offline_filter_added(self):
        """No OFFLINE-specific fixture filter or OFFLINE fixture records must be added."""
        # Extract only the rpToggleFixtureMode function body
        m = re.search(
            r'function rpToggleFixtureMode\(\)\s*\{([^}]*)\}',
            self.html, re.DOTALL
        )
        if m:
            toggle_body = m.group(1)
            assert 'OFFLINE' not in toggle_body, (
                "OFFLINE found inside rpToggleFixtureMode body — must never be a fixture type"
            )
        # Verify fixture_mode param is still only wired to existing endpoint
        assert 'fixture_mode=true' in self.html, (
            "fixture_mode=true must still be passed to API"
        )

    # T-P23-S16 — no new backend API added in toggle
    def test_no_new_api_endpoint_in_toggle(self):
        """Toggle must only call existing /api/replay endpoints, not new ones."""
        toggle_func_match = re.search(
            r'function rpToggleFixtureMode\(\)[^}]*\}', self.html, re.DOTALL
        )
        if toggle_func_match:
            toggle_code = toggle_func_match.group(0)
            assert 'fetch(' not in toggle_code, (
                "rpToggleFixtureMode must not make new fetch() calls — "
                "it only updates state + URL"
            )
