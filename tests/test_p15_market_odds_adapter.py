"""Tests for P15 MarketOddsJoinAdapter (wbc_backend/simulation/market_odds_adapter.py)."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.simulation.market_odds_adapter import (
    JOIN_STATUS_INVALID_ODDS,
    JOIN_STATUS_JOINED,
    JOIN_STATUS_MISSING,
    MarketOddsJoinAdapter,
    american_to_decimal_odds,
    american_to_implied_probability,
    build_game_key,
    decimal_to_implied_probability,
    normalize_team_name,
    parse_american_odds_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_csv(tmp_path: Path, n_rows: int = 40) -> Path:
    """Create a minimal source CSV with 40 rows and required columns."""
    import numpy as np

    rng = np.random.default_rng(seed=42)
    dates = pd.date_range("2025-04-01", periods=n_rows, freq="D")
    home_wins = rng.integers(0, 2, size=n_rows).tolist()
    away_scores = [2 if hw == 0 else 1 for hw in home_wins]
    home_scores = [3 if hw == 1 else 0 for hw in home_wins]

    df = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Home": [f"Team_H_{i}" for i in range(n_rows)],
        "Away": [f"Team_A_{i}" for i in range(n_rows)],
        "Home Score": home_scores,
        "Away Score": away_scores,
        "Away ML": ["+150"] * n_rows,
        "Home ML": ["-180"] * n_rows,
        "game_id": [f"2025-04-{i:02d}_H{i}_A{i}" for i in range(n_rows)],
        "indep_recent_win_rate_delta": rng.uniform(-0.3, 0.3, size=n_rows),
        "indep_starter_era_delta": rng.uniform(-2.0, 2.0, size=n_rows),
    })
    p = tmp_path / "variant_no_rest.csv"
    df.to_csv(p, index=False)
    return p


def _make_oof_df(n_folds: int = 5, rows_per_fold: int = 7) -> pd.DataFrame:
    """Minimal OOF DF aligned to the synthetic source CSV boundaries."""
    import numpy as np

    rng = np.random.default_rng(seed=7)
    # Re-compute boundaries for n=40, n_folds=5
    n = 40
    boundaries = [int(round(n * k / (n_folds + 1))) for k in range(n_folds + 2)]

    fold_ids, y_trues, p_oofs = [], [], []
    for fi in range(n_folds):
        fid = fi + 1
        size = boundaries[fi + 2] - boundaries[fi + 1]
        fold_ids.extend([fid] * size)
        y_trues.extend(rng.integers(0, 2, size=size).tolist())
        p_oofs.extend(rng.uniform(0.4, 0.7, size=size).tolist())

    return pd.DataFrame({
        "y_true": y_trues,
        "p_oof": p_oofs,
        "fold_id": fold_ids,
        "source_model": "p13_walk_forward_logistic",
        "source_bss_oof": 0.008253,
        "paper_only": True,
    })


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestNormalizeTeamName:
    def test_lowercase_strips(self):
        assert normalize_team_name("  Kansas City Royals  ") == "kansas city royals"

    def test_removes_punctuation(self):
        assert normalize_team_name("Los Angeles Dodgers!") == "los angeles dodgers"

    def test_collapses_whitespace(self):
        assert normalize_team_name("New   York  Yankees") == "new york yankees"

    def test_non_string_returns_empty(self):
        assert normalize_team_name(None) == ""  # type: ignore[arg-type]


class TestBuildGameKey:
    def test_deterministic(self):
        k1 = build_game_key("2025-05-08", "Kansas City Royals", "Chicago White Sox")
        k2 = build_game_key("2025-05-08", "Kansas City Royals", "Chicago White Sox")
        assert k1 == k2

    def test_format(self):
        k = build_game_key("2025-05-08", "Boston Red Sox", "Texas Rangers")
        assert k == "2025-05-08|boston red sox|texas rangers"


class TestAmericanToDecimalOdds:
    def test_negative_american(self):
        # -150 → 1 + 100/150 ≈ 1.6667
        result = american_to_decimal_odds(-150)
        assert abs(result - 1.666667) < 0.001

    def test_positive_american(self):
        # +130 → 1 + 130/100 = 2.30
        result = american_to_decimal_odds(130)
        assert abs(result - 2.30) < 0.001

    def test_plus_100(self):
        assert abs(american_to_decimal_odds(100) - 2.0) < 0.001

    def test_minus_100(self):
        assert abs(american_to_decimal_odds(-100) - 2.0) < 0.001

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            american_to_decimal_odds(0)


class TestDecimalToImpliedProbability:
    def test_even_odds(self):
        assert abs(decimal_to_implied_probability(2.0) - 0.5) < 0.001

    def test_heavy_favourite(self):
        # -300 → decimal = 1 + 100/300 ≈ 1.3333 → p ≈ 0.75
        dec = american_to_decimal_odds(-300)
        p = decimal_to_implied_probability(dec)
        assert abs(p - 0.75) < 0.01

    def test_invalid_decimal_raises(self):
        with pytest.raises(ValueError):
            decimal_to_implied_probability(0.5)

    def test_invalid_one_raises(self):
        with pytest.raises(ValueError):
            decimal_to_implied_probability(1.0)


class TestAmericanToImpliedProbability:
    def test_heavy_fav(self):
        p = american_to_implied_probability(-200)
        assert abs(p - (1 / (1 + 100 / 200))) < 0.001

    def test_underdog(self):
        p = american_to_implied_probability(200)
        assert p < 0.35


class TestParseAmericanOddsString:
    def test_plus_string(self):
        assert parse_american_odds_string("+130") == 130.0

    def test_minus_string(self):
        assert parse_american_odds_string("-150") == -150.0

    def test_bare_number(self):
        assert parse_american_odds_string("200") == 200.0

    def test_none_returns_none(self):
        assert parse_american_odds_string(None) is None

    def test_nan_returns_none(self):
        import math
        assert parse_american_odds_string(float("nan")) is None

    def test_invalid_string_returns_none(self):
        assert parse_american_odds_string("n/a") is None

    def test_integer_input(self):
        assert parse_american_odds_string(-180) == -180.0


# ---------------------------------------------------------------------------
# MarketOddsJoinAdapter
# ---------------------------------------------------------------------------

class TestMarketOddsJoinAdapter:
    def test_positional_join_all_folds_match(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        # Should return same number of rows as OOF
        assert len(joined) == len(oof_df)

    def test_joined_status_filled(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        assert (joined["odds_join_status"] == JOIN_STATUS_JOINED).all()

    def test_odds_columns_present(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        for col in ["p_market", "odds_decimal_home", "edge", "game_id"]:
            assert col in joined.columns, f"Missing column: {col}"

    def test_p_market_values_valid(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        p_market = joined[joined["odds_join_status"] == JOIN_STATUS_JOINED]["p_market"].astype(float)
        assert (p_market > 0.0).all()
        assert (p_market < 1.0).all()

    def test_edge_is_p_oof_minus_p_market(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        joined_rows = joined[joined["odds_join_status"] == JOIN_STATUS_JOINED]
        for _, row in joined_rows.head(10).iterrows():
            expected = round(float(row["p_oof"]) - float(row["p_market"]), 6)
            assert abs(float(row["edge"]) - expected) < 1e-5

    def test_join_report_coverage_100(self, tmp_path):
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        adapter.join_with_p13_oof(oof_df)
        report = adapter.join_report()
        assert report["coverage_pct"] == 100.0
        assert report["joined"] == len(oof_df)
        assert report["missing"] == 0

    def test_file_not_found_raises(self, tmp_path):
        adapter = MarketOddsJoinAdapter(source_csv_path=str(tmp_path / "no_file.csv"))
        oof_df = _make_oof_df()
        with pytest.raises(FileNotFoundError):
            adapter.join_with_p13_oof(oof_df)

    def test_fold_count_mismatch_raises(self, tmp_path):
        """If OOF has wrong row count in a fold, adapter should raise ValueError."""
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        # Remove one row from fold 1 to cause mismatch
        bad_oof = oof_df[~((oof_df["fold_id"] == 1) & (oof_df.index == oof_df[oof_df["fold_id"] == 1].index[0]))].copy()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        with pytest.raises(ValueError, match="Fold 1"):
            adapter.join_with_p13_oof(bad_oof)

    def test_missing_odds_produces_missing_status(self, tmp_path):
        """Rows with NaN odds should get MISSING status."""
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        # Corrupt Home ML for some rows
        df = pd.read_csv(src_csv)
        df.loc[0:4, "Home ML"] = None
        df.to_csv(src_csv, index=False)

        oof_df = _make_oof_df()
        adapter = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        joined = adapter.join_with_p13_oof(oof_df)
        # Rows with None odds → INVALID_ODDS or MISSING
        bad = joined[joined["odds_join_status"].isin([JOIN_STATUS_INVALID_ODDS, JOIN_STATUS_MISSING])]
        assert len(bad) > 0

    def test_deterministic_repeated_call(self, tmp_path):
        """Two identical calls should produce identical DataFrames."""
        src_csv = _make_source_csv(tmp_path, n_rows=40)
        oof_df = _make_oof_df()
        adapter1 = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        j1 = adapter1.join_with_p13_oof(oof_df)

        adapter2 = MarketOddsJoinAdapter(source_csv_path=str(src_csv))
        j2 = adapter2.join_with_p13_oof(oof_df)

        pd.testing.assert_frame_equal(
            j1[["game_id", "p_market", "edge", "odds_join_status"]].reset_index(drop=True),
            j2[["game_id", "p_market", "edge", "odds_join_status"]].reset_index(drop=True),
        )
