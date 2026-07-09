"""Focused static tests for the P537B robustness review minimal UI section."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _section() -> str:
    html = _html()
    return html.split("<!-- ===== P537B Robustness Review", 1)[1].split(
        "<!-- ===== END P537B", 1
    )[0]


def _script() -> str:
    html = _html()
    return html.split("// ===== P537B SHORTLIST ROBUSTNESS REVIEW", 1)[1].split(
        "// ===== P258O", 1
    )[0]


def test_nav_button_present_and_points_to_section():
    html = _html()
    assert 'data-section="p537b-robustness-review"' in html
    assert 'id="p537b-robustness-review-section"' in html


def test_section_has_manual_load_button_not_auto_load():
    section = _section()
    assert 'id="p537b-load-btn"' in section

    script = _script()
    assert "initP537B" in script
    assert "p537b-load-btn" in script
    assert "addEventListener('click', loadP537B)" in script
    # must not auto-fetch on section-nav click (manual load only)
    assert "data-section=\"p537b-robustness-review\"].forEach" not in script
    assert "[data-section]').forEach" not in script


def test_section_has_five_candidate_blocks_and_summary_counts():
    section = _section()
    assert 'id="p537b-summary-counts"' in section
    assert 'id="p537b-stable-tbody"' in section
    assert 'id="p537b-spike-tbody"' in section
    assert 'id="p537b-combo-tbody"' in section
    assert 'id="p537b-cross-tbody"' in section
    assert 'id="p537b-insufficient-tbody"' in section
    assert 'id="p537b-provenance"' in section


def test_disclaimer_text_present_in_section():
    section = _section()
    assert (
        "Historical replay review artifact only; not a prediction, "
        "betting edge, future-winning, or production-readiness claim." in section
    )


def test_script_fetches_the_new_readonly_route_only():
    script = _script()
    assert "fetch(base + '/api/replay/shortlist-robustness-review')" in script
    assert "method:" not in script


def test_script_treats_non_ok_route_response_as_error_status():
    script = _script()
    assert "if (r.ok) return r.json();" in script
    assert "throw new Error((data && data.detail) ? data.detail : ('HTTP ' + r.status));" in script
    assert "setStatus('載入失敗：' + (e && e.message ? e.message : 'unknown error'))" in script


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


def test_no_new_charting_library_or_export_added():
    section = _section()
    script = _script()
    for forbidden in ("<script src=", "chart.js", "Chart(", "d3.js", "plotly", "csv", "CSV", "export", "filter"):
        assert forbidden not in section
        assert forbidden not in script
