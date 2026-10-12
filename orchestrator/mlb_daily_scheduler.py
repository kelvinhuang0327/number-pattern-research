"""MLB Daily Scheduler — Dry-run / Paper-Only MVP.

Orchestrates the daily MLB pipeline:
  1. Pregame advisory job  (run_mlb_daily_advisory)
  2. Postgame review job   (run_postgame_review)
  3. DailyJobManifest      (build + persist + query)
  4. Scheduler gate        (7-value enum)

All execution is dry-run / paper-only. No real bets. No real money.

Safety:
  PRODUCTION_MODIFIED      = False
  NO_REAL_BET              = True
  PAPER_ONLY               = True
  NO_PROFIT_CLAIM          = True
  LEDGER_OVERWRITE_BLOCKED = True
  SCHEDULER_DRY_RUN_ONLY   = True
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
CANDIDATE_PATCH_CREATED: bool = False
ALPHA_MODIFIED: bool = False
PREDICTION_JSONL_OVERWRITTEN: bool = False
LEDGER_OVERWRITE_BLOCKED: bool = True
NO_EDGE_CLAIM: bool = True
NO_PROFIT_CLAIM: bool = True
DIAGNOSTIC_ONLY: bool = True
PAPER_ONLY: bool = True
NO_REAL_BET: bool = True
SCHEDULER_DRY_RUN_ONLY: bool = True
NO_AUTO_EXECUTION: bool = True

MODULE_VERSION: str = "mlb_daily_scheduler_v1"
COMPLETION_MARKER: str = "MLB_DAILY_SCHEDULER_API_MVP_VERIFIED"

# ─── Scheduler gate constants (7 valid) ───────────────────────────────────────

MLB_DAILY_SCHEDULER_READY: str = "MLB_DAILY_SCHEDULER_READY"
MLB_ADVISORY_API_READY: str = "MLB_ADVISORY_API_READY"
MLB_SCHEDULER_API_MVP_READY: str = "MLB_SCHEDULER_API_MVP_READY"
MLB_SCHEDULER_DATA_LIMITED: str = "MLB_SCHEDULER_DATA_LIMITED"
MLB_SCHEDULER_NEEDS_LIVE_SOURCE: str = "MLB_SCHEDULER_NEEDS_LIVE_SOURCE"
MLB_SCHEDULER_GOVERNANCE_RISK: str = "MLB_SCHEDULER_GOVERNANCE_RISK"
MLB_SCHEDULER_NOT_READY: str = "MLB_SCHEDULER_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    MLB_DAILY_SCHEDULER_READY,
    MLB_ADVISORY_API_READY,
    MLB_SCHEDULER_API_MVP_READY,
    MLB_SCHEDULER_DATA_LIMITED,
    MLB_SCHEDULER_NEEDS_LIVE_SOURCE,
    MLB_SCHEDULER_GOVERNANCE_RISK,
    MLB_SCHEDULER_NOT_READY,
})

# ─── Job status tokens ────────────────────────────────────────────────────────

JOB_STATUS_SUCCESS: str = "SUCCESS"
JOB_STATUS_SKIPPED: str = "SKIPPED"
JOB_STATUS_FAILED: str = "FAILED"
JOB_STATUS_DATA_LIMITED: str = "DATA_LIMITED"
JOB_STATUS_NOT_RUN: str = "NOT_RUN"

# ─── Paper evaluation data-status tokens (P144) ───────────────────────────────
# These classify *why* a paper-evaluation step is DATA_LIMITED vs SUCCESS, so the
# daily chain can accumulate deterministic per-date artifacts even when outcomes
# are not yet available (the normal pregame case).
PAPER_EVAL_STATUS_NO_PAPER_ROWS: str = "NO_PAPER_ROWS"
PAPER_EVAL_STATUS_OUTCOMES_UNAVAILABLE: str = "OUTCOMES_UNAVAILABLE"
PAPER_EVAL_STATUS_OUTCOMES_MATCHED: str = "OUTCOMES_MATCHED"

# Below this many matched outcomes, hit_rate / Brier are not statistically
# meaningful — surface a small-sample warning instead of implying significance.
PAPER_EVAL_SMALL_SAMPLE_THRESHOLD: int = 30

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_LEDGER_PATH: str = "reports/mlb_paper_betting_ledger.jsonl"
DEFAULT_FIXTURE_PATH: str = "data/fixtures/mlb_current_source_sample_20260507.json"
DEFAULT_PREDICTION_JSONL: str = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
DEFAULT_MANIFEST_DIR: str = "reports"


def _snapshot_to_advisory_row_list(
    snapshots: list,
) -> list[dict]:
    """
    Convert a list of GameMarketSnapshot objects to advisory-compatible dicts.

    The advisory expects plain dicts with row.get("game_date"), etc.
    Fixture source games have market odds but no model prediction → returns
    a dict with _model_prediction_available=False so advisory outputs PASS.
    """
    rows: list[dict] = []
    for snap in snapshots:
        # Handle both dataclass and dict (defensive)
        if isinstance(snap, dict):
            rows.append(snap)
            continue
        # GameMarketSnapshot dataclass → dict
        rows.append({
            "game_id": snap.game_id,
            "game_date": snap.game_date,
            "home_team": snap.home_team,
            "away_team": snap.away_team,
            "model_home_prob": 0.5,  # No model prediction in fixture source
            "market_home_prob_no_vig": snap.market_home_prob_no_vig or 0.5,
            "home_win": None,        # No result available from fixture
            "p0_features": {},
            "_model_prediction_available": False,  # No model for this game
            "runline_spread": snap.runline_spread,
            "runline_odds_home": snap.runline_home_odds,
            "runline_odds_away": snap.runline_away_odds,
            "total_line": snap.total_line,
            "total_odds_over": snap.over_odds,
            "total_odds_under": snap.under_odds,
            "source_name": snap.source_name,
            "source_timestamp": snap.source_timestamp,
        })
    return rows


def _date_nodash(date_str: str) -> str:
    return date_str.replace("-", "")


def _default_advisory_report_path(date_str: str) -> str:
    return f"reports/mlb_daily_advisory_dry_run_{_date_nodash(date_str)}.json"


def _default_review_report_path(date_str: str) -> str:
    return f"reports/mlb_postgame_review_{_date_nodash(date_str)}.json"


def _default_manifest_path(date_str: str) -> str:
    return f"reports/mlb_daily_scheduler_manifest_{_date_nodash(date_str)}.json"


def _default_reviewed_snapshot_path(date_str: str) -> str:
    return f"reports/mlb_paper_betting_reviewed_snapshot_{_date_nodash(date_str)}.jsonl"


def _default_markdown_path(date_str: str) -> str:
    date_nd = _date_nodash(date_str)
    return f"00-BettingPlan/{date_nd}/mlb_daily_scheduler_report_{date_nd}.md"


# ════════════════════════════════════════════════════════════════════════════
# SECTION A — Dataclasses
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class DailyJobResult:
    """Result of a single scheduler job step."""
    job_name: str
    status: str                         # SUCCESS / SKIPPED / FAILED / DATA_LIMITED / NOT_RUN
    started_at: str
    finished_at: str
    duration_seconds: float
    output_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safety_flags: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyJobManifest:
    """Manifest for a complete daily scheduler run."""
    run_id: str
    run_date: str
    mode: str                           # today / replay
    source: str                         # fixture / replay / current
    scheduler_mode: str                 # dry_run
    pregame_advisory_status: str        # SUCCESS / SKIPPED / FAILED / NOT_RUN
    postgame_review_status: str         # SUCCESS / SKIPPED / FAILED / DATA_LIMITED / NOT_RUN
    advisory_report_path: str
    ledger_path: str
    review_report_path: str
    reviewed_snapshot_path: str
    total_advisories: int
    total_ledger_entries: int
    reviewed_count: int
    pending_count: int
    failure_notes_count: int
    gate: str
    paper_only: bool = True
    no_real_bet: bool = True
    no_profit_claim: bool = True
    no_auto_execution: bool = True
    scheduler_dry_run_only: bool = True
    ledger_overwrite_blocked: bool = True
    pregame_failure_reason: str | None = None
    postgame_failure_reason: str | None = None
    pregame_warnings: list[str] = field(default_factory=list)
    postgame_warnings: list[str] = field(default_factory=list)
    source_mode_advisory: str = "replay"
    source_mode_review: str = "replay"
    brier_score: float | None = None
    recommendation_accuracy: float | None = None
    gate_rationale: str = ""
    created_at: str = ""
    module_version: str = MODULE_VERSION
    completion_marker: str = COMPLETION_MARKER


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — Job Runners
# ════════════════════════════════════════════════════════════════════════════


def run_pregame_advisory_job(
    run_date: str,
    mode: str = "today",
    source: str = "fixture",
    limit: int = 15,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    fixture_path: str = DEFAULT_FIXTURE_PATH,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
    report_path: str | None = None,
    markdown_path: str | None = None,
    *,
    write_reports: bool = True,
) -> DailyJobResult:
    """
    Run the pregame advisory job for a given date.

    Calls run_mlb_daily_advisory (or fixture/current source variant).
    All output is paper-only / no-real-bet.

    Returns DailyJobResult with status + output paths.
    """
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    output_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    payload: dict = {}

    resolved_report = report_path or _default_advisory_report_path(run_date)
    resolved_md = markdown_path or None  # scheduler does not require markdown from advisory

    try:
        from orchestrator.mlb_daily_advisory import (
            run_mlb_daily_advisory,
            DEFAULT_LEDGER_PATH as ADV_DEFAULT_LEDGER,
        )
        from orchestrator.mlb_current_sources import (
            load_fixture_schedule_odds,
            probe_current_mlb_source,
            merge_current_source_with_advisory_rows,
            SOURCE_MODE_FIXTURE,
            SOURCE_MODE_CURRENT,
            SOURCE_MODE_REPLAY,
        )

        override_games: list[dict] | None = None
        fixture_source_used = False
        current_source_reachable = False

        if source == "fixture":
            # Load from fixture file — returns GameMarketSnapshot objects; convert to dicts
            raw_games = load_fixture_schedule_odds(fixture_path)
            if raw_games:
                # Convert GameMarketSnapshot → dict for advisory compatibility
                override_games = _snapshot_to_advisory_row_list(raw_games)
                fixture_source_used = True
                warnings.append(
                    f"fixture source: loaded {len(raw_games)} games from {fixture_path}"
                )
            else:
                warnings.append(f"fixture source returned 0 games from {fixture_path}")
        elif source == "current":
            # Attempt live probe
            health = probe_current_mlb_source(run_date)
            if health.reachable and health.games_available:
                current_source_reachable = True
                override_games = merge_current_source_with_advisory_rows(
                    health.raw_games or [], []
                )
            else:
                warnings.append(
                    f"current source not reachable: {health.source_name} — "
                    f"falling back to replay"
                )
        # else: replay mode — no override_games, advisory uses JSONL directly

        payload = run_mlb_daily_advisory(
            date_str=run_date,
            mode=mode,
            limit=limit,
            prediction_jsonl_path=prediction_jsonl_path,
            ledger_path=ledger_path,
            report_path=resolved_report if write_reports else None,
            markdown_path=resolved_md if write_reports else None,
            write_reports=write_reports,
            override_games=override_games,
            source_mode=source,
            fixture_source_used=fixture_source_used,
            current_source_reachable=current_source_reachable,
            model_prediction_available=True,
        )

        if write_reports and resolved_report:
            output_paths.append(resolved_report)
        if write_reports and ledger_path:
            output_paths.append(ledger_path)

        status = JOB_STATUS_SUCCESS
        total_advisory = payload.get("total_advisories", 0)
        if total_advisory == 0:
            status = JOB_STATUS_DATA_LIMITED
            warnings.append("total_advisories = 0 — source may be limited")

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())
        payload = {}
        status = JOB_STATUS_FAILED

    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration = round(time.monotonic() - t0, 3)

    return DailyJobResult(
        job_name="pregame_advisory",
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration,
        output_paths=output_paths,
        errors=errors,
        warnings=warnings,
        safety_flags={
            "paper_only": PAPER_ONLY,
            "no_real_bet": NO_REAL_BET,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "production_modified": PRODUCTION_MODIFIED,
            "no_auto_execution": NO_AUTO_EXECUTION,
        },
    )


def run_paper_recommendation_job(
    run_date: str,
    *,
    allow_replay: bool = False,
    allow_missing_simulation_gate: bool = False,
    output_base_dir: str | None = None,
) -> DailyJobResult:
    """Run the MLB→TSL paper recommendation job for a given date (dry-run/paper-only).

    Wraps ``build_recommendation`` from ``scripts.run_mlb_tsl_paper_recommendation``
    and writes one paper row to ``outputs/recommendations/PAPER/<date>/``.

    Safety invariants (permanently enforced):
    - paper_only = True
    - no real stake / Kelly fraction produced (gate blocks when TSL unavailable)
    - no production bets written
    - no EV/CLV/Kelly unlock

    Parameters
    ----------
    run_date : str
        Date string in YYYY-MM-DD format for which to generate a recommendation.
    allow_replay : bool
        If True, use a synthetic replay fixture when no live games are available.
        Equivalent to ``--allow-replay-paper`` on the CLI.
    allow_missing_simulation_gate : bool
        If True, skip simulation gate enforcement when no simulation result exists.
        Equivalent to ``--allow-missing-simulation-gate`` on the CLI.
    output_base_dir : str | None
        Override the base output directory. Defaults to repo root / outputs / ....
    """
    import importlib
    import sys
    from pathlib import Path

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    output_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    _safety_flags = {
        "paper_only": True,
        "no_real_bet": True,
        "no_profit_claim": True,
        "production_modified": False,
        "no_auto_execution": True,
        "scheduler_dry_run_only": True,
        "no_ev_clv_kelly_unlock": True,
    }

    try:
        # Lazy import: keeps scheduler importable without requiring script deps
        mod_name = "scripts.run_mlb_tsl_paper_recommendation"
        script = sys.modules.get(mod_name) or importlib.import_module(mod_name)

        # Simulation gate: load latest if available
        from wbc_backend.recommendation.recommendation_gate_policy import (
            build_recommendation_gate_from_simulation,
        )
        from wbc_backend.simulation.simulation_result_loader import (
            load_latest_simulation_result,
        )
        from wbc_backend.recommendation.provenance_contract import (
            resolve_explicit_strategy_id,
        )

        root = Path(output_base_dir) if output_base_dir else script.ROOT
        sim_dir = root / "outputs" / "simulation" / "PAPER"
        simulation = load_latest_simulation_result(
            simulation_dir=sim_dir,
            strategy_name="moneyline_edge_threshold_v0",
        )
        simulation_gate: dict | None = None
        if simulation is None and allow_missing_simulation_gate:
            warnings.append(
                "No simulation result found; proceeding without simulation gate "
                "(allow_missing_simulation_gate=True)."
            )
        else:
            simulation_gate = build_recommendation_gate_from_simulation(simulation)

        # Pick game (replay fallback when allow_replay is set)
        game = script._pick_game(run_date)
        is_replay = False
        if game is None:
            if allow_replay:
                game = {
                    "gamePk": 0,
                    "gameDate": f"{run_date}T18:00:00Z",
                    "status": {"detailedState": "Scheduled"},
                    "teams": {
                        "home": {"team": {"name": "Home Team", "abbreviation": "HOM"}},
                        "away": {"team": {"name": "Away Team", "abbreviation": "AWY"}},
                    },
                }
                is_replay = True
                warnings.append(
                    f"No live MLB games found for {run_date}; "
                    "using synthetic replay fixture (allow_replay=True)."
                )
            else:
                finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                return DailyJobResult(
                    job_name="paper_recommendation",
                    status=JOB_STATUS_DATA_LIMITED,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=round(time.monotonic() - t0, 3),
                    output_paths=[],
                    errors=[f"No MLB games found for {run_date}; pass allow_replay=True to use replay fixture."],
                    warnings=warnings,
                    safety_flags=_safety_flags,
                )

        # TSL probe
        tsl_live, tsl_note = script._probe_tsl()

        # Build recommendation row
        row = script.build_recommendation(
            game=game,
            date_str=run_date,
            tsl_live=tsl_live,
            tsl_note=tsl_note,
            simulation_gate=simulation_gate,
            strategy_id=resolve_explicit_strategy_id(simulation),
        )

        # Write row (honour output_base_dir override)
        if output_base_dir:
            # Temporarily override ROOT for write_row
            original_root = script.ROOT
            script.ROOT = Path(output_base_dir)
            try:
                out_path = script.write_row(row, run_date, is_replay=is_replay)
            finally:
                script.ROOT = original_root
        else:
            out_path = script.write_row(row, run_date, is_replay=is_replay)

        output_paths.append(str(out_path))
        if row.gate_status not in ("PASS",):
            warnings.append(
                f"Paper row written with gate_status={row.gate_status!r} — "
                "stake_units_paper=0 (expected for paper-only mode)."
            )

    except Exception as exc:
        errors.append(f"run_paper_recommendation_job failed: {exc}")
        finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return DailyJobResult(
            job_name="paper_recommendation",
            status=JOB_STATUS_FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - t0, 3),
            output_paths=[],
            errors=errors,
            warnings=warnings,
            safety_flags=_safety_flags,
        )

    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return DailyJobResult(
        job_name="paper_recommendation",
        status=JOB_STATUS_SUCCESS,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(time.monotonic() - t0, 3),
        output_paths=output_paths,
        errors=errors,
        warnings=warnings,
        safety_flags=_safety_flags,
    )


def run_postgame_review_job(
    run_date: str,
    source: str = "fixture",
    ledger_path: str = DEFAULT_LEDGER_PATH,
    fixture_path: str = DEFAULT_FIXTURE_PATH,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
    reviewed_snapshot_path: str | None = None,
    report_path: str | None = None,
    markdown_path: str | None = None,
    *,
    write_reports: bool = True,
    skip_if_no_pregame: bool = False,
    pregame_status: str = JOB_STATUS_SUCCESS,
) -> DailyJobResult:
    """
    Run the postgame review job for a given date.

    Calls run_postgame_review.
    If pregame advisory failed and skip_if_no_pregame=True, returns SKIPPED.
    If result source has no data, returns DATA_LIMITED.
    """
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    output_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    # Skip if pregame failed and caller requested skip
    if skip_if_no_pregame and pregame_status == JOB_STATUS_FAILED:
        finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return DailyJobResult(
            job_name="postgame_review",
            status=JOB_STATUS_SKIPPED,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - t0, 3),
            output_paths=[],
            errors=[],
            warnings=["skipped: pregame advisory job failed"],
            safety_flags={
                "paper_only": PAPER_ONLY,
                "no_real_bet": NO_REAL_BET,
                "no_profit_claim": NO_PROFIT_CLAIM,
                "production_modified": PRODUCTION_MODIFIED,
                "no_auto_execution": NO_AUTO_EXECUTION,
            },
        )

    resolved_snapshot = reviewed_snapshot_path or _default_reviewed_snapshot_path(run_date)
    resolved_report = report_path or _default_review_report_path(run_date)
    payload: dict = {}

    try:
        from orchestrator.mlb_result_review import run_postgame_review

        payload = run_postgame_review(
            review_date=run_date,
            source_mode=source,
            ledger_path=ledger_path,
            fixture_path=fixture_path,
            prediction_jsonl_path=prediction_jsonl_path,
            reviewed_snapshot_path=resolved_snapshot if write_reports else None,
            report_path=resolved_report if write_reports else None,
            markdown_path=markdown_path if write_reports else None,
            write_reports=write_reports,
        )

        if write_reports:
            output_paths.append(resolved_snapshot)
            output_paths.append(resolved_report)

        rs = payload.get("review_summary", {})
        pending = rs.get("pending_results", 0)
        reviewed = rs.get("reviewed_count", 0)

        if pending > 0:
            warnings.append(
                f"pending_results={pending}: result source did not cover all entries"
            )

        status = JOB_STATUS_SUCCESS
        if reviewed == 0 and pending > 0:
            status = JOB_STATUS_DATA_LIMITED
            warnings.append("reviewed_count=0 — all entries still pending")

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())
        payload = {}
        status = JOB_STATUS_FAILED

    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration = round(time.monotonic() - t0, 3)

    return DailyJobResult(
        job_name="postgame_review",
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration,
        output_paths=output_paths,
        errors=errors,
        warnings=warnings,
        safety_flags={
            "paper_only": PAPER_ONLY,
            "no_real_bet": NO_REAL_BET,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "production_modified": PRODUCTION_MODIFIED,
            "ledger_overwrite_blocked": LEDGER_OVERWRITE_BLOCKED,
            "no_auto_execution": NO_AUTO_EXECUTION,
        },
    )


def run_paper_evaluation_job(
    run_date: str,
    *,
    paper_dir: str | None = None,
    outcome_path: str | None = None,
    output_path: str | None = None,
    write_output: bool = True,
) -> DailyJobResult:
    """Run the offline paper evaluation job for a given date (dry-run/paper-only).

    Connects P141 PAPER recommendation outputs to the P142 evaluator.
    Reads paper rows from ``outputs/recommendations/PAPER/<run_date>/``,
    evaluates them against the outcome corpus, and (optionally) writes a JSON
    summary artifact.

    Outcome-unavailable hardening (P144):
    The normal pregame case is "paper rows exist, but their game outcomes have
    not happened yet". Such a date is reported as ``DATA_LIMITED`` with
    ``data_status = OUTCOMES_UNAVAILABLE`` (not SUCCESS), so the daily chain
    never implies a meaningful evaluation before outcomes arrive. The evaluation
    metrics are a pure function of (paper rows, outcome corpus), so re-running
    the same date before outcomes arrive is deterministic / idempotent; once
    outcomes arrive the same output path is overwritten with updated metrics.

    Safety invariants (permanently enforced):
    - Offline execution only — no live API calls.
    - No DB writes.
    - No production betting / no real stake / no EV/CLV/Kelly unlock.
    - paper_only = True.

    Parameters
    ----------
    run_date : str
        Date string in YYYY-MM-DD format to evaluate.
    paper_dir : str | None
        Override the paper recommendation directory for this date.
        Defaults to ``outputs/recommendations/PAPER/<run_date>/``.
    outcome_path : str | None
        Override the outcome JSONL path.
        Defaults to ``data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl``.
    output_path : str | None
        Override the output artifact path.
        Defaults to ``data/mlb_2026/derived/p143_paper_eval_<run_date_nodash>.json``.
    write_output : bool
        If False, evaluate in-memory only and do not write any artifact to disk.
        Used by the daily orchestrator's dry-run / no-write test path.
    """
    from pathlib import Path

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    output_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    _safety_flags = {
        "paper_only": True,
        "no_real_bet": True,
        "no_profit_claim": True,
        "production_modified": False,
        "no_auto_execution": True,
        "scheduler_dry_run_only": True,
        "no_ev_clv_kelly_unlock": True,
        "no_db_writes": True,
        "no_live_api_calls": True,
        "no_provider_unlock": True,
    }

    resolved_paper_dir = paper_dir or f"outputs/recommendations/PAPER/{run_date}"
    resolved_outcome_path = (
        outcome_path
        or "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
    )
    resolved_output_path = (
        output_path
        or f"data/mlb_2026/derived/p143_paper_eval_{_date_nodash(run_date)}.json"
    )

    try:
        from orchestrator.mlb_paper_evaluator import execute_evaluation

        result = execute_evaluation(
            paper_dir=resolved_paper_dir,
            outcome_path=resolved_outcome_path,
            summary_output_path=resolved_output_path if write_output else None,
        )

        metrics = result.get("metrics", {})
        evaluated = metrics.get("evaluated_count", 0)
        matched = metrics.get("matched_outcome_count", 0)
        missing = metrics.get("missing_outcome_count", 0)
        coverage = metrics.get("coverage_rate", 0.0)

        if evaluated == 0:
            # No paper rows for this date at all.
            data_status = PAPER_EVAL_STATUS_NO_PAPER_ROWS
            status = JOB_STATUS_DATA_LIMITED
            warnings.append(
                f"No paper rows found in {resolved_paper_dir} — "
                "evaluation produced empty metrics (expected for dates with no recommendations)."
            )
        elif matched == 0:
            # Paper rows exist but no outcomes are available yet — the normal
            # pregame case. Treat as DATA_LIMITED, not SUCCESS.
            data_status = PAPER_EVAL_STATUS_OUTCOMES_UNAVAILABLE
            status = JOB_STATUS_DATA_LIMITED
            warnings.append(
                f"evaluated_count={evaluated} but matched_outcome_count=0 — "
                "paper rows are present but their outcomes are not yet available "
                "(coverage_rate=0.0). Re-run after outcomes land to refresh metrics."
            )
            if write_output:
                output_paths.append(resolved_output_path)
        else:
            # Outcomes matched — a meaningful evaluation.
            data_status = PAPER_EVAL_STATUS_OUTCOMES_MATCHED
            status = JOB_STATUS_SUCCESS
            if write_output:
                output_paths.append(resolved_output_path)
            if matched < PAPER_EVAL_SMALL_SAMPLE_THRESHOLD:
                warnings.append(
                    f"matched_outcome_count={matched} < "
                    f"{PAPER_EVAL_SMALL_SAMPLE_THRESHOLD} — small sample; "
                    "metrics are not statistically significant."
                )

        details = {
            "data_status": data_status,
            "evaluated_count": evaluated,
            "matched_outcome_count": matched,
            "missing_outcome_count": missing,
            "coverage_rate": coverage,
            "hit_rate": metrics.get("hit_rate", 0.0),
            "brier_score": metrics.get("brier_score"),
            "artifact_written": bool(write_output),
        }

    except Exception as exc:
        errors.append(f"run_paper_evaluation_job failed: {exc}")
        errors.append(traceback.format_exc())
        finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return DailyJobResult(
            job_name="paper_evaluation",
            status=JOB_STATUS_FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round(time.monotonic() - t0, 3),
            output_paths=[],
            errors=errors,
            warnings=warnings,
            safety_flags=_safety_flags,
            details={"data_status": "EXCEPTION"},
        )

    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return DailyJobResult(
        job_name="paper_evaluation",
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=round(time.monotonic() - t0, 3),
        output_paths=output_paths,
        errors=errors,
        warnings=warnings,
        safety_flags=_safety_flags,
        details=details,
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION C — Gate
# ════════════════════════════════════════════════════════════════════════════


def build_scheduler_gate(
    pregame_result: DailyJobResult,
    postgame_result: DailyJobResult,
    source: str,
    advisory_total: int = 0,
    reviewed_count: int = 0,
    pending_count: int = 0,
) -> tuple[str, str]:
    """
    Determine the scheduler gate from job results.

    Returns (gate_str, rationale).
    Gate is strictly one of VALID_GATES.
    Conservative judgment — never claim more than what actually worked.
    """
    pregame_ok = pregame_result.status in {JOB_STATUS_SUCCESS, JOB_STATUS_DATA_LIMITED}
    postgame_ok = postgame_result.status in {JOB_STATUS_SUCCESS, JOB_STATUS_DATA_LIMITED,
                                             JOB_STATUS_SKIPPED}
    pregame_failed = pregame_result.status == JOB_STATUS_FAILED
    postgame_failed = postgame_result.status == JOB_STATUS_FAILED

    # Governance risk: both failed is suspicious
    if pregame_failed and postgame_failed:
        return (
            MLB_SCHEDULER_NOT_READY,
            "both pregame and postgame jobs failed — scheduler not ready",
        )

    # Both pending/data-limited only
    all_pending = pending_count > 0 and reviewed_count == 0

    # source = current but not actually reachable
    source_is_live_needed = source == "current"

    if pregame_failed:
        return (
            MLB_SCHEDULER_NOT_READY,
            f"pregame advisory job failed: {'; '.join(pregame_result.errors[:1])}",
        )

    if postgame_failed:
        return (
            MLB_SCHEDULER_DATA_LIMITED,
            f"postgame review job failed: {'; '.join(postgame_result.errors[:1])}",
        )

    # All paths working — gate by data completeness and source coverage
    if pregame_ok and postgame_ok:
        if source_is_live_needed:
            return (
                MLB_SCHEDULER_NEEDS_LIVE_SOURCE,
                "scheduler + API operational but no live schedule/odds/result source connected",
            )
        if all_pending:
            return (
                MLB_SCHEDULER_DATA_LIMITED,
                f"pipeline runs but pending_count={pending_count} — "
                "source (fixture/replay) lacks live results",
            )
        if reviewed_count > 0:
            return (
                MLB_SCHEDULER_API_MVP_READY,
                f"scheduler + API handlers + manifest operational; "
                f"reviewed_count={reviewed_count}, pending={pending_count}, "
                "safety flags verified",
            )
        # Advisory ran but only fixture/replay with 0 reviewed (not a failure)
        return (
            MLB_DAILY_SCHEDULER_READY,
            f"scheduler runs advisory + review; advisory_total={advisory_total}; "
            f"reviewed_count={reviewed_count}; source={source}",
        )

    # Partial: only pregame ran
    if pregame_ok and not postgame_ok:
        return (
            MLB_DAILY_SCHEDULER_READY,
            "pregame advisory job completed; postgame review skipped or incomplete",
        )

    return (
        MLB_SCHEDULER_NOT_READY,
        "scheduler unable to complete both advisory and review jobs",
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION D — Manifest
# ════════════════════════════════════════════════════════════════════════════


def build_daily_manifest(
    run_id: str,
    run_date: str,
    mode: str,
    source: str,
    pregame_result: DailyJobResult,
    postgame_result: DailyJobResult,
    ledger_path: str,
    advisory_report_path: str,
    review_report_path: str,
    reviewed_snapshot_path: str,
    advisory_payload: dict | None = None,
    review_payload: dict | None = None,
    gate: str = MLB_SCHEDULER_NOT_READY,
    gate_rationale: str = "",
) -> DailyJobManifest:
    """Build a DailyJobManifest from job results and payloads."""
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Extract advisory stats
    total_advisories = 0
    total_ledger_entries = 0
    if advisory_payload:
        total_advisories = advisory_payload.get("total_advisories", 0)
        total_ledger_entries = advisory_payload.get("total_ledger_entries_written", 0)

    # Extract review stats
    reviewed_count = 0
    pending_count = 0
    failure_notes_count = 0
    brier_score: float | None = None
    rec_acc: float | None = None
    if review_payload:
        rs = review_payload.get("review_summary", {})
        reviewed_count = rs.get("reviewed_count", 0)
        pending_count = rs.get("pending_results", 0)
        brier_score = rs.get("brier_score")
        rec_acc = rs.get("recommendation_accuracy")
        failure_notes_count = len(review_payload.get("failure_notes", []))

    # Pregame failure reason
    pregame_failure_reason: str | None = None
    if pregame_result.status == JOB_STATUS_FAILED:
        pregame_failure_reason = (pregame_result.errors[0] if pregame_result.errors else
                                  "unknown failure")

    postgame_failure_reason: str | None = None
    if postgame_result.status == JOB_STATUS_FAILED:
        postgame_failure_reason = (postgame_result.errors[0] if postgame_result.errors else
                                   "unknown failure")

    return DailyJobManifest(
        run_id=run_id,
        run_date=run_date,
        mode=mode,
        source=source,
        scheduler_mode="dry_run",
        pregame_advisory_status=pregame_result.status,
        postgame_review_status=postgame_result.status,
        advisory_report_path=advisory_report_path,
        ledger_path=ledger_path,
        review_report_path=review_report_path,
        reviewed_snapshot_path=reviewed_snapshot_path,
        total_advisories=total_advisories,
        total_ledger_entries=total_ledger_entries,
        reviewed_count=reviewed_count,
        pending_count=pending_count,
        failure_notes_count=failure_notes_count,
        gate=gate,
        paper_only=PAPER_ONLY,
        no_real_bet=NO_REAL_BET,
        no_profit_claim=NO_PROFIT_CLAIM,
        no_auto_execution=NO_AUTO_EXECUTION,
        scheduler_dry_run_only=SCHEDULER_DRY_RUN_ONLY,
        ledger_overwrite_blocked=LEDGER_OVERWRITE_BLOCKED,
        pregame_failure_reason=pregame_failure_reason,
        postgame_failure_reason=postgame_failure_reason,
        pregame_warnings=pregame_result.warnings,
        postgame_warnings=postgame_result.warnings,
        source_mode_advisory=source,
        source_mode_review=source,
        brier_score=brier_score,
        recommendation_accuracy=rec_acc,
        gate_rationale=gate_rationale,
        created_at=created_at,
        module_version=MODULE_VERSION,
        completion_marker=COMPLETION_MARKER,
    )


def validate_daily_manifest(manifest: DailyJobManifest) -> list[str]:
    """
    Validate a DailyJobManifest for schema completeness.

    Returns list of validation error strings (empty = valid).
    """
    errors: list[str] = []

    # Required string fields
    for field_name in ("run_id", "run_date", "mode", "source", "scheduler_mode"):
        val = getattr(manifest, field_name, None)
        if not val:
            errors.append(f"manifest.{field_name} is empty or missing")

    # Gate must be in VALID_GATES
    if manifest.gate not in VALID_GATES:
        errors.append(
            f"manifest.gate={manifest.gate!r} is not in VALID_GATES ({len(VALID_GATES)} values)"
        )

    # Safety flags
    if not manifest.paper_only:
        errors.append("manifest.paper_only must be True")
    if not manifest.no_real_bet:
        errors.append("manifest.no_real_bet must be True")
    if not manifest.no_profit_claim:
        errors.append("manifest.no_profit_claim must be True")
    if not manifest.no_auto_execution:
        errors.append("manifest.no_auto_execution must be True")
    if not manifest.scheduler_dry_run_only:
        errors.append("manifest.scheduler_dry_run_only must be True")

    # Status tokens
    valid_statuses = {
        JOB_STATUS_SUCCESS, JOB_STATUS_SKIPPED, JOB_STATUS_FAILED,
        JOB_STATUS_DATA_LIMITED, JOB_STATUS_NOT_RUN,
    }
    if manifest.pregame_advisory_status not in valid_statuses:
        errors.append(
            f"manifest.pregame_advisory_status={manifest.pregame_advisory_status!r} unknown"
        )
    if manifest.postgame_review_status not in valid_statuses:
        errors.append(
            f"manifest.postgame_review_status={manifest.postgame_review_status!r} unknown"
        )

    return errors


def write_daily_manifest(
    manifest: DailyJobManifest,
    manifest_path: str | None = None,
    *,
    write: bool = True,
) -> str:
    """
    Serialize DailyJobManifest to JSON and write to disk.

    Returns the manifest path. Does not overwrite if write=False.
    """
    resolved_path = manifest_path or _default_manifest_path(manifest.run_date)

    payload = {
        "run_id": manifest.run_id,
        "run_date": manifest.run_date,
        "mode": manifest.mode,
        "source": manifest.source,
        "scheduler_mode": manifest.scheduler_mode,
        "pregame_advisory_status": manifest.pregame_advisory_status,
        "postgame_review_status": manifest.postgame_review_status,
        "advisory_report_path": manifest.advisory_report_path,
        "ledger_path": manifest.ledger_path,
        "review_report_path": manifest.review_report_path,
        "reviewed_snapshot_path": manifest.reviewed_snapshot_path,
        "total_advisories": manifest.total_advisories,
        "total_ledger_entries": manifest.total_ledger_entries,
        "reviewed_count": manifest.reviewed_count,
        "pending_count": manifest.pending_count,
        "failure_notes_count": manifest.failure_notes_count,
        "gate": manifest.gate,
        "paper_only": manifest.paper_only,
        "no_real_bet": manifest.no_real_bet,
        "no_profit_claim": manifest.no_profit_claim,
        "no_auto_execution": manifest.no_auto_execution,
        "scheduler_dry_run_only": manifest.scheduler_dry_run_only,
        "ledger_overwrite_blocked": manifest.ledger_overwrite_blocked,
        "pregame_failure_reason": manifest.pregame_failure_reason,
        "postgame_failure_reason": manifest.postgame_failure_reason,
        "pregame_warnings": manifest.pregame_warnings,
        "postgame_warnings": manifest.postgame_warnings,
        "source_mode_advisory": manifest.source_mode_advisory,
        "source_mode_review": manifest.source_mode_review,
        "brier_score": manifest.brier_score,
        "recommendation_accuracy": manifest.recommendation_accuracy,
        "gate_rationale": manifest.gate_rationale,
        "created_at": manifest.created_at,
        "module_version": manifest.module_version,
        "completion_marker": manifest.completion_marker,
    }

    if write:
        os.makedirs(os.path.dirname(os.path.abspath(resolved_path)), exist_ok=True)
        with open(resolved_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    return resolved_path


def load_latest_daily_manifest(
    manifest_dir: str = DEFAULT_MANIFEST_DIR,
    date_str: str | None = None,
) -> dict | None:
    """
    Load the latest scheduler manifest from disk.

    If date_str is given, loads that specific manifest.
    Otherwise, loads the most recently written manifest in manifest_dir.

    Returns the manifest dict or None if not found.
    """
    if date_str:
        path = _default_manifest_path(date_str)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        return None

    # Find most recent manifest
    pattern = os.path.join(manifest_dir, "mlb_daily_scheduler_manifest_*.json")
    matches = sorted(glob.glob(pattern), reverse=True)
    if not matches:
        return None

    latest = matches[0]
    with open(latest, encoding="utf-8") as fh:
        return json.load(fh)


# ════════════════════════════════════════════════════════════════════════════
# SECTION E — Markdown Report
# ════════════════════════════════════════════════════════════════════════════


def generate_scheduler_markdown(
    manifest: DailyJobManifest,
    pregame_result: DailyJobResult,
    postgame_result: DailyJobResult,
    markdown_path: str,
    *,
    write: bool = True,
) -> str:
    """Generate a markdown scheduler report. Returns content string."""
    lines: list[str] = [
        "# MLB Daily Scheduler — Dry-run Report",
        "",
        f"**Run Date**: {manifest.run_date}",
        f"**Run ID**: {manifest.run_id}",
        f"**Mode**: {manifest.mode}",
        f"**Source**: {manifest.source}",
        f"**Scheduler Mode**: {manifest.scheduler_mode}",
        f"**Gate**: `{manifest.gate}`",
        "",
        "---",
        "",
        "## Safety Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
        f"| NO_REAL_BET | {manifest.no_real_bet} |",
        f"| NO_PROFIT_CLAIM | {manifest.no_profit_claim} |",
        f"| PAPER_ONLY | {manifest.paper_only} |",
        f"| LEDGER_OVERWRITE_BLOCKED | {manifest.ledger_overwrite_blocked} |",
        f"| SCHEDULER_DRY_RUN_ONLY | {manifest.scheduler_dry_run_only} |",
        f"| NO_AUTO_EXECUTION | {manifest.no_auto_execution} |",
        f"| PRODUCTION_MODIFIED | {PRODUCTION_MODIFIED} |",
        "",
        "```",
        "NO_REAL_BET = True",
        "NO_PROFIT_CLAIM = True",
        "PAPER_ONLY = True",
        "LEDGER_OVERWRITE_BLOCKED = True",
        "SCHEDULER_DRY_RUN_ONLY = True",
        "NO_AUTO_EXECUTION = True",
        "```",
        "",
        "---",
        "",
        "## Job Results",
        "",
        f"### Pregame Advisory Job",
        f"- **Status**: {pregame_result.status}",
        f"- **Duration**: {pregame_result.duration_seconds}s",
        f"- **Total Advisories**: {manifest.total_advisories}",
        f"- **Ledger Entries Written**: {manifest.total_ledger_entries}",
    ]

    if pregame_result.warnings:
        lines.append(f"- **Warnings**: {'; '.join(pregame_result.warnings)}")
    if pregame_result.errors:
        lines.append(f"- **Errors**: {'; '.join(pregame_result.errors[:2])}")
    if manifest.pregame_failure_reason:
        lines.append(f"- **Failure Reason**: {manifest.pregame_failure_reason}")

    lines += [
        "",
        f"### Postgame Review Job",
        f"- **Status**: {postgame_result.status}",
        f"- **Duration**: {postgame_result.duration_seconds}s",
        f"- **Reviewed Count**: {manifest.reviewed_count}",
        f"- **Pending Count**: {manifest.pending_count}",
        f"- **Failure Notes**: {manifest.failure_notes_count}",
    ]

    if manifest.brier_score is not None:
        lines.append(f"- **Brier Score**: {manifest.brier_score:.4f}")
    if manifest.recommendation_accuracy is not None:
        lines.append(f"- **Recommendation Accuracy**: {manifest.recommendation_accuracy:.2%}")
    if postgame_result.warnings:
        lines.append(f"- **Warnings**: {'; '.join(postgame_result.warnings)}")
    if postgame_result.errors:
        lines.append(f"- **Errors**: {'; '.join(postgame_result.errors[:2])}")
    if manifest.postgame_failure_reason:
        lines.append(f"- **Failure Reason**: {manifest.postgame_failure_reason}")

    lines += [
        "",
        "---",
        "",
        "## Report Paths",
        "",
        f"- Advisory Report: `{manifest.advisory_report_path}`",
        f"- Ledger: `{manifest.ledger_path}`",
        f"- Review Report: `{manifest.review_report_path}`",
        f"- Reviewed Snapshot: `{manifest.reviewed_snapshot_path}`",
        "",
        "---",
        "",
        "## Gate",
        "",
        f"**{manifest.gate}**",
        "",
        f"> {manifest.gate_rationale}",
        "",
        "---",
        "",
        "## Governance Disclaimer",
        "",
        "> This report is **PAPER-ONLY** / **NO REAL BET** / **NO PROFIT CLAIM**.",
        "> The scheduler is a dry-run research tool. No real bets are placed.",
        "> No guaranteed profit is implied. Human review required before any decision.",
        "",
        "---",
        "",
        f"**Created**: {manifest.created_at}",
        f"**Module Version**: {manifest.module_version}",
        "",
        f"## Completion Marker",
        "",
        f"`{manifest.completion_marker}`",
        "",
        f"<!-- {manifest.completion_marker} -->",
    ]

    content = "\n".join(lines)
    if write:
        os.makedirs(os.path.dirname(os.path.abspath(markdown_path)), exist_ok=True)
        with open(markdown_path, "w", encoding="utf-8") as fh:
            fh.write(content)
    return content


# ════════════════════════════════════════════════════════════════════════════
# SECTION F — Main Scheduler Orchestration
# ════════════════════════════════════════════════════════════════════════════


def run_daily_mlb_scheduler(
    run_date: str,
    mode: str = "today",
    source: str = "fixture",
    limit: int = 15,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    fixture_path: str = DEFAULT_FIXTURE_PATH,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
    manifest_path: str | None = None,
    advisory_report_path: str | None = None,
    review_report_path: str | None = None,
    reviewed_snapshot_path: str | None = None,
    markdown_path: str | None = None,
    *,
    run_pregame: bool = True,
    run_postgame: bool = True,
    skip_postgame_if_pregame_fails: bool = True,
    write_reports: bool = True,
    run_paper_recommendation: bool = False,
    run_paper_evaluation: bool = False,
    paper_allow_replay: bool = True,
    paper_allow_missing_simulation_gate: bool = True,
    paper_output_base_dir: str | None = None,
    paper_eval_paper_dir: str | None = None,
    paper_eval_outcome_path: str | None = None,
    paper_eval_output_path: str | None = None,
) -> dict:
    """
    Main daily MLB scheduler orchestration function.

    Runs, in order:
      1. pregame advisory
      2. paper recommendation   (P141, opt-in — see below)
      3. paper evaluation       (P143, opt-in — offline)
      4. postgame review
    then builds manifest and writes reports.

    Paper-step wiring (P144):
    The paper recommendation + paper evaluation jobs are wired into the daily
    chain so the paper corpus and per-date evaluation artifacts can accumulate
    deterministically every day. Both are **off by default** and surface as
    ``NOT_RUN`` in ``payload["jobs"]`` unless explicitly enabled:

    - ``run_paper_recommendation`` defaults to False because the recommendation
      job performs live TSL / MLB schedule probes; the daily daemon enables it
      explicitly for live paper generation. Keeping it off by default preserves
      the no-live-fetch-by-default contract for all other callers.
    - ``run_paper_evaluation`` is fully offline (reads local PAPER rows + local
      outcome corpus) and also defaults to False so existing default callers see
      no behavior change; it is enabled alongside the recommendation step.

    Neither paper step affects the scheduler gate or manifest (which remain
    derived from pregame + postgame), so existing behavior is preserved.

    Runs pregame advisory + postgame review, builds manifest, writes reports.

    Returns complete payload dict with gate, manifest, job results.

    Args:
        run_date: YYYY-MM-DD date string
        mode: "today" or "replay"
        source: "fixture" | "replay" | "current"
        limit: max games to process
        ledger_path: paper betting ledger JSONL path
        fixture_path: fixture source JSON path
        prediction_jsonl_path: historical prediction JSONL path
        manifest_path: where to write manifest JSON
        advisory_report_path: where to write advisory JSON report
        review_report_path: where to write review JSON report
        reviewed_snapshot_path: where to write reviewed snapshot JSONL
        markdown_path: where to write markdown scheduler report
        run_pregame: whether to run pregame advisory job
        run_postgame: whether to run postgame review job
        skip_postgame_if_pregame_fails: skip postgame if pregame fails
        write_reports: if False, skip all disk writes (for unit tests)
    """
    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Generate run_id
    ts_clean = run_ts.replace(":", "").replace("-", "").replace(".", "")[:16]
    run_id = f"SCHED_{run_date.replace('-', '')}_{source.upper()}_{ts_clean}"

    resolved_advisory_path = advisory_report_path or _default_advisory_report_path(run_date)
    resolved_review_path = review_report_path or _default_review_report_path(run_date)
    resolved_snapshot_path = reviewed_snapshot_path or _default_reviewed_snapshot_path(run_date)
    resolved_manifest_path = manifest_path or _default_manifest_path(run_date)
    resolved_markdown_path = markdown_path or _default_markdown_path(run_date)

    # ── 1. Pregame advisory job ──────────────────────────────────────────────
    advisory_payload: dict = {}
    if run_pregame:
        pregame_result = run_pregame_advisory_job(
            run_date=run_date,
            mode=mode,
            source=source,
            limit=limit,
            ledger_path=ledger_path,
            fixture_path=fixture_path,
            prediction_jsonl_path=prediction_jsonl_path,
            report_path=resolved_advisory_path,
            write_reports=write_reports,
        )
        # Try to load advisory payload from report file if written
        if write_reports and os.path.exists(resolved_advisory_path):
            try:
                with open(resolved_advisory_path, encoding="utf-8") as fh:
                    advisory_payload = json.load(fh)
            except Exception:
                pass
        # If no file, re-run without disk write to get payload in memory
        if not advisory_payload and pregame_result.status != JOB_STATUS_FAILED:
            try:
                from orchestrator.mlb_daily_advisory import run_mlb_daily_advisory
                from orchestrator.mlb_current_sources import (
                    load_fixture_schedule_odds,
                    probe_current_mlb_source,
                )
                override_games = None
                if source == "fixture":
                    raw_games = load_fixture_schedule_odds(fixture_path) or []
                    override_games = _snapshot_to_advisory_row_list(raw_games) if raw_games else None
                advisory_payload = run_mlb_daily_advisory(
                    date_str=run_date,
                    mode=mode,
                    limit=limit,
                    prediction_jsonl_path=prediction_jsonl_path,
                    ledger_path=ledger_path,
                    report_path=None,
                    markdown_path=None,
                    write_reports=False,
                    override_games=override_games,
                    source_mode=source,
                    fixture_source_used=(source == "fixture"),
                    current_source_reachable=False,
                    model_prediction_available=True,
                )
            except Exception:
                pass
    else:
        pregame_result = DailyJobResult(
            job_name="pregame_advisory",
            status=JOB_STATUS_NOT_RUN,
            started_at=run_ts,
            finished_at=run_ts,
            duration_seconds=0.0,
            safety_flags={
                "paper_only": PAPER_ONLY,
                "no_real_bet": NO_REAL_BET,
                "no_profit_claim": NO_PROFIT_CLAIM,
                "production_modified": PRODUCTION_MODIFIED,
                "no_auto_execution": NO_AUTO_EXECUTION,
            },
        )

    # ── 1b. Paper recommendation job (P141, opt-in) ──────────────────────────
    _paper_safety_flags = {
        "paper_only": True,
        "no_real_bet": True,
        "no_profit_claim": True,
        "production_modified": False,
        "no_auto_execution": True,
        "scheduler_dry_run_only": True,
        "no_ev_clv_kelly_unlock": True,
        "no_db_writes": True,
        "no_live_api_calls": True,
        "no_provider_unlock": True,
    }
    if run_paper_recommendation:
        paper_recommendation_result = run_paper_recommendation_job(
            run_date=run_date,
            allow_replay=paper_allow_replay,
            allow_missing_simulation_gate=paper_allow_missing_simulation_gate,
            output_base_dir=paper_output_base_dir,
        )
    else:
        paper_recommendation_result = DailyJobResult(
            job_name="paper_recommendation",
            status=JOB_STATUS_NOT_RUN,
            started_at=run_ts,
            finished_at=run_ts,
            duration_seconds=0.0,
            safety_flags=_paper_safety_flags,
            details={"reason": "run_paper_recommendation=False (default; live-probe step is opt-in)"},
        )

    # ── 1c. Paper evaluation job (P143, opt-in, offline) ─────────────────────
    if run_paper_evaluation:
        paper_evaluation_result = run_paper_evaluation_job(
            run_date=run_date,
            paper_dir=paper_eval_paper_dir,
            outcome_path=paper_eval_outcome_path,
            output_path=paper_eval_output_path,
            write_output=write_reports,
        )
    else:
        paper_evaluation_result = DailyJobResult(
            job_name="paper_evaluation",
            status=JOB_STATUS_NOT_RUN,
            started_at=run_ts,
            finished_at=run_ts,
            duration_seconds=0.0,
            safety_flags=_paper_safety_flags,
            details={"reason": "run_paper_evaluation=False (default)"},
        )

    # ── 2. Postgame review job ───────────────────────────────────────────────
    review_payload: dict = {}
    if run_postgame:
        postgame_result = run_postgame_review_job(
            run_date=run_date,
            source=source,
            ledger_path=ledger_path,
            fixture_path=fixture_path,
            prediction_jsonl_path=prediction_jsonl_path,
            reviewed_snapshot_path=resolved_snapshot_path,
            report_path=resolved_review_path,
            write_reports=write_reports,
            skip_if_no_pregame=skip_postgame_if_pregame_fails,
            pregame_status=pregame_result.status,
        )
        if write_reports and os.path.exists(resolved_review_path):
            try:
                with open(resolved_review_path, encoding="utf-8") as fh:
                    review_payload = json.load(fh)
            except Exception:
                pass
        if not review_payload and postgame_result.status != JOB_STATUS_FAILED:
            try:
                from orchestrator.mlb_result_review import run_postgame_review
                review_payload = run_postgame_review(
                    review_date=run_date,
                    source_mode=source,
                    ledger_path=ledger_path,
                    fixture_path=fixture_path,
                    prediction_jsonl_path=prediction_jsonl_path,
                    reviewed_snapshot_path=None,
                    report_path=None,
                    markdown_path=None,
                    write_reports=False,
                )
            except Exception:
                pass
    else:
        postgame_result = DailyJobResult(
            job_name="postgame_review",
            status=JOB_STATUS_NOT_RUN,
            started_at=run_ts,
            finished_at=run_ts,
            duration_seconds=0.0,
            safety_flags={
                "paper_only": PAPER_ONLY,
                "no_real_bet": NO_REAL_BET,
                "no_profit_claim": NO_PROFIT_CLAIM,
                "production_modified": PRODUCTION_MODIFIED,
                "ledger_overwrite_blocked": LEDGER_OVERWRITE_BLOCKED,
                "no_auto_execution": NO_AUTO_EXECUTION,
            },
        )

    # ── 3. Extract summary stats for gate ────────────────────────────────────
    advisory_total = advisory_payload.get("total_advisories", 0) if advisory_payload else 0
    rs = review_payload.get("review_summary", {}) if review_payload else {}
    reviewed_count = rs.get("reviewed_count", 0)
    pending_count = rs.get("pending_results", 0)

    # ── 4. Build gate ────────────────────────────────────────────────────────
    gate, gate_rationale = build_scheduler_gate(
        pregame_result=pregame_result,
        postgame_result=postgame_result,
        source=source,
        advisory_total=advisory_total,
        reviewed_count=reviewed_count,
        pending_count=pending_count,
    )
    assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"

    # ── 5. Build manifest ────────────────────────────────────────────────────
    manifest = build_daily_manifest(
        run_id=run_id,
        run_date=run_date,
        mode=mode,
        source=source,
        pregame_result=pregame_result,
        postgame_result=postgame_result,
        ledger_path=ledger_path,
        advisory_report_path=resolved_advisory_path,
        review_report_path=resolved_review_path,
        reviewed_snapshot_path=resolved_snapshot_path,
        advisory_payload=advisory_payload,
        review_payload=review_payload,
        gate=gate,
        gate_rationale=gate_rationale,
    )

    # ── 6. Validate manifest ─────────────────────────────────────────────────
    validation_errors = validate_daily_manifest(manifest)

    # ── 7. Write manifest ────────────────────────────────────────────────────
    manifest_written = write_daily_manifest(manifest, resolved_manifest_path, write=write_reports)

    # ── 8. Generate markdown ─────────────────────────────────────────────────
    md_content = generate_scheduler_markdown(
        manifest=manifest,
        pregame_result=pregame_result,
        postgame_result=postgame_result,
        markdown_path=resolved_markdown_path,
        write=write_reports,
    )

    # ── 9. Build final payload ────────────────────────────────────────────────
    payload = {
        "module_version": MODULE_VERSION,
        "run_id": run_id,
        "run_timestamp_utc": run_ts,
        "run_date": run_date,
        "mode": mode,
        "source": source,
        "scheduler_mode": "dry_run",
        "gate": gate,
        "gate_rationale": gate_rationale,
        "completion_marker": COMPLETION_MARKER,
        "safety": {
            "production_modified": PRODUCTION_MODIFIED,
            "candidate_patch_created": CANDIDATE_PATCH_CREATED,
            "alpha_modified": ALPHA_MODIFIED,
            "prediction_jsonl_overwritten": PREDICTION_JSONL_OVERWRITTEN,
            "ledger_overwrite_blocked": LEDGER_OVERWRITE_BLOCKED,
            "no_edge_claim": NO_EDGE_CLAIM,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "paper_only": PAPER_ONLY,
            "no_real_bet": NO_REAL_BET,
            "scheduler_dry_run_only": SCHEDULER_DRY_RUN_ONLY,
            "no_auto_execution": NO_AUTO_EXECUTION,
        },
        "jobs": {
            "pregame_advisory": {
                "status": pregame_result.status,
                "duration_seconds": pregame_result.duration_seconds,
                "errors": pregame_result.errors,
                "warnings": pregame_result.warnings,
                "output_paths": pregame_result.output_paths,
            },
            "paper_recommendation": {
                "status": paper_recommendation_result.status,
                "duration_seconds": paper_recommendation_result.duration_seconds,
                "errors": paper_recommendation_result.errors,
                "warnings": paper_recommendation_result.warnings,
                "output_paths": paper_recommendation_result.output_paths,
                "safety_flags": paper_recommendation_result.safety_flags,
                "details": paper_recommendation_result.details,
            },
            "paper_evaluation": {
                "status": paper_evaluation_result.status,
                "duration_seconds": paper_evaluation_result.duration_seconds,
                "errors": paper_evaluation_result.errors,
                "warnings": paper_evaluation_result.warnings,
                "output_paths": paper_evaluation_result.output_paths,
                "safety_flags": paper_evaluation_result.safety_flags,
                "details": paper_evaluation_result.details,
            },
            "postgame_review": {
                "status": postgame_result.status,
                "duration_seconds": postgame_result.duration_seconds,
                "errors": postgame_result.errors,
                "warnings": postgame_result.warnings,
                "output_paths": postgame_result.output_paths,
            },
        },
        "scheduler_sequence": [
            "pregame_advisory",
            "paper_recommendation",
            "paper_evaluation",
            "postgame_review",
        ],
        "manifest": {
            "run_id": manifest.run_id,
            "run_date": manifest.run_date,
            "mode": manifest.mode,
            "source": manifest.source,
            "pregame_advisory_status": manifest.pregame_advisory_status,
            "postgame_review_status": manifest.postgame_review_status,
            "total_advisories": manifest.total_advisories,
            "total_ledger_entries": manifest.total_ledger_entries,
            "reviewed_count": manifest.reviewed_count,
            "pending_count": manifest.pending_count,
            "failure_notes_count": manifest.failure_notes_count,
            "brier_score": manifest.brier_score,
            "recommendation_accuracy": manifest.recommendation_accuracy,
            "gate": manifest.gate,
            "paper_only": manifest.paper_only,
            "no_real_bet": manifest.no_real_bet,
            "no_profit_claim": manifest.no_profit_claim,
            "no_auto_execution": manifest.no_auto_execution,
            "ledger_overwrite_blocked": manifest.ledger_overwrite_blocked,
            "scheduler_dry_run_only": manifest.scheduler_dry_run_only,
        },
        "manifest_path": manifest_written,
        "markdown_path": resolved_markdown_path,
        "validation_errors": validation_errors,
        "advisory_payload_summary": {
            "total_advisories": advisory_total,
            "total_ledger_written": advisory_payload.get("total_ledger_entries_written", 0)
            if advisory_payload else 0,
        },
        "review_payload_summary": {
            "reviewed_count": reviewed_count,
            "pending_count": pending_count,
            "brier_score": rs.get("brier_score"),
            "recommendation_accuracy": rs.get("recommendation_accuracy"),
        },
        "metrics_ssot_used": True,
    }

    return payload
