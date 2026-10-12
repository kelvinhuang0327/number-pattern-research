"""Focused static tests for AutoFetchManager status live-region semantics."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
AUTO_FETCH_JS = REPO_ROOT / "src" / "ui" / "AutoFetchManager.js"


def _status_helper() -> str:
    script = AUTO_FETCH_JS.read_text(encoding="utf-8")
    return script.split("_setStatus(el, type, msg) {", 1)[1].split(
        "\n    }\n\n    _setBtnLoading", 1
    )[0]


def test_status_helper_marks_messages_as_live_regions() -> None:
    helper = _status_helper()

    assert "el.setAttribute('role', type === 'error' ? 'alert' : 'status')" in helper
    assert "el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite')" in helper


def test_status_helper_preserves_existing_visual_and_text_behavior() -> None:
    helper = _status_helper()

    assert "el.className = `af-status af-status--${type}`" in helper
    assert "el.style.display  = 'block'" in helper
    assert "el.style.whiteSpace = 'pre-wrap'" in helper
    assert "el.textContent = msg" in helper


def test_auto_fetch_status_placeholders_are_static_live_regions() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    auto_fetch = html.split('class="af-section"', 1)[1].split(
        '<!-- P535A/G03: fetch-latest write-capable insert confirmation modal -->', 1
    )[0]

    for status_id in (
        "af-source-health-status",
        "af-fetch-status",
        "af-scan-status",
        "af-bf-status",
    ):
        status_markup = auto_fetch.split(f'id="{status_id}"', 1)[1].split(">", 1)[0]
        assert 'class="af-status"' in status_markup
        assert 'role="status"' in status_markup
        assert 'aria-live="polite"' in status_markup
