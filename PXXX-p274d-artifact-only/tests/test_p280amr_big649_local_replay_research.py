"""Focused tests for the P280AM-R BIG 6/49 local replay research module.

These tests use synthetic draws and the merged P280AJ no-DB adapter; they never
write/copy the production DB, perform a publication, or look up an official
target/deadline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import tools.p280amr_big649_local_replay_research as mod
from tools.big649_no_db_strategy_output_adapter import (
    generate_strategy_outputs_no_db,
    list_frozen_big649_strategy_ids,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "tools" / "p280amr_big649_local_replay_research.py"


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------
def _synthetic_draws(count: int) -> list[dict]:
    """Deterministic synthetic canonical-style draws (six distinct 1..49 + special)."""
    draws = []
    for i in range(count):
        base = i % 40
        nums = sorted({((base + j * 7) % 49) + 1 for j in range(6)})
        while len(nums) < 6:  # repair rare collisions
            nums = sorted(set(nums) | {((nums[-1]) % 49) + 1})
        nums = sorted(nums)[:6]
        special = ((base + 13) % 49) + 1
        if special in nums:
            special = (special % 49) + 1
        year = 96 + i // 100
        seq = i % 100 + 1
        draws.append(
            {
                "draw": f"{year}{seq:06d}",
                "draw_int": int(f"{year}{seq:06d}"),
                "date": f"{2007 + i // 100}/{(i % 12) + 1:02d}/{(i % 28) + 1:02d}",
                "numbers": nums,
                "special": special,
            }
        )
    # enforce strictly increasing date+draw ordering for the gate
    for idx, row in enumerate(draws):
        row["date"] = f"2007/01/01+{idx:05d}"
    draws.sort(key=lambda r: (r["date"], r["draw_int"]))
    return draws


# ---------------------------------------------------------------------------
# Scoring correctness
# ---------------------------------------------------------------------------
def test_score_ticket_hit_and_special():
    actual = [1, 2, 3, 10, 20, 30]
    special = 40
    s = mod.score_ticket([1, 2, 3, 41, 42, 43], actual, special)
    assert s["hit_count"] == 3 and s["special_hit"] == 0 and s["prize_aware_win"] is True


def test_prize_aware_win_two_plus_special():
    actual = [1, 2, 3, 10, 20, 30]
    special = 40
    # exactly two main hits + special present -> win
    s = mod.score_ticket([1, 2, 40, 45, 46, 47], actual, special)
    assert s["hit_count"] == 2 and s["special_hit"] == 1 and s["prize_aware_win"] is True


def test_prize_aware_win_two_without_special_is_loss():
    actual = [1, 2, 3, 10, 20, 30]
    special = 40
    s = mod.score_ticket([1, 2, 44, 45, 46, 47], actual, special)
    assert s["hit_count"] == 2 and s["special_hit"] == 0 and s["prize_aware_win"] is False


def test_prize_aware_win_boundary_three():
    actual = [1, 2, 3, 10, 20, 30]
    s = mod.score_ticket([1, 2, 3, 44, 45, 46], actual, special=49)
    assert s["prize_aware_win"] is True
    s2 = mod.score_ticket([1, 44, 45, 46, 47, 48], actual, special=49)
    assert s2["hit_count"] == 1 and s2["prize_aware_win"] is False


def test_analytic_prize_probability_matches_brute_force():
    ap = mod.analytic_single_ticket_prize_prob()
    assert 0.030 < ap["p_prize_aware_win"] < 0.032
    assert abs(ap["p_hit_ge_3"] + ap["p_two_plus_special"] - ap["p_prize_aware_win"]) < 1e-12


# ---------------------------------------------------------------------------
# Dataset gate
# ---------------------------------------------------------------------------
def test_validate_dataset_accepts_clean_synthetic():
    draws = _synthetic_draws(600)
    info = mod.validate_dataset(draws)
    assert info["row_count"] == 600
    assert info["duplicate_draw_ids"] == 0 and info["duplicate_dates"] == 0
    assert info["ordering"] == "DATE_ORDER_EQUALS_DRAW_INT_ORDER"
    assert info["eligible_target_count"] == 600 - mod.MIN_HISTORY


def test_validate_dataset_rejects_duplicate_draw():
    draws = _synthetic_draws(600)
    draws[5]["draw"] = draws[4]["draw"]
    with pytest.raises(mod.ReplayDatasetError):
        mod.validate_dataset(draws)


def test_validate_dataset_rejects_ambiguous_ordering():
    draws = _synthetic_draws(600)
    # break draw-int vs date agreement
    draws[10]["draw_int"] = draws[-1]["draw_int"] + 1
    with pytest.raises(mod.ReplayDatasetError):
        mod.validate_dataset(draws)


def test_validate_dataset_rejects_insufficient_history():
    draws = _synthetic_draws(mod.MIN_HISTORY)  # need MIN_HISTORY + 1
    with pytest.raises(mod.ReplayDatasetError):
        mod.validate_dataset(draws)


def test_validate_dataset_rejects_bad_ticket():
    draws = _synthetic_draws(600)
    draws[3]["numbers"] = [1, 2, 3, 4, 5, 50]  # out of range
    with pytest.raises(mod.ReplayDatasetError):
        mod.validate_dataset(draws)


# ---------------------------------------------------------------------------
# Replay engine: leakage guards + adapter equivalence
# ---------------------------------------------------------------------------
def test_replay_history_strictly_before_target():
    draws = _synthetic_draws(mod.MIN_HISTORY + 5)
    target_index = mod.MIN_HISTORY + 2
    record = mod.replay_one_target(draws, target_index)
    assert record["history_len"] == target_index
    assert record["target_draw"] == draws[target_index]["draw"]
    # cutoff is the immediately preceding draw
    assert record["history_cutoff"] == draws[target_index - 1]["draw"]


def test_replay_target_not_in_history_input(monkeypatch):
    """The adapter must never receive the target outcome in its history input."""
    draws = _synthetic_draws(mod.MIN_HISTORY + 5)
    target_index = mod.MIN_HISTORY + 1
    target_id = draws[target_index]["draw"]

    captured = {}
    original = mod.enumerate_strategy_candidates

    def _spy(history, cutoff, target_metadata):
        captured["history_ids"] = [row.get("draw") for row in history]
        captured["target_metadata"] = dict(target_metadata)
        return original(history, cutoff, target_metadata)

    monkeypatch.setattr(mod, "enumerate_strategy_candidates", _spy)
    mod.replay_one_target(draws, target_index)
    assert target_id not in captured["history_ids"]
    # target_metadata carries no outcome fields
    assert set(captured["target_metadata"]) == {"target_draw", "synthetic"}
    assert captured["target_metadata"]["target_draw"] == target_id


def test_replay_rejects_too_little_history():
    draws = _synthetic_draws(mod.MIN_HISTORY + 5)
    with pytest.raises(mod.ReplayDatasetError):
        mod.replay_one_target(draws, mod.MIN_HISTORY - 1)


def test_remediated_matches_adapter_when_resolved():
    """Best-effort remediation equals the adapter's exact output when it resolves."""
    draws = _synthetic_draws(mod.MIN_HISTORY + 3)
    target_index = mod.MIN_HISTORY + 1
    record = mod.replay_one_target(draws, target_index)
    if record["remediated_resolution_status"] != mod.RESOLVED_STATUS:
        pytest.skip("synthetic target did not resolve to 11 unique (best-effort path)")
    history = [{"draw": r["draw"], "numbers": list(r["numbers"])} for r in draws[:target_index]]
    cutoff = draws[target_index - 1]["draw"]
    tm = {"target_draw": draws[target_index]["draw"], "synthetic": True}
    adapter_out = generate_strategy_outputs_no_db(history=history, history_cutoff=cutoff, target_metadata=tm)
    adapter_map = {o["strategy_id"]: o["predicted_main_numbers"] for o in adapter_out}
    replay_map = {row["strategy_id"]: row["ticket"] for row in record["remediated"]}
    assert replay_map == adapter_map


