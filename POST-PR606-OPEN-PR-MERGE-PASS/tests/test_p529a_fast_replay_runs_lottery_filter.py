"""Focused static tests for the P529A_FAST Replay runs lottery filter."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _runs_script() -> str:
    return _html().split("// P525A_FAST: read-only monitoring", 1)[1].split(
        "// P526A_FAST:", 1
    )[0]


def _runs_filter_snippet() -> str:
    script = _runs_script()
    return "\n".join(
        line
        for line in script.splitlines()
        if "lotteryFilter" in line
        or "replay-runs-lottery-filter" in line
        or "lottery_type" in line
        or "/api/replay/runs" in line
    )


def test_lottery_filter_control_extends_recent_runs_monitor() -> None:
    html = _html()
    panel = html.split('id="replay-runs-panel"', 1)[1].split(
        '<!-- Data Explanation Panel -->', 1
    )[0]

    assert 'id="replay-runs-lottery-filter"' in panel
    assert 'for="replay-runs-lottery-filter"' in panel
    assert '<option value="">全部</option>' in panel
    assert '<option value="BIG_LOTTO">大樂透</option>' in panel
    assert '<option value="POWER_LOTTO">威力彩</option>' in panel
    assert '<option value="DAILY_539">今彩539</option>' in panel


def test_runs_loader_uses_existing_read_only_lottery_type_parameter() -> None:
    script = _runs_script()

    assert "base + '/api/replay/runs?page=1&page_size=5'" in script
    assert "base + '/api/replay/runs?page=1&page_size=5&lottery_type=' + encodeURIComponent(lotteryFilter.value)" in script
    assert "await fetch(base + '/api/replay/runs?page=1&page_size=5')" in script
    assert "response.ok" in script
    assert "method:" not in script


def test_lottery_filter_has_loading_and_change_states() -> None:
    script = _runs_script()

    assert "lotteryFilter.disabled = true" in script
    assert "lotteryFilter.disabled = false" in script
    assert "lotteryFilter.addEventListener('change', loadReplayRuns)" in script
    assert "refresh.addEventListener('click', loadReplayRuns)" in script


def test_lottery_filter_does_not_add_db_prediction_or_mutation_behavior() -> None:
    snippet = _runs_filter_snippet()

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
        assert forbidden not in snippet
