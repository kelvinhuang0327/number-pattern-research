"""Static tests for the P251F evidence dashboard UI."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


@pytest.fixture(scope="module")
def html_text() -> str:
    assert INDEX_HTML.exists(), f"index.html missing: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def section(html_text: str) -> str:
    match = re.search(
        r"<!-- ===== P251F: Evidence Dashboard UI.*?<!-- ===== END P251F =====",
        html_text,
        re.DOTALL,
    )
    assert match, "P251F evidence dashboard section not found"
    return match.group(0)


def test_nav_button_present(html_text: str) -> None:
    assert 'data-section="p251-evidence-dashboard"' in html_text
    assert "證據儀表板" in html_text


def test_section_present(section: str) -> None:
    assert 'id="p251-evidence-dashboard-section"' in section
    assert "Evidence Dashboard (artifact-backed)" in section


def test_ui_uses_readonly_artifact_api_route(section: str) -> None:
    assert "/api/replay/evidence-dashboard" in section
    assert "fetch((window.API_BASE || '') + ROUTE)" in section


def test_ui_has_expected_filters(section: str) -> None:
    for marker in (
        'id="p251f-filter-lottery"',
        'id="p251f-filter-lifecycle"',
        'id="p251f-filter-artifact-only"',
        "BIG_LOTTO",
        "DAILY_539",
        "POWER_LOTTO",
    ):
        assert marker in section


def test_ui_preserves_no_exclusion_default_semantics(section: str) -> None:
    assert "生命週期只作為標籤與篩選，不作為預設排除規則" in section
    assert "include_all_rows=true" in section
    assert "exclude_by_lifecycle=false" in section
    assert "lifecycle_filtered=" in section


def test_ui_exposes_core_payload_fields(section: str) -> None:
    for marker in (
        "current_registry_entries",
        "historical_inventory_entries",
        "artifact_only_entries",
        "replay_rows_total",
        "draw_rows_total",
        "strategy_rows",
        "lottery_cards",
        "lifecycle_filter_options",
    ):
        assert marker in section


def test_ui_no_overclaim_copy(section: str) -> None:
    assert "不宣稱預測優勢" in section
    assert "不晉級策略" in section
    assert "不提供實際行動指引" in section
    assert "不查詢 DB" in section
    assert "不修改 registry" in section

    for banned in ("最佳策略", "推薦下注", "建議下注", "投注建議", "保證中獎", "提高中獎率"):
        assert banned not in section
