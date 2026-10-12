#!/usr/bin/env python3
"""
Phase 44 CLI Runner: Market Blend Paper-Only Tracking
=====================================================
Usage:
    python scripts/run_phase44_market_blend_paper_tracking.py [--print] [--report] [--json]

Options:
    --print    Print a human-readable summary to stdout (default if no flag given).
    --report   Write Markdown report to docs/orchestration/phase44_market_blend_paper_tracking_YYYY-MM-DD.md
    --json     Write JSON evidence to reports/phase44_market_blend_paper_tracking_YYYY-MM-DD.json
    --rerun-bootstrap  Re-run bootstrap CI from prediction JSONL (slow, ~60s)
    --input    Override prediction JSONL path

Hard Rules (enforced by module):
    - gate_state = PAPER_ONLY  (never changes)
    - candidate_patch_created = False  (never changes)
    - alpha = 0.4 (never changes)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root on sys.path when run directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from orchestrator.phase44_market_blend_paper_tracking import (
    NEXT_GATE_CRITERIA,
    PAPER_ALPHA,
    PHASE43_EVIDENCE_SUMMARY,
    RISK_NOTES,
    BootstrapSummary,
    GateCriteriaStatus,
    PaperTrackingSnapshot,
    run_phase44_tracking,
)
from wbc_backend.evaluation.prediction_persistence import (
    DEFAULT_PREDICTIONS_PATH,
    load_prediction_rows,
)

# ─── Report paths ────────────────────────────────────────────────────────────
_REPORT_DIR = _PROJECT_ROOT / "docs" / "orchestration"
_JSON_DIR = _PROJECT_ROOT / "reports"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _print_summary(snap: PaperTrackingSnapshot) -> None:
    """Print a concise one-screen summary to stdout."""
    hr = "=" * 72
    sub = "-" * 72
    bs = snap.bootstrap

    print(hr)
    print("PHASE 44 — MARKET BLEND PAPER-ONLY TRACKING")
    print(hr)
    print(f"Run ID        : {snap.run_id}")
    print(f"Generated at  : {snap.generated_at}")
    print(f"Input path    : {snap.input_prediction_path}")
    print(f"Sample size   : {snap.sample_size:,}")
    print(f"Date range    : {snap.date_start} → {snap.date_end}")
    print(f"Alpha (fixed) : {snap.alpha}")
    print()
    print(sub)
    print("GATE STATE")
    print(sub)
    print(f"  gate_state             : {snap.gate_state}")
    print(f"  candidate_patch_created: {snap.candidate_patch_created}")
    print(f"  gate_criteria          : {snap.gate_criteria_summary}")
    print()

    print(sub)
    print("METRICS")
    print(sub)
    print(f"  {'':30} {'Raw':>10} {'Market':>10} {'Blend(α=0.4)':>14}")
    print(f"  {'Brier Score':30} {snap.raw_brier:10.4f} {snap.market_brier:10.4f} {snap.blend_brier:14.4f}")
    print(f"  {'BSS vs Market':30} {snap.raw_bss:+10.4f} {'—':>10} {snap.blend_bss:+14.4f}")
    print(f"  {'ECE':30} {snap.raw_ece:10.4f} {snap.market_ece:10.4f} {snap.blend_ece:14.4f}")
    print(f"  {'Brier Delta (blend-mkt)':30} {'—':>10} {'—':>10} {snap.brier_delta:+14.4f}")
    print()

    if bs:
        print(sub)
        print("BOOTSTRAP CI (blend vs market)")
        print(sub)
        ci_str = f"[{bs.ci_lower:+.4f}, {bs.ci_upper:+.4f}]" if (bs.ci_lower is not None and bs.ci_upper is not None) else "N/A"
        p_str = f"{bs.prob_improvement:.1%}" if bs.prob_improvement is not None else "N/A"
        print(f"  Significance  : {bs.significance}")
        print(f"  CI (95%)      : {ci_str}")
        print(f"  P(improve)    : {p_str}")
        print(f"  Source        : {bs.source}")
        print()

    if snap.segment_summary:
        print(sub)
        print("SEGMENT SUMMARY (best classification per segment type)")
        print(sub)
        for seg_type, classification in snap.segment_summary.items():
            print(f"  {seg_type:30} {classification}")
        print()

    gc = snap.gate_criteria
    if gc:
        print(sub)
        print("NEXT GATE CRITERIA STATUS")
        print(sub)
        criteria = [
            (f"sample_size >= {3000:,}", gc.sample_size_met),
            ("bootstrap SIGNIFICANT", gc.bootstrap_significant),
            ("blend_bss consistently > 0", gc.blend_bss_consistently_positive),
            ("ECE not deteriorated", gc.ece_not_deteriorated),
            (">= 4/5 folds positive", gc.folds_positive_met),
            ("human review approved", gc.human_review_approved),
        ]
        for label, met in criteria:
            icon = "✅" if met else "❌"
            print(f"  {icon}  {label}")
        print()

    print(sub)
    print("RISK NOTES")
    print(sub)
    for note in snap.risk_notes:
        print(f"  • {note}")
    print()

    print(sub)
    print(f"Audit hash: {snap.audit_hash}")
    print(hr)


def generate_markdown_report(snap: PaperTrackingSnapshot) -> str:
    """Generate the full Markdown report string."""
    bs = snap.bootstrap
    gc = snap.gate_criteria
    p43 = snap.phase43_evidence

    ci_str = (
        f"[{bs.ci_lower:+.4f}, {bs.ci_upper:+.4f}]"
        if bs and bs.ci_lower is not None and bs.ci_upper is not None
        else "N/A"
    )
    p_str = f"{bs.prob_improvement:.1%}" if bs and bs.prob_improvement is not None else "N/A"
    bs_sig = bs.significance if bs else "NOT_RUN"

    def _gate_row(label: str, met: bool) -> str:
        icon = "✅ MET" if met else "❌ NOT MET"
        return f"| {label} | {icon} |"

    gc_rows = ""
    if gc:
        criteria_pairs = [
            (f"sample_size >= {3000:,}", gc.sample_size_met),
            ("Bootstrap CI does not cross 0 (SIGNIFICANT)", gc.bootstrap_significant),
            ("blend_bss consistently > 0", gc.blend_bss_consistently_positive),
            ("ECE not clearly deteriorated (≤ market_ece + 0.01)", gc.ece_not_deteriorated),
            (">= 4/5 folds have positive blend_bss", gc.folds_positive_met),
            ("Human review approved", gc.human_review_approved),
        ]
        gc_rows = "\n".join(_gate_row(label, met) for label, met in criteria_pairs)

    seg_rows = ""
    if snap.segment_summary:
        seg_rows = "\n".join(
            f"| {seg_type} | {cls} |"
            for seg_type, cls in snap.segment_summary.items()
        )

    risk_block = "\n".join(f"- {note}" for note in snap.risk_notes)
    gate_block = "\n".join(f"- {c}" for c in snap.next_gate_criteria)

    p43_blend_bss = p43.get("overall_blend_bss", "N/A")
    p43_raw_bss = p43.get("overall_raw_bss", "N/A")
    p43_blend_brier = p43.get("overall_blend_brier", "N/A")
    p43_market_brier = p43.get("overall_market_brier", "N/A")
    p43_ci = p43.get("bootstrap_ci", ["N/A", "N/A"])
    p43_sig = p43.get("bootstrap_significance", "N/A")
    p43_fold_stab = p43.get("fold_stability", "N/A")
    p43_folds_pos = p43.get("folds_positive", "N/A")
    p43_sample = p43.get("sample_size", "N/A")

    p43_ci_str = f"[{p43_ci[0]:+.4f}, {p43_ci[1]:+.4f}]" if isinstance(p43_ci, list) and len(p43_ci) == 2 and isinstance(p43_ci[0], float) else str(p43_ci)

    report = f"""# Phase 44 — Market Blend Paper-Only Tracking
