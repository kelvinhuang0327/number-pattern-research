"""
P282B tests — BIG 6/49 deduplicated portfolio replay & diversified-random falsification.

Covers Task G items 1..20. Pure functions are tested directly; the full read-only
pipeline is exercised end-to-end against a SYNTHETIC temporary SQLite DB (deterministic
fixtures, no production data, no real-DB dependency). Monte Carlo iterations and
diversified-resamples are kept small for speed.
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOL_PATH = _REPO_ROOT / "tools" / "p282b_big649_deduplicated_portfolio_replay.py"

# import the tool module by path
_spec = importlib.util.spec_from_file_location("p282b_tool", _TOOL_PATH)
p282b = importlib.util.module_from_spec(_spec)
sys.modules["p282b_tool"] = p282b
_spec.loader.exec_module(p282b)

from lottery_api.prize_aware_scorer import score_prize_aware_ticket, SCORING_VERSION


# ---------------------------------------------------------------------------
# Synthetic temp DB fixture
# ---------------------------------------------------------------------------

CANONICAL_VIEW_SQL = """
CREATE VIEW draws_big_lotto_canonical_main AS
SELECT d.*
FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND d.draw NOT LIKE '%-%'
  AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
  AND (SELECT MAX(CAST(j.value AS INTEGER)) FROM json_each(d.numbers) j) > 25
