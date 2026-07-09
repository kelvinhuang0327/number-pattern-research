"""P561A focused static tests for UIManager stats render safety.

No DB, no service startup, no runtime artifacts: these assertions cover the
API-derived stats values that UIManager writes through innerHTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
UI_MANAGER_JS = REPO_ROOT / "src" / "ui" / "UIManager.js"


def _ui_manager() -> str:
    return UI_MANAGER_JS.read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    script = _ui_manager()
    return script.split(f"    {name}(", 1)[1].split(f"\n    {next_name}(", 1)[0]


def test_ui_manager_has_local_html_escape_helper() -> None:
    script = _ui_manager()

    assert "    _escapeHtml(value) {" in script
    assert "String(value ?? '').replace(/[&<>\"']/g" in script
    for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert escaped in script


def test_data_summary_escapes_api_stats_before_inner_html() -> None:
    method = _method("updateDataSummary", "updateHistoryTable")

    assert "${this._escapeHtml(stats.totalDraws)}" in method
    assert "${this._escapeHtml(stats.dateRange.start)}" in method
    assert "${this._escapeHtml(stats.dateRange.end)}" in method
    assert "${this._escapeHtml(stats.latestDraw)}" in method

    for unsafe in (
        "${stats.totalDraws}",
        "${stats.dateRange.start}",
        "${stats.dateRange.end}",
        "${stats.latestDraw}",
    ):
        assert unsafe not in method


def test_lottery_selector_counts_escape_api_stats_before_inner_html() -> None:
    card_method = _method("updateLotteryTypeSelector", "updateCurrentGameBadge")
    dropdown_method = _method("populateGameSelector", "updateDataSummary")

    assert "${this._escapeHtml(count)} 期" in card_method
    assert "${this._escapeHtml(count)} 期" in dropdown_method
    assert "${count} 期" not in card_method
    assert "${count} 期" not in dropdown_method


def test_ui_manager_stats_render_safety_does_not_add_runtime_or_data_behavior() -> None:
    changed_methods = "\n".join(
        [
            _method("updateLotteryTypeSelector", "updateCurrentGameBadge"),
            _method("populateGameSelector", "updateDataSummary"),
            _method("updateDataSummary", "updateHistoryTable"),
        ]
    )

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in changed_methods