## Evidence Pack: α=0.4 Strategy (Paper-Only Gate)

**Generated at**: {snap.generated_at}
**Run ID**: `{snap.run_id}`
**Input**: `{snap.input_prediction_path}`
**Audit Hash**: `{snap.audit_hash}`

---

## Executive Summary

| Field | Value |
|-------|-------|
| **Gate State** | `{snap.gate_state}` |
| **Candidate Patch Created** | `{snap.candidate_patch_created}` |
| **Alpha (fixed)** | `{snap.alpha}` |
| **Sample Size** | {snap.sample_size:,} |
| **Date Range** | {snap.date_start} → {snap.date_end} |
| **blend BSS vs Market** | `{snap.blend_bss:+.4f}` |
| **Bootstrap Significance** | `{bs_sig}` |
| **Bootstrap CI (95%)** | `{ci_str}` |
| **Gate Criteria Summary** | `{snap.gate_criteria_summary}` |

> **Why not production?** The α=0.4 market_blend strategy shows a marginal BSS of `{snap.blend_bss:+.4f}` vs market, but the 95% bootstrap CI crosses 0 (`{ci_str}`), confirming the result is statistically NOT SIGNIFICANT. Current sample ({snap.sample_size:,} games) is below the re-evaluation threshold of 3,000. All hard rules are enforced: gate stays PAPER_ONLY, no candidate patch is created.

---

## Phase 43 Evidence Recap

Phase 43 completed on 2026-05-05 with the following findings:

