from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path

import pytest

from analysis import p279b_disjoint_block_diversified_baseline_falsification as p279b


@pytest.fixture(scope="session")
def report():
    return p279b.build_artifact()


def test_exact_source_artifact_identities_and_digests(report):
    assert len(report["source_artifacts"]) == 5
    actual = {item["source_id"]: item for item in report["source_artifacts"]}
    assert set(actual) == set(p279b.SOURCE_SPECS)
    for source_id, spec in p279b.SOURCE_SPECS.items():
        assert actual[source_id]["path"] == spec["path"]
        assert actual[source_id]["raw_sha256"] == spec["raw_sha256"]
        assert (
            actual[source_id]["canonical_payload_digest"]
            == spec["canonical_payload_digest"]
        )
        assert actual[source_id]["digest_verified"] is True


def test_exact_frozen_candidate_family_and_budgets(report):
    assert [
        (item["lottery_type"], item["strategy_id"], item["ticket_budget"])
        for item in report["frozen_candidates"]
    ] == [
        ("DAILY_539", "acb_markov_midfreq_3bet", 3),
        ("DAILY_539", "daily539_f4cold_3bet", 3),
        ("DAILY_539", "daily539_f4cold_5bet", 5),
    ]
    assert all(item["identity_budget_verified"] for item in report["frozen_candidates"])
    assert all(item["p275b_budget_verified"] for item in report["frozen_candidates"])


def test_nested_supports_disjoint_subtraction_and_recombination(report):
    expected = p279b.EXPECTED_DISJOINT_COUNTS
    for item in report["disjoint_block_derivation"]:
        assert [
            item["nested_counts"][f"latest_{size}"]["support"]
            for size in (50, 300, 750)
        ] == [50, 300, 750]
        assert item["derived_disjoint_counts"] == expected[item["strategy_id"]]
        assert item["nonnegative_integer_subtraction"] is True
        assert all(item["recombination"].values())
        assert item["expected_p279a_counts_matched"] is True
        assert all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in item["derived_disjoint_counts"].values()
        )


def test_exhaustive_universe_and_canonical_disjoint_ticket_validity(report):
    assert p279b.UNIVERSE_SIZE == math.comb(39, 5) == 575_757
    for budget in (3, 5):
        p279b.validate_disjoint_ticket_family(p279b.CANONICAL_TICKET_FAMILY, budget)
        tickets = p279b.CANONICAL_TICKET_FAMILY[:budget]
        assert len(set().union(*(set(ticket) for ticket in tickets))) == budget * 5
        baseline = report["baseline_contract"]["exact_diversified"][str(budget)]
        assert baseline["total_outcome_count"] == 575_757


def test_exact_diversified_baseline_numerators_and_probabilities(report):
    baselines = report["baseline_contract"]["exact_diversified"]
    assert baselines["3"]["winning_outcome_count"] == 187_563
    assert baselines["5"]["winning_outcome_count"] == 297_105
    assert baselines["3"]["probability"] == pytest.approx(187_563 / 575_757)
    assert baselines["5"]["probability"] == pytest.approx(297_105 / 575_757)
    assert (baselines["3"]["reduced_numerator"], baselines["3"]["reduced_denominator"]) == (62_521, 191_919)
    assert (baselines["5"]["reduced_numerator"], baselines["5"]["reduced_denominator"]) == (99_035, 191_919)


def test_symmetry_across_three_alternative_disjoint_families(report):
    symmetry = report["baseline_contract"]["symmetry_verification"]
    assert symmetry["status"] == "PASS"
    assert symmetry["alternative_family_count"] == 3
    counts = list(symmetry["family_winning_outcome_counts"].values())
    assert len(counts) == 4
    assert all(item == {"N3": 187_563, "N5": 297_105} for item in counts)
    assert "permutation" in symmetry["proof"]
    assert "invariant" in symmetry["proof"]


