#!/usr/bin/env python3
"""
scripts/run_phase64_granular_bullpen_attribution.py
===================================================
Phase 64 — Granular Bullpen Attribution runner script.

Usage:
    python scripts/run_phase64_granular_bullpen_attribution.py

輸出 artifacts:
    reports/phase64_granular_bullpen_attribution_20260506.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# 確保 project root 在 path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_PROJECT_ROOT))

from orchestrator.phase64_granular_bullpen_attribution import (
    PHASE_VERSION,
    DIAGNOSTIC_ONLY,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    run_phase64_attribution,
)

# ---------------------------------------------------------------------------
# 路徑設定
# ---------------------------------------------------------------------------
PREDICTIONS_PATH = str(
    _PROJECT_ROOT / "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
BULLPEN_3D_PATH = str(_PROJECT_ROOT / "data/mlb_context/bullpen_usage_3d.jsonl")
PHASE63_SSOT_PATH = str(_PROJECT_ROOT / "reports/phase63_bullpen_ssot_features_20260506.jsonl")
PHASE63_APPEARANCES_PATH = str(
    _PROJECT_ROOT / "reports/phase63_bullpen_relief_appearances_20260506.jsonl"
)
PHASE63_REPORT_PATH = str(
    _PROJECT_ROOT / "reports/phase63_statsapi_bullpen_granular_ingestion_20260506.json"
)

RUN_DATE = "20260506"
OUTPUT_JSON = str(_PROJECT_ROOT / f"reports/phase64_granular_bullpen_attribution_{RUN_DATE}.json")


def _safe_val(v: object) -> object:
    """Convert non-serialisable values for JSON output."""
    if v is None:
        return None
    if isinstance(v, float):
        if v != v:  # nan
            return None
        return v
    return v


def _sanitize_dict(d: dict) -> dict:
    """Recursively sanitize dict for JSON serialisation."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _sanitize_dict(x) if isinstance(x, dict) else _safe_val(x)
                for x in v
            ]
        else:
            result[k] = _safe_val(v)
    return result


def main() -> None:
    print(f"[Phase64] Starting attribution run — {PHASE_VERSION}")
    print(f"[Phase64] DIAGNOSTIC_ONLY={DIAGNOSTIC_ONLY}")
    print(f"[Phase64] CANDIDATE_PATCH_CREATED={CANDIDATE_PATCH_CREATED}")
    print(f"[Phase64] PRODUCTION_MODIFIED={PRODUCTION_MODIFIED}")
    print()

    # Validate safety constants
    assert CANDIDATE_PATCH_CREATED is False, "CANDIDATE_PATCH_CREATED must be False!"
    assert PRODUCTION_MODIFIED is False, "PRODUCTION_MODIFIED must be False!"
    assert ALPHA_MODIFIED is False, "ALPHA_MODIFIED must be False!"
    assert DIAGNOSTIC_ONLY is True, "DIAGNOSTIC_ONLY must be True!"

    print(f"[Phase64] Loading predictions: {Path(PREDICTIONS_PATH).name}")
    print(f"[Phase64] Loading bullpen 3d: {Path(BULLPEN_3D_PATH).name}")
    print(f"[Phase64] Loading Phase63 SSOT: {Path(PHASE63_SSOT_PATH).name}")
    print(f"[Phase64] Loading Phase63 appearances: {Path(PHASE63_APPEARANCES_PATH).name}")
    print(f"[Phase64] Loading Phase63 report: {Path(PHASE63_REPORT_PATH).name}")
    print()

    # Run attribution
    result = run_phase64_attribution(
        predictions_path=PREDICTIONS_PATH,
        bullpen_3d_path=BULLPEN_3D_PATH,
        phase63_ssot_path=PHASE63_SSOT_PATH,
        phase63_appearances_path=PHASE63_APPEARANCES_PATH,
        phase63_report_path=PHASE63_REPORT_PATH,
    )

    print("[Phase64] Attribution complete.")
    print(f"  n_predictions       = {result.n_predictions}")
    print(f"  n_bullpen_3d_rows   = {result.n_bullpen_3d_rows}")
    print(f"  n_phase63_ssot      = {result.n_phase63_ssot_artifacts}")
    print(f"  n_aligned_3d        = {result.n_aligned_3d}")
    print(f"  phase63_alignment   = {result.phase63_alignment.n_game_alignments} games "
          f"({result.phase63_alignment.alignment_rate_partial:.1%} partial, "
          f"{result.phase63_alignment.n_fully_aligned} fully aligned)")
    print(f"  n_available_features   = {result.n_available_features}")
    print(f"  n_data_limited_features= {result.n_data_limited_features}")
    print()
    print(f"  Segment sizes:")
    print(f"    all            = {result.segment_n_all}")
    print(f"    heavy_fav      = {result.segment_n_heavy_fav}")
    print(f"    high_conf      = {result.segment_n_high_conf}")
    print(f"    phase45_failure= {result.segment_n_phase45_failure}")
    print()
    print(f"  Phase60 baseline replication: {result.phase60_baseline_replication.get('status')}")
    print(f"  any_bootstrap_significant = {result.any_bootstrap_significant}")
    print()
    print(f"  GATE: {result.gate}")
    print(f"  Rationale: {result.gate_rationale[:120]}...")
    print(f"  Next step: {result.next_step[:100]}...")
    print()

    # Feature coverage summary
    print("[Phase64] Feature Coverage:")
    for fc in result.feature_coverage:
        status = "DATA_LIMITED" if fc.data_limited else "AVAILABLE"
        print(f"  {fc.feature_name:<42} [{status:>12}] {fc.n_available}/{fc.n_total} "
              f"({fc.coverage_pct:.1%})")

    print()

    # Serialise result to JSON
    result_dict = asdict(result)
    result_dict_clean = _sanitize_dict(result_dict)

    output_path = Path(OUTPUT_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result_dict_clean, f, indent=2, ensure_ascii=False)

    print(f"[Phase64] JSON artifact written: {output_path}")

    # Safety assertions before declaring success
    assert result.candidate_patch_created is False, "Safety: CANDIDATE_PATCH_CREATED"
    assert result.production_modified is False, "Safety: PRODUCTION_MODIFIED"
    assert result.alpha_modified is False, "Safety: ALPHA_MODIFIED"
    assert result.diagnostic_only is True, "Safety: DIAGNOSTIC_ONLY"

    print()
    print("=" * 60)
    print("PHASE_64_GRANULAR_BULLPEN_ATTRIBUTION_VERIFIED")
    print("=" * 60)
    print(f"Gate: {result.gate}")


if __name__ == "__main__":
    main()
