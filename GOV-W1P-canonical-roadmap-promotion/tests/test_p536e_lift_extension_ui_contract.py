"""Focused static tests for the P536E lift-extension minimal UI section."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _section() -> str:
    html = _html()
    return html.split("<!-- ===== P536E Strategy Lift Extension", 1)[1].split(
        "<!-- ===== END P536E", 1
    )[0]


def _script() -> str:
    html = _html()
    return html.split("// ===== P536E STRATEGY LIFT EXTENSION", 1)[1].split(
        "// ===== P258O", 1
    )[0]


def test_nav_button_present_and_points_to_section():
    html = _html()
    assert 'data-section="p536e-lift-extension"' in html
    assert 'id="p536e-lift-extension-section"' in html


def test_section_has_manual_load_button_not_auto_load():
    section = _section()
    assert 'id="p536e-load-btn"' in section

    script = _script()
    assert "initP536E" in script
    assert "p536e-load-btn" in script
    assert "addEventListener('click', loadP536E)" in script
    # must not auto-fetch on section-nav click (manual load only)
    assert "data-section=\"p536e-lift-extension\"].forEach" not in script
    assert "[data-section]').forEach" not in script


def test_section_has_top_lift_cells_table_and_cross_lottery_and_stability_blocks():
    section = _section()
    assert 'id="p536e-top-cells-tbody"' in section
    assert 'id="p536e-cross-lottery-list"' in section
    assert 'id="p536e-stability-tbody"' in section
    assert 'id="p536e-provenance"' in section


def test_disclaimer_text_present_in_section():
    section = _section()
    assert (
        "Retrospective historical replay evidence only; no prediction, betting, "
        "edge, future-winning, or production-readiness claim." in section
    )


def test_script_fetches_the_new_readonly_route_only():
    script = _script()
    assert "fetch(base + '/api/replay/strategy-lift-extension')" in script
    assert "method:" not in script


def test_script_does_not_add_db_prediction_or_mutation_behavior():
    script = _script()
    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in script


def test_no_new_charting_library_or_external_script_added():
    section = _section()
    script = _script()
    for forbidden in ("<script src=", "chart.js", "Chart(", "d3.js", "plotly"):
        assert forbidden not in section
        assert forbidden not in script
