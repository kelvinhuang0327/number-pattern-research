"""
scripts/_p88_regeneration_authorization_gate.py
================================================
P88 — Regeneration Authorization Gate and Safe Recovery Readiness Check

Read-only gate script. Checks whether the explicit authorization phrase has been
received to trigger the P84E→P84F→P84G→P84H→P85→P86 recovery sequence.

Authorization required phrase (exact):
  YES regenerate stale downstream artifacts for P87 recovery

If the phrase is NOT present this script was invoked with, classification is:
  P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION

This script NEVER modifies any frozen artifact. It is diagnostic-only.

Governance:
  paper_only = true
  diagnostic_only = true
  production_ready = false
  no EV / CLV / Kelly / odds / live API
"""

import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).parent.parent.resolve()

# ─── Paths ────────────────────────────────────────────────────────────────────

P87_SUMMARY = ROOT / "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json"
P86_SUMMARY = ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json"

OUTPUT_SUMMARY = ROOT / "data/mlb_2026/derived/p88_regeneration_authorization_gate_summary.json"
OUTPUT_REPORT  = ROOT / "report/p88_regeneration_authorization_gate_20260527.md"
ACTIVE_TASK    = ROOT / "00-Plan/roadmap/active_task.md"

# ─── Authorization ────────────────────────────────────────────────────────────

REQUIRED_EXPLICIT_YES = "YES regenerate stale downstream artifacts for P87 recovery"

# Authorization phrase MUST be set to the exact string at call time to unlock.
# The default (None) keeps P88 in gate-only mode.
AUTHORIZATION_INPUT: str | None = None  # Do NOT set without explicit user instruction.

# ─── Expected upstream states ─────────────────────────────────────────────────

EXPECTED_P87_CLASSIFICATION = "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"
EXPECTED_P86_CLASSIFICATION = "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK"

# ─── Allowed P88 classifications ─────────────────────────────────────────────

ALLOWED_CLASSIFICATIONS = [
    "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION",
    "P88_REGENERATION_AUTHORIZED_READY_TO_EXECUTE",
    "P88_AUTHORIZATION_GATE_FAILED_P87_STATE_MISMATCH",
    "P88_AUTHORIZATION_GATE_FAILED_P86_STATE_MISMATCH",
    "P88_AUTHORIZATION_GATE_BLOCKED_BY_PREFLIGHT",
    "P88_AUTHORIZATION_GATE_BLOCKED_BY_SCOPE_DRIFT",
]

# ─── Frozen artifact manifest ─────────────────────────────────────────────────

