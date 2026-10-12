"""
Cold-Start Integration: wire MAML meta-learner into stacking model.

Usage:
    from learning.cold_start import get_cold_start_adapter

    adapter = get_cold_start_adapter()
    # After each game result:
    adapter.observe(game_result_dict)
    # Before each prediction:
    weights = adapter.get_adapted_weights()
"""
from __future__ import annotations

from typing import Dict, List, Optional

from models.maml_meta_learner import MAMLWeightLearner

# Singleton
_adapter: Optional[ColdStartAdapter] = None


class ColdStartAdapter:
    """
    Wraps MAMLWeightLearner for live tournament use.

    Tracks observed games in the current tournament and returns
    adapted weights that improve as more games are observed.
    Designed to stabilize after ~5 games ("5 場後穩定").
    """

    def __init__(self) -> None:
        self._learner = MAMLWeightLearner()
        self._observed: List[Dict] = []
        self._adapted_weights: Optional[Dict[str, float]] = None

    def observe(
        self,
        model_probs: Dict[str, float],
        actual_home_win: int,
    ) -> None:
        """Record one observed game result and re-adapt weights."""
        self._observed.append({
            "model_probs": model_probs,
            "actual_home_win": actual_home_win,
        })
        # Progressive adaptation: more steps as we get more data
        n_steps = min(len(self._observed), 3)
        self._adapted_weights = self._learner.adapt(
            self._observed, n_steps=n_steps,
        )

    def get_adapted_weights(self) -> Dict[str, float]:
        """Return current adapted weights (or meta-init if no games yet)."""
        if self._adapted_weights is not None:
            return dict(self._adapted_weights)
        return self._learner.get_cold_start_weights()

    @property
    def games_observed(self) -> int:
        return len(self._observed)

    @property
    def is_stabilized(self) -> bool:
        """Target: stable after 5 games."""
        return len(self._observed) >= 5


def get_cold_start_adapter() -> ColdStartAdapter:
    """Get or create the singleton ColdStartAdapter."""
    global _adapter
    if _adapter is None:
        _adapter = ColdStartAdapter()
    return _adapter
