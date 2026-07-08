"""Focused static tests for the P536P row-level candidate detail panel added
on top of the P536N filter/export controls and P536L minimal shortlist UI.
No DB, no route change, no artifact regeneration, no new metric/ranking
formula — pure static HTML/JS assertions operating on fields already present
in the already-loaded /api/replay/lift-candidate-shortlist response."""

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


def test_detail_column_header_present_in_all_four_tables():
    section = _section()
    # stable + spike + combo are <table>-based; each needs a 詳情 header.
    assert section.count(">詳情<") == 3


def test_toggle_attribute_wired_for_all_four_render_functions():
    script = _script()
    assert "data-p536p-toggle" in script
    assert script.count("data-p536p-toggle") >= 4


def test_detail_builder_functions_present_for_each_section_shape():
    script = _script()
    assert "buildStableSpikeDetailHtmlP536P" in script
    assert "buildComboDetailHtmlP536P" in script
    assert "buildCrossDetailHtmlP536P" in script


def test_detail_builders_only_reference_fields_already_in_p536k_artifact():
    script = _script()
    # stable/spike shape
    for field in (
        "r.lottery_type", "r.window", "r.strategy_id", "r.feature_family",
        "r.pick_k", "r.metric", "r.observed_rate", "r.baseline_rate",
        "r.lift", "r.log10_lift", "r.support_draws", "r.why_included",
        "r.caution_label",
    ):
        assert field in script
    # combination shape
    for field in (
        "r.combo_id", "r.requested_budget", "r.windows_present",
        "r.windows_present_count", "r.stability_rank",
        "r.avg_prize_signal_lift_across_present_windows", "r.per_window",
    ):
        assert field in script
    # cross-lottery shape
    assert "r.lotteries" in script


def test_caution_text_present_in_detail_panel():
    script = _script()
    assert "Historical replay review detail only; not a prediction or promotion gate." in script


def test_toggle_binding_survives_rerenders_via_event_delegation():
    script = _script()
    assert "bindP536PToggle" in script
    assert "['p536l-stable-tbody', 'p536l-spike-tbody', 'p536l-combo-tbody', 'p536l-cross-lottery-list'].forEach(bindP536PToggle)" in script


def test_no_new_fetch_or_route_introduced():
    script = _script()
    # still only the one fetch call from P536L itself
    assert script.count("fetch(") == 1
    assert "fetch(base + '/api/replay/lift-candidate-shortlist')" in script


def test_existing_filters_reset_and_export_still_present():
    section = _section()
    script = _script()
    assert 'id="p536n-filter-bar"' in section
    assert 'id="p536n-filter-reset"' in section
    assert 'id="p536n-export-csv"' in section
    assert "resetFiltersP536N" in script
    assert "exportVisibleCsvP536N" in script


def test_provenance_and_disclaimer_still_present():
    section = _section()
    assert "歷史回放聲明" in section
    assert 'id="p536l-provenance"' in section
    assert 'id="p536l-provenance-detail"' in section


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
