"""Manual one-shot recorder for prospective official MLB result availability.

The recorder has exactly two modes:

* capture performs one unauthenticated request for one explicit numeric gamePk and
  records the UTC time immediately after the complete response has been received.
* offline-verify reads saved response bytes and permits a fixed observation time for
  deterministic offline verification.

A current observation establishes availability no earlier than its own observation
timestamp.  It does not claim globally earliest official availability.  File mtimes,
feed-generated metadata, retries, polling, season fetches, and caller-controlled
timestamps in capture mode are deliberately excluded.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


OBSERVATION_CONTRACT_VERSION = "p272-prospective-result-availability.v1"
SOURCE_INDEX_CONTRACT_VERSION = "p272-prospective-source-index.v1"
SOURCE_NAME = "MLB_STATSAPI_GAME_FEED_LIVE"
SOURCE_ENDPOINT_ID = "GET statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"
OFFICIAL_HOST = "statsapi.mlb.com"
OFFICIAL_ENDPOINT_TEMPLATE = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "Betting-pool-P272-prospective-result-recorder/1.0"
OBSERVATION_FILENAME = "observation.json"
SOURCE_INDEX_FILENAME = "source_index.json"
CHECKSUM_FILENAME = "SHA256SUMS"

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
RESOLVED_STATUSES = frozenset({"FINAL", "FORFEIT"})
ALLOWED_PROVENANCE_STATUSES = frozenset({"COMPLETE", "INCOMPLETE"})

# This is the complete identity-alias allowlist.  The official response spelling is
# always retained in evidence; aliases are used only when validating identity.
TEAM_IDENTITY_ALIAS_GROUPS: Mapping[str, frozenset[str]] = {
    "ARI": frozenset({"ARI", "AZ"}),
}

OBSERVATION_FIELDS = frozenset(
    {
        "observation_contract_version",
        "game_id",
        "official_game_pk",
        "season",
        "scheduled_start_utc",
        "official_status",
        "status_reason",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
        "source_name",
        "source_endpoint_id",
        "source_observed_at_utc",
        "result_available_at_utc",
        "raw_sha256",
        "source_fingerprint",
        "record_fingerprint",
        "provenance_status",
    }
)
SOURCE_INDEX_FIELDS = frozenset(
    {
        "source_index_contract_version",
        "observation_contract_version",
        "game_id",
        "official_game_pk",
        "source_name",
        "source_endpoint_id",
        "source_observed_at_utc",
        "relative_raw_path",
        "relative_observation_path",
        "raw_sha256",
        "source_fingerprint",
        "record_fingerprint",
        "provenance_status",
    }
)

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
    "W": "SCHEDULED",
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
_ABSTRACT_CODE_MAP = {
    "P": "SCHEDULED",
    "L": "IN_PROGRESS",
    "F": "FINAL",
}


class P272Error(RuntimeError):
    """Fail-closed validation, network-boundary, or write-once error."""


def normalize_nfc(value: Any) -> Any:
    """Recursively normalize JSON strings and mapping keys to Unicode NFC."""
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
                raise P272Error("Canonical JSON mappings require string keys")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise P272Error("Unicode NFC normalization produced a duplicate key")
            normalized[normalized_key] = normalize_nfc(item)
        return normalized
    return value


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    """Return deterministic compact UTF-8 JSON using the P271-approved rules."""
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
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def utc_now() -> str:
    """Return the current UTC time; capture calls this only after response.read()."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def normalize_utc_timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P272Error(f"{field_name} must be a non-empty timestamp string")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P272Error(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise P272Error(f"{field_name} must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P272Error(f"{field_name} must be an object")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise P272Error(f"{field_name} must be a string or null")
    normalized = unicodedata.normalize("NFC", value).strip()
    return normalized or None


def _strict_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise P272Error(f"{field_name} must be a positive integer")
    return value


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P272Error(f"{field_name} must be a non-negative integer")
    return value


