"""Focused static tests for P528B_FAST replay summary interpretation."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P528B_FAST: expose replay summary scope", 1)[1].split(
        "// Init event listeners", 1
    )[0]


def test_summary_scope_note_is_visible_in_replay_summary_card() -> None:
    html = _html()
    summary_card = html.split('id="rp-summary-cards"', 1)[1].split(
        '<!-- History Table -->', 1
    )[0]

    assert 'id="rp-summary-scope-note"' in summary_card
    assert "摘要 scope / denominator 尚未載入" in summary_card
    assert "<th>總 replay rows</th>" in summary_card
    assert "<th>已預測期數</th>" in summary_card
    assert 'colspan="10"' in summary_card


def test_summary_scope_uses_existing_read_only_payload_fields() -> None:
    script = _script()

    for expected in (
        "rpRenderSummaryScope(data)",
        "data.data_scope",
        "data.legacy_error_count",
        "data.scope_note",
        "data.disclaimer",
        "denominator=total replay rows; hit metrics use predicted rows only",
        "r.total_rows",
        "r.predicted_count",
    ):
        assert expected in script


def test_summary_scope_uses_existing_summary_endpoint_without_mutation() -> None:
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
