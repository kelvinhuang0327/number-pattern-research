"""Focused static tests for P522L_FAST search match badges and clear action."""

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


def test_accessible_clear_search_control_exists(section: str) -> None:
    assert 'id="p251f-clear-search"' in section
    assert 'aria-label="清除證據儀表板關鍵字搜尋"' in section
    assert ">清除搜尋</button>" in section
    assert "clearSearch.disabled = !keyword" in section


def test_clear_search_resets_keyword_and_renders_visible_results(section: str) -> None:
    clear_handler = section.split("clearSearch.addEventListener('click'")[1][:300]
    assert "keyword.value = '';" in clear_handler
    assert "keyword.focus();" in clear_handler
    assert "renderRows();" in clear_handler
    assert "updateDashboardUrlState();" in section
    assert "url.searchParams.delete(URL_KEYS.keyword)" in section
    assert "var url = new URL(window.location.href)" in section


def test_safe_visible_match_badges_exist_for_rows_and_cards(section: str) -> None:
    assert "function matchBadge(keyword, matched)" in section
    assert 'class="p251f-search-match-badge"' in section
    assert 'aria-label="符合搜尋關鍵字"' in section
    assert "matchBadge(keyword, matchesKeyword(c, keyword))" in section
    assert "matchBadge(keyword, true)" in section


def test_match_badges_depend_only_on_existing_loaded_text(section: str) -> None:
    assert "function collectSearchText(value, parts)" in section
    assert "if (typeof value === 'string') parts.push(value);" in section
    assert "value && typeof value === 'object'" in section
    assert "function matchesKeyword(record, keyword)" in section
    assert "return matchesKeyword(r, keyword);" in section
    match_badge = section.split("function matchBadge(keyword, matched)")[1].split(
        "function supportedValue"
    )[0]
    assert "innerHTML" not in match_badge
    assert "+ keyword +" not in match_badge


def test_existing_search_and_url_state_remain(section: str) -> None:
    for marker in (
        'id="p251f-keyword-search"',
        "keyword.addEventListener('input', renderRows)",
        "keyword: 'evidence_search'",
        "keyword: params.get(URL_KEYS.keyword) || ''",
        "url.searchParams.set(URL_KEYS.keyword, keyword)",
        "window.history.replaceState(null, '', url.toString())",
    ):
        assert marker in section


def test_existing_integrations_and_no_overclaim_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-visible-stats"',
        'id="p251f-export-visible-results"',
        "lastVisibleRows = rows;",
        "lastVisibleRows.forEach(function (r)",
        'id="p251f-copy-share-link"',
        '<details class="p251f-card-details">',
        "沒有符合目前篩選條件的歷史證據結果",
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
