from __future__ import annotations

import re


def _slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", (value or "").upper()).strip("_")


def make_mlb_game_id(
    game_date: str,
    start_time: str,
    away_team: str,
    home_team: str,
) -> str:
    return f"MLB-{_slug(game_date)}-{_slug(start_time)}-{_slug(away_team)}-AT-{_slug(home_team)}"
