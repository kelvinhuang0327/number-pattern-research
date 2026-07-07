"""Focused static tests for the P530A_FAST lifecycle registry refresh control."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _lifecycle_card() -> str:
    return _html().split('id="rp-lifecycle-registry-card"', 1)[1].split(
        "<!-- P29: 策略狀態總覽", 1
    )[0]


def _lifecycle_script() -> str:
    return _html().split("// ── P7: Strategy Lifecycle Registry", 1)[1].split(
        "// ── P29: Strategy Catalog", 1
    )[0]


def test_refresh_control_extends_existing_lifecycle_registry_card() -> None:
    card = _lifecycle_card()

    assert 'id="refresh-rp-lifecycle-btn"' in card
    assert 'type="button"' in card
    assert "刷新登錄表" in card
    assert 'id="rp-lc-loading"' in card
    assert 'id="rp-lc-error"' in card
    assert 'id="rp-lc-table-wrap"' in card


def test_refresh_control_reuses_existing_read_only_lifecycle_endpoint() -> None:
    script = _lifecycle_script()

    assert "fetch(`${API_BASE}/api/replay/strategy-lifecycle`)" in script
    assert "resp.ok" in script
    assert "resp.json()" in script
    assert "method:" not in script


def test_refresh_control_has_loading_error_and_click_states() -> None:
    html = _html()
    script = _lifecycle_script()

    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "errEl.style.display    = 'none'" in script
    assert "errEl.style.display   = ''" in script
    assert "finally" in script
    assert "lifecycleRefreshBtn.addEventListener('click', rpLoadLifecycleRegistry)" in html


def test_lifecycle_refresh_does_not_add_db_prediction_or_mutation_behavior() -> None:
    script = _lifecycle_script()

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