def test_exact_eleven_strategies():
    assert len(list_frozen_big649_strategy_ids()) == 11


# ---------------------------------------------------------------------------
# Portfolio + combination scoring
# ---------------------------------------------------------------------------
def test_score_portfolio_any_win_and_coverage():
    actual = [1, 2, 3, 10, 20, 30]
    special = 40
    tickets = [[1, 2, 3, 4, 5, 6], [44, 45, 46, 47, 48, 49]]
    sc = mod.score_portfolio(tickets, actual, special)
    assert sc["prize_aware_win"] is True  # first ticket has 3 hits
    assert sc["best_hit_count"] == 3
    assert sc["coverage"] == 12
    assert sc["duplicate_ticket_count"] == 0
    assert sc["budget"] == 2


def test_score_portfolio_counts_duplicate_tickets():
    actual = [1, 2, 3, 10, 20, 30]
    tickets = [[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]]
    sc = mod.score_portfolio(tickets, actual, special=40)
    assert sc["duplicate_ticket_count"] == 1


def test_diversity_greedy_minimizes_overlap_deterministic():
    tickets = [
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 5, 7],   # high overlap with #0
        [44, 45, 46, 47, 48, 49],  # disjoint from #0
    ]
    chosen = mod.diversity_greedy_select(tickets, 2)
    keys = sorted(tuple(t) for t in chosen)
    assert (1, 2, 3, 4, 5, 6) in keys and (44, 45, 46, 47, 48, 49) in keys
    # deterministic
    assert mod.diversity_greedy_select(tickets, 2) == chosen


