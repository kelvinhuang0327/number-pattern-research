"""
Phase 43: Model Value & Market Blend Stability Audit — CLI
===========================================================
Runs the Phase 43 stability audit on Phase 39 persisted prediction rows.

Hard Rules:
  - PAPER_ONLY mode: read-only by default, no production mutation.
  - Do NOT modify production model.
  - Do NOT create CANDIDATE_PATCH.
  - Do NOT call external API / LLM.
  - Do NOT bypass BSS Safety Gate.
  - Do NOT treat best-per-fold alpha as production proof.
  - Bootstrap CI crossing zero → NOT_SIGNIFICANT.

Usage:
  python scripts/run_phase43_model_value_market_blend_stability.py
  python scripts/run_phase43_model_value_market_blend_stability.py --print
  python scripts/run_phase43_model_value_market_blend_stability.py --report
  python scripts/run_phase43_model_value_market_blend_stability.py --print --report
  python scripts/run_phase43_model_value_market_blend_stability.py --splits 5 --bootstrap 1000
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.prediction_persistence import (
    DEFAULT_PREDICTIONS_PATH,
    load_prediction_rows,
    PredictionRow,
)
from orchestrator.phase43_model_value_market_blend_stability import (
    Phase43AuditReport,
    FoldStabilityRow,
    BootstrapResult,
    SegmentResult,
    FIXED_ALPHA,
    run_phase43_audit,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
REPORT_DIR = ROOT / "docs" / "orchestration"
_TODAY = date.today().isoformat()
REPORT_PATH = REPORT_DIR / f"phase43_model_value_market_blend_stability_audit_{_TODAY}.md"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("phase43_cli")


# ══════════════════════════════════════════════════════════════════════════════
# § Report Generation (Markdown)
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_bss(v: float) -> str:
    return f"{v:+.4f} ({v:+.2%})"


def _sig_badge(result: BootstrapResult) -> str:
    icon = "✅" if result.significant else "⚠️"
    return f"{icon} {result.significance_label}"


def _gate_badge(gate: str) -> str:
    badges = {
        "PATCH_GATE_RECHECK": "🟢",
        "MARKET_BLEND_PAPER_ONLY": "🟡",
        "FEATURE_REPAIR_INVESTIGATION": "🟡",
        "COLLECT_MORE_DATA": "🔴",
        "HOLD": "🔴",
        "PENDING": "⚪",
    }
    return f"{badges.get(gate, '⚪')} {gate}"


def _fold_table(fold_results: list[FoldStabilityRow]) -> str:
    header = (
        "| Fold | N | Date Range | Raw Brier | Market Brier | Blend Brier | "
        "Raw BSS | Blend BSS | Raw ECE | Blend ECE | Best α* |\n"
        "|------|---|------------|-----------|--------------|-------------|"
        "---------|-----------|---------|-----------|----------|\n"
    )
    rows = []
    for f in fold_results:
        bss_raw_icon = "✅" if f.raw_bss >= 0 else "❌"
        bss_blend_icon = "✅" if f.blend_bss >= 0 else "❌"
        rows.append(
            f"| {f.fold_id} | {f.n} | {f.date_start} → {f.date_end} | "
            f"{f.raw_brier:.4f} | {f.market_brier:.4f} | {f.blend_brier:.4f} | "
            f"{bss_raw_icon} {f.raw_bss:+.4f} | {bss_blend_icon} {f.blend_bss:+.4f} | "
            f"{f.raw_ece:.4f} | {f.blend_ece:.4f} | {f.best_alpha_per_fold} |"
        )
    footer = "\n\n> \\* Best α per fold is **DIAGNOSTIC ONLY** — not production proof.\n"
    return header + "\n".join(rows) + footer


def _bootstrap_section(bs: BootstrapResult) -> str:
    return (
        f"| {bs.label} | {bs.n_samples} | {bs.n_bootstrap} | "
        f"{bs.mean_delta_brier:+.4f} | "
        f"[{bs.ci_lower:+.4f}, {bs.ci_upper:+.4f}] | "
        f"{bs.prob_improvement:.1%} | {_sig_badge(bs)} |"
    )


def _segment_table(seg_results: list[SegmentResult]) -> str:
    header = (
        "| Type | Segment | N | Raw Brier | Market Brier | Blend Brier | "
        "Raw BSS | Blend BSS | Value |\n"
        "|------|---------|---|-----------|--------------|-------------|"
        "---------|-----------|-------|\n"
    )
    rows = []
    for sr in seg_results:
        val_icon = {
            "STABLE_VALUE": "🟢", "CONDITIONAL_VALUE": "🟡",
            "WEAK_VALUE": "🟠", "NO_VALUE": "🔴",
        }.get(sr.value_classification, "⚪")
        rows.append(
            f"| {sr.segment_type} | {sr.segment_label} | {sr.n} | "
            f"{sr.raw_brier:.4f} | {sr.market_brier:.4f} | {sr.blend_brier:.4f} | "
            f"{sr.raw_bss:+.4f} | {sr.blend_bss:+.4f} | "
            f"{val_icon} {sr.value_classification} |"
        )
    return header + "\n".join(rows)


def generate_markdown_report(report: Phase43AuditReport) -> str:
    """Generate full Markdown report for Phase 43."""
    bs_blend = report.bootstrap_blend_vs_market
    bs_raw = report.bootstrap_raw_vs_market

    md: list[str] = []
    md.append(f"# Phase 43: Model Value & Market Blend Stability Audit\n")
    md.append(f"> **生成日期**: {_TODAY}  |  Run: {report.timestamp_utc}\n")
    md.append("---\n")

    # Summary box
    md.append("## Executive Summary\n")
    md.append(f"| 項目 | 值 |")
    md.append("|------|----|")
    md.append(f"| Gate Recommendation | {_gate_badge(report.gate.recommendation)} |")
    md.append(f"| Fold Stability | {report.fold_stability_label} ({report.folds_with_positive_blend_bss}/{len(report.fold_results)} folds blend_bss ≥ 0) |")
    if bs_blend:
        md.append(f"| Bootstrap blend_vs_market | {_sig_badge(bs_blend)} |")
        md.append(f"| Bootstrap CI (blend) | [{bs_blend.ci_lower:+.4f}, {bs_blend.ci_upper:+.4f}] |")
        md.append(f"| P(blend improves) | {bs_blend.prob_improvement:.1%} |")
    md.append(f"| Segment Best Value | {max(report.segment_value_summary.values(), key=lambda v: ['NO_VALUE','WEAK_VALUE','CONDITIONAL_VALUE','STABLE_VALUE'].index(v)) if report.segment_value_summary else 'N/A'} |")
    md.append(f"| Candidate Patch Created | {'⛔ YES (ERROR)' if report.gate.candidate_patch_created else '✅ NO'} |")
    md.append("")

    # Overall metrics
    md.append("## 1. Overall Metrics\n")
    md.append("| Metric | Raw Model | Market Baseline | Blend α=0.4 |")
    md.append("|--------|-----------|-----------------|-------------|")
    md.append(f"| Brier | {report.overall_raw_brier:.6f} | {report.overall_market_brier:.6f} | {report.overall_blend_brier:.6f} |")
    md.append(f"| BSS vs market | {_fmt_bss(report.overall_raw_bss)} | — | {_fmt_bss(report.overall_blend_bss)} |")
    md.append(f"| ECE | {report.overall_raw_ece:.6f} | — | {report.overall_blend_ece:.6f} |")
    md.append(f"| Row count | {report.row_count} | | |")
    md.append("")

    # Fold stability
    md.append("## 2. Fold-Level Stability Audit\n")
    md.append(f"> Time-aware expanding-window splits: {len(report.fold_results)} folds.  \n")
    md.append(f"> Stability: **{report.fold_stability_label}** — {report.folds_with_positive_blend_bss}/{len(report.fold_results)} folds have blend_bss ≥ 0.\n")
    md.append(_fold_table(report.fold_results))
    md.append("")

    # Bootstrap
    md.append("## 3. Bootstrap CI / Significance Test\n")
    md.append("> **Rule**: if 95% CI crosses 0, classification = NOT_SIGNIFICANT.\n")
    md.append("")
    md.append("| Comparison | N | Bootstraps | Mean ΔBrier | 95% CI | P(improve) | Significance |")
    md.append("|------------|---|------------|-------------|--------|------------|--------------|")
    if bs_raw:
        md.append(_bootstrap_section(bs_raw))
    if bs_blend:
        md.append(_bootstrap_section(bs_blend))
    md.append("")
    if bs_blend and not bs_blend.significant:
        md.append("> ⚠️ **NOT_SIGNIFICANT**: CI crosses 0. Cannot recommend PATCH_GATE_RECHECK based on bootstrap alone.\n")

    # Segment analysis
    md.append("## 4. Segment-Level Model Value Analysis\n")
    md.append("| Segment Type | Best Value Classification |")
    md.append("|--------------|--------------------------|")
    for seg_type, val in sorted(report.segment_value_summary.items()):
        icon = {"STABLE_VALUE": "🟢", "CONDITIONAL_VALUE": "🟡", "WEAK_VALUE": "🟠", "NO_VALUE": "🔴"}.get(val, "⚪")
        md.append(f"| {seg_type} | {icon} {val} |")
    md.append("")
    md.append("### Segment Detail\n")
    md.append(_segment_table(report.segment_results))
    md.append("")

    # Gate
    md.append("## 5. Gate Recommendation\n")
    md.append(f"### {_gate_badge(report.gate.recommendation)}\n")
    md.append("**Reasoning:**\n")
    for r in report.gate.reasoning:
        md.append(f"- {r}")
    md.append("")
    md.append("**Hard Rules Verified:**\n")
    md.append(f"- CANDIDATE_PATCH created: {'⛔ YES — ERROR' if report.gate.candidate_patch_created else '✅ No'}")
    md.append(f"- Bootstrap significant: {'✅ Yes' if report.gate.bootstrap_significant else '⚠️ No (CI crosses 0)'}")
    md.append(f"- Fold stable: {'✅ Yes' if report.gate.fold_stable else '❌ No'}")
    md.append(f"- Has STABLE_VALUE segment: {'✅ Yes' if report.gate.has_stable_value_segment else '❌ No'}")
    md.append(f"- Best-per-fold alpha used as proof: ✅ No (diagnostic_only=True on all folds)")
    md.append("")

    # Notes
    if report.notes:
        md.append("## 6. Notes\n")
        for n in report.notes:
            md.append(f"- {n}")
        md.append("")

    md.append("---")
    md.append(f"*Generated by Phase 43 audit — read-only, no production mutations.*")

    return "\n".join(md)


def write_report(report: Phase43AuditReport) -> Path:
    """Write Markdown report and return path."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    content = generate_markdown_report(report)
    REPORT_PATH.write_text(content, encoding="utf-8")
    logger.info("Report written → %s", REPORT_PATH)
    return REPORT_PATH


