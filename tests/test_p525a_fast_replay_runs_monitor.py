"""Focused static tests for the P525A_FAST read-only Replay runs monitor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P525A_FAST: read-only monitoring", 1)[1]


def test_replay_runs_panel_is_part_of_visible_replay_monitoring() -> None:
    html = _html()
    replay = html.split('id="replay-section"', 1)[1].split('id="tracking-section"', 1)[0]

    assert '<!-- Read-only recent Replay runs monitor -->' in replay
    assert 'id="replay-runs-panel"' in replay
    assert 'id="replay-runs-summary"' in replay
    assert 'id="replay-runs-detail"' in replay
    assert 'id="refresh-replay-runs-btn"' in replay
    assert 'aria-live="polite"' in replay


def test_monitor_uses_only_existing_read_only_runs_endpoint() -> None:
    script = _script()

    assert "fetch(base + '/api/replay/runs?page=1&page_size=5')" in script
    assert "response.ok" in script
    assert "response.json()" in script
    assert "method:" not in script


def test_monitor_renders_run_identity_status_and_timestamps() -> None:
    script = _script()

    for field in (
        "payload.runs",
        "payload.total",
        "run.id",
        "run.lottery_type",
        "run.status",
        "run.finished_at || run.started_at || run.created_at",
    ):
        assert field in script
    assert "runs.map(formatReplayRun).join(' ｜ ')" in script
    assert "只顯示最近 5 筆執行紀錄" in _html()


def test_monitor_has_loading_error_empty_and_manual_refresh_states() -> None:
    script = _script()

    assert "讀取中…" in script
    assert "無法讀取" in script
    assert "目前沒有 Replay Run 紀錄" in script
    assert "不影響其他查詢功能" in script
    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "refresh.addEventListener('click', loadReplayRuns)" in script


def test_monitor_does_not_add_db_prediction_or_mutation_behavior() -> None:
    script = _script()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "method:",
    ):
        assert forbidden not in script
