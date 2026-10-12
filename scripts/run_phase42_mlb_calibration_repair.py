"""
Phase 42: MLB Calibration Repair — CLI
========================================
Loads Phase 39 persisted prediction rows and runs calibration repair
evaluation via wbc_backend.evaluation.calibration.

Hard Rules:
  - PAPER_ONLY mode: read-only by default, no production mutation.
  - Do NOT modify production model.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS Safety Gate.
  - Do NOT fabricate model probabilities.
  - Do NOT use same-fold calibration and evaluation.
  - Do NOT random shuffle for time-aware splits.

Usage:
  python scripts/run_phase42_mlb_calibration_repair.py
  python scripts/run_phase42_mlb_calibration_repair.py --print
  python scripts/run_phase42_mlb_calibration_repair.py --json
  python scripts/run_phase42_mlb_calibration_repair.py --report
  python scripts/run_phase42_mlb_calibration_repair.py --method platt --splits 5
  python scripts/run_phase42_mlb_calibration_repair.py --method all --report
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.prediction_persistence import (
    DEFAULT_PREDICTIONS_PATH,
    load_prediction_rows,
    PredictionRow,
)
from wbc_backend.evaluation.calibration import (
    CalibrationClassification,
    CalibrationReport,
    run_calibration_repair,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
REPORT_DIR = ROOT / "docs" / "orchestration"
REPORT_PATH = REPORT_DIR / "phase42_mlb_calibration_repair_report_2026-05-04.md"
JSONL_PATH = DEFAULT_PREDICTIONS_PATH

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase42")


# ══════════════════════════════════════════════════════════════════════════════
# § Data Loading
# ══════════════════════════════════════════════════════════════════════════════

def _try_load_jsonl() -> list[PredictionRow] | None:
    """
    Attempt to load prediction rows from the Phase 39 JSONL path.
    Returns None if the file does not exist.
    """
    if not JSONL_PATH.exists():
        logger.warning(
            "Phase 39 JSONL not found at %s. "
            "Will attempt to generate via FullBacktestEngine.",
            JSONL_PATH,
        )
        return None
    try:
        rows = load_prediction_rows(JSONL_PATH)
        logger.info("Loaded %d prediction rows from %s", len(rows), JSONL_PATH)
        return rows
    except Exception as exc:
        logger.error("Failed to load JSONL: %s", exc)
        return None


def _generate_via_backtest() -> list[PredictionRow] | None:
    """
    Generate Phase 39 prediction rows by running FullBacktestEngine
    with persist_predictions=True.

    This is a fallback when the JSONL file does not exist.
    Does NOT modify the production model.
    """
    try:
        from data.mlb_data_loader import load_mlb_records  # type: ignore[import]
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine

        logger.info("Loading MLB game records for backtest …")
        records = load_mlb_records()

        if not records:
            logger.error("No game records loaded — cannot generate predictions.")
            return None

        logger.info(
            "Running FullBacktestEngine (persist_predictions=True) "
            "on %d records → %s",
            len(records),
            JSONL_PATH,
        )
        JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        engine = FullBacktestEngine(
            n_windows=5,
            min_train_size=200,
            marl_n_generations=10,
            marl_n_candidates=6,
            persist_predictions=True,
            prediction_output_path=JSONL_PATH,
        )
        report = engine.run(records)

        # Check if rows were written
        if JSONL_PATH.exists():
            rows = load_prediction_rows(JSONL_PATH)
            logger.info(
                "FullBacktestEngine wrote %d prediction rows.", len(rows)
            )
            return rows
        else:
            logger.error(
                "FullBacktestEngine completed but JSONL not found. "
                "Notes: %s",
                report.notes,
            )
            return None

    except ImportError as exc:
        logger.error("Cannot import required module for backtest: %s", exc)
        return None
    except Exception as exc:
        logger.error("FullBacktestEngine failed: %s", exc)
        return None


def load_rows() -> list[PredictionRow]:
    """
    Load prediction rows, falling back to backtest generation if needed.
    Returns empty list if all attempts fail.
    """
    rows = _try_load_jsonl()
    if rows is not None:
        return rows

    rows = _generate_via_backtest()
    if rows is not None:
        return rows

    logger.error(
        "Could not obtain prediction rows. "
        "Run FullBacktestEngine manually with persist_predictions=True."
    )
    return []


# ══════════════════════════════════════════════════════════════════════════════
# § Report Generation (Task 8)
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_bss(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.4f} ({v:+.1%})"


def _method_table_rows(report: CalibrationReport) -> str:
    """Build a Markdown table of per-method overall metrics."""
    summaries = report.method_summaries
    if not summaries:
        return "_No method summaries available._"

    # Deduplicate: show all non-blend + best blend alpha only
    display_keys: list[str] = []
    best_blend: str | None = None
    best_blend_brier = float("inf")
    for k in summaries:
        if k.startswith("market_blend_a"):
            if summaries[k]["calibrated_brier"] < best_blend_brier:
                best_blend_brier = summaries[k]["calibrated_brier"]
                best_blend = k
        else:
            display_keys.append(k)
    if best_blend:
        display_keys.append(best_blend)

    lines = [
        "| Method | Cal Brier | Raw Brier | Market Brier | Cal BSS | Raw BSS | Cal ECE | Raw ECE | N |",
        "|--------|-----------|-----------|--------------|---------|---------|---------|---------|---|",
    ]
    for k in display_keys:
        d = summaries[k]
        lines.append(
            f"| {k} "
            f"| {d['calibrated_brier']:.4f} "
            f"| {d['model_brier']:.4f} "
            f"| {d['market_brier']:.4f} "
            f"| {_fmt_bss(d['calibrated_bss'])} "
            f"| {_fmt_bss(d['raw_bss'])} "
            f"| {d['calibrated_ece']:.4f} "
            f"| {d['raw_ece']:.4f} "
            f"| {d['sample_size']} |"
        )

    return "\n".join(lines)


def _blend_alpha_table(report: CalibrationReport) -> str:
    """Build a Markdown table of all market_blend alpha values."""
    summaries = report.method_summaries
    blend_keys = sorted(
        [k for k in summaries if k.startswith("market_blend_a")],
        key=lambda k: float(k.split("market_blend_a", 1)[1]),
    )
    if not blend_keys:
        return "_market_blend not evaluated._"

    lines = [
        "| Alpha | Cal Brier | Cal BSS | Cal ECE |",
        "|-------|-----------|---------|---------|",
    ]
    for k in blend_keys:
        d = summaries[k]
        alpha = float(k.split("market_blend_a", 1)[1])
        lines.append(
            f"| {alpha:.1f} "
            f"| {d['calibrated_brier']:.4f} "
            f"| {_fmt_bss(d['calibrated_bss'])} "
            f"| {d['calibrated_ece']:.4f} |"
        )
    return "\n".join(lines)


def _split_table(report: CalibrationReport) -> str:
    if not report.fold_defs:
        return "_No fold data._"
    lines = [
        "| Fold | Train Start | Train End | Test Start | Test End | Train N | Test N |",
        "|------|-------------|-----------|------------|----------|---------|--------|",
    ]
    for fd in report.fold_defs:
        lines.append(
            f"| {fd.fold_id} "
            f"| {fd.train_start} | {fd.train_end} "
            f"| {fd.test_start} | {fd.test_end} "
            f"| {fd.train_n} | {fd.test_n} |"
        )
    return "\n".join(lines)


def generate_markdown_report(report: CalibrationReport) -> str:
    """Render a human-readable Markdown report from a CalibrationReport."""
    gate = report.bss_gate
    gate_status = "✅ ALLOWED" if gate.get("allowed") else "🚫 BLOCKED"
    patch_status = "✅ PATCH_GATE_RECHECK_ELIGIBLE" if report.patch_gate_eligible else "🔒 PATCH GATE LOCKED"

    lines = [
        "# Phase 42 — MLB Calibration Repair Report",
        "",
        f"**Generated**: {report.timestamp_utc}",
        f"**Input Path**: `{report.input_path}`",
        f"**Row Count**: {report.row_count}",
        f"**N Splits**: {report.n_splits}",
        f"**Methods Evaluated**: {', '.join(report.methods_evaluated)}",
        "",
        "---",
        "",
        "## Classification",
        "",
        f"**Result**: `{report.classification}`",
        "",
        "---",
        "",
        "## Split Summary",
        "",
        _split_table(report),
        "",
        "---",
        "",
        "## Per-Method Overall Metrics",
        "",
        _method_table_rows(report),
        "",
        "---",
        "",
        "## Market Blend Alpha Grid",
        "",
        _blend_alpha_table(report),
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Raw Model | Calibrated ({report.best_method}) | Market Baseline |",
        "|--------|-----------|-----------------------------------|-----------------|",
        f"| Brier  | {report.raw_brier_overall:.4f} | {report.calibrated_brier_overall:.4f} | {report.market_brier_overall:.4f} |",
        f"| BSS    | {_fmt_bss(report.raw_bss_overall)} | {_fmt_bss(report.calibrated_bss_overall)} | 0.0 (baseline) |",
        f"| ECE    | {report.raw_ece_overall:.4f} | {report.calibrated_ece_overall:.4f} | — |",
        "",
        f"**Best Method**: `{report.best_method}`"
        + (f" (alpha={report.best_alpha:.1f})" if report.best_alpha is not None else ""),
        "",
        "---",
        "",
        "## BSS Safety Gate",
        "",
        f"- **Gate Status**: {gate_status}",
        f"- **BSS (calibrated)**: {gate.get('bss', 'N/A'):.4f}" if gate.get('bss') is not None else "- **BSS (calibrated)**: N/A",
        f"- **Model Brier**: {gate.get('model_brier', 'N/A')}",
        f"- **Market Brier**: {gate.get('baseline', 'N/A')}",
        f"- **Task Kind**: `{gate.get('task_kind', 'N/A')}`",
        f"- **Block Reason**: {gate.get('block_reason', '—') or '—'}",
        f"- **Recommendation**: {gate.get('recommendation', '—')}",
        "",
        f"**Patch Gate**: {patch_status}",
        "",
        "---",
        "",
        "## Next Recommended Action",
        "",
    ]

    clf = report.classification
    if clf == CalibrationClassification.CALIBRATION_REPAIR_HELPFUL:
        lines += [
            "✅ Calibration repair improved both ECE and achieved BSS ≥ 0.",
            "   → Proceed to PATCH_GATE_RECHECK with calibrated probabilities.",
            "   → Do NOT deploy without full re-validation.",
        ]
    elif clf == CalibrationClassification.CALIBRATION_REPAIR_HELPFUL_BUT_NOT_SUFFICIENT:
        lines += [
            "⚠️  Calibration repair improved ECE but BSS is still negative.",
            "   → Continue FEATURE_REPAIR_INVESTIGATION or DATA_REPAIR.",
            "   → Consider COLLECT_MORE_DATA before re-attempting calibration.",
        ]
    elif clf == CalibrationClassification.MARKET_ONLY_BEST:
        lines += [
            "📊 Market-only blend performs best (alpha near 0).",
            "   → Model signal adds minimal value over raw market odds.",
            "   → Investigate model feature quality or training data issues.",
        ]
    elif clf == CalibrationClassification.CALIBRATION_REPAIR_NOT_HELPFUL:
        lines += [
            "❌ Calibration did not improve Brier/ECE on out-of-sample folds.",
            "   → Focus on DATA_REPAIR or FEATURE_REPAIR_INVESTIGATION first.",
        ]
    elif clf == CalibrationClassification.INSUFFICIENT_DATA:
        lines += [
            "⚠️  Insufficient prediction rows to evaluate calibration.",
            "   → Run FullBacktestEngine with persist_predictions=True.",
        ]
    elif clf == CalibrationClassification.RAW_MODEL_PROB_MISSING:
        lines += [
            "❌ No valid model_home_prob values found in rows.",
            "   → Check Phase 39 JSONL generation.",
        ]
    elif clf == CalibrationClassification.SKLEARN_UNAVAILABLE:
        lines += [
            "⚠️  sklearn not available. Install with: pip install scikit-learn",
        ]
    else:
        lines += ["→ Review output above for recommended next steps."]

    if report.notes:
        lines += ["", "---", "", "## Notes", ""]
        for note in report.notes:
            lines.append(f"- {note}")

    lines += ["", "---", "", "_Phase 42 MLB Calibration Repair — read-only analysis, no production changes._"]
    return "\n".join(lines)


def write_report(report: CalibrationReport) -> None:
    """Write the Markdown report to REPORT_PATH."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md = generate_markdown_report(report)
    REPORT_PATH.write_text(md, encoding="utf-8")
    logger.info("Report written → %s", REPORT_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# § CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 42 MLB Calibration Repair — read-only evaluation.",
    )
    p.add_argument(
        "--print",
        action="store_true",
        dest="print_output",
        help="Print human-readable summary to stdout.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print JSON output to stdout.",
    )
    p.add_argument(
        "--report",
        action="store_true",
        dest="write_report",
        help=f"Write Markdown report to {REPORT_PATH}.",
    )
    p.add_argument(
        "--method",
        default="all",
        dest="method",
        choices=["identity", "binwise", "platt", "isotonic", "market_blend", "all"],
        help="Calibration method to evaluate (default: all).",
    )
    p.add_argument(
        "--splits",
        type=int,
        default=5,
        dest="n_splits",
        help="Number of time-aware cross-validation splits (default: 5).",
    )
    return p.parse_args()


