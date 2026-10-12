"""
scripts/run_phase64b_full_season_bullpen_ingestion_and_attribution.py
======================================================================
Phase 64-B Runner — Full-Season Bullpen Ingestion + Attribution

執行步驟：
  1. 安全常數驗證
  2. Full-season ingestion（從 bullpen_usage_3d.jsonl 建構全季 SSOT）
  3. Phase 64-B Attribution（特徵覆蓋率 + bucket 分析 + OOF + gate 決策）
  4. 產出 JSON 報告至 reports/

安全約束：
  CANDIDATE_PATCH_CREATED = False
  PRODUCTION_MODIFIED     = False
  ALPHA_MODIFIED          = False
  DIAGNOSTIC_ONLY         = True
  ALPHA                   = 0.40

完成標記：PHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from orchestrator.phase64b_full_season_attribution import (
    ALPHA,
    ALPHA_MODIFIED,
    BULLPEN_GRANULAR_FEATURE_NOT_PROMISING,
    BULLPEN_GRANULAR_FEATURE_PROMISING,
    CANDIDATE_PATCH_CREATED,
    DATA_LIMITED,
    DIAGNOSTIC_ONLY,
    DIAGNOSTIC_ONLY_SIGNAL,
    OVERFIT_RISK,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    run_phase64b_attribution,
)
from wbc_backend.features.mlb_bullpen_full_season_ingestion import (
    MODULE_VERSION,
    run_full_season_ingestion,
)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
_PRED_PATH = str(
    _ROOT / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_BULL_3D_PATH = str(_ROOT / "data/mlb_context/bullpen_usage_3d.jsonl")
_PHASE63_SSOT_PATH = str(_ROOT / "reports/phase63_bullpen_ssot_features_20260506.jsonl")
_OUTPUT_DIR = str(_ROOT / "reports")

_SSOT_OUTPUT = str(_ROOT / "reports/phase64b_bullpen_ssot_features_20260506.jsonl")
_APPEARANCES_OUTPUT = str(_ROOT / "reports/phase64b_bullpen_relief_appearances_20260506.jsonl")
_INGESTION_SUMMARY_OUTPUT = str(_ROOT / "reports/phase64b_full_season_ingestion_summary_20260506.json")
_ATTRIBUTION_OUTPUT = str(_ROOT / "reports/phase64b_full_season_bullpen_ingestion_and_attribution_20260506.json")


# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------

def _validate_safety() -> None:
    """Assert all safety constants are correct before running."""
    errors = []
    if CANDIDATE_PATCH_CREATED:
        errors.append("CANDIDATE_PATCH_CREATED must be False")
    if PRODUCTION_MODIFIED:
        errors.append("PRODUCTION_MODIFIED must be False")
    if ALPHA_MODIFIED:
        errors.append("ALPHA_MODIFIED must be False")
    if not DIAGNOSTIC_ONLY:
        errors.append("DIAGNOSTIC_ONLY must be True")
    if abs(ALPHA - 0.40) > 1e-9:
        errors.append(f"ALPHA must be 0.40, got {ALPHA}")
    if errors:
        print("[SAFETY VIOLATION]", "; ".join(errors))
        sys.exit(1)
    print("[SAFETY] All constants verified OK")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print(f"Phase 64-B Full-Season Bullpen Ingestion + Attribution")
    print(f"  phase_version: {PHASE_VERSION}")
    print(f"  ingestion_module: {MODULE_VERSION}")
    print("=" * 70)

    # Step 1: Safety validation
    _validate_safety()

    # Step 2: Full-season ingestion
    print("\n[1/4] Running full-season ingestion (artifact-first, dry_run=True)...")
    ingestion_summary = run_full_season_ingestion(
        bull_3d_path=_BULL_3D_PATH,
        phase63_ssot_path=_PHASE63_SSOT_PATH,
        ssot_output_path=_SSOT_OUTPUT,
        appearances_output_path=_APPEARANCES_OUTPUT,
        dry_run=True,
    )
    print(f"  bull_3d rows        : {ingestion_summary.n_bull_3d_rows}")
    print(f"  parseable games     : {ingestion_summary.n_parseable_games}")
    print(f"  team artifacts      : {ingestion_summary.n_team_artifacts}")
    print(f"  3d available        : {ingestion_summary.n_3d_available}")
    print(f"  1d available        : {ingestion_summary.n_1d_available} (DATA_LIMITED)")
    print(f"  phase63 consistent  : {ingestion_summary.n_phase63_consistent}/{ingestion_summary.n_phase63_artifacts}")
    print(f"  coverage_rate_3d    : {ingestion_summary.coverage_rate_3d:.1%}")
    print(f"  ready_for_attribution: {ingestion_summary.ready_for_attribution}")
    print(f"  → SSOT written      : {_SSOT_OUTPUT}")
    print(f"  → appearances written: {_APPEARANCES_OUTPUT}")

    # Write ingestion summary JSON
    Path(_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    ingestion_dict = {
        **vars(ingestion_summary),
        "phase64b_ingestion_verified": True,
    }
    with open(_INGESTION_SUMMARY_OUTPUT, "w") as f:
        json.dump(ingestion_dict, f, indent=2, default=str)
    print(f"  → summary written   : {_INGESTION_SUMMARY_OUTPUT}")

    # Step 3: Phase 64-B Attribution
    print("\n[2/4] Running Phase 64-B attribution...")
    result = run_phase64b_attribution(
        predictions_path=_PRED_PATH,
        bull_3d_path=_BULL_3D_PATH,
        ssot_output_path=_SSOT_OUTPUT,
    )

    print(f"  n_predictions       : {result.n_predictions}")
    print(f"  n_ssot_artifacts    : {result.n_ssot_artifacts}")
    print(f"  n_bull_3d_rows      : {result.n_bull_3d_rows}")
    print(f"  n_aligned_3d        : {result.alignment.n_aligned_3d}")
    print(f"  alignment_rate      : {result.alignment.alignment_rate:.1%}")
    print(f"  coverage_sufficient : {result.alignment.coverage_sufficient}")
    print(f"  n_available_features: {result.n_available_features}")
    print(f"  n_data_limited      : {result.n_data_limited_features}")

    # Step 4: Print gate chain
    print("\n[3/4] Gate chain:")
    print(f"  phase64_gate        : {result.phase64_gate}")
    print(f"  phase64b_gate       : {result.gate}")
    print(f"  any_bootstrap_sig   : {result.any_bootstrap_significant}")

    if result.phase60_baseline_replication.get("status") == "REPLICATED":
        rep = result.phase60_baseline_replication
        print(f"\n  Phase60 Baseline Replication:")
        print(f"    n_all_aligned   : {rep['n_all_aligned']}")
        print(f"    n_heavy_fav     : {rep['n_heavy_fav']}")
        print(f"    brier           : {rep['brier']}")
        print(f"    bss             : {rep['bss']}")
        ba = rep.get("heavy_fav_bucket_attribution")
        if ba:
            print(f"    heavy_fav delta : {ba['win_rate_delta']:+.4f}")
            print(f"    CI              : [{ba['bootstrap_ci_lower']:+.4f}, {ba['bootstrap_ci_upper']:+.4f}]")
            print(f"    significant     : {ba['bootstrap_significant']}")

    # Feature coverage summary
    print("\n  Feature Coverage:")
    for cov in result.feature_coverage:
        tag = "✓" if not cov.data_limited else "✗ DATA_LIMITED"
        print(f"    {cov.feature_name:40s}: {cov.coverage_pct:.1%} [{tag}]")

    # Attribution summary for available features
    avail_attrs = [a for a in result.attributions
                   if not a.data_limited and a.segment == "heavy_favorite"]
    if avail_attrs:
        print("\n  Heavy_fav Attributions (available features):")
        for attr in avail_attrs:
            ba = attr.bucket_attribution
            if ba:
                sig_tag = "*** SIGNIFICANT ***" if ba.bootstrap_significant else ""
                print(f"    {attr.feature_name:40s}: delta={ba.win_rate_delta:+.4f} "
                      f"CI=[{ba.bootstrap_ci_lower:+.4f},{ba.bootstrap_ci_upper:+.4f}] "
                      f"n={ba.n_high+ba.n_low} {sig_tag}")

    # OOF summary
    if result.oof_results:
        print("\n  OOF Summary:")
        for oof in result.oof_results:
            print(f"    {oof.feature_name:40s}: n_folds={oof.n_folds} "
                  f"mean_delta={oof.oof_mean_delta:+.4f} "
                  f"consistent={oof.oof_consistent_sign} "
                  f"significant={oof.oof_significant}")

    print(f"\n[4/4] GATE: {result.gate}")
    print(f"  Rationale: {result.gate_rationale}")
    print(f"  Next step: {result.next_step}")
    print(f"\n  Completion marker: {result.completion_marker}")

    # Write attribution JSON
    result_dict = asdict(result)
    with open(_ATTRIBUTION_OUTPUT, "w") as f:
        json.dump(result_dict, f, indent=2, default=str)
    print(f"\n  → Attribution JSON : {_ATTRIBUTION_OUTPUT}")

    # Final assertion
    valid_gates = {
        BULLPEN_GRANULAR_FEATURE_PROMISING,
        DIAGNOSTIC_ONLY_SIGNAL,
        DATA_LIMITED,
        OVERFIT_RISK,
        BULLPEN_GRANULAR_FEATURE_NOT_PROMISING,
    }
    assert result.gate in valid_gates, f"Invalid gate: {result.gate}"
    assert result.completion_marker == "PHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED"
    assert not result.candidate_patch_created
    assert not result.production_modified
    assert not result.alpha_modified
    assert result.diagnostic_only

    print("\nPHASE_64B_FULL_SEASON_BULLPEN_INGESTION_ATTRIBUTION_VERIFIED")


if __name__ == "__main__":
    main()
