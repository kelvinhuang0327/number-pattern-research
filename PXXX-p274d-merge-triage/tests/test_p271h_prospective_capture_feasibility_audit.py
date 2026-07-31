from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.json"
MD_PATH = ROOT / "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.md"

P271G_HASHES = {
    ROOT / "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.json":
        "8ff20a9969e2e4bca3ace8fc0a6899cbafda5a31be2a9201df755704cba38092",
    ROOT / "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.md":
        "4ab9ef261303b5ac9beb11077e998977bcc9358b1bbee4fa9aea70d153f12ef9",
    ROOT / "tests/test_p271g_prize_aware_null_prospective_preregistration.py":
        "24cf0a5163610ed78a32ca8634629a2381ff772fbef0777dc39a6e6e1ebb0645",
}

DIMENSIONS = {
    "identity",
    "timestamp availability",
    "authoritative draw-close resolution",
    "timezone normalization",
    "database uniqueness",
    "application duplicate prevention",
    "immutability",
    "update/amendment protection",
    "outcome separation",
    "POWER second zone",
    "prospective membership",
    "draw clustering",
    "audit trail",
    "backfill exclusion",
    "concurrent-write safety",
    "activation mechanism",
}

ALLOWED_STATUSES = {"READY", "PARTIAL", "BLOCKED", "UNKNOWN"}
ALLOWED_FINAL = {
    "P271H_PROSPECTIVE_CAPTURE_READY_WITHOUT_SCHEMA_CHANGE",
    "P271H_PROSPECTIVE_CAPTURE_PARTIAL_REQUIRES_IMPLEMENTATION",
    "P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP",
    "P271H_BLOCKED_DB_READ_ONLY_GUARD",
    "P271H_BLOCKED_GOVERNANCE_CONFLICT",
    "P271H_TEST_FAILURE",
}


