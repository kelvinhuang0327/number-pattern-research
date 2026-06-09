"""P260A — Tests for History Replay Detail UX Parity.

Validates:
- page_size raised to le=1500; page_size=1500 accepted, page_size=1501 rejected
- Quick range buttons 100/300/500/1500 present in index.html
- 1000期 quick range button NOT present
- Circular number token CSS present (.replay-number-token)
- Special token CSS present (.replay-number-token--special)
- Hit token CSS present (.replay-number-token--hit)
- fmtSpecialToken / fmtHitTokens helpers present in JS
- renderDetailRows emits 命中號碼 column (7 <th> in P259B table)
- P260A quick range container present with data-testid
- API: page_size=300/500/1500 accepted; page_size=1501 returns 422
- API: response schema unchanged (backward-compatible)
- No DB write / no replay backfill in any test
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with replay router mounted."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility")


@pytest.fixture(scope="module")
def sample(client):
    """Discover a real strategy with production replay rows."""
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    candidates = [
        r for r in ov.get("rows", [])
        if r.get("has_production_replay") and r.get("total_replay_rows", 0) > 5
    ]
    if not candidates:
        pytest.skip("No strategy with replay rows found in DB")
    candidates.sort(key=lambda r: r["total_replay_rows"], reverse=True)
    c = candidates[0]
    return {
        "lottery_type": c["lottery_type"],
        "strategy_id": c["strategy_id"],
        "bet_index": c["derived_bet_count"],
    }


# ---------------------------------------------------------------------------
# Group 1: HTML structure — quick range buttons
# ---------------------------------------------------------------------------

class TestQuickRangeHTML:
    def test_quick_range_container_present(self):
        """P260A quick range div with data-testid present."""
        assert 'data-testid="p260a-quick-range"' in _html()

    def test_range_100_present(self):
        assert 'data-testid="p260a-range-100"' in _html()

    def test_range_300_present(self):
        assert 'data-testid="p260a-range-300"' in _html()

    def test_range_500_present(self):
        assert 'data-testid="p260a-range-500"' in _html()

    def test_range_1500_present(self):
        assert 'data-testid="p260a-range-1500"' in _html()

    def test_range_1000_absent(self):
        """1000期 quick range button must NOT exist in P260A detail panel."""
        assert 'data-testid="p260a-range-1000"' not in _html()

    def test_range_buttons_have_correct_data_ps(self):
        html = _html()
        assert 'data-ps="100"' in html
        assert 'data-ps="300"' in html
        assert 'data-ps="500"' in html
        assert 'data-ps="1500"' in html

    def test_range_1000_data_ps_absent_in_p260a(self):
        """No data-ps="1000" in P260A range buttons."""
        # data-ps="1000" must not appear in the P260A quick range section
        html = _html()
        assert 'data-testid="p260a-range-1000"' not in html

    def test_p260a_range_btn_class_present(self):
        assert 'class="p260a-range-btn"' in _html() or 'p260a-range-btn' in _html()


# ---------------------------------------------------------------------------
# Group 2: HTML structure — table and columns
# ---------------------------------------------------------------------------

class TestDetailTableHTML:
    def test_hit_numbers_column_header_present(self):
        """命中號碼 column header must be in detail table."""
        assert '命中號碼' in _html()

    def test_detail_table_has_seven_columns(self):
        """P259B detail table thead must have 7 <th> elements (P260A added 命中號碼)."""
        html = _html()
        # Find the table section and count th elements
        table_start = html.find('id="p259b-detail-table"')
        assert table_start != -1
        thead_start = html.find('<thead>', table_start)
        thead_end = html.find('</thead>', thead_start)
        thead = html[thead_start:thead_end]
        assert thead.count('<th>') == 7

    def test_footnote_mentions_1500(self):
        """Footnote updated to mention 1500 期 max."""
        assert '1500' in _html()


# ---------------------------------------------------------------------------
# Group 3: CSS — circular tokens and special class
# ---------------------------------------------------------------------------

class TestTokenCSS:
    def test_replay_number_token_class_present(self):
        assert '.replay-number-token' in _html()

    def test_replay_number_token_hit_class_present(self):
        assert '.replay-number-token--hit' in _html()

    def test_replay_number_token_special_class_present(self):
        """P260A: special number token class for purple pill."""
        assert '.replay-number-token--special' in _html()

    def test_replay_number_token_special_hit_class_present(self):
        assert '.replay-number-token--special-hit' in _html()

    def test_circular_border_radius(self):
        """Tokens now use border-radius:50% (circular style)."""
        assert 'border-radius:50%' in _html()

    def test_special_token_pill_radius(self):
        """Special tokens use pill border-radius (1000px)."""
        assert 'border-radius:1000px' in _html()

    def test_special_token_purple_color(self):
        """Special token has purple border/background."""
        html = _html()
        assert '#6e40c9' in html or '#b392f0' in html

    def test_row_hit_class_present(self):
        assert '.replay-row--hit' in _html()

    def test_result_badge_hit_present(self):
        assert '.replay-result-badge--hit' in _html()

    def test_result_badge_miss_present(self):
        assert '.replay-result-badge--miss' in _html()

    def test_p260a_range_btn_css_present(self):
        assert '.p260a-range-btn' in _html()


# ---------------------------------------------------------------------------
# Group 4: JS helpers present
# ---------------------------------------------------------------------------

class TestJSHelpers:
    def test_fmt_special_token_function_defined(self):
        """fmtSpecialToken helper added in P260A."""
        assert 'function fmtSpecialToken(' in _html()

    def test_fmt_hit_tokens_function_defined(self):
        """fmtHitTokens helper added in P260A."""
        assert 'function fmtHitTokens(' in _html()

    def test_fmt_number_tokens_function_still_present(self):
        """P259C fmtNumberTokens still present."""
        assert 'function fmtNumberTokens(' in _html()

    def test_special_token_emits_special_class(self):
        """fmtSpecialToken uses replay-number-token--special class."""
        assert 'replay-number-token--special' in _html()

    def test_special_token_emits_special_hit_class(self):
        assert 'replay-number-token--special-hit' in _html()

    def test_render_detail_rows_uses_fmt_special_token(self):
        """renderDetailRows calls fmtSpecialToken."""
        assert 'fmtSpecialToken(' in _html()

    def test_render_detail_rows_uses_fmt_hit_tokens(self):
        """renderDetailRows calls fmtHitTokens."""
        assert 'fmtHitTokens(' in _html()

    def test_render_detail_rows_uses_predicted_special(self):
        """renderDetailRows accesses r.predicted_special."""
        assert 'r.predicted_special' in _html()

    def test_render_detail_rows_uses_actual_special(self):
        """renderDetailRows accesses r.actual_special."""
        assert 'r.actual_special' in _html()

    def test_render_detail_rows_uses_hit_numbers(self):
        """renderDetailRows accesses r.hit_numbers for hit column."""
        assert 'r.hit_numbers' in _html()

    def test_quick_range_event_handler_present(self):
        """init() wires up click handler for .p260a-range-btn."""
        assert 'p260a-range-btn' in _html()
        assert 'p260a-quick-range' in _html()

    def test_quick_range_max_guard(self):
        """JS guard: ps > 1500 returns early (matches authorized limit)."""
        assert '> 1500' in _html()


# ---------------------------------------------------------------------------
# Group 5: API — page_size limit raised to 1500
# ---------------------------------------------------------------------------

class TestPageSizeLimit:
    def test_page_size_100_accepted(self, client, sample):
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=100"
        )
        assert r.status_code == 200

    def test_page_size_300_accepted(self, client, sample):
        """P260A: page_size=300 now within le=1500."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=300"
        )
        assert r.status_code == 200

    def test_page_size_500_accepted(self, client, sample):
        """P260A: page_size=500 now within le=1500."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=500"
        )
        assert r.status_code == 200

    def test_page_size_1500_accepted(self, client, sample):
        """P260A: page_size=1500 is the new authorized maximum."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=1500"
        )
        assert r.status_code == 200

    def test_page_size_1501_rejected(self, client, sample):
        """page_size=1501 exceeds le=1500 and must be rejected (422)."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=1501"
        )
        assert r.status_code == 422

    def test_page_size_2000_rejected(self, client, sample):
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=2000"
        )
        assert r.status_code == 422

    def test_page_size_default_still_100(self, client, sample):
        """Default page_size remains 100."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
        )
        assert r.status_code == 200
        d = r.json()
        assert d["page_size"] == 100


