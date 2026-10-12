"""Focused static tests for P522H_FAST evidence dashboard visible export."""

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


def test_export_visible_results_control_exists(section: str) -> None:
    assert 'id="p251f-export-visible-results"' in section
    assert "匯出目前顯示結果" in section
    assert 'aria-label="匯出目前顯示的證據儀表板結果"' in section


def test_export_status_and_fallback_elements_exist(section: str) -> None:
    assert 'id="p251f-export-status"' in section
    assert 'role="status"' in section.split('id="p251f-export-status"')[1][:80]
    assert 'id="p251f-export-fallback"' in section
    assert 'readonly' in section.split('id="p251f-export-fallback"')[1][:80]


def test_client_side_csv_generation_exists(section: str) -> None:
    assert "function buildVisibleResultsCsv()" in section
    assert "function csvEscape(v)" in section
    for header_field in (
        "'lottery_type'", "'strategy_id'",
        "'current_registry_lifecycle_status'", "'historical_snapshot_lifecycle_status'",
        "'replay_rows'", "'distinct_target_draws'", "'status_note'",
        "'default_visible'", "'lifecycle_filtered'",
    ):
        assert header_field in section
    assert '/[",\\n]/.test(s)' in section


def test_export_uses_currently_visible_filtered_sorted_rows(section: str) -> None:
    assert "var lastVisibleRows = [];" in section
    assert "lastVisibleRows = rows;" in section
    assert "lastVisibleRows.forEach(function (r) {" in section
    assert "function exportVisibleResults()" in section


def test_export_uses_native_blob_and_url_apis_only(section: str) -> None:
    assert "typeof Blob !== 'undefined'" in section
    assert "new Blob([csv]" in section
    assert "URL.createObjectURL(blob)" in section
    assert "URL.revokeObjectURL(blobUrl)" in section
    assert "function showExportFallback(text)" in section
    assert "exportVisible.addEventListener('click', exportVisibleResults)" in section


def test_export_does_not_call_backend_or_mutate_filters(section: str) -> None:
    export_fn = section.split("function exportVisibleResults()")[1].split("function detailValue")[0]
    assert "fetch(" not in export_fn
    assert ".value = ''" not in export_fn
    assert "updateDashboardUrlState" not in export_fn
    assert "history.replaceState" not in export_fn


def test_export_feedback_text_is_non_promotional(section: str) -> None:
    for marker in (
        "已匯出目前顯示的",
        "此瀏覽器不支援自動下載",
    ):
        assert marker in section
    assert "提高中獎率" not in section


def test_prior_dashboard_ui_remains(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-clear-filters"',
        'id="p251f-active-filters"',
        'id="p251f-copy-share-link"',
        'id="p251f-share-status"',
        'id="p251f-share-url-fallback"',
        "function copyShareLink()",
        '<details class="p251f-card-details">',
        "function readDashboardUrlState()",
        "function updateDashboardUrlState()",
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section


def test_endpoint_and_overclaim_disclaimer_unchanged(section: str) -> None:
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
