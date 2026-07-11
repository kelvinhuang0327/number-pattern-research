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
    assert payload["generated_at_utc"] == "2026-07-11T07:58:26Z"
    assert payload["generated_at_policy"] == evaluator.GENERATED_AT_POLICY
    policy = payload["generated_at_policy"]
    assert policy["source_timestamp_field"] == "committer timestamp"
    assert policy["output_format"] == "RFC 3339 with trailing Z"
    assert policy["wall_clock_used"] is False


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
    assert {item["source_commit"] for item in manifest} == {evaluator.IMPLEMENTATION_BASE_COMMIT}


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
    assert summary["attempts"] == 47_250
    assert summary["eligible_attempts"] == 33_749
    assert summary["excluded_attempts"] == 13_501
    assert summary["supported_opportunities"] == 23_999
    assert summary["unsupported_opportunities"] == 3_001


def test_evaluable_nullable_window_accounting(payload):
    summary = payload["global_summary"]
    assert summary["evaluable_windows"] == 86
    assert summary["unevaluable_windows"] == 22
    assert summary["reconciliation_totals"]["full_canonical_field_pass"] == 108


def test_all_exclusions_are_missing_predicted_second_zone(payload):
    assert payload["global_summary"]["exclusion_totals"] == {"MISSING_PREDICTED_SECOND_ZONE": 13_501}


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


def test_confidence_interval_fixtures():
    inference = evaluator.load_verified_legacy_module(REPO_ROOT).inference
    wilson = inference.wilson_interval(5, 10)
    exact = inference.clopper_pearson_interval(5, 10)
    assert wilson == pytest.approx((0.236593090513, 0.763406909487), abs=1e-12)
    assert exact == pytest.approx((0.187086028447, 0.812913971553), abs=1e-10)


def test_raw_upper_and_lower_p_value_fixtures():
    inference = evaluator.load_verified_legacy_module(REPO_ROOT).inference
    upper, upper_method = inference.upper_tail_pvalue(2, [0.5, 0.5, 0.5])
    lower, lower_method = inference.lower_tail_pvalue(2, [0.5, 0.5, 0.5])
    assert (upper, lower) == pytest.approx((0.5, 0.875))
    assert (upper_method, lower_method) == ("exact_binomial_upper", "exact_binomial_lower")


def test_bonferroni_fixture():
    inference = evaluator.load_verified_legacy_module(REPO_ROOT).inference
    assert inference.bonferroni_pvalue(0.0001) == pytest.approx(0.0108)


def test_bh_fdr_descriptive_fixture():
    inference = evaluator.load_verified_legacy_module(REPO_ROOT).inference
    assert inference.benjamini_hochberg([0.01, 0.03, 0.2], q=0.10) == [True, True, False]


def test_support_evaluability_fixture():
    inference = evaluator.load_verified_legacy_module(REPO_ROOT).inference
    draws = [{"target_draw": str(index), "distinct_ticket_count": 1} for index in range(50)]
    record = {
        "lottery_type": "DAILY_539", "strategy_id": "fixture", "window": 50,
        "window_label": "SHORT", "support_draws": 50, "observed_successes": 5,
        "bet_count_distribution": {"1": 50},
    }
    assert inference.evaluate_window("DAILY_539", "fixture", record, draws)["evaluable"] is True
    record["support_draws"] = 29
    assert inference.evaluate_window("DAILY_539", "fixture", record, draws[:29])["evaluable"] is False


def test_tier_and_endpoint_aggregation(payload):
    for record in payload["opportunity_evaluations"]:
        assert sum(record["tier_counts"].values()) == record["eligible_attempt_count"]
        assert sum(record["endpoint_counts"].values()) == record["eligible_attempt_count"]


def test_observed_success_counts_match_any_success(payload):
    assert all(record["observed_success_count"] == int(record["any_success"]) for record in payload["opportunity_evaluations"])


