"""
replay_reconstruction_plan_contract.py
========================================
P5 Reconstruction Plan Contract.

Defines the per-row plan entry for the P5 Historical Reconstruction Dry-run.

HARD CONSTRAINTS:
  - can_apply() always returns False in P5
  - dry_run_only always True
  - truth_level always RECONSTRUCTION_PLAN_ONLY
  - ARTIFACT_CANDIDATE cannot produce a plan row
  - NO_DATA cannot produce a plan row
  - REGISTERED_WITH_REPLAY_ROWS already-covered cells must SKIP_ALREADY_COVERED
  - No prediction numbers may be invented; only propagated from existing payload
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class PlannedAction:
    PLAN_INSERT_REPLAY_ROW   = "PLAN_INSERT_REPLAY_ROW"   # has payload; ready for P7
    SKIP_SOURCE_MISSING      = "SKIP_SOURCE_MISSING"       # no artifact at all
    SKIP_NO_HISTORICAL_PAYLOAD = "SKIP_NO_HISTORICAL_PAYLOAD"  # has source; no payload for this draw
    SKIP_PROVENANCE_MISSING  = "SKIP_PROVENANCE_MISSING"   # artifact exists but provenance broken
    SKIP_UNSAFE              = "SKIP_UNSAFE"               # safety constraint blocks
    SKIP_ALREADY_COVERED     = "SKIP_ALREADY_COVERED"      # replay row already exists
    SKIP_ARTIFACT_ONLY       = "SKIP_ARTIFACT_ONLY"        # ARTIFACT_CANDIDATE; needs P6
    NEEDS_P6_POLICY          = "NEEDS_P6_POLICY"           # CODE_SCAN; re-run blocked until P6

    _ALL = (
        PLAN_INSERT_REPLAY_ROW,
        SKIP_SOURCE_MISSING,
        SKIP_NO_HISTORICAL_PAYLOAD,
        SKIP_PROVENANCE_MISSING,
        SKIP_UNSAFE,
        SKIP_ALREADY_COVERED,
        SKIP_ARTIFACT_ONLY,
        NEEDS_P6_POLICY,
    )

    @classmethod
    def is_skip(cls, action: str) -> bool:
        return action != cls.PLAN_INSERT_REPLAY_ROW


class TrustLevel:
    ARTIFACT_DERIVED  = "ARTIFACT_DERIVED"   # from prediction_items payload
    LOG_DERIVED       = "LOG_DERIVED"         # from JSONL prediction log
    STATE_DERIVED     = "STATE_DERIVED"       # from StrategyState pickle
    UNKNOWN           = "UNKNOWN"

class TruthLevel:
    RECONSTRUCTION_PLAN_ONLY = "RECONSTRUCTION_PLAN_ONLY"  # P5: plan only, never a real replay row


# ---------------------------------------------------------------------------
# Plan row dataclass
# ---------------------------------------------------------------------------

@dataclass
class ReconstructionPlanRow:
    plan_id:                   str
    strategy_id:               str
    lottery_type:              str
    draw_id:                   str
    draw_date:                 Optional[str]
    catalog_visibility_state:  str            # must be RECONSTRUCTIBLE
    coverage_status_before:    str            # from P4 matrix (RECONSTRUCTIBLE_PENDING)
    planned_action:            str            # PlannedAction constant
    source_paths:              list           = field(default_factory=list)
    artifact_source_type:      str            = "NONE"
    provenance_hash:           Optional[str]  = None
    provenance_source:         Optional[str]  = None
    reconstruction_reason:     Optional[str]  = None
    skip_reason:               Optional[str]  = None
    trust_level:               str            = TrustLevel.UNKNOWN
    truth_level:               str            = TruthLevel.RECONSTRUCTION_PLAN_ONLY
    predicted_numbers:         Optional[list] = None   # only populated if payload exists
    predicted_special:         Optional[int]  = None
    item_count:                int            = 0      # bets in payload
    run_id:                    Optional[int]  = None
    dry_run_only:              bool           = True
    created_by_phase:          str            = "P5"
    created_at:                str            = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def can_apply(self) -> bool:
        """Always False in P5. P7 Controlled Apply is the gate."""
        return False

    def is_plannable(self) -> bool:
        return self.planned_action == PlannedAction.PLAN_INSERT_REPLAY_ROW

    def to_dict(self) -> dict:
        return {
            "plan_id":                  self.plan_id,
            "strategy_id":              self.strategy_id,
            "lottery_type":             self.lottery_type,
            "draw_id":                  self.draw_id,
            "draw_date":                self.draw_date,
            "catalog_visibility_state": self.catalog_visibility_state,
            "coverage_status_before":   self.coverage_status_before,
            "planned_action":           self.planned_action,
            "source_paths":             self.source_paths,
            "artifact_source_type":     self.artifact_source_type,
            "provenance_hash":          self.provenance_hash,
            "provenance_source":        self.provenance_source,
            "reconstruction_reason":    self.reconstruction_reason,
            "skip_reason":              self.skip_reason,
            "trust_level":              self.trust_level,
            "truth_level":              self.truth_level,
            "predicted_numbers":        self.predicted_numbers,
            "predicted_special":        self.predicted_special,
            "item_count":               self.item_count,
            "run_id":                   self.run_id,
            "dry_run_only":             self.dry_run_only,
            "can_apply":                self.can_apply(),
            "created_by_phase":         self.created_by_phase,
            "created_at":               self.created_at,
        }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_plan_row(row: ReconstructionPlanRow) -> list[str]:
    """Return list of validation errors; empty means OK."""
    errors: list[str] = []

    if not row.dry_run_only:
        errors.append("dry_run_only must be True in P5")
    if row.can_apply():
        errors.append("can_apply must return False in P5")
    if row.truth_level != TruthLevel.RECONSTRUCTION_PLAN_ONLY:
        errors.append(f"truth_level must be RECONSTRUCTION_PLAN_ONLY, got {row.truth_level!r}")
    if row.catalog_visibility_state != "RECONSTRUCTIBLE":
        errors.append(
            f"Only RECONSTRUCTIBLE entries produce plan rows; "
            f"got {row.catalog_visibility_state!r}"
        )
    if row.planned_action not in PlannedAction._ALL:
        errors.append(f"Unknown planned_action: {row.planned_action!r}")
    if row.planned_action == PlannedAction.PLAN_INSERT_REPLAY_ROW:
        if not row.provenance_hash:
            errors.append("PLAN_INSERT_REPLAY_ROW requires provenance_hash")
        if row.predicted_numbers is None:
            errors.append("PLAN_INSERT_REPLAY_ROW requires predicted_numbers from payload")
    return errors
