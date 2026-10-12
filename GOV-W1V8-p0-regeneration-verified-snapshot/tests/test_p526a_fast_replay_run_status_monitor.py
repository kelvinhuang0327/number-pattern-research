"""Focused static tests for the P526A_FAST read-only Replay run status monitor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P526A_FAST: read-only status counts", 1)[1]


def test_status_controls_extend_existing_recent_runs_monitor() -> None:
    html = _html()
    panel = html.split('id="replay-runs-panel"', 1)[1].split(
        '<!-- Data Explanation Panel -->', 1
    )[0]

    assert 'id="replay-run-select"' in panel
    assert 'id="load-replay-run-status-btn"' in panel
    assert 'id="replay-run-status-detail"' in panel
    assert '查看狀態計數' in panel
    assert '唯讀狀態計數' in panel


def test_recent_runs_populate_safe_select_options() -> None:
    html = _html()
    p525_script = html.split("// P525A_FAST: read-only monitoring", 1)[1]

    assert "document.createElement('option')" in p525_script
    assert "option.value = String(run.id)" in p525_script
    assert "option.textContent = formatReplayRun(run)" in p525_script
    assert "select.disabled = !runs.length" in p525_script
    assert "loadStatus.disabled = !runs.length" in p525_script


def test_status_monitor_uses_only_existing_read_only_endpoint() -> None:
    script = _script()

    assert "fetch(base + '/api/replay/run/' + encodeURIComponent(runId) + '/status')" in script
    assert "response.ok" in script
    assert "response.json()" in script
    assert "method:" not in script


def test_status_monitor_validates_run_id_and_renders_counts() -> None:
    script = _script()

    assert "if (!/^\\d+$/.test(runId))" in script
    assert "payload.run" in script
    assert "payload.status_counts" in script
    assert "Object.keys(counts).sort()" in script
    assert "Number(counts[status])" in script
    assert "countLabels.join(' / ')" in script


def test_status_monitor_has_loading_empty_error_and_click_states() -> None:
    script = _script()

    assert "正在讀取 Run #" in script
    assert "沒有狀態計數" in script
    assert "暫時無法使用，不影響其他查詢功能" in script
    assert "loadStatus.disabled = true" in script
    assert "loadStatus.addEventListener('click', loadReplayRunStatus)" in script


def test_status_monitor_does_not_add_db_prediction_or_mutation_behavior() -> None:
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
