#!/usr/bin/env python3
"""
PHASE 5 — MLB Paper Loop

- Parse MLB games from data/mlb_context/odds_timeline.jsonl
- Prefer today's games; fallback to latest available date if today has no rows
- Deduplicate by game_id
- Build minimal record and run PredictionOrchestrator
- Validate at least 3 MLB prediction records with execution_mode=PAPER_ONLY
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator


ODDS_TIMELINE = Path("data/mlb_context/odds_timeline.jsonl")
LEDGER = Path("research/trade_ledger.jsonl")


def _american_to_prob(odds: Optional[float]) -> float:
    if odds is None:
        return 0.5
    x = float(odds)
    if x > 0:
        return 100.0 / (x + 100.0)
    if x < 0:
        return (-x) / ((-x) + 100.0)
    return 0.5


def _pick_moneyline(row: dict[str, Any], side: str) -> Optional[float]:
    keys = [
        f"decision_{side}_ml",
        f"latest_pregame_{side}_ml",
        f"closing_{side}_ml",
        f"opening_{side}_ml",
        f"external_closing_{side}_ml",
    ]
    for key in keys:
        val = row.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def _parse_game_id(game_id: str) -> tuple[str, str, str]:
    # Example: MLB-2026_04_18-8_11_PM-TORONTO_BLUE_JAYS-AT-ARIZONA_DIAMONDBACKS
    if "-AT-" not in game_id:
        raise ValueError(f"Invalid game_id format: {game_id}")

    left, home = game_id.rsplit("-AT-", 1)
    chunks = left.split("-", 3)
    if len(chunks) < 4:
        raise ValueError(f"Invalid game_id format: {game_id}")

    date_part = chunks[1]
    away = chunks[3]
    return date_part, away, home


def _load_rows() -> list[dict[str, Any]]:
    if not ODDS_TIMELINE.exists():
        raise FileNotFoundError(f"Missing timeline file: {ODDS_TIMELINE}")

    rows: list[dict[str, Any]] = []
    for line in ODDS_TIMELINE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        game_id = str(row.get("game_id", "")).strip()
        if not game_id.startswith("MLB-"):
            continue
        try:
            date_part, away, home = _parse_game_id(game_id)
        except ValueError:
            continue
        row["_date_part"] = date_part
        row["_away_team"] = away
        row["_home_team"] = home
        rows.append(row)
    return rows


def _target_date(rows: list[dict[str, Any]]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    if any(r.get("_date_part") == today for r in rows):
        return today
    return max(str(r.get("_date_part")) for r in rows)


def _existing_mlb_prediction_ids() -> set[str]:
    if not LEDGER.exists():
        return set()
    ids: set[str] = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event_type") != "prediction":
            continue
        if row.get("league") != "MLB":
            continue
        gid = row.get("game_id")
        if gid:
            ids.add(str(gid))
    return ids


@dataclass
class MinimalMLBRecord:
    game_id: str
    round_name: str
    home_team: str
    away_team: str
    home_elo: float
    away_elo: float
    home_woba: float
    away_woba: float
    home_fip: float
    away_fip: float
    market_home_prob: float
    odds: dict[str, float]
    league: str = "MLB"


def _records_for_target_date() -> list[MinimalMLBRecord]:
    rows = _load_rows()
    if not rows:
        return []

    date_key = _target_date(rows)
    seen: set[str] = set()
    records: list[MinimalMLBRecord] = []

    for row in rows:
        if row.get("_date_part") != date_key:
            continue
        game_id = str(row.get("game_id", "")).strip()
        if not game_id or game_id in seen:
            continue

        home_ml = _pick_moneyline(row, "home")
        away_ml = _pick_moneyline(row, "away")
        if home_ml is None or away_ml is None:
            continue

        seen.add(game_id)
        records.append(
            MinimalMLBRecord(
                game_id=game_id,
                round_name="MLB_REGULAR",
                home_team=str(row.get("_home_team")),
                away_team=str(row.get("_away_team")),
                home_elo=1500.0,
                away_elo=1500.0,
                home_woba=0.315,
                away_woba=0.315,
                home_fip=4.0,
                away_fip=4.0,
                market_home_prob=_american_to_prob(home_ml),
                odds={"home_ml": home_ml, "away_ml": away_ml},
            )
        )

    return records


def _new_mlb_paper_predictions(before_ids: set[str]) -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event_type") != "prediction":
            continue
        if row.get("league") != "MLB":
            continue
        gid = str(row.get("game_id", ""))
        if gid in before_ids:
            continue
        if str(row.get("execution_mode", "")).upper() != "PAPER_ONLY":
            continue
        rows.append(row)
    return rows


def main() -> int:
    print("=" * 60)
    print("PHASE 5 — MLB PAPER LOOP")
    print("=" * 60)

    existing_ids = _existing_mlb_prediction_ids()
    records = _records_for_target_date()

    if not records:
        print("No MLB records available from odds timeline.")
        return 1

    print(f"Candidate records: {len(records)}")
    print(f"Existing MLB predictions in ledger: {len(existing_ids)}")

    orchestrator = PredictionOrchestrator()
    run_count = 0
    skip_count = 0
    err_count = 0

    for rec in records:
        if rec.game_id in existing_ids:
            skip_count += 1
            continue
        try:
            result = orchestrator.predict(rec, use_world_model=False)
            run_count += 1
            print(
                f"OK  {rec.game_id}  side={result.recommended_side}  "
                f"mode={result.execution_mode}  paper={result.paper_side}"
            )
        except Exception as exc:
            err_count += 1
            print(f"ERR {rec.game_id}: {exc}")

    new_paper_rows = _new_mlb_paper_predictions(existing_ids)
    print("\nSummary")
    print(f"  run   : {run_count}")
    print(f"  skip  : {skip_count}")
    print(f"  error : {err_count}")
    print(f"  new MLB PAPER_ONLY predictions: {len(new_paper_rows)}")

    passed = len(new_paper_rows) >= 3
    print(f"  PASS gate (>=3): {'✅' if passed else '❌'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
