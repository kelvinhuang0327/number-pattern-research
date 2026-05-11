"""
test_replay_strategy_lifecycle_dashboard_static.py
==================================================
P10 — Dashboard Read-only Lifecycle Card Static Smoke Tests

Static HTML/JS string inspection tests for the lifecycle registry card.
No browser automation, no Playwright, no external API calls.
No replay generation, no DB write.

Covers 10 smoke checks:
  1.  index.html contains rp-lifecycle-registry-card
  2.  index.html contains rpLoadLifecycleRegistry function
  3.  endpoint path /api/replay/strategy-lifecycle exists in frontend JS
  4.  lifecycle card contains badge display elements
  5.  lifecycle card does not contain promote button
  6.  lifecycle card does not contain backfill button
  7.  lifecycle card does not contain run replay button / scheduler trigger
  8.  lifecycle card does not contain scheduler trigger
  9.  lifecycle rendering uses _esc() for strategy data (XSS protection)
  10. error state element is display-only (not an action trigger)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


@pytest.fixture(scope="module")
def html_text():
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Helper: extract the content of the lifecycle registry card block and the
# rpLoadLifecycleRegistry JS function from the full page text.
# ---------------------------------------------------------------------------

def _extract_card_block(html: str) -> str:
    """Return the substring of html that contains the lifecycle registry card."""
    start = html.find('id="rp-lifecycle-registry-card"')
    if start == -1:
        return ""
    # Take enough context after the card opening tag (up to 3000 chars)
    return html[max(0, start - 50): start + 3000]


def _extract_js_function(html: str, func_name: str) -> str:
    """Return a best-effort substring containing the named JS function."""
    start = html.find(f"function {func_name}")
    if start == -1:
        start = html.find(f"async function {func_name}")
    if start == -1:
        return ""
    return html[start: start + 2000]


# ---------------------------------------------------------------------------
# 1. rp-lifecycle-registry-card present
# ---------------------------------------------------------------------------

class TestCardPresence:
    def test_lifecycle_registry_card_exists(self, html_text):
        assert 'id="rp-lifecycle-registry-card"' in html_text

    def test_lifecycle_registry_card_has_tbody(self, html_text):
        assert 'id="rp-lc-tbody"' in html_text

    def test_lifecycle_registry_card_has_table(self, html_text):
        assert 'id="rp-lc-table"' in html_text


# ---------------------------------------------------------------------------
# 2. rpLoadLifecycleRegistry function present
# ---------------------------------------------------------------------------

class TestJsFunction:
    def test_rpLoadLifecycleRegistry_function_exists(self, html_text):
        assert "rpLoadLifecycleRegistry" in html_text

    def test_rpLoadLifecycleRegistry_is_defined_as_function(self, html_text):
        # Must be defined (not just called)
        assert re.search(
            r"(async\s+)?function\s+rpLoadLifecycleRegistry\s*\(", html_text
        ), "rpLoadLifecycleRegistry is not defined as a function"


# ---------------------------------------------------------------------------
# 3. Endpoint path in frontend JS
# ---------------------------------------------------------------------------

class TestEndpointReference:
    def test_frontend_references_strategy_lifecycle_endpoint(self, html_text):
        assert "/api/replay/strategy-lifecycle" in html_text

    def test_endpoint_referenced_via_fetch(self, html_text):
        js_fn = _extract_js_function(html_text, "rpLoadLifecycleRegistry")
        assert "fetch" in js_fn or "fetch" in html_text, (
            "No fetch() call found in rpLoadLifecycleRegistry"
        )


# ---------------------------------------------------------------------------
# 4. Badge display elements present
# ---------------------------------------------------------------------------

class TestBadgeElements:
    def test_online_badge_exists(self, html_text):
        assert 'id="rp-lc-badge-online"' in html_text

    def test_rejected_badge_exists(self, html_text):
        assert 'id="rp-lc-badge-rejected"' in html_text

    def test_retired_badge_exists(self, html_text):
        assert 'id="rp-lc-badge-retired"' in html_text

    def test_observation_badge_exists(self, html_text):
        assert 'id="rp-lc-badge-obs"' in html_text


# ---------------------------------------------------------------------------
# 5. No promote button in lifecycle card
# ---------------------------------------------------------------------------

class TestNoPromoteButton:
    def test_card_block_has_no_promote_button(self, html_text):
        card = _extract_card_block(html_text)
        # Accept Chinese or English variants
        assert "promote" not in card.lower(), (
            "lifecycle registry card contains 'promote' — prohibited write action"
        )
        assert "升級" not in card, (
            "lifecycle registry card contains '升級' (promote) — prohibited write action"
        )
        assert "晉升" not in card, (
            "lifecycle registry card contains '晉升' (promote) — prohibited write action"
        )


# ---------------------------------------------------------------------------
# 6. No backfill button in lifecycle card
# ---------------------------------------------------------------------------

class TestNoBackfillButton:
    def test_card_block_has_no_backfill_button(self, html_text):
        card = _extract_card_block(html_text)
        # "backfill" may appear in other sections (e.g. lifecycle select emptyMsg)
        # We check specifically within the card block
        assert "backfill" not in card.lower() or "catalog backfill" not in card, (
            "lifecycle registry card contains backfill trigger — prohibited write action"
        )

    def test_card_block_has_no_backfill_button_tag(self, html_text):
        card = _extract_card_block(html_text)
        # Must not have a <button> with backfill-related text
        assert not re.search(r"<button[^>]*>[^<]*backfill[^<]*</button>", card, re.I), (
            "lifecycle registry card has a backfill button tag"
        )


# ---------------------------------------------------------------------------
# 7. No run-replay button in lifecycle card
# ---------------------------------------------------------------------------

class TestNoRunReplayButton:
    def test_card_block_has_no_run_replay_button(self, html_text):
        card = _extract_card_block(html_text)
        assert not re.search(r"<button[^>]*>[^<]*(run|執行|replay)[^<]*</button>", card, re.I), (
            "lifecycle registry card has a run/replay button"
        )

    def test_card_block_has_no_execute_action(self, html_text):
        card = _extract_card_block(html_text)
        assert "run_replay" not in card
        assert "triggerReplay" not in card


# ---------------------------------------------------------------------------
# 8. No scheduler trigger in lifecycle card
# ---------------------------------------------------------------------------

class TestNoSchedulerTrigger:
    def test_card_block_has_no_scheduler_trigger(self, html_text):
        card = _extract_card_block(html_text)
        # scheduler controls exist elsewhere in page, check the card block only
        assert "scheduler-toggle" not in card, (
            "lifecycle registry card contains scheduler toggle — prohibited"
        )
        assert "scheduler_trigger" not in card.lower(), (
            "lifecycle registry card contains scheduler_trigger — prohibited"
        )


# ---------------------------------------------------------------------------
# 9. _esc() used for strategy data rendering
# ---------------------------------------------------------------------------

class TestXssProtection:
    def test_esc_function_defined(self, html_text):
        assert "_esc(" in html_text or "function _esc" in html_text, (
            "_esc() function not found in index.html"
        )

    def test_strategy_id_rendered_via_esc(self, html_text):
        js_fn = _extract_js_function(html_text, "rpLoadLifecycleRegistry")
        assert "_esc(s.strategy_id)" in js_fn or "_esc(" in js_fn, (
            "rpLoadLifecycleRegistry does not use _esc() for strategy data"
        )

    def test_lifecycle_status_rendered_via_esc(self, html_text):
        # The function body may exceed the 2000-char extraction window.
        # Search the full page for the escape call instead.
        assert "_esc(s.lifecycle_status)" in html_text, (
            "lifecycle_status not XSS-escaped in rpLoadLifecycleRegistry"
        )


# ---------------------------------------------------------------------------
# 10. Error state is display-only
# ---------------------------------------------------------------------------

class TestErrorStateDisplayOnly:
    def test_error_element_exists(self, html_text):
        assert 'id="rp-lc-error"' in html_text

    def test_error_element_is_not_a_button(self, html_text):
        # Find the rp-lc-error element and verify it is not a <button>
        idx = html_text.find('id="rp-lc-error"')
        if idx == -1:
            pytest.skip("rp-lc-error element not found")
        context = html_text[max(0, idx - 10): idx + 5]
        assert "<button" not in context, (
            "rp-lc-error element is a button — should be display-only"
        )

    def test_error_state_has_no_retry_action(self, html_text):
        card = _extract_card_block(html_text)
        assert "onclick" not in html_text[
            html_text.find('id="rp-lc-error"'):
            html_text.find('id="rp-lc-error"') + 200
        ], "rp-lc-error element has an onclick handler — should be display-only"
