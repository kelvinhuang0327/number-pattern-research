"""P15 Market Odds Adapter — deterministic join of P13 OOF predictions with historical market odds.

Join strategy:
  The P13 OOF CSV contains no game identifiers (y_true, p_oof, fold metadata only).
  The source training CSV (from which OOF rows were generated) contains Date, Home,
  Away, Away ML, Home ML, and game_id.  Because WalkForwardLogisticBaseline uses a
  deterministic sort-then-split algorithm, each OOF row maps exactly to a source row
  by positional offset within its fold window.

  This module re-runs the same fold boundary calculation and positionally aligns OOF
  rows back to source rows, then extracts American odds → decimal odds → p_market.

  No live network calls. No fabricated odds. Missing odds are preserved as MISSING.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OOF_FEATURES: list[str] = ["indep_recent_win_rate_delta", "indep_starter_era_delta"]
OOF_LABEL_COL: str = "home_win"
OOF_TIME_COL: str = "Date"
N_FOLDS: int = 5

JOIN_STATUS_JOINED: str = "JOINED"
JOIN_STATUS_MISSING: str = "MISSING"
JOIN_STATUS_INVALID_ODDS: str = "INVALID_ODDS"

_AMERICAN_POSITIVE_RE = re.compile(r"^\+?(\d+)$")
_AMERICAN_NEGATIVE_RE = re.compile(r"^-(\d+)$")


# ---------------------------------------------------------------------------
# Pure odds conversion utilities
# ---------------------------------------------------------------------------

def normalize_team_name(value: str) -> str:
    """Normalise a team name to a canonical lowercase slug.

    Strips leading/trailing whitespace, collapses internal whitespace,
    lowercases, and removes punctuation that may vary between sources.

    Args:
        value: Raw team name string.

    Returns:
        Normalised slug string, e.g. "los angeles dodgers".
    """
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    v = re.sub(r"[^a-z0-9 ]", " ", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def build_game_key(date: str, home_team: str, away_team: str) -> str:
    """Build a deterministic game key from date and team names.

    Args:
        date: ISO date string, e.g. "2025-05-08".
        home_team: Home team raw name.
        away_team: Away team raw name.

    Returns:
        Key like "2025-05-08|kansas city royals|chicago white sox".
    """
    d = str(date)[:10]
    h = normalize_team_name(home_team)
    a = normalize_team_name(away_team)
    return f"{d}|{h}|{a}"


def american_to_decimal_odds(american_odds: float) -> float:
    """Convert American moneyline odds to decimal odds.

    Args:
        american_odds: American odds value (e.g. -150, +130).

    Returns:
        Decimal odds (always >= 1.0).

    Raises:
        ValueError: If the value is 0 or cannot be converted.
    """
    v = float(american_odds)
    if v == 0.0:
        raise ValueError(f"American odds cannot be 0: {american_odds}")
    if v > 0:
        return round(1.0 + v / 100.0, 6)
    else:
        return round(1.0 + 100.0 / abs(v), 6)


def decimal_to_implied_probability(decimal_odds: float) -> float:
    """Convert decimal odds to raw implied probability (no vig removal).

    Args:
        decimal_odds: Decimal odds value (must be > 1.0).

    Returns:
        Implied probability in (0, 1).

    Raises:
        ValueError: If decimal_odds <= 1.0.
    """
    if decimal_odds <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {decimal_odds}")
    return round(1.0 / decimal_odds, 6)


def american_to_implied_probability(american_odds: float) -> float:
    """Convert American odds to raw implied probability.

    Args:
        american_odds: American odds value.

    Returns:
        Implied probability in (0, 1).
    """
    dec = american_to_decimal_odds(american_odds)
    return decimal_to_implied_probability(dec)


def parse_american_odds_string(raw: str | float | int) -> Optional[float]:
    """Parse American odds from a string like '+130', '-150', or '130'.

    Args:
        raw: Raw value from a CSV cell.

    Returns:
        Float odds or None if unparseable.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return None
    s = str(raw).strip()
    m_pos = _AMERICAN_POSITIVE_RE.match(s)
    if m_pos:
        v = float(m_pos.group(1))
        return v if s.startswith("+") else v  # treat bare number as positive
    m_neg = _AMERICAN_NEGATIVE_RE.match(s)
    if m_neg:
        return -float(m_neg.group(1))
    return None


