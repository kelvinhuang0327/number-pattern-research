"""
P34: Replay UI Usability Gap Closure — test suite

Covers:
  1. Default half-year date range IIFE in index.html
  2. RETIRED replay-backed label in strategy dropdown (rpLoadStrategies)
  3. History row RETIRED badge in rpBuildHistoryRows
  4. Lifecycle registry RETIRED badge for strategies with rows
  5. Preset buttons present (100/500/1000/1500)
  6. Production rows unchanged at 19960
  7. P31B strategies queryable via API (5 × 1500 rows each)
  8. No lifecycle promotion (RETIRED must not become ONLINE in any label)
"""

import json
import os
import re
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INDEX_HTML = os.path.join(os.path.dirname(__file__), '..', 'index.html')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'lottery_api', 'data', 'lottery_v2.db')

EXPECTED_TOTAL_ROWS = 19960
P31B_STRATEGIES = [
    'acb_1bet',
    'acb_markov_midfreq',
    'acb_markov_midfreq_3bet',
    'midfreq_acb_2bet',
    'midfreq_fourier_2bet',
]
P31B_EXPECTED_ROWS_PER_STRATEGY = 1500


def _read_index() -> str:
    with open(INDEX_HTML, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Default half-year date range
# ---------------------------------------------------------------------------

class TestDateRangeDefault:
    def test_rpSetDefaultDates_iife_present(self):
        """P34 IIFE rpSetDefaultDates must set rp-date-from and rp-date-to."""
        html = _read_index()
        assert 'rpSetDefaultDates' in html, \
            'rpSetDefaultDates IIFE not found in index.html'

    def test_setMonth_minus_6_present(self):
        """Date range must subtract 6 months."""
        html = _read_index()
        # Either setMonth(... - 6) or setMonth(getMonth() - 6)
        assert 'setMonth' in html and '- 6' in html, \
            'Six-month lookback logic not found (setMonth ... - 6)'

    def test_default_dates_before_rpRestoreFromURL(self):
        """rpSetDefaultDates IIFE must appear before the DOMContentLoaded rpRestoreFromURL(); call."""
        html = _read_index()
        # Use 'rpRestoreFromURL();' (with semicolon) to skip the function definition
        pos_default = html.find('rpSetDefaultDates')
        pos_restore = html.find('rpRestoreFromURL();')
        assert pos_default != -1, 'rpSetDefaultDates not found'
        assert pos_restore != -1, 'rpRestoreFromURL(); call not found'
        assert pos_default < pos_restore, \
            'rpSetDefaultDates must appear before rpRestoreFromURL(); in DOMContentLoaded'


# ---------------------------------------------------------------------------
# 2. RETIRED replay-backed label in strategy dropdown
# ---------------------------------------------------------------------------

class TestRetiredDropdownLabel:
    def test_retired_replay_backed_label_present(self):
        """rpLoadStrategies must include '已退役 · 有回放資料' label for RETIRED strategies."""
        html = _read_index()
        assert '已退役 · 有回放資料' in html, \
            "Strategy dropdown RETIRED replay-backed label '已退役 · 有回放資料' not found"

    def test_retired_fallback_label_present(self):
        """rpLoadStrategies must include fallback '已退役' label."""
        html = _read_index()
        assert '已退役' in html, \
            "'已退役' fallback label not found in index.html"

    def test_rpStrategyRowCountMap_checked_for_retired(self):
        """rpLoadStrategies must consult rpStrategyRowCountMap for RETIRED rows."""
        html = _read_index()
        # The pattern: lcValue === 'RETIRED' near rpStrategyRowCountMap
        pattern = re.compile(r"lcValue\s*===\s*'RETIRED'.*?rpStrategyRowCountMap", re.DOTALL)
        assert pattern.search(html), \
            'rpLoadStrategies does not check rpStrategyRowCountMap for RETIRED lifecycle'


# ---------------------------------------------------------------------------
# 3. History row RETIRED badge
# ---------------------------------------------------------------------------

class TestHistoryRowRetiredBadge:
    def test_retired_badge_in_history_rows(self):
        """rpBuildHistoryRows must render a 回放 badge for RETIRED strategy rows."""
        html = _read_index()
        assert "lifecycle_status === 'RETIRED'" in html or \
               "strategy_lifecycle_status === 'RETIRED'" in html, \
            'RETIRED check not found in rpBuildHistoryRows row template'

    def test_replay_badge_text(self):
        """The 回放 badge must appear in rpBuildHistoryRows template."""
        html = _read_index()
        assert '>回放</span>' in html, \
            "'>回放</span>' badge not found in history row template"


# ---------------------------------------------------------------------------
# 4. Lifecycle registry RETIRED badge
# ---------------------------------------------------------------------------

class TestLifecycleRegistryRetiredBadge:
    def test_lc_registry_has_replay_badge(self):
        """rpRenderLifecycleRegistryRows must render '有回放資料' badge for RETIRED with rows."""
        html = _read_index()
        assert '有回放資料' in html, \
            "'有回放資料' badge not found in lifecycle registry rendering"

    def test_lc_registry_badge_checks_row_count(self):
        """The badge must be conditional on rpStrategyRowCountMap row count > 0."""
        html = _read_index()
        # Look for: rpStrategyRowCountMap[s.strategy_id] ... > 0 near '有回放資料'
        segment = html[html.find('rpRenderLifecycleRegistryRows'):][:3000]
        assert 'rpStrategyRowCountMap' in segment, \
            'Lifecycle registry badge does not check rpStrategyRowCountMap'
        assert '> 0' in segment, \
            'Lifecycle registry badge does not gate on row count > 0'


# ---------------------------------------------------------------------------
# 5. Period preset buttons
# ---------------------------------------------------------------------------

class TestPresetButtons:
    @pytest.mark.parametrize('n', [100, 500, 1000, 1500])
    def test_preset_button_present(self, n):
        html = _read_index()
        assert f'data-preset="{n}"' in html or f"rpPresetFetch({n})" in html, \
            f'Preset button for {n} periods not found in index.html'


# ---------------------------------------------------------------------------
# 6. Production row count unchanged
# ---------------------------------------------------------------------------

class TestProductionRowCount:
    def test_total_rows_unchanged(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM strategy_prediction_replays')
        count = cur.fetchone()[0]
        conn.close()
        assert count == EXPECTED_TOTAL_ROWS, \
            f'Production rows changed: expected {EXPECTED_TOTAL_ROWS}, got {count}'


# ---------------------------------------------------------------------------
# 7. P31B strategies queryable (5 × 1500 rows each)
# ---------------------------------------------------------------------------

class TestP31BStrategiesQueryable:
    @pytest.mark.parametrize('strategy_id', P31B_STRATEGIES)
    def test_p31b_strategy_has_rows(self, strategy_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            'SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND controlled_apply_id LIKE ?',
            (strategy_id, 'P31B%')
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count == P31B_EXPECTED_ROWS_PER_STRATEGY, \
            f'{strategy_id} expected {P31B_EXPECTED_ROWS_PER_STRATEGY} P31B rows, got {count}'

    def test_total_retired_p31b_rows(self):
        """Total P31B rows must equal 7500 (5 × 1500)."""
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P31B%'"
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count == len(P31B_STRATEGIES) * P31B_EXPECTED_ROWS_PER_STRATEGY, \
            f'Total P31B rows: expected {len(P31B_STRATEGIES) * P31B_EXPECTED_ROWS_PER_STRATEGY}, got {count}'


# ---------------------------------------------------------------------------
# 8. No lifecycle promotion — RETIRED must not become ONLINE
# ---------------------------------------------------------------------------

class TestNoLifecyclePromotion:
    def test_retired_not_promoted_to_online_in_labels(self):
        """UI must not programmatically change lifecycle_status from RETIRED to ONLINE."""
        html = _read_index()
        # The concern is JS code that would reassign lifecycle to ONLINE for RETIRED strategies
        # Check that there is no assignment of 'ONLINE' value when the context is RETIRED
        dangerous_patterns = [
            "lifecycle_status = 'ONLINE'",
            'lifecycle_status = "ONLINE"',
            "lcValue = 'ONLINE'",
        ]
        for pat in dangerous_patterns:
            assert pat not in html, \
                f'Potential lifecycle promotion found: {pat}'
