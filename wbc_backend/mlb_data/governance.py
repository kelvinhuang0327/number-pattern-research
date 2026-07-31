from __future__ import annotations

from copy import deepcopy
from typing import Any


MLB_GOVERNANCE_FLAGS: dict[str, Any] = {
    "execution_mode": "PAPER_ONLY",
    "clv_mode": "SANDBOX_ONLY",
    "decision_quality_scale": "UNAVAILABLE",
    "live_recommendation": "disabled",
    "live_sizing": "disabled",
    "live_execution": "disabled",
    "promotion_guard": "FROZEN_UNTIL_GENUINE_PREGAME_ODDS_AVAILABLE",
}


SPRING_TRAINING_GOVERNANCE_FLAGS: dict[str, Any] = {
    "execution_mode": "SANDBOX_ONLY",
    "betting_advice": "NOT_RECOMMENDED_FOR_BETTING",
    "clv_mode": "UNAVAILABLE",
    "decision_quality_scale": "SANDBOX_ONLY",
    "live_recommendation": "disabled",
    "live_sizing": "disabled",
    "live_execution": "disabled",
    "metrics_pool": "SPRING_SANDBOX_ONLY",
    "promotion_guard": "SPRING_SANDBOX_ONLY",
}


def mlb_governance_flags() -> dict[str, Any]:
    return deepcopy(MLB_GOVERNANCE_FLAGS)


def spring_training_governance_flags() -> dict[str, Any]:
    return deepcopy(SPRING_TRAINING_GOVERNANCE_FLAGS)
