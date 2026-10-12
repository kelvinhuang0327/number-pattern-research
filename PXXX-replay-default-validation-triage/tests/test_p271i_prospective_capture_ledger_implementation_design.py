from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.json"
MD_PATH = ROOT / "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.md"

P271H_MERGE_COMMIT = "24c170759350ac756a2b20dc08817986cba3dcb0"

ALLOWED_FINAL = {
    "P271I_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_DESIGN_COMPLETE",
    "P271I_BLOCKED_DRAW_CLOSE_SOURCE_AMBIGUITY",
    "P271I_BLOCKED_IDENTITY_OR_IMMUTABILITY_AMBIGUITY",
    "P271I_BLOCKED_GOVERNANCE_CONFLICT",
    "P271I_TEST_FAILURE",
}

REQUIRED_LEDGER_COLUMNS = {
    "ledger_id",
    "activation_id",
    "preregistration_version",
    "prospective_protocol_version",
    "lottery_type",
    "target_draw",
    "strategy_id",
    "strategy_version",
    "bet_index",
    "predicted_main_numbers",
    "predicted_second_zone",
    "prediction_created_at_utc",
    "draw_close_at_utc",
    "eligibility_status",
    "rejection_reason",
    "source_provenance",
    "payload_hash",
    "created_by",
    "recorded_at_utc",
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "task_id",
    "generated_at",
    "repo_head_before_task",
    "branch",
    "mode",
    "design_only",
    "p271h_merge_commit",
    "p271h_classification",
    "prospective_collection_activated",
    "activation_timestamp_inserted",
    "db_access",
    "db_write",
    "schema_modified",
    "runtime_code_modified",
    "deployment_started",
    "ledger_schema_design",
    "identity_contract",
    "uniqueness_contract",
    "transaction_contract",
    "immutability_contract",
    "amendment_contract",
    "causality_contract",
    "draw_close_source_contract",
    "timezone_contract",
    "power_second_zone_contract",
    "backfill_exclusion_contract",
    "outcome_separation_contract",
    "prospective_membership_contract",
    "activation_contract",
    "draw_cluster_contract",
    "failure_matrix",
    "migration_plan",
    "deployment_plan",
    "rollback_and_deactivation_plan",
    "future_task_sequence",
    "proposed_future_allowed_files",
    "source_verification_status",
    "p270c_allowed",
    "p270a_p270b_reopened",
    "baseline_executed",
    "statistical_analysis_executed",
    "strategy_comparison_run",
    "temporal_window_research_started",
    "feature_mining_started",
    "production_integration_added",
    "tests_result",
    "modified_files",
    "final_classification",
    "limitations",
}

REQUIRED_FAILURE_CONDITIONS = [
    "missing close time",
    "stale schedule",
    "unsupported lottery",
    "invalid predicted numbers",
    "missing POWER second zone",
    "duplicate identity",
    "clock ambiguity",
    "post-close submission",
    "inactive activation",
    "unknown strategy version",
    "transaction failure",
    "partial multi-ticket write",
    "backfill/import source",
    "source-provenance failure",
]


def _artifact() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD_PATH.read_text(encoding="utf-8")


def test_01_json_exists():
    assert JSON_PATH.exists()


def test_02_md_exists():
    assert MD_PATH.exists()


def test_03_required_top_level_fields_present():
    assert REQUIRED_TOP_LEVEL_FIELDS <= set(_artifact())


def test_04_design_only_and_mode():
    data = _artifact()
    assert data["mode"] == "prospective_capture_ledger_implementation_design"
    assert data["design_only"] is True


def test_05_no_execution_flags():
    data = _artifact()
    for key in (
        "prospective_collection_activated",
        "activation_timestamp_inserted",
        "db_access",
        "db_write",
        "schema_modified",
        "runtime_code_modified",
        "deployment_started",
        "baseline_executed",
        "statistical_analysis_executed",
        "strategy_comparison_run",
        "temporal_window_research_started",
        "feature_mining_started",
        "production_integration_added",
    ):
        assert data[key] is False, key


def test_06_p271h_merge_reference():
    data = _artifact()
    assert data["p271h_merge_commit"] == P271H_MERGE_COMMIT
    assert data["p271h_classification"] == "P271H_PROSPECTIVE_CAPTURE_BLOCKED_SCHEMA_OR_CAUSALITY_GAP"


def test_07_no_db_schema_runtime_modification():
    data = _artifact()
    assert data["db_access"] is False
    assert data["db_write"] is False
    assert data["schema_modified"] is False
    assert data["runtime_code_modified"] is False


def test_08_required_ledger_columns_present():
    cols = set(_artifact()["ledger_schema_design"]["required_ledger_columns"])
    assert REQUIRED_LEDGER_COLUMNS <= cols


def test_09_ledger_is_separate_from_retrospective_store():
    design = _artifact()["ledger_schema_design"]
    tables = set(design["tables"])
    assert "prospective_prediction_ledger" in tables
    assert "strategy_prediction_replays" not in tables
    assert "reuse" not in design["principle"].lower() or "never reuse" in design["principle"].lower()


