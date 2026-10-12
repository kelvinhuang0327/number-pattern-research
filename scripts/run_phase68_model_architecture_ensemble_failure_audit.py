#!/usr/bin/env python3
"""Phase 68 — runner script.

Usage:
    python scripts/run_phase68_model_architecture_ensemble_failure_audit.py

Reads:
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl

Writes:
    reports/phase68_model_architecture_ensemble_failure_audit_20260506.json
"""
import json
import sys
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
    ALPHA,
    ALPHA_MODIFIED,
    ABSTENTION_GUARD_PROMISING,
    CALIBRATION_OBJECTIVE_REDESIGN_PROMISING,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
    MODEL_ARCHITECTURE_NOT_PROMISING,
    MODEL_ARCHITECTURE_REPAIR_PROMISING,
    OVERFIT_RISK,
    PHASE67_GATE_ANCHOR,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    _VALID_GATES,
    _to_dict,
    run_phase68_model_architecture_ensemble_failure_audit,
)

# ── Paths ──────────────────────────────────────────────────────────────────
_PREDICTIONS_PATH = (
    REPO_ROOT
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_OUTPUT_PATH = (
    REPO_ROOT
    / "reports"
    / "phase68_model_architecture_ensemble_failure_audit_20260506.json"
)


def main() -> None:
    print("[Phase 68] Model Architecture and Ensemble Failure Audit")
    print(f"[Phase 68] PHASE_VERSION           = {PHASE_VERSION}")
    print(f"[Phase 68] DIAGNOSTIC_ONLY         = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 68] ALPHA                   = {ALPHA}")
    print(f"[Phase 68] CANDIDATE_PATCH_CREATED = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 68] PRODUCTION_MODIFIED     = {PRODUCTION_MODIFIED}")
    print(f"[Phase 68] ALPHA_MODIFIED          = {ALPHA_MODIFIED}")
    print(f"[Phase 68] PHASE67_GATE_ANCHOR     = {PHASE67_GATE_ANCHOR}")
    print()

    # ── Safety guard ──────────────────────────────────────────────
    assert CANDIDATE_PATCH_CREATED is False, "SAFETY: candidate patch flag must be False"
    assert PRODUCTION_MODIFIED is False,     "SAFETY: production modified flag must be False"
    assert ALPHA_MODIFIED is False,          "SAFETY: alpha modified flag must be False"
    assert DIAGNOSTIC_ONLY is True,          "SAFETY: diagnostic only flag must be True"
    assert abs(ALPHA - 0.40) < 1e-9,        "SAFETY: alpha must be 0.40"
    print("[Phase 68] Safety constants verified ✓")

    # ── Verify input ──────────────────────────────────────────────
    if not _PREDICTIONS_PATH.exists():
        print(f"[Phase 68] ERROR: predictions not found: {_PREDICTIONS_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"[Phase 68] predictions: {_PREDICTIONS_PATH}")
    print(f"[Phase 68] output:      {_OUTPUT_PATH}")
    print()

    # ── Run audit ─────────────────────────────────────────────────
    print("[Phase 68] Running audit (bootstrap n=1000)…")
    report = run_phase68_model_architecture_ensemble_failure_audit(
        predictions_path=_PREDICTIONS_PATH,
        n_boot=1000,
        rng_seed=42,
    )

    # ── Print summary ──────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  n_predictions    : {report.n_predictions}")
    print(f"  feature_version  : {report.feature_version}")
    print()
    print("  ALL GAMES:")
    m = report.all_metrics
    print(f"    model_brier    : {m.model_brier:.4f}")
    print(f"    market_brier   : {m.market_brier:.4f}")
    print(f"    blend_brier    : {m.blend_brier:.4f}")
    print(f"    blend_bss_vs_mkt: {m.blend_bss_vs_market:+.4f}")
    print(f"    fav_win_rate   : {m.fav_win_rate:.4f}")
    print(f"    ece_blend      : {m.ece_blend:.4f}")
    print()
    print("  HEAVY FAV (>= 0.70):")
    h = report.heavy_fav_metrics
    print(f"    n              : {h.n}")
    print(f"    model_brier    : {h.model_brier:.4f}")
    print(f"    market_brier   : {h.market_brier:.4f}")
    print(f"    blend_brier    : {h.blend_brier:.4f}")
    print(f"    blend_bss_vs_mkt: {h.blend_bss_vs_market:+.4f}")
    print(f"    model_bss_vs_mkt: {h.model_bss_vs_market:+.4f}")
    print(f"    fav_win_rate   : {h.fav_win_rate:.4f}")
    print()
    print("  CALIBRATION RESIDUALS (blend fav_prob bands):")
    for b in report.calibration_bands_blend:
        flag = " ← OVERCONF" if b.is_overconfident else (" ← UNDERCONF" if b.is_underconfident else "")
        print(f"    {b.band_label}: n={b.n:4d} pred={b.blend_pred:.4f} actual={b.actual_win_rate:.4f} "
              f"residual={b.residual:+.4f}{flag}")
    print()
    print("  DISAGREEMENT ANALYSIS:")
    for d in report.disagreement_buckets:
        flag = " ← mkt>blend" if d.market_beats_blend else ""
        print(f"    {d.bucket_label:18s}: n={d.n:4d} model={d.model_brier:.4f} "
              f"mkt={d.market_brier:.4f} blend={d.blend_brier:.4f}{flag}")
    print()
    print("  ARCHITECTURE INSTABILITY:")
    ai = report.architecture_instability
    print(f"    n_model_versions: {ai.n_model_versions}")
    print(f"    w_market_cv     : {ai.w_market_cv:.4f}  (instability={ai.instability_detected})")
    print(f"    w_elo_cv        : {ai.w_elo_cv:.4f}")
    print()
    print("  ENSEMBLE SHARPNESS:")
    es = report.ensemble_sharpness
    print(f"    model  : {es.model_mean_fav_prob:.4f} ± {es.model_std_fav_prob:.4f}")
    print(f"    market : {es.market_mean_fav_prob:.4f} ± {es.market_std_fav_prob:.4f}")
    print(f"    blend  : {es.blend_mean_fav_prob:.4f} ± {es.blend_std_fav_prob:.4f}")
    print(f"    model_less_sharp_than_market: {es.model_less_sharp_than_market}")
    print()
    print("  BLEND DILUTION:")
    for c in report.blend_dilution_checks:
        if c.n >= 15:
            flag = " ← DILUTION" if c.dilution_detected else ""
            print(f"    {c.segment:20s}: n={c.n:4d} mkt={c.market_brier:.4f} "
                  f"blend={c.blend_brier:.4f} mag={c.dilution_magnitude:+.4f}{flag}")
    print()
    print("  NEGATIVE CONTROLS:")
    for nc in report.negative_controls:
        flag = " ← OVERFIT RISK" if nc.overfit_risk else ""
        print(f"    {nc.control_name:35s}: real_bss={nc.real_bss:+.4f} "
              f"null_mean={nc.null_bss_mean:+.4f} gap={nc.signal_gap:+.4f}{flag}")
    print()
    print("  SUMMARY FLAGS:")
    print(f"    calibration_overconfidence_detected : {report.calibration_overconfidence_detected}")
    print(f"    calibration_underconfidence_detected: {report.calibration_underconfidence_detected}")
    print(f"    blend_dilution_heavy_fav            : {report.blend_dilution_heavy_fav}")
    print(f"    architecture_instability_detected   : {report.architecture_instability_detected}")
    print(f"    overfit_risk_detected               : {report.overfit_risk_detected}")
    print(f"    worth_phase69                       : {report.worth_phase69}")
    print()
    print(f"  GATE : {report.gate}")
    print(f"  RATIONALE: {report.gate_rationale}")
    print(f"  NEXT STEP: {report.next_step}")
    print("=" * 60)

    # ── Gate assertion ────────────────────────────────────────────
    assert report.gate in _VALID_GATES, f"Invalid gate: {report.gate}"
    assert report.completion_marker == "PHASE_68_MODEL_ARCHITECTURE_ENSEMBLE_FAILURE_AUDIT_VERIFIED"
    assert report.candidate_patch_created is False
    assert report.production_modified is False
    assert report.alpha_modified is False
    assert report.diagnostic_only is True
    assert abs(report.alpha - 0.40) < 1e-9

    # ── Write JSON report ─────────────────────────────────────────
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_dict = _to_dict(report)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report_dict, fh, indent=2, ensure_ascii=False)

    print(f"\n[Phase 68] Report written → {_OUTPUT_PATH}")
    print(f"[Phase 68] COMPLETION MARKER: {report.completion_marker}")
    print("[Phase 68] Done.")


if __name__ == "__main__":
    main()
