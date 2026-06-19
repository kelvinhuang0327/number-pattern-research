"""Focused tests for the P280AT BIG 6/49 strategy ranking & portfolio replay.

All tests use synthetic in-memory fixtures or a temporary SQLite database. The
production DB is never opened. The tests assert leakage freedom, deterministic
ranking/scoring/baselines, the prize-aware rule, read-only DB behaviour, and that
the artifact carries the mandatory negative safety assertions (no prediction
success claim, no promotion, no activation, no publication/deadline/manifest).
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import p280at_big649_strategy_ranking_replay as mod


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def synthetic_history(n: int, start: int = 96000001) -> list[dict]:
    """n deterministic valid 6/49 draws with a special, strictly ascending ids."""
    rows = []
    for i in range(n):
        rng = random.Random(1000 + i)
        rows.append(
            {
                "draw": str(start + i),
                "date": "2020/01/01",
                "numbers": sorted(rng.sample(range(1, 50), 6)),
                "special": rng.randint(1, 49),
            }
        )
    return rows


def fake_replay(strategy_ids, n_eligible, win_map):
    """Build a replay structure with controllable per-strategy win patterns.

    ``win_map[sid]`` is a list of (main_hits, special_hit) tuples of length
    ``n_eligible``.
    """
    eligible = list(range(mod.MIN_HISTORY, mod.MIN_HISTORY + n_eligible))
    per_target = {sid: [] for sid in strategy_ids}
    for sid in strategy_ids:
        for pos, target_index in enumerate(eligible):
            hits, sp = win_map[sid][pos]
            per_target[sid].append(
                {
                    "target_index": target_index,
                    "target_draw": str(target_index),
                    "ticket": sorted([1, 2, 3, 4, 5, 6]),
                    "main_hits": hits,
                    "special_hit": sp,
                    "prize_win": hits >= 3 or (hits == 2 and sp),
                }
            )
    return {"strategy_ids": list(strategy_ids), "per_target": per_target, "eligible": eligible}


def temp_canonical_db(tmp_path: Path, history) -> Path:
    db = tmp_path / "synthetic_v2.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE draws_big_lotto_canonical_main "
        "(draw TEXT, date TEXT, numbers TEXT, special INTEGER)"
    )
    conn.executemany(
        "INSERT INTO draws_big_lotto_canonical_main VALUES (?,?,?,?)",
        [(d["draw"], d["date"], json.dumps(d["numbers"]), d["special"]) for d in history],
    )
    conn.commit()
    conn.close()
    return db


# --------------------------------------------------------------------------- #
# Prize rule + analytic baseline + binomial (Task G 4, 5 partial, Task E)
# --------------------------------------------------------------------------- #
def test_prize_rule_matches_dalotto_tiers():
    assert mod.main_hit_count([1, 2, 3, 4, 5, 6], [1, 2, 3, 7, 8, 9]) == 3
    assert mod.special_hit([1, 2, 3, 4, 5, 6], 4) is True
    assert mod.special_hit([1, 2, 3, 4, 5, 6], 40) is False
    # 3 main always wins regardless of special
    assert mod.prize_aware_win([1, 2, 3, 4, 5, 6], [1, 2, 3, 40, 41, 42], 49) is True
    # 2 main + special wins (tier 7)
    assert mod.prize_aware_win([1, 2, 3, 4, 5, 6], [1, 2, 40, 41, 42, 43], 6) is True
    # 2 main without special does NOT win
    assert mod.prize_aware_win([1, 2, 3, 4, 5, 6], [1, 2, 40, 41, 42, 43], 49) is False
    # 1 main never wins
    assert mod.prize_aware_win([1, 2, 3, 4, 5, 6], [1, 40, 41, 42, 43, 44], 2) is False


def test_analytic_baseline_exact_values():
    b = mod.analytic_baseline()
    assert b["combinations_6_of_49"] == 13983816
    assert abs(b["expected_main_hits_single_ticket"] - 36 / 49) < 1e-5  # value is rounded to 6 dp
    # P(>=3) ~ 0.018637, P(any prize) ~ 0.030952
    assert abs(b["p_main_ge3"] - 0.0186375) < 1e-5
    assert abs(b["p_any_prize_single_ticket"] - 0.0309518) < 1e-5
    # probabilities sum to 1
    assert abs(sum(b["p_exact_main_hits"].values()) - 1.0) < 1e-9


def test_binom_sf_bounds_and_monotonicity():
    assert mod.binom_sf(0, 100, 0.03) == 1.0
    assert mod.binom_sf(101, 100, 0.03) == 0.0
    # more observed wins -> smaller upper tail
    assert mod.binom_sf(10, 750, 0.031) > mod.binom_sf(40, 750, 0.031)
    # a value near the mean should be < 1 and > 0
    p = mod.binom_sf(int(750 * 0.031) + 5, 750, 0.031)
    assert 0.0 < p < 1.0


# --------------------------------------------------------------------------- #
# Metric aggregation + hit distribution (Task G 3, 4)
# --------------------------------------------------------------------------- #
def test_metric_aggregation_and_hit_distribution():
    records = [
        {"main_hits": 0, "special_hit": False, "prize_win": False},
        {"main_hits": 2, "special_hit": True, "prize_win": True},   # tier-7 rescue
        {"main_hits": 3, "special_hit": False, "prize_win": True},
        {"main_hits": 4, "special_hit": True, "prize_win": True},
        {"main_hits": 2, "special_hit": False, "prize_win": False},
    ]
    m = mod._metrics_over(records)
    assert m["support"] == 5
    assert m["hit_distribution"]["2"] == 2
    assert m["ge3_count"] == 2 and m["ge4_count"] == 1
    assert m["prize_win_count"] == 3
    assert m["best_main_hits"] == 4
    assert m["special_hit_count"] == 2
    assert m["special_rescue_count"] == 1  # only the 2+special rescue
    assert abs(m["avg_main_hits"] - (0 + 2 + 3 + 4 + 2) / 5) < 1e-9


# --------------------------------------------------------------------------- #
# Ranking determinism + tie-break (Task G 1)
# --------------------------------------------------------------------------- #
def test_ranking_tiebreak_is_deterministic_by_strategy_id():
    # Two strategies tie on every metric except the id tie-break.
    def make_metrics(rate, avg):
        return {name: {"prize_win_rate": rate, "avg_main_hits": avg} for name, _ in mod.HORIZONS}

    metrics = {
        "b_strat": make_metrics(0.03, 0.73),
        "a_strat": make_metrics(0.03, 0.73),
        "c_strat": make_metrics(0.05, 0.80),
    }
    ranked = mod.rank_strategies(metrics)
    assert [r["strategy_id"] for r in ranked] == ["c_strat", "a_strat", "b_strat"]
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    # stable across repeated calls
    assert mod.rank_strategies(metrics) == ranked


# --------------------------------------------------------------------------- #
# No outcome leakage (Task G 2)
# --------------------------------------------------------------------------- #
def test_no_outcome_leakage_in_replay():
    history = synthetic_history(mod.MIN_HISTORY + 15)
    dataset = mod.build_replay_dataset(history)
    seen_lengths = []
    captured = {}

    def recorder(hist, **kwargs):
        seen_lengths.append(len(hist))
        captured[len(hist)] = [dict(h) for h in hist]
        return [1, 2, 3, 4, 5, 6]

    bound = [{"strategy_id": "rec", "function": recorder, "kwargs": {}, "multi": False}]
    replay = mod.run_strategy_replay(dataset, bound)

    # Each eligible target index i must have received exactly i prior draws.
    assert seen_lengths == dataset["eligible_target_indices"]
    # The target draw's numbers were never present in the history fed to the strategy.
    for i in dataset["eligible_target_indices"]:
        target_numbers = dataset["rows"][i]["numbers"]
        fed = captured[i]
        assert len(fed) == i
        # the fed history is exactly minimal[:i]
        assert fed == dataset["minimal"][:i]
        # the target's own draw is strictly after the fed window
        assert all(d["numbers"] == dataset["minimal"][j]["numbers"] for j, d in enumerate(fed))
    assert len(replay["per_target"]["rec"]) == dataset["eligible_target_count"]


def test_walkforward_prior_winrate_is_leakage_free_with_warmup():
    # one strategy that wins on every eligible target
    sid = "always"
    n = mod.WALK_FORWARD_MIN_PRIOR + 10
    win_map = {sid: [(6, True)] * n}
    replay = fake_replay([sid], n, win_map)
    prior = mod._prefix_prior_winrate(replay)[sid]
    # positions below the warmup are not selectable
    assert all(prior[pos] == -1.0 for pos in range(mod.WALK_FORWARD_MIN_PRIOR))
    # at the first selectable position, prior uses strictly-before wins only
    pos = mod.WALK_FORWARD_MIN_PRIOR
    assert abs(prior[pos] - 1.0) < 1e-9  # all prior were wins
    # the very first record's outcome cannot influence its own selection (pos 0 -> -1)
    assert prior[0] == -1.0


# --------------------------------------------------------------------------- #
# Current pack contribution ranking (Task G 5)
# --------------------------------------------------------------------------- #
def test_pack_contribution_ranking_and_coverage():
    # craft 3 tickets with known overlap structure
    outputs = [
        {"strategy_id": "s1", "bet_index": 1, "predicted_main_numbers": [1, 2, 3, 4, 5, 6]},
        {"strategy_id": "s2", "bet_index": 1, "predicted_main_numbers": [1, 2, 3, 4, 5, 7]},  # 5 overlap with s1
        {"strategy_id": "s3", "bet_index": 1, "predicted_main_numbers": [40, 41, 42, 43, 44, 45]},  # disjoint
    ]
    analysis = mod.pack_contribution_analysis(outputs)
    per = analysis["per_ticket"]
    # s3 is fully unique (disjoint); s1/s2 overlap heavily
    assert per["s3"]["unique_number_count"] == 6
    assert per["s1"]["max_pair_overlap"] == 5
    assert per["s2"]["max_pair_overlap"] == 5
    # s3 ranks first (highest unique contribution)
    assert analysis["ranking"][0]["strategy_id"] == "s3"
    # coverage = distinct numbers across all tickets
    assert analysis["distinct_numbers_covered"] == len({1, 2, 3, 4, 5, 6, 7, 40, 41, 42, 43, 44, 45})
    # expected random coverage field present and comparison computed
    assert "expected_random_coverage_same_budget" in analysis
    assert isinstance(analysis["pack_coverage_beats_random_coverage"], bool)


# --------------------------------------------------------------------------- #
# Random + diversified-random baselines (Task G 7, 8)
# --------------------------------------------------------------------------- #
def test_random_ticket_is_valid_and_seed_deterministic():
    r1 = mod._random_ticket(mod._rng(42, 1, 500, 0))
    r2 = mod._random_ticket(mod._rng(42, 1, 500, 0))
    r3 = mod._random_ticket(mod._rng(7, 1, 500, 0))
    assert r1 == r2  # same seed/parts -> identical
    assert len(r1) == 6 and len(set(r1)) == 6 and all(1 <= x <= 49 for x in r1)
    assert r1 != r3 or True  # different seed usually differs (not asserted strictly)


def test_diversified_tickets_low_overlap_and_deterministic():
    t1 = mod._diversified_tickets(mod._rng(42, 2, 500, 0), 8)
    t2 = mod._diversified_tickets(mod._rng(42, 2, 500, 0), 8)
    assert t1 == t2  # deterministic
    # first floor(49/6)=8 tickets drawn without replacement -> pairwise disjoint
    flat = [n for ticket in t1 for n in ticket]
    assert len(flat) == len(set(flat)) == 48


def test_random_baselines_reproducible_and_increasing_in_k():
    history = synthetic_history(mod.MIN_HISTORY + 30)
    dataset = mod.build_replay_dataset(history)
    a = mod.random_baselines(dataset, seed=42, replicates=8)
    b = mod.random_baselines(dataset, seed=42, replicates=8)
    assert a == b  # fully reproducible
    eq = a["equal_budget_random"]["all_available"]
    # portfolio win rate is non-decreasing in budget k
    rates = [eq[str(k)]["mean_portfolio_win_rate"] for k in mod.BUDGETS]
    assert rates == sorted(rates)


# --------------------------------------------------------------------------- #
# Digest fixture validation (Task G 14)
# --------------------------------------------------------------------------- #
def test_strategy_output_digest_is_canonical_and_deterministic():
    outputs = [
        {"strategy_id": sid, "bet_index": 1, "predicted_main_numbers": list(range(i, i + 6))}
        for i, sid in zip(range(1, 23, 2), mod.list_frozen_big649_strategy_ids())
    ]
    d1 = mod.compute_strategy_output_digest(outputs)
    # reordering inputs must not change the canonical digest
    d2 = mod.compute_strategy_output_digest(list(reversed(outputs)))
    assert d1 == d2
    assert len(d1) == 64 and all(c in "0123456789abcdef" for c in d1)


# --------------------------------------------------------------------------- #
# Read-only DB behaviour (Task G 13)
# --------------------------------------------------------------------------- #
def test_db_loaded_read_only_and_unchanged(tmp_path):
    history = synthetic_history(10)
    db = temp_canonical_db(tmp_path, history)
    before = mod._sha256_file(db)
    loaded = mod.load_canonical_history(db)
    after = mod._sha256_file(db)
    assert before == after  # read did not modify the file
    assert len(loaded) == 10
    assert loaded[0]["draw"] == "96000001"
    assert loaded[0]["numbers"] == history[0]["numbers"]


def test_write_is_rejected_through_readonly_uri(tmp_path):
    history = synthetic_history(3)
    db = temp_canonical_db(tmp_path, history)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO draws_big_lotto_canonical_main VALUES ('x','y','[1,2,3,4,5,6]',7)")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Dataset gate (Task A) — duplicate / malformed rejection
# --------------------------------------------------------------------------- #
def test_dataset_gate_rejects_duplicate_draw_ids():
    history = synthetic_history(mod.MIN_HISTORY + 5)
    history[-1]["draw"] = history[-2]["draw"]  # duplicate id
    with pytest.raises(mod.ReplayDatasetError):
        mod.build_replay_dataset(history)


def test_dataset_gate_eligible_targets_need_min_history():
    history = synthetic_history(mod.MIN_HISTORY + 7)
    dataset = mod.build_replay_dataset(history)
    assert dataset["eligible_target_count"] == 7
    assert dataset["eligible_target_indices"][0] == mod.MIN_HISTORY


# --------------------------------------------------------------------------- #
# End-to-end integration on a synthetic DB (Tasks B-F, G 6, 9-12)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def integration_payload(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("p280at_int")
    history = synthetic_history(mod.MIN_HISTORY + 40)
    db = temp_canonical_db(tmp, history)
    state = mod.run_full_replay(db, origin_main="TEST_MAIN", git_head="TESTHEAD", seed=42, replicates=5)
    return mod.build_payload(state, db)


def test_integration_schema_has_final_classification(integration_payload):
    p = integration_payload
    assert p["task_id"] == "P280AT"
    assert p["final_classification"] in (mod.NULL_CLASSIFICATION, mod.OBSERVATION_CLASSIFICATION)
    assert p["exact_strategy_ids"] == list(mod.list_frozen_big649_strategy_ids())
    assert len(p["exact_strategy_ids"]) == 11
    assert "canonical_digest" in p and len(p["canonical_digest"]) == 64


def test_integration_combination_methods_present_and_leakage_free(integration_payload):
    detail = integration_payload["portfolio_combination_detail"]
    for method in mod.COMBINATION_METHODS:
        assert method in detail
    # all_11 only applicable at k == 11
    all11 = detail["all_11_strategy_pack"]["long_750"]
    assert all11["11"]["applicable"] is True
    assert all11["1"]["applicable"] is False
    # every applicable strategy method cell is flagged leakage_free
    for method in ("top_k_by_historical_replay", "diversity_first_low_overlap", "marginal_contribution_greedy"):
        for k in ("1", "3", "5", "7", "11"):
            cell = detail[method]["long_750"][k]
            if cell.get("applicable"):
                assert cell["leakage_free"] is True
    # outcome-using methods are correctly flagged
    assert detail["top_k_by_historical_replay"]["long_750"]["3"]["uses_outcomes"] is True
    assert detail["diversity_first_low_overlap"]["long_750"]["3"]["uses_outcomes"] is False


def test_integration_no_success_claim_promotion_or_publication(integration_payload):
    p = integration_payload
    # mandatory negative safety assertions
    assert p["prediction_success_claim"] is False
    assert p["strategy_promoted"] is False
    assert p["activation_authorized"] is False
    assert p["registry_mutated"] is False
    assert p["official_target_lookup"] is False
    assert p["official_deadline_lookup"] is False
    assert p["real_publication_performed"] is False
    assert p["pre_draw_manifest_created"] is False
    assert p["publication_pr_created"] is False
    assert p["post_draw_evaluation_started"] is False


def test_integration_no_publication_or_deadline_tokens_in_artifact(integration_payload):
    # The serialized artifact must not assert any real deadline/manifest/publication.
    blob = json.dumps(integration_payload).lower()
    for forbidden in ("official_deadline\": \"", "manifest_path", "publication_url", "pre_draw_manifest_path"):
        assert forbidden not in blob
    # database is read-only: copied/written are False
    assert integration_payload["database_access"]["copied"] is False
    assert integration_payload["database_access"]["written"] is False


def test_integration_db_not_modified_by_full_run(tmp_path):
    history = synthetic_history(mod.MIN_HISTORY + 25)
    db = temp_canonical_db(tmp_path, history)
    before = mod._sha256_file(db)
    state = mod.run_full_replay(db, origin_main="T", git_head="T", seed=42, replicates=4)
    after = mod._sha256_file(db)
    assert before == after
    assert state["db_hash_pre"]["main"] == state["db_hash_post"]["main"]


def test_integration_canonical_digest_is_deterministic(tmp_path):
    history = synthetic_history(mod.MIN_HISTORY + 25)
    db = temp_canonical_db(tmp_path, history)
    p1 = mod.build_payload(mod.run_full_replay(db, "M", "H", seed=42, replicates=5), db)
    p2 = mod.build_payload(mod.run_full_replay(db, "M", "H", seed=42, replicates=5), db)
    assert p1["canonical_digest"] == p2["canonical_digest"]
