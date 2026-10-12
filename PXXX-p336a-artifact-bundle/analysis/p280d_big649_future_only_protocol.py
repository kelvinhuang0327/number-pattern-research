"""P280D BIG 6/49 future-only freeze and immutable-publication protocol.

This module is deliberately local-only and import-safe. It builds and validates
an unpublished prediction manifest from explicit inputs. It does not read a DB,
discover a target draw, fetch a deadline, publish, select a strategy, or write a
file. GitHub publication is a separately authorized human-controlled procedure.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ProtocolValidationError(ValueError):
    """Raised when a freeze or manifest contract fails closed."""


FREEZE_ID = "P280D_BIG649_FUTURE_ONLY_FREEZE_20260618"
FREEZE_STATUS = "PROTOCOL_FROZEN_NOT_ACTIVATED"
MANIFEST_SCHEMA_VERSION = "p280d_big649_prediction_manifest_v1"
FREEZE_SCHEMA_VERSION = "p280d_big649_future_only_freeze_v1"
GAME = "BIG"
GAME_LABEL = "大樂透"
GAME_RULE = "6-49"
TICKET_SIZE = 6
NUMBER_MIN = 1
NUMBER_MAX = 49
PRIMARY_BUDGET = 1
BET_INDEX = 1
ENDPOINT_ID = "BIG_ANY_PRIZE_AWARE_WIN"
ENDPOINT_SEMANTICS = (
    "hit_count >= 3 OR (hit_count == 2 AND special_hit == true); "
    "hit_count uses the six actual main numbers; special_hit means the actual "
    "special number is present in the predicted six main numbers; no special "
    "number is predicted"
)
PUBLICATION_STATUS = "UNPUBLISHED_LOCAL_DRAFT"
SELECTION_BASIS = "FROZEN_ALL_11_BET_INDEX_1_NO_OUTCOME_SELECTION"

STRATEGY_IDS = (
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

_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_OUTCOME_KEY_TOKENS = {
    "actual",
    "hit",
    "hits",
    "outcome",
    "outcomes",
    "prize",
    "prizes",
    "win",
    "winner",
    "winning",
    "wins",
}
_TICKET_INPUT_FIELDS = {"strategy_id", "bet_index", "predicted_main_numbers"}
_SOURCE_FIELDS = {"source_path", "git_blob_sha1", "sha256", "generator_identity"}
_STRATEGY_MANIFEST_FIELDS = {
    "strategy_id",
    "bet_index",
    "predicted_main_numbers",
    "canonical_sorted_ticket",
    "ticket_sha256",
    "duplicate_ticket_relationship",
}
_MANIFEST_FIELDS = {
    "manifest_schema_version",
    "freeze_id",
    "game",
    "target_draw",
    "target_draw_deadline_at",
    "deadline_timezone",
    "local_generated_at",
    "history_cutoff_draw",
    "history_snapshot_digest",
    "origin_main_sha",
    "protocol_source_sha256",
    "strategy_source_digests",
    "selection_basis",
    "strategies",
    "previous_manifest_sha256",
    "manifest_sha256",
    "publication_status",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON using sorted keys, compact separators, and LF."""
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolValidationError(f"value is not canonical JSON: {exc}") from exc
    return (rendered + "\n").encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_payload_sha256(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    payload = {key: copy.deepcopy(value) for key, value in manifest.items()
               if key != "manifest_sha256"}
    return canonical_payload_sha256(payload)


def _require_hex(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ProtocolValidationError(f"{label} must be lowercase hexadecimal")
    return value


def _forbidden_outcome_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            tokens = {token for token in re.split(r"[^a-z0-9]+", key_text.lower()) if token}
            if tokens & _OUTCOME_KEY_TOKENS:
                found.append(f"{path}.{key_text}")
            found.extend(_forbidden_outcome_keys(child, f"{path}.{key_text}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_forbidden_outcome_keys(child, f"{path}[{index}]"))
    return found


def _reject_outcome_keys(value: Any, label: str) -> None:
    found = _forbidden_outcome_keys(value)
    if found:
        raise ProtocolValidationError(
            f"{label} contains forbidden target-outcome field(s): {', '.join(found)}"
        )


def _parse_aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ProtocolValidationError(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolValidationError(f"{label} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProtocolValidationError(f"{label} must include a UTC offset")
    return parsed


def _canonical_datetime(value: Any, label: str) -> str:
    return _parse_aware_datetime(value, label).isoformat()


def _validate_deadline_timezone(deadline: datetime, timezone_name: Any) -> str:
    if not isinstance(timezone_name, str) or not timezone_name:
        raise ProtocolValidationError("deadline_timezone must be a non-empty IANA name")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ProtocolValidationError("deadline_timezone is not an installed IANA zone") from exc
    if deadline.utcoffset() != deadline.astimezone(zone).utcoffset():
        raise ProtocolValidationError(
            "target_draw_deadline_at offset does not match deadline_timezone"
        )
    return timezone_name


def _canonical_ticket(numbers: Any, label: str) -> list[int]:
    if not isinstance(numbers, (list, tuple)) or len(numbers) != TICKET_SIZE:
        raise ProtocolValidationError(f"{label} must contain exactly six numbers")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in numbers):
        raise ProtocolValidationError(f"{label} must contain integers only")
    if len(set(numbers)) != TICKET_SIZE:
        raise ProtocolValidationError(f"{label} must contain six unique numbers")
    if any(number < NUMBER_MIN or number > NUMBER_MAX for number in numbers):
        raise ProtocolValidationError(f"{label} number outside 1..49")
    return sorted(numbers)


def ticket_sha256(ticket: Sequence[int]) -> str:
    canonical = _canonical_ticket(ticket, "ticket")
    return canonical_payload_sha256({"game": GAME, "main_numbers": canonical})


def _canonical_history(history: Any, target_draw: int, history_cutoff_draw: int) -> list[dict]:
    if not isinstance(history, (list, tuple)) or not history:
        raise ProtocolValidationError("history must be a non-empty sequence")
    _reject_outcome_keys(history, "history")
    rows: list[dict] = []
    seen_draws: set[int] = set()
    for index, row in enumerate(history):
        if not isinstance(row, Mapping) or set(row) != {"draw", "numbers"}:
            raise ProtocolValidationError(
                f"history[{index}] must contain only draw and numbers"
            )
        draw = row["draw"]
        if isinstance(draw, bool) or not isinstance(draw, int) or draw <= 0:
            raise ProtocolValidationError(f"history[{index}].draw must be a positive integer")
        if draw in seen_draws:
            raise ProtocolValidationError("history contains duplicate draw identity")
        if draw >= target_draw:
            raise ProtocolValidationError("history contains target or future draw")
        if draw > history_cutoff_draw:
            raise ProtocolValidationError("history contains a row after history_cutoff_draw")
        seen_draws.add(draw)
        rows.append({"draw": draw, "numbers": _canonical_ticket(
            row["numbers"], f"history[{index}].numbers"
        )})
    rows.sort(key=lambda row: row["draw"])
    if rows[-1]["draw"] != history_cutoff_draw:
        raise ProtocolValidationError(
            "history_cutoff_draw must equal the latest explicit history draw"
        )
    return rows


def history_snapshot_digest(history: Any, target_draw: int, history_cutoff_draw: int) -> str:
    rows = _canonical_history(history, target_draw, history_cutoff_draw)
    return canonical_payload_sha256({"game": GAME, "history": rows})


def _canonical_source_digests(source_digests: Any) -> dict[str, dict[str, str]]:
    if not isinstance(source_digests, Mapping) or set(source_digests) != set(STRATEGY_IDS):
        raise ProtocolValidationError("strategy_source_digests must cover exact frozen 11 IDs")
    canonical: dict[str, dict[str, str]] = {}
    for strategy_id in STRATEGY_IDS:
        record = source_digests[strategy_id]
        if not isinstance(record, Mapping) or set(record) != _SOURCE_FIELDS:
            raise ProtocolValidationError(f"invalid source record for {strategy_id}")
        source_path = record["source_path"]
        generator_identity = record["generator_identity"]
        if not isinstance(source_path, str) or not source_path or source_path.startswith("/"):
            raise ProtocolValidationError(f"invalid source_path for {strategy_id}")
        if not isinstance(generator_identity, str) or not generator_identity:
            raise ProtocolValidationError(f"missing generator_identity for {strategy_id}")
        canonical[strategy_id] = {
            "source_path": source_path,
            "git_blob_sha1": _require_hex(
                record["git_blob_sha1"], _HEX_40, f"{strategy_id}.git_blob_sha1"
            ),
            "sha256": _require_hex(
                record["sha256"], _HEX_64, f"{strategy_id}.sha256"
            ),
            "generator_identity": generator_identity,
        }
    return canonical


def _canonical_strategy_inputs(strategy_tickets: Any) -> list[dict]:
    if not isinstance(strategy_tickets, (list, tuple)):
        raise ProtocolValidationError("strategy_tickets must be a sequence")
    _reject_outcome_keys(strategy_tickets, "strategy_tickets")
    records: dict[str, dict] = {}
    for index, record in enumerate(strategy_tickets):
        if not isinstance(record, Mapping) or set(record) != _TICKET_INPUT_FIELDS:
            raise ProtocolValidationError(f"strategy_tickets[{index}] has invalid fields")
        strategy_id = record["strategy_id"]
        if not isinstance(strategy_id, str):
            raise ProtocolValidationError("strategy_id must be a string")
        if strategy_id in records:
            raise ProtocolValidationError(f"duplicate strategy ID: {strategy_id}")
        if record["bet_index"] != BET_INDEX or isinstance(record["bet_index"], bool):
            raise ProtocolValidationError(f"{strategy_id} must use exactly bet_index=1")
        canonical = _canonical_ticket(
            record["predicted_main_numbers"], f"{strategy_id}.predicted_main_numbers"
        )
        records[strategy_id] = {
            "strategy_id": strategy_id,
            "bet_index": BET_INDEX,
            "predicted_main_numbers": canonical,
            "canonical_sorted_ticket": canonical,
            "ticket_sha256": ticket_sha256(canonical),
        }
    if set(records) != set(STRATEGY_IDS):
        missing = sorted(set(STRATEGY_IDS) - set(records))
        extra = sorted(set(records) - set(STRATEGY_IDS))
        raise ProtocolValidationError(
            f"strategy set must be exact frozen 11; missing={missing}; extra={extra}"
        )
    by_ticket: dict[str, list[str]] = {}
    for strategy_id, record in records.items():
        by_ticket.setdefault(record["ticket_sha256"], []).append(strategy_id)
    output: list[dict] = []
    for strategy_id in STRATEGY_IDS:
        record = records[strategy_id]
        peers = sorted(peer for peer in by_ticket[record["ticket_sha256"]]
                       if peer != strategy_id)
        record["duplicate_ticket_relationship"] = {
            "collision": bool(peers),
            "other_strategy_ids": peers,
        }
        output.append(record)
    return output


def build_prediction_manifest(
    *,
    target_draw: int,
    target_draw_deadline_at: str,
    deadline_timezone: str,
    local_generated_at: str,
    history_cutoff_draw: int,
    history: Sequence[Mapping[str, Any]],
    strategy_tickets: Sequence[Mapping[str, Any]],
    origin_main_sha: str,
    protocol_source_sha256: str,
    strategy_source_digests: Mapping[str, Mapping[str, str]],
    previous_manifest_sha256: str | None = None,
    freeze_id: str = FREEZE_ID,
    target_outcome: Any = None,
    outcome_based_ticket_selection: bool = False,
) -> dict:
    """Build one deterministic unpublished manifest or reject the input."""
    if freeze_id != FREEZE_ID:
        raise ProtocolValidationError("freeze_id does not match the frozen protocol")
    if isinstance(target_draw, bool) or not isinstance(target_draw, int) or target_draw <= 0:
        raise ProtocolValidationError("target_draw must be a positive integer")
    if (isinstance(history_cutoff_draw, bool)
            or not isinstance(history_cutoff_draw, int)
            or history_cutoff_draw <= 0):
        raise ProtocolValidationError("history_cutoff_draw must be a positive integer")
    if target_draw <= history_cutoff_draw:
        raise ProtocolValidationError("target_draw must be strictly after history_cutoff_draw")
    if target_outcome is not None:
        raise ProtocolValidationError("target outcome must not be present")
    if outcome_based_ticket_selection:
        raise ProtocolValidationError("outcome-based ticket selection is prohibited")

    origin_sha = _require_hex(origin_main_sha, _HEX_40, "origin_main_sha")
    protocol_sha = _require_hex(
        protocol_source_sha256, _HEX_64, "protocol_source_sha256"
    )
    previous = None
    if previous_manifest_sha256 is not None:
        previous = _require_hex(
            previous_manifest_sha256, _HEX_64, "previous_manifest_sha256"
        )
    deadline = _parse_aware_datetime(
        target_draw_deadline_at, "target_draw_deadline_at"
    )
    generated = _parse_aware_datetime(local_generated_at, "local_generated_at")
    _validate_deadline_timezone(deadline, deadline_timezone)
    if generated >= deadline:
        raise ProtocolValidationError("local_generated_at must be strictly before deadline")

    canonical_history = _canonical_history(history, target_draw, history_cutoff_draw)
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "freeze_id": FREEZE_ID,
        "game": GAME,
        "target_draw": target_draw,
        "target_draw_deadline_at": deadline.isoformat(),
        "deadline_timezone": deadline_timezone,
        "local_generated_at": generated.isoformat(),
        "history_cutoff_draw": history_cutoff_draw,
        "history_snapshot_digest": canonical_payload_sha256(
            {"game": GAME, "history": canonical_history}
        ),
        "origin_main_sha": origin_sha,
        "protocol_source_sha256": protocol_sha,
        "strategy_source_digests": _canonical_source_digests(strategy_source_digests),
        "selection_basis": SELECTION_BASIS,
        "strategies": _canonical_strategy_inputs(strategy_tickets),
        "previous_manifest_sha256": previous,
        "publication_status": PUBLICATION_STATUS,
    }
    manifest["manifest_sha256"] = _manifest_digest(manifest)
    validate_prediction_manifest(manifest)
    return manifest


def validate_prediction_manifest(manifest: Any) -> None:
    """Validate structure, frozen identities, guards, and the self hash."""
    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_FIELDS:
        raise ProtocolValidationError("manifest top-level fields do not match schema")
    _reject_outcome_keys(manifest, "manifest")
    if manifest["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ProtocolValidationError("manifest_schema_version mismatch")
    if manifest["freeze_id"] != FREEZE_ID:
        raise ProtocolValidationError("freeze_id mismatch")
    if manifest["game"] != GAME:
        raise ProtocolValidationError("game mismatch")
    if manifest["publication_status"] != PUBLICATION_STATUS:
        raise ProtocolValidationError("publication_status must remain unpublished local draft")
    if manifest["selection_basis"] != SELECTION_BASIS:
        raise ProtocolValidationError("selection basis is not frozen")
    target_draw = manifest["target_draw"]
    cutoff = manifest["history_cutoff_draw"]
    if (isinstance(target_draw, bool) or not isinstance(target_draw, int)
            or isinstance(cutoff, bool) or not isinstance(cutoff, int)
            or target_draw <= cutoff):
        raise ProtocolValidationError("target draw/cutoff ordering is invalid")
    deadline = _parse_aware_datetime(
        manifest["target_draw_deadline_at"], "target_draw_deadline_at"
    )
    generated = _parse_aware_datetime(manifest["local_generated_at"], "local_generated_at")
    _validate_deadline_timezone(deadline, manifest["deadline_timezone"])
    if generated >= deadline:
        raise ProtocolValidationError("manifest was locally generated at/after deadline")
    _require_hex(manifest["origin_main_sha"], _HEX_40, "origin_main_sha")
    _require_hex(
        manifest["protocol_source_sha256"], _HEX_64, "protocol_source_sha256"
    )
    _require_hex(
        manifest["history_snapshot_digest"], _HEX_64, "history_snapshot_digest"
    )
    _canonical_source_digests(manifest["strategy_source_digests"])
    if manifest["previous_manifest_sha256"] is not None:
        _require_hex(
            manifest["previous_manifest_sha256"], _HEX_64,
            "previous_manifest_sha256",
        )

    strategies = manifest["strategies"]
    if not isinstance(strategies, list) or len(strategies) != len(STRATEGY_IDS):
        raise ProtocolValidationError("manifest must contain exactly 11 strategy records")
    if [record.get("strategy_id") for record in strategies] != list(STRATEGY_IDS):
        raise ProtocolValidationError("strategy records must be exact lexical frozen order")
    hashes: dict[str, list[str]] = {}
    for record in strategies:
        if not isinstance(record, Mapping) or set(record) != _STRATEGY_MANIFEST_FIELDS:
            raise ProtocolValidationError("strategy record fields do not match schema")
        strategy_id = record["strategy_id"]
        if record["bet_index"] != BET_INDEX or isinstance(record["bet_index"], bool):
            raise ProtocolValidationError(f"{strategy_id} bet_index mismatch")
        canonical = _canonical_ticket(
            record["predicted_main_numbers"], f"{strategy_id}.predicted_main_numbers"
        )
        if record["predicted_main_numbers"] != canonical:
            raise ProtocolValidationError(f"{strategy_id} predicted ticket is not sorted")
        if record["canonical_sorted_ticket"] != canonical:
            raise ProtocolValidationError(f"{strategy_id} canonical ticket mismatch")
        expected_ticket_hash = ticket_sha256(canonical)
        if record["ticket_sha256"] != expected_ticket_hash:
            raise ProtocolValidationError(f"{strategy_id} ticket_sha256 mismatch")
        hashes.setdefault(expected_ticket_hash, []).append(strategy_id)
    for record in strategies:
        relation = record["duplicate_ticket_relationship"]
        peers = sorted(
            strategy_id for strategy_id in hashes[record["ticket_sha256"]]
            if strategy_id != record["strategy_id"]
        )
        if relation != {"collision": bool(peers), "other_strategy_ids": peers}:
            raise ProtocolValidationError("duplicate-ticket relationship mismatch")

    actual_digest = _require_hex(
        manifest["manifest_sha256"], _HEX_64, "manifest_sha256"
    )
    if actual_digest != _manifest_digest(manifest):
        raise ProtocolValidationError("manifest_sha256 mismatch; manifest mutated")


def validate_freeze_artifact(artifact: Any) -> None:
    """Validate the immutable P280D freeze claims needed by the manifest."""
    if not isinstance(artifact, Mapping):
        raise ProtocolValidationError("freeze artifact must be an object")
    required = {
        "schema_version", "freeze_id", "freeze_created_at", "freeze_status",
        "origin_main_sha", "protocol_source_sha256", "game", "strategy_ids",
        "strategies", "research_contract", "selection_policy", "claims",
        "publication_protocol",
    }
    if not required <= set(artifact):
        raise ProtocolValidationError("freeze artifact missing required fields")
    if artifact["schema_version"] != FREEZE_SCHEMA_VERSION:
        raise ProtocolValidationError("freeze schema version mismatch")
    if artifact["freeze_id"] != FREEZE_ID or artifact["freeze_status"] != FREEZE_STATUS:
        raise ProtocolValidationError("freeze identity/status mismatch")
    _parse_aware_datetime(artifact["freeze_created_at"], "freeze_created_at")
    _require_hex(artifact["origin_main_sha"], _HEX_40, "origin_main_sha")
    _require_hex(
        artifact["protocol_source_sha256"], _HEX_64, "protocol_source_sha256"
    )
    if artifact["game"] != {"id": GAME, "label": GAME_LABEL, "rule": GAME_RULE}:
        raise ProtocolValidationError("game contract mismatch")
    if artifact["strategy_ids"] != list(STRATEGY_IDS):
        raise ProtocolValidationError("freeze strategy IDs/order mismatch")
    records = artifact["strategies"]
    if not isinstance(records, list) or len(records) != len(STRATEGY_IDS):
        raise ProtocolValidationError("freeze must contain 11 strategy source records")
    sources = {}
    for expected_id, record in zip(STRATEGY_IDS, records):
        if record.get("strategy_id") != expected_id:
            raise ProtocolValidationError("freeze strategy record order mismatch")
        sources[expected_id] = {key: record.get(key) for key in _SOURCE_FIELDS}
    _canonical_source_digests(sources)
    contract = artifact["research_contract"]
    if contract.get("primary_budget_n") != PRIMARY_BUDGET:
        raise ProtocolValidationError("primary budget is not N=1")
    if contract.get("bet_index") != BET_INDEX:
        raise ProtocolValidationError("bet_index is not 1")
    if contract.get("endpoint_id") != ENDPOINT_ID:
        raise ProtocolValidationError("endpoint mismatch")
    if artifact["selection_policy"] != {
        "freeze_all_11": True,
        "strategy_ranking": "NONE",
        "historical_candidate_selection": "NONE",
        "outcome_based_exclusion": False,
    }:
        raise ProtocolValidationError("selection policy mismatch")
    if artifact["claims"] != {
        "prediction_success_claim": False,
        "strategy_promoted": False,
        "activation_authorized": False,
    }:
        raise ProtocolValidationError("claim/activation flags mismatch")


def synthetic_strategy_tickets(history: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Create deterministic synthetic-only ticket fixtures for rehearsal."""
    if not history:
        raise ProtocolValidationError("synthetic history must not be empty")
    seed_digest = canonical_payload_sha256(history)
    tickets: list[dict] = []
    for strategy_id in STRATEGY_IDS:
        material = hashlib.sha256(f"{seed_digest}:{strategy_id}".encode("ascii")).digest()
        numbers: list[int] = []
        counter = 0
        while len(numbers) < TICKET_SIZE:
            block = hashlib.sha256(material + counter.to_bytes(2, "big")).digest()
            for byte in block:
                number = (byte % NUMBER_MAX) + 1
                if number not in numbers:
                    numbers.append(number)
                    if len(numbers) == TICKET_SIZE:
                        break
            counter += 1
        tickets.append({
            "strategy_id": strategy_id,
            "bet_index": BET_INDEX,
            "predicted_main_numbers": sorted(numbers),
        })
    return tickets