def _parse_game_pk_argument(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
        raise argparse.ArgumentTypeError("gamePk must contain only digits and be positive")
    return int(value)


def validate_single_game_pk(game_pks: Sequence[int]) -> int:
    """Require exactly one explicit gamePk and reject batch-shaped input."""
    if len(game_pks) != 1:
        raise P272Error("Exactly one explicit numeric gamePk is required")
    return _strict_positive_int(game_pks[0], "gamePk")


def _parse_official_json(raw: bytes) -> Mapping[str, Any]:
    if not isinstance(raw, bytes) or not raw:
        raise P272Error("Official raw response must be non-empty bytes")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        normalized_keys: set[str] = set()
        for key, value in pairs:
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized_keys:
                raise P272Error("Official JSON contains duplicate or NFC-equivalent keys")
            normalized_keys.add(normalized_key)
            result[key] = value
        return result

    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P272Error("Official response must be valid UTF-8 JSON") from exc
    return _require_mapping(parsed, "official response")


def _team_code(value: Any, field_name: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise P272Error(f"{field_name} must be a non-empty abbreviation")
    preserved = unicodedata.normalize("NFC", value).strip()
    validation_code = preserved.upper()
    if not re.fullmatch(r"[A-Z0-9]{2,4}", validation_code):
        raise P272Error(f"{field_name} is not a valid team abbreviation")
    return preserved, validation_code


def _team_identity_key(code: str) -> str:
    normalized = unicodedata.normalize("NFC", code).strip().upper()
    for canonical, aliases in TEAM_IDENTITY_ALIAS_GROUPS.items():
        if normalized in aliases:
            return canonical
    return normalized


def validate_expected_team(official: str, expected: str, field_name: str) -> None:
    _, official_code = _team_code(official, field_name)
    _, expected_code = _team_code(expected, f"expected {field_name}")
    if _team_identity_key(official_code) != _team_identity_key(expected_code):
        raise P272Error(
            f"Official {field_name} identity mismatch: expected {expected_code}, "
            f"observed {official_code}"
        )


def _optional_team_id(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    return _strict_positive_int(value, field_name)


def _extract_team_identity(
    root: Mapping[str, Any], game_data: Mapping[str, Any], side: str
) -> tuple[str, int | None]:
    teams = _require_mapping(game_data.get("teams"), "gameData.teams")
    primary = _require_mapping(teams.get(side), f"gameData.teams.{side}")
    preserved, primary_code = _team_code(
        primary.get("abbreviation"), f"gameData.teams.{side}.abbreviation"
    )
    primary_id = _optional_team_id(primary.get("id"), f"gameData.teams.{side}.id")

    live_data = root.get("liveData")
    if live_data is not None:
        live = _require_mapping(live_data, "liveData")
        boxscore = live.get("boxscore")
        if boxscore is not None:
            boxscore_obj = _require_mapping(boxscore, "liveData.boxscore")
            box_teams = boxscore_obj.get("teams")
            if box_teams is not None:
                box_team_map = _require_mapping(box_teams, "liveData.boxscore.teams")
                side_payload = box_team_map.get(side)
                if side_payload is not None:
                    side_obj = _require_mapping(
                        side_payload, f"liveData.boxscore.teams.{side}"
                    )
                    box_team = _require_mapping(
                        side_obj.get("team"), f"liveData.boxscore.teams.{side}.team"
                    )
                    box_id = _optional_team_id(
                        box_team.get("id"), f"liveData.boxscore.teams.{side}.team.id"
                    )
                    if primary_id is not None and box_id is not None and primary_id != box_id:
                        raise P272Error(f"Conflicting official {side} team identity evidence")
                    box_abbreviation = box_team.get("abbreviation")
                    if box_abbreviation is not None:
                        _, box_code = _team_code(
                            box_abbreviation,
                            f"liveData.boxscore.teams.{side}.team.abbreviation",
                        )
                        if _team_identity_key(primary_code) != _team_identity_key(box_code):
                            raise P272Error(
                                f"Conflicting official {side} team abbreviation evidence"
                            )
    return preserved, primary_id


def _mapped_status(
    raw_value: Any, field_name: str, mapping: Mapping[str, str], *, uppercase: bool
) -> str | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, str):
        raise P272Error(f"{field_name} must be a string")
    key = raw_value.strip().upper() if uppercase else raw_value.strip().casefold()
    mapped = mapping.get(key)
    if mapped is None:
        raise P272Error(f"Unrecognized official status evidence in {field_name}: {raw_value!r}")
    return mapped


def _abstract_compatible(abstract: str, selected: str) -> bool:
    if abstract == "SCHEDULED":
        return selected == "SCHEDULED"
    if abstract == "IN_PROGRESS":
        return selected in {"IN_PROGRESS", "SUSPENDED"}
    return selected in {"FINAL", "FORFEIT", "POSTPONED", "CANCELLED", "SUSPENDED"}


def resolve_official_status(status_payload: Mapping[str, Any]) -> str:
    """Resolve official status and fail closed on contradictory status fields."""
    status = _require_mapping(status_payload, "gameData.status")
    detailed = _mapped_status(
        status.get("detailedState"),
        "gameData.status.detailedState",
        _DETAILED_STATUS_MAP,
        uppercase=False,
    )
    coded_values = [
        mapped
        for mapped in (
            _mapped_status(
                status.get("statusCode"),
                "gameData.status.statusCode",
                _CODED_STATUS_MAP,
                uppercase=True,
            ),
            _mapped_status(
                status.get("codedGameState"),
                "gameData.status.codedGameState",
                _CODED_STATUS_MAP,
                uppercase=True,
            ),
        )
        if mapped is not None
    ]
    if len(set(coded_values)) > 1:
        raise P272Error("Conflicting official coded status evidence")
    coded = coded_values[0] if coded_values else None

    abstract_values = [
        mapped
        for mapped in (
            _mapped_status(
                status.get("abstractGameState"),
                "gameData.status.abstractGameState",
                _ABSTRACT_STATUS_MAP,
                uppercase=False,
            ),
            _mapped_status(
                status.get("abstractGameCode"),
                "gameData.status.abstractGameCode",
                _ABSTRACT_CODE_MAP,
                uppercase=True,
            ),
        )
        if mapped is not None
    ]
    if len(set(abstract_values)) > 1:
        raise P272Error("Conflicting official abstract status evidence")
    abstract = abstract_values[0] if abstract_values else None

    selected = detailed or coded or abstract
    if selected is None:
        raise P272Error("Official status evidence is missing")
    if detailed is not None and coded is not None and detailed != coded:
        if not (detailed == "FORFEIT" and coded == "FINAL"):
            raise P272Error("Conflicting official detailed/coded status evidence")
    if abstract is not None and not _abstract_compatible(abstract, selected):
        raise P272Error("Conflicting official abstract status evidence")
    return selected


def _optional_timestamp(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return normalize_utc_timestamp(value, field_name)


def _optional_season(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise P272Error("gameData.game.season must be a four-digit year or null")
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}", value.strip()):
        season = int(value.strip())
    elif isinstance(value, int):
        season = value
    else:
        raise P272Error("gameData.game.season must be a four-digit year or null")
    if season < 1800 or season > 9999:
        raise P272Error("gameData.game.season is outside the accepted year range")
    return season


def _score_candidates(root: Mapping[str, Any], side: str) -> list[int]:
    candidates: list[int] = []
    game_data = _require_mapping(root.get("gameData"), "gameData")
    teams = _require_mapping(game_data.get("teams"), "gameData.teams")
    team = _require_mapping(teams.get(side), f"gameData.teams.{side}")
    if team.get("score") is not None:
        candidates.append(
            _strict_nonnegative_int(team["score"], f"gameData.teams.{side}.score")
        )

    live_data = root.get("liveData")
    if live_data is not None:
        live = _require_mapping(live_data, "liveData")
        linescore = live.get("linescore")
        if linescore is not None:
            linescore_obj = _require_mapping(linescore, "liveData.linescore")
            line_teams = linescore_obj.get("teams")
            if line_teams is not None:
                line_team_map = _require_mapping(line_teams, "liveData.linescore.teams")
                line_side = line_team_map.get(side)
                if line_side is not None:
                    line_side_obj = _require_mapping(
                        line_side, f"liveData.linescore.teams.{side}"
                    )
                    if line_side_obj.get("runs") is not None:
                        candidates.append(
                            _strict_nonnegative_int(
                                line_side_obj["runs"],
                                f"liveData.linescore.teams.{side}.runs",
                            )
                        )

        boxscore = live.get("boxscore")
        if boxscore is not None:
            boxscore_obj = _require_mapping(boxscore, "liveData.boxscore")
            box_teams = boxscore_obj.get("teams")
            if box_teams is not None:
                box_team_map = _require_mapping(box_teams, "liveData.boxscore.teams")
                box_side = box_team_map.get(side)
                if box_side is not None:
                    box_side_obj = _require_mapping(
                        box_side, f"liveData.boxscore.teams.{side}"
                    )
                    team_stats = box_side_obj.get("teamStats")
                    if team_stats is not None:
                        stats_obj = _require_mapping(
                            team_stats, f"liveData.boxscore.teams.{side}.teamStats"
                        )
                        batting = stats_obj.get("batting")
                        if batting is not None:
                            batting_obj = _require_mapping(
                                batting,
                                f"liveData.boxscore.teams.{side}.teamStats.batting",
                            )
                            if batting_obj.get("runs") is not None:
                                candidates.append(
                                    _strict_nonnegative_int(
                                        batting_obj["runs"],
                                        "liveData.boxscore.teams."
                                        f"{side}.teamStats.batting.runs",
                                    )
                                )
    return candidates


def _resolved_score(root: Mapping[str, Any], side: str) -> int | None:
    candidates = _score_candidates(root, side)
    distinct = set(candidates)
    if len(distinct) > 1:
        raise P272Error(f"Conflicting official {side} score evidence")
    return next(iter(distinct)) if distinct else None


def _source_fingerprint(record: Mapping[str, Any]) -> str:
    source_identity = {
        "official_game_pk": record["official_game_pk"],
        "raw_sha256": record["raw_sha256"],
        "source_endpoint_id": record["source_endpoint_id"],
        "source_name": record["source_name"],
        "source_observed_at_utc": record["source_observed_at_utc"],
    }
    return sha256_bytes(canonical_json_bytes(source_identity))


def _record_fingerprint(record: Mapping[str, Any]) -> str:
    logical_record = {
        key: value for key, value in record.items() if key != "record_fingerprint"
    }
    return sha256_bytes(canonical_json_bytes(logical_record))


def build_observation_record(
    raw: bytes,
    game_pk: int,
    source_observed_at_utc: str,
    *,
    expected_away_team: str | None = None,
    expected_home_team: str | None = None,
) -> dict[str, Any]:
    """Build one logical observation from exact official response bytes."""
    requested_game_pk = _strict_positive_int(game_pk, "gamePk")
    observed_at = normalize_utc_timestamp(
        source_observed_at_utc, "source_observed_at_utc"
    )
    if (expected_away_team is None) != (expected_home_team is None):
        raise P272Error("Expected away and home teams must be supplied together")

    root = _parse_official_json(raw)
    game_data = _require_mapping(root.get("gameData"), "gameData")
    game = _require_mapping(game_data.get("game"), "gameData.game")
    official_game_pk = _strict_positive_int(game.get("pk"), "gameData.game.pk")
    if official_game_pk != requested_game_pk:
        raise P272Error(
            f"Official game identity mismatch: requested {requested_game_pk}, "
            f"observed {official_game_pk}"
        )
    top_level_pk = root.get("gamePk")
    if top_level_pk is not None:
        parsed_top_level_pk = _strict_positive_int(top_level_pk, "gamePk")
        if parsed_top_level_pk != official_game_pk:
            raise P272Error("Conflicting top-level and nested official game identity")

    away_team, away_team_id = _extract_team_identity(root, game_data, "away")
    home_team, home_team_id = _extract_team_identity(root, game_data, "home")
    if away_team_id is not None and home_team_id is not None and away_team_id == home_team_id:
        raise P272Error("Official away and home team identities conflict")
    if expected_away_team is not None and expected_home_team is not None:
        validate_expected_team(away_team, expected_away_team, "away_team")
        validate_expected_team(home_team, expected_home_team, "home_team")

    status_payload = _require_mapping(game_data.get("status"), "gameData.status")
    official_status = resolve_official_status(status_payload)
    status_reason = _optional_string(
        status_payload.get("reason"), "gameData.status.reason"
    )
    datetime_payload = game_data.get("datetime")
    if datetime_payload is None:
        scheduled_start = None
    else:
        datetime_obj = _require_mapping(datetime_payload, "gameData.datetime")
        scheduled_start = _optional_timestamp(
            datetime_obj.get("dateTime"), "gameData.datetime.dateTime"
        )
    season = _optional_season(game.get("season"))

    away_score_candidate = _resolved_score(root, "away")
    home_score_candidate = _resolved_score(root, "home")
    if official_status in RESOLVED_STATUSES:
        away_score = away_score_candidate
        home_score = home_score_candidate
        result_available = observed_at
    else:
        away_score = None
        home_score = None
        result_available = None

    game_id = (
        f"mlb_{season}_{official_game_pk}"
        if season is not None
        else f"mlb_{official_game_pk}"
    )
    required_logical_values = [season, scheduled_start, away_team, home_team]
    if official_status in RESOLVED_STATUSES:
        required_logical_values.extend([away_score, home_score])
    provenance_status = (
        "COMPLETE" if all(value is not None for value in required_logical_values) else "INCOMPLETE"
    )

    record: dict[str, Any] = {
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "game_id": game_id,
        "official_game_pk": official_game_pk,
        "season": season,
        "scheduled_start_utc": scheduled_start,
        "official_status": official_status,
        "status_reason": status_reason,
        "away_team": away_team,
        "home_team": home_team,
        "away_score": away_score,
        "home_score": home_score,
        "source_name": SOURCE_NAME,
        "source_endpoint_id": SOURCE_ENDPOINT_ID,
        "source_observed_at_utc": observed_at,
        "result_available_at_utc": result_available,
        "raw_sha256": sha256_bytes(raw),
        "source_fingerprint": None,
        "record_fingerprint": None,
        "provenance_status": provenance_status,
    }
    record["source_fingerprint"] = _source_fingerprint(record)
    record["record_fingerprint"] = _record_fingerprint(record)
    normalized = normalize_nfc(record)
    validate_observation_record(normalized)
    return normalized


def validate_observation_record(record: Mapping[str, Any]) -> None:
    if set(record) != OBSERVATION_FIELDS:
        missing = sorted(OBSERVATION_FIELDS - set(record))
        extra = sorted(set(record) - OBSERVATION_FIELDS)
        raise P272Error(f"Observation schema mismatch; missing={missing}, extra={extra}")
    if record["observation_contract_version"] != OBSERVATION_CONTRACT_VERSION:
        raise P272Error("Unexpected observation_contract_version")

    official_game_pk = _strict_positive_int(record["official_game_pk"], "official_game_pk")
    season = record["season"]
    if season is not None:
        season = _optional_season(season)
    expected_game_id = (
        f"mlb_{season}_{official_game_pk}" if season is not None else f"mlb_{official_game_pk}"
    )
    if record["game_id"] != expected_game_id:
        raise P272Error("game_id does not match the official game identity")

    status = record["official_status"]
    if status not in ALLOWED_STATUSES:
        raise P272Error(f"official_status is not allowed: {status!r}")
    if record["source_name"] != SOURCE_NAME:
        raise P272Error("source_name is not the approved official source")
    if record["source_endpoint_id"] != SOURCE_ENDPOINT_ID:
        raise P272Error("source_endpoint_id is not the approved endpoint")

    observed_at = normalize_utc_timestamp(
        record["source_observed_at_utc"], "source_observed_at_utc"
    )
    if observed_at != record["source_observed_at_utc"]:
        raise P272Error("source_observed_at_utc is not in canonical UTC form")
    scheduled_start = record["scheduled_start_utc"]
    if scheduled_start is not None:
        normalized_start = normalize_utc_timestamp(scheduled_start, "scheduled_start_utc")
        if normalized_start != scheduled_start:
            raise P272Error("scheduled_start_utc is not in canonical UTC form")

    result_available = record["result_available_at_utc"]
    if status in RESOLVED_STATUSES:
        if result_available != observed_at:
            raise P272Error(
                "FINAL/FORFEIT result availability must equal the observation timestamp"
            )
    elif result_available is not None:
        raise P272Error("Non-final result availability must remain null")

    for field in ("away_team", "home_team"):
        _team_code(record[field], field)
    if record["status_reason"] is not None and not isinstance(record["status_reason"], str):
        raise P272Error("status_reason must be a string or null")
    for field in ("away_score", "home_score"):
        if record[field] is not None:
            _strict_nonnegative_int(record[field], field)
    if status not in RESOLVED_STATUSES and (
        record["away_score"] is not None or record["home_score"] is not None
    ):
        raise P272Error("Non-final observations must not expose partial scores as results")

    provenance = record["provenance_status"]
    if provenance not in ALLOWED_PROVENANCE_STATUSES:
        raise P272Error("provenance_status is not allowed")
    if provenance == "COMPLETE":
        required = [season, scheduled_start, record["away_team"], record["home_team"]]
        if status in RESOLVED_STATUSES:
            required.extend([record["away_score"], record["home_score"]])
        if any(value is None for value in required):
            raise P272Error("COMPLETE provenance is missing required official evidence")

    for field in ("raw_sha256", "source_fingerprint", "record_fingerprint"):
        if not _is_sha256(record[field]):
            raise P272Error(f"{field} must be a lowercase SHA-256")
    if record["source_fingerprint"] != _source_fingerprint(record):
        raise P272Error("source_fingerprint does not match canonical source evidence")
    if record["record_fingerprint"] != _record_fingerprint(record):
        raise P272Error("record_fingerprint does not match canonical record content")


def _raw_relative_path(record: Mapping[str, Any]) -> str:
    return f"raw/{record['game_id']}.feed.live.json"


def build_bundle_bytes(raw: bytes, record: Mapping[str, Any]) -> dict[str, bytes]:
    """Build the complete deterministic four-file observation bundle in memory."""
    validate_observation_record(record)
    if sha256_bytes(raw) != record["raw_sha256"]:
        raise P272Error("Raw response bytes do not match observation raw_sha256")
    raw_relative_path = _raw_relative_path(record)
    observation_bytes = canonical_json_bytes(record, trailing_newline=True)
    source_index = {
        "source_index_contract_version": SOURCE_INDEX_CONTRACT_VERSION,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "game_id": record["game_id"],
        "official_game_pk": record["official_game_pk"],
        "source_name": SOURCE_NAME,
        "source_endpoint_id": SOURCE_ENDPOINT_ID,
        "source_observed_at_utc": record["source_observed_at_utc"],
        "relative_raw_path": raw_relative_path,
        "relative_observation_path": OBSERVATION_FILENAME,
        "raw_sha256": record["raw_sha256"],
        "source_fingerprint": record["source_fingerprint"],
        "record_fingerprint": record["record_fingerprint"],
        "provenance_status": record["provenance_status"],
    }
    if set(source_index) != SOURCE_INDEX_FIELDS:
        raise P272Error("Internal source index schema mismatch")
    source_index_bytes = canonical_json_bytes(source_index, trailing_newline=True)
    artifacts = {
        raw_relative_path: raw,
        OBSERVATION_FILENAME: observation_bytes,
        SOURCE_INDEX_FILENAME: source_index_bytes,
    }
    checksum_lines = [
        f"{sha256_bytes(artifacts[path])}  {path}" for path in sorted(artifacts)
    ]
    artifacts[CHECKSUM_FILENAME] = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    return artifacts


FilesystemIdentity = tuple[int, int]
WrittenArtifact = tuple[int, str, FilesystemIdentity]

CLEANUP_NOT_NEEDED = "CLEANUP_NOT_NEEDED"
CLEANUP_RETAINED_IDENTITY_UNCERTAIN = "CLEANUP_RETAINED_IDENTITY_UNCERTAIN"
CLEANUP_RETAINED_REPLACED = "CLEANUP_RETAINED_REPLACED"
CLEANUP_FAILED = "CLEANUP_FAILED"


def _filesystem_identity(metadata: os.stat_result) -> FilesystemIdentity:
    return metadata.st_dev, metadata.st_ino


def _require_secure_filesystem_support() -> None:
    required_flags = ("O_NOFOLLOW", "O_DIRECTORY", "O_EXCL")
    missing_flags = [name for name in required_flags if not hasattr(os, name)]
    required_dir_fd = (os.open, os.stat, os.mkdir)
    missing_dir_fd = [
        function.__name__
        for function in required_dir_fd
        if function not in os.supports_dir_fd
    ]
    if (
        missing_flags
        or missing_dir_fd
        or os.stat not in os.supports_follow_symlinks
        or os.listdir not in os.supports_fd
        or not hasattr(os, "geteuid")
        or sys.platform not in {"darwin", "linux"}
    ):
        raise P272Error(
            "Secure dirfd/no-follow bundle containment is unavailable; "
            f"missing_flags={missing_flags}, missing_dir_fd={missing_dir_fd}"
        )


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _file_read_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _file_create_flags() -> int:
    return (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _validate_component(name: str, label: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise P272Error(f"{label} must be one safe relative path component")
    return name


def _validate_bundle_relative_path(relative_path: str) -> tuple[str, ...]:
    if not isinstance(relative_path, str) or not relative_path:
        raise P272Error("Bundle relative path must be a non-empty string")
    if relative_path.startswith(("/", "\\")) or "\\" in relative_path:
        raise P272Error(f"Bundle relative path must not be absolute: {relative_path!r}")
    parts = tuple(relative_path.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise P272Error(f"Bundle relative path traversal is forbidden: {relative_path!r}")
    for part in parts:
        _validate_component(part, "Bundle relative path component")
    return parts


def _validated_artifacts(artifacts: Mapping[str, bytes]) -> dict[str, bytes]:
    copied: dict[str, bytes] = {}
    for relative_path, data in artifacts.items():
        _validate_bundle_relative_path(relative_path)
        if not isinstance(data, bytes):
            raise P272Error(f"Bundle artifact must be exact bytes: {relative_path}")
        copied[relative_path] = data

    if set(copied) & {OBSERVATION_FILENAME, SOURCE_INDEX_FILENAME, CHECKSUM_FILENAME} != {
        OBSERVATION_FILENAME,
        SOURCE_INDEX_FILENAME,
        CHECKSUM_FILENAME,
    }:
        raise P272Error("Bundle inventory is missing a required root artifact")

    observation_bytes = copied[OBSERVATION_FILENAME]
    try:
        parsed_record = json.loads(observation_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P272Error("Bundle observation artifact must be valid UTF-8 JSON") from exc
    record = _require_mapping(parsed_record, "bundle observation")
    validate_observation_record(record)
    if canonical_json_bytes(record, trailing_newline=True) != observation_bytes:
        raise P272Error("Bundle observation artifact is not canonical JSON")

    raw_relative_path = _raw_relative_path(record)
    expected_paths = {
        raw_relative_path,
        OBSERVATION_FILENAME,
        SOURCE_INDEX_FILENAME,
        CHECKSUM_FILENAME,
    }
    if set(copied) != expected_paths:
        raise P272Error(
            "Bundle inventory must contain exactly the four deterministic artifacts"
        )
    rebuilt = build_bundle_bytes(copied[raw_relative_path], record)
    if copied != rebuilt:
        raise P272Error("Bundle artifacts are not internally valid and byte-consistent")
    return copied


def _split_output_root(output_root: Path) -> tuple[bool, list[str], str]:
    raw_path = os.fspath(output_root)
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        raise P272Error("Output root must be a non-empty filesystem path")
    raw_parts = raw_path.split(os.sep)
    if ".." in raw_parts:
        raise P272Error("Output root path traversal is forbidden")
    absolute = os.path.isabs(raw_path)
    components = [part for part in raw_parts if part not in {"", "."}]
    if not components:
        raise P272Error("Output root must name a bundle below an existing parent")
    for component in components:
        _validate_component(component, "Output root component")
    return absolute, components[:-1], components[-1]


def _validate_trusted_directory(
    directory_fd: int, label: str
) -> tuple[os.stat_result, FilesystemIdentity]:
    metadata = os.fstat(directory_fd)
    if not stat.S_ISDIR(metadata.st_mode):
        raise P272Error(f"{label} must remain a directory")
    if metadata.st_uid != os.geteuid():
        raise P272Error(f"{label} must be owned by the effective user")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise P272Error(f"{label} must not be group/world writable")
    return metadata, _filesystem_identity(metadata)


def _open_publication_parent(output_root: Path) -> tuple[int, str]:
    absolute, parent_components, final_name = _split_output_root(output_root)
    try:
        current_fd = os.open("/" if absolute else ".", _directory_open_flags())
    except OSError as exc:
        raise P272Error("Unable to securely open the output-root anchor") from exc
    try:
        for component in parent_components:
            try:
                next_fd = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=current_fd,
                )
            except OSError as exc:
                raise P272Error(
                    "Output-root parent component is a symlink or cannot be securely opened: "
                    f"{component}"
                ) from exc
            os.close(current_fd)
            current_fd = next_fd
        _validate_trusted_directory(current_fd, "Publication parent")
        return current_fd, final_name
    except BaseException:
        os.close(current_fd)
        raise


def _stat_name_no_follow(directory_fd: int, name: str, label: str) -> os.stat_result:
    _validate_component(name, label)
    try:
        return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise P272Error(f"{label} disappeared or was replaced") from exc
    except OSError as exc:
        raise P272Error(f"Unable to inspect {label} without following links") from exc


def _assert_named_directory_identity(
    parent_fd: int,
    name: str,
    directory_fd: int,
    expected_identity: FilesystemIdentity,
    label: str,
) -> None:
    named_metadata = _stat_name_no_follow(parent_fd, name, label)
    if stat.S_ISLNK(named_metadata.st_mode):
        raise P272Error(f"{label} was replaced by a symlink")
    if not stat.S_ISDIR(named_metadata.st_mode):
        raise P272Error(f"{label} is no longer a directory")
    descriptor_metadata, descriptor_identity = _validate_trusted_directory(
        directory_fd, label
    )
    if (
        _filesystem_identity(named_metadata) != expected_identity
        or descriptor_identity != expected_identity
        or named_metadata.st_uid != descriptor_metadata.st_uid
    ):
        raise P272Error(f"{label} directory identity changed")


def _open_named_directory(
    parent_fd: int, name: str, label: str
) -> tuple[int, FilesystemIdentity]:
    metadata = _stat_name_no_follow(parent_fd, name, label)
    if stat.S_ISLNK(metadata.st_mode):
        raise P272Error(f"{label} may not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise P272Error(f"{label} must be a directory")
    try:
        directory_fd = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
    except OSError as exc:
        raise P272Error(f"{label} cannot be securely opened without following links") from exc
    try:
        _, identity = _validate_trusted_directory(directory_fd, label)
        _assert_named_directory_identity(parent_fd, name, directory_fd, identity, label)
        return directory_fd, identity
    except BaseException:
        os.close(directory_fd)
        raise


def _read_regular_file_at(directory_fd: int, name: str) -> bytes:
    _validate_component(name, "Bundle filename")
    try:
        file_fd = os.open(name, _file_read_flags(), dir_fd=directory_fd)
    except OSError as exc:
        raise P272Error(f"Bundle file is missing, unsafe, or a symlink: {name}") from exc
    try:
        metadata = os.fstat(file_fd)
        identity = _filesystem_identity(metadata)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise P272Error(f"Bundle file must be a single-link regular file: {name}")
        if metadata.st_uid != os.geteuid() or metadata.st_mode & (
            stat.S_IWGRP | stat.S_IWOTH
        ):
            raise P272Error(f"Bundle file has an unsafe owner or write mode: {name}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        named_metadata = _stat_name_no_follow(directory_fd, name, f"Bundle file {name}")
        if stat.S_ISLNK(named_metadata.st_mode) or _filesystem_identity(
            named_metadata
        ) != identity:
            raise P272Error(f"Bundle file identity changed while reading: {name}")
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def _write_regular_file_exclusive_at(
    directory_fd: int, name: str, data: bytes
) -> FilesystemIdentity:
    _validate_component(name, "Staged filename")
    file_fd: int | None = None
    identity: FilesystemIdentity | None = None
    try:
        file_fd = os.open(
            name,
            _file_create_flags(),
            0o600,
            dir_fd=directory_fd,
        )
        metadata = os.fstat(file_fd)
        identity = _filesystem_identity(metadata)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise P272Error(f"Staged artifact is not an exclusive regular file: {name}")
        remaining = memoryview(data)
        while remaining:
            written = os.write(file_fd, remaining)
            if written <= 0:
                raise OSError("short staged artifact write")
            remaining = remaining[written:]
        os.fsync(file_fd)
        named_metadata = _stat_name_no_follow(directory_fd, name, f"Staged file {name}")
        if stat.S_ISLNK(named_metadata.st_mode) or _filesystem_identity(
            named_metadata
        ) != identity:
            raise P272Error(f"Staged file identity changed while writing: {name}")
        return identity
    except BaseException:
        # Never use a pathname to remove this file after a failed write.  The
        # name can be replaced after its identity is checked, while an open
        # regular-file descriptor has no portable unlink-by-identity primitive.
        # The caller retains the hidden staging directory and reports that
        # outcome rather than risking a replacement entry.
        raise
    finally:
        if file_fd is not None:
            os.close(file_fd)


def _write_bundle_artifact(
    staging_fd: int,
    raw_fd: int,
    relative_path: str,
    data: bytes,
) -> WrittenArtifact:
    parts = _validate_bundle_relative_path(relative_path)
    if len(parts) == 1:
        directory_fd, name = staging_fd, parts[0]
    elif len(parts) == 2 and parts[0] == "raw":
        directory_fd, name = raw_fd, parts[1]
    else:
        raise P272Error(f"Unsupported staged bundle path: {relative_path}")
    identity = _write_regular_file_exclusive_at(directory_fd, name, data)
    return directory_fd, name, identity


def _scan_directory(directory_fd: int, label: str) -> set[str]:
    try:
        names = set(os.listdir(directory_fd))
    except OSError as exc:
        raise P272Error(f"Unable to inventory {label} through its retained descriptor") from exc
    for name in names:
        _validate_component(name, f"{label} entry")
        metadata = _stat_name_no_follow(directory_fd, name, f"{label} entry {name}")
        if stat.S_ISLNK(metadata.st_mode):
            raise P272Error(f"{label} entry may not be a symlink: {name}")
        if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
            raise P272Error(f"{label} contains an unsupported filesystem entry: {name}")
    return names


def _verify_bundle_contents(
    bundle_fd: int,
    raw_fd: int,
    artifacts: Mapping[str, bytes],
    *,
    existing: bool,
) -> None:
    raw_relative_path = next(path for path in artifacts if path.startswith("raw/"))
    raw_name = raw_relative_path.split("/", 1)[1]
    expected_root = {
        OBSERVATION_FILENAME,
        SOURCE_INDEX_FILENAME,
        CHECKSUM_FILENAME,
        "raw",
    }
    root_names = _scan_directory(bundle_fd, "Bundle")
    raw_names = _scan_directory(raw_fd, "Bundle raw directory")
    if root_names != expected_root or raw_names != {raw_name}:
        raise P272Error(
            "Existing bundle is partial or invalid; bundle inventory differs from "
            "the deterministic four-file contract"
        )

    for relative_path, expected_bytes in artifacts.items():
        parts = relative_path.split("/")
        if len(parts) == 1:
            observed_bytes = _read_regular_file_at(bundle_fd, parts[0])
        else:
            observed_bytes = _read_regular_file_at(raw_fd, parts[1])
        if observed_bytes != expected_bytes:
            if existing:
                raise P272Error(
                    "Existing bundle differs; write-once overwrite refused: "
                    f"{relative_path}"
                )
            raise P272Error(f"Staged bundle verification failed: {relative_path}")


def _verify_existing_bundle(
    parent_fd: int,
    final_name: str,
    artifacts: Mapping[str, bytes],
) -> bool:
    try:
        metadata = os.stat(final_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise P272Error("Unable to inspect the final bundle path safely") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise P272Error("Final output root may not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise P272Error("Final output root must be a real directory")

    bundle_fd, bundle_identity = _open_named_directory(
        parent_fd, final_name, "Final bundle"
    )
    raw_fd: int | None = None
    try:
        try:
            raw_fd, raw_identity = _open_named_directory(
                bundle_fd, "raw", "Final bundle raw directory"
            )
        except P272Error as exc:
            raise P272Error(
                "Existing bundle is partial, invalid, or contains a raw symlink"
            ) from exc
        _verify_bundle_contents(bundle_fd, raw_fd, artifacts, existing=True)
        _assert_named_directory_identity(
            bundle_fd,
            "raw",
            raw_fd,
            raw_identity,
            "Final bundle raw directory",
        )
        _assert_named_directory_identity(
            parent_fd,
            final_name,
            bundle_fd,
            bundle_identity,
            "Final bundle",
        )
        return True
    finally:
        if raw_fd is not None:
            os.close(raw_fd)
        os.close(bundle_fd)


def _verify_staging_before_publish(
    parent_fd: int,
    staging_name: str,
    staging_fd: int,
    staging_identity: FilesystemIdentity,
    raw_fd: int,
    raw_identity: FilesystemIdentity,
    artifacts: Mapping[str, bytes],
) -> None:
    _assert_named_directory_identity(
        parent_fd,
        staging_name,
        staging_fd,
        staging_identity,
        "Staging directory",
    )
    _assert_named_directory_identity(
        staging_fd,
        "raw",
        raw_fd,
        raw_identity,
        "Staging raw directory",
    )
    _verify_bundle_contents(staging_fd, raw_fd, artifacts, existing=False)
    _assert_named_directory_identity(
        staging_fd,
        "raw",
        raw_fd,
        raw_identity,
        "Staging raw directory",
    )
    _assert_named_directory_identity(
        parent_fd,
        staging_name,
        staging_fd,
        staging_identity,
        "Staging directory",
    )


def _atomic_publish_noreplace(
    parent_fd: int, staging_name: str, final_name: str
) -> bool:
    """Publish one directory atomically; False means the destination already exists."""
    _validate_component(staging_name, "Staging directory name")
    _validate_component(final_name, "Final bundle name")
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        try:
            rename_function = library.renameatx_np
        except AttributeError as exc:
            raise P272Error("Atomic no-replace directory publication is unavailable") from exc
        rename_function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_function.restype = ctypes.c_int
        flags = 0x00000004 | 0x00000010  # RENAME_EXCL | RENAME_NOFOLLOW_ANY
    elif sys.platform == "linux":
        try:
            rename_function = library.renameat2
        except AttributeError as exc:
            raise P272Error("Atomic no-replace directory publication is unavailable") from exc
        rename_function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename_function.restype = ctypes.c_int
        flags = 0x00000001  # RENAME_NOREPLACE
    else:
        raise P272Error("Atomic no-replace directory publication is unsupported")

    ctypes.set_errno(0)
    result = rename_function(
        parent_fd,
        os.fsencode(staging_name),
        parent_fd,
        os.fsencode(final_name),
        flags,
    )
    if result == 0:
        return True
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        return False
    unsupported_errors = {
        errno.EINVAL,
        errno.ENOSYS,
        getattr(errno, "ENOTSUP", errno.EINVAL),
        getattr(errno, "EOPNOTSUPP", errno.EINVAL),
    }
    if error_number in unsupported_errors:
        raise P272Error(
            "Filesystem does not support safe atomic no-replace directory publication"
        )
    raise P272Error(
        "Atomic no-replace directory publication failed: "
        f"{os.strerror(error_number)}"
    )


def _cleanup_owned_staging(
    parent_fd: int,
    staging_name: str,
    staging_fd: int,
    staging_identity: FilesystemIdentity,
    raw_fd: int | None,
    raw_identity: FilesystemIdentity | None,
    written_artifacts: Sequence[WrittenArtifact],
) -> str:
    """Fail closed by retaining a failed staging entry instead of deleting by name.

    POSIX exposes unlink/rmdir only by mutable pathname.  A descriptor and a
    matching pre-delete stat cannot bind either operation to the originally
    created object, so no pathname cleanup is safe here.  The unused raw and
    artifact arguments intentionally preserve the cleanup-call contract and
    make the retention boundary explicit at every former cleanup site.
    """
    del raw_fd, raw_identity, written_artifacts
    try:
        _, descriptor_identity = _validate_trusted_directory(
            staging_fd, "Retained staging directory"
        )
    except (OSError, P272Error):
        return CLEANUP_FAILED

    if descriptor_identity != staging_identity:
        return CLEANUP_FAILED

    try:
        named_metadata = _stat_name_no_follow(
            parent_fd, staging_name, "Retained staging directory"
        )
    except P272Error:
        return CLEANUP_RETAINED_REPLACED

    if (
        stat.S_ISLNK(named_metadata.st_mode)
        or not stat.S_ISDIR(named_metadata.st_mode)
        or _filesystem_identity(named_metadata) != staging_identity
    ):
        return CLEANUP_RETAINED_REPLACED
    return CLEANUP_RETAINED_IDENTITY_UNCERTAIN


def write_bundle(output_root: Path, artifacts: Mapping[str, bytes]) -> str:
    """Stage a complete immutable bundle and expose it with one no-replace rename."""
    _require_secure_filesystem_support()
    expected_artifacts = _validated_artifacts(artifacts)
    parent_fd, final_name = _open_publication_parent(Path(output_root))
    staging_fd: int | None = None
    raw_fd: int | None = None
    staging_identity: FilesystemIdentity | None = None
    raw_identity: FilesystemIdentity | None = None
    staging_name: str | None = None
    written_artifacts: list[WrittenArtifact] = []
    published = False
    state: str | None = None
    failure: BaseException | None = None
    cleanup_outcome = CLEANUP_NOT_NEEDED
    try:
        if _verify_existing_bundle(parent_fd, final_name, expected_artifacts):
            state = "VERIFIED_IDENTICAL"
        else:
            staging_name = f".{final_name}.p272-stage-{secrets.token_hex(12)}"
            try:
                name_limit = os.fpathconf(parent_fd, "PC_NAME_MAX")
            except (OSError, ValueError):
                name_limit = 255
            if len(os.fsencode(staging_name)) > name_limit:
                raise P272Error("Output bundle name is too long for safe hidden staging")
            try:
                os.mkdir(staging_name, mode=0o700, dir_fd=parent_fd)
                staging_fd, staging_identity = _open_named_directory(
                    parent_fd, staging_name, "Staging directory"
                )
                os.mkdir("raw", mode=0o700, dir_fd=staging_fd)
                raw_fd, raw_identity = _open_named_directory(
                    staging_fd, "raw", "Staging raw directory"
                )
            except OSError as exc:
                raise P272Error("Unable to create secure hidden bundle staging") from exc

            write_order = sorted(
                set(expected_artifacts) - {CHECKSUM_FILENAME}
            ) + [CHECKSUM_FILENAME]
            for relative_path in write_order:
                try:
                    written = _write_bundle_artifact(
                        staging_fd,
                        raw_fd,
                        relative_path,
                        expected_artifacts[relative_path],
                    )
                except OSError as exc:
                    raise P272Error(
                        f"Bundle staging write failed before publication: {relative_path}"
                    ) from exc
                written_artifacts.append(written)

            _verify_staging_before_publish(
                parent_fd,
                staging_name,
                staging_fd,
                staging_identity,
                raw_fd,
                raw_identity,
                expected_artifacts,
            )
            os.fsync(raw_fd)
            os.fsync(staging_fd)
            os.fsync(parent_fd)

            did_publish = _atomic_publish_noreplace(parent_fd, staging_name, final_name)
            if not did_publish:
                if _verify_existing_bundle(parent_fd, final_name, expected_artifacts):
                    state = "VERIFIED_IDENTICAL"
                else:
                    raise P272Error("Concurrent bundle publication collision failed closed")
            else:
                published = True
                _assert_named_directory_identity(
                    parent_fd,
                    final_name,
                    staging_fd,
                    staging_identity,
                    "Published final bundle",
                )
                _assert_named_directory_identity(
                    staging_fd,
                    "raw",
                    raw_fd,
                    raw_identity,
                    "Published final raw directory",
                )
                _verify_bundle_contents(
                    staging_fd, raw_fd, expected_artifacts, existing=False
                )
                os.fsync(parent_fd)
                state = "CREATED"
    except BaseException as exc:
        failure = exc
    finally:
        if (
            not published
            and staging_name is not None
            and staging_fd is not None
            and staging_identity is not None
        ):
            cleanup_outcome = _cleanup_owned_staging(
                parent_fd,
                staging_name,
                staging_fd,
                staging_identity,
                raw_fd,
                raw_identity,
                written_artifacts,
            )
        if raw_fd is not None:
            os.close(raw_fd)
        if staging_fd is not None:
            os.close(staging_fd)
        os.close(parent_fd)

    if failure is not None:
        detail = f"Publication failure: {failure}; cleanup={cleanup_outcome}"
        if staging_name is not None and staging_fd is not None:
            detail += f"; retained_staging={staging_name}"
        if isinstance(failure, P272Error):
            raise P272Error(detail) from failure
        raise failure
    if cleanup_outcome != CLEANUP_NOT_NEEDED:
        raise P272Error(
            "Publication was not accepted as successful because staging cleanup was retained: "
            f"bundle_state={state}; cleanup={cleanup_outcome}; "
            f"retained_staging={staging_name}"
        )
    if state is None:
        raise P272Error("Bundle publication produced no state")
    return state


def validate_official_request(
    url: str, game_pk: int, headers: Mapping[str, str]
) -> None:
    """Enforce the exact unauthenticated official MLB request boundary."""
    requested_game_pk = _strict_positive_int(game_pk, "gamePk")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise P272Error("Official endpoint URL is malformed") from exc
    if parsed.scheme.lower() != "https":
        raise P272Error("Official endpoint must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise P272Error("URL userinfo/authentication is forbidden")
    if parsed.hostname is None or parsed.hostname.lower() != OFFICIAL_HOST:
        raise P272Error("Only the official statsapi.mlb.com host is allowed")
    if port is not None:
        raise P272Error("Custom endpoint ports are forbidden")
    expected_path = f"/api/v1.1/game/{requested_game_pk}/feed/live"
    if parsed.path != expected_path or parsed.query or parsed.fragment:
        raise P272Error("Endpoint must be the exact one-game MLB live-feed path")

    normalized_headers = {name.strip().lower(): value for name, value in headers.items()}
    if set(normalized_headers) != {"accept", "user-agent"}:
        raise P272Error("Authentication, cookies, credentials, and extra headers are forbidden")
    if normalized_headers["accept"] != "application/json":
        raise P272Error("Official request Accept header must be application/json")
    if normalized_headers["user-agent"] != USER_AGENT:
        raise P272Error("Official request User-Agent is fixed by the recorder contract")


def build_official_request(
    game_pk: int,
    *,
    url: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> urllib.request.Request:
    requested_game_pk = _strict_positive_int(game_pk, "gamePk")
    endpoint = url or OFFICIAL_ENDPOINT_TEMPLATE.format(game_pk=requested_game_pk)
    request_headers = dict(
        headers or {"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    validate_official_request(endpoint, requested_game_pk, request_headers)
    return urllib.request.Request(endpoint, headers=request_headers, method="GET")


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject every redirect response before urllib can issue a second request."""

    def _reject_redirect(self, request, response, code, message, headers):
        try:
            response.close()
        finally:
            raise P272Error(
                f"Official MLB redirect status {code} rejected; redirects are forbidden"
            )

    http_error_301 = _reject_redirect
    http_error_302 = _reject_redirect
    http_error_303 = _reject_redirect
    http_error_307 = _reject_redirect
    http_error_308 = _reject_redirect


def _build_official_opener() -> urllib.request.OpenerDirector:
    """Build a direct, cookie-free, auth-free opener with redirects disabled."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RejectRedirectHandler(),
        urllib.request.HTTPSHandler(),
    )


def _validate_effective_response_url(url: Any, game_pk: int) -> None:
    if not isinstance(url, str):
        raise P272Error("Official MLB effective response URL is missing")
    try:
        validate_official_request(
            url,
            game_pk,
            {"Accept": "application/json", "User-Agent": USER_AGENT},
        )
    except P272Error as exc:
        raise P272Error(
            "Official MLB effective response URL escaped the approved boundary"
        ) from exc


def fetch_official_response_once(game_pk: int) -> tuple[bytes, str]:
    """Perform exactly one request and timestamp after the complete body is read."""
    request = build_official_request(game_pk)
    opener = _build_official_opener()
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = int(response.getcode())
            _validate_effective_response_url(response.geturl(), game_pk)
            content_type = response.headers.get("Content-Type")
            if status != 200:
                raise P272Error(
                    f"Official MLB response status must be 200, observed {status}"
                )
            if not content_type or not content_type.lower().startswith("application/json"):
                raise P272Error(
                    "Official MLB response Content-Type must be application/json"
                )
            raw = response.read()
        observed_at = utc_now()
    except urllib.error.HTTPError as exc:
        if exc.code in {301, 302, 303, 307, 308}:
            raise P272Error(
                f"Official MLB redirect status {exc.code} rejected; redirects are forbidden"
            ) from exc
        raise P272Error(f"Official MLB request failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise P272Error("Official MLB request failed; automatic retry is forbidden") from exc
    return raw, observed_at


def capture(
    *,
    game_pk: int,
    output_root: Path,
    expected_away_team: str | None = None,
    expected_home_team: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Capture one game; intentionally has no caller-supplied timestamp parameter."""
    raw, observed_at = fetch_official_response_once(game_pk)
    record = build_observation_record(
        raw,
        game_pk,
        observed_at,
        expected_away_team=expected_away_team,
        expected_home_team=expected_home_team,
    )
    state = write_bundle(output_root, build_bundle_bytes(raw, record))
    return record, state


def _read_offline_raw_response(source_path: Path) -> bytes:
    path_text = os.fspath(source_path)
    try:
        source_fd = os.open(path_text, _file_read_flags())
    except OSError as exc:
        raise P272Error("--raw-response must be an existing non-symlink regular file") from exc
    try:
        metadata = os.fstat(source_fd)
        identity = _filesystem_identity(metadata)
        if not stat.S_ISREG(metadata.st_mode):
            raise P272Error("--raw-response must be an existing regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        try:
            named_metadata = os.stat(path_text, follow_symlinks=False)
        except OSError as exc:
            raise P272Error("--raw-response identity changed while reading") from exc
        if stat.S_ISLNK(named_metadata.st_mode) or _filesystem_identity(
            named_metadata
        ) != identity:
            raise P272Error("--raw-response identity changed while reading")
        return b"".join(chunks)
    finally:
        os.close(source_fd)


def offline_verify(
    *,
    raw_response: Path,
    game_pk: int,
    observed_at_utc: str,
    output_root: Path,
    expected_away_team: str | None = None,
    expected_home_team: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Build or verify a bundle from already saved bytes without any network call."""
    source_path = Path(raw_response)
    raw = _read_offline_raw_response(source_path)
    record = build_observation_record(
        raw,
        game_pk,
        observed_at_utc,
        expected_away_team=expected_away_team,
        expected_home_team=expected_home_team,
    )
    state = write_bundle(output_root, build_bundle_bytes(raw, record))
    return record, state


def _add_shared_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--game-pk",
        action="append",
        dest="game_pks",
        type=_parse_game_pk_argument,
        required=True,
        help="Exactly one explicit numeric MLB gamePk",
    )
    command.add_argument("--output-root", type=Path, required=True)
    command.add_argument("--expected-away-team")
    command.add_argument("--expected-home-team")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record prospective official MLB result availability for one game"
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    capture_parser = subparsers.add_parser("capture")
    _add_shared_arguments(capture_parser)

    offline_parser = subparsers.add_parser("offline-verify")
    _add_shared_arguments(offline_parser)
    offline_parser.add_argument("--raw-response", type=Path, required=True)
    offline_parser.add_argument("--observed-at-utc", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        game_pk = validate_single_game_pk(args.game_pks)
        if args.mode == "capture":
            record, bundle_state = capture(
                game_pk=game_pk,
                output_root=args.output_root,
                expected_away_team=args.expected_away_team,
                expected_home_team=args.expected_home_team,
            )
        else:
            record, bundle_state = offline_verify(
                raw_response=args.raw_response,
                game_pk=game_pk,
                observed_at_utc=args.observed_at_utc,
                output_root=args.output_root,
                expected_away_team=args.expected_away_team,
                expected_home_team=args.expected_home_team,
            )
    except P272Error as exc:
        print(f"P272_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2

    result = {
        "bundle_state": bundle_state,
        "game_id": record["game_id"],
        "mode": args.mode,
        "official_game_pk": record["official_game_pk"],
        "record_fingerprint": record["record_fingerprint"],
        "source_observed_at_utc": record["source_observed_at_utc"],
    }
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
