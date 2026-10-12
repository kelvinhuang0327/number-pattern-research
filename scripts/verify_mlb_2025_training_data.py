#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DATASET_PATH = Path("data/mlb_2025/mlb-2025-asplayed.csv")
RETROSHEET_PATH = Path("data/mlb_2025/gl2025.txt")
METADATA_PATH = Path("data/mlb_2025/mlb-2025-asplayed.csv.metadata.json")


TEAM_CODE_TO_NAME = {
    "ANA": "Los Angeles Angels",
    "ARI": "Arizona Diamondbacks",
    "ATH": "Athletics",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CAL": "Los Angeles Angels",
    "CHA": "Chicago White Sox",
    "CHC": "Chicago Cubs",
    "CHN": "Chicago Cubs",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "CWS": "Chicago White Sox",
    "DET": "Detroit Tigers",
    "FLO": "Miami Marlins",
    "HOU": "Houston Astros",
    "KCA": "Kansas City Royals",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "LAN": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "MON": "Washington Nationals",
    "NYA": "New York Yankees",
    "NYM": "New York Mets",
    "NYN": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SDN": "San Diego Padres",
    "SDP": "San Diego Padres",
    "SEA": "Seattle Mariners",
    "SFN": "San Francisco Giants",
    "SFG": "San Francisco Giants",
    "SLN": "St. Louis Cardinals",
    "STL": "St. Louis Cardinals",
    "TBA": "Tampa Bay Rays",
    "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
    "WSN": "Washington Nationals",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_retrosheet_counter(path: Path) -> Counter:
    rows = Counter()
    with path.open("r", encoding="latin1", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            raw_date = row[0]
            game_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            away = TEAM_CODE_TO_NAME.get(row[3], row[3])
            home = TEAM_CODE_TO_NAME.get(row[6], row[6])
            away_score = int(row[9])
            home_score = int(row[10])
            rows[(game_date, away, home, away_score, home_score)] += 1
    return rows


def build_dataset_counter(df: pd.DataFrame) -> Counter:
    rows = Counter()
    for r in df.itertuples(index=False):
        rows[(str(r.date), r.away_team, r.home_team, int(r.away_score), int(r.home_score))] += 1
    return rows


def main() -> int:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
    if not RETROSHEET_PATH.exists():
        raise FileNotFoundError(f"Retrosheet log not found: {RETROSHEET_PATH}")

    df = pd.read_csv(DATASET_PATH)
    required = {"date", "away_team", "home_team", "away_score", "home_score"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Dataset missing required columns: {sorted(missing)}")

    retro_counter = build_retrosheet_counter(RETROSHEET_PATH)
    data_counter = build_dataset_counter(df)

    deficits = sum(max(0, c - retro_counter[k]) for k, c in data_counter.items())
    extras = sum(max(0, c - data_counter[k]) for k, c in retro_counter.items())
    verified = deficits == 0 and extras == 0 and len(df) == sum(retro_counter.values())

    df["source_file"] = "gl2025.txt"
    df["source_type"] = "retrosheet_gamelog"
    df["is_verified_real"] = bool(verified)
    df.to_csv(DATASET_PATH, index=False)

    metadata = {
        "dataset": DATASET_PATH.name,
        "ingest_source_file": RETROSHEET_PATH.name,
        "ingest_source_type": "retrosheet_gamelog",
        "source_chain_verified": bool(verified),
        "verification": {
            "method": "exact_match_on_date_teams_scores",
            "rows_dataset": int(len(df)),
            "rows_retrosheet": int(sum(retro_counter.values())),
            "unmatched_dataset_rows": int(deficits),
            "missing_dataset_rows": int(extras),
            "retrosheet_sha256": sha256_file(RETROSHEET_PATH),
            "verified_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "notes": (
            "Verified against Retrosheet gl2025.txt by exact tuple match "
            "(date, away_team, home_team, away_score, home_score)."
            if verified
            else "Verification failed: tuple mismatch against Retrosheet gl2025.txt."
        ),
        "row_count": int(len(df)),
    }
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verified": verified,
                "rows_dataset": len(df),
                "rows_retrosheet": sum(retro_counter.values()),
                "unmatched_dataset_rows": deficits,
                "missing_dataset_rows": extras,
            },
            ensure_ascii=False,
        )
    )
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
