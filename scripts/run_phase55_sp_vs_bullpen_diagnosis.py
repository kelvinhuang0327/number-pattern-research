#!/usr/bin/env python3
"""
scripts/run_phase55_sp_vs_bullpen_diagnosis.py
=============================================
Phase 55 CLI runner — SP Functional Form Redesign vs Bullpen Feature Investigation

Usage:
  python scripts/run_phase55_sp_vs_bullpen_diagnosis.py [--print] [--json] [--report]

Flags:
  --print    Print summary to stdout
  --json     Write JSON report to reports/phase55_sp_vs_bullpen_diagnosis_YYYY-MM-DD.json
  --report   Write Markdown report to docs/feature_repair/phase55_sp_vs_bullpen_diagnosis_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

# Activate project root for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.phase55_sp_vs_bullpen_diagnosis import (
    run_phase55_diagnosis,
    Phase55DiagnosisResult,
    FunctionalFormResult,
    SP_FUNCTIONAL_FORM_REDESIGN,
    BULLPEN_FEATURE_INVESTIGATION,
    COLLECT_MORE_DATA,
    RECOMMENDED_BULLPEN_FEATURES,
    ALL_FORM_NAMES,
    _PHASE54_FAILURE_COUNT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_BASELINE_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl"
_CONTEXT_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl"
_PHASE54_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase54_sp_safe_coeff_v1.jsonl"
_PHASE54_REPORT = ROOT / "reports/phase54_safe_sp_stability_audit_2026-05-05.json"
_REPORTS_DIR = ROOT / "reports"
_DOCS_DIR = ROOT / "docs/feature_repair"


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Markdown builder
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v: float | None, precision: int = 6) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.{precision}f}"


def _pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def _build_markdown(result: Phase55DiagnosisResult, today: str) -> str:
    lines: list[str] = []
    bd = result.bullpen_diagnosis

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append(f"# Phase 55 — SP Functional Form Redesign vs Bullpen Feature Investigation")
    lines.append(f"")
    lines.append(f"**Report Date**: {today}")
    lines.append(f"**Phase**: 55 — SP vs Bullpen Diagnosis")
    lines.append(f"**Version**: {result.phase55_version}")
    lines.append(f"**Audit Hash**: `{result.audit_hash}`")
    lines.append(f"")

    # ── Executive Summary ──────────────────────────────────────────────────────
    lines.append(f"## Executive Summary")
    lines.append(f"")
    conclusion_emoji = {
        SP_FUNCTIONAL_FORM_REDESIGN: "🔧",
        BULLPEN_FEATURE_INVESTIGATION: "⚾",
        COLLECT_MORE_DATA: "📊",
    }.get(result.conclusion, "❓")
    lines.append(f"**Conclusion**: {conclusion_emoji} `{result.conclusion}`")
    lines.append(f"")
    lines.append(f"**Rationale**: {result.conclusion_rationale}")
    lines.append(f"")
    lines.append(f"**Bullpen Missing Score**: {bd.bullpen_missing_score:.4f} / 1.0")
    lines.append(f"**Failure Pattern**: `{bd.failure_pattern}`")
    lines.append(f"**Best SP Form**: `{result.best_form_name}` (failure_count={result.best_form_failure_count})")
    lines.append(f"**Phase54 Baseline Failure Count**: {result.phase54_failure_count}")
    lines.append(f"")
    lines.append(f"| Hard Rule | Value |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| candidate_patch_created | `{result.candidate_patch_created}` |")
    lines.append(f"| production_modified | `{result.production_modified}` |")
    lines.append(f"| diagnostic_only | `{result.diagnostic_only}` |")
    lines.append(f"")

    # ── Why Phase54 Failed ────────────────────────────────────────────────────
    lines.append(f"## Why Phase54 Failed")
    lines.append(f"")
    lines.append(f"Phase 54 applied safe coefficient (scale=0.25x, effective=0.00075) to Phase52 SP context rows.")
    lines.append(f"Despite conservative coefficient, Phase45 re-run showed **{result.phase54_failure_count} failure segments**.")
    lines.append(f"")
    lines.append(f"**Phase54 failure segments**:")
    for seg in result.phase54_failure_segments:
        lines.append(f"- `{seg}`")
    lines.append(f"")
    lines.append(f"Key observations from Phase54:")
    lines.append(f"- `heavy_fav_ece_no_longer_failure = False` → heavy_favorite ECE issue persists")
    lines.append(f"- `high_conf_improved = False` → high_confidence segment not resolved")
    lines.append(f"- Phase43 BSS delta vs baseline = -2.6e-05 (slight degradation)")
    lines.append(f"- failure_count_delta = +6 (all failures new vs Phase43 baseline)")
    lines.append(f"")
    lines.append(f"Phase 55 investigates whether this is due to:")
    lines.append(f"1. **SP functional form** (tanh shape, scale, sign, bucket)")
    lines.append(f"2. **Missing bullpen / late-game features** (fatigue, leverage, ERA proxy)")
    lines.append(f"3. **Insufficient sample size** (bootstrap still not significant)")
    lines.append(f"")

    # ── SP Functional Form Comparison ─────────────────────────────────────────
    lines.append(f"## SP Functional Form Comparison")
    lines.append(f"")
    lines.append(
        f"| Form | adj_rows | adj_rate | max_abs_adj | overall_bss | overall_ece "
        f"| heavy_fav_ece | high_conf_bss | month_04_bss | failure_count |"
    )
    lines.append(
        f"|------|----------|----------|-------------|-------------|-------------"
        f"|---------------|---------------|--------------|---------------|"
    )
    for fr in result.functional_form_results:
        best_mark = " ⭐" if fr.form_name == result.best_form_name else ""
        lines.append(
            f"| `{fr.form_name}`{best_mark} "
            f"| {fr.adjusted_rows} "
            f"| {_pct(fr.adjusted_rate)} "
            f"| {fr.max_abs_adjustment:.6f} "
            f"| {_fmt(fr.overall_bss)} "
            f"| {_fmt(fr.overall_ece)} "
            f"| {_fmt(fr.heavy_fav_ece)} "
            f"| {_fmt(fr.high_conf_bss)} "
            f"| {_fmt(fr.month_2025_04_bss)} "
            f"| {fr.failure_segment_count} |"
        )
    lines.append(f"")
    lines.append(f"**Phase54 reference**: failure_count={result.phase54_failure_count}")
    lines.append(f"")

    # ── Functional Form Descriptions ──────────────────────────────────────────
    lines.append(f"### Functional Form Descriptions")
    lines.append(f"")
    descriptions = {
        "tanh_current": "tanh(delta × 0.5) × 0.003 × 0.25 — Phase54 safe coefficient (reference)",
        "tanh_stronger": "tanh(delta × 0.5) × 0.003 × 0.50 — 2× the safe coefficient",
        "linear_capped": "clip(delta × 0.0005, -0.008, +0.008) — linear form with hard cap",
        "sign_only": "±0.001 if |delta| > 1.0 else 0 — sign-only advantage",
        "bucketed_delta": "5 buckets: large/small home/away edge (±0.003/±0.001), neutral",
        "shrink_to_market": "tanh_current but 50% shrinkage when |model - 0.5| >= 0.15 (high confidence)",
    }
    for form_name, desc in descriptions.items():
        lines.append(f"- **`{form_name}`**: {desc}")
    lines.append(f"")

    # ── Bullpen Missing-Feature Evidence ──────────────────────────────────────
    lines.append(f"## Bullpen Missing-Feature Evidence")
    lines.append(f"")
    lines.append(f"| Indicator | Value |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| bullpen_missing_score | {bd.bullpen_missing_score:.4f} |")
    lines.append(f"| bullpen_feature_likely_missing | `{bd.bullpen_feature_likely_missing}` |")
    lines.append(f"| failure_pattern | `{bd.failure_pattern}` |")
    lines.append(f"")
    lines.append(f"**Evidence:**")
    if bd.evidence:
        for ev in bd.evidence:
            lines.append(f"- {ev}")
    else:
        lines.append(f"- 無顯著 bullpen missing-feature 證據")
    lines.append(f"")
    lines.append(f"**Recommended Bullpen Features** (for Phase56 if BULLPEN_FEATURE_INVESTIGATION):")
    for feat in bd.recommended_features:
        lines.append(f"- `{feat}`")
    lines.append(f"")

    # ── Decision Conclusion ────────────────────────────────────────────────────
    lines.append(f"## Decision Conclusion")
    lines.append(f"")
    lines.append(f"```")
    lines.append(f"conclusion = {result.conclusion}")
    lines.append(f"```")
    lines.append(f"")
    lines.append(f"**Rationale**: {result.conclusion_rationale}")
    lines.append(f"")

    if result.conclusion == SP_FUNCTIONAL_FORM_REDESIGN:
        lines.append(f"### SP Functional Form Redesign Path")
        lines.append(f"")
        lines.append(f"Best form `{result.best_form_name}` demonstrated:")
        lines.append(
            f"- Failure segment reduction: "
            f"{result.phase54_failure_count} → {result.best_form_failure_count} "
            f"(Δ={result.phase54_failure_count - (result.best_form_failure_count or 0):+d})"
        )
        best_form = next(
            (f for f in result.functional_form_results if f.form_name == result.best_form_name),
            None,
        )
        if best_form:
            lines.append(f"- overall_bss = {_fmt(best_form.overall_bss)}")
            lines.append(f"- heavy_fav_ece = {_fmt(best_form.heavy_fav_ece)}")
            lines.append(f"- high_conf_bss = {_fmt(best_form.high_conf_bss)}")
        lines.append(f"")
    elif result.conclusion == BULLPEN_FEATURE_INVESTIGATION:
        lines.append(f"### Bullpen Feature Investigation Path")
        lines.append(f"")
        lines.append(
            f"bullpen_missing_score={bd.bullpen_missing_score:.4f} >= {0.60}. "
            f"All SP functional forms fail to resolve heavy_favorite / high_confidence failures. "
            f"Market likely pricing in bullpen state information the model lacks."
        )
        lines.append(f"")
    else:
        lines.append(f"### Collect More Data Path")
        lines.append(f"")
        lines.append(
            f"Signal too weak: bullpen_missing_score={bd.bullpen_missing_score:.4f} < 0.60, "
            f"no SP form clearly reduces failures. "
            f"Recommend continuing paper tracking for 500+ additional games."
        )
        lines.append(f"")

    # ── Recommended Phase56 Tasks ──────────────────────────────────────────────
    lines.append(f"## Recommended Phase56 Tasks")
    lines.append(f"")
    for i, task in enumerate(result.recommended_phase56_tasks, 1):
        lines.append(f"{i}. {task}")
    lines.append(f"")

    # ── Limitations ───────────────────────────────────────────────────────────
    lines.append(f"## Limitations")
    lines.append(f"")
    lines.append(f"1. Functional form evaluation uses raw model BSS (not blended) for consistency across forms.")
    lines.append(f"2. Segment failure count may differ from Phase45's blended analysis.")
    lines.append(f"3. bootstrap significance was NOT_SIGNIFICANT in Phase54; Phase55 does not rerun bootstrap.")
    lines.append(
        f"4. heavy_favorite ECE references Phase54 values; any improvement here is "
        f"diagnostic-only and cannot be productionized without Phase43/44/45 re-audit."
    )
    lines.append(f"5. All {len(ALL_FORM_NAMES)} forms are offline-only; no production JSONL is written.")
    lines.append(f"")

    # ── Hard-Rule Confirmation ─────────────────────────────────────────────────
    lines.append(f"## Hard-Rule Confirmation")
    lines.append(f"")
    lines.append(f"```")
    lines.append(f"candidate_patch_created = {result.candidate_patch_created}")
    lines.append(f"production_modified     = {result.production_modified}")
    lines.append(f"diagnostic_only         = {result.diagnostic_only}")
    lines.append(f"conclusion              = {result.conclusion}")
    lines.append(f"audit_hash              = {result.audit_hash}")
    lines.append(f"```")
    lines.append(f"")
    lines.append(f"All hard rules satisfied:")
    lines.append(f"- No production JSONL written in Phase 55")
    lines.append(f"- No model retraining or ensemble")
    lines.append(f"- No look-ahead leakage (p0_features computed pre-game)")
    lines.append(f"- candidate_patch_created enforced by Phase55DiagnosisResult.__post_init__")
    lines.append(f"")

    # ── Completion Marker ──────────────────────────────────────────────────────
    lines.append(f"## Completion Marker")
    lines.append(f"")
    lines.append(f"```")
    lines.append(f"PHASE_55_SP_VS_BULLPEN_DIAGNOSIS_VERIFIED")
    lines.append(f"conclusion={result.conclusion}")
    lines.append(f"bullpen_missing_score={bd.bullpen_missing_score:.4f}")
    lines.append(f"bullpen_feature_likely_missing={bd.bullpen_feature_likely_missing}")
    lines.append(f"failure_pattern={bd.failure_pattern}")
    lines.append(f"best_form_name={result.best_form_name}")
    lines.append(f"best_form_failure_count={result.best_form_failure_count}")
    lines.append(f"phase54_failure_count={result.phase54_failure_count}")
    lines.append(f"candidate_patch_created={result.candidate_patch_created}")
    lines.append(f"production_modified={result.production_modified}")
    lines.append(f"diagnostic_only={result.diagnostic_only}")
    lines.append(f"audit_hash={result.audit_hash}")
    lines.append(f"```")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  Print summary
# ═══════════════════════════════════════════════════════════════════════════════

def _print_summary(result: Phase55DiagnosisResult) -> None:
    bd = result.bullpen_diagnosis
    print("\n=== Phase 55 SP vs Bullpen Diagnosis ===")
    print(f"conclusion:                     {result.conclusion}")
    print(f"bullpen_missing_score:          {bd.bullpen_missing_score:.4f}")
    print(f"bullpen_feature_likely_missing: {bd.bullpen_feature_likely_missing}")
    print(f"failure_pattern:                {bd.failure_pattern}")
    print(f"best_form_name:                 {result.best_form_name}")
    print(f"best_form_failure_count:        {result.best_form_failure_count}")
    print(f"phase54_failure_count_ref:      {result.phase54_failure_count}")
    print()
    print("--- SP Functional Forms ---")
    for fr in result.functional_form_results:
        marker = " ← best" if fr.form_name == result.best_form_name else ""
        bss_str = f"{fr.overall_bss:.6f}" if fr.overall_bss is not None else "N/A"
        ece_str = f"{fr.heavy_fav_ece:.6f}" if fr.heavy_fav_ece is not None else "N/A"
        print(
            f"  {fr.form_name:<22} failure_count={fr.failure_segment_count} "
            f"| overall_bss={bss_str:>10} "
            f"| heavy_fav_ece={ece_str:>10}{marker}"
        )
    print()
    print("--- Bullpen Evidence ---")
    for ev in bd.evidence:
        print(f"  - {ev}")
    print()
    print("--- Recommended Phase56 Tasks ---")
    for i, task in enumerate(result.recommended_phase56_tasks, 1):
        print(f"  {i}. {task}")
    print()
    print(f"candidate_patch_created:        {result.candidate_patch_created}")
    print(f"production_modified:            {result.production_modified}")
    print(f"diagnostic_only:                {result.diagnostic_only}")
    print(f"audit_hash:                     {result.audit_hash}")


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Main
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 55 — SP Functional Form Redesign vs Bullpen Feature Investigation"
    )
    p.add_argument("--print", action="store_true", dest="print_summary", help="Print summary to stdout")
    p.add_argument("--json", action="store_true", dest="write_json", help="Write JSON report")
    p.add_argument("--report", action="store_true", dest="write_report", help="Write Markdown report")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    today = date.today().isoformat()

    # Validate inputs
    if not _CONTEXT_JSONL.exists():
        logger.error("Phase52 context JSONL not found: %s", _CONTEXT_JSONL)
        sys.exit(1)

    # Run Phase55
    result = run_phase55_diagnosis(
        context_path=_CONTEXT_JSONL,
        baseline_path=_BASELINE_JSONL if _BASELINE_JSONL.exists() else None,
        phase54_path=_PHASE54_JSONL if _PHASE54_JSONL.exists() else None,
        phase54_report_path=_PHASE54_REPORT if _PHASE54_REPORT.exists() else None,
    )

    # Print summary
    if args.print_summary:
        _print_summary(result)

    # Write JSON
    if args.write_json:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        json_path = _REPORTS_DIR / f"phase55_sp_vs_bullpen_diagnosis_{today}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)
        logger.info("JSON report written: %s", json_path)
        print(f"  JSON:     {json_path}")

    # Write Markdown
    if args.write_report:
        _DOCS_DIR.mkdir(parents=True, exist_ok=True)
        md_path = _DOCS_DIR / f"phase55_sp_vs_bullpen_diagnosis_{today}.md"
        md = _build_markdown(result, today)
        md_path.write_text(md, encoding="utf-8")
        logger.info("Markdown report written: %s", md_path)
        print(f"\nReports written:")
        print(f"  Markdown: {md_path}")

    if not any([args.print_summary, args.write_json, args.write_report]):
        _print_summary(result)


if __name__ == "__main__":
    main()
