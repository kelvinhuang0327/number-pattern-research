"""Focused static tests for P531_FAST replay-run data-hash provenance."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
REPLAY_ROUTE = REPO_ROOT / "lottery_api" / "routes" / "replay.py"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _status_script() -> str:
    return _html().split("// P526B_FAST: expose status-count denominator", 1)[1].split(
        "</script>", 1
    )[0]


def test_status_route_returns_run_row_with_existing_data_hash_field() -> None:
    source = REPLAY_ROUTE.read_text(encoding="utf-8")
    runs_schema = source.split('@router.get("/api/replay/runs")', 1)[1].split(
        '@router.get("/api/replay/run/{run_id}/status")', 1
    )[0]
    status_route = source.split('@router.get("/api/replay/run/{run_id}/status")', 1)[1].split(
        "# ─── Freshness / Coverage Status", 1
    )[0]

    assert "data_hash" in runs_schema
    assert "SELECT * FROM strategy_replay_runs WHERE id = ?" in status_route
    assert '"run":           dict(row)' in status_route


def test_selected_run_status_displays_data_hash_provenance_safely() -> None:
    script = _status_script()

    assert "// P531_FAST: expose existing replay-run data hash provenance." in script
    assert "run.data_hash" in script
    assert "data_hash=" in script
    assert "String(run.data_hash).trim()" in script
    assert "statusDetail.textContent" in script
    assert "statusDetail.innerHTML" not in script


def test_existing_p526b_scope_context_is_preserved() -> None:
    script = _status_script()

    for expected in (
        "run.strategy_scope",
        "run.generator_version",
        "run.notes",
        "scope=",
        "generator=",
        "notes=",
        "無 run notes",
    ):
        assert expected in script


def test_data_hash_reuses_existing_status_fetch_without_mutation() -> None:
    script = _status_script()

    status_fetch = "fetch(base + '/api/replay/run/' + encodeURIComponent(runId) + '/status')"
    assert script.count(status_fetch) == 1
    assert "data_hash" not in "\n".join(
        line for line in script.splitlines() if "fetch(" in line
    )
    assert "method:" not in script

    for forbidden in (
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
    ):
        assert forbidden not in script
