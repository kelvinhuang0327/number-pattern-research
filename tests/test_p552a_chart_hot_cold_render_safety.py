"""P552A focused static tests for chart hot/cold badge render safety.

No DB, no service startup, no runtime artifacts: these assertions verify the
client renders statistics-derived badge values as text instead of HTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CHART_MANAGER_JS = REPO_ROOT / "src" / "ui" / "ChartManager.js"


def _script() -> str:
    return CHART_MANAGER_JS.read_text(encoding="utf-8")


def _hot_cold_helper() -> str:
    script = _script()
    return script.split("    async updateHotColdNumbers(lotteryType = '') {", 1)[
        1
    ].split("\n    /**\n     * 創建漸層色", 1)[0]


def test_hot_cold_badges_use_dom_text_rendering() -> None:
    helper = _hot_cold_helper()

    assert "this.renderNumberBadges(hotContainer, hotNumbers, 'hot');" in helper
    assert "this.renderNumberBadges(coldContainer, coldNumbers, 'cold');" in helper
    assert "const badge = document.createElement('div');" in helper
    assert "badge.className = `number-badge ${type}`;" in helper
    assert "badge.title = `出現 ${item.frequency} 次 (${item.percentage}%)`;" in helper
    assert "badge.textContent = item.number;" in helper


def test_hot_cold_badges_do_not_interpolate_statistics_into_inner_html() -> None:
    helper = _hot_cold_helper()

    assert "hotContainer.innerHTML" not in helper
    assert "coldContainer.innerHTML" not in helper
    assert "${item.number}" not in helper
    assert "${item.frequency}" not in helper.replace("badge.title = `出現 ${item.frequency} 次 (${item.percentage}%)`;", "")


def test_render_safety_fix_does_not_add_dependency_or_runtime_behavior() -> None:
    helper = _hot_cold_helper()

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
