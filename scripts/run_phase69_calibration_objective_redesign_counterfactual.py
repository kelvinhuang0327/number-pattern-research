#!/usr/bin/env python3
"""Phase 69 — Calibration Objective Redesign Counterfactual runner.

Usage:
    python scripts/run_phase69_calibration_objective_redesign_counterfactual.py

Reads:
    data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl

Writes:
    reports/phase69_calibration_objective_redesign_counterfactual_20260507.json
"""
import json
import sys
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.phase69_calibration_objective_redesign_counterfactual import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    IN_SAMPLE_FIT_AND_EVALUATE,
    PHASE68_GATE_ANCHOR,
    PHASE_VERSION,
    PIT_SAFE_VALIDATION,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    _VALID_GATES,
    _to_dict,
    run_phase69_calibration_objective_redesign_counterfactual,
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
    / "phase69_calibration_objective_redesign_counterfactual_20260507.json"
)


def main() -> None:
    print("[Phase 69] Calibration Objective Redesign Counterfactual")
    print(f"[Phase 69] PHASE_VERSION                = {PHASE_VERSION}")
    print(f"[Phase 69] DIAGNOSTIC_ONLY              = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 69] ALPHA                        = {ALPHA}")
    print(f"[Phase 69] CANDIDATE_PATCH_CREATED      = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 69] PRODUCTION_MODIFIED          = {PRODUCTION_MODIFIED}")
    print(f"[Phase 69] ALPHA_MODIFIED               = {ALPHA_MODIFIED}")
    print(f"[Phase 69] PREDICTION_JSONL_OVERWRITTEN = {PREDICTION_JSONL_OVERWRITTEN}")
    print(f"[Phase 69] IN_SAMPLE_FIT_AND_EVALUATE   = {IN_SAMPLE_FIT_AND_EVALUATE}")
    print(f"[Phase 69] PIT_SAFE_VALIDATION          = {PIT_SAFE_VALIDATION}")
    print(f"[Phase 69] Phase 68 gate anchor         = {PHASE68_GATE_ANCHOR}")
    print(f"[Phase 69] Predictions path: {_PREDICTIONS_PATH}")

    if not _PREDICTIONS_PATH.exists():
        print(f"[Phase 69] ERROR: predictions file not found: {_PREDICTIONS_PATH}")
        sys.exit(1)

    print("[Phase 69] Running counterfactual analysis (OOF calibration + shaping reversals)...")
    report = run_phase69_calibration_objective_redesign_counterfactual(
        predictions_path=_PREDICTIONS_PATH,
    )

    # Verify safety constants in report
    assert report.candidate_patch_created is False, "SAFETY VIOLATION: candidate_patch_created"
    assert report.production_modified is False,      "SAFETY VIOLATION: production_modified"
    assert report.alpha_modified is False,           "SAFETY VIOLATION: alpha_modified"
    assert report.prediction_jsonl_overwritten is False, "SAFETY VIOLATION: prediction_jsonl_overwritten"
    assert report.in_sample_fit_and_evaluate is False, "SAFETY VIOLATION: in_sample_fit_and_evaluate"
    assert report.pit_safe_validation is True,       "SAFETY VIOLATION: pit_safe_validation"
    assert report.gate in _VALID_GATES,              f"SAFETY: invalid gate {report.gate!r}"
    assert report.completion_marker == COMPLETION_MARKER, "SAFETY: completion marker mismatch"

    # Serialize and write
    output = _to_dict(report)
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    print(f"\n[Phase 69] ═══════════════════════════════════════════")
    print(f"[Phase 69] n_total         = {report.n_total}")
    print(f"[Phase 69] n_train (OOF)   = {report.n_train}")
    print(f"[Phase 69] n_eval (OOF)    = {report.n_eval}")
    print(f"[Phase 69] feature_version = {report.feature_version}")
    print(f"[Phase 69] OOF split: train={report.oof_split.train_date_start}→{report.oof_split.train_date_end}")
    print(f"[Phase 69]            eval ={report.oof_split.eval_date_start}→{report.oof_split.eval_date_end}")
    print(f"[Phase 69] pit_safe        = {report.oof_split.pit_safe}")

    # Print counterfactual results for all_games and heavy_favorite
    print(f"\n[Phase 69] COUNTERFACTUAL RESULTS (eval set, n={report.n_eval})")
    print(f"[Phase 69] {'Method':<30} {'Seg':<18} {'Brier':>8} {'BSSvsMkt':>10} {'ECE':>8} {'ΔBrier':>9}")
    print(f"[Phase 69] {'-'*30} {'-'*18} {'-'*8} {'-'*10} {'-'*8} {'-'*9}")
    for m in report.counterfactual_metrics:
        if m.segment in ("all_games", "heavy_favorite") and not m.data_limited:
            print(
                f"[Phase 69] {m.method:<30} {m.segment:<18} "
                f"{m.brier:>8.4f} {m.bss_vs_market:>10.4f} "
                f"{m.ece:>8.4f} {m.brier_delta_vs_original:>+9.4f}"
            )

    print(f"\n[Phase 69] CALIBRATION BANDS (original_baseline vs oof_isotonic, eval set):")
    print(f"[Phase 69] {'Method':<25} {'Band':<12} {'n':>5} {'Pred':>7} {'Actual':>8} {'Residual':>10} {'Flags'}")
    for b in report.calibration_bands:
        if b.method in ("original_baseline", "oof_isotonic"):
            flags = ""
            if b.is_overconfident: flags += " OC"
            if b.is_underconfident: flags += " UC"
            if b.data_limited: flags += " DL"
            print(
                f"[Phase 69] {b.method:<25} {b.band_label:<12} {b.n:>5} "
                f"{b.pred:>7.4f} {b.actual_win_rate:>8.4f} {b.residual:>+10.4f}{flags}"
            )

    print(f"\n[Phase 69] BOOTSTRAP CIs (all_games Brier delta):")
    for ci in report.bootstrap_cis:
        if ci.segment == "all_games":
            print(
                f"[Phase 69]   {ci.method:<30}: delta={ci.observed:+.4f} "
                f"95%CI=[{ci.ci_lower:+.4f}, {ci.ci_upper:+.4f}] "
                f"excl0={ci.ci_excludes_zero} stable={ci.ci_stable}"
            )

    print(f"\n[Phase 69] NEGATIVE CONTROLS:")
    for nc in report.negative_controls:
        print(
            f"[Phase 69]   {nc.control_name:<35}: real_imp={nc.real_improvement:+.4f} "
            f"null_mean={nc.null_improvement_mean:+.4f} gap={nc.signal_gap:+.4f} "
            f"overfit_risk={nc.overfit_risk}"
        )

    print(f"\n[Phase 69] SUMMARY FLAGS:")
    print(f"[Phase 69]   oof_calibration_improves_ece     = {report.oof_calibration_improves_ece}")
    print(f"[Phase 69]   oof_calibration_improves_bss     = {report.oof_calibration_improves_bss}")
    print(f"[Phase 69]   shaping_removal_improves_hf      = {report.shaping_removal_improves_heavy_fav}")
    print(f"[Phase 69]   negative_controls_clear          = {report.negative_controls_clear}")
    print(f"[Phase 69]   bootstrap_ci_stable              = {report.bootstrap_ci_stable}")
    print(f"[Phase 69]   worth_phase70                    = {report.worth_phase70}")

    if report.risk_notes:
        print(f"\n[Phase 69] RISK NOTES:")
        for note in report.risk_notes:
            print(f"[Phase 69]   ⚠  {note}")

    print(f"\n[Phase 69] ═══════════════════════════════════════════")
    print(f"[Phase 69] GATE: {report.gate}")
    print(f"[Phase 69] RATIONALE: {report.gate_rationale}")
    print(f"[Phase 69] PHASE 70 RECOMMENDATION: {report.phase70_recommendation}")
    print(f"\n[Phase 69] completion_marker = {report.completion_marker}")
    print(f"[Phase 69] Output written to: {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
