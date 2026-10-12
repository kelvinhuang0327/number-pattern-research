"""
scripts/run_phase65_sp_fatigue_attribution.py
=============================================
Phase 65 — SP Fatigue Attribution Runner

執行 Phase 65 SP 疲勞歸因分析並輸出 JSON 診斷報告。

Usage:
    python scripts/run_phase65_sp_fatigue_attribution.py

輸出：
    reports/phase65_sp_fatigue_attribution_YYYYMMDD.json

安全常數快照：
    CANDIDATE_PATCH_CREATED = False
    PRODUCTION_MODIFIED     = False
    ALPHA_MODIFIED          = False
    DIAGNOSTIC_ONLY         = True
    ALPHA                   = 0.40
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

# ── 確保 project root 在 sys.path ─────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from orchestrator.phase65_sp_fatigue_attribution import (
    ALPHA,
    CANDIDATE_PATCH_CREATED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    SP_FATIGUE_FEATURE_NOT_PROMISING,
    SP_FATIGUE_FEATURE_PROMISING,
    DATA_LIMITED,
    DIAGNOSTIC_ONLY_SIGNAL,
    OVERFIT_RISK,
    run_phase65_sp_fatigue_attribution,
)

# ── 路徑設定 ────────────────────────────────────────────────────────────────────
_PREDICTIONS_PATH = str(
    _ROOT / "data" / "mlb_2025" / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_ASPLAYED_PATH = str(_ROOT / "data" / "mlb_2025" / "mlb-2025-asplayed.csv")
_REPORT_DATE = date.today().strftime("%Y%m%d")
_REPORT_PATH = str(_ROOT / "reports" / f"phase65_sp_fatigue_attribution_{_REPORT_DATE}.json")

# ── Gate 顯示映射 ────────────────────────────────────────────────────────────────
_GATE_EMOJI = {
    SP_FATIGUE_FEATURE_PROMISING:     "🟢",
    DIAGNOSTIC_ONLY_SIGNAL:           "🟡",
    DATA_LIMITED:                     "🔴",
    OVERFIT_RISK:                     "🔴",
    SP_FATIGUE_FEATURE_NOT_PROMISING: "⚪",
}


def main() -> int:
    print("=" * 70)
    print("Phase 65 — SP Fatigue Attribution")
    print(f"  phase_version: {PHASE_VERSION}")
    print(f"  predictions:   {_PREDICTIONS_PATH}")
    print(f"  asplayed:      {_ASPLAYED_PATH}")
    print("=" * 70)

    # ── 安全常數快照 ────────────────────────────────────────────────────────────
    print("\n[Safety Constants]")
    print(f"  CANDIDATE_PATCH_CREATED = {CANDIDATE_PATCH_CREATED}")
    print(f"  PRODUCTION_MODIFIED     = {PRODUCTION_MODIFIED}")
    print(f"  ALPHA_MODIFIED          = {ALPHA_MODIFIED}")
    print(f"  DIAGNOSTIC_ONLY         = {DIAGNOSTIC_ONLY}")
    print(f"  ALPHA                   = {ALPHA}")
    assert not CANDIDATE_PATCH_CREATED
    assert not PRODUCTION_MODIFIED
    assert not ALPHA_MODIFIED
    assert DIAGNOSTIC_ONLY
    assert ALPHA == 0.40

    # ── 執行 attribution ────────────────────────────────────────────────────────
    print("\n[Running Phase 65 SP Fatigue Attribution...]")
    result = run_phase65_sp_fatigue_attribution(
        predictions_path=_PREDICTIONS_PATH,
        asplayed_path=_ASPLAYED_PATH,
    )

    # ── 顯示摘要 ────────────────────────────────────────────────────────────────
    print("\n[SP Start History]")
    h = result.sp_start_history
    print(f"  asplayed rows:    {h.n_asplayed_rows}")
    print(f"  unique pitchers:  {h.n_unique_pitchers}")
    print(f"  multi-start SPs:  {h.n_pitchers_with_multiple_starts}")
    print(f"  date range:       {h.date_range_start} → {h.date_range_end}")

    print("\n[Alignment]")
    al = result.alignment
    print(f"  predictions:       {al.n_predictions}")
    print(f"  home rest aligned: {al.n_aligned_home_rest} ({al.home_rest_coverage:.1%})")
    print(f"  away rest aligned: {al.n_aligned_away_rest} ({al.away_rest_coverage:.1%})")
    print(f"  both aligned:      {al.n_both_aligned} ({al.both_coverage:.1%})")
    print(f"  coverage_sufficient: {al.coverage_sufficient}")

    print("\n[Feature Coverage]")
    print(f"  AVAILABLE:    {result.n_available_features}")
    print(f"  DATA_LIMITED: {result.n_data_limited_features}")
    for cov in result.feature_coverage:
        status = "DATA_LIMITED" if cov.data_limited else f"{cov.coverage_pct:.1%}"
        print(f"    {cov.feature_name:<45} {status}")

    print("\n[Segment Sizes]")
    print(f"  all:            {result.segment_n_all}")
    print(f"  heavy_favorite: {result.segment_n_heavy_fav}")
    print(f"  high_confidence:{result.segment_n_high_conf}")

    print("\n[Attribution Summary (available features × heavy_fav)]")
    for attr in result.attributions:
        if attr.segment != "heavy_favorite" or attr.data_limited:
            continue
        ba = attr.bucket_attribution
        if ba:
            sig = "★SIGNIFICANT★" if ba.bootstrap_significant else ""
            print(
                f"  {attr.feature_name:<40} "
                f"Δ={ba.win_rate_delta:+.4f} "
                f"CI=[{ba.ci_lower if hasattr(ba,'ci_lower') else ba.bootstrap_ci_lower:.4f},"
                f"{ba.ci_upper if hasattr(ba,'ci_upper') else ba.bootstrap_ci_upper:.4f}] "
                f"n_high={ba.n_high} n_low={ba.n_low} {sig}"
            )
        else:
            print(f"  {attr.feature_name:<40} n={attr.n} (insufficient or no bucket attr)")

    print("\n[OOF Summary (available features × heavy_fav)]")
    for oof in result.oof_results:
        sig = "★" if oof.oof_significant and oof.oof_consistent_sign else ""
        print(
            f"  {oof.feature_name:<40} "
            f"mean_Δ={oof.oof_mean_delta:+.4f} "
            f"folds={oof.n_folds} "
            f"consistent={oof.oof_consistent_sign} {sig}"
        )

    print("\n[Negative Controls (heavy_fav)]")
    for nc in result.negative_controls:
        flag = "⚠OVERFIT" if nc.overfit_risk else ("null_rejected" if nc.null_rejected else "OK")
        print(
            f"  {nc.feature_name:<40} "
            f"real={nc.real_win_rate_delta:+.4f} "
            f"shuf_mean={nc.shuffled_mean_delta:+.4f} "
            f"std={nc.shuffled_std_delta:.4f} {flag}"
        )

    emoji = _GATE_EMOJI.get(result.gate, "❓")
    print(f"\n{'='*70}")
    print(f"GATE: {emoji} {result.gate}")
    print(f"  {result.gate_rationale}")
    print(f"\nNext step: {result.next_step}")
    print(f"Worth Phase 66: {result.worth_phase66}")
    print(f"Completion marker: {result.completion_marker}")
    print("=" * 70)

    # ── 輸出 JSON ────────────────────────────────────────────────────────────────
    report = asdict(result)
    Path(_REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[Report saved] → {_REPORT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
