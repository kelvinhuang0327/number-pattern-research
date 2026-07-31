"""Focused static tests for P522B evidence dashboard UX states."""

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


def test_loading_state_is_visible_and_accessible(section: str) -> None:
    assert 'id="p251f-loading"' in section
    assert 'role="status"' in section
    assert 'aria-live="polite"' in section
    assert "正在載入證據儀表板，請稍候" in section
    assert "setLoading(true)" in section


def test_empty_state_describes_filtered_historical_results(section: str) -> None:
    assert 'id="p251f-empty"' in section
    assert "沒有符合目前篩選條件的歷史證據結果" in section
    assert "empty.style.display = rows.length ? 'none' : ''" in section


def test_error_state_and_invalid_payload_handling_exist(section: str) -> None:
    assert 'id="p251f-error"' in section
    assert 'role="alert"' in section
    assert 'id="p251f-error-message"' in section
    assert "證據儀表板載入失敗" in section
    assert "validatePayload" in section
    assert "伺服器回應格式無效" in section


def test_retry_reuses_readonly_evidence_dashboard_load(section: str) -> None:
    assert 'id="p251f-retry"' in section
    assert "重新載入" in section
    assert "retry.addEventListener('click', load)" in section
    assert "var ROUTE = '/api/replay/evidence-dashboard'" in section
    assert "fetch((window.API_BASE || '') + ROUTE)" in section
    assert section.count("/api/replay/evidence-dashboard") == 2


def test_no_overclaim_copy_remains(section: str) -> None:
    for text in (
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
        "不查詢 DB",
        "不修改 registry",
    ):
        assert text in section

    for banned in ("最佳策略", "推薦下注", "建議下注", "投注建議", "保證中獎", "提高中獎率"):
        assert banned not in section
