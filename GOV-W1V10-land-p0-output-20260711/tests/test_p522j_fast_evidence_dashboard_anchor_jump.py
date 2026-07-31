"""Focused static tests for the P522J_FAST dashboard anchor and quick jump."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def section(html: str) -> str:
    match = re.search(
        r"<!-- ===== P251F: Evidence Dashboard UI.*?<!-- ===== END P251F =====",
        html,
        re.DOTALL,
    )
    assert match, "P251F evidence dashboard section not found"
    return match.group(0)


def test_stable_focusable_dashboard_anchor_exists_once(html: str, section: str) -> None:
    assert html.count('id="evidence-dashboard"') == 1
    assert '<h2 id="evidence-dashboard" tabindex="-1">' in section


def test_visible_quick_jump_targets_dashboard_anchor(html: str) -> None:
    quick_jump = re.search(r'<a id="p251f-quick-jump"[^>]*>', html)
    assert quick_jump, "Evidence Dashboard quick-jump link not found"
    control = quick_jump.group(0)
    assert 'href="#evidence-dashboard"' in control
    assert 'data-section="p251-evidence-dashboard"' in control
    assert 'aria-controls="p251-evidence-dashboard-section"' in control


def test_hash_navigation_reveals_and_focuses_dashboard(section: str) -> None:
    assert "function activateDashboardAnchor()" in section
    assert "window.location.hash !== '#evidence-dashboard'" in section
    assert "section.id === SEC + '-section'" in section
    assert "target.focus({ preventScroll: true });" in section
    assert "target.scrollIntoView();" in section
    assert "window.addEventListener('hashchange', activateDashboardAnchor)" in section


def test_query_state_and_share_link_remain_compatible(section: str) -> None:
    for marker in (
        "new URL(window.location.href)",
        "window.history.replaceState(null, '', url.toString())",
        "var url = window.location.href;",
        "function copyShareLink()",
        'id="p251f-copy-share-link"',
    ):
        assert marker in section


def test_prior_dashboard_features_and_endpoint_remain(section: str) -> None:
    for marker in (
        'id="p251f-visible-stats"',
        'id="p251f-export-visible-results"',
        'id="p251f-copy-share-link"',
        "function readDashboardUrlState()",
        "var ROUTE = '/api/replay/evidence-dashboard'",
    ):
        assert marker in section


def test_no_overclaim_copy_remains(section: str) -> None:
    for marker in ("不宣稱預測優勢", "不晉級策略", "不提供實際行動指引"):
        assert marker in section
    assert "提高中獎率" not in section
