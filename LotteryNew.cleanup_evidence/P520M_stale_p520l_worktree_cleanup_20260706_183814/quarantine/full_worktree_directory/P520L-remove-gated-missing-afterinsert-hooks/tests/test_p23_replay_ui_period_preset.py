"""
P23a: Replay UI Period Preset — Verification Tests

Tests:
  1. HTML structure — preset button DOM nodes present with correct data-preset attrs
  2. JS variables — rpPresetPeriods declared, rpPageSize changed to let
  3. rpBuildHistoryRows — helper function present and shared by rpQuery + rpPresetFetch
  4. rpPresetFetch — multi-fetch function present and references FETCH_PS=200
  5. rpQuery — no longer contains inline records.map() render loop (uses helper)
  6. DOMContentLoaded — preset button event wiring present
  7. Query button — resets rpPresetPeriods=0 and rpPageSize=50 on manual query
  8. Backend API page_size ceiling — confirmed le=200 in replay.py
  9. Production rows unchanged — 12460
 10. DAILY_539 regression — P22 test suite still passes (no special chip regression)
"""

import re
import sqlite3
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
INDEX_HTML = WORKSPACE / "index.html"
REPLAY_ROUTE = WORKSPACE / "lottery_api" / "routes" / "replay.py"
PROD_DB      = WORKSPACE / "lottery_api" / "data" / "lottery_v2.db"

# ── helpers ──────────────────────────────────────────────────────────────────

def html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")

def route_src() -> str:
    return REPLAY_ROUTE.read_text(encoding="utf-8")


# ── 1. HTML structure ─────────────────────────────────────────────────────────

class TestPresetButtonHTML:
    def test_preset_container_present(self):
        assert 'id="rp-preset-btns"' in html()

    def test_preset_container_testid(self):
        assert 'data-testid="rp-preset-btns"' in html()

    def test_preset_100_present(self):
        src = html()
        assert 'data-preset="100"' in src
        assert 'data-testid="rp-preset-100"' in src
        assert '>100期<' in src

    def test_preset_500_present(self):
        src = html()
        assert 'data-preset="500"' in src
        assert 'data-testid="rp-preset-500"' in src
        assert '>500期<' in src

    def test_preset_1000_present(self):
        src = html()
        assert 'data-preset="1000"' in src
        assert 'data-testid="rp-preset-1000"' in src
        assert '>1000期<' in src

    def test_preset_1500_present(self):
        src = html()
        assert 'data-preset="1500"' in src
        assert 'data-testid="rp-preset-1500"' in src
        assert '>1500期<' in src

    def test_preset_btn_class(self):
        """All four preset buttons carry the rp-preset-btn class for delegation."""
        matches = re.findall(r'class="[^"]*rp-preset-btn[^"]*"', html())
        assert len(matches) == 4, f"Expected 4 rp-preset-btn elements, got {len(matches)}"

    def test_total_label_still_present(self):
        """rp-total-label must remain intact (used by both rpQuery and rpPresetFetch)."""
        assert 'id="rp-total-label"' in html()

    def test_card_header_flex_wrap(self):
        """card-header updated to flex-wrap:wrap to handle the new button row."""
        assert 'flex-wrap:wrap' in html()


# ── 2. JS variables ────────────────────────────────────────────────────────────

class TestJSVariables:
    def test_rpPageSize_is_let_not_const(self):
        src = html()
        # Must NOT appear as const
        assert "const rpPageSize" not in src
        # Must appear as let
        assert "let rpPageSize = 50" in src

    def test_rpPresetPeriods_declared(self):
        assert "let rpPresetPeriods = 0" in html()

    def test_rpPresetPeriods_comment(self):
        assert "P23a" in html()


# ── 3. rpBuildHistoryRows helper ───────────────────────────────────────────────

