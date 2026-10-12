#!/usr/bin/env python3
"""
scripts/run_phase66_market_microstructure_failure_attribution.py
================================================================
Phase 66 runner — Market Microstructure Failure Attribution for Heavy Favorites

執行方式：
    python scripts/run_phase66_market_microstructure_failure_attribution.py

輸出：
    reports/phase66_market_microstructure_failure_attribution_20260506.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator.phase66_market_microstructure_failure_attribution import (
    run_phase66_market_microstructure_failure_attribution,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    ALPHA,
    PHASE_VERSION,
    _PHASE65_GATE,
    _DATA_LIMITED_DIMENSIONS,
    _DATA_LIMITED_FIELDS,
)

_PREDICTIONS_PATH = str(
    _REPO_ROOT / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_ODDS_CSV_PATH = str(_REPO_ROOT / "data/mlb_2025/mlb_odds_2025_real.csv")
_REPORT_DIR = _REPO_ROOT / "reports"
_REPORT_PATH = _REPORT_DIR / "phase66_market_microstructure_failure_attribution_20260506.json"


def _assert_safety() -> None:
    assert not CANDIDATE_PATCH_CREATED, "SAFETY: CANDIDATE_PATCH_CREATED must be False"
    assert not PRODUCTION_MODIFIED, "SAFETY: PRODUCTION_MODIFIED must be False"
    assert not ALPHA_MODIFIED, "SAFETY: ALPHA_MODIFIED must be False"
    assert DIAGNOSTIC_ONLY, "SAFETY: DIAGNOSTIC_ONLY must be True"
    assert ALPHA == 0.40, f"SAFETY: ALPHA must be 0.40, got {ALPHA}"
    assert _PHASE65_GATE == "OVERFIT_RISK", f"SAFETY: phase65 gate anchor mismatch"


def main() -> int:
    print(f"[Phase 66] Market Microstructure Failure Attribution")
    print(f"[Phase 66] PHASE_VERSION = {PHASE_VERSION}")
    print(f"[Phase 66] DIAGNOSTIC_ONLY = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 66] ALPHA = {ALPHA}")
    print(f"[Phase 66] CANDIDATE_PATCH_CREATED = {CANDIDATE_PATCH_CREATED}")
    print()

    # Safety gate
    _assert_safety()
    print("[Phase 66] Safety constants verified OK")

    # Check inputs
    for path, label in [(_PREDICTIONS_PATH, "predictions"), (_ODDS_CSV_PATH, "odds CSV")]:
        if not Path(path).exists():
            print(f"[Phase 66] ERROR: {label} not found: {path}", file=sys.stderr)
            return 1
    print(f"[Phase 66] Predictions: {_PREDICTIONS_PATH}")
    print(f"[Phase 66] Odds CSV: {_ODDS_CSV_PATH}")
    print()

    # Run attribution
    print("[Phase 66] Running attribution analysis …")
    result = run_phase66_market_microstructure_failure_attribution(
        predictions_path=_PREDICTIONS_PATH,
        odds_csv_path=_ODDS_CSV_PATH,
    )

    # Summaries
    print(f"[Phase 66] n_predictions       = {result.n_predictions}")
    print(f"[Phase 66] odds_alignment       = {result.odds_alignment.n_aligned}/{result.odds_alignment.n_predictions} "
          f"({result.odds_alignment.coverage:.1%})")
    print()
    print(f"[Phase 66] segment_n_all        = {result.segment_n_all}")
    print(f"[Phase 66] segment_n_heavy_fav  = {result.segment_n_heavy_fav}")
    print(f"[Phase 66] segment_n_high_conf  = {result.segment_n_high_conf}")
    print(f"[Phase 66] segment_n_extreme    = {result.segment_n_extreme_fav}")
    print(f"[Phase 66] segment_n_phase45_fail = {result.segment_n_phase45_failure}")
    print()

    # Key metrics
    am = result.all_metrics
    hf = result.heavy_fav_metrics
    print(f"[Phase 66] ALL:       blend_bss_vs_market={am.blend_bss_vs_market:+.4f}  "
          f"fav_win_rate={am.fav_win_rate:.3f}  ece_blend={am.blend_ece:.4f}")
    print(f"[Phase 66] HEAVY_FAV: blend_bss_vs_market={hf.blend_bss_vs_market:+.4f}  "
          f"fav_win_rate={hf.fav_win_rate:.3f}  n={hf.n}")
    print()

    # Gate
    print(f"[Phase 66] ═══ GATE DECISION ═══════════════════════════════════════════")
    print(f"[Phase 66] gate             = {result.gate}")
    print(f"[Phase 66] worth_phase67    = {result.worth_phase67}")
    print(f"[Phase 66] any_boot_sig     = {result.any_bootstrap_significant}")
    print(f"[Phase 66] any_oof_promising= {result.any_oof_promising}")
    print(f"[Phase 66] any_overfit_risk = {result.any_overfit_risk}")
    print(f"[Phase 66] rationale: {result.gate_rationale}")
    print(f"[Phase 66] next_step: {result.next_step}")
    print()

    # DATA_LIMITED info
    print(f"[Phase 66] DATA_LIMITED dimensions: {result.data_limited_dimensions}")
    print(f"[Phase 66] DATA_LIMITED fields:     {result.data_limited_fields}")
    print()

    # Completion marker
    print(f"[Phase 66] completion_marker = {result.completion_marker}")

    # Serialize and save
    def _serialise(obj: object) -> object:
        if hasattr(obj, "__dict__"):
            return asdict(obj)  # type: ignore[arg-type]
        return str(obj)

    result_dict = asdict(result)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_REPORT_PATH, "w") as f:
        json.dump(result_dict, f, indent=2, default=str)
    print(f"[Phase 66] Report saved → {_REPORT_PATH}")

    # Safety assertion on saved report
    assert result_dict["candidate_patch_created"] is False
    assert result_dict["production_modified"] is False
    assert result_dict["alpha"] == 0.40
    assert result_dict["completion_marker"] == "PHASE_66_MARKET_MICROSTRUCTURE_FAILURE_ATTRIBUTION_VERIFIED"

    print(f"[Phase 66] All assertions passed. Gate = {result.gate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
