"""Focused static tests for P522E evidence dashboard card details."""

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


def test_each_lottery_card_renders_collapsed_accessible_details(section: str) -> None:
    assert '<details class="p251f-card-details">' in section
    assert "<summary>查看 " in section
    assert " 證據明細</summary>" in section
    assert '<details class="p251f-card-details" open>' not in section
    assert "(d.lottery_cards || []).filter" in section
    assert "box.innerHTML = cards.map" in section


def test_details_expose_only_artifact_backed_card_fields(section: str) -> None:
    for field in (
        "card_title",
        "replay_strategy_entries",
        "distinct_replay_draws",
        "artifact_only_rows_visible",
        "visible_by_default",
        "lifecycle_visibility_rule",
        "summary_notes",
    ):
        assert f"c.{field}" in section
    for label in (
        "Evidence label",
        "Replay strategies",
        "Distinct replay draws",
        "Summary notes",
    ):
        assert label in section


def test_missing_details_use_safe_neutral_fallback(section: str) -> None:
    assert "function detailValue(v)" in section
    assert "function detailNotes(notes)" in section
    assert "No additional details available." in section
    assert 'class="p251f-no-additional-details"' in section
    assert "esc(note)" in section


def test_prior_dashboard_controls_and_states_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        "目前顯示",
        'id="p251f-active-filters"',
        'id="p251f-clear-filters"',
        "清除篩選",
        "正在載入證據儀表板，請稍候",
        "沒有符合目前篩選條件的歷史證據結果",
        "證據儀表板載入失敗",
        'id="p251f-retry"',
        "重新載入",
        "伺服器回應格式無效",
    ):
        assert marker in section


def test_endpoint_and_no_overclaim_copy_remain(section: str) -> None:
    assert "var ROUTE = '/api/replay/evidence-dashboard'" in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    for marker in ("不宣稱預測優勢", "不晉級策略", "不提供實際行動指引"):
        assert marker in section
    assert "提高中獎率" not in section