# ---------------------------------------------------------------------------
# Core adapter class
# ---------------------------------------------------------------------------

class MarketOddsJoinAdapter:
    """Attach historical market odds to P13 OOF predictions via positional join.

    Join algorithm:
      1. Load the original source CSV (same file used to train P13).
      2. Apply identical NaN-drop and sort used by WalkForwardLogisticBaseline.
      3. Compute identical fold boundaries (round(n * k / (n_folds+1))).
      4. For each fold f, the OOF rows at positions [cum_start_f .. cum_start_f + fold_size_f)
         correspond positionally to source rows at [pred_start_f .. pred_end_f).
      5. Extract game_id, Date, Home, Away, Away ML, Home ML from source.
      6. Convert American ML odds → decimal odds → implied probability.
      7. Compute edge = p_oof - p_market (home-win perspective).

    All operations are deterministic given the same inputs.
    """

    def __init__(
        self,
        source_csv_path: str,
        n_folds: int = N_FOLDS,
        features: list[str] | None = None,
        label_col: str = OOF_LABEL_COL,
        time_col: str = OOF_TIME_COL,
    ) -> None:
        self._source_path = str(source_csv_path)
        self._n_folds = n_folds
        self._features = features if features is not None else list(OOF_FEATURES)
        self._label_col = label_col
        self._time_col = time_col
        self._join_report: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def join_with_p13_oof(self, oof_df: pd.DataFrame) -> pd.DataFrame:
        """Attach market odds columns to a P13 OOF DataFrame.

        New columns added:
          game_id, game_date, home_team, away_team,
          away_ml_raw, home_ml_raw,
          odds_decimal_home, odds_decimal_away,
          p_market,      # home-win implied probability (home ML, vig NOT removed)
          edge,          # p_oof - p_market
          odds_join_status  # JOINED | MISSING | INVALID_ODDS

        Args:
            oof_df: P13 OOF DataFrame. Must have columns: y_true, p_oof, fold_id.

        Returns:
            New DataFrame (copy) with odds columns appended. Original row order preserved.

        Raises:
            ValueError: If fold row counts don't match between OOF and source.
        """
        src_clean = self._load_and_clean_source()
        boundaries = self._compute_boundaries(len(src_clean))

        result = oof_df.copy().reset_index(drop=True)

        # Initialise new columns with sentinel values
        for col in ["game_id", "game_date", "home_team", "away_team",
                    "away_ml_raw", "home_ml_raw", "odds_decimal_home",
                    "odds_decimal_away", "p_market", "edge"]:
            result[col] = None
        result["odds_join_status"] = JOIN_STATUS_MISSING

        oof_cursor = 0  # running index into OOF rows

        for fi in range(self._n_folds):
            fold_id = fi + 1
            pred_start = boundaries[fi + 1]
            pred_end = boundaries[fi + 2]
            fold_size = pred_end - pred_start

            oof_fold_mask = result["fold_id"] == fold_id
            oof_fold_indices = result.index[oof_fold_mask].tolist()

            if len(oof_fold_indices) != fold_size:
                raise ValueError(
                    f"Fold {fold_id}: OOF has {len(oof_fold_indices)} rows "
                    f"but source has {fold_size} rows. "
                    f"Source CSV may differ from the one used to generate P13 OOF."
                )

            src_fold = src_clean.iloc[pred_start:pred_end].reset_index(drop=True)

            for i, oof_idx in enumerate(oof_fold_indices):
                src_row = src_fold.iloc[i]
                game_date = str(src_row.get(self._time_col, ""))[:10]
                home_team = str(src_row.get("Home", ""))
                away_team = str(src_row.get("Away", ""))
                game_id = str(src_row.get("game_id", build_game_key(game_date, home_team, away_team)))

                result.at[oof_idx, "game_id"] = game_id
                result.at[oof_idx, "game_date"] = game_date
                result.at[oof_idx, "home_team"] = home_team
                result.at[oof_idx, "away_team"] = away_team

                home_ml_raw = src_row.get("Home ML")
                away_ml_raw = src_row.get("Away ML")
                result.at[oof_idx, "home_ml_raw"] = home_ml_raw
                result.at[oof_idx, "away_ml_raw"] = away_ml_raw

                home_ml = parse_american_odds_string(home_ml_raw)
                away_ml = parse_american_odds_string(away_ml_raw)

                if home_ml is None or away_ml is None:
                    result.at[oof_idx, "odds_join_status"] = JOIN_STATUS_INVALID_ODDS
                    continue

                try:
                    dec_home = american_to_decimal_odds(home_ml)
                    dec_away = american_to_decimal_odds(away_ml)
                    p_mkt = decimal_to_implied_probability(dec_home)
                    p_oof_val = float(result.at[oof_idx, "p_oof"])
                    edge_val = round(p_oof_val - p_mkt, 6)

                    result.at[oof_idx, "odds_decimal_home"] = dec_home
                    result.at[oof_idx, "odds_decimal_away"] = dec_away
                    result.at[oof_idx, "p_market"] = p_mkt
                    result.at[oof_idx, "edge"] = edge_val
                    result.at[oof_idx, "odds_join_status"] = JOIN_STATUS_JOINED
                except (ValueError, ZeroDivisionError):
                    result.at[oof_idx, "odds_join_status"] = JOIN_STATUS_INVALID_ODDS

        self._build_join_report(result)
        return result

    def join_report(self) -> dict:
        """Return the join coverage report from the most recent join call.

        Returns:
            Dict with keys: source_path, n_oof_rows, joined, missing,
            invalid_odds, coverage_pct, odds_join_status_counts.
        """
        return dict(self._join_report)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_and_clean_source(self) -> pd.DataFrame:
        """Load source CSV and apply the same preprocessing as WalkForwardLogistic."""
        p = Path(self._source_path)
        if not p.exists():
            raise FileNotFoundError(f"Source CSV not found: {self._source_path}")

        df = pd.read_csv(str(p))

        if self._label_col not in df.columns:
            if (self._label_col == "home_win"
                    and "Home Score" in df.columns
                    and "Away Score" in df.columns):
                df["home_win"] = (df["Home Score"] > df["Away Score"]).astype(int)
            else:
                raise ValueError(
                    f"Label column '{self._label_col}' not found and cannot be derived."
                )

        required = self._features + [self._label_col, self._time_col]
        df_clean = df.dropna(subset=required).copy()
        df_clean[self._time_col] = pd.to_datetime(df_clean[self._time_col])
        df_clean = df_clean.sort_values(self._time_col).reset_index(drop=True)
        return df_clean

    def _compute_boundaries(self, n: int) -> list[int]:
        """Compute fold boundaries using the same formula as WalkForwardLogistic."""
        n_chunks = self._n_folds + 1
        return [int(round(n * k / n_chunks)) for k in range(n_chunks + 1)]

    def _build_join_report(self, df: pd.DataFrame) -> None:
        """Populate internal join report after a join call."""
        counts = df["odds_join_status"].value_counts().to_dict()
        joined = int(counts.get(JOIN_STATUS_JOINED, 0))
        missing = int(counts.get(JOIN_STATUS_MISSING, 0))
        invalid = int(counts.get(JOIN_STATUS_INVALID_ODDS, 0))
        n = len(df)
        self._join_report = {
            "source_path": self._source_path,
            "n_oof_rows": n,
            "joined": joined,
            "missing": missing,
            "invalid_odds": invalid,
            "coverage_pct": round(100.0 * joined / n, 2) if n > 0 else 0.0,
            "odds_join_status_counts": counts,
        }
