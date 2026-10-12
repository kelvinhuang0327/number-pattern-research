from __future__ import annotations

from .base import LeagueAdapter, LeagueContext, LeagueRuleSet, LeagueSimulationConfig


class MLBLeagueAdapter(LeagueAdapter):
    def name(self) -> str:
        return "MLB"

    def rules(self, context: LeagueContext) -> LeagueRuleSet:
        return LeagueRuleSet(
            league="MLB",
            mode="long_season",
            pitch_limit=None,
            bullpen_fatigue_window_days=3,
            neutral_site=False,
            short_sample_shrinkage=0.10,
            travel_fatigue_weight=0.05,
            lineup_required=True,
            starter_required=True,
            deployment_mode="paper",
            paper_only_reason=(
                "CLV 仍為代理值（無真實歷史賠率時間軸）；"
                "無 Statcast pitch-level 數據；"
                "Brier Skill Score = -14.1%（模型落後市場基準）"
            ),
        )

    def simulation_config(self, context: LeagueContext) -> LeagueSimulationConfig:
        return LeagueSimulationConfig(
            simulations=50_000,
            innings=9,
            allow_extras=True,
            include_mercy_rule=False,
            use_closing_line=True,
        )

    def required_fields(self) -> tuple[str, ...]:
        return (
            "game_id",
            "home_team",
            "away_team",
            "weather",
            "bullpen_usage",
            "lineups",
            "pitchers",
        )

    def feature_transform(self, features: dict[str, float], context: LeagueContext) -> dict[str, float]:
        transformed = dict(features)
        transformed["short_sample_shrinkage"] = min(transformed.get("short_sample_shrinkage", 0.0), 0.10)
        transformed["travel_fatigue_weight"] = max(transformed.get("travel_fatigue_weight", 0.0), 0.05)
        return transformed

    def adjust_probabilities(self, probs: dict[str, float], context: LeagueContext) -> dict[str, float]:
        adjusted = dict(probs)
        if "home_win_prob" in adjusted:
            adjusted["home_win_prob"] = min(0.97, max(0.03, adjusted["home_win_prob"]))
            adjusted["away_win_prob"] = 1.0 - adjusted["home_win_prob"]
        return adjusted
