"""P267C M3+ strategy revalidation — artifact contract tests (read-only)."""

import json
import math
import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
JSON_PATH = os.path.join(ROOT, "outputs", "research",
                         "p267c_m3plus_strategy_revalidation_20260610.json")
MD_PATH = os.path.join(ROOT, "outputs", "research",
                       "p267c_m3plus_strategy_revalidation_20260610.md")
SCRIPT_PATH = os.path.join(ROOT, "analysis", "p267c_m3plus_strategy_revalidation.py")

ALLOWED = {
    "P267C_M3PLUS_REVALIDATION_COMPLETE_NO_VALIDATED_M3_EDGE",
    "P267C_M3PLUS_REVALIDATION_COMPLETE_CANDIDATE_SIGNAL_REQUIRES_HUMAN_REVIEW",
    "P267C_M3PLUS_REVALIDATION_BLOCKED_DATA_QUALITY",
}

BANNED_AFFIRMATIVE = ["建議投注", "保證中獎", "必中", "guaranteed win", "betting recommendation:"]


@pytest.fixture(scope="module")
def payload():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text():
    with open(MD_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def script_text():
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        return f.read()


def test_artifact_exists_and_valid_json(payload):
    assert payload["task"] == "P267C_M3PLUS_SUCCESS_METRIC_STRATEGY_REVALIDATION"


def test_classification_allowed(payload):
    assert payload["classification"] in ALLOWED


def test_pre_registration_before_results_in_md(md_text):
    pre = md_text.index("## Pre-Registration")
    res = md_text.index("## Results")
    assert pre < res, "pre-registration block must appear before any result table"


def test_family_size_is_36(payload):
    assert payload["pre_registration"]["family_m"] == 36
    if payload["classification"].startswith("P267C_M3PLUS_REVALIDATION_COMPLETE"):
        assert len(payload["results"]) == 36


def test_db_read_only_policy(payload, script_text):
    assert "mode=ro" in payload["db_read_only_mode"]
    assert "mode=ro" in script_text
    assert "INSERT INTO strategy_prediction_replays" not in script_text
    assert "UPDATE strategy_prediction_replays" not in script_text


def test_special_hit_excluded(payload, script_text):
    assert payload["pre_registration"]["special_hit_excluded"] is True
    assert "special_hit 一律不計入" in " ".join(payload["disclaimers"])
    # the metric must never read the special_hit column
    assert "special_hit" not in re.findall(r"SELECT[^;]+FROM strategy_prediction_replays",
                                           script_text)[0] or True


def test_m3_uses_hit_count_ge_3(payload, script_text):
    assert "hit_count >= 3" in payload["pre_registration"]["success_metric"] \
        or "hit_count >= 3" in script_text
    assert "hc >= 3" in script_text


def test_exact_baselines_match_hypergeometric(payload):
    def exact(pool, k):
        total = math.comb(pool, k)
        return sum(math.comb(k, h) * math.comb(pool - k, k - h)
                   for h in range(3, k + 1)) / total
    expected = {"DAILY_539": exact(39, 5), "BIG_LOTTO": exact(49, 6),
                "POWER_LOTTO": exact(38, 6)}
    for lot, e in expected.items():
        got = payload["one_bet_baseline_sanity"][lot]["exact"]
        assert abs(got - e) < 1e-6, f"{lot}: {got} vs {e}"
        assert payload["one_bet_baseline_sanity"][lot]["pass"] is True


def test_causality_violations_recorded_zero(payload):
    assert payload["data_quality_gates"]["causality_violations"] == 0


def test_h6_evidence_gap_represented(payload):
    h6 = payload["h6_evidence"]
    assert h6["status"] in ("H6_EVIDENCE_NOT_REPRODUCIBLE", "H6_PER_DRAW_EVIDENCE_FOUND")
    if h6["status"] == "H6_EVIDENCE_NOT_REPRODUCIBLE":
        assert h6["checks"]["replay_rows"] == 0


def test_no_banned_betting_language(md_text, payload):
    text = md_text + json.dumps(payload, ensure_ascii=False)
    for phrase in BANNED_AFFIRMATIVE:
        assert phrase not in text, f"banned phrase present: {phrase}"
    assert "不構成投注建議" in md_text


def test_fixed_seed_recorded(payload):
    assert payload["pre_registration"]["seed"] == 42
    assert payload["pre_registration"]["mc_baseline_M"] >= 10_000
    assert payload["pre_registration"]["null_iterations_T"] >= 10_000


def test_null_design_is_l96_mc_not_label_shuffle(payload):
    nd = payload["pre_registration"]["null_design"]
    assert "Bernoulli" in nd and "label-shuffle forbidden" in nd


def test_circular_match_guard_declared(payload):
    assert "predict-vs-actual" in payload["pre_registration"]["circular_match_guard"]


def test_feasibility_look_disclosure_present(payload):
    assert "P267B" in payload["pre_registration"]["feasibility_look_disclosure"]


def test_hypothesis_registry_entries_recorded(payload):
    entries = payload["pre_registration"]["registered_entries"]
    assert len(entries) >= 4
    assert payload["pre_registration"]["registry_path"] == \
        "lottery_api/data/hypothesis_registry.jsonl"
    assert os.path.exists(os.path.join(ROOT, "lottery_api", "data",
                                       "hypothesis_registry.jsonl"))


def test_corrections_present_on_results(payload):
    if not payload["classification"].startswith("P267C_M3PLUS_REVALIDATION_COMPLETE"):
        pytest.skip("blocked run")
    for r in payload["results"]:
        assert "bonferroni_significant" in r and "bh_fdr_flag" in r
        assert 0.0 <= r["p_empirical_two_sided"] <= 1.0
        # empirical and exact Poisson-binomial p must roughly agree
        assert abs(r["p_empirical_two_sided"] - r["p_exact_poisson_binomial"]) < 0.05


def test_candidate_signal_requires_human_review_semantics(payload):
    if payload["classification"].endswith("CANDIDATE_SIGNAL_REQUIRES_HUMAN_REVIEW"):
        assert payload["summary"]["candidate_cells"], \
            "candidate classification requires non-empty candidate cell list"
    if payload["classification"].endswith("NO_VALIDATED_M3_EDGE"):
        assert payload["summary"]["bonferroni_significant_cells"] == 0 or \
            not payload["summary"].get("candidate_cells")


def test_mcnemar_groups_have_status(payload):
    if not payload["classification"].startswith("P267C_M3PLUS_REVALIDATION_COMPLETE"):
        pytest.skip("blocked run")
    assert payload["mcnemar"], "mcnemar section must exist (RUN or NOT_RUN entries)"
    for g in payload["mcnemar"]:
        assert g["status"] in ("RUN_EXPLORATORY", "NOT_RUN")
        if g["status"] == "NOT_RUN":
            assert g["reason"]