def _print_summary(report: CalibrationReport) -> None:
    print("=" * 70)
    print("Phase 42 — MLB Calibration Repair")
    print("=" * 70)
    print(f"Classification  : {report.classification}")
    print(f"Input path      : {report.input_path}")
    print(f"Row count       : {report.row_count}")
    print(f"N splits        : {report.n_splits}")
    print(f"Folds produced  : {len(report.fold_defs)}")
    print(f"Best method     : {report.best_method}"
          + (f" (alpha={report.best_alpha:.1f})" if report.best_alpha is not None else ""))
    print()
    print("Overall Metrics (pooled across all test folds):")
    print(f"  Raw Brier     : {report.raw_brier_overall:.4f}")
    print(f"  Cal Brier     : {report.calibrated_brier_overall:.4f}")
    print(f"  Market Brier  : {report.market_brier_overall:.4f}")
    print(f"  Raw BSS       : {_fmt_bss(report.raw_bss_overall)}")
    print(f"  Cal BSS       : {_fmt_bss(report.calibrated_bss_overall)}")
    print(f"  Raw ECE       : {report.raw_ece_overall:.4f}")
    print(f"  Cal ECE       : {report.calibrated_ece_overall:.4f}")
    print()
    gate = report.bss_gate
    gate_ok = "ALLOWED" if gate.get("allowed") else "BLOCKED"
    print(f"BSS Safety Gate : {gate_ok} | task={gate.get('task_kind')}")
    print(f"Patch Gate      : {'ELIGIBLE' if report.patch_gate_eligible else 'LOCKED'}")
    if report.notes:
        print()
        print("Notes:")
        for note in report.notes:
            print(f"  • {note}")
    print("=" * 70)


def main() -> None:
    args = _parse_args()

    methods = (
        None
        if args.method == "all"
        else [args.method]
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    rows = load_rows()

    # ── Run calibration repair ────────────────────────────────────────────────
    report = run_calibration_repair(
        rows=rows,
        methods=methods,
        n_splits=args.n_splits,
        input_path=str(JSONL_PATH),
    )

    # ── Output ────────────────────────────────────────────────────────────────
    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    if args.print_output or (not args.json_output and not args.write_report):
        _print_summary(report)

    if args.write_report:
        write_report(report)
        if not args.print_output:
            _print_summary(report)

    # Exit 0 always — this is a read-only analysis script.
    sys.exit(0)


if __name__ == "__main__":
    main()
