#!/usr/bin/env python3
"""
scripts/run_p17_replay_with_p19_enriched_ledger.py

P17 Paper Recommendation Ledger Replay — uses P19-enriched simulation ledger.

This replays the P17 pipeline but sources game_id / y_true from the
P19-enriched simulation ledger instead of the raw P15 output.

Expected outcome: P17_PAPER_LEDGER_READY, ~100% settlement coverage

Exit codes:
  0 — P17_PAPER_LEDGER_READY
  1 — blocked
  2 — fatal

Usage:
  python scripts/run_p17_replay_with_p19_enriched_ledger.py \\
    --recommendation-rows  outputs/.../recommendation_rows.csv \\
    --recommendation-summary  outputs/.../recommendation_summary.json \\
    --p19-enriched-ledger  outputs/.../p19_odds_identity_join_repair/enriched_simulation_ledger.csv \\
    --output-dir  outputs/.../p17_replay_with_p19_identity \\
    --bankroll-units 100 \\
    --paper-only true

PAPER_ONLY — no production systems, no live TSL, no real bets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _add_project_root() -> None:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_add_project_root()

import pandas as pd  # noqa: E402

from wbc_backend.recommendation.p17_paper_ledger_contract import (  # noqa: E402
    P17_BLOCKED_CONTRACT_VIOLATION,
    P17_BLOCKED_NO_ACTIVE_RECOMMENDATIONS,
    P17_BLOCKED_SETTLEMENT_JOIN_INCOMPLETE,
    P17_FAIL_INPUT_MISSING,
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
    audit_recommendation_to_enriched_p15_join,
    summarize_settlement_join_quality,
    identify_unmatched_recommendations,
    identify_duplicate_game_ids,
)

SCRIPT_VERSION = "P17_REPLAY_WITH_P19_IDENTITY_V1"
PAPER_ONLY = True
PRODUCTION_READY = False


def _df_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=SCRIPT_VERSION)
    parser.add_argument("--recommendation-rows", required=True)
    parser.add_argument("--recommendation-summary", required=True)
    parser.add_argument("--p19-enriched-ledger", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--bankroll-units", type=float, default=100.0)
    parser.add_argument("--paper-only", default="true")
    args = parser.parse_args()

    if args.paper_only.lower() != "true":
        print(f"[P17-REPLAY] FATAL: --paper-only must be 'true'. Got: {args.paper_only}",
              file=sys.stderr)
        return 2

    print(f"[P17-REPLAY] Script: {SCRIPT_VERSION}")
    print(f"[P17-REPLAY] PAPER_ONLY=True, PRODUCTION_READY=False")

    # Validate inputs
    for path_str, label in [
        (args.recommendation_rows, "recommendation-rows"),
        (args.recommendation_summary, "recommendation-summary"),
        (args.p19_enriched_ledger, "p19-enriched-ledger"),
    ]:
        if not Path(path_str).exists():
            print(f"[P17-REPLAY] {P17_FAIL_INPUT_MISSING}: missing {label}: {path_str}",
                  file=sys.stderr)
            return 2

    rec_df = pd.read_csv(args.recommendation_rows)
    enriched_df = pd.read_csv(args.p19_enriched_ledger)
    with open(args.recommendation_summary) as f:
        rec_summary = json.load(f)

    print(f"[P17-REPLAY] Loaded {len(rec_df)} recommendation rows")
    print(f"[P17-REPLAY] Loaded {len(enriched_df)} enriched P15 rows")

    # Check enrichment status
    if "identity_enrichment_status" in enriched_df.columns:
        status = enriched_df["identity_enrichment_status"].iloc[0] if len(enriched_df) > 0 else "UNKNOWN"
        print(f"[P17-REPLAY] Enrichment status: {status}")

    # Settlement join audit using enriched ledger
    print("[P17-REPLAY] Running settlement join audit (enriched) …")
    joined_df, join_result = audit_recommendation_to_enriched_p15_join(rec_df, enriched_df)

    print(
        f"[P17-REPLAY] Join: {join_result.join_method} | "
        f"coverage={join_result.join_coverage:.1%} | "
        f"quality={join_result.join_quality}"
    )
    for note in join_result.risk_notes:
        print(f"  [RISK] {note}")

    # Propagate y_true from join
    rec_rows_for_ledger = joined_df.copy()
    if "p15_y_true" in rec_rows_for_ledger.columns and "y_true" not in rec_rows_for_ledger.columns:
        rec_rows_for_ledger["y_true"] = rec_rows_for_ledger["p15_y_true"]
    elif "p15_y_true" in rec_rows_for_ledger.columns:
        mask = rec_rows_for_ledger["y_true"].isna()
        rec_rows_for_ledger.loc[mask, "y_true"] = rec_rows_for_ledger.loc[mask, "p15_y_true"]

    # Build paper ledger
    print("[P17-REPLAY] Building paper ledger …")
    try:
        ledger_df = build_paper_ledger(rec_rows_for_ledger, bankroll_units=args.bankroll_units)
    except Exception as e:
        print(f"[P17-REPLAY] {P17_BLOCKED_CONTRACT_VIOLATION}: {e}", file=sys.stderr)
        return 1

    settled_df = settle_ledger_entries(ledger_df)

    # Contract validation
    validation = validate_paper_ledger_contract(settled_df)
    if not validation.valid:
        print(f"[P17-REPLAY] {validation.error_code}: {validation.error_message}", file=sys.stderr)
        return 1

    source_gate = rec_summary.get("p16_6_gate", "UNKNOWN")
    unmatched = identify_unmatched_recommendations(joined_df)
    summary = summarize_paper_ledger(
        settled_df,
        source_p16_6_gate=source_gate,
        duplicate_game_id_count=join_result.n_duplicate_game_ids,
        unmatched_recommendation_count=join_result.n_unmatched,
    )

    print(f"[P17-REPLAY] Active entries: {summary.n_active_paper_entries}")
    print(
        f"[P17-REPLAY] Settled WIN: {summary.n_settled_win}, "
        f"LOSS: {summary.n_settled_loss}, "
        f"UNSETTLED: {summary.n_unsettled}"
    )
    print(f"[P17-REPLAY] ROI: {summary.roi_units:.4%}")
    print(f"[P17-REPLAY] Gate: {summary.p17_gate}")

    # Write outputs
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _now()

    # paper_recommendation_ledger.csv
    csv_path = out_dir / "paper_recommendation_ledger.csv"
    settled_df.to_csv(csv_path, index=False)
    print(f"[P17-REPLAY] Wrote {csv_path} ({len(settled_df)} rows)")

    # summary.json
    summary_dict = {
        "p17_gate": summary.p17_gate,
        "source_p16_6_gate": summary.source_p16_6_gate,
        "source_p19_enrichment": True,
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
        "settlement_join_method": join_result.join_method,
        "duplicate_game_id_count": summary.duplicate_game_id_count,
        "unmatched_recommendation_count": summary.unmatched_recommendation_count,
        "paper_only": True,
        "production_ready": False,
        "bankroll_units": args.bankroll_units,
        "generated_at": generated_at,
    }
    summary_json = out_dir / "paper_recommendation_ledger_summary.json"
    with open(summary_json, "w") as f:
        json.dump(summary_dict, f, indent=2)
    print(f"[P17-REPLAY] Wrote {summary_json}")

    # settlement_join_audit.json
    join_audit = {
        "join_method": join_result.join_method,
        "join_quality": join_result.join_quality,
        "n_recommendations": join_result.n_recommendations,
        "n_joined": join_result.n_joined,
        "n_unmatched": join_result.n_unmatched,
        "n_duplicate_game_ids": join_result.n_duplicate_game_ids,
        "join_coverage": join_result.join_coverage,
        "risk_notes": list(join_result.risk_notes),
        "source_p19_enrichment": True,
        "paper_only": True,
        "production_ready": False,
        "generated_at": generated_at,
    }
    with open(out_dir / "settlement_join_audit.json", "w") as f:
        json.dump(join_audit, f, indent=2)

    # ledger_gate_result.json
    gate_result = {
        "p17_gate": summary.p17_gate,
        "source_p19_enrichment": True,
        "paper_only": True,
        "production_ready": False,
        "determinism_hash": _df_hash(settled_df),
        "script_version": SCRIPT_VERSION,
        "generated_at": generated_at,
    }
    with open(out_dir / "ledger_gate_result.json", "w") as f:
        json.dump(gate_result, f, indent=2)

    print(f"\n[P17-REPLAY] Overall gate: {summary.p17_gate}")
    return 0 if summary.p17_gate == P17_PAPER_LEDGER_READY else 1


if __name__ == "__main__":
    sys.exit(main())
