"""
tests/test_p29_density_diagnosis_analyzer.py

Unit tests for P29 density diagnosis analyzer.
"""
import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p29_density_diagnosis_analyzer import (
    compute_available_row_coverage,
    compute_current_density,
    compute_gate_reason_distribution,
    diagnose_density_gap,
    identify_zero_active_dates,
    load_p25_true_date_slices,
    load_p27_date_results,
    summarize_density_diagnosis,
)
from wbc_backend.recommendation.p29_density_expansion_contract import P29DensityDiagnosis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DATE_RESULTS_CSV = textwrap.dedent("""\
    run_date,n_active_paper_entries,total_pnl_units,total_stake_units,roi_units,blocker_reason,paper_only,production_ready
    2025-05-08,1,0.15,0.25,0.60,,True,False
    2025-05-09,3,0.30,0.75,0.40,,True,False
    2025-05-10,0,0.00,0.00,0.00,BLOCKED,True,False
    2025-05-11,2,0.10,0.50,0.20,,True,False
""")

_SLICE_CSV = textwrap.dedent("""\
    ledger_id,recommendation_id,game_id,date,side,p_model,p_market,edge,odds_decimal,paper_stake_fraction,paper_stake_units,policy_id,strategy_policy,gate_decision,gate_reason,paper_only,production_ready,source_phase,created_from,y_true,settlement_status,settlement_reason,pnl_units,roi,is_win,is_loss,is_push,risk_profile_max_drawdown,risk_profile_sharpe,risk_profile_n_bets
    1,r1,g1,2025-05-08,home,0.55,0.48,0.07,2.10,0.007,0.007,pol,pol,ELIGIBLE,P16_6_ELIGIBLE_PAPER_RECOMMENDATION,True,False,p25,p25,1.0,settled,win,0.077,0.60,True,False,False,0.1,0.5,1
    2,r2,g2,2025-05-08,away,0.45,0.52,-0.07,2.20,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_EDGE_BELOW_P18_THRESHOLD,True,False,p25,p25,0.0,settled,loss,0.0,0.0,False,True,False,0.1,0.5,1
    3,r3,g3,2025-05-08,home,0.55,0.50,0.05,3.00,0.0,0.0,pol,pol,BLOCKED,P16_6_BLOCKED_ODDS_ABOVE_POLICY_MAX,True,False,p25,p25,0.0,settled,loss,0.0,0.0,False,True,False,0.1,0.5,1
""")


@pytest.fixture
def tmp_p27_dir(tmp_path: Path) -> Path:
    dr = tmp_path / "p27"
    dr.mkdir()
    (dr / "date_results.csv").write_text(_DATE_RESULTS_CSV)
    return dr


@pytest.fixture
def tmp_p25_dir(tmp_path: Path) -> Path:
    p25 = tmp_path / "p25"
    slices = p25 / "true_date_slices" / "2025-05-08"
    slices.mkdir(parents=True)
    (slices / "p15_true_date_input.csv").write_text(_SLICE_CSV)
    return p25


# ---------------------------------------------------------------------------
# load_p27_date_results
# ---------------------------------------------------------------------------


def test_load_p27_date_results(tmp_p27_dir: Path) -> None:
    df = load_p27_date_results(tmp_p27_dir / "date_results.csv")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4
    assert "n_active_paper_entries" in df.columns


def test_load_p27_date_results_missing(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, Exception)):
        load_p27_date_results(tmp_path / "nonexistent.csv")


# ---------------------------------------------------------------------------
# load_p25_true_date_slices
# ---------------------------------------------------------------------------


def test_load_p25_true_date_slices(tmp_p25_dir: Path) -> None:
    df = load_p25_true_date_slices(tmp_p25_dir)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert "gate_reason" in df.columns


def test_load_p25_true_date_slices_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_p25_true_date_slices(tmp_path / "nonexistent")


def test_load_p25_true_date_slices_empty_dir(tmp_path: Path) -> None:
    p25 = tmp_path / "p25"
    (p25 / "true_date_slices").mkdir(parents=True)
    df = load_p25_true_date_slices(p25)
    assert df.empty


