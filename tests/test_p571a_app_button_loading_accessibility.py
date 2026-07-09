"""P571A focused static tests for App button loading accessibility.

No DB, no service startup, no runtime artifacts: these assertions cover the
shared App button-loading helper used by prediction and simulation actions.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
APP_JS = REPO_ROOT / "src" / "core" / "App.js"


def _app_js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _set_button_loading_helper() -> str:
    script = _app_js()
    return script.split("    setButtonLoading(button, isLoading) {", 1)[1].split(
        "\n\n    setSimulationLoading(", 1
    )[0]


def test_app_button_loading_exposes_busy_state_to_assistive_tech() -> None:
    helper = _set_button_loading_helper()

    assert "button.disabled = true" in helper
    assert "button.setAttribute('aria-busy', 'true')" in helper
    assert "button.disabled = false" in helper
    assert "button.removeAttribute('aria-busy')" in helper


def test_app_button_loading_still_restores_original_markup() -> None:
    helper = _set_button_loading_helper()

    assert "button.dataset.originalText = button.innerHTML" in helper
    assert "button.innerHTML = button.dataset.originalText" in helper
    assert "delete button.dataset.originalText" in helper
    assert "icon.textContent = '⏳'" in helper


def test_app_button_loading_change_stays_no_db_non_mutating() -> None:
    helper = _set_button_loading_helper()

    for forbidden in (
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
        "method:",
    ):
        assert forbidden not in helper
