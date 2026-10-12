"""
wbc_backend/prediction/mlb_model_probability.py

Contract dataclass for per-game MLB model win probabilities.

Invariants:
  - model_prob_home in [0, 1]
  - model_prob_away in [0, 1]
  - abs(model_prob_home + model_prob_away - 1.0) <= 0.01
  - probability_source must be one of the Literal values
  - "market_proxy" must never be labelled "real_model"
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

VALID_PROBABILITY_SOURCES = frozenset({
    "real_model",
    "calibrated_model",
    "market_proxy",
    "fixture",
    "walk_forward_ml_candidate",
})

ProbabilitySource = Literal[
    "real_model",
    "calibrated_model",
    "market_proxy",
    "fixture",
    "walk_forward_ml_candidate",
]


@dataclass
class MlbModelProbability:
    """
    Per-game MLB model win probability record.

    Fields
    ------
    game_id : str | None
        Canonical game identifier (may be None for legacy rows without ID).
    game_date : str
        YYYY-MM-DD date string.
    home_team : str
        Home team name or 3-letter code.
    away_team : str
        Away team name or 3-letter code.
    model_prob_home : float
        Model probability of home team winning, in [0, 1].
    model_prob_away : float
        Model probability of away team winning, in [0, 1].
    model_version : str
        Model version identifier (e.g., "v1-mlb-moneyline-trained").
    probability_source : ProbabilitySource
        Source type — must be one of: real_model, calibrated_model,
        market_proxy, fixture.
    generated_at_utc : datetime
        UTC timestamp when this probability was generated.
    source_trace : dict
        Audit dictionary with provenance metadata.
    """

    game_id: str | None
    game_date: str
    home_team: str
    away_team: str
    model_prob_home: float
    model_prob_away: float
    model_version: str
    probability_source: ProbabilitySource
    generated_at_utc: datetime
    source_trace: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate probability range
        if not (0.0 <= self.model_prob_home <= 1.0):
            raise ValueError(
                f"model_prob_home must be in [0, 1], got {self.model_prob_home}"
            )
        if not (0.0 <= self.model_prob_away <= 1.0):
            raise ValueError(
                f"model_prob_away must be in [0, 1], got {self.model_prob_away}"
            )
        # Validate sum-to-one (within tolerance)
        total = self.model_prob_home + self.model_prob_away
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"model_prob_home + model_prob_away must sum to ~1.0 "
                f"(tolerance 0.01), got {total:.6f}"
            )
        # Validate probability source
        if self.probability_source not in VALID_PROBABILITY_SOURCES:
            raise ValueError(
                f"probability_source must be one of {sorted(VALID_PROBABILITY_SOURCES)}, "
                f"got {self.probability_source!r}"
            )
        # Hard invariant: market_proxy must never be labelled real_model
        # (enforced at construction to prevent accidental mislabelling)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "game_date": self.game_date,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "model_prob_home": round(self.model_prob_home, 6),
            "model_prob_away": round(self.model_prob_away, 6),
            "model_version": self.model_version,
            "probability_source": self.probability_source,
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "source_trace": self.source_trace,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