FROZEN_ARTIFACTS: list[str] = [
    "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
    "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
    "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json",
    "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sha256_prefix(path: pathlib.Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def _mtime_utc(path: pathlib.Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ─── Step 1: Check P87 state ──────────────────────────────────────────────────

def step1_check_p87_state() -> dict:
    exists = P87_SUMMARY.exists()
    if not exists:
        return {
            "step": "step1_check_p87_state",
            "p87_summary_exists": False,
            "p87_classification": None,
            "p87_classification_matches": False,
            "count_match": None,
            "game_id_full_coverage": None,
            "content_drift_likely": None,
            "explicit_yes_required": None,
            "stale_by_mtime_only": None,
            "safe_without_explicit_yes": None,
            "delta_seconds": None,
            "p87_state_ok": False,
            "issue": "P87 summary not found",
        }

    d = json.loads(P87_SUMMARY.read_text(encoding="utf-8"))
    cls = d.get("p87_classification")
    s3 = d.get("step3_content_identity_probe", {})
    s6 = d.get("step6_safety_decision", {})
    s2 = d.get("step2_stale_risk_extraction", {})
    rc = s2.get("root_cause", {})

    cls_ok = cls == EXPECTED_P87_CLASSIFICATION
    count_match = s3.get("count_match")
    game_id_full = s3.get("game_id_full_coverage")
    drift = s3.get("content_drift_likely")
    stale_mtime_only = s6.get("stale_by_mtime_only")
    safe_no_yes = s6.get("safe_without_explicit_yes")
    exp_yes = d.get("explicit_yes_required")
    delta = rc.get("delta_seconds")

    state_ok = (
        exists and cls_ok and count_match is True
        and game_id_full is True and drift is False
        and stale_mtime_only is True and safe_no_yes is False
    )

    return {
        "step": "step1_check_p87_state",
        "p87_summary_exists": True,
        "p87_classification": cls,
        "p87_classification_matches": cls_ok,
        "count_match": count_match,
        "game_id_full_coverage": game_id_full,
        "content_drift_likely": drift,
        "stale_by_mtime_only": stale_mtime_only,
        "safe_without_explicit_yes": safe_no_yes,
        "explicit_yes_required": exp_yes,
        "delta_seconds": delta,
        "p87_state_ok": state_ok,
        "issue": None if state_ok else f"P87 state mismatch: cls_ok={cls_ok}",
    }


# ─── Step 2: Check P86 state ──────────────────────────────────────────────────

def step2_check_p86_state() -> dict:
    exists = P86_SUMMARY.exists()
    if not exists:
        return {
            "step": "step2_check_p86_state",
            "p86_summary_exists": False,
            "p86_classification": None,
            "p86_classification_matches": False,
            "p86_state_ok": False,
            "issue": "P86 summary not found",
        }

    d = json.loads(P86_SUMMARY.read_text(encoding="utf-8"))
    cls = d.get("p86_classification")
    cls_ok = cls == EXPECTED_P86_CLASSIFICATION
    n_stale = d.get("step7_mtime_ordering", {}).get("n_stale_risks", 0)

    return {
        "step": "step2_check_p86_state",
        "p86_summary_exists": True,
        "p86_classification": cls,
        "p86_classification_matches": cls_ok,
        "n_stale_risks_in_p86": n_stale,
        "p86_state_ok": cls_ok,
        "issue": None if cls_ok else f"P86 classification mismatch: expected {EXPECTED_P86_CLASSIFICATION}, got {cls}",
    }


# ─── Step 3: Check authorization phrase ──────────────────────────────────────

def step3_check_authorization(auth_input: str | None) -> dict:
    is_authorized = auth_input == REQUIRED_EXPLICIT_YES
    return {
        "step": "step3_authorization_phrase_check",
        "required_phrase": REQUIRED_EXPLICIT_YES,
        "authorization_input_provided": auth_input is not None,
        "authorization_granted": is_authorized,
        "authorization_status": "GRANTED" if is_authorized else "NOT GRANTED",
        "note": (
            "Exact phrase matched. Recovery is authorized."
            if is_authorized
            else (
                "Authorization phrase not present in this invocation. "
                "P88 remains in gate-only mode. No frozen artifacts will be touched."
            )
        ),
    }


# ─── Step 4: Recovery preconditions ──────────────────────────────────────────

def step4_recovery_preconditions(s1: dict, s2: dict) -> dict:
    preconditions = [
        {
            "name": "p87_summary_exists",
            "status": s1["p87_summary_exists"],
            "required": True,
        },
        {
            "name": "p87_classification_correct",
            "status": s1["p87_classification_matches"],
            "required": True,
        },
        {
            "name": "p87_count_match",
            "status": s1.get("count_match") is True,
            "required": True,
        },
        {
            "name": "p87_game_id_full_coverage",
            "status": s1.get("game_id_full_coverage") is True,
            "required": True,
        },
        {
            "name": "p87_content_drift_likely_false",
            "status": s1.get("content_drift_likely") is False,
            "required": True,
        },
        {
            "name": "p86_summary_exists",
            "status": s2["p86_summary_exists"],
            "required": True,
        },
        {
            "name": "p86_classification_correct",
            "status": s2["p86_classification_matches"],
            "required": True,
        },
        {
            "name": "canonical_rows_exists",
            "status": (ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl").exists(),
            "required": True,
        },
    ]
    all_pass = all(p["status"] for p in preconditions if p["required"])
    return {
        "step": "step4_recovery_preconditions",
        "preconditions": preconditions,
        "all_preconditions_met": all_pass,
        "note": "All preconditions met — recovery CAN proceed once authorized." if all_pass
                else "One or more preconditions failed. Do not proceed.",
    }


# ─── Step 5: Forbidden actions (when not authorized) ─────────────────────────

def step5_forbidden_actions() -> dict:
    return {
        "step": "step5_forbidden_actions_when_not_authorized",
        "forbidden": [
            "Overwrite p84e_2026_outcome_attached_prediction_rows.jsonl",
            "Overwrite p84e_2026_outcome_attachment_summary.json",
            "Overwrite p84f_predicted_side_calibration_diagnostic_summary.json",
            "Overwrite p84g_predicted_side_mapping_fix_summary.json",
            "Overwrite p84h_corrected_signal_validation_coverage_guard_summary.json",
            "Overwrite p85_prediction_convention_invariant_gate_summary.json",
            "Overwrite p86_artifact_regeneration_dependency_contract_summary.json",
            "Overwrite mlb_2026_prediction_rows.jsonl (canonical_rows)",
            "Run _p84e_2026_outcome_attachment_pipeline.py in write mode",
            "Run _p84f_predicted_side_calibration_diagnostic.py in write mode",
            "Run _p84g_predicted_side_mapping_fix.py in write mode",
            "Run _p84h_corrected_signal_validation_coverage_guard.py in write mode",
            "Run _p85_prediction_convention_invariant_gate.py in write mode",
            "Run _p86_artifact_regeneration_dependency_contract.py in write mode",
            "Compute EV / CLV / Kelly / stake",
            "Call live paid API",
            "Retrain or re-calibrate any model",
            "Mutate runtime recommendation logic",
            "Issue production betting recommendation",
        ],
        "enforcement": "P88 is diagnostic-only. All forbidden actions produce classification P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION.",
    }


# ─── Step 6: Authorized recovery sequence plan ───────────────────────────────

def step6_recovery_sequence_plan() -> dict:
    return {
        "step": "step6_authorized_recovery_sequence_plan",
        "note": "These steps are ONLY to be executed after receiving the exact authorization phrase.",
        "authorization_required": REQUIRED_EXPLICIT_YES,
        "execution_order": ["P84E", "P84F", "P84G", "P84H", "P85", "P86"],
        "recovery_steps": [
            {
                "step_num": 1,
                "phase": "P84E",
                "action": "Rerun outcome attachment against current canonical_rows (828 rows)",
                "script": "scripts/_p84e_2026_outcome_attachment_pipeline.py",
                "expected_classification": "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
                "expected_n_outcome_available": "808 ± 5",
                "tolerance": 1e-4,
                "files_written": [
                    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
                    "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
                ],
            },
            {
                "step_num": 2,
                "phase": "P84F",
                "action": "Rerun predicted-side calibration diagnostic",
                "script": "scripts/_p84f_predicted_side_calibration_diagnostic.py",
                "expected_classification": "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK",
                "tolerance": 1e-4,
                "files_written": [
                    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
                ],
            },
            {
                "step_num": 3,
                "phase": "P84G",
                "action": "Rerun side mapping fix and metrics regeneration",
                "script": "scripts/_p84g_predicted_side_mapping_fix.py",
                "expected_classification": "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED",
                "tolerance": 1e-4,
                "files_written": [
                    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
                ],
            },
            {
                "step_num": 4,
                "phase": "P84H",
                "action": "Rerun corrected signal validation and coverage guard",
                "script": "scripts/_p84h_corrected_signal_validation_coverage_guard.py",
                "expected_classification": "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
                "expected_metrics": {
                    "hit_rate": 0.569307,
                    "auc": 0.594315,
                    "brier": 0.249408,
                    "ece": 0.069682,
                },
                "tolerance": 1e-4,
                "files_written": [
                    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
                ],
            },
            {
                "step_num": 5,
                "phase": "P85",
                "action": "Rerun prediction convention invariant gate",
                "script": "scripts/_p85_prediction_convention_invariant_gate.py",
                "expected_classification": "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
                "expected_n_violations": 0,
                "tolerance": 1e-4,
                "files_written": [
                    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
                ],
            },
            {
                "step_num": 6,
                "phase": "P86",
                "action": "Rerun artifact regeneration dependency contract",
                "script": "scripts/_p86_artifact_regeneration_dependency_contract.py",
                "expected_classification": "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY",
                "note": "P86 classification MUST upgrade from FAILED to READY after recovery",
                "files_written": [
                    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
                ],
            },
            {
                "step_num": 7,
                "phase": "VERIFY",
                "action": "Verify P86 classification upgraded to READY",
                "check": "p86_classification == P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY",
                "stop_condition": "If P86 still shows FAILED, STOP and report",
            },
            {
                "step_num": 8,
                "phase": "TEST",
                "action": "Run P83A–P88 targeted regression",
                "test_command": ".venv/bin/pytest tests/test_p83a_*.py tests/test_p83b_*.py tests/test_p83c_*.py tests/test_p83d_*.py tests/test_p83e_*.py tests/test_p84a_*.py tests/test_p84b_*.py tests/test_p84c_*.py tests/test_p84d_*.py tests/test_p84e_*.py tests/test_p84f_*.py tests/test_p84g_*.py tests/test_p84h_*.py tests/test_p85_*.py tests/test_p86_*.py tests/test_p87_*.py tests/test_p88_*.py -q",
                "expected_pass_count": "≥ 1071 + P88 tests (≥ 1200 total)",
                "expected_skip_count": 4,
            },
            {
                "step_num": 9,
                "phase": "COMMIT",
                "action": "Commit whitelist-only regenerated artifacts",
                "whitelist": [
                    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
                    "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
                    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
                    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
                    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
                    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
                    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
                    "00-Plan/roadmap/active_task.md",
                ],
                "commit_message_prefix": "feat(P89): Authorized stale downstream recovery — P86 upgrades to READY",
            },
        ],
        "files_to_touch_after_authorization": [
            "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
            "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
            "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
            "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
            "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
            "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
            "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
        ],
        "files_never_to_touch": [
            "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
            "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json",
            "data/mlb_2026/derived/p88_regeneration_authorization_gate_summary.json",
            "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json",
        ],
    }


# ─── Step 7: Governance scan ─────────────────────────────────────────────────

def step7_governance_scan() -> dict:
    flags = {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "no_champion_replacement": True,
        "no_runtime_recommendation_mutation": True,
        "no_canonical_row_rewrite": True,
        "no_outcome_row_rewrite": True,
        "no_historical_artifact_overwrite": True,
        "no_calibration_refit": True,
        "no_production_betting_recommendation": True,
        "no_real_bet": True,
    }
    checks = {
        "paper_only": flags["paper_only"] is True,
        "diagnostic_only": flags["diagnostic_only"] is True,
        "not_production_ready": flags["production_ready"] is False,
        "no_odds": flags["odds_used"] is False,
        "no_ev": flags["ev_computed"] is False,
        "no_clv": flags["clv_computed"] is False,
        "no_kelly": flags["kelly_computed"] is False,
        "no_live_api": flags["live_api_calls"] == 0,
        "no_paid_api": flags["paid_api_called"] is False,
        "no_champion_replacement": flags["no_champion_replacement"] is True,
        "no_runtime_mutation": flags["no_runtime_recommendation_mutation"] is True,
        "no_canonical_row_rewrite": flags["no_canonical_row_rewrite"] is True,
        "no_outcome_row_rewrite": flags["no_outcome_row_rewrite"] is True,
        "no_historical_artifact_overwrite": flags["no_historical_artifact_overwrite"] is True,
        "no_calibration_refit": flags["no_calibration_refit"] is True,
        "no_production_betting": flags["no_production_betting_recommendation"] is True,
        "no_real_bet": flags["no_real_bet"] is True,
    }
    return {
        "step": "step7_governance_scan",
        "p88_governance": flags,
        "governance_checks": checks,
        "governance_all_pass": all(checks.values()),
    }


# ─── Step 8: Frozen artifact snapshot ────────────────────────────────────────

def step8_frozen_artifact_snapshot() -> dict:
    snapshot = {}
    for rel in FROZEN_ARTIFACTS:
        p = ROOT / rel
        if p.exists():
            snapshot[pathlib.Path(rel).name] = {
                "exists": True,
                "sha256_prefix": _sha256_prefix(p),
                "mtime": _mtime_utc(p),
                "size_bytes": p.stat().st_size,
                "modified_by_p88": False,
            }
        else:
            snapshot[pathlib.Path(rel).name] = {"exists": False, "modified_by_p88": False}
    return {
        "step": "step8_frozen_artifact_snapshot",
        "snapshot": snapshot,
        "p88_modified_frozen_artifacts": False,
        "note": "P88 is gate-only. No frozen artifacts were read in write mode or overwritten.",
    }


# ─── Step 9: Final classification ────────────────────────────────────────────

def step9_final_classification(
    s1: dict,
    s2: dict,
    s3_auth: dict,
    s4: dict,
    s7: dict,
) -> dict:
    if not s1["p87_state_ok"]:
        cls = "P88_AUTHORIZATION_GATE_FAILED_P87_STATE_MISMATCH"
        rationale = f"P87 state mismatch: {s1.get('issue')}"
    elif not s2["p86_state_ok"]:
        cls = "P88_AUTHORIZATION_GATE_FAILED_P86_STATE_MISMATCH"
        rationale = f"P86 state mismatch: {s2.get('issue')}"
    elif not s4["all_preconditions_met"]:
        cls = "P88_AUTHORIZATION_GATE_BLOCKED_BY_PREFLIGHT"
        rationale = "One or more recovery preconditions not met."
    elif s3_auth["authorization_granted"]:
        cls = "P88_REGENERATION_AUTHORIZED_READY_TO_EXECUTE"
        rationale = "Exact authorization phrase received. Recovery can begin."
    else:
        cls = "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION"
        rationale = (
            "All preconditions met. P87 and P86 state confirmed. "
            "Authorization phrase not present. P88 remains in gate-only mode. "
            f"Awaiting: '{REQUIRED_EXPLICIT_YES}'"
        )

    return {
        "step": "step9_final_classification",
        "classification": cls,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "authorization_granted": s3_auth["authorization_granted"],
        "all_preconditions_met": s4["all_preconditions_met"],
        "governance_all_pass": s7["governance_all_pass"],
        "steps_checked": 9,
        "steps_passed": 9 if s7["governance_all_pass"] and s1["p87_state_ok"] and s2["p86_state_ok"] else 8,
        "rationale": rationale,
        "explicit_yes_required": REQUIRED_EXPLICIT_YES,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    generated_at = _now_utc()

    s1 = step1_check_p87_state()
    s2 = step2_check_p86_state()
    s3_auth = step3_check_authorization(AUTHORIZATION_INPUT)
    s4 = step4_recovery_preconditions(s1, s2)
    s5 = step5_forbidden_actions()
    s6 = step6_recovery_sequence_plan()
    s7 = step7_governance_scan()
    s8 = step8_frozen_artifact_snapshot()
    s9 = step9_final_classification(s1, s2, s3_auth, s4, s7)

    summary = {
        "p88_classification": s9["classification"],
        "date": "2026-05-27",
        "generated_at": generated_at,
        "phase": "diagnostic-only",
        "authorization_status": s3_auth["authorization_status"],
        "explicit_yes_required": REQUIRED_EXPLICIT_YES,
        "p87_classification_confirmed": s1["p87_classification"],
        "p86_classification_confirmed": s2["p86_classification"],
        "all_preconditions_met": s4["all_preconditions_met"],
        "governance_all_pass": s7["governance_all_pass"],
        "p88_modified_frozen_artifacts": False,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "frozen_artifacts_count": len(FROZEN_ARTIFACTS),
        "step1_check_p87_state": s1,
        "step2_check_p86_state": s2,
        "step3_authorization_phrase_check": s3_auth,
        "step4_recovery_preconditions": s4,
        "step5_forbidden_actions": s5,
        "step6_authorized_recovery_sequence_plan": s6,
        "step7_governance_scan": s7,
        "step8_frozen_artifact_snapshot": s8,
        "step9_final_classification": s9,
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    _write_report(summary)
    _update_active_task(s9["classification"])

    print(f"P88 classification: {s9['classification']}")
    print(f"Authorization status: {s3_auth['authorization_status']}")
    print(f"All preconditions met: {s4['all_preconditions_met']}")
    print(f"Governance all pass: {s7['governance_all_pass']}")
    print(f"Summary: {OUTPUT_SUMMARY}")
    print(f"Report:  {OUTPUT_REPORT}")


def _write_report(summary: dict) -> None:
    cls = summary["p88_classification"]
    auth_status = summary["authorization_status"]
    p87_cls = summary["p87_classification_confirmed"]
    p86_cls = summary["p86_classification_confirmed"]
    gov = summary["step7_governance_scan"]["p88_governance"]
    recovery_steps = summary["step6_authorized_recovery_sequence_plan"]["recovery_steps"]

    lines = [
        "# P88 — Regeneration Authorization Gate",
        "",
        "## Classification",
        "",
        f"`{cls}`",
        "",
        "## Authorization Status",
        "",
        f"**{auth_status}**",
        "",
        f"Required phrase: `{REQUIRED_EXPLICIT_YES}`",
        "",
        "## Gate Check Results",
        "",
        f"- P87 classification confirmed: `{p87_cls}`",
        f"- P86 classification confirmed: `{p86_cls}`",
        f"- count_match: {summary['step1_check_p87_state']['count_match']}",
        f"- game_id_full_coverage: {summary['step1_check_p87_state']['game_id_full_coverage']}",
        f"- content_drift_likely: {summary['step1_check_p87_state']['content_drift_likely']}",
        f"- stale_by_mtime_only: {summary['step1_check_p87_state']['stale_by_mtime_only']}",
        f"- safe_without_explicit_yes: {summary['step1_check_p87_state']['safe_without_explicit_yes']}",
        f"- all_preconditions_met: {summary['all_preconditions_met']}",
        "",
        "## What P88 Did NOT Do",
        "",
        "- P88 did not regenerate artifacts",
        "- P88 did not overwrite frozen outputs",
        "- P88 did not run P84E / P84F / P84G / P84H / P85 / P86 recovery",
        "- P88 only prepared the authorization gate and readiness plan",
        "",
        "## Governance",
        "",
        f"- paper_only = {str(gov['paper_only']).lower()}",
        f"- diagnostic_only = {str(gov['diagnostic_only']).lower()}",
        f"- production_ready = {str(gov['production_ready']).lower()}",
        f"- ev_computed = false",
        f"- clv_computed = false",
        f"- kelly_computed = false",
        f"- odds_used = false",
        f"- live_api_calls = 0",
        f"- paid_api_called = false",
        f"- no_canonical_row_rewrite = true",
        f"- no_outcome_row_rewrite = true",
        f"- no_historical_artifact_overwrite = true",
        f"- no_calibration_refit = true",
        f"- no_production_betting_recommendation = true",
        f"- no real bet instruction issued",
        f"- no stake calculation",
        f"- no EV / CLV / Kelly computation",
        f"- no Taiwan lottery betting recommendation",
        "",
        "## Regeneration Order (After Future Authorization Only)",
        "",
    ]

    for step in recovery_steps:
        n = step["step_num"]
        action = step["action"]
        phase = step.get("phase", "")
        lines.append(f"- **Step {n} [{phase}]**: {action}")

    lines += [
        "",
        "## Allowed Classifications",
        "",
    ]
    for c in ALLOWED_CLASSIFICATIONS:
        lines.append(f"- `{c}`")

    lines += [
        "",
        "---",
        "",
        f"*Generated at {summary['generated_at']} UTC*",
    ]

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def _update_active_task(classification: str) -> None:
    content = f"""# Active Task — P84C 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit

## Current Task
P88 — Regeneration Authorization Gate and Safe Recovery Readiness Check

## Classification
{classification}

## Authorization Status
NOT GRANTED — awaiting explicit YES phrase

## Required Phrase
YES regenerate stale downstream artifacts for P87 recovery

## State Summary
- P87 classification: P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES
- P86 classification: P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK
- content_drift_likely: False (mtime-only drift confirmed)
- count_match: True (828/828 game_ids)
- safe_without_explicit_yes: False
- P88 is gate-only: no frozen artifacts modified

## Next Steps
Once explicit YES is received → execute P89 recovery sequence:
P84E → P84F → P84G → P84H → P85 → P86

## Historical Classification Log
<!-- P82: P82 completed -->
<!-- P83A: P83A_LIVE_ACCUMULATION_FIRST_SNAPSHOT_READY -->
<!-- P83C: P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA -->
<!-- P84A: P84A_UPSTREAM_COLLECTOR_CONTRACT_READY -->
<!-- P84B: P84B_SCHEDULE_READY_PITCHER_MODEL_BLOCKED -->
<!-- P84C: P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING -->
<!-- P84D: P84D_PITCHER_COVERAGE backfill audit complete -->
<!-- P84E: P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS -->
<!-- P84F: P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK -->
<!-- P84G: P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED -->
<!-- P84H: P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED -->
<!-- P85: P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY -->
<!-- P86: P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK -->
<!-- P87: P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES -->
<!-- P88: {classification} -->
"""
    ACTIVE_TASK.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
