"""P546A static tests for advanced optimization panel visibility."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
STYLES_CSS = REPO_ROOT / "styles.css"
AUTO_LEARNING_MANAGER_JS = REPO_ROOT / "src" / "ui" / "AutoLearningManager.js"


def _script() -> str:
    return AUTO_LEARNING_MANAGER_JS.read_text(encoding="utf-8")


def _advanced_panel_helper() -> str:
    script = _script()
    return script.split("setAdvancedPanelVisible(panel, visible) {", 1)[1].split(
        "\n    /**\n     * 啟動進階優化進度輪詢",
        1,
    )[0]


def test_advanced_panels_start_hidden_by_important_utility_class() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".ui-hidden { display: none !important; }" in css
    assert 'id="advanced-optimization-progress" class="ui-panel-dark-20 ui-hidden ui-mt-20"' in html
    assert 'id="advanced-optimization-result" class="ui-panel-dark-20 ui-hidden ui-mt-20"' in html
    assert 'id="optimization-results-panel" class="ui-panel-dark-20 ui-hidden ui-mt-20"' in html


def test_advanced_panel_helper_toggles_hidden_class_with_display_state() -> None:
    helper = _advanced_panel_helper()

    assert "if (!panel)" in helper
    assert "panel.classList.toggle('ui-hidden', !visible);" in helper
    assert "panel.style.display = visible ? 'block' : 'none';" in helper


def test_advanced_optimization_paths_use_helper_for_hidden_panels() -> None:
    script = _script()

    assert script.count("this.setAdvancedPanelVisible(progressDiv, true);") == 2
    assert script.count("this.setAdvancedPanelVisible(resultDiv, false);") == 2
    assert script.count("this.setAdvancedPanelVisible(progressDiv, false);") >= 4
    assert "this.setAdvancedPanelVisible(resultDiv, true);" in script
    assert "this.setAdvancedPanelVisible(panel, true);" in script
