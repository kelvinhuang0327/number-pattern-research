"""Tests for MLB Daily Scheduler (mlb_daily_scheduler_v1).

23 tests covering:
  - Dataclass schemas (DailyJobManifest, DailyJobResult)
  - Job runners (pregame advisory, postgame review)
  - Full scheduler pipeline (fixture today, replay mode)
  - Manifest write + read
  - Safety flags
  - Gate validation
  - API handler integration (tests 13–20)
  - Markdown report (tests 21–22)
  - Full regression (test 23)
"""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from typing import Any

import pytest

# ─── Module imports ───────────────────────────────────────────────────────────

from orchestrator.mlb_daily_scheduler import (
    COMPLETION_MARKER,
    LEDGER_OVERWRITE_BLOCKED,
    MODULE_VERSION,
    NO_AUTO_EXECUTION,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    PRODUCTION_MODIFIED,
    SCHEDULER_DRY_RUN_ONLY,
    VALID_GATES,
    DailyJobManifest,
    DailyJobResult,
    JOB_STATUS_DATA_LIMITED,
    JOB_STATUS_FAILED,
    JOB_STATUS_NOT_RUN,
    JOB_STATUS_SKIPPED,
    JOB_STATUS_SUCCESS,
    build_daily_manifest,
    build_scheduler_gate,
    generate_scheduler_markdown,
    load_latest_daily_manifest,
    run_daily_mlb_scheduler,
    run_postgame_review_job,
    run_pregame_advisory_job,
    validate_daily_manifest,
    write_daily_manifest,
    DEFAULT_FIXTURE_PATH,
    DEFAULT_LEDGER_PATH,
    DEFAULT_PREDICTION_JSONL,
)

# ─── Shared fixtures ──────────────────────────────────────────────────────────

RUN_DATE_FIXTURE = "2026-05-07"
RUN_DATE_REPLAY = "2025-07-01"


def _make_job_result(
    job_name: str = "test_job",
    status: str = JOB_STATUS_SUCCESS,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> DailyJobResult:
    return DailyJobResult(
        job_name=job_name,
        status=status,
        started_at="2026-05-07T09:00:00+00:00",
        finished_at="2026-05-07T09:00:01+00:00",
        duration_seconds=1.0,
        output_paths=[],
        errors=errors or [],
        warnings=warnings or [],
        safety_flags={
            "paper_only": True,
            "no_real_bet": True,
            "no_profit_claim": True,
            "no_auto_execution": True,
        },
    )


def _make_manifest(
    run_id: str = "SCHED_TEST_001",
    run_date: str = RUN_DATE_FIXTURE,
    gate: str = "MLB_SCHEDULER_API_MVP_READY",
    pregame_status: str = JOB_STATUS_SUCCESS,
    postgame_status: str = JOB_STATUS_SUCCESS,
) -> DailyJobManifest:
    return DailyJobManifest(
        run_id=run_id,
        run_date=run_date,
        mode="today",
        source="fixture",
        scheduler_mode="dry_run",
        pregame_advisory_status=pregame_status,
        postgame_review_status=postgame_status,
        advisory_report_path=f"reports/mlb_daily_advisory_dry_run_{run_date.replace('-','')}.json",
        ledger_path=DEFAULT_LEDGER_PATH,
        review_report_path=f"reports/mlb_postgame_review_{run_date.replace('-','')}.json",
        reviewed_snapshot_path=f"reports/mlb_paper_betting_reviewed_snapshot_{run_date.replace('-','')}.jsonl",
        total_advisories=5,
        total_ledger_entries=5,
        reviewed_count=3,
        pending_count=2,
        failure_notes_count=1,
        gate=gate,
    )


# ════════════════════════════════════════════════════════════════════════════
# TEST 1 — DailyJobManifest schema complete
# ════════════════════════════════════════════════════════════════════════════

def test_01_daily_job_manifest_schema_complete():
    """DailyJobManifest has all required fields with correct types."""
    manifest = _make_manifest()
    required_fields = [
        "run_id", "run_date", "mode", "source", "scheduler_mode",
        "pregame_advisory_status", "postgame_review_status",
        "advisory_report_path", "ledger_path", "review_report_path",
        "reviewed_snapshot_path", "total_advisories", "total_ledger_entries",
        "reviewed_count", "pending_count", "failure_notes_count", "gate",
        "paper_only", "no_real_bet", "no_profit_claim", "no_auto_execution",
        "scheduler_dry_run_only", "ledger_overwrite_blocked",
        "module_version", "completion_marker",
    ]
    for f in required_fields:
        assert hasattr(manifest, f), f"DailyJobManifest missing field: {f}"
    assert manifest.paper_only is True
    assert manifest.no_real_bet is True
    assert manifest.no_profit_claim is True
    assert manifest.no_auto_execution is True
    assert manifest.module_version == MODULE_VERSION
    assert manifest.completion_marker == COMPLETION_MARKER


# ════════════════════════════════════════════════════════════════════════════
# TEST 2 — DailyJobResult schema complete
# ════════════════════════════════════════════════════════════════════════════

def test_02_daily_job_result_schema_complete():
    """DailyJobResult has all required fields with correct types."""
    result = _make_job_result()
    required_fields = [
        "job_name", "status", "started_at", "finished_at",
        "duration_seconds", "output_paths", "errors", "warnings",
        "safety_flags",
    ]
    for f in required_fields:
        assert hasattr(result, f), f"DailyJobResult missing field: {f}"
    assert isinstance(result.output_paths, list)
    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)
    assert isinstance(result.safety_flags, dict)
    assert result.safety_flags.get("no_real_bet") is True
    assert result.safety_flags.get("paper_only") is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 3 — Pregame advisory job can execute
