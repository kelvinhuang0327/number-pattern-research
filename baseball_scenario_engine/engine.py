from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from league_adapters.base import LeagueAdapter, LeagueContext


@dataclass
class ScenarioOutcome:
    league: str
    scenario_tags: list[str]
    adjustments: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class ScenarioEngine:
    def __init__(self, adapter: LeagueAdapter):
        self.adapter = adapter

    def evaluate(self, context: LeagueContext, base_probs: dict[str, float], features: dict[str, float] | None = None) -> ScenarioOutcome:
        features = features or {}
        transformed = self.adapter.feature_transform(features, context)
        adjusted = self.adapter.adjust_probabilities(base_probs, context)
        return ScenarioOutcome(
            league=self.adapter.name(),
            scenario_tags=list(context.scenario_tags),
            adjustments={
                "short_sample_shrinkage": float(transformed.get("short_sample_shrinkage", 0.0)),
                "travel_fatigue_weight": float(transformed.get("travel_fatigue_weight", 0.0)),
                "home_win_prob": float(adjusted.get("home_win_prob", base_probs.get("home_win_prob", 0.5))),
                "away_win_prob": float(adjusted.get("away_win_prob", base_probs.get("away_win_prob", 0.5))),
            },
            diagnostics={
                "missing_context_fields": self.adapter.validate_context(context),
                "rules": self.adapter.rules(context).__dict__,
            },
        )
