"""Static tests for P522C evidence dashboard sorting and visible counts."""

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


def test_sort_control_has_stable_supported_options(section: str) -> None:
    assert 'id="p251f-sort"' in section
    assert '<option value="default">預設順序</option>' in section
    assert '<option value="lottery-name">彩種／策略名稱</option>' in section
    assert '<option value="status">生命週期／證據狀態</option>' in section
    assert "'p251f-sort'" in section


def test_sort_is_stable_and_tolerates_absent_fields(section: str) -> None:
    assert "function textSortValue(v) { return v == null ? ''" in section
    assert "a.index - b.index" in section
    for field in (
        "lottery_type",
        "strategy_id",
        "current_registry_lifecycle_status",
        "latest_classification",
    ):
        assert field in section


def test_result_count_is_visible_accessible_and_updates(section: str) -> None:
    assert 'id="p251f-result-count"' in section
    assert 'role="status"' in section
    assert 'aria-live="polite"' in section
    assert "已載入證據列" in section
    assert "目前顯示" in section
    assert "彩種卡" in section
    assert "data.strategy_rows.length" in section
    assert "rows.length" in section
    assert "data.lottery_cards.length" in section


def test_count_copy_is_non_promotional(section: str) -> None:
    count_markup = re.search(
        r'<span id="p251f-result-count".*?</span>', section, re.DOTALL
    )
    assert count_markup
    for banned in ("推薦", "下注", "投注", "保證", "提高中獎率"):
        assert banned not in count_markup.group(0)


def test_p522b_states_endpoint_and_no_overclaim_remain(section: str) -> None:
    for marker in (
        "正在載入證據儀表板，請稍候",
        "沒有符合目前篩選條件的歷史證據結果",
        "證據儀表板載入失敗",
        'id="p251f-retry"',
        "重新載入",
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section

    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
