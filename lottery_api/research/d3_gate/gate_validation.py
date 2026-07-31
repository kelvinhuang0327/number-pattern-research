"""D3 gate read-only contract validators (P258F).

CONTRACT VALIDATION ONLY. These functions check schema completeness, timestamp
ordering, alignment metadata, and approval-status safety. They do not evaluate a
candidate, generate nulls, run paired tests, compute p-values, backtest, touch
the DB, or integrate with recommendation/registry/production/deployment paths.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Tuple

from .schemas import (
    CandidateInput,
    GateStatus,
    GateOutput,
    MatchedNullFamily,
    P257ABaselineInput,
)

FORBIDDEN_GATE_STATUS_VALUES = frozenset(
    {"APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED"}
)


class ContractValidationError(ValueError):
    """Raised when a read-only D3 contract object violates P258F constraints."""


@dataclass(frozen=True)
class ValidationResult:
    """Small immutable result for successful read-only contract validation."""

    validator: str
    checked_fields: Tuple[str, ...]


def _value(obj: Any, field_name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name)
    return getattr(obj, field_name, None)


def _dataclass_field_names(obj: Any) -> set:
    if not is_dataclass(obj):
        return set()
    return {field.name for field in fields(obj)}


def _require_fields(obj: Any, field_names: Iterable[str], validator: str) -> None:
    available = set(obj) if isinstance(obj, dict) else _dataclass_field_names(obj)
    for field_name in field_names:
        if available and field_name not in available:
            raise ContractValidationError(f"{validator}: missing field {field_name}")
        value = _value(obj, field_name)
        if value is None:
            raise ContractValidationError(f"{validator}: missing field {field_name}")
        if isinstance(value, str) and not value.strip():
            raise ContractValidationError(f"{validator}: empty field {field_name}")


def _require_positive_int(obj: Any, field_name: str, validator: str) -> None:
    value = _value(obj, field_name)
    if not isinstance(value, int) or value <= 0:
        raise ContractValidationError(f"{validator}: {field_name} must be positive")


def _parse_temporal(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ContractValidationError(
                f"timestamp_cutoff: invalid temporal field {field_name}"
            ) from exc
        if isinstance(parsed, datetime):
            return parsed.replace(tzinfo=None)
    raise ContractValidationError(f"timestamp_cutoff: invalid temporal field {field_name}")


def _status_token(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value).upper()
    return str(value).upper()


def _assert_gate_status_enum_safe() -> None:
    allowed = {"REJECTED", "NOT_YET_REJECTED"}
    actual = {member.value for member in GateStatus}
    if actual != allowed:
        raise ContractValidationError("gate_status: GateStatus enum values changed")
    forbidden_present = FORBIDDEN_GATE_STATUS_VALUES.intersection(actual)
    if forbidden_present:
        joined = ", ".join(sorted(forbidden_present))
        raise ContractValidationError(f"gate_status: forbidden values present: {joined}")


def _success(validator: str, field_names: Iterable[str]) -> ValidationResult:
    return ValidationResult(validator=validator, checked_fields=tuple(field_names))


CANDIDATE_REQUIRED_FIELDS = (
    "candidate_id",
    "lottery_type",
    "target_draw_id",
    "target_draw_date",
    "n_bet_count",
    "numbers_per_bet",
    "feature_dimensionality",
    "regime_count_or_parameter_count",
    "window_schedule",
    "generated_at",
    "available_information_cutoff",
    "random_seed",
    "source_artifact_path",
    "provenance_digest",
)

BASELINE_REQUIRED_FIELDS = (
    "baseline_id",
    "lottery_type",
    "target_draw_id",
    "n_bet_count",
    "source_artifact_path",
    "baseline_digest",
)

MATCHED_NULL_REQUIRED_FIELDS = (
    "null_family_id",
    "matched_lottery_type",
    "matched_n_bet_count",
    "matched_numbers_per_bet",
    "matched_window_schedule",
    "matched_feature_dimensionality",
    "matched_regime_or_parameter_count",
    "null_generation_seed",
    "null_count",
    "source_artifact_path",
)

CORRECTION_FAMILY_REQUIRED_FIELDS = (
    "candidate_methods",
    "null_variants",
    "lottery_types",
    "n_bet_counts",
    "metrics",
    "windows",
)


def validate_candidate_provenance_contract(candidate: CandidateInput) -> ValidationResult:
    """Validate required candidate/provenance metadata only."""

    validator = "candidate_provenance"
    _require_fields(candidate, CANDIDATE_REQUIRED_FIELDS, validator)
    for field_name in (
        "n_bet_count",
        "numbers_per_bet",
        "feature_dimensionality",
        "regime_count_or_parameter_count",
    ):
        _require_positive_int(candidate, field_name, validator)
    if not isinstance(_value(candidate, "random_seed"), int):
        raise ContractValidationError(f"{validator}: random_seed must be an integer")
    return _success(validator, CANDIDATE_REQUIRED_FIELDS)


def validate_timestamp_cutoff_contract(candidate: CandidateInput) -> ValidationResult:
    """Validate cutoff ordering; this performs no feature or result evaluation."""

    validator = "timestamp_cutoff"
    _require_fields(
        candidate,
        ("target_draw_date", "generated_at", "available_information_cutoff"),
        validator,
    )
    cutoff = _parse_temporal(
        _value(candidate, "available_information_cutoff"),
        "available_information_cutoff",
    )
    generated_at = _parse_temporal(_value(candidate, "generated_at"), "generated_at")
    target_draw_date = _parse_temporal(
        _value(candidate, "target_draw_date"), "target_draw_date"
    )
    if cutoff > generated_at:
        raise ContractValidationError(
            "timestamp_cutoff: available_information_cutoff is after generated_at"
        )
    if cutoff >= target_draw_date:
        raise ContractValidationError(
            "timestamp_cutoff: available_information_cutoff must precede target_draw_date"
        )
    return _success(
        validator,
        ("target_draw_date", "generated_at", "available_information_cutoff"),
    )


def validate_p257a_baseline_contract(
    candidate: CandidateInput, baseline: P257ABaselineInput
) -> ValidationResult:
    """Validate baseline alignment metadata by lottery, draw, and N-bet count."""

    validator = "p257a_baseline"
    validate_candidate_provenance_contract(candidate)
    _require_fields(baseline, BASELINE_REQUIRED_FIELDS, validator)
    _require_positive_int(baseline, "n_bet_count", validator)
    for field_name in ("lottery_type", "target_draw_id", "n_bet_count"):
        if _value(candidate, field_name) != _value(baseline, field_name):
            raise ContractValidationError(
                f"{validator}: baseline {field_name} does not match candidate"
            )
    return _success(validator, BASELINE_REQUIRED_FIELDS)


def validate_matched_null_family_contract(
    candidate: CandidateInput, null_family: MatchedNullFamily
) -> ValidationResult:
    """Validate matched-null metadata only; no null generation is performed."""

    validator = "matched_null_family"
    validate_candidate_provenance_contract(candidate)
    _require_fields(null_family, MATCHED_NULL_REQUIRED_FIELDS, validator)
    for field_name in (
        "matched_n_bet_count",
        "matched_numbers_per_bet",
        "matched_feature_dimensionality",
        "matched_regime_or_parameter_count",
        "null_count",
    ):
        _require_positive_int(null_family, field_name, validator)
    expected_pairs = (
        ("lottery_type", "matched_lottery_type"),
        ("n_bet_count", "matched_n_bet_count"),
        ("numbers_per_bet", "matched_numbers_per_bet"),
        ("window_schedule", "matched_window_schedule"),
        ("feature_dimensionality", "matched_feature_dimensionality"),
        ("regime_count_or_parameter_count", "matched_regime_or_parameter_count"),
    )
    for candidate_field, null_field in expected_pairs:
        if _value(candidate, candidate_field) != _value(null_family, null_field):
            raise ContractValidationError(
                f"{validator}: {null_field} does not match candidate {candidate_field}"
            )
    if not isinstance(_value(null_family, "null_generation_seed"), int):
        raise ContractValidationError(f"{validator}: null_generation_seed must be an integer")
    return _success(validator, MATCHED_NULL_REQUIRED_FIELDS)


def validate_correction_family_contract(correction_family: object) -> ValidationResult:
    """Validate multiple-testing family declarations without computing tests."""

    validator = "correction_family"
    _require_fields(correction_family, CORRECTION_FAMILY_REQUIRED_FIELDS, validator)
    for field_name in CORRECTION_FAMILY_REQUIRED_FIELDS:
        value = _value(correction_family, field_name)
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ContractValidationError(f"{validator}: {field_name} must be a collection")
        if not tuple(value):
            raise ContractValidationError(f"{validator}: {field_name} must be non-empty")
    return _success(validator, CORRECTION_FAMILY_REQUIRED_FIELDS)


def validate_no_approval_status_contract(output: GateOutput) -> ValidationResult:
    """Validate that gate output cannot encode approval or promotion semantics."""

    validator = "no_approval_status"
    _assert_gate_status_enum_safe()
    _require_fields(output, ("gate_decision",), validator)
    gate_decision = _value(output, "gate_decision")
    token = _status_token(gate_decision)
    if token in FORBIDDEN_GATE_STATUS_VALUES:
        raise ContractValidationError(f"{validator}: forbidden gate status {token}")
    if token not in {member.value for member in GateStatus}:
        raise ContractValidationError(f"{validator}: unknown gate status {token}")
    return _success(validator, ("gate_decision",))
