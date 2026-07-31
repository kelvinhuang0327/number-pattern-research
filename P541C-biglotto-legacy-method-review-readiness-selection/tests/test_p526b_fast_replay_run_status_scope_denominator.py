"""Focused static tests for P526B_FAST replay run status interpretation."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _script() -> str:
    return _html().split("// P526B_FAST: expose status-count denominator", 1)[1].split("</script>", 1)[0]


def test_run_status_renders_denominator_and_sample_scope_metadata() -> None:
    script = _script()

    for expected in (
        "formatReplayRunScope(run, countTotal)",
        "Object.keys(counts).reduce",
        "狀態計數分母=",
        "run.strategy_scope",
        "run.generator_version",
        "run.notes",
        "無 run notes",
    ):
        assert expected in script


def test_scope_context_extends_existing_read_only_status_endpoint() -> None:
    script = _script()

    assert "payload.run" in script
    assert "payload.status_counts" in script
    assert "fetch(base + '/api/replay/run/' + encodeURIComponent(runId) + '/status')" in script
    assert "method:" not in script


def test_scope_context_does_not_add_prediction_db_or_claim_behavior() -> None:
    script = _script()

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
