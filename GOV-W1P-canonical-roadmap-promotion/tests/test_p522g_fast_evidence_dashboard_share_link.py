"""Focused static tests for P522G_FAST evidence dashboard share link."""

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


def test_copy_share_link_control_exists(section: str) -> None:
    assert 'id="p251f-copy-share-link"' in section
    assert "複製分享連結" in section
    assert 'aria-label="複製證據儀表板分享連結"' in section


def test_share_status_and_fallback_elements_exist(section: str) -> None:
    assert 'id="p251f-share-status"' in section
    assert 'role="status"' in section.split('id="p251f-share-status"')[1][:80]
    assert 'id="p251f-share-url-fallback"' in section
    assert 'readonly' in section.split('id="p251f-share-url-fallback"')[1][:80]


def test_clipboard_api_used_with_fallback(section: str) -> None:
    assert "function copyShareLink()" in section
    assert "navigator.clipboard && navigator.clipboard.writeText" in section
    assert "navigator.clipboard.writeText(url)" in section
    assert "function showShareUrlFallback(url)" in section
    assert "input.select()" in section


def test_share_link_uses_current_url_and_query_state(section: str) -> None:
    assert "updateDashboardUrlState();" in section.split("function copyShareLink()")[1][:200]
    assert "var url = window.location.href;" in section
    assert "copyShare.addEventListener('click', copyShareLink)" in section


def test_share_feedback_text_is_non_promotional(section: str) -> None:
    for marker in (
        "已複製目前的證據儀表板分享連結",
        "自動複製失敗",
        "此瀏覽器不支援自動複製",
    ):
        assert marker in section
    assert "提高中獎率" not in section
    assert "中獎機率" not in section.split("function copyShareLink()")[1][:400]


def test_p522f_url_state_behavior_remains(section: str) -> None:
    for marker in (
        "function readDashboardUrlState()",
        "function applyDashboardUrlState(state, d)",
        "function updateDashboardUrlState()",
        "var URL_KEYS =",
        "new URLSearchParams(window.location.search)",
        "window.history.replaceState(null, '', url.toString())",
    ):
        assert marker in section


def test_prior_dashboard_controls_remain(section: str) -> None:
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
