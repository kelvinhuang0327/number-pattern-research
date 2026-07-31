"""Side-effect-free BIG 6/49 real-publication manifest tooling.

This module never selects a draw, looks up a deadline, generates tickets, reads
a database, writes artifacts, or calls a publication service.  A separately
authorized future task must supply every target/source/deadline field and the
already-generated outputs for all frozen strategies.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

__all__ = [
    "ALREADY_PUBLISHED_SAME_MANIFEST",
    "BIG649_FROZEN_STRATEGY_IDS",
    "DETERMINISTIC_MISMATCH_STOP",
    "DUPLICATE_MANIFEST_CONFLICT_STOP",
    "ENDPOINT",
    "IDEMPOTENCY_PASS",
    "MANIFEST_SCHEMA_VERSION",
    "NO_EXISTING_MANIFEST",
    "NO_PREVIOUS_MANIFEST",
    "PublicationGuardError",
    "RANDOMNESS_NOT_APPLICABLE",
    "SAFE_VALIDATE_ONLY",
    "STOCHASTIC_POLICY_MISSING_STOP",
    "STOCHASTIC_READY_WITH_SEED_AND_POLICY",
    "SYNTHETIC_TARGET",
    "build_publication_manifest_candidate",
    "check_publication_duplicate",
    "check_publication_idempotency",
    "classify_publication_randomness",
    "compute_manifest_sha256",
    "resolve_publication_artifact_paths",
    "stop_on_publication_guard_failure",
    "validate_publication_manifest",
]


class PublicationGuardError(ValueError):
    """Raised when a publication manifest or pre-write guard fails closed."""


MANIFEST_SCHEMA_VERSION = "p280ad_big649_real_publication_manifest_v1"
TASK_FAMILY = "BIG649_REAL_PUBLICATION"
SAFE_VALIDATE_ONLY = "SAFE_VALIDATE_ONLY"
PUBLICATION_STATUS = "MANIFEST_CANDIDATE_NOT_WRITTEN"
SYNTHETIC_TARGET = "SYNTHETIC_BIG649_TARGET_DO_NOT_PUBLISH"

GAME = {"id": "BIG", "label": "大樂透", "rule": "6-49"}
ENDPOINT = "BIG_ANY_PRIZE_AWARE_WIN"
STRATEGY_COUNT = 11
N = 1
BET_INDEX = 1
TICKET_SIZE = 6
NUMBER_MIN = 1
NUMBER_MAX = 49

BIG649_FROZEN_STRATEGY_IDS = (
    "bet2_fourier_expansion_biglotto",
    "biglotto_deviation_2bet",
    "biglotto_echo_aware_3bet",
    "biglotto_triple_strike",
    "biglotto_ts3_markov_4bet_w30",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
    "fourier30_markov30_biglotto",
    "markov_2bet_biglotto",
    "markov_single_biglotto",
    "ts3_regime_3bet",
)

NO_EXISTING_MANIFEST = "NO_EXISTING_MANIFEST"
ALREADY_PUBLISHED_SAME_MANIFEST = "ALREADY_PUBLISHED_SAME_MANIFEST"
DUPLICATE_MANIFEST_CONFLICT_STOP = "DUPLICATE_MANIFEST_CONFLICT_STOP"
NO_PREVIOUS_MANIFEST = "NO_PREVIOUS_MANIFEST"
IDEMPOTENCY_PASS = "IDEMPOTENCY_PASS"
DETERMINISTIC_MISMATCH_STOP = "DETERMINISTIC_MISMATCH_STOP"
RANDOMNESS_NOT_APPLICABLE = "RANDOMNESS_NOT_APPLICABLE"
STOCHASTIC_READY_WITH_SEED_AND_POLICY = "STOCHASTIC_READY_WITH_SEED_AND_POLICY"
STOCHASTIC_POLICY_MISSING_STOP = "STOCHASTIC_POLICY_MISSING_STOP"
STOCHASTIC_RERUN_ALLOWED = "STOCHASTIC_RERUN_ALLOWED_WITH_RECORDED_POLICY"

_REAL_TARGET_PATTERN = re.compile(r"^[0-9]{9}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_TICKET_INPUT_FIELDS = {"strategy_id", "bet_index", "predicted_main_numbers"}
_TICKET_FIELDS = _TICKET_INPUT_FIELDS | {"canonical_sorted_ticket", "ticket_sha256"}
_MANIFEST_FIELDS = {
    "schema_version",
    "task_family",
    "mode",
    "game",
    "target_draw",
    "target_draw_date",
    "official_source_url",
    "official_source_accessed_at",
    "official_deadline",
    "outcome_unavailable_at_generation",
    "generation_timestamp_utc",
    "cutoff_policy",
    "history_cutoff",
    "strategy_count",
    "strategy_ids",
    "N",
    "bet_index",
    "endpoint",
    "tickets",
    "ticket_validation",
    "duplicate_guard",
    "idempotency_guard",
    "randomness_guard",
    "source_digests",
    "tool_digests",
    "manifest_sha256",
    "publication_status",
    "no_outcome_used",
    "no_rerun_after_generation",
    "prediction_success_claim",
    "strategy_promoted",
    "activation_authorized",
    "real_publication_requires_owner_authorization",
}


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PublicationGuardError(f"value is not canonical JSON: {exc}") from exc
    return (rendered + "\n").encode("utf-8")


def compute_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Hash canonical manifest content while excluding the self-hash field."""
    if not isinstance(manifest, Mapping):
        raise PublicationGuardError("manifest must be a mapping")
    payload = {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key != "manifest_sha256"
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationGuardError(f"{label} is required")
    return value


def _require_aware_datetime(value: Any, label: str, *, utc_only: bool = False) -> str:
    text = _require_text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicationGuardError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PublicationGuardError(f"{label} must include a UTC offset")
    if utc_only and parsed.utcoffset().total_seconds() != 0:
        raise PublicationGuardError(f"{label} must be UTC")
    return text


def _validate_target_draw(target_draw: Any) -> str:
    value = _require_text(target_draw, "target_draw")
    if value != SYNTHETIC_TARGET and _REAL_TARGET_PATTERN.fullmatch(value) is None:
        raise PublicationGuardError(
            "target_draw must be a nine-digit BIG draw ID or the synthetic fixture ID"
        )
    return value


def resolve_publication_artifact_paths(target_draw: str) -> dict[str, str]:
    """Resolve deterministic relative paths without reading or writing the filesystem."""
    safe_target = _validate_target_draw(target_draw)
    base = PurePosixPath("outputs/publications/big649/pre_draw") / safe_target
    return {
        "manifest_json": str(base / "manifest.json"),
        "manifest_markdown": str(base / "manifest.md"),
    }


def _canonical_ticket(numbers: Any, label: str) -> list[int]:
    if not isinstance(numbers, (list, tuple)) or len(numbers) != TICKET_SIZE:
        raise PublicationGuardError(f"{label} must contain exactly six numbers")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in numbers):
        raise PublicationGuardError(f"{label} must contain integers only")
    if len(set(numbers)) != TICKET_SIZE:
        raise PublicationGuardError(f"{label} contains duplicate numbers")
    if any(number < NUMBER_MIN or number > NUMBER_MAX for number in numbers):
        raise PublicationGuardError(f"{label} number outside 1..49")
    return sorted(numbers)


