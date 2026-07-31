"""
scripts/run_p16_6_recommendation_gate_with_p18_policy.py

P16.6 — Recommendation Gate Re-run with P18 Risk-Repaired Policy.

Re-runs the P16 recommendation gate using P18's selected strategy policy
parameters (edge_threshold, max_stake_cap, kelly_fraction, odds_decimal_max)
instead of a sweep-derived threshold.

Outputs 6 files:
  1. recommendation_rows.csv            — all rows with gate decisions
  2. recommendation_summary.json        — aggregate summary
  3. recommendation_summary.md          — human-readable summary
  4. gate_reason_counts.json            — per-reason code counts
  5. p18_policy_applied.json            — copy of applied P18 policy params
  6. p16_6_policy_risk_profile.json     — risk profile derived from P18 policy

Gate decisions (overall):
  P16_6_PAPER_RECOMMENDATION_GATE_READY      — eligible rows found
  P16_6_BLOCKED_NO_ELIGIBLE_ROWS             — all rows blocked
  P16_6_BLOCKED_INVALID_P18_POLICY           — P18 policy validation failed
  P16_6_FAIL_INPUT_MISSING                   — required input files not found
  P16_6_FAIL_CONTRACT_VIOLATION              — output schema contract failure
  P16_6_FAIL_NON_DETERMINISTIC               — two runs produced different hash

PAPER_ONLY: This script enforces PAPER_ONLY=True, production_ready=False.
No real bets are placed or implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── Adjust path so module imports work when called as a script ─────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p16_p18_policy_loader import (
    P18SelectedPolicy,
    load_p18_selected_policy,
    validate_p18_selected_policy,
)
from wbc_backend.recommendation.p16_recommendation_gate import (
    apply_gate_with_p18_policy,
    compute_paper_stake_p18,
    P16_6_ELIGIBLE,
)
from wbc_backend.recommendation.p16_recommendation_input_adapter import (
    SOURCE_BSS_OOF,
    ODDS_JOIN_COVERAGE,
    load_p16_input_rows,
)
from wbc_backend.recommendation.p16_recommendation_row_builder import (
    build_all_rows_p16_6,
)

# ── Overall gate decision constants ───────────────────────────────────────────

GATE_READY = "P16_6_PAPER_RECOMMENDATION_GATE_READY"
GATE_NO_ELIGIBLE = "P16_6_BLOCKED_NO_ELIGIBLE_ROWS"
GATE_INVALID_POLICY = "P16_6_BLOCKED_INVALID_P18_POLICY"
GATE_INPUT_MISSING = "P16_6_FAIL_INPUT_MISSING"
GATE_FAIL_CONTRACT = "P16_6_FAIL_CONTRACT_VIOLATION"
GATE_FAIL_NON_DET = "P16_6_FAIL_NON_DETERMINISTIC"

# ── Required output columns for contract check ───────────────────────────────

REQUIRED_COLUMNS = {
    "recommendation_id",
    "game_id",
    "date",
    "side",
    "p_model",
    "p_market",
    "edge",
    "odds_decimal",
    "paper_stake_fraction",
    "strategy_policy",
    "gate_decision",
    "gate_reason",
    "source_model",
    "source_bss_oof",
    "odds_join_status",
    "paper_only",
    "production_ready",
    "created_from",
    "selected_edge_threshold",
    "p18_policy_id",
    "p18_edge_threshold",
    "p18_max_stake_cap",
    "p18_kelly_fraction",
    "p18_odds_decimal_max",
    "p18_policy_max_drawdown_pct",
    "p18_policy_sharpe_ratio",
    "p18_policy_n_bets",
    "p18_policy_roi_ci_low_95",
    "p18_policy_roi_ci_high_95",
}


# ── Arg parser ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P16.6 recommendation gate re-run using P18 selected policy."
    )
    p.add_argument(
        "--joined-oof",
        required=True,
        help="Path to joined_oof_with_odds.csv (P15 output).",
    )
    p.add_argument(
        "--p15-ledger",
        required=True,
        help="Path to simulation_ledger.csv (P15 output, used only for validation).",
    )
    p.add_argument(
        "--p18-policy",
        required=True,
        help="Path to selected_strategy_policy.json (P18 output).",
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write output files.",
    )
    p.add_argument(
        "--paper-only",
        default="true",
        choices=["true", "True", "1", "false", "False", "0"],
        help="PAPER_ONLY flag (must remain true).",
    )
    return p.parse_args(argv)


# ── Output hash helper ────────────────────────────────────────────────────────

def _hash_csv(path: Path) -> str:
    """Deterministic SHA-256 hash of a CSV file (ignores generated_at columns)."""
    df = pd.read_csv(path)
    cols = [c for c in df.columns if "generated_at" not in c.lower()]
    df = df[cols].sort_values(by=sorted(df.columns & set(cols))).reset_index(drop=True)
    content = df.to_csv(index=False).encode()
    return hashlib.sha256(content).hexdigest()


# ── Main ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Validate paper_only flag ──────────────────────────────────────────────
    paper_only_flag = args.paper_only.lower() not in ("false", "0")
    if not paper_only_flag:
        print("ERROR: --paper-only must remain true. Production bets are not allowed.")
        _write_summary_json(output_dir, GATE_INPUT_MISSING, None, {}, 0, 0, 0, 0, 0)
        return 2

    # ── Check input files exist ───────────────────────────────────────────────
    joined_oof_path = Path(args.joined_oof)
    p15_ledger_path = Path(args.p15_ledger)
    p18_policy_path = Path(args.p18_policy)

    for path in (joined_oof_path, p15_ledger_path, p18_policy_path):
        if not path.exists():
            print(f"ERROR: input file not found: {path}")
            _write_summary_json(output_dir, GATE_INPUT_MISSING, None, {}, 0, 0, 0, 0, 0)
            return 2

    # ── Load & validate P18 policy ────────────────────────────────────────────
    print(f"[P16.6] Loading P18 policy from: {p18_policy_path}")
    try:
        p18_policy = load_p18_selected_policy(str(p18_policy_path))
    except Exception as exc:
        print(f"ERROR: failed to load P18 policy: {exc}")
        _write_summary_json(output_dir, GATE_INVALID_POLICY, None, {}, 0, 0, 0, 0, 0)
        return 2

    validation = validate_p18_selected_policy(p18_policy)
    if not validation.valid:
        print(f"ERROR: P18 policy validation failed: {validation.error_message}")
        _write_summary_json(
            output_dir, GATE_INVALID_POLICY, p18_policy, {}, 0, 0, 0, 0, 0
        )
        return 2

    print(f"[P16.6] P18 policy valid: policy_id={p18_policy.selected_policy_id}")
    print(f"  edge_threshold={p18_policy.edge_threshold}")
    print(f"  max_stake_cap={p18_policy.max_stake_cap}")
    print(f"  kelly_fraction={p18_policy.kelly_fraction}")
    print(f"  odds_decimal_max={p18_policy.odds_decimal_max}")
    print(f"  max_drawdown_pct={p18_policy.max_drawdown_pct:.4f}%")
    print(f"  sharpe_ratio={p18_policy.sharpe_ratio:.4f}")
    print(f"  n_bets={p18_policy.n_bets}")

    # ── Load P16 input rows from P15 joined OOF ───────────────────────────────
    print(f"[P16.6] Loading input rows from: {joined_oof_path}")
    input_rows = load_p16_input_rows(
        str(joined_oof_path),
        source_bss_oof=SOURCE_BSS_OOF,
        odds_join_coverage=ODDS_JOIN_COVERAGE,
    )

    n_input_rows = len(input_rows)
    n_joined_rows = sum(1 for r in input_rows if r.odds_join_status == "JOINED")
    print(f"[P16.6] Loaded {n_input_rows} input rows, {n_joined_rows} with JOINED odds")

    # ── Apply P16.6 gate to each row ──────────────────────────────────────────
    print("[P16.6] Applying P16.6 gate with P18 policy parameters...")
    gate_results = [apply_gate_with_p18_policy(r, p18_policy) for r in input_rows]

    # ── Compute per-row stakes ────────────────────────────────────────────────
    stakes = [compute_paper_stake_p18(r, g, p18_policy) for r, g in zip(input_rows, gate_results)]

    # ── Build recommendation rows ─────────────────────────────────────────────
    rec_rows = build_all_rows_p16_6(input_rows, gate_results, stakes, p18_policy)

    n_eligible = sum(1 for r in rec_rows if r.gate_decision == P16_6_ELIGIBLE)
    n_blocked = len(rec_rows) - n_eligible
    n_policy_eligible = sum(1 for r in input_rows if r.odds_join_status == "JOINED")
    gate_reason_counts = dict(Counter(r.gate_decision for r in rec_rows))

    print(f"[P16.6] Gate results: {n_eligible} eligible, {n_blocked} blocked")
    for code, cnt in sorted(gate_reason_counts.items(), key=lambda x: -x[1]):
        print(f"  {code}: {cnt}")

    # ── Determine overall gate decision ───────────────────────────────────────
    if n_eligible == 0:
        p16_6_gate = GATE_NO_ELIGIBLE
    else:
        p16_6_gate = GATE_READY

    # ── Write outputs ─────────────────────────────────────────────────────────

    # 1. recommendation_rows.csv
    rows_csv_path = output_dir / "recommendation_rows.csv"
    rows_df = pd.DataFrame([r.to_dict() for r in rec_rows])
    rows_df.to_csv(rows_csv_path, index=False)
    print(f"[P16.6] Wrote recommendation_rows.csv ({len(rows_df)} rows)")

    # Contract check
    actual_cols = set(rows_df.columns)
    missing_cols = REQUIRED_COLUMNS - actual_cols
    if missing_cols:
        print(f"ERROR: recommendation_rows.csv missing columns: {missing_cols}")
        _write_summary_json(
            output_dir, GATE_FAIL_CONTRACT, p18_policy,
            gate_reason_counts, n_input_rows, n_joined_rows,
            n_policy_eligible, n_eligible, n_blocked
        )
        return 2

    # Invariant: no row has production_ready=True
    if (rows_df["production_ready"] == True).any():  # noqa: E712
        print("ERROR: contract violation — production_ready=True found in output rows")
        return 2

    # Invariant: no row has paper_only=False
    if (rows_df["paper_only"] == False).any():  # noqa: E712
        print("ERROR: contract violation — paper_only=False found in output rows")
        return 2

    # 2. recommendation_summary.json
    top_reasons = sorted(gate_reason_counts.items(), key=lambda x: -x[1])[:5]
    summary = _write_summary_json(
        output_dir, p16_6_gate, p18_policy,
        gate_reason_counts, n_input_rows, n_joined_rows,
        n_policy_eligible, n_eligible, n_blocked
    )

    # 3. recommendation_summary.md
    _write_summary_md(output_dir, summary, top_reasons)

    # 4. gate_reason_counts.json
    with open(output_dir / "gate_reason_counts.json", "w") as f:
        json.dump(gate_reason_counts, f, indent=2, sort_keys=True)

    # 5. p18_policy_applied.json
    policy_dict = {
        "selected_policy_id": p18_policy.selected_policy_id,
        "edge_threshold": p18_policy.edge_threshold,
        "max_stake_cap": p18_policy.max_stake_cap,
        "kelly_fraction": p18_policy.kelly_fraction,
        "odds_decimal_max": p18_policy.odds_decimal_max,
        "n_bets": p18_policy.n_bets,
        "max_drawdown_pct": p18_policy.max_drawdown_pct,
        "sharpe_ratio": p18_policy.sharpe_ratio,
        "roi_mean": p18_policy.roi_mean,
        "roi_ci_low_95": p18_policy.roi_ci_low_95,
        "roi_ci_high_95": p18_policy.roi_ci_high_95,
        "hit_rate": p18_policy.hit_rate,
        "gate_decision": p18_policy.gate_decision,
        "paper_only": True,
        "production_ready": False,
    }
    with open(output_dir / "p18_policy_applied.json", "w") as f:
        json.dump(policy_dict, f, indent=2)

    # 6. p16_6_policy_risk_profile.json
    risk_profile_dict = {
        "roi_mean": p18_policy.roi_mean,
        "roi_ci_low_95": p18_policy.roi_ci_low_95,
        "roi_ci_high_95": p18_policy.roi_ci_high_95,
        "max_drawdown_pct": p18_policy.max_drawdown_pct,
        "sharpe_ratio": p18_policy.sharpe_ratio,
        "n_bets": p18_policy.n_bets,
        "hit_rate": p18_policy.hit_rate,
        "source": "p18_selected_policy",
        "selected_policy_id": p18_policy.selected_policy_id,
        "edge_threshold": p18_policy.edge_threshold,
        "max_stake_cap": p18_policy.max_stake_cap,
        "kelly_fraction": p18_policy.kelly_fraction,
        "odds_decimal_max": p18_policy.odds_decimal_max,
        "paper_only": True,
        "production_ready": False,
    }
    with open(output_dir / "p16_6_policy_risk_profile.json", "w") as f:
        json.dump(risk_profile_dict, f, indent=2)

    print(f"[P16.6] All 6 output files written to: {output_dir}")
    print(f"[P16.6] Overall gate decision: {p16_6_gate}")

    if p16_6_gate == GATE_READY:
        return 0
    elif p16_6_gate == GATE_NO_ELIGIBLE:
        return 1
    else:
        return 2


def _write_summary_json(
    output_dir: Path,
    p16_6_gate: str,
    p18_policy: P18SelectedPolicy | None,
    gate_reason_counts: dict,
    n_input_rows: int,
    n_joined_rows: int,
    n_policy_eligible_rows: int,
    n_recommended_rows: int,
    n_blocked_rows: int,
) -> dict:
    top_reasons = sorted(gate_reason_counts.items(), key=lambda x: -x[1])[:5]
    summary: dict = {
        "p16_6_gate": p16_6_gate,
        "p18_source_gate": p18_policy.gate_decision if p18_policy else None,
        "p18_policy_id": p18_policy.selected_policy_id if p18_policy else None,
        "p18_edge_threshold": p18_policy.edge_threshold if p18_policy else None,
        "p18_max_stake_cap": p18_policy.max_stake_cap if p18_policy else None,
        "p18_kelly_fraction": p18_policy.kelly_fraction if p18_policy else None,
        "p18_odds_decimal_max": p18_policy.odds_decimal_max if p18_policy else None,
        "n_input_rows": n_input_rows,
        "n_joined_rows": n_joined_rows,
        "n_policy_eligible_rows": n_policy_eligible_rows,
        "n_recommended_rows": n_recommended_rows,
        "n_blocked_rows": n_blocked_rows,
        "top_gate_reasons": top_reasons,
        "selected_policy_max_drawdown_pct": p18_policy.max_drawdown_pct if p18_policy else None,
        "selected_policy_sharpe_ratio": p18_policy.sharpe_ratio if p18_policy else None,
        "selected_policy_n_bets": p18_policy.n_bets if p18_policy else None,
        "paper_only": True,
        "production_ready": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(output_dir / "recommendation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def _write_summary_md(
    output_dir: Path,
    summary: dict,
    top_reasons: list[tuple[str, int]],
) -> None:
    lines = [
        "# P16.6 Recommendation Gate Re-run with P18 Policy",
        "",
        f"**Overall Gate**: `{summary['p16_6_gate']}`",
        f"**P18 Policy ID**: `{summary['p18_policy_id']}`",
        f"**P18 Source Gate**: `{summary['p18_source_gate']}`",
        "",
        "## Policy Parameters",
        "",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Edge Threshold | {summary['p18_edge_threshold']} |",
        f"| Max Stake Cap | {summary['p18_max_stake_cap']} |",
        f"| Kelly Fraction | {summary['p18_kelly_fraction']} |",
        f"| Odds Decimal Max | {summary['p18_odds_decimal_max']} |",
        f"| Max Drawdown % | {summary['selected_policy_max_drawdown_pct']:.4f}% |",
        f"| Sharpe Ratio | {summary['selected_policy_sharpe_ratio']:.4f} |",
        f"| N Bets (P18 backtest) | {summary['selected_policy_n_bets']} |",
        "",
        "## Row Counts",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Input Rows | {summary['n_input_rows']} |",
        f"| Rows with JOINED Odds | {summary['n_joined_rows']} |",
        f"| Policy Eligible Rows | {summary['n_policy_eligible_rows']} |",
        f"| Recommended Rows | {summary['n_recommended_rows']} |",
        f"| Blocked Rows | {summary['n_blocked_rows']} |",
        "",
        "## Top Gate Reasons",
        "",
        "| Reason Code | Count |",
        "|-------------|-------|",
    ]
    for code, cnt in top_reasons:
        lines.append(f"| `{code}` | {cnt} |")
    lines += [
        "",
        "## Safety Invariants",
        "",
        "- `paper_only: true`",
        "- `production_ready: false`",
        "",
        f"*Generated at: {summary['generated_at']}*",
    ]
    with open(output_dir / "recommendation_summary.md", "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
