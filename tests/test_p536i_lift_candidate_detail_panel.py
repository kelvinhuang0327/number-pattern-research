"""Focused static tests for the P536I client-side "candidate detail / why
included" row panel added on top of the P536E/G/H lift-extension minimal UI
section. No DB, no route change, no artifact regeneration — pure static
HTML/JS assertions."""

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


def test_detail_panel_and_placeholder_present():
    section = _section()
    assert 'id="p536i-detail-panel"' in section
    assert 'id="p536i-detail-body"' in section
    assert 'id="p536i-detail-placeholder"' in section
    # panel starts hidden until a row is selected
    assert 'id="p536i-detail-panel" style="padding:14px;margin-bottom:18px;display:none"' in section


def test_detail_panel_caution_text_present():
    section = _section()
    assert "僅供歷史回放審視細節；非預測或晉升判準。" in section
    assert "Historical replay review detail only; not a prediction or promotion gate." in section


def test_existing_filters_presets_export_provenance_disclaimer_still_present():
    section = _section()
    assert 'id="p536e-filter-bar"' in section
    assert 'id="p536e-filter-lottery"' in section
    assert 'id="p536e-filter-window"' in section
    assert 'id="p536e-filter-min-lift"' in section
    assert 'id="p536e-filter-search"' in section
    assert 'id="p536e-filter-reset"' in section
    assert 'id="p536e-export-csv"' in section
    assert 'id="p536h-preset-bar"' in section
    assert 'id="p536h-preset-stable"' in section
    assert 'id="p536h-preset-spike"' in section
    assert 'id="p536h-preset-combo"' in section
    assert 'id="p536e-provenance"' in section
    assert "Retrospective historical replay evidence only" in section


def test_rows_carry_data_attributes_for_click_selection():
    script = _script()
    assert "data-p536i-type=\"top_cell\" data-p536i-idx=\"" in script
    assert "data-p536i-type=\"cross_lottery\" data-p536i-idx=\"" in script
    assert "data-p536i-type=\"stability\" data-p536i-idx=\"" in script


def test_row_click_handlers_wired_via_delegation():
    script = _script()
    assert "topCellsTbody.addEventListener('click'" in script
    assert "crossLotteryList.addEventListener('click'" in script
    assert "stabilityTbody.addEventListener('click'" in script
    assert "renderCandidateDetailP536I('top_cell'" in script
    assert "renderCandidateDetailP536I('cross_lottery'" in script
    assert "renderCandidateDetailP536I('stability'" in script


def test_detail_render_function_uses_only_existing_payload_fields():
    script = _script()
    assert "function renderCandidateDetailP536I" in script
    for field in (
        "r.lottery_type",
        "r.window",
        "r.strategy_id",
        "r.feature_family",
        "r.support_draws",
        "r.any_main_hit_rate",
        "r.baseline_any_main_hit_rate",
        "r.any_main_hit_lift",
        "rc.pick_k",
        "rs.stability_rank",
        "rs.combo_id",
        "rs.windows_present_count",
        "rs.avg_prize_signal_lift_across_present_windows",
    ):
        assert field in script


def test_preset_reason_helpers_mirror_existing_p536h_predicates_read_only():
    script = _script()
    assert "function presetReasonsTopCellP536I" in script
    assert "function presetReasonsCrossLotteryP536I" in script
    assert "function presetReasonsStabilityP536I" in script
    for field in (
        "r.window === 300",
        "r.window === 750",
        "r.window === 50",
        "r.any_main_hit_lift",
        "stats.avg_any_main_hit_log10_lift",
        "stats.avg_any_main_hit_lift",
        "r.windows_present_count",
    ):
        assert field in script


def test_preset_reason_labels_present_in_detail_render():
    script = _script()
    assert "審視預設原因 / Preset Reason" in script
    assert "穩定 300/750 候選 / Stable 300/750" in script
    assert "短期高峰 / Short-term Spike (50)" in script
    assert "組合候選 / Combination Candidate" in script
    assert "未符合任何審視預設 / Does not match any review preset" in script


def test_refilter_hides_stale_detail_selection():
    script = _script()
    assert "function hideCandidateDetailP536I" in script
    render_filtered = script.split("function renderFilteredP536E()", 1)[1].split(
        "\n  }\n", 1
    )[0]
    assert "hideCandidateDetailP536I();" in render_filtered


def test_presets_only_filter_already_loaded_data_no_new_fetch():
    script = _script()
    # still only the one fetch call from P536E itself
    assert script.count("fetch(") == 1
    assert "fetch(base + '/api/replay/strategy-lift-extension')" in script


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
