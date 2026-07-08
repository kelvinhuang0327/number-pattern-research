"""Focused static tests for the P536H client-side "Review Presets" control group
added on top of the P536E/P536G lift-extension minimal UI section. No DB, no
route change, no artifact regeneration — pure static HTML/JS assertions."""

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


def test_preset_bar_has_at_most_three_buttons():
    section = _section()
    assert 'id="p536h-preset-bar"' in section
    preset_buttons = [
        line
        for line in section.split('id="p536h-preset-bar"', 1)[1].split(
            "</div>", 1
        )[0].split("<button")
        if "p536h-preset-" in line
    ]
    assert len(preset_buttons) == 3


def test_preset_buttons_present():
    section = _section()
    assert 'id="p536h-preset-stable"' in section
    assert 'id="p536h-preset-spike"' in section
    assert 'id="p536h-preset-combo"' in section


def test_preset_disclaimer_text_present():
    section = _section()
    assert 'id="p536h-preset-note"' in section
    assert "Historical replay review preset only" in section
    assert "not a prediction or promotion gate" in section


def test_existing_filters_reset_export_still_present():
    section = _section()
    assert 'id="p536e-filter-bar"' in section
    assert 'id="p536e-filter-lottery"' in section
    assert 'id="p536e-filter-window"' in section
    assert 'id="p536e-filter-min-lift"' in section
    assert 'id="p536e-filter-search"' in section
    assert 'id="p536e-filter-reset"' in section
    assert 'id="p536e-export-csv"' in section


def test_provenance_and_replay_disclaimer_still_present():
    section = _section()
    assert 'id="p536e-provenance"' in section
    assert "Retrospective historical replay evidence only" in section


def test_preset_buttons_wired_to_toggle_function():
    script = _script()
    assert "function togglePresetP536H" in script
    assert "addEventListener('click', function() { togglePresetP536H(pair[1]); });" in script
    for pair in (
        "['p536h-preset-stable', 'stable_300_750']",
        "['p536h-preset-spike', 'spike_50']",
        "['p536h-preset-combo', 'combo']",
    ):
        assert pair in script


def test_presets_only_filter_already_loaded_data_no_new_fetch():
    script = _script()
    # still only the one fetch call from P536E itself
    assert script.count("fetch(") == 1
    assert "fetch(base + '/api/replay/strategy-lift-extension')" in script


def test_preset_predicates_use_only_existing_payload_fields():
    script = _script()
    assert "function passesPresetTopCellP536H" in script
    assert "function passesPresetCrossLotteryP536H" in script
    assert "function passesPresetStabilityP536H" in script
    # stable/spike gates read window + already-existing lift/log-lift fields
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


def test_preset_filters_wired_into_existing_filtered_getters():
    script = _script()
    assert "if (!passesPresetTopCellP536H(r)) return false;" in script
    assert "if (!passesPresetCrossLotteryP536H(r)) return false;" in script
    assert "if (!passesPresetStabilityP536H(r)) return false;" in script


def test_reset_clears_active_preset():
    script = _script()
    reset_fn = script.split("function resetFiltersP536E()", 1)[1].split(
        "\n  }\n", 1
    )[0]
    assert "_p536hPreset = null;" in reset_fn


def test_spike_badges_present_and_toggled_by_preset_state():
    section = _section()
    script = _script()
    assert 'id="p536h-spike-badge-cells"' in section
    assert 'id="p536h-spike-badge-cross"' in section
    assert "50-window review only" in section
    assert "function updatePresetButtonsP536H" in script
    assert "spikeBadgeCells" in script
    assert "spikeBadgeCross" in script


def test_no_new_metric_or_ranking_formula_introduced():
    script = _script()
    # preset helpers must only read already-existing fields, never compute a
    # new score/ranking formula
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