def test_evaluable_missing_field_fails_closed(payload):
    bad = dict(payload)
    bad["window_evaluations"] = list(payload["window_evaluations"])
    index = next(i for i, item in enumerate(bad["window_evaluations"]) if item["evaluable"])
    bad["window_evaluations"][index] = dict(bad["window_evaluations"][index])
    bad["window_evaluations"][index]["expected_successes"] = None
    with pytest.raises(evaluator.CanonicalEvaluationError, match="evaluable field missing"):
        evaluator.validate_canonical_payload(bad)


def test_excluded_attempt_is_explicit_null_not_failure(payload):
    record = next(item for item in payload["opportunity_evaluations"] if item["excluded_attempt_count"])
    excluded = [item for item in record["attempt_result_refs"] if not item["eligible"]]
    assert excluded
    assert all(item["prize_tier"] is None and item["any_prize_aware_win"] is None for item in excluded)


def test_all_excluded_opportunity_is_unsupported(payload):
    record = next(item for item in payload["opportunity_evaluations"] if not item["supported"])
    assert record["eligible_attempt_count"] == 0
    assert record["eligible_ticket_identity_refs"] == []
    assert record["observed_success_count"] == 0
    assert record["any_success"] is False
    assert record["best_observed_tier"] is None
    assert record["all_attempts_excluded"] is True


def test_distinct_ticket_identity_groups_are_canonical():
    attempts = [
        {"eligible": True, "bet_index": 2, "ticket_identity": {"fingerprint_sha256": "a", "canonical_ticket_content": {"main_numbers": [1, 2]}}},
        {"eligible": True, "bet_index": 1, "ticket_identity": {"fingerprint_sha256": "a", "canonical_ticket_content": {"main_numbers": [1, 2]}}},
        {"eligible": False, "bet_index": 3, "ticket_identity": None},
    ]
    assert evaluator._identity_groups(attempts) == [{
        "fingerprint_sha256": "a", "bet_indices": [1, 2]
    }]


def test_opportunity_interface_is_explicit(payload):
    required = {
        "opportunity_id", "cell_id", "outcome_id", "target_draw", "canonical_date",
        "in_short_window", "in_mid_window", "in_long_window", "gross_attempt_count",
        "eligible_attempt_count", "excluded_attempt_count", "exclusion_by_reason",
        "supported", "all_attempts_excluded", "eligible_ticket_identity_refs",
        "attempt_result_refs", "tier_counts", "endpoint_counts",
        "observed_success_count", "any_success", "best_observed_tier",
        "opportunity_evaluation_digest",
    }
    assert all(required <= set(item) for item in payload["opportunity_evaluations"])


def test_attempt_references_cover_all_attempts(payload):
    assert sum(len(item["attempt_result_refs"]) for item in payload["opportunity_evaluations"]) == 47_250


def test_exact_frozen_window_membership_and_anchors(payload):
    for record in payload["window_evaluations"]:
        assert len(record["opportunity_ids"]) == record["window_size"]
        assert record["window_size"] in (50, 300, 750)
        assert int(record["anchor_first_draw"]) <= int(record["anchor_last_draw"])


def test_draw_set_digest_is_published_from_exact_membership(payload):
    for record in payload["window_evaluations"]:
        target_draws = [item.rsplit(":", 1)[1] for item in record["opportunity_ids"]]
        assert record["draw_set_digest"] == evaluator.digest(target_draws)


def test_postfreeze_rows_are_rejected(payload):
    record = next(item for item in payload["window_evaluations"] if item["cell_id"] == "DAILY_539:acb_markov_midfreq_3bet" and item["window_size"] == 750)
    assert record["anchor_last_draw"] == "115000121"
    assert all(int(item.rsplit(":", 1)[1]) <= 115000121 for item in record["opportunity_ids"])


def test_window_interface_is_explicit(payload):
    required = {
        "window_id", "cell_id", "window_name", "window_size", "opportunity_ids",
        "draw_set_digest", "anchor_first_draw", "anchor_last_draw",
        "gross_attempt_count", "eligible_attempt_count", "excluded_attempt_count",
        "supported_opportunity_count", "unsupported_opportunity_count",
        "observed_success_count", "tier_counts", "endpoint_counts", "evaluable",
        "support_status", "inferential_field_presence", "omitted_inferential_fields",
        "omission_reason", "stability", "decision", "reconciliation",
        "source_derivation", "window_evaluation_digest",
    }
    assert all(required <= set(item) for item in payload["window_evaluations"])


