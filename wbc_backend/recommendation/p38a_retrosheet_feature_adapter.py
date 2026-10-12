"""
P38A Retrosheet Feature Adapter.

Converts mlb_2024_game_identity_outcomes_joined.csv into a pregame-only
feature DataFrame. All features are computed STRICTLY from games that
occurred BEFORE the target game date (no look-ahead leakage).

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False

# Columns that carry target-game information — forbidden as features
_LEAKAGE_COLUMNS = frozenset(
    [
        "home_score",
        "away_score",
        "y_true_home_win",
        "winner",
        "run_diff_current_game",
        "total_runs_current_game",
    ]
)

REQUIRED_INPUT_COLUMNS = frozenset(
    ["game_id", "game_date", "home_team", "away_team", "home_score", "away_score", "y_true_home_win"]
)

REQUIRED_OUTPUT_FEATURE_KEYS = frozenset(
    [
        "home_rolling_winrate_10g",
        "away_rolling_winrate_10g",
        "home_rolling_run_diff_10g",
        "away_rolling_run_diff_10g",
        "home_rest_days",
        "away_rest_days",
        "is_home_team_indicator",
    ]
)


@dataclass(frozen=True)
class AdapterResult:
    feature_df: pd.DataFrame  # one row per game, pregame_features as dict column
    row_count: int
    source_path: str
    output_hash: str  # SHA-256 of feature_df canonical CSV bytes


def _parse_date(val: Any) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


def _build_team_history(df: pd.DataFrame) -> dict[str, list[dict]]:
    """
    Build chronological per-team game history (home AND away perspective).
    Returns dict: team_id -> list of {game_date, win, run_diff} sorted by date.
    Only includes info available BEFORE a game (from prior completed games).
    """
    team_history: dict[str, list[dict]] = {}

    for _, row in df.sort_values("game_date").iterrows():
        gdate = _parse_date(row["game_date"])
        home = row["home_team"]
        away = row["away_team"]
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        home_win = int(row["y_true_home_win"])

        for team, won, scored, allowed in [
            (home, home_win, home_score, away_score),
            (away, 1 - home_win, away_score, home_score),
        ]:
            if team not in team_history:
                team_history[team] = []
            team_history[team].append(
                {
                    "game_date": gdate,
                    "win": won,
                    "run_diff": scored - allowed,
                }
            )

    return team_history


def _rolling_stats_before(
    history: list[dict], before_date: date, window: int = 10
) -> dict[str, float]:
    """
    Compute rolling winrate and run_diff for the last `window` games
    that occurred STRICTLY before `before_date`.
    """
    prior = [g for g in history if g["game_date"] < before_date]
    recent = prior[-window:]
    if not recent:
        return {"winrate": 0.5, "run_diff": 0.0, "n_games": 0}
    return {
        "winrate": sum(g["win"] for g in recent) / len(recent),
        "run_diff": sum(g["run_diff"] for g in recent) / len(recent),
        "n_games": len(recent),
    }


def _rest_days_before(history: list[dict], before_date: date) -> float:
    """Days since last game strictly before `before_date`. Returns 14.0 if none."""
    prior = [g for g in history if g["game_date"] < before_date]
    if not prior:
        return 14.0
    last = max(g["game_date"] for g in prior)
    return float((before_date - last).days)


def build_feature_dataframe(csv_path: str | Path) -> AdapterResult:
    """
    Main entry point. Reads the P32 joined CSV and returns an AdapterResult
    with pregame-only features for every game.

    Deterministic: same input -> byte-identical output_hash.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype={"game_id": str, "home_team": str, "away_team": str})

    missing = REQUIRED_INPUT_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV missing required columns: {missing}")

    # Validate no leakage columns would be passed through as features
    # (they exist in input but must not appear in pregame_features dict)

    df = df.sort_values("game_date").reset_index(drop=True)

    team_history = _build_team_history(df)

    records: list[dict] = []
    for _, row in df.iterrows():
        gdate = _parse_date(row["game_date"])
        home = str(row["home_team"])
        away = str(row["away_team"])

        home_hist = team_history.get(home, [])
        away_hist = team_history.get(away, [])

        home_stats = _rolling_stats_before(home_hist, gdate, window=10)
        away_stats = _rolling_stats_before(away_hist, gdate, window=10)

        pregame_features: dict[str, float] = {
            "home_rolling_winrate_10g": home_stats["winrate"],
            "away_rolling_winrate_10g": away_stats["winrate"],
            "home_rolling_run_diff_10g": home_stats["run_diff"],
            "away_rolling_run_diff_10g": away_stats["run_diff"],
            "home_rest_days": _rest_days_before(home_hist, gdate),
            "away_rest_days": _rest_days_before(away_hist, gdate),
            "is_home_team_indicator": 1.0,
        }

        # Safety assertion: no leakage keys should appear in features
        feature_keys = set(pregame_features.keys())
        leaked = feature_keys & _LEAKAGE_COLUMNS
        if leaked:
            raise RuntimeError(f"Leakage detected in features for {row['game_id']}: {leaked}")

        records.append(
            {
                "game_id": str(row["game_id"]),
                "game_date": gdate,
                "home_team": home,
                "away_team": away,
                "pregame_features": pregame_features,
            }
        )

    feature_df = pd.DataFrame(records)

    # Deterministic hash: sort by game_id then serialize feature values
    flat_records = []
    for r in feature_df.sort_values("game_id").itertuples():
        flat_records.append(
            r.game_id + "," + ",".join(f"{r.pregame_features[k]:.10f}" for k in sorted(REQUIRED_OUTPUT_FEATURE_KEYS))
        )
    canonical_bytes = "\n".join(flat_records).encode("utf-8")
    output_hash = hashlib.sha256(canonical_bytes).hexdigest()

    logger.info(
        "P38A feature adapter complete: %d rows, hash=%s",
        len(feature_df),
        output_hash[:16],
    )

    return AdapterResult(
        feature_df=feature_df,
        row_count=len(feature_df),
        source_path=str(csv_path),
        output_hash=output_hash,
    )
