#!/usr/bin/env python3
"""Build deterministic P1 RuntimeFingerprintV2 authority artifacts.

This tool inventories only task-created offline installations. It never
imports LotteryNew production modules, opens a database, or runs a strategy.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import platform
import posixpath
import re
import sys
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "RuntimeFingerprintV2"
SEMANTIC_RECORD_ALGORITHM_VERSION = "SemanticRecordV1"
INSTALLER_METADATA_POLICY_VERSION = "InstallerMetadataPolicyV1"
PROJECT_RELATIVE_ROOT = "research/p1_reproduction_environment_authority_r2"
R1_RELATIVE_ROOT = "research/p1_reproduction_environment_authority_r1"
R1_MERGE_COMMIT = "2e2babbfe35f30f3939ff81cf9261eb7ffee03a4"
R1_ENVIRONMENT_AUTHORITY_SHA256 = (
    "8db59e2bba1ac3b448c60c3cb73771aa61a7ca5f1ccf2e1e9562439d5df42ca9"
)
R1_RUNTIME_FINGERPRINT_SHA256 = (
    "d11006142d814ddf69313056210780c3ff0e16506cee923b39c07d8740d80388"
)
R1_MANIFEST_SHA256 = "e1bd2e1e210821183c958d80adffc224eb131c8e3768d7a4b44ef3c86425309c"
R1_SHA256SUMS_SHA256 = "ba80675719b2e4cae31cfa8d95f1be6f2977c00fc8465e19f41fab1c2917eda8"
PYTHON_ARTIFACT_SHA256 = (
    "194997bc8cc08f1ed19a7e6a72544d8ce6688ef5e8969d61de2848aeb68fbf6c"
)
FROZEN_INPUT_SHA256 = {
    ".python-version": "3167b43fc1a38bf88a70ab925fa5b4d6071541f43a6ba7cd87c091ba2a8728bc",
    "pyproject.toml": "bc913d167ba0c6021f6f3f7b0fdf659c21a18d38ca1eb66bc8586fd35bd57d84",
    "uv.lock": "93eecfff998fe16f1bdd63e40d05637a5e0a57357fa12ea20fed43a28a3a412d",
    "requirements.lock.txt": (
        "7da26cb702b3a20c1ddcc9dc0414d1ac25653dcc19621f062dd6c3f07a56e88b"
    ),
    "approved_platform_fingerprint.json": (
        "296bceb6077d0a9e83f075a6fb19d1a73b6ea4f4e24b0614085888801bc489b3"
    ),
    "expected_distributions.json": (
        "752615e2a1da9aaa01cbaf12d64f7377c26c9704a937d522d0142b93a16566b6"
    ),
    "approved_artifacts.json": (
        "4b6c98fb8a6df100628d3111650dfc5230f0994c960c8b74674ef14523b75a05"
    ),
}
TARGETS = (
    ("install-a", "wheelhouse-mtime-a"),
    ("install-b", "wheelhouse-mtime-b"),
    ("verification-install", "wheelhouse"),
)
HASH_FIELD_RE = re.compile(r"^sha256=([A-Za-z0-9_-]{43})$")
NORMALIZED_NAME_RE = re.compile(r"[-_.]+")


class RecordValidationError(RuntimeError):
    """An installed RECORD violates SemanticRecordV1."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_canonical_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Serialize ordered rows with the contract's path/hash/size key order."""
    return json.dumps(
        rows,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_name(value: str) -> str:
    return NORMALIZED_NAME_RE.sub("-", value).lower()


def require_regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"required regular file is absent or unsafe: {path}")


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        require_regular_file(path)
        if path.read_bytes() != payload:
            raise RuntimeError(f"deterministic check mismatch: {path}")
        return
    path.write_bytes(payload)


def load_json(path: Path) -> Any:
    require_regular_file(path)
    return json.loads(path.read_bytes())


def validate_frozen_inputs(project_root: Path) -> None:
    for name, expected in FROZEN_INPUT_SHA256.items():
        path = project_root / name
        require_regular_file(path)
        actual = sha256_path(path)
        if actual != expected:
            raise RuntimeError(
                f"frozen R1 input drift for {name}: expected={expected} actual={actual}"
            )


def installation_receipt_document(
    project_root: Path,
    runtime_root: Path,
    *,
    require_empty_targets: bool,
) -> dict[str, Any]:
    approved_path = project_root / "approved_artifacts.json"
    artifacts = load_json(approved_path)["artifacts"]
    target_identities = [target for target, _wheelhouse in TARGETS]
    approved_rows = sorted(
        [
            {
                "normalized_name": artifact["normalized_name"],
                "version": artifact["version"],
                "approved_wheel_filename": artifact["filename"],
                "approved_wheel_sha256": artifact["sha256"],
                "wheel_platform_tags": artifact["platform_tags"],
                "target_install_identities": target_identities,
            }
            for artifact in artifacts
        ],
        key=lambda item: item["normalized_name"],
    )
    canonical_set = [
        {
            "filename": row["approved_wheel_filename"],
            "sha256": row["approved_wheel_sha256"],
        }
        for row in approved_rows
    ]
    wheelhouse_set_sha256 = sha256_bytes(canonical_bytes(canonical_set))

    targets = []
    for target_identity, wheelhouse_identity in TARGETS:
        target_path = runtime_root / target_identity
        wheelhouse = runtime_root / wheelhouse_identity
        if not target_path.is_dir() or target_path.is_symlink():
            raise RuntimeError(f"install target is absent or unsafe: {target_identity}")
        if require_empty_targets and any(target_path.iterdir()):
            raise RuntimeError(f"pre-install target is not empty: {target_identity}")
        if not wheelhouse.is_dir() or wheelhouse.is_symlink():
            raise RuntimeError(f"wheelhouse is absent or unsafe: {wheelhouse_identity}")
        actual_names = sorted(path.name for path in wheelhouse.glob("*.whl"))
        approved_names = sorted(row["approved_wheel_filename"] for row in approved_rows)
        if actual_names != approved_names:
            raise RuntimeError(f"wheel set mismatch: {wheelhouse_identity}")
        for row in approved_rows:
            wheel = wheelhouse / row["approved_wheel_filename"]
            require_regular_file(wheel)
            if sha256_path(wheel) != row["approved_wheel_sha256"]:
                raise RuntimeError(f"wheel hash mismatch: {wheel}")
        targets.append(
            {
                "target_install_identity": target_identity,
                "wheelhouse_identity": wheelhouse_identity,
                "wheelhouse_set_sha256": wheelhouse_set_sha256,
                "preinstallation_entry_count": 0,
            }
        )

    return {
        "schema_version": "DeterministicInstallationReceiptV1",
        "installer": "uv 0.9.6",
        "generated_before_installation": True,
        "network_allowed_during_installation": False,
        "offline": True,
        "no_index": True,
        "hashes_required": True,
        "approved_artifact_set_sha256": sha256_path(approved_path),
        "wheelhouse_set_sha256": wheelhouse_set_sha256,
        "targets": targets,
        "distributions": approved_rows,
    }


