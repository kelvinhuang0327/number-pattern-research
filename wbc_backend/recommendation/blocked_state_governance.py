"""P12-B — Blocked-State Governance Contract.

Defines blocked reasons, allowed actions, and forbidden actions to prevent
the system from advancing into optimizer / promotion / production tasks
while CEO decision is pending or CLV gate is not cleared.

All operations are paper_only. No network calls. No crawler modification.
"""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BlockedReason(str, Enum):
    """Why the system is in a blocked state."""

    CEO_DECISION_PENDING = "CEO_DECISION_PENDING"
    API_KEY_MISSING = "API_KEY_MISSING"
    POST_GAME_PROXY_ONLY = "POST_GAME_PROXY_ONLY"
    NO_CLOSING_LINE = "NO_CLOSING_LINE"
    FORWARD_ACCUMULATION_INSUFFICIENT = "FORWARD_ACCUMULATION_INSUFFICIENT"
    CLV_NOT_READY = "CLV_NOT_READY"
    PROMOTION_FROZEN = "PROMOTION_FROZEN"


class AllowedAction(str, Enum):
    """Actions permitted regardless of blocked state."""

    CEO_FOLLOWUP = "CEO_FOLLOWUP"
    PAPER_ONLY_MONITORING = "PAPER_ONLY_MONITORING"
    FORWARD_COVERAGE_READINESS_CHECK = "FORWARD_COVERAGE_READINESS_CHECK"
    API_KEY_READINESS_CHECK = "API_KEY_READINESS_CHECK"
    REPORT_ONLY = "REPORT_ONLY"


class ForbiddenAction(str, Enum):
    """Actions explicitly forbidden while blocked constraints hold."""

    OPTIMIZER_PROMOTION = "OPTIMIZER_PROMOTION"
    PRODUCTION_PROPOSAL = "PRODUCTION_PROPOSAL"
    LIVE_ODDS_WRITE = "LIVE_ODDS_WRITE"
    TSL_CRAWLER_MODIFICATION = "TSL_CRAWLER_MODIFICATION"
    HISTORICAL_API_CALL_WITHOUT_APPROVAL = "HISTORICAL_API_CALL_WITHOUT_APPROVAL"
    PROFITABILITY_CLAIM = "PROFITABILITY_CLAIM"
    NEW_ROADMAP_EXPANSION = "NEW_ROADMAP_EXPANSION"
    NEW_BACKFILL_WITHOUT_DECISION = "NEW_BACKFILL_WITHOUT_DECISION"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALWAYS_ALLOWED: FrozenSet[AllowedAction] = frozenset(AllowedAction)
ALWAYS_FORBIDDEN: FrozenSet[ForbiddenAction] = frozenset(ForbiddenAction)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GovernanceViolationError(RuntimeError):
    """Raised when a forbidden action is attempted in a blocked state."""


class PaperOnlyViolationError(RuntimeError):
    """Raised when paper_only=False is passed to a governance function."""


# ---------------------------------------------------------------------------
# Core governance checker
# ---------------------------------------------------------------------------

class BlockedStateGovernance:
    """Evaluates whether an action is permitted given the current blocked state.

    This class is intentionally stateless — callers pass all state flags at
    construction time. No I/O, no network, no mutations.
    """

    def __init__(
        self,
        *,
        ceo_decision_pending: bool,
        api_key_missing: bool,
        post_game_proxy_only: bool,
        no_closing_line: bool,
        forward_accumulation_insufficient: bool,
        clv_not_ready: bool,
        promotion_frozen: bool,
        paper_only: bool = True,
    ) -> None:
        if not paper_only:
            raise PaperOnlyViolationError(
                "BlockedStateGovernance must be instantiated with paper_only=True. "
                "Live governance writes are not permitted."
            )
        self.paper_only = paper_only

        # Build active blocked reasons
        self._blocked_reasons: list[BlockedReason] = []
        if ceo_decision_pending:
            self._blocked_reasons.append(BlockedReason.CEO_DECISION_PENDING)
        if api_key_missing:
            self._blocked_reasons.append(BlockedReason.API_KEY_MISSING)
        if post_game_proxy_only:
            self._blocked_reasons.append(BlockedReason.POST_GAME_PROXY_ONLY)
        if no_closing_line:
            self._blocked_reasons.append(BlockedReason.NO_CLOSING_LINE)
        if forward_accumulation_insufficient:
            self._blocked_reasons.append(BlockedReason.FORWARD_ACCUMULATION_INSUFFICIENT)
        if clv_not_ready:
            self._blocked_reasons.append(BlockedReason.CLV_NOT_READY)
        if promotion_frozen:
            self._blocked_reasons.append(BlockedReason.PROMOTION_FROZEN)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def blocked_reasons(self) -> list[BlockedReason]:
        """Return the list of active blocked reasons (may be empty)."""
        return list(self._blocked_reasons)

    @property
    def is_blocked(self) -> bool:
        """True if any blocked reason is active."""
        return bool(self._blocked_reasons)

    def is_action_allowed(self, action: AllowedAction) -> bool:
        """An AllowedAction is always permitted regardless of blocked state."""
        return action in ALWAYS_ALLOWED

    def is_action_forbidden(self, action: ForbiddenAction) -> bool:
        """A ForbiddenAction is forbidden whenever the system is in blocked state."""
        if not self.is_blocked:
            return False
        return action in ALWAYS_FORBIDDEN

    def assert_action_not_forbidden(self, action: ForbiddenAction) -> None:
        """Raise GovernanceViolationError if the action is forbidden."""
        if self.is_action_forbidden(action):
            reasons = ", ".join(r.value for r in self._blocked_reasons)
            raise GovernanceViolationError(
                f"Action '{action.value}' is forbidden. "
                f"Active blocked reasons: [{reasons}]"
            )

    def p13_allowed(self) -> bool:
        """P13 (CLV validation) may only start when no blocking reasons remain."""
        return not self.is_blocked

    def p14_allowed(self) -> bool:
        """P14 (no-expansion guard) may only proceed when no blocking reasons remain."""
        return not self.is_blocked

    def p15_allowed(self) -> bool:
        """P15 (no-expansion watch + CEO escalation) may only proceed when no blocking reasons remain."""
        return not self.is_blocked

    def p16_allowed(self) -> bool:
        """P16 (no-expansion hold + CEO response gate) may only proceed when no blocking reasons remain."""
        return not self.is_blocked

    def p17_allowed(self) -> bool:
        """P17 (hold-state continuity check) may only proceed when no blocking reasons remain."""
        return not self.is_blocked

    def to_dict(self) -> dict:
        """Serialise governance state to a paper-only dict."""
        return {
            "paper_only": self.paper_only,
            "is_blocked": self.is_blocked,
            "blocked_reasons": [r.value for r in self._blocked_reasons],
            "allowed_actions": [a.value for a in sorted(ALWAYS_ALLOWED, key=lambda x: x.value)],
            "forbidden_actions": [f.value for f in sorted(ALWAYS_FORBIDDEN, key=lambda x: x.value)],
            "p13_allowed": self.p13_allowed(),
            "p14_allowed": self.p14_allowed(),
            "p15_allowed": self.p15_allowed(),
            "p16_allowed": self.p16_allowed(),
            "p17_allowed": self.p17_allowed(),
            "network_call": False,
            "crawler_modified": False,
        }