def test_10_append_only_semantics():
    imm = _artifact()["immutability_contract"]
    assert imm["append_only"] is True
    assert imm["reject_update"] is True
    assert imm["reject_delete"] is True
    assert imm["payload_cannot_change_after_insert"] is True


def test_11_no_update_or_delete_replacement():
    am = _artifact()["amendment_contract"]
    assert am["amendment_creates_new_record"] is True
    assert am["no_update_in_place"] is True
    assert am["no_delete_reinsert"] is True
    assert am["original_remains_auditable"] is True
    assert am["amended_never_silently_substituted"] is True
    assert am["post_close_amendment_ineligible"] is True


def test_12_deterministic_identity():
    ident = _artifact()["identity_contract"]
    assert ident["deterministic"] is True
    assert ident["manual_override_blocked"] is True
    assert ident["no_mutable_text_identity"] is True
    assert set(ident["identity_tuple"]) == {
        "activation_id",
        "lottery_type",
        "target_draw",
        "strategy_id",
        "strategy_version",
        "bet_index",
    }


def test_13_uniqueness_enforced_and_fail_closed():
    uniq = _artifact()["uniqueness_contract"]
    assert uniq["enforced_by_db_unique_constraint"] is True
    assert uniq["duplicate_insert_fails_closed"] is True
    assert uniq["preflight_only_check_forbidden"] is True


def test_14_transaction_and_concurrency_rules():
    tx = _artifact()["transaction_contract"]
    assert tx["single_transaction"] is True
    assert tx["begin_immediate"] is True
    assert tx["foreign_keys_enabled"] is True
    assert tx["busy_timeout_required"] is True
    assert tx["validate_and_insert_in_same_transaction"] is True
    assert tx["deterministic_conflict_handling"] is True
    assert tx["no_separate_readonly_preflight_for_uniqueness"] is True


def test_15_utc_timestamp_contract():
    tz = _artifact()["timezone_contract"]
    assert tz["resolution_timezone"] == "Asia/Taipei"
    assert "UTC" in tz["canonical_storage"]
    assert tz["reject_naive_timestamps"] is True
    assert tz["reject_ambiguous_timestamps"] is True
    assert tz["single_comparison_contract"] is True


