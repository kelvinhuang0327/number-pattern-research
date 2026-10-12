"""
Targeted validation tests for P241B P234 Statistical Diagnostics Inventory.
Validates artifact format, no-claim booleans, and governance compliance.
No DB write. No registry mutation. No production change.
"""
import json
import os
import pytest

ARTIFACT_BASE = "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605"
MD_PATH = f"{ARTIFACT_BASE}.md"
JSON_PATH = f"{ARTIFACT_BASE}.json"

REQUIRED_SCHEMA_FIELDS = [
    "task_id", "report_date", "lottery_type", "strategy_id", "diagnostic_subject",
    "lifecycle_status", "sample_size", "window_definition", "is_oos", "split_boundary",
    "family_size_k", "baseline_method", "baseline_value", "observed_metric",
    "delta_vs_baseline", "n_blocks", "blocks_above_baseline", "p_value_raw",
    "correction_method", "corrected_threshold", "is_corrected_significant",
    "mc_null_99th_pct", "is_above_mc_noise_floor", "robustness_check_description",
    "robustness_metric", "robustness_sign_stable", "drift_guard_result",
    "psi_value", "psi_status", "feature_bottleneck", "min_detectable_effect",
    "power_at_observed_effect", "overfit_ratio", "classification",
    "blocker_classification", "allowed_next_action", "forbidden_next_action",
    "confidence_language", "human_review_required", "db_write_authorized",
    "registry_write_authorized", "production_authorized", "betting_advice",
    "nist_alert_level",
]


@pytest.fixture(scope="module")
def artifact():
    with open(JSON_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_content():
    with open(MD_PATH) as f:
        return f.read()


def test_markdown_exists():
    assert os.path.exists(MD_PATH), f"Markdown artifact missing: {MD_PATH}"


def test_json_exists():
    assert os.path.exists(JSON_PATH), f"JSON artifact missing: {JSON_PATH}"


def test_json_parses(artifact):
    assert isinstance(artifact, dict)


def test_classification(artifact):
    assert artifact["classification"] == "P241B_P234_STATISTICAL_DIAGNOSTICS_INVENTORY_COMPLETE"


def test_task_type_is_type_b(artifact):
    assert artifact["task_type"] == "Type B"


def test_no_code_implementation(artifact):
    assert artifact["no_code_implementation"] is True


def test_db_write_not_authorized(artifact):
    assert artifact["db_write_authorized"] is False


def test_registry_write_not_authorized(artifact):
    assert artifact["registry_write_authorized"] is False


def test_production_not_authorized(artifact):
    assert artifact["production_authorized"] is False


def test_monitoring_not_authorized(artifact):
    assert artifact["monitoring_authorized"] is False


def test_strategy_not_authorized(artifact):
    assert artifact["strategy_authorized"] is False


def test_no_betting_advice(artifact):
    assert artifact["betting_advice"] is False


def test_p211_not_restarted(artifact):
    assert artifact["p211_restarted"] is False


def test_p238b_interpretation(artifact):
    assert "YELLOW" in artifact["p238b_interpretation"] or "observation" in artifact["p238b_interpretation"].lower()


def test_nist_yellow_not_prediction_edge(artifact):
    assert artifact["nist_yellow_is_prediction_edge"] is False


def test_nist_yellow_not_strategy_signal(artifact):
    assert artifact["nist_yellow_is_strategy_signal"] is False


def test_same_pr_closeout_allowed(artifact):
    assert artifact["same_pr_closeout_allowed"] is True


def test_no_separate_closeout_pr_required(artifact):
    assert artifact["separate_closeout_pr_required"] is False


def test_required_schema_fields_documented(artifact):
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in artifact["proposed_schema_fields"], (
            f"Required schema field missing from proposal: {field}"
        )


def test_inventory_methods_nonempty(artifact):
    assert len(artifact["inventory_methods"]) >= 10


def test_gap_categories_nonempty(artifact):
    assert len(artifact["gap_categories"]) >= 5


def test_final_state_db_rows(artifact):
    assert artifact["final_state"]["db_rows"] == 94924


def test_final_state_drift_guard(artifact):
    assert artifact["final_state"]["drift_guard"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_final_state_no_deployable_candidate(artifact):
    assert artifact["final_state"]["deployable_candidate_exists"] is False


def test_final_state_no_separate_closeout(artifact):
    assert artifact["final_state"]["separate_closeout_pr_needed"] is False


def test_markdown_no_db_write_claim(md_content):
    lower = md_content.lower()
    assert "no db write" in lower or "no database write" in lower or "db write\nnot authorized" in lower or "db_write_authorized" in lower


def test_markdown_no_registry_mutation_claim(md_content):
    assert "registry mutation" in md_content.lower()


def test_markdown_no_production_claim(md_content):
    assert "no production" in md_content.lower() or "production_authorized" in md_content.lower()


def test_markdown_no_betting_advice_claim(md_content):
    assert "betting advice" in md_content.lower()


def test_markdown_no_strategy_promotion(md_content):
    assert "strategy promotion" in md_content.lower() or "no strategy" in md_content.lower()


def test_markdown_implementation_requires_separate_authorization(md_content):
    assert "separate explicit" in md_content.lower() or "separate explicit authorization" in md_content.lower()


def test_markdown_no_separate_closeout_pr_statement(md_content):
    assert "no separate" in md_content.lower() or "no p241c closeout" in md_content.lower()


def test_markdown_type_b_classification(md_content):
    assert "type b" in md_content.lower()
