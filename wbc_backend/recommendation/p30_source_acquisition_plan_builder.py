"""
wbc_backend/recommendation/p30_source_acquisition_plan_builder.py

P30 Source Acquisition Plan Builder.

Builds a full source acquisition plan for a target season, ranking
options by verifiability and schema completeness, and determining
the P30 gate status.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from wbc_backend.recommendation.p30_source_acquisition_contract import (
    P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
    P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
    P30_BLOCKED_NO_VERIFIABLE_SOURCE,
    P30_SOURCE_ACQUISITION_PLAN_READY,
    P30ArtifactBuilderPlan,
    P30RequiredArtifactSpec,
    P30SourceAcquisitionGateResult,
    P30SourceAcquisitionPlan,
    SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    SOURCE_PLAN_BLOCKED_PROVENANCE,
    SOURCE_PLAN_BLOCKED_SCHEMA_GAP,
    SOURCE_PLAN_PARTIAL,
    SOURCE_PLAN_READY,
    TARGET_ACTIVE_ENTRIES_DEFAULT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Empirical active-entry conversion rate from P29: 324 active / 1577 total = 0.205
ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT: float = 0.205

_VERIFIABLE_PROVENANCE_STATUSES = frozenset(
    {"KNOWN_HISTORICAL", "INTERNAL_PIPELINE_OUTPUT", "DERIVED_INTERNAL"}
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_verifiable(candidate: Dict[str, Any]) -> bool:
    """Return True if the source has a known, safe provenance."""
    return candidate.get("provenance_status", "UNKNOWN") in _VERIFIABLE_PROVENANCE_STATUSES


def _schema_score(candidate: Dict[str, Any]) -> int:
    """Return numeric schema completeness score (higher is better)."""
    cov = candidate.get("schema_coverage", "MINIMAL")
    return {"FULL": 3, "PARTIAL": 2, "MINIMAL": 1}.get(cov, 0)


def _expected_gain_score(candidate: Dict[str, Any], rate: float) -> int:
    rows = max(0, candidate.get("estimated_rows", 0))
    return int(rows * rate)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_provenance_and_license(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate provenance and license risk for a candidate.
    Returns {safe: bool, risk_level: str, notes: str}.
    """
    provenance = candidate.get("provenance_status", "UNKNOWN")
    license_risk = candidate.get("license_risk", "UNKNOWN")

    if provenance == "UNKNOWN":
        return {
            "safe": False,
            "risk_level": "HIGH",
            "notes": "Provenance UNKNOWN: cannot verify data origin or license terms.",
        }
    if license_risk == "HIGH":
        return {
            "safe": False,
            "risk_level": "HIGH",
            "notes": f"License risk HIGH for source: {candidate.get('path', '?')}",
        }
    if provenance in _VERIFIABLE_PROVENANCE_STATUSES and license_risk in ("LOW", "MEDIUM"):
        return {
            "safe": True,
            "risk_level": license_risk,
            "notes": f"Provenance {provenance}, license risk {license_risk}: acceptable for paper-only use.",
        }
    return {
        "safe": False,
        "risk_level": license_risk,
        "notes": f"Provenance '{provenance}' with license risk '{license_risk}': not verified safe.",
    }


def rank_source_acquisition_options(
    options: List[Dict[str, Any]],
    conversion_rate: float = ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT,
) -> List[Dict[str, Any]]:
    """
    Rank source acquisition options: verifiable first, then by schema completeness,
    then by expected gain.
    """
    def sort_key(c: Dict[str, Any]) -> tuple:
        verifiable = 1 if _is_verifiable(c) else 0
        schema = _schema_score(c)
        gain = _expected_gain_score(c, conversion_rate)
        return (verifiable, schema, gain)

    return sorted(options, key=sort_key, reverse=True)


def estimate_active_entry_gain(
    candidate: Dict[str, Any],
    conversion_rate: float = ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT,
) -> int:
    """
    Estimate additional active entries if this source were incorporated.
    Uses the P29-derived conversion rate (20.5%).
    """
    rows = max(0, candidate.get("estimated_rows", 0))
    return int(rows * conversion_rate)


