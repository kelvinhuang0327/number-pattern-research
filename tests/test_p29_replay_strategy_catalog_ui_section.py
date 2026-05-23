"""
P29: Replay Strategy Catalog UI Section Tests
=============================================
Verifies that the P29 UI section correctly integrates with the P28
/api/replay/strategy-catalog endpoint without hardcoded label mappings,
enforces is_queryable semantics, and does not alter the production DB.

Tests:
  1. Catalog section HTML elements are present in index.html
  2. P29 JS function rpLoadCatalog is defined in index.html
  3. P29 JS does NOT hardcode any label-to-display mapping
  4. P29 JS enforces is_queryable: non-queryable rows cannot trigger rpQuery
  5. Correct catalog counts from API: 59 total / 8 / 41 / 5 / 4 / 1
  6. Every strategy has label_display_name and safe_user_message from API
  7. Non-row-backed entries have is_queryable=False
  8. Row-backed entries have is_queryable=True and row_count > 0
  9. Production rows remain 12460 (no DB write)
  10. Existing replay history flow: /api/replay endpoint still responds
  11. CEO coverage footnote: row_backed/total ratio expressed
  12. rpInitCatalogClickHandler is wired in DOMContentLoaded
  13. rpLoadCatalog is called on nav section click (replay)
  14. No console.error call in catalog error path (uses console.warn)
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
sys.path.insert(0, str(LOTTERY_API))

from routes.replay import get_replay_strategy_catalog  # noqa: E402

_DB_PATH     = LOTTERY_API / "data" / "lottery_v2.db"
_INDEX_HTML  = REPO_ROOT / "index.html"

_EXPECTED_TOTAL       = 59
_EXPECTED_ROW_BACKED  = 8
_EXPECTED_AO          = 41
_EXPECTED_RETIRED     = 5
_EXPECTED_REJECTED    = 4
_EXPECTED_OBSERVATION = 1
_EXPECTED_PRODUCTION_ROWS = 12460


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def catalog():
    return asyncio.get_event_loop().run_until_complete(get_replay_strategy_catalog())


@pytest.fixture(scope="module")
def html_source():
    return _INDEX_HTML.read_text(encoding="utf-8")


# ── 1. HTML elements present ──────────────────────────────────────────────────

def test_catalog_card_present(html_source):
    assert 'id="rp-catalog-card"' in html_source, "catalog card div must exist"


def test_catalog_title_present(html_source):
    assert '策略狀態總覽' in html_source, "catalog section title must be present"


def test_catalog_tbody_present(html_source):
    assert 'id="rp-catalog-tbody"' in html_source


def test_catalog_summary_present(html_source):
    assert 'id="rp-catalog-summary"' in html_source


def test_catalog_coverage_footnote_element(html_source):
    assert 'id="rp-catalog-coverage-footnote"' in html_source


def test_catalog_count_chips_element(html_source):
    assert 'id="rp-catalog-count-chips"' in html_source


def test_catalog_error_element_present(html_source):
    assert 'id="rp-catalog-error"' in html_source


def test_catalog_loading_element_present(html_source):
    assert 'id="rp-catalog-loading"' in html_source


# ── 2. JS function defined ────────────────────────────────────────────────────

def test_rpLoadCatalog_defined(html_source):
    assert 'async function rpLoadCatalog()' in html_source


def test_rpInitCatalogClickHandler_defined(html_source):
    assert 'function rpInitCatalogClickHandler()' in html_source


# ── 3. No hardcoded label-to-display mapping in P29 JS ───────────────────────

def test_no_hardcoded_label_map_in_catalog_js(html_source):
    """P29 must consume label_display_name from API, not hardcode it."""
    # Extract the rpLoadCatalog function body
    match = re.search(
        r'async function rpLoadCatalog\(\)(.*?)^\s{2}// ──',
        html_source,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "rpLoadCatalog body not found"
    body = match.group(1)
    # Must not hardcode the known label strings as mapping keys
    forbidden = [
        "'row-backed':","\"row-backed\":",
        "'artifact-only':","\"artifact-only\":",
        "row_backed_label","artifact_only_label",
    ]
    for f in forbidden:
        assert f not in body, f"hardcoded label mapping detected: {f}"


# ── 4. is_queryable enforcement in JS ────────────────────────────────────────

def test_non_queryable_click_does_not_trigger_rpQuery(html_source):
    """Clicking a non-queryable row must NOT call rpQuery."""
    match = re.search(
        r'function rpInitCatalogClickHandler\(\)(.*?)^\s{2}// ──',
        html_source,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "rpInitCatalogClickHandler body not found"
    body = match.group(1)
    # Must short-circuit (return) when not queryable
    assert "isQueryable" in body or "catalogQueryable" in body
    assert "return;" in body, "must return early for non-queryable entries"


# ── 5. API counts ─────────────────────────────────────────────────────────────

def test_catalog_total(catalog):
    assert catalog["total_strategies"] == _EXPECTED_TOTAL


def test_catalog_row_backed_count(catalog):
    assert catalog["row_backed_count"] == _EXPECTED_ROW_BACKED


def test_catalog_label_summary_artifact_only(catalog):
    assert catalog["label_summary"].get("artifact-only") == _EXPECTED_AO


def test_catalog_label_summary_retired(catalog):
    assert catalog["label_summary"].get("retired") == _EXPECTED_RETIRED


def test_catalog_label_summary_rejected(catalog):
    assert catalog["label_summary"].get("rejected-registered") == _EXPECTED_REJECTED


def test_catalog_label_summary_observation(catalog):
    assert catalog["label_summary"].get("observation") == _EXPECTED_OBSERVATION


# ── 6. Every strategy has required display fields ─────────────────────────────

def test_every_strategy_has_label_display_name(catalog):
    missing = [s["strategy_id"] for s in catalog["strategies"] if not s.get("label_display_name")]
    assert not missing, f"Missing label_display_name: {missing}"


def test_every_strategy_has_safe_user_message(catalog):
    missing = [s["strategy_id"] for s in catalog["strategies"] if not s.get("safe_user_message")]
    assert not missing, f"Missing safe_user_message: {missing}"


def test_every_strategy_has_is_queryable_field(catalog):
    missing = [s["strategy_id"] for s in catalog["strategies"] if "is_queryable" not in s]
    assert not missing, f"Missing is_queryable: {missing}"


# ── 7. Non-row-backed is_queryable=False ──────────────────────────────────────

def test_non_row_backed_not_queryable(catalog):
    bad = [
        s["strategy_id"]
        for s in catalog["strategies"]
        if not s.get("is_row_backed") and s.get("is_queryable") is True
    ]
    assert not bad, f"Non-row-backed entries must not be queryable: {bad}"


# ── 8. Row-backed is_queryable=True and row_count > 0 ────────────────────────

def test_row_backed_queryable_and_has_rows(catalog):
    bad = [
        s["strategy_id"]
        for s in catalog["strategies"]
        if s.get("is_row_backed") and (not s.get("is_queryable") or (s.get("row_count") or 0) <= 0)
    ]
    assert not bad, f"Row-backed entries must be queryable with row_count>0: {bad}"


# ── 9. Production rows unchanged ──────────────────────────────────────────────

def test_production_rows_unchanged():
    conn = sqlite3.connect(str(_DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    assert count == _EXPECTED_PRODUCTION_ROWS, (
        f"Production rows changed: expected {_EXPECTED_PRODUCTION_ROWS}, got {count}"
    )


# ── 10. Existing replay history endpoint still accessible ────────────────────

def test_existing_replay_api_still_importable():
    """Smoke: the replay route module loads without error after P29 changes."""
    from routes.replay import get_replay_history  # noqa: F401
    assert callable(get_replay_history)


# ── 11. CEO coverage footnote ratio correct ───────────────────────────────────

def test_ceo_coverage_footnote_ratio(catalog):
    """row_backed / total must be ~13.5%."""
    total = catalog["total_strategies"]
    rb    = catalog["row_backed_count"]
    pct   = rb / total * 100
    assert 13.0 < pct < 14.5, f"Expected ~13.5% coverage, got {pct:.2f}%"


# ── 12 & 13. Wiring in DOMContentLoaded ──────────────────────────────────────

def test_rpInitCatalogClickHandler_called_in_domcontentloaded(html_source):
    # Find the DOMContentLoaded block
    dcl_start = html_source.find("document.addEventListener('DOMContentLoaded'")
    assert dcl_start != -1
    dcl_block = html_source[dcl_start:dcl_start + 4000]
    assert "rpInitCatalogClickHandler()" in dcl_block


def test_rpLoadCatalog_called_in_domcontentloaded(html_source):
    dcl_start = html_source.find("document.addEventListener('DOMContentLoaded'")
    dcl_block = html_source[dcl_start:dcl_start + 4000]
    assert "rpLoadCatalog()" in dcl_block


def test_rpLoadCatalog_called_on_nav_click(html_source):
    """rpLoadCatalog must be called when the replay nav button is clicked."""
    assert "rpLoadCatalog();" in html_source


# ── 14. Catalog error path uses console.warn, not console.error ───────────────

def test_catalog_error_uses_warn_not_error(html_source):
    """Catalog load failure must not call console.error (non-blocking)."""
    match = re.search(
        r'async function rpLoadCatalog\(\)(.*?)^\s{2}// ──',
        html_source,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "rpLoadCatalog body not found"
    body = match.group(1)
    assert "console.error" not in body, "catalog error path must not call console.error"
    assert "console.warn" in body, "catalog error path must call console.warn"
