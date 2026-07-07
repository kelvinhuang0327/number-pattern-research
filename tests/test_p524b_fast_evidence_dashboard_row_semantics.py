"""Focused static tests for P524B_FAST evidence dashboard row semantics."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P524B_FAST: expose row-semantics context", 1)[1].split("</script>", 1)[0]


def test_row_semantics_context_is_visible_in_evidence_monitor() -> None:
    html = _html()
    replay = html.split('id="replay-section"', 1)[1].split('id="tracking-section"', 1)[0]

    assert 'id="evidence-dashboard-row-semantics"' in replay
    assert "Replay rows 與 draw rows 語意讀取中…" in replay


def test_row_semantics_uses_existing_evidence_payload_fields() -> None:
    script = _script()

    for field in (
        "global.draw_rows_total",
        "card.draw_rows",
        "card.canonical_rows",
        "Replay rows 是回放紀錄，不是 draw rows",
        "全域 draw rows",
        "canonical rows",
    ):
        assert field in script


def test_row_semantics_stays_read_only_and_non_predictive() -> None:
    script = _script()

    assert "fetch(base + '/api/replay/evidence-dashboard')" in script
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
