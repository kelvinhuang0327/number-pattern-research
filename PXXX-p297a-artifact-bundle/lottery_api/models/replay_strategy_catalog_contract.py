"""
replay_strategy_catalog_contract.py
=====================================
P1 Catalog Visibility Contract — dry-run only.

Defines the canonical catalog_visibility_state enum and the CatalogEntry
dataclass that planner (scripts/p1_catalog_visibility_plan.py) populates.

HARD CONSTRAINTS (P1):
  - can_generate_replay_rows() always returns False — no row generation in P1
  - can_mark_online() returns False unless strategy is already ONLINE in registry
  - dry_run_only=True on all entries from the planner
  - No DB writes, no imports of draw data, no prediction execution

catalog_visibility_state values:
  REGISTERED_WITH_REPLAY_ROWS  — strategy is in DB registry AND has ≥1 replay row
  RECONSTRUCTIBLE              — artifact/log/state exists; rows can be rebuilt (P5-P7)
  REGISTERED_NO_DATA           — in DB registry but zero replay rows; artifact unclear
  ARTIFACT_CANDIDATE           — found in code/artifact scan; NOT in DB registry
  UNSUPPORTED                  — in registry but no artifact, no rows, not reconstructible
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enum-style constants
# ---------------------------------------------------------------------------

class CatalogVisibilityState:
    """Catalog visibility state enum (string constants for JSON compatibility)."""

    REGISTERED_WITH_REPLAY_ROWS = "REGISTERED_WITH_REPLAY_ROWS"
    RECONSTRUCTIBLE             = "RECONSTRUCTIBLE"
    REGISTERED_NO_DATA          = "REGISTERED_NO_DATA"
    ARTIFACT_CANDIDATE          = "ARTIFACT_CANDIDATE"
    UNSUPPORTED                 = "UNSUPPORTED"

    _ALL = (
        REGISTERED_WITH_REPLAY_ROWS,
        RECONSTRUCTIBLE,
        REGISTERED_NO_DATA,
        ARTIFACT_CANDIDATE,
        UNSUPPORTED,
    )

    @classmethod
    def validate(cls, state: str) -> str:
        if state not in cls._ALL:
            raise ValueError(
                f"Invalid catalog_visibility_state {state!r}. "
                f"Must be one of: {cls._ALL}"
            )
        return state


# ---------------------------------------------------------------------------
# Artifact source type
# ---------------------------------------------------------------------------

class ArtifactSourceType:
    """How the artifact that could support reconstruction was found."""

    PREDICTION_LOG     = "PREDICTION_LOG"     # JSONL prediction logger
    STRATEGY_STATE     = "STRATEGY_STATE"     # StrategyState / RSM pickle
    CODE_SCAN          = "CODE_SCAN"          # Found in Python source
    REJECTED_JSON      = "REJECTED_JSON"      # rejected/*.json file
    BACKTEST_REPORT    = "BACKTEST_REPORT"    # backtest_report.md
    REPLAY_RUN         = "REPLAY_RUN"         # strategy_replay_runs row
    NONE               = "NONE"               # no artifact found

    _ALL = (
        PREDICTION_LOG, STRATEGY_STATE, CODE_SCAN,
        REJECTED_JSON, BACKTEST_REPORT, REPLAY_RUN, NONE,
    )


# ---------------------------------------------------------------------------
# Catalog Entry
# ---------------------------------------------------------------------------

@dataclass
class CatalogEntry:
    """
    Single strategy's P1 catalog visibility record.

    All entries produced by the planner have dry_run_only=True.
    Nothing is written to DB during P1.
    """

    # Identity
    strategy_id:              str
    display_name:             str
    lottery_type:             str         # e.g. "DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "MULTI"
    lifecycle_state:          str         # from DB registry (ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED)

    # Visibility classification
    catalog_visibility_state: str         # CatalogVisibilityState constant

    # Source paths discovered during artifact scan (read-only)
    source_paths:             List[str]   = field(default_factory=list)
    artifact_source_type:     str         = ArtifactSourceType.NONE

    # Data presence flags
    has_replay_rows:              bool    = False
    has_historical_predictions:   bool    = False   # in prediction_items / prediction_results
    replay_row_count:             int     = 0

    # Reconstruction metadata
    reconstructible_reason:   Optional[str] = None  # why RECONSTRUCTIBLE
    no_data_reason:           Optional[str] = None  # why NO_DATA / UNSUPPORTED

    # Provenance
    provenance_hash:          Optional[str] = None
    created_by_phase:         str           = "P1"
    dry_run_only:             bool          = True   # always True in P1

    # -----------------------------------------------------------------------
    # Safety helpers — P1 locks these to False/raise
    # -----------------------------------------------------------------------

    def can_generate_replay_rows(self) -> bool:
        """Always False in P1. Row generation is gated to P5-P7."""
        return False

    def can_mark_online(self) -> bool:
        """
        Returns True only if the strategy is already ONLINE in the registry.
        Artifact-only (ARTIFACT_CANDIDATE) strategies may never be marked ONLINE via P1.
        """
        return self.lifecycle_state == "ONLINE"

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "strategy_id":               self.strategy_id,
            "display_name":              self.display_name,
            "lottery_type":              self.lottery_type,
            "lifecycle_state":           self.lifecycle_state,
            "catalog_visibility_state":  self.catalog_visibility_state,
            "source_paths":              self.source_paths,
            "artifact_source_type":      self.artifact_source_type,
            "has_replay_rows":           self.has_replay_rows,
            "has_historical_predictions": self.has_historical_predictions,
            "replay_row_count":          self.replay_row_count,
            "reconstructible_reason":    self.reconstructible_reason,
            "no_data_reason":            self.no_data_reason,
            "provenance_hash":           self.provenance_hash,
            "created_by_phase":          self.created_by_phase,
            "dry_run_only":              self.dry_run_only,
        }


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

def classify_visibility(
    *,
    lifecycle_state: str,
    replay_row_count: int,
    has_historical_predictions: bool,
    artifact_source_type: str,
    is_registered: bool,
) -> str:
    """
    Derive catalog_visibility_state from observed facts.
    This is deterministic and side-effect free.
    """
    if not is_registered:
        # Found in artifact/code scan but not in runtime registry
        return CatalogVisibilityState.ARTIFACT_CANDIDATE

    if replay_row_count > 0:
        return CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS

    # No replay rows — can we reconstruct?
    has_artifact = artifact_source_type not in (ArtifactSourceType.NONE, None)
    if has_artifact or has_historical_predictions:
        return CatalogVisibilityState.RECONSTRUCTIBLE

    if lifecycle_state in ("ONLINE", "OFFLINE", "OBSERVATION"):
        # Registered and active/shadow but truly no data
        return CatalogVisibilityState.REGISTERED_NO_DATA

    # REJECTED or RETIRED with no artifact — unsupported
    return CatalogVisibilityState.UNSUPPORTED