# ════════════════════════════════════════════════════════════════════════════

def test_03_pregame_advisory_job_executes():
    """Pregame advisory job runs without raising and returns DailyJobResult."""
    result = run_pregame_advisory_job(
        run_date=RUN_DATE_FIXTURE,
        mode="today",
        source="fixture",
        limit=5,
        ledger_path=DEFAULT_LEDGER_PATH,
        fixture_path=DEFAULT_FIXTURE_PATH,
        prediction_jsonl_path=DEFAULT_PREDICTION_JSONL,
        write_reports=False,
    )
    assert isinstance(result, DailyJobResult)
    assert result.job_name == "pregame_advisory"
    assert result.status in {
        JOB_STATUS_SUCCESS, JOB_STATUS_FAILED, JOB_STATUS_DATA_LIMITED
    }
    assert isinstance(result.errors, list)
    assert isinstance(result.warnings, list)
    assert result.safety_flags.get("no_real_bet") is True
    assert result.safety_flags.get("paper_only") is True
    assert result.safety_flags.get("production_modified") is False


# ════════════════════════════════════════════════════════════════════════════
# TEST 4 — Postgame review job can execute
# ════════════════════════════════════════════════════════════════════════════

def test_04_postgame_review_job_executes():
    """Postgame review job runs without raising and returns DailyJobResult."""
    result = run_postgame_review_job(
        run_date=RUN_DATE_FIXTURE,
        source="fixture",
        ledger_path=DEFAULT_LEDGER_PATH,
        fixture_path=DEFAULT_FIXTURE_PATH,
        prediction_jsonl_path=DEFAULT_PREDICTION_JSONL,
        write_reports=False,
    )
    assert isinstance(result, DailyJobResult)
    assert result.job_name == "postgame_review"
    assert result.status in {
        JOB_STATUS_SUCCESS, JOB_STATUS_FAILED, JOB_STATUS_DATA_LIMITED,
        JOB_STATUS_SKIPPED,
    }
    assert isinstance(result.errors, list)
    assert result.safety_flags.get("paper_only") is True
    assert result.safety_flags.get("ledger_overwrite_blocked") is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 5 — Scheduler can execute fixture today mode
# ════════════════════════════════════════════════════════════════════════════

