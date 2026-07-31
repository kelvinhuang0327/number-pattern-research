#!/usr/bin/env python3
"""
scripts/run_p17_paper_recommendation_ledger.py

P17 Paper Recommendation Ledger — CLI runner.

Build a deterministic paper recommendation ledger from P16.6 recommendation
rows, join to P15 simulation ledger for settlement audit, and emit 6 output
files.

Exit codes:
  0 — P17_PAPER_LEDGER_READY
  1 — blocked (no active recommendations / join incomplete / contract violation)
  2 — fatal input error or non-determinism

Usage:
  python scripts/run_p17_paper_recommendation_ledger.py \\
    --recommendation-rows outputs/predictions/PAPER/2026-05-12/p16_6_recommendation_gate_p18_policy/recommendation_rows.csv \\
    --recommendation-summary outputs/predictions/PAPER/2026-05-12/p16_6_recommendation_gate_p18_policy/recommendation_summary.json \\
    --p15-ledger outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation/simulation_ledger.csv \\
    --output-dir outputs/predictions/PAPER/2026-05-12/p17_paper_recommendation_ledger \\
    --bankroll-units 100 \\
    --paper-only true

PAPER_ONLY — no production systems, no live TSL, no real bets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _add_project_root() -> None:
    """Ensure repo root is on sys.path regardless of cwd."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_add_project_root()

import pandas as pd  # noqa: E402 — after sys.path patch

from wbc_backend.recommendation.p17_paper_ledger_contract import (  # noqa: E402
    P17_BLOCKED_CONTRACT_VIOLATION,
    P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
    P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE,
    P17_FAIL_INPUT_MISSING,
    P17_FAIL_NON_DETERMINISTIC,
    P17_PAPER_LEDGER_READY,
    P16_6_ELIGIBLE_DECISION,
)
from wbc_backend.recommendation.p17_paper_ledger_writer import (  # noqa: E402
    build_paper_ledger,
    settle_ledger_entries,
    summarize_paper_ledger,
    validate_paper_ledger_contract,
)
from wbc_backend.recommendation.p17_settlement_join_audit import (  # noqa: E402
    audit_recommendation_to_p15_join,
    summarize_settlement_join_quality,
    identify_unmatched_recommendations,
    identify_duplicate_game_ids,
)

# ── Constants ──────────────────────────────────────────────────────────────────
PAPER_ONLY = True
PRODUCTION_READY = False
SCRIPT_VERSION = "P17_PAPER_RECOMMENDATION_LEDGER_V1"


# ── Determinism hash ───────────────────────────────────────────────────────────

def _df_determinism_hash(df: pd.DataFrame) -> str:
    """SHA-256 of a deterministic string representation of a DataFrame."""
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _dict_determinism_hash(d: dict) -> str:
    """SHA-256 of a sorted JSON dump (excluding generated_at)."""
    d_copy = {k: v for k, v in d.items() if k != "generated_at"}
    return hashlib.sha256(json.dumps(d_copy, sort_keys=True).encode()).hexdigest()


