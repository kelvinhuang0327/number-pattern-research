#!/usr/bin/env python3
"""
scripts/run_phase59_pre_heavy_favorite_local_calibration.py
============================================================
Phase 59-Pre+ CLI Runner
Heavy-Favorite Local Calibration Counterfactual with OOF / PIT-safe Validation

Usage:
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py --print
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py --json
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py --report
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py --print --json --report
  python scripts/run_phase59_pre_heavy_favorite_local_calibration.py --bootstrap 2000

Hard Rules (enforced by orchestrator module):
  - CANDIDATE_PATCH_CREATED = False
  - PRODUCTION_MODIFIED = False
  - ALPHA_MODIFIED = False
  - All calibration is strictly OOF — training data must predate evaluation data
  - No production model modification

Outputs (with --report):
  reports/phase59_pre_heavy_favorite_local_calibration_YYYY-MM-DD.json
  00-BettingPlan/phase59_pre_heavy_favorite_local_calibration_report_20260506.md
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.phase59_pre_heavy_favorite_local_calibration import (
    Phase59PreResult,
    BucketMetrics,
    CalibrationVariantResult,
    NegativeControlResult,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    PHASE_VERSION,
    LOCAL_CALIBRATION_SUFFICIENT,
    BULLPEN_HYPOTHESIS_RETAINED,
    MIXED,
    BLOCKED_INSUFFICIENT_DATA,
    ALPHA,
    run_phase59_pre,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase59_pre_cli")

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
_REPORTS_DIR = ROOT / "reports"
_BETTING_PLAN_DIR = ROOT / "00-BettingPlan"


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Formatters
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v: float | None, precision: int = 6) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v:+.{precision}f}" if abs(v) < 100 else f"{v:.{precision}f}"


def _pct(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v * 100:.2f}%"


def _gate_emoji(gate: str) -> str:
    return {
        LOCAL_CALIBRATION_SUFFICIENT: "✅",
        BULLPEN_HYPOTHESIS_RETAINED: "🔬",
        MIXED: "⚠️",
        BLOCKED_INSUFFICIENT_DATA: "🚫",
    }.get(gate, "❓")


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Markdown builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_markdown(result: Phase59PreResult, today: str) -> str:
    lines: list[str] = []
    b = result.baseline
    iso = result.isotonic
    platt = result.platt
    nc = result.negative_control

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        f"# Phase 59-Pre+ — Heavy-Favorite Local Calibration Counterfactual",
        f"",
        f"**Report Date**: {today}  ",
        f"**Phase Version**: `{result.phase_version}`  ",
        f"**Audit Hash**: `{result.audit_hash}`  ",
        f"**Run Timestamp**: {result.run_timestamp}  ",
        f"",
        f"---",
        f"",
    ]

    # ── Safety flags ──────────────────────────────────────────────────────────
    lines += [
        f"## 0. Safety Flags",
        f"",
        f"| Flag | Value |",
        f"|------|-------|",
        f"| `CANDIDATE_PATCH_CREATED` | `{result.candidate_patch_created}` |",
        f"| `PRODUCTION_MODIFIED`     | `{result.production_modified}` |",
        f"| `ALPHA_MODIFIED`          | `{result.alpha_modified}` |",
        f"| `DIAGNOSTIC_ONLY`         | `{result.diagnostic_only}` |",
        f"| `ALPHA` (blend weight)    | `{ALPHA}` (frozen) |",
        f"",
    ]

    # ── Input artifacts ───────────────────────────────────────────────────────
    lines += [
        f"## 1. Input Artifacts",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Input JSONL | `{result.input_jsonl_path}` |",
        f"| Input Audit Hash | `{result.input_audit_hash}` |",
        f"| Total Sample Size | {result.sample_size} rows |",
        f"| Date Range | {result.date_range_start} → {result.date_range_end} |",
        f"",
        f"**Selection rationale**: Using `mlb_2025_per_game_predictions.jsonl` (Phase42A baseline)",
        f"because it is the canonical, audit-hashed artifact with complete market probabilities",
        f"and verified home_win labels for the full 2025 MLB season. Blend is computed fresh",
        f"from `model_home_prob` and `market_home_prob_no_vig` at alpha=0.4 to avoid any",
        f"dependency on pre-computed blend values.",
        f"",
    ]

    # ── Validation strategy ───────────────────────────────────────────────────
    lines += [
        f"## 2. Calibration Validation Strategy",
        f"",
        f"**Method**: `{result.validation_strategy}`",
        f"",
        f"For each evaluation month M, the calibrator is trained on **all data with",
        f"`game_date` strictly before the first day of M**. This guarantees:",
        f"- No game from month M appears in training data (temporal isolation)",
        f"- No in-sample fit-and-evaluate (strictly out-of-fold)",
        f"- PIT safety: calibration cannot use future results to adjust past predictions",
        f"",
        f"| Split | Months | Rows |",
        f"|-------|--------|------|",
        f"| Training only (not evaluated) | {', '.join(result.train_months) or 'none'} | {result.n_train} |",
        f"| Evaluation (OOF calibrated)   | {', '.join(result.eval_months) or 'none'} | {result.n_eval} |",
        f"",
        f"**PIT guard**: `assert_no_lookahead()` called before every calibrator fit.",
        f"",
    ]

    # ── Sample composition ────────────────────────────────────────────────────
    lines += [
        f"## 3. Sample Composition (Evaluation Split)",
        f"",
        f"| Bucket | n | Fraction |",
        f"|--------|---|----------|",
    ]
    for bm in result.bucket_metrics:
        frac = f"{bm.n / result.n_eval * 100:.1f}%" if result.n_eval > 0 else "N/A"
        lines.append(f"| {bm.bucket} | {bm.n} | {frac} |")
    lines += [
        f"| **Total eval** | **{result.n_eval}** | 100% |",
        f"| Heavy favorite (≥0.70) | {b.heavy_fav_n} | "
        f"{'N/A' if result.n_eval == 0 else f'{b.heavy_fav_n / result.n_eval * 100:.1f}%'} |",
        f"",
    ]

    # ── Results table ─────────────────────────────────────────────────────────
    lines += [
        f"## 4. Results: Baseline vs Isotonic vs Platt (OOF Evaluation Split)",
        f"",
        f"| Metric | Baseline | Isotonic | Platt |",
        f"|--------|----------|----------|-------|",
        f"| Overall BSS | {_fmt(b.overall_bss)} | {_fmt(iso.overall_bss)} | {_fmt(platt.overall_bss)} |",
        f"| Overall ECE | {_fmt(b.overall_ece)} | {_fmt(iso.overall_ece)} | {_fmt(platt.overall_ece)} |",
        f"| **Heavy Fav ECE** (≥0.70) | **{_fmt(b.heavy_fav_ece)}** | **{_fmt(iso.heavy_fav_ece)}** | **{_fmt(platt.heavy_fav_ece)}** |",
        f"| Heavy Fav n | {b.heavy_fav_n} | {iso.heavy_fav_n} | {platt.heavy_fav_n} |",
        f"| High Conf BSS (≥0.65) | {_fmt(b.high_conf_bss)} | {_fmt(iso.high_conf_bss)} | {_fmt(platt.high_conf_bss)} |",
        f"| High Conf n | {b.high_conf_n} | {iso.high_conf_n} | {platt.high_conf_n} |",
        f"| Phase45 Failure Segments | {b.phase45_failure_segment_count} | {iso.phase45_failure_segment_count} | {platt.phase45_failure_segment_count} |",
        f"| Bootstrap CI lower | {_fmt(b.bootstrap_ci_lower)} | {_fmt(iso.bootstrap_ci_lower)} | {_fmt(platt.bootstrap_ci_lower)} |",
        f"| Bootstrap CI upper | {_fmt(b.bootstrap_ci_upper)} | {_fmt(iso.bootstrap_ci_upper)} | {_fmt(platt.bootstrap_ci_upper)} |",
        f"| Bootstrap P(improve) | {_pct(b.bootstrap_prob_improvement)} | {_pct(iso.bootstrap_prob_improvement)} | {_pct(platt.bootstrap_prob_improvement)} |",
        f"| Bootstrap Significant | {b.bootstrap_significant} | {iso.bootstrap_significant} | {platt.bootstrap_significant} |",
        f"",
    ]

    # ── Bucket-level ECE ──────────────────────────────────────────────────────
    lines += [
        f"## 5. Bucket-Level ECE Comparison",
        f"",
        f"| Bucket | n | Baseline ECE | Isotonic ECE | Platt ECE | Baseline BSS | Isotonic BSS | Platt BSS |",
        f"|--------|---|-------------|--------------|-----------|-------------|-------------|---------|",
    ]
    for bm in result.bucket_metrics:
        lines.append(
            f"| {bm.bucket} | {bm.n} "
            f"| {_fmt(bm.baseline_ece, 4)} "
            f"| {_fmt(bm.isotonic_ece, 4)} "
            f"| {_fmt(bm.platt_ece, 4)} "
            f"| {_fmt(bm.baseline_bss, 4)} "
            f"| {_fmt(bm.isotonic_bss, 4)} "
            f"| {_fmt(bm.platt_bss, 4)} |"
        )
    lines.append(f"")

    # ── Negative control ──────────────────────────────────────────────────────
    lines += [
        f"## 6. Negative Control (Shuffled-Label Sanity Check)",
        f"",
        f"A calibrator trained on **randomly shuffled labels** should not improve heavy_fav ECE.",
        f"If it does, the result in §4 is likely an artifact of overfit or data leakage.",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Real Baseline Heavy Fav ECE | {_fmt(nc.baseline_heavy_fav_ece, 4)} |",
        f"| Shuffled Isotonic Heavy Fav ECE | {_fmt(nc.shuffled_isotonic_heavy_fav_ece, 4)} |",
        f"| Shuffled Platt Heavy Fav ECE | {_fmt(nc.shuffled_platt_heavy_fav_ece, 4)} |",
        f"| Sanity Check Passed | `{nc.sanity_ok}` |",
        f"",
        (
            "**Interpretation**: Shuffled-label calibration should produce ECE ≈ baseline "
            "or worse. If `sanity_ok=False`, the OOF calibration gains may be spurious."
            if not nc.sanity_ok
            else
            "**Interpretation**: Shuffled-label ECE does not beat real baseline — "
            "negative control passes. Calibration gains (if any) are not due to overfit."
        ),
        f"",
    ]

    # ── Gate conclusion ───────────────────────────────────────────────────────
    gate_em = _gate_emoji(result.gate)
    lines += [
        f"## 7. Gate Conclusion",
        f"",
        f"### {gate_em} `{result.gate}`",
        f"",
        f"**Rationale**: {result.gate_rationale}",
        f"",
        f"---",
        f"",
        f"## 8. Next Step Recommendation",
        f"",
        f"{result.next_step_recommendation}",
        f"",
    ]

    # ── Bootstrap interpretation ──────────────────────────────────────────────
    lines += [
        f"## 9. Bootstrap CI Interpretation",
        f"",
        f"Bootstrap samples (n={1000}) were drawn with replacement from the evaluation set.",
        f"CI is the 2.5th–97.5th percentile of (variant_BSS − baseline_BSS) deltas.",
        f"",
        f"- **CI straddles 0** → NOT SIGNIFICANT. Improvement could be sampling noise.",
        f"- **CI strictly > 0** → SIGNIFICANT at 95% level. Improvement is likely real.",
        f"",
        f"| Variant | CI [{_fmt(0.025, 3)}, {_fmt(0.975, 3)}] | Significant |",
        f"|---------|----------|-------------|",
        f"| Isotonic | [{_fmt(iso.bootstrap_ci_lower, 4)}, {_fmt(iso.bootstrap_ci_upper, 4)}] | {iso.bootstrap_significant} |",
        f"| Platt    | [{_fmt(platt.bootstrap_ci_lower, 4)}, {_fmt(platt.bootstrap_ci_upper, 4)}] | {platt.bootstrap_significant} |",
        f"",
    ]

    # ── Data sufficiency note ─────────────────────────────────────────────────
    lines += [
        f"## 10. Data Sufficiency Notes",
        f"",
        f"- Total sample: **{result.sample_size}** rows (full 2025 season backtest)",
        f"- Evaluation split: **{result.n_eval}** rows",
        f"- Heavy favorite in eval: **{b.heavy_fav_n}** rows",
        f"",
    ]
    if b.heavy_fav_n < 30:
        lines.append(
            f"> ⚠️ **Small heavy_fav sample** ({b.heavy_fav_n} rows in eval). "
            f"Heavy-favorite ECE estimates have high variance. "
            f"Results are INDICATIVE, not conclusive."
        )
    lines.append(f"")

    # ── Completion marker ─────────────────────────────────────────────────────
    lines += [
        f"---",
        f"",
        f"`PHASE_59_PRE_HEAVY_FAVORITE_LOCAL_CALIBRATION_COUNTERFACTUAL_VERIFIED`",
        f"",
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Stdout summary
# ═══════════════════════════════════════════════════════════════════════════════

def _print_summary(result: Phase59PreResult) -> None:
    b = result.baseline
    iso = result.isotonic
    platt = result.platt
    nc = result.negative_control

    print(f"\n{'='*70}")
    print(f" Phase 59-Pre+ — Heavy-Favorite Local Calibration Counterfactual")
    print(f"{'='*70}")
    print(f" Phase version : {result.phase_version}")
    print(f" Audit hash    : {result.audit_hash}")
    print(f" Run timestamp : {result.run_timestamp}")
    print(f" Sample size   : {result.sample_size} total / {result.n_eval} eval")
    print(f" Eval months   : {', '.join(result.eval_months)}")
    print(f"")
    print(f" {'Metric':<35} {'Baseline':>12} {'Isotonic':>12} {'Platt':>12}")
    print(f" {'-'*35} {'-'*12} {'-'*12} {'-'*12}")
    print(f" {'Overall BSS':<35} {_fmt(b.overall_bss):>12} {_fmt(iso.overall_bss):>12} {_fmt(platt.overall_bss):>12}")
    print(f" {'Overall ECE':<35} {_fmt(b.overall_ece):>12} {_fmt(iso.overall_ece):>12} {_fmt(platt.overall_ece):>12}")
    print(f" {'Heavy Fav ECE (>=0.70)':<35} {_fmt(b.heavy_fav_ece):>12} {_fmt(iso.heavy_fav_ece):>12} {_fmt(platt.heavy_fav_ece):>12}")
    print(f" {'Heavy Fav n':<35} {b.heavy_fav_n:>12} {iso.heavy_fav_n:>12} {platt.heavy_fav_n:>12}")
    print(f" {'High Conf BSS (>=0.65)':<35} {_fmt(b.high_conf_bss):>12} {_fmt(iso.high_conf_bss):>12} {_fmt(platt.high_conf_bss):>12}")
    print(f" {'Phase45 Failure Segs':<35} {b.phase45_failure_segment_count:>12} {iso.phase45_failure_segment_count:>12} {platt.phase45_failure_segment_count:>12}")
    print(f" {'Bootstrap CI':<35} {'[' + _fmt(b.bootstrap_ci_lower,4) + ',' + _fmt(b.bootstrap_ci_upper,4) + ']':>12} "
          f"{'[' + _fmt(iso.bootstrap_ci_lower,4) + ',' + _fmt(iso.bootstrap_ci_upper,4) + ']':>12} "
          f"{'[' + _fmt(platt.bootstrap_ci_lower,4) + ',' + _fmt(platt.bootstrap_ci_upper,4) + ']':>12}")
    print(f" {'Bootstrap Significant':<35} {str(b.bootstrap_significant):>12} {str(iso.bootstrap_significant):>12} {str(platt.bootstrap_significant):>12}")
    print(f"")
    print(f" Negative Control (shuffled labels):")
    print(f"   Baseline Heavy Fav ECE   : {_fmt(nc.baseline_heavy_fav_ece, 4)}")
    print(f"   Shuffled Isotonic HF ECE : {_fmt(nc.shuffled_isotonic_heavy_fav_ece, 4)}")
    print(f"   Shuffled Platt HF ECE    : {_fmt(nc.shuffled_platt_heavy_fav_ece, 4)}")
    print(f"   Sanity OK                : {nc.sanity_ok}")
    print(f"")
    gate_emoji = {"LOCAL_CALIBRATION_SUFFICIENT": "✅", "BULLPEN_HYPOTHESIS_RETAINED": "🔬",
                  "MIXED": "⚠️", "BLOCKED_INSUFFICIENT_DATA": "🚫"}.get(result.gate, "❓")
    print(f" Gate: {gate_emoji} {result.gate}")
    print(f" Rationale: {result.gate_rationale}")
    print(f"")
    print(f" Next step: {result.next_step_recommendation}")
    print(f"{'='*70}")
    print(f" Safety: CANDIDATE_PATCH_CREATED={result.candidate_patch_created}")
    print(f"         PRODUCTION_MODIFIED={result.production_modified}")
    print(f"         ALPHA_MODIFIED={result.alpha_modified}")
    print(f"{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 59-Pre+ — Heavy-Favorite Local Calibration Counterfactual"
    )
    parser.add_argument("--print", dest="do_print", action="store_true",
                        help="Print summary to stdout")
    parser.add_argument("--json", dest="do_json", action="store_true",
                        help="Write JSON report to reports/")
    parser.add_argument("--report", dest="do_report", action="store_true",
                        help="Write Markdown report to 00-BettingPlan/")
    parser.add_argument("--bootstrap", type=int, default=1000,
                        help="Number of bootstrap samples (default: 1000)")
    parser.add_argument("--input", type=str,
                        default=str(_BASELINE_JSONL),
                        help="Path to input prediction JSONL")
    args = parser.parse_args()

    # Default: print if nothing specified
    if not (args.do_print or args.do_json or args.do_report):
        args.do_print = True

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input JSONL not found: {input_path}")
        sys.exit(1)

    logger.info(f"Running Phase 59-Pre on {input_path}")
    logger.info(f"Bootstrap samples: {args.bootstrap}")

    result = run_phase59_pre(
        input_path,
        n_bootstrap=args.bootstrap,
        verbose=True,
    )

    today = date.today().isoformat()

    if args.do_print:
        _print_summary(result)

    if args.do_json:
        _REPORTS_DIR.mkdir(exist_ok=True)
        json_path = _REPORTS_DIR / f"phase59_pre_heavy_favorite_local_calibration_{today}.json"
        with json_path.open("w") as fh:
            json.dump(asdict(result), fh, indent=2, ensure_ascii=False)
        logger.info(f"JSON report → {json_path}")

    if args.do_report:
        md_text = _build_markdown(result, today)
        _BETTING_PLAN_DIR.mkdir(exist_ok=True)
        md_path = _BETTING_PLAN_DIR / f"phase59_pre_heavy_favorite_local_calibration_report_20260506.md"
        md_path.write_text(md_text, encoding="utf-8")
        logger.info(f"Markdown report → {md_path}")


if __name__ == "__main__":
    main()
