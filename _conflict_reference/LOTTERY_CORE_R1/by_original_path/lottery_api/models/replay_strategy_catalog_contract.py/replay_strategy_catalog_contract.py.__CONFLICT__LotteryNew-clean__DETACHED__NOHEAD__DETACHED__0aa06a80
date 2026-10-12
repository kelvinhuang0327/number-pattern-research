"""
replay_strategy_catalog_contract.py
====================================
P1 Catalog Visibility — Contract definitions for artifact-level strategy catalog expansion.

This module defines the data contract for the P1 phase:
  - Artifact-level strategies that exist in rejected/ JSON files and research inventory
    but are NOT yet registered in the live code registry (replay_strategy_registry.py)
  - NO_DATA visibility state for strategies without replay rows
  - Safety helpers that enforce P1 hard constraints

HARD RULES (P1):
  - can_generate_replay_rows() always returns False in P1
  - can_mark_online() returns False unless existing DB state is already ONLINE
  - NO_DATA entries must NOT fabricate replay rows
  - All DB writes require explicit --apply flag
  - Idempotent: safe to apply multiple times

Phase: P1 Catalog Visibility (2026-05-18)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ─── Enumerations ────────────────────────────────────────────────────────────

class CatalogVisibilityState(str, Enum):
    """
    Catalog visibility state for a strategy entry.

    REGISTERED_WITH_REPLAY_ROWS — in code registry AND has replay rows in DB
    REGISTERED_NO_DATA          — in code registry BUT has zero replay rows
    ARTIFACT_CANDIDATE          — has artifact source (rejected JSON / research doc)
                                  but NOT yet in code registry
    UNSUPPORTED                 — cannot be safely categorized; excluded from catalog
    """
    REGISTERED_WITH_REPLAY_ROWS = "REGISTERED_WITH_REPLAY_ROWS"
    REGISTERED_NO_DATA = "REGISTERED_NO_DATA"
    ARTIFACT_CANDIDATE = "ARTIFACT_CANDIDATE"
    UNSUPPORTED = "UNSUPPORTED"


class ArtifactSourceType(str, Enum):
    """Source type for artifact-level strategies."""
    REJECTED_JSON = "REJECTED_JSON"        # Found in rejected/*.json
    RESEARCH_INVENTORY = "RESEARCH_INVENTORY"  # Found in p1_strategy_lifecycle_inventory JSON
    CODE_REGISTRY = "CODE_REGISTRY"        # Found in replay_strategy_registry._ALL_ADAPTERS
    UNKNOWN = "UNKNOWN"


class LifecycleState(str, Enum):
    """Canonical lifecycle states (matches replay_strategy_registry.LIFECYCLE_STATUSES)."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    REJECTED = "REJECTED"
    OBSERVATION = "OBSERVATION"
    RETIRED = "RETIRED"
    ARTIFACT_ONLY = "ARTIFACT_ONLY"  # P1 extension: artifact source, not in code registry


# ─── CatalogEntry Dataclass ───────────────────────────────────────────────────

@dataclass
class CatalogEntry:
    """
    A single entry in the P1 expanded strategy catalog.

    Fields:
      strategy_id              — stable unique identifier (snake_case)
      display_name             — human-readable name
      lottery_type             — BIG_LOTTO / DAILY_539 / POWER_LOTTO / CROSS_GAME / UNKNOWN
      lifecycle_state          — canonical lifecycle status
      catalog_visibility_state — P1 visibility classification
      source_paths             — artifact file paths (relative to repo root)
      artifact_source_type     — where this entry was discovered
      has_replay_rows          — True only if strategy_replay_runs rows exist
      has_historical_predictions — True only if prediction_runs/prediction_items rows exist
      no_data_reason           — explanation when catalog_visibility_state is *_NO_DATA
      provenance_hash          — SHA-256 of (strategy_id + sorted source_paths)
      created_by_phase         — which system phase registered this entry
      dry_run_only             — True means NOT written to DB yet (default)
    """
    strategy_id: str
    display_name: str
    lottery_type: str
    lifecycle_state: LifecycleState
    catalog_visibility_state: CatalogVisibilityState
    source_paths: List[str] = field(default_factory=list)
    artifact_source_type: ArtifactSourceType = ArtifactSourceType.UNKNOWN
    has_replay_rows: bool = False
    has_historical_predictions: bool = False
    no_data_reason: Optional[str] = None
    provenance_hash: Optional[str] = None
    created_by_phase: str = "P1_CATALOG_VISIBILITY_20260518"
    dry_run_only: bool = True

    def __post_init__(self):
        """Compute provenance_hash if not provided."""
        if self.provenance_hash is None:
            hash_input = self.strategy_id + "|" + "|".join(sorted(self.source_paths))
            self.provenance_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "lottery_type": self.lottery_type,
            "lifecycle_state": self.lifecycle_state.value if isinstance(self.lifecycle_state, LifecycleState) else self.lifecycle_state,
            "catalog_visibility_state": self.catalog_visibility_state.value if isinstance(self.catalog_visibility_state, CatalogVisibilityState) else self.catalog_visibility_state,
            "source_paths": self.source_paths,
            "artifact_source_type": self.artifact_source_type.value if isinstance(self.artifact_source_type, ArtifactSourceType) else self.artifact_source_type,
            "has_replay_rows": self.has_replay_rows,
            "has_historical_predictions": self.has_historical_predictions,
            "no_data_reason": self.no_data_reason,
            "provenance_hash": self.provenance_hash,
            "created_by_phase": self.created_by_phase,
            "dry_run_only": self.dry_run_only,
        }


