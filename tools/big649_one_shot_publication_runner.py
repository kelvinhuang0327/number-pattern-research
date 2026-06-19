"""P280X BIG 6/49 one-shot publication runner.

Dry-run only by default. This module builds and validates an unpublished
manifest for a frozen 11-strategy BIG/大樂透/6-49 publication candidate.
It intentionally avoids DB access, target selection, deadline lookup, GitHub
publication, or any outcome evaluation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from analysis.p280d_big649_future_only_protocol import (
    BET_INDEX,
    ENDPOINT_ID,
    FREEZE_ID,
    GAME,
    GAME_LABEL,
    GAME_RULE,
    PRIMARY_BUDGET,
    ProtocolValidationError,
    STRATEGY_IDS as BIG649_FROZEN_STRATEGY_IDS,
)

__all__ = [
    "ALREADY_PUBLISHED_SAME_MANIFEST",
    "BET_INDEX",
    "BIG649_FROZEN_STRATEGY_IDS",
    "DRY_RUN_ONLY_NOT_PUBLISHED",
    "DRY_RUN_TARGET_LABEL",
    "DRY_RUN_WARNING",
    "DUPLICATE_PUBLICATION_CONFLICT",
    "IDEMPOTENCY_FAIL_UNEXPLAINED",
    "IDEMPOTENCY_PASS",
    "MANIFEST_SCHEMA_VERSION",
    "NO_EXISTING_MANIFEST",
    "NOT_A_REAL_PREDICTION",
    "PUBLICATION_STATUS_NOT_PUBLISHED",
    "ProtocolValidationError",
    "RANDOMNESS_ALLOWED_WITH_SEED",
    "RANDOMNESS_NOT_APPLICABLE",
    "RANDOMNESS_POLICY_MISSING",
    "SCHEMA_VERSION",
    "STOP_UNEXPLAINED_NONDETERMINISM",
    "build_default_source_digests",
    "build_default_strategy_tickets",
    "build_dry_run_manifest",
    "canonical_json_bytes",
    "check_duplicate_manifest",
    "check_idempotency",
    "classify_randomness",
    "manifest_sha256",
    "stop_on_unexplained_difference",
    "validate_manifest",
    "validate_ticket",
]

SCHEMA_VERSION = "p280x_big649_one_shot_publication_runner_design_v1"
MANIFEST_SCHEMA_VERSION = SCHEMA_VERSION
DRY_RUN_ONLY_NOT_PUBLISHED = "DRY_RUN_ONLY_NOT_PUBLISHED"
DRY_RUN_WARNING = "NOT_A_REAL_PREDICTION"
NOT_A_REAL_PREDICTION = DRY_RUN_WARNING
DRY_RUN_TARGET_LABEL = "DRY_RUN_TARGET_DO_NOT_PUBLISH"
DRY_RUN_CUTOFF_LABEL = "DRY_RUN_CUTOFF_DO_NOT_PUBLISH"
PUBLICATION_STATUS_NOT_PUBLISHED = "NOT_PUBLISHED"

NO_EXISTING_MANIFEST = "NO_EXISTING_MANIFEST"
ALREADY_PUBLISHED_SAME_MANIFEST = "ALREADY_PUBLISHED_SAME_MANIFEST"
DUPLICATE_PUBLICATION_CONFLICT = "DUPLICATE_PUBLICATION_CONFLICT"
IDEMPOTENCY_PASS = "IDEMPOTENCY_PASS"
IDEMPOTENCY_FAIL_UNEXPLAINED = "IDEMPOTENCY_FAIL_UNEXPLAINED"
RANDOMNESS_ALLOWED_WITH_SEED = "RANDOMNESS_ALLOWED_WITH_SEED"
RANDOMNESS_POLICY_MISSING = "RANDOMNESS_POLICY_MISSING"
STOP_UNEXPLAINED_NONDETERMINISM = "STOP_UNEXPLAINED_NONDETERMINISM"
RANDOMNESS_NOT_APPLICABLE = "RANDOMNESS_NOT_APPLICABLE"

TICKET_SIZE = 6
NUMBER_MIN = 1
NUMBER_MAX = 49
DEFAULT_TICKET_SEED = "P280X_BIG649_SYNTHETIC_TICKET_SEED_20260619"
DEFAULT_SOURCE_SEED = "P280X_BIG649_SYNTHETIC_SOURCE_SEED_20260619"
DEFAULT_LOCAL_GENERATED_AT = "2026-06-19T00:00:00+08:00"
SOURCE_FIELDS = {"source_path", "git_blob_sha1", "sha256", "generator_identity"}
TICKET_FIELDS = {"strategy_id", "bet_index", "predicted_main_numbers"}
MANIFEST_FIELDS = {
    "schema_version",
    "mode",
    "publication_status",
    "dry_run_warning",
    "game",
    "target_draw_label",
    "history_cutoff_label",
    "origin_main_sha",
    "protocol_source_sha256",
    "history_snapshot_digest",
    "source_identity_digest",
    "strategy_identity_digest",
    "real_target_selected",
    "real_ticket_published",
    "official_deadline_lookup",
    "future_evaluation_started",
    "zero_db_guard",
    "no_github_publication_side_effect",
    "strategy_count",
    "strategy_ids",
    "primary_budget_n",
    "bet_index",
    "endpoint_id",
    "strategy_source_digests",
    "strategy_tickets",
    "ticket_validation_result",
    "duplicate_check_result",
    "idempotency_check_result",
    "randomness_policy_result",
    "stop_conditions",
    "publication_guard_state",
    "manifest_sha256",
}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes with stable ordering."""
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (rendered + "\n").encode("utf-8")


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Return the manifest digest excluding the self-hash field."""
    payload = {
        key: copy.deepcopy(value)
        for key, value in manifest.items()
        if key != "manifest_sha256"
    }
    return _sha256_hex(canonical_json_bytes(payload))


def _require_hex_or_label(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if isinstance(value, str) and (
        pattern.fullmatch(value) is not None or value.startswith("DRY_RUN_")
    ):
        return value
    raise ProtocolValidationError(f"{label} must be lowercase hex or a DRY_RUN label")


def _canonical_ticket_numbers(numbers: Any, label: str) -> list[int]:
    if not isinstance(numbers, (list, tuple)) or len(numbers) != TICKET_SIZE:
        raise ProtocolValidationError(f"{label} must contain exactly six numbers")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in numbers):
        raise ProtocolValidationError(f"{label} must contain integers only")
    if len(set(numbers)) != TICKET_SIZE:
        raise ProtocolValidationError(f"{label} must contain six unique numbers")
    if any(number < NUMBER_MIN or number > NUMBER_MAX for number in numbers):
        raise ProtocolValidationError(f"{label} number outside 1..49")
    return sorted(numbers)


def validate_ticket(numbers: Sequence[int]) -> list[int]:
    """Validate and canonicalize a 6/49 ticket."""
    return _canonical_ticket_numbers(numbers, "ticket")


def ticket_sha256(ticket: Sequence[int]) -> str:
    return _sha256_hex(
        canonical_json_bytes({"game": GAME, "main_numbers": validate_ticket(ticket)})
    )


def build_default_strategy_tickets(seed: str = DEFAULT_TICKET_SEED) -> list[dict[str, Any]]:
    """Generate deterministic dry-run-only tickets for the frozen 11 strategies."""
    records: list[dict[str, Any]] = []
    for strategy_id in BIG649_FROZEN_STRATEGY_IDS:
        material = hashlib.sha256(f"{seed}:{strategy_id}".encode("utf-8")).digest()
        numbers: list[int] = []
        counter = 0
        while len(numbers) < TICKET_SIZE:
            block = hashlib.sha256(material + counter.to_bytes(2, "big")).digest()
            for byte in block:
                candidate = (byte % NUMBER_MAX) + 1
                if candidate not in numbers:
                    numbers.append(candidate)
                    if len(numbers) == TICKET_SIZE:
                        break
            counter += 1
        records.append(
            {
                "strategy_id": strategy_id,
                "bet_index": BET_INDEX,
                "predicted_main_numbers": sorted(numbers),
            }
        )
    return records


def build_default_source_digests(seed: str = DEFAULT_SOURCE_SEED) -> dict[str, dict[str, str]]:
    """Return placeholder read-only source identity records for the frozen 11 IDs."""
    source_digests: dict[str, dict[str, str]] = {}
    for strategy_id in BIG649_FROZEN_STRATEGY_IDS:
        source_digests[strategy_id] = {
            "source_path": f"dry_run/{strategy_id}.json",
            "git_blob_sha1": _sha256_hex(f"{seed}:{strategy_id}:blob1".encode("utf-8"))[:40],
            "sha256": _sha256_hex(f"{seed}:{strategy_id}:blob2".encode("utf-8")),
            "generator_identity": f"{seed}:{strategy_id}",
        }
    return source_digests


def _canonical_source_digests(
    source_digests: Mapping[str, Mapping[str, str]]
) -> dict[str, dict[str, str]]:
    if not isinstance(source_digests, Mapping) or set(source_digests) != set(
        BIG649_FROZEN_STRATEGY_IDS
    ):
        raise ProtocolValidationError("strategy_source_digests must cover exact frozen 11 IDs")

    canonical: dict[str, dict[str, str]] = {}
    for strategy_id in BIG649_FROZEN_STRATEGY_IDS:
        record = source_digests[strategy_id]
        if not isinstance(record, Mapping) or set(record) != SOURCE_FIELDS:
            raise ProtocolValidationError(f"invalid source record for {strategy_id}")
        source_path = record["source_path"]
        if not isinstance(source_path, str) or not source_path or source_path.startswith("/"):
            raise ProtocolValidationError(f"invalid source_path for {strategy_id}")
        canonical[strategy_id] = {
            "source_path": source_path,
            "git_blob_sha1": _require_hex_or_label(
                record["git_blob_sha1"], HEX_40, f"{strategy_id}.git_blob_sha1"
            ),
            "sha256": _require_hex_or_label(
                record["sha256"], HEX_64, f"{strategy_id}.sha256"
            ),
            "generator_identity": record["generator_identity"],
        }
    return canonical


def _canonical_strategy_tickets(
    strategy_tickets: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(strategy_tickets, (list, tuple)):
        raise ProtocolValidationError("strategy_tickets must be a sequence")

    records: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(strategy_tickets):
        if not isinstance(record, Mapping) or set(record) != TICKET_FIELDS:
            raise ProtocolValidationError(f"strategy_tickets[{index}] has invalid fields")
        strategy_id = record["strategy_id"]
        if not isinstance(strategy_id, str):
            raise ProtocolValidationError("strategy_id must be a string")
        if strategy_id in records:
            raise ProtocolValidationError(f"duplicate strategy ID: {strategy_id}")
        bet_index = record["bet_index"]
        if bet_index != BET_INDEX or isinstance(bet_index, bool):
            raise ProtocolValidationError(f"{strategy_id} must use exactly bet_index=1")
        canonical = validate_ticket(record["predicted_main_numbers"])
        records[strategy_id] = {
            "strategy_id": strategy_id,
            "bet_index": BET_INDEX,
            "predicted_main_numbers": canonical,
            "canonical_sorted_ticket": canonical,
            "ticket_sha256": ticket_sha256(canonical),
        }

    if set(records) != set(BIG649_FROZEN_STRATEGY_IDS):
        missing = sorted(set(BIG649_FROZEN_STRATEGY_IDS) - set(records))
        extra = sorted(set(records) - set(BIG649_FROZEN_STRATEGY_IDS))
        raise ProtocolValidationError(
            f"strategy set must be exact frozen 11; missing={missing}; extra={extra}"
        )

    by_ticket: dict[str, list[str]] = {}
    for strategy_id, record in records.items():
        by_ticket.setdefault(record["ticket_sha256"], []).append(strategy_id)

    ordered: list[dict[str, Any]] = []
    for strategy_id in BIG649_FROZEN_STRATEGY_IDS:
        record = records[strategy_id]
        peers = sorted(peer for peer in by_ticket[record["ticket_sha256"]] if peer != strategy_id)
        record["duplicate_ticket_relationship"] = {
            "collision": bool(peers),
            "other_strategy_ids": peers,
        }
        ordered.append(record)
    return ordered


def _manifest_core_signature(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable publication content signature used for duplicate/idempotency checks."""
    return {
        "schema_version": manifest["schema_version"],
        "mode": manifest["mode"],
        "publication_status": manifest["publication_status"],
        "dry_run_warning": manifest["dry_run_warning"],
        "game": manifest["game"],
        "target_draw_label": manifest["target_draw_label"],
        "history_cutoff_label": manifest["history_cutoff_label"],
        "origin_main_sha": manifest["origin_main_sha"],
        "protocol_source_sha256": manifest["protocol_source_sha256"],
        "history_snapshot_digest": manifest["history_snapshot_digest"],
        "source_identity_digest": manifest["source_identity_digest"],
        "strategy_identity_digest": manifest["strategy_identity_digest"],
        "real_target_selected": manifest["real_target_selected"],
        "real_ticket_published": manifest["real_ticket_published"],
        "official_deadline_lookup": manifest["official_deadline_lookup"],
        "future_evaluation_started": manifest["future_evaluation_started"],
        "zero_db_guard": manifest["zero_db_guard"],
        "no_github_publication_side_effect": manifest["no_github_publication_side_effect"],
        "strategy_count": manifest["strategy_count"],
        "strategy_ids": manifest["strategy_ids"],
        "primary_budget_n": manifest["primary_budget_n"],
        "bet_index": manifest["bet_index"],
        "endpoint_id": manifest["endpoint_id"],
        "strategy_source_digests": manifest["strategy_source_digests"],
        "strategy_tickets": manifest["strategy_tickets"],
        "ticket_validation_result": manifest["ticket_validation_result"],
        "stop_conditions": manifest["stop_conditions"],
        "publication_guard_state": manifest["publication_guard_state"],
    }


