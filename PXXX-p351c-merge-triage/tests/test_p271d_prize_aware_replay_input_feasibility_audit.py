"""Tests for P271D prize-aware replay input feasibility audit (read-only).

These tests verify:
  * the audit script and artifacts exist and are well-formed
  * the audit script is read-only (no SQL writes, no scorer import/call,
    no predicted-vs-actual comparison)
  * all required structural/feasibility fields are present per lottery type
  * all "must be NO/false" safety guard fields hold
  * the final classification is in the allowed set
  * the MD artifact contains all required safety declarations
  * the future adapter design is described as parallel and read-only
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "analysis" / "p271d_prize_aware_replay_input_feasibility_audit.py"
JSON_PATH = REPO_ROOT / "outputs" / "research" / "p271d_prize_aware_replay_input_feasibility_audit_20260612.json"
MD_PATH = REPO_ROOT / "outputs" / "research" / "p271d_prize_aware_replay_input_feasibility_audit_20260612.md"

LOTTERY_TYPES = ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")

ALLOWED_CLASSIFICATIONS = {
    "P271D_ALL_LOTTERIES_REPLAY_INPUTS_FEASIBLE_GO_ADAPTER",
    "P271D_PARTIAL_LOTTERY_FEASIBILITY_GO_SCOPED_ADAPTER",
    "P271D_NO_GO_REQUIRED_REPLAY_INPUTS_MISSING",
    "P271D_BLOCKED_SCHEMA_OR_CAUSALITY_MISMATCH",
    "P271D_BLOCKED_CANONICAL_DB_AMBIGUITY",
    "P271D_BLOCKED_GOVERNANCE_CONFLICT",
    "P271D_TEST_FAILURE",
}


@pytest.fixture(scope="module")
def script_source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def script_source_without_docstring(script_ast: ast.Module, script_source: str) -> str:
    docstring = ast.get_docstring(script_ast)
    if docstring is None:
        return script_source
    return script_source.replace(docstring, "")


@pytest.fixture(scope="module")
def script_ast(script_source: str) -> ast.Module:
    return ast.parse(script_source)


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md_text() -> str:
    return MD_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Existence
# ---------------------------------------------------------------------------

def test_audit_script_exists():
    assert SCRIPT_PATH.is_file()


def test_json_artifact_exists():
    assert JSON_PATH.is_file()


def test_md_artifact_exists():
    assert MD_PATH.is_file()


# ---------------------------------------------------------------------------
# 2. Script opens DB read-only
# ---------------------------------------------------------------------------

def test_script_opens_db_readonly(script_source: str):
    assert "mode=ro" in script_source
    assert "uri=True" in script_source


# ---------------------------------------------------------------------------
# 3. Script contains no SQL write statements
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "forbidden",
    [
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "CREATE TABLE",
        "DROP TABLE",
        "ALTER TABLE",
        "REPLACE INTO",
        "VACUUM",
        "PRAGMA",
    ],
)
def test_script_contains_no_sql_write_statements(script_source: str, forbidden: str):
    assert forbidden.upper() not in script_source.upper()


def test_script_contains_no_write_cursor_calls(script_source: str):
    for forbidden in ("conn.commit", ".executescript", "controlled_apply"):
        assert forbidden not in script_source


# ---------------------------------------------------------------------------
# 4. Script does not import or call prize_aware_scorer
# ---------------------------------------------------------------------------

def test_script_does_not_import_prize_aware_scorer(script_ast: ast.Module):
    for node in ast.walk(script_ast):
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or "prize_aware_scorer" not in node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "prize_aware_scorer" not in alias.name


def test_script_does_not_reference_scorer_functions(script_source_without_docstring: str):
    for forbidden in (
        "score_prize_aware_ticket",
        "score_replay_row",
        "classify_tier",
        "classify_power_lotto_tier",
        "classify_big_lotto_tier",
        "classify_daily_539_tier",
    ):
        assert forbidden not in script_source_without_docstring


# ---------------------------------------------------------------------------
# 5/6. Script does not calculate hit counts/endpoint flags or compare
#       predicted vs actual numbers
# ---------------------------------------------------------------------------

def test_script_does_not_compute_hit_counts_or_endpoint_flags(script_source: str):
    for forbidden in (
        "hit_count =",
        "hit_count=",
        "any_prize_aware_win",
        "tier_class",
        "endpoint_flags",
        "is_m3_plus",
        "special_hit =",
    ):
        assert forbidden not in script_source


def test_script_does_not_compare_predicted_vs_actual_numbers(script_source: str):
    """The script reads predicted/actual numbers independently but never
    intersects, diffs, or otherwise compares the two sets of values."""
    forbidden_patterns = (
        "set(pred) & set(act)",
        "set(p) & set(a)",
        "pred_set & act_set",
        "predicted_main_numbers) & set(actual",
        "& set(actual",
    )
    for forbidden in forbidden_patterns:
        assert forbidden not in script_source


# ---------------------------------------------------------------------------
# 7. Three lottery types reported
# ---------------------------------------------------------------------------

def test_three_lottery_types_reported(artifact: dict):
    for key in (
        "field_inventory_by_lottery",
        "structural_metrics_by_lottery",
        "join_contract_by_lottery",
        "causality_check_by_lottery",
        "scorer_input_mapping_by_lottery",
        "feasibility_by_lottery",
        "blocking_reasons_by_lottery",
    ):
        assert set(artifact[key].keys()) == set(LOTTERY_TYPES), key


# ---------------------------------------------------------------------------
# 8. POWER predicted-second-zone availability explicit
# ---------------------------------------------------------------------------

def test_power_predicted_second_zone_availability_explicit(artifact: dict):
    power = artifact["field_inventory_by_lottery"]["POWER_LOTTO"]
    assert "predicted_special" in power["null_count"]
    assert power["null_count"]["predicted_special"] == 27104
    metrics = artifact["structural_metrics_by_lottery"]["POWER_LOTTO"]
    assert metrics["rows_with_required_predicted_aux_field"] == 9000
    assert metrics["total_replay_rows"] == 36104


def test_power_blocking_reason_present(artifact: dict):
    reason = artifact["blocking_reasons_by_lottery"]["POWER_LOTTO"]
    assert reason is not None
    assert "predicted_special" in reason or "second-zone" in reason


# ---------------------------------------------------------------------------
# 9. BIG actual-special-number availability explicit
# ---------------------------------------------------------------------------

def test_big_actual_special_availability_explicit(artifact: dict):
    big = artifact["field_inventory_by_lottery"]["BIG_LOTTO"]
    assert big["null_count"]["actual_special"] == 0
    metrics = artifact["structural_metrics_by_lottery"]["BIG_LOTTO"]
    assert metrics["rows_missing_actual_aux_result"] == 0
    assert metrics["total_replay_rows"] == 24140


def test_big_lotto_no_blocking_reason(artifact: dict):
    assert artifact["blocking_reasons_by_lottery"]["BIG_LOTTO"] is None


# ---------------------------------------------------------------------------
# 10. DAILY_539 has no auxiliary-field requirement
# ---------------------------------------------------------------------------

def test_daily539_no_auxiliary_field_requirement(artifact: dict):
    daily = artifact["field_inventory_by_lottery"]["DAILY_539"]
    assert daily["null_count"]["predicted_special"] == 34680
    assert daily["null_count"]["actual_special"] == 34680
    mapping = artifact["scorer_input_mapping_by_lottery"]["DAILY_539"]
    assert mapping["predicted_second_zone"].startswith("must be None")
    assert mapping["actual_second_zone"].startswith("must be None")
    assert mapping["actual_special_number"].startswith("must be None")


def test_daily539_no_blocking_reason(artifact: dict):
    assert artifact["blocking_reasons_by_lottery"]["DAILY_539"] is None


# ---------------------------------------------------------------------------
# 11/12/13/14. Structural metrics / join coverage / causality / malformed
# ---------------------------------------------------------------------------

def test_structural_metrics_present_for_every_lottery(artifact: dict):
    required_keys = {
        "total_replay_rows",
        "parseable_predicted_main_rows",
        "rows_with_required_predicted_aux_field",
        "target_draws_represented",
        "rows_joinable_to_one_actual_draw",
        "rows_missing_actual_main_result",
        "rows_missing_actual_aux_result",
        "rows_failing_cardinality_range_or_duplicate_validation",
        "causality_verifiable_rows",
        "structurally_eligible_rows",
        "structurally_eligible_percentage",
    }
    for lt in LOTTERY_TYPES:
        metrics = artifact["structural_metrics_by_lottery"][lt]
        assert required_keys.issubset(metrics.keys()), lt


def test_join_coverage_present_for_every_lottery(artifact: dict):
    for lt in LOTTERY_TYPES:
        join = artifact["join_contract_by_lottery"][lt]
        assert "join_coverage" in join
        assert "100%" in join["join_coverage"]
        assert join["depends_on_strategy_performance_fields"] is False


def test_causality_status_present_for_every_lottery(artifact: dict):
    for lt in LOTTERY_TYPES:
        causality = artifact["causality_check_by_lottery"][lt]
        assert causality["causality_status"] == "CAUSALITY_VERIFIABLE"
        assert causality["post_draw_feature_required"] is False


def test_malformed_and_missing_field_counts_explicit(artifact: dict):
    for lt in LOTTERY_TYPES:
        field_inv = artifact["field_inventory_by_lottery"][lt]
        assert field_inv["malformed_or_unparseable_count"] == 0
        assert field_inv["duplicate_key_count"] == 0
        metrics = artifact["structural_metrics_by_lottery"][lt]
        assert metrics["rows_failing_cardinality_range_or_duplicate_validation"] == 0
        assert metrics["rows_missing_actual_main_result"] == 0


# ---------------------------------------------------------------------------
# 15/16. No raw winning numbers stored; raw_outcomes_exported is false
# ---------------------------------------------------------------------------

def test_no_raw_winning_numbers_in_artifacts(artifact: dict, md_text: str):
    artifact_text = json.dumps(artifact)
    # Heuristic: no JSON array of 5+ small ints (a winning-number-shaped list)
    import re

    pattern = re.compile(r"\[\s*\d{1,2}\s*(,\s*\d{1,2}\s*){4,5}\]")
    assert not pattern.search(artifact_text)
    assert not pattern.search(md_text)


def test_raw_outcomes_exported_false(artifact: dict):
    assert artifact["raw_outcomes_exported"] is False


# ---------------------------------------------------------------------------
# 17-32. Safety guard booleans
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,expected",
    [
        ("prediction_outcome_comparison_run", False),
        ("scorer_called", False),
        ("prize_aware_evaluation_run", False),
        ("backtest_run", False),
        ("strategy_comparison_run", False),
        ("db_read_only", True),
        ("db_write", False),
        ("registry_write", False),
        ("existing_replay_modified", False),
        ("existing_m3_replay_scoring_changed", False),
        ("production_integration_added", False),
        ("strategy_generated", False),
        ("hit_rate_improvement_claimed", False),
        ("p270c_allowed", False),
        ("temporal_window_research_started", False),
        ("feature_mining_started", False),
        ("db_access", True),
    ],
)
def test_safety_guard_booleans(artifact: dict, field: str, expected: bool):
    assert artifact[field] is expected


# ---------------------------------------------------------------------------
# 33. Final classification in allowed set
# ---------------------------------------------------------------------------

def test_final_classification_in_allowed_set(artifact: dict):
    assert artifact["final_classification"] in ALLOWED_CLASSIFICATIONS


def test_power_partial_classification_consistent(artifact: dict):
    """Given POWER_LOTTO is partial and BIG/DAILY are full, classification
    must be the PARTIAL scoped-adapter classification."""
    assert artifact["final_classification"] == "P271D_PARTIAL_LOTTERY_FEASIBILITY_GO_SCOPED_ADAPTER"
    assert "PARTIAL" in artifact["feasibility_by_lottery"]["POWER_LOTTO"]
    assert "FULL" in artifact["feasibility_by_lottery"]["BIG_LOTTO"]
    assert "FULL" in artifact["feasibility_by_lottery"]["DAILY_539"]


# ---------------------------------------------------------------------------
# 34. MD contains all required safety declarations
# ---------------------------------------------------------------------------

REQUIRED_DECLARATIONS = [
    "No prediction-versus-outcome comparison was run.",
    "The prize-aware scorer was not called.",
    "No prize-aware historical evaluation was run.",
    "No success rate, lift, p-value, or strategy ranking was calculated.",
    "DB access was read-only.",
    "No DB write happened.",
    "No registry mutation happened.",
    "Existing replay rows were not modified.",
    "Existing M3+/replay scoring remains unchanged.",
    "No production integration was added.",
    "No strategy was generated.",
    "No hit-rate improvement is claimed.",
    "Official source status remains `MANUAL_VERIFICATION_REQUIRED`.",
    "P270C remains unauthorized.",
    "Temporal-window research and feature mining were not started.",
]


@pytest.mark.parametrize("declaration", REQUIRED_DECLARATIONS)
def test_md_contains_required_declaration(md_text: str, declaration: str):
    assert declaration in md_text


# ---------------------------------------------------------------------------
# 35. Future adapter design is parallel and read-only
# ---------------------------------------------------------------------------

def test_future_adapter_design_parallel_and_readonly(artifact: dict):
    adapter = artifact["future_adapter_design"]
    assert adapter["db_write"] is False
    assert adapter["modifies_existing_replay_rows"] is False
    assert adapter["modifies_m3_plus_output"] is False
    assert adapter["calls_scorer_in_this_task"] is False
    assert adapter["independently_versioned"] is True
    assert adapter["enableable_per_lottery_type"] is True

    parallel = artifact["parallel_feature_design"]
    assert "PARALLEL" in parallel["principle"]
    assert "is_m3_plus = hit_count >= 3" in parallel["existing_m3_definition_unchanged"]


# ---------------------------------------------------------------------------
# Additional: script executes successfully and matches artifact metrics
# ---------------------------------------------------------------------------

def test_script_output_matches_artifact_metrics(artifact: dict):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=True,
    )
    computed = json.loads(result.stdout)
    for lt in LOTTERY_TYPES:
        assert computed[lt] == artifact["structural_metrics_by_lottery"][lt], lt


# ---------------------------------------------------------------------------
# Required fields presence on top-level artifact
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL_FIELDS = [
    "task_id",
    "generated_at",
    "repo_head_before_task",
    "branch",
    "mode",
    "canonical_db_path",
    "db_open_mode",
    "source_contract_files",
    "scorer_contract_file",
    "source_verification_status",
    "tables_and_sources_inspected",
    "lottery_type_mapping",
    "field_inventory_by_lottery",
    "structural_metrics_by_lottery",
    "join_contract_by_lottery",
    "causality_check_by_lottery",
    "scorer_input_mapping_by_lottery",
    "feasibility_by_lottery",
    "blocking_reasons_by_lottery",
    "future_adapter_design",
    "parallel_feature_design",
    "raw_outcomes_exported",
    "prediction_outcome_comparison_run",
    "scorer_called",
    "prize_aware_evaluation_run",
    "backtest_run",
    "strategy_comparison_run",
    "db_access",
    "db_read_only",
    "db_write",
    "registry_write",
    "existing_replay_modified",
    "existing_m3_replay_scoring_changed",
    "production_integration_added",
    "strategy_generated",
    "hit_rate_improvement_claimed",
    "p270c_allowed",
    "temporal_window_research_started",
    "feature_mining_started",
    "tests_result",
    "modified_files",
    "next_recommended_task",
    "final_classification",
    "limitations",
]


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL_FIELDS)
def test_required_top_level_field_present(artifact: dict, field: str):
    assert field in artifact


def test_mode_field_value(artifact: dict):
    assert artifact["mode"] == "prize_aware_replay_input_feasibility_audit"


def test_source_verification_status(artifact: dict):
    assert artifact["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_canonical_db_path(artifact: dict):
    assert artifact["canonical_db_path"] == "lottery_api/data/lottery_v2.db"
    assert (REPO_ROOT / artifact["canonical_db_path"]).is_file()