class TestRpBuildHistoryRows:
    def test_function_declared(self):
        assert "function rpBuildHistoryRows(records)" in html()

    def test_function_called_by_rpQuery(self):
        """rpQuery must delegate rendering to rpBuildHistoryRows."""
        src = html()
        # rpQuery must contain the call
        rp_query_idx = src.index("async function rpQuery()")
        rp_query_src = src[rp_query_idx: rp_query_idx + 3000]
        assert "rpBuildHistoryRows(records)" in rp_query_src

    def test_function_called_by_rpPresetFetch(self):
        src = html()
        preset_idx = src.index("async function rpPresetFetch(n)")
        preset_src = src[preset_idx: preset_idx + 3000]
        assert "rpBuildHistoryRows(allRecords)" in preset_src

    def test_no_inline_map_in_rpQuery(self):
        """rpQuery must NOT contain the old inline records.map() render loop."""
        src = html()
        rp_query_idx = src.index("async function rpQuery()")
        rp_query_src = src[rp_query_idx: rp_query_idx + 3000]
        assert "records.map(r =>" not in rp_query_src

    def test_helper_contains_rp_toggle_btn(self):
        """rpBuildHistoryRows must render the detail toggle button."""
        src = html()
        helper_idx = src.index("function rpBuildHistoryRows(records)")
        # Extract until next function declaration
        end_idx = src.index("\n  async function rpPresetFetch", helper_idx)
        helper_src = src[helper_idx:end_idx]
        assert "rp-toggle-btn" in helper_src

    def test_helper_contains_rp_detail_row(self):
        src = html()
        helper_idx = src.index("function rpBuildHistoryRows(records)")
        end_idx = src.index("\n  async function rpPresetFetch", helper_idx)
        helper_src = src[helper_idx:end_idx]
        assert "rp-detail-row" in helper_src

    def test_helper_contains_rpSpecialChip_guard(self):
        """predicted_special null guard must be present in rpBuildHistoryRows."""
        src = html()
        helper_idx = src.index("function rpBuildHistoryRows(records)")
        end_idx = src.index("\n  async function rpPresetFetch", helper_idx)
        helper_src = src[helper_idx:end_idx]
        assert "predicted_special != null" in helper_src


# ── 4. rpPresetFetch function ─────────────────────────────────────────────────

class TestRpPresetFetch:
    def _preset_src(self):
        src = html()
        start = src.index("async function rpPresetFetch(n)")
        end   = src.index("\n  // Query history records\n  async function rpQuery", start)
        return src[start:end]

    def test_function_declared(self):
        assert "async function rpPresetFetch(n)" in html()

    def test_fetch_page_size_is_200(self):
        """Backend max page_size is 200; preset must use 200 for multi-fetch."""
        assert "FETCH_PS = 200" in self._preset_src()

    def test_multi_fetch_loop_present(self):
        assert "while (allRecords.length < n)" in self._preset_src()

    def test_accumulates_records(self):
        assert "allRecords = allRecords.concat(batch)" in self._preset_src()

    def test_slices_to_n(self):
        assert "allRecords.slice(0, n)" in self._preset_src()

    def test_sets_rpPresetPeriods(self):
        assert "rpPresetPeriods = n" in self._preset_src()

    def test_disables_prev_btn(self):
        assert "prevBtn.disabled = true" in self._preset_src()

    def test_disables_next_btn(self):
        assert "nextBtn.disabled = true" in self._preset_src()

    def test_uses_current_filters(self):
        """rpPresetFetch must read lottery_type, strategy_id, date filters."""
        src = self._preset_src()
        assert "rp-lottery-select" in src
        assert "rp-strategy-select" in src
        assert "rp-date-from" in src
        assert "rp-date-to" in src

    def test_fixture_mode_forwarded(self):
        assert "fixture_mode=true" in self._preset_src()

    def test_total_label_updated(self):
        assert "rp-total-label" in self._preset_src()

    def test_page_info_updated(self):
        assert "rp-page-info" in self._preset_src()


# ── 5. DOMContentLoaded event wiring ─────────────────────────────────────────

