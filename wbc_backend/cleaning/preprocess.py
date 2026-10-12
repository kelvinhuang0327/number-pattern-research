from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = [
    "team",
    "woba",
    "ops_plus",
    "fip",
    "whip",
    "stuff_plus",
    "der",
    "bullpen_depth",
    "elo",
]


def clean_team_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in REQUIRED_COLUMNS:
        if col not in out.columns:
            raise ValueError(f"missing required column: {col}")

    out = out.dropna(subset=["team"]).copy()
    out["team"] = out["team"].str.upper().str.strip()
    numeric_cols = [c for c in REQUIRED_COLUMNS if c != "team"]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
    out[numeric_cols] = out[numeric_cols].fillna(out[numeric_cols].median())
    return out
