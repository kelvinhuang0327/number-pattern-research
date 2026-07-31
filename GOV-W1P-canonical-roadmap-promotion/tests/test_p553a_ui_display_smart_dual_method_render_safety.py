"""P553A focused static tests for smart dual-bet method render safety.

No DB, no service startup, no runtime artifacts: these assertions verify the
client renders the API-provided method label as text instead of HTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DISPLAY_HANDLER_JS = REPO_ROOT / "src" / "core" / "handlers" / "UIDisplayHandler.js"


def _smart_dual_bet_helper() -> str:
    script = UI_DISPLAY_HANDLER_JS.read_text(encoding="utf-8")
    return script.split("    displaySmartDualBetResult(result) {", 1)[1].split(
        "\n    /**\n     * 顯示下一期預測結果",
        1,
    )[0]


def test_smart_dual_bet_method_uses_dom_text_rendering() -> None:
    helper = _smart_dual_bet_helper()

    assert "methodDiv.textContent = '';" in helper
    assert "methodDiv.appendChild(document.createTextNode('使用策略：'));" in helper
    assert "const methodName = document.createElement('strong');" in helper
    assert "methodName.textContent = String(result.method ?? '');" in helper
    assert "methodDiv.appendChild(methodName);" in helper
    assert "methodDiv.appendChild(document.createTextNode(`${specialNote} | 基於全部歷史數據分析`));" in helper


def test_smart_dual_bet_method_does_not_interpolate_api_string_into_html() -> None:
    helper = _smart_dual_bet_helper()

    assert "methodDiv.innerHTML" not in helper
    assert "<strong>${result.method}</strong>" not in helper


def test_render_safety_fix_does_not_add_dependency_or_runtime_behavior() -> None:
    helper = _smart_dual_bet_helper()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
    ):
        assert forbidden not in helper