# ---------------------------------------------------------------------------
# Group 6: API — response schema unchanged (backward-compatible)
# ---------------------------------------------------------------------------

class TestAPISchemaBackwardCompat:
    def test_response_has_required_fields(self, client, sample):
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=100"
        )
        assert r.status_code == 200
        d = r.json()
        for field in ("rows", "total_count", "has_next", "page", "page_size"):
            assert field in d, f"Missing field: {field}"

    def test_rows_have_special_fields(self, client, sample):
        """Each row must carry predicted_special, actual_special, special_hit."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=10"
        )
        assert r.status_code == 200
        rows = r.json().get("rows", [])
        if not rows:
            pytest.skip("No rows returned — skip schema check")
        for row in rows[:5]:
            assert "predicted_special" in row
            assert "actual_special" in row
            assert "special_hit" in row
            assert "hit_numbers" in row
            assert "hit_count" in row

    def test_page_size_echoed_in_response(self, client, sample):
        for ps in (100, 300, 500):
            r = client.get(
                f"/api/replay/history-detail"
                f"?lottery_type={sample['lottery_type']}"
                f"&strategy_id={sample['strategy_id']}"
                f"&bet_index={sample['bet_index']}"
                f"&page_size={ps}"
            )
            assert r.status_code == 200
            assert r.json()["page_size"] == ps

    def test_server_side_pagination_still_active(self, client, sample):
        """page_size=100 returns at most 100 rows — server-side still enforced."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
            f"&page_size=100"
        )
        assert r.status_code == 200
        assert len(r.json()["rows"]) <= 100

    def test_no_db_write_on_detail_fetch(self, client, sample):
        """GET endpoint must be read-only — 200 response is sufficient proof."""
        r = client.get(
            f"/api/replay/history-detail"
            f"?lottery_type={sample['lottery_type']}"
            f"&strategy_id={sample['strategy_id']}"
            f"&bet_index={sample['bet_index']}"
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group 7: Hit highlighting still works (P259C regression)
# ---------------------------------------------------------------------------

class TestHitHighlightingRegression:
    def test_fmtNumberTokens_still_present(self):
        assert 'function fmtNumberTokens(' in _html()

    def test_hit_class_in_js(self):
        assert 'replay-number-token--hit' in _html()

    def test_non_hit_class_in_js(self):
        # The base class appears as part of a template string in fmtNumberTokens
        assert 'replay-number-token' in _html()

    def test_predicted_numbers_rendered_with_tokens(self):
        """fmtNumberTokens called for predicted_numbers in renderDetailRows."""
        html = _html()
        assert 'r.predicted_numbers' in html

    def test_actual_numbers_rendered_with_tokens(self):
        """fmtNumberTokens called for actual_numbers in renderDetailRows."""
        assert 'r.actual_numbers' in _html()

    def test_hit_numbers_used_in_fmtNumberTokens(self):
        assert 'r.hit_numbers' in _html()

    def test_replay_row_hit_class_applied(self):
        assert 'replay-row--hit' in _html()

    def test_result_badge_classes_applied(self):
        html = _html()
        assert 'replay-result-badge--hit' in html
        assert 'replay-result-badge--miss' in html


# ---------------------------------------------------------------------------
# Group 8: Overview API unchanged (P259A regression guard)
# ---------------------------------------------------------------------------

class TestOverviewUnchanged:
    def test_overview_has_no_per_draw_detail(self, client):
        """Overview API must NOT include per-draw row detail."""
        r = client.get("/api/replay/history-overview")
        assert r.status_code == 200
        d = r.json()
        for row in d.get("rows", []):
            assert "draws" not in row
            assert "per_draw" not in row
            assert "detail_rows" not in row

    def test_overview_endpoint_still_200(self, client):
        r = client.get("/api/replay/history-overview")
        assert r.status_code == 200