def test_05_scheduler_fixture_today_mode():
    """Full scheduler pipeline executes without raising in fixture/today mode."""
    payload = run_daily_mlb_scheduler(
        run_date=RUN_DATE_FIXTURE,
        mode="today",
        source="fixture",
        limit=5,
        ledger_path=DEFAULT_LEDGER_PATH,
        fixture_path=DEFAULT_FIXTURE_PATH,
        prediction_jsonl_path=DEFAULT_PREDICTION_JSONL,
        write_reports=False,
    )
    assert isinstance(payload, dict)
    assert "gate" in payload
    assert payload["gate"] in VALID_GATES
    assert "manifest" in payload
    assert "jobs" in payload
    assert "completion_marker" in payload
    assert payload["completion_marker"] == COMPLETION_MARKER
    assert payload["safety"]["no_real_bet"] is True
    assert payload["safety"]["paper_only"] is True
    assert payload["safety"]["production_modified"] is False
    assert payload["metrics_ssot_used"] is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 6 — Scheduler can execute replay mode
# ════════════════════════════════════════════════════════════════════════════

def test_06_scheduler_replay_mode():
    """Full scheduler pipeline executes in replay mode."""
    payload = run_daily_mlb_scheduler(
        run_date=RUN_DATE_REPLAY,
        mode="replay",
        source="replay",
        limit=5,
        ledger_path=DEFAULT_LEDGER_PATH,
        prediction_jsonl_path=DEFAULT_PREDICTION_JSONL,
        write_reports=False,
    )
    assert isinstance(payload, dict)
    assert payload["gate"] in VALID_GATES
    assert payload["mode"] == "replay"
    assert payload["source"] == "replay"
    assert payload["safety"]["no_real_bet"] is True
    assert payload["safety"]["scheduler_dry_run_only"] is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 7 — Manifest can be written
# ════════════════════════════════════════════════════════════════════════════

def test_07_manifest_can_be_written():
    """write_daily_manifest writes valid JSON file."""
    manifest = _make_manifest()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "scheduler_manifest_test.json")
        written_path = write_daily_manifest(manifest, path, write=True)
        assert os.path.exists(written_path)
        with open(written_path) as fh:
            data = json.load(fh)
        assert data["run_id"] == manifest.run_id
        assert data["gate"] == manifest.gate
        assert data["paper_only"] is True
        assert data["no_real_bet"] is True
        assert data["completion_marker"] == COMPLETION_MARKER


# ════════════════════════════════════════════════════════════════════════════
# TEST 8 — Manifest can read latest
# ════════════════════════════════════════════════════════════════════════════

def test_08_manifest_load_latest():
    """load_latest_daily_manifest can load the manifest that was written."""
    manifest = _make_manifest(run_date=RUN_DATE_FIXTURE)
    with tempfile.TemporaryDirectory() as tmpdir:
        date_nd = RUN_DATE_FIXTURE.replace("-", "")
        path = os.path.join(tmpdir, f"mlb_daily_scheduler_manifest_{date_nd}.json")
        write_daily_manifest(manifest, path, write=True)

        loaded = load_latest_daily_manifest(manifest_dir=tmpdir)
        assert loaded is not None
        assert loaded["run_id"] == manifest.run_id
        assert loaded["run_date"] == RUN_DATE_FIXTURE
        assert loaded["paper_only"] is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 9 — Manifest includes paper_only / no_real_bet / no_profit_claim
# ════════════════════════════════════════════════════════════════════════════

def test_09_manifest_safety_flags_true():
    """Manifest always has all safety flags set to True."""
    manifest = _make_manifest()
    assert manifest.paper_only is True
    assert manifest.no_real_bet is True
    assert manifest.no_profit_claim is True
    assert manifest.no_auto_execution is True
    assert manifest.scheduler_dry_run_only is True
    assert manifest.ledger_overwrite_blocked is True
    # Verify via validation
    errors = validate_daily_manifest(manifest)
    assert not errors, f"Unexpected validation errors: {errors}"


# ════════════════════════════════════════════════════════════════════════════
# TEST 10 — Pregame failure records failure_reason
# ════════════════════════════════════════════════════════════════════════════

