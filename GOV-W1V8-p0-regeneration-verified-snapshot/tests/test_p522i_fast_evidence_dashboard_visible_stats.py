"""Focused static tests for P522I_FAST evidence dashboard visible aggregate stats."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


@pytest.fixture(scope="module")
def section() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- ===== P251F: Evidence Dashboard UI.*?<!-- ===== END P251F =====",
        html,
        re.DOTALL,
    )
    assert match, "P251F evidence dashboard section not found"
    return match.group(0)


def test_visible_stats_container_exists(section: str) -> None:
    assert 'id="p251f-visible-stats"' in section
    assert 'role="status"' in section.split('id="p251f-visible-stats"')[1][:80]


def test_visible_row_count_stat_exists(section: str) -> None:
    assert 'id="p251f-stats-count"' in section
    assert "可見筆數 " in section


def test_distinct_lottery_artifact_only_lifecycle_stats_exist(section: str) -> None:
    assert 'id="p251f-stats-lottery-count"' in section
    assert 'id="p251f-stats-artifact-only-count"' in section
    assert 'id="p251f-stats-lifecycle-breakdown"' in section
    assert "function computeVisibleStats(rows)" in section
    assert "lotterySet[r.lottery_type] = true" in section
    assert "if (r.artifact_only_flag) artifactOnlyCount++;" in section
    assert "r.current_registry_lifecycle_status || 'UNKNOWN'" in section


def test_stats_tied_to_visible_rows_not_raw_data(section: str) -> None:
    assert "function renderVisibleStats()" in section
    assert "computeVisibleStats(lastVisibleRows)" in section
    assert "lastVisibleRows = rows;\n              renderVisibleStats();" in section
    assert "data.strategy_rows" not in section.split("function computeVisibleStats(rows)")[1][:600]


def test_zero_state_and_missing_field_handling(section: str) -> None:
    assert "(rows || []).forEach" in section
    assert "(rows || []).length" in section
    assert "無可見資料" in section


def test_export_visible_ui_remains(section: str) -> None:
    for marker in (
        'id="p251f-export-visible-results"',
        'id="p251f-export-status"',
        'id="p251f-export-fallback"',
        "function exportVisibleResults()",
        "function buildVisibleResultsCsv()",
    ):
        assert marker in section


def test_share_link_ui_remains(section: str) -> None:
    for marker in (
        'id="p251f-copy-share-link"',
        'id="p251f-share-status"',
        'id="p251f-share-url-fallback"',
        "function copyShareLink()",
    ):
        assert marker in section


def test_url_state_behavior_remains(section: str) -> None:
    for marker in (
        "function readDashboardUrlState()",
        "function applyDashboardUrlState(state, d)",
        "function updateDashboardUrlState()",
        "var URL_KEYS =",
    ):
        assert marker in section


def test_prior_dashboard_ui_remains(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-clear-filters"',
        'id="p251f-active-filters"',
        '<details class="p251f-card-details">',
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section


def test_endpoint_and_overclaim_disclaimer_unchanged(section: str) -> None:
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
