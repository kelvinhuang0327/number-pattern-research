"""
tests/test_p29_policy_sensitivity_simulator.py

Unit tests for P29 policy sensitivity simulator.
"""
import textwrap
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from wbc_backend.recommendation.p29_density_expansion_contract import (
    P29PolicySensitivityCandidate,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
)
from wbc_backend.recommendation.p29_policy_sensitivity_simulator import (
    DEFAULT_POLICY_GRID,
    _build_policy_id,
    compute_gate_reason_distribution,
    rank_policy_candidates,
    simulate_policy_density_on_true_date_slices,
    summarize_policy_candidate,
)

# ---------------------------------------------------------------------------
# Slice fixture — 10 rows spanning two dates
# ---------------------------------------------------------------------------

_SLICE_CSV = textwrap.dedent("""\
    ledger_id,recommendation_id,game_id,date,side,p_model,p_market,edge,odds_decimal,paper_stake_fraction,paper_stake_units,policy_id,strategy_policy,gate_decision,gate_reason,paper_only,production_ready,source_phase,created_from,y_true,settlement_status,settlement_reason,pnl_units,roi,is_win,is_loss,is_push,risk_profile_max_drawdown,risk_profile_sharpe,risk_profile_n_bets
    1,r1,g1,2025-05-08,home,0.58,0.50,0.08,1.90,0.008,0.008,pol,pol,ELIGIBLE,P16_6_ELIGIBLE_PAPER_RECOMMENDATION,True,False,p25,p25,1.0,settled,win,0.072,0.90,True,False,False,0.0,1.0,1
    2,r2,g2,2025-05-08,away,0.55,0.50,0.05,3.50,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX,True,False,p25,p25,0.0,settled,loss,0.0,0.0,False,True,False,0.0,0.0,1
    3,r3,g3,2025-05-08,home,0.52,0.50,0.02,2.10,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD,True,False,p25,p25,1.0,settled,win,0.0,0.0,False,False,False,0.0,0.0,1
    4,r4,g4,2025-05-09,home,0.57,0.50,0.07,2.00,0.007,0.007,pol,pol,ELIGIBLE,P16_6_ELIGIBLE_PAPER_RECOMMENDATION,True,False,p25,p25,0.0,settled,loss,-0.007,-1.0,False,True,False,0.0,0.0,1
    5,r5,g5,2025-05-09,away,0.45,0.50,-0.05,2.20,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD,True,False,p25,p25,1.0,settled,win,0.0,0.0,False,False,False,0.0,0.0,1
""")


@pytest.fixture
def tmp_p25_dir(tmp_path: Path) -> Path:
    p25 = tmp_path / "p25"
    for date_name in ["2025-05-08", "2025-05-09"]:
        slices = p25 / "true_date_slices" / date_name
        slices.mkdir(parents=True)
        # Write date-specific rows
        rows = [
            line for line in _SLICE_CSV.strip().splitlines()
            if date_name in line or line.startswith("ledger_id")
        ]
        (slices / "p15_true_date_input.csv").write_text("\n".join(rows) + "\n")
    return p25


# ---------------------------------------------------------------------------
# _build_policy_id
# ---------------------------------------------------------------------------


def test_build_policy_id_formats() -> None:
    pid = _build_policy_id(0.05, 2.50, 0.0025, 0.10)
    assert isinstance(pid, str)
    assert len(pid) > 0


def test_build_policy_id_inf_odds() -> None:
    pid = _build_policy_id(0.02, 999.0, 0.001, 0.05)
    assert "inf" in pid


# ---------------------------------------------------------------------------
# simulate_policy_density_on_true_date_slices
# ---------------------------------------------------------------------------


def test_simulate_returns_list(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    assert isinstance(results, list)
    assert len(results) > 0


def test_simulate_all_candidates_paper_only(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    for c in results:
        assert c.paper_only is True
        assert c.production_ready is False


def test_simulate_all_candidates_exploratory(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    for c in results:
        assert c.exploratory_only is True
        assert c.is_deployment_ready is False


def test_simulate_sorted_desc(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    n_actives = [c.n_active_entries for c in results]
    assert n_actives == sorted(n_actives, reverse=True)


def test_simulate_number_of_candidates(tmp_p25_dir: Path) -> None:
    grid = DEFAULT_POLICY_GRID
    expected = (
        len(grid["edge_threshold"])
        * len(grid["odds_decimal_max"])
        * len(grid["max_stake_cap"])
        * len(grid["kelly_fraction"])
    )
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    assert len(results) == expected


def test_simulate_missing_dir(tmp_path: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_path / "nonexistent")
    assert results == []


def test_simulate_looser_policy_gets_more_entries(tmp_p25_dir: Path) -> None:
    """Loosening edge threshold should not reduce active entries."""
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    # The most restrictive policy (edge=0.05, odds=2.50) should have fewest active entries
    strict = [c for c in results if c.edge_threshold == 0.05 and c.odds_decimal_max == 2.50]
    loose = [c for c in results if c.edge_threshold == 0.02 and c.odds_decimal_max >= 999]
    if strict and loose:
        assert strict[0].n_active_entries <= loose[0].n_active_entries


# ---------------------------------------------------------------------------
# compute_gate_reason_distribution
# ---------------------------------------------------------------------------


def test_compute_gate_reason_distribution_basic() -> None:
    df = pd.DataFrame({
        "gate_reason": ["P16_6_ELIGIBLE_PAPER_RECOMMENDATION", "P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD"],
        "edge": [0.07, 0.02],
        "odds_decimal": [2.0, 2.0],
    })
    policy = {"edge_threshold": 0.05, "odds_decimal_max": 2.50}
    result = compute_gate_reason_distribution(df, policy)
    # Only the edge=0.07 row passes
    assert "P16_6_ELIGIBLE_PAPER_RECOMMENDATION" in result


def test_compute_gate_reason_distribution_empty() -> None:
    result = compute_gate_reason_distribution(pd.DataFrame(), {"edge_threshold": 0.05, "odds_decimal_max": 2.50})
    assert result == {}


# ---------------------------------------------------------------------------
# summarize_policy_candidate
# ---------------------------------------------------------------------------


def test_summarize_policy_candidate_empty() -> None:
    result = summarize_policy_candidate([])
    assert result["n_candidates_tested"] == 0
    assert result["best_candidate_policy_id"] is None


def test_summarize_policy_candidate_basic(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    summary = summarize_policy_candidate(results)
    assert summary["n_candidates_tested"] == len(results)
    assert isinstance(summary["best_candidate_n_active"], int)


# ---------------------------------------------------------------------------
# rank_policy_candidates
# ---------------------------------------------------------------------------


def test_rank_policy_candidates_targets_first(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    ranked = rank_policy_candidates(results)
    # Candidates reaching target should come first (if any)
    reaches_target = [c for c in ranked if c.n_active_entries >= TARGET_ACTIVE_ENTRIES_DEFAULT]
    no_target = [c for c in ranked if c.n_active_entries < TARGET_ACTIVE_ENTRIES_DEFAULT]
    if reaches_target and no_target:
        first_no_target_idx = ranked.index(no_target[0])
        last_reaches_idx = ranked.index(reaches_target[-1])
        assert last_reaches_idx < first_no_target_idx


def test_rank_policy_candidates_all_are_candidates(tmp_p25_dir: Path) -> None:
    results = simulate_policy_density_on_true_date_slices(tmp_p25_dir)
    ranked = rank_policy_candidates(results)
    assert all(isinstance(c, P29PolicySensitivityCandidate) for c in ranked)
    assert len(ranked) == len(results)