def test_per_family_cap_one_per_family():
    remediated = [
        {"strategy_id": sid, "ticket": [1, 2, 3, 4, 5, 6]}
        for sid in list_frozen_big649_strategy_ids()
    ]
    chosen = mod.per_family_cap_select(remediated, cap=1)
    # one ticket per derived family; fewer than 11 strategies
    families = {mod.assign_family(sid) for sid in list_frozen_big649_strategy_ids()}
    assert len(chosen) == len(families)
    assert len(chosen) < 11


# ---------------------------------------------------------------------------
# Random baselines: deterministic seed + nesting
# ---------------------------------------------------------------------------
def test_equal_budget_random_deterministic_and_valid():
    a = mod.equal_budget_random_tickets("96000123", 0, 5)
    b = mod.equal_budget_random_tickets("96000123", 0, 5)
    assert a == b
    for ticket in a:
        assert len(ticket) == 6 and len(set(ticket)) == 6
        assert min(ticket) >= 1 and max(ticket) <= 49
    # different replicate -> different (almost surely)
    assert a != mod.equal_budget_random_tickets("96000123", 1, 5)


def test_equal_budget_random_nested_prefix():
    full = mod.equal_budget_random_tickets("96000123", 3, 11)
    assert mod.equal_budget_random_tickets("96000123", 3, 5) == full[:5]


def test_diversified_random_disjoint_and_nested():
    tickets = mod.diversified_random_tickets("96000123", 0, 7)
    # 7 tickets, k*6=42 <= 49 so all disjoint (zero overlap)
    union = set()
    for ticket in tickets:
        assert len(set(ticket) & union) == 0
        union |= set(ticket)
    assert mod.diversified_random_tickets("96000123", 0, 3) == tickets[:3]


def test_diversified_random_deterministic():
    assert mod.diversified_random_tickets("96000123", 2, 5) == mod.diversified_random_tickets("96000123", 2, 5)