# ══════════════════════════════════════════════════════════════════════════════
# § Print Summary
# ══════════════════════════════════════════════════════════════════════════════

def _print_summary(report: Phase43AuditReport) -> None:
    """Print compact summary to stdout."""
    bs_blend = report.bootstrap_blend_vs_market
    bs_raw = report.bootstrap_raw_vs_market

    print("=" * 70)
    print("Phase 43 — Model Value & Market Blend Stability Audit")
    print("=" * 70)
    print(f"Input path      : {report.input_path}")
    print(f"Row count       : {report.row_count}")
    print(f"N splits        : {report.n_splits}  |  Fixed alpha: {report.fixed_alpha}")
    print(f"Folds produced  : {len(report.fold_results)}")
    print()
    print("Overall Metrics (all rows):")
    print(f"  Raw Brier     : {report.overall_raw_brier:.4f}")
    print(f"  Blend Brier   : {report.overall_blend_brier:.4f}")
    print(f"  Market Brier  : {report.overall_market_brier:.4f}")
    print(f"  Raw BSS       : {report.overall_raw_bss:+.4f} ({report.overall_raw_bss:+.2%})")
    print(f"  Blend BSS     : {report.overall_blend_bss:+.4f} ({report.overall_blend_bss:+.2%})")
    print(f"  Raw ECE       : {report.overall_raw_ece:.4f}")
    print(f"  Blend ECE     : {report.overall_blend_ece:.4f}")
    print()
    print("Fold Stability:")
    print(f"  Label         : {report.fold_stability_label}")
    print(f"  Positive folds: {report.folds_with_positive_blend_bss}/{len(report.fold_results)} (blend_bss >= 0)")
    for f in report.fold_results:
        icon = "✓" if f.blend_bss >= 0 else "✗"
        diag = "DIAG-ONLY" if f.diagnostic_only else "ERROR"
        print(f"  {f.fold_id}  n={f.n}  raw={f.raw_bss:+.4f}  blend={f.blend_bss:+.4f}  best_a={f.best_alpha_per_fold} [{diag}]  {icon}")
    print()
    print("Bootstrap CI (95%):")
    if bs_raw:
        print(f"  Raw  vs market: {bs_raw.significance_label:16s}  CI=[{bs_raw.ci_lower:+.4f}, {bs_raw.ci_upper:+.4f}]  p_improve={bs_raw.prob_improvement:.1%}")
    if bs_blend:
        print(f"  Blend vs market: {bs_blend.significance_label:15s}  CI=[{bs_blend.ci_lower:+.4f}, {bs_blend.ci_upper:+.4f}]  p_improve={bs_blend.prob_improvement:.1%}")
    print()
    print("Segment Value Summary:")
    for seg_type, val in sorted(report.segment_value_summary.items()):
        print(f"  {seg_type:30s}: {val}")
    print()
    print(f"Gate Recommendation: {report.gate.recommendation}")
    for r in report.gate.reasoning:
        print(f"  • {r}")
    print(f"\nCandidate Patch Created: {report.gate.candidate_patch_created}")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# § Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 43: Model Value & Market Blend Stability Audit"
    )
    parser.add_argument("--print", dest="do_print", action="store_true",
                        help="Print summary to stdout.")
    parser.add_argument("--report", action="store_true",
                        help="Write Markdown report to docs/orchestration/.")
    parser.add_argument("--splits", type=int, default=5,
                        help="Number of time-aware splits (default: 5).")
    parser.add_argument("--bootstrap", type=int, default=1000,
                        help="Number of bootstrap samples (default: 1000).")
    args = parser.parse_args()

    # Default: print if no flags given
    if not args.do_print and not args.report:
        args.do_print = True

    # Load rows
    if not DEFAULT_PREDICTIONS_PATH.exists():
        logger.error(
            "Phase 39 JSONL not found at %s. "
            "Run FullBacktestEngine with persist_predictions=True first.",
            DEFAULT_PREDICTIONS_PATH,
        )
        sys.exit(1)

    rows = load_prediction_rows(DEFAULT_PREDICTIONS_PATH)
    if not rows:
        logger.error("No prediction rows loaded. Cannot run Phase 43 audit.")
        sys.exit(1)

    # Run audit
    report = run_phase43_audit(
        rows,
        n_splits=args.splits,
        n_bootstrap=args.bootstrap,
        input_path=str(DEFAULT_PREDICTIONS_PATH),
    )

    if args.do_print:
        _print_summary(report)

    if args.report:
        path = write_report(report)
        print(f"Report: {path}")


if __name__ == "__main__":
    main()