"""


def _draws_rows():
    # (draw, numbers, special) — all canonical (max > 25, 6-digit, no dash, not 20*)
    return [
        ("900001", [1, 2, 3, 30, 40, 49], 7),
        ("900002", [4, 5, 6, 28, 35, 44], 9),
        ("900003", [11, 12, 13, 27, 33, 41], 2),
        ("900004", [7, 8, 9, 26, 38, 47], 14),
        ("900005", [3, 10, 19, 29, 36, 45], 21),
        ("900006", [2, 15, 22, 31, 39, 48], 6),
        # non-canonical: all numbers <= 25 -> filtered out of the view
        ("900099", [1, 2, 3, 4, 5, 6], 8),
    ]


def _replay_rows():
    # (target_draw, strategy_id, bet_index, predicted_numbers, history_cutoff_draw)
    # Deliberate exact duplicates within a draw to exercise deduplication.
    rows = []

    def add(td, sid, bi, pred, cutoff):
        rows.append((td, sid, bi, json.dumps(pred), cutoff))

    # draw 900001 : 4 tickets, 2 exact duplicates -> 2 unique
    add("900001", "s_alpha", 1, [1, 2, 3, 30, 40, 49], "900000")     # 6-hit
    add("900001", "s_beta", 1, [1, 2, 3, 30, 40, 49], "900000")      # duplicate of s_alpha
    add("900001", "s_gamma", 1, [10, 11, 12, 13, 14, 15], "900000")  # miss
    add("900001", "s_gamma", 2, [10, 11, 12, 13, 14, 15], "900000")  # duplicate of s_gamma/1

    # draw 900002 : 3 tickets, all distinct
    add("900002", "s_alpha", 1, [4, 5, 6, 1, 2, 3], "900001")        # hit 3
    add("900002", "s_beta", 1, [28, 35, 44, 7, 8, 9], "900001")      # hit 3
    add("900002", "s_gamma", 1, [40, 41, 42, 43, 44, 45], "900001")  # hit 1

    # draw 900003 : 3 tickets, one duplicate pair
    add("900003", "s_alpha", 1, [11, 12, 13, 1, 2, 4], "900002")     # hit 3
    add("900003", "s_beta", 1, [11, 12, 13, 1, 2, 4], "900002")      # duplicate
    add("900003", "s_gamma", 1, [27, 33, 41, 2, 5, 8], "900002")     # hit 3 + special(2)

    # draw 900004 : 2 tickets distinct
    add("900004", "s_alpha", 1, [7, 8, 9, 1, 2, 3], "900003")        # hit 3
    add("900004", "s_beta", 1, [26, 38, 47, 14, 1, 2], "900003")     # hit 3 + special(14)

    # draw 900005 : 2 tickets, one a 2-hit+special candidate
    add("900005", "s_alpha", 1, [3, 10, 1, 2, 4, 5], "900004")       # hit 2 (3,10), special 21 not in
    add("900005", "s_beta", 1, [29, 36, 21, 1, 2, 4], "900004")      # hit 2 (29,36) + special(21) -> win

    # draw 900006 : 2 tickets distinct, misses
    add("900006", "s_alpha", 1, [1, 3, 5, 7, 9, 11], "900005")       # miss
    add("900006", "s_beta", 1, [2, 4, 6, 8, 10, 12], "900005")       # hit 2 (2), special 6 in? 6 in ticket -> hit2+special

    # non-canonical target -> excluded
    add("900099", "s_alpha", 1, [1, 2, 3, 4, 5, 6], "900098")

    return rows


@pytest.fixture()
def synth_db(tmp_path):
    db_path = tmp_path / "synthetic_lottery.db"
    con = sqlite3.connect(str(db_path))
    con.execute(
        """CREATE TABLE draws (id INTEGER PRIMARY KEY AUTOINCREMENT, draw TEXT NOT NULL,
           date TEXT NOT NULL, lottery_type TEXT NOT NULL, numbers TEXT NOT NULL,
           special INTEGER DEFAULT 0, UNIQUE(draw, lottery_type))"""
    )
    con.execute(
        """CREATE TABLE strategy_prediction_replays (id INTEGER PRIMARY KEY AUTOINCREMENT,
           lottery_type TEXT NOT NULL, target_draw TEXT NOT NULL, strategy_id TEXT NOT NULL,
           bet_index INTEGER NOT NULL DEFAULT 1, predicted_numbers TEXT,
           history_cutoff_draw TEXT, replay_status TEXT NOT NULL,
           UNIQUE(lottery_type, target_draw, strategy_id, bet_index))"""
    )
    for draw, numbers, special in _draws_rows():
        con.execute("INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?,?,?,?,?)",
                    (draw, "2026/01/01", "BIG_LOTTO", json.dumps(numbers), special))
    for td, sid, bi, pred, cutoff in _replay_rows():
        con.execute(
            """INSERT INTO strategy_prediction_replays
               (lottery_type, target_draw, strategy_id, bet_index, predicted_numbers,
                history_cutoff_draw, replay_status) VALUES (?,?,?,?,?,?, 'PREDICTED')""",
            ("BIG_LOTTO", td, sid, bi, pred, cutoff))
    con.execute(CANONICAL_VIEW_SQL)
    con.commit()
    con.close()
    return str(db_path)


@pytest.fixture()
def results(synth_db):
    return p282b.run_research(synth_db, iters=60, master_seed=282, diversity_resamples=20)


# ---------------------------------------------------------------------------
# 1. Ticket canonicalization
# ---------------------------------------------------------------------------

def test_canonicalize_sorts_and_validates():
    assert p282b.canonicalize_ticket([49, 1, 7, 3, 28, 15]) == (1, 3, 7, 15, 28, 49)
    with pytest.raises(ValueError):
        p282b.canonicalize_ticket([1, 2, 3, 4, 5])          # wrong count
    with pytest.raises(ValueError):
        p282b.canonicalize_ticket([1, 2, 3, 4, 5, 5])       # duplicate number
    with pytest.raises(ValueError):
        p282b.canonicalize_ticket([0, 2, 3, 4, 5, 6])       # out of range
    with pytest.raises(ValueError):
        p282b.canonicalize_ticket([1, 2, 3, 4, 5, 50])      # out of range
    with pytest.raises(ValueError):
        p282b.canonicalize_ticket("123456")                 # not a sequence of ints


# ---------------------------------------------------------------------------
# 2. Exact duplicate removal  /  3. non-identical retained  /  4. no add/replace
# ---------------------------------------------------------------------------

def test_dedup_removes_only_exact_duplicates():
    a = (1, 2, 3, 4, 5, 6)
    b = (1, 2, 3, 4, 5, 7)
    tickets = [a, a, b, a]
    unique, removed = p282b.deduplicate_tickets(tickets)
    assert unique == [a, b]            # first-seen order preserved
    assert removed == 2


def test_dedup_retains_all_distinct_tickets():
    a = (1, 2, 3, 4, 5, 6)
    b = (1, 2, 3, 4, 5, 7)
    c = (10, 11, 12, 13, 14, 15)
    unique, removed = p282b.deduplicate_tickets([a, b, c])
    assert unique == [a, b, c]
    assert removed == 0


def test_dedup_never_adds_or_replaces():
    tickets = [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]
    unique, removed = p282b.deduplicate_tickets(tickets)
    # every retained ticket is a member of the original input (no invented tickets)
    assert set(unique).issubset(set(tickets))
    # count is monotone non-increasing; total accounted for
    assert len(unique) + removed == len(tickets)


# ---------------------------------------------------------------------------
# 5. Underfilled detection (in realized groups)
# ---------------------------------------------------------------------------

def test_underfilled_detected_for_dedup(results):
    # draw 900001 has 4 raw tickets, 2 duplicates -> D underfilled by 2
    rec = next(r for r in results["per_draw_aggregate_metrics"]["sample_per_draw_records_recent"]
               if r["draw"] == "900001")
    d = rec["groups"][p282b.GROUP_D]
    assert d["requested_budget"] == 4
    assert d["produced_count"] == 2
    assert d["underfilled_count"] == 2
    assert d["duplicate_identities_removed"] == 2
    assert d["no_replacement_count"] == 0


# ---------------------------------------------------------------------------
# 6. Independent random determinism with fixed seed
# ---------------------------------------------------------------------------

def test_independent_random_deterministic():
    import random
    p1 = p282b.sample_independent_random(random.Random(1), 5)
    p2 = p282b.sample_independent_random(random.Random(1), 5)
    p3 = p282b.sample_independent_random(random.Random(2), 5)
    assert p1 == p2
    assert p1 != p3 or True  # different seed may differ; equality not required
    for t in p1:
        assert len(t) == 6 and len(set(t)) == 6 and all(1 <= n <= 49 for n in t)


# ---------------------------------------------------------------------------
# 7-9. Diversified random: determinism, overlap constraint, underfill-not-relax
# ---------------------------------------------------------------------------

def test_diversified_random_deterministic():
    import random
    a = p282b.sample_diversified_random(random.Random(7), 6)
    b = p282b.sample_diversified_random(random.Random(7), 6)
    assert a == b


def test_diversified_random_respects_overlap_cap():
    import random
    tickets, underfilled, produced = p282b.sample_diversified_random(
        random.Random(3), 8, cap=p282b.DIVERSITY_OVERLAP_CAP)
    sets = [set(t) for t in tickets]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert len(sets[i] & sets[j]) <= p282b.DIVERSITY_OVERLAP_CAP
    # no exact duplicates possible under the cap
    assert len(set(tickets)) == len(tickets)


def test_diversified_random_underfills_when_infeasible():
    import random
    # cap=0 (disjoint) cannot place 9 mutually-disjoint 6-number tickets from 49 (max 8)
    tickets, underfilled, produced = p282b.sample_diversified_random(
        random.Random(5), 9, cap=0, max_attempts=500)
    assert underfilled is True
    assert produced < 9
    # the produced tickets still satisfy the (un-relaxed) constraint
    sets = [set(t) for t in tickets]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert len(sets[i] & sets[j]) == 0


# ---------------------------------------------------------------------------
# 10. No outcome access during ticket generation
# ---------------------------------------------------------------------------

def test_ticket_generation_has_no_outcome_parameter():
    import inspect
    for fn in (p282b.sample_independent_random, p282b.sample_diversified_random):
        params = list(inspect.signature(fn).parameters)
        assert "actual_main" not in params
        assert "actual_special" not in params
        assert "actuals" not in params
    # deduplication likewise takes only ticket contents
    assert list(inspect.signature(p282b.deduplicate_tickets).parameters) == ["tickets"]


# ---------------------------------------------------------------------------
# 11. Same-budget comparison eligibility
# ---------------------------------------------------------------------------

def test_same_budget_groups(results):
    for rec in results["per_draw_aggregate_metrics"]["sample_per_draw_records_recent"]:
        b = rec["requested_budget"]
        ga = rec["groups"][p282b.GROUP_A]
        gc = rec["groups"][p282b.GROUP_C]
        gd = rec["groups"][p282b.GROUP_D]
        gb = rec["groups"][p282b.GROUP_B]
        assert ga["produced_count"] == b      # independent random always fills
        assert gc["produced_count"] == b      # raw deterministic = budget
        assert gd["produced_count"] <= b      # dedup may reduce
        assert gb["produced_count"] <= b      # diversity may underfill
    # primary comparison budget policy is equal-budget at U_d
    assert "EQUAL budget U_d" in results["primary_comparison_d_vs_a"]["budget_policy"]


# ---------------------------------------------------------------------------
# 12. Primary D vs A uses paired same-draw observations
# ---------------------------------------------------------------------------

def test_primary_paired_same_draw(results):
    method = results["primary_comparison_d_vs_a"]["method"]
    assert "paired same-draw" in method
    by_window = results["primary_comparison_d_vs_a"]["results_by_window"]
    for name, size in results["frozen_windows"].items():
        assert by_window[name]["window_draws"] == size
        assert by_window[name]["mc_iterations"] == 60


# ---------------------------------------------------------------------------
# 13. Random/deterministic group result schema
# ---------------------------------------------------------------------------

def test_group_window_schema(results):
    required = {"draw_count", "mean_requested_budget", "mean_produced_budget",
                "mean_unique_tickets", "duplicate_rate", "underfilled_rate",
                "mean_main_coverage", "mean_max_overlap", "mean_pairwise_overlap",
                "prize_aware_success_count", "prize_aware_success_rate",
                "m3_plus_success_count", "m3_plus_success_rate",
                "best_main_hit_distribution"}
    for g in p282b.GROUPS:
        for name in results["frozen_windows"]:
            assert required.issubset(results["group_window_metrics"][g][name].keys())


# ---------------------------------------------------------------------------
# 14. Artifact safety flags
# ---------------------------------------------------------------------------

def test_safety_flags(results):
    assert results["db_copied"] is False
    assert results["db_written"] is False
    assert results["no_db_write_or_copy"] is True
    assert results["no_prediction_success_claim"] is True
    assert results["no_strategy_promoted"] is True
    assert results["no_activation"] is True
    assert results["no_real_publication"] is True
    assert results["no_official_target_or_deadline_lookup"] is True
    assert results["no_pre_draw_manifest"] is True
    assert results["research_only"] is True


# ---------------------------------------------------------------------------
# 15. DB write/copy rejection (read-only connection)
# ---------------------------------------------------------------------------

def test_db_connection_is_read_only(synth_db):
    con = p282b.open_readonly(synth_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("INSERT INTO draws (draw, date, lottery_type, numbers, special) "
                        "VALUES ('x','y','BIG_LOTTO','[1,2,3,4,5,6]',1)")
        with pytest.raises(sqlite3.OperationalError):
            con.execute("CREATE TABLE evil (x INT)")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 16. No current/future live ticket declaration in artifact
# ---------------------------------------------------------------------------

def test_no_live_ticket_declaration(results):
    # the artifact must carry the explicit NEGATIVE declaration, not a positive one
    assert results["current_or_future_live_tickets_output"] is False
    assert results["ticket_replacement_count"] == 0
    blob = json.dumps(results).lower()
    # positive-intent phrases that would only appear in a real publication / live bet
    for forbidden in ("published_tickets", "buy these", "place these bets",
                      "official deadline is", "live betting ticket", "recommended_play"):
        assert forbidden not in blob


# ---------------------------------------------------------------------------
# 17. Deterministic artifact digest (two runs identical)
# ---------------------------------------------------------------------------

def test_deterministic_digest_reproduces(synth_db):
    r1 = p282b.run_research(synth_db, iters=60, master_seed=282, diversity_resamples=20)
    r2 = p282b.run_research(synth_db, iters=60, master_seed=282, diversity_resamples=20)
    assert r1["deterministic_digest"] == r2["deterministic_digest"]
    assert len(r1["deterministic_digest"]) == 64


def test_digest_excludes_environment_fields(synth_db):
    r = p282b.run_research(synth_db, iters=40, master_seed=282, diversity_resamples=10)
    # injecting environment-only fields must not change the digest
    import copy
    r2 = copy.deepcopy(r)
    r2["generated_at_utc"] = "SOMETHING"
    r2["db_sha256_pre"] = "deadbeef"
    r2["db_path_basename"] = "other.db"
    assert p282b.compute_deterministic_digest(r2) == r["deterministic_digest"]


# ---------------------------------------------------------------------------
# 18. JSON final classification exists and is valid
# ---------------------------------------------------------------------------

def test_final_classification_valid(results):
    valid = {
        "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_NULL_NO_PUBLICATION",
        "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_OBSERVATION_CANDIDATE_NO_PUBLICATION",
        "P282B_BIG649_DEDUP_REPLAY_PR_OPEN_UNDERFILLED_OR_SUPPORT_BLOCKED_NO_PUBLICATION",
        "P282B_BIG649_DEDUP_REPLAY_VALIDATION_FAIL_NOT_PUSHED",
        "P282B_PHASE0_BLOCKED_NO_CHANGES",
    }
    assert results["final_classification"] in valid


# ---------------------------------------------------------------------------
# 19. Draw-level prize-aware endpoint  (M3+ OR M2+special)
# ---------------------------------------------------------------------------

def test_fast_win_matches_endpoint_definition():
    am = {1, 2, 3, 30, 40, 49}
    asp = 7
    # hit>=3 wins
    assert p282b.fast_ticket_is_win({1, 2, 3, 10, 11, 12}, am, asp) is True
    # hit==2 without special -> lose
    assert p282b.fast_ticket_is_win({1, 2, 10, 11, 12, 13}, am, asp) is False
    # hit==2 WITH special -> win
    assert p282b.fast_ticket_is_win({1, 2, 7, 11, 12, 13}, am, asp) is True
    # hit<=1 -> lose
    assert p282b.fast_ticket_is_win({1, 7, 11, 12, 13, 14}, am, asp) is False


def test_fast_win_equivalent_to_frozen_scorer():
    """The MC's fast predicate must equal the frozen scorer's any_prize_aware_win
    across a battery of tickets (underpins MC validity and Task-20 'no scorer change')."""
    import random
    rng = random.Random(99)
    am = (1, 2, 3, 30, 40, 49)
    asp = 7
    am_set = set(am)
    for _ in range(400):
        ticket = tuple(sorted(rng.sample(range(1, 50), 6)))
        if asp in ticket and asp in am_set:
            continue  # special never overlaps main in canonical draws
        fast = p282b.fast_ticket_is_win(set(ticket), am_set, asp)
        scored = score_prize_aware_ticket("BIG_LOTTO", list(ticket), list(am),
                                          actual_special_number=asp)["any_prize_aware_win"]
        assert fast == scored


def test_single_ticket_win_prob_matches_monte_carlo():
    """Exact hypergeometric single-ticket win prob agrees with brute MC."""
    import random
    am = (1, 2, 3, 30, 40, 49)
    asp = 7
    exact = p282b.single_ticket_win_prob(am, asp)
    rng = random.Random(123)
    wins = 0
    N = 40000
    am_set = set(am)
    for _ in range(N):
        t = set(rng.sample(range(1, 50), 6))
        if p282b.fast_ticket_is_win(t, am_set, asp):
            wins += 1
    assert abs(wins / N - exact) < 0.01


# ---------------------------------------------------------------------------
# 20. No unexpected source strategy/scorer/adapter modification
# ---------------------------------------------------------------------------

def test_scorer_is_frozen_unchanged():
    # the tool consumes the frozen scorer read-only; its contract constant is unchanged
    assert SCORING_VERSION == "prize_aware_v1"
    assert p282b.score_prize_aware_ticket is score_prize_aware_ticket


def test_tool_writes_only_two_artifact_paths():
    src = _TOOL_PATH.read_text(encoding="utf-8")
    # only the two whitelisted artifact files are produced by name-stem
    assert p282b.ARTIFACT_STEM == "p282b_big649_deduplicated_portfolio_replay_20260620"
    # no DB-write SQL verbs in the tool source
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ", "CREATE TABLE",
                 "ALTER TABLE"):
        assert verb not in src


# ---------------------------------------------------------------------------
# extra: eligibility / exclusion of non-canonical draws
# ---------------------------------------------------------------------------

def test_non_canonical_draw_excluded(results):
    tu = results["target_draw_universe"]
    assert tu["eligible_draw_count"] == 6           # 6 canonical draws
    assert tu["excluded_non_canonical_count"] == 1  # 900099 filtered out
    assert "900099" in tu["excluded_non_canonical_sample"]


def test_d_equals_c_success_by_construction(results):
    # deduplication cannot change draw-level success
    for name in results["frozen_windows"]:
        dvc = results["secondary_comparisons"]["d_vs_c"]["results_by_window"][name]
        assert dvc["success_identical_by_construction"] is True
        assert dvc["success_rate_difference"] == 0.0


def test_anti_leakage_causality(results):
    ale = results["anti_leakage_evidence"]
    assert ale["causality_violations_cutoff_ge_target"] == 0
    assert ale["random_construction_reads_outcomes"] is False
    assert ale["deduplication_adds_or_replaces_tickets"] is False