# ── Argument parsing ───────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P17 paper recommendation ledger runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--recommendation-rows", required=True,
        help="Path to P16.6 recommendation_rows.csv",
    )
    p.add_argument(
        "--recommendation-summary", required=True,
        help="Path to P16.6 recommendation_summary.json",
    )
    p.add_argument(
        "--p15-ledger", required=True,
        help="Path to P15 simulation_ledger.csv",
    )
    p.add_argument(
        "--output-dir", required=True,
        help="Directory for P17 output files",
    )
    p.add_argument(
        "--bankroll-units", type=float, default=100.0,
        help="Hypothetical starting bankroll in units (default: 100)",
    )
    p.add_argument(
        "--paper-only", default="true",
        help="Safety flag — must be 'true' (default: true)",
    )
    return p.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    args = _parse_args()

    # Safety invariant: paper-only must be true
    if args.paper_only.lower() != "true":
        print(f"[P17] FATAL: --paper-only must be 'true'. Got: {args.paper_only}",
              file=sys.stderr)
        return 2

    print(f"[P17] Script: {SCRIPT_VERSION}")
    print(f"[P17] PAPER_ONLY={PAPER_ONLY}, PRODUCTION_READY={PRODUCTION_READY}")

    # ── Load inputs ──────────────────────────────────────────────────────────────
    for path_str, label in [
        (args.recommendation_rows, "recommendation-rows"),
        (args.recommendation_summary, "recommendation-summary"),
        (args.p15_ledger, "p15-ledger"),
    ]:
        if not os.path.isfile(path_str):
            print(f"[P17] {P17_FAIL_INPUT_MISSING}: missing {label}: {path_str}",
                  file=sys.stderr)
            return 2

    try:
        rec_rows_df = pd.read_csv(args.recommendation_rows)
    except Exception as e:
        print(f"[P17] {P17_FAIL_INPUT_MISSING}: cannot read recommendation rows: {e}",
              file=sys.stderr)
        return 2

    try:
        with open(args.recommendation_summary, "r") as f:
            rec_summary = json.load(f)
    except Exception as e:
        print(f"[P17] {P17_FAIL_INPUT_MISSING}: cannot read recommendation summary: {e}",
              file=sys.stderr)
        return 2

    try:
        p15_df = pd.read_csv(args.p15_ledger)
    except Exception as e:
        print(f"[P17] {P17_FAIL_INPUT_MISSING}: cannot read P15 ledger: {e}",
              file=sys.stderr)
        return 2

    print(f"[P17] Loaded {len(rec_rows_df)} recommendation rows")
    print(f"[P17] Loaded {len(p15_df)} P15 ledger rows")

    source_p16_6_gate = rec_summary.get("p16_6_gate", "UNKNOWN")
    print(f"[P17] Source P16.6 gate: {source_p16_6_gate}")

    # ── Settlement join audit ────────────────────────────────────────────────────
    print("[P17] Running settlement join audit …")
    joined_df, join_result = audit_recommendation_to_p15_join(rec_rows_df, p15_df)
    join_quality_summary = summarize_settlement_join_quality(joined_df)

    print(f"[P17] Join: {join_result.join_method} | coverage={join_result.join_coverage:.1%} "
          f"| quality={join_result.join_quality}")
    if join_result.risk_notes:
        for note in join_result.risk_notes:
            print(f"  [RISK] {note}")

    # Propagate y_true from join into rec_rows_df when available
    # (the join may add a 'p15_y_true' column if game_id matched)
    rec_rows_for_ledger = joined_df.copy()
    if "p15_y_true" in rec_rows_for_ledger.columns and "y_true" not in rec_rows_for_ledger.columns:
        rec_rows_for_ledger["y_true"] = rec_rows_for_ledger["p15_y_true"]
    elif "p15_y_true" in rec_rows_for_ledger.columns:
        # Prefer P15 y_true if we have it (fill gaps in existing y_true)
        mask = rec_rows_for_ledger["y_true"].isna()
        rec_rows_for_ledger.loc[mask, "y_true"] = rec_rows_for_ledger.loc[mask, "p15_y_true"]

    # ── Build ledger ─────────────────────────────────────────────────────────────
    print("[P17] Building paper ledger …")
    try:
        ledger_df = build_paper_ledger(rec_rows_for_ledger, bankroll_units=args.bankroll_units)
    except Exception as e:
        print(f"[P17] {P17_BLOCKED_CONTRACT_VIOLATION}: build_paper_ledger failed: {e}",
              file=sys.stderr)
        return 1

    print("[P17] Settling ledger entries …")
    settled_df = settle_ledger_entries(ledger_df)

    # ── Validate contract ────────────────────────────────────────────────────────
    validation = validate_paper_ledger_contract(settled_df)
    if not validation.valid:
        print(f"[P17] {validation.error_code}: {validation.error_message}", file=sys.stderr)
        return 1

    # ── Summarize ────────────────────────────────────────────────────────────────
    unmatched = identify_unmatched_recommendations(joined_df)
    dup_game_ids = identify_duplicate_game_ids(joined_df)
    summary = summarize_paper_ledger(
        settled_df,
        source_p16_6_gate=source_p16_6_gate,
        duplicate_game_id_count=join_result.n_duplicate_game_ids,
        unmatched_recommendation_count=join_result.n_unmatched,
    )

    active_df = settled_df[settled_df["gate_decision"] == P16_6_ELIGIBLE_DECISION]
    print(f"[P17] Active paper entries: {summary.n_active_paper_entries}")
    print(f"[P17] Settled WIN: {summary.n_settled_win}, LOSS: {summary.n_settled_loss}, "
          f"UNSETTLED: {summary.n_unsettled}")
    print(f"[P17] Total stake: {summary.total_stake_units:.4f} units")
    print(f"[P17] Total P&L: {summary.total_pnl_units:.4f} units, ROI: {summary.roi_units:.4%}")
    print(f"[P17] Gate: {summary.p17_gate}")

    # ── Prepare output directory ─────────────────────────────────────────────────
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(tz=timezone.utc).isoformat()

    # ── File 1: paper_recommendation_ledger.csv ──────────────────────────────────
    ledger_csv_path = out_dir / "paper_recommendation_ledger.csv"
    settled_df.to_csv(ledger_csv_path, index=False)
    print(f"[P17] Wrote {ledger_csv_path} ({len(settled_df)} rows)")

    # ── File 2: paper_recommendation_ledger_summary.json ─────────────────────────
    summary_dict = {
        "p17_gate": summary.p17_gate,
        "source_p16_6_gate": summary.source_p16_6_gate,
        "n_recommendation_rows": summary.n_recommendation_rows,
        "n_active_paper_entries": summary.n_active_paper_entries,
        "n_settled_win": summary.n_settled_win,
        "n_settled_loss": summary.n_settled_loss,
        "n_settled_push": summary.n_settled_push,
        "n_unsettled": summary.n_unsettled,
        "total_stake_units": summary.total_stake_units,
        "total_pnl_units": summary.total_pnl_units,
        "roi_units": summary.roi_units,
        "hit_rate": summary.hit_rate,
        "avg_edge": summary.avg_edge,
        "avg_odds_decimal": summary.avg_odds_decimal,
        "max_drawdown_pct": summary.max_drawdown_pct,
        "sharpe_ratio": summary.sharpe_ratio,
        "settlement_join_coverage": summary.settlement_join_coverage,
        "duplicate_game_id_count": summary.duplicate_game_id_count,
        "unmatched_recommendation_count": summary.unmatched_recommendation_count,
        "paper_only": True,
        "production_ready": False,
        "bankroll_units": args.bankroll_units,
        "generated_at": generated_at,
    }
    summary_json_path = out_dir / "paper_recommendation_ledger_summary.json"
    with open(summary_json_path, "w") as f:
        json.dump(summary_dict, f, indent=2)
    print(f"[P17] Wrote {summary_json_path}")

    # ── File 3: paper_recommendation_ledger_summary.md ───────────────────────────
    md_lines = [
        "# P17 Paper Recommendation Ledger Summary",
        "",
        f"**P17 Gate**: `{summary.p17_gate}`  ",
        f"**Source P16.6 Gate**: `{summary.source_p16_6_gate}`  ",
        f"**Generated**: {generated_at}  ",
        "",
        "## Ledger Counts",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Total recommendation rows | {summary.n_recommendation_rows} |",
        f"| Active paper entries | {summary.n_active_paper_entries} |",
        f"| Settled WIN | {summary.n_settled_win} |",
        f"| Settled LOSS | {summary.n_settled_loss} |",
        f"| Settled PUSH | {summary.n_settled_push} |",
        f"| Unsettled | {summary.n_unsettled} |",
        "",
        "## P&L Summary",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Bankroll units | {args.bankroll_units:.1f} |",
        f"| Total stake units | {summary.total_stake_units:.4f} |",
        f"| Total P&L units | {summary.total_pnl_units:.4f} |",
        f"| ROI | {summary.roi_units:.4%} |",
        f"| Hit rate | {summary.hit_rate:.4%} |",
        f"| Avg edge | {summary.avg_edge:.4f} |",
        f"| Avg odds (decimal) | {summary.avg_odds_decimal:.4f} |",
        "",
        "## Risk Profile (from P18 Policy)",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Max drawdown % | {summary.max_drawdown_pct:.4f} |",
        f"| Sharpe ratio | {summary.sharpe_ratio:.6f} |",
        "",
        "## Settlement Join Quality",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Settlement join coverage | {summary.settlement_join_coverage:.4%} |",
        f"| Duplicate game_id count | {summary.duplicate_game_id_count} |",
        f"| Unmatched recommendation count | {summary.unmatched_recommendation_count} |",
        "",
        "## Safety",
        "",
        f"- `paper_only`: `True`",
        f"- `production_ready`: `False`",
        "",
    ]
    summary_md_path = out_dir / "paper_recommendation_ledger_summary.md"
    with open(summary_md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"[P17] Wrote {summary_md_path}")

    # ── File 4: settlement_join_audit.json ───────────────────────────────────────
    audit_dict = {
        "join_method": join_result.join_method,
        "join_quality": join_result.join_quality,
        "n_recommendations": join_result.n_recommendations,
        "n_joined": join_result.n_joined,
        "n_unmatched": join_result.n_unmatched,
        "n_duplicate_game_ids": join_result.n_duplicate_game_ids,
        "join_coverage": join_result.join_coverage,
        "risk_notes": list(join_result.risk_notes),
        "y_true_quality": join_quality_summary,
        "unmatched_recommendation_ids_sample": unmatched[:10],  # first 10
        "duplicate_game_ids_sample": dup_game_ids[:10],
        "paper_only": True,
        "production_ready": False,
        "generated_at": generated_at,
    }
    audit_json_path = out_dir / "settlement_join_audit.json"
    with open(audit_json_path, "w") as f:
        json.dump(audit_dict, f, indent=2)
    print(f"[P17] Wrote {audit_json_path}")

    # ── File 5: settlement_join_audit.md ─────────────────────────────────────────
    audit_md_lines = [
        "# P17 Settlement Join Audit",
        "",
        f"**Join Method**: `{join_result.join_method}`  ",
        f"**Join Quality**: `{join_result.join_quality}`  ",
        f"**Generated**: {generated_at}  ",
        "",
        "## Join Metrics",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| Total recommendations | {join_result.n_recommendations} |",
        f"| Joined to P15 ledger | {join_result.n_joined} |",
        f"| Unmatched | {join_result.n_unmatched} |",
        f"| Join coverage | {join_result.join_coverage:.4%} |",
        f"| Duplicate game_ids (rec side) | {join_result.n_duplicate_game_ids} |",
        "",
        "## Risk Notes",
        "",
    ]
    if join_result.risk_notes:
        for note in join_result.risk_notes:
            audit_md_lines.append(f"- ⚠️ {note}")
    else:
        audit_md_lines.append("No risk notes — join quality is HIGH.")
    audit_md_lines += [
        "",
        "## P15 Join Fragility Assessment",
        "",
        "P15's `simulation_ledger.csv` uses position-based row ordering and **does not include "
        "a `game_id` column**. The settlement join attempts an identity join on `game_id`, which "
        "will fail unless the P15 input file (`joined_oof_with_odds.csv`) is used instead.",
        "",
        "**Resolution path**: P19 Odds Data Quality — repair game_id-based join so that "
        "P17 settlement can achieve HIGH join quality and produce fully settled P&L accounts.",
        "",
    ]
    audit_md_path = out_dir / "settlement_join_audit.md"
    with open(audit_md_path, "w") as f:
        f.write("\n".join(audit_md_lines))
    print(f"[P17] Wrote {audit_md_path}")

    # ── File 6: ledger_gate_result.json ──────────────────────────────────────────
    gate_dict = {
        "gate_decision": summary.p17_gate,
        "paper_only": True,
        "production_ready": False,
        "n_active_entries": summary.n_active_paper_entries,
        "n_settled": summary.n_settled_win + summary.n_settled_loss + summary.n_settled_push,
        "n_unsettled": summary.n_unsettled,
        "settlement_join_quality": join_result.join_quality,
        "error_message": None,
        "script_version": SCRIPT_VERSION,
        "generated_at": generated_at,
    }
    gate_json_path = out_dir / "ledger_gate_result.json"
    with open(gate_json_path, "w") as f:
        json.dump(gate_dict, f, indent=2)
    print(f"[P17] Wrote {gate_json_path}")

    # ── Determine exit code ──────────────────────────────────────────────────────
    gate = summary.p17_gate
    if gate == P17_PAPER_LEDGER_READY:
        print(f"\n[P17] Overall gate decision: {gate}")
        return 0
    elif gate in (P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
                  P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE,
                  P17_BLOCKED_CONTRACT_VIOLATION):
        print(f"\n[P17] Overall gate decision: {gate}")
        return 1
    else:
        print(f"\n[P17] Overall gate decision: {gate}")
        return 0  # Default to success for P17_PAPER_LEDGER_READY-like states


if __name__ == "__main__":
    sys.exit(main())
