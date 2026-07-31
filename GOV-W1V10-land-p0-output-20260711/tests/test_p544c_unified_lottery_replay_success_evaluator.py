"""Focused no-database tests for the deterministic P544C R1 evaluator."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from analysis import p544c_unified_lottery_replay_success_evaluator as evaluator


REPO_ROOT = Path(evaluator.__file__).resolve().parents[1]
OUTPUT_STEM = "p544c_unified_lottery_replay_success_evaluator_20260710"
COMMITTED_JSON = REPO_ROOT / "outputs" / "research" / f"{OUTPUT_STEM}.json"
COMMITTED_MARKDOWN = REPO_ROOT / "outputs" / "research" / f"{OUTPUT_STEM}.md"


@pytest.fixture(scope="module")
def p543c_packet() -> dict[str, object]:
    source = evaluator.GitBlobSource(REPO_ROOT)
    spec = evaluator.SOURCE_SPECS[0]
    raw = source.read(spec["path"])
    evaluator.verify_source_bytes(spec, raw)
    return json.loads(raw)


@pytest.fixture(scope="module")
def p543c_audit(p543c_packet: dict[str, object]) -> dict[str, object]:
    return evaluator.audit_p543c(p543c_packet)


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    first_dir = tmp_path_factory.mktemp("p544c-first")
    second_dir = tmp_path_factory.mktemp("p544c-second")
    first_json, first_markdown = evaluator.generate(REPO_ROOT, first_dir)
    second_json, second_markdown = evaluator.generate(REPO_ROOT, second_dir)
    first_json_bytes = first_json.read_bytes()
    first_markdown_bytes = first_markdown.read_bytes()
    return {
        "first_json": first_json_bytes,
        "second_json": second_json.read_bytes(),
        "first_markdown": first_markdown_bytes,
        "second_markdown": second_markdown.read_bytes(),
        "payload": json.loads(first_json_bytes),
        "markdown": first_markdown_bytes.decode("utf-8"),
    }


def test_committed_p543c_shape_and_field_inventory(p543c_audit: dict[str, object]) -> None:
    shape = p543c_audit["contract_shape"]
    amendment = p543c_audit["special_hit_contract_amendment"]
    assert shape["candidate_count"] == 10
    assert shape["row_count"] == 500
    assert set(shape["rows_per_candidate"].values()) == {50}
    assert amendment["special_actual_present_rows"] == 500
    assert amendment["special_selected_null_rows"] == 500
    assert amendment["source_special_hit_count"] == 0


def test_main_hit_counts_recompute_without_drift(p543c_audit: dict[str, object]) -> None:
    rows = p543c_audit["per_draw_cells"]
    assert p543c_audit["contract_shape"]["main_hit_count_mismatch_count"] == 0
    assert all(row["main_hit_consistent"] for row in rows)
    spectrum = Counter(row["recomputed_hit_count"] for row in rows)
    assert [spectrum.get(index, 0) for index in range(7)] == [204, 204, 74, 18, 0, 0, 0]


def test_special_hit_amendment_reproduces_expected_counts(p543c_audit: dict[str, object]) -> None:
    amendment = p543c_audit["special_hit_contract_amendment"]
    rows = p543c_audit["per_draw_cells"]
    assert amendment["recomputed_special_hit_count"] == 63
    assert amendment["mismatch_count"] == 63
    assert amendment["m2_plus_special_prize_case_count"] == 7
    assert sum(row["official_any_prize_success"] for row in rows) == 25
    assert sum(row["recomputed_hit_count"] >= 3 for row in rows) == 18


def test_special_hit_rule_uses_selected_numbers_not_special_selected() -> None:
    assert evaluator.recompute_big_lotto_special_hit([1, 2, 3, 4, 5, 6], 6) is True
    assert evaluator.recompute_big_lotto_special_hit([1, 2, 3, 4, 5, 6], 7) is False
    assert evaluator.score_big_lotto_any_prize(2, True) is True
    assert evaluator.score_big_lotto_any_prize(2, False) is False
    assert evaluator.score_big_lotto_any_prize(3, False) is True


def test_special_selected_is_non_authoritative_and_does_not_block(
    p543c_packet: dict[str, object],
) -> None:
    amended = copy.deepcopy(p543c_packet)
    amended["contract"]["rows"][0]["special_selected"] = 49
    audit = evaluator.audit_p543c(amended)
    assert audit["special_hit_contract_amendment"]["special_selected_null_rows"] == 499
    assert audit["special_hit_contract_amendment"]["recomputed_special_hit_count"] == 63
    assert audit["special_hit_contract_amendment"]["mismatch_count"] == 63
    assert audit["special_hit_contract_amendment"]["m2_plus_special_prize_case_count"] == 7


def test_missing_special_actual_blocks_affected_row(p543c_packet: dict[str, object]) -> None:
    broken = copy.deepcopy(p543c_packet)
    broken["contract"]["rows"][0]["special_actual"] = None
    with pytest.raises(evaluator.ContractSemanticError, match="special_actual"):
        evaluator.audit_p543c(broken)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("selected_numbers", [1, 1, 2, 3, 4, 5]),
        ("actual_numbers", [1, 2, 3, 4, 5]),
        ("hit_count", 6),
        ("special_actual", True),
    ),
)
def test_malformed_primary_fields_fail_closed(
    p543c_packet: dict[str, object], field: str, value: object
) -> None:
    broken = copy.deepcopy(p543c_packet)
    broken["contract"]["rows"][0][field] = value
    with pytest.raises(evaluator.ContractSemanticError):
        evaluator.audit_p543c(broken)


def test_conflicting_primary_outcome_fields_fail_closed(p543c_packet: dict[str, object]) -> None:
    broken = copy.deepcopy(p543c_packet)
    first = broken["contract"]["rows"][0]
    first["special_actual"] = first["actual_numbers"][0]
    with pytest.raises(evaluator.ContractSemanticError, match="duplicates a main outcome"):
        evaluator.audit_p543c(broken)


def test_duplicate_or_conflicting_draw_identity_fails_closed(
    p543c_packet: dict[str, object],
) -> None:
    duplicate = copy.deepcopy(p543c_packet)
    first, second = duplicate["contract"]["rows"][0:2]
    first["draw_id"] = second["draw_id"]
    first["draw_date"] = second["draw_date"]
    with pytest.raises(evaluator.ContractSemanticError, match="duplicate candidate/draw identity"):
        evaluator.audit_p543c(duplicate)

    conflict = copy.deepcopy(p543c_packet)
    rows = conflict["contract"]["rows"]
    first = rows[0]
    other_candidate = next(row for row in rows if row["candidate_id"] != first["candidate_id"])
    other_candidate["draw_id"] = first["draw_id"]
    other_candidate["draw_date"] = first["draw_date"]
    with pytest.raises(evaluator.ContractSemanticError, match="conflicting official primary fields"):
        evaluator.audit_p543c(conflict)


def test_amendment_provenance_and_affected_ids_are_complete(p543c_audit: dict[str, object]) -> None:
    amendment = p543c_audit["special_hit_contract_amendment"]
    affected = amendment["affected_row_ids"]
    keys = [
        (row["candidate_id"], row["draw_order"], row["draw_id"], row["draw_date"])
        for row in affected
    ]
    assert amendment["resolution"] == "semantic_drift_explained_recomputed_from_primary_fields"
    assert amendment["source_field_authority"] == "non_authoritative_derived_field"
    assert amendment["authoritative_primary_fields"] == ["selected_numbers", "special_actual"]
    assert amendment["upstream_artifact_modified"] is False
    assert len(keys) == len(set(keys)) == 63
    assert keys == sorted(keys)


def test_big_lotto_exact_baselines_and_endpoint_truth_table() -> None:
    constants = evaluator.derive_analytic_constants()["BIG_LOTTO"]
    assert constants["universe"] == 13_983_816
    assert constants["m3_plus_numerator"] == 260_624
    assert constants["m2_plus_special_numerator"] == 172_200
    assert constants["any_prize_numerator"] == 432_824
    assert constants["rate_12dp"] == "0.030951780258"
    assert sum(evaluator.BIG_LOTTO_MAIN_HIT_NUMERATORS.values()) == evaluator.BIG_LOTTO_UNIVERSE


def test_track1_candidate_metrics_and_inference_fixtures(two_runs: dict[str, object]) -> None:
    candidates = {
        item["candidate_id"]: item
        for item in two_runs["payload"]["track1_big_lotto_short"]["candidate_evaluations"]
    }
    assert {key: value["official_any_prize_count"] for key, value in candidates.items()} == {
        "bet2_fourier_expansion_biglotto:1": 4,
        "biglotto_deviation_2bet:1": 2,
        "biglotto_echo_aware_3bet:1": 2,
        "biglotto_triple_strike:1": 4,
        "biglotto_ts3_markov_4bet_w30:1": 4,
        "coldpool15_biglotto:1": 2,
        "fourier30_markov30_biglotto:1": 1,
        "markov_2bet_biglotto:1": 1,
        "markov_single_biglotto:1": 1,
        "ts3_regime_3bet:1": 4,
    }
    bet2 = candidates["bet2_fourier_expansion_biglotto:1"]
    assert bet2["exact_main_hit_counts"] == {
        "M0": 20,
        "M1": 19,
        "M2": 8,
        "M3": 3,
        "M4": 0,
        "M5": 0,
        "M6": 0,
    }
    assert bet2["m2_and_special_count"] == 1
    assert sum(item["m3_and_special_count"] for item in candidates.values()) == 1
    assert candidates["biglotto_echo_aware_3bet:1"]["m3_and_special_count"] == 1
    assert bet2["inference"]["raw_p_value_one_sided_upper"] == 0.068736400078
    assert bet2["inference"]["bonferroni_p_value_upper"] == 0.687364000784
    assert bet2["inference"]["relative_lift"] == 2.584665545349
    assert all(item["classification"] not in {"research_candidate", "holdout_supported_candidate"} for item in candidates.values())


def test_track1_internal_denominator_and_cumulative_invariants(two_runs: dict[str, object]) -> None:
    for candidate in two_runs["payload"]["track1_big_lotto_short"]["candidate_evaluations"]:
        exact = candidate["exact_main_hit_counts"]
        cumulative = candidate["cumulative_main_hit_counts"]
        assert sum(exact.values()) == 50
        for threshold in range(1, 7):
            assert cumulative[f"M{threshold}plus"] == sum(exact[f"M{hit}"] for hit in range(threshold, 7))
        partition = candidate["denominator_partition"]
        assert partition["supported_draws"] + partition["no_prediction_draws"] + partition["excluded_invalid_draws"] == partition["window_draw_count"]
        assert candidate["coverage"] == 1.0
        assert 0.0 <= candidate["inference"]["raw_p_value_one_sided_upper"] <= 1.0


def test_chronological_stability_is_se_scaled(two_runs: dict[str, object]) -> None:
    for candidate in two_runs["payload"]["track1_big_lotto_short"]["candidate_evaluations"]:
        stability = candidate["chronological_stability"]
        assert stability["early"]["draws"] == stability["late"]["draws"] == 25
        assert stability["absolute_delta_alone_is_decision_gate"] is False
        assert stability["status"] != "chronologically_unstable"
        assert 0.0 <= stability["two_sided_p_value"] <= 1.0


def test_fixed_seed_pairing_permutation_fixtures(two_runs: dict[str, object]) -> None:
    candidates = {
        item["candidate_id"]: item["pairing_permutation"]
        for item in two_runs["payload"]["track1_big_lotto_short"]["candidate_evaluations"]
    }
    bet2 = candidates["bet2_fourier_expansion_biglotto:1"]
    assert bet2["seed"] == 543_010
    assert bet2["permutations"] == 1_000
    assert bet2["permutation_success_count_distribution"]["mean"] == 2.148
    assert bet2["inclusive_empirical_percentile"] == 0.934
    assert bet2["add_one_empirical_upper_p_value"] == 0.167832167832
    fourier = candidates["fourier30_markov30_biglotto:1"]
    assert fourier["permutation_success_count_distribution"]["mean"] == 4.283
    assert fourier["add_one_empirical_upper_p_value"] == 0.993006993007
    assert "alignment/timing null" in bet2["null_hypothesis"]


def test_p273a_108_windows_recompute_without_mismatch(two_runs: dict[str, object]) -> None:
    verification = two_runs["payload"]["aggregate_verification"]["p273a"]
    assert verification["consistency_with_committed"] is True
    assert verification["verified_window_count"] == 108
    assert verification["family_size"] == 108
    assert verification["mismatched_fields"] == []
    assert verification["committed_prediction_success_claim"] is False
    zero_support = [row for row in verification["verification_rows"] if row["support_draws"] == 0]
    assert len(zero_support) == 12
    assert all(row["baseline_rate_recomputed"] is None for row in zero_support)


def test_p281a_analytic_constants_reproduce_exactly(two_runs: dict[str, object]) -> None:
    verification = two_runs["payload"]["aggregate_verification"]["p281a"]
    constants = verification["analytic_constants"]
    assert verification["consistency_with_committed"] is True
    assert verification["mismatched_fields"] == []
    assert constants["DAILY_539"]["universe"] == 575_757
    assert constants["DAILY_539"]["any_prize_numerator"] == 65_621
    assert constants["DAILY_539"]["rate_12dp"] == "0.113973429763"
    assert constants["POWER_LOTTO"]["universe"] == 22_085_448
    assert constants["POWER_LOTTO"]["any_prize_numerator"] == 2_602_320
    assert constants["POWER_LOTTO"]["rate_12dp"] == "0.117829622474"


def test_track3_normalization_counts_and_summary_boundary(two_runs: dict[str, object]) -> None:
    normalized = two_runs["payload"]["normalized_summaries"]
    assert normalized["counts"] == {
        "p542a_strategy_rows": 603,
        "p536c_lift_rows": 603,
        "p536c_cross_lottery_projections": 195,
        "p543a_historical_evidence_rows": 621,
    }
    assert normalized["raw_cross_lottery_rate_pooling_performed"] is False
    assert all(row["source_record_type"] != "per_draw" for section in (
        "p542a_strategy_rows",
        "p536c_lift_rows",
        "p543a_historical_evidence_rows",
    ) for row in normalized[section])
    with pytest.raises(evaluator.CrossLotteryPoolingError):
        evaluator.reject_cross_lottery_raw_rate_pooling(["BIG_LOTTO", "DAILY_539"])


def test_stable_input_order_semantics(p543c_packet: dict[str, object]) -> None:
    original_audit = evaluator.audit_p543c(p543c_packet)
    reordered = copy.deepcopy(p543c_packet)
    reordered["candidate_subset"].reverse()
    reordered["contract"]["rows"].reverse()
    for row in reordered["contract"]["rows"]:
        row["selected_numbers"].reverse()
        row["actual_numbers"].reverse()
    reordered_audit = evaluator.audit_p543c(reordered)
    assert reordered_audit["contract_shape"] == original_audit["contract_shape"]
    assert reordered_audit["special_hit_contract_amendment"] == original_audit["special_hit_contract_amendment"]
    assert evaluator.build_track1(reordered_audit, 20) == evaluator.build_track1(original_audit, 20)


def test_source_sha_verification_and_tamper_fail_closed() -> None:
    source = evaluator.GitBlobSource(REPO_ROOT)
    for spec in evaluator.SOURCE_SPECS:
        raw = source.read(spec["path"])
        evaluator.verify_source_bytes(spec, raw)
    spec = evaluator.SOURCE_SPECS[0]
    tampered = bytearray(source.read(spec["path"]))
    tampered[-2] ^= 1
    with pytest.raises(evaluator.InputIntegrityError, match="SHA-256 mismatch"):
        evaluator.verify_source_bytes(spec, bytes(tampered))


def test_timestamp_comes_from_pinned_commit(two_runs: dict[str, object]) -> None:
    metadata = two_runs["payload"]["metadata"]
    assert metadata["pinned_source_commit"] == evaluator.PINNED_SOURCE_COMMIT
    assert metadata["generated_at_utc"] == "2026-07-10T09:11:15+00:00"
    assert metadata["frozen_spec_digest"] == evaluator.FROZEN_SPEC_DIGEST


def test_two_run_json_bytes_are_deterministic(two_runs: dict[str, object]) -> None:
    assert two_runs["first_json"] == two_runs["second_json"]


def test_two_run_markdown_bytes_are_deterministic(two_runs: dict[str, object]) -> None:
    assert two_runs["first_markdown"] == two_runs["second_markdown"]


def test_generated_artifacts_match_committed_bytes(two_runs: dict[str, object]) -> None:
    assert two_runs["first_json"] == COMMITTED_JSON.read_bytes()
    assert two_runs["first_markdown"] == COMMITTED_MARKDOWN.read_bytes()


def test_canonical_payload_digest_reproduces_independently(two_runs: dict[str, object]) -> None:
    payload = two_runs["payload"]
    stripped = {key: value for key, value in payload.items() if key != "canonical_payload_digest"}
    canonical = json.dumps(stripped, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == payload["canonical_payload_digest"]


def test_p544c_sources_have_no_data_engine_import_or_connection() -> None:
    forbidden_module = "sql" + "ite3"
    forbidden_call = "con" + "nect"
    for path in (Path(evaluator.__file__), Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert forbidden_module not in imported
        assert not any(
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == forbidden_call)
                or (isinstance(node.func, ast.Name) and node.func.id == forbidden_call)
            )
            for node in ast.walk(tree)
        )


def test_no_database_artifact_path_can_be_opened() -> None:
    assert all(Path(spec["path"]).suffix == ".json" for spec in evaluator.SOURCE_SPECS)
    with pytest.raises(evaluator.InputIntegrityError):
        evaluator.validate_repo_relative_json_path("data/example.db")
    with pytest.raises(evaluator.InputIntegrityError):
        evaluator.validate_repo_relative_json_path("/tmp/example.json")
    with pytest.raises(evaluator.InputIntegrityError):
        evaluator.validate_repo_relative_json_path("../example.json")


def test_upstream_p543c_p543d_p544b_bytes_are_unchanged() -> None:
    paths = (
        "analysis/p543c_candidate_per_draw_validation_contract.py",
        "tests/test_p543c_candidate_per_draw_validation_contract.py",
        "outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json",
        "outputs/research/p543c_candidate_per_draw_validation_contract_20260710.md",
        "analysis/p543d_contract_validation_pilot.py",
        "tests/test_p543d_contract_validation_pilot.py",
        "outputs/research/p543d_contract_validation_pilot_20260710.json",
        "outputs/research/p543d_contract_validation_pilot_20260710.md",
        "analysis/p544b_readonly_replay_artifact_inventory.py",
        "tests/test_p544b_readonly_replay_artifact_inventory.py",
        "outputs/research/p544b_readonly_replay_artifact_inventory_20260710.json",
        "outputs/research/p544b_readonly_replay_artifact_inventory_20260710.md",
    )
    for relative_path in paths:
        committed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{evaluator.PINNED_SOURCE_COMMIT}:{relative_path}"],
            check=True,
            capture_output=True,
        ).stdout
        assert (REPO_ROOT / relative_path).read_bytes() == committed


def test_outputs_are_retrospective_without_positive_claims(two_runs: dict[str, object]) -> None:
    safety = two_runs["payload"]["safety"]
    markdown = two_runs["markdown"]
    assert safety["retrospective_research_only"] is True
    assert safety["historical_replay_is_future_prediction_evidence"] is False
    assert safety["increased_winning_odds_claim"] is False
    assert safety["betting_advice"] is False
    assert safety["production_or_go_live_readiness"] is False
    assert safety["database_opened"] is False
    assert safety["database_written"] is False
    for required in ("Retrospective research only", "not betting advice", "does not establish production"):
        assert required in markdown
    for forbidden in ("guarantees future", "increases your odds", "ready for betting", "production-ready"):
        assert forbidden not in markdown.lower()
