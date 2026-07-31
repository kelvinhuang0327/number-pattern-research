from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


TEAM_ALIASES = {
    "Arizona Diamondbacks": "ARI", "Athletics": "OAK", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS", "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU",
    "Kansas City Royals": "KCR", "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN",
    "New York Mets": "NYM", "New York Yankees": "NYY", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBA",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
}

TEAM_HOME_PARK = {
    "ARI": "chase_field", "OAK": "sutter_health_park", "ATL": "truist_park", "BAL": "camden_yards",
    "BOS": "fenway_park", "CHC": "wrigley_field", "CWS": "rate_field", "CIN": "great_american",
    "CLE": "progressive_field", "COL": "coors_field", "DET": "comerica_park", "HOU": "minute_maid",
    "KCR": "kauffman", "LAA": "angel_stadium", "LAD": "dodger_stadium", "MIA": "loan_depot",
    "MIL": "american_family", "MIN": "target_field", "NYM": "citi_field", "NYY": "yankee_stadium",
    "PHI": "citizens_bank", "PIT": "pnc_park", "SD": "petco_park", "SF": "oracle_park",
    "SEA": "t_mobile", "STL": "busch_stadium", "TBA": "steinbrenner_field", "TEX": "globe_life",
    "TOR": "rogers_centre", "WSN": "nationals_park",
}

PARK_FACTORS = {
    "default": {"hr": 1.00, "run": 1.00},
    "coors_field": {"hr": 1.22, "run": 1.28},
    "fenway_park": {"hr": 1.04, "run": 1.03},
    "dodger_stadium": {"hr": 0.98, "run": 0.99},
    "loan_depot": {"hr": 0.90, "run": 0.93},
    "tokyo_dome": {"hr": 1.03, "run": 1.02},
    "loan_depot_wbc": {"hr": 0.92, "run": 0.95},
}


def american_to_decimal(odds: float) -> float:
    val = float(odds)
    if val > 0:
        return 1.0 + val / 100.0
    return 1.0 + 100.0 / abs(val)


def _load_optional_pitcher_profiles(path: str = "data/external/pitcher_profiles_2025.csv") -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["pitcher", "throws", "kbb_last30", "kbb_trend"])
    df = pd.read_csv(p)
    for col in ["pitcher", "throws", "kbb_last30", "kbb_trend"]:
        if col not in df.columns:
            raise ValueError(f"pitcher profile missing column: {col}")
    return df


def _load_optional_team_split(path: str = "data/external/team_batter_split_2025.csv") -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["team", "woba_vs_lhp", "woba_vs_rhp", "ops_vs_lhp", "ops_vs_rhp"])
    df = pd.read_csv(p)
    for col in ["team", "woba_vs_lhp", "woba_vs_rhp", "ops_vs_lhp", "ops_vs_rhp"]:
        if col not in df.columns:
            raise ValueError(f"team split profile missing column: {col}")
    return df


