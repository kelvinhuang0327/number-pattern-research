"""Focused static tests for P522F evidence dashboard URL state."""

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


def test_supported_dashboard_query_keys_are_explicit(section: str) -> None:
    assert "var URL_KEYS =" in section
    for key in (
        "evidence_lottery",
        "evidence_lifecycle",
        "evidence_artifact_only",
        "evidence_sort",
    ):
        assert f"'{key}'" in section


def test_page_load_reads_and_safely_validates_url_state(section: str) -> None:
    assert "function readDashboardUrlState()" in section
    assert "new URLSearchParams(window.location.search)" in section
    assert "function supportedValue(value, supported, fallback)" in section
    assert "var LOTTERY_VALUES =" in section
    assert "var SORT_VALUES =" in section
    assert "catch (e)" in section
    assert "applyDashboardUrlState(initialUrlState, null)" in section
    assert "applyDashboardUrlState(initialUrlState, d)" in section


def test_filter_and_sort_changes_replace_url_without_reload(section: str) -> None:
    assert "function updateDashboardUrlState()" in section
    assert "new URL(window.location.href)" in section
    assert ".searchParams.set(URL_KEYS." in section
    assert "window.history.replaceState(null, '', url.toString())" in section
    assert "addEventListener('change', renderRows)" in section
    assert "updateDashboardUrlState();" in section
    assert "window.location.reload" not in section


def test_clear_filters_removes_filter_keys_and_preserves_sort(section: str) -> None:
    for marker in (
        "lottery.value = ''",
        "lifecycle.value = ''",
        "artifactOnly.checked = false",
        "url.searchParams.delete(URL_KEYS.lottery)",
        "url.searchParams.delete(URL_KEYS.lifecycle)",
        "url.searchParams.delete(URL_KEYS.artifactOnly)",
        "sort !== 'default' ? url.searchParams.set(URL_KEYS.sort, sort)",
    ):
        assert marker in section


def test_unknown_params_are_preserved_and_invalid_values_fall_back(section: str) -> None:
    assert "Unknown query parameters are preserved" in section
    assert "supportedValue(params.get(URL_KEYS.lottery)" in section
    assert "supportedValue(params.get(URL_KEYS.sort)" in section
    assert "supportedValue(state.lifecycle, lifecycleValues, '')" in section
    assert "url.searchParams =" not in section


def test_prior_dashboard_behavior_endpoint_and_copy_remain(section: str) -> None:
    for marker in (
        'id="p251f-sort"',
        'id="p251f-result-count"',
        'id="p251f-active-filters"',
        'id="p251f-clear-filters"',
        '<details class="p251f-card-details">',
        "目前顯示",
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section
    assert section.count("/api/replay/evidence-dashboard") == 2
    assert "提高中獎率" not in section