def determine_p30_gate(
    inventory: List[Dict[str, Any]],
    artifact_specs: List[P30RequiredArtifactSpec],
    schema_gaps: Dict[str, Any],
) -> str:
    """
    Determine the P30 gate based on inventory and artifact spec coverage.

    Priority:
    1. At least one verifiable source with partial+ schema coverage → READY
    2. Source available but license/provenance unsafe → BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE
    3. No viable source → BLOCKED_NO_VERIFIABLE_SOURCE
    4. Required specs are missing → BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC
    """
    # Check if required specs exist at all
    if not artifact_specs:
        return P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC

    # Check if any verifiable partial+ sources exist
    verifiable = [c for c in inventory if _is_verifiable(c)]
    verifiable_with_data = [
        c for c in verifiable
        if c.get("source_status") in (SOURCE_PLAN_READY, SOURCE_PLAN_PARTIAL)
    ]

    if verifiable_with_data:
        # Even if there are schema gaps, we have a plan path → READY
        return P30_SOURCE_ACQUISITION_PLAN_READY

    # No verifiable sources with data — check if there are provenance-blocked sources
    prov_blocked = [
        c for c in inventory
        if c.get("source_status") == SOURCE_PLAN_BLOCKED_PROVENANCE
        or c.get("provenance_status") == "UNKNOWN"
    ]
    if prov_blocked:
        return P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE

    # No sources at all
    return P30_BLOCKED_NO_VERIFIABLE_SOURCE


