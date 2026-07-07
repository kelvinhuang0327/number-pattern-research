"""Focused static tests for the P524A_FAST read-only evidence monitor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P524A_FAST: read-only monitoring", 1)[1]


def test_evidence_panel_is_part_of_visible_replay_monitoring() -> None:
    html = _html()
    replay = html.split('id="replay-section"', 1)[1].split('id="tracking-section"', 1)[0]

    assert '<!-- Read-only cross-lottery evidence dashboard monitor -->' in replay
    assert 'id="evidence-dashboard-panel"' in replay
    assert 'id="evidence-dashboard-summary"' in replay
    assert 'id="evidence-dashboard-detail"' in replay
    assert 'id="evidence-dashboard-warning"' in replay
    assert 'id="refresh-evidence-dashboard-btn"' in replay
    assert 'aria-live="polite"' in replay


def test_monitor_uses_only_existing_read_only_endpoint() -> None:
    script = _script()

    assert "fetch(base + '/api/replay/evidence-dashboard')" in script
    assert "response.ok" in script
    assert "response.json()" in script
    assert "method:" not in script


def test_monitor_renders_global_lottery_and_staleness_evidence() -> None:
    script = _script()

    for field in (
        "global.current_registry_entries",
        "global.historical_inventory_entries",
        "global.artifact_only_entries",
        "global.replay_rows_total",
        "payload.lottery_cards",
        "payload.stale_snapshot_warning.message",
    ):
        assert field in script
    assert "lotteryLabels.join(' / ')" in script
    assert "僅供歷史證據稽核，不代表策略建議或可部署狀態" in _html()


def test_monitor_has_loading_error_empty_and_manual_refresh_states() -> None:
    script = _script()

    assert "讀取中…" in script
    assert "無法讀取" in script
    assert "無彩種明細" in script
    assert "不影響其他查詢功能" in script
    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "refresh.addEventListener('click', loadEvidenceDashboard)" in script


def test_monitor_does_not_add_prediction_db_or_mutation_behavior() -> None:
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
