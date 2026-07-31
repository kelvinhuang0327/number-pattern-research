"""P541A — read-only tests for the BIG_LOTTO strategy inventory / replay
coverage audit.

These tests call `build_report()` (a pure function that only reads source
files via regex/text parsing, runs `git grep -l`, and opens the canonical DB
read-only with PRAGMA query_only=ON) and assert the reconciled numbers. They
never write the DB, the registry, or any artifact file.
"""
import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pytestmark = pytest.mark.filterwarnings("ignore")


def _module():
    from analysis import p541a_biglotto_strategy_inventory_replay_coverage_audit as mod

    return mod


def _report():
    mod = _module()
    if not mod.DB_PATH.exists():
        pytest.skip(f"replay DB not present at {mod.DB_PATH}")
    return mod.build_report()


# ── Static registry parsing ──────────────────────────────────────────────


def test_main_registry_online_biglotto_strategies_found():
    mod = _module()
    entries = mod.parse_main_registry()
    online_ids = {e["strategy_id"] for e in entries if e["status"] == "ONLINE"}
    assert online_ids == {"biglotto_triple_strike", "biglotto_deviation_2bet", "ts3_regime_3bet"}


def test_main_registry_rejected_zero_row_ids_present():
    mod = _module()
    entries = mod.parse_main_registry()
    rejected_ids = {e["strategy_id"] for e in entries if e["status"] == "REJECTED"}
    assert {"biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet"} <= rejected_ids


def test_p42_wave3_shadow_ids_not_in_all_adapters():
    mod = _module()
    entries = mod.parse_p42_wave3()
    ids = {e["strategy_id"] for e in entries}
    assert ids == {
        "markov_single_biglotto",
        "markov_2bet_biglotto",
        "bet2_fourier_expansion_biglotto",
        "fourier30_markov30_biglotto",
        "cold_complement_biglotto",
        "coldpool15_biglotto",
    }
    assert all(e["in_all_adapters"] is False for e in entries)


def test_p93_tierb_lifecycle_conflict_ids_found():
    mod = _module()
    entries = mod.parse_p93_tierb()
    online = {e["strategy_id"] for e in entries if e["status"] == "ONLINE"}
    assert {"biglotto_echo_aware_3bet", "biglotto_ts3_markov_4bet_w30"} <= online


def test_d3_phantom_ids_match_p263a_baseline():
    mod = _module()
    d3 = mod.parse_d3_phantom_and_registered_without_rows()
    assert set(d3["phantom_ids"]) == {
        "regime_2bet",
        "p1_deviation_4bet",
        "p1_dev_sum5bet",
        "p1_neighbor_cold_2bet",
    }
    assert set(d3["registered_without_rows"]) == {
        "biglotto_ts3_acb_4bet",
        "biglotto_ts3_markov_freq_5bet",
    }


# ── Full report (requires read-only DB access) ──────────────────────────


def test_report_has_required_top_level_sections():
    r = _report()
    required = {
        "summary_answer",
        "inventory_sources_scanned",
        "big_lotto_strategy_inventory",
        "folklore_and_statistical_method_inventory",
        "replay_coverage_by_strategy",
        "artifact_coverage_by_strategy",
        "coverage_gaps",
        "ambiguous_or_unmapped_items",
        "deprecated_or_excluded_items",
        "answer_to_owner_question",
        "recommended_next_single_worker_task",
        "provenance_and_limits",
    }
    assert required <= set(r.keys())


def test_disclaimer_present():
    r = _report()
    disclaimer = (
        "Historical strategy inventory and replay coverage audit only; not a "
        "prediction, betting edge, future-winning, or production-readiness claim."
    )
    assert r["disclaimer"] == disclaimer
    assert r["provenance_and_limits"]["disclaimer"] == disclaimer


def test_eleven_strategies_replayed_and_artifact_covered():
    r = _report()
    covered = [
        sid
        for sid, e in r["big_lotto_strategy_inventory"].items()
        if e["classification"] == "replayed_and_artifact_covered"
    ]
    assert len(covered) == 11
    assert set(covered) == {
        "bet2_fourier_expansion_biglotto",
        "biglotto_deviation_2bet",
        "biglotto_echo_aware_3bet",
        "biglotto_triple_strike",
        "biglotto_ts3_markov_4bet_w30",
        "cold_complement_biglotto",
        "coldpool15_biglotto",
        "fourier30_markov30_biglotto",
        "markov_2bet_biglotto",
        "markov_single_biglotto",
        "ts3_regime_3bet",
    }


def test_two_registered_zero_replay_row_strategies():
    r = _report()
    no_rows = [
        sid
        for sid, e in r["big_lotto_strategy_inventory"].items()
        if e["classification"] == "code_or_registry_only_no_replay_rows"
    ]
    assert set(no_rows) == {"biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet"}
    for sid in no_rows:
        assert r["big_lotto_strategy_inventory"][sid]["replay_row_count"] is None


def test_four_phantom_ids_no_code_no_replay():
    r = _report()
    phantom = [
        sid
        for sid, e in r["big_lotto_strategy_inventory"].items()
        if e["classification"] == "artifact_only_unmapped_to_code"
    ]
    assert set(phantom) == {
        "regime_2bet",
        "p1_deviation_4bet",
        "p1_dev_sum5bet",
        "p1_neighbor_cold_2bet",
    }


def test_total_replay_rows_matches_direct_db_count():
    r = _report()
    assert r["replay_coverage_totals"]["total_rows"] == 24140
    assert r["replay_coverage_totals"]["distinct_strategy_ids_with_rows"] == 11


def test_owner_answer_is_partial_with_evidence():
    r = _report()
    answer = r["answer_to_owner_question"]
    assert answer["verdict"] == "PARTIAL"
    assert answer["covered_count"] == 11
    assert set(answer["uncovered_registered_strategy_ids"]) == {
        "biglotto_ts3_acb_4bet",
        "biglotto_ts3_markov_freq_5bet",
    }
    assert set(answer["uncovered_phantom_ids_no_code_no_replay"]) == {
        "regime_2bet",
        "p1_deviation_4bet",
        "p1_dev_sum5bet",
        "p1_neighbor_cold_2bet",
    }
    assert isinstance(answer["reason"], str) and len(answer["reason"]) > 0


def test_lifecycle_status_conflict_flagged():
    r = _report()
    conflicts = set(r["coverage_gaps"]["lifecycle_status_conflicts_retired_vs_online"])
    assert {"biglotto_echo_aware_3bet", "biglotto_ts3_markov_4bet_w30"} <= conflicts


def test_legacy_scripts_are_listed_not_individually_traced():
    r = _report()
    ambiguous = r["ambiguous_or_unmapped_items"]
    assert len(ambiguous["legacy_tools_scripts_matched_not_individually_traced"]) > 0
    assert all(
        p.startswith("tools/")
        for p in ambiguous["legacy_tools_scripts_matched_not_individually_traced"]
    )


def test_report_is_json_serializable():
    r = _report()
    json.dumps(r, ensure_ascii=False)


# ── DB safety ─────────────────────────────────────────────────────────────


def test_db_unchanged_across_report_build():
    mod = _module()
    if not mod.DB_PATH.exists():
        pytest.skip(f"replay DB not present at {mod.DB_PATH}")
    before = mod.db_snapshot(mod.DB_PATH)
    mod.build_report()
    after = mod.db_snapshot(mod.DB_PATH)
    assert before == after
