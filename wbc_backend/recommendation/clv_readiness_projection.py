"""
P8-E — CLV Readiness Projection Module

輸入：historical backfill option availability + forward collection coverage assumptions
輸出：CLV readiness status enum

paper_only=true。不呼叫外部 API。不做 production write。
不代表任何實盤獲利能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CLVReadinessStatus(str, Enum):
    """CLV readiness projection result."""

    HISTORICAL_BACKFILL_READY = "HISTORICAL_BACKFILL_READY"
    """Historical odds source available + ≥500 pregame+closing pairs projected."""

    FORWARD_COLLECTION_ACCUMULATING = "FORWARD_COLLECTION_ACCUMULATING"
    """Forward collection above minimum threshold; CLV analysis possible but growing."""

    BLOCKED_NEEDS_API_KEY = "BLOCKED_NEEDS_API_KEY"
    """Historical backfill path chosen but no API key available."""

    BLOCKED_NO_CLOSING_LINE = "BLOCKED_NO_CLOSING_LINE"
    """Odds source does not provide closing line — CLV undefined."""

    BLOCKED_LOW_COVERAGE = "BLOCKED_LOW_COVERAGE"
    """Pregame+closing pair coverage below minimum threshold."""

    BLOCKED_POST_GAME_PROXY_ONLY = "BLOCKED_POST_GAME_PROXY_ONLY"
    """All available data is POST_GAME_PROXY — no genuine pregame timestamps."""

    BLOCKED_NO_SOURCE = "BLOCKED_NO_SOURCE"
    """No historical or forward odds source configured."""


class BackfillPath(str, Enum):
    """Which backfill / collection path is being evaluated."""

    HISTORICAL_API = "HISTORICAL_API"
    """External paid API for historical pregame/closing odds (e.g., The Odds API)."""

    FORWARD_COLLECTION = "FORWARD_COLLECTION"
    """TSL or equivalent forward-only live odds collection."""

    BOTH = "BOTH"
    """Evaluating both paths simultaneously."""


# Minimum viability thresholds (must match P7 plan)
MIN_PREGAME_CLOSING_PAIRS: int = 200
MIN_PAIR_COVERAGE_PCT: float = 90.0


class CLVReadinessProjectionError(ValueError):
    """Invalid input for CLV readiness projection."""


@dataclass
class CLVReadinessInput:
    """
    Inputs for CLV readiness projection.

    All booleans and counts reflect the PROJECTED state after the chosen path
    is executed — NOT the current state.
    """

    path: BackfillPath
    paper_only: bool

    # Historical API path
    historical_api_available: bool = False
    """True if provider confirmed available (API key required)."""
    historical_api_key_provided: bool = False
    """True only if actual API key has been provided to engineering."""
    historical_has_closing_line: bool = False
    """True if provider offers genuine timestamped closing line."""
    historical_has_pregame_timestamps: bool = False
    """True if provider offers pregame snapshots with captured_at_utc < game_start_utc."""
    historical_projected_pairs: int = 0
    """Projected number of pregame+closing game pairs available after backfill."""
    historical_all_post_game_proxy: bool = False
    """True if all historical records would still be POST_GAME_PROXY."""

    # Forward collection path
    forward_current_pair_coverage_pct: float = 0.0
    """Current pregame+closing pair coverage percentage (0-100)."""
    forward_projected_pair_coverage_pct: float = 0.0
    """Projected coverage at end of accumulation period."""
    forward_current_pairs: int = 0
    """Current count of confirmed pregame+closing pairs."""
    forward_projected_pairs: int = 0
    """Projected count after accumulation."""
    forward_has_closing_line: bool = False
    """True if forward source provides genuine closing line."""

    def __post_init__(self) -> None:
        if self.paper_only is not True:
            raise CLVReadinessProjectionError(
                "CLVReadinessInput: paper_only must be True. "
                "Production evaluation not permitted."
            )
        if not isinstance(self.path, BackfillPath):
            raise CLVReadinessProjectionError(
                f"CLVReadinessInput: path must be BackfillPath enum, got {type(self.path)}"
            )
        if self.forward_current_pair_coverage_pct < 0 or self.forward_current_pair_coverage_pct > 100:
            raise CLVReadinessProjectionError(
                f"CLVReadinessInput: forward_current_pair_coverage_pct must be 0-100, "
                f"got {self.forward_current_pair_coverage_pct}"
            )
        if self.forward_projected_pair_coverage_pct < 0 or self.forward_projected_pair_coverage_pct > 100:
            raise CLVReadinessProjectionError(
                f"CLVReadinessInput: forward_projected_pair_coverage_pct must be 0-100, "
                f"got {self.forward_projected_pair_coverage_pct}"
            )
        if self.historical_projected_pairs < 0:
            raise CLVReadinessProjectionError(
                f"CLVReadinessInput: historical_projected_pairs must be >= 0, "
                f"got {self.historical_projected_pairs}"
            )


@dataclass
class CLVReadinessProjection:
    """Result of CLV readiness projection."""

    path: BackfillPath
    status: CLVReadinessStatus
    reason: str
    projected_pairs: int
    target_pairs: int = MIN_PREGAME_CLOSING_PAIRS
    pair_coverage_pct: float = 0.0
    target_coverage_pct: float = MIN_PAIR_COVERAGE_PCT
    api_key_required: bool = False
    ceo_action_required: bool = False
    estimated_ready_date: Optional[str] = None
    paper_only: bool = True
    annotation: str = (
        "paper_only=true。此預測不代表任何實盤獲利能力。"
        "策略推廣凍結直到 CLV gate 通過。"
    )


def project_clv_readiness(inp: CLVReadinessInput) -> CLVReadinessProjection:
    """
    Given a CLVReadinessInput, project the CLV readiness status.

    Rules (evaluated in priority order):
    1. paper_only=false → raises (handled in __post_init__)
    2. HISTORICAL_API path:
       - all_post_game_proxy → BLOCKED_POST_GAME_PROXY_ONLY
       - api_key not provided → BLOCKED_NEEDS_API_KEY
       - no closing line → BLOCKED_NO_CLOSING_LINE
       - projected_pairs < threshold → BLOCKED_LOW_COVERAGE
       - projected_pairs >= threshold → HISTORICAL_BACKFILL_READY
    3. FORWARD_COLLECTION path:
       - no closing line → BLOCKED_NO_CLOSING_LINE
       - projected coverage < threshold → BLOCKED_LOW_COVERAGE
       - projected pairs < minimum → BLOCKED_LOW_COVERAGE
       - projected coverage >= threshold AND pairs >= minimum → FORWARD_COLLECTION_ACCUMULATING
    4. BOTH: evaluate historical first, fall back to forward
    """
    if inp.path in (BackfillPath.HISTORICAL_API, BackfillPath.BOTH):
        result = _evaluate_historical_path(inp)
        if inp.path == BackfillPath.HISTORICAL_API:
            return result
        # BOTH: if historical is READY, return that; otherwise check forward
        if result.status == CLVReadinessStatus.HISTORICAL_BACKFILL_READY:
            return result
        # Fall through to forward evaluation
        fwd = _evaluate_forward_path(inp)
        # Return better of the two
        if fwd.status == CLVReadinessStatus.FORWARD_COLLECTION_ACCUMULATING:
            return fwd
        return result  # return historical result (which has the primary path context)

    if inp.path == BackfillPath.FORWARD_COLLECTION:
        return _evaluate_forward_path(inp)

    raise CLVReadinessProjectionError(f"Unknown path: {inp.path}")


def _evaluate_historical_path(inp: CLVReadinessInput) -> CLVReadinessProjection:
    """Evaluate historical API backfill path."""
    base = dict(
        path=inp.path,
        projected_pairs=inp.historical_projected_pairs,
        pair_coverage_pct=0.0,
        paper_only=True,
    )

    if inp.historical_all_post_game_proxy:
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_POST_GAME_PROXY_ONLY,
            reason=(
                "Historical source would still yield POST_GAME_PROXY records only. "
                "No genuine pregame timestamps available from this provider."
            ),
            api_key_required=inp.historical_api_key_provided is False,
            ceo_action_required=True,
        )

    if not inp.historical_api_key_provided:
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_NEEDS_API_KEY,
            reason=(
                "Historical API path selected but API key has not been provided. "
                "CEO purchase decision required before P9 can proceed."
            ),
            api_key_required=True,
            ceo_action_required=True,
        )

    if not inp.historical_has_closing_line:
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_NO_CLOSING_LINE,
            reason=(
                "Historical odds source does not provide a genuine closing line. "
                "CLV calculation requires closing line (captured_at_utc near game_start_utc)."
            ),
            api_key_required=False,
            ceo_action_required=False,
        )

    if inp.historical_projected_pairs < MIN_PREGAME_CLOSING_PAIRS:
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_LOW_COVERAGE,
            reason=(
                f"Historical source projected to yield only {inp.historical_projected_pairs} "
                f"pregame+closing pairs, below minimum threshold of {MIN_PREGAME_CLOSING_PAIRS}."
            ),
            api_key_required=False,
            ceo_action_required=False,
        )

    return CLVReadinessProjection(
        **base,
        status=CLVReadinessStatus.HISTORICAL_BACKFILL_READY,
        reason=(
            f"Historical API backfill projected to yield {inp.historical_projected_pairs} "
            f"pregame+closing pairs (>= {MIN_PREGAME_CLOSING_PAIRS} threshold). "
            "CLV analysis unblocked after P9 integration."
        ),
        api_key_required=False,
        ceo_action_required=False,
    )


def _evaluate_forward_path(inp: CLVReadinessInput) -> CLVReadinessProjection:
    """Evaluate forward collection path."""
    base = dict(
        path=inp.path,
        projected_pairs=inp.forward_projected_pairs,
        pair_coverage_pct=inp.forward_projected_pair_coverage_pct,
        paper_only=True,
    )

    if not inp.forward_has_closing_line:
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_NO_CLOSING_LINE,
            reason=(
                "Forward collection source does not provide a closing line. "
                "CLV requires closing line snapshot captured before game_start_utc."
            ),
            api_key_required=False,
            ceo_action_required=False,
        )

    if (
        inp.forward_projected_pair_coverage_pct < MIN_PAIR_COVERAGE_PCT
        or inp.forward_projected_pairs < MIN_PREGAME_CLOSING_PAIRS
    ):
        return CLVReadinessProjection(
            **base,
            status=CLVReadinessStatus.BLOCKED_LOW_COVERAGE,
            reason=(
                f"Forward collection projected coverage {inp.forward_projected_pair_coverage_pct:.1f}% "
                f"or pair count {inp.forward_projected_pairs} below minimum thresholds "
                f"({MIN_PAIR_COVERAGE_PCT}% / {MIN_PREGAME_CLOSING_PAIRS} pairs)."
            ),
            api_key_required=False,
            ceo_action_required=False,
        )

    return CLVReadinessProjection(
        **base,
        status=CLVReadinessStatus.FORWARD_COLLECTION_ACCUMULATING,
        reason=(
            f"Forward collection projected to reach {inp.forward_projected_pair_coverage_pct:.1f}% "
            f"coverage with {inp.forward_projected_pairs} pairs. "
            "CLV analysis possible when threshold is sustained."
        ),
        api_key_required=False,
        ceo_action_required=False,
    )
