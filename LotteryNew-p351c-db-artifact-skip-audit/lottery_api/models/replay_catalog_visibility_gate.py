"""
lottery_api/models/replay_catalog_visibility_gate.py
======================================================
P3 Catalog Visibility Gate — defines which catalog_visibility_states are safe
to expose on public-facing replay pages vs admin/debug/catalog-audit pages.

HARD CONSTRAINTS:
  - This module is READ-ONLY; it never writes to DB or changes any state.
  - It only classifies / filters — no side effects.
  - ARTIFACT_CANDIDATE is always internal-only (never public).
  - RECONSTRUCTIBLE is always internal-only (rows not yet applied via P7).
  - REGISTERED_NO_DATA is internal-only (no useful data to show users).
  - UNSUPPORTED is internal-only (tombstone; confusing to users).

Visibility rules:
  Public (user-facing replay page):
    REGISTERED_WITH_REPLAY_ROWS → isPublicVisible = True
    All others                  → isPublicVisible = False

  Admin / Debug / Catalog Audit:
    All 5 states → visible (no restriction)

Badge metadata for UI rendering:
  Each state carries:
    is_public_visible    — safe to show on main replay page
    is_internal_only     — admin/catalog-audit only
    requires_admin_or_debug — alias for is_internal_only
    display_label        — human-readable label
    badge_class          — CSS class hint for UI theming
"""
from __future__ import annotations

from typing import Dict, List

from lottery_api.models.replay_strategy_catalog_contract import CatalogVisibilityState


# ---------------------------------------------------------------------------
# Public-visible states — safe on the main replay page
# ---------------------------------------------------------------------------

PUBLIC_VISIBLE_STATES: frozenset = frozenset({
    CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS,
})

# ---------------------------------------------------------------------------
# Internal-only states — admin/catalog-audit only
# ---------------------------------------------------------------------------

INTERNAL_ONLY_STATES: frozenset = frozenset({
    CatalogVisibilityState.ARTIFACT_CANDIDATE,
    CatalogVisibilityState.RECONSTRUCTIBLE,
    CatalogVisibilityState.REGISTERED_NO_DATA,
    CatalogVisibilityState.UNSUPPORTED,
})

# ---------------------------------------------------------------------------
# Full per-state metadata (used by badge renderer / API serializer)
# ---------------------------------------------------------------------------

STATE_VISIBILITY_META: Dict[str, Dict] = {
    CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS: {
        "is_public_visible":     True,
        "is_internal_only":      False,
        "requires_admin_or_debug": False,
        "display_label":         "Registered (has rows)",
        "badge_class":           "badge-live",
    },
    CatalogVisibilityState.RECONSTRUCTIBLE: {
        "is_public_visible":     False,
        "is_internal_only":      True,
        "requires_admin_or_debug": True,
        "display_label":         "Reconstructible",
        "badge_class":           "badge-internal",
    },
    CatalogVisibilityState.REGISTERED_NO_DATA: {
        "is_public_visible":     False,
        "is_internal_only":      True,
        "requires_admin_or_debug": True,
        "display_label":         "Registered (no data)",
        "badge_class":           "badge-internal",
    },
    CatalogVisibilityState.ARTIFACT_CANDIDATE: {
        "is_public_visible":     False,
        "is_internal_only":      True,
        "requires_admin_or_debug": True,
        "display_label":         "Artifact Candidate",
        "badge_class":           "badge-internal",
    },
    CatalogVisibilityState.UNSUPPORTED: {
        "is_public_visible":     False,
        "is_internal_only":      True,
        "requires_admin_or_debug": True,
        "display_label":         "Unsupported",
        "badge_class":           "badge-internal",
    },
}


# ---------------------------------------------------------------------------
# Gate functions
# ---------------------------------------------------------------------------

def is_public_visible(catalog_visibility_state: str) -> bool:
    """Return True if this state may appear on a public/user-facing replay page."""
    return catalog_visibility_state in PUBLIC_VISIBLE_STATES


def is_internal_only(catalog_visibility_state: str) -> bool:
    """Return True if this state must be restricted to admin/debug/audit views."""
    return catalog_visibility_state in INTERNAL_ONLY_STATES


def requires_admin_or_debug(catalog_visibility_state: str) -> bool:
    """Alias for is_internal_only — for clarity in route/template code."""
    return is_internal_only(catalog_visibility_state)


def get_visibility_meta(catalog_visibility_state: str) -> Dict:
    """Return the full visibility metadata dict for a given state.

    Returns a safe fallback (all-internal, unknown label) for unrecognised states.
    """
    return STATE_VISIBILITY_META.get(
        catalog_visibility_state,
        {
            "is_public_visible":     False,
            "is_internal_only":      True,
            "requires_admin_or_debug": True,
            "display_label":         catalog_visibility_state,
            "badge_class":           "badge-unknown",
        },
    )


def filter_for_public(
    entries: List[dict],
    *,
    visibility_key: str = "catalog_visibility_state",
) -> List[dict]:
    """
    Filter a list of CatalogEntry dicts to only public-visible entries.

    Works on any dict that carries `visibility_key`.
    """
    return [e for e in entries if is_public_visible(e.get(visibility_key, ""))]


def annotate_with_visibility(
    entries: List[dict],
    *,
    visibility_key: str = "catalog_visibility_state",
) -> List[dict]:
    """
    Annotate each dict with visibility metadata fields in-place.

    Adds `is_public_visible`, `is_internal_only`, `requires_admin_or_debug`
    and `visibility_badge_class` to each entry dict (shallow copy).
    Does NOT mutate the originals.
    """
    result = []
    for entry in entries:
        meta = get_visibility_meta(entry.get(visibility_key, ""))
        annotated = dict(entry)
        annotated["is_public_visible"]      = meta["is_public_visible"]
        annotated["is_internal_only"]       = meta["is_internal_only"]
        annotated["requires_admin_or_debug"] = meta["requires_admin_or_debug"]
        annotated["visibility_badge_class"]  = meta["badge_class"]
        result.append(annotated)
    return result