def _ticket_sha256(numbers: Sequence[int]) -> str:
    return hashlib.sha256(
        _canonical_json_bytes({"game": GAME, "main_numbers": list(numbers)})
    ).hexdigest()


def _canonical_tickets(tickets: Any) -> list[dict[str, Any]]:
    if not isinstance(tickets, (list, tuple)):
        raise PublicationGuardError("tickets must be a sequence")
    by_strategy: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(tickets):
        if not isinstance(record, Mapping) or frozenset(record) not in {
            frozenset(_TICKET_INPUT_FIELDS),
            frozenset(_TICKET_FIELDS),
        }:
            raise PublicationGuardError(f"tickets[{index}] fields do not match schema")
        strategy_id = record.get("strategy_id")
        if not isinstance(strategy_id, str):
            raise PublicationGuardError(f"tickets[{index}].strategy_id must be a string")
        if strategy_id in by_strategy:
            raise PublicationGuardError(f"duplicate strategy ticket: {strategy_id}")
        if record.get("bet_index") != BET_INDEX or isinstance(record.get("bet_index"), bool):
            raise PublicationGuardError(f"{strategy_id} must use bet_index=1")
        canonical = _canonical_ticket(
            record.get("predicted_main_numbers"),
            f"tickets[{index}].predicted_main_numbers",
        )
        expected_hash = _ticket_sha256(canonical)
        if "canonical_sorted_ticket" in record and record["canonical_sorted_ticket"] != canonical:
            raise PublicationGuardError(f"{strategy_id} canonical ticket mismatch")
        if "ticket_sha256" in record and record["ticket_sha256"] != expected_hash:
            raise PublicationGuardError(f"{strategy_id} ticket hash mismatch")
        by_strategy[strategy_id] = {
            "strategy_id": strategy_id,
            "bet_index": BET_INDEX,
            "predicted_main_numbers": canonical,
            "canonical_sorted_ticket": canonical,
            "ticket_sha256": expected_hash,
        }

    expected = set(BIG649_FROZEN_STRATEGY_IDS)
    actual = set(by_strategy)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise PublicationGuardError(
            f"strategy set must be exact frozen 11; missing={missing}; extra={extra}"
        )
    ordered = [by_strategy[strategy_id] for strategy_id in BIG649_FROZEN_STRATEGY_IDS]
    hashes = [record["ticket_sha256"] for record in ordered]
    if len(set(hashes)) != len(hashes):
        raise PublicationGuardError("duplicate complete tickets across strategies")
    return ordered


