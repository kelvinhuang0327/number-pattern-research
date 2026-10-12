"""Focused static tests for P522D evidence dashboard filter summary and reset."""

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


def test_active_filter_summary_and_chips_are_accessible(section: str) -> None:
    assert 'id="p251f-active-filters"' in section
    assert 'class="p251f-filter-chip"' in section
    assert "function renderActiveFilters()" in section
    assert "啟用中的篩選" in section
    assert "顯示全部證據（無啟用中的篩選）" in section
    assert 'role="status"' in section
    assert 'aria-live="polite"' in section


def test_clear_filters_resets_filter_defaults_and_rerenders(section: str) -> None:
    assert 'id="p251f-clear-filters"' in section
    assert "清除篩選" in section
    assert "lottery.value = ''" in section
    assert "lifecycle.value = ''" in section
    assert "artifactOnly.checked = false" in section
    assert "clear.addEventListener('click'" in section
    assert "renderRows();" in section


def test_filtered_empty_state_references_clearing_filters(section: str) -> None:
    assert "沒有符合目前篩選條件的歷史證據結果" in section
    assert "清除篩選後可能會顯示其他結果" in section


def test_prior_sort_count_and_ux_states_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        "目前顯示",
        "正在載入證據儀表板，請稍候",
        "證據儀表板載入失敗",
        'id="p251f-retry"',
        "重新載入",
    ):
        assert marker in section


def test_endpoint_and_no_overclaim_copy_remain(section: str) -> None:
    assert "var ROUTE = '/api/replay/evidence-dashboard'" in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    for marker in ("不宣稱預測優勢", "不晉級策略", "不提供實際行動指引"):
        assert marker in section
    assert "提高中獎率" not in section
