"""Focused static tests for the P532A_FAST D3 SSOT coverage refresh control."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _coverage_section() -> str:
    return _html().split("<!-- ===== P263B D3 Strategy Status", 1)[1].split(
        "<!-- ===== END P263B =====", 1
    )[0]


def _coverage_script() -> str:
    return _html().split("<!-- ===== P263B D3 STRATEGY STATUS SSOT COVERAGE JS", 1)[1].split(
        "<!-- P259A: History Replay Overview JS", 1
    )[0]


def test_refresh_control_extends_existing_d3_ssot_coverage_audit() -> None:
    section = _coverage_section()

    assert 'id="refresh-p263b-coverage-btn"' in section
    assert 'type="button"' in section
    assert "刷新 SSOT 稽核" in section
    assert 'id="p263b-status"' in section
    assert 'id="p263b-rows-table"' in section


def test_refresh_control_reuses_existing_read_only_coverage_endpoint() -> None:
    script = _coverage_script()

    assert "/api/replay/d3-strategy-status-coverage" in script
    assert "fetch(url)" in script
    assert ".json()" in script
    assert "method:" not in script


def test_refresh_control_has_loading_error_and_click_states() -> None:
    script = _coverage_script()

    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "p263bSetStatus('載入中…')" in script
    assert "p263bSetStatus('載入失敗：' + e.message)" in script
    assert ".finally(function ()" in script
    assert "refresh.addEventListener('click', p263bLoad)" in script


def test_coverage_refresh_does_not_add_db_prediction_or_mutation_behavior() -> None:
    script = _coverage_script()

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
