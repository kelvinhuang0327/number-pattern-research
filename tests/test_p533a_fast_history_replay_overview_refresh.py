"""Focused static tests for the P533A_FAST history overview refresh control."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _overview_section() -> str:
    return _html().split("<!-- ===== P259A: History Replay Overview", 1)[1].split(
        "<!-- ===== END P259A", 1
    )[0]


def _overview_script() -> str:
    return _html().split("<!-- P259A: History Replay Overview JS", 1)[1].split(
        "<!-- P259B: History Replay Detail JS", 1
    )[0]


def test_refresh_control_extends_existing_history_overview() -> None:
    section = _overview_section()

    assert 'id="refresh-p259a-overview-btn"' in section
    assert 'type="button"' in section
    assert "刷新回放總覽" in section
    assert 'id="p259a-loading"' in section
    assert 'id="p259a-error"' in section
    assert 'id="p259a-table"' in section


def test_refresh_control_reuses_existing_read_only_overview_endpoint() -> None:
    script = _overview_script()

    assert "/api/replay/history-overview?coverage_mode=true&bet_index=" in script
    assert "fetch(url)" in script
    assert ".json()" in script
    assert "method:" not in script


def test_refresh_control_preserves_active_bet_view_and_loading_states() -> None:
    script = _overview_script()

    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert ".finally(function()" in script
    assert "refresh.addEventListener('click', function()" in script
    assert "p259aLoad(_p259aBetIndex)" in script


def test_overview_refresh_does_not_add_db_prediction_or_mutation_behavior() -> None:
    script = _overview_script()

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
