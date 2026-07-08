"""Focused static tests for the P536L lift-candidate-shortlist minimal UI section."""

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


def test_nav_button_present_and_points_to_section():
    html = _html()
    assert 'data-section="p536l-lift-candidate-shortlist"' in html
    assert 'id="p536l-lift-candidate-shortlist-section"' in html


def test_section_has_manual_load_button_not_auto_load():
    section = _section()
    assert 'id="p536l-load-btn"' in section

    script = _script()
    assert "initP536L" in script
    assert "p536l-load-btn" in script
    assert "addEventListener('click', loadP536L)" in script
    # must not auto-fetch on section-nav click (manual load only)
    assert "data-section=\"p536l-lift-candidate-shortlist\"].forEach" not in script
    assert "[data-section]').forEach" not in script


def test_section_has_four_candidate_blocks_and_summary_counts():
    section = _section()
    assert 'id="p536l-summary-counts"' in section
    assert 'id="p536l-stable-tbody"' in section
    assert 'id="p536l-spike-tbody"' in section
    assert 'id="p536l-combo-tbody"' in section
    assert 'id="p536l-cross-lottery-list"' in section
    assert 'id="p536l-provenance"' in section


def test_disclaimer_text_present_in_section():
    section = _section()
    assert (
        "Historical replay review artifact only; not a prediction, "
        "betting edge, future-winning, or production-readiness claim." in section
    )


def test_script_fetches_the_new_readonly_route_only():
    script = _script()
    assert "fetch(base + '/api/replay/lift-candidate-shortlist')" in script
    assert "method:" not in script


def test_script_treats_non_ok_route_response_as_error_status():
    script = _script()
    assert "if (r.ok) return r.json();" in script
    assert "throw new Error(getErrorMessageP536L(data, 'HTTP ' + r.status));" in script
    assert "setStatus('載入失敗：' + (e && e.message ? e.message : 'unknown error'))" in script


def test_script_uses_route_json_error_detail_without_inner_html():
    script = _script()
    error_helper = script.split("function getErrorMessageP536L", 1)[1].split(
        "function renderProvenance", 1
    )[0]
    assert "if (data && data.detail) return String(data.detail);" in error_helper
    assert "if (data && data.message) return String(data.message);" in error_helper
    assert "if (data && data.error) return String(data.error);" in error_helper
    assert "innerHTML" not in error_helper


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


def test_no_new_charting_library_added():
    section = _section()
    script = _script()
    for forbidden in ("<script src=", "chart.js", "Chart(", "d3.js", "plotly"):
        assert forbidden not in section
        assert forbidden not in script
    # P536N added client-side filter/export controls on top of this minimal
    # UI (see tests/test_p536n_shortlist_ui_filter_export.py); this contract
    # test now only guards against a new charting dependency being pulled in.
