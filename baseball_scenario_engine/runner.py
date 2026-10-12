from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from league_adapters.base import LeagueContext
from league_adapters.registry import get_league_adapter
from .engine import ScenarioEngine, ScenarioOutcome


@dataclass(frozen=True)
class ScenarioRequest:
    league: str
    game_id: str
    home_team: str
    away_team: str
    round_name: str = ""
    base_probs: dict[str, float] | None = None
    features: dict[str, float] | None = None
    context: dict[str, Any] | None = None


class ScenarioRunner:
    def run(self, request: ScenarioRequest) -> ScenarioOutcome:
        adapter = get_league_adapter(request.league)
        ctx = LeagueContext(
            league=request.league,
            game_id=request.game_id,
            home_team=request.home_team,
            away_team=request.away_team,
            round_name=request.round_name,
            weather=(request.context or {}).get("weather", {}),
            odds=(request.context or {}).get("odds", {}),
            roster=(request.context or {}).get("roster", {}),
            pitchers=(request.context or {}).get("pitchers", {}),
            lineups=(request.context or {}).get("lineups", {}),
            bullpen_usage=(request.context or {}).get("bullpen_usage", {}),
            injury_report=(request.context or {}).get("injury_report", {}),
            scenario_tags=(request.context or {}).get("scenario_tags", []),
            venue=(request.context or {}).get("venue", ""),
        )
        engine = ScenarioEngine(adapter)
        return engine.evaluate(ctx, request.base_probs or {}, request.features or {})
