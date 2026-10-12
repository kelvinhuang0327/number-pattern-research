#!/usr/bin/env python3
"""Phase 67 — runner script.

Usage:
    python scripts/run_phase67_context_failure_attribution.py

Reads:
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
    data/mlb_2025/gl2025.txt

Writes:
    reports/phase67_context_failure_attribution_20260506.json
"""
import json
import sys
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.phase67_context_failure_attribution import (
    ALPHA,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    CONTEXT_FEATURE_PROMISING,
    DATA_LIMITED_GATE,
    DIAGNOSTIC_ONLY,
    DIAGNOSTIC_ONLY_SIGNAL,
    OVERFIT_RISK,
    PHASE66_GATE_ANCHOR,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    _DATA_LIMITED_DIMENSIONS,
    _to_dict,
    run_phase67_context_failure_attribution,
    save_result,
)

# ── Paths ──────────────────────────────────────────────────────────────────
_PREDICTIONS_PATH = (
    REPO_ROOT
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_GL2025_PATH = REPO_ROOT / "data/mlb_2025/gl2025.txt"
_OUTPUT_PATH = (
    REPO_ROOT
    / "reports"
    / "phase67_context_failure_attribution_20260506.json"
)


def main() -> None:
    print("[Phase 67] Lineup / Rest / Schedule / Ballpark Context Failure Attribution")
    print(f"[Phase 67] PHASE_VERSION         = {PHASE_VERSION}")
    print(f"[Phase 67] DIAGNOSTIC_ONLY       = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 67] ALPHA                 = {ALPHA}")
    print(f"[Phase 67] CANDIDATE_PATCH_CREATED = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 67] PRODUCTION_MODIFIED   = {PRODUCTION_MODIFIED}")
    print()

    # ── File existence checks ──────────────────────────────────────
    for p in (_PREDICTIONS_PATH, _GL2025_PATH):
        if not p.exists():
            print(f"[Phase 67] ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"[Phase 67] Predictions : {_PREDICTIONS_PATH}")
    print(f"[Phase 67] GL2025      : {_GL2025_PATH}")
    print()
    print("[Phase 67] Running context attribution analysis …")

    result = run_phase67_context_failure_attribution(
        predictions_path=_PREDICTIONS_PATH,
        gl2025_path=_GL2025_PATH,
    )

    # ── Print summary ──────────────────────────────────────────────
    print(f"[Phase 67] n_predictions         = {result.segment_n_all}")
    print(
        f"[Phase 67] context_alignment     = "
        f"{result.context_alignment.n_aligned}/"
        f"{result.context_alignment.n_predictions} "
        f"({result.context_alignment.coverage * 100:.1f}%)"
    )
    print()
    print(f"[Phase 67] segment_n_all         = {result.segment_n_all}")
    print(f"[Phase 67] segment_n_heavy_fav   = {result.segment_n_heavy_fav}")
    print(f"[Phase 67] segment_n_high_conf   = {result.segment_n_high_conf}")
    print(f"[Phase 67] segment_n_extreme     = {result.segment_n_extreme_fav}")
    print(f"[Phase 67] segment_n_phase45_fail= {result.segment_n_phase45_failure}")
    print()
    m = result.all_metrics
    print(
        f"[Phase 67] ALL:       blend_bss_vs_market={m.blend_bss_vs_market:+.4f}"
        f"  fav_win_rate={m.fav_win_rate:.3f}"
        f"  ece_blend={m.ece_blend:.4f}"
    )
    hf = result.heavy_fav_metrics
    print(
        f"[Phase 67] HEAVY_FAV: blend_bss_vs_market={hf.blend_bss_vs_market:+.4f}"
        f"  fav_win_rate={hf.fav_win_rate:.3f}"
        f"  n={result.segment_n_heavy_fav}"
    )
    print()

    # ── Gate decision ──────────────────────────────────────────────
    print("[Phase 67] ═══ GATE DECISION ═══════════════════════════════════════════")
    print(f"[Phase 67] gate              = {result.gate}")
    print(f"[Phase 67] worth_phase68     = {result.worth_phase68}")
    print(f"[Phase 67] any_boot_sig      = {result.any_bootstrap_significant}")
    print(f"[Phase 67] any_oof_promising = {result.any_oof_promising}")
    print(f"[Phase 67] any_overfit_risk  = {result.any_overfit_risk}")
    print(f"[Phase 67] rationale: {result.gate_rationale}")
    print(f"[Phase 67] next_step: {result.next_step}")
    print()

    print(f"[Phase 67] DATA_LIMITED dimensions: {result.data_limited_dimensions}")
    print(f"[Phase 67] DATA_LIMITED fields:     {result.data_limited_fields}")
    print()

    # ── Top attribution buckets (by abs BSS) ──────────────────────
    sorted_buckets = sorted(
        result.attribution_buckets,
        key=lambda b: abs(b.metrics.blend_bss_vs_market),
        reverse=True,
    )[:10]
    print("[Phase 67] Top attribution buckets (by |blend_bss_vs_market|):")
    for b in sorted_buckets:
        print(
            f"  [{b.dim}|{b.bucket_label}]  n={b.n:4d}"
            f"  bss={b.metrics.blend_bss_vs_market:+.4f}"
            f"  sig={b.bootstrap.significant}"
            f"  ci=[{b.bootstrap.ci_lower:.3f},{b.bootstrap.ci_upper:.3f}]"
        )
    print()

    # ── Save report ────────────────────────────────────────────────
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_result(result, _OUTPUT_PATH)
    print(f"[Phase 67] Report saved → {_OUTPUT_PATH}")

    # ── Assertions ────────────────────────────────────────────────
    assert result.candidate_patch_created is False, "SAFETY: patch flag"
    assert result.production_modified is False,     "SAFETY: prod flag"
    assert result.diagnostic_only is True,          "SAFETY: diag flag"
    assert abs(result.alpha - 0.40) < 1e-9,         "SAFETY: alpha 0.40"
    assert result.phase66_gate_anchor == PHASE66_GATE_ANCHOR, "anchor mismatch"
    assert result.context_alignment.coverage >= _MIN_COVERAGE_THRESHOLD, (
        f"Context coverage {result.context_alignment.coverage:.2%} below threshold"
    )
    assert result.gate in {
        "CONTEXT_FEATURE_PROMISING", "DIAGNOSTIC_ONLY_SIGNAL",
        "DATA_LIMITED", "OVERFIT_RISK", "CONTEXT_FEATURE_NOT_PROMISING",
    }, f"Unknown gate: {result.gate}"
    assert result.completion_marker == COMPLETION_MARKER

    print(f"[Phase 67] completion_marker = {result.completion_marker}")
    print(f"[Phase 67] All assertions passed. Gate = {result.gate}")


_MIN_COVERAGE_THRESHOLD = 0.70

if __name__ == "__main__":
    main()
