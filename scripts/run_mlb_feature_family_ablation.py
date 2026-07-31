"""
scripts/run_mlb_feature_family_ablation.py

P12: Feature-family ablation study CLI.

For each ablation variant (16 total), this script:
  1. Builds variant rows by enabling/disabling feature families.
  2. Runs walk-forward OOF calibration.
  3. Runs strategy simulation.
  4. Collects BSS / ECE / ROI / gate status.
  5. Writes ablation_plan.json, ablation_results.json,
     ablation_leaderboard.csv, ablation_summary.md.

Usage:
    .venv/bin/python scripts/run_mlb_feature_family_ablation.py \\
        --input-csv outputs/predictions/PAPER/2026-05-11/mlb_odds_with_feature_candidate_probabilities.csv \\
        --output-dir outputs/predictions/PAPER/2026-05-11/ablation \\
        --date-start 2025-03-01 \\
        --date-end 2025-12-31 \\
        --edge-threshold 0.01 \\
        --kelly-cap 0.05 \\
        --run-oof \\
        --run-simulation

Security / paper guards:
  - Output dir must be under outputs/predictions/PAPER/.
  - paper_only = True always.
  - Never enables production mode.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wbc_backend.prediction.mlb_feature_family_ablation import (
    build_ablation_variant_rows,
    classify_feature_columns,
    generate_ablation_plan,
)
from wbc_backend.prediction.mlb_oof_calibration import (
    build_walk_forward_calibrated_rows,
    evaluate_oof_calibration,
)
from wbc_backend.simulation.strategy_simulator import simulate_strategy

_PAPER_ZONE = "outputs/predictions/PAPER"
_TODAY = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Guards
# ─────────────────────────────────────────────────────────────────────────────

def _refuse(reason: str) -> None:
    print(f"[REFUSED] {reason}", file=sys.stderr)
    sys.exit(2)


def _assert_paper_output_dir(path: Path) -> None:
    resolved = path.resolve()
    if _PAPER_ZONE not in resolved.as_posix():
        _refuse(
            f"Output dir must be under '{_PAPER_ZONE}'. Got: {resolved}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# § 2  I/O helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(obj: Any, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _filter_by_date(rows: list[dict], date_start: str, date_end: str) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        d = str(row.get("Date") or row.get("date") or "").strip()[:10]
        if d and date_start <= d <= date_end:
            out.append(row)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# § 3  OOF calibration runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_oof(
    rows: list[dict],
    *,
    min_train_size: int = 300,
    min_bin_size: int = 30,
    initial_train_months: int = 2,
    n_bins: int = 10,
) -> dict[str, Any]:
    """Run walk-forward OOF calibration and return evaluation metrics."""
    try:
        oof_rows, _fold_meta = build_walk_forward_calibrated_rows(
            rows,
            date_col="Date",
            model_prob_col="model_prob_home",
            n_bins=n_bins,
            min_train_size=min_train_size,
            min_bin_size=min_bin_size,
            initial_train_months=initial_train_months,
        )
        eval_result = evaluate_oof_calibration(rows, oof_rows)
        return {
            "oof_bss": eval_result.get("oof_bss"),
            "oof_ece": eval_result.get("oof_ece"),
            "original_bss": eval_result.get("original_bss"),
            "original_ece": eval_result.get("original_ece"),
            "delta_bss": eval_result.get("delta_bss"),
            "delta_ece": eval_result.get("delta_ece"),
            "oof_row_count": eval_result.get("oof_row_count"),
            "skipped_row_count": eval_result.get("skipped_row_count"),
            "recommendation": eval_result.get("recommendation"),
            "oof_rows": oof_rows,
            "oof_error": None,
        }
    except Exception as exc:
        return {
            "oof_bss": None,
            "oof_ece": None,
            "oof_error": str(exc),
            "oof_rows": [],
        }


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Simulation runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_sim(
    rows: list[dict],
    *,
    variant_name: str,
    date_start: str,
    date_end: str,
    edge_threshold: float,
    kelly_cap: float,
) -> dict[str, Any]:
    """Run strategy simulation and return key metrics."""
    try:
        strategy_name = f"p12_ablation_{variant_name[:40]}"
        result = simulate_strategy(
            strategy_name=strategy_name,
            rows=rows,
            date_start=date_start,
            date_end=date_end,
            edge_threshold=edge_threshold,
            kelly_cap=kelly_cap,
            require_positive_bss=True,
        )
        return {
            "gate_status": result.gate_status,
            "gate_reasons": result.gate_reasons,
            "roi_pct": result.roi_pct,
            "bet_count": result.bet_count,
            "sample_size": result.sample_size,
            "brier_model": result.brier_model,
            "brier_market": result.brier_market,
            "bss": result.brier_skill_score,
            "ece": result.ece,
            "sharpe_proxy": result.sharpe_proxy,
            "max_drawdown_pct": result.max_drawdown_pct,
            "avg_edge_pct": result.avg_edge_pct,
            "sim_error": None,
        }
    except Exception as exc:
        return {
            "gate_status": "ERROR",
            "roi_pct": None,
            "sim_error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Main ablation loop
# ─────────────────────────────────────────────────────────────────────────────

def run_ablation(
    input_rows: list[dict],
    output_dir: Path,
    *,
    date_start: str,
    date_end: str,
    edge_threshold: float,
    kelly_cap: float,
    run_oof: bool,
    run_simulation: bool,
) -> dict[str, Any]:
    """Execute the full ablation study and write all artifacts."""
    plan = generate_ablation_plan()
    all_columns = list(input_rows[0].keys()) if input_rows else []
    classification = classify_feature_columns(all_columns)

    print(f"\n[P12] Feature families classified: {classification['feature_count_by_family']}")
    print(f"[P12] Unknown columns: {len(classification['unknown_columns'])}")

    # Write ablation plan
    _write_json(plan, output_dir / "ablation_plan.json")
    print(f"[P12] Wrote ablation_plan.json ({len(plan)} variants)")

    results: list[dict] = []
    date_filtered = _filter_by_date(input_rows, date_start, date_end)
    print(f"[P12] Date-filtered rows: {len(date_filtered)} / {len(input_rows)}")

    for spec in plan:
        variant_name: str = spec["variant_name"]
        enabled_families: list[str] = spec["enabled_families"]
        description: str = spec["description"]

        print(f"\n[P12] Variant: {variant_name}")
        print(f"      Enabled: {enabled_families}")

        variant_result: dict[str, Any] = {
            "variant_name": variant_name,
            "enabled_families": enabled_families,
            "description": description,
            "input_rows": len(date_filtered),
            "paper_only": True,
        }

        # Build variant rows
        try:
            variant_rows, build_meta = build_ablation_variant_rows(
                date_filtered,
                enabled_families=enabled_families,
                variant_name=variant_name,
            )
            variant_result["build_meta"] = build_meta
            variant_result["variant_rows_count"] = len(variant_rows)

            # Write variant CSV
            variant_csv_path = output_dir / f"variant_{variant_name}.csv"
            _write_csv(variant_rows, variant_csv_path)
            variant_result["variant_csv"] = str(variant_csv_path)
            print(f"      Rows: {len(variant_rows)} → {variant_csv_path.name}")
        except Exception as exc:
            variant_result["build_error"] = str(exc)
            variant_result["gate_status"] = "ERROR"
            results.append(variant_result)
            print(f"      BUILD ERROR: {exc}")
            continue

        # OOF calibration
        if run_oof and variant_rows:
            oof_result = _run_oof(variant_rows)
            variant_result.update({
                "oof_bss": oof_result.get("oof_bss"),
                "oof_ece": oof_result.get("oof_ece"),
                "original_bss": oof_result.get("original_bss"),
                "delta_bss": oof_result.get("delta_bss"),
                "oof_row_count": oof_result.get("oof_row_count"),
                "oof_recommendation": oof_result.get("recommendation"),
                "oof_error": oof_result.get("oof_error"),
            })
            # Use OOF rows for simulation if available
            sim_rows = oof_result.get("oof_rows") or variant_rows
            if oof_result.get("oof_error"):
                print(f"      OOF ERROR: {oof_result['oof_error']}")
            else:
                bss_v = oof_result.get("oof_bss")
                ece_v = oof_result.get("oof_ece")
                bss_s = f"{bss_v:.6f}" if bss_v is not None else "N/A"
                ece_s = f"{ece_v:.6f}" if ece_v is not None else "N/A"
                print(f"      OOF BSS: {bss_s}  ECE: {ece_s}")
        else:
            sim_rows = variant_rows

        # Simulation
        if run_simulation and sim_rows:
            sim_result = _run_sim(
                sim_rows,
                variant_name=variant_name,
                date_start=date_start,
                date_end=date_end,
                edge_threshold=edge_threshold,
                kelly_cap=kelly_cap,
            )
            variant_result.update({
                "gate_status": sim_result.get("gate_status"),
                "gate_reasons": sim_result.get("gate_reasons"),
                "roi_pct": sim_result.get("roi_pct"),
                "bet_count": sim_result.get("bet_count"),
                "sample_size": sim_result.get("sample_size"),
                "bss_sim": sim_result.get("bss"),
                "ece_sim": sim_result.get("ece"),
                "sim_error": sim_result.get("sim_error"),
            })
            if sim_result.get("sim_error"):
                print(f"      SIM ERROR: {sim_result['sim_error']}")
            else:
                print(f"      Gate: {sim_result.get('gate_status')}  ROI: {sim_result.get('roi_pct')}%")
        elif not run_simulation:
            variant_result["gate_status"] = "SIMULATION_SKIPPED"

        results.append(variant_result)

    # Build leaderboard (sort by oof_bss descending)
    def _sort_key(r: dict) -> float:
        v = r.get("oof_bss")
        return float(v) if v is not None else -999.0

    leaderboard = sorted(results, key=_sort_key, reverse=True)

    # Write results JSON
    _write_json(results, output_dir / "ablation_results.json")

    # Write leaderboard CSV
    lb_fields = [
        "variant_name", "enabled_families", "oof_bss", "oof_ece",
        "roi_pct", "gate_status", "bet_count", "sample_size",
        "oof_recommendation", "oof_error", "sim_error",
    ]
    lb_path = output_dir / "ablation_leaderboard.csv"
    with lb_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=lb_fields, extrasaction="ignore")
        writer.writeheader()
        for row in leaderboard:
            flat = dict(row)
            flat["enabled_families"] = json.dumps(row.get("enabled_families", []))
            writer.writerow(flat)

    # Determine best/worst
    scored = [r for r in leaderboard if r.get("oof_bss") is not None]
    best = scored[0] if scored else None
    worst = scored[-1] if scored else None

    # Write summary markdown
    summary_path = output_dir / "ablation_summary.md"
    _write_ablation_summary(
        summary_path,
        leaderboard=leaderboard,
        classification=classification,
        best=best,
        worst=worst,
        date_start=date_start,
        date_end=date_end,
        input_csv_rows=len(input_rows),
        date_filtered_rows=len(date_filtered),
    )

    return {
        "plan_count": len(plan),
        "results": results,
        "leaderboard": leaderboard,
        "best_variant": best,
        "worst_variant": worst,
        "column_classification": classification,
    }


# ─────────────────────────────────────────────────────────────────────────────
# § 6  Summary markdown writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_ablation_summary(
    path: Path,
    *,
    leaderboard: list[dict],
    classification: dict,
    best: dict | None,
    worst: dict | None,
    date_start: str,
    date_end: str,
    input_csv_rows: int,
    date_filtered_rows: int,
) -> None:
    lines: list[str] = [
        "# P12 Feature-Family Ablation Summary",
        "",
        f"Generated: {datetime.now(tz=timezone.utc).isoformat()}",
        f"Date range: {date_start} → {date_end}",
        f"Input rows (total / date-filtered): {input_csv_rows} / {date_filtered_rows}",
        "",
        "## Feature Family Classification",
        "",
        "| Family | Columns Present |",
        "|--------|----------------|",
    ]
    for fam, count in classification.get("feature_count_by_family", {}).items():
        lines.append(f"| {fam} | {count} |")

    unknown = classification.get("unknown_columns", [])
    lines += [
        "",
        f"Unknown columns (not in any family): {len(unknown)}",
        "",
        "## Ablation Leaderboard",
        "",
        "| Rank | Variant | Enabled Families | OOF BSS | OOF ECE | ROI% | Gate |",
        "|------|---------|-----------------|---------|---------|------|------|",
    ]
    for i, r in enumerate(leaderboard, 1):
        bss_str = f"{r['oof_bss']:.6f}" if r.get("oof_bss") is not None else "N/A"
        ece_str = f"{r['oof_ece']:.6f}" if r.get("oof_ece") is not None else "N/A"
        roi_str = f"{r['roi_pct']:.2f}" if r.get("roi_pct") is not None else "N/A"
        gate = r.get("gate_status", "N/A")
        fams = ", ".join(r.get("enabled_families", []))
        lines.append(f"| {i} | {r['variant_name']} | {fams} | {bss_str} | {ece_str} | {roi_str} | {gate} |")

    lines += [""]

    if best:
        lines += [
            "## Best Variant",
            "",
            f"**{best['variant_name']}** — {best.get('description', '')}",
            f"- OOF BSS: {best.get('oof_bss')}",
            f"- OOF ECE: {best.get('oof_ece')}",
            f"- Gate: {best.get('gate_status')}",
            f"- Enabled: {best.get('enabled_families')}",
            "",
        ]

    if worst:
        lines += [
            "## Worst Variant",
            "",
            f"**{worst['variant_name']}** — {worst.get('description', '')}",
            f"- OOF BSS: {worst.get('oof_bss')}",
            f"- OOF ECE: {worst.get('oof_ece')}",
            f"- Gate: {worst.get('gate_status')}",
            "",
        ]

    lines += [
        "## P12 Conclusion",
        "",
        "This ablation study identifies which feature families help or hurt model quality.",
        "See ablation_results.json for full per-variant details.",
        "",
        "paper_only: true",
        "production_enablement_attempted: false",
        "real_bets_placed: false",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# § 7  CLI entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P12 feature-family ablation study")
    parser.add_argument(
        "--input-csv",
        default=f"outputs/predictions/PAPER/2026-05-11/mlb_odds_with_feature_candidate_probabilities.csv",
        help="P11 feature candidate CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=f"outputs/predictions/PAPER/{_TODAY}/ablation",
        help="Output directory (must be under outputs/predictions/PAPER/)",
    )
    parser.add_argument("--date-start", default="2025-03-01")
    parser.add_argument("--date-end", default="2025-12-31")
    parser.add_argument("--edge-threshold", type=float, default=0.01)
    parser.add_argument("--kelly-cap", type=float, default=0.05)
    parser.add_argument("--run-oof", action="store_true", default=False)
    parser.add_argument("--run-simulation", action="store_true", default=False)
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_dir = Path(args.output_dir)

    # Guards
    if not input_path.exists():
        _refuse(f"Input CSV not found: {input_path}")
    _assert_paper_output_dir(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[P12] Input CSV: {input_path} ({input_path.stat().st_size:,} bytes)")
    print(f"[P12] Output dir: {output_dir}")
    print(f"[P12] Date range: {args.date_start} → {args.date_end}")
    print(f"[P12] Edge threshold: {args.edge_threshold}  Kelly cap: {args.kelly_cap}")
    print(f"[P12] Run OOF: {args.run_oof}  Run simulation: {args.run_simulation}")

    # Load input
    rows = _load_csv(input_path)
    print(f"[P12] Loaded {len(rows)} rows from {input_path.name}")

    # Run ablation
    summary = run_ablation(
        rows,
        output_dir,
        date_start=args.date_start,
        date_end=args.date_end,
        edge_threshold=args.edge_threshold,
        kelly_cap=args.kelly_cap,
        run_oof=args.run_oof,
        run_simulation=args.run_simulation,
    )

    # Print leaderboard
    print("\n" + "=" * 80)
    print("P12 ABLATION LEADERBOARD")
    print("=" * 80)
    print(f"{'Rank':<5} {'Variant':<35} {'OOF BSS':>10} {'OOF ECE':>10} {'ROI%':>8} {'Gate':<30}")
    print("-" * 100)
    for i, r in enumerate(summary["leaderboard"], 1):
        bss_str = f"{r['oof_bss']:.6f}" if r.get("oof_bss") is not None else "N/A"
        ece_str = f"{r['oof_ece']:.6f}" if r.get("oof_ece") is not None else "N/A"
        roi_str = f"{r['roi_pct']:.2f}" if r.get("roi_pct") is not None else "N/A"
        gate = r.get("gate_status", "N/A")
        print(f"{i:<5} {r['variant_name']:<35} {bss_str:>10} {ece_str:>10} {roi_str:>8} {gate:<30}")

    best = summary["best_variant"]
    worst = summary["worst_variant"]
    if best:
        print(f"\n[P12] BEST variant:  {best['variant_name']} (OOF BSS={best.get('oof_bss')})")
    if worst:
        print(f"[P12] WORST variant: {worst['variant_name']} (OOF BSS={worst.get('oof_bss')})")

    print(f"\n[P12] Artifacts written to: {output_dir}")
    print("[P12] paper_only=True | production_enabled=False | real_bets=False")
    print("\nP12_FEATURE_FAMILY_ABLATION_CONTEXT_SAFETY_READY\n")


if __name__ == "__main__":
    main()
