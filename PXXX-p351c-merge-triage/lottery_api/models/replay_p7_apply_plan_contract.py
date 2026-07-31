"""
replay_p7_apply_plan_contract.py
===================================
P7 Controlled Replay Row Apply — Dry-run Contract.

Defines the plan schema and hard rules for producing a P7 apply plan.

HARD CONSTRAINTS (enforced here and in tests):
  - No DB writes anywhere in this module
  - No replay row generation
  - p7_can_apply must remain False in dry-run phase
  - dry_run_only must be True
  - RETIRED lifecycle → PLAN_MANUAL_REVIEW_REQUIRED in default ONLINE_ONLY scope
  - duplicate_check_key required for every row
  - truth_level = RECONSTRUCTION_DRY_RUN_PLAN
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# P7ApplyDecision
# ---------------------------------------------------------------------------

class P7ApplyDecision:
    """Decision for a single P7 plan row."""

    PLAN_INSERT                  = "PLAN_INSERT"
    PLAN_SKIP_DUPLICATE          = "PLAN_SKIP_DUPLICATE"
    PLAN_SKIP_LIFECYCLE_WARNING  = "PLAN_SKIP_LIFECYCLE_WARNING"
    PLAN_SKIP_INVALID_CANDIDATE  = "PLAN_SKIP_INVALID_CANDIDATE"
    PLAN_SKIP_MISSING_PROVENANCE = "PLAN_SKIP_MISSING_PROVENANCE"
    PLAN_SKIP_MISSING_PAYLOAD    = "PLAN_SKIP_MISSING_PAYLOAD"
    PLAN_MANUAL_REVIEW_REQUIRED  = "PLAN_MANUAL_REVIEW_REQUIRED"

    _INSERT_DECISIONS = frozenset({PLAN_INSERT})
    _SKIP_DECISIONS   = frozenset({
        PLAN_SKIP_DUPLICATE,
        PLAN_SKIP_LIFECYCLE_WARNING,
        PLAN_SKIP_INVALID_CANDIDATE,
        PLAN_SKIP_MISSING_PROVENANCE,
        PLAN_SKIP_MISSING_PAYLOAD,
    })

    _ALL = (
        PLAN_INSERT,
        PLAN_SKIP_DUPLICATE,
        PLAN_SKIP_LIFECYCLE_WARNING,
        PLAN_SKIP_INVALID_CANDIDATE,
        PLAN_SKIP_MISSING_PROVENANCE,
        PLAN_SKIP_MISSING_PAYLOAD,
        PLAN_MANUAL_REVIEW_REQUIRED,
    )

    @classmethod
    def is_insert(cls, decision: str) -> bool:
        return decision in cls._INSERT_DECISIONS

    @classmethod
    def is_skip(cls, decision: str) -> bool:
        return decision in cls._SKIP_DECISIONS


# ---------------------------------------------------------------------------
# P7ApplyScope
# ---------------------------------------------------------------------------

class P7ApplyScope:
    """Scope controlling which candidates are eligible for PLAN_INSERT."""

    ONLINE_ONLY                   = "ONLINE_ONLY"
    INCLUDE_RETIRED_WITH_WARNING  = "INCLUDE_RETIRED_WITH_WARNING"
    MANUAL_REVIEW_ONLY            = "MANUAL_REVIEW_ONLY"

    _ALL = (ONLINE_ONLY, INCLUDE_RETIRED_WITH_WARNING, MANUAL_REVIEW_ONLY)

    # Default scope for P7 dry-run — safest option
    DEFAULT = ONLINE_ONLY


# ---------------------------------------------------------------------------
# P7ApplyPlanRow
# ---------------------------------------------------------------------------

@dataclass
class P7ApplyPlanRow:
    """
    Single row in the P7 dry-run apply plan.

    Maps one P6 approved candidate to a P7 apply decision.
    p7_can_apply is always False in this phase.
    dry_run_only is always True.
    truth_level is always RECONSTRUCTION_DRY_RUN_PLAN.
    """

    # Plan identity
    plan_id:                  str       # generated UUID

    # From P6 candidate
    strategy_id:              str
    lottery_type:             str
    draw_id:                  str        # == target_draw in DB schema
    draw_date:                Optional[str]
    predicted_numbers:        Optional[str]
    source_run_id:            Optional[int]
    source_prediction_item_id: Optional[int]
    provenance_hash:          Optional[str]
    source_tier:              str
    lifecycle_state:          str
    lifecycle_warning:        Optional[str]
    p7_candidate_status:      str

    # P7 decision
    apply_decision:           str  = P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED
    apply_decision_reason:    Optional[str] = None
    scope_applied:            str  = P7ApplyScope.DEFAULT

    # Safety invariants
    dry_run_only:             bool = True   # always True
    p7_can_apply:             bool = False  # always False in dry-run phase
    truth_level:              str  = "RECONSTRUCTION_DRY_RUN_PLAN"
    created_by_phase:         str  = "P7"
    created_at:               Optional[str] = None

    # Duplicate / idempotency
    duplicate_check_key:      Optional[str] = None   # strategy_id:lottery_type:draw_id
    is_duplicate:             bool = False

    # Batch / rollback planning
    rollback_batch_id:        Optional[str] = None   # UUID for batch
    controlled_apply_id:      Optional[str] = None   # UUID for this row's apply token

    def to_dict(self) -> dict:
        return {
            "plan_id":                    self.plan_id,
            "strategy_id":                self.strategy_id,
            "lottery_type":               self.lottery_type,
            "draw_id":                    self.draw_id,
            "draw_date":                  self.draw_date,
            "predicted_numbers":          self.predicted_numbers,
            "source_run_id":              self.source_run_id,
            "source_prediction_item_id":  self.source_prediction_item_id,
            "provenance_hash":            self.provenance_hash,
            "source_tier":                self.source_tier,
            "lifecycle_state":            self.lifecycle_state,
            "lifecycle_warning":          self.lifecycle_warning,
            "p7_candidate_status":        self.p7_candidate_status,
            "apply_decision":             self.apply_decision,
            "apply_decision_reason":      self.apply_decision_reason,
            "scope_applied":              self.scope_applied,
            "dry_run_only":               self.dry_run_only,
            "p7_can_apply":               self.p7_can_apply,
            "truth_level":                self.truth_level,
            "created_by_phase":           self.created_by_phase,
            "created_at":                 self.created_at,
            "duplicate_check_key":        self.duplicate_check_key,
            "is_duplicate":               self.is_duplicate,
            "rollback_batch_id":          self.rollback_batch_id,
            "controlled_apply_id":        self.controlled_apply_id,
        }


# ---------------------------------------------------------------------------
# Duplicate check key helper
# ---------------------------------------------------------------------------

def make_duplicate_check_key(strategy_id: str, lottery_type: str, draw_id: str) -> str:
    """Deterministic composite key for idempotency check."""
    return f"{strategy_id}:{lottery_type}:{draw_id}"


# ---------------------------------------------------------------------------
# apply_decision_for_candidate — core policy
# ---------------------------------------------------------------------------

def apply_decision_for_candidate(
    candidate: dict,
    *,
    scope: str = P7ApplyScope.DEFAULT,
    is_duplicate: bool = False,
) -> tuple[str, Optional[str]]:
    """
    Determine the P7ApplyDecision for a single P6 candidate under a given scope.

    Returns (decision, reason).

    Hard rules:
      1. Missing provenance_hash → PLAN_SKIP_MISSING_PROVENANCE
      2. Missing predicted_numbers → PLAN_SKIP_MISSING_PAYLOAD
      3. is_duplicate → PLAN_SKIP_DUPLICATE
      4. scope=ONLINE_ONLY + RETIRED lifecycle → PLAN_MANUAL_REVIEW_REQUIRED
      5. scope=ONLINE_ONLY + OBSERVATION lifecycle → PLAN_MANUAL_REVIEW_REQUIRED
      6. scope=INCLUDE_RETIRED_WITH_WARNING + RETIRED + no lifecycle_warning → PLAN_MANUAL_REVIEW_REQUIRED
      7. All other valid ONLINE candidates → PLAN_INSERT
      8. INCLUDE_RETIRED_WITH_WARNING + RETIRED + has lifecycle_warning → PLAN_INSERT
         (still dry-run; p7_can_apply remains False)
    """
    D = P7ApplyDecision

    # Gate 1: provenance
    if not candidate.get("provenance_hash"):
        return D.PLAN_SKIP_MISSING_PROVENANCE, "provenance_hash missing or empty"

    # Gate 2: payload
    if not candidate.get("has_predicted_numbers"):
        return D.PLAN_SKIP_MISSING_PAYLOAD, "predicted_numbers missing"

    # Gate 3: duplicate
    if is_duplicate:
        return D.PLAN_SKIP_DUPLICATE, (
            f"duplicate: strategy_id={candidate.get('strategy_id')!r} "
            f"draw_id={candidate.get('draw_id')!r} already in strategy_prediction_replays"
        )

    lifecycle = candidate.get("lifecycle_state", "")
    lc_warning = candidate.get("lifecycle_warning")

    # Gate 4/5: scope ONLINE_ONLY restricts non-ONLINE to manual review
    if scope == P7ApplyScope.ONLINE_ONLY:
        if lifecycle != "ONLINE":
            return D.PLAN_MANUAL_REVIEW_REQUIRED, (
                f"ONLINE_ONLY scope: lifecycle={lifecycle!r} requires manual review. "
                "Use --scope INCLUDE_RETIRED_WITH_WARNING to include RETIRED candidates."
            )
        return D.PLAN_INSERT, None

    # Gate 6: INCLUDE_RETIRED_WITH_WARNING
    if scope == P7ApplyScope.INCLUDE_RETIRED_WITH_WARNING:
        if lifecycle == "ONLINE":
            return D.PLAN_INSERT, None
        if lifecycle in ("RETIRED", "OBSERVATION"):
            if not lc_warning:
                # Retired without warning — should not happen in valid P6 output
                return D.PLAN_MANUAL_REVIEW_REQUIRED, (
                    f"lifecycle={lifecycle!r} is missing lifecycle_warning — manual review required"
                )
            # Retired with lifecycle_warning acknowledged → PLAN_INSERT in dry-run
            return D.PLAN_INSERT, (
                f"INCLUDE_RETIRED_WITH_WARNING scope acknowledged: {lc_warning}"
            )
        # Other lifecycle states
        return D.PLAN_MANUAL_REVIEW_REQUIRED, (
            f"lifecycle={lifecycle!r} not eligible for auto-insert under this scope"
        )

    # Gate 7: MANUAL_REVIEW_ONLY scope
    if scope == P7ApplyScope.MANUAL_REVIEW_ONLY:
        return D.PLAN_MANUAL_REVIEW_REQUIRED, "MANUAL_REVIEW_ONLY scope"

    # Unknown scope → manual review
    return D.PLAN_MANUAL_REVIEW_REQUIRED, f"unknown scope={scope!r}"


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def summarize_p7_plan(
    rows: List[P7ApplyPlanRow],
    *,
    rollback_batch_id: str,
    scope: str,
) -> dict:
    from collections import Counter

    plan_insert      = [r for r in rows if r.apply_decision == P7ApplyDecision.PLAN_INSERT]
    manual_review    = [r for r in rows if r.apply_decision == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED]
    dup_skip         = [r for r in rows if r.apply_decision == P7ApplyDecision.PLAN_SKIP_DUPLICATE]
    other_skip       = [
        r for r in rows
        if r.apply_decision not in (
            P7ApplyDecision.PLAN_INSERT,
            P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED,
        )
    ]

    by_strategy = {}
    for r in rows:
        if r.strategy_id not in by_strategy:
            by_strategy[r.strategy_id] = {
                "strategy_id":   r.strategy_id,
                "lifecycle":     r.lifecycle_state,
                "plan_insert":   0,
                "manual_review": 0,
                "skip":          0,
                "total":         0,
            }
        by_strategy[r.strategy_id]["total"] += 1
        if r.apply_decision == P7ApplyDecision.PLAN_INSERT:
            by_strategy[r.strategy_id]["plan_insert"] += 1
        elif r.apply_decision == P7ApplyDecision.PLAN_MANUAL_REVIEW_REQUIRED:
            by_strategy[r.strategy_id]["manual_review"] += 1
        else:
            by_strategy[r.strategy_id]["skip"] += 1

    by_lc    = Counter(r.lifecycle_state for r in rows)
    by_dec   = Counter(r.apply_decision  for r in rows)

    return {
        "scope":                   scope,
        "rollback_batch_id":       rollback_batch_id,
        "total_p6_candidates":     len(rows),
        "online_candidates":       sum(1 for r in rows if r.lifecycle_state == "ONLINE"),
        "retired_warning_candidates": sum(1 for r in rows if r.lifecycle_state == "RETIRED"),
        "plan_insert_count":       len(plan_insert),
        "manual_review_required_count": len(manual_review),
        "duplicate_skip_count":    len(dup_skip),
        "invalid_candidate_count": len(other_skip),
        "by_strategy":             by_strategy,
        "by_lifecycle_state":      dict(by_lc),
        "by_apply_decision":       dict(by_dec),
        "backup_plan": {
            "description": (
                "Before P7 actual apply, a DB snapshot must be created: "
                "sqlite3 lottery_v2.db .dump > backups/p7_pre_apply_YYYYMMDD.sql"
            ),
            "snapshot_target":  "lottery_api/data/lottery_v2.db",
            "backup_path":      "backups/p7_pre_apply_20260520.sql",
            "verified_row_count_before": 460,
            "rollback_command": (
                "sqlite3 lottery_api/data/lottery_v2.db < backups/p7_pre_apply_20260520.sql"
            ),
        },
        "rollback_plan": {
            "rollback_batch_id": rollback_batch_id,
            "description": (
                "All rows inserted in the P7 apply batch share rollback_batch_id. "
                "Rollback SQL: DELETE FROM strategy_prediction_replays "
                "WHERE controlled_apply_id IN (SELECT controlled_apply_id "
                "FROM p7_apply_log WHERE rollback_batch_id=?)"
            ),
            "rollback_batch_id_param": rollback_batch_id,
            "idempotency_check": (
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND target_draw=? AND lottery_type=?"
            ),
        },
        "safety_flags": {
            "p7_can_apply_globally":     False,
            "dry_run_only_globally":     True,
            "db_write_performed":        False,
            "replay_rows_generated":     False,
            "prediction_rows_generated": False,
        },
        "p7_insert_rows": [r.to_dict() for r in plan_insert],
        "p7_manual_review_rows_sample": [
            r.to_dict()
            for r in manual_review[:5]  # sample only — full list in JSON
        ],
    }
