"""Focused static tests for P530_FAST replay summary baseline context."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P530_FAST: include API-returned lottery/lifecycle", 1)[1].split(
        "// Init event listeners", 1
    )[0]


def test_summary_scope_renders_lottery_and_lifecycle_baseline_context() -> None:
    script = _script()

    for expected in (
        "data.lottery_type",
        "data.filter_lifecycle_status",
        "UNKNOWN_LOTTERY",
        "ALL_LIFECYCLES",
        "Lottery=",
        "lifecycle=",
        "Scope=",
        "denominator=total replay rows; hit metrics use predicted rows only",
    ):
        assert expected in script


def test_summary_baseline_context_preserves_existing_coverage_formatter() -> None:
    script = _script()

    assert "function rpFormatSummaryPredictedCoverage(row)" in script
    assert "row.predicted_count" in script
    assert "row.total_rows" in script
    assert "% coverage" in script


def test_summary_baseline_context_stays_read_only_and_non_predictive() -> None:
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
