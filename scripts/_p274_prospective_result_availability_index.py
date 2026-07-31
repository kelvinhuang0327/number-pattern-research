"""Build and query a deterministic prospective result-availability index.

P274 consumes already-recorded P272 prospective observation bundles.  It is
strictly offline: availability begins at the bundle's recorded local observation
time and is never inferred from feed metadata, filesystem mtimes, or wall time.
Version 1 accepts resolved FINAL/FORFEIT observations only and rejects any claim
of historical, globally-earliest, or retroactive certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


INDEX_SCHEMA_VERSION = "p274-prospective-result-availability-index.v1"
OBSERVATION_CONTRACT_VERSION = "p272-prospective-result-availability.v1"
SOURCE_INDEX_CONTRACT_VERSION = "p272-prospective-source-index.v1"
SOURCE_NAME = "MLB_STATSAPI_GAME_FEED_LIVE"
SOURCE_ENDPOINT_ID = "GET statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"
AVAILABILITY_SEMANTICS = "LOCAL_OBSERVATION_LOWER_BOUND"
RETROACTIVE_CERTIFICATION = False
INDEX_FILENAME = "index.json"
CHECKSUM_FILENAME = "SHA256SUMS"
OBSERVATION_FILENAME = "observation.json"
SOURCE_INDEX_FILENAME = "source_index.json"
RESOLVED_STATUSES = frozenset({"FINAL", "FORFEIT"})

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
RECORD_FIELDS = frozenset(
    {
        "game_id",
        "official_game_pk",
        "source_bundle_root",
        "source_observed_at_utc",
        "result_available_at_utc",
        "official_status",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
        "raw_sha256",
        "observation_sha256",
        "source_index_sha256",
        "manifest_fingerprint",
        "availability_semantics",
        "retroactive_certification",
    }
)
INDEX_FIELDS = frozenset(
    {
        "index_schema_version",
        "record_count",
        "availability_semantics",
        "retroactive_certification",
        "records",
    }
)
FORBIDDEN_CLAIM_TOKENS = ("global", "earliest", "historical", "retroactive")
TEAM_ALIASES = {"ARI": frozenset({"ARI", "AZ"})}


class P274Error(RuntimeError):
    """Fail-closed P274 validation or deterministic-publication error."""


def normalize_nfc(value: Any) -> Any:
    """Recursively normalize JSON strings and keys to Unicode NFC."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise P274Error("Canonical JSON mappings require string keys")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                raise P274Error("Unicode NFC normalization produced a duplicate key")
            result[normalized_key] = normalize_nfc(item)
        return result
    return value


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
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
    return bool(
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value)
    )


def _strict_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise P274Error(f"{field_name} must be a positive integer")
    return value


def _strict_nonnegative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise P274Error(f"{field_name} must be a non-negative integer")
    return value


