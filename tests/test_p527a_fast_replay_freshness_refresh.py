"""Focused static tests for the P527A_FAST Replay freshness refresh control."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _freshness_block() -> str:
    return _html().split("// ── Freshness badge", 1)[1].split("// ===== P95", 1)[0]


def test_refresh_control_extends_existing_freshness_card() -> None:
    html = _html()
    card = html.split('id="rp-freshness-card"', 1)[1].split(
        '<!-- Read-only model cache monitor -->', 1
    )[0]

    assert 'id="refresh-rp-freshness-btn"' in card
    assert '刷新覆蓋狀態' in card
    assert 'id="rp-coverage-badge"' in card
    assert 'id="rp-freshness-error"' in card


def test_refresh_control_reuses_existing_read_only_freshness_endpoint() -> None:
    block = _freshness_block()

    assert "fetch(BASE + '/freshness')" in block
    assert "response.ok" not in block
    assert "resp.ok" in block
    assert "resp.json()" in block
    assert "method:" not in block


def test_refresh_control_has_loading_error_and_click_states() -> None:
    block = _freshness_block()

    assert "refresh.disabled = true" in block
    assert "refresh.disabled = false" in block
    assert "addEventListener('click', rpLoadFreshness)" in block
    assert "errEl.style.display   = 'none'" in block
    assert "errEl.style.display   = ''" in block
    assert "console.warn('[replay] freshness load failed'" in block


def test_freshness_refresh_does_not_add_mutation_or_prediction_behavior() -> None:
    block = _freshness_block()

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
        assert forbidden not in block
