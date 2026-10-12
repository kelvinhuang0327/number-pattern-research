"""Focused static tests for P529_FAST replay summary predicted coverage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P529_FAST: compare predicted rows", 1)[1].split(
        "// Init event listeners", 1
    )[0]


def test_summary_predicted_count_renders_coverage_against_total_rows() -> None:
    script = _script()

    for expected in (
        "function rpFormatSummaryPredictedCoverage(row)",
        "row.predicted_count",
        "row.total_rows",
        "predicted / total",
        "% coverage",
        "coverage N/A",
        "rpFormatSummaryPredictedCoverage({ predicted_count: r.predicted_count, total_rows: r.total_rows })",
    ):
        assert expected in script


def test_summary_keeps_denominator_disclosure_and_table_shape() -> None:
    html = _html()
    summary_card = html.split('id="rp-summary-cards"', 1)[1].split(
        '<!-- History Table -->', 1
    )[0]

    assert 'id="rp-summary-scope-note"' in summary_card
    assert "<th>總 replay rows</th>" in summary_card
    assert "<th>已預測期數</th>" in summary_card
    assert 'colspan="10"' in summary_card


def test_summary_coverage_stays_read_only_and_non_predictive() -> None:
    script = _script()

    assert "fetch(url)" in script
    assert "`${BASE}/summary?lottery_type=${lt}`" in script
    assert "method:" not in script

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "winning",
        "edge",
        "betting",
    ):
        assert forbidden not in script
