"""Focused static tests for the P523A_FAST stale snapshot warning banner."""

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


def test_warning_banner_exists_and_is_hidden_by_default(section: str) -> None:
    banner = re.search(
        r'<div id="p251f-stale-snapshot-warning"[^>]*>', section
    )
    assert banner, "stale snapshot warning banner not found"
    assert 'role="note"' in banner.group(0)
    assert " hidden" in banner.group(0)


def test_warning_helper_reads_and_escapes_artifact_message(section: str) -> None:
    helper = section.split("function renderStaleSnapshotWarning(d)")[1].split(
        "function num(v)"
    )[0]
    assert "d.stale_snapshot_warning" in helper
    assert "warning.message" in helper
    assert "typeof warning.message === 'string'" in helper
    assert "warning.message.trim()" in helper
    assert "esc(message)" in helper


def test_missing_empty_or_malformed_warning_remains_hidden(section: str) -> None:
    helper = section.split("function renderStaleSnapshotWarning(d)")[1].split(
        "function num(v)"
    )[0]
    assert ": '';" in helper
    assert "box.innerHTML = message ?" in helper
    assert "box.hidden = !message;" in helper
    assert "renderStaleSnapshotWarning(d);" in section


def test_existing_dashboard_behaviors_and_disclaimers_remain(section: str) -> None:
    for marker in (
        'id="p251f-keyword-search"',
        'id="p251f-expand-all-details"',
        'id="p251f-collapse-all-details"',
        'id="p251f-copy-share-link"',
        'id="p251f-export-visible-results"',
        'id="p251f-visible-stats"',
        'id="evidence-dashboard"',
        "var ROUTE = '/api/replay/evidence-dashboard'",
        "不宣稱預測優勢",
        "不晉級策略",
        "不提供實際行動指引",
    ):
        assert marker in section


def test_warning_helper_does_not_add_a_fetch(section: str) -> None:
    helper = section.split("function renderStaleSnapshotWarning(d)")[1].split(
        "function num(v)"
    )[0]
    assert "fetch(" not in helper
    assert section.count("fetch(") == 1
