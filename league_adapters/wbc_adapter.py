from __future__ import annotations

from dataclasses import replace

from .base import LeagueAdapter, LeagueContext, LeagueRuleSet, LeagueSimulationConfig


class WBCLeagueAdapter(LeagueAdapter):
    def name(self) -> str:
        return "WBC"

    def rules(self, context: LeagueContext) -> LeagueRuleSet:
        pitch_limit = 65 if context.round_name.lower().startswith("pool") else 80
        if context.round_name.lower() in {"qf", "sf", "final"}:
            pitch_limit = 95
        return LeagueRuleSet(
            league="WBC",
            mode="tournament",
            pitch_limit=pitch_limit,
            bullpen_fatigue_window_days=2,
            neutral_site=True,
            short_sample_shrinkage=0.35,
            travel_fatigue_weight=0.20,
            lineup_required=True,
            starter_required=True,
        )

    def simulation_config(self, context: LeagueContext) -> LeagueSimulationConfig:
        return LeagueSimulationConfig(
            simulations=15_000,
            innings=9,
            allow_extras=False,
            include_mercy_rule=True,
            use_closing_line=False,
        )

    def required_fields(self) -> tuple[str, ...]:
        return ("game_id", "home_team", "away_team")

    def feature_transform(self, features: dict[str, float], context: LeagueContext) -> dict[str, float]:
        transformed = dict(features)
        transformed["short_sample_shrinkage"] = max(transformed.get("short_sample_shrinkage", 0.0), 0.35)
        transformed["travel_fatigue_weight"] = max(transformed.get("travel_fatigue_weight", 0.0), 0.20)
        return transformed

    def adjust_probabilities(self, probs: dict[str, float], context: LeagueContext) -> dict[str, float]:
        adjusted = dict(probs)
        if "home_win_prob" in adjusted:
            adjusted["home_win_prob"] = min(0.95, max(0.05, adjusted["home_win_prob"]))
            adjusted["away_win_prob"] = 1.0 - adjusted["home_win_prob"]
        return adjusted
