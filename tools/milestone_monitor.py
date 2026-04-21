"""Milestone monitoring helpers for shadow-tracked strategies."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _latest_draw(lottery_type: str) -> Optional[int]:
    if not DB_PATH.exists():
        return None

    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MAX(CAST(draw AS INTEGER))
            FROM draws
            WHERE lottery_type = ?
            """,
            (lottery_type,),
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])
    except Exception:
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _approx_weeks_remaining(draws_remaining: int, lottery_type: str) -> float:
    if draws_remaining <= 0:
        return 0.0
    draws_per_week = {
        "DAILY_539": 7.0,
        "BIG_LOTTO": 2.0,
        "POWER_LOTTO": 2.0,
    }.get(lottery_type, 1.0)
    return round(draws_remaining / draws_per_week, 1)


def _status_for_draws(draws_remaining: int) -> str:
    if draws_remaining <= 0:
        return "NEEDS_EVALUATION"
    if draws_remaining <= 10:
        return "APPROACHING"
    return "TRACKING"


def _milestone_from_file(path: Path) -> Optional[Dict[str, Any]]:
    data = _load_json(path)
    if not data:
        return None

    milestone_name = path.stem
    lottery_type = "POWER_LOTTO" if "combo_b" in milestone_name else data.get("lottery_type", "POWER_LOTTO")
    evaluate_at_draw = data.get("evaluate_at_draw")
    if evaluate_at_draw is None:
        return None

    current_draw = _latest_draw(lottery_type)
    if current_draw is None:
        return {
            "name": milestone_name,
            "lottery_type": lottery_type,
            "current_draw": None,
            "evaluate_at_draw": int(evaluate_at_draw),
            "draws_remaining": None,
            "weeks_remaining": None,
            "status": data.get("status", "TRACKING"),
            "started_draw": data.get("started_draw"),
            "source_file": path.name,
        }

    draws_remaining = int(evaluate_at_draw) - current_draw
    return {
        "name": milestone_name,
        "lottery_type": lottery_type,
        "current_draw": current_draw,
        "evaluate_at_draw": int(evaluate_at_draw),
        "draws_remaining": max(0, draws_remaining),
        "weeks_remaining": _approx_weeks_remaining(max(0, draws_remaining), lottery_type),
        "status": _status_for_draws(draws_remaining),
        "started_draw": data.get("started_draw"),
        "source_file": path.name,
        "notes": data.get("retest_condition"),
        "auto_retire_condition": data.get("auto_retire_condition"),
    }


def check_milestones() -> List[Dict[str, Any]]:
    """Scan tracked milestone files and report approaching or due items."""
    milestones: List[Dict[str, Any]] = []
    for path in sorted(DATA_DIR.glob("*_milestone.json")):
        item = _milestone_from_file(path)
        if item:
            milestones.append(item)
    return milestones
