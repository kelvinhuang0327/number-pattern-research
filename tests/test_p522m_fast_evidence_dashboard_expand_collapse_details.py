"""Focused static tests for P522M_FAST expand/collapse visible card details."""

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


def test_expand_all_details_control_exists(section: str) -> None:
    assert 'id="p251f-expand-all-details"' in section
    assert ">展開全部明細</button>" in section
    assert "expandAllDetails.addEventListener('click'" in section


def test_collapse_all_details_control_exists(section: str) -> None:
    assert 'id="p251f-collapse-all-details"' in section
    assert ">收合全部明細</button>" in section
    assert "collapseAllDetails.addEventListener('click'" in section


def test_controls_open_and_close_currently_rendered_details(section: str) -> None:
    assert "function setVisibleDetailsOpen(open)" in section
    assert "setVisibleDetailsOpen(true);" in section
    assert "setVisibleDetailsOpen(false);" in section
    assert "detail.open = open;" in section


def test_behavior_targets_visible_dom_details_and_is_safe_when_empty(section: str) -> None:
    helper = section.split("function setVisibleDetailsOpen(open)")[1].split(
        "function renderRows()"
    )[0]
    assert "el('p251f-lottery-cards')" in helper
    assert "if (!box) return;" in helper
    assert "box.querySelectorAll('details.p251f-card-details')" in helper
    assert "data." not in helper
    assert "fetch(" not in helper
    assert "URL" not in helper


def test_existing_search_and_card_details_remain(section: str) -> None:
    for marker in (
        '<details class="p251f-card-details">',
        'id="p251f-keyword-search"',
        'id="p251f-clear-search"',
        'class="p251f-search-match-badge"',
        "function matchesKeyword(record, keyword)",
        "keyword: 'evidence_search'",
    ):
        assert marker in section


def test_existing_integrations_endpoint_and_no_overclaim_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-visible-stats"',
        'id="p251f-export-visible-results"',
        'id="p251f-copy-share-link"',
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
