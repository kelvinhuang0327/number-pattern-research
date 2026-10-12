"""Focused tests for P273A exact distinct-ticket prize-aware inference."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import subprocess
from pathlib import Path

import pytest

import analysis.p273a_prize_aware_inferential_validation as P

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_FILE = REPO_ROOT / "analysis/p273a_prize_aware_inferential_validation.py"
PRIMARY_ARTIFACT = REPO_ROOT / P.PRIMARY_OBSERVED_COUNTS_PATH
IDENTITY_ARTIFACT = REPO_ROOT / P.IDENTITY_ARTIFACT_PATH
REFERENCE_ARTIFACT = REPO_ROOT / P.REFERENCE_OBSERVED_COUNTS_PATH


@pytest.fixture(scope="session")
def report():
    return P.build_report()


def _raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _window_record(lottery, strategy, window, support, observed, bet_dist=None):
    bet_dist = {"1": support} if bet_dist is None else dict(bet_dist)
    return {
        "lottery_type": lottery,
        "strategy_id": strategy,
        "window": window,
        "requested_window": window,
        "support_draws": support,
        "observed_successes": observed,
        "observed_success_rate": observed / support if support else None,
        "bet_count_distribution": bet_dist,
        "bet_count_constant": len(bet_dist) == 1 if bet_dist else None,
        "window_label": P.PRIMARY_WINDOW_LABELS[window],
        "distinct_draws_in_window": window,
        "latest_target_draw": str(900000 + window),
        "earliest_target_draw": str(900001),
        "excluded_rows": 0,
        "excluded_missing_special_rows": 0,
        "exclusion_by_reason": {},
    }


def _identity_draws(counts):
    return [
        {"target_draw": str(900001 + index), "distinct_ticket_count": count}
        for index, count in enumerate(counts)
    ]


def _win(lottery, window, support, observed, counts=None):
    counts = [1] * support if counts is None else list(counts)
    rec = _window_record(lottery, "synthetic", window, support, observed)
    return P.evaluate_window(lottery, "synthetic", rec, _identity_draws(counts))


def _group(lottery, short_obs, mid_obs, long_obs, short_support=50):
    windows = {
        "SHORT": _win(lottery, 50, short_support, short_obs),
        "MID": _win(lottery, 300, 300, mid_obs),
        "LONG": _win(lottery, 750, 750, long_obs),
    }
    stability = P.evaluate_stability(windows)
    for label, window in windows.items():
        window["window_decision"] = P.finalize_window_decision(
            label, window, stability
        )
    return windows, stability, P.overall_group_decision(windows, stability)


def _synthetic_primary():
    cells = []
    for lottery in P.LOTTERIES:
        for strategy in P.FROZEN_STRATEGY_CELLS[lottery]:
            windows = [
                _window_record(lottery, strategy, window, window, 0)
                for window in P.PRIMARY_WINDOWS
            ]
            cells.append({
                "lottery_type": lottery,
                "strategy_id": strategy,
                "distinct_draws_available": 750,
                "windows": windows,
            })
    artifact = {
        "meta": {"task_id": "SYNTH"},
        "window_policy": {"primary_windows": list(P.PRIMARY_WINDOWS)},
        "cells": cells,
    }
    artifact["canonical_payload_digest"] = P.compute_observed_payload_digest(
        artifact
    )
    return artifact


def _write_json(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return str(path)


# Frozen scope and source identity


def test_primary_windows_and_reference_containment_locked():
    assert P.PRIMARY_WINDOWS == (50, 300, 750)
    assert P.PRIMARY_WINDOW_LABELS == {50: "SHORT", 300: "MID", 750: "LONG"}
    assert P.REFERENCE_ONLY_WINDOWS == (100, 500, 1500)
    assert P.FORBIDDEN_PRIMARY_WINDOWS == frozenset({100, 500, 1500})
    assert "stability_pass_or_fail" in P.REFERENCE_ONLY_PROHIBITED_USES


def test_frozen_36_groups_and_108_hypotheses():
    assert {k: len(v) for k, v in P.FROZEN_STRATEGY_CELLS.items()} == {
        "DAILY_539": 15,
        "BIG_LOTTO": 11,
        "POWER_LOTTO": 10,
    }
    assert P.EXPECTED_FROZEN_CELL_COUNT == 36
    assert P.CORRECTION_FAMILY_M == 108


@pytest.mark.parametrize(
    "path,canonical,raw",
    [
        (PRIMARY_ARTIFACT, P.PRIMARY_OBSERVED_COUNTS_DIGEST, P.PRIMARY_OBSERVED_COUNTS_RAW_SHA),
        (IDENTITY_ARTIFACT, P.IDENTITY_ARTIFACT_DIGEST, P.IDENTITY_ARTIFACT_RAW_SHA),
        (REFERENCE_ARTIFACT, P.REFERENCE_OBSERVED_COUNTS_DIGEST, P.REFERENCE_OBSERVED_COUNTS_RAW_SHA),
    ],
)
def test_three_artifact_digests(path, canonical, raw):
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert _raw_sha(path) == raw
    assert artifact["canonical_payload_digest"] == canonical
    assert P.compute_observed_payload_digest(artifact) == canonical
    assert P.compute_observed_payload_digest(artifact) == canonical


@pytest.mark.parametrize(
    "path",
    [
        P.PRIMARY_OBSERVED_COUNTS_PATH,
        P.IDENTITY_ARTIFACT_PATH,
        P.REFERENCE_OBSERVED_COUNTS_PATH,
    ],
)
def test_source_artifact_bytes_match_origin_main(path):
    local = (REPO_ROOT / path).read_bytes()
    upstream = subprocess.run(
        ["git", "show", f"origin/main:{path}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    assert local == upstream


def test_report_records_required_base_and_identity_commits(report):
    assert report["base_origin_main"] == P.BASE_ORIGIN_MAIN
    frozen = report["frozen_setup"]
    assert frozen["identity_export_commit"] == P.IDENTITY_EXPORT_COMMIT
    assert frozen["identity_merge_commit"] == P.IDENTITY_MERGE_COMMIT


# Identity contract


def test_identity_loader_validates_all_108_windows():
    artifact = P.load_identity_artifact()
    assert len(artifact["cells"]) == 36
    assert sum(len(cell["windows"]) for cell in artifact["cells"]) == 108
    assert artifact["summary"]["artifact_alignment_windows_checked"] == 108


def test_identity_zero_conflicts_and_duplicates():
    summary = json.loads(IDENTITY_ARTIFACT.read_text(encoding="utf-8"))["summary"]
    assert summary["same_bet_index_content_conflict_count"] == 0
    assert summary["same_bet_index_duplicate_rows_collapsed"] == 0
    assert summary["duplicate_content_draw_count_long_window_records"] == 0
    assert summary["total_duplicate_ticket_content_count_long_window_records"] == 0
    assert summary["duplicate_content_groups"] == []


def test_identity_expected_distinct_ticket_distributions():
    summary = json.loads(IDENTITY_ARTIFACT.read_text(encoding="utf-8"))["summary"]
    assert summary["distinct_ticket_count_distribution_by_window"] == {
        "50": {"1": 1349, "3": 150, "4": 50, "5": 50},
        "300": {"1": 8099, "3": 900, "4": 300, "5": 300},
        "750": {"1": 20249, "3": 2250, "4": 750, "5": 750},
    }


def test_identity_distinguishes_eligible_indices_from_distinct_tickets():
    artifact = json.loads(IDENTITY_ARTIFACT.read_text(encoding="utf-8"))
    for cell in artifact["cells"]:
        for draw in cell["supported_draws"]:
            assert draw["eligible_bet_index_count"] >= draw["distinct_ticket_count"]
            assert draw["duplicate_ticket_count"] == (
                draw["eligible_bet_index_count"] - draw["distinct_ticket_count"]
            )
    assert {
        draw["distinct_ticket_count"]
        for cell in artifact["cells"]
        for draw in cell["supported_draws"]
    } == {1, 3, 4, 5}


def test_power_missing_second_zone_remains_excluded():
    artifact = json.loads(IDENTITY_ARTIFACT.read_text(encoding="utf-8"))
    assert artifact["summary"]["power_excluded_missing_special_rows_by_window"] == {
        "50": 901,
        "300": 5401,
        "750": 13501,
    }
    assert all(
        "predicted_second_zone" in group["canonical_ticket_content"]
        for cell in artifact["cells"]
        if cell["lottery_type"] == "POWER_LOTTO"
        for draw in cell["supported_draws"]
        for group in draw["canonical_ticket_groups"]
    )


def test_identity_loader_rejects_duplicate_evidence(tmp_path):
    artifact = json.loads(IDENTITY_ARTIFACT.read_text(encoding="utf-8"))
    artifact["summary"]["same_bet_index_content_conflict_count"] = 1
    artifact["canonical_payload_digest"] = P.compute_observed_payload_digest(
        artifact
    )
    path = _write_json(tmp_path, "bad-identity.json", artifact)
    with pytest.raises(P.IdentityArtifactError):
        P.load_identity_artifact(path, expected_digest=None, expected_raw_sha=None)


# Exact governed universes and null


def test_exact_ticket_universe_values():
    assert P.ticket_universe("DAILY_539") == (575757, 65621)
    assert P.ticket_universe("BIG_LOTTO") == (13983816, 432824)
    assert P.ticket_universe("POWER_LOTTO") == (22085448, 2602320)


def test_daily539_formula():
    total = math.comb(39, 5)
    winning = sum(math.comb(5, k) * math.comb(34, 5 - k) for k in range(2, 6))
    assert P.ticket_universe("DAILY_539") == (total, winning)


def test_big_lotto_joint_special_formula():
    total = math.comb(49, 6)
    winning = (
        sum(math.comb(6, k) * math.comb(43, 6 - k) for k in range(3, 7))
        + math.comb(6, 2) * math.comb(42, 3)
    )
    baseline = P.big_lotto_ticket_baseline()
    assert P.ticket_universe("BIG_LOTTO") == (total, winning)
    assert baseline["p_special_given_hit2"] == pytest.approx(4 / 43)
    assert baseline["independence_assumed"] is False


def test_power_lotto_joint_second_zone_formula():
    total = math.comb(38, 6) * 8
    winning = (
        8 * sum(math.comb(6, k) * math.comb(32, 6 - k) for k in range(3, 7))
        + math.comb(6, 1) * math.comb(32, 5)
        + math.comb(6, 2) * math.comb(32, 4)
    )
    baseline = P.power_lotto_ticket_baseline()
    assert P.ticket_universe("POWER_LOTTO") == (total, winning)
    assert baseline["p_second"] == pytest.approx(1 / 8)
    assert baseline["independence_assumed"] is True


@pytest.mark.parametrize("total,winning,n", [(7, 2, 1), (7, 2, 3), (8, 3, 5)])
def test_exact_null_matches_exhaustive_toy_enumeration(total, winning, n):
    identities = range(total)
    winning_ids = set(range(winning))
    combinations = list(itertools.combinations(identities, n))
    brute = sum(bool(set(combo) & winning_ids) for combo in combinations) / len(
        combinations
    )
    assert P.exact_distinct_draw_baseline(total, winning, n) == pytest.approx(
        brute, abs=1e-15
    )


@pytest.mark.parametrize("lottery", P.LOTTERIES)
def test_n1_exactly_matches_w_over_t(lottery):
    total, winning = P.ticket_universe(lottery)
    assert P.exact_distinct_draw_baseline(total, winning, 1) == winning / total


@pytest.mark.parametrize("lottery", P.LOTTERIES)
def test_exact_null_monotone_and_dominates_independent(lottery):
    total, winning = P.ticket_universe(lottery)
    ticket_p = winning / total
    exact = [P.exact_distinct_draw_baseline(total, winning, n) for n in (1, 3, 4, 5)]
    independent = [P.independent_draw_baseline(ticket_p, n) for n in (1, 3, 4, 5)]
    assert exact == sorted(exact)
    assert all(a >= b for a, b in zip(exact, independent))
    assert all(a > b for a, b in zip(exact[1:], independent[1:]))


def test_report_records_every_actual_n_and_differences(report):
    assert report["baseline_contract"]["actual_distinct_ticket_counts_used"] == {
        "DAILY_539": [1, 3, 5],
        "BIG_LOTTO": [1, 3, 4],
        "POWER_LOTTO": [1],
    }
    used_across_family = set()
    for diagnostics in report["exact_null_probability_diagnostics"].values():
        used_across_family.update(
            item["distinct_ticket_count"] for item in diagnostics
        )
        assert all(item["absolute_difference"] >= 0 for item in diagnostics)
    assert used_across_family == {1, 3, 4, 5}


# Statistical engine


def test_constant_q_uses_exact_binomial():
    probs = P.per_draw_probabilities("DAILY_539", [1] * 40)
    value, method = P.upper_tail_pvalue(12, probs)
    assert method == "exact_binomial_upper"
    assert value == pytest.approx(
        P.binomial_upper_pvalue(12, 40, probs[0]), abs=1e-12
    )


def test_variable_q_uses_exact_poisson_binomial():
    probs = P.per_draw_probabilities("DAILY_539", [1] * 20 + [3] * 20)
    value, method = P.upper_tail_pvalue(12, probs)
    assert method == "exact_poisson_binomial_upper"
    assert value == pytest.approx(
        sum(P.poisson_binomial_pmf(probs)[12:]), abs=1e-12
    )


def test_expected_successes_is_sum_of_exact_per_draw_q():
    counts = [1] * 20 + [3] * 20
    window = _win("DAILY_539", 50, 40, 10, counts)
    expected = math.fsum(P.per_draw_probabilities("DAILY_539", counts))
    assert window["expected_successes"] == pytest.approx(expected, abs=1e-12)
    assert window["p_value_method_upper"] == "exact_poisson_binomial_upper"


def test_confidence_interval_methods():
    wilson = P.wilson_interval(20, 100)
    exact = P.clopper_pearson_interval(20, 100)
    assert wilson[0] < 0.2 < wilson[1]
    assert exact[0] < 0.2 < exact[1]
    assert exact[0] <= wilson[0] and exact[1] >= wilson[1]
    assert P.clopper_pearson_interval(0, 50)[0] == 0.0
    assert P.clopper_pearson_interval(50, 50)[1] == 1.0


def test_minimum_support_rules():
    assert P.MIN_SUPPORT_DRAWS == 30
    assert P.MIN_EXPECTED_SUCCESSES == 5.0
    assert _win("DAILY_539", 50, 20, 5)["evaluable"] is False
    assert _win("BIG_LOTTO", 50, 50, 2)["evaluable"] is False


def test_bonferroni_m108_and_bh_descriptive_only(report):
    assert P.bonferroni_pvalue(0.0001) == pytest.approx(0.0108)
    assert report["correction_family"]["family_m"] == 108
    assert "descriptive only" in report["statistical_methods"]["fdr"]
    assert all(
        "bh_fdr_descriptive_reject" in window
        for group in report["inference"]["groups"]
        for window in group["windows"]
    )


def test_finalize_positive_but_raw_nonsignificant_is_null():
    ticket_p = P.analytic_ticket_baseline("DAILY_539")["ticket_baseline"]
    window = _win("DAILY_539", 300, 300, round(300 * ticket_p) + 1)
    assert window["absolute_excess"] > 0
    assert window["raw_p_value_one_sided_upper"] > 0.05
    assert P.finalize_window_decision(
        "MID", window, {"status": "STABILITY_FAIL"}
    ) == "PRIZE_AWARE_NULL"


# Stability and decisions


def test_stability_rule_has_all_ten_frozen_criteria():
    assert len(P.STABILITY_RULE["criteria"]) == 10
    assert P.STABILITY_RULE["family_m_fixed"] == 108


def test_stability_pass_and_mid_long_promotion():
    windows, stability, overall = _group("DAILY_539", 8, 90, 200)
    assert stability["status"] == "STABILITY_PASS"
    assert all(stability["criteria"].values())
    assert windows["MID"]["window_decision"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    assert windows["LONG"]["window_decision"] == "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    assert overall == "GO_CANDIDATE_RESEARCH_ONLY"


def test_short_guardrail_cannot_promote_alone():
    windows, stability, overall = _group("DAILY_539", 30, 20, 86)
    assert windows["SHORT"]["significant_positive"] is True
    assert stability["criteria"]["c6_short_cannot_trigger_promotion"] is True
    assert stability["status"] == "STABILITY_FAIL"
    assert windows["SHORT"]["window_decision"] != "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    assert overall != "GO_CANDIDATE_RESEARCH_ONLY"


def test_insufficient_window_fails_c1_and_c7():
    _, stability, overall = _group("DAILY_539", 5, 90, 200, short_support=20)
    assert stability["criteria"]["c1_all_three_evaluable"] is False
    assert stability["criteria"]["c7_no_negative_or_insufficient_window"] is False
    assert overall == "INSUFFICIENT_SUPPORT"


def test_nonpositive_mid_and_long_fail_c2_c3():
    windows, stability, _ = _group("DAILY_539", 8, 0, 0)
    assert windows["MID"]["absolute_excess"] < 0
    assert windows["LONG"]["absolute_excess"] < 0
    assert stability["criteria"]["c2_mid_excess_strictly_positive"] is False
    assert stability["criteria"]["c3_long_excess_strictly_positive"] is False


def test_negative_short_fails_c4():
    _, stability, _ = _group("DAILY_539", 0, 90, 200)
    assert stability["criteria"]["c4_short_excess_nonnegative"] is False


def test_no_corrected_mid_or_long_fails_c5():
    ticket_p = P.analytic_ticket_baseline("DAILY_539")["ticket_baseline"]
    _, stability, _ = _group(
        "DAILY_539",
        round(50 * ticket_p) + 1,
        round(300 * ticket_p) + 1,
        round(750 * ticket_p) + 1,
    )
    assert stability["criteria"]["c5_mid_or_long_bonferroni_sig"] is False


def test_significantly_negative_window_fails_c7():
    windows, stability, _ = _group("DAILY_539", 8, 90, 0)
    assert windows["LONG"]["significant_negative"] is True
    assert stability["criteria"]["c7_no_negative_or_insufficient_window"] is False


def test_structural_stability_conditions_c8_c9_c10_true():
    _, stability, _ = _group("DAILY_539", 8, 90, 200)
    assert stability["criteria"]["c8_no_post_outcome_family_or_threshold_change"]
    assert stability["criteria"]["c9_nested_not_independent_replications"]
    assert stability["criteria"]["c10_passing_is_research_go_candidate_only"]


# Loaders, real result, and reconciliation


def test_primary_loader_rejects_forbidden_window(tmp_path):
    artifact = _synthetic_primary()
    artifact["cells"][0]["windows"][0]["window"] = 100
    artifact["canonical_payload_digest"] = P.compute_observed_payload_digest(
        artifact
    )
    path = _write_json(tmp_path, "bad-primary.json", artifact)
    with pytest.raises(P.ObservedCountsError):
        P.load_primary_observed_counts(path, expected_digest=None)


def test_real_report_has_complete_108_window_trace(report):
    assert report["inference"]["n_groups"] == 36
    assert report["inference"]["n_windows"] == 108
    assert sum(
        len(group["windows"]) for group in report["inference"]["groups"]
    ) == 108
    for group in report["inference"]["groups"]:
        for window in group["windows"]:
            assert len(window["per_draw_distinct_ticket_trace"]) == window[
                "support_draws"
            ]


def test_real_window_counts_match_immutable_primary(report):
    source = json.loads(PRIMARY_ARTIFACT.read_text(encoding="utf-8"))
    expected = {
        (cell["lottery_type"], cell["strategy_id"], window["window"]): (
            window["support_draws"],
            window["observed_successes"],
        )
        for cell in source["cells"]
        for window in cell["windows"]
    }
    actual = {
        (group["lottery_type"], group["strategy_id"], window["window"]): (
            window["support_draws"],
            window["observed_successes"],
        )
        for group in report["inference"]["groups"]
        for window in group["windows"]
    }
    assert actual == expected


def test_preliminary_independent_null_candidates_audited(report):
    candidates = report["preliminary_result_reconciliation"]["candidates"]
    assert {
        (candidate["lottery_type"], candidate["strategy_id"])
        for candidate in candidates
    } == {
        ("DAILY_539", "acb_markov_midfreq_3bet"),
        ("DAILY_539", "daily539_f4cold_3bet"),
        ("DAILY_539", "daily539_f4cold_5bet"),
    }
    assert all(len(candidate["windows"]) == 3 for candidate in candidates)
    assert all(
        set(window["distinct_ticket_count_distribution"]) <= {"1", "3", "4", "5"}
        for candidate in candidates
        for window in candidate["windows"]
    )


def test_corrected_classification_transitions_survive(report):
    candidates = report["preliminary_result_reconciliation"]["candidates"]
    assert all(
        candidate["classification_transition"]
        == "GO_CANDIDATE_RESEARCH_ONLY -> GO_CANDIDATE_RESEARCH_ONLY"
        for candidate in candidates
    )
    assert all(
        candidate["exact_distinct_stability"] == "STABILITY_PASS"
        for candidate in candidates
    )


def test_final_real_classification_and_evidence_boundary(report):
    assert report["overall_project_classification"] == (
        "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    )
    assert report["final_classification"] == (
        "P273A_DISTINCT_TICKET_INFERENCE_COMPLETE_EDGE_SURVIVES_RESEARCH_ONLY"
    )
    assert report["prediction_success_claim"] is False
    assert report["governance"]["production_apply"] is False
    assert report["governance"]["production_apply_readiness"] == "NOT_READY_FOR_APPLY"


def test_real_go_groups_and_decision_counts(report):
    assert report["summary"]["go_candidate_research_only_groups"] == [
        {"lottery_type": "DAILY_539", "strategy_id": "acb_markov_midfreq_3bet"},
        {"lottery_type": "DAILY_539", "strategy_id": "daily539_f4cold_3bet"},
        {"lottery_type": "DAILY_539", "strategy_id": "daily539_f4cold_5bet"},
    ]
    assert report["summary"]["stability_counts"] == {
        "STABILITY_PASS": 3,
        "STABILITY_FAIL": 33,
    }
    assert report["summary"]["window_decision_counts"][
        "PRIZE_AWARE_EDGE_CORRECTION_SURVIVING"
    ] == 4


# Determinism, rendering, and safety


def test_deterministic_report_regeneration():
    first = P.build_report()
    second = P.build_report()
    assert first == second
    assert P.render_markdown(first) == P.render_markdown(second)
    assert first["canonical_payload_digest"] == P.compute_report_digest(first)


def test_json_markdown_consistency(report):
    markdown = P.render_markdown(report)
    assert report["overall_project_classification"] in markdown
    assert report["final_classification"] in markdown
    assert report["canonical_payload_digest"] in markdown
    assert "q_N = 1 - C(T-W,N) / C(T,N)" in markdown
    assert "Provisionally promoted groups audited: **3**" in markdown


def test_write_artifacts_is_byte_deterministic(tmp_path):
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    first = P.write_artifacts(str(json_path), str(md_path))
    first_bytes = (json_path.read_bytes(), md_path.read_bytes())
    second = P.write_artifacts(str(json_path), str(md_path))
    assert first == second
    assert first_bytes == (json_path.read_bytes(), md_path.read_bytes())
    assert json.loads(json_path.read_text(encoding="utf-8")) == first


def test_inference_does_not_modify_source_artifacts():
    paths = (PRIMARY_ARTIFACT, IDENTITY_ARTIFACT, REFERENCE_ARTIFACT)
    before = [_raw_sha(path) for path in paths]
    P.build_report()
    assert [_raw_sha(path) for path in paths] == before


def test_governance_flags_are_safe(report):
    governance = report["governance"]
    for key in (
        "production_db_opened",
        "production_db_queried",
        "production_db_written",
        "observed_counts_artifacts_modified",
        "identity_artifact_modified",
        "registry_mutated",
        "production_apply",
        "controlled_apply_or_migration_or_deploy",
        "service_or_process_control",
        "strategy_reselection",
        "prospective_activation",
        "feature_mining_started",
        "p273b_started",
    ):
        assert governance[key] is False


def test_forbidden_interface_static_scan():
    source = MODULE_FILE.read_text(encoding="utf-8")
    for banned in (
        "import sqlite3",
        "import subprocess",
        "import socket",
        "import urllib",
        "import requests",
        "os.system(",
        "eval(",
        "exec(",
        ".connect(",
        "subprocess.",
        "urlopen",
    ):
        assert banned not in source


def test_independent_formula_is_diagnostic_only():
    source = MODULE_FILE.read_text(encoding="utf-8")
    assert source.count("1.0 - (1.0 - ticket_p) ** n_tickets") == 1
    assert "independent_approximation_rejected_for_final_inference" in source
    assert "monte_carlo_baseline_validation" not in source
    assert "import random" not in source


def test_report_required_artifact_statements(report):
    joined = " ".join(report["disclaimers"])
    for phrase in (
        "Retrospective research only",
        "exact distinct-ticket without-replacement null",
        "independent-with-replacement approximation is rejected",
        "production DB was not opened",
        "BH-FDR is descriptive only",
        "SHORT-50 is a recent-direction guardrail",
        "No strategy reselection",
        "No prospective activation",
        "No production apply",
        "P273B",
    ):
        assert phrase in joined
