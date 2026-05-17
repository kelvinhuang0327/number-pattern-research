"""Formal replay lifecycle contract for Strategy Historical Replay.

This module defines the replay-facing lifecycle taxonomy used by replay
fixtures, contract tests, and report generation. It intentionally does not
touch DB state or strategy execution.
"""
from __future__ import annotations

from typing import Iterable


FORMAL_LIFECYCLE_STATES: tuple[str, ...] = (
    "PRODUCTION",
    "WATCHING",
    "PROVISIONAL",
    "REJECTED",
    "OFFLINE",
    "EXPERIMENTAL",
    "UNKNOWN",
)

PRODUCTION_APPLY_ALLOWED_STATES = frozenset({"PRODUCTION", "ONLINE", "ACTIVE"})
PRODUCTION_APPLY_FORBIDDEN_STATES = frozenset(
    {
        "WATCHING",
        "PROVISIONAL",
        "REJECTED",
        "OFFLINE",
        "EXPERIMENTAL",
        "UNKNOWN",
    }
)


def canonicalize_formal_lifecycle_status(value: str | None) -> str:
    """Upper-case and validate a formal replay lifecycle state."""
    if value is None:
        return "UNKNOWN"
    canonical = value.upper()
    if canonical in FORMAL_LIFECYCLE_STATES:
        return canonical
    return "UNKNOWN"


def is_formal_lifecycle_status(value: str | None) -> bool:
    """Return True when value is one of the 7 formal replay lifecycle states."""
    return canonicalize_formal_lifecycle_status(value) in FORMAL_LIFECYCLE_STATES


def can_production_apply(value: str | None) -> bool:
    """Return True only for lifecycle states that are production-apply safe."""
    if value is None:
        return False
    return value.upper() in PRODUCTION_APPLY_ALLOWED_STATES


def normalize_formal_lifecycle_sequence(values: Iterable[str | None]) -> list[str]:
    """Normalize an iterable of lifecycle labels into canonical contract states."""
    return [canonicalize_formal_lifecycle_status(value) for value in values]