| Metric | Value |
|--------|-------|
| Sample size | {p43_sample:,} |
| Date range | {p43.get("date_range", ["?", "?"])[0]} → {p43.get("date_range", ["?", "?"])[1]} |
| Overall raw BSS | `{p43_raw_bss:+.4f}` |
| Overall blend BSS | `{p43_blend_bss:+.4f}` |
| Overall blend Brier | `{p43_blend_brier:.4f}` |
| Overall market Brier | `{p43_market_brier:.4f}` |
| Fold stability | `{p43_fold_stab}` |
| Folds with positive blend_bss | {p43_folds_pos} / 5 |
| Bootstrap CI (blend vs market) | `{p43_ci_str}` |
| Bootstrap significance | `{p43_sig}` |
| Gate recommendation | `{p43.get("gate_recommendation", "N/A")}` |

**Segment value summary (Phase 43)**:
{chr(10).join(f'- `{k}` → {v}' for k, v in p43.get("segment_value", {}).items())}

---

## Paper-Only Metrics Table (This Run)

| Metric | Raw Model | Market Baseline | Blend (α=0.4) |
|--------|-----------|-----------------|---------------|
| **Brier Score** | {snap.raw_brier:.4f} | {snap.market_brier:.4f} | {snap.blend_brier:.4f} |
| **BSS vs Market** | {snap.raw_bss:+.4f} | — | {snap.blend_bss:+.4f} |
| **ECE** | {snap.raw_ece:.4f} | {snap.market_ece:.4f} | {snap.blend_ece:.4f} |
| **Brier Delta (blend−mkt)** | — | — | {snap.brier_delta:+.4f} |

**Bootstrap CI (blend vs market)**: {ci_str}  ·  Significance: `{bs_sig}`  ·  P(improve): {p_str}

---

## Segment Tracking Table

| Segment Type | Best Value Classification |
|---|---|
{seg_rows}

---

## Next Gate Criteria

The following criteria must ALL be met before re-evaluating the PAPER_ONLY gate:

| Criterion | Current Status |
|-----------|---------------|
{gc_rows}

**Summary**: `{snap.gate_criteria_summary}`

---

## Risk Notes

{risk_block}

---

## Next Gate Criteria (Detail)

{gate_block}

---

## Hard Rules (always enforced)

- `gate_state = PAPER_ONLY` — never changes until ALL gate criteria met
- `candidate_patch_created = False` — never flip
- `alpha = 0.4` — fixed from Phase 42A / Phase 43, no per-fold override
- Do NOT deploy to production without `PATCH_GATE_RECHECK` from BSS Safety Gate
- Bootstrap CI crossing 0 → NOT_SIGNIFICANT → PAPER_ONLY stays
- Best-per-fold alpha (0.1–1.0) is diagnostic only; do NOT use in production

---

*Phase 44 — Market Blend Paper-Only Tracking | Betting-pool quant research*
"""
    return report


def write_report(snap: PaperTrackingSnapshot, report_dir: Path = _REPORT_DIR) -> Path:
    """Write the Markdown report and return the output path."""
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"phase44_market_blend_paper_tracking_{_today()}.md"
    out_path.write_text(generate_markdown_report(snap), encoding="utf-8")
    return out_path


def write_json(snap: PaperTrackingSnapshot, json_dir: Path = _JSON_DIR) -> Path:
    """Write the JSON evidence pack and return the output path."""
    json_dir.mkdir(parents=True, exist_ok=True)
    out_path = json_dir / f"phase44_market_blend_paper_tracking_{_today()}.json"
    out_path.write_text(
        json.dumps(snap.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 44: Market Blend Paper-Only Tracking CLI"
    )
    parser.add_argument("--print", action="store_true", help="Print summary to stdout")
    parser.add_argument("--report", action="store_true", help="Write Markdown report")
    parser.add_argument("--json", action="store_true", help="Write JSON evidence pack")
    parser.add_argument(
        "--rerun-bootstrap",
        action="store_true",
        help="Re-run bootstrap CI from JSONL (slow ~60s)",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Override prediction JSONL path",
    )
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else DEFAULT_PREDICTIONS_PATH
    if not input_path.exists():
        print(f"ERROR: prediction JSONL not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Loading predictions from {input_path} …", file=sys.stderr)
    rows = load_prediction_rows(input_path)
    print(f"Loaded {len(rows):,} rows.", file=sys.stderr)

    snap = run_phase44_tracking(
        rows,
        input_path=str(input_path),
        rerun_bootstrap=args.rerun_bootstrap,
    )

    any_action = args.print or args.report or args.json
    if not any_action or args.print:
        _print_summary(snap)

    if args.report:
        out = write_report(snap)
        print(f"Report written → {out}", file=sys.stderr)

    if args.json:
        out = write_json(snap)
        print(f"JSON written   → {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
