from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LeagueRuleSet:
    league: str
    mode: str
    pitch_limit: int | None = None
    bullpen_fatigue_window_days: int = 3
    neutral_site: bool = False
    short_sample_shrinkage: float = 0.0
    travel_fatigue_weight: float = 0.0
    lineup_required: bool = True
    starter_required: bool = True
    deployment_mode: str = "live"  # "live" | "paper" | "disabled"
    paper_only_reason: str = ""    # 供 gate log 說明 paper 原因


@dataclass(frozen=True)
class LeagueSimulationConfig:
    simulations: int = 25_000
    innings: int = 9
    allow_extras: bool = True
    include_mercy_rule: bool = False
    use_closing_line: bool = True


@dataclass
class LeagueContext:
    league: str
    game_id: str
    home_team: str
    away_team: str
    round_name: str = ""
    venue: str = ""
    weather: dict[str, Any] = field(default_factory=dict)
    odds: dict[str, Any] = field(default_factory=dict)
    roster: dict[str, Any] = field(default_factory=dict)
    pitchers: dict[str, Any] = field(default_factory=dict)
    lineups: dict[str, Any] = field(default_factory=dict)
    bullpen_usage: dict[str, Any] = field(default_factory=dict)
    injury_report: dict[str, Any] = field(default_factory=dict)
    scenario_tags: list[str] = field(default_factory=list)


class LeagueAdapter(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def rules(self, context: LeagueContext) -> LeagueRuleSet:
        raise NotImplementedError

    @abstractmethod
    def simulation_config(self, context: LeagueContext) -> LeagueSimulationConfig:
        raise NotImplementedError

    @abstractmethod
    def required_fields(self) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def feature_transform(self, features: dict[str, float], context: LeagueContext) -> dict[str, float]:
        raise NotImplementedError

    @abstractmethod
    def adjust_probabilities(self, probs: dict[str, float], context: LeagueContext) -> dict[str, float]:
        raise NotImplementedError

    def validate_context(self, context: LeagueContext) -> list[str]:
        missing = []
        for field_name in self.required_fields():
            value = getattr(context, field_name, None)
            if value in (None, "", {}, []):
                missing.append(field_name)
        return missing

    # Legacy compatibility hooks.
    def get_config(self) -> Any:
        return {
            "rules": self.rules(
                LeagueContext(
                    league=self.name(),
                    game_id="",
                    home_team="",
                    away_team="",
                )
            ),
            "simulation": self.simulation_config(
                LeagueContext(
                    league=self.name(),
                    game_id="",
                    home_team="",
                    away_team="",
                )
            ),
        }

    def adjust_run_expectancy(self, base_lam: float, inning: int, context: dict[str, Any]) -> float:
        if inning <= 0:
            return max(0.05, base_lam / 9.0)
        return max(0.05, base_lam / 9.0)

    def adjust_elo(self, raw_elo: float, team_code: str, context: dict[str, Any]) -> float:
        return raw_elo

    def bullpen_transition_inning(self, pitch_count_limit: int = 100) -> float:
        return 6.0
