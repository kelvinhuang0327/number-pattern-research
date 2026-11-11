"""
tests/test_p28_sample_density_analyzer.py

Unit tests for P28 sample density analyzer.
"""
import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p28_sample_density_analyzer import (
    compute_daily_sample_density,
    compute_segment_sample_density,
    identify_sparse_dates,
    identify_sparse_segments,
    load_p27_date_results,
    load_p27_segment_results,
    summarize_sample_density,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_date_df(rows: list[dict]) -> pd.DataFrame:
    """Create a minimal date_results-style DataFrame."""
    df = pd.DataFrame(rows)
    for col in ["n_active_paper_entries", "total_stake_units", "total_pnl_units",
                "roi_units", "hit_rate", "n_settled_win", "n_settled_loss",
                "n_unsettled", "segment_index"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "run_date" not in df.columns:
        df["run_date"] = "2025-05-08"
    return df


def _make_segment_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["segment_index", "total_active_entries", "total_settled_win",
                "total_settled_loss", "total_unsettled", "total_stake_units",
                "total_pnl_units"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "blocked" not in df.columns:
        df["blocked"] = False
    return df


# ---------------------------------------------------------------------------
# compute_daily_sample_density
# ---------------------------------------------------------------------------


def test_daily_density_basic():
    df = _make_date_df([
        {"run_date": "2025-05-08", "n_active_paper_entries": 4},
        {"run_date": "2025-05-09", "n_active_paper_entries": 6},
        {"run_date": "2025-05-10", "n_active_paper_entries": 2},
    ])
    result = compute_daily_sample_density(df)
    assert result["min"] == 2.0
    assert result["max"] == 6.0
    assert abs(result["mean"] - 4.0) < 1e-9
    assert len(result["per_day"]) == 3


def test_daily_density_empty():
    result = compute_daily_sample_density(pd.DataFrame())
    assert result["min"] == 0.0
    assert result["per_day"] == []


def test_daily_density_single_row():
    df = _make_date_df([{"run_date": "2025-05-08", "n_active_paper_entries": 5}])
    result = compute_daily_sample_density(df)
    assert result["min"] == 5.0
    assert result["max"] == 5.0
    assert result["std"] == 0.0


# ---------------------------------------------------------------------------
# compute_segment_sample_density
# ---------------------------------------------------------------------------


def test_segment_density_basic():
    df = _make_segment_df([
        {"segment_index": 0, "total_active_entries": 37},
        {"segment_index": 1, "total_active_entries": 29},
    ])
    result = compute_segment_sample_density(df)
    assert result["min"] == 29.0
    assert result["max"] == 37.0
    assert len(result["per_segment"]) == 2


def test_segment_density_empty():
    result = compute_segment_sample_density(pd.DataFrame())
    assert result["per_segment"] == []


# ---------------------------------------------------------------------------
# identify_sparse_dates
# ---------------------------------------------------------------------------


def test_identify_sparse_dates_zero_active():
    df = _make_date_df([
        {"run_date": "2025-07-14", "n_active_paper_entries": 0},
        {"run_date": "2025-05-08", "n_active_paper_entries": 5},
        {"run_date": "2025-05-09", "n_active_paper_entries": 0},
    ])
    sparse = identify_sparse_dates(df, min_active_per_day=1)
    assert "2025-07-14" in sparse
    assert "2025-05-09" in sparse
    assert "2025-05-08" not in sparse
    assert sparse == sorted(sparse)


def test_identify_sparse_dates_none():
    df = _make_date_df([
        {"run_date": "2025-05-08", "n_active_paper_entries": 5},
        {"run_date": "2025-05-09", "n_active_paper_entries": 3},
    ])
    sparse = identify_sparse_dates(df)
    assert sparse == []


def test_identify_sparse_dates_empty_df():
    sparse = identify_sparse_dates(pd.DataFrame())
    assert sparse == []


# ---------------------------------------------------------------------------
# identify_sparse_segments
# ---------------------------------------------------------------------------


def test_identify_sparse_segments():
    df = _make_segment_df([
        {"segment_index": 0, "date_start": "2025-05-08", "date_end": "2025-05-21", "total_active_entries": 37},
        {"segment_index": 10, "date_start": "2025-09-25", "date_end": "2025-09-28", "total_active_entries": 8},
    ])
    sparse = identify_sparse_segments(df, min_active_per_segment=50)
    # Both < 50
    assert any("seg0" in s for s in sparse)
    assert any("seg10" in s for s in sparse)


def test_identify_sparse_segments_none():
    df = _make_segment_df([
        {"segment_index": 0, "date_start": "2025-05-08", "date_end": "2025-05-21", "total_active_entries": 100},
    ])
    sparse = identify_sparse_segments(df, min_active_per_segment=50)
    assert sparse == []


def test_identify_sparse_segments_empty():
    assert identify_sparse_segments(pd.DataFrame()) == []


# ---------------------------------------------------------------------------
# summarize_sample_density
# ---------------------------------------------------------------------------


def test_summarize_sample_density_below_advisory():
    date_df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "n_active_paper_entries": 2}
        for i in range(8, 18)
    ])
    seg_df = _make_segment_df([
        {"segment_index": 0, "date_start": "2025-05-08", "date_end": "2025-05-21",
         "total_active_entries": 20},
    ])
    profile = summarize_sample_density(
        date_df, seg_df,
        n_dates_total=144, n_dates_ready=140, n_dates_blocked=4,
        min_sample_size=1500,
    )
    assert profile.paper_only is True
    assert profile.production_ready is False
    assert profile.sample_size_pass is False
    assert profile.total_active_entries == 20  # 10 rows × 2 each
    assert profile.min_sample_size_advisory == 1500


def test_summarize_sample_density_above_advisory():
    date_df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "n_active_paper_entries": 15}
        for i in range(8, 18)
    ])
    seg_df = _make_segment_df([
        {"segment_index": 0, "date_start": "2025-05-08", "date_end": "2025-05-21",
         "total_active_entries": 150},
    ])
    profile = summarize_sample_density(
        date_df, seg_df,
        n_dates_total=10, n_dates_ready=10, n_dates_blocked=0,
        min_sample_size=100,
    )
    assert profile.sample_size_pass is True


# ---------------------------------------------------------------------------
# load functions (integration with tmp files)
# ---------------------------------------------------------------------------


def test_load_p27_date_results(tmp_path):
    csv = textwrap.dedent("""\
        run_date,n_active_paper_entries,n_settled_win,n_settled_loss,roi_units,hit_rate,total_stake_units,total_pnl_units,segment_index
        2025-05-08,5,3,2,0.1,0.6,1.25,0.125,0
    """)
    p = tmp_path / "date_results.csv"
    p.write_text(csv)
    df = load_p27_date_results(p)
    assert len(df) == 1
    assert df["n_active_paper_entries"].iloc[0] == 5.0


def test_load_p27_segment_results(tmp_path):
    csv = textwrap.dedent("""\
        segment_index,date_start,date_end,p26_gate,blocked,returncode,total_active_entries,total_settled_win,total_settled_loss,total_unsettled,total_stake_units,total_pnl_units
        0,2025-05-08,2025-05-21,P26_READY,False,0,37,17,20,0,9.25,-0.331
    """)
    p = tmp_path / "segment_results.csv"
    p.write_text(csv)
    df = load_p27_segment_results(p)
    assert len(df) == 1
    assert df["total_active_entries"].iloc[0] == 37.0
    assert df["blocked"].iloc[0] == False  # noqa: E712 — np.False_ != False (identity)
