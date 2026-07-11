"""Focused no-database tests for the canonical P545B publication contract."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path

import pytest

from analysis import p545b_full_50_300_750_per_draw_evaluator as evaluator


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def payload():
    return evaluator.strict_json_load(REPO_ROOT / evaluator.OUTPUT_JSON)


@pytest.fixture(scope="module")
def rebuilt():
    return evaluator.build_evaluation(REPO_ROOT)


def test_schema_and_required_top_level_contract(payload):
    assert payload["schema"] == "p545b_full_50_300_750_per_draw_evaluation.v1"
    assert set(payload) == {
        "schema", "task_id", "classification", "generated_at_utc",
        "generated_at_policy", "implementation_base_commit", "input_registry",
        "contract_manifest", "scoring_contract", "statistical_contract",
        "opportunity_evaluations", "window_evaluations", "cell_summaries",
        "global_summary", "reconciliation", "determinism", "safety",
        "limitations", "canonical_payload_digest",
    }


def test_implementation_commit_timestamp_policy(payload):
    assert payload["implementation_base_commit"] == evaluator.IMPLEMENTATION_BASE_COMMIT
    assert payload["generated_at_utc"] == "2026-07-11T07:58:26+00:00"
    assert payload["generated_at_policy"] == evaluator.GENERATED_AT_POLICY


def test_input_registry_identity(payload):
    source = payload["input_registry"]
    assert source["path"] == evaluator.REGISTRY_PATH
    assert source["byte_size"] == 52_393_107
    assert source["sha256"] == evaluator.REGISTRY_SHA256
    assert source["semantic_projection_digest"] == evaluator.REGISTRY_SEMANTIC_DIGEST
    assert source["canonical_payload_digest"] == evaluator.REGISTRY_CANONICAL_DIGEST
    assert source["sole_row_level_evidence_input"] is True


def test_contract_manifest_is_verified_and_complete(payload):
    manifest = payload["contract_manifest"]
    assert len(manifest) == 7
    assert {item["role"] for item in manifest} == {
        "legacy_pure_evaluation_logic", "legacy_numerical_evidence",
        "sole_row_level_evidence", "exact_statistical_contract",
        "lottery_scoring_contract", "endpoint_definition_contract",
        "frozen_36_cell_roster",
    }
    assert {item["verification"] for item in manifest} == {"PASS"}
    assert {item["commit"] for item in manifest} == {evaluator.IMPLEMENTATION_BASE_COMMIT}


def test_legacy_source_and_output_are_pinned():
    assert evaluator.file_sha256(REPO_ROOT / evaluator.LEGACY_SOURCE) == evaluator.LEGACY_SOURCE_SHA256
    assert evaluator.file_sha256(REPO_ROOT / evaluator.LEGACY_OUTPUT) == evaluator.LEGACY_OUTPUT_SHA256
    assert (REPO_ROOT / evaluator.LEGACY_SOURCE).stat().st_size == evaluator.LEGACY_SOURCE_SIZE
    assert (REPO_ROOT / evaluator.LEGACY_OUTPUT).stat().st_size == evaluator.LEGACY_OUTPUT_SIZE


def test_legacy_module_semantics_verified_before_use():
    module = evaluator.load_verified_legacy_module(REPO_ROOT)
    assert module.SCHEMA == evaluator.LEGACY_SCHEMA
    assert module.REGISTRY_SHA256 == evaluator.REGISTRY_SHA256


def test_exact_published_record_counts(payload):
    assert len(payload["opportunity_evaluations"]) == 27_000
    assert len(payload["window_evaluations"]) == 108
    assert len(payload["cell_summaries"]) == 36


def test_global_attempt_and_support_accounting(payload):
    summary = payload["global_summary"]
    assert summary["attempts_represented"] == 47_250
    assert summary["eligible_attempts"] == 33_749
    assert summary["excluded_attempts"] == 13_501
    assert summary["supported_opportunities"] == 23_999
    assert summary["identity_missing_opportunities"] == 3_001


def test_evaluable_nullable_window_accounting(payload):
    summary = payload["global_summary"]
    assert summary["evaluable_windows"] == 86
    assert summary["unevaluable_windows"] == 22
    assert summary["reconciled_windows"] == 108


def test_all_exclusions_are_missing_predicted_second_zone(payload):
    assert payload["global_summary"]["all_exclusion_reasons"] == ["MISSING_PREDICTED_SECOND_ZONE"]


def test_daily_539_scoring_contract():
    legacy = evaluator.load_verified_legacy_module(REPO_ROOT)
    attempt = {"predicted_main_numbers": [1, 2, 7, 8, 9], "predicted_auxiliary": None}
    outcome = {"main_numbers": [1, 2, 3, 4, 5], "auxiliary": 0}
    assert legacy._score("DAILY_539", attempt, outcome) == {
        "main_hit_count": 2, "special_hit": 0,
        "prize_tier": "D539_FOURTH_PRIZE", "any_prize_aware_win": True,
    }


def test_big_lotto_special_number_scoring_contract():
    legacy = evaluator.load_verified_legacy_module(REPO_ROOT)
    attempt = {"predicted_main_numbers": [1, 2, 7, 8, 9, 10], "predicted_auxiliary": None}
    outcome = {"main_numbers": [1, 2, 3, 4, 5, 6], "auxiliary": 7}
    assert legacy._score("BIG_LOTTO", attempt, outcome)["prize_tier"] == "BIG_CONSOLATION_PRIZE"


def test_power_lotto_second_zone_scoring_contract():
    legacy = evaluator.load_verified_legacy_module(REPO_ROOT)
    attempt = {"predicted_main_numbers": [1, 2, 7, 8, 9, 10], "predicted_auxiliary": 3}
    outcome = {"main_numbers": [1, 4, 5, 6, 11, 12], "auxiliary": 3}
    score = legacy._score("POWER_LOTTO", attempt, outcome)
    assert (score["main_hit_count"], score["special_hit"], score["any_prize_aware_win"]) == (1, 1, True)


def test_excluded_attempt_is_explicit_null_not_failure(payload):
    record = next(item for item in payload["opportunity_evaluations"] if item["excluded_attempts"])
    excluded = [item for item in record["attempt_result_references"] if not item["eligible"]]
    assert excluded
    assert all(item["prize_tier"] is None and item["any_prize_aware_win"] is None for item in excluded)


def test_all_excluded_opportunity_is_unsupported(payload):
    record = next(item for item in payload["opportunity_evaluations"] if not item["supported"])
    assert record["eligible_attempts"] == 0
    assert record["distinct_ticket_count"] == 0
    assert record["observed_success_count"] == 0
    assert record["any_prize_aware_success"] is False
    assert record["best_observed_tier"] is None


def test_distinct_ticket_identity_groups_are_canonical():
    attempts = [
        {"eligible": True, "bet_index": 2, "ticket_identity": {"fingerprint_sha256": "a", "canonical_ticket_content": {"main_numbers": [1, 2]}}},
        {"eligible": True, "bet_index": 1, "ticket_identity": {"fingerprint_sha256": "a", "canonical_ticket_content": {"main_numbers": [1, 2]}}},
        {"eligible": False, "bet_index": 3, "ticket_identity": None},
    ]
    assert evaluator._identity_groups(attempts) == [{
        "fingerprint_sha256": "a", "canonical_ticket_content": {"main_numbers": [1, 2]}, "bet_indices": [1, 2]
    }]


def test_opportunity_interface_is_explicit(payload):
    required = {
        "opportunity_id", "cell_id", "outcome_id", "target_draw", "canonical_date",
        "window_membership", "gross_attempts", "eligible_attempts", "excluded_attempts",
        "exclusion_by_reason", "supported", "eligible_ticket_identities",
        "attempt_result_references", "tier_counts", "endpoint_counts",
        "observed_success_count", "any_prize_aware_success", "best_observed_tier",
        "opportunity_evaluation_digest",
    }
    assert all(required <= set(item) for item in payload["opportunity_evaluations"])


def test_attempt_references_cover_all_attempts(payload):
    assert sum(len(item["attempt_result_references"]) for item in payload["opportunity_evaluations"]) == 47_250


def test_exact_frozen_window_membership_and_anchors(payload):
    for record in payload["window_evaluations"]:
        assert len(record["opportunity_ids"]) == record["window"]
        assert record["window"] in (50, 300, 750)
        assert int(record["earliest_target_draw"]) <= int(record["latest_target_draw"])


def test_postfreeze_rows_are_rejected(payload):
    record = next(item for item in payload["window_evaluations"] if item["cell_id"] == "DAILY_539:acb_markov_midfreq_3bet" and item["window"] == 750)
    assert record["latest_target_draw"] == "115000121"
    assert all(int(item.rsplit(":", 1)[1]) <= 115000121 for item in record["opportunity_ids"])


def test_window_interface_is_explicit(payload):
    required = {
        "window_evaluation_id", "cell_id", "window", "window_label",
        "opportunity_ids", "draw_set_sha256", "latest_target_draw",
        "earliest_target_draw", "gross_attempts", "eligible_attempts",
        "excluded_attempts", "supported_opportunities", "unsupported_opportunities",
        "observed_successes", "tier_counts", "endpoint_counts", "evaluable",
        "support_status", "inferential_field_presence", "inferential_omission_reason",
        "stability", "window_decision", "group_decision", "reconciliation",
        "source_and_derivation_digest",
    }
    assert all(required <= set(item) for item in payload["window_evaluations"])


def test_inferential_values_are_finite_and_intervals_ordered(payload):
    for record in payload["window_evaluations"]:
        if not record["evaluable"]:
            continue
        for field in ("expected_successes", "observed_rate", "mean_baseline_rate", "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower", "bonferroni_p_value", "bonferroni_p_value_lower"):
            assert math.isfinite(record[field])
        assert 0 <= record["raw_p_value_one_sided_upper"] <= 1
        assert 0 <= record["raw_p_value_one_sided_lower"] <= 1
        assert record["wilson_ci_95"][0] <= record["wilson_ci_95"][1]
        assert record["clopper_pearson_ci_95"][0] <= record["clopper_pearson_ci_95"][1]


def test_unevaluable_inference_uses_explicit_null_metadata(payload):
    records = [item for item in payload["window_evaluations"] if not item["evaluable"]]
    assert len(records) == 22
    for record in records:
        assert record["inferential_omission_reason"].startswith("UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:")
        assert record["wilson_ci_95"] is None
        assert record["clopper_pearson_ci_95"] is None
        assert record["raw_p_value_one_sided_upper"] is None
        assert record["bonferroni_p_value"] is None
        assert record["inferential_field_presence"]["wilson_ci_95"] == "present-null"


def test_stability_and_final_decisions_are_published(payload):
    assert all(item["stability"]["status"] in {"STABILITY_PASS", "STABILITY_FAIL"} for item in payload["window_evaluations"])
    assert all(item["window_decision"].startswith("PRIZE_AWARE_") for item in payload["window_evaluations"])


def test_full_field_level_reconciliation(payload):
    for record in payload["window_evaluations"]:
        rec = record["reconciliation"]
        assert rec["primary"]["status"] == "PASS"
        assert rec["identity"]["status"] == "PASS"
        assert rec["inferential"]["status"] == "PASS"
        assert rec["unexplained_mismatches"] == []


def test_numerical_projection_equals_legacy(payload):
    rec = payload["reconciliation"]
    assert rec["legacy_numerical_equivalence"] is True
    assert rec["legacy_numerical_projection_digest"] == rec["canonical_numerical_projection_digest"]


def test_four_zero_identity_power_cells(payload):
    zero = payload["global_summary"]["four_zero_identity_power_lotto_cells"]
    assert (zero["opportunities"], zero["gross_attempts"], zero["eligible_attempts"], zero["excluded_attempts"]) == (3_000, 9_750, 0, 9_750)
    assert zero["exclusion_by_reason"] == {"MISSING_PREDICTED_SECOND_ZONE": 9_750}


def test_known_daily_correction(payload):
    correction = payload["global_summary"]["known_daily_539_correction"]
    assert correction == {
        "cell_id": "DAILY_539:acb_markov_midfreq_3bet", "window": 750,
        "frozen_long_gross_attempts": 2_250, "post_freeze_rows_included": False,
        "minus_88_deficit_present": False,
    }


def test_duplicate_and_index_invariants_are_zero(payload):
    assert set(payload["global_summary"]["duplicate_and_index_invariants"].values()) == {0}


def test_stable_collection_ordering(payload):
    opportunities = payload["opportunity_evaluations"]
    windows = payload["window_evaluations"]
    cells = payload["cell_summaries"]
    assert opportunities == sorted(opportunities, key=lambda item: item["opportunity_id"])
    assert windows == sorted(windows, key=lambda item: (item["lottery_type"], item["strategy_id"], item["window"]))
    assert cells == sorted(cells, key=lambda item: item["cell_id"])


def test_canonical_payload_digest_recomputes(payload):
    assert evaluator.canonical_payload_digest(payload) == payload["canonical_payload_digest"]


def test_canonical_json_rejects_nonfinite_values():
    with pytest.raises(evaluator.CanonicalEvaluationError, match="not finite"):
        evaluator.canonical_bytes({"bad": float("nan")})
    with pytest.raises(evaluator.CanonicalEvaluationError, match="not finite"):
        evaluator.canonical_bytes({"bad": float("inf")})


def test_strict_json_loader_rejects_nonfinite_constants(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"bad":NaN}', encoding="utf-8")
    with pytest.raises(evaluator.CanonicalEvaluationError, match="non-finite"):
        evaluator.strict_json_load(path)


def test_committed_json_has_no_nonfinite_constants():
    json.loads((REPO_ROOT / evaluator.OUTPUT_JSON).read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def test_artifact_size_gates():
    assert (REPO_ROOT / evaluator.OUTPUT_JSON).stat().st_size < evaluator.MAX_JSON_BYTES
    assert (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).stat().st_size < evaluator.MAX_MARKDOWN_BYTES


def test_two_build_determinism_and_committed_bytes(rebuilt):
    second = evaluator.build_evaluation(REPO_ROOT)
    assert evaluator.canonical_bytes(rebuilt) == evaluator.canonical_bytes(second)
    assert evaluator.canonical_bytes(rebuilt) + b"\n" == (REPO_ROOT / evaluator.OUTPUT_JSON).read_bytes()
    assert evaluator.render_markdown(rebuilt).encode("utf-8") == (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).read_bytes()


def test_generate_performs_two_build_gate(tmp_path):
    json_path = tmp_path / "canonical.json"
    markdown_path = tmp_path / "canonical.md"
    evaluator.generate(REPO_ROOT, json_path, markdown_path)
    assert json_path.read_bytes() == (REPO_ROOT / evaluator.OUTPUT_JSON).read_bytes()
    assert markdown_path.read_bytes() == (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).read_bytes()


def test_no_database_network_or_process_imports():
    source = (REPO_ROOT / "analysis/p545b_full_50_300_750_per_draw_evaluator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert imports.isdisjoint({"sqlite3", "socket", "subprocess", "requests", "urllib", "httpx"})


def test_no_database_or_snapshot_path_fallback():
    source = (REPO_ROOT / "analysis/p545b_full_50_300_750_per_draw_evaluator.py").read_text(encoding="utf-8")
    assert "lottery_v2.db" not in source
    assert "P545F" not in source
    assert "PRAGMA" not in source
    assert "ATTACH" not in source


def test_no_predictive_or_betting_claim(payload):
    assert payload["safety"]["predictive_validity_claim"] is False
    assert payload["safety"]["betting_recommendation"] is False
    markdown = (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).read_text(encoding="utf-8")
    assert "No predictive-validity or betting recommendation claim" in markdown


def test_legacy_files_remain_byte_identical():
    assert hashlib.sha256((REPO_ROOT / evaluator.LEGACY_SOURCE).read_bytes()).hexdigest() == evaluator.LEGACY_SOURCE_SHA256
    assert hashlib.sha256((REPO_ROOT / evaluator.LEGACY_OUTPUT).read_bytes()).hexdigest() == evaluator.LEGACY_OUTPUT_SHA256


def test_exact_canonical_file_paths_exist():
    expected = {
        "analysis/p545b_full_50_300_750_per_draw_evaluator.py",
        "tests/test_p545b_full_50_300_750_per_draw_evaluator.py",
        "outputs/research/p545b_full_50_300_750_per_draw_evaluation_20260711.json",
        "outputs/research/p545b_full_50_300_750_per_draw_evaluation_20260711.md",
    }
    assert all((REPO_ROOT / path).is_file() for path in expected)
