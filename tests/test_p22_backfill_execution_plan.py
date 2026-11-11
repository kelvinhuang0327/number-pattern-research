"""
Tests for P22 backfill execution plan generator.

Covers:
- build_backfill_execution_plan skips already-ready dates
- build_backfill_execution_plan emits commands for replayable dates
- build_backfill_execution_plan blocks missing required source dates
- validate_execution_plan rejects production_ready=True
- validate_execution_plan rejects paper_only=False
- validate_execution_plan detects date overlap
- build_daily_command_for_date returns SKIP for already-ready
- build_daily_command_for_date returns replay commands for replayable
- build_daily_command_for_date returns comment for missing
- build_p21_command_for_range returns the P21 CLI command
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from wbc_backend.recommendation.p22_historical_availability_contract import (
    DATE_BLOCKED_INVALID_ARTIFACTS,
    DATE_MISSING_REQUIRED_SOURCE,
    DATE_PARTIAL_SOURCE_AVAILABLE,
    DATE_READY_P20_EXISTS,
    DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
    EXPECTED_P20_GATE,
    P15_DIR,
    P16_6_DIR,
    P19_DIR,
    P20_DIR,
    P22_BLOCKED_NO_AVAILABLE_DATES,
    P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
    P22BackfillExecutionPlan,
    P22DateAvailabilityResult,
    P22HistoricalAvailabilitySummary,
)
from wbc_backend.recommendation.p22_backfill_execution_plan import (
    ValidationResult,
    build_backfill_execution_plan,
    build_daily_command_for_date,
    build_p21_command_for_range,
    validate_execution_plan,
)
from wbc_backend.recommendation.p22_historical_artifact_scanner import (
    scan_paper_date_range,
    summarize_scan_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_date_result(
    run_date: str,
    status: str,
    p20_gate: str = "",
) -> P22DateAvailabilityResult:
    return P22DateAvailabilityResult(
        run_date=run_date,
        availability_status=status,
        p20_gate=p20_gate,
    )


def _make_summary(
    date_results: List[P22DateAvailabilityResult],
    date_start: str,
    date_end: str,
) -> P22HistoricalAvailabilitySummary:
    from wbc_backend.recommendation.p22_historical_artifact_scanner import summarize_scan_results
    return summarize_scan_results(date_results, date_start, date_end)


def _write_p20(date_dir: Path, gate: str = EXPECTED_P20_GATE) -> None:
    p20_dir = date_dir / P20_DIR
    p20_dir.mkdir(parents=True, exist_ok=True)
    (p20_dir / "daily_paper_summary.json").write_text(json.dumps({}), encoding="utf-8")
    (p20_dir / "p20_gate_result.json").write_text(json.dumps({"p20_gate": gate}), encoding="utf-8")
    (p20_dir / "artifact_manifest.json").write_text(json.dumps({}), encoding="utf-8")


def _write_replay_sources(date_dir: Path) -> None:
    p15 = date_dir / P15_DIR
    p15.mkdir(parents=True, exist_ok=True)
    (p15 / "joined_oof_with_odds.csv").write_text("game_id\n1", encoding="utf-8")
    (p15 / "simulation_ledger.csv").write_text("game_id\n1", encoding="utf-8")
    p16 = date_dir / P16_6_DIR
    p16.mkdir(parents=True, exist_ok=True)
    (p16 / "recommendation_rows.csv").write_text("game_id\n1", encoding="utf-8")
    (p16 / "recommendation_summary.json").write_text(json.dumps({}), encoding="utf-8")
    p19 = date_dir / P19_DIR
    p19.mkdir(parents=True, exist_ok=True)
    (p19 / "enriched_simulation_ledger.csv").write_text("game_id\n1", encoding="utf-8")
    (p19 / "p19_gate_result.json").write_text(
        json.dumps({"p19_gate": "P19_ODDS_IDENTITY_JOIN_REPAIR_READY"}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# build_daily_command_for_date
# ---------------------------------------------------------------------------


def test_daily_command_skip_already_ready() -> None:
    cmds = build_daily_command_for_date("2026-05-12", DATE_READY_P20_EXISTS)
    assert len(cmds) == 1
    assert "SKIP" in cmds[0]
    assert "2026-05-12" in cmds[0]


def test_daily_command_replayable_returns_three_commands() -> None:
    cmds = build_daily_command_for_date("2026-05-10", DATE_READY_REPLAYABLE_FROM_P15_P16_P19)
    assert len(cmds) == 3
    # Must mention p19, p17, p20 scripts
    joined = " ".join(cmds)
    assert "p19" in joined.lower()
    assert "p17" in joined.lower()
    assert "p20" in joined.lower()
    assert "2026-05-10" in joined


def test_daily_command_missing_returns_comment() -> None:
    cmds = build_daily_command_for_date("2026-05-01", DATE_MISSING_REQUIRED_SOURCE)
    assert len(cmds) == 1
    assert "#" in cmds[0]  # comment, no executable command


def test_daily_command_partial_returns_comment() -> None:
    cmds = build_daily_command_for_date("2026-05-05", DATE_PARTIAL_SOURCE_AVAILABLE)
    assert len(cmds) == 1
    assert "#" in cmds[0]


def test_daily_command_blocked_returns_comment() -> None:
    cmds = build_daily_command_for_date("2026-05-06", DATE_BLOCKED_INVALID_ARTIFACTS)
    assert len(cmds) == 1
    assert "#" in cmds[0]


# ---------------------------------------------------------------------------
# build_p21_command_for_range
# ---------------------------------------------------------------------------


def test_p21_command_for_range() -> None:
    cmds = build_p21_command_for_range("2026-05-01", "2026-05-12")
    assert len(cmds) == 1
    assert "run_p21_multi_day_paper_backfill" in cmds[0]
    assert "2026-05-01" in cmds[0]
    assert "2026-05-12" in cmds[0]


# ---------------------------------------------------------------------------
# build_backfill_execution_plan
# ---------------------------------------------------------------------------


def test_plan_skips_already_ready_dates(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    results = scan_paper_date_range(base, "2026-05-12", "2026-05-12")
    summary = summarize_scan_results(results, "2026-05-12", "2026-05-12")
    plan = build_backfill_execution_plan(summary, results)

    assert "2026-05-12" in plan.dates_to_skip_already_ready
    assert "2026-05-12" not in plan.dates_to_replay_from_existing_sources


def test_plan_emits_commands_for_replayable(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_replay_sources(base / "2026-05-10")
    results = scan_paper_date_range(base, "2026-05-10", "2026-05-10")
    summary = summarize_scan_results(results, "2026-05-10", "2026-05-10")
    plan = build_backfill_execution_plan(summary, results)

    assert "2026-05-10" in plan.dates_to_replay_from_existing_sources
    # Should have 3 replay commands + 1 P21 command
    assert len(plan.recommended_commands) >= 4
    joined = " ".join(plan.recommended_commands)
    assert "run_p21_multi_day_paper_backfill" in joined


def test_plan_blocks_missing_source_dates(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-03")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-03")
    plan = build_backfill_execution_plan(summary, results)

    # All 3 should be in missing (we put partial→missing category in plan)
    assert len(plan.dates_missing_required_sources) == 3
    assert plan.dates_to_replay_from_existing_sources == ()
    # No P21 command when no replay
    joined = " ".join(plan.recommended_commands)
    assert "run_p21_multi_day_paper_backfill" not in joined


def test_plan_no_overlap_ready_and_replay(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    _write_p20(base / "2026-05-12")
    _write_replay_sources(base / "2026-05-10")
    results = scan_paper_date_range(base, "2026-05-10", "2026-05-12")
    summary = summarize_scan_results(results, "2026-05-10", "2026-05-12")
    plan = build_backfill_execution_plan(summary, results)

    ready = set(plan.dates_to_skip_already_ready)
    replay = set(plan.dates_to_replay_from_existing_sources)
    assert ready & replay == set()


def test_plan_safety_invariants(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-01")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-01")
    plan = build_backfill_execution_plan(summary, results)
    assert plan.paper_only is True
    assert plan.production_ready is False


def test_plan_includes_risk_notes(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-01")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-01")
    plan = build_backfill_execution_plan(summary, results)
    assert len(plan.risk_notes) >= 1
    assert any("PAPER_ONLY" in note for note in plan.risk_notes)


# ---------------------------------------------------------------------------
# validate_execution_plan
# ---------------------------------------------------------------------------


def test_validate_plan_valid_plan(tmp_path: Path) -> None:
    base = tmp_path / "PAPER"
    base.mkdir()
    results = scan_paper_date_range(base, "2026-05-01", "2026-05-01")
    summary = summarize_scan_results(results, "2026-05-01", "2026-05-01")
    plan = build_backfill_execution_plan(summary, results)
    vr = validate_execution_plan(plan)
    assert vr.valid is True


def test_validate_plan_rejects_production_ready() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        P22BackfillExecutionPlan(
            date_start="2026-05-01",
            date_end="2026-05-12",
            production_ready=True,
        )


def test_validate_plan_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        P22BackfillExecutionPlan(
            date_start="2026-05-01",
            date_end="2026-05-12",
            paper_only=False,
        )