# ---------------------------------------------------------------------------
# compute_current_density
# ---------------------------------------------------------------------------


def test_compute_current_density_basic(tmp_p27_dir: Path) -> None:
    df = load_p27_date_results(tmp_p27_dir / "date_results.csv")
    result = compute_current_density(df)
    assert result["total_active_entries"] == 6  # 1+3+0+2
    assert result["n_days"] == 4
    assert result["active_per_day_mean"] == pytest.approx(1.5)


def test_compute_current_density_empty() -> None:
    result = compute_current_density(pd.DataFrame())
    assert result["total_active_entries"] == 0
    assert result["n_days"] == 0


# ---------------------------------------------------------------------------
# compute_available_row_coverage
# ---------------------------------------------------------------------------


def test_compute_available_row_coverage(tmp_p25_dir: Path) -> None:
    result = compute_available_row_coverage(tmp_p25_dir)
    assert result["total_source_rows"] == 3
    assert result["n_active_eligible"] == 1
    assert result["n_blocked_edge"] == 1
    assert result["n_blocked_odds"] == 1


def test_compute_available_row_coverage_missing_dir(tmp_path: Path) -> None:
    result = compute_available_row_coverage(tmp_path / "nonexistent")
    assert result["total_source_rows"] == 0


# ---------------------------------------------------------------------------
# diagnose_density_gap
# ---------------------------------------------------------------------------


def test_diagnose_density_gap_basic() -> None:
    result = diagnose_density_gap(324, 1500)
    assert result["density_gap"] == 1176
    assert result["required_lift_pct"] == pytest.approx(363.0, abs=1.0)


def test_diagnose_density_gap_zero() -> None:
    result = diagnose_density_gap(0, 1500)
    assert result["density_gap"] == 1500
    assert result["required_lift_pct"] == float("inf")


def test_diagnose_density_gap_already_reached() -> None:
    result = diagnose_density_gap(2000, 1500)
    assert result["density_gap"] == 0


# ---------------------------------------------------------------------------
# identify_zero_active_dates
# ---------------------------------------------------------------------------


def test_identify_zero_active_dates(tmp_p27_dir: Path) -> None:
    df = load_p27_date_results(tmp_p27_dir / "date_results.csv")
    zeros = identify_zero_active_dates(df)
    assert "2025-05-10" in zeros


def test_identify_zero_active_dates_empty() -> None:
    result = identify_zero_active_dates(pd.DataFrame())
    assert result == []


# ---------------------------------------------------------------------------
# compute_gate_reason_distribution
# ---------------------------------------------------------------------------


def test_compute_gate_reason_distribution(tmp_p25_dir: Path) -> None:
    df = load_p25_true_date_slices(tmp_p25_dir)
    dist = compute_gate_reason_distribution(df)
    assert "P16_6_ELIGIBLE_PAPER_RECOMMENDATION" in dist
    assert dist["P16_6_ELIGIBLE_PAPER_RECOMMENDATION"] == 1


def test_compute_gate_reason_distribution_empty() -> None:
    result = compute_gate_reason_distribution(pd.DataFrame())
    assert result == {}


# ---------------------------------------------------------------------------
# summarize_density_diagnosis
# ---------------------------------------------------------------------------


def test_summarize_density_diagnosis(tmp_p27_dir: Path, tmp_p25_dir: Path) -> None:
    df = load_p27_date_results(tmp_p27_dir / "date_results.csv")
    diag = summarize_density_diagnosis(df, tmp_p25_dir, target_active_entries=1500)
    assert isinstance(diag, P29DensityDiagnosis)
    assert diag.paper_only is True
    assert diag.production_ready is False
    assert diag.target_active_entries == 1500
    assert diag.density_gap == max(0, 1500 - diag.current_active_entries)
    assert diag.primary_blocker in ("edge_threshold", "odds_cap", "no_source_rows", "unknown")
    assert diag.total_source_rows == 3
