#!/usr/bin/env python3
"""P15 CLI — Historical Market Odds Join Simulation.

Joins P13 OOF predictions with historical market odds (from the P13 source
training CSV), then runs the full strategy simulation spine.

Usage
-----
python scripts/run_p15_market_odds_join_simulation.py \\
    --p13-oof-dir  outputs/predictions/PAPER/2026-05-12/p13_walk_forward_logistic \\
    --source-csv   /path/to/variant_no_rest.csv \\
    --output-dir   outputs/predictions/PAPER/2026-05-12/p15_market_odds_simulation \\
    --paper-only

Outputs (all inside --output-dir):
    joined_oof_with_odds.csv   – OOF rows enriched with game ids + odds
    simulation_summary.json    – spine gate, per-policy metrics, odds coverage
    simulation_summary.md      – human-readable report
    simulation_ledger.csv      – row-level bet decisions (all policies)
    odds_join_report.json      – coverage stats from MarketOddsJoinAdapter

Gate markers written to simulation_summary.json under "p15_gate":
    P15_ODDS_AWARE_SIMULATION_READY    – coverage >= 50%
    P15_BLOCKED_NO_HISTORICAL_ODDS_SOURCE  – --source-csv not supplied or file missing
    P15_BLOCKED_LOW_JOIN_COVERAGE          – coverage < 50%
    P15_FAIL_INVALID_ODDS_SOURCE           – source file exists but invalid
    P15_FAIL_NON_DETERMINISTIC             – two identical runs differ (detected externally)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────
P15_GATE_READY = "P15_ODDS_AWARE_SIMULATION_READY"
P15_GATE_NO_SOURCE = "P15_BLOCKED_NO_HISTORICAL_ODDS_SOURCE"
P15_GATE_LOW_COVERAGE = "P15_BLOCKED_LOW_JOIN_COVERAGE"
P15_GATE_INVALID_SOURCE = "P15_FAIL_INVALID_ODDS_SOURCE"

SOURCE_BSS_OOF_P13 = 0.008253  # from P13 OOF report

_PAPER_ONLY_OUTPUT_PREFIX = "outputs/predictions/PAPER"
_ALLOWED_OUTPUT_PREFIXES = (
    "outputs/predictions/PAPER",
    "/tmp/",
    "/var/folders/",
    "/private/var/folders/",
)


def _validate_output_zone(output_dir: Path) -> None:
    """Refuse writes outside the PAPER prediction zone."""
    s = str(output_dir)
    if not any(s.startswith(p) or str(output_dir.resolve()).startswith(p)
               for p in _ALLOWED_OUTPUT_PREFIXES):
        # Also allow relative paths under outputs/predictions/PAPER
        rel = str(output_dir)
        if not rel.startswith(_PAPER_ONLY_OUTPUT_PREFIX):
            print(
                f"[P15 GUARD] output_dir '{output_dir}' is outside the PAPER zone. "
                f"Only paths under '{_PAPER_ONLY_OUTPUT_PREFIX}' are permitted.\n"
                f"P15 gate: {P15_GATE_INVALID_SOURCE}",
                file=sys.stderr,
            )
            sys.exit(1)


def _load_oof(p13_oof_dir: Path) -> tuple[pd.DataFrame, float]:
    """Load OOF predictions CSV and extract BSS from summary JSON if available."""
    oof_csv = p13_oof_dir / "oof_predictions.csv"
    if not oof_csv.exists():
        print(
            f"[P15 FATAL] OOF CSV not found: {oof_csv}",
            file=sys.stderr,
        )
        sys.exit(1)

    df = pd.read_csv(oof_csv)
    bss = SOURCE_BSS_OOF_P13

    summary_json = p13_oof_dir / "p13_summary.json"
    if summary_json.exists():
        try:
            with open(summary_json) as fh:
                data = json.load(fh)
            bss = float(data.get("bss_oof", bss))
        except Exception:
            pass  # fallback to hardcoded

    return df, bss


def _write_markdown(output_dir: Path, summary_dict: dict, join_report: dict,
                    p15_gate: str) -> None:
    coverage = join_report.get("coverage_pct", 0.0)
    joined = join_report.get("joined", 0)
    total = join_report.get("n_oof_rows", 0)

    lines = [
        "# P15 Market Odds Join Simulation Report",
        "",
        f"**Generated**: {datetime.now(tz=timezone.utc).isoformat()}",
        f"**P15 Gate**: `{p15_gate}`",
        f"**P14/P13 Spine Gate**: `{summary_dict.get('spine_gate', 'N/A')}`",
        "",
        "## Odds Join Coverage",
        f"- Source CSV: `{join_report.get('source_path', 'N/A')}`",
        f"- Total OOF rows: {total}",
        f"- Joined rows: {joined}",
        f"- Missing rows: {join_report.get('missing', 0)}",
        f"- Invalid odds rows: {join_report.get('invalid_odds', 0)}",
        f"- Coverage: **{coverage:.1f}%**",
        "",
        "## Market Odds Available",
        f"- `market_odds_available`: {summary_dict.get('market_odds_available')}",
        "",
        "## Per-Policy Results",
        "",
    ]

    for policy, res in summary_dict.get("per_policy", {}).items():
        lines.extend([
            f"### {policy}",
            f"- Gate: `{res.get('gate_status')}`",
            f"- Bets: {res.get('bet_count')} / {res.get('sample_size')}",
            f"- Avg model prob: {res.get('avg_model_prob')}",
            f"- BSS: {res.get('brier_skill_score')}",
            f"- ROI: {res.get('roi_pct')}",
            f"- Avg edge: {res.get('avg_edge_pct')}",
            f"- Avg Kelly fraction: {res.get('avg_kelly_fraction')}",
            "",
        ])

    lines.extend([
        "## Notes",
        f"- `paper_only=True` enforced throughout.",
        f"- `production_ready=False`.",
        "",
        "---",
        "",
        f"<!-- marker: P15_MARKET_ODDS_JOIN_SIMULATION_READY -->",
    ])

    md_path = output_dir / "simulation_summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P15 market-odds join simulation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--p13-oof-dir",
        required=True,
        help="Directory containing oof_predictions.csv (P13 output).",
    )
    parser.add_argument(
        "--source-csv",
        default=None,
        help="Path to the source training CSV with Away ML / Home ML columns.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory (must be under outputs/predictions/PAPER/).",
    )
    parser.add_argument(
        "--paper-only",
        action="store_true",
        default=True,
        help="Enforce paper_only=True (always on).",
    )

    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    _validate_output_zone(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    p13_oof_dir = Path(args.p13_oof_dir)
    oof_df, source_bss_oof = _load_oof(p13_oof_dir)

    # ── Gate: no source CSV supplied? ─────────────────────────────────────────
    if not args.source_csv:
        blocker = {
            "p15_gate": P15_GATE_NO_SOURCE,
            "reason": "--source-csv not provided. P15 cannot join market odds.",
            "paper_only": True,
            "production_ready": False,
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        (output_dir / "simulation_summary.json").write_text(
            json.dumps(blocker, indent=2), encoding="utf-8"
        )
        print(f"[P15] BLOCKED — no source CSV supplied.")
        print(f"[P15] Gate: {P15_GATE_NO_SOURCE}")
        return 0

    source_csv_path = Path(args.source_csv)
    if not source_csv_path.exists():
        blocker = {
            "p15_gate": P15_GATE_NO_SOURCE,
            "reason": f"--source-csv file not found: {source_csv_path}",
            "paper_only": True,
            "production_ready": False,
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        (output_dir / "simulation_summary.json").write_text(
            json.dumps(blocker, indent=2), encoding="utf-8"
        )
        print(f"[P15] BLOCKED — source CSV not found: {source_csv_path}")
        print(f"[P15] Gate: {P15_GATE_NO_SOURCE}")
        return 0

    # ── Join market odds ───────────────────────────────────────────────────────
    try:
        from wbc_backend.simulation.market_odds_adapter import MarketOddsJoinAdapter
    except ImportError as exc:
        print(f"[P15 FATAL] Cannot import MarketOddsJoinAdapter: {exc}", file=sys.stderr)
        return 1

    try:
        adapter = MarketOddsJoinAdapter(source_csv_path=str(source_csv_path))
        joined_df = adapter.join_with_p13_oof(oof_df)
        join_report = adapter.join_report()
    except Exception as exc:
        blocker = {
            "p15_gate": P15_GATE_INVALID_SOURCE,
            "reason": str(exc),
            "paper_only": True,
            "production_ready": False,
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        (output_dir / "simulation_summary.json").write_text(
            json.dumps(blocker, indent=2), encoding="utf-8"
        )
        print(f"[P15] FAIL — odds join error: {exc}")
        print(f"[P15] Gate: {P15_GATE_INVALID_SOURCE}")
        return 0

    coverage_pct = join_report.get("coverage_pct", 0.0)
    joined_rows = join_report.get("joined", 0)
    missing_rows = join_report.get("missing", 0)

    # Write joined OOF CSV
    joined_csv_path = output_dir / "joined_oof_with_odds.csv"
    joined_df.to_csv(joined_csv_path, index=False)
    print(f"[P15] Joined OOF written: {joined_csv_path} ({len(joined_df)} rows)")
    print(f"[P15] Odds coverage: {coverage_pct:.1f}% ({joined_rows}/{join_report['n_oof_rows']})")

    # Write join report
    join_report_path = output_dir / "odds_join_report.json"
    join_report_path.write_text(json.dumps(join_report, indent=2), encoding="utf-8")

    # ── Gate: low coverage? ────────────────────────────────────────────────────
    if coverage_pct < 50.0:
        blocker = {
            "p15_gate": P15_GATE_LOW_COVERAGE,
            "reason": f"Odds join coverage {coverage_pct:.1f}% < 50% threshold.",
            "coverage_pct": coverage_pct,
            "joined_rows": joined_rows,
            "total_rows": join_report["n_oof_rows"],
            "paper_only": True,
            "production_ready": False,
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        (output_dir / "simulation_summary.json").write_text(
            json.dumps(blocker, indent=2), encoding="utf-8"
        )
        print(f"[P15] BLOCKED — low coverage {coverage_pct:.1f}%")
        print(f"[P15] Gate: {P15_GATE_LOW_COVERAGE}")
        return 0

    # ── Run simulation ─────────────────────────────────────────────────────────
    try:
        from wbc_backend.simulation.p13_strategy_simulator import (
            P13StrategySimulationRunner,
        )
    except ImportError as exc:
        print(f"[P15 FATAL] Cannot import P13StrategySimulationRunner: {exc}", file=sys.stderr)
        return 1

    runner = P13StrategySimulationRunner.from_joined_df(
        joined_df=joined_df,
        source_bss_oof=source_bss_oof,
        odds_join_coverage=joined_rows,
        odds_joined_rows=joined_rows,
        odds_missing_rows=missing_rows,
        odds_source_path=str(source_csv_path),
    )

    summary = runner.run(policies=["flat", "capped_kelly", "confidence_rank", "no_bet"])
    summary_dict = summary.to_summary_dict()

    p15_gate = P15_GATE_READY
    summary_dict["p15_gate"] = p15_gate
    summary_dict["generated_at_utc"] = datetime.now(tz=timezone.utc).isoformat()

    # Write JSON summary
    json_path = output_dir / "simulation_summary.json"
    json_path.write_text(json.dumps(summary_dict, indent=2), encoding="utf-8")

    # Write markdown report
    _write_markdown(output_dir, summary_dict, join_report, p15_gate)

    # Write ledger CSV
    ledger_rows = summary.ledger_rows()
    if ledger_rows:
        ledger_df = pd.DataFrame(ledger_rows)
        ledger_path = output_dir / "simulation_ledger.csv"
        ledger_df.to_csv(ledger_path, index=False)

    print(f"[P15] Spine gate: {summary_dict.get('spine_gate')}")
    print(f"[P15] P15 gate:   {p15_gate}")
    print(f"[P15] Outputs:    {output_dir}")
    print(f"[P15] Gate: {p15_gate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
