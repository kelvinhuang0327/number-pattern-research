"""Focused static tests for AutoFetchManager status live-region semantics."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
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