def _validate_digests(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise PublicationGuardError(f"{label} must be a non-empty mapping")
    canonical: dict[str, str] = {}
    for key, digest in value.items():
        name = _require_text(key, f"{label} key")
        if any(token in name for token in ("..", "/", "\\")):
            raise PublicationGuardError(f"{label} key is unsafe: {name}")
        if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
            raise PublicationGuardError(f"{label}.{name} must be lowercase SHA-256")
        canonical[name] = digest
    return dict(sorted(canonical.items()))


def classify_publication_randomness(
    *,
    strategy_kind: str = "deterministic",
    seed: str | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify whether publication outputs have an auditable randomness policy."""
    if not isinstance(strategy_kind, str):
        raise PublicationGuardError("strategy_kind must be deterministic or stochastic")
    kind = strategy_kind.strip().lower()
    if kind == "deterministic":
        return {
            "status": RANDOMNESS_NOT_APPLICABLE,
            "strategy_kind": kind,
            "seed": None,
            "policy": None,
        }
    if kind != "stochastic":
        raise PublicationGuardError("strategy_kind must be deterministic or stochastic")
    valid_seed = isinstance(seed, str) and bool(seed.strip())
    valid_policy = isinstance(policy, Mapping) and bool(policy)
    return {
        "status": (
            STOCHASTIC_READY_WITH_SEED_AND_POLICY
            if valid_seed and valid_policy
            else STOCHASTIC_POLICY_MISSING_STOP
        ),
        "strategy_kind": kind,
        "seed": seed if valid_seed else None,
        "policy": copy.deepcopy(dict(policy)) if valid_policy else None,
    }


def _publication_signature(manifest: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {
        "manifest_sha256",
        "duplicate_guard",
        "idempotency_guard",
    }
    return {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key not in ignored
    }


def check_publication_duplicate(
    existing_manifest: Mapping[str, Any] | None,
    candidate_manifest: Mapping[str, Any],
) -> dict[str, str]:
    """Classify an existing target manifest without performing filesystem access."""
    candidate = _validate_manifest_structure(candidate_manifest, enforce_guard_stop=False)
    if existing_manifest is None:
        return {"status": NO_EXISTING_MANIFEST}
    existing = _validate_manifest_structure(existing_manifest, enforce_guard_stop=False)
    if existing["target_draw"] != candidate["target_draw"]:
        return {"status": NO_EXISTING_MANIFEST}
    if _publication_signature(existing) == _publication_signature(candidate):
        return {"status": ALREADY_PUBLISHED_SAME_MANIFEST}
    return {"status": DUPLICATE_MANIFEST_CONFLICT_STOP}


def check_publication_idempotency(
    previous_manifest: Mapping[str, Any] | None,
    candidate_manifest: Mapping[str, Any],
    *,
    strategy_kind: str = "deterministic",
    seed: str | None = None,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Fail closed on deterministic drift and unaudited stochastic reruns."""
    candidate = _validate_manifest_structure(candidate_manifest, enforce_guard_stop=False)
    if previous_manifest is None:
        return {"status": NO_PREVIOUS_MANIFEST}
    previous = _validate_manifest_structure(previous_manifest, enforce_guard_stop=False)
    if _publication_signature(previous) == _publication_signature(candidate):
        return {"status": IDEMPOTENCY_PASS}
    randomness = classify_publication_randomness(
        strategy_kind=strategy_kind,
        seed=seed,
        policy=policy,
    )
    if randomness["status"] == STOCHASTIC_READY_WITH_SEED_AND_POLICY:
        return {"status": STOCHASTIC_RERUN_ALLOWED}
    if randomness["status"] == STOCHASTIC_POLICY_MISSING_STOP:
        return {"status": STOCHASTIC_POLICY_MISSING_STOP}
    return {"status": DETERMINISTIC_MISMATCH_STOP}


def stop_on_publication_guard_failure(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Raise on any ticket, duplicate, idempotency, or randomness STOP state."""
    validated = _validate_manifest_structure(manifest, enforce_guard_stop=False)
    stops = {
        DUPLICATE_MANIFEST_CONFLICT_STOP,
        DETERMINISTIC_MISMATCH_STOP,
        STOCHASTIC_POLICY_MISSING_STOP,
    }
    statuses = {
        validated["duplicate_guard"]["status"],
        validated["idempotency_guard"]["status"],
        validated["randomness_guard"]["status"],
    }
    failed = sorted(statuses & stops)
    if failed:
        raise PublicationGuardError(f"publication guard STOP: {', '.join(failed)}")
    if validated["ticket_validation"].get("status") != "PASS":
        raise PublicationGuardError("publication guard STOP: ticket validation failed")
    return validated


def _validate_manifest_structure(
    manifest: Any,
    *,
    enforce_guard_stop: bool,
) -> dict[str, Any]:
    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_FIELDS:
        raise PublicationGuardError("manifest top-level fields do not match schema")
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise PublicationGuardError("schema_version mismatch")
    if manifest["task_family"] != TASK_FAMILY:
        raise PublicationGuardError("task_family mismatch")
    if manifest["mode"] != SAFE_VALIDATE_ONLY:
        raise PublicationGuardError("mode must be SAFE_VALIDATE_ONLY")
    if manifest["publication_status"] != PUBLICATION_STATUS:
        raise PublicationGuardError("publication_status mismatch")
    if manifest["game"] != GAME:
        raise PublicationGuardError("game must be BIG / 大樂透 / 6-49")
    _validate_target_draw(manifest["target_draw"])
    resolve_publication_artifact_paths(manifest["target_draw"])
    try:
        date.fromisoformat(_require_text(manifest["target_draw_date"], "target_draw_date"))
    except ValueError as exc:
        raise PublicationGuardError("target_draw_date must be YYYY-MM-DD") from exc
    source_url = _require_text(manifest["official_source_url"], "official_source_url")
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise PublicationGuardError("official_source_url must be an HTTPS URL")
    _require_aware_datetime(manifest["official_source_accessed_at"], "official_source_accessed_at")
    _require_aware_datetime(manifest["official_deadline"], "official_deadline")
    _require_aware_datetime(
        manifest["generation_timestamp_utc"],
        "generation_timestamp_utc",
        utc_only=True,
    )
    if manifest["outcome_unavailable_at_generation"] is not True:
        raise PublicationGuardError("outcome_unavailable_at_generation must be true")
    if manifest["no_outcome_used"] is not True:
        raise PublicationGuardError("no_outcome_used must be true")
    if manifest["no_rerun_after_generation"] is not True:
        raise PublicationGuardError("no_rerun_after_generation must be true")
    if manifest["prediction_success_claim"] is not False:
        raise PublicationGuardError("prediction_success_claim must be false")
    if manifest["strategy_promoted"] is not False:
        raise PublicationGuardError("strategy_promoted must be false")
    if manifest["activation_authorized"] is not False:
        raise PublicationGuardError("activation_authorized must be false")
    if manifest["real_publication_requires_owner_authorization"] is not True:
        raise PublicationGuardError("real publication requires Owner authorization")
    _require_text(manifest["cutoff_policy"], "cutoff_policy")
    _require_text(manifest["history_cutoff"], "history_cutoff")
    if manifest["strategy_count"] != STRATEGY_COUNT:
        raise PublicationGuardError("strategy_count must be exactly 11")
    if manifest["strategy_ids"] != list(BIG649_FROZEN_STRATEGY_IDS):
        raise PublicationGuardError("strategy_ids must be the exact frozen 11 IDs")
    if manifest["N"] != N or isinstance(manifest["N"], bool):
        raise PublicationGuardError("N must be 1")
    if manifest["bet_index"] != BET_INDEX or isinstance(manifest["bet_index"], bool):
        raise PublicationGuardError("bet_index must be 1")
    if manifest["endpoint"] != ENDPOINT:
        raise PublicationGuardError("endpoint mismatch")
    canonical_tickets = _canonical_tickets(manifest["tickets"])
    if canonical_tickets != manifest["tickets"]:
        raise PublicationGuardError("tickets are not canonical")
    expected_ticket_validation = {
        "status": "PASS",
        "ticket_count": STRATEGY_COUNT,
        "numbers_per_ticket": TICKET_SIZE,
        "number_range": [NUMBER_MIN, NUMBER_MAX],
        "duplicate_complete_ticket_count": 0,
    }
    if manifest["ticket_validation"] != expected_ticket_validation:
        raise PublicationGuardError("ticket_validation mismatch")
    allowed_duplicate = {
        NO_EXISTING_MANIFEST,
        ALREADY_PUBLISHED_SAME_MANIFEST,
        DUPLICATE_MANIFEST_CONFLICT_STOP,
    }
    allowed_idempotency = {
        NO_PREVIOUS_MANIFEST,
        IDEMPOTENCY_PASS,
        DETERMINISTIC_MISMATCH_STOP,
        STOCHASTIC_POLICY_MISSING_STOP,
        STOCHASTIC_RERUN_ALLOWED,
    }
    allowed_randomness = {
        RANDOMNESS_NOT_APPLICABLE,
        STOCHASTIC_READY_WITH_SEED_AND_POLICY,
        STOCHASTIC_POLICY_MISSING_STOP,
    }
    for field, allowed in (
        ("duplicate_guard", allowed_duplicate),
        ("idempotency_guard", allowed_idempotency),
        ("randomness_guard", allowed_randomness),
    ):
        guard = manifest[field]
        if not isinstance(guard, Mapping) or guard.get("status") not in allowed:
            raise PublicationGuardError(f"{field} status mismatch")
    if set(manifest["duplicate_guard"]) != {"status"}:
        raise PublicationGuardError("duplicate_guard fields mismatch")
    if set(manifest["idempotency_guard"]) != {"status"}:
        raise PublicationGuardError("idempotency_guard fields mismatch")
    randomness_guard = manifest["randomness_guard"]
    if set(randomness_guard) != {"status", "strategy_kind", "seed", "policy"}:
        raise PublicationGuardError("randomness_guard fields mismatch")
    if randomness_guard["status"] == RANDOMNESS_NOT_APPLICABLE:
        if randomness_guard != {
            "status": RANDOMNESS_NOT_APPLICABLE,
            "strategy_kind": "deterministic",
            "seed": None,
            "policy": None,
        }:
            raise PublicationGuardError("deterministic randomness guard mismatch")
    elif randomness_guard["status"] == STOCHASTIC_READY_WITH_SEED_AND_POLICY:
        if (
            randomness_guard["strategy_kind"] != "stochastic"
            or not isinstance(randomness_guard["seed"], str)
            or not randomness_guard["seed"].strip()
            or not isinstance(randomness_guard["policy"], Mapping)
            or not randomness_guard["policy"]
        ):
            raise PublicationGuardError("stochastic seed/policy missing")
    elif randomness_guard["strategy_kind"] != "stochastic":
        raise PublicationGuardError("stochastic randomness guard mismatch")
    _validate_digests(manifest["source_digests"], "source_digests")
    _validate_digests(manifest["tool_digests"], "tool_digests")
    digest = manifest["manifest_sha256"]
    if not isinstance(digest, str) or _HEX_64.fullmatch(digest) is None:
        raise PublicationGuardError("manifest_sha256 must be lowercase SHA-256")
    if digest != compute_manifest_sha256(manifest):
        raise PublicationGuardError("manifest hash mismatch; manifest mutated")
    validated = copy.deepcopy(dict(manifest))
    if enforce_guard_stop:
        return stop_on_publication_guard_failure(validated)
    return validated


def validate_publication_manifest(manifest: Any) -> dict[str, Any]:
    """Validate schema, caller data, self-hash, and every pre-write guard."""
    return _validate_manifest_structure(manifest, enforce_guard_stop=True)


def build_publication_manifest_candidate(
    *,
    target_draw: str,
    target_draw_date: str,
    official_source_url: str,
    official_source_accessed_at: str,
    official_deadline: str,
    generation_timestamp_utc: str,
    cutoff_policy: str,
    history_cutoff: str,
    tickets: Sequence[Mapping[str, Any]],
    source_digests: Mapping[str, str],
    tool_digests: Mapping[str, str],
    outcome_unavailable_at_generation: bool = True,
    no_outcome_used: bool = True,
    no_rerun_after_generation: bool = True,
    prediction_success_claim: bool = False,
    strategy_promoted: bool = False,
    activation_authorized: bool = False,
    real_publication_requires_owner_authorization: bool = True,
    strategy_kind: str = "deterministic",
    randomness_seed: str | None = None,
    randomness_policy: Mapping[str, Any] | None = None,
    existing_manifest: Mapping[str, Any] | None = None,
    previous_manifest: Mapping[str, Any] | None = None,
    mode: str = SAFE_VALIDATE_ONLY,
) -> dict[str, Any]:
    """Build and validate one candidate; no lookup, generation, write, or publish occurs."""
    canonical_tickets = _canonical_tickets(tickets)
    randomness_guard = classify_publication_randomness(
        strategy_kind=strategy_kind,
        seed=randomness_seed,
        policy=randomness_policy,
    )
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "task_family": TASK_FAMILY,
        "mode": mode,
        "game": copy.deepcopy(GAME),
        "target_draw": target_draw,
        "target_draw_date": target_draw_date,
        "official_source_url": official_source_url,
        "official_source_accessed_at": official_source_accessed_at,
        "official_deadline": official_deadline,
        "outcome_unavailable_at_generation": outcome_unavailable_at_generation,
        "generation_timestamp_utc": generation_timestamp_utc,
        "cutoff_policy": cutoff_policy,
        "history_cutoff": history_cutoff,
        "strategy_count": STRATEGY_COUNT,
        "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
        "N": N,
        "bet_index": BET_INDEX,
        "endpoint": ENDPOINT,
        "tickets": canonical_tickets,
        "ticket_validation": {
            "status": "PASS",
            "ticket_count": STRATEGY_COUNT,
            "numbers_per_ticket": TICKET_SIZE,
            "number_range": [NUMBER_MIN, NUMBER_MAX],
            "duplicate_complete_ticket_count": 0,
        },
        "duplicate_guard": {"status": NO_EXISTING_MANIFEST},
        "idempotency_guard": {"status": NO_PREVIOUS_MANIFEST},
        "randomness_guard": randomness_guard,
        "source_digests": _validate_digests(source_digests, "source_digests"),
        "tool_digests": _validate_digests(tool_digests, "tool_digests"),
        "manifest_sha256": "0" * 64,
        "publication_status": PUBLICATION_STATUS,
        "no_outcome_used": no_outcome_used,
        "no_rerun_after_generation": no_rerun_after_generation,
        "prediction_success_claim": prediction_success_claim,
        "strategy_promoted": strategy_promoted,
        "activation_authorized": activation_authorized,
        "real_publication_requires_owner_authorization": (
            real_publication_requires_owner_authorization
        ),
    }
    manifest["manifest_sha256"] = compute_manifest_sha256(manifest)
    _validate_manifest_structure(manifest, enforce_guard_stop=False)

    manifest["duplicate_guard"] = check_publication_duplicate(existing_manifest, manifest)
    manifest["manifest_sha256"] = compute_manifest_sha256(manifest)
    manifest["idempotency_guard"] = check_publication_idempotency(
        previous_manifest,
        manifest,
        strategy_kind=strategy_kind,
        seed=randomness_seed,
        policy=randomness_policy,
    )
    manifest["manifest_sha256"] = compute_manifest_sha256(manifest)
    return validate_publication_manifest(manifest)
