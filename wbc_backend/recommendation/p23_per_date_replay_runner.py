"""
wbc_backend/recommendation/p23_per_date_replay_runner.py

P23 Per-Date Replay Runner — materializes P15 inputs for a single date
and runs the P16.6 → P19 → P17-replay → P20 pipeline via subprocess.

For 2026-05-12 (or any date with an existing P20_DAILY_PAPER_ORCHESTRATOR_READY
result), the existing artifacts are reused without overwriting.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_DATE_ALREADY_READY,
    P23_DATE_BLOCKED_P15_BUILD_FAILED,
    P23_DATE_BLOCKED_P16_6_FAILED,
    P23_DATE_BLOCKED_P17_REPLAY_FAILED,
    P23_DATE_BLOCKED_P19_FAILED,
    P23_DATE_BLOCKED_P20_FAILED,
    P23_DATE_BLOCKED_SOURCE_NOT_READY,
    P23_DATE_REPLAY_READY,
    P23ReplayDateResult,
    P23ReplayDateTask,
)
from wbc_backend.recommendation.p23_p15_source_materializer import (
    materialize_p15_inputs_for_date,
)

# P20 output directory name matches the existing pipeline convention
_P20_GATE_FILE = "p20_gate_result.json"
_P20_GATE_READY = "P20_DAILY_PAPER_ORCHESTRATOR_READY"

# P18 policy: the static policy used for all historical replay dates
_P18_POLICY_SOURCE_DATE = "2026-05-12"
_P18_POLICY_FILENAME = "selected_strategy_policy.json"

# Python executable — resolved relative to the repo root at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYTHON = str(_REPO_ROOT / ".venv" / "bin" / "python")

# Sub-process environment
import os as _os
_BASE_ENV = {
    "PYTHONPATH": str(_REPO_ROOT),
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _run_script(args: list[str]) -> tuple[int, str]:
    """Run a script via subprocess. Returns (returncode, combined_output)."""
    env = {**_BASE_ENV}
    result = subprocess.run(
        [_PYTHON] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )
    combined = (result.stdout or "") + (result.stderr or "")
    return result.returncode, combined


def _load_json_safe(path: Path) -> Optional[dict]:
    """Load JSON from a path; return None if file does not exist."""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_date_result_from_existing_p20(
    run_date: str,
    paper_base_dir: Path,
) -> P23ReplayDateResult:
    """Build a P23ReplayDateResult from an existing P20 gate result.

    Used for 2026-05-12 and any other date that already has a valid P20 output.
    """
    p20_dir = paper_base_dir / run_date / "p20_daily_paper_orchestrator"
    p20_data = _load_json_safe(p20_dir / _P20_GATE_FILE) or {}

    # Pull P17 summary for stake/pnl totals if available
    p17_dir = paper_base_dir / run_date / "p17_replay_with_p19_identity"
    p17_summary = _load_json_safe(p17_dir / "paper_recommendation_ledger_summary.json") or {}

    total_stake = float(p17_summary.get("total_stake_units", 0.0))
    total_pnl = float(p17_summary.get("total_pnl_units", 0.0))

    n_active = int(p20_data.get("n_active_paper_entries", 0))
    n_win = int(p20_data.get("n_settled_win", 0))
    n_loss = int(p20_data.get("n_settled_loss", 0))
    n_unsettled = int(p20_data.get("n_unsettled", 0))
    roi_units = float(p20_data.get("roi_units", 0.0))
    hit_rate = float(p20_data.get("hit_rate", 0.0))
    game_id_coverage = float(p20_data.get("game_id_coverage", 0.0))
    settlement_join_method = p20_data.get("settlement_join_method", "JOIN_BY_GAME_ID")

    # Determine upstream gate strings from actual P20 data
    p16_6_dir = paper_base_dir / run_date / "p16_6_recommendation_gate_p18_policy"
    p16_6_summary = _load_json_safe(p16_6_dir / "recommendation_summary.json") or {}
    p16_6_gate = p16_6_summary.get("p16_6_gate", "P16_6_PAPER_RECOMMENDATION_GATE_READY")

    p19_dir = paper_base_dir / run_date / "p19_odds_identity_join_repair"
    p19_data = _load_json_safe(p19_dir / "p19_gate_result.json") or {}
    p19_gate = p19_data.get("gate_decision", "P19_ODDS_IDENTITY_JOIN_REPAIRED")

    p17_gate = p17_summary.get("p17_gate", "P17_PAPER_LEDGER_READY")

    return P23ReplayDateResult(
        run_date=run_date,
        source_ready=True,
        p15_preview_ready=True,
        p16_6_gate=p16_6_gate,
        p19_gate=p19_gate,
        p17_replay_gate=p17_gate,
        p20_gate=_P20_GATE_READY,
        date_gate=P23_DATE_ALREADY_READY,
        n_recommended_rows=int(p20_data.get("n_recommended_rows", n_active)),
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=n_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi_units,
        hit_rate=hit_rate,
        game_id_coverage=game_id_coverage,
        settlement_join_method=settlement_join_method,
        blocker_reason="",
        paper_only=True,
        production_ready=False,
    )


def _find_p18_policy_path(paper_base_dir: Path) -> str:
    """Return the path to the P18 selected policy JSON.

    Uses the 2026-05-12 policy by default (static policy, shared across all replay dates).
    """
    p18_path = (
        paper_base_dir
        / _P18_POLICY_SOURCE_DATE
        / "p18_strategy_policy_risk_repair"
        / _P18_POLICY_FILENAME
    )
    return str(p18_path) if p18_path.exists() else ""


def _run_pipeline_for_date(
    run_date: str,
    mat_result: dict,
    paper_base_dir: Path,
    p23_replay_dir: Path,
) -> P23ReplayDateResult:
    """Run P16.6 → P19 → P17-replay → P20 for a single date.

    All intermediate outputs go to p23_replay_dir/<stage>/.

    Args:
        run_date:        Target date string
        mat_result:      Result dict from materialize_p15_inputs_for_date
        paper_base_dir:  Base PAPER output dir
        p23_replay_dir:  Per-date p23_historical_replay dir

    Returns:
        P23ReplayDateResult
    """
    materialized_joined_oof = mat_result["p15_materialized_path"]
    materialized_sim_ledger = mat_result["sim_ledger_path"]
    p18_policy = _find_p18_policy_path(paper_base_dir)

    if not p18_policy:
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate="",
            p19_gate="",
            p17_replay_gate="",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_P15_BUILD_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason="P18 policy file not found",
            paper_only=True,
            production_ready=False,
        )

    # Stage directories
    p16_6_out = p23_replay_dir / "p16_6"
    p19_out = p23_replay_dir / "p19"
    p17_out = p23_replay_dir / "p17_replay"
    p20_out = p23_replay_dir / "p20"

    for d in [p16_6_out, p19_out, p17_out, p20_out]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Step 1: P16.6 ─────────────────────────────────────────────────────
    p16_6_script = str(_REPO_ROOT / "scripts" / "run_p16_6_recommendation_gate_with_p18_policy.py")
    rc, out = _run_script([
        p16_6_script,
        "--joined-oof", materialized_joined_oof,
        "--p15-ledger", materialized_sim_ledger or materialized_joined_oof,
        "--p18-policy", p18_policy,
        "--output-dir", str(p16_6_out),
        "--paper-only", "true",
    ])
    p16_6_summary = _load_json_safe(p16_6_out / "recommendation_summary.json") or {}
    p16_6_gate = p16_6_summary.get("p16_6_gate", "")

    if rc != 0 or not p16_6_gate.startswith("P16_6_PAPER_RECOMMENDATION_GATE"):
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate=p16_6_gate or "FAILED",
            p19_gate="",
            p17_replay_gate="",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_P16_6_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason=f"P16.6 failed (rc={rc}): {out[:300]}",
            paper_only=True,
            production_ready=False,
        )

    p16_6_recommendation_rows = str(p16_6_out / "recommendation_rows.csv")
    p16_6_recommendation_summary = str(p16_6_out / "recommendation_summary.json")

    # ── Step 2: P19 ─────────────────────────────────────────────────────────
    p19_script = str(_REPO_ROOT / "scripts" / "run_p19_odds_identity_join_repair.py")
    p19_cmd = [
        p19_script,
        "--p15-ledger", materialized_sim_ledger or materialized_joined_oof,
        "--p15-joined", materialized_joined_oof,
        "--p16-6-recommendation-rows", p16_6_recommendation_rows,
        "--output-dir", str(p19_out),
        "--paper-only", "true",
    ]
    rc, out = _run_script(p19_cmd)
    p19_data = _load_json_safe(p19_out / "p19_gate_result.json") or {}
    p19_gate = p19_data.get("gate_decision", "")

    if rc != 0 or not p19_gate:
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate=p16_6_gate,
            p19_gate=p19_gate or "FAILED",
            p17_replay_gate="",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_P19_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason=f"P19 failed (rc={rc}): {out[:300]}",
            paper_only=True,
            production_ready=False,
        )

    p19_enriched_ledger = str(p19_out / "enriched_simulation_ledger.csv")

    # ── Step 3: P17 replay ──────────────────────────────────────────────────
    p17_script = str(_REPO_ROOT / "scripts" / "run_p17_replay_with_p19_enriched_ledger.py")
    rc, out = _run_script([
        p17_script,
        "--recommendation-rows", p16_6_recommendation_rows,
        "--recommendation-summary", p16_6_recommendation_summary,
        "--p19-enriched-ledger", p19_enriched_ledger,
        "--output-dir", str(p17_out),
        "--paper-only", "true",
    ])
    p17_summary = _load_json_safe(p17_out / "paper_recommendation_ledger_summary.json") or {}
    p17_gate = p17_summary.get("p17_gate", "")

    if rc != 0 or not p17_gate:
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate=p16_6_gate,
            p19_gate=p19_gate,
            p17_replay_gate=p17_gate or "FAILED",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_P17_REPLAY_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason=f"P17-replay failed (rc={rc}): {out[:300]}",
            paper_only=True,
            production_ready=False,
        )

    # ── Step 4: P20 ─────────────────────────────────────────────────────────
    p20_script = str(_REPO_ROOT / "scripts" / "run_p20_daily_paper_mlb_orchestrator.py")
    rc, out = _run_script([
        p20_script,
        "--run-date", run_date,
        "--p16-6-dir", str(p16_6_out),
        "--p19-dir", str(p19_out),
        "--p17-replay-dir", str(p17_out),
        "--output-dir", str(p20_out),
        "--paper-only", "true",
    ])
    p20_data = _load_json_safe(p20_out / _P20_GATE_FILE) or {}
    p20_gate = p20_data.get("p20_gate", "")

    if rc != 0 or p20_gate != _P20_GATE_READY:
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate=p16_6_gate,
            p19_gate=p19_gate,
            p17_replay_gate=p17_gate,
            p20_gate=p20_gate or "FAILED",
            date_gate=P23_DATE_BLOCKED_P20_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason=f"P20 failed (rc={rc}): {out[:300]}",
            paper_only=True,
            production_ready=False,
        )

    # ── Collect metrics from P20 + P17 ──────────────────────────────────────
    n_active = int(p20_data.get("n_active_paper_entries", 0))
    n_win = int(p20_data.get("n_settled_win", 0))
    n_loss = int(p20_data.get("n_settled_loss", 0))
    n_unsettled = int(p20_data.get("n_unsettled", 0))
    roi_units = float(p20_data.get("roi_units", 0.0))
    hit_rate = float(p20_data.get("hit_rate", 0.0))
    game_id_coverage = float(p20_data.get("game_id_coverage", 0.0))
    settlement_join_method = p20_data.get("settlement_join_method", "JOIN_BY_GAME_ID")
    total_stake = float(p17_summary.get("total_stake_units", 0.0))
    total_pnl = float(p17_summary.get("total_pnl_units", 0.0))
    n_recommended = int(p20_data.get("n_recommended_rows", n_active))

    return P23ReplayDateResult(
        run_date=run_date,
        source_ready=True,
        p15_preview_ready=True,
        p16_6_gate=p16_6_gate,
        p19_gate=p19_gate,
        p17_replay_gate=p17_gate,
        p20_gate=p20_gate,
        date_gate=P23_DATE_REPLAY_READY,
        n_recommended_rows=n_recommended,
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=n_unsettled,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi_units,
        hit_rate=hit_rate,
        game_id_coverage=game_id_coverage,
        settlement_join_method=settlement_join_method,
        blocker_reason="",
        paper_only=True,
        production_ready=False,
    )


def run_date_replay(
    task: P23ReplayDateTask,
    p22_5_output_dir: str | Path,
    paper_base_dir: str | Path,
    force: bool = False,
) -> P23ReplayDateResult:
    """Run or reuse the full pipeline for a single date.

    If the date already has a valid P20_DAILY_PAPER_ORCHESTRATOR_READY result
    and force=False, the existing result is reused without re-running.

    Args:
        task:              P23ReplayDateTask specification for this date
        p22_5_output_dir:  P22.5 source artifact builder output dir
        paper_base_dir:    Base PAPER output dir (outputs/predictions/PAPER)
        force:             If True, re-run even if P20 result already exists

    Returns:
        P23ReplayDateResult
    """
    run_date = task.run_date
    base_dir = Path(paper_base_dir)
    p22_5_dir = Path(p22_5_output_dir)

    # Check for already-ready P20 (unless --force)
    if task.source_type == "ALREADY_READY" and not force:
        return _build_date_result_from_existing_p20(run_date, base_dir)

    # Source not ready → immediately blocked
    if not task.p22_5_source_ready:
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=False,
            p15_preview_ready=False,
            p16_6_gate="",
            p19_gate="",
            p17_replay_gate="",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_SOURCE_NOT_READY,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason="P22.5 source candidate not ready",
            paper_only=True,
            production_ready=False,
        )

    # Materialize P15 inputs
    mat_result = materialize_p15_inputs_for_date(
        run_date=run_date,
        p22_5_output_dir=p22_5_dir,
        output_base_dir=base_dir,
    )

    if mat_result["status"] != "P23_MATERIALIZED":
        return P23ReplayDateResult(
            run_date=run_date,
            source_ready=True,
            p15_preview_ready=False,
            p16_6_gate="",
            p19_gate="",
            p17_replay_gate="",
            p20_gate="",
            date_gate=P23_DATE_BLOCKED_P15_BUILD_FAILED,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=0.0,
            settlement_join_method="",
            blocker_reason=mat_result.get("blocker_reason", "Materialization failed"),
            paper_only=True,
            production_ready=False,
        )

    # Run P16.6 → P19 → P17 → P20
    p23_replay_dir = base_dir / run_date / "p23_historical_replay"
    p23_replay_dir.mkdir(parents=True, exist_ok=True)

    return _run_pipeline_for_date(
        run_date=run_date,
        mat_result=mat_result,
        paper_base_dir=base_dir,
        p23_replay_dir=p23_replay_dir,
    )
