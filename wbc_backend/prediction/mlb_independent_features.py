"""
wbc_backend/prediction/mlb_independent_features.py

P10: Independent baseball feature contract.

Defines MlbIndependentFeatureRow — a validated, leakage-safe container for
independent (non-market) baseball signals used in P10 feature candidate
probability construction.

Hard invariants (enforced in __post_init__):
- leakage_safe must be True.
- recent win rate values must be in [0, 1] if present.
- rest day values must be >= 0 if present.
- feature_source must not be "market".
- feature_version required.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MlbIndependentFeatureRow:
    """Single-game independent feature record.

    All features are computed from pre-game information only.
    Post-game outcomes are NEVER used for the game being predicted.
    """

    game_id: str
    date: str
    home_team: str
    away_team: str

    # Rest features
    home_rest_days: float | None = None
    away_rest_days: float | None = None
    rest_days_delta: float | None = None   # home − away (positive = home more rested)

    # Recent-form features (rolling win rate over lookback_games prior games)
    home_recent_win_rate: float | None = None
    away_recent_win_rate: float | None = None
    recent_win_rate_delta: float | None = None   # home − away

    # Game count available for each team's rolling window
    home_recent_games_count: int | None = None
    away_recent_games_count: int | None = None

    # Starter ERA proxy (rolling avg runs-allowed per start — leakage-safe)
    # Positive starter_era_delta means home starter has HIGHER runs-allowed (worse)
    starter_era_delta: float | None = None
    home_starter_era_proxy: float | None = None
    away_starter_era_proxy: float | None = None

    # Bullpen proxy (from bullpen_usage_last_3d_home/away)
    # Positive = home bullpen more fatigued
    bullpen_proxy_delta: float | None = None
    home_bullpen_usage_3d: float | None = None
    away_bullpen_usage_3d: float | None = None

    # Weather features (pre-game; affects run scoring distribution)
    wind_kmh: float | None = None          # wind speed in km/h at game time
    temp_c: float | None = None            # average temperature in °C
    park_roof_type: str | None = None      # "open" / "retractable" / "dome" / None

    # Metadata
    feature_version: str = "p10_independent_features_v1"
    feature_source: str = "p10_baseball_stats"
    leakage_safe: bool = True
    generated_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_trace: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.leakage_safe:
            raise ValueError(
                f"MlbIndependentFeatureRow {self.game_id}: leakage_safe must be True"
            )
        if self.feature_source.lower() == "market":
            raise ValueError(
                f"MlbIndependentFeatureRow {self.game_id}: feature_source must not be 'market'"
            )
        if not self.feature_version:
            raise ValueError(
                f"MlbIndependentFeatureRow {self.game_id}: feature_version is required"
            )
        # Validate bounds
        for attr_name, lo, hi in [
            ("home_recent_win_rate", 0.0, 1.0),
            ("away_recent_win_rate", 0.0, 1.0),
        ]:
            v = getattr(self, attr_name)
            if v is not None and not (lo <= v <= hi):
                raise ValueError(
                    f"MlbIndependentFeatureRow {self.game_id}: {attr_name}={v} "
                    f"must be in [{lo}, {hi}]"
                )
        for attr_name in ("home_rest_days", "away_rest_days"):
            v = getattr(self, attr_name)
            if v is not None and v < 0:
                raise ValueError(
                    f"MlbIndependentFeatureRow {self.game_id}: {attr_name}={v} must be >= 0"
                )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (datetime → ISO string)."""
        d: dict = {}
        for f in self.__dataclass_fields__:  # type: ignore[attr-defined]
            v = getattr(self, f)
            if isinstance(v, datetime):
                d[f] = v.isoformat()
            elif f == "source_trace":
                d[f] = v
            else:
                d[f] = v
        return d

    def to_jsonl_line(self) -> str:
        """Return a single JSONL line."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