def load_odds_results(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[df["Status"] == "Final"].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Date", "Start Time (EDT)"]).reset_index(drop=True)

    for col in [
        "Away Score", "Home Score", "O/U", "Home RL Spread", "Away ML", "Home ML", "Over", "Under", "RL Away", "RL Home"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["Away Score", "Home Score", "Away ML", "Home ML", "O/U", "Over", "Under", "RL Away", "RL Home", "Home RL Spread"]
    )
    df["away_team"] = df["Away"].map(TEAM_ALIASES)
    df["home_team"] = df["Home"].map(TEAM_ALIASES)
    df = df.dropna(subset=["away_team", "home_team"]).copy()

    df["home_win"] = (df["Home Score"] > df["Away Score"]).astype(int)
    df["total_runs"] = df["Home Score"] + df["Away Score"]
    df["over_hit"] = (df["total_runs"] > df["O/U"]).astype(int)
    df["home_cover"] = ((df["Home Score"] + df["Home RL Spread"]) > df["Away Score"]).astype(int)

    df["away_ml_dec"] = df["Away ML"].map(american_to_decimal)
    df["home_ml_dec"] = df["Home ML"].map(american_to_decimal)
    df["over_dec"] = df["Over"].map(american_to_decimal)
    df["under_dec"] = df["Under"].map(american_to_decimal)
    df["rl_away_dec"] = df["RL Away"].map(american_to_decimal)
    df["rl_home_dec"] = df["RL Home"].map(american_to_decimal)

    df["home_park"] = df["home_team"].map(TEAM_HOME_PARK).fillna("default")
    return df


def _park_factors(park_name: str) -> tuple[float, float]:
    f = PARK_FACTORS.get(park_name, PARK_FACTORS["default"])
    return float(f["hr"]), float(f["run"])


def _rolling_values(hist: list, key: str, n: int, default: float) -> tuple[float, float]:
    if not hist:
        return default, 0.0
    arr = np.array([x[key] for x in hist[-n:]], dtype=float)
    return float(arr.mean()), float(arr.var())


def _summarize(hist: list) -> tuple[float, float, float, float]:
    if not hist:
        return 0.5, 0.0, 4.3, 4.3
    wins = np.mean([x["win"] for x in hist])
    run_diff = np.mean([x["rf"] - x["ra"] for x in hist])
    rf = np.mean([x["rf"] for x in hist])
    ra = np.mean([x["ra"] for x in hist])
    return float(wins), float(run_diff), float(rf), float(ra)


def _bullpen_stress(hist: list, current_date: pd.Timestamp) -> float:
    if not hist:
        return 0.0
    recent = [x for x in hist[-7:] if (current_date - x["date"]).days <= 3]
    if not recent:
        return 0.0
    close_game_load = sum(1.0 for x in recent if abs(x["rf"] - x["ra"]) <= 2)
    high_run_load = sum(1.0 for x in recent if x["ra"] >= 6)
    back_to_back = 0.0
    dates = sorted({x["date"] for x in recent})
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            back_to_back += 1.0
    return float(min(6.0, close_game_load + 0.7 * high_run_load + 0.5 * back_to_back))


def build_pregame_features(df: pd.DataFrame, lookback: int = 15, elo_k: float = 24.0) -> pd.DataFrame:
    pitcher_df = _load_optional_pitcher_profiles()
    pitcher_map = {
        str(r["pitcher"]).strip(): {
            "throws": str(r["throws"]).upper().strip(),
            "kbb_last30": float(r["kbb_last30"]),
            "kbb_trend": float(r["kbb_trend"]),
        }
        for _, r in pitcher_df.iterrows()
    }

    split_df = _load_optional_team_split()
    split_map = {
        str(r["team"]).upper().strip(): {
            "woba_vs_lhp": float(r["woba_vs_lhp"]),
            "woba_vs_rhp": float(r["woba_vs_rhp"]),
            "ops_vs_lhp": float(r["ops_vs_lhp"]),
            "ops_vs_rhp": float(r["ops_vs_rhp"]),
        }
        for _, r in split_df.iterrows()
    }

    history: dict[str, list] = {}
    elo: dict[str, float] = {}

    rows = []
    for _, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        now = row["Date"]
        for t in (home, away):
            history.setdefault(t, [])
            elo.setdefault(t, 1500.0)

        h_hist = history[home][-lookback:]
        a_hist = history[away][-lookback:]

        h_wr, h_rd, h_rf, h_ra = _summarize(h_hist)
        a_wr, a_rd, a_rf, a_ra = _summarize(a_hist)

        h_rf_5, h_rf_var_5 = _rolling_values(h_hist, "rf", 5, 4.3)
        a_rf_5, a_rf_var_5 = _rolling_values(a_hist, "rf", 5, 4.3)
        h_rf_10, h_rf_var_10 = _rolling_values(h_hist, "rf", 10, 4.3)
        a_rf_10, a_rf_var_10 = _rolling_values(a_hist, "rf", 10, 4.3)
        h_wr_5, _ = _rolling_values(h_hist, "win", 5, 0.5)
        a_wr_5, _ = _rolling_values(a_hist, "win", 5, 0.5)
        h_wr_10, _ = _rolling_values(h_hist, "win", 10, 0.5)
        a_wr_10, _ = _rolling_values(a_hist, "win", 10, 0.5)

        home_bsi = _bullpen_stress(h_hist, now)
        away_bsi = _bullpen_stress(a_hist, now)

        hr_factor, run_factor = _park_factors(row["home_park"])

        away_starter = str(row.get("Away Starter", "")).strip()
        home_starter = str(row.get("Home Starter", "")).strip()

        away_pitch = pitcher_map.get(away_starter, {"throws": "R", "kbb_last30": 2.7, "kbb_trend": 0.0})
        home_pitch = pitcher_map.get(home_starter, {"throws": "R", "kbb_last30": 2.7, "kbb_trend": 0.0})

        home_split = split_map.get(home, {"woba_vs_lhp": 0.318, "woba_vs_rhp": 0.314, "ops_vs_lhp": 0.725, "ops_vs_rhp": 0.713})
        away_split = split_map.get(away, {"woba_vs_lhp": 0.318, "woba_vs_rhp": 0.314, "ops_vs_lhp": 0.725, "ops_vs_rhp": 0.713})

        home_vs_pitch_woba = home_split["woba_vs_lhp"] if away_pitch["throws"] == "L" else home_split["woba_vs_rhp"]
        away_vs_pitch_woba = away_split["woba_vs_lhp"] if home_pitch["throws"] == "L" else away_split["woba_vs_rhp"]

        h_kbb_trend = away_pitch["kbb_trend"]
        a_kbb_trend = home_pitch["kbb_trend"]

        feat = {
            "Date": now,
            "game_idx": int(len(rows)),
            "home_team": home,
            "away_team": away,
            "home_elo": elo[home],
            "away_elo": elo[away],
            "elo_diff": elo[home] - elo[away],
            "wr_diff": h_wr - a_wr,
            "rd_diff": h_rd - a_rd,
            "rf_diff": h_rf - a_rf,
            "ra_diff": h_ra - a_ra,
            # Recency bias
            "wr_5_diff": h_wr_5 - a_wr_5,
            "wr_10_diff": h_wr_10 - a_wr_10,
            "rf_5_diff": h_rf_5 - a_rf_5,
            "rf_10_diff": h_rf_10 - a_rf_10,
            "rf_var_5_diff": h_rf_var_5 - a_rf_var_5,
            "rf_var_10_diff": h_rf_var_10 - a_rf_var_10,
            # Platoon + K/BB trend
            "platoon_woba_diff": home_vs_pitch_woba - away_vs_pitch_woba,
            "starter_kbb_trend_diff": h_kbb_trend - a_kbb_trend,
            "starter_kbb_level_diff": away_pitch["kbb_last30"] - home_pitch["kbb_last30"],
            # Park + bullpen stress
            "park_hr_factor": hr_factor,
            "park_run_factor": run_factor,
            "bullpen_stress_diff": home_bsi - away_bsi,
            "home_win": int(row["home_win"]),
            "home_score": float(row["Home Score"]),
            "away_score": float(row["Away Score"]),
            "total_runs": float(row["total_runs"]),
            "line_total": float(row["O/U"]),
            "home_spread": float(row["Home RL Spread"]),
            "over_hit": int(row["over_hit"]),
            "home_cover": int(row["home_cover"]),
            "away_ml_dec": float(row["away_ml_dec"]),
            "home_ml_dec": float(row["home_ml_dec"]),
            "over_dec": float(row["over_dec"]),
            "under_dec": float(row["under_dec"]),
            "rl_away_dec": float(row["rl_away_dec"]),
            "rl_home_dec": float(row["rl_home_dec"]),
            "exp_home_runs_base": max(
                2.0,
                min(
                    8.5,
                    (4.2 + 0.35 * h_rf + 0.20 * a_ra + 0.1 * h_rd - 0.08 * a_rd)
                    * (0.96 + 0.08 * run_factor)
                    * (0.97 + 0.08 * hr_factor)
                    * (1.0 - 0.015 * home_bsi)
                ),
            ),
            "exp_away_runs_base": max(
                2.0,
                min(
                    8.5,
                    (4.0 + 0.35 * a_rf + 0.20 * h_ra + 0.1 * a_rd - 0.08 * h_rd)
                    * (0.96 + 0.08 * run_factor)
                    * (0.97 + 0.08 * hr_factor)
                    * (1.0 - 0.015 * away_bsi)
                ),
            ),
        }
        rows.append(feat)

        expected_home = 1.0 / (1.0 + 10 ** ((elo[away] - elo[home]) / 400.0))
        actual_home = 1.0 if row["home_win"] else 0.0
        elo[home] += elo_k * (actual_home - expected_home)
        elo[away] += elo_k * ((1 - actual_home) - (1 - expected_home))

        history[home].append({"win": actual_home, "rf": row["Home Score"], "ra": row["Away Score"], "date": now})
        history[away].append({"win": 1.0 - actual_home, "rf": row["Away Score"], "ra": row["Home Score"], "date": now})

    return pd.DataFrame(rows)