def test_16_authoritative_close_time_versioned():
    contract = _artifact()["draw_close_source_contract"]
    assert _artifact()["causality_contract"]["authoritative_source_versioned"] is True
    types = {s["type"] for s in contract["source_types"]}
    assert {
        "official_machine_readable",
        "official_published_schedule",
        "repository_configured_deterministic_schedule",
        "manual",
    } <= types
    for src in contract["source_types"]:
        assert src["versioning"]
        assert "fail_closed_rule" in src
    # manual source can never be confirmatory
    manual = next(s for s in contract["source_types"] if s["type"] == "manual")
    assert manual["confirmatory_use_allowed"] is False
    assert contract["official_verification_claimed"] is False
    assert contract["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_17_fail_closed_missing_or_ambiguous_close_time():
    cz = _artifact()["causality_contract"]
    assert cz["missing_timestamp_fail_closed"] is True
    assert cz["ambiguous_timezone_fail_closed"] is True
    assert cz["fallback_cannot_be_confirmatory"] is True


def test_18_prediction_precedes_draw_close():
    cz = _artifact()["causality_contract"]
    assert "prediction_created_at_utc < draw_close_at_utc" in cz["rule"]
    assert cz["no_outcome_table_queried_by_capture"] is True
    assert "skew" in cz["clock_skew_tolerance"].lower()


def test_19_power_second_zone_mandatory():
    p = _artifact()["power_second_zone_contract"]
    assert p["mandatory_for_power_ticket"] is True
    assert p["must_exist_at_creation_time"] is True
    assert p["cannot_fill_later"] is True
    assert p["cannot_use_actual_value"] is True
    assert p["missing_or_invalid_causes_rejection"] is True


def test_20_backfill_cannot_become_prospective():
    b = _artifact()["backfill_exclusion_contract"]
    assert b["historical_import_backfill_reconciliation_excluded"] is True
    assert b["atomic_eligibility_at_insert"] is True
    assert b["requires_active_activation_id"] is True
    assert b["requires_created_after_activation_start"] is True
    assert b["requires_target_draw_not_closed"] is True
    assert b["no_status_upgrade_to_prospective"] is True
    assert b["no_retrospective_row_conversion"] is True


def test_21_outcome_data_separated():
    o = _artifact()["outcome_separation_contract"]
    assert o["ledger_contains_no_results"] is True
    assert o["separate_result_path"] is True
    assert o["read_only_join_after_draw"] is True
    assert o["membership_frozen_before_outcome"] is True
    assert o["membership_cannot_change_after_result_ingestion"] is True
    assert o["actual_values_cannot_populate_predicted_fields"] is True
    assert o["capture_service_never_reads_results"] is True


def test_22_activation_separate_and_inactive():
    a = _artifact()["activation_contract"]
    assert a["activated_in_p271i"] is False
    assert a["separate_activation_artifact_required"] is True
    assert a["records_activation_id_and_timestamp"] is True
    assert a["start_no_earlier_than_activation_artifact_merge_and_verification"] is True
    assert a["excludes_all_earlier_rows"] is True
    assert a["reversible_only_by_deactivation"] is True
    assert a["never_by_rewriting_captured_records"] is True
    assert a["p271g_merge_is_not_activation"] is True


def test_23_migration_deployment_activation_distinct_gates():
    seq = {item["id"]: item for item in _artifact()["future_task_sequence"]}
    assert {"P271J", "P271K", "P271L", "P271M", "P271N"} <= set(seq)
    for item in seq.values():
        assert item["authorizes_next"] is False
    # only the activation gate activates
    assert seq["P271N"]["activates"] is True
    for other in ("P271J", "P271K", "P271L", "P271M"):
        assert seq[other]["activates"] is False
    phase = _artifact()["phase_separation"]
    assert phase["no_phase_implicitly_authorizes_next"] is True
    assert phase["each_phase_separately_authorized"] is True


def test_24_no_historical_rows_imported_into_ledger():
    b = _artifact()["backfill_exclusion_contract"]
    assert b["only_live_pre_close_capture_eligible"]
    assert "LIVE_PRE_CLOSE" in b["only_live_pre_close_capture_eligible"]


def test_25_failure_matrix_covers_all_required_cases():
    matrix = _artifact()["failure_matrix"]
    assert len(matrix) >= 14
    conditions = " | ".join(item["condition"].lower() for item in matrix)
    for required in REQUIRED_FAILURE_CONDITIONS:
        assert required.lower() in conditions, required
    for item in matrix:
        assert item.get("fail_closed_behavior")


def test_26_proposed_future_files_are_proposals_only():
    files = _artifact()["proposed_future_allowed_files"]
    assert files
    for item in files:
        assert item["separate_explicit_authorization_required"] is True
        assert item["purpose"]


def test_27_no_baseline_statistical_or_strategy_work():
    data = _artifact()
    assert data["baseline_executed"] is False
    assert data["statistical_analysis_executed"] is False
    assert data["strategy_comparison_run"] is False
    assert data["temporal_window_research_started"] is False
    assert data["feature_mining_started"] is False


def test_28_p270c_false():
    assert _artifact()["p270c_allowed"] is False


def test_29_p270a_p270b_not_reopened():
    assert _artifact()["p270a_p270b_reopened"] is False


def test_30_final_classification_allowed():
    assert _artifact()["final_classification"] in ALLOWED_FINAL


def test_31_final_classification_is_design_complete():
    assert _artifact()["final_classification"] == "P271I_PROSPECTIVE_CAPTURE_LEDGER_IMPLEMENTATION_DESIGN_COMPLETE"


def test_32_source_verification_manual():
    assert _artifact()["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_33_migration_additive_and_not_executed():
    m = _artifact()["migration_plan"]
    assert m["additive_only"] is True
    assert m["no_production_write_in_design_or_implementation_task"] is True
    assert m["executed"] is False


def test_34_deployment_not_started():
    d = _artifact()["deployment_plan"]
    assert d["deploy_disabled_first"] is True
    assert d["no_activation_at_deploy"] is True
    assert d["started"] is False


def test_35_rollback_never_rewrites_records():
    r = _artifact()["rollback_and_deactivation_plan"]
    assert r["deactivation_not_record_rewriting"] is True
    assert r["captured_records_never_deleted"] is True


def test_36_draw_cluster_contract():
    c = _artifact()["draw_cluster_contract"]
    assert c["cluster_key"] == ["lottery_type", "target_draw"]
    assert c["persisted_directly_on_batch_and_ticket"] is True
    assert c["validated_against_authoritative_schedule"] is True
    assert c["no_latest_known_draw_plus_one_inference"] is True


def test_37_modified_files_exact_whitelist():
    assert set(_artifact()["modified_files"]) == {
        "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.json",
        "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.md",
        "tests/test_p271i_prospective_capture_ledger_implementation_design.py",
        "00-Plan/roadmap/active_task.md",
        "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
    }


def test_38_md_has_all_twenty_one_sections():
    md = _md()
    for index in range(1, 22):
        assert re.search(rf"^## {index}\. ", md, flags=re.MULTILINE), index


def test_39_md_contains_required_declarations():
    md = _md()
    declarations = [
        "This is a design-only task.",
        "No prospective collection was activated.",
        "No activation timestamp was inserted.",
        "No DB was opened; no schema, runtime code, or migration was modified.",
        "No deployment was started.",
        "No baseline, statistical, scorer, adapter, or strategy comparison work was performed.",
        "P270C remains unauthorized.",
        "P270A and P270B remain closed and were not reopened.",
        "Official source status remains MANUAL_VERIFICATION_REQUIRED.",
        "Implementation, migration, deployment, and activation remain separate authorization gates.",
    ]
    for declaration in declarations:
        assert declaration in md, declaration


def test_40_prospective_membership_computed_once():
    m = _artifact()["prospective_membership_contract"]
    assert m["eligibility_computed_once_at_insert"] is True
    assert m["computed_before_outcomes"] is True
    assert m["never_upgraded_later"] is True
    assert m["fail_closed_rejection_reason_recorded"] is True