def build_source_acquisition_plan(
    inventory: List[Dict[str, Any]],
    artifact_specs: List[P30RequiredArtifactSpec],
    schema_gaps: Dict[str, Any],
    target_season: str,
    conversion_rate: float = ACTIVE_ENTRY_CONVERSION_RATE_DEFAULT,
) -> P30SourceAcquisitionPlan:
    """
    Build the full source acquisition plan for a target season.
    """
    ranked = rank_source_acquisition_options(inventory, conversion_rate)

    n_total = len(ranked)
    n_ready = sum(1 for c in ranked if c.get("source_status") == SOURCE_PLAN_READY)
    n_partial = sum(1 for c in ranked if c.get("source_status") == SOURCE_PLAN_PARTIAL)

    total_estimated_rows = sum(
        c.get("estimated_rows", 0)
        for c in ranked
        if c.get("source_status") in (SOURCE_PLAN_READY, SOURCE_PLAN_PARTIAL)
    )
    expected_gain = int(total_estimated_rows * conversion_rate)

    # Determine gate
    p30_gate = determine_p30_gate(inventory, artifact_specs, schema_gaps)

    # Determine audit_status using source statuses
    verifiable = [c for c in ranked if _is_verifiable(c)]
    has_usable = any(
        c.get("source_status") in (SOURCE_PLAN_READY, SOURCE_PLAN_PARTIAL)
        for c in verifiable
    )
    audit_status = SOURCE_PLAN_PARTIAL if has_usable else SOURCE_PLAN_BLOCKED_NOT_AVAILABLE

    # Identify missing artifacts
    missing_artifact_types = [
        s.artifact_type for s in artifact_specs if s.coverage_status == "MISSING"
    ]

    # Build recommendations
    if p30_gate == P30_SOURCE_ACQUISITION_PLAN_READY:
        recommended_action = (
            "READY: Proceed to P31 to build joined input artifacts. "
            "Fill schema gaps by joining game identity + outcomes + model predictions + market odds."
        )
    elif p30_gate == P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE:
        recommended_action = (
            "BLOCKED: Resolve provenance/license uncertainty before using identified sources."
        )
    elif p30_gate == P30_BLOCKED_NO_VERIFIABLE_SOURCE:
        recommended_action = (
            "BLOCKED: No verifiable historical source found for target season. "
            f"Acquire MLB {target_season} full-season game outcomes + market odds data "
            "from a verified provider (e.g., Retrosheet, Baseball-Reference, or the-odds-api archive)."
        )
    else:
        recommended_action = "BLOCKED: Check missing artifact specs and source inventory."

    # Provenance and license summaries
    provenance_statuses = sorted({c.get("provenance_status", "UNKNOWN") for c in ranked})
    license_risks = sorted({c.get("license_risk", "UNKNOWN") for c in ranked})

    # Best source path
    best_path = ""
    if ranked:
        best_path = ranked[0].get("path", "")

    # Date range from best candidate
    date_start = ranked[0].get("date_start", "") if ranked else ""
    date_end = ranked[0].get("date_end", "") if ranked else ""
    expected_games = ranked[0].get("estimated_games", 0) if ranked else 0

    # Build steps (description only — dry run)
    build_steps = (
        "Step 1: Identify game identity file (game_id, game_date, home_team, away_team)\n"
        "Step 2: Identify game outcomes file (game_id, y_true)\n"
        "Step 3: Identify model predictions file (game_id, game_date, p_model or p_oof)\n"
        "Step 4: Identify market odds file (game_id, p_market, odds_decimal)\n"
        "Step 5: Join all four on game_id + game_date\n"
        "Step 6: Validate joined input schema\n"
        "Step 7: Run P22→P25 pipeline on joined input\n"
        "Step 8: Validate P25 output has edge + gate_reason columns"
    )
    validation_steps = (
        "Validate 1: No look-ahead leakage (predictions use only pre-game data)\n"
        "Validate 2: y_true values are 0/1 (not NaN)\n"
        "Validate 3: odds_decimal > 1.0 for all rows\n"
        "Validate 4: p_model in (0, 1) for all rows\n"
        "Validate 5: schema matches TRUE_DATE_JOINED_INPUT spec\n"
        "Validate 6: No duplicate game_id + game_date combinations"
    )

    feasibility_note = (
        f"{n_partial} partial + {n_ready} ready source(s) found. "
        f"Expected active entry gain: {expected_gain} (at {conversion_rate:.1%} conversion rate). "
        f"Schema gaps: {schema_gaps.get('schema_gap_count', 0)}. "
        f"Missing artifact types: {', '.join(missing_artifact_types) or 'none'}."
    )

    return P30SourceAcquisitionPlan(
        target_season=target_season,
        date_start=date_start,
        date_end=date_end,
        expected_games=expected_games,
        expected_min_active_entries=expected_gain,
        source_path_or_url=best_path,
        provenance_status=", ".join(provenance_statuses) or "UNKNOWN",
        license_risk=", ".join(license_risks) or "UNKNOWN",
        schema_coverage=ranked[0].get("schema_coverage", "MINIMAL") if ranked else "MINIMAL",
        n_source_candidates=n_total,
        n_partial_sources=n_partial,
        n_ready_sources=n_ready,
        schema_gap_count=schema_gaps.get("schema_gap_count", 0),
        missing_artifact_types=", ".join(missing_artifact_types),
        required_build_steps=build_steps,
        required_validation_steps=validation_steps,
        estimated_sample_gain=expected_gain,
        recommended_next_action=recommended_action,
        acquisition_feasibility_note=feasibility_note,
        p30_gate=p30_gate,
        audit_status=audit_status,
        paper_only=True,
        production_ready=False,
    )


def build_gate_result(plan: P30SourceAcquisitionPlan) -> P30SourceAcquisitionGateResult:
    """Build the final gate result from the acquisition plan."""
    return P30SourceAcquisitionGateResult(
        p30_gate=plan.p30_gate,
        target_season=plan.target_season,
        n_source_candidates=plan.n_source_candidates,
        n_partial_sources=plan.n_partial_sources,
        n_ready_sources=plan.n_ready_sources,
        schema_gap_count=plan.schema_gap_count,
        expected_sample_gain=plan.estimated_sample_gain,
        recommended_next_action=plan.recommended_next_action,
        audit_status=plan.audit_status,
        blocker_reason=(
            plan.p30_gate
            if plan.p30_gate != P30_SOURCE_ACQUISITION_PLAN_READY
            else ""
        ),
        paper_only=True,
        production_ready=False,
    )
