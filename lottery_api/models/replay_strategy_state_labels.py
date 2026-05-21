"""
replay_strategy_state_labels.py
================================
P26: Non-ONLINE Strategy State Labels

Read-only label mapping for the full P24 strategy universe.

Provides safe, user-facing labels for all 59 known strategies so the
replay system can display them without pretending artifact-only /
rejected / retired strategies have replay rows.

SCOPE (strictly enforced):
  - Read-only: no DB writes, no migrations, no new tables.
  - No strategy execution.
  - No modification of production DB.
  - Evidence source: outputs/replay/p24_full_strategy_universe_inventory_20260521.json

LABEL PRECEDENCE (assign_label):
  1. ONLINE_ROW_BACKED + row_count > 0   → "row-backed"
  2. ONLINE_ROW_BACKED + row_count == 0  → "no-data"   (edge: registered row-backed but empty)
  3. needs_manual_review = True           → "manual-review"
  4. unsupported_reason is not None       → "unsupported"
  5. ARTIFACT_ONLY + reconstructible=True → "reconstructible"
  6. ARTIFACT_ONLY                        → "artifact-only"
  7. RETIRED                              → "retired"
  8. REJECTED_REGISTERED                  → "rejected-registered"
  9. OBSERVATION                          → "observation"
  10. (fallback)                          → "no-data"

All functions are pure / side-effect-free.
The optional P24-catalog helpers load from disk at call time (no module-level I/O).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Canonical Label Definitions ─────────────────────────────────────────────

LABEL_DEFINITIONS: dict[str, dict] = {
    "row-backed": {
        "display": "Row-Backed",
        "description": (
            "Strategy has production replay rows in DB. "
            "Queryable via /api/replay/history."
        ),
        "queryable": True,
    },
    "artifact-only": {
        "display": "Artifact Only",
        "description": (
            "Catalogued from artifact evidence only (rejected archive, "
            "source files). No replay rows in DB. Not queryable."
        ),
        "queryable": False,
    },
    "no-data": {
        "display": "No Data",
        "description": (
            "No replay rows and no recoverable artifact. "
            "Display as catalog entry only."
        ),
        "queryable": False,
    },
    "reconstructible": {
        "display": "Reconstructible",
        "description": (
            "Strategy logic is recoverable from archived source. "
            "Can be replayed after a formal reconstruction pass. "
            "Not currently queryable."
        ),
        "queryable": False,
    },
    "manual-review": {
        "display": "Manual Review",
        "description": (
            "Requires manual evaluation before display. "
            "Not automatically visible in the replay catalog."
        ),
        "queryable": False,
    },
    "unsupported": {
        "display": "Unsupported",
        "description": (
            "Strategy lacks sufficient source to reconstruct or replay. "
            "Reason recorded in unsupported_reason field."
        ),
        "queryable": False,
    },
    "retired": {
        "display": "Retired",
        "description": (
            "Formally retired from active use. "
            "Lifecycle state preserved for reference. "
            "No new rows will be generated."
        ),
        "queryable": False,
    },
    "rejected-registered": {
        "display": "Rejected (Registered)",
        "description": (
            "Evaluated and rejected during governance review. "
            "Metadata registered for lifecycle tracking only. "
            "MUST NOT be executed."
        ),
        "queryable": False,
    },
    "observation": {
        "display": "Observation",
        "description": (
            "Under shadow evaluation / observation period. "
            "Not in active production. Not queryable until promoted."
        ),
        "queryable": False,
    },
}

# All 9 canonical label keys
ALL_LABEL_KEYS: frozenset[str] = frozenset(LABEL_DEFINITIONS.keys())

# Replay visibility states that map to row-backed (production DB rows exist)
_ROW_BACKED_STATES: frozenset[str] = frozenset({"ONLINE_ROW_BACKED"})

# ─── P24 evidence file path ───────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_P24_INVENTORY_PATH = (
    _PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p24_full_strategy_universe_inventory_20260521.json"
)


# ─── Pure label assignment ────────────────────────────────────────────────────

def assign_label(
    replay_visibility_state: str,
    row_count: int = 0,
    reconstructible_candidate: bool = False,
    needs_manual_review: bool = False,
    unsupported_reason: Optional[str] = None,
) -> str:
    """
    Return the canonical label key for a strategy given its visibility state
    and flag attributes.

    This is a pure function — no I/O, no DB access.

    Parameters
    ----------
    replay_visibility_state : str
        One of: ONLINE_ROW_BACKED, ARTIFACT_ONLY, RETIRED,
                REJECTED_REGISTERED, OBSERVATION, or any unknown value.
    row_count : int
        Number of production replay rows. Only relevant for ONLINE_ROW_BACKED.
    reconstructible_candidate : bool
        True if the strategy logic can be reconstructed from archived source.
    needs_manual_review : bool
        True if the entry requires manual evaluation before display.
    unsupported_reason : str | None
        Non-None if the strategy cannot be supported/reconstructed.

    Returns
    -------
    str
        One of the 9 canonical label keys from LABEL_DEFINITIONS.
    """
    # 1. Row-backed: must have actual rows
    if replay_visibility_state in _ROW_BACKED_STATES:
        return "row-backed" if row_count > 0 else "no-data"

    # 2. Manual review takes priority over other non-ONLINE labels
    if needs_manual_review:
        return "manual-review"

    # 3. Unsupported (reason recorded)
    if unsupported_reason is not None:
        return "unsupported"

    # 4. Artifact-only: check if reconstructible
    if replay_visibility_state == "ARTIFACT_ONLY":
        return "reconstructible" if reconstructible_candidate else "artifact-only"

    # 5. State-specific labels
    _STATE_MAP: dict[str, str] = {
        "RETIRED":              "retired",
        "REJECTED_REGISTERED":  "rejected-registered",
        "OBSERVATION":          "observation",
    }
    if replay_visibility_state in _STATE_MAP:
        return _STATE_MAP[replay_visibility_state]

    # Fallback
    return "no-data"


def is_row_backed(
    replay_visibility_state: str,
    row_count: int = 0,
) -> bool:
    """
    Returns True only if the strategy has production replay rows in the DB.

    Safe to call for any strategy — non-ONLINE strategies always return False.
    """
    return (
        replay_visibility_state in _ROW_BACKED_STATES
        and row_count > 0
    )


def get_label_definition(label_key: str) -> Optional[dict]:
    """
    Returns the label definition dict for a given label key, or None if unknown.

    The returned dict is a shallow copy — callers cannot mutate the canonical
    definitions.
    """
    defn = LABEL_DEFINITIONS.get(label_key)
    return dict(defn) if defn is not None else None


# ─── P24 catalog helpers ──────────────────────────────────────────────────────

def _load_p24_inventory() -> list[dict]:
    """
    Load strategies list from the P24 evidence file.

    Returns empty list if the file is missing (test isolation).
    Never raises — callers should check the return value.
    """
    if not _P24_INVENTORY_PATH.exists():
        logger.warning("P24 inventory not found at %s", _P24_INVENTORY_PATH)
        return []
    with _P24_INVENTORY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("strategies", [])


def build_label_entry(strategy: dict) -> dict:
    """
    Given a P24 strategy dict, compute and return a label entry.

    The returned dict includes:
      strategy_id, display_name, lottery_type, lifecycle_state,
      replay_visibility_state, row_count, reconstructible_candidate,
      primary_label, label_display, label_description, is_row_backed,
      queryable, reason_text

    This function is pure given its input dict.
    """
    sid      = strategy.get("strategy_id", "")
    rvs      = strategy.get("replay_visibility_state", "")
    ltype    = strategy.get("lottery_type", "")
    lstate   = strategy.get("lifecycle_state", "")
    rc       = int(strategy.get("row_count") or 0)
    recon    = bool(strategy.get("reconstructible_candidate"))
    manual   = bool(strategy.get("needs_manual_review"))
    unsup    = strategy.get("unsupported_reason")
    display  = strategy.get("display_name", sid)

    primary = assign_label(
        replay_visibility_state=rvs,
        row_count=rc,
        reconstructible_candidate=recon,
        needs_manual_review=manual,
        unsupported_reason=unsup,
    )
    row_backed = is_row_backed(rvs, rc)
    defn = LABEL_DEFINITIONS.get(primary, LABEL_DEFINITIONS["no-data"])

    # Build reason text
    if row_backed:
        reason = f"Production rows in DB: {rc:,}"
    elif manual:
        reason = "Requires manual review before display."
    elif unsup:
        reason = f"Unsupported: {unsup}"
    elif recon and not row_backed:
        reason = "Logic recoverable from archived source."
    else:
        reason = defn["description"]

    return {
        "strategy_id":               sid,
        "display_name":              display,
        "lottery_type":              ltype,
        "lifecycle_state":           lstate,
        "replay_visibility_state":   rvs,
        "row_count":                 rc,
        "reconstructible_candidate": recon,
        "primary_label":             primary,
        "label_display":             defn["display"],
        "label_description":         defn["description"],
        "is_row_backed":             row_backed,
        "queryable":                 defn["queryable"],
        "reason_text":               reason,
    }


def get_full_label_catalog() -> list[dict]:
    """
    Return the full P26 label catalog for all 59 P24 strategies.

    Each entry has strategy metadata + label fields (see build_label_entry).
    Order is preserved from the P24 inventory file.

    Read-only: no DB access, no modifications.
    """
    strategies = _load_p24_inventory()
    return [build_label_entry(s) for s in strategies]


def get_label_for_strategy(strategy_id: str) -> Optional[dict]:
    """
    Return the label entry for a single strategy_id, or None if not in P24.

    Read-only: no DB access.
    """
    for s in _load_p24_inventory():
        if s.get("strategy_id") == strategy_id:
            return build_label_entry(s)
    return None


def get_label_summary() -> dict:
    """
    Return a summary dict: label_key → count of strategies with that label.

    Read-only.
    """
    catalog = get_full_label_catalog()
    summary: dict[str, int] = {k: 0 for k in LABEL_DEFINITIONS}
    for entry in catalog:
        lbl = entry["primary_label"]
        summary[lbl] = summary.get(lbl, 0) + 1
    return summary
