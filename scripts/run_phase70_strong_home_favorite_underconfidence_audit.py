"""Runner for Phase 70 — Strong Home Favorite Underconfidence Feature Root-Cause Audit.

DIAGNOSTIC ONLY. Does NOT modify any production files.
Reads Phase 56 prediction JSONL, runs full Phase 70 audit, writes JSON report.

Usage:
    .venv/bin/python scripts/run_phase70_strong_home_favorite_underconfidence_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.phase70_strong_home_favorite_underconfidence_audit import (
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    PHASE_VERSION,
    PHASE69_GATE_ANCHOR,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    ALPHA,
    ALPHA_MODIFIED,
    PIT_SAFE_VALIDATION,
    _VALID_GATES,
    _to_dict,
    run_phase70_strong_home_favorite_underconfidence_audit,
)

# ─────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent
_PREDICTIONS_PATH = (
    _REPO
    / "data"
    / "mlb_2025"
    / "derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
_OUTPUT_PATH = (
    _REPO
    / "reports"
    / "phase70_strong_home_favorite_underconfidence_audit_20260507.json"
)


def main() -> None:
    print("[Phase 70] Strong Home Favorite Underconfidence Feature Root-Cause Audit")
    print(f"[Phase 70] PHASE_VERSION                = {PHASE_VERSION}")
    print(f"[Phase 70] DIAGNOSTIC_ONLY              = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 70] ALPHA                        = {ALPHA}")
    print(f"[Phase 70] CANDIDATE_PATCH_CREATED      = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 70] PRODUCTION_MODIFIED          = {PRODUCTION_MODIFIED}")
    print(f"[Phase 70] ALPHA_MODIFIED               = {ALPHA_MODIFIED}")
    print(f"[Phase 70] PREDICTION_JSONL_OVERWRITTEN = {PREDICTION_JSONL_OVERWRITTEN}")
    print(f"[Phase 70] PIT_SAFE_VALIDATION          = {PIT_SAFE_VALIDATION}")
    print(f"[Phase 70] Phase 69 gate anchor         = {PHASE69_GATE_ANCHOR}")
    print(f"[Phase 70] Predictions path: {_PREDICTIONS_PATH}")
    print("[Phase 70] Running full audit (A→E dimensions + 5 NCs + bootstrap) ...")
    print()

    if not _PREDICTIONS_PATH.exists():
        print(f"[Phase 70] ERROR: predictions file not found: {_PREDICTIONS_PATH}")
        sys.exit(1)

    # Run audit
    report = run_phase70_strong_home_favorite_underconfidence_audit(
        predictions_path=_PREDICTIONS_PATH,
        n_boot=1000,
        rng_seed=42,
    )

    # Verify safety constants in report
    assert not report.candidate_patch_created, "Safety violation: candidate_patch_created=True"
    assert not report.production_modified, "Safety violation: production_modified=True"
    assert not report.alpha_modified, "Safety violation: alpha_modified=True"
    assert report.diagnostic_only, "Safety violation: diagnostic_only=False"
    assert not report.prediction_jsonl_overwritten, "Safety violation: jsonl_overwritten=True"
    assert report.gate in _VALID_GATES, f"Invalid gate: {report.gate}"

    # ─── Print results ────────────────────────────────────────────
    print("═" * 60)
    print(f"[Phase 70] n_total          = {report.n_total}")
    print(f"[Phase 70] n_target_band    = {report.n_target_band}  (model_prob 0.65–0.70)")
    print(f"[Phase 70] feature_version  = {report.feature_version}")
    print()

    # Segment metrics table
    print("[Phase 70] SEGMENT METRICS")
    print(f"[Phase 70] {'Segment':<30} {'n':>5} {'Brier':>8} {'BSS':>8} "
          f"{'ECE':>8} {'Resid':>8} {'WinRate':>8} {'MktBrier':>9} {'MktBetter':>10}")
    print("[Phase 70] " + "-" * 98)
    for sm in report.segment_metrics:
        dl_mark = " DL" if sm.data_limited else ""
        print(
            f"[Phase 70] {sm.segment:<30} {sm.n:>5} {sm.brier:>8.4f} "
            f"{sm.bss_vs_market:>8.4f} {sm.ece:>8.4f} {sm.residual_mean:>+8.4f} "
            f"{sm.observed_win_rate:>8.4f} {sm.market_brier:>9.4f} "
            f"{'Yes' if sm.market_beats_model_brier else 'No':>10}{dl_mark}"
        )

    print()

    # Market vs model in target band
    target_seg = next(
        (s for s in report.segment_metrics if s.segment == "model_prob_0.65_0.70"), None
    )
    if target_seg and not target_seg.data_limited:
        print("[Phase 70] TARGET BAND (0.65–0.70) DETAIL:")
        print(f"[Phase 70]   model_brier          = {target_seg.brier:.4f}")
        print(f"[Phase 70]   market_brier         = {target_seg.market_brier:.4f}")
        print(f"[Phase 70]   model_residual_mean  = {target_seg.residual_mean:+.4f}")
        print(f"[Phase 70]   market_residual_mean = {target_seg.market_residual_mean:+.4f}")
        print(f"[Phase 70]   model_minus_market   = {target_seg.model_minus_market_mean:+.4f}")
        print(f"[Phase 70]   observed_win_rate    = {target_seg.observed_win_rate:.4f}")
        print(f"[Phase 70]   predicted_mean_prob  = {target_seg.predicted_mean_prob:.4f}")
        print(f"[Phase 70]   market_mean_prob     = {target_seg.market_mean_prob:.4f}")
        print(f"[Phase 70]   severe_underconf     = {target_seg.severe_underconfidence}")
    print()

    # Split stability
    print("[Phase 70] SPLIT STABILITY (target band):")
    for ss in report.split_stability:
        dl_mark = " DL" if ss.data_limited else ""
        print(
            f"[Phase 70]   {ss.split_id:<12}: n={ss.n:>4} "
            f"resid={ss.residual_mean:>+7.4f} win={ss.observed_win_rate:.3f} "
            f"pred={ss.predicted_mean_prob:.3f}{dl_mark}"
        )
    print()

    # Team concentration
    print("[Phase 70] TEAM CONCENTRATION (target band, top teams):")
    for tc in report.team_concentration[:8]:
        dl_mark = " DL" if tc.data_limited else ""
        print(
            f"[Phase 70]   {tc.team:<8} ({tc.team_role:<4}): n={tc.n_in_target_band:>3} "
            f"share={tc.share_of_target_band:.1%} "
            f"win={tc.observed_win_rate:.3f} resid={tc.residual_mean:>+7.4f}{dl_mark}"
        )
    print()

    # Feature attribution
    print("[Phase 70] FEATURE ATTRIBUTION PROXY (target band vs all):")
    print(f"[Phase 70] {'Feature':<30} {'Avail%T':>8} {'Avail%A':>8} "
          f"{'ExtDelta':>10} {'ResDelta':>10} {'DL':>4}")
    for fa in report.feature_attribution:
        dl_mark = "DL" if fa.data_limited else ""
        mv_t = f"{fa.mean_value_target:.4f}" if fa.mean_value_target is not None else "N/A"
        print(
            f"[Phase 70] {fa.feature_name:<30} {fa.availability_rate_target:>8.1%} "
            f"{fa.availability_rate_all:>8.1%} "
            f"{fa.extreme_value_delta:>+10.4f} {fa.residual_delta_proxy:>+10.4f} {dl_mark:>4}"
        )
    print()

    # Bootstrap CIs
    print("[Phase 70] BOOTSTRAP CIs:")
    for ci in report.bootstrap_cis:
        print(
            f"[Phase 70]   {ci.segment:<30} [{ci.metric:<22}]: "
            f"obs={ci.observed:>+8.4f} "
            f"95%CI=[{ci.ci_lower:>+8.4f}, {ci.ci_upper:>+8.4f}] "
            f"excl0={ci.ci_excludes_zero} stable={ci.ci_stable}"
        )
    print()

    # Negative controls
    print("[Phase 70] NEGATIVE CONTROLS:")
    for nc in report.negative_controls:
        print(
            f"[Phase 70]   {nc.control_name:<35}: "
            f"obs={nc.observed_gap:>+8.4f} "
            f"null_mean={nc.permuted_gap_mean:>+8.4f} "
            f"sig_gap={nc.signal_gap:>+8.4f} "
            f"overfit_risk={nc.overfit_risk}"
        )
    print()

    # Summary flags
    print("[Phase 70] SUMMARY FLAGS:")
    print(f"[Phase 70]   market_better_in_target_band    = {report.market_better_in_target_band}")
    print(f"[Phase 70]   feature_gap_detected            = {report.feature_gap_detected}")
    print(f"[Phase 70]   team_concentration_detected     = {report.team_concentration_detected}")
    print(f"[Phase 70]   split_instability_detected      = {report.split_instability_detected}")
    print(f"[Phase 70]   negative_controls_clear         = {report.negative_controls_clear}")
    print(f"[Phase 70]   bootstrap_ci_stable             = {report.bootstrap_ci_stable}")
    print(f"[Phase 70]   worth_phase71                   = {report.worth_phase71}")

    if report.risk_notes:
        print()
        print("[Phase 70] RISK NOTES:")
        for note in report.risk_notes:
            print(f"[Phase 70]   {note}")

    print()
    print("═" * 60)
    print(f"[Phase 70] GATE: {report.gate}")
    print(f"[Phase 70] RATIONALE: {report.gate_rationale}")
    print(f"[Phase 70] PHASE 71 RECOMMENDATION: {report.phase71_recommendation}")
    print()
    print(f"[Phase 70] completion_marker = {report.completion_marker}")

    # ─── Write JSON report ────────────────────────────────────────
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_dict = _to_dict(report)
    with _OUTPUT_PATH.open("w") as fh:
        json.dump(report_dict, fh, indent=2, ensure_ascii=False)
    print(f"[Phase 70] Output written to: {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
