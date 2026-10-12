"""Focused static tests for the P536N client-side filter/export controls added
on top of the P536L lift-candidate-shortlist minimal UI. No DB, no route
change, no artifact regeneration, no new metric/ranking formula — pure
static HTML/JS assertions operating on the already-loaded response."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _section() -> str:
    html = _html()
    return html.split("<!-- ===== P536L Lift Candidate Shortlist", 1)[1].split(
        "<!-- ===== END P536L", 1
    )[0]


def _script() -> str:
    html = _html()
    return html.split("// ===== P536L LIFT CANDIDATE SHORTLIST", 1)[1].split(
        "// ===== P258O", 1
    )[0]


def test_filter_bar_controls_present():
    section = _section()
    assert 'id="p536n-filter-bar"' in section
    assert 'id="p536n-filter-category"' in section
    assert 'id="p536n-filter-lottery"' in section
    assert 'id="p536n-filter-search"' in section
    assert 'id="p536n-filter-reset"' in section
    assert 'id="p536n-export-csv"' in section


def test_category_filter_options_match_four_candidate_sections():
    section = _section()
    filter_block = section.split('id="p536n-filter-category"', 1)[1].split("</select>", 1)[0]
    for value in ("ALL", "stable_300_750", "short_window_spike", "combination", "cross_lottery"):
        assert f'value="{value}"' in filter_block


def test_lottery_filter_options_match_known_lottery_types():
    section = _section()
    filter_block = section.split('id="p536n-filter-lottery"', 1)[1].split("</select>", 1)[0]
    for lottery in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        assert lottery in filter_block


def test_candidate_cards_have_stable_ids_for_category_visibility_toggle():
    section = _section()
    assert 'id="p536l-card-stable"' in section
    assert 'id="p536l-card-spike"' in section
    assert 'id="p536l-card-combo"' in section
    assert 'id="p536l-card-cross"' in section


def test_reset_button_wired_to_reset_function():
    script = _script()
    assert "resetFiltersP536N" in script
    assert "addEventListener('click', resetFiltersP536N)" in script


def test_export_button_wired_to_export_function():
    script = _script()
    assert "exportVisibleCsvP536N" in script
    assert "addEventListener('click', exportVisibleCsvP536N)" in script


def test_filters_only_operate_on_already_loaded_data_no_new_fetch():
    script = _script()
    # still only the one fetch call from P536L itself
    assert script.count("fetch(") == 1
    assert "fetch(base + '/api/replay/lift-candidate-shortlist')" in script
    assert "_p536lData = data" in script


def test_csv_export_builds_from_filtered_in_memory_rows_not_dom():
    script = _script()
    assert "buildVisibleCsvP536N" in script
    assert "getFilteredStableP536N" in script
    assert "getFilteredSpikeP536N" in script
    assert "getFilteredComboP536N" in script
    assert "getFilteredCrossP536N" in script
    assert "new Blob(" in script
    assert "text/csv" in script


def test_category_filter_narrows_to_single_section_and_all_shows_everything():
    script = _script()
    assert "getFilteredStableP536N" in script
    assert "f.category !== 'ALL' && f.category !== 'stable_300_750'" in script
    assert "f.category !== 'ALL' && f.category !== 'short_window_spike'" in script
    assert "f.category !== 'ALL' && f.category !== 'combination'" in script
    assert "f.category !== 'ALL' && f.category !== 'cross_lottery'" in script


def test_lottery_filter_handles_cross_lottery_multi_lottery_shape():
    script = _script()
    # cross_lottery rows have a `lotteries` dict keyed by lottery type rather
    # than a single lottery_type field — filtering must check membership.
    assert "hasOwnProperty.call(r.lotteries, f.lottery)" in script


def test_provenance_rendering_unaffected_by_filters():
    script = _script()
    assert "renderProvenance(data)" in script
    assert "renderSummaryCounts(data)" in script
    assert "renderProvenanceDetail(data)" in script


def test_no_new_metric_or_ranking_formula_introduced():
    script = _script()
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
