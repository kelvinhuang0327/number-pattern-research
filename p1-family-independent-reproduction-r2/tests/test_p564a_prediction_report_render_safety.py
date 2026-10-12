"""P564A focused static tests for single-prediction report render safety.

No DB, no service startup, no runtime artifacts: these assertions verify the
general single-prediction report escapes API-provided report strings before
writing the small HTML wrapper used for labels and line breaks.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_JS = REPO_ROOT / "src" / "core" / "App.js"
UI_DISPLAY_HANDLER_JS = REPO_ROOT / "src" / "core" / "handlers" / "UIDisplayHandler.js"


def _script(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _display_prediction_result(path: Path) -> str:
    script = _script(path)
    return script.split("    displayPredictionResult(result) {", 1)[1].split(
        "\n    async displayHistory" if path == APP_JS else "\n    /**\n     * 顯示雙注預測結果",
        1,
    )[0]


def test_active_app_prediction_report_has_local_escape_helper() -> None:
    script = _script(APP_JS)

    assert "    _escapePredictionReportHtml(value) {" in script
    assert "String(value ?? '').replace(/[&<>\"']/g" in script
    for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert escaped in script


def test_active_app_prediction_report_escapes_api_strings_before_inner_html() -> None:
    method = _display_prediction_result(APP_JS)

    assert "${this._escapePredictionReportHtml(result.method)}" in method
    assert "result.details.map(detail => this._escapePredictionReportHtml(detail)).join('<br>')" in method
    assert "${this._escapePredictionReportHtml(result.report || '分析完成')}" in method
    assert "${result.method}" not in method
    assert "${result.report || '分析完成'}" not in method
    assert "result.details.join('<br>')" not in method


def test_handler_prediction_report_matches_active_app_escape_contract() -> None:
    method = _display_prediction_result(UI_DISPLAY_HANDLER_JS)

    assert "${this._escapePredictionReportHtml(result.method)}" in method
    assert "result.details.map(detail => this._escapePredictionReportHtml(detail)).join('<br>')" in method
    assert "${this._escapePredictionReportHtml(result.report || '分析完成')}" in method
    assert "${result.method}" not in method
    assert "${result.report || '分析完成'}" not in method
    assert "result.details.join('<br>')" not in method


def test_prediction_report_fix_does_not_add_runtime_or_data_behavior() -> None:
    combined = "\n".join(
        _display_prediction_result(path) for path in (APP_JS, UI_DISPLAY_HANDLER_JS)
    )

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
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
        assert forbidden not in combined