def test_p276_monte_carlo_reconciliation(report):
    reconciliation = report["baseline_contract"]["p276_monte_carlo_reconciliation"]
    assert reconciliation["status"] == "PASS"
    assert reconciliation["same_endpoint"] == p279b.ENDPOINT_ID
    assert reconciliation["same_equal_ticket_budgets"] == [3, 5]
    for budget in ("3", "5"):
        item = reconciliation["by_ticket_budget"][budget]
        assert item["p276_sample_count"] == 200_000
        assert item["exact_inside_derived_mc_interval"] is True
        assert item["status"] == "RECONCILED_EXACT_SUPERSEDES_MC_FOR_P279B_ONLY"
        lo, hi = item["derived_wilson_95_interval"]
        assert lo <= item["exact_probability"] <= hi
        assert abs(item["standardized_difference"]) < 1.0
        expected_rows = 2 if budget == "3" else 1
        assert len(item["p276_prize_aware_single_candidate_rows_verified"]) == expected_rows
        assert all(
            sorted(map(int, row["windows"])) == [50, 300, 750]
            for row in item["p276_prize_aware_single_candidate_rows_verified"]
        )


def test_p273_ordinary_random_baseline_reproduction(report):
    baselines = report["baseline_contract"]["ordinary_random_sensitivity"]
    assert baselines["3"]["probability"] == pytest.approx(0.304431435742626)
    assert baselines["5"]["probability"] == pytest.approx(0.453949563749733)
    assert all(item["committed_p273_reproduced"] for item in baselines.values())
    assert all(item["role"] == "SECONDARY_SENSITIVITY_ONLY" for item in baselines.values())


def _brute_probability_ordering(successes: int, trials: int, probability: float) -> float:
    probabilities = [
        math.comb(trials, value)
        * probability ** value
        * (1 - probability) ** (trials - value)
        for value in range(trials + 1)
    ]
    observed = probabilities[successes]
    return math.fsum(value for value in probabilities if value <= observed + observed * 1e-12)


@pytest.mark.parametrize(
    ("successes", "trials", "probability", "expected"),
    [
        (0, 5, 0.5, 0.0625),
        (2, 4, 0.5, 1.0),
        (1, 6, 0.2, None),
        (4, 7, 0.35, None),
    ],
)
def test_exact_two_sided_binomial_toy_case_correctness(
    successes, trials, probability, expected,
):
    actual = p279b.exact_two_sided_binomial_pvalue(successes, trials, probability)
    assert actual == pytest.approx(_brute_probability_ordering(successes, trials, probability), abs=1e-15)
    if expected is not None:
        assert actual == pytest.approx(expected, abs=1e-15)


def test_fixed_m6_alpha_and_d50_exclusion(report):
    contract = report["statistical_contract"]
    assert contract["family_size"] == 6
    assert contract["family_alpha"] == 0.05
    assert contract["bonferroni_alpha_per_test"] == pytest.approx(0.05 / 6)
    assert len(report["primary_test_results"]) == 6
    assert {item["block"] for item in report["primary_test_results"]} == {"P250", "P450"}
    assert all(item["included_in_m6_family"] for item in report["primary_test_results"])
    assert len(report["diagnostic_d50_results"]) == 3
    assert all(item["block"] == "D50" for item in report["diagnostic_d50_results"])
    assert all(not item["included_in_m6_family"] for item in report["diagnostic_d50_results"])
    assert all(item["bonferroni_adjusted_p_value"] is None for item in report["diagnostic_d50_results"])


def test_six_primary_pvalues_match_scipy_probability_ordering(report):
    expected = {
        ("acb_markov_midfreq_3bet", "P250"): 0.006832435202756915,
        ("acb_markov_midfreq_3bet", "P450"): 0.8801884602970758,
        ("daily539_f4cold_3bet", "P250"): 0.6857510138015165,
        ("daily539_f4cold_3bet", "P450"): 0.006568647882244292,
        ("daily539_f4cold_5bet", "P250"): 0.48646854680142104,
        ("daily539_f4cold_5bet", "P450"): 0.033720023535143334,
    }
    assert len(report["primary_test_results"]) == 6
    for item in report["primary_test_results"]:
        key = (item["strategy_id"], item["block"])
        assert item["raw_p_value"] == pytest.approx(expected[key], abs=2e-15)
        assert item["bonferroni_adjusted_p_value"] == pytest.approx(
            min(1.0, expected[key] * 6), abs=2e-14
        )


