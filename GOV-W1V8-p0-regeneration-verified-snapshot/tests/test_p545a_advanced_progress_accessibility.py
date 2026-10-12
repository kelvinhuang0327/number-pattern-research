"""P545A static tests for advanced optimization progress accessibility."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
AUTO_LEARNING_MANAGER_JS = REPO_ROOT / "src" / "ui" / "AutoLearningManager.js"


def _advanced_progress_markup() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return html.split('id="advanced-optimization-progress"', 1)[1].split(
        "<!-- 進階優化結果顯示 -->", 1
    )[0]


def test_advanced_progress_bar_exposes_native_progressbar_contract() -> None:
    markup = _advanced_progress_markup()

    assert 'id="advanced-progress-bar"' in markup
    assert 'role="progressbar"' in markup
    assert 'aria-label="進階優化完成進度"' in markup
    assert 'aria-valuemin="0"' in markup
    assert 'aria-valuemax="100"' in markup
    assert 'aria-valuenow="0"' in markup


def test_advanced_progress_helper_keeps_visual_and_accessible_values_in_sync() -> None:
    script = AUTO_LEARNING_MANAGER_JS.read_text(encoding="utf-8")
    helper = script.split("updateAdvancedProgress(percentage, status, method) {", 1)[1].split(
        "\n    simulateAdvancedProgress(method) {", 1
    )[0]

    assert "const safePercentage = Math.max(0, Math.min(100, Number.isFinite(Number(percentage)) ? Number(percentage) : 0));" in helper
    assert "const roundedPercentage = Math.round(safePercentage);" in helper
    assert "progressBar.style.width = `${safePercentage}%`" in helper
    assert "progressBar.setAttribute('aria-valuenow', roundedPercentage.toString())" in helper
    assert "progressPercentage.textContent = `${roundedPercentage}%`" in helper
