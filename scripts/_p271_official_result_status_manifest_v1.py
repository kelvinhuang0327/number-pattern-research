"""P271 official MLB result/status evidence capture and immutable manifest builder.

This module is intentionally isolated from shared ingestion clients.  It only knows
the twelve owner-approved MLB game identifiers, uses the public unauthenticated MLB
Stats API game feed, preserves exact response bytes, and regenerates all derived
artifacts offline from the saved evidence.

The current retrieval timestamp and MLB feed metadata are observation metadata;
neither is evidence of the earliest historical availability of a result.  The
manifest therefore fails closed unless an explicit result-availability field is
present in the official record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MANIFEST_CONTRACT_VERSION = "pit-result-status.v1"
MANIFEST_VERSION = "p271-official-result-status.v1"
SOURCE_INDEX_CONTRACT_VERSION = "p271-official-source-index.v1"
OFFICIAL_SOURCE_IDENTIFIER = "MLB_STATSAPI"
SOURCE_NAME = "MLB_STATSAPI_GAME_FEED_LIVE"
ENDPOINT_ACTION_IDENTIFIER = "GET statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"
ENDPOINT_TEMPLATE = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "Betting-pool-P271-official-manifest/1.0"

ALLOWED_STATUSES = frozenset(
    {
        "SCHEDULED",
        "IN_PROGRESS",
        "SUSPENDED",
        "FINAL",
        "POSTPONED",
        "CANCELLED",
        "FORFEIT",
    }
)
ALLOWED_PROVENANCE_STATUSES = frozenset({"COMPLETE", "INCOMPLETE", "CONFLICT"})
ALLOWED_RETRIEVAL_OUTCOMES = frozenset(
    {"SUCCESS", "HTTP_ERROR", "TRANSPORT_ERROR", "VALIDATION_ERROR"}
)
CLASSIFICATIONS = (
    "CERTIFIED",
    "OFFICIAL_STATUS_RECOVERED_AVAILABILITY_BLOCKED",
    "CONFLICT",
    "UNRESOLVED",
)

ALLOWLIST: tuple[dict[str, Any], ...] = (
    {
        "game_id": "mlb_2026_822834",
        "game_pk": 822834,
        "expected_date": "2026-03-30",
        "away_team": "COL",
        "home_team": "TOR",
    },
    {
        "game_id": "mlb_2026_825108",
        "game_pk": 825108,
        "expected_date": "2026-03-30",
        "away_team": "DET",
        "home_team": "ARI",
    },
    {
        "game_id": "mlb_2026_824861",
        "game_pk": 824861,
        "expected_date": "2026-03-31",
        "away_team": "TEX",
        "home_team": "BAL",
    },
    {
        "game_id": "mlb_2026_824053",
        "game_pk": 824053,
        "expected_date": "2026-04-05",
        "away_team": "SEA",
        "home_team": "LAA",
    },
    {
        "game_id": "mlb_2026_824535",
        "game_pk": 824535,
        "expected_date": "2026-04-11",
        "away_team": "LAA",
        "home_team": "CIN",
    },
    {
        "game_id": "mlb_2026_823391",
        "game_pk": 823391,
        "expected_date": "2026-04-30",
        "away_team": "STL",
        "home_team": "PIT",
    },
    {
        "game_id": "mlb_2026_823955",
        "game_pk": 823955,
        "expected_date": "2026-05-09",
        "away_team": "ATL",
        "home_team": "LAD",
    },
    {
        "game_id": "mlb_2026_823709",
        "game_pk": 823709,
        "expected_date": "2026-05-14",
        "away_team": "MIA",
        "home_team": "MIN",
    },
    {
        "game_id": "mlb_2026_823865",
        "game_pk": 823865,
        "expected_date": "2026-05-19",
        "away_team": "ATL",
        "home_team": "MIA",
    },
    {
        "game_id": "mlb_2026_824356",
        "game_pk": 824356,
        "expected_date": "2026-05-19",
        "away_team": "TEX",
        "home_team": "COL",
    },
    {
        "game_id": "mlb_2026_824273",
        "game_pk": 824273,
        "expected_date": "2026-05-20",
        "away_team": "CLE",
        "home_team": "DET",
    },
    {
        "game_id": "mlb_2026_822735",
        "game_pk": 822735,
        "expected_date": "2026-05-20",
        "away_team": "NYM",
        "home_team": "WSH",
    },
)
GAME_BY_ID = {item["game_id"]: item for item in ALLOWLIST}
GAME_BY_PK = {item["game_pk"]: item for item in ALLOWLIST}
ALLOWLISTED_GAME_IDS = tuple(item["game_id"] for item in ALLOWLIST)

# MLB StatsAPI uses ``AZ`` for the Arizona Diamondbacks while the owner-approved
# task allowlist uses the common ``ARI`` label.  This is an identity-validation
# alias only; the manifest preserves the official response abbreviation.
OFFICIAL_TEAM_ABBREVIATION_ALIASES = {"ARI": frozenset({"ARI", "AZ"})}

MANIFEST_FIELDS = (
    "manifest_contract_version",
    "manifest_version",
    "game_id",
    "season",
    "scheduled_start_utc",
    "actual_start_utc",
    "game_final_utc",
    "result_available_at_utc",
    "status",
    "status_reason",
    "away_team",
    "home_team",
    "away_score",
    "home_score",
    "doubleheader_game_number",
    "source_name",
    "source_record_id",
    "source_retrieved_at_utc",
    "source_fingerprint",
    "provenance_status",
    "record_fingerprint",
)

SOURCE_ENTRY_FIELDS = frozenset(
    {
        "game_id",
        "official_source_identifier",
        "official_endpoint_action_identifier",
        "request_parameters",
        "http_status",
        "content_type",
        "source_retrieved_at_utc",
        "relative_raw_path",
        "raw_sha256",
        "retrieval_outcome",
        "error_reason",
        "attempt_count",
    }
)


class P271Error(RuntimeError):
    """Fail-closed validation or execution error."""


def normalize_nfc(value: Any) -> Any:
    """Recursively normalize every string, including mapping keys, to Unicode NFC."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise P271Error("Canonical JSON mappings require string keys")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise P271Error("Unicode normalization produced a duplicate mapping key")
            normalized[normalized_key] = normalize_nfc(item)
        return normalized
    return value


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    """Return deterministic UTF-8 JSON using the approved canonicalization rules."""
    encoded = json.dumps(
        normalize_nfc(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def normalize_utc_timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P271Error(f"{field_name} must be a non-empty timestamp string")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P271Error(f"{field_name} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise P271Error(f"{field_name} must include an explicit UTC offset")
    normalized = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return normalized


def _timestamp_or_none(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return normalize_utc_timestamp(value, field_name)


def _require_dict(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise P271Error(f"{field_name} must be an object")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise P271Error(f"{field_name} must be a string or null")
    normalized = unicodedata.normalize("NFC", value).strip()
    return normalized or None


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P271Error(f"{field_name} must be a non-negative integer")
    return value


_DETAILED_STATUS_MAP = {
    "scheduled": "SCHEDULED",
    "pre-game": "SCHEDULED",
    "pregame": "SCHEDULED",
    "warmup": "SCHEDULED",
    "delayed start": "SCHEDULED",
    "in progress": "IN_PROGRESS",
    "manager challenge": "IN_PROGRESS",
    "review": "IN_PROGRESS",
    "delayed": "IN_PROGRESS",
    "rain delay": "IN_PROGRESS",
    "suspended": "SUSPENDED",
    "final": "FINAL",
    "game over": "FINAL",
    "completed early": "FINAL",
    "postponed": "POSTPONED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
    "forfeit": "FORFEIT",
    "forfeited": "FORFEIT",
}
_CODED_STATUS_MAP = {
    "S": "SCHEDULED",
    "P": "SCHEDULED",
    "I": "IN_PROGRESS",
    "M": "IN_PROGRESS",
    "U": "SUSPENDED",
    "F": "FINAL",
    "O": "FINAL",
    "D": "POSTPONED",
    "C": "CANCELLED",
}
_ABSTRACT_STATUS_MAP = {
    "preview": "SCHEDULED",
    "live": "IN_PROGRESS",
    "final": "FINAL",
}


def resolve_official_status(status_payload: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Map official status fields and report internal official-record conflicts."""
    detail_raw = status_payload.get("detailedState")
    code_raw = status_payload.get("statusCode") or status_payload.get("codedGameState")
    abstract_raw = status_payload.get("abstractGameState")

    detailed: str | None = None
    if detail_raw is not None:
        if not isinstance(detail_raw, str):
            raise P271Error("gameData.status.detailedState must be a string")
        detailed = _DETAILED_STATUS_MAP.get(detail_raw.strip().casefold())
        if detailed is None:
            raise P271Error(f"Unrecognized official detailed status: {detail_raw!r}")

    coded: str | None = None
    if code_raw is not None:
        if not isinstance(code_raw, str):
            raise P271Error("Official coded status must be a string")
        coded = _CODED_STATUS_MAP.get(code_raw.strip().upper())
        if coded is None:
            raise P271Error(f"Unrecognized official coded status: {code_raw!r}")

    abstract: str | None = None
    if abstract_raw is not None:
        if not isinstance(abstract_raw, str):
            raise P271Error("gameData.status.abstractGameState must be a string")
        abstract = _ABSTRACT_STATUS_MAP.get(abstract_raw.strip().casefold())
        if abstract is None:
            raise P271Error(f"Unrecognized official abstract status: {abstract_raw!r}")

    selected = detailed or coded or abstract
    if selected is None:
        raise P271Error("Official status fields are missing")

    conflicts: list[str] = []
    if detailed and coded and detailed != coded:
        compatible_forfeit = detailed == "FORFEIT" and coded == "FINAL"
        if not compatible_forfeit:
            conflicts.append("OFFICIAL_STATUS_FIELDS_CONFLICT")

    if abstract:
        compatible_abstract = (
            (abstract == "SCHEDULED" and selected == "SCHEDULED")
            or (abstract == "IN_PROGRESS" and selected in {"IN_PROGRESS", "SUSPENDED"})
            or (
                abstract == "FINAL"
                and selected in {"FINAL", "POSTPONED", "CANCELLED", "FORFEIT", "SUSPENDED"}
            )
        )
        if not compatible_abstract:
            conflicts.append("OFFICIAL_ABSTRACT_STATUS_CONFLICT")
    return selected, sorted(set(conflicts))


def _official_team_abbreviation(team_payload: Any, field_name: str) -> str:
    team = _require_dict(team_payload, field_name)
    abbreviation = team.get("abbreviation")
    if not isinstance(abbreviation, str) or not abbreviation.strip():
        raise P271Error(f"{field_name}.abbreviation is required")
    return unicodedata.normalize("NFC", abbreviation.strip().upper())


def _official_team_matches_expected(official: str, expected: str) -> bool:
    accepted = OFFICIAL_TEAM_ABBREVIATION_ALIASES.get(expected, frozenset({expected}))
    return official in accepted


def _score_candidates(payload: Mapping[str, Any], side: str) -> list[int]:
    candidates: list[int] = []
    game_data = _require_dict(payload.get("gameData"), "gameData")
    game_teams = _require_dict(game_data.get("teams"), "gameData.teams")
    game_team = _require_dict(game_teams.get(side), f"gameData.teams.{side}")
    if game_team.get("score") is not None:
        candidates.append(
            _strict_nonnegative_int(game_team["score"], f"gameData.teams.{side}.score")
        )

    live_data = payload.get("liveData")
    if live_data is not None:
        live = _require_dict(live_data, "liveData")
        linescore = live.get("linescore")
        if linescore is not None:
            line_obj = _require_dict(linescore, "liveData.linescore")
            line_teams = line_obj.get("teams")
            if line_teams is not None:
                line_team_map = _require_dict(line_teams, "liveData.linescore.teams")
                line_team = line_team_map.get(side)
                if line_team is not None:
                    line_side = _require_dict(
                        line_team, f"liveData.linescore.teams.{side}"
                    )
                    if line_side.get("runs") is not None:
                        candidates.append(
                            _strict_nonnegative_int(
                                line_side["runs"],
                                f"liveData.linescore.teams.{side}.runs",
                            )
                        )
    return candidates


def _single_timestamp_candidate(
    container: Mapping[str, Any], keys: Iterable[str], field_name: str
) -> tuple[str | None, bool]:
    values = {
        normalize_utc_timestamp(container[key], f"{field_name}.{key}")
        for key in keys
        if container.get(key) is not None
    }
    if not values:
        return None, False
    if len(values) > 1:
        return None, True
    return next(iter(values)), False


def validate_official_payload(payload: Any, game_spec: Mapping[str, Any]) -> None:
    """Validate official response identity and minimum parseable evidence."""
    root = _require_dict(payload, "official response")
    game_data = _require_dict(root.get("gameData"), "gameData")
    game = _require_dict(game_data.get("game"), "gameData.game")
    game_pk = game.get("pk")
    if isinstance(game_pk, bool) or not isinstance(game_pk, int):
        raise P271Error("gameData.game.pk must be an integer")
    if game_pk != game_spec["game_pk"]:
        raise P271Error(
            f"Official record identity mismatch: expected {game_spec['game_pk']}, got {game_pk}"
        )

    top_level_pk = root.get("gamePk")
    if top_level_pk is not None and top_level_pk != game_pk:
        raise P271Error("Top-level gamePk conflicts with gameData.game.pk")

    teams = _require_dict(game_data.get("teams"), "gameData.teams")
    away = _official_team_abbreviation(teams.get("away"), "gameData.teams.away")
    home = _official_team_abbreviation(teams.get("home"), "gameData.teams.home")
    if not _official_team_matches_expected(
        away, game_spec["away_team"]
    ) or not _official_team_matches_expected(home, game_spec["home_team"]):
        raise P271Error(
            f"Official teams mismatch for {game_spec['game_id']}: {away} @ {home}"
        )

    datetime_payload = _require_dict(game_data.get("datetime"), "gameData.datetime")
    normalize_utc_timestamp(datetime_payload.get("dateTime"), "gameData.datetime.dateTime")
    status_payload = _require_dict(game_data.get("status"), "gameData.status")
    resolve_official_status(status_payload)


def _extract_doubleheader_number(game_payload: Mapping[str, Any]) -> int | None:
    indicator = game_payload.get("doubleHeader")
    if indicator is None:
        return None
    if not isinstance(indicator, str) or indicator not in {"N", "Y", "S"}:
        raise P271Error("gameData.game.doubleHeader has an unrecognized value")
    if indicator == "N":
        return None
    number = game_payload.get("gameNumber")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise P271Error("Official doubleheader record requires a positive gameNumber")
    return number


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    without_fingerprint = {
        key: value for key, value in record.items() if key != "record_fingerprint"
    }
    return sha256_bytes(canonical_json_bytes(without_fingerprint))


def extract_manifest_record(
    payload: Any, source_entry: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Extract one fail-closed manifest record from a validated official payload."""
    game_id = source_entry.get("game_id")
    if game_id not in GAME_BY_ID:
        raise P271Error(f"Source entry has a non-allowlisted game_id: {game_id!r}")
    game_spec = GAME_BY_ID[game_id]
    validate_official_payload(payload, game_spec)

    root = _require_dict(payload, "official response")
    game_data = _require_dict(root["gameData"], "gameData")
    game = _require_dict(game_data["game"], "gameData.game")
    datetime_payload = _require_dict(game_data["datetime"], "gameData.datetime")
    status_payload = _require_dict(game_data["status"], "gameData.status")
    teams = _require_dict(game_data["teams"], "gameData.teams")

    status, conflicts = resolve_official_status(status_payload)
    scheduled_start = normalize_utc_timestamp(
        datetime_payload.get("dateTime"), "gameData.datetime.dateTime"
    )
    actual_start, actual_start_conflict = _single_timestamp_candidate(
        datetime_payload,
        ("actualStartTime", "actualStartDateTime"),
        "gameData.datetime",
    )
    game_final, game_final_conflict = _single_timestamp_candidate(
        datetime_payload,
        ("gameEndTime", "gameFinalTime", "gameFinalDateTime"),
        "gameData.datetime",
    )

    # Only an explicit semantically named availability field can establish this.
    # metaData.timeStamp, play times, file mtimes and source_retrieved_at_utc are
    # deliberately excluded because they do not prove earliest result availability.
    result_available, result_available_conflict = _single_timestamp_candidate(
        status_payload,
        ("resultAvailableAt", "resultAvailableAtUtc"),
        "gameData.status",
    )
    if actual_start_conflict:
        conflicts.append("OFFICIAL_ACTUAL_START_FIELDS_CONFLICT")
    if game_final_conflict:
        conflicts.append("OFFICIAL_GAME_FINAL_FIELDS_CONFLICT")
    if result_available_conflict:
        conflicts.append("OFFICIAL_RESULT_AVAILABILITY_FIELDS_CONFLICT")

    away_candidates = _score_candidates(root, "away")
    home_candidates = _score_candidates(root, "home")
    if len(set(away_candidates)) > 1 or len(set(home_candidates)) > 1:
        conflicts.append("OFFICIAL_FINAL_SCORE_CONFLICT")

    away_score: int | None = None
    home_score: int | None = None
    if status in {"FINAL", "FORFEIT"}:
        if len(set(away_candidates)) == 1 and len(set(home_candidates)) == 1:
            away_score = away_candidates[0]
            home_score = home_candidates[0]
        elif "OFFICIAL_FINAL_SCORE_CONFLICT" not in conflicts:
            raise P271Error("Final/forfeit official record is missing final scores")
    elif status in {"POSTPONED", "CANCELLED"}:
        away_score = None
        home_score = None

    source_retrieved = normalize_utc_timestamp(
        source_entry.get("source_retrieved_at_utc"), "source_retrieved_at_utc"
    )
    if result_available:
        if datetime.fromisoformat(result_available.replace("Z", "+00:00")) > datetime.fromisoformat(
            source_retrieved.replace("Z", "+00:00")
        ):
            conflicts.append("RESULT_AVAILABILITY_AFTER_SOURCE_RETRIEVAL")

    blockers: list[str] = []
    if conflicts:
        provenance_status = "CONFLICT"
        blockers.extend(sorted(set(conflicts)))
    elif result_available is None:
        provenance_status = "INCOMPLETE"
        blockers.append("HISTORICAL_RESULT_AVAILABILITY_UNPROVEN")
    else:
        provenance_status = "COMPLETE"

    source_fingerprint = source_entry.get("raw_sha256")
    if not _is_sha256(source_fingerprint):
        raise P271Error("Successful source entry requires a valid raw_sha256")

    record: dict[str, Any] = {
        "manifest_contract_version": MANIFEST_CONTRACT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "game_id": game_id,
        "season": 2026,
        "scheduled_start_utc": scheduled_start,
        "actual_start_utc": actual_start,
        "game_final_utc": game_final if status in {"FINAL", "FORFEIT"} else None,
        "result_available_at_utc": result_available,
        "status": status,
        "status_reason": _optional_string(
            status_payload.get("reason"), "gameData.status.reason"
        ),
        "away_team": _official_team_abbreviation(
            teams.get("away"), "gameData.teams.away"
        ),
        "home_team": _official_team_abbreviation(
            teams.get("home"), "gameData.teams.home"
        ),
        "away_score": away_score,
        "home_score": home_score,
        "doubleheader_game_number": _extract_doubleheader_number(game),
        "source_name": SOURCE_NAME,
        "source_record_id": str(game_spec["game_pk"]),
        "source_retrieved_at_utc": source_retrieved,
        "source_fingerprint": source_fingerprint,
        "provenance_status": provenance_status,
        "record_fingerprint": None,
    }
    record["record_fingerprint"] = _record_fingerprint(record)
    validate_manifest_record(record)
    return normalize_nfc(record), sorted(set(blockers))


def _unresolved_manifest_record(
    source_entry: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    game_id = source_entry["game_id"]
    game_spec = GAME_BY_ID[game_id]
    record: dict[str, Any] = {
        "manifest_contract_version": MANIFEST_CONTRACT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "game_id": game_id,
        "season": 2026,
        "scheduled_start_utc": None,
        "actual_start_utc": None,
        "game_final_utc": None,
        "result_available_at_utc": None,
        "status": None,
        "status_reason": None,
        "away_team": None,
        "home_team": None,
        "away_score": None,
        "home_score": None,
        "doubleheader_game_number": None,
        "source_name": SOURCE_NAME,
        "source_record_id": str(game_spec["game_pk"]),
        "source_retrieved_at_utc": normalize_utc_timestamp(
            source_entry["source_retrieved_at_utc"], "source_retrieved_at_utc"
        ),
        "source_fingerprint": None,
        "provenance_status": "INCOMPLETE",
        "record_fingerprint": None,
    }
    record["record_fingerprint"] = _record_fingerprint(record)
    validate_manifest_record(record)
    blocker = f"SOURCE_{source_entry['retrieval_outcome']}"
    return record, [blocker]


def validate_manifest_record(record: Mapping[str, Any]) -> None:
    """Validate exact manifest schema, null rules, and record fingerprint."""
    if set(record) != set(MANIFEST_FIELDS):
        missing = sorted(set(MANIFEST_FIELDS) - set(record))
        extra = sorted(set(record) - set(MANIFEST_FIELDS))
        raise P271Error(f"Manifest schema mismatch; missing={missing}, extra={extra}")
    if record["manifest_contract_version"] != MANIFEST_CONTRACT_VERSION:
        raise P271Error("Unexpected manifest_contract_version")
    if record["manifest_version"] != MANIFEST_VERSION:
        raise P271Error("Unexpected manifest_version")
    if record["game_id"] not in GAME_BY_ID:
        raise P271Error("Manifest game_id is not allowlisted")
    if record["season"] != 2026:
        raise P271Error("Manifest season must be 2026")

    status = record["status"]
    if status is not None and status not in ALLOWED_STATUSES:
        raise P271Error(f"Manifest status is not allowed: {status!r}")
    provenance = record["provenance_status"]
    if provenance not in ALLOWED_PROVENANCE_STATUSES:
        raise P271Error(f"Manifest provenance_status is not allowed: {provenance!r}")

    for field in (
        "scheduled_start_utc",
        "actual_start_utc",
        "game_final_utc",
        "result_available_at_utc",
        "source_retrieved_at_utc",
    ):
        if record[field] is not None:
            normalize_utc_timestamp(record[field], field)

    for field in ("away_team", "home_team", "status_reason", "source_name", "source_record_id"):
        if record[field] is not None and not isinstance(record[field], str):
            raise P271Error(f"{field} must be a string or null")

    for field in ("away_score", "home_score"):
        if record[field] is not None:
            _strict_nonnegative_int(record[field], field)
    doubleheader_number = record["doubleheader_game_number"]
    if doubleheader_number is not None:
        if (
            isinstance(doubleheader_number, bool)
            or not isinstance(doubleheader_number, int)
            or doubleheader_number <= 0
        ):
            raise P271Error("doubleheader_game_number must be a positive integer or null")

    if status in {"FINAL", "FORFEIT"}:
        scores_present = record["away_score"] is not None and record["home_score"] is not None
        if not scores_present and provenance != "CONFLICT":
            raise P271Error("Final/forfeit rows require both official final scores")
    elif record["away_score"] is not None or record["home_score"] is not None:
        raise P271Error("Only final/forfeit rows may contain scores")
    if status in {"POSTPONED", "CANCELLED"} and (
        record["away_score"] is not None or record["home_score"] is not None
    ):
        raise P271Error("Postponed/cancelled rows must keep scores null")

    if provenance == "COMPLETE" and record["result_available_at_utc"] is None:
        raise P271Error("COMPLETE provenance requires result_available_at_utc")
    if record["source_fingerprint"] is not None and not _is_sha256(
        record["source_fingerprint"]
    ):
        raise P271Error("source_fingerprint must be a SHA-256 or null")
    if not _is_sha256(record["record_fingerprint"]):
        raise P271Error("record_fingerprint must be a SHA-256")
    if record["record_fingerprint"] != _record_fingerprint(record):
        raise P271Error("record_fingerprint does not match canonical record content")


def _validate_source_entry(entry: Any) -> dict[str, Any]:
    source = _require_dict(entry, "source entry")
    if set(source) != SOURCE_ENTRY_FIELDS:
        missing = sorted(SOURCE_ENTRY_FIELDS - set(source))
        extra = sorted(set(source) - SOURCE_ENTRY_FIELDS)
        raise P271Error(f"Source entry schema mismatch; missing={missing}, extra={extra}")
    game_id = source["game_id"]
    if game_id not in GAME_BY_ID:
        raise P271Error(f"Source entry game_id is not allowlisted: {game_id!r}")
    game_spec = GAME_BY_ID[game_id]
    if source["official_source_identifier"] != OFFICIAL_SOURCE_IDENTIFIER:
        raise P271Error("Source entry official_source_identifier is not approved")
    if source["official_endpoint_action_identifier"] != ENDPOINT_ACTION_IDENTIFIER:
        raise P271Error("Source entry endpoint/action is not approved")
    if source["request_parameters"] != {"gamePk": game_spec["game_pk"]}:
        raise P271Error("Source entry request parameters do not match the allowlist")
    normalize_utc_timestamp(source["source_retrieved_at_utc"], "source_retrieved_at_utc")

    outcome = source["retrieval_outcome"]
    if outcome not in ALLOWED_RETRIEVAL_OUTCOMES:
        raise P271Error(f"Unrecognized retrieval outcome: {outcome!r}")
    attempts = source["attempt_count"]
    if isinstance(attempts, bool) or attempts not in {1, 2}:
        raise P271Error("attempt_count must be 1 or the single approved transport retry value 2")

    http_status = source["http_status"]
    if http_status is not None and (
        isinstance(http_status, bool) or not isinstance(http_status, int)
    ):
        raise P271Error("http_status must be an integer or null")
    content_type = source["content_type"]
    if content_type is not None and not isinstance(content_type, str):
        raise P271Error("content_type must be a string or null")

    expected_raw_path = f"raw/{game_id}.feed.live.json"
    if outcome == "SUCCESS":
        if http_status != 200:
            raise P271Error("Successful source entry must have HTTP 200")
        if not content_type or not content_type.lower().startswith("application/json"):
            raise P271Error("Successful source entry must have an application/json content type")
        if source["relative_raw_path"] != expected_raw_path:
            raise P271Error("Successful source entry has an unexpected raw path")
        if not _is_sha256(source["raw_sha256"]):
            raise P271Error("Successful source entry requires raw_sha256")
        if source["error_reason"] is not None:
            raise P271Error("Successful source entry must have a null error_reason")
    else:
        if source["relative_raw_path"] is not None or source["raw_sha256"] is not None:
            raise P271Error("Failed source entries may not reference unvalidated raw evidence")
        if not isinstance(source["error_reason"], str) or not source["error_reason"]:
            raise P271Error("Failed source entries require an error_reason")
    return source


def validate_source_index(index: Any) -> dict[str, Any]:
    source_index = _require_dict(index, "source index")
    expected_top_level = {
        "source_index_contract_version",
        "retrieval_started_at_utc",
        "retrieval_completed_at_utc",
        "allowlisted_game_ids",
        "sources",
    }
    if set(source_index) != expected_top_level:
        raise P271Error("Source index top-level schema mismatch")
    if source_index["source_index_contract_version"] != SOURCE_INDEX_CONTRACT_VERSION:
        raise P271Error("Unexpected source index contract version")
    normalize_utc_timestamp(source_index["retrieval_started_at_utc"], "retrieval_started_at_utc")
    normalize_utc_timestamp(
        source_index["retrieval_completed_at_utc"], "retrieval_completed_at_utc"
    )
    if source_index["allowlisted_game_ids"] != list(ALLOWLISTED_GAME_IDS):
        raise P271Error("Source index allowlisted_game_ids is not the exact approved order")
    sources = source_index["sources"]
    if not isinstance(sources, list):
        raise P271Error("Source index sources must be a list")
    raw_game_ids = [entry.get("game_id") if isinstance(entry, dict) else None for entry in sources]
    if len(raw_game_ids) != len(set(raw_game_ids)):
        raise P271Error("Source index contains duplicate game IDs")
    validated_sources = [_validate_source_entry(entry) for entry in sources]
    game_ids = [entry["game_id"] for entry in validated_sources]
    if len(game_ids) != len(set(game_ids)):
        raise P271Error("Source index contains duplicate game IDs")
    if game_ids != list(ALLOWLISTED_GAME_IDS):
        raise P271Error("Source index must contain exactly one entry per allowlisted game in order")
    return source_index


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _safe_error_reason(prefix: str, detail: Any) -> str:
    text = unicodedata.normalize("NFC", str(detail)).replace("\n", " ").strip()
    return f"{prefix}:{text[:300]}" if text else prefix


def _base_source_entry(game_spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "game_id": game_spec["game_id"],
        "official_source_identifier": OFFICIAL_SOURCE_IDENTIFIER,
        "official_endpoint_action_identifier": ENDPOINT_ACTION_IDENTIFIER,
        "request_parameters": {"gamePk": game_spec["game_pk"]},
        "http_status": None,
        "content_type": None,
        "source_retrieved_at_utc": None,
        "relative_raw_path": None,
        "raw_sha256": None,
        "retrieval_outcome": None,
        "error_reason": None,
        "attempt_count": 1,
    }


def fetch_official_game(game_spec: Mapping[str, Any], output_root: Path) -> dict[str, Any]:
    """Fetch one allowlisted official game, with at most one transport-only retry."""
    entry = _base_source_entry(game_spec)
    url = ENDPOINT_TEMPLATE.format(game_pk=game_spec["game_pk"])
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )

    for attempt in (1, 2):
        entry["attempt_count"] = attempt
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
                http_status = int(response.getcode())
                content_type = response.headers.get("Content-Type")
            retrieved_at = utc_now()
            entry["http_status"] = http_status
            entry["content_type"] = content_type
            entry["source_retrieved_at_utc"] = retrieved_at
            if http_status != 200:
                entry["retrieval_outcome"] = "HTTP_ERROR"
                entry["error_reason"] = f"HTTP_STATUS_{http_status}"
                return _validate_source_entry(entry)
            if not content_type or not content_type.lower().startswith("application/json"):
                entry["retrieval_outcome"] = "VALIDATION_ERROR"
                entry["error_reason"] = "CONTENT_TYPE_NOT_APPLICATION_JSON"
                return _validate_source_entry(entry)
            try:
                payload = json.loads(raw.decode("utf-8"))
                validate_official_payload(payload, game_spec)
            except (UnicodeDecodeError, json.JSONDecodeError, P271Error) as exc:
                entry["retrieval_outcome"] = "VALIDATION_ERROR"
                entry["error_reason"] = _safe_error_reason(
                    "OFFICIAL_PAYLOAD_VALIDATION_FAILED", exc
                )
                return _validate_source_entry(entry)

            raw_relative_path = f"raw/{game_spec['game_id']}.feed.live.json"
            raw_path = output_root / raw_relative_path
            raw_sha256 = sha256_bytes(raw)
            _atomic_write(raw_path, raw)
            entry["relative_raw_path"] = raw_relative_path
            entry["raw_sha256"] = raw_sha256
            entry["retrieval_outcome"] = "SUCCESS"
            entry["error_reason"] = None
            return _validate_source_entry(entry)
        except urllib.error.HTTPError as exc:
            entry["http_status"] = exc.code
            entry["content_type"] = exc.headers.get("Content-Type") if exc.headers else None
            entry["source_retrieved_at_utc"] = utc_now()
            entry["retrieval_outcome"] = "HTTP_ERROR"
            entry["error_reason"] = f"HTTP_STATUS_{exc.code}"
            return _validate_source_entry(entry)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            if attempt == 1:
                continue
            entry["source_retrieved_at_utc"] = utc_now()
            entry["retrieval_outcome"] = "TRANSPORT_ERROR"
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            entry["error_reason"] = _safe_error_reason(
                "TRANSPORT_FAILURE_AFTER_RETRY", reason
            )
            return _validate_source_entry(entry)
        except Exception as exc:
            entry["source_retrieved_at_utc"] = utc_now()
            entry["retrieval_outcome"] = "VALIDATION_ERROR"
            entry["error_reason"] = _safe_error_reason(
                "UNEXPECTED_FETCH_VALIDATION_FAILURE", type(exc).__name__
            )
            return _validate_source_entry(entry)
    raise P271Error("Unreachable fetch state")


def _load_raw_payload(output_root: Path, entry: Mapping[str, Any]) -> Any:
    relative_path = entry["relative_raw_path"]
    if not isinstance(relative_path, str):
        raise P271Error("Successful source entry is missing relative_raw_path")
    root_resolved = output_root.resolve()
    raw_path = (output_root / relative_path).resolve()
    if root_resolved not in raw_path.parents:
        raise P271Error("Raw source path escapes the explicit output root")
    if not raw_path.is_file():
        raise P271Error(f"Referenced raw evidence is missing: {relative_path}")
    raw = raw_path.read_bytes()
    if sha256_bytes(raw) != entry["raw_sha256"]:
        raise P271Error(f"Raw SHA-256 mismatch: {relative_path}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P271Error(f"Saved raw evidence is not valid UTF-8 JSON: {relative_path}") from exc
    validate_official_payload(payload, GAME_BY_ID[entry["game_id"]])
    return payload


def load_source_index(output_root: Path) -> tuple[dict[str, Any], bytes]:
    path = output_root / "source_index.json"
    if not path.is_file():
        raise P271Error(f"Source index is missing: {path}")
    raw = path.read_bytes()
    try:
        source_index = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P271Error("source_index.json is not valid UTF-8 JSON") from exc
    validate_source_index(source_index)

    referenced_raw = sorted(
        entry["relative_raw_path"]
        for entry in source_index["sources"]
        if entry["retrieval_outcome"] == "SUCCESS"
    )
    raw_dir = output_root / "raw"
    actual_raw = (
        sorted(str(path.relative_to(output_root)) for path in raw_dir.glob("*.json"))
        if raw_dir.exists()
        else []
    )
    if actual_raw != referenced_raw:
        raise P271Error(
            f"Raw evidence inventory mismatch; referenced={referenced_raw}, actual={actual_raw}"
        )
    return source_index, raw


def _classification(record: Mapping[str, Any], blockers: Sequence[str]) -> str:
    if record["provenance_status"] == "CONFLICT":
        return "CONFLICT"
    if record["status"] is None or record["source_fingerprint"] is None:
        return "UNRESOLVED"
    if record["provenance_status"] == "COMPLETE" and not blockers:
        return "CERTIFIED"
    if blockers == ["HISTORICAL_RESULT_AVAILABILITY_UNPROVEN"]:
        return "OFFICIAL_STATUS_RECOVERED_AVAILABILITY_BLOCKED"
    return "UNRESOLVED"


def build_artifacts(
    output_root: Path, source_index: Mapping[str, Any], source_index_bytes: bytes
) -> tuple[list[dict[str, Any]], dict[str, Any], bytes, bytes]:
    """Build deterministic manifest and summary bytes entirely from saved inputs."""
    validate_source_index(source_index)
    records: list[dict[str, Any]] = []
    game_summaries: list[dict[str, Any]] = []
    for entry in source_index["sources"]:
        if entry["retrieval_outcome"] == "SUCCESS":
            payload = _load_raw_payload(output_root, entry)
            record, blockers = extract_manifest_record(payload, entry)
        else:
            record, blockers = _unresolved_manifest_record(entry)
        records.append(record)
        game_summaries.append(
            {
                "game_id": record["game_id"],
                "status": record["status"],
                "provenance_status": record["provenance_status"],
                "classification": _classification(record, blockers),
                "blockers": blockers,
                "record_fingerprint": record["record_fingerprint"],
            }
        )

    if [record["game_id"] for record in records] != list(ALLOWLISTED_GAME_IDS):
        raise P271Error("Manifest record order differs from the approved allowlist")
    for record in records:
        validate_manifest_record(record)

    fingerprints = [record["record_fingerprint"] for record in records]
    manifest_root_hash = sha256_bytes("\n".join(fingerprints).encode("ascii"))
    classification_counts = Counter(item["classification"] for item in game_summaries)
    logical_summary_counts = {name: classification_counts.get(name, 0) for name in CLASSIFICATIONS}
    status_counts = Counter(record["status"] or "UNKNOWN" for record in records)
    provenance_counts = Counter(record["provenance_status"] for record in records)
    outcome_counts = Counter(entry["retrieval_outcome"] for entry in source_index["sources"])

    manifest_bytes = b"".join(
        canonical_json_bytes(record, trailing_newline=True) for record in records
    )
    summary: dict[str, Any] = {
        "manifest_contract_version": MANIFEST_CONTRACT_VERSION,
        "manifest_version": MANIFEST_VERSION,
        "game_count": len(records),
        "ordered_game_ids": list(ALLOWLISTED_GAME_IDS),
        "manifest_root_hash": manifest_root_hash,
        "manifest_root_hash_algorithm": (
            "SHA-256 over ASCII record_fingerprint values joined by one LF, no trailing LF"
        ),
        "logical_summary_counts": logical_summary_counts,
        "status_counts": dict(sorted(status_counts.items())),
        "provenance_status_counts": dict(sorted(provenance_counts.items())),
        "source_retrieval_outcome_counts": dict(sorted(outcome_counts.items())),
        "raw_capture_count": outcome_counts.get("SUCCESS", 0),
        "source_index_sha256": sha256_bytes(source_index_bytes),
        "pit_replay_ready": logical_summary_counts["CERTIFIED"] == len(ALLOWLIST),
        "paper_only": True,
        "diagnostic_only": True,
        "model_executed": False,
        "prediction_output_created": False,
        "sha256sums_scope_note": "SHA256SUMS covers every raw and generated artifact except itself",
        "games": game_summaries,
    }
    summary_bytes = canonical_json_bytes(summary, trailing_newline=True)
    return records, summary, manifest_bytes, summary_bytes


def _checksum_paths(output_root: Path, source_index: Mapping[str, Any]) -> list[str]:
    paths = [
        entry["relative_raw_path"]
        for entry in source_index["sources"]
        if entry["retrieval_outcome"] == "SUCCESS"
    ]
    paths.extend(["source_index.json", "pit-result-status.v1.jsonl", "manifest_summary.json"])
    return sorted(paths)


def build_sha256sums(output_root: Path, source_index: Mapping[str, Any]) -> bytes:
    lines: list[str] = []
    for relative_path in _checksum_paths(output_root, source_index):
        artifact = output_root / relative_path
        if not artifact.is_file():
            raise P271Error(f"Cannot hash missing artifact: {relative_path}")
        lines.append(f"{sha256_bytes(artifact.read_bytes())}  {relative_path}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def regenerate(output_root: Path) -> dict[str, Any]:
    source_index, source_index_bytes = load_source_index(output_root)
    _, summary, manifest_bytes, summary_bytes = build_artifacts(
        output_root, source_index, source_index_bytes
    )
    _atomic_write(output_root / "pit-result-status.v1.jsonl", manifest_bytes)
    _atomic_write(output_root / "manifest_summary.json", summary_bytes)
    _atomic_write(output_root / "SHA256SUMS", build_sha256sums(output_root, source_index))
    return summary


def verify(output_root: Path) -> dict[str, Any]:
    source_index, source_index_bytes = load_source_index(output_root)
    _, summary, expected_manifest, expected_summary = build_artifacts(
        output_root, source_index, source_index_bytes
    )
    expected_files = {
        "pit-result-status.v1.jsonl": expected_manifest,
        "manifest_summary.json": expected_summary,
    }
    for relative_path, expected_bytes in expected_files.items():
        path = output_root / relative_path
        if not path.is_file() or path.read_bytes() != expected_bytes:
            raise P271Error(
                f"Offline artifact differs from deterministic regeneration: {relative_path}"
            )

    expected_sha256sums = build_sha256sums(output_root, source_index)
    sha_path = output_root / "SHA256SUMS"
    if not sha_path.is_file() or sha_path.read_bytes() != expected_sha256sums:
        raise P271Error("SHA256SUMS does not match the complete artifact inventory")
    return summary


def validate_requested_game_ids(game_ids: Sequence[str] | None) -> tuple[str, ...]:
    if not game_ids:
        return ALLOWLISTED_GAME_IDS
    if len(game_ids) != len(set(game_ids)):
        raise P271Error("Duplicate --game-id values are forbidden")
    if tuple(game_ids) != ALLOWLISTED_GAME_IDS:
        raise P271Error("Network mode requires the exact twelve allowlisted game IDs in order")
    return tuple(game_ids)


def fetch_all(output_root: Path, game_ids: Sequence[str] | None = None) -> dict[str, Any]:
    selected = validate_requested_game_ids(game_ids)
    if output_root.exists() and any(output_root.iterdir()):
        raise P271Error("Fetch output root must not contain pre-existing evidence or artifacts")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "raw").mkdir(exist_ok=True)

    retrieval_started = utc_now()
    sources = [fetch_official_game(GAME_BY_ID[game_id], output_root) for game_id in selected]
    retrieval_completed = utc_now()
    source_index = {
        "source_index_contract_version": SOURCE_INDEX_CONTRACT_VERSION,
        "retrieval_started_at_utc": retrieval_started,
        "retrieval_completed_at_utc": retrieval_completed,
        "allowlisted_game_ids": list(ALLOWLISTED_GAME_IDS),
        "sources": sources,
    }
    validate_source_index(source_index)
    source_index_bytes = canonical_json_bytes(source_index, trailing_newline=True)
    _atomic_write(output_root / "source_index.json", source_index_bytes)
    return regenerate(output_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and regenerate the P271 official MLB result/status manifest"
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("fetch", "regenerate", "verify"):
        command = subparsers.add_parser(mode)
        command.add_argument("--output-root", type=Path, required=True)
        if mode == "fetch":
            command.add_argument(
                "--game-id",
                action="append",
                dest="game_ids",
                help="Repeat in the exact approved allowlist order; defaults to all twelve",
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "fetch":
            summary = fetch_all(args.output_root, args.game_ids)
        elif args.mode == "regenerate":
            summary = regenerate(args.output_root)
        else:
            summary = verify(args.output_root)
    except P271Error as exc:
        print(f"P271_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
    result = {
        "mode": args.mode,
        "game_count": summary["game_count"],
        "manifest_root_hash": summary["manifest_root_hash"],
        "logical_summary_counts": summary["logical_summary_counts"],
        "pit_replay_ready": summary["pit_replay_ready"],
    }
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