def test_all_three_decision_rule_branches():
    positive_pass = {"direction": "POSITIVE", "passes_bonferroni_threshold": True}
    positive_fail = {"direction": "POSITIVE", "passes_bonferroni_threshold": False}
    negative_pass = {"direction": "NEGATIVE", "passes_bonferroni_threshold": True}
    equal_pass = {"direction": "EQUAL", "passes_bonferroni_threshold": True}
    assert p279b.classify_candidate([positive_pass, positive_pass]) == p279b.DECISION_RETAIN
    assert p279b.classify_candidate([positive_pass, positive_fail]) == p279b.DECISION_INCONCLUSIVE
    assert p279b.classify_candidate([negative_pass, positive_pass]) == p279b.DECISION_FALSIFIED
    assert p279b.classify_candidate([positive_pass, equal_pass]) == p279b.DECISION_FALSIFIED


def test_primary_results_and_candidate_decisions(report):
    expected = {
        "acb_markov_midfreq_3bet": p279b.DECISION_INCONCLUSIVE,
        "daily539_f4cold_3bet": p279b.DECISION_FALSIFIED,
        "daily539_f4cold_5bet": p279b.DECISION_INCONCLUSIVE,
    }
    assert {item["strategy_id"]: item["decision"] for item in report["candidate_decisions"]} == expected
    assert report["project_summary"]["decision_counts"] == {
        p279b.DECISION_RETAIN: 0,
        p279b.DECISION_INCONCLUSIVE: 2,
        p279b.DECISION_FALSIFIED: 1,
    }
    assert report["project_summary"]["research_verdict"] == "ONE_FALSIFIED_TWO_INCONCLUSIVE_ZERO_RETAINED"


def test_no_candidate_promotion_or_future_confirmation_semantics(report):
    flags = report["safety_flags"]
    assert flags["prediction_success_claim"] is False
    assert flags["strategy_promoted"] is False
    assert flags["prospective_confirmation_complete"] is False
    assert flags["deployment_authorized"] is False
    assert flags["production_db_opened"] is False
    assert flags["production_db_queried"] is False
    assert flags["production_db_copied"] is False
    assert flags["production_db_written"] is False
    assert all(item["retrospective_research_only"] for item in report["candidate_decisions"])


def test_deterministic_json_and_markdown_regeneration_twice(report):
    regenerated_one = p279b.build_artifact()
    regenerated_two = p279b.build_artifact()
    assert p279b.serialize_json(regenerated_one) == p279b.serialize_json(regenerated_two)
    assert p279b.render_markdown(regenerated_one) == p279b.render_markdown(regenerated_two)
    assert p279b.serialize_json(report) == p279b.repository_path(p279b.DEFAULT_JSON_PATH).read_text(encoding="utf-8")
    assert p279b.render_markdown(report) == p279b.repository_path(p279b.DEFAULT_MD_PATH).read_text(encoding="utf-8")


def test_canonical_digest_recomputation_and_exclusions(report):
    assert report["canonical_payload_digest"] == p279b.canonical_digest(
        report, p279b._SELF_DIGEST_EXCLUDES
    )
    changed = copy.deepcopy(report)
    changed["generated_at"] = "2099-12-31T23:59:59Z"
    changed["canonical_payload_digest"] = "not-the-real-hash"
    assert p279b.canonical_digest(changed, p279b._SELF_DIGEST_EXCLUDES) == report["canonical_payload_digest"]


def test_json_markdown_consistency(report):
    markdown = p279b.render_markdown(report)
    assert report["canonical_payload_digest"] in markdown
    assert report["source_commit"] in markdown
    for item in report["candidate_decisions"]:
        assert item["strategy_id"] in markdown
        assert item["decision"] in markdown
    for item in report["primary_test_results"]:
        assert p279b._format_probability(item["raw_p_value"]) in markdown
        assert p279b._format_probability(item["bonferroni_adjusted_p_value"]) in markdown
    parsed = json.loads(p279b.serialize_json(report))
    assert parsed == report


def test_repository_relative_path_safety_and_no_absolute_payload_paths(report):
    with pytest.raises(ValueError):
        p279b.repository_path("/tmp/p279b.json")
    with pytest.raises(ValueError):
        p279b.repository_path("../p279b.json")

    def strings(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, str):
            yield value

    assert not any(value.startswith("/") for value in strings(report))


def test_forbidden_interface_scan():
    source_path = Path(p279b.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint({
        "sqlite3", "sqlalchemy", "requests", "urllib", "socket", "subprocess",
    })
    for forbidden in (
        "sqlite3.connect", "create_engine(", "requests.", "urlopen(",
        "subprocess.", "controlled_apply", "replay_strategy_registry",
    ):
        assert forbidden not in source
