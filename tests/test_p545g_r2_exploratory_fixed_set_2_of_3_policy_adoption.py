"""Focused no-database tests for P545G R2 exploratory policy adoption."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from analysis import p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption as calibration


REPO_ROOT = Path(calibration.__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def payload():
    return calibration.build_evaluation(REPO_ROOT)


def test_strict_json_rejects_duplicate_and_nonfinite_values():
    with pytest.raises(calibration.CalibrationError, match="duplicate JSON key"):
        calibration.strict_json_bytes(b'{"a":1,"a":2}')
    with pytest.raises(calibration.CalibrationError, match="non-finite"):
        calibration.strict_json_bytes(b'{"a":NaN}')


def test_pinned_input_identities(payload):
    identities = {item["role"]: item for item in payload["input_identities"]}
    registry = identities["SOLE_ROW_LEVEL_EVIDENCE"]
    p545b = identities["EXPECTED_RECONCILIATION_EVIDENCE_ONLY"]
    assert registry["byte_size"] == 52_393_107
    assert registry["sha256"] == calibration.REGISTRY_SHA256
    assert registry["semantic_projection_digest"] == calibration.REGISTRY_SEMANTIC_DIGEST
    assert p545b["byte_size"] == 37_431_814
    assert p545b["sha256"] == calibration.P545B_SHA256
    assert {item["source_commit"] for item in identities.values()} == {calibration.BASE_COMMIT}


def test_exact_fixed_set_algorithm_identities():
    single = ((1, 2, 3, 4, 5),)
    assert calibration.exact_fixed_probability(single)[0] == 65_621
    assert calibration.exact_fixed_probability((single[0], single[0]))[0] == 65_621
    disjoint = tuple(tuple(range(start, start + 5)) for start in (1, 6, 11, 16, 21))
    assert calibration.exact_fixed_probability(disjoint)[0] == 297_105
    assert calibration.per_number_dp_favorable(disjoint) == 297_105


def test_candidate_draw_scope_and_scoring_reconciliation(payload):
    assert payload["candidate_scope"] == list(calibration.CANDIDATES)
    draws = payload["candidate_draws"]
    assert len(draws) == 2_250
    for cell_id in calibration.CANDIDATES:
        selected = [item for item in draws if item["cell_id"] == cell_id]
        assert len(selected) == 750
        assert sum("SHORT" in item["window_memberships"] for item in selected) == 50
        assert sum("MID" in item["window_memberships"] for item in selected) == 300
        assert sum("LONG" in item["window_memberships"] for item in selected) == 750
        assert all(item["duplicate_collapse_count"] == 0 for item in selected)
        assert all(item["excluded_attempt_count"] == 0 for item in selected)


def test_exact_nine_window_results(payload):
    windows = {
        (item["cell_id"], item["window_size"]): item
        for item in payload["window_calibrations"]
    }
    assert len(windows) == 9
    expected = {
        ("DAILY_539:daily539_f4cold_5bet", 50): (35, "0.006358612173812848373113204317", True),
        ("DAILY_539:daily539_f4cold_5bet", 300): (170, "0.044614780019457699148198815648", True),
        ("DAILY_539:daily539_f4cold_5bet", 750): (425, "0.003042232920669618446024340700", True),
        ("DAILY_539:daily539_f4cold_3bet", 50): (23, "0.032821272974945158794154987574", True),
        ("DAILY_539:daily539_f4cold_3bet", 300): (101, "0.364129621830438705595848114322", False),
        ("DAILY_539:daily539_f4cold_3bet", 750): (275, "0.009845382595326627400054747186", True),
        ("DAILY_539:acb_markov_midfreq_3bet", 50): (18, "0.303586885909572890047551152732", False),
        ("DAILY_539:acb_markov_midfreq_3bet", 300): (120, "0.001387404030053310520923596022", True),
        ("DAILY_539:acb_markov_midfreq_3bet", 750): (268, "0.009991285833279449231165609443", True),
    }
    for key, (observed, raw_p, exploratory_pass) in expected.items():
        item = windows[key]
        assert item["observed_successes"] == observed
        assert item["calibrated_poisson_binomial"]["upper_tail_decimal_30"] == raw_p
        assert item["exploratory_policy_window_pass"] is exploratory_pass
        assert item["original_confirmatory_window_survives"] is False


def test_owner_directed_policy_retains_three_but_confirmatory_retains_none(payload):
    assert payload["policy"]["policy_id"] == "EXPLORATORY_FIXED_SET_NULL_2_OF_3.v1"
    assert payload["policy"]["pre_registered"] is False
    assert payload["decision"]["exploratory_policy_result"] == "ALL_THREE_RETAINED_EXPLORATORY"
    assert payload["decision"]["retained_exploratory_candidates"] == list(calibration.CANDIDATES)
    assert payload["decision"]["original_confirmatory_bonferroni_108_result"] == "NONE_SURVIVE"
    assert payload["decision"]["original_confirmatory_survivors"] == []
    assert [item["passing_window_count"] for item in payload["cell_results"]] == [3, 2, 2]


def test_design_only_gate_and_safety(payload):
    assert payload["p544d_gate"]["status"] == "DESIGN_ONLY_GATE_OPEN"
    assert payload["p544d_gate"]["combination_generation_authorized"] is False
    assert payload["p544d_gate"]["combination_evaluation_authorized"] is False
    assert payload["safety"] == {
        "database_or_snapshot_opened": False,
        "sqlite_imported_or_invoked": False,
        "network_used_for_calibration": False,
        "strategy_combinations_generated": False,
        "candidate_set_expanded": False,
        "thresholds_tuned": False,
        "upstream_p545b_or_p545c_modified": False,
        "predictive_validity_claim": False,
        "roi_ev_staking_purchase_or_betting_claim": False,
    }


def test_canonical_digest_and_committed_outputs(payload):
    without_digest = dict(payload)
    recorded = without_digest.pop("canonical_payload_digest")
    assert recorded == calibration.digest(without_digest)
    assert (REPO_ROOT / calibration.OUTPUT_JSON).read_bytes() == calibration.render_json(payload)
    assert (REPO_ROOT / calibration.OUTPUT_MARKDOWN).read_text(encoding="utf-8") == calibration.render_markdown(payload)


def test_no_database_network_or_combination_imports():
    source = Path(calibration.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports.isdisjoint({"sqlite3", "requests", "urllib", "socket", "itertools"})
    assert "combinations(" not in source


def test_upstream_artifacts_remain_byte_identical():
    for path, size, sha256 in (
        (calibration.REGISTRY_PATH, calibration.REGISTRY_SIZE, calibration.REGISTRY_SHA256),
        (calibration.P545B_PATH, calibration.P545B_SIZE, calibration.P545B_SHA256),
    ):
        raw = (REPO_ROOT / path).read_bytes()
        assert len(raw) == size
        assert hashlib.sha256(raw).hexdigest() == sha256


def test_exact_four_p545g_r2_paths():
    discovered = {
        str(path.relative_to(REPO_ROOT))
        for root in (REPO_ROOT / "analysis", REPO_ROOT / "tests", REPO_ROOT / "outputs/research")
        for path in root.glob("*p545g_r2_exploratory_fixed_set_2_of_3_policy_adoption*")
    }
    assert discovered == set(calibration.NEW_FILES)
