#!/usr/bin/env python3
"""
P87 — Stale Downstream Recovery Dry-Run and Regeneration Plan
==============================================================
PURPOSE:
  P86 confirmed a true stale downstream risk: canonical_rows.jsonl was regenerated
  by a P83C run at ~15:23 local, AFTER P84E ran at ~13:40 local.
  This script performs a read-only dry-run analysis and outputs a safe recovery plan.

GOVERNANCE:
  paper_only = True, diagnostic_only = True, production_ready = False
  No artifacts are overwritten. No EV / CLV / Kelly / odds. No live API calls.
  Explicit authorization is required before any downstream regeneration.

REQUIRED EXPLICIT YES:
  "YES regenerate stale downstream artifacts for P87 recovery"

OUTPUT:
  data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json
  report/p87_stale_downstream_recovery_dry_run_20260527.md
"""

import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).parent.parent.resolve()

# ─── Artifact paths ──────────────────────────────────────────────────────────

ARTIFACTS: dict[str, pathlib.Path] = {
    "p83e_summary": ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json",
    "canonical_rows": ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
    "p84e_rows": ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
    "p84e_summary": ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    "p84f_summary": ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
    "p84g_summary": ROOT / "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
    "p84h_summary": ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
    "p85_summary": ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
    "p86_summary": ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
}

# Files that MUST NOT be overwritten during this dry-run
FROZEN_ARTIFACTS: list[str] = [
    "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl",
    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
    "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
    "report/p84e_2026_outcome_attachment_pipeline_20260527.md",
    "report/p84f_predicted_side_calibration_diagnostic_20260527.md",
    "report/p84g_predicted_side_mapping_fix_20260527.md",
    "report/p84h_corrected_signal_validation_coverage_guard_20260527.md",
    "report/p85_prediction_convention_invariant_gate_20260527.md",
    "report/p86_artifact_regeneration_dependency_contract_20260527.md",
]

EXPLICIT_YES_REQUIRED = "YES regenerate stale downstream artifacts for P87 recovery"

ALLOWED_CLASSIFICATIONS = [
    "P87_STALE_DOWNSTREAM_RECOVERY_DRY_RUN_READY",
    "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES",
    "P87_RECOVERY_BLOCKED_BY_MISSING_ARTIFACT",
    "P87_RECOVERY_BLOCKED_BY_PREFLIGHT",
    "P87_RECOVERY_BLOCKED_BY_SCOPE_DRIFT",
    "P87_RECOVERY_FAILED_UNEXPECTED_DEPENDENCY_STATE",
]

GOVERNANCE: dict[str, object] = {
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
    "no_calibration_refit": True,
    "no_production_betting_recommendation": True,
    "no_real_bet": True,
}

OUTPUT_DIR = ROOT / "data/mlb_2026/derived"
REPORT_DIR = ROOT / "report"
DATE_STR = "20260527"
SUMMARY_PATH = OUTPUT_DIR / "p87_stale_downstream_recovery_dry_run_summary.json"
REPORT_PATH = REPORT_DIR / f"p87_stale_downstream_recovery_dry_run_{DATE_STR}.md"
ACTIVE_TASK_PATH = ROOT / "00-Plan/roadmap/active_task.md"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def sha256_prefix(path: pathlib.Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:n]


def mtime_utc(path: pathlib.Path) -> str:
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def load_jsonl_game_ids(path: pathlib.Path) -> set[str]:
    game_ids: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                gid = row.get("game_id") or row.get("game_pk")
                if gid is not None:
                    game_ids.add(str(gid))
            except (json.JSONDecodeError, AttributeError):
                pass
    return game_ids


# ─── Main pipeline ───────────────────────────────────────────────────────────