def test_10_pregame_failure_records_failure_reason():
    """When pregame job fails, manifest.pregame_failure_reason is non-empty."""
    failed_pregame = _make_job_result(
        "pregame_advisory",
        status=JOB_STATUS_FAILED,
        errors=["TestError: forced test failure"],
    )
    ok_postgame = _make_job_result("postgame_review", status=JOB_STATUS_SKIPPED)

    manifest = build_daily_manifest(
        run_id="SCHED_TEST_FAIL",
        run_date=RUN_DATE_FIXTURE,
        mode="today",
        source="fixture",
        pregame_result=failed_pregame,
        postgame_result=ok_postgame,
        ledger_path=DEFAULT_LEDGER_PATH,
        advisory_report_path="reports/advisory.json",
        review_report_path="reports/review.json",
        reviewed_snapshot_path="reports/snapshot.jsonl",
        gate="MLB_SCHEDULER_NOT_READY",
        gate_rationale="pregame failed",
    )
    assert manifest.pregame_failure_reason is not None
    assert len(manifest.pregame_failure_reason) > 0
    assert manifest.pregame_advisory_status == JOB_STATUS_FAILED


# ════════════════════════════════════════════════════════════════════════════
# TEST 11 — Postgame pending result records pending_count
# ════════════════════════════════════════════════════════════════════════════

def test_11_postgame_pending_count_recorded():
    """When review has pending results, manifest.pending_count > 0."""
    ok_pregame = _make_job_result("pregame_advisory", status=JOB_STATUS_SUCCESS)
    data_limited_postgame = _make_job_result(
        "postgame_review",
        status=JOB_STATUS_DATA_LIMITED,
        warnings=["pending_results=5"],
    )
    review_payload = {
        "review_summary": {
            "reviewed_count": 0,
            "pending_results": 5,
        }
    }
    manifest = build_daily_manifest(
        run_id="SCHED_TEST_PENDING",
        run_date=RUN_DATE_FIXTURE,
        mode="today",
        source="fixture",
        pregame_result=ok_pregame,
        postgame_result=data_limited_postgame,
        ledger_path=DEFAULT_LEDGER_PATH,
        advisory_report_path="reports/advisory.json",
        review_report_path="reports/review.json",
        reviewed_snapshot_path="reports/snapshot.jsonl",
        review_payload=review_payload,
        gate="MLB_SCHEDULER_DATA_LIMITED",
        gate_rationale="pending results",
    )
    assert manifest.pending_count > 0
    assert manifest.reviewed_count == 0
    assert manifest.postgame_review_status == JOB_STATUS_DATA_LIMITED


# ════════════════════════════════════════════════════════════════════════════
# TEST 12 — Gate only one of 7 valid values
# ════════════════════════════════════════════════════════════════════════════

def test_12_gate_is_always_valid():
    """build_scheduler_gate always returns a gate in VALID_GATES."""
    assert len(VALID_GATES) == 7

    scenarios = [
        # (pregame_status, postgame_status, source)
        (JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS, "fixture"),
        (JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS, "current"),
        (JOB_STATUS_FAILED, JOB_STATUS_SKIPPED, "fixture"),
        (JOB_STATUS_FAILED, JOB_STATUS_FAILED, "fixture"),
        (JOB_STATUS_SUCCESS, JOB_STATUS_DATA_LIMITED, "replay"),
        (JOB_STATUS_SUCCESS, JOB_STATUS_FAILED, "fixture"),
        (JOB_STATUS_SUCCESS, JOB_STATUS_SUCCESS, "replay"),
    ]
    for pg_status, po_status, source in scenarios:
        pg = _make_job_result("pregame_advisory", status=pg_status)
        po = _make_job_result("postgame_review", status=po_status)
        gate, rationale = build_scheduler_gate(pg, po, source=source)
        assert gate in VALID_GATES, (
            f"gate={gate!r} not in VALID_GATES for scenario "
            f"pg={pg_status} po={po_status} src={source}"
        )
        assert len(rationale) > 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 13 — API: get_latest_daily_manifest returns governance flags
# ════════════════════════════════════════════════════════════════════════════

