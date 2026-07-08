"""P543A static tests for simulation loading progress visibility."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
APP_JS = REPO_ROOT / "src" / "core" / "App.js"


def _simulation_loading_markup() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return html.split('id="sim-loading"', 1)[1].split("</div>\n\n                <div id=\"simulation-results\"", 1)[0]


def test_simulation_loading_panel_is_announced_as_progress_status() -> None:
    markup = _simulation_loading_markup()

    assert 'class="sim-loading"' in markup
    assert 'role="status"' in markup
    assert 'aria-live="polite"' in markup
    assert 'aria-label="模擬運算進度"' in markup
    assert 'aria-hidden="true"' in markup
    assert 'aria-busy="false"' in markup


def test_simulation_loading_helper_toggles_visibility_and_progress() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    helper = script.split("setSimulationLoading(isLoading, current = 0, total = 0) {", 1)[1].split(
        "\n    }\n\n    /**\n     * 檢查檔名是否應該被忽略", 1
    )[0]

    assert "loading.classList.toggle('is-active', isLoading)" in helper
    assert "loading.setAttribute('aria-hidden', isLoading ? 'false' : 'true')" in helper
    assert "loading.setAttribute('aria-busy', isLoading ? 'true' : 'false')" in helper
    assert "progress.textContent = total > 0 ? `${current} / ${total} 期` : '準備模擬資料...'" in helper
    assert "progressBar.style.width = `${percentage}%`" in helper


def test_run_simulation_activates_and_clears_loading_panel() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    run_simulation = script.split("async runSimulation() {", 1)[1].split(
        "\n    async runCollaborativeSimulation()", 1
    )[0]

    assert "this.setSimulationLoading(true);" in run_simulation
    assert "this.setSimulationLoading(true, 0, testTargets.length);" in run_simulation
    assert "this.setSimulationLoading(true, index + 1, testTargets.length);" in run_simulation
    assert "this.setSimulationLoading(false);" in run_simulation