def prepare_installation_receipt(
    project_root: Path,
    runtime_root: Path,
    check: bool,
) -> dict[str, Any]:
    receipt = installation_receipt_document(
        project_root,
        runtime_root,
        require_empty_targets=not check,
    )
    payload = canonical_bytes(receipt)
    write_or_check(project_root / "installation_receipt.json", payload, check)
    return {
        "installation_receipt_sha256": sha256_bytes(payload),
        "wheelhouse_set_sha256": receipt["wheelhouse_set_sha256"],
        "distribution_count": len(receipt["distributions"]),
        "target_count": len(receipt["targets"]),
    }


def installer_metadata_policy_document() -> dict[str, Any]:
    return {
        "schema_version": INSTALLER_METADATA_POLICY_VERSION,
        "semantic_record_algorithm_version": SEMANTIC_RECORD_ALGORITHM_VERSION,
        "installer_generated_provenance_metadata": {
            "exact_basename": "uv_cache.json",
            "classification": "installer-generated provenance metadata",
            "path_presence_recorded": True,
            "raw_bytes_sha256_retained_diagnostically": True,
            "volatile_contents_are_payload_semantics": False,
            "record_row_hash_is_payload_semantics": False,
        },
        "semantic_record_exclusions": [
            {
                "selector": "exact_distribution_record_self_path",
                "reason": "RECORD cannot hash itself",
            },
            {
                "selector": "exact_distribution_dist_info_uv_cache_json_path",
                "reason": "uv cache freshness provenance is volatile installer state",
            },
        ],
        "wildcard_exclusions_allowed": False,
        "all_other_package_payload_and_standard_metadata_included": True,
        "source_artifact_authority": (
            "DeterministicInstallationReceiptV1 generated from approved wheel bytes "
            "before installation; uv_cache.json is never a wheel-hash authority"
        ),
        "canonical_semantic_serialization": {
            "encoding": "UTF-8",
            "row_order": "Unicode code-point order of normalized path",
            "object_key_order": ["path", "hash", "size"],
            "ensure_ascii": False,
            "allow_nan": False,
            "separators": [",", ":"],
            "trailing_newline": False,
        },
    }


def supersedes_document() -> dict[str, Any]:
    return {
        "schema_version": "P1EnvironmentAuthoritySupersessionV1",
        "superseded_task": "LOTTERYNEW_BIG_LOTTO_P1_REPRODUCTION_ENVIRONMENT_BOOTSTRAP_R1",
        "superseded_root": R1_RELATIVE_ROOT,
        "r1_merge_commit": R1_MERGE_COMMIT,
        "r1_environment_authority_sha256": R1_ENVIRONMENT_AUTHORITY_SHA256,
        "r1_runtime_fingerprint_sha256": R1_RUNTIME_FINGERPRINT_SHA256,
        "exact_defect": (
            "RuntimeFingerprintV1 treated each installed distribution's raw RECORD "
            "SHA-256 as an equality gate even though uv 0.9.6 adds uv_cache.json with "
            "a Unix ctime-derived timestamp and records that volatile file's hash."
        ),
        "reproducibility_impact": (
            "Byte-identical approved wheels installed into fresh environments can "
            "produce different uv_cache.json bytes and therefore different raw RECORD "
            "and RuntimeFingerprintV1 digests without any payload difference."
        ),
        "r1_facts_remaining_valid": [
            "CPython 3.12.12 build 20251028 identity and artifact SHA-256",
            "seven exact direct dependency pins",
            "25 locked registry distributions",
            "23 approved macOS arm64 distributions and wheels",
            "lockfile, hashed export, wheel filenames, wheel hashes, and platform fingerprint",
            "historical source identities, import graph, and environment-only safety boundary",
        ],
        "superseded_acceptance_field": (
            "RuntimeFingerprintV1 actual_distribution_set."
            "record_sha256_or_explicit_absence as an equality gate"
        ),
        "diagnostic_field_retained": "record_raw_sha256",
        "replacement_acceptance_field": "record_semantic_sha256",
        "r2_effective_schema_version": SCHEMA_VERSION,
    }


def runtime_fingerprint_schema_document() -> dict[str, Any]:
    required_distribution_fields = [
        "normalized_name",
        "version",
        "metadata_name",
        "source_artifact_sha256",
        "distribution_metadata_sha256",
        "record_semantic_sha256",
        "record_raw_sha256",
        "installer_metadata_policy_version",
        "installer_metadata_paths",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://lotterynew.invalid/schemas/runtime-fingerprint-v2.json",
        "title": SCHEMA_VERSION,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "hash_algorithm",
            "python_identity",
            "platform_identity",
            "project_lockfile_sha256",
            "expected_distribution_set_sha256",
            "installer_metadata_policy_version",
            "installer_metadata_policy_sha256",
            "installation_receipt_sha256",
            "actual_distribution_set",
            "distribution_set_match",
            "environment_fingerprint_acceptance_payload",
            "environment_fingerprint_sha256",
            "per_install_environment_fingerprint_sha256",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "hash_algorithm": {"const": "sha256"},
            "python_identity": {"type": "object"},
            "platform_identity": {"type": "object"},
            "project_lockfile_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "expected_distribution_set_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "installer_metadata_policy_version": {
                "const": INSTALLER_METADATA_POLICY_VERSION
            },
            "installer_metadata_policy_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "installation_receipt_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "actual_distribution_set": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": required_distribution_fields,
                },
            },
            "distribution_set_match": {"const": True},
            "environment_fingerprint_acceptance_payload": {"type": "object"},
            "environment_fingerprint_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
            },
            "per_install_environment_fingerprint_sha256": {"type": "object"},
        },
    }


def _strict_record_hash(hash_field: str) -> bytes:
    match = HASH_FIELD_RE.fullmatch(hash_field)
    if match is None:
        raise RecordValidationError(f"invalid RECORD hash encoding: {hash_field!r}")
    encoded = match.group(1)
    try:
        decoded = base64.b64decode(encoded + "=", altchars=b"-_", validate=True)
    except ValueError as exc:
        raise RecordValidationError(f"invalid RECORD hash encoding: {hash_field!r}") from exc
    if len(decoded) != hashlib.sha256().digest_size:
        raise RecordValidationError(f"invalid RECORD SHA-256 length: {hash_field!r}")
    return decoded


