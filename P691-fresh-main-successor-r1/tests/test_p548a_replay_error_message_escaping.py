"""Focused static tests for replay table error-message escaping.

P548A scope: no DB, no service startup, no route changes. These assertions
cover the existing replay history/summary fallback rows that render exception
messages through innerHTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _replay_script() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return html.split("// P23a: Multi-fetch up to N records", 1)[1].split(
        "// Init event listeners", 1
    )[0]


def test_replay_error_fallbacks_escape_exception_messages():
    script = _replay_script()

    assert "function rpEscapeHtml" in INDEX_HTML.read_text(encoding="utf-8")
    assert script.count("rpEscapeHtml(e.message)") >= 3

    for unsafe_pattern in (
        "錯誤：${e.message}",
        "錯誤：${ e.message",
        "錯誤：${(e.message",
    ):
        assert unsafe_pattern not in script


def test_replay_error_escaping_does_not_add_fetches_or_mutations():
    script = _replay_script()

    assert "method:" not in script
    for forbidden in ("POST", "PUT", "PATCH", "DELETE", "lottery_v2.db", "sqlite"):
        assert forbidden not in script