def test_inferential_values_are_finite_and_intervals_ordered(payload):
    for record in payload["window_evaluations"]:
        if not record["evaluable"]:
            continue
        for field in ("expected_successes", "observed_rate", "mean_baseline_rate", "raw_p_value_one_sided_upper", "raw_p_value_one_sided_lower", "bonferroni_p_value_upper", "bonferroni_p_value_lower"):
            assert math.isfinite(record[field])
        assert 0 <= record["raw_p_value_one_sided_upper"] <= 1
        assert 0 <= record["raw_p_value_one_sided_lower"] <= 1
        assert record["confidence_interval"]["wilson_95"][0] <= record["confidence_interval"]["wilson_95"][1]
        assert record["confidence_interval"]["clopper_pearson_95"][0] <= record["confidence_interval"]["clopper_pearson_95"][1]


def test_unevaluable_inference_uses_explicit_null_metadata(payload):
    records = [item for item in payload["window_evaluations"] if not item["evaluable"]]
    assert len(records) == 22
    for record in records:
        assert record["omission_reason"].startswith("UNEVALUABLE_WINDOW_STATISTIC_NOT_COMPUTED:")
        assert record["confidence_interval"]["wilson_95"] is None
        assert record["confidence_interval"]["clopper_pearson_95"] is None
        assert record["raw_p_value_one_sided_upper"] is None
        assert record["bonferroni_p_value_upper"] is None
        assert record["inferential_field_presence"]["confidence_interval.wilson_95"] == "source_absent_normalized_to_null"
        assert "confidence_interval.wilson_95" in record["omitted_inferential_fields"]


def test_inferential_field_presence_vocabulary(payload):
    allowed = {"present_value", "present_null", "source_absent_normalized_to_null"}
    assert all(set(record["inferential_field_presence"].values()) <= allowed for record in payload["window_evaluations"])


def test_window_source_derivation_is_explicit_and_pinned(payload):
    for record in payload["window_evaluations"]:
        derivation = record["source_derivation"]
        assert set(derivation) == {
            "input_registry", "scoring_contracts", "statistical_contracts",
            "frozen_window_evidence", "relevant_digests", "duplicate_content_draw_count",
        }
        assert derivation["input_registry"] == {
            "path": evaluator.REGISTRY_PATH,
            "sha256": evaluator.REGISTRY_SHA256,
            "semantic_projection_digest": evaluator.REGISTRY_SEMANTIC_DIGEST,
            "canonical_payload_digest": evaluator.REGISTRY_CANONICAL_DIGEST,
        }
        assert len(derivation["scoring_contracts"]) == 2
        assert len(derivation["statistical_contracts"]) == 1
        frozen = derivation["frozen_window_evidence"]
        assert (frozen["cell_id"], frozen["window_name"], frozen["window_size"]) == (
            record["cell_id"], record["window_name"], record["window_size"],
        )
        assert frozen["anchor_first_draw"] == record["anchor_first_draw"]
        assert frozen["anchor_last_draw"] == record["anchor_last_draw"]
        assert set(derivation["relevant_digests"]) == {
            "legacy_window_evaluation_digest", "inferential_record_digest",
            "committed_window_reconciliation_digest",
        }


def test_stability_and_final_decisions_are_published(payload):
    assert all(item["stability"]["status"] in {"STABILITY_PASS", "STABILITY_FAIL"} for item in payload["window_evaluations"])
    assert all(item["decision"]["window"].startswith("PRIZE_AWARE_") for item in payload["window_evaluations"])


def test_full_field_level_reconciliation(payload):
    for record in payload["window_evaluations"]:
        rec = record["reconciliation"]
        assert rec["primary"]["status"] == "PASS"
        assert rec["identity"]["status"] == "PASS"
        assert rec["inferential"]["status"] == "PASS"
        assert rec["classification"] == "FULL_CANONICAL_FIELD_RECONCILIATION_PASS"
        assert rec["unexplained_mismatches"] == []