# ---------------------------------------------------------------------------
# End-to-end build_report on synthetic DB (no production DB)
# ---------------------------------------------------------------------------
@pytest.fixture()
def synthetic_db(tmp_path) -> Path:
    import sqlite3

    db = tmp_path / "synthetic.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, draw TEXT, date TEXT, "
        "lottery_type TEXT, numbers TEXT, special INTEGER)"
    )
    con.execute(
        f"CREATE VIEW {mod.CANONICAL_VIEW} AS SELECT * FROM draws WHERE lottery_type='BIG_LOTTO'"
    )
    draws = _synthetic_draws(mod.MIN_HISTORY + 40)
    for row in draws:
        con.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?,?,?,?,?)",
            (row["draw"], row["date"], "BIG_LOTTO", json.dumps(row["numbers"]), row["special"]),
        )
    con.commit()
    con.close()
    return db


def test_build_report_end_to_end_and_deterministic(synthetic_db):
    r1 = mod.build_report(synthetic_db, max_targets=20)
    r2 = mod.build_report(synthetic_db, max_targets=20)
    assert r1["result_digest"] == r2["result_digest"]
    assert r1["task_id"] == "P280AM-R"
    assert r1["strategy_count"] == 11
    assert r1["exact_11_strategy_replay"] is True
    assert r1["database_access"]["written"] is False
    assert r1["database_access"]["copied"] is False
    assert r1["database_access"]["query_only_enabled"] is True
    assert r1["horizon_results"], "expected at least one horizon"


def test_build_report_governance_flags_false(synthetic_db):
    r = mod.build_report(synthetic_db, max_targets=15)
    for flag in (
        "prediction_success_claim",
        "strategy_promoted",
        "activation_authorized",
        "registry_mutated",
        "production_write",
        "real_publication_performed",
        "official_target_lookup",
        "official_deadline_lookup",
        "pre_draw_manifest_created",
        "publication_pr_created",
        "post_draw_evaluation_of_real_publication",
    ):
        assert r[flag] is False, flag
    assert r["research_only"] is True


def test_build_report_no_outcome_leak_in_metadata(synthetic_db, monkeypatch):
    seen = []
    original = mod.enumerate_strategy_candidates

    def _spy(history, cutoff, target_metadata):
        seen.append(dict(target_metadata))
        return original(history, cutoff, target_metadata)

    monkeypatch.setattr(mod, "enumerate_strategy_candidates", _spy)
    mod.build_report(synthetic_db, max_targets=10)
    assert seen
    for meta in seen:
        assert set(meta) <= {"target_draw", "synthetic"}


def test_markdown_renders(synthetic_db):
    r = mod.build_report(synthetic_db, max_targets=12)
    md = mod.render_markdown(r)
    assert "P280AM-R" in md and "Research-Only" in md
    assert "result_digest" in md


# ---------------------------------------------------------------------------
# Static safety scans of the script source
# ---------------------------------------------------------------------------
def _source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_no_db_write_or_copy_calls():
    src = _source()
    assert "mode=ro" in src
    for forbidden in ("shutil.copy", "INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ", "CREATE TABLE", "executemany"):
        assert forbidden not in src, forbidden


def test_no_network_or_deadline_lookup():
    src = _source()
    # no network libraries / lookup primitives (disclaimer flags naming "deadline"
    # are allowed and asserted separately)
    for forbidden in ("import requests", "import httpx", "urllib", "import socket", "urlopen", "http://", "https://"):
        assert forbidden not in src, forbidden
    assert '"official_deadline_lookup": False' in src
    assert '"official_target_lookup": False' in src


def test_no_publication_artifact_paths():
    src = _source()
    # no publication artifact write paths (disclaimer prose may mention the words)
    assert "outputs/publications" not in src
    assert "manifest.json" not in src
    assert "manifest.md" not in src
    assert "pre_draw/" not in src


def test_no_prediction_or_promotion_claims_in_source():
    src = _source().lower()
    # the script declares these flags as False; ensure no truthy claim slips in
    assert '"prediction_success_claim": false' in src or "prediction_success_claim\": false" in src
    for token in ("promoted = true", "activation_authorized = true"):
        assert token not in src