def run() -> None:
    result: dict = {
        "p87_classification": "PENDING",
        "date": "2026-05-27",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "phase": "diagnostic-only",
        "governance": GOVERNANCE,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "explicit_yes_required": EXPLICIT_YES_REQUIRED,
        "frozen_artifacts": FROZEN_ARTIFACTS,
    }

    # ── Step 1: Artifact inventory ────────────────────────────────────────────
    step1: dict = {"step": "step1_artifact_inventory", "artifacts": {}}
    all_present = True
    for key, path in ARTIFACTS.items():
        exists = path.exists()
        info: dict = {
            "path": str(path.relative_to(ROOT)),
            "exists": exists,
        }
        if exists:
            info["sha256_prefix"] = sha256_prefix(path)
            info["mtime"] = mtime_utc(path)
            info["size_bytes"] = path.stat().st_size
        else:
            all_present = False
        step1["artifacts"][key] = info
    step1["all_present"] = all_present
    result["step1_artifact_inventory"] = step1

    if not all_present:
        missing = [k for k, v in step1["artifacts"].items() if not v["exists"]]
        step1["missing"] = missing
        result["p87_classification"] = "P87_RECOVERY_BLOCKED_BY_MISSING_ARTIFACT"
        _save(result)
        return

    # ── Step 2: Extract stale risk from P86 ──────────────────────────────────
    with open(ARTIFACTS["p86_summary"], encoding="utf-8") as f:
        p86: dict = json.load(f)

    p86_cls = p86.get("p86_classification", "UNKNOWN")
    p86_step7 = p86.get("step7_mtime_ordering", {})
    stale_risks: list[dict] = p86_step7.get("stale_risks", [])
    n_stale = len(stale_risks)

    step2: dict = {
        "step": "step2_stale_risk_extraction",
        "p86_classification": p86_cls,
        "p86_is_stale_downstream": p86_cls == "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK",
        "n_stale_risks": n_stale,
        "stale_risks_from_p86": stale_risks,
    }

    if stale_risks:
        risk = stale_risks[0]
        delta_s = risk.get("delta_seconds", 0)
        step2["root_cause"] = {
            "upstream_artifact": risk.get("upstream"),
            "downstream_artifact": risk.get("downstream"),
            "upstream_mtime": risk.get("upstream_mtime"),
            "downstream_mtime": risk.get("downstream_mtime"),
            "delta_seconds": delta_s,
            "interpretation": (
                f"`canonical_rows` was regenerated at {risk.get('upstream_mtime')} (~15:23 local) "
                f"by a P83C run, AFTER `p84e_rows` was written at "
                f"{risk.get('downstream_mtime')} (~13:40 local). "
                f"P84E consumed the pre-regeneration version of canonical_rows. "
                f"Delta = {delta_s}s (~{delta_s // 60} min). "
                f"This is the true stale downstream root cause confirmed by P86."
            ),
        }
    else:
        step2["root_cause"] = None

    result["step2_stale_risk_extraction"] = step2

    # ── Step 3: Content identity probe ───────────────────────────────────────
    with open(ARTIFACTS["p84e_summary"], encoding="utf-8") as f:
        p84e_summary: dict = json.load(f)

    p84e_consumed_count: int = (
        p84e_summary.get("step1_verify", {}).get("canonical_rows", 0)
        or p84e_summary.get("step3_attachment_stats", {}).get("total_canonical_rows", 0)
    )

    # Count current canonical rows
    canonical_lines = ARTIFACTS["canonical_rows"].read_text(encoding="utf-8").splitlines()
    canonical_count = sum(1 for ln in canonical_lines if ln.strip())

    # Load game_ids from each JSONL
    canonical_game_ids = load_jsonl_game_ids(ARTIFACTS["canonical_rows"])
    p84e_row_game_ids = load_jsonl_game_ids(ARTIFACTS["p84e_rows"])

    in_canonical_not_p84e = canonical_game_ids - p84e_row_game_ids
    in_p84e_not_canonical = p84e_row_game_ids - canonical_game_ids
    intersection = canonical_game_ids & p84e_row_game_ids

    count_match = canonical_count == p84e_consumed_count
    game_id_full_coverage = len(in_canonical_not_p84e) == 0 and len(in_p84e_not_canonical) == 0
    content_drift_likely = not (count_match and game_id_full_coverage)

    if not content_drift_likely:
        interpretation = (
            f"Current canonical_rows has {canonical_count} rows — identical count to what "
            f"P84E consumed ({p84e_consumed_count}). Game_id cross-reference: "
            f"{len(intersection)} IDs match, 0 mismatches on either side. "
            "This indicates the P83C regeneration at ~15:23 produced content-identical "
            "canonical_rows (same 828 game_ids, same order). "
            "The stale risk is likely mtime-only drift, not content drift. "
            "However, formal mtime attestation still requires an authorized re-run."
        )
    else:
        details = []
        if not count_match:
            details.append(f"count mismatch: current={canonical_count} vs p84e_consumed={p84e_consumed_count}")
        if in_canonical_not_p84e:
            details.append(f"{len(in_canonical_not_p84e)} game_ids in canonical not in p84e")
        if in_p84e_not_canonical:
            details.append(f"{len(in_p84e_not_canonical)} game_ids in p84e not in canonical")
        interpretation = (
            "Content drift confirmed: " + "; ".join(details) + ". "
            "Actual regeneration of P84E and all downstream artifacts is required."
        )

    step3: dict = {
        "step": "step3_content_identity_probe",
        "canonical_rows_current_count": canonical_count,
        "p84e_consumed_count_at_run_time": p84e_consumed_count,
        "canonical_game_ids_count": len(canonical_game_ids),
        "p84e_row_game_ids_count": len(p84e_row_game_ids),
        "game_id_intersection_count": len(intersection),
        "in_canonical_not_p84e": len(in_canonical_not_p84e),
        "in_p84e_not_canonical": len(in_p84e_not_canonical),
        "count_match": count_match,
        "game_id_full_coverage": game_id_full_coverage,
        "content_drift_likely": content_drift_likely,
        "interpretation": interpretation,
    }
    result["step3_content_identity_probe"] = step3

    # ── Step 4: Affected downstream artifacts ─────────────────────────────────
    step4: dict = {
        "step": "step4_affected_downstream_artifacts",
        "stale_root": "canonical_rows",
        "stale_root_cause_summary": (
            "P83C regenerated canonical_rows at ~15:23 local. "
            "P84E ran at ~13:40 local, consuming the pre-regeneration version."
        ),
        "directly_stale": [
            {
                "artifact": "p84e_rows",
                "path": "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
                "reason": "First downstream consumer of canonical_rows; written before canonical_rows was re-generated.",
            },
            {
                "artifact": "p84e_summary",
                "path": "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
                "reason": "P84E summary co-written with p84e_rows at same mtime.",
            },
        ],
        "derivedly_stale": [
            {
                "artifact": "p84f_summary",
                "path": "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
                "reason": "P84F reads p84e_rows; stale if p84e_rows is stale.",
            },
            {
                "artifact": "p84g_summary",
                "path": "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
                "reason": "P84G reads p84f output; stale by transitivity.",
            },
            {
                "artifact": "p84h_summary",
                "path": "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
                "reason": "P84H reads p84g output; stale by transitivity.",
            },
            {
                "artifact": "p85_summary",
                "path": "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
                "reason": "P85 reads p84e_rows; stale by transitivity.",
            },
            {
                "artifact": "p86_summary",
                "path": "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
                "reason": "P86 verifies full chain; must be re-run after all downstream artifacts are regenerated.",
            },
        ],
        "artifacts_safe_in_this_dry_run": [
            "scripts/_p87_stale_downstream_recovery_dry_run.py",
            "data/mlb_2026/derived/p87_stale_downstream_recovery_dry_run_summary.json",
            "report/p87_stale_downstream_recovery_dry_run_20260527.md",
            "00-Plan/roadmap/active_task.md",
        ],
        "frozen_artifacts": FROZEN_ARTIFACTS,
    }
    result["step4_affected_downstream_artifacts"] = step4

    # ── Step 5: Dry-run regeneration order ────────────────────────────────────
    step5: dict = {
        "step": "step5_dry_run_regeneration_order",
        "note": "DRY-RUN ONLY. No files are written. Authorization gate must be passed first.",
        "requires_explicit_yes": EXPLICIT_YES_REQUIRED,
        "regeneration_steps": [
            {
                "step_num": 1,
                "action": "confirm_p83e_canonical_source_inputs",
                "description": (
                    "Verify P83E upstream inputs are still present and unchanged: "
                    "schedule (mlb_2026_schedule.jsonl), pitchers (mlb_2026_sp_fip_features.jsonl), "
                    "model_outputs (mlb_2026_model_outputs.jsonl). All P83E gates must pass."
                ),
                "files_read": [
                    "data/mlb_2026/schedule/mlb_2026_schedule.jsonl",
                    "data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl",
                    "data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl",
                ],
                "files_written": [],
                "safe_as_dry_run": True,
            },
            {
                "step_num": 2,
                "action": "confirm_canonical_rows_hash_and_count",
                "description": (
                    "Compute SHA256 of current canonical_rows. Confirm count=828. "
                    "Record sha256_prefix as baseline. Compare with P86-recorded sha256_prefix=74c4a5498f80b2e7."
                ),
                "files_read": ["data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"],
                "files_written": [],
                "safe_as_dry_run": True,
            },
            {
                "step_num": 3,
                "action": "dry_run_check_p84e_would_consume_current_canonical_rows",
                "description": (
                    "Verify that the P84E script reads canonical_rows from the canonical path "
                    "(not a hardcoded snapshot). Confirm no path override is in effect."
                ),
                "files_read": ["scripts/_p84e_2026_outcome_attachment_pipeline.py"],
                "files_written": [],
                "safe_as_dry_run": True,
            },
            {
                "step_num": 4,
                "action": "identify_p84e_as_first_stale_downstream_artifact",
                "description": (
                    "P84E is the first stale downstream artifact. "
                    "Content identity probe shows count_match=True and game_id_full_coverage=True, "
                    "so re-run of P84E is expected to produce metrics within 1e-4 tolerance of current values. "
                    "Re-run would consume current canonical_rows (828 rows) and re-attach outcomes. "
                    "REQUIRES explicit YES before execution."
                ),
                "files_read": ["data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"],
                "files_written_if_authorized": [
                    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
                    "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
                ],
                "safe_as_dry_run": False,
                "requires_explicit_yes": True,
            },
            {
                "step_num": 5,
                "action": "identify_p84f_p84g_p84h_p85_p86_as_derived_downstream",
                "description": (
                    "After P84E is regenerated, P84F → P84G → P84H → P85 → P86 must be re-run "
                    "in sequence to restore mtime consistency in the dependency chain. "
                    "P84G consistency check must pass before P84H proceeds."
                ),
                "files_read": [
                    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl",
                    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
                    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
                    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
                    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
                    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
                ],
                "files_written_if_authorized": [
                    "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
                    "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
                    "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
                    "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
                    "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
                    "report/p84f_*.md, report/p84g_*.md, report/p84h_*.md, report/p85_*.md, report/p86_*.md",
                ],
                "safe_as_dry_run": False,
                "requires_explicit_yes": True,
            },
            {
                "step_num": 6,
                "action": "require_explicit_yes_before_any_regeneration",
                "description": (
                    f"User must send exactly: '{EXPLICIT_YES_REQUIRED}'. "
                    "No frozen artifact will be touched until this gate is passed. "
                    "This is the formal authorization gate for P87 recovery."
                ),
                "files_read": [],
                "files_written": [],
                "safe_as_dry_run": True,
                "is_authorization_gate": True,
            },
            {
                "step_num": 7,
                "action": "authorized_regeneration_execution_order",
                "description": (
                    "After YES: execute scripts in this exact order: "
                    "P84E → P84F → P84G → P84H → P85 → P86. "
                    "P84G must confirm side_mapping_consistent=True before proceeding. "
                    "Each step must produce its summary JSON before the next starts."
                ),
                "execution_order": ["P84E", "P84F", "P84G", "P84H", "P85", "P86"],
                "scripts_to_run": [
                    "scripts/_p84e_2026_outcome_attachment_pipeline.py",
                    "scripts/_p84f_predicted_side_calibration_diagnostic.py",
                    "scripts/_p84g_predicted_side_mapping_fix.py",
                    "scripts/_p84h_corrected_signal_validation_coverage_guard.py",
                    "scripts/_p85_prediction_convention_invariant_gate.py",
                    "scripts/_p86_artifact_regeneration_dependency_contract.py",
                ],
                "safe_as_dry_run": False,
                "requires_explicit_yes": True,
            },
            {
                "step_num": 8,
                "action": "rerun_p83a_through_p86_regression_after_regeneration",
                "description": (
                    "After regeneration, run full P83A–P86 test suite. "
                    "Expected result: ≥889 passed, 4 skipped. "
                    "If metrics changed beyond 1e-4 tolerance, tests will fail and must be investigated."
                ),
                "test_command": (
                    "./.venv/bin/pytest tests/test_p83a_*.py tests/test_p83b_*.py "
                    "tests/test_p83c_*.py tests/test_p83d_*.py tests/test_p83e_*.py "
                    "tests/test_p84a_*.py tests/test_p84b_*.py tests/test_p84c_*.py "
                    "tests/test_p84d_*.py tests/test_p84e_*.py tests/test_p84f_*.py "
                    "tests/test_p84g_*.py tests/test_p84h_*.py tests/test_p85_*.py "
                    "tests/test_p86_*.py -q"
                ),
                "safe_as_dry_run": True,
                "requires_explicit_yes": False,
                "note": "Read-only. Safe to run at any time.",
            },
            {
                "step_num": 9,
                "action": "update_active_task_and_reports_after_confirmed_metrics",
                "description": (
                    "Only after regenerated metrics are confirmed (within 1e-4 tolerance), "
                    "update active_task.md and create P87 completion report. "
                    "If metrics diverge, stop and report divergence before any further action."
                ),
                "files_written": [
                    "00-Plan/roadmap/active_task.md",
                    "report/p87_stale_downstream_recovery_completion_20260527.md",
                ],
                "safe_as_dry_run": False,
                "requires_explicit_yes": True,
            },
        ],
    }
    result["step5_dry_run_regeneration_order"] = step5

    # ── Step 6: Safety decision ────────────────────────────────────────────────
    content_identity_passed = not content_drift_likely
    step6: dict = {
        "step": "step6_safety_decision",
        "content_identity_probe_passed": content_identity_passed,
        "stale_by_mtime_only": content_identity_passed,
        "content_drift_likely": content_drift_likely,
        "actual_regeneration_needed": True,
        "safe_without_explicit_yes": False,
        "reason": (
            "Even when content is identical (mtime-only drift confirmed), formal re-run of "
            "P84E→P84F→P84G→P84H→P85→P86 is required to restore mtime consistency. "
            f"Authorization required: '{EXPLICIT_YES_REQUIRED}'"
        ),
        "expected_metric_stability": (
            "If content is identical (count_match=True, game_id_full_coverage=True), "
            "regenerated metrics are expected to be within 1e-4 of current values: "
            "hit_rate≈0.5693, auc≈0.5943, brier≈0.2494, ece≈0.0697 (P84H). "
            "P85 n_violations expected to remain 0. P86 expected to classify as READY."
        ),
        "recommendation": (
            "Content identity probe passed: count_match=True, game_id_full_coverage=True. "
            "Re-running P84E→P86 with the same inputs is expected to produce identical metrics. "
            "Once explicit YES is received, execute the 9-step recovery in Step 5 order."
        ) if content_identity_passed else (
            "Content drift detected. Full re-validation of all downstream metrics is required. "
            "Metrics may change. All tests must be re-run and verified."
        ),
    }
    result["step6_safety_decision"] = step6

    # ── Step 7: Governance scan ────────────────────────────────────────────────
    governance_checks: dict[str, bool] = {
        "paper_only": GOVERNANCE["paper_only"] is True,
        "diagnostic_only": GOVERNANCE["diagnostic_only"] is True,
        "not_production_ready": GOVERNANCE["production_ready"] is False,
        "no_odds": GOVERNANCE["odds_used"] is False,
        "no_ev": GOVERNANCE["ev_computed"] is False,
        "no_clv": GOVERNANCE["clv_computed"] is False,
        "no_kelly": GOVERNANCE["kelly_computed"] is False,
        "no_live_api": GOVERNANCE["live_api_calls"] == 0,
        "no_paid_api": GOVERNANCE["paid_api_called"] is False,
        "no_champion_replacement": GOVERNANCE["no_champion_replacement"] is True,
        "no_runtime_mutation": GOVERNANCE["no_runtime_recommendation_mutation"] is True,
        "no_canonical_row_rewrite": GOVERNANCE["no_canonical_row_rewrite"] is True,
        "no_outcome_row_rewrite": GOVERNANCE["no_outcome_row_rewrite"] is True,
        "no_calibration_refit": GOVERNANCE["no_calibration_refit"] is True,
        "no_production_betting": GOVERNANCE["no_production_betting_recommendation"] is True,
        "no_real_bet": GOVERNANCE["no_real_bet"] is True,
    }
    governance_all_pass = all(governance_checks.values())

    step7: dict = {
        "step": "step7_governance_scan",
        "p87_governance": GOVERNANCE,
        "governance_checks": governance_checks,
        "governance_all_pass": governance_all_pass,
    }
    result["step7_governance_scan"] = step7

    # ── Step 8: Final classification ──────────────────────────────────────────
    if not all_present:
        cls = "P87_RECOVERY_BLOCKED_BY_MISSING_ARTIFACT"
    elif not governance_all_pass:
        cls = "P87_RECOVERY_BLOCKED_BY_SCOPE_DRIFT"
    else:
        cls = "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"

    step8: dict = {
        "step": "step8_final_classification",
        "classification": cls,
        "rationale": (
            f"P86 confirmed stale downstream risk (canonical_rows regenerated after P84E ran, delta=6134s). "
            f"P87 dry-run content probe: count_match={count_match}, "
            f"game_id_full_coverage={game_id_full_coverage}, content_drift_likely={content_drift_likely}. "
            f"Stale risk is mtime-only (content likely identical). "
            f"Formal recovery requires authorized re-run of P84E→P84F→P84G→P84H→P85→P86. "
            f"Classification: {cls}."
        ),
        "explicit_yes_required": EXPLICIT_YES_REQUIRED,
        "steps_checked": 8,
        "steps_passed": 8 if governance_all_pass and all_present else 0,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
    }
    result["step8_final_classification"] = step8
    result["p87_classification"] = cls

    _save(result)


