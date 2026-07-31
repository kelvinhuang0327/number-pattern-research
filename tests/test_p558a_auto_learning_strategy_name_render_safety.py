"""P558A focused static tests for AutoLearning strategy-name render safety."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
AUTO_LEARNING_JS = REPO_ROOT / "src" / "ui" / "AutoLearningManager.js"


def _script() -> str:
    return AUTO_LEARNING_JS.read_text(encoding="utf-8")


def _evaluate_all_strategies_helper() -> str:
    script = _script()
    return script.split("async runStrategyEvaluation() {", 1)[1].split(
        "\n    /**\n     * 🆕 生成雙注優化預測", 1
    )[0]


def _dual_bet_prediction_helper() -> str:
    script = _script()
    return script.split("async generateDualBetPrediction(lotteryType, bestStrategy) {", 1)[
        1
    ].split("\n    /**\n     * 🚀 執行多階段優化", 1)[0]


def test_auto_learning_has_local_strategy_name_escape_helper() -> None:
    script = _script()

    assert "function autoLearningEscapeHtml(value)" in script
    assert "String(value ?? '').replace(/[&<>\"']/g" in script
    for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert escaped in script


def test_evaluate_all_strategies_escapes_names_before_html_templates() -> None:
    helper = _evaluate_all_strategies_helper()
    html_render_region = helper.split("allTable.innerHTML = tableHTML;", 1)[0]

    assert "const bestStrategyName = autoLearningEscapeHtml(best.strategy_name);" in helper
    assert "${bestStrategyName}" in html_render_region
    assert "${best.strategy_name}" not in html_render_region
    assert "const strategyName = autoLearningEscapeHtml(data.name);" in helper
    assert "${strategyName}" in html_render_region
    assert "${data.name}" not in html_render_region


def test_dual_bet_report_escapes_best_strategy_name_before_inner_html() -> None:
    helper = _dual_bet_prediction_helper()

    assert "const strategyName = autoLearningEscapeHtml(bestStrategy.strategy_name);" in helper
    assert "<strong>${strategyName}</strong>" in helper
    assert "${bestStrategy.strategy_name}" not in helper


def test_render_safety_fix_does_not_add_runtime_or_data_behavior() -> None:
    helper = _evaluate_all_strategies_helper() + _dual_bet_prediction_helper()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "DELETE",
        "PUT",
        "PATCH",
    ):
        assert forbidden not in helper
