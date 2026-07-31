from __future__ import annotations

from .base import LeagueAdapter
from .mlb_adapter import MLBLeagueAdapter
from .wbc_adapter import WBCLeagueAdapter

_REGISTRY: dict[str, LeagueAdapter] = {
    "WBC": WBCLeagueAdapter(),
    "MLB": MLBLeagueAdapter(),
}


def normalize_league_name(league: str | None) -> str:
    key = (league or "MLB").strip().upper()
    # WBC 含年份後綴（WBC2026、WBC2023 等）一律歸 WBC
    if key.startswith("WBC") or key in {"WORLD_BASEBALL_CLASSIC"}:
        return "WBC"
    if key.startswith("MLB") or key in {"MAJOR_LEAGUE_BASEBALL"}:
        return "MLB"
    return key


def register_league_adapter(league: str, adapter: LeagueAdapter) -> None:
    _REGISTRY[normalize_league_name(league)] = adapter


def get_league_adapter(league: str | None) -> LeagueAdapter:
    key = normalize_league_name(league)
    return _REGISTRY.get(key, _REGISTRY["MLB"])
