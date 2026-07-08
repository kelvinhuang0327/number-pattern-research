"""Focused static tests for the P536G client-side filter/export controls added
on top of the P536E lift-extension minimal UI section. No DB, no route change,
no artifact regeneration — pure static HTML/JS assertions."""

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


def test_filter_bar_controls_present():
    section = _section()
    assert 'id="p536e-filter-bar"' in section
    assert 'id="p536e-filter-lottery"' in section
    assert 'id="p536e-filter-window"' in section
    assert 'id="p536e-filter-min-lift"' in section
    assert 'id="p536e-filter-search"' in section
    assert 'id="p536e-filter-reset"' in section
    assert 'id="p536e-export-csv"' in section


def test_lottery_filter_options_match_known_lottery_types():
    section = _section()
    filter_block = section.split('id="p536e-filter-lottery"', 1)[1].split("</select>", 1)[0]
    for lottery in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        assert lottery in filter_block


def test_window_filter_options_match_known_primary_windows():
    section = _section()
    filter_block = section.split('id="p536e-filter-window"', 1)[1].split("</select>", 1)[0]
    for window in ("50", "300", "750"):
        assert f'value="{window}"' in filter_block


def test_reset_button_wired_to_reset_function():
    script = _script()
    assert "resetFiltersP536E" in script
    assert "p536e-filter-reset" in script
    assert "addEventListener('click', resetFiltersP536E)" in script


def test_export_button_wired_to_export_function():
    script = _script()
    assert "exportVisibleCsvP536E" in script
    assert "p536e-export-csv" in script
    assert "addEventListener('click', exportVisibleCsvP536E)" in script


def test_filters_only_operate_on_already_loaded_data_no_new_fetch():
    script = _script()
    # still only the one fetch call from P536E itself
    assert script.count("fetch(") == 1
    assert "fetch(base + '/api/replay/strategy-lift-extension')" in script


def test_csv_export_builds_from_filtered_in_memory_rows_not_dom():
    script = _script()
    assert "buildVisibleCsvP536E" in script
    assert "getFilteredTopCellsP536E" in script
    assert "getFilteredCrossLotteryP536E" in script
    assert "getFilteredStabilityRankP536E" in script
    assert "new Blob(" in script
    assert "text/csv" in script


def test_rendered_artifact_strings_are_html_escaped():
    script = _script()
    assert "function escP536E" in script
    assert "function textP536E" in script
    for field in (
        "r.strategy_id",
        "r.feature_family",
        "r.combo_id",
    ):
        assert f"textP536E({field}" in script
    assert "textP536E(LOTTERY_LABELS_P536E[r.lottery_type] || r.lottery_type)" in script
    assert "textP536E(LOTTERY_LABELS_P536E[lt] || lt)" in script
    for unsafe_pattern in (
        "+ (r.strategy_id ||",
        "+ (r.feature_family ||",
        "+ (r.combo_id ||",
        "+ (LOTTERY_LABELS_P536E[lt] || lt)",
        "+ (LOTTERY_LABELS_P536E[r.lottery_type] || r.lottery_type",
    ):
        assert unsafe_pattern not in script


def test_provenance_rendering_unaffected_by_filters():
    script = _script()
    # renderProvenance must still be called with the full raw payload on load,
    # not a filtered subset, so disclaimer/provenance/data_hash stay visible.
    assert "renderProvenance(data)" in script


def test_no_new_metric_or_ranking_formula_introduced():
    script = _script()
    # the export/filter helpers must only read already-existing fields, never
    # compute a new score/ranking formula
    for forbidden in ("score", "rank =", "Score", "ranking_formula"):
        assert forbidden not in script


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