def _artifact() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD_PATH.read_text(encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_01_json_exists():
    assert JSON_PATH.exists()


def test_02_md_exists():
    assert MD_PATH.exists()


def test_03_audit_design_only():
    data = _artifact()
    assert data["mode"] == "prospective_capture_feasibility_audit"
    assert data["design_and_audit_only"] is True


def test_04_prospective_collection_not_activated():
    assert _artifact()["prospective_collection_activated"] is False


def test_05_start_marker_pending_separate_task():
    assert _artifact()["prospective_prediction_start_at"] == "PENDING_SEPARATE_ACTIVATION_TASK"


def test_06_p271g_files_unchanged():
    for path, expected in P271G_HASHES.items():
        assert path.exists()
        assert _sha256(path) == expected


def test_07_db_write_false():
    data = _artifact()
    assert data["db_access"] is True
    assert data["db_open_mode"] == "sqlite_uri_mode_ro"
    assert data["db_write"] is False
    assert data["db_hash_unchanged"] is True


def test_08_all_sql_is_read_only():
    statements = _artifact()["executed_sql_statements"]
    assert statements
    for statement in statements:
        normalized = re.sub(r"\s+", " ", statement.strip()).upper()
        assert normalized.startswith(("SELECT ", "PRAGMA "))
        assert not re.search(r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|REPLACE|VACUUM|ATTACH)\b", normalized)


def test_09_no_row_level_records_embedded():
    data = _artifact()
    assert data["row_level_records_read"] is False
    assert "rows" not in data
    assert "row_records" not in data


def test_10_no_prediction_number_arrays_embedded():
    for key, value in _walk(_artifact()):
        if key in {"predicted_numbers", "prediction_numbers", "numbers"}:
            assert not isinstance(value, list)


def test_11_no_actual_number_arrays_embedded():
    for key, value in _walk(_artifact()):
        if key in {"actual_numbers", "winning_numbers", "matched_numbers"}:
            assert not isinstance(value, list)


def test_12_no_outcome_rate_or_prize_result_fields():
    banned = {
        "win_rate",
        "hit_rate",
        "m3_plus_rate",
        "prize_result",
        "prize_tier_result",
        "roi",
        "expected_value",
    }
    keys = {key.lower() for key, _ in _walk(_artifact())}
    assert not (keys & banned)


def test_13_no_baseline_scorer_or_adapter_execution():
    data = _artifact()
    assert data["baseline_executed"] is False
    assert data["scorer_executed"] is False
    assert data["adapter_executed"] is False


def test_14_p271f_not_rerun():
    assert _artifact()["p271f_evaluation_rerun"] is False


def test_15_exact_dimension_set():
    assert set(_artifact()["readiness_by_dimension"]) == DIMENSIONS


def test_16_identity_classified():
    assert _artifact()["readiness_by_dimension"]["identity"]["status"] in ALLOWED_STATUSES


def test_17_timestamp_classified():
    assert _artifact()["readiness_by_dimension"]["timestamp availability"]["status"] in ALLOWED_STATUSES


def test_18_draw_close_classified():
    assert _artifact()["readiness_by_dimension"]["authoritative draw-close resolution"]["status"] in ALLOWED_STATUSES


def test_19_timezone_classified():
    assert _artifact()["readiness_by_dimension"]["timezone normalization"]["status"] in ALLOWED_STATUSES


def test_20_database_uniqueness_classified():
    assert _artifact()["readiness_by_dimension"]["database uniqueness"]["status"] in ALLOWED_STATUSES


def test_21_application_duplicate_prevention_classified():
    assert _artifact()["readiness_by_dimension"]["application duplicate prevention"]["status"] in ALLOWED_STATUSES


def test_22_immutability_classified():
    assert _artifact()["readiness_by_dimension"]["immutability"]["status"] in ALLOWED_STATUSES


def test_23_amendment_protection_classified():
    assert _artifact()["readiness_by_dimension"]["update/amendment protection"]["status"] in ALLOWED_STATUSES


def test_24_outcome_separation_classified():
    assert _artifact()["readiness_by_dimension"]["outcome separation"]["status"] in ALLOWED_STATUSES


def test_25_power_second_zone_classified():
    assert _artifact()["readiness_by_dimension"]["POWER second zone"]["status"] in ALLOWED_STATUSES


def test_26_prospective_membership_classified():
    assert _artifact()["readiness_by_dimension"]["prospective membership"]["status"] in ALLOWED_STATUSES


def test_27_draw_clustering_classified():
    assert _artifact()["readiness_by_dimension"]["draw clustering"]["status"] in ALLOWED_STATUSES


def test_28_audit_trail_classified():
    assert _artifact()["readiness_by_dimension"]["audit trail"]["status"] in ALLOWED_STATUSES


def test_29_backfill_exclusion_classified():
    assert _artifact()["readiness_by_dimension"]["backfill exclusion"]["status"] in ALLOWED_STATUSES


def test_30_concurrent_write_classified():
    assert _artifact()["readiness_by_dimension"]["concurrent-write safety"]["status"] in ALLOWED_STATUSES


def test_31_activation_mechanism_classified():
    assert _artifact()["readiness_by_dimension"]["activation mechanism"]["status"] in ALLOWED_STATUSES


def test_32_ready_forbidden_without_enforcement():
    data = _artifact()
    missing_enforcement = (
        data["schema_change_required"]
        or data["runtime_code_change_required"]
        or data["readiness_by_dimension"]["immutability"]["status"] != "READY"
        or data["readiness_by_dimension"]["authoritative draw-close resolution"]["status"] != "READY"
    )
    if missing_enforcement:
        assert data["final_classification"] != "P271H_PROSPECTIVE_CAPTURE_READY_WITHOUT_SCHEMA_CHANGE"


def test_33_every_partial_or_blocked_dimension_has_evidence_and_remediation():
    for dimension, assessment in _artifact()["readiness_by_dimension"].items():
        if assessment["status"] in {"PARTIAL", "BLOCKED"}:
            assert assessment.get("evidence"), dimension
            assert assessment.get("remediation"), dimension


def test_34_required_implementation_controls_explicit():
    controls = _artifact()["required_implementation_controls"]
    assert len(controls) >= 10
    assert all(item.get("id") and item.get("control") for item in controls)


def test_35_proposed_production_files_require_separate_authorization():
    for item in _artifact()["proposed_next_allowed_files"]:
        if item["production_or_db_file"]:
            assert item["separate_explicit_authorization_required"] is True
            assert item["purpose"]


def test_36_no_activation_timestamp_inserted():
    data = _artifact()
    assert data["prospective_prediction_start_at"] == "PENDING_SEPARATE_ACTIVATION_TASK"
    assert data["p271g_pending_marker_changed"] is False
    assert data["p271g_merged_at"] != data["prospective_prediction_start_at"]


def test_37_no_strategy_ranking_or_comparison():
    assert _artifact()["strategy_comparison_or_ranking_started"] is False


def test_38_no_temporal_window_or_feature_mining():
    data = _artifact()
    assert data["temporal_window_research_started"] is False
    assert data["feature_mining_started"] is False


def test_39_md_has_all_twenty_sections():
    md = _md()
    for index in range(1, 21):
        assert re.search(rf"^## {index}\. ", md, flags=re.MULTILINE), index


def test_40_md_contains_required_declarations():
    md = _md()
    declarations = [
        "No prospective collection was activated.",
        "PENDING_P271G_MERGE_TIMESTAMP was not changed.",
        "No baseline or statistical analysis was run.",
        "No prediction outcome metrics were read or calculated.",
        "No row-level prediction or result data was exported.",
        "DB access, if used, was read-only.",
        "No DB/schema/runtime code was modified.",
        "Existing scorer, adapter, replay, strategy, API, and frontend behavior remain unchanged.",
        "P270C remains unauthorized.",
        "Official source status remains MANUAL_VERIFICATION_REQUIRED.",
    ]
    for declaration in declarations:
        assert declaration in md


def test_41_final_classification_allowed():
    assert _artifact()["final_classification"] in ALLOWED_FINAL


def test_42_blocked_verdict_matches_schema_and_runtime_gaps():
    data = _artifact()
    assert data["schema_change_required"] is True
    assert data["runtime_code_change_required"] is True
    assert data["final_classification"] == "P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP"


def test_43_source_verification_manual():
    assert _artifact()["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_44_p270c_remains_unauthorized():
    assert _artifact()["p270c_allowed"] is False


def test_45_no_production_integration_added():
    assert _artifact()["production_integration_added"] is False


def test_46_modified_files_exact_whitelist():
    assert set(_artifact()["modified_files"]) == {
        "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.json",
        "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.md",
        "tests/test_p271h_prospective_capture_feasibility_audit.py",
        "00-Plan/roadmap/active_task.md",
        "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
    }


def test_47_phase_zero_passed():
    phase = _artifact()["phase_0"]
    assert phase["result"] == "PASS"
    assert phase["starting_branch"] == "main"
    assert phase["head_equals_origin_main"] is True
    assert phase["staged_files_before_task"] == []


def test_48_current_governance_remains_hold():
    data = _artifact()
    assert data["current_governance"] == "HOLD / WAITING_FOR_USER_AUTHORIZATION"
    assert data["next_round_allowed"] is False


def test_49_future_scope_is_proposed_not_authorized():
    scope = _artifact()["proposed_next_task_scope"]
    assert scope["status"] == "PROPOSED_NOT_AUTHORIZED"
    assert "activation" in " ".join(scope["excluded"]).lower()


def test_50_activation_contract_is_later_than_implementation():
    contract = _artifact()["activation_mechanism_assessment"]["future_contract"]
    text = " ".join(contract).lower()
    assert "implementation" in text
    assert "activation artifact merge timestamp" in text
    assert "fail closed" in text
