"""Fail-closed consumer gate for prospective result availability.

The gate is the read-only seam between the P274 index and a replay/feature
consumer.  It permits result usage only when the recorded local-observation
lower bound is at or before ``feature_as_of_utc``.  It never derives an
availability time from game status, feed metadata, file metadata, or wall time.
"""
from __future__ import annotations

import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from scripts import _p274_prospective_result_availability_index as p274


MISSING_AVAILABILITY_EVIDENCE = "missing_availability_evidence"
INVALID_AVAILABILITY_EVIDENCE = "invalid_availability_evidence"
INVALID_FEATURE_AS_OF_UTC = "invalid_feature_as_of_utc"
RESULT_NOT_YET_AVAILABLE = "result_not_yet_available"


class P275Error(RuntimeError):
    """Base error for P275 evidence loading failures."""


class MissingAvailabilityEvidenceError(P275Error):
    """Required P274 publication evidence is absent."""


class InvalidAvailabilityEvidenceError(P275Error):
    """P274 publication evidence is malformed or fails integrity checks."""


@dataclass(frozen=True)
class AvailabilityGateDecision:
    """A fail-closed decision made before a consumer can use result fields."""

    result_usage_allowed: bool
    block_reason: str | None
    game_id: str
    feature_as_of_utc: str | None
    result_available_at_utc: str | None
    availability_semantics: str = p274.AVAILABILITY_SEMANTICS
    retroactive_certification: bool = p274.RETROACTIVE_CERTIFICATION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_regular_file(path: Path, label: str) -> bytes:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise MissingAvailabilityEvidenceError(f"Missing {label}") from exc
    except OSError as exc:
        raise InvalidAvailabilityEvidenceError(f"Unable to inspect {label}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise InvalidAvailabilityEvidenceError(f"{label} must be a regular non-symlink file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise InvalidAvailabilityEvidenceError(f"Unable to read {label}") from exc


def load_verified_availability_index(
    index_path: str | Path,
    manifest_path: str | Path,
) -> Mapping[str, Any]:
    """Load a P274 index only when its explicitly supplied manifest verifies."""
    path = Path(index_path)
    manifest = Path(manifest_path)
    if path.name != p274.INDEX_FILENAME:
        raise InvalidAvailabilityEvidenceError(
            f"P274 index path must end with {p274.INDEX_FILENAME}"
        )
    if manifest.name != p274.CHECKSUM_FILENAME:
        raise InvalidAvailabilityEvidenceError(
            f"P274 manifest path must end with {p274.CHECKSUM_FILENAME}"
        )

    index_bytes = _read_regular_file(path, p274.INDEX_FILENAME)
    checksum_bytes = _read_regular_file(manifest, p274.CHECKSUM_FILENAME)
    expected_checksum = (
        f"{p274.sha256_bytes(index_bytes)}  {p274.INDEX_FILENAME}\n".encode("utf-8")
    )
    if checksum_bytes != expected_checksum:
        raise InvalidAvailabilityEvidenceError("P274 index checksum verification failed")

    try:
        index = p274.parse_json_bytes(
            index_bytes,
            p274.INDEX_FILENAME,
            require_canonical=True,
        )
        p274.validate_index(index)
    except p274.P274Error as exc:
        raise InvalidAvailabilityEvidenceError("P274 index validation failed") from exc
    return index


def evaluate_result_availability(
    *,
    game_id: str,
    feature_as_of_utc: str | None,
    index_path: str | Path,
    manifest_path: str | Path,
) -> AvailabilityGateDecision:
    """Decide whether indexed result evidence may be used by a feature consumer.

    Missing, malformed, unknown, or integrity-failing evidence is rejected.  A
    valid record is accepted exactly when P274's recorded
    ``result_available_at_utc <= feature_as_of_utc`` comparison succeeds.
    """
    try:
        canonical_feature_as_of, _ = p274.parse_canonical_utc(
            feature_as_of_utc,
            "feature_as_of_utc",
        )
    except p274.P274Error:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=INVALID_FEATURE_AS_OF_UTC,
            game_id=game_id if isinstance(game_id, str) else "",
            feature_as_of_utc=None,
            result_available_at_utc=None,
        )

    try:
        index = load_verified_availability_index(index_path, manifest_path)
    except MissingAvailabilityEvidenceError:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=MISSING_AVAILABILITY_EVIDENCE,
            game_id=game_id if isinstance(game_id, str) else "",
            feature_as_of_utc=canonical_feature_as_of,
            result_available_at_utc=None,
        )
    except InvalidAvailabilityEvidenceError:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=INVALID_AVAILABILITY_EVIDENCE,
            game_id=game_id if isinstance(game_id, str) else "",
            feature_as_of_utc=canonical_feature_as_of,
            result_available_at_utc=None,
        )

    try:
        query, found = p274.query_index(index, game_id, canonical_feature_as_of)
    except p274.P274Error:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=INVALID_AVAILABILITY_EVIDENCE,
            game_id=game_id if isinstance(game_id, str) else "",
            feature_as_of_utc=canonical_feature_as_of,
            result_available_at_utc=None,
        )

    if not found:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=MISSING_AVAILABILITY_EVIDENCE,
            game_id=game_id,
            feature_as_of_utc=canonical_feature_as_of,
            result_available_at_utc=None,
        )

    result_available_at_utc = query["available_from_utc"]
    if query["available"] is not True:
        return AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=RESULT_NOT_YET_AVAILABLE,
            game_id=game_id,
            feature_as_of_utc=canonical_feature_as_of,
            result_available_at_utc=result_available_at_utc,
        )

    return AvailabilityGateDecision(
        result_usage_allowed=True,
        block_reason=None,
        game_id=game_id,
        feature_as_of_utc=canonical_feature_as_of,
        result_available_at_utc=result_available_at_utc,
    )