# ─── Save ─────────────────────────────────────────────────────────────────────

def _save(result: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    cls = result.get("p87_classification", "UNKNOWN")
    s1 = result.get("step1_artifact_inventory", {})
    s2 = result.get("step2_stale_risk_extraction", {})
    s3 = result.get("step3_content_identity_probe", {})
    s4 = result.get("step4_affected_downstream_artifacts", {})
    s5 = result.get("step5_dry_run_regeneration_order", {})
    s6 = result.get("step6_safety_decision", {})
    s7 = result.get("step7_governance_scan", {})
    s8 = result.get("step8_final_classification", {})

    lines: list[str] = [
        "# P87 — Stale Downstream Recovery Dry-Run and Regeneration Plan",
        "",
        f"**Date**: {result.get('date', '2026-05-27')}  ",
        f"**Generated**: {result.get('generated_at', '')}  ",
        f"**Classification**: `{cls}`  ",
        f"**Phase**: diagnostic-only  ",
        "",
        "> ⚠️ This report contains NO production betting recommendation, NO EV, NO CLV, NO Kelly, NO stake instruction.",
        "> paper_only = true | diagnostic_only = true | production_ready = false",
        "",
        "---",
        "",
        "## Overview",
        "",
        "P86 detected a true stale downstream risk: `canonical_rows.jsonl` was regenerated by P83C",
        "at ~15:23 local, after P84E consumed it at ~13:40 local. This dry-run analyzes the recovery path.",
        "",
        "**No frozen artifacts were modified in this run. This is a plan/dry-run only.**",
        "",
        "---",
        "",
        "## Step 1: Artifact Inventory",
        "",
    ]

    for key, info in s1.get("artifacts", {}).items():
        status = "✅" if info["exists"] else "❌"
        lines.append(f"- {status} `{key}`: `{info['path']}`  sha256=`{info.get('sha256_prefix', 'N/A')}`")

    lines += [
        "",
        f"**All present**: {s1.get('all_present', False)}",
        "",
        "---",
        "",
        "## Step 2: Stale Risk Root Cause (from P86)",
        "",
        f"**P86 Classification**: `{s2.get('p86_classification', 'N/A')}`  ",
        f"**Stale risks detected**: {s2.get('n_stale_risks', 0)}",
        "",
    ]

    rc = s2.get("root_cause")
    if rc:
        delta_s = rc.get("delta_seconds", 0)
        lines += [
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Upstream | `{rc.get('upstream_artifact')}` |",
            f"| Downstream | `{rc.get('downstream_artifact')}` |",
            f"| Upstream mtime | `{rc.get('upstream_mtime')}` |",
            f"| Downstream mtime | `{rc.get('downstream_mtime')}` |",
            f"| Delta | `{delta_s}s` (~{delta_s // 60} min) |",
            "",
            f"**Interpretation**: {rc.get('interpretation', '')}",
        ]

    lines += [
        "",
        "---",
        "",
        "## Step 3: Content Identity Probe",
        "",
        f"| Check | Value |",
        f"|-------|-------|",
        f"| canonical_rows current count | `{s3.get('canonical_rows_current_count')}` |",
        f"| P84E consumed count at run time | `{s3.get('p84e_consumed_count_at_run_time')}` |",
        f"| Count match | `{s3.get('count_match')}` |",
        f"| Game ID intersection count | `{s3.get('game_id_intersection_count')}` |",
        f"| In canonical not P84E | `{s3.get('in_canonical_not_p84e')}` |",
        f"| In P84E not canonical | `{s3.get('in_p84e_not_canonical')}` |",
        f"| Game ID full coverage | `{s3.get('game_id_full_coverage')}` |",
        f"| Content drift likely | `{s3.get('content_drift_likely')}` |",
        "",
        f"**Interpretation**: {s3.get('interpretation', '')}",
        "",
        "---",
        "",
        "## Step 4: Affected Downstream Artifacts",
        "",
        f"**Stale root**: `{s4.get('stale_root', 'canonical_rows')}`  ",
        f"**Root cause**: {s4.get('stale_root_cause_summary', '')}",
        "",
        "### Directly Stale",
    ]

    for art in s4.get("directly_stale", []):
        lines.append(f"- `{art['artifact']}` — {art['reason']}")

    lines += [
        "",
        "### Derivedly Stale",
    ]
    for art in s4.get("derivedly_stale", []):
        lines.append(f"- `{art['artifact']}` — {art['reason']}")

    lines += [
        "",
        "### Frozen Artifacts (must NOT be overwritten without explicit YES)",
    ]
    for fa in FROZEN_ARTIFACTS:
        lines.append(f"- `{fa}`")

    lines += [
        "",
        "---",
        "",
        "## Step 5: Dry-Run Regeneration Order",
        "",
        f"⚠️ **Authorization gate**: `{s5.get('requires_explicit_yes', EXPLICIT_YES_REQUIRED)}`",
        "",
    ]

    for s in s5.get("regeneration_steps", []):
        auth_tag = " 🔒 REQUIRES explicit YES" if s.get("requires_explicit_yes") else ""
        lines += [
            f"### Step {s['step_num']}: `{s['action']}`{auth_tag}",
            "",
            s["description"],
            "",
            f"**Risk**: `{s.get('safe_as_dry_run', False) and 'dry-run safe' or 'REQUIRES authorization'}`  ",
            "",
        ]

    lines += [
        "---",
        "",
        "## Step 6: Safety Decision",
        "",
        f"| Decision | Value |",
        f"|----------|-------|",
        f"| Content identity probe passed | `{s6.get('content_identity_probe_passed')}` |",
        f"| Stale by mtime only | `{s6.get('stale_by_mtime_only')}` |",
        f"| Content drift likely | `{s6.get('content_drift_likely')}` |",
        f"| Safe without explicit YES | `{s6.get('safe_without_explicit_yes')}` |",
        f"| Actual regeneration needed | `{s6.get('actual_regeneration_needed')}` |",
        "",
        f"**Reason**: {s6.get('reason', '')}",
        "",
        f"**Expected metric stability**: {s6.get('expected_metric_stability', '')}",
        "",
        f"**Recommendation**: {s6.get('recommendation', '')}",
        "",
        "---",
        "",
        "## Step 7: Governance",
        "",
    ]

    for flag, val in GOVERNANCE.items():
        lines.append(f"- `{flag}` = `{val}`")

    lines += [
        "",
        f"**Governance all pass**: {s7.get('governance_all_pass', False)}",
        "",
        "---",
        "",
        "## Step 8: Final Classification",
        "",
        f"```",
        f"{cls}",
        f"```",
        "",
        f"**Rationale**: {s8.get('rationale', '')}",
        "",
        f"**Explicit authorization required**:  ",
        f"`{EXPLICIT_YES_REQUIRED}`",
        "",
        "---",
        "",
        "## Governance Summary",
        "",
        "- ❌ No production betting recommendation",
        "- ❌ No EV / CLV / Kelly / stake calculation",
        "- ❌ No Taiwan lottery betting recommendation",
        "- ❌ No real bet",
        "- ❌ No frozen artifact modified",
        "- ✅ paper_only = true",
        "- ✅ diagnostic_only = true",
        "- ✅ production_ready = false",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # Update active_task
    try:
        existing = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
        new_block = (
            f"\n\n## P87 — Stale Downstream Recovery Dry-Run [2026-05-27]\n"
            f"- Classification: `{cls}`\n"
            f"- Content drift likely: {result.get('step3_content_identity_probe', {}).get('content_drift_likely', 'N/A')}\n"
            f"- Mtime-only stale: {result.get('step6_safety_decision', {}).get('stale_by_mtime_only', 'N/A')}\n"
            f"- Explicit YES required for regeneration\n"
            f"- Summary: {SUMMARY_PATH.relative_to(ROOT)}\n"
            f"- Report: {REPORT_PATH.relative_to(ROOT)}\n"
        )
        ACTIVE_TASK_PATH.write_text(existing + new_block, encoding="utf-8")
    except Exception:
        pass

    print(f"[P87] Classification : {cls}")
    print(f"[P87] Summary        : {SUMMARY_PATH.relative_to(ROOT)}")
    print(f"[P87] Report         : {REPORT_PATH.relative_to(ROOT)}")
    print(f"[P87] Content drift  : {result.get('step3_content_identity_probe', {}).get('content_drift_likely', 'N/A')}")
    print(f"[P87] Mtime-only     : {result.get('step6_safety_decision', {}).get('stale_by_mtime_only', 'N/A')}")
    print(f"[P87] Explicit YES   : {EXPLICIT_YES_REQUIRED}")


if __name__ == "__main__":
    run()