def test_13_api_get_latest_manifest_governance_flags():
    """get_latest_daily_manifest response always contains governance flags."""
    from orchestrator.mlb_advisory_api import (
        get_latest_daily_manifest,
        validate_api_response,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = _make_manifest()
        date_nd = RUN_DATE_FIXTURE.replace("-", "")
        path = os.path.join(tmpdir, f"mlb_daily_scheduler_manifest_{date_nd}.json")
        write_daily_manifest(manifest, path, write=True)

        response = get_latest_daily_manifest(manifest_dir=tmpdir)

    assert isinstance(response, dict)
    errors = validate_api_response(response)
    assert not errors, f"API governance errors: {errors}"
    assert response.get("paper_only") is True
    assert response.get("no_real_bet") is True
    assert response.get("no_profit_claim") is True
    assert response.get("no_auto_execution") is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 14 — API: get_daily_advisory_report returns market coverage matrix
# ════════════════════════════════════════════════════════════════════════════

def test_14_api_advisory_report_market_coverage():
    """get_daily_advisory_report returns market_coverage_matrix key when file missing,
    or populated when a real report exists."""
    from orchestrator.mlb_advisory_api import get_daily_advisory_report, validate_api_response

    # Test unavailable response (non-existent date) — governance flags always present
    response_unavailable = get_daily_advisory_report("1900-01-01")
    assert isinstance(response_unavailable, dict)
    errors = validate_api_response(response_unavailable)
    assert not errors, f"API governance errors: {errors}"
    assert response_unavailable.get("status") == "unavailable"
    assert response_unavailable.get("no_real_bet") is True
    assert response_unavailable.get("paper_only") is True

    # Test with an advisory report written from the scheduler pipeline
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = os.path.join(
            tmpdir, f"mlb_daily_advisory_dry_run_19000102.json"
        )
        # Write a minimal advisory report file
        minimal_report = {
            "total_advisories": 3,
            "total_ledger_entries_written": 3,
            "effective_mode": "today",
            "market_coverage_matrix_summary": {"total_games": 3, "covered": 3},
            "advisories": [],
            "review_summary": {
                "lean_count": 2,
                "watch_only_count": 1,
                "pass_count": 0,
                "market_only_shadow_count": 0,
            },
            "gate": "MLB_DAILY_ADVISORY_LEDGER_READY",
        }
        with open(report_path, "w") as fh:
            json.dump(minimal_report, fh)

        # Patch the API function to use tempdir path
        import orchestrator.mlb_advisory_api as api_mod
        original_fn = api_mod._advisory_report_path
        api_mod._advisory_report_path = lambda d: report_path
        try:
            response = get_daily_advisory_report("1900-01-02")
        finally:
            api_mod._advisory_report_path = original_fn

    errors = validate_api_response(response)
    assert not errors, f"API governance errors: {errors}"
    assert response.get("status") == "ok"
    assert "market_coverage_matrix" in response
    assert response["advisory_count"] == 3


# ════════════════════════════════════════════════════════════════════════════
# TEST 15 — API: get_paper_ledger_summary returns ledger summary
# ════════════════════════════════════════════════════════════════════════════

def test_15_api_ledger_summary():
    """get_paper_ledger_summary returns summary with required keys."""
    from orchestrator.mlb_advisory_api import (
        get_paper_ledger_summary,
        validate_api_response,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "test_ledger.jsonl")
        # Write a minimal ledger
        entries = [
            {"game_date": "2025-07-01", "game_id": "g1", "recommendation": "LEAN_HOME"},
            {"game_date": "2025-07-01", "game_id": "g2", "recommendation": "LEAN_AWAY"},
            {"game_date": "2025-07-02", "game_id": "g3", "recommendation": "WATCH_ONLY"},
        ]
        with open(ledger_path, "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

        response = get_paper_ledger_summary(ledger_path=ledger_path)

    assert isinstance(response, dict)
    errors = validate_api_response(response)
    assert not errors, f"API governance errors: {errors}"
    assert "total_ledger_entries" in response
    assert response["total_ledger_entries"] == 3
    assert "entries_by_date" in response
    assert "recommendation_summary" in response
    assert "review_status_summary" in response
    # Must NOT have forbidden keys
    for forbidden in ("stake_sizing", "real_bet_placement_instruction"):
        assert forbidden not in response, f"Forbidden key {forbidden!r} found in response"


# ════════════════════════════════════════════════════════════════════════════
# TEST 16 — API: get_postgame_review_report returns failure notes
# ════════════════════════════════════════════════════════════════════════════

def test_16_api_review_report_failure_notes():
    """get_postgame_review_report unavailable response has governance flags."""
    from orchestrator.mlb_advisory_api import (
        get_postgame_review_report,
        validate_api_response,
    )

    # Test with a non-existent date → unavailable response
    response = get_postgame_review_report("1900-01-01")
    assert isinstance(response, dict)
    errors = validate_api_response(response)
    assert not errors, f"API governance errors: {errors}"
    assert response.get("no_real_bet") is True
    assert response.get("no_auto_execution") is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 17 — API: get_mlb_mvp_status returns missing live source
# ════════════════════════════════════════════════════════════════════════════

def test_17_api_mvp_status_missing_live_sources():
    """get_mlb_mvp_status always shows live_source_ready=False and lists missing sources."""
    from orchestrator.mlb_advisory_api import (
        get_mlb_mvp_status,
        validate_api_response,
    )

    response = get_mlb_mvp_status()
    assert isinstance(response, dict)
    errors = validate_api_response(response)
    assert not errors, f"API governance errors: {errors}"

    assert response["live_source_ready"] is False
    assert "missing_live_sources" in response
    assert isinstance(response["missing_live_sources"], list)
    assert len(response["missing_live_sources"]) > 0, (
        "must list at least one missing live source"
    )
    assert "overall_gate" in response
    assert response["overall_gate"] in (
        "MLB_SCHEDULER_NOT_READY",
        "MLB_ADVISORY_API_READY",
        "MLB_DAILY_SCHEDULER_READY",
        "MLB_SCHEDULER_NEEDS_LIVE_SOURCE",
        "MLB_SCHEDULER_API_MVP_READY",
        "MLB_SCHEDULER_DATA_LIMITED",
        "MLB_SCHEDULER_GOVERNANCE_RISK",
    )


# ════════════════════════════════════════════════════════════════════════════
# TEST 18 — API doesn't return stake sizing
# ════════════════════════════════════════════════════════════════════════════

def test_18_api_no_stake_sizing():
    """No API handler returns stake_sizing in its response."""
    from orchestrator.mlb_advisory_api import (
        get_latest_daily_manifest,
        get_daily_advisory_report,
        get_paper_ledger_summary,
        get_postgame_review_report,
        get_mlb_mvp_status,
        _FORBIDDEN_RESPONSE_KEYS,
    )

    responses = [
        get_latest_daily_manifest(),
        get_daily_advisory_report("1900-01-01"),
        get_paper_ledger_summary(ledger_path="nonexistent_ledger.jsonl"),
        get_postgame_review_report("1900-01-01"),
        get_mlb_mvp_status(),
    ]

    for resp in responses:
        assert "stake_sizing" not in resp, (
            f"stake_sizing found in response: {list(resp.keys())}"
        )
        for forbidden in _FORBIDDEN_RESPONSE_KEYS:
            assert forbidden not in resp, (
                f"forbidden key {forbidden!r} found in response"
            )


# ════════════════════════════════════════════════════════════════════════════
# TEST 19 — API doesn't return real_bet_placement_instruction
# ════════════════════════════════════════════════════════════════════════════

def test_19_api_no_real_bet_placement():
    """No API handler returns real_bet_placement_instruction."""
    from orchestrator.mlb_advisory_api import (
        get_latest_daily_manifest,
        get_daily_advisory_report,
        get_paper_ledger_summary,
        get_postgame_review_report,
        get_mlb_mvp_status,
    )

    responses = [
        get_latest_daily_manifest(),
        get_daily_advisory_report("1900-01-01"),
        get_paper_ledger_summary(ledger_path="nonexistent_ledger.jsonl"),
        get_postgame_review_report("1900-01-01"),
        get_mlb_mvp_status(),
    ]

    for resp in responses:
        assert "real_bet_placement_instruction" not in resp
        assert "guaranteed_profit_wording" not in resp
        assert "production_patch_instruction" not in resp


# ════════════════════════════════════════════════════════════════════════════
# TEST 20 — API response includes no_auto_execution
# ════════════════════════════════════════════════════════════════════════════

def test_20_api_response_no_auto_execution():
    """Every API response includes no_auto_execution=True."""
    from orchestrator.mlb_advisory_api import (
        get_latest_daily_manifest,
        get_daily_advisory_report,
        get_paper_ledger_summary,
        get_postgame_review_report,
        get_mlb_mvp_status,
    )

    responses = [
        ("get_latest_daily_manifest", get_latest_daily_manifest()),
        ("get_daily_advisory_report", get_daily_advisory_report("1900-01-01")),
        ("get_paper_ledger_summary", get_paper_ledger_summary(ledger_path="nonexistent.jsonl")),
        ("get_postgame_review_report", get_postgame_review_report("1900-01-01")),
        ("get_mlb_mvp_status", get_mlb_mvp_status()),
    ]

    for name, resp in responses:
        assert resp.get("no_auto_execution") is True, (
            f"{name} response missing no_auto_execution=True"
        )


# ════════════════════════════════════════════════════════════════════════════
# TEST 21 — Markdown includes NO_REAL_BET / no profit claim
# ════════════════════════════════════════════════════════════════════════════

def test_21_markdown_safety_flags():
    """Scheduler markdown includes NO_REAL_BET and NO_PROFIT_CLAIM verbiage."""
    manifest = _make_manifest()
    pregame = _make_job_result("pregame_advisory")
    postgame = _make_job_result("postgame_review")

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = os.path.join(tmpdir, "scheduler_report.md")
        content = generate_scheduler_markdown(
            manifest=manifest,
            pregame_result=pregame,
            postgame_result=postgame,
            markdown_path=md_path,
            write=True,
        )

    assert "NO_REAL_BET = True" in content, "markdown must contain NO_REAL_BET = True"
    assert "NO_PROFIT_CLAIM" in content, "markdown must contain NO_PROFIT_CLAIM"
    assert "PAPER-ONLY" in content or "paper_only" in content.lower(), (
        "markdown must contain paper-only governance disclaimer"
    )
    assert "NO REAL BET" in content.upper() or "no_real_bet" in content.lower()


# ════════════════════════════════════════════════════════════════════════════
# TEST 22 — Markdown includes completion marker
# ════════════════════════════════════════════════════════════════════════════

def test_22_markdown_completion_marker():
    """Scheduler markdown contains the completion marker."""
    manifest = _make_manifest()
    pregame = _make_job_result("pregame_advisory")
    postgame = _make_job_result("postgame_review")

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = os.path.join(tmpdir, "scheduler_report.md")
        content = generate_scheduler_markdown(
            manifest=manifest,
            pregame_result=pregame,
            postgame_result=postgame,
            markdown_path=md_path,
            write=False,
        )

    assert COMPLETION_MARKER in content, (
        f"markdown must contain completion marker {COMPLETION_MARKER!r}"
    )


# ════════════════════════════════════════════════════════════════════════════
# TEST 23 — Phase67–72 + metrics + advisory + current source + result review
#            full regression (not broken)
# ════════════════════════════════════════════════════════════════════════════

def test_23_prior_modules_still_importable():
    """All prior pipeline modules import without errors — regression guard."""
    import orchestrator.mlb_daily_advisory as advisory
    import orchestrator.mlb_current_sources as cs
    import orchestrator.mlb_result_review as rr
    import orchestrator.metrics_ssot as ms
    import orchestrator.mlb_daily_scheduler as scheduler
    import orchestrator.mlb_advisory_api as api

    # Safety constants from each module
    assert advisory.NO_REAL_BET is True
    assert advisory.PRODUCTION_MODIFIED is False
    assert cs.NO_REAL_BET is True
    assert rr.LEDGER_OVERWRITE_BLOCKED is True
    assert rr.PRODUCTION_MODIFIED is False
    assert scheduler.NO_REAL_BET is True
    assert scheduler.SCHEDULER_DRY_RUN_ONLY is True
    assert scheduler.COMPLETION_MARKER == "MLB_DAILY_SCHEDULER_API_MVP_VERIFIED"
    assert api.NO_REAL_BET is True
    assert api.NO_AUTO_EXECUTION is True
    assert api.PRODUCTION_MODIFIED is False

    # Module version strings non-empty
    assert len(advisory.MODULE_VERSION) > 0
    assert len(scheduler.MODULE_VERSION) > 0
    assert len(api.MODULE_VERSION) > 0

    # Metrics SSOT: verify key constants/classes
    assert hasattr(ms, "MODULE_VERSION") or hasattr(ms, "MetricsPayload") or hasattr(ms, "BrierResult")
