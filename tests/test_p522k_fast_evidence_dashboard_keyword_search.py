"""Focused static tests for P522K_FAST evidence dashboard keyword search."""

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


def test_accessible_keyword_search_control_exists(section: str) -> None:
    assert 'for="p251f-keyword-search"' in section
    assert 'id="p251f-keyword-search"' in section
    assert 'type="search"' in section
    assert 'aria-label="搜尋證據儀表板結果"' in section


def test_search_reads_loaded_string_fields_and_handles_missing_values(section: str) -> None:
    assert "function collectSearchText(value, parts)" in section
    assert "if (typeof value === 'string') parts.push(value);" in section
    assert "Array.isArray(value)" in section
    assert "value && typeof value === 'object'" in section
    assert "Object.keys(value)" in section
    assert "matchesKeyword(r, keyword)" in section
    for field in (
        "r.lottery_type",
        "r.strategy_id",
        "r.current_registry_lifecycle_status",
        "r.historical_snapshot_lifecycle_status",
        "state.status_note",
        "r.latest_classification",
    ):
        assert field in section


def test_search_is_case_insensitive_and_filters_rows_and_cards(section: str) -> None:
    assert "function matchesKeyword(record, keyword)" in section
    assert "collectSearchText(record).toLocaleLowerCase().indexOf(keyword)" in section
    assert ".trim().toLocaleLowerCase()" in section
    assert "return matchesKeyword(r, keyword);" in section
    assert "return matchesKeyword(c, keyword) || !!visibleLotteries[c.lottery_type];" in section


def test_search_uses_visible_rows_stats_count_and_export_pipeline(section: str) -> None:
    search_filter = section.index("return matchesKeyword(r, keyword);")
    visible_assignment = section.index("lastVisibleRows = rows;")
    assert search_filter < visible_assignment
    assert "renderVisibleStats();" in section[visible_assignment : visible_assignment + 250]
    assert "lastVisibleRows.forEach(function (r)" in section
    assert "rows.length + ' 筆；彩種卡 ' + visibleCardCount" in section


def test_search_integrates_with_filters_sort_reset_and_empty_state(section: str) -> None:
    assert "keyword.addEventListener('input', renderRows)" in section
    assert "if (keyword) filters.push('關鍵字：' + keyword);" in section
    assert "if (keyword) keyword.value = '';" in section
    assert "if (lottery && r.lottery_type !== lottery) return false;" in section
    assert "if (artifactOnly && !r.artifact_only_flag) return false;" in section
    assert "if (sort !== 'default')" in section
    assert "沒有符合目前篩選條件的歷史證據結果" in section


def test_search_url_state_preserves_share_link_behavior(section: str) -> None:
    assert "keyword: 'evidence_search'" in section
    assert "keyword: params.get(URL_KEYS.keyword) || ''" in section
    assert "url.searchParams.set(URL_KEYS.keyword, keyword)" in section
    assert "url.searchParams.delete(URL_KEYS.keyword)" in section
    assert "new URL(window.location.href)" in section
    assert "var url = window.location.href;" in section


def test_prior_dashboard_features_endpoint_and_disclaimer_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-clear-filters"',
        '<details class="p251f-card-details">',
        'id="p251f-copy-share-link"',
        'id="p251f-export-visible-results"',
        'id="p251f-visible-stats"',
        'id="evidence-dashboard"',
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
