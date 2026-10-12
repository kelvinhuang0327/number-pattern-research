"""Focused static tests for the P531A_FAST strategy catalog refresh control."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _catalog_card() -> str:
    return _html().split('id="rp-catalog-card"', 1)[1].split(
        "<!-- ═══════════════════════ REVIEWS SECTION", 1
    )[0]


def _catalog_script() -> str:
    return _html().split("// ── P29: Strategy Catalog", 1)[1].split(
        "// ── P29: catalog row click delegation", 1
    )[0]


def test_refresh_control_extends_existing_strategy_catalog_card() -> None:
    card = _catalog_card()

    assert 'id="refresh-rp-catalog-btn"' in card
    assert 'type="button"' in card
    assert "刷新策略目錄" in card
    assert 'id="rp-catalog-loading"' in card
    assert 'id="rp-catalog-error"' in card
    assert 'id="rp-catalog-list-wrap"' in card


def test_refresh_control_reuses_existing_read_only_catalog_endpoint() -> None:
    script = _catalog_script()

    assert "fetch(`${API_BASE}/api/replay/strategy-catalog`)" in script
    assert "resp.ok" in script
    assert "resp.json()" in script
    assert "method:" not in script


def test_refresh_control_has_loading_error_and_click_states() -> None:
    html = _html()
    script = _catalog_script()

    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "errEl.style.display   = 'none'" in script
    assert "errEl.style.display   = ''" in script
    assert "finally" in script
    assert "catalogRefreshBtn.addEventListener('click', rpLoadCatalog)" in html


def test_catalog_refresh_does_not_add_db_prediction_or_mutation_behavior() -> None:
    script = _catalog_script()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in script