class TestDOMEventWiring:
    def _dom_src(self):
        src = html()
        start = src.index("document.addEventListener('DOMContentLoaded'")
        return src[start: start + 4000]

    def test_preset_buttons_wired(self):
        assert "querySelectorAll('.rp-preset-btn')" in self._dom_src()

    def test_preset_calls_rpPresetFetch(self):
        assert "rpPresetFetch(n)" in self._dom_src()

    def test_query_btn_resets_preset_periods(self):
        """Manual query must reset rpPresetPeriods=0 to exit preset mode."""
        assert "rpPresetPeriods = 0" in self._dom_src()

    def test_query_btn_resets_page_size(self):
        """Manual query must restore rpPageSize=50 after any preset run."""
        assert "rpPageSize = 50" in self._dom_src()

    def test_query_btn_resets_page_to_1(self):
        assert "rpPage = 1" in self._dom_src()


# ── 6. Backend API ceiling ────────────────────────────────────────────────────

class TestBackendPageSizeCeiling:
    def test_replay_history_max_page_size_200(self):
        """Backend enforces page_size le=200 — preset multi-fetch must stay within this."""
        src = route_src()
        assert "le=200" in src

    def test_replay_history_default_page_size_50(self):
        assert "Query(50, ge=1, le=200)" in route_src()

    def test_preset_fetch_size_within_ceiling(self):
        """FETCH_PS constant in rpPresetFetch must not exceed 200."""
        src = html()
        # Extract numeric value from the assignment
        m = re.search(r"FETCH_PS\s*=\s*(\d+)", src)
        assert m is not None, "FETCH_PS not found in index.html"
        fetch_ps = int(m.group(1))
        assert fetch_ps <= 200, f"FETCH_PS={fetch_ps} exceeds backend ceiling of 200"


# ── 7. Production row count ───────────────────────────────────────────────────

class TestProductionRowCount:
    def test_rows_unchanged_12460(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        finally:
            conn.close()
        assert count == 12460, f"Production rows changed: expected 12460, got {count}"

    def test_daily539_rows_present(self):
        conn = sqlite3.connect(str(PROD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='DAILY_539'"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 3180, f"DAILY_539 rows: expected 3180, got {count}"


# ── 8. DAILY_539 regression guard ────────────────────────────────────────────

class TestDaily539Regression:
    def test_null_special_unchanged(self):
        """predicted_special must still be SQL NULL for all DAILY_539 rows."""
        conn = sqlite3.connect(str(PROD_DB))
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type='DAILY_539' AND predicted_special IS NOT NULL"
            ).fetchone()[0]
        finally:
            conn.close()
        assert rows == 0, f"DAILY_539 rows with non-null predicted_special: {rows}"

    def test_rpSpecialChip_null_guard_in_helper(self):
        """rpBuildHistoryRows must guard predicted_special with != null check."""
        src = html()
        helper_idx = src.index("function rpBuildHistoryRows(records)")
        end_idx = src.index("\n  async function rpPresetFetch", helper_idx)
        helper_src = src[helper_idx:end_idx]
        assert "predicted_special != null" in helper_src

    def test_rpQuery_uses_shared_helper(self):
        """rpQuery must NOT have its own special-chip guard (must use rpBuildHistoryRows)."""
        src = html()
        rp_query_idx = src.index("async function rpQuery()")
        rp_query_src = src[rp_query_idx: rp_query_idx + 3000]
        # The old inline map should not be present
        assert "predicted_special != null" not in rp_query_src

    def test_existing_selectors_intact(self):
        """lottery_type / strategy / date selectors must still be present."""
        src = html()
        assert 'id="rp-lottery-select"' in src
        assert 'id="rp-strategy-select"' in src
        assert 'id="rp-date-from"' in src
        assert 'id="rp-date-to"' in src

    def test_fixture_toggle_intact(self):
        assert 'id="rp-fixture-toggle"' in html()

    def test_prev_next_pagination_intact(self):
        src = html()
        assert 'id="rp-prev-btn"' in src
        assert 'id="rp-next-btn"' in src
        assert 'id="rp-page-info"' in src
