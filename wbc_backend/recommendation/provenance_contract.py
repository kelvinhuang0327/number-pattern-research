"""Versioned recommendation provenance contract.

P205A centralizes the source-truth fields used by paper recommendation and
daily advisory paths.  The contract is intentionally conservative: invalid,
missing, or legacy provenance is never upgraded into learning eligibility.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


PROVENANCE_CONTRACT_VERSION = "p205a.v1"

CONTRACT_FIELDS: tuple[str, ...] = (
    "provenance_contract_version",
    "prediction_input_mode",
    "prediction_source",
    "prediction_source_id",
    "model_version",
    "feature_fingerprint",
    "prediction_as_of_utc",
    "game_specific",
    "selected_side_method",
    "odds_source",
    "odds_is_market_observed",
    "edge_is_real_evidence",
    "learning_eligible",
    "learning_block_reason",
)

BOOLEAN_FIELDS: tuple[str, ...] = (
    "game_specific",
    "odds_is_market_observed",
    "edge_is_real_evidence",
    "learning_eligible",
)

NON_REAL_EVIDENCE_ODDS_SOURCES = frozenset({"estimated", "historical_no_vig"})


class ProvenanceContractError(ValueError):
    """Raised when a provenance source_trace violates the P205A contract."""


def _isoformat_utc(value: datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def validate_provenance_contract(source_trace: dict[str, Any]) -> None:
    """Validate a P205A provenance contract and fail closed on ambiguity."""
    if not isinstance(source_trace, dict):
        raise ProvenanceContractError("source_trace must be a dict")

    missing = [field for field in CONTRACT_FIELDS if field not in source_trace]
    if missing:
        raise ProvenanceContractError(
            "missing provenance contract field(s): " + ", ".join(missing)
        )

    if source_trace["provenance_contract_version"] != PROVENANCE_CONTRACT_VERSION:
        raise ProvenanceContractError(
            "unsupported provenance_contract_version="
            f"{source_trace['provenance_contract_version']!r}"
        )

    for field in BOOLEAN_FIELDS:
        if type(source_trace[field]) is not bool:
            raise ProvenanceContractError(f"{field} must be a literal boolean")

    if source_trace["learning_eligible"] is True:
        if source_trace["game_specific"] is not True:
            raise ProvenanceContractError(
                "learning_eligible=True requires game_specific=True"
            )
        if not source_trace["prediction_as_of_utc"]:
            raise ProvenanceContractError(
                "learning_eligible=True requires prediction_as_of_utc"
            )
        if source_trace["odds_is_market_observed"] is not True:
            raise ProvenanceContractError(
                "learning_eligible=True requires odds_is_market_observed=True"
            )
        if source_trace["edge_is_real_evidence"] is not True:
            raise ProvenanceContractError(
                "learning_eligible=True requires edge_is_real_evidence=True"
            )
        if source_trace["learning_block_reason"] != "":
            raise ProvenanceContractError(
                "learning_eligible=True requires empty learning_block_reason"
            )
    else:
        reason = source_trace["learning_block_reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ProvenanceContractError(
                "learning_eligible=False requires non-empty learning_block_reason"
            )

    odds_source = source_trace["odds_source"]
    if (
        source_trace["learning_eligible"] is True
        and odds_source in NON_REAL_EVIDENCE_ODDS_SOURCES
    ):
        raise ProvenanceContractError(
            f"odds_source={odds_source!r} cannot set learning_eligible=True"
        )
    if (
        odds_source in NON_REAL_EVIDENCE_ODDS_SOURCES
        and source_trace["edge_is_real_evidence"] is True
    ):
        raise ProvenanceContractError(
            f"odds_source={odds_source!r} cannot set edge_is_real_evidence=True"
        )


def serialize_provenance_contract(source_trace: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-ready contract dict after validation."""
    validate_provenance_contract(source_trace)
    return {field: source_trace[field] for field in CONTRACT_FIELDS}


def build_provenance_contract(
    *,
    prediction_input_mode: str,
    prediction_source: str,
    prediction_source_id: str | None,
    model_version: str,
    feature_fingerprint: str,
    prediction_as_of_utc: datetime | str | None,
    game_specific: bool,
    selected_side_method: str,
    odds_source: str,
    odds_is_market_observed: bool,
    edge_is_real_evidence: bool,
    learning_eligible: bool,
    learning_block_reason: str | None,
) -> dict[str, Any]:
    """Build and validate the versioned provenance contract."""
    contract = {
        "provenance_contract_version": PROVENANCE_CONTRACT_VERSION,
        "prediction_input_mode": prediction_input_mode,
        "prediction_source": prediction_source,
        "prediction_source_id": prediction_source_id or "",
        "model_version": model_version,
        "feature_fingerprint": feature_fingerprint,
        "prediction_as_of_utc": _isoformat_utc(prediction_as_of_utc),
        "game_specific": game_specific,
        "selected_side_method": selected_side_method,
        "odds_source": odds_source,
        "odds_is_market_observed": odds_is_market_observed,
        "edge_is_real_evidence": edge_is_real_evidence,
        "learning_eligible": learning_eligible,
        "learning_block_reason": learning_block_reason or "",
    }
    return serialize_provenance_contract(contract)


def legacy_or_missing_contract_is_learning_eligible(source_trace: Any) -> bool:
    """Return True only for a valid versioned contract with explicit eligibility."""
    if not isinstance(source_trace, dict):
        return False
    if source_trace.get("provenance_contract_version") != PROVENANCE_CONTRACT_VERSION:
        return False
    try:
        validate_provenance_contract(source_trace)
    except ProvenanceContractError:
        return False
    return source_trace["learning_eligible"] is True


def validate_source_trace_fail_closed(source_trace: Any) -> None:
    """Validate versioned traces and reject legacy traces that claim eligibility."""
    if not isinstance(source_trace, dict):
        return
    if source_trace.get("provenance_contract_version") == PROVENANCE_CONTRACT_VERSION:
        validate_provenance_contract(source_trace)
    elif source_trace.get("learning_eligible") is True:
        raise ProvenanceContractError(
            "legacy or missing provenance contract cannot set learning_eligible=True"
        )


def resolve_explicit_strategy_id(simulation: Any) -> str | None:
    """Use only the simulation's explicit strategy_name for attribution."""
    strategy_name = getattr(simulation, "strategy_name", None)
    if isinstance(strategy_name, str) and strategy_name.strip():
        return strategy_name
    return None