def test_semantic_projection_equals_legacy(payload):
    rec = payload["reconciliation"]
    assert rec["legacy_canonical_semantic_equivalence"] is True
    assert rec["legacy_semantic_projection_digest"] == rec["canonical_semantic_projection_digest"]


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
    assert set(payload["global_summary"]["duplicate_conflict_totals"].values()) == {0}


def test_stable_collection_ordering(payload):
    opportunities = payload["opportunity_evaluations"]
    windows = payload["window_evaluations"]
    cells = payload["cell_summaries"]
    assert opportunities == sorted(opportunities, key=lambda item: item["opportunity_id"])
    assert windows == sorted(windows, key=lambda item: (item["cell_id"], item["window_size"]))
    assert cells == sorted(cells, key=lambda item: item["cell_id"])


def test_canonical_payload_digest_recomputes(payload):
    assert evaluator.canonical_payload_digest(payload) == payload["canonical_payload_digest"]


def test_committed_payload_passes_explicit_validator(payload):
    evaluator.validate_canonical_payload(payload)


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


def test_strict_json_loader_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"same":1,"same":2}', encoding="utf-8")
    with pytest.raises(evaluator.CanonicalEvaluationError, match="duplicate JSON object key"):
        evaluator.strict_json_load(path)


def test_committed_json_has_no_nonfinite_constants():
    json.loads((REPO_ROOT / evaluator.OUTPUT_JSON).read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def test_artifact_size_gates():
    assert (REPO_ROOT / evaluator.OUTPUT_JSON).stat().st_size < evaluator.MAX_JSON_BYTES
    assert (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).stat().st_size < evaluator.MAX_MARKDOWN_BYTES


def test_two_build_determinism_and_committed_bytes(rebuilt):
    first = evaluator.canonical_bytes(rebuilt)
    second = evaluator.canonical_bytes(rebuilt)
    assert first == second
    assert evaluator.canonical_bytes(rebuilt) + b"\n" == (REPO_ROOT / evaluator.OUTPUT_JSON).read_bytes()
    assert evaluator.render_markdown(rebuilt).encode("utf-8") == (REPO_ROOT / evaluator.OUTPUT_MARKDOWN).read_bytes()


def test_non_self_referential_determinism_hashes(payload):
    determinism = payload["determinism"]
    json_hash = hashlib.sha256(evaluator._json_determinism_projection(payload)).hexdigest()
    assert determinism["json_build_a_projection_sha256"] == json_hash
    assert determinism["json_build_b_projection_sha256"] == json_hash
    markdown_hash = hashlib.sha256(
        evaluator.render_markdown(payload, projection=True).encode("utf-8")
    ).hexdigest()
    assert determinism["markdown_build_a_sha256"] == markdown_hash
    assert determinism["markdown_build_b_sha256"] == markdown_hash
    assert determinism["immutable_in_memory_result_count"] == 1
    assert determinism["json_serialization_build_count"] == 2
    assert determinism["markdown_render_build_count"] == 2


def test_ordered_60_case_test_contract_mapping(payload):
    mapping = payload["determinism"]["test_contract_mapping"]
    assert len(mapping) == 60
    assert [item["case"] for item in mapping] == list(range(1, 61))
    assert all(set(item) == {"case", "requirement", "test_name"} for item in mapping)
    test_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    test_names = {
        node.name for node in test_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert all(item["requirement"] and item["test_name"] in test_names for item in mapping)


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


def test_safety_contract_is_complete(payload):
    safety = payload["safety"]
    assert safety["database_opened"] is False
    assert safety["snapshot_opened"] is False
    assert safety["sqlite_imported_or_connection_opened"] is False
    assert safety["network_used_by_evaluator_or_tests"] is False
    assert safety["strategy_search"] is False
    assert safety["parameter_tuning"] is False
    assert safety["combination_optimization"] is False
    assert safety["deployment_action"] is False


def test_limitations_include_required_no_claims(payload):
    text = " ".join(payload["limitations"])
    assert "no untouched prospective holdout" in text.lower()
    assert "predictive validity" in text.lower()
    assert "betting edge" in text.lower()
    assert "ROI" in text and "EV" in text and "staking" in text
    assert "deployment-readiness" in text


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