def classify_randomness(
    *,
    strategy_kind: str = "deterministic",
    randomness_policy: Mapping[str, Any] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    """Classify whether a rerun difference is explainable by randomness."""
    strategy_kind = strategy_kind.lower().strip()
    if strategy_kind not in {"deterministic", "stochastic"}:
        raise ProtocolValidationError("strategy_kind must be deterministic or stochastic")

    if strategy_kind == "deterministic":
        return {
            "status": RANDOMNESS_NOT_APPLICABLE,
            "strategy_kind": strategy_kind,
            "seed_recorded": False,
            "randomness_policy_present": randomness_policy is not None,
        }

    policy_present = bool(randomness_policy)
    seed_present = isinstance(seed, str) and bool(seed)
    if not policy_present or not seed_present:
        return {
            "status": RANDOMNESS_POLICY_MISSING,
            "strategy_kind": strategy_kind,
            "seed_recorded": seed_present,
            "randomness_policy_present": policy_present,
        }
    return {
        "status": RANDOMNESS_ALLOWED_WITH_SEED,
        "strategy_kind": strategy_kind,
        "seed_recorded": True,
        "randomness_policy_present": True,
    }


def _manifest_signature(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_manifest_core_signature(manifest),
        "manifest_sha256": manifest["manifest_sha256"],
    }


def check_duplicate_manifest(
    existing_manifest: Mapping[str, Any] | None,
    candidate_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Check whether a target publication already exists."""
    if existing_manifest is None:
        return {"status": NO_EXISTING_MANIFEST}

    existing = validate_manifest(existing_manifest)
    candidate = validate_manifest(candidate_manifest)
    if existing["target_draw_label"] != candidate["target_draw_label"]:
        return {"status": NO_EXISTING_MANIFEST}

    if _manifest_core_signature(existing) == _manifest_core_signature(candidate):
        return {"status": ALREADY_PUBLISHED_SAME_MANIFEST}
    return {"status": DUPLICATE_PUBLICATION_CONFLICT}


def check_idempotency(
    previous_manifest: Mapping[str, Any] | None,
    candidate_manifest: Mapping[str, Any],
    *,
    strategy_kind: str = "deterministic",
    randomness_policy: Mapping[str, Any] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    """Check whether the rerun is idempotent or explained by policy-approved randomness."""
    candidate = validate_manifest(candidate_manifest)
    if previous_manifest is None:
        return {"status": NO_EXISTING_MANIFEST}

    previous = validate_manifest(previous_manifest)
    if _manifest_core_signature(previous) == _manifest_core_signature(candidate):
        return {"status": IDEMPOTENCY_PASS}

    randomness = classify_randomness(
        strategy_kind=strategy_kind, randomness_policy=randomness_policy, seed=seed
    )
    if randomness["status"] == RANDOMNESS_ALLOWED_WITH_SEED:
        return randomness
    if randomness["status"] == RANDOMNESS_POLICY_MISSING:
        raise ProtocolValidationError(RANDOMNESS_POLICY_MISSING)
    raise ProtocolValidationError(STOP_UNEXPLAINED_NONDETERMINISM)


def stop_on_unexplained_difference(
    previous_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    *,
    strategy_kind: str = "deterministic",
    randomness_policy: Mapping[str, Any] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    """Return a policy result or raise on an unexplained difference."""
    result = check_idempotency(
        previous_manifest,
        candidate_manifest,
        strategy_kind=strategy_kind,
        randomness_policy=randomness_policy,
        seed=seed,
    )
    if result["status"] == STOP_UNEXPLAINED_NONDETERMINISM:
        raise ProtocolValidationError(STOP_UNEXPLAINED_NONDETERMINISM)
    if result["status"] == RANDOMNESS_POLICY_MISSING:
        raise ProtocolValidationError(RANDOMNESS_POLICY_MISSING)
    return result


def build_dry_run_manifest(
    *,
    origin_main_sha: str,
    target_draw_label: str = DRY_RUN_TARGET_LABEL,
    history_cutoff_label: str = DRY_RUN_CUTOFF_LABEL,
    local_generated_at: str = DEFAULT_LOCAL_GENERATED_AT,
    strategy_tickets: Sequence[Mapping[str, Any]] | None = None,
    strategy_source_digests: Mapping[str, Mapping[str, str]] | None = None,
    previous_manifest: Mapping[str, Any] | None = None,
    randomness_policy: Mapping[str, Any] | None = None,
    seed: str | None = None,
    protocol_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic dry-run manifest with zero publication side effects."""
    origin_sha = _require_hex_or_label(origin_main_sha, HEX_40, "origin_main_sha")
    protocol_sha = (
        _require_hex_or_label(protocol_source_sha256, HEX_64, "protocol_source_sha256")
        if protocol_source_sha256 is not None
        else _sha256_hex(Path(__file__).read_bytes())
    )
    canonical_source_digests = _canonical_source_digests(
        strategy_source_digests or build_default_source_digests(seed=DEFAULT_SOURCE_SEED)
    )
    canonical_strategy_tickets = _canonical_strategy_tickets(
        strategy_tickets or build_default_strategy_tickets(seed=seed or DEFAULT_TICKET_SEED)
    )
    history_snapshot_digest = _sha256_hex(
        canonical_json_bytes(
            {
                "mode": "DRY_RUN_ONLY",
                "target_draw_label": target_draw_label,
                "history_cutoff_label": history_cutoff_label,
                "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
            }
        )
    )
    source_identity_digest = _sha256_hex(
        canonical_json_bytes(canonical_source_digests)
    )
    strategy_identity_digest = _sha256_hex(
        canonical_json_bytes(list(BIG649_FROZEN_STRATEGY_IDS))
    )
    ticket_validation_result = {
        "status": "PASS",
        "ticket_count": len(canonical_strategy_tickets),
        "tickets": [record["canonical_sorted_ticket"] for record in canonical_strategy_tickets],
        "ticket_sha256_values": [record["ticket_sha256"] for record in canonical_strategy_tickets],
        "collision_count": sum(
            1 for record in canonical_strategy_tickets if record["duplicate_ticket_relationship"]["collision"]
        ),
    }
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": "DRY_RUN_ONLY",
        "publication_status": PUBLICATION_STATUS_NOT_PUBLISHED,
        "dry_run_warning": DRY_RUN_WARNING,
        "game": {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE},
        "target_draw_label": target_draw_label,
        "history_cutoff_label": history_cutoff_label,
        "origin_main_sha": origin_sha,
        "protocol_source_sha256": protocol_sha,
        "history_snapshot_digest": history_snapshot_digest,
        "source_identity_digest": source_identity_digest,
        "strategy_identity_digest": strategy_identity_digest,
        "real_target_selected": False,
        "real_ticket_published": False,
        "official_deadline_lookup": False,
        "future_evaluation_started": False,
        "zero_db_guard": True,
        "no_github_publication_side_effect": True,
        "strategy_count": len(BIG649_FROZEN_STRATEGY_IDS),
        "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
        "primary_budget_n": PRIMARY_BUDGET,
        "bet_index": BET_INDEX,
        "endpoint_id": ENDPOINT_ID,
        "strategy_source_digests": canonical_source_digests,
        "strategy_tickets": canonical_strategy_tickets,
        "ticket_validation_result": ticket_validation_result,
        "duplicate_check_result": check_duplicate_manifest(previous_manifest, {
            "schema_version": SCHEMA_VERSION,
            "mode": "DRY_RUN_ONLY",
            "publication_status": PUBLICATION_STATUS_NOT_PUBLISHED,
            "dry_run_warning": DRY_RUN_WARNING,
            "game": {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE},
            "target_draw_label": target_draw_label,
            "history_cutoff_label": history_cutoff_label,
            "origin_main_sha": origin_sha,
            "protocol_source_sha256": protocol_sha,
            "history_snapshot_digest": history_snapshot_digest,
            "source_identity_digest": source_identity_digest,
            "strategy_identity_digest": strategy_identity_digest,
            "real_target_selected": False,
            "real_ticket_published": False,
            "official_deadline_lookup": False,
            "future_evaluation_started": False,
            "zero_db_guard": True,
            "no_github_publication_side_effect": True,
            "strategy_count": len(BIG649_FROZEN_STRATEGY_IDS),
            "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
            "primary_budget_n": PRIMARY_BUDGET,
            "bet_index": BET_INDEX,
            "endpoint_id": ENDPOINT_ID,
            "strategy_source_digests": canonical_source_digests,
            "strategy_tickets": canonical_strategy_tickets,
            "ticket_validation_result": ticket_validation_result,
            "duplicate_check_result": {"status": NO_EXISTING_MANIFEST},
            "idempotency_check_result": {"status": IDEMPOTENCY_PASS},
            "randomness_policy_result": classify_randomness(
                strategy_kind="deterministic",
                randomness_policy=randomness_policy,
                seed=seed,
            ),
            "stop_conditions": [
                "real target selected",
                "official deadline lookup",
                "real ticket published",
                "future evaluation started",
                "database opened or queried",
                "publication side effect",
            ],
            "publication_guard_state": DRY_RUN_ONLY_NOT_PUBLISHED,
        }) if previous_manifest is not None else {"status": NO_EXISTING_MANIFEST},
        "idempotency_check_result": check_idempotency(
            {
                "schema_version": SCHEMA_VERSION,
                "mode": "DRY_RUN_ONLY",
                "publication_status": PUBLICATION_STATUS_NOT_PUBLISHED,
                "dry_run_warning": DRY_RUN_WARNING,
                "game": {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE},
                "target_draw_label": target_draw_label,
                "history_cutoff_label": history_cutoff_label,
                "origin_main_sha": origin_sha,
                "protocol_source_sha256": protocol_sha,
                "history_snapshot_digest": history_snapshot_digest,
                "source_identity_digest": source_identity_digest,
                "strategy_identity_digest": strategy_identity_digest,
                "real_target_selected": False,
                "real_ticket_published": False,
                "official_deadline_lookup": False,
                "future_evaluation_started": False,
                "zero_db_guard": True,
                "no_github_publication_side_effect": True,
                "strategy_count": len(BIG649_FROZEN_STRATEGY_IDS),
                "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
                "primary_budget_n": PRIMARY_BUDGET,
                "bet_index": BET_INDEX,
                "endpoint_id": ENDPOINT_ID,
                "strategy_source_digests": canonical_source_digests,
                "strategy_tickets": canonical_strategy_tickets,
                "ticket_validation_result": ticket_validation_result,
                "duplicate_check_result": {"status": NO_EXISTING_MANIFEST},
                "idempotency_check_result": {"status": IDEMPOTENCY_PASS},
                "randomness_policy_result": classify_randomness(
                    strategy_kind="deterministic",
                    randomness_policy=randomness_policy,
                    seed=seed,
                ),
                "stop_conditions": [
                    "real target selected",
                    "official deadline lookup",
                    "real ticket published",
                    "future evaluation started",
                    "database opened or queried",
                    "publication side effect",
                ],
                "publication_guard_state": DRY_RUN_ONLY_NOT_PUBLISHED,
            },
            {
                "schema_version": SCHEMA_VERSION,
                "mode": "DRY_RUN_ONLY",
                "publication_status": PUBLICATION_STATUS_NOT_PUBLISHED,
                "dry_run_warning": DRY_RUN_WARNING,
                "game": {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE},
                "target_draw_label": target_draw_label,
                "history_cutoff_label": history_cutoff_label,
                "origin_main_sha": origin_sha,
                "protocol_source_sha256": protocol_sha,
                "history_snapshot_digest": history_snapshot_digest,
                "source_identity_digest": source_identity_digest,
                "strategy_identity_digest": strategy_identity_digest,
                "real_target_selected": False,
                "real_ticket_published": False,
                "official_deadline_lookup": False,
                "future_evaluation_started": False,
                "zero_db_guard": True,
                "no_github_publication_side_effect": True,
                "strategy_count": len(BIG649_FROZEN_STRATEGY_IDS),
                "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
                "primary_budget_n": PRIMARY_BUDGET,
                "bet_index": BET_INDEX,
                "endpoint_id": ENDPOINT_ID,
                "strategy_source_digests": canonical_source_digests,
                "strategy_tickets": canonical_strategy_tickets,
                "ticket_validation_result": ticket_validation_result,
                "duplicate_check_result": {"status": NO_EXISTING_MANIFEST},
                "idempotency_check_result": {"status": IDEMPOTENCY_PASS},
                "randomness_policy_result": classify_randomness(
                    strategy_kind="deterministic",
                    randomness_policy=randomness_policy,
                    seed=seed,
                ),
                "stop_conditions": [
                    "real target selected",
                    "official deadline lookup",
                    "real ticket published",
                    "future evaluation started",
                    "database opened or queried",
                    "publication side effect",
                ],
                "publication_guard_state": DRY_RUN_ONLY_NOT_PUBLISHED,
            },
            strategy_kind="deterministic",
            randomness_policy=randomness_policy,
            seed=seed,
        ),
        "randomness_policy_result": classify_randomness(
            strategy_kind="deterministic",
            randomness_policy=randomness_policy,
            seed=seed,
        ),
        "stop_conditions": [
            "real target selected",
            "official deadline lookup",
            "real ticket published",
            "future evaluation started",
            "database opened or queried",
            "publication side effect",
        ],
        "publication_guard_state": DRY_RUN_ONLY_NOT_PUBLISHED,
    }
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    return validate_manifest(manifest)


def _build_manifest_body(
    *,
    origin_sha: str,
    target_draw_label: str,
    history_cutoff_label: str,
    protocol_sha: str,
    canonical_source_digests: Mapping[str, Mapping[str, str]],
    canonical_strategy_tickets: Sequence[Mapping[str, Any]],
    randomness_policy: Mapping[str, Any] | None,
    seed: str | None,
    strategy_kind: str,
) -> dict[str, Any]:
    history_snapshot_digest = _sha256_hex(
        canonical_json_bytes(
            {
                "mode": "DRY_RUN_ONLY",
                "target_draw_label": target_draw_label,
                "history_cutoff_label": history_cutoff_label,
                "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
            }
        )
    )
    source_identity_digest = _sha256_hex(canonical_json_bytes(canonical_source_digests))
    strategy_identity_digest = _sha256_hex(canonical_json_bytes(list(BIG649_FROZEN_STRATEGY_IDS)))
    ticket_validation_result = {
        "status": "PASS",
        "ticket_count": len(canonical_strategy_tickets),
        "tickets": [record["canonical_sorted_ticket"] for record in canonical_strategy_tickets],
        "ticket_sha256_values": [record["ticket_sha256"] for record in canonical_strategy_tickets],
        "collision_count": sum(
            1
            for record in canonical_strategy_tickets
            if record["duplicate_ticket_relationship"]["collision"]
        ),
    }
    stop_conditions = [
        "real target selected",
        "official deadline lookup",
        "real ticket published",
        "future evaluation started",
        "database opened or queried",
        "publication side effect",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "DRY_RUN_ONLY",
        "publication_status": PUBLICATION_STATUS_NOT_PUBLISHED,
        "dry_run_warning": DRY_RUN_WARNING,
        "game": {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE},
        "target_draw_label": target_draw_label,
        "history_cutoff_label": history_cutoff_label,
        "origin_main_sha": origin_sha,
        "protocol_source_sha256": protocol_sha,
        "history_snapshot_digest": history_snapshot_digest,
        "source_identity_digest": source_identity_digest,
        "strategy_identity_digest": strategy_identity_digest,
        "real_target_selected": False,
        "real_ticket_published": False,
        "official_deadline_lookup": False,
        "future_evaluation_started": False,
        "zero_db_guard": True,
        "no_github_publication_side_effect": True,
        "strategy_count": len(BIG649_FROZEN_STRATEGY_IDS),
        "strategy_ids": list(BIG649_FROZEN_STRATEGY_IDS),
        "primary_budget_n": PRIMARY_BUDGET,
        "bet_index": BET_INDEX,
        "endpoint_id": ENDPOINT_ID,
        "strategy_source_digests": dict(canonical_source_digests),
        "strategy_tickets": [dict(record) for record in canonical_strategy_tickets],
        "ticket_validation_result": ticket_validation_result,
        "duplicate_check_result": {"status": NO_EXISTING_MANIFEST},
        "idempotency_check_result": {"status": NO_EXISTING_MANIFEST},
        "randomness_policy_result": classify_randomness(
            strategy_kind=strategy_kind,
            randomness_policy=randomness_policy,
            seed=seed,
        ),
        "stop_conditions": stop_conditions,
        "publication_guard_state": DRY_RUN_ONLY_NOT_PUBLISHED,
    }


def build_dry_run_manifest(
    *,
    origin_main_sha: str,
    target_draw_label: str = DRY_RUN_TARGET_LABEL,
    history_cutoff_label: str = DRY_RUN_CUTOFF_LABEL,
    local_generated_at: str = DEFAULT_LOCAL_GENERATED_AT,
    strategy_tickets: Sequence[Mapping[str, Any]] | None = None,
    strategy_source_digests: Mapping[str, Mapping[str, str]] | None = None,
    previous_manifest: Mapping[str, Any] | None = None,
    randomness_policy: Mapping[str, Any] | None = None,
    seed: str | None = None,
    strategy_kind: str = "deterministic",
    protocol_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic dry-run manifest with zero publication side effects."""
    _ = local_generated_at
    origin_sha = _require_hex_or_label(origin_main_sha, HEX_40, "origin_main_sha")
    protocol_sha = (
        _require_hex_or_label(protocol_source_sha256, HEX_64, "protocol_source_sha256")
        if protocol_source_sha256 is not None
        else _sha256_hex(Path(__file__).read_bytes())
    )
    canonical_source_digests = _canonical_source_digests(
        strategy_source_digests or build_default_source_digests(seed=DEFAULT_SOURCE_SEED)
    )
    canonical_strategy_tickets = _canonical_strategy_tickets(
        strategy_tickets or build_default_strategy_tickets(seed=seed or DEFAULT_TICKET_SEED)
    )
    manifest = _build_manifest_body(
        origin_sha=origin_sha,
        target_draw_label=target_draw_label,
        history_cutoff_label=history_cutoff_label,
        protocol_sha=protocol_sha,
        canonical_source_digests=canonical_source_digests,
        canonical_strategy_tickets=canonical_strategy_tickets,
        randomness_policy=randomness_policy,
        seed=seed,
        strategy_kind=strategy_kind,
    )

    if previous_manifest is None:
        manifest["duplicate_check_result"] = {"status": NO_EXISTING_MANIFEST}
        manifest["idempotency_check_result"] = {"status": NO_EXISTING_MANIFEST}
    else:
        manifest["duplicate_check_result"] = check_duplicate_manifest(previous_manifest, manifest)
        manifest["idempotency_check_result"] = check_idempotency(
            previous_manifest,
            manifest,
            strategy_kind=strategy_kind,
            randomness_policy=randomness_policy,
            seed=seed,
        )

    manifest["manifest_sha256"] = manifest_sha256(manifest)
    return validate_manifest(manifest)


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate a dry-run manifest and return a normalized deep copy."""
    if not isinstance(manifest, Mapping) or set(manifest) != MANIFEST_FIELDS:
        raise ProtocolValidationError("manifest top-level fields do not match schema")

    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ProtocolValidationError("schema_version mismatch")
    if manifest["mode"] != "DRY_RUN_ONLY":
        raise ProtocolValidationError("mode must remain DRY_RUN_ONLY")
    if manifest["publication_status"] != PUBLICATION_STATUS_NOT_PUBLISHED:
        raise ProtocolValidationError("publication_status must remain NOT_PUBLISHED")
    if manifest["dry_run_warning"] != DRY_RUN_WARNING:
        raise ProtocolValidationError("dry_run_warning mismatch")
    if manifest["game"] != {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE}:
        raise ProtocolValidationError("game contract mismatch")
    if not isinstance(manifest["target_draw_label"], str) or not manifest["target_draw_label"].startswith("DRY_RUN_"):
        raise ProtocolValidationError("target_draw_label must be a synthetic DRY_RUN label")
    if not isinstance(manifest["history_cutoff_label"], str) or not manifest["history_cutoff_label"].startswith("DRY_RUN_"):
        raise ProtocolValidationError("history_cutoff_label must be a synthetic DRY_RUN label")
    _require_hex_or_label(manifest["origin_main_sha"], HEX_40, "origin_main_sha")
    _require_hex_or_label(manifest["protocol_source_sha256"], HEX_64, "protocol_source_sha256")
    _require_hex_or_label(manifest["history_snapshot_digest"], HEX_64, "history_snapshot_digest")
    _require_hex_or_label(manifest["source_identity_digest"], HEX_64, "source_identity_digest")
    _require_hex_or_label(manifest["strategy_identity_digest"], HEX_64, "strategy_identity_digest")
    if manifest["real_target_selected"] is not False:
        raise ProtocolValidationError("real_target_selected must be false")
    if manifest["real_ticket_published"] is not False:
        raise ProtocolValidationError("real_ticket_published must be false")
    if manifest["official_deadline_lookup"] is not False:
        raise ProtocolValidationError("official_deadline_lookup must be false")
    if manifest["future_evaluation_started"] is not False:
        raise ProtocolValidationError("future_evaluation_started must be false")
    if manifest["zero_db_guard"] is not True:
        raise ProtocolValidationError("zero_db_guard must be true")
    if manifest["no_github_publication_side_effect"] is not True:
        raise ProtocolValidationError("no_github_publication_side_effect must be true")
    if manifest["strategy_count"] != len(BIG649_FROZEN_STRATEGY_IDS):
        raise ProtocolValidationError("strategy_count must be 11")
    if manifest["strategy_ids"] != list(BIG649_FROZEN_STRATEGY_IDS):
        raise ProtocolValidationError("strategy_ids must be the exact frozen lexical order")
    if manifest["primary_budget_n"] != PRIMARY_BUDGET:
        raise ProtocolValidationError("primary_budget_n must be 1")
    if manifest["bet_index"] != BET_INDEX:
        raise ProtocolValidationError("bet_index must be 1")
    if manifest["endpoint_id"] != ENDPOINT_ID:
        raise ProtocolValidationError("endpoint_id mismatch")
    if manifest["publication_guard_state"] != DRY_RUN_ONLY_NOT_PUBLISHED:
        raise ProtocolValidationError("publication_guard_state mismatch")

    _canonical_source_digests(manifest["strategy_source_digests"])
    strategies = manifest["strategy_tickets"]
    if not isinstance(strategies, list) or len(strategies) != len(BIG649_FROZEN_STRATEGY_IDS):
        raise ProtocolValidationError("strategy_tickets must contain exactly 11 strategy records")
    if [record.get("strategy_id") for record in strategies] != list(BIG649_FROZEN_STRATEGY_IDS):
        raise ProtocolValidationError("strategy tickets must be exact lexical frozen order")

    for record in strategies:
        if not isinstance(record, Mapping) or set(record) != {
            "strategy_id",
            "bet_index",
            "predicted_main_numbers",
            "canonical_sorted_ticket",
            "ticket_sha256",
            "duplicate_ticket_relationship",
        }:
            raise ProtocolValidationError("strategy ticket record fields do not match schema")
        canonical = validate_ticket(record["predicted_main_numbers"])
        if record["canonical_sorted_ticket"] != canonical:
            raise ProtocolValidationError("canonical_sorted_ticket mismatch")
        if record["ticket_sha256"] != ticket_sha256(canonical):
            raise ProtocolValidationError("ticket_sha256 mismatch")

    ticket_validation_result = manifest["ticket_validation_result"]
    if not isinstance(ticket_validation_result, Mapping) or ticket_validation_result.get("status") != "PASS":
        raise ProtocolValidationError("ticket_validation_result must be PASS")
    if ticket_validation_result.get("ticket_count") != len(BIG649_FROZEN_STRATEGY_IDS):
        raise ProtocolValidationError("ticket_validation_result count mismatch")

    duplicate_result = manifest["duplicate_check_result"]
    idempotency_result = manifest["idempotency_check_result"]
    randomness_result = manifest["randomness_policy_result"]
    if not isinstance(duplicate_result, Mapping) or "status" not in duplicate_result:
        raise ProtocolValidationError("duplicate_check_result must be an object with status")
    if not isinstance(idempotency_result, Mapping) or "status" not in idempotency_result:
        raise ProtocolValidationError("idempotency_check_result must be an object with status")
    if not isinstance(randomness_result, Mapping) or "status" not in randomness_result:
        raise ProtocolValidationError("randomness_policy_result must be an object with status")
    if duplicate_result["status"] not in {
        NO_EXISTING_MANIFEST,
        ALREADY_PUBLISHED_SAME_MANIFEST,
        DUPLICATE_PUBLICATION_CONFLICT,
    }:
        raise ProtocolValidationError("duplicate_check_result status mismatch")
    if idempotency_result["status"] not in {
        NO_EXISTING_MANIFEST,
        IDEMPOTENCY_PASS,
        IDEMPOTENCY_FAIL_UNEXPLAINED,
        RANDOMNESS_ALLOWED_WITH_SEED,
        RANDOMNESS_POLICY_MISSING,
        STOP_UNEXPLAINED_NONDETERMINISM,
    }:
        raise ProtocolValidationError("idempotency_check_result status mismatch")
    if randomness_result["status"] not in {
        RANDOMNESS_NOT_APPLICABLE,
        RANDOMNESS_ALLOWED_WITH_SEED,
        RANDOMNESS_POLICY_MISSING,
    }:
        raise ProtocolValidationError("randomness_policy_result status mismatch")

    actual_digest = _require_hex_or_label(
        manifest["manifest_sha256"], HEX_64, "manifest_sha256"
    )
    if actual_digest != manifest_sha256(manifest):
        raise ProtocolValidationError("manifest_sha256 mismatch; manifest mutated")

    return copy.deepcopy(dict(manifest))
