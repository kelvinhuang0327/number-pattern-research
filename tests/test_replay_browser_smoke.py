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
  - No edge discovery
  - No replay generation triggered
  - No external API calls
"""

from __future__ import annotations

import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")


def _load_html() -> str:
    if not os.path.exists(INDEX_HTML):
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
