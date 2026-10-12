"""
wbc_backend/recommendation/p20_daily_summary_aggregator.py

P20 Daily PAPER MLB Orchestrator — loads phase outputs, aggregates the
daily summary, validates the contract, and writes output files.

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    EXPECTED_P16_6_GATE,
    EXPECTED_P17_REPLAY_GATE,
    EXPECTED_P19_GATE,
    P20_BLOCKED_CONTRACT_VIOLATION,
    P20_BLOCKED_P16_6_NOT_READY,
    P20_BLOCKED_P17_REPLAY_NOT_READY,
    P20_BLOCKED_P19_NOT_READY,
    P20_DAILY_PAPER_ORCHESTRATOR_READY,
    P20_FAIL_INPUT_MISSING,
    P20DailyPaperGateResult,
    P20DailyPaperRunSummary,
)
from wbc_backend.recommendation.p20_artifact_manifest import ValidationResult

SCRIPT_VERSION = "P20_DAILY_PAPER_ORCHESTRATOR_V1"


# ---------------------------------------------------------------------------
# Phase output loader
# ---------------------------------------------------------------------------

def load_phase_outputs(
    p16_6_dir: str,
    p19_dir: str,
    p17_replay_dir: str,
) -> dict:
    """Load JSON summaries from each upstream phase directory.

    Returns a dict with keys: p16_6_summary, p19_gate, p17_replay_summary,
    p17_replay_ledger_df.  Raises FileNotFoundError on any missing required file.
    """
    def _load_json(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Required file not found: {path}")
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)

    p16_6_summary = _load_json(f"{p16_6_dir}/recommendation_summary.json")
    p19_gate = _load_json(f"{p19_dir}/p19_gate_result.json")
    p17_replay_summary = _load_json(f"{p17_replay_dir}/paper_recommendation_ledger_summary.json")

    # Load the ledger CSV for row-level metrics
    ledger_path = Path(f"{p17_replay_dir}/paper_recommendation_ledger.csv")
    if not ledger_path.exists():
        raise FileNotFoundError(f"Required file not found: {ledger_path}")
    p17_replay_ledger_df = pd.read_csv(ledger_path)

    return {
        "p16_6_summary": p16_6_summary,
        "p19_gate": p19_gate,
        "p17_replay_summary": p17_replay_summary,
        "p17_replay_ledger_df": p17_replay_ledger_df,
    }


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def aggregate_daily_paper_summary(
    run_date: str,
    phase_outputs: dict,
    generated_artifact_count: int = 4,
) -> P20DailyPaperRunSummary:
    """Build a P20DailyPaperRunSummary from loaded phase outputs."""

    p16_6_summary: dict = phase_outputs["p16_6_summary"]
    p19_gate: dict = phase_outputs["p19_gate"]
    p17_replay_summary: dict = phase_outputs["p17_replay_summary"]
    ledger_df: pd.DataFrame = phase_outputs["p17_replay_ledger_df"]

    source_p16_6_gate = p17_replay_summary.get("source_p16_6_gate", "")
    source_p19_gate = p19_gate.get("gate_decision", "")
    source_p17_replay_gate = p17_replay_summary.get("p17_gate", "")

    n_input_rows = int(p17_replay_summary.get("n_recommendation_rows", 0))
    n_active = int(p17_replay_summary.get("n_active_paper_entries", 0))
    n_win = int(p17_replay_summary.get("n_settled_win", 0))
    n_loss = int(p17_replay_summary.get("n_settled_loss", 0))
    n_unsettled = int(p17_replay_summary.get("n_unsettled", 0))

    total_stake = float(p17_replay_summary.get("total_stake_units", 0.0))
    total_pnl = float(p17_replay_summary.get("total_pnl_units", 0.0))
    roi = float(p17_replay_summary.get("roi_units", 0.0))
    hit_rate = float(p17_replay_summary.get("hit_rate", 0.0))
    avg_edge = float(p17_replay_summary.get("avg_edge", 0.0))
    avg_odds = float(p17_replay_summary.get("avg_odds_decimal", 0.0))
    max_dd = float(p17_replay_summary.get("max_drawdown_pct", 0.0))
    sharpe = float(p17_replay_summary.get("sharpe_ratio", 0.0))
    bankroll = float(p17_replay_summary.get("bankroll_units", 100.0))

    join_method = str(p17_replay_summary.get("settlement_join_method", ""))
    game_id_coverage = float(p19_gate.get("game_id_coverage_after", 0.0))

    # Determine gate
    if source_p16_6_gate != EXPECTED_P16_6_GATE:
        p20_gate = P20_BLOCKED_P16_6_NOT_READY
    elif source_p19_gate != EXPECTED_P19_GATE:
        p20_gate = P20_BLOCKED_P19_NOT_READY
    elif source_p17_replay_gate != EXPECTED_P17_REPLAY_GATE:
        p20_gate = P20_BLOCKED_P17_REPLAY_NOT_READY
    elif n_unsettled > 0:
        p20_gate = P20_BLOCKED_CONTRACT_VIOLATION
    elif not p17_replay_summary.get("paper_only", False):
        p20_gate = P20_BLOCKED_CONTRACT_VIOLATION
    elif p17_replay_summary.get("production_ready", True):
        p20_gate = P20_BLOCKED_CONTRACT_VIOLATION
    else:
        p20_gate = P20_DAILY_PAPER_ORCHESTRATOR_READY

    return P20DailyPaperRunSummary(
        run_date=run_date,
        p20_gate=p20_gate,
        source_p16_6_gate=source_p16_6_gate,
        source_p19_gate=source_p19_gate,
        source_p17_replay_gate=source_p17_replay_gate,
        n_input_rows=n_input_rows,
        n_recommended_rows=n_active,
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=n_unsettled,
        settlement_join_method=join_method,
        game_id_coverage=game_id_coverage,
        total_stake_units=total_stake,
        total_pnl_units=total_pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        paper_only=bool(p17_replay_summary.get("paper_only", True)),
        production_ready=bool(p17_replay_summary.get("production_ready", False)),
        generated_artifact_count=generated_artifact_count,
        avg_edge=avg_edge,
        avg_odds_decimal=avg_odds,
        bankroll_units=bankroll,
        script_version=SCRIPT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------

def validate_daily_summary_contract(summary: P20DailyPaperRunSummary) -> ValidationResult:
    """Validate invariants on the aggregated daily summary."""
    if summary.production_ready:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_CONTRACT_VIOLATION,
            error_message="production_ready must be False",
        )
    if not summary.paper_only:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_CONTRACT_VIOLATION,
            error_message="paper_only must be True",
        )
    if summary.source_p16_6_gate != EXPECTED_P16_6_GATE:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_P16_6_NOT_READY,
            error_message=f"P16.6 gate not ready: {summary.source_p16_6_gate}",
        )
    if summary.source_p19_gate != EXPECTED_P19_GATE:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_P19_NOT_READY,
            error_message=f"P19 gate not ready: {summary.source_p19_gate}",
        )
    if summary.source_p17_replay_gate != EXPECTED_P17_REPLAY_GATE:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_P17_REPLAY_NOT_READY,
            error_message=f"P17 replay gate not ready: {summary.source_p17_replay_gate}",
        )
    if summary.n_unsettled > 0:
        return ValidationResult(
            valid=False,
            error_code=P20_BLOCKED_CONTRACT_VIOLATION,
            error_message=f"n_unsettled must be 0, got {summary.n_unsettled}",
        )
    return ValidationResult(valid=True)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _summary_to_dict(summary: P20DailyPaperRunSummary) -> dict:
    return {
        "run_date": summary.run_date,
        "p20_gate": summary.p20_gate,
        "source_p16_6_gate": summary.source_p16_6_gate,
        "source_p19_gate": summary.source_p19_gate,
        "source_p17_replay_gate": summary.source_p17_replay_gate,
        "n_input_rows": summary.n_input_rows,
        "n_recommended_rows": summary.n_recommended_rows,
        "n_active_paper_entries": summary.n_active_paper_entries,
        "n_settled_win": summary.n_settled_win,
        "n_settled_loss": summary.n_settled_loss,
        "n_unsettled": summary.n_unsettled,
        "settlement_join_method": summary.settlement_join_method,
        "game_id_coverage": summary.game_id_coverage,
        "total_stake_units": summary.total_stake_units,
        "total_pnl_units": summary.total_pnl_units,
        "roi_units": summary.roi_units,
        "hit_rate": summary.hit_rate,
        "max_drawdown_pct": summary.max_drawdown_pct,
        "sharpe_ratio": summary.sharpe_ratio,
        "avg_edge": summary.avg_edge,
        "avg_odds_decimal": summary.avg_odds_decimal,
        "bankroll_units": summary.bankroll_units,
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "generated_artifact_count": summary.generated_artifact_count,
        "script_version": summary.script_version,
        "generated_at": summary.generated_at,
    }


def _summary_to_md(summary: P20DailyPaperRunSummary, manifest_summary: dict) -> str:
    roi_pct = summary.roi_units * 100
    hit_pct = summary.hit_rate * 100
    cov_pct = summary.game_id_coverage * 100
    lines = [
        f"# P20 Daily PAPER MLB Orchestrator — {summary.run_date}",
        "",
        f"**Gate**: `{summary.p20_gate}`  ",
        f"**Paper Only**: {summary.paper_only}  ",
        f"**Production Ready**: {summary.production_ready}",
        "",
        "## Upstream Gate Sources",
        "",
        f"| Phase | Gate |",
        f"|-------|------|",
        f"| P16.6 | `{summary.source_p16_6_gate}` |",
        f"| P19   | `{summary.source_p19_gate}` |",
        f"| P17 Replay | `{summary.source_p17_replay_gate}` |",
        "",
        "## Settlement Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| n_input_rows | {summary.n_input_rows} |",
        f"| n_active_paper_entries | {summary.n_active_paper_entries} |",
        f"| n_settled_win | {summary.n_settled_win} |",
        f"| n_settled_loss | {summary.n_settled_loss} |",
        f"| n_unsettled | {summary.n_unsettled} |",
        f"| settlement_join_method | `{summary.settlement_join_method}` |",
        f"| game_id_coverage | {cov_pct:.1f}% |",
        "",
        "## Performance Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| total_stake_units | {summary.total_stake_units:.4f} |",
        f"| total_pnl_units | {summary.total_pnl_units:.4f} |",
        f"| ROI | {roi_pct:.4f}% |",
        f"| hit_rate | {hit_pct:.4f}% |",
        f"| avg_edge | {summary.avg_edge:.6f} |",
        f"| avg_odds_decimal | {summary.avg_odds_decimal:.6f} |",
        f"| max_drawdown_pct | {summary.max_drawdown_pct:.6f}% |",
        f"| sharpe_ratio | {summary.sharpe_ratio:.6f} |",
        "",
        "## Artifact Manifest",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| total_artifacts | {manifest_summary.get('total_artifacts', 0)} |",
        f"| required_present | {manifest_summary.get('required_artifacts_present', 0)} |",
        f"| required_missing | {manifest_summary.get('required_artifacts_missing', 0)} |",
        "",
        "## Safety Invariants",
        "",
        f"- `PAPER_ONLY = {summary.paper_only}`",
        f"- `PRODUCTION_READY = {summary.production_ready}`",
        "",
        "## Terminal Marker",
        "",
        f"`{summary.p20_gate}`",
    ]
    return "\n".join(lines)


def write_daily_summary_outputs(
    summary: P20DailyPaperRunSummary,
    manifest_summary: dict,
    output_dir: str,
) -> list[str]:
    """Write all P20 output files. Returns list of written paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # daily_paper_summary.json (exclude generated_at for determinism in comparisons)
    summary_dict = _summary_to_dict(summary)
    summary_path = out / "daily_paper_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary_dict, fh, indent=2, ensure_ascii=False)
    written.append(str(summary_path))

    # daily_paper_summary.md
    md_path = out / "daily_paper_summary.md"
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(_summary_to_md(summary, manifest_summary))
    written.append(str(md_path))

    # artifact_manifest.json
    manifest_path = out / "artifact_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest_summary, fh, indent=2, ensure_ascii=False)
    written.append(str(manifest_path))

    # p20_gate_result.json
    gate_dict = {
        "run_date": summary.run_date,
        "p20_gate": summary.p20_gate,
        "paper_only": summary.paper_only,
        "production_ready": summary.production_ready,
        "n_recommended_rows": summary.n_recommended_rows,
        "n_active_paper_entries": summary.n_active_paper_entries,
        "n_settled_win": summary.n_settled_win,
        "n_settled_loss": summary.n_settled_loss,
        "n_unsettled": summary.n_unsettled,
        "roi_units": summary.roi_units,
        "hit_rate": summary.hit_rate,
        "settlement_join_method": summary.settlement_join_method,
        "game_id_coverage": summary.game_id_coverage,
        "script_version": summary.script_version,
        "generated_at": summary.generated_at,
    }
    gate_path = out / "p20_gate_result.json"
    with open(gate_path, "w", encoding="utf-8") as fh:
        json.dump(gate_dict, fh, indent=2, ensure_ascii=False)
    written.append(str(gate_path))

    return written
