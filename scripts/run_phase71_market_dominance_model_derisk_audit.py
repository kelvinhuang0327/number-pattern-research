"""Runner script for Phase 71 — Market Dominance and Model De-risk Audit.

Reads prediction JSONL, runs full audit, prints a summary, writes JSON report.
Does NOT modify the source JSONL file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.phase71_market_dominance_model_derisk_audit import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    PHASE70_GATE_ANCHOR,
    PHASE_VERSION,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    PIT_SAFE_VALIDATION,
    _to_dict,
    run_phase71_market_dominance_model_derisk_audit,
)

_PREDICTIONS_PATH = (
    Path(__file__).parent.parent
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

_REPORT_PATH = (
    Path(__file__).parent.parent
    / "reports"
    / "phase71_market_dominance_model_derisk_audit_20260507.json"
)

_SEP = "═" * 60


def main() -> None:
    print("[Phase 71] Market Dominance and Model De-risk Audit")
    print(f"[Phase 71] PHASE_VERSION                = {PHASE_VERSION}")
    print(f"[Phase 71] DIAGNOSTIC_ONLY              = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 71] ALPHA                        = {ALPHA}")
    print(f"[Phase 71] CANDIDATE_PATCH_CREATED      = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 71] PRODUCTION_MODIFIED          = {PRODUCTION_MODIFIED}")
    print(f"[Phase 71] ALPHA_MODIFIED               = {ALPHA_MODIFIED}")
    print(f"[Phase 71] PREDICTION_JSONL_OVERWRITTEN = {PREDICTION_JSONL_OVERWRITTEN}")
    print(f"[Phase 71] PIT_SAFE_VALIDATION          = {PIT_SAFE_VALIDATION}")
    print(f"[Phase 71] Phase 70 gate anchor         = {PHASE70_GATE_ANCHOR}")
    print(f"[Phase 71] Predictions path: {_PREDICTIONS_PATH}")
    print("[Phase 71] Running full audit (A→E dimensions + 6 NCs + bootstrap) ...")
    print()

    report = run_phase71_market_dominance_model_derisk_audit(
        predictions_path=_PREDICTIONS_PATH,
        n_boot=1000,
        rng_seed=42,
        n_permutations=200,
    )

    print(_SEP)
    print(f"[Phase 71] n_total          = {report.n_total}")
    print(f"[Phase 71] n_target_band    = {report.n_target_band}  (model_prob 0.65–0.70)")
    print(f"[Phase 71] feature_version  = {report.feature_version}")
    print()

    # ── Dimension A: segment metrics ──────────────────────────────
    print("[Phase 71] SEGMENT METRICS (market vs model)")
    header = (
        f"[Phase 71] {'Segment':<36} {'n':>5}  "
        f"{'MdlBrier':>8}  {'MktBrier':>8}  {'Delta':>7}  "
        f"{'MdlResid':>8}  {'MktResid':>8}  {'WinRate':>7}  "
        f"{'MktSup':>6}"
    )
    print(header)
    print(f"[Phase 71] {'-' * 108}")
    for s in report.segment_metrics:
        sup = "Yes" if s.market_superiority else ("Yes DL" if s.data_limited and s.brier_delta > 0 else "No")
        if s.data_limited and not s.market_superiority:
            sup = "No  DL"
        print(
            f"[Phase 71] {s.segment:<36} {s.n:>5}  "
            f"{s.model_brier:>8.4f}  {s.market_brier:>8.4f}  "
            f"{s.brier_delta:>+7.4f}  "
            f"{s.model_residual_mean:>+8.4f}  {s.market_residual_mean:>+8.4f}  "
            f"{s.observed_win_rate:>7.4f}  {sup:>6}"
        )

    # ── TARGET BAND detail ────────────────────────────────────────
    tgt = next((s for s in report.segment_metrics if s.segment == "model_prob_0.65_0.70"), None)
    if tgt:
        print()
        print("[Phase 71] TARGET BAND (0.65–0.70) DETAIL:")
        print(f"[Phase 71]   model_brier              = {tgt.model_brier:.4f}")
        print(f"[Phase 71]   market_brier             = {tgt.market_brier:.4f}")
        print(f"[Phase 71]   brier_delta              = {tgt.brier_delta:+.4f}")
        print(f"[Phase 71]   model_residual_mean      = {tgt.model_residual_mean:+.4f}")
        print(f"[Phase 71]   market_residual_mean     = {tgt.market_residual_mean:+.4f}")
        print(f"[Phase 71]   observed_win_rate        = {tgt.observed_win_rate:.4f}")
        print(f"[Phase 71]   model_mean_prob          = {tgt.model_mean_prob:.4f}")
        print(f"[Phase 71]   market_mean_prob         = {tgt.market_mean_prob:.4f}")
        print(f"[Phase 71]   model_minus_market_mean  = {tgt.model_minus_market_mean:+.4f}")
        print(f"[Phase 71]   bss_vs_market            = {tgt.bss_vs_market:+.4f}")
        print(f"[Phase 71]   market_superiority       = {tgt.market_superiority}")

    # ── Dimension B: distribution shape ───────────────────────────
    print()
    print("[Phase 71] DISTRIBUTION SHAPE (target band 0.65–0.70 focus):")
    tgt_shape = next(
        (d for d in report.distribution_shape if d.segment == "model_prob_0.65_0.70"), None
    )
    if tgt_shape:
        print(f"[Phase 71]   model_std         = {tgt_shape.model_std:.4f}")
        print(f"[Phase 71]   market_std        = {tgt_shape.market_std:.4f}")
        print(f"[Phase 71]   compression_ratio = {tgt_shape.compression_ratio:.4f}")
        print(f"[Phase 71]   model_iqr         = {tgt_shape.model_iqr:.4f}")
        print(f"[Phase 71]   market_iqr        = {tgt_shape.market_iqr:.4f}")
        print(f"[Phase 71]   rank_correlation  = {tgt_shape.rank_correlation:.4f}")
        print(f"[Phase 71]   mean_disagreement = {tgt_shape.mean_disagreement:.4f}")
        print(f"[Phase 71]   disagreement_rate = {tgt_shape.disagreement_rate:.2%}")
        print(f"[Phase 71]   model_compressed  = {tgt_shape.model_compressed}")
    print()
    print(
        f"[Phase 71] {'Segment':<36} {'MdlStd':>7}  {'MktStd':>7}  "
        f"{'Compress':>8}  {'RankCorr':>8}  {'DiagRate':>8}"
    )
    print(f"[Phase 71] {'-' * 84}")
    for d in report.distribution_shape:
        print(
            f"[Phase 71] {d.segment:<36} {d.model_std:>7.4f}  {d.market_std:>7.4f}  "
            f"{d.compression_ratio:>8.4f}  {d.rank_correlation:>8.4f}  "
            f"{d.disagreement_rate:>8.2%}"
        )

    # ── Dimension C: sp_fip attribution ───────────────────────────
    print()
    print("[Phase 71] SP_FIP_DELTA ATTRIBUTION (target band):")
    sp = report.sp_fip_attribution
    if sp:
        print(f"[Phase 71]   n_available (target)    = {sp.n_target_available} / {sp.n_target_total}")
        print(f"[Phase 71]   availability_rate        = {sp.availability_rate_target:.1%}")
        print(f"[Phase 71]   mean_sp_fip_target       = {sp.mean_sp_fip_target}")
        print(f"[Phase 71]   mean_sp_fip_all          = {sp.mean_sp_fip_all}")
        print(f"[Phase 71]   sp_fip vs model-market corr = {sp.sp_fip_vs_model_minus_market_corr:+.4f}")
        print(f"[Phase 71]   sp_fip vs market_prob corr  = {sp.sp_fip_vs_market_prob_corr:+.4f}")
        print(f"[Phase 71]   sp_fip vs residual corr     = {sp.sp_fip_vs_outcome_residual_corr:+.4f}")
        print(f"[Phase 71]   bucket high n={sp.n_sp_fip_high_bucket}  "
              f"model_brier={sp.model_brier_sp_fip_high:.4f}  "
              f"market_brier={sp.market_brier_sp_fip_high:.4f}  "
              f"residual={sp.residual_mean_sp_fip_high:+.4f}")
        print(f"[Phase 71]   bucket low  n={sp.n_sp_fip_low_bucket}  "
              f"model_brier={sp.model_brier_sp_fip_low:.4f}  "
              f"market_brier={sp.market_brier_sp_fip_low:.4f}  "
              f"residual={sp.residual_mean_sp_fip_low:+.4f}")
        print(f"[Phase 71]   residual_bucket_gap      = {sp.residual_bucket_gap:+.4f}")
        print(f"[Phase 71]   sp_fip_absorbed_by_market = {sp.sp_fip_absorbed_by_market}")
        print(f"[Phase 71]   sp_fip_independent_signal = {sp.sp_fip_independent_signal}")
        if sp.data_limited:
            print("[Phase 71]   ⚠  DATA_LIMITED: < 10 sp_fip available rows in target band")

    # ── Dimension D: split market results ─────────────────────────
    print()
    print("[Phase 71] SPLIT MARKET COMPARISON (target band):")
    print(
        f"[Phase 71]   {'SplitID':<12} {'n':>5}  "
        f"{'MdlBrier':>8}  {'MktBrier':>8}  {'Delta':>7}  "
        f"{'MdlResid':>8}  {'WinRate':>7}  {'MktSup':>6}"
    )
    for s in report.split_market_results:
        dl_tag = " DL" if s.data_limited else ""
        sup = "Yes" if s.market_superior else "No"
        print(
            f"[Phase 71]   {s.split_id:<12} {s.n:>5}  "
            f"{s.model_brier:>8.4f}  {s.market_brier:>8.4f}  "
            f"{s.brier_delta:>+7.4f}  "
            f"{s.model_residual_mean:>+8.4f}  {s.observed_win_rate:>7.4f}  "
            f"{sup:>6}{dl_tag}"
        )

    # ── Dimension E: team concentration ───────────────────────────
    print()
    print("[Phase 71] TEAM CONCENTRATION (target band, top teams):")
    for t in report.team_concentration:
        dl_tag = " DL" if t.data_limited else ""
        print(
            f"[Phase 71]   {t.team:<35} n={t.n_in_target_band:>3} "
            f"share={t.share_of_target_band:.1%}  "
            f"delta={t.brier_delta:+.4f}  "
            f"resid={t.model_residual_mean:+.4f}{dl_tag}"
        )

    print()
    print("[Phase 71] FEATURE AVAILABILITY MATRIX:")
    print(
        f"[Phase 71] {'Feature':<30} {'Avail%T':>7}  {'Avail%A':>7}  "
        f"{'MeanT':>8}  {'MeanA':>8}  {'ExtDelta':>9}"
    )
    print(f"[Phase 71] {'-' * 80}")
    for f in report.feature_availability:
        dl_tag = " DL" if f.data_limited else ""
        mv_t = f"{f.mean_value_target:>8.4f}" if f.mean_value_target is not None else "    N/A "
        mv_a = f"{f.mean_value_all:>8.4f}" if f.mean_value_all is not None else "    N/A "
        print(
            f"[Phase 71] {f.feature_name:<30} "
            f"{f.availability_rate_target:>7.1%}  "
            f"{f.availability_rate_all:>7.1%}  "
            f"{mv_t}  {mv_a}  "
            f"{f.extreme_delta:>+9.4f}{dl_tag}"
        )

    # ── Bootstrap CIs ─────────────────────────────────────────────
    print()
    print("[Phase 71] BOOTSTRAP CIs:")
    for ci in report.bootstrap_cis:
        excl = "excl0=True" if ci.ci_excludes_zero else "excl0=False"
        stable = "stable=True" if ci.ci_stable else "stable=False"
        dl_tag = " DL" if ci.data_limited else ""
        print(
            f"[Phase 71]   {ci.segment:<30} [{ci.metric:<30}]: "
            f"obs={ci.observed:>+7.4f} "
            f"95%CI=[{ci.ci_lower:>+7.4f}, {ci.ci_upper:>+7.4f}] "
            f"{excl} {stable}{dl_tag}"
        )

    # ── Negative controls ─────────────────────────────────────────
    print()
    print("[Phase 71] NEGATIVE CONTROLS:")
    for nc in report.negative_controls:
        print(
            f"[Phase 71]   {nc.control_name:<40}: "
            f"obs={nc.observed_gap:>+8.4f} "
            f"null_mean={nc.permuted_gap_mean:>+8.4f} "
            f"sig_gap={nc.signal_gap:>+8.4f} "
            f"overfit_risk={nc.overfit_risk}"
        )

    # ── Summary flags ─────────────────────────────────────────────
    print()
    print("[Phase 71] SUMMARY FLAGS:")
    print(f"[Phase 71]   market_dominance_stable    = {report.market_dominance_stable}")
    print(f"[Phase 71]   split_instability_detected = {report.split_instability_detected}")
    print(f"[Phase 71]   sp_fip_independent_signal  = {report.sp_fip_independent_signal}")
    print(f"[Phase 71]   overfit_risk_detected      = {report.overfit_risk_detected}")
    print(f"[Phase 71]   model_compressed           = {report.model_compressed}")
    print(f"[Phase 71]   worth_phase72              = {report.worth_phase72}")

    if report.risk_notes:
        print()
        print("[Phase 71] RISK NOTES:")
        for note in report.risk_notes:
            print(f"[Phase 71]   {note}")

    print()
    print(_SEP)
    print(f"[Phase 71] GATE: {report.gate}")
    print(f"[Phase 71] RATIONALE: {report.gate_rationale}")
    print(f"[Phase 71] PHASE 72 RECOMMENDATION: {report.phase72_recommendation}")
    print()
    print(f"[Phase 71] completion_marker = {report.completion_marker}")

    # ── Write JSON report ─────────────────────────────────────────
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _REPORT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(_to_dict(report), fh, indent=2, ensure_ascii=False)
    print(f"[Phase 71] Output written to: {_REPORT_PATH}")

    # ── Final safety assertion ─────────────────────────────────────
    assert not report.candidate_patch_created, "candidate_patch_created must be False"
    assert not report.production_modified, "production_modified must be False"
    assert not report.alpha_modified, "alpha_modified must be False"
    assert report.diagnostic_only, "diagnostic_only must be True"
    assert not report.prediction_jsonl_overwritten, "prediction_jsonl_overwritten must be False"
    assert report.alpha == 0.40, f"alpha must be 0.40, got {report.alpha}"
    print("[Phase 71] Safety assertions: PASS")


if __name__ == "__main__":
    main()