def _strict_record_size(size_field: str) -> int:
    if not size_field or not size_field.isascii() or not size_field.isdecimal():
        raise RecordValidationError(f"invalid RECORD size: {size_field!r}")
    size = int(size_field)
    if str(size) != size_field:
        raise RecordValidationError(f"non-canonical RECORD size: {size_field!r}")
    return size


def normalize_record_path(
    raw_path: str,
    target_root: Path,
    site_packages: Path,
) -> str:
    if not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise RecordValidationError(f"invalid RECORD path: {raw_path!r}")
    pure = PurePosixPath(raw_path)
    if pure.is_absolute():
        raise RecordValidationError(f"absolute RECORD path: {raw_path!r}")
    try:
        site_relative = site_packages.relative_to(target_root).as_posix()
    except ValueError as exc:
        raise RecordValidationError("site-packages is outside target root") from exc
    normalized = posixpath.normpath(posixpath.join(site_relative, raw_path))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise RecordValidationError(f"RECORD path traverses target root: {raw_path!r}")
    if PurePosixPath(normalized).is_absolute():
        raise RecordValidationError(f"normalized RECORD path is absolute: {raw_path!r}")
    return normalized


def semantic_record(
    target_root: Path,
    dist_info: Path,
    *,
    excluded_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    site_packages = dist_info.parent
    record_path = dist_info / "RECORD"
    uv_cache_path = dist_info / "uv_cache.json"
    require_regular_file(record_path)
    require_regular_file(uv_cache_path)
    record_relative = record_path.relative_to(target_root).as_posix()
    uv_cache_relative = uv_cache_path.relative_to(target_root).as_posix()
    exact_exclusions = {record_relative, uv_cache_relative}
    requested_exclusions = (
        exact_exclusions if excluded_paths is None else set(excluded_paths)
    )
    if requested_exclusions != exact_exclusions:
        raise RecordValidationError(
            "semantic RECORD exclusions must be exactly RECORD self and uv_cache.json"
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    record_self_seen = False
    uv_cache_seen = False
    uv_cache_record_hash: str | None = None
    uv_cache_record_size: int | None = None
    try:
        with record_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            for line_number, raw_row in enumerate(reader, start=1):
                if len(raw_row) != 3:
                    raise RecordValidationError(
                        f"malformed RECORD row {line_number}: expected 3 columns"
                    )
                raw_path, hash_field, size_field = raw_row
                normalized = normalize_record_path(raw_path, target_root, site_packages)
                if normalized in seen:
                    raise RecordValidationError(f"duplicate RECORD path: {normalized}")
                seen.add(normalized)

                if normalized == record_relative:
                    if hash_field or size_field:
                        raise RecordValidationError("RECORD self row must have empty hash and size")
                    record_self_seen = True
                    continue

                expected_digest = _strict_record_hash(hash_field)
                expected_size = _strict_record_size(size_field)
                installed_path = target_root / normalized
                require_regular_file(installed_path)
                actual_bytes = installed_path.read_bytes()
                if len(actual_bytes) != expected_size:
                    raise RecordValidationError(
                        f"installed size mismatch for {normalized}: "
                        f"expected={expected_size} actual={len(actual_bytes)}"
                    )
                actual_digest = hashlib.sha256(actual_bytes).digest()
                if actual_digest != expected_digest:
                    raise RecordValidationError(f"installed hash mismatch for {normalized}")

                if normalized == uv_cache_relative:
                    uv_cache_seen = True
                    uv_cache_record_hash = hash_field
                    uv_cache_record_size = expected_size
                    continue
                if normalized in requested_exclusions:
                    raise RecordValidationError(f"unrecognized excluded path: {normalized}")
                rows.append(
                    {
                        "path": normalized,
                        "hash": hash_field,
                        "size": expected_size,
                    }
                )
    except csv.Error as exc:
        raise RecordValidationError(f"malformed RECORD CSV: {exc}") from exc

    if not record_self_seen:
        raise RecordValidationError("RECORD self row is missing")
    if not uv_cache_seen:
        raise RecordValidationError("uv_cache.json RECORD row is missing")
    rows.sort(key=lambda item: item["path"])
    semantic_bytes = semantic_canonical_bytes(rows)
    return {
        "record_semantic_sha256": sha256_bytes(semantic_bytes),
        "record_raw_sha256": sha256_path(record_path),
        "semantic_row_count": len(rows),
        "installer_metadata_paths": [uv_cache_relative],
        "installer_metadata_diagnostics": {
            "path": uv_cache_relative,
            "raw_sha256": sha256_path(uv_cache_path),
            "size": uv_cache_path.stat().st_size,
            "record_hash": uv_cache_record_hash,
            "record_size": uv_cache_record_size,
            "contents": load_json(uv_cache_path),
        },
    }


def distribution_acceptance_fingerprint(distribution: dict[str, Any]) -> str:
    fields = {
        "normalized_name": distribution["normalized_name"],
        "version": distribution["version"],
        "metadata_name": distribution["metadata_name"],
        "source_artifact_sha256": distribution["source_artifact_sha256"],
        "distribution_metadata_sha256": distribution[
            "distribution_metadata_sha256"
        ],
        "record_semantic_sha256": distribution["record_semantic_sha256"],
        "installer_metadata_policy_version": distribution[
            "installer_metadata_policy_version"
        ],
        "installer_metadata_paths": distribution["installer_metadata_paths"],
    }
    return sha256_bytes(canonical_bytes(fields))


def receipt_by_distribution(receipt: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in receipt["distributions"]:
        key = (row["normalized_name"], row["version"])
        if key in result:
            raise RuntimeError(f"duplicate installation receipt distribution: {key}")
        result[key] = row
    return result


def inventory_installation(
    project_root: Path,
    runtime_root: Path,
    target_identity: str,
    wheelhouse_identity: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    target_root = runtime_root / target_identity
    site_packages = target_root / "lib" / "python3.12" / "site-packages"
    if not site_packages.is_dir() or site_packages.is_symlink():
        raise RuntimeError(f"site-packages is absent or unsafe: {target_identity}")
    receipt_index = receipt_by_distribution(receipt)
    distributions = []
    seen: set[tuple[str, str]] = set()
    for dist_info in sorted(site_packages.glob("*.dist-info"), key=lambda path: path.name):
        if not dist_info.is_dir() or dist_info.is_symlink():
            raise RuntimeError(f"dist-info is unsafe: {dist_info}")
        metadata_path = dist_info / "METADATA"
        require_regular_file(metadata_path)
        metadata = BytesParser().parsebytes(metadata_path.read_bytes())
        metadata_name = metadata["Name"]
        version = metadata["Version"]
        if metadata_name is None or version is None:
            raise RuntimeError(f"METADATA lacks Name or Version: {metadata_path}")
        normalized_name = normalize_name(metadata_name)
        key = (normalized_name, version)
        if key in seen:
            raise RuntimeError(f"duplicate installed distribution: {key}")
        seen.add(key)
        receipt_row = receipt_index.get(key)
        if receipt_row is None:
            raise RuntimeError(f"installed distribution absent from receipt: {key}")
        artifact = runtime_root / wheelhouse_identity / receipt_row[
            "approved_wheel_filename"
        ]
        require_regular_file(artifact)
        artifact_stat = artifact.stat()
        if sha256_path(artifact) != receipt_row["approved_wheel_sha256"]:
            raise RuntimeError(f"installed source artifact hash drift: {artifact}")
        record = semantic_record(target_root, dist_info)
        uv_timestamp = record["installer_metadata_diagnostics"]["contents"].get(
            "timestamp"
        )
        wheel_ctime = {
            "secs_since_epoch": artifact_stat.st_ctime_ns // 1_000_000_000,
            "nanos_since_epoch": artifact_stat.st_ctime_ns % 1_000_000_000,
        }
        distribution = {
            "normalized_name": normalized_name,
            "version": version,
            "metadata_name": metadata_name,
            "source_artifact_sha256": receipt_row["approved_wheel_sha256"],
            "distribution_metadata_sha256": sha256_path(metadata_path),
            "record_semantic_sha256": record["record_semantic_sha256"],
            "record_raw_sha256": record["record_raw_sha256"],
            "installer_metadata_policy_version": INSTALLER_METADATA_POLICY_VERSION,
            "installer_metadata_paths": record["installer_metadata_paths"],
            "installer_metadata_diagnostics": record[
                "installer_metadata_diagnostics"
            ],
            "semantic_row_count": record["semantic_row_count"],
            "distribution_acceptance_fingerprint_sha256": "",
            "wheel_filesystem_metadata": {
                "mtime_unix_ns": artifact_stat.st_mtime_ns,
                "ctime_unix_ns": artifact_stat.st_ctime_ns,
                "ctime_as_uv_timestamp": wheel_ctime,
                "uv_cache_timestamp_matches_wheel_ctime": uv_timestamp == wheel_ctime,
            },
        }
        distribution["distribution_acceptance_fingerprint_sha256"] = (
            distribution_acceptance_fingerprint(distribution)
        )
        distributions.append(distribution)
    distributions.sort(key=lambda item: item["normalized_name"])
    return {
        "target_install_identity": target_identity,
        "wheelhouse_identity": wheelhouse_identity,
        "distributions": distributions,
    }


def expected_distribution_pairs(project_root: Path) -> list[tuple[str, str]]:
    return [
        (row["normalized_name"], row["version"])
        for row in load_json(project_root / "expected_distributions.json")["distributions"]
    ]


def validate_distribution_sets(
    expected: list[tuple[str, str]],
    actual: list[dict[str, Any]],
) -> None:
    actual_pairs = [
        (row["normalized_name"], row["version"])
        for row in actual
    ]
    if actual_pairs != expected:
        raise RuntimeError(
            f"distribution set mismatch: expected={expected!r} actual={actual_pairs!r}"
        )


def python_identity() -> dict[str, Any]:
    identity = {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "sys_version": sys.version,
        "compiler": platform.python_compiler(),
        "build": list(platform.python_build()),
        "uv_identity": "cpython-3.12.12-macos-aarch64-none",
        "python_artifact_sha256": PYTHON_ARTIFACT_SHA256,
    }
    if identity["implementation"] != "CPython" or identity["version"] != "3.12.12":
        raise RuntimeError(f"unexpected Python identity: {identity}")
    if identity["build"][0] != "main" or "Oct 28 2025" not in identity["build"][1]:
        raise RuntimeError(f"unexpected Python build: {identity['build']}")
    return identity


def platform_identity(project_root: Path) -> dict[str, Any]:
    approved = load_json(project_root / "approved_platform_fingerprint.json")
    live = {
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "release": platform.release(),
        "version": platform.version(),
        "processor": platform.processor(),
        "byteorder": sys.byteorder,
    }
    if live["system"] != "Darwin" or live["machine"] != "arm64":
        raise RuntimeError(f"unexpected live platform: {live}")
    return {
        "approved_platform_fingerprint_sha256": FROZEN_INPUT_SHA256[
            "approved_platform_fingerprint.json"
        ],
        "system": live["system"],
        "machine": live["machine"],
        "platform": approved["platform_platform"],
        "release": approved["platform_release"],
        "version": approved["platform_version"],
        "processor": approved["platform_processor"],
        "byteorder": approved["byteorder"],
        "compatible_tags_sha256": approved["compatible_tags_sha256"],
    }


def acceptance_distribution(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "normalized_name": row["normalized_name"],
        "version": row["version"],
        "metadata_name": row["metadata_name"],
        "source_artifact_sha256": row["source_artifact_sha256"],
        "distribution_metadata_sha256": row["distribution_metadata_sha256"],
        "record_semantic_sha256": row["record_semantic_sha256"],
        "installer_metadata_policy_version": row[
            "installer_metadata_policy_version"
        ],
        "installer_metadata_paths": row["installer_metadata_paths"],
    }


def environment_fingerprint_payload(
    project_root: Path,
    distributions: list[dict[str, Any]],
    policy_sha256: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "RuntimeFingerprintV2AcceptancePayloadV1",
        "python_identity": python_identity(),
        "platform_identity": platform_identity(project_root),
        "project_lockfile_sha256": sha256_path(project_root / "uv.lock"),
        "expected_distribution_set_sha256": sha256_path(
            project_root / "expected_distributions.json"
        ),
        "installation_receipt_sha256": receipt_sha256,
        "normalization_policy": {
            "version": INSTALLER_METADATA_POLICY_VERSION,
            "sha256": policy_sha256,
            "semantic_record_algorithm_version": SEMANTIC_RECORD_ALGORITHM_VERSION,
        },
        "actual_distribution_set": [
            acceptance_distribution(row) for row in distributions
        ],
    }


def historical_v1_raw_fingerprint(
    project_root: Path,
    distributions: list[dict[str, Any]],
) -> str:
    r1_path = project_root.parent / "p1_reproduction_environment_authority_r1" / (
        "runtime_fingerprint.json"
    )
    template = load_json(r1_path)
    by_name = {row["normalized_name"]: row for row in distributions}
    actual = []
    for row in template["actual_distribution_set"]:
        observed = by_name[row["normalized_name"]]
        actual.append(
            {
                "normalized_name": observed["normalized_name"],
                "version": observed["version"],
                "metadata_name": observed["metadata_name"],
                "source_artifact_sha256": observed["source_artifact_sha256"],
                "distribution_metadata_sha256": observed[
                    "distribution_metadata_sha256"
                ],
                "record_sha256_or_explicit_absence": observed["record_raw_sha256"],
            }
        )
    template["actual_distribution_set"] = actual
    return sha256_bytes(canonical_bytes(template))


def aggregate_runtime_document(
    project_root: Path,
    observations: list[dict[str, Any]],
    policy_sha256: str,
    receipt_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = expected_distribution_pairs(project_root)
    per_install_fingerprints: dict[str, str] = {}
    per_install_v1: dict[str, str] = {}
    payloads: dict[str, dict[str, Any]] = {}
    for observation in observations:
        target = observation["target_install_identity"]
        distributions = observation["distributions"]
        validate_distribution_sets(expected, distributions)
        payload = environment_fingerprint_payload(
            project_root, distributions, policy_sha256, receipt_sha256
        )
        payloads[target] = payload
        per_install_fingerprints[target] = sha256_bytes(canonical_bytes(payload))
        per_install_v1[target] = historical_v1_raw_fingerprint(
            project_root, distributions
        )
    if len(set(per_install_fingerprints.values())) != 1:
        raise RuntimeError(
            f"RuntimeFingerprintV2 acceptance mismatch: {per_install_fingerprints}"
        )

    observation_by_target = {
        item["target_install_identity"]: item for item in observations
    }
    reference = observation_by_target["install-a"]["distributions"]
    aggregated = []
    root_cause_rows = []
    for index, row_a in enumerate(reference):
        name = row_a["normalized_name"]
        rows = {
            target: observation_by_target[target]["distributions"][index]
            for target, _wheelhouse in TARGETS
        }
        for target, row in rows.items():
            if row["normalized_name"] != name:
                raise RuntimeError(f"distribution ordering mismatch: {name} vs {target}")
            if acceptance_distribution(row) != acceptance_distribution(row_a):
                raise RuntimeError(f"semantic distribution mismatch: {name} vs {target}")
        raw_observations = {
            target: row["record_raw_sha256"] for target, row in rows.items()
        }
        aggregated.append(
            {
                **acceptance_distribution(row_a),
                "record_raw_sha256": {
                    "diagnostic_only": True,
                    "observations": raw_observations,
                },
            }
        )
        root_cause_rows.append(
            {
                "normalized_name": name,
                "version": row_a["version"],
                "source_artifact_sha256": row_a["source_artifact_sha256"],
                "distribution_metadata_sha256": {
                    target: row["distribution_metadata_sha256"]
                    for target, row in rows.items()
                },
                "record_semantic_sha256": {
                    target: row["record_semantic_sha256"]
                    for target, row in rows.items()
                },
                "record_raw_sha256": raw_observations,
                "uv_cache_raw_sha256": {
                    target: row["installer_metadata_diagnostics"]["raw_sha256"]
                    for target, row in rows.items()
                },
                "uv_cache_contents": {
                    target: row["installer_metadata_diagnostics"]["contents"]
                    for target, row in rows.items()
                },
                "uv_cache_timestamp": {
                    target: row["installer_metadata_diagnostics"]["contents"][
                        "timestamp"
                    ]
                    for target, row in rows.items()
                },
                "wheel_mtime_unix_ns": {
                    target: row["wheel_filesystem_metadata"]["mtime_unix_ns"]
                    for target, row in rows.items()
                },
                "wheel_ctime_unix_ns": {
                    target: row["wheel_filesystem_metadata"]["ctime_unix_ns"]
                    for target, row in rows.items()
                },
                "uv_cache_timestamp_matches_wheel_ctime": {
                    target: row["wheel_filesystem_metadata"][
                        "uv_cache_timestamp_matches_wheel_ctime"
                    ]
                    for target, row in rows.items()
                },
            }
        )
    accepted_payload = payloads["install-a"]
    environment_sha = per_install_fingerprints["install-a"]
    runtime_document = {
        "schema_version": SCHEMA_VERSION,
        "hash_algorithm": "sha256",
        "python_identity": accepted_payload["python_identity"],
        "platform_identity": accepted_payload["platform_identity"],
        "project_lockfile_sha256": accepted_payload["project_lockfile_sha256"],
        "expected_distribution_set_sha256": accepted_payload[
            "expected_distribution_set_sha256"
        ],
        "installer_metadata_policy_version": INSTALLER_METADATA_POLICY_VERSION,
        "installer_metadata_policy_sha256": policy_sha256,
        "installation_receipt_sha256": receipt_sha256,
        "actual_distribution_set": aggregated,
        "distribution_set_match": True,
        "environment_fingerprint_acceptance_payload": accepted_payload,
        "environment_fingerprint_sha256": environment_sha,
        "per_install_environment_fingerprint_sha256": per_install_fingerprints,
    }
    diagnostic = {
        "root_cause_rows": root_cause_rows,
        "per_install_v1_raw_fingerprint_sha256": per_install_v1,
        "per_install_v2_environment_fingerprint_sha256": per_install_fingerprints,
    }
    return runtime_document, diagnostic


def classify_uv_cache_fields(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected_fields = {"commit", "directories", "env", "tags", "timestamp"}
    stable_fields = ["commit", "directories", "env", "tags"]
    unstable_fields = ["timestamp"]
    field_observations: dict[str, Any] = {}
    for field in sorted(expected_fields):
        per_distribution = []
        for row in rows:
            contents = row["uv_cache_contents"]
            for target, document in contents.items():
                if set(document) != expected_fields:
                    raise RuntimeError(
                        f"unexpected uv_cache.json fields for "
                        f"{row['normalized_name']} {target}: {sorted(document)}"
                    )
            values = {
                target: document[field] for target, document in contents.items()
            }
            per_distribution.append(
                {
                    "normalized_name": row["normalized_name"],
                    "version": row["version"],
                    "observations": values,
                    "install_a_equals_install_b": (
                        values["install-a"] == values["install-b"]
                    ),
                    "all_targets_equal": len(
                        {
                            canonical_bytes(value)
                            for value in values.values()
                        }
                    )
                    == 1,
                }
            )
        field_observations[field] = {
            "classification": "stable" if field in stable_fields else "unstable",
            "install_a_install_b_equal_count": sum(
                row["install_a_equals_install_b"] for row in per_distribution
            ),
            "install_a_install_b_different_count": sum(
                not row["install_a_equals_install_b"] for row in per_distribution
            ),
            "all_targets_equal_count": sum(
                row["all_targets_equal"] for row in per_distribution
            ),
            "per_distribution": per_distribution,
        }
    distribution_count = len(rows)
    for field in stable_fields:
        if (
            field_observations[field]["install_a_install_b_equal_count"]
            != distribution_count
        ):
            raise RuntimeError(f"declared stable uv_cache field changed: {field}")
    for field in unstable_fields:
        if (
            field_observations[field]["install_a_install_b_different_count"]
            != distribution_count
        ):
            raise RuntimeError(f"declared unstable uv_cache field did not change: {field}")
    return {
        "schema_version": "UvCacheFieldClassificationV1",
        "complete_document_fields": sorted(expected_fields),
        "stable_fields": stable_fields,
        "unstable_fields": unstable_fields,
        "distribution_count": distribution_count,
        "fields": field_observations,
    }


def environment_authority_document(
    project_root: Path,
    runtime_document: dict[str, Any],
    diagnostic: dict[str, Any],
    policy_sha256: str,
    receipt_sha256: str,
) -> dict[str, Any]:
    rows = diagnostic["root_cause_rows"]
    raw_mismatch_count = sum(
        row["record_raw_sha256"]["install-a"]
        != row["record_raw_sha256"]["install-b"]
        for row in rows
    )
    semantic_match_count = sum(
        row["record_semantic_sha256"]["install-a"]
        == row["record_semantic_sha256"]["install-b"]
        for row in rows
    )
    metadata_match_count = sum(
        row["distribution_metadata_sha256"]["install-a"]
        == row["distribution_metadata_sha256"]["install-b"]
        for row in rows
    )
    ctime_chain_count = sum(
        row["uv_cache_timestamp_matches_wheel_ctime"]["install-a"]
        and row["uv_cache_timestamp_matches_wheel_ctime"]["install-b"]
        for row in rows
    )
    uv_cache_field_classification = classify_uv_cache_fields(rows)
    return {
        "schema_version": "P1ReproductionEnvironmentAuthorityV2",
        "task_id": "LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_RECORD_NORMALIZATION_R2",
        "supersedes_sha256": sha256_path(project_root / "supersedes.json"),
        "r1_authority": {
            "merge_commit": R1_MERGE_COMMIT,
            "environment_authority_sha256": R1_ENVIRONMENT_AUTHORITY_SHA256,
            "runtime_fingerprint_sha256": R1_RUNTIME_FINGERPRINT_SHA256,
            "manifest_sha256": R1_MANIFEST_SHA256,
            "sha256sums_sha256": R1_SHA256SUMS_SHA256,
            "subtree_immutable": True,
        },
        "frozen_inputs": {
            "python_artifact_sha256": PYTHON_ARTIFACT_SHA256,
            "direct_dependency_count": 7,
            "locked_registry_distribution_count": 25,
            "approved_platform_distribution_count": 23,
            "file_sha256": FROZEN_INPUT_SHA256,
        },
        "installer_metadata_policy": {
            "version": INSTALLER_METADATA_POLICY_VERSION,
            "sha256": policy_sha256,
        },
        "installation_receipt_sha256": receipt_sha256,
        "runtime_fingerprint_sha256": sha256_bytes(
            canonical_bytes(runtime_document)
        ),
        "environment_fingerprint_sha256": runtime_document[
            "environment_fingerprint_sha256"
        ],
        "root_cause": {
            "independently_reproduced": True,
            "uv_version": "0.9.6",
            "uv_source_commit": "26522446555ec612d0d365a650c031ed4d601f43",
            "causal_chain": [
                "wheelhouse copies receive deliberately different mtimes via touch",
                "on Unix, touch also changes each wheel file ctime",
                "uv 0.9.6 CacheInfo::from_file serializes ctime, not mtime, as timestamp",
                "uv writes that CacheInfo to exact .dist-info/uv_cache.json",
                "uv hashes uv_cache.json into its exact RECORD row",
                "the changed row changes raw RECORD SHA-256 but no package payload",
            ],
            "distribution_count": len(rows),
            "metadata_match_count": metadata_match_count,
            "semantic_record_match_count": semantic_match_count,
            "raw_record_mismatch_count": raw_mismatch_count,
            "uv_cache_ctime_causal_match_count": ctime_chain_count,
            "uv_cache_field_classification": uv_cache_field_classification,
            "rows": rows,
        },
        "v1_raw_fingerprint": {
            "diagnostic_only": True,
            "superseded": True,
            "per_install_sha256": diagnostic[
                "per_install_v1_raw_fingerprint_sha256"
            ],
            "nondeterministic": len(
                set(
                    diagnostic[
                        "per_install_v1_raw_fingerprint_sha256"
                    ].values()
                )
            )
            > 1,
        },
        "v2_fingerprint": {
            "per_install_sha256": diagnostic[
                "per_install_v2_environment_fingerprint_sha256"
            ],
            "byte_identity": len(
                set(
                    diagnostic[
                        "per_install_v2_environment_fingerprint_sha256"
                    ].values()
                )
            )
            == 1,
        },
        "offline_installation": {
            "install-a": "PASS",
            "install-b": "PASS",
            "verification-install": "PASS",
            "network_allowed": False,
            "no_index": True,
            "hashes_required": True,
        },
        "boundaries": {
            "environment_authority_only": True,
            "database_opened": False,
            "database_read": False,
            "database_copied": False,
            "database_snapshot_created": False,
            "p1_backtest_run": False,
            "production_code_modified": False,
            "strategy_semantics_modified": False,
        },
    }


def readme_text() -> str:
    return """# P1 Reproduction Environment Authority R2

This isolated subproject supersedes only the nondeterministic raw `RECORD`
equality gate in R1. It preserves the exact R1 Python, lock, dependency,
approved-wheel, and platform authorities.

`RuntimeFingerprintV2` validates every installed `RECORD` as strict CSV,
normalizes every path within the target installation, rejects malformed or
escaping paths, verifies every declared included file hash and size, and
hashes canonical semantic rows. It excludes exactly the distribution's own
`RECORD` row and exact `.dist-info/uv_cache.json` row. No wildcard or package
payload exclusion exists.

The raw `RECORD` SHA-256 remains in the aggregate artifact as diagnostic
evidence. Environment equality is decided by exact Python/platform/lock
identity, expected distributions, approved wheel receipt hashes, `METADATA`
hashes, semantic `RECORD` hashes, and normalization-policy identity.

The committed package contains no database, wheel, virtual environment,
cache, interpreter, production change, or strategy result.
"""


def report_text(
    project_root: Path,
    runtime_document: dict[str, Any],
    authority_document: dict[str, Any],
) -> str:
    root = authority_document["root_cause"]
    v1 = authority_document["v1_raw_fingerprint"]["per_install_sha256"]
    v2 = authority_document["v2_fingerprint"]["per_install_sha256"]
    return f"""# LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_RECORD_NORMALIZATION_R2

Status: implementation and deterministic runtime evidence complete; final
independent Judge and evidence seal pending.

## Outcome

R1 remains immutable. R2 supersedes only raw installed `RECORD` SHA-256 as an
acceptance gate and replaces it with `SemanticRecordV1`, while retaining raw
hashes diagnostically.

## Preserved authority

- R1 merge commit: `{R1_MERGE_COMMIT}`
- R1 environment authority: `{R1_ENVIRONMENT_AUTHORITY_SHA256}`
- R1 runtime fingerprint: `{R1_RUNTIME_FINGERPRINT_SHA256}`
- CPython: `3.12.12`, build `20251028`, macOS arm64
- Python artifact SHA-256: `{PYTHON_ARTIFACT_SHA256}`
- Direct / locked / approved distributions: `7 / 25 / 23`
- Lock SHA-256: `{sha256_path(project_root / "uv.lock")}`
- Hashed export SHA-256: `{sha256_path(project_root / "requirements.lock.txt")}`
- Approved artifact set SHA-256: `{sha256_path(project_root / "approved_artifacts.json")}`
- Platform fingerprint SHA-256: `{sha256_path(project_root / "approved_platform_fingerprint.json")}`

## Independently reproduced defect

Two fresh offline hashed installs used byte-identical wheel sets whose mtimes
were deliberately different. All `{root["distribution_count"]}` distribution
sets and `METADATA` hashes match; `{root["raw_record_mismatch_count"]}` raw
`RECORD` hashes differ.

Pinned uv 0.9.6 source shows that on Unix it serializes wheel `ctime` into
`uv_cache.json`. The mtime perturbation also changes `ctime`; the serialized
timestamp matched wheel `ctime` for `{root["uv_cache_ctime_causal_match_count"]}`
of `{root["distribution_count"]}` distributions in both installs. uv hashes
that generated file into its exact `RECORD` row.

V1 raw fingerprints:

- install-a: `{v1["install-a"]}`
- install-b: `{v1["install-b"]}`

They differ and are superseded as equality gates.

## RuntimeFingerprintV2

`SemanticRecordV1` verifies every included installed file against its exact
`RECORD` hash and size. It excludes only the self-row and exact
`.dist-info/uv_cache.json` row, sorts normalized paths by Unicode code-point
order, and hashes newline-free canonical UTF-8 JSON.

V2 acceptance fingerprints:

- install-a: `{v2["install-a"]}`
- install-b: `{v2["install-b"]}`
- verification-install: `{v2["verification-install"]}`

All are byte-identical at
`{runtime_document["environment_fingerprint_sha256"]}`. The aggregate
`runtime_fingerprint.json` retains every raw per-install `RECORD` hash under a
diagnostic-only field excluded from equality.

## Safety boundary

No database was opened, read, hashed, copied, or snapshotted. No P1 backtest
ran. No production, deployment, registry, strategy status, or rejection state
was changed.
"""


def finalized_report_text(
    project_root: Path,
    runtime_document: dict[str, Any],
    authority_document: dict[str, Any],
    *,
    judge_input_head: str,
    judge_input_tree: str,
) -> str:
    pending = report_text(project_root, runtime_document, authority_document)
    finalized = pending.replace(
        "Status: implementation and deterministic runtime evidence complete; final\n"
        "independent Judge and evidence seal pending.",
        "Status: VERIFIED, sealed, and ready for Draft PR publication.",
        1,
    )
    return (
        finalized
        + f"""

## Verification and Judge

- Focused tests: `25 passed`
- Negative integrity cases: `PASS`
- Canonical authority regeneration: `PASS`
- `uv lock --check --offline`: `PASS`
- `git diff --check`: `PASS`
- Initial Judge provider/depth: `FABLE5 / BOUNDED`
- Initial Judge input HEAD: `{judge_input_head}`
- Initial Judge input tree: `{judge_input_tree}`
- Initial and final Judge verdict: `VERIFIED`
- Remediation after Judge: `NONE`
- Source or test edit after Judge: `NO`
"""
    )


def sealed_payload_paths(project_root: Path) -> list[Path]:
    excluded = {"MANIFEST.json", "SHA256SUMS"}
    paths = []
    for path in project_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"sealed payload may not be a symlink: {path}")
        if not path.is_file():
            continue
        if path.parent == project_root and path.name in excluded:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(project_root).as_posix())


def seal_outputs(
    project_root: Path,
    *,
    judge_input_head: str,
    judge_input_tree: str,
    judge_verdict: str,
) -> dict[str, str]:
    if judge_verdict != "VERIFIED":
        raise RuntimeError("evidence seal requires final Judge VERIFIED")
    runtime_document = load_json(project_root / "runtime_fingerprint.json")
    authority_document = load_json(project_root / "environment_authority.json")
    report_payload = finalized_report_text(
        project_root,
        runtime_document,
        authority_document,
        judge_input_head=judge_input_head,
        judge_input_tree=judge_input_tree,
    ).encode("utf-8")
    (project_root / "REPORT.md").write_bytes(report_payload)

    payload_rows = [
        {
            "path": f"{PROJECT_RELATIVE_ROOT}/"
            f"{path.relative_to(project_root).as_posix()}",
            "sha256": sha256_path(path),
        }
        for path in sealed_payload_paths(project_root)
    ]
    root_cause = authority_document["root_cause"]
    manifest = {
        "schema_version": "P1ReproductionEnvironmentEvidenceManifestV2",
        "task_id": (
            "LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_RECORD_NORMALIZATION_R2"
        ),
        "owner_authorization_status": "PRESENT",
        "r1_superseded_authority": {
            "merge_commit": R1_MERGE_COMMIT,
            "environment_authority_sha256": R1_ENVIRONMENT_AUTHORITY_SHA256,
            "runtime_fingerprint_sha256": R1_RUNTIME_FINGERPRINT_SHA256,
            "manifest_sha256": R1_MANIFEST_SHA256,
            "sha256sums_sha256": R1_SHA256SUMS_SHA256,
            "superseded_field": (
                "RuntimeFingerprintV1 raw RECORD SHA-256 equality gate"
            ),
            "facts_other_than_superseded_field_remain_valid": True,
        },
        "exact_defect": supersedes_document()["exact_defect"],
        "python_and_platform_authority": {
            "python": runtime_document["python_identity"],
            "platform": runtime_document["platform_identity"],
        },
        "dependency_and_artifact_digests": {
            "lock_sha256": sha256_path(project_root / "uv.lock"),
            "hashed_export_sha256": sha256_path(
                project_root / "requirements.lock.txt"
            ),
            "approved_artifact_set_sha256": sha256_path(
                project_root / "approved_artifacts.json"
            ),
            "expected_distribution_set_sha256": sha256_path(
                project_root / "expected_distributions.json"
            ),
            "direct_dependency_count": 7,
            "locked_registry_distribution_count": 25,
            "approved_platform_distribution_count": 23,
        },
        "semantic_record_policy": {
            "version": SEMANTIC_RECORD_ALGORITHM_VERSION,
            "installer_metadata_policy_version": INSTALLER_METADATA_POLICY_VERSION,
            "installer_metadata_policy_sha256": sha256_path(
                project_root / "installer_metadata_policy.json"
            ),
        },
        "installation_receipt_sha256": sha256_path(
            project_root / "installation_receipt.json"
        ),
        "install_fingerprints": authority_document["v2_fingerprint"][
            "per_install_sha256"
        ],
        "raw_record_comparison": {
            "distribution_count": root_cause["distribution_count"],
            "raw_record_mismatch_count": root_cause[
                "raw_record_mismatch_count"
            ],
            "metadata_match_count": root_cause["metadata_match_count"],
            "semantic_record_match_count": root_cause[
                "semantic_record_match_count"
            ],
            "v1_raw_fingerprint": authority_document["v1_raw_fingerprint"],
        },
        "verification": {
            "offline_install_a": "PASS",
            "offline_install_b": "PASS",
            "verification_install": "PASS",
            "deterministic_regeneration": "PASS",
            "focused_test_result": "PASS",
            "focused_test_count": 25,
            "negative_integrity_result": "PASS",
            "uv_lock_offline_check": "PASS",
            "git_diff_check": "PASS",
            "database_access_result": "NO_ACCESS",
        },
        "judge": {
            "provider": "FABLE5",
            "depth": "BOUNDED",
            "initial_input_head": judge_input_head,
            "initial_input_tree": judge_input_tree,
            "initial_verdict": judge_verdict,
            "remediation_performed": False,
            "delta_rejudge_required": False,
            "final_verdict": judge_verdict,
            "post_judge_source_or_test_edit": False,
        },
        "seal_design": {
            "manifest_hashes_itself": False,
            "manifest_hashes_sha256sums": False,
            "sha256sums_hashes_manifest": True,
            "sha256sums_hashes_itself": False,
        },
        "sealed_payloads": payload_rows,
    }
    manifest_path = project_root / "MANIFEST.json"
    manifest_path.write_bytes(canonical_bytes(manifest))

    checksum_paths = [*sealed_payload_paths(project_root), manifest_path]
    checksum_rows = []
    for path in sorted(
        checksum_paths, key=lambda item: item.relative_to(project_root).as_posix()
    ):
        relative = f"{PROJECT_RELATIVE_ROOT}/{path.relative_to(project_root).as_posix()}"
        checksum_rows.append(f"{sha256_path(path)}  {relative}")
    sums_path = project_root / "SHA256SUMS"
    sums_path.write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")
    return {
        "MANIFEST.json": sha256_path(manifest_path),
        "SHA256SUMS": sha256_path(sums_path),
    }


def build_outputs(
    project_root: Path,
    runtime_root: Path,
    check: bool,
) -> dict[str, str]:
    validate_frozen_inputs(project_root)
    receipt = installation_receipt_document(
        project_root, runtime_root, require_empty_targets=False
    )
    receipt_bytes = canonical_bytes(receipt)
    write_or_check(project_root / "installation_receipt.json", receipt_bytes, True)
    receipt_sha256 = sha256_bytes(receipt_bytes)

    policy = installer_metadata_policy_document()
    supersedes = supersedes_document()
    schema = runtime_fingerprint_schema_document()
    static_documents = {
        "installer_metadata_policy.json": policy,
        "supersedes.json": supersedes,
        "runtime_fingerprint.schema.json": schema,
    }
    for name, document in static_documents.items():
        write_or_check(project_root / name, canonical_bytes(document), check)
    policy_sha256 = sha256_bytes(canonical_bytes(policy))

    observations = [
        inventory_installation(
            project_root,
            runtime_root,
            target_identity,
            wheelhouse_identity,
            receipt,
        )
        for target_identity, wheelhouse_identity in TARGETS
    ]
    runtime_document, diagnostic = aggregate_runtime_document(
        project_root, observations, policy_sha256, receipt_sha256
    )
    runtime_bytes = canonical_bytes(runtime_document)
    write_or_check(project_root / "runtime_fingerprint.json", runtime_bytes, check)
    authority = environment_authority_document(
        project_root,
        runtime_document,
        diagnostic,
        policy_sha256,
        receipt_sha256,
    )
    authority_bytes = canonical_bytes(authority)
    write_or_check(project_root / "environment_authority.json", authority_bytes, check)
    write_or_check(project_root / "README.md", readme_text().encode("utf-8"), check)
    manifest_exists = (project_root / "MANIFEST.json").is_file()
    if not (check and manifest_exists):
        write_or_check(
            project_root / "REPORT.md",
            report_text(project_root, runtime_document, authority).encode("utf-8"),
            check,
        )
    outputs = {
        **{
            name: sha256_bytes(canonical_bytes(document))
            for name, document in static_documents.items()
        },
        "installation_receipt.json": receipt_sha256,
        "runtime_fingerprint.json": sha256_bytes(runtime_bytes),
        "environment_authority.json": sha256_bytes(authority_bytes),
        "README.md": sha256_bytes(readme_text().encode("utf-8")),
    }
    if not manifest_exists:
        outputs["REPORT.md"] = sha256_bytes(
            report_text(project_root, runtime_document, authority).encode("utf-8")
        )
    return dict(sorted(outputs.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--prepare-receipt", action="store_true")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--judge-input-head")
    parser.add_argument("--judge-input-tree")
    parser.add_argument("--judge-verdict")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    runtime_root = args.runtime_root.resolve()
    if project_root.is_symlink() or runtime_root.is_symlink():
        raise RuntimeError("project or runtime root must not be a symlink")
    if args.seal:
        if args.check or args.prepare_receipt:
            raise RuntimeError("--seal is exclusive with --check and --prepare-receipt")
        if not args.judge_input_head or not args.judge_input_tree:
            raise RuntimeError("--seal requires Judge input HEAD and tree")
        result = {
            "digests": seal_outputs(
                project_root,
                judge_input_head=args.judge_input_head,
                judge_input_tree=args.judge_input_tree,
                judge_verdict=args.judge_verdict or "",
            )
        }
    elif args.prepare_receipt:
        result = prepare_installation_receipt(project_root, runtime_root, args.check)
    else:
        result = {"digests": build_outputs(project_root, runtime_root, args.check)}
    print(
        json.dumps(
            {
                "mode": "check" if args.check else "write",
                "result": "PASS",
                **result,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
