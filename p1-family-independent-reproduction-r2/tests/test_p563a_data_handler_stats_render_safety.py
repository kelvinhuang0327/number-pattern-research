"""P563A focused static tests for DataHandler stats render safety.

No DB, no service startup, no runtime artifacts: these assertions cover the
IndexedDB/backend-derived stats values that DataHandler writes through
innerHTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_HANDLER_JS = REPO_ROOT / "src" / "core" / "handlers" / "DataHandler.js"


def _script() -> str:
    return DATA_HANDLER_JS.read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    script = _script()
    return script.split(f"    {name}(", 1)[1].split(f"\n    {next_name}(", 1)[0]


def _show_lottery_type_selector_method() -> str:
    script = _script()
    return script.split("    showLotteryTypeSelector(stats) {", 1)[1].split(
        "\n    /**\n     * 清除所有數據", 1
    )[0]


def test_data_handler_has_local_html_escape_helper() -> None:
    script = _script()

    assert "    _escapeHtml(value) {" in script
    assert "String(value ?? '').replace(/[&<>\"']/g" in script
    for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert escaped in script


def test_indexeddb_summary_values_escape_before_inner_html() -> None:
    method = _method("updateDataSummaryFromStats", "showLotteryTypeSelector")

    assert "${this._escapeHtml(stats.total.toLocaleString())}" in method
    assert "${this._escapeHtml(Object.keys(stats.byType).length)} 種" in method
    assert "${this._escapeHtml(typeNames[type] || type)}" in method
    assert "${this._escapeHtml(count.toLocaleString())} 筆" in method

    for unsafe in (
        "${stats.total.toLocaleString()}",
        "${Object.keys(stats.byType).length} 種",
        "${typeNames[type] || type}",
        "${count.toLocaleString()} 筆",
    ):
        assert unsafe not in method


def test_lottery_type_selector_values_escape_before_inner_html() -> None:
    method = _show_lottery_type_selector_method()

    assert 'data-type="${this._escapeHtml(type)}"' in method
    assert "${this._escapeHtml(info.icon)}" in method
    assert "${this._escapeHtml(info.name)}" in method
    assert "${this._escapeHtml(count.toLocaleString())} 筆數據" in method

    for unsafe in (
        'data-type="${type}"',
        "${info.icon}",
        "${info.name}",
        "${count.toLocaleString()} 筆數據",
    ):
        assert unsafe not in method


def test_data_handler_render_safety_does_not_add_runtime_or_data_behavior() -> None:
    changed_methods = "\n".join(
        [
            _method("updateDataSummaryFromStats", "showLotteryTypeSelector"),
            _show_lottery_type_selector_method(),
        ]
    )

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
    ):
        assert forbidden not in changed_methods