# ─── Safety Helpers ───────────────────────────────────────────────────────────

def is_visible_in_catalog(entry: CatalogEntry) -> bool:
    """
    Returns True if the entry should appear in the replay page catalog.
    UNSUPPORTED entries are excluded from the catalog.
    """
    return entry.catalog_visibility_state != CatalogVisibilityState.UNSUPPORTED


def is_no_data_entry(entry: CatalogEntry) -> bool:
    """
    Returns True if this entry has no replay rows (NO_DATA or ARTIFACT_CANDIDATE).
    These entries must NOT have replay rows fabricated for them.
    """
    return not entry.has_replay_rows


def can_generate_replay_rows(entry: CatalogEntry) -> bool:
    """
    P1 HARD CONSTRAINT: Always returns False.
    Replay row generation is NOT permitted in P1 (catalog visibility only).
    """
    return False  # P1 hard constraint: no replay row generation


def can_mark_online(entry: CatalogEntry) -> bool:
    """
    Returns True only if the entry's existing lifecycle state is already ONLINE.
    Artifact-only entries MUST NOT be promoted to ONLINE via P1 apply.
    """
    return entry.lifecycle_state == LifecycleState.ONLINE


def requires_controlled_apply(entry: CatalogEntry) -> bool:
    """
    Returns True if this entry requires the --apply flag for DB writes.
    Always True for non-UNSUPPORTED entries — all DB writes are controlled.
    """
    return entry.catalog_visibility_state != CatalogVisibilityState.UNSUPPORTED


# ─── Validation helpers ───────────────────────────────────────────────────────

VALID_LOTTERY_TYPES = frozenset({"BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "CROSS_GAME", "UNKNOWN"})
SAFE_ARTIFACT_ONLY_LIFECYCLES = frozenset({
    LifecycleState.ARTIFACT_ONLY,
    LifecycleState.REJECTED,
    LifecycleState.RETIRED,
    LifecycleState.OBSERVATION,
    LifecycleState.OFFLINE,
})


def is_safe_artifact_lifecycle(lifecycle_state: LifecycleState) -> bool:
    """
    Returns True if a lifecycle state is safe for a new artifact-only DB entry.
    ONLINE is NOT safe for artifact-only entries — they must not appear as active.
    """
    return lifecycle_state in SAFE_ARTIFACT_ONLY_LIFECYCLES


def validate_entry(entry: CatalogEntry) -> List[str]:
    """
    Validates a CatalogEntry against P1 safety rules.
    Returns a list of violation strings (empty if valid).
    """
    violations = []

    if not entry.strategy_id or not entry.strategy_id.strip():
        violations.append("strategy_id must be non-empty")

    if entry.lottery_type not in VALID_LOTTERY_TYPES:
        violations.append(f"lottery_type {entry.lottery_type!r} not in {VALID_LOTTERY_TYPES}")

    # Artifact candidates must not be ONLINE
    if (entry.catalog_visibility_state == CatalogVisibilityState.ARTIFACT_CANDIDATE
            and entry.lifecycle_state == LifecycleState.ONLINE):
        violations.append(
            f"ARTIFACT_CANDIDATE {entry.strategy_id!r} cannot have lifecycle_state=ONLINE"
        )

    # NO_DATA entries must have no_data_reason
    if is_no_data_entry(entry) and not entry.no_data_reason:
        violations.append(
            f"Entry {entry.strategy_id!r} has no replay rows but no_data_reason is empty"
        )

    return violations


# ─── Plan-level summary ───────────────────────────────────────────────────────

@dataclass
class CatalogExpansionPlan:
    """
    Summary of the P1 catalog expansion plan (dry-run output).

    This captures the planned changes before any DB writes occur.
    """
    generated_at: str
    runtime_canonical_before: int = 18
    artifact_candidate_count: int = 0
    planned_new_registry_entries: int = 0
    planned_existing_registry_updates: int = 0
    planned_no_data_entries: int = 0
    entries: List[CatalogEntry] = field(default_factory=list)
    skipped_entries: List[dict] = field(default_factory=list)
    by_lottery: dict = field(default_factory=dict)
    by_lifecycle: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "runtime_canonical_before": self.runtime_canonical_before,
            "artifact_candidate_count": self.artifact_candidate_count,
            "planned_new_registry_entries": self.planned_new_registry_entries,
            "planned_existing_registry_updates": self.planned_existing_registry_updates,
            "planned_no_data_entries": self.planned_no_data_entries,
            "by_lottery": self.by_lottery,
            "by_lifecycle": self.by_lifecycle,
            "entries": [e.to_dict() for e in self.entries],
            "skipped_entries": self.skipped_entries,
            "safety": {
                "db_write": False,
                "draw_import": False,
                "replay_row_generation": False,
                "prediction_update": False,
                "strategy_execution": False,
            },
        }
