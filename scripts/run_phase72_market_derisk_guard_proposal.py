"""Runner script for Phase 72 — Paper-only Market De-risk Guard Proposal.

Builds full guard proposal in memory, prints summary, writes JSON report.
Does NOT read or write any prediction JSONL.
Does NOT modify production model, alpha, or stacking_model.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.phase72_market_derisk_guard_proposal import (
    ALPHA,
    ALPHA_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    PHASE70_GATE_ANCHOR,
    PHASE71_GATE_ANCHOR,
    PHASE_VERSION,
    PREDICTION_JSONL_OVERWRITTEN,
    PRODUCTION_MODIFIED,
    PIT_SAFE_VALIDATION,
    _VALID_GATES,
    run_phase72_market_derisk_guard_proposal,
)

_REPORT_PATH = (
    Path(__file__).parent.parent
    / "reports"
    / "phase72_market_derisk_guard_proposal_20260507.json"
)

_SEP = "═" * 70


def main() -> None:
    print("[Phase 72] Paper-only Market De-risk Guard Proposal")
    print(f"[Phase 72] PHASE_VERSION                = {PHASE_VERSION}")
    print(f"[Phase 72] DIAGNOSTIC_ONLY              = {DIAGNOSTIC_ONLY}")
    print(f"[Phase 72] ALPHA (frozen)               = {ALPHA}")
    print(f"[Phase 72] CANDIDATE_PATCH_CREATED      = {CANDIDATE_PATCH_CREATED}")
    print(f"[Phase 72] PRODUCTION_MODIFIED          = {PRODUCTION_MODIFIED}")
    print(f"[Phase 72] ALPHA_MODIFIED               = {ALPHA_MODIFIED}")
    print(f"[Phase 72] PREDICTION_JSONL_OVERWRITTEN = {PREDICTION_JSONL_OVERWRITTEN}")
    print(f"[Phase 72] PIT_SAFE_VALIDATION          = {PIT_SAFE_VALIDATION}")
    print(f"[Phase 72] Phase 70 gate anchor         = {PHASE70_GATE_ANCHOR}")
    print(f"[Phase 72] Phase 71 gate anchor         = {PHASE71_GATE_ANCHOR}")
    print()

    # Safety assertions — must never fail
    assert CANDIDATE_PATCH_CREATED is False, "SAFETY: CANDIDATE_PATCH_CREATED must be False"
    assert PRODUCTION_MODIFIED is False, "SAFETY: PRODUCTION_MODIFIED must be False"
    assert ALPHA_MODIFIED is False, "SAFETY: ALPHA_MODIFIED must be False"
    assert DIAGNOSTIC_ONLY is True, "SAFETY: DIAGNOSTIC_ONLY must be True"
    assert PREDICTION_JSONL_OVERWRITTEN is False, "SAFETY: PREDICTION_JSONL_OVERWRITTEN must be False"
    assert PIT_SAFE_VALIDATION is True, "SAFETY: PIT_SAFE_VALIDATION must be True"
    assert ALPHA == 0.40, f"SAFETY: ALPHA must be 0.40, got {ALPHA}"

    print("[Phase 72] Safety assertions passed.")
    print("[Phase 72] Building guard proposal (no data read, no model import) ...")
    print()

    report = run_phase72_market_derisk_guard_proposal()

    # Validate gate
    assert report.gate in _VALID_GATES, f"Invalid gate: {report.gate}"
    assert report.candidate_patch_created is False
    assert report.production_modified is False
    assert report.alpha_modified is False

    print(_SEP)
    print(f"[Phase 72] Phase 71 Evidence Summary (read-only, from Phase 71 run)")
    print(f"[Phase 72]   target band n        = {report.p71_n_target_band}")
    print(f"[Phase 72]   Brier delta          = {report.p71_brier_delta:+.4f}")
    print(f"[Phase 72]   bootstrap 95% CI     = [{report.p71_ci_lo:+.4f}, {report.p71_ci_hi:+.4f}]")
    print(f"[Phase 72]   CI stable            = {report.p71_ci_stable}")
    print(f"[Phase 72]   CI excludes zero     = {report.p71_ci_excludes_zero}")
    print(f"[Phase 72]   compression_ratio    = {report.p71_compression_ratio:.3f}")
    print(f"[Phase 72]   rank_corr            = {report.p71_rank_corr:.3f}")
    print(f"[Phase 72]   windows mkt superior = {report.p71_windows_market_superior}/5")
    print(f"[Phase 72]   NC overfit count     = {report.p71_nc_overfit_risk_count}/6")
    print()

    # Guard matrix
    print(_SEP)
    print("[Phase 72] CANDIDATE GUARD MATRIX")
    print(
        f"[Phase 72] {'guard_id':<36}  {'pit_safe':>8}  {'recommended':>11}  "
        f"{'action_type':<30}"
    )
    print("[Phase 72] " + "-" * 90)
    for g in report.guard_candidates:
        action_short = g["action_definition"][:45].rstrip()
        print(
            f"[Phase 72] {g['guard_id']:<36}  {str(g['pit_safe']):>8}  "
            f"{str(g['recommended']):>11}  {action_short}"
        )
    print()

    # Recommended vs rejected
    print(f"[Phase 72] Recommended guards  ({len(report.recommended_guards)}): "
          f"{', '.join(report.recommended_guards)}")
    print(f"[Phase 72] Rejected guards     ({len(report.rejected_guards)}): "
          f"{', '.join(report.rejected_guards) if report.rejected_guards else 'none'}")
    print()

    # Risk register summary
    print(_SEP)
    print("[Phase 72] RISK REGISTER SUMMARY")
    print(f"[Phase 72] {'risk_name':<35}  {'severity':>8}  {'likelihood':>10}")
    print("[Phase 72] " + "-" * 60)
    for r in report.risk_register:
        print(
            f"[Phase 72] {r['risk_name']:<35}  {r['severity']:>8}  {r['likelihood']:>10}"
        )
    print()

    # PIT-safe rules
    print(_SEP)
    print(f"[Phase 72] PIT-SAFE RULES ({len(report.pit_safe_rules)} rules, "
          f"{sum(1 for r in report.pit_safe_rules if r['required'])} required)")
    for r in report.pit_safe_rules:
        req_str = "REQUIRED" if r["required"] else "optional"
        print(f"[Phase 72]   [{req_str:>8}] {r['rule_id']}")
    print()

    # Success/Failure criteria
    n_sc = sum(1 for c in report.success_failure_criteria if c["criterion_type"] == "success")
    n_fc = sum(1 for c in report.success_failure_criteria if c["criterion_type"] == "failure")
    print(_SEP)
    print(f"[Phase 72] PHASE 73 SUCCESS/FAILURE CRITERIA: {n_sc} success, {n_fc} failure")
    print()

    # Governance rules
    print(_SEP)
    print(f"[Phase 72] GOVERNANCE RULES ({len(report.governance_rules)} rules)")
    for r in report.governance_rules:
        print(f"[Phase 72]   {r['rule_id']}: {r['rule_text'][:80]}")
    print()

    # Gate risk notes
    print(_SEP)
    print("[Phase 72] GATE RISK NOTES")
    for note in report.gate_risk_notes:
        print(f"[Phase 72]   ⚠  {note}")
    print()

    # Gate
    print(_SEP)
    print(f"[Phase 72] *** GATE: {report.gate} ***")
    print(f"[Phase 72] Rationale: {report.gate_rationale[:200]}")
    print()
    print(f"[Phase 72] Phase 73 recommended: {report.phase73_recommended}")
    print(f"[Phase 72] Phase 73 note: {report.phase73_recommendation_note[:120]}")
    print()

    # Write report
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    assert str(_REPORT_PATH).startswith(str(Path(__file__).parent.parent / "reports")), (
        "SAFETY: output path must be under reports/"
    )

    with open(_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "phase_version": report.phase_version,
                "completion_marker": report.completion_marker,
                "run_timestamp_utc": report.run_timestamp_utc,
                "safety": {
                    "candidate_patch_created": report.candidate_patch_created,
                    "production_modified": report.production_modified,
                    "alpha_modified": report.alpha_modified,
                    "diagnostic_only": report.diagnostic_only,
                    "prediction_jsonl_overwritten": report.prediction_jsonl_overwritten,
                    "pit_safe_validation": report.pit_safe_validation,
                    "alpha": report.alpha,
                },
                "phase_chain": {
                    "phase70_gate_anchor": report.phase70_gate_anchor,
                    "phase71_gate_anchor": report.phase71_gate_anchor,
                },
                "p71_evidence": {
                    "n_target_band": report.p71_n_target_band,
                    "brier_delta": report.p71_brier_delta,
                    "ci_lo": report.p71_ci_lo,
                    "ci_hi": report.p71_ci_hi,
                    "ci_stable": report.p71_ci_stable,
                    "ci_excludes_zero": report.p71_ci_excludes_zero,
                    "compression_ratio": report.p71_compression_ratio,
                    "rank_corr": report.p71_rank_corr,
                    "windows_market_superior": report.p71_windows_market_superior,
                    "nc_overfit_risk_count": report.p71_nc_overfit_risk_count,
                },
                "gate": report.gate,
                "gate_rationale": report.gate_rationale,
                "gate_risk_notes": report.gate_risk_notes,
                "recommended_guards": report.recommended_guards,
                "rejected_guards": report.rejected_guards,
                "phase73_recommended": report.phase73_recommended,
                "phase73_recommendation_note": report.phase73_recommendation_note,
                "guard_candidates": report.guard_candidates,
                "risk_register": report.risk_register,
                "pit_safe_rules": report.pit_safe_rules,
                "success_failure_criteria": report.success_failure_criteria,
                "governance_rules": report.governance_rules,
                "phase73_simulation_design": report.phase73_simulation_design,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"[Phase 72] JSON report written to: {_REPORT_PATH}")
    print()
    print(f"[Phase 72] {COMPLETION_MARKER}")


if __name__ == "__main__":
    main()