def parse_canonical_utc(value: Any, field_name: str) -> tuple[str, datetime]:
    """Require the exact canonical UTC form emitted by the P272 contract."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z", value
    ):
        raise P274Error(f"{field_name} must be a canonical timezone-aware UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P274Error(f"{field_name} must be a valid UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise P274Error(f"{field_name} must use UTC")
    normalized = parsed.isoformat().replace("+00:00", "Z")
    if normalized != value:
        raise P274Error(f"{field_name} is not in canonical UTC form")
    return normalized, parsed


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    normalized_keys: set[str] = set()
    for key, value in pairs:
        normalized_key = unicodedata.normalize("NFC", key)
        if normalized_key in normalized_keys:
            raise P274Error("JSON contains duplicate or NFC-equivalent keys")
        normalized_keys.add(normalized_key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise P274Error(f"JSON contains forbidden non-finite value {value}")


def parse_json_bytes(data: bytes, label: str, *, require_canonical: bool) -> Mapping[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P274Error(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise P274Error(f"{label} must contain one JSON object")
    normalized = normalize_nfc(value)
    if require_canonical and data != canonical_json_bytes(normalized, trailing_newline=True):
        raise P274Error(f"{label} must use canonical JSON with one trailing newline")
    return normalized


def _logical_bundle_root(bundle_root: Path) -> str:
    text = os.fspath(bundle_root)
    if not text or "\\" in text:
        raise P274Error("--bundle-root must be a non-empty POSIX relative path")
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise P274Error("--bundle-root must be a canonical relative path without traversal")
    normalized = pure.as_posix()
    if normalized != text.rstrip("/"):
        raise P274Error("--bundle-root must be a canonical relative path")
    return normalized


def _require_regular_file(path: Path, label: str) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise P274Error(f"Partial bundle: missing {label}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise P274Error(f"{label} must be a non-symlink regular file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise P274Error(f"Unable to read {label}") from exc


def _validate_bundle_inventory(bundle_root: Path) -> str:
    logical_root = _logical_bundle_root(bundle_root)
    try:
        root_metadata = bundle_root.lstat()
    except OSError as exc:
        raise P274Error("Bundle root does not exist") from exc
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        raise P274Error("Bundle root must be a non-symlink directory")
    try:
        root_names = {entry.name for entry in bundle_root.iterdir()}
    except OSError as exc:
        raise P274Error("Unable to inventory bundle root") from exc
    expected_root_names = {
        CHECKSUM_FILENAME,
        OBSERVATION_FILENAME,
        SOURCE_INDEX_FILENAME,
        "raw",
    }
    if root_names != expected_root_names:
        raise P274Error(
            "Partial or unexpected bundle inventory; "
            f"missing={sorted(expected_root_names - root_names)}, "
            f"extra={sorted(root_names - expected_root_names)}"
        )
    raw_root = bundle_root / "raw"
    raw_metadata = raw_root.lstat()
    if stat.S_ISLNK(raw_metadata.st_mode) or not stat.S_ISDIR(raw_metadata.st_mode):
        raise P274Error("Bundle raw entry must be a non-symlink directory")
    raw_names = [entry.name for entry in raw_root.iterdir()]
    if len(raw_names) != 1:
        raise P274Error("Partial or unexpected bundle: raw must contain exactly one file")
    _require_regular_file(raw_root / raw_names[0], f"raw/{raw_names[0]}")
    return logical_root


def _parse_checksum_manifest(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise P274Error("SHA256SUMS must be UTF-8") from exc
    if not text.endswith("\n") or "\r" in text:
        raise P274Error("SHA256SUMS must use canonical LF-terminated lines")
    lines = text.splitlines()
    entries: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\x00\r\n]+)", line)
        if match is None:
            raise P274Error("Invalid SHA256SUMS entry")
        digest, relative_path = match.groups()
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise P274Error("SHA256SUMS contains an unsafe relative path")
        if relative_path in entries:
            raise P274Error("SHA256SUMS contains a duplicate path")
        entries[relative_path] = digest
    if lines != sorted(lines, key=lambda line: line.split("  ", 1)[1]):
        raise P274Error("SHA256SUMS entries must use stable path ordering")
    return entries


def _reject_certification_claims(value: Mapping[str, Any], label: str) -> None:
    for key in value:
        folded = key.casefold().replace("-", "_")
        if any(token in folded for token in FORBIDDEN_CLAIM_TOKENS):
            raise P274Error(
                f"{label} claims historical/globally-earliest/retroactive certification"
            )


def _require_exact_fields(value: Mapping[str, Any], fields: frozenset[str], label: str) -> None:
    _reject_certification_claims(value, label)
    if set(value) != fields:
        raise P274Error(
            f"{label} schema mismatch; missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )


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


def _team_identity(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{2,4}", value):
        raise P274Error(f"{field_name} must be an uppercase team abbreviation")
    for canonical, aliases in TEAM_ALIASES.items():
        if value in aliases:
            return canonical
    return value


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise P274Error(f"{field_name} must be an object")
    return value


def _official_status(raw_root: Mapping[str, Any]) -> str:
    game_data = _mapping(raw_root.get("gameData"), "raw.gameData")
    status = _mapping(game_data.get("status"), "raw.gameData.status")
    detailed = status.get("detailedState")
    if not isinstance(detailed, str):
        raise P274Error("Official raw status is missing")
    folded = detailed.strip().casefold()
    if folded in {"final", "game over", "completed early"}:
        return "FINAL"
    if folded in {"forfeit", "forfeited"}:
        return "FORFEIT"
    raise P274Error("Official raw status is not a resolved FINAL/FORFEIT result")


def _official_score(raw_root: Mapping[str, Any], side: str) -> int:
    live_data = _mapping(raw_root.get("liveData"), "raw.liveData")
    linescore = _mapping(live_data.get("linescore"), "raw.liveData.linescore")
    teams = _mapping(linescore.get("teams"), "raw.liveData.linescore.teams")
    side_value = _mapping(teams.get(side), f"raw.liveData.linescore.teams.{side}")
    return _strict_nonnegative_int(side_value.get("runs"), f"official {side} score")


def _verify_raw_identity(raw: bytes, observation: Mapping[str, Any]) -> None:
    raw_root = parse_json_bytes(raw, "official raw response", require_canonical=False)
    official_game_pk = _strict_positive_int(observation["official_game_pk"], "official_game_pk")
    if _strict_positive_int(raw_root.get("gamePk"), "raw.gamePk") != official_game_pk:
        raise P274Error("Official raw top-level gamePk conflicts with observation")
    game_data = _mapping(raw_root.get("gameData"), "raw.gameData")
    game = _mapping(game_data.get("game"), "raw.gameData.game")
    if _strict_positive_int(game.get("pk"), "raw.gameData.game.pk") != official_game_pk:
        raise P274Error("Official raw nested gamePk conflicts with observation")
    raw_season = game.get("season")
    if isinstance(raw_season, str) and re.fullmatch(r"[0-9]{4}", raw_season):
        raw_season = int(raw_season)
    if raw_season != observation["season"]:
        raise P274Error("Official raw season conflicts with observation game identity")
    if _official_status(raw_root) != observation["official_status"]:
        raise P274Error("Official raw status conflicts with observation")
    teams = _mapping(game_data.get("teams"), "raw.gameData.teams")
    for side in ("away", "home"):
        official_team = _mapping(teams.get(side), f"raw.gameData.teams.{side}").get(
            "abbreviation"
        )
        if _team_identity(official_team, f"official {side} team") != _team_identity(
            observation[f"{side}_team"], f"observation {side} team"
        ):
            raise P274Error(f"Official raw {side} identity conflicts with observation")
        if _official_score(raw_root, side) != observation[f"{side}_score"]:
            raise P274Error(f"Official raw {side} score conflicts with observation")


def _validate_observation(observation: Mapping[str, Any]) -> tuple[datetime, datetime]:
    _require_exact_fields(observation, OBSERVATION_FIELDS, "observation.json")
    if observation["observation_contract_version"] != OBSERVATION_CONTRACT_VERSION:
        raise P274Error("Unexpected observation_contract_version")
    game_pk = _strict_positive_int(observation["official_game_pk"], "official_game_pk")
    season = observation["season"]
    if isinstance(season, bool) or not isinstance(season, int) or not 1800 <= season <= 9999:
        raise P274Error("season must be a four-digit integer")
    if observation["game_id"] != f"mlb_{season}_{game_pk}":
        raise P274Error("game_id does not match season and official gamePk")
    if observation["official_status"] not in RESOLVED_STATUSES:
        raise P274Error("P274 v1 accepts resolved FINAL/FORFEIT observations only")
    if observation["provenance_status"] != "COMPLETE":
        raise P274Error("Resolved observation provenance must be COMPLETE")
    if observation["source_name"] != SOURCE_NAME:
        raise P274Error("Observation source_name is not approved")
    if observation["source_endpoint_id"] != SOURCE_ENDPOINT_ID:
        raise P274Error("Observation source_endpoint_id is not approved")
    _, observed_dt = parse_canonical_utc(
        observation["source_observed_at_utc"], "source_observed_at_utc"
    )
    _, available_dt = parse_canonical_utc(
        observation["result_available_at_utc"], "result_available_at_utc"
    )
    if available_dt < observed_dt:
        raise P274Error("Backdated result availability precedes source observation")
    if observation["result_available_at_utc"] != observation["source_observed_at_utc"]:
        raise P274Error(
            "P272 FINAL/FORFEIT result availability must equal source observation"
        )
    scheduled_start = observation["scheduled_start_utc"]
    if scheduled_start is not None:
        parse_canonical_utc(scheduled_start, "scheduled_start_utc")
    if observation["status_reason"] is not None and not isinstance(
        observation["status_reason"], str
    ):
        raise P274Error("status_reason must be a string or null")
    for side in ("away", "home"):
        _team_identity(observation[f"{side}_team"], f"{side}_team")
        _strict_nonnegative_int(observation[f"{side}_score"], f"{side}_score")
    for field in ("raw_sha256", "source_fingerprint", "record_fingerprint"):
        if not _is_sha256(observation[field]):
            raise P274Error(f"{field} must be a lowercase SHA-256")
    if observation["source_fingerprint"] != _source_fingerprint(observation):
        raise P274Error("source_fingerprint does not match canonical source evidence")
    if observation["record_fingerprint"] != _record_fingerprint(observation):
        raise P274Error("record_fingerprint does not match canonical observation content")
    return observed_dt, available_dt


def _validate_source_index(
    source_index: Mapping[str, Any], observation: Mapping[str, Any], raw_relative_path: str
) -> None:
    _require_exact_fields(source_index, SOURCE_INDEX_FIELDS, "source_index.json")
    if source_index["source_index_contract_version"] != SOURCE_INDEX_CONTRACT_VERSION:
        raise P274Error("Unexpected source_index_contract_version")
    if source_index["relative_observation_path"] != OBSERVATION_FILENAME:
        raise P274Error("source_index relative_observation_path is invalid")
    if source_index["relative_raw_path"] != raw_relative_path:
        raise P274Error("source_index relative_raw_path does not match bundle inventory")
    shared_fields = (
        "observation_contract_version",
        "game_id",
        "official_game_pk",
        "source_name",
        "source_endpoint_id",
        "source_observed_at_utc",
        "raw_sha256",
        "source_fingerprint",
        "record_fingerprint",
        "provenance_status",
    )
    for field in shared_fields:
        if source_index[field] != observation[field]:
            raise P274Error(f"source_index {field} conflicts with observation")


def verify_bundle(bundle_root: Path) -> dict[str, Any]:
    """Verify one P272 bundle and return its deterministic P274 index record."""
    logical_root = _validate_bundle_inventory(bundle_root)
    manifest_bytes = _require_regular_file(bundle_root / CHECKSUM_FILENAME, CHECKSUM_FILENAME)
    observation_bytes = _require_regular_file(
        bundle_root / OBSERVATION_FILENAME, OBSERVATION_FILENAME
    )
    source_index_bytes = _require_regular_file(
        bundle_root / SOURCE_INDEX_FILENAME, SOURCE_INDEX_FILENAME
    )
    raw_name = next((bundle_root / "raw").iterdir()).name
    raw_relative_path = f"raw/{raw_name}"
    raw_bytes = _require_regular_file(bundle_root / raw_relative_path, raw_relative_path)

    manifest = _parse_checksum_manifest(manifest_bytes)
    expected_manifest_paths = {
        OBSERVATION_FILENAME,
        SOURCE_INDEX_FILENAME,
        raw_relative_path,
    }
    if set(manifest) != expected_manifest_paths:
        raise P274Error("SHA256SUMS does not describe the exact complete bundle")
    artifacts = {
        OBSERVATION_FILENAME: observation_bytes,
        SOURCE_INDEX_FILENAME: source_index_bytes,
        raw_relative_path: raw_bytes,
    }
    for relative_path, data in artifacts.items():
        if sha256_bytes(data) != manifest[relative_path]:
            raise P274Error(f"Checksum mismatch for {relative_path}")

    source_index = parse_json_bytes(
        source_index_bytes, SOURCE_INDEX_FILENAME, require_canonical=True
    )
    observation = parse_json_bytes(
        observation_bytes, OBSERVATION_FILENAME, require_canonical=True
    )
    _validate_observation(observation)
    _validate_source_index(source_index, observation, raw_relative_path)
    raw_sha256 = sha256_bytes(raw_bytes)
    if raw_sha256 != observation["raw_sha256"]:
        raise P274Error("Raw SHA-256 conflicts with observation and source index")
    _verify_raw_identity(raw_bytes, observation)

    record = {
        "game_id": observation["game_id"],
        "official_game_pk": observation["official_game_pk"],
        "source_bundle_root": logical_root,
        "source_observed_at_utc": observation["source_observed_at_utc"],
        "result_available_at_utc": observation["result_available_at_utc"],
        "official_status": observation["official_status"],
        "away_team": observation["away_team"],
        "home_team": observation["home_team"],
        "away_score": observation["away_score"],
        "home_score": observation["home_score"],
        "raw_sha256": raw_sha256,
        "observation_sha256": sha256_bytes(observation_bytes),
        "source_index_sha256": sha256_bytes(source_index_bytes),
        "manifest_fingerprint": sha256_bytes(manifest_bytes),
        "availability_semantics": AVAILABILITY_SEMANTICS,
        "retroactive_certification": RETROACTIVE_CERTIFICATION,
    }
    validate_index_record(record)
    return record


def validate_index_record(record: Mapping[str, Any]) -> None:
    if set(record) != RECORD_FIELDS:
        raise P274Error("Index record schema mismatch")
    if not isinstance(record["game_id"], str) or not record["game_id"]:
        raise P274Error("Index game_id must be a non-empty string")
    _strict_positive_int(record["official_game_pk"], "official_game_pk")
    if not isinstance(record["source_bundle_root"], str):
        raise P274Error("source_bundle_root must be a canonical relative path string")
    _logical_bundle_root(Path(record["source_bundle_root"]))
    parse_canonical_utc(record["source_observed_at_utc"], "source_observed_at_utc")
    _, available_dt = parse_canonical_utc(
        record["result_available_at_utc"], "result_available_at_utc"
    )
    _, observed_dt = parse_canonical_utc(
        record["source_observed_at_utc"], "source_observed_at_utc"
    )
    if available_dt < observed_dt:
        raise P274Error("Index record contains backdated availability")
    if record["official_status"] not in RESOLVED_STATUSES:
        raise P274Error("Index record status must be FINAL/FORFEIT")
    for side in ("away", "home"):
        _team_identity(record[f"{side}_team"], f"{side}_team")
        _strict_nonnegative_int(record[f"{side}_score"], f"{side}_score")
    for field in (
        "raw_sha256",
        "observation_sha256",
        "source_index_sha256",
        "manifest_fingerprint",
    ):
        if not _is_sha256(record[field]):
            raise P274Error(f"{field} must be a lowercase SHA-256")
    if record["availability_semantics"] != AVAILABILITY_SEMANTICS:
        raise P274Error("Index record has unsupported availability semantics")
    if record["retroactive_certification"] is not RETROACTIVE_CERTIFICATION:
        raise P274Error("Retroactive certification must remain false")


def build_index(bundle_roots: Sequence[Path]) -> dict[str, Any]:
    if not bundle_roots:
        raise P274Error("At least one --bundle-root is required")
    by_game_id: dict[str, dict[str, Any]] = {}
    for bundle_root in bundle_roots:
        record = verify_bundle(Path(bundle_root))
        existing = by_game_id.get(record["game_id"])
        if existing is not None and existing != record:
            raise P274Error(f"Conflicting duplicate game ID: {record['game_id']}")
        by_game_id[record["game_id"]] = record
    records = [by_game_id[game_id] for game_id in sorted(by_game_id)]
    index = {
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "record_count": len(records),
        "availability_semantics": AVAILABILITY_SEMANTICS,
        "retroactive_certification": RETROACTIVE_CERTIFICATION,
        "records": records,
    }
    validate_index(index)
    return index


def validate_index(index: Mapping[str, Any]) -> None:
    if set(index) != INDEX_FIELDS:
        raise P274Error("Index schema fields do not match v1")
    if index["index_schema_version"] != INDEX_SCHEMA_VERSION:
        raise P274Error("Unexpected index_schema_version")
    if index["availability_semantics"] != AVAILABILITY_SEMANTICS:
        raise P274Error("Unsupported index availability semantics")
    if index["retroactive_certification"] is not RETROACTIVE_CERTIFICATION:
        raise P274Error("Index retroactive certification must remain false")
    records = index["records"]
    if not isinstance(records, list):
        raise P274Error("Index records must be an array")
    if isinstance(index["record_count"], bool) or index["record_count"] != len(records):
        raise P274Error("Index record_count does not match records")
    game_ids: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise P274Error("Every index record must be an object")
        validate_index_record(record)
        game_ids.append(record["game_id"])
    if game_ids != sorted(game_ids) or len(game_ids) != len(set(game_ids)):
        raise P274Error("Index records must have unique, stable game_id ordering")


def write_index(output_root: Path, index: Mapping[str, Any]) -> tuple[bytes, bytes]:
    validate_index(index)
    output_root = Path(output_root)
    try:
        if output_root.exists():
            metadata = output_root.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise P274Error("--output-root must be a non-symlink directory")
            extras = {
                entry.name for entry in output_root.iterdir()
            } - {INDEX_FILENAME, CHECKSUM_FILENAME}
            if extras:
                raise P274Error(f"Output root contains unexpected entries: {sorted(extras)}")
        else:
            output_root.mkdir(parents=True)
    except OSError as exc:
        raise P274Error("Unable to prepare output root") from exc
    index_bytes = canonical_json_bytes(index, trailing_newline=True)
    manifest_bytes = f"{sha256_bytes(index_bytes)}  {INDEX_FILENAME}\n".encode("utf-8")
    try:
        (output_root / INDEX_FILENAME).write_bytes(index_bytes)
        (output_root / CHECKSUM_FILENAME).write_bytes(manifest_bytes)
    except OSError as exc:
        raise P274Error("Unable to write deterministic index artifacts") from exc
    return index_bytes, manifest_bytes


def load_index(index_path: Path) -> Mapping[str, Any]:
    data = _require_regular_file(Path(index_path), "index.json")
    index = parse_json_bytes(data, "index.json", require_canonical=True)
    validate_index(index)
    return index


def query_index(
    index: Mapping[str, Any], game_id: str, as_of_utc: str
) -> tuple[dict[str, Any], bool]:
    validate_index(index)
    if not isinstance(game_id, str) or not game_id or game_id != normalize_nfc(game_id):
        raise P274Error("--game-id must be one exact NFC-normalized non-empty string")
    canonical_as_of, as_of_dt = parse_canonical_utc(as_of_utc, "as_of_utc")
    record = next(
        (item for item in index["records"] if item["game_id"] == game_id), None
    )
    if record is None:
        return (
            {
                "game_id": game_id,
                "as_of_utc": canonical_as_of,
                "found": False,
                "available": False,
                "available_from_utc": None,
                "semantics": AVAILABILITY_SEMANTICS,
                "retroactive_certification": RETROACTIVE_CERTIFICATION,
            },
            False,
        )
    _, available_from_dt = parse_canonical_utc(
        record["result_available_at_utc"], "result_available_at_utc"
    )
    return (
        {
            "game_id": game_id,
            "as_of_utc": canonical_as_of,
            "found": True,
            "available": available_from_dt <= as_of_dt,
            "available_from_utc": record["result_available_at_utc"],
            "semantics": AVAILABILITY_SEMANTICS,
            "retroactive_certification": RETROACTIVE_CERTIFICATION,
        },
        True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or query the P274 prospective result-availability index"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument(
        "--bundle-root", action="append", type=Path, required=True
    )
    build_parser.add_argument("--output-root", type=Path, required=True)
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--index", type=Path, required=True)
    query_parser.add_argument("--game-id", required=True)
    query_parser.add_argument("--as-of-utc", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            index = build_index(args.bundle_root)
            index_bytes, _ = write_index(args.output_root, index)
            result = {
                "index_schema_version": INDEX_SCHEMA_VERSION,
                "record_count": index["record_count"],
                "index_sha256": sha256_bytes(index_bytes),
            }
            print(canonical_json_bytes(result).decode("utf-8"))
            return 0
        index = load_index(args.index)
        result, found = query_index(index, args.game_id, args.as_of_utc)
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0 if found else 3
    except P274Error as exc:
        print(f"P274_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
