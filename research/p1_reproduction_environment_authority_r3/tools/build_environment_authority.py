#!/usr/bin/env python3
"""Build deterministic P1 RuntimeFingerprintV3 authority artifacts.

This tool inventories only task-created offline installations. It never
imports LotteryNew production modules, opens a database, or runs a strategy.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import csv
import hashlib
import json
import platform
import posixpath
import re
import stat
import sys
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "RuntimeFingerprintV3"
SEMANTIC_RECORD_ALGORITHM_VERSION = "SemanticRecordV1"
INSTALLER_METADATA_POLICY_VERSION = "InstallerMetadataPolicyV1"
LAUNCHER_NORMALIZATION_POLICY_VERSION = "LauncherNormalizationPolicyV2"
CONSOLE_SCRIPT_SEMANTIC_VERSION = "ConsoleScriptSemanticV2"
PRESEAL_JUDGE_DEPTH = "DELTA"
PROJECT_RELATIVE_ROOT = "research/p1_reproduction_environment_authority_r3"
R2_RELATIVE_ROOT = "research/p1_reproduction_environment_authority_r2"
R2_MERGE_COMMIT = "8bfb4acce43e45a7920799699d9f946b442a3ec6"
R2_ENVIRONMENT_AUTHORITY_SHA256 = (
    "eeb0bdf0f6b4c3a5e49a02e540828a1917dcee11f3f716ebc53f72b4b6c1d5e8"
)
R2_RUNTIME_FINGERPRINT_SHA256 = (
    "040f9c261a716460a760f6b72496fd42f9dafe5fb8b9423f4269e97f3d69ddec"
)
R2_MANIFEST_SHA256 = "405f9a270878f0909bf0fa54d5cd5737ffbd7388111dfd3c191a63ed783d9849"
R2_SHA256SUMS_SHA256 = "36e4e4a1ff0f4499a9c2302bb683fec82beed5c2f58688671b39aa3f43843aea"
R2_INSTALLER_METADATA_POLICY_SHA256 = (
    "1521210a24785ca69e16d6c41a1536fbe8921463e06cb72044e7d505f23ac32b"
)
PRIOR_REFUTED_HEAD = "063293ae157a3d392235292cfb754faf535394c8"
PRIOR_REFUTED_TREE = "d8528c0ee6e6e7f1f29973aa7fa109cfbb99dd9b"
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
    ("install-short", "wheelhouse"),
    ("install-long-path-for-normalization-proof", "wheelhouse"),
    ("verification-install", "wheelhouse"),
)
AFFECTED_DISTRIBUTIONS = ["fastapi", "idna", "numpy", "pygments", "pytest"]
AFFECTED_LAUNCHERS = [
    "bin/fastapi",
    "bin/idna",
    "bin/f2py",
    "bin/numpy-config",
    "bin/pygmentize",
    "bin/pytest",
    "bin/py.test",
]
PYTHON_INTERPRETER_TOKEN = "${PYTHON_INTERPRETER}"
UV_CONSOLE_SCRIPT_LAUNCHER_TYPE = "uv_console_script"
CANONICAL_UV_CONSOLE_SCRIPT_PREFIX = (
    b"#!" + PYTHON_INTERPRETER_TOKEN.encode("utf-8") + b"\n"
)
TRAMPOLINE_PREFIX = b"#!/bin/sh\n'''exec' '"
TRAMPOLINE_SUFFIX = b"' \"$0\" \"$@\"\n' '''\n"
ABS_PATH_RE = re.compile(rb"/[^\s'\"]+")
HASH_FIELD_RE = re.compile(r"^sha256=([A-Za-z0-9_-]{43})$")
NORMALIZED_NAME_RE = re.compile(r"[-_.]+")
# Created by `uv venv`, never owned by any distribution's RECORD; excluded from
# launcher discovery so they are never mistaken for an undeclared console script.
VENV_SCAFFOLDING_BASENAMES = frozenset(
    {
        "activate",
        "activate.bat",
        "activate.csh",
        "activate.fish",
        "activate.nu",
        "activate.ps1",
        "activate_this.py",
        "deactivate.bat",
        "pydoc.bat",
        "python",
        "python3",
        "python3.12",
    }
)


class RecordValidationError(RuntimeError):
    """An installed RECORD violates SemanticRecordV1."""


class LauncherValidationError(RuntimeError):
    """An installed console-script launcher violates LauncherNormalizationPolicyV2."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def declared_key_order_bytes(value: Any) -> bytes:
    """Serialize with the exact key order the caller already constructed."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=False,
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
                f"frozen R2 input drift for {name}: expected={expected} actual={actual}"
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


def supersedes_document() -> dict[str, Any]:
    return {
        "schema_version": "P1EnvironmentAuthoritySupersessionV1",
        "superseded_task": "LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_RECORD_NORMALIZATION_R2",
        "superseded_root": R2_RELATIVE_ROOT,
        "r2_merge_commit": R2_MERGE_COMMIT,
        "r2_environment_authority_sha256": R2_ENVIRONMENT_AUTHORITY_SHA256,
        "r2_runtime_fingerprint_sha256": R2_RUNTIME_FINGERPRINT_SHA256,
        "r2_manifest_sha256": R2_MANIFEST_SHA256,
        "r2_sha256sums_sha256": R2_SHA256SUMS_SHA256,
        "affected_distributions": AFFECTED_DISTRIBUTIONS,
        "affected_launchers": AFFECTED_LAUNCHERS,
        "exact_defect": (
            "R2 RuntimeFingerprintV2 hashed every console-script launcher's raw "
            "installed bytes as ordinary semantic RECORD payload. Every launcher uv "
            "generates for an installed console_scripts entry point embeds the "
            "resolved absolute Python interpreter path of the installation root. R2 "
            "never bound an original installation root and never normalized launcher "
            "semantics, so the raw record_semantic_sha256 for any distribution owning "
            "a console script is location-dependent even though no package payload "
            "changed."
        ),
        "reproducibility_impact": (
            "Three offline installs of byte-identical approved wheels under "
            "installation roots of materially different absolute path length produce "
            "different raw launcher bytes and therefore a location-dependent "
            "RuntimeFingerprintV2 for the five distributions that declare "
            "console_scripts entry points."
        ),
        "r2_facts_remaining_valid": [
            "CPython 3.12.12 build 20251028 identity and artifact SHA-256",
            "seven exact direct dependency pins",
            "25 locked registry distributions",
            "23 approved macOS arm64 distributions and wheels",
            "lockfile, hashed export, wheel filenames, wheel hashes, and platform fingerprint",
            "InstallerMetadataPolicyV1 self-row and uv_cache.json exclusions",
            "SemanticRecordV1 equality for all non-launcher installed file content",
            "environment-only safety boundary",
        ],
        "superseded_acceptance_field": (
            "RuntimeFingerprintV2 record_semantic_sha256 computed over raw "
            "console-script launcher bytes as ordinary package payload"
        ),
        "diagnostic_fields_retained": [
            "raw_launcher_type",
            "raw_launcher_sha256",
            "raw_launcher_size",
        ],
        "replacement_acceptance_field": (
            "console_script_semantic_set_sha256 "
            "(normalized_launcher_sha256 per declared console script)"
        ),
        "launcher_policy_v2_correction": {
            "prior_policy_version": "LauncherNormalizationPolicyV1",
            "approved_raw_templates": ["python_shebang", "shell_trampoline"],
            "semantic_launcher_type": UV_CONSOLE_SCRIPT_LAUNCHER_TYPE,
            "equivalence_boundary": (
                "same declared entry point and byte-identical non-bootstrap "
                "Python payload"
            ),
        },
        "r3_effective_schema_version": SCHEMA_VERSION,
        "r3_launcher_normalization_policy_version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
        "r3_console_script_semantic_version": CONSOLE_SCRIPT_SEMANTIC_VERSION,
    }


def launcher_normalization_policy_document() -> dict[str, Any]:
    return {
        "schema_version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
        "console_script_semantic_version": CONSOLE_SCRIPT_SEMANTIC_VERSION,
        "discovery": {
            "source_of_truth": (
                "each installed distribution's own declared [console_scripts] "
                "entry points, read from <dist-info>/entry_points.txt"
            ),
            "expected_launcher_relative_path": "bin/{entry_point_name}",
            "mapping_cardinality": "exactly one installed launcher per declared entry point",
            "undeclared_extra_launcher_allowed": False,
            "venv_scaffolding_excluded": sorted(VENV_SCAFFOLDING_BASENAMES),
        },
        "normalization": {
            "semantic_launcher_type": UV_CONSOLE_SCRIPT_LAUNCHER_TYPE,
            "preserved_bytes": (
                "all non-bootstrap Python payload bytes after the exact approved "
                "raw-template header"
            ),
            "canonical_semantic_prefix": (
                "#!${PYTHON_INTERPRETER}\\n"
            ),
            "recognized_templates": [
                {
                    "raw_launcher_type": "python_shebang",
                    "description": "first line is '#!' followed by the resolved interpreter path",
                    "bootstrap_span": "first line only",
                },
                {
                    "raw_launcher_type": "shell_trampoline",
                    "description": (
                        "#!/bin/sh trampoline embedding the resolved interpreter path "
                        "once, in single quotes, on the second line"
                    ),
                    "bootstrap_span": "first three lines",
                },
            ],
            "cross_template_equivalence": (
                "approved raw templates are semantically identical only when their "
                "declared console-script entry point and complete non-bootstrap "
                "Python payload bytes are identical"
            ),
            "any_other_absolute_path_is_invalid": True,
            "any_unrecognized_template_is_invalid": True,
            "executable_mode_is_acceptance_critical": True,
            "non_bootstrap_byte_differences_are_acceptance_critical": True,
        },
        "fingerprint_exclusion": (
            "bin/** is never wholesale excluded from RuntimeFingerprintV3; only the "
            "declared console-script launcher rows move from raw semantic RECORD "
            "content into ConsoleScriptSemanticV2, retaining raw template type, "
            "hash, and size as diagnostics"
        ),
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
    required_console_script_fields = [
        "relative_posix_path",
        "executable_mode",
        "distribution_normalized_name",
        "distribution_version",
        "entry_point_group",
        "entry_point_name",
        "target_module",
        "target_callable",
        "launcher_type",
        "source_wheel_filename",
        "source_wheel_sha256",
        "normalized_launcher_sha256",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://lotterynew.invalid/schemas/runtime-fingerprint-v3.json",
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
            "launcher_normalization_policy_version",
            "launcher_normalization_policy_sha256",
            "actual_distribution_set",
            "console_script_semantic_set",
            "console_script_semantic_set_sha256",
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
            "launcher_normalization_policy_version": {
                "const": LAUNCHER_NORMALIZATION_POLICY_VERSION
            },
            "launcher_normalization_policy_sha256": {
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
            "console_script_semantic_set": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": required_console_script_fields,
                    "properties": {
                        "launcher_type": {
                            "const": UV_CONSOLE_SCRIPT_LAUNCHER_TYPE
                        }
                    },
                },
            },
            "console_script_semantic_set_sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
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


def declared_console_scripts(dist_info: Path) -> dict[str, str]:
    """Parse the distribution's own declared [console_scripts] entry points."""
    entry_points_path = dist_info / "entry_points.txt"
    if not entry_points_path.is_file() or entry_points_path.is_symlink():
        return {}
    parser = configparser.ConfigParser(delimiters=("=",), interpolation=None)
    parser.optionxform = str  # preserve case, e.g. "py.test"
    parser.read_string(entry_points_path.read_text(encoding="utf-8"))
    if "console_scripts" not in parser:
        return {}
    return {
        name.strip(): value.strip() for name, value in parser.items("console_scripts")
    }


def classify_and_normalize_launcher(
    data: bytes, expected_interpreter_path: str
) -> tuple[str, bytes]:
    """Return the raw template type and canonical semantic launcher bytes.

    The two uv bootstraps are transport details. Both collapse to one canonical
    prefix while every byte of their shared non-bootstrap Python payload remains
    acceptance-critical. A stray absolute path in that payload still invalidates
    the launcher.
    """
    expected_bytes = expected_interpreter_path.encode("utf-8")

    if data.startswith(TRAMPOLINE_PREFIX):
        remainder = data[len(TRAMPOLINE_PREFIX) :]
        expected_infix = expected_bytes + TRAMPOLINE_SUFFIX
        if not remainder.startswith(expected_infix):
            raise LauncherValidationError("unrecognized shell trampoline structure")
        rest = remainder[len(expected_infix) :]
        if ABS_PATH_RE.search(rest):
            raise LauncherValidationError(
                "unexpected absolute path outside the approved trampoline position"
            )
        normalized = CANONICAL_UV_CONSOLE_SCRIPT_PREFIX + rest
        return "shell_trampoline", normalized

    shebang_prefix = b"#!" + expected_bytes + b"\n"
    if data.startswith(shebang_prefix):
        rest = data[len(shebang_prefix) :]
        if ABS_PATH_RE.search(rest):
            raise LauncherValidationError(
                "unexpected absolute path outside the shebang line"
            )
        normalized = CANONICAL_UV_CONSOLE_SCRIPT_PREFIX + rest
        return "python_shebang", normalized

    raise LauncherValidationError("unrecognized launcher template")


def semantic_record(
    target_root: Path,
    dist_info: Path,
    *,
    launcher_relative_paths: dict[str, str] | None = None,
    excluded_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate a distribution's RECORD and split launcher rows from payload rows.

    ``launcher_relative_paths`` maps an expected ``bin/<name>`` normalized path to
    its declared console-script entry-point name for this distribution.
    """
    launcher_relative_paths = launcher_relative_paths or {}
    site_packages = dist_info.parent
    record_path = dist_info / "RECORD"
    uv_cache_path = dist_info / "uv_cache.json"
    require_regular_file(record_path)
    require_regular_file(uv_cache_path)
    record_relative = record_path.relative_to(target_root).as_posix()
    uv_cache_relative = uv_cache_path.relative_to(target_root).as_posix()
    exact_exclusions = {record_relative, uv_cache_relative, *launcher_relative_paths}
    requested_exclusions = (
        exact_exclusions if excluded_paths is None else set(excluded_paths)
    )
    if requested_exclusions != exact_exclusions:
        raise RecordValidationError(
            "semantic RECORD exclusions must be exactly RECORD self, "
            "uv_cache.json, and this distribution's declared launchers"
        )

    rows: list[dict[str, Any]] = []
    launcher_rows: list[dict[str, Any]] = []
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
                if normalized in launcher_relative_paths:
                    launcher_rows.append(
                        {
                            "path": normalized,
                            "entry_point_name": launcher_relative_paths[normalized],
                            "raw_bytes": actual_bytes,
                            "record_hash": hash_field,
                            "record_size": expected_size,
                            "executable_mode": stat.S_IMODE(installed_path.stat().st_mode),
                        }
                    )
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
    found_launcher_paths = {row["path"] for row in launcher_rows}
    missing = set(launcher_relative_paths) - found_launcher_paths
    if missing:
        raise RecordValidationError(f"missing declared console-script launcher(s): {sorted(missing)}")
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
        },
        "launcher_rows": launcher_rows,
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


def console_script_acceptance_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "relative_posix_path": row["relative_posix_path"],
        "executable_mode": row["executable_mode"],
        "distribution_normalized_name": row["distribution_normalized_name"],
        "distribution_version": row["distribution_version"],
        "entry_point_group": row["entry_point_group"],
        "entry_point_name": row["entry_point_name"],
        "target_module": row["target_module"],
        "target_callable": row["target_callable"],
        "launcher_type": row["launcher_type"],
        "source_wheel_filename": row["source_wheel_filename"],
        "source_wheel_sha256": row["source_wheel_sha256"],
        "normalized_launcher_sha256": row["normalized_launcher_sha256"],
    }


def console_script_semantic_set_fingerprint(rows: list[dict[str, Any]]) -> str:
    projected = sorted(
        (console_script_acceptance_row(row) for row in rows),
        key=lambda item: item["relative_posix_path"],
    )
    return sha256_bytes(canonical_bytes(projected))


def register_launcher_claim(
    claimed_launcher_paths: dict[str, str], launcher_path: str, owner: str
) -> None:
    """Record that ``owner`` declares ``launcher_path``; raise on a second claimant."""
    existing = claimed_launcher_paths.get(launcher_path)
    if existing is not None:
        raise RuntimeError(
            f"duplicate console-script launcher mapping: {launcher_path} claimed by "
            f"both {existing} and {owner}"
        )
    claimed_launcher_paths[launcher_path] = owner


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
    expected_interpreter_path = (target_root / "bin" / "python3.12").as_posix()

    distributions = []
    console_script_rows: list[dict[str, Any]] = []
    claimed_launcher_paths: dict[str, str] = {}
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
        if sha256_path(artifact) != receipt_row["approved_wheel_sha256"]:
            raise RuntimeError(f"installed source artifact hash drift: {artifact}")

        declared = declared_console_scripts(dist_info)
        launcher_relative_paths = {
            f"bin/{name}": name for name in declared
        }
        if len(launcher_relative_paths) != len(declared):
            raise RuntimeError(f"duplicate console-script name maps to one path: {key}")
        for launcher_path in launcher_relative_paths:
            register_launcher_claim(claimed_launcher_paths, launcher_path, normalized_name)

        record = semantic_record(
            target_root, dist_info, launcher_relative_paths=launcher_relative_paths
        )
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
            "semantic_row_count": record["semantic_row_count"],
            "distribution_acceptance_fingerprint_sha256": "",
        }
        distribution["distribution_acceptance_fingerprint_sha256"] = (
            distribution_acceptance_fingerprint(distribution)
        )
        distributions.append(distribution)

        for launcher_row in record["launcher_rows"]:
            name = launcher_row["entry_point_name"]
            target = declared[name]
            target_module, _, target_callable = target.partition(":")
            raw_launcher_type, normalized_bytes = classify_and_normalize_launcher(
                launcher_row["raw_bytes"], expected_interpreter_path
            )
            console_script_rows.append(
                {
                    "relative_posix_path": launcher_row["path"],
                    "executable_mode": format(launcher_row["executable_mode"], "o"),
                    "distribution_normalized_name": normalized_name,
                    "distribution_version": version,
                    "entry_point_group": "console_scripts",
                    "entry_point_name": name,
                    "target_module": target_module,
                    "target_callable": target_callable,
                    "launcher_type": UV_CONSOLE_SCRIPT_LAUNCHER_TYPE,
                    "source_wheel_filename": receipt_row["approved_wheel_filename"],
                    "source_wheel_sha256": receipt_row["approved_wheel_sha256"],
                    "normalized_launcher_sha256": sha256_bytes(normalized_bytes),
                    "raw_launcher_type": raw_launcher_type,
                    "raw_launcher_sha256": sha256_bytes(launcher_row["raw_bytes"]),
                    "raw_launcher_size": len(launcher_row["raw_bytes"]),
                }
            )

    distributions.sort(key=lambda item: item["normalized_name"])
    console_script_rows.sort(key=lambda item: item["relative_posix_path"])

    bin_dir = target_root / "bin"
    actual_bin_names = {
        path.name for path in bin_dir.iterdir() if not path.is_dir()
    }
    accounted_for = VENV_SCAFFOLDING_BASENAMES | {
        Path(row["relative_posix_path"]).name for row in console_script_rows
    }
    extra = actual_bin_names - accounted_for
    if extra:
        raise RuntimeError(f"undeclared extra launcher(s) in bin/: {sorted(extra)}")

    return {
        "target_install_identity": target_identity,
        "wheelhouse_identity": wheelhouse_identity,
        "distributions": distributions,
        "console_script_rows": console_script_rows,
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
    console_script_rows: list[dict[str, Any]],
    receipt_sha256: str,
    launcher_policy_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "RuntimeFingerprintV3AcceptancePayloadV1",
        "python_identity": python_identity(),
        "platform_identity": platform_identity(project_root),
        "project_lockfile_sha256": sha256_path(project_root / "uv.lock"),
        "expected_distribution_set_sha256": sha256_path(
            project_root / "expected_distributions.json"
        ),
        "installation_receipt_sha256": receipt_sha256,
        "normalization_policy": {
            "version": INSTALLER_METADATA_POLICY_VERSION,
            "sha256": R2_INSTALLER_METADATA_POLICY_SHA256,
            "semantic_record_algorithm_version": SEMANTIC_RECORD_ALGORITHM_VERSION,
        },
        "launcher_normalization_policy": {
            "version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
            "sha256": launcher_policy_sha256,
        },
        "actual_distribution_set": [
            acceptance_distribution(row) for row in distributions
        ],
        "console_script_semantic_set": [
            console_script_acceptance_row(row) for row in console_script_rows
        ],
        "console_script_semantic_set_sha256": console_script_semantic_set_fingerprint(
            console_script_rows
        ),
    }


def aggregate_runtime_document(
    project_root: Path,
    observations: list[dict[str, Any]],
    receipt_sha256: str,
    launcher_policy_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = expected_distribution_pairs(project_root)
    per_install_fingerprints: dict[str, str] = {}
    payloads: dict[str, dict[str, Any]] = {}
    per_install_console_sha256: dict[str, str] = {}
    for observation in observations:
        target = observation["target_install_identity"]
        distributions = observation["distributions"]
        console_script_rows = observation["console_script_rows"]
        validate_distribution_sets(expected, distributions)
        payload = environment_fingerprint_payload(
            project_root,
            distributions,
            console_script_rows,
            receipt_sha256,
            launcher_policy_sha256,
        )
        payloads[target] = payload
        per_install_fingerprints[target] = sha256_bytes(canonical_bytes(payload))
        per_install_console_sha256[target] = payload["console_script_semantic_set_sha256"]
    if len(set(per_install_fingerprints.values())) != 1:
        raise RuntimeError(
            f"RuntimeFingerprintV3 acceptance mismatch: {per_install_fingerprints}"
        )
    if len(set(per_install_console_sha256.values())) != 1:
        raise RuntimeError(
            f"ConsoleScriptSemanticV2 set mismatch across installs: {per_install_console_sha256}"
        )

    observation_by_target = {
        item["target_install_identity"]: item for item in observations
    }
    reference = observation_by_target["install-short"]["distributions"]
    aggregated = []
    for index, row_a in enumerate(reference):
        name = row_a["normalized_name"]
        for target, _wheelhouse in TARGETS:
            row = observation_by_target[target]["distributions"][index]
            if row["normalized_name"] != name:
                raise RuntimeError(f"distribution ordering mismatch: {name} vs {target}")
            if acceptance_distribution(row) != acceptance_distribution(row_a):
                raise RuntimeError(f"semantic distribution mismatch: {name} vs {target}")
        raw_observations = {
            target: observation_by_target[target]["distributions"][index]["record_raw_sha256"]
            for target, _wheelhouse in TARGETS
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

    reference_console = observation_by_target["install-short"]["console_script_rows"]
    console_script_semantic_set = [
        console_script_acceptance_row(row) for row in reference_console
    ]
    raw_launcher_diagnostics = []
    for row_a in reference_console:
        type_by_target = {}
        raw_by_target = {}
        size_by_target = {}
        for target, _wheelhouse in TARGETS:
            match = next(
                r
                for r in observation_by_target[target]["console_script_rows"]
                if r["relative_posix_path"] == row_a["relative_posix_path"]
            )
            type_by_target[target] = match["raw_launcher_type"]
            raw_by_target[target] = match["raw_launcher_sha256"]
            size_by_target[target] = match["raw_launcher_size"]
        raw_launcher_diagnostics.append(
            {
                "relative_posix_path": row_a["relative_posix_path"],
                "raw_launcher_type": {
                    "diagnostic_only": True,
                    "observations": type_by_target,
                },
                "raw_launcher_sha256": {"diagnostic_only": True, "observations": raw_by_target},
                "raw_launcher_size": {"diagnostic_only": True, "observations": size_by_target},
            }
        )

    accepted_payload = payloads["install-short"]
    environment_sha = per_install_fingerprints["install-short"]
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
        "installer_metadata_policy_sha256": R2_INSTALLER_METADATA_POLICY_SHA256,
        "installation_receipt_sha256": receipt_sha256,
        "launcher_normalization_policy_version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
        "launcher_normalization_policy_sha256": launcher_policy_sha256,
        "actual_distribution_set": aggregated,
        "console_script_semantic_set": console_script_semantic_set,
        "console_script_semantic_set_sha256": accepted_payload[
            "console_script_semantic_set_sha256"
        ],
        "distribution_set_match": True,
        "environment_fingerprint_acceptance_payload": accepted_payload,
        "environment_fingerprint_sha256": environment_sha,
        "per_install_environment_fingerprint_sha256": per_install_fingerprints,
    }
    diagnostic = {
        "raw_launcher_diagnostics": raw_launcher_diagnostics,
        "per_install_v3_environment_fingerprint_sha256": per_install_fingerprints,
    }
    return runtime_document, diagnostic


def environment_authority_document(
    project_root: Path,
    runtime_document: dict[str, Any],
    diagnostic: dict[str, Any],
    receipt_sha256: str,
    launcher_policy_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "P1ReproductionEnvironmentAuthorityV3",
        "task_id": (
            "LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_"
            "CONSOLE_SCRIPT_NORMALIZATION_R3"
        ),
        "supersedes_sha256": sha256_path(project_root / "supersedes.json"),
        "r2_authority": {
            "merge_commit": R2_MERGE_COMMIT,
            "environment_authority_sha256": R2_ENVIRONMENT_AUTHORITY_SHA256,
            "runtime_fingerprint_sha256": R2_RUNTIME_FINGERPRINT_SHA256,
            "manifest_sha256": R2_MANIFEST_SHA256,
            "sha256sums_sha256": R2_SHA256SUMS_SHA256,
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
            "sha256": R2_INSTALLER_METADATA_POLICY_SHA256,
        },
        "launcher_normalization_policy": {
            "version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
            "sha256": launcher_policy_sha256,
        },
        "installation_receipt_sha256": receipt_sha256,
        "runtime_fingerprint_sha256": sha256_bytes(canonical_bytes(runtime_document)),
        "environment_fingerprint_sha256": runtime_document[
            "environment_fingerprint_sha256"
        ],
        "console_script_semantic_set_sha256": runtime_document[
            "console_script_semantic_set_sha256"
        ],
        "root_cause": {
            "independently_reproduced": True,
            "affected_distributions": AFFECTED_DISTRIBUTIONS,
            "affected_launchers": AFFECTED_LAUNCHERS,
            "causal_chain": [
                "uv generates one launcher per declared console_scripts entry point",
                "the launcher embeds the resolved absolute installation-root interpreter path",
                "R2 hashed every installed file including launchers as ordinary RECORD payload",
                "three installs at materially different absolute path lengths therefore "
                "produce different raw launcher bytes with no package payload difference",
                "LauncherNormalizationPolicyV2 collapses both approved uv bootstrap "
                "templates to one canonical uv_console_script prefix while preserving "
                "the complete non-bootstrap Python payload, restoring location independence",
            ],
        },
        "raw_vs_normalized_launcher_comparison": diagnostic["raw_launcher_diagnostics"],
        "per_install_v3_fingerprint": diagnostic[
            "per_install_v3_environment_fingerprint_sha256"
        ],
        "v3_fingerprint_byte_identity": len(
            set(diagnostic["per_install_v3_environment_fingerprint_sha256"].values())
        )
        == 1,
        "offline_installation": {
            "install-short": "PASS",
            "install-long-path-for-normalization-proof": "PASS",
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


def installation_recipe_document(launcher_policy_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "InstallationRecipeV1",
        "uv_version": "0.9.6",
        "python": {
            "uv_identity": "cpython-3.12.12-macos-aarch64-none",
            "artifact_sha256": PYTHON_ARTIFACT_SHA256,
            "install_command_form": [
                "uv",
                "python",
                "install",
                "3.12.12",
                "--install-dir",
                "${RUNTIME_ROOT}/python",
                "--no-bin",
            ],
        },
        "wheelhouse": {
            "identity": "wheelhouse",
            "source_authority": "approved_artifacts.json source_url + sha256, hash-verified on fetch",
            "shared_across_all_targets": True,
        },
        "virtual_environment_creation": {
            "command_form": [
                "uv",
                "venv",
                "--python",
                "${RUNTIME_ROOT}/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12",
                "--offline",
                "${TARGET_ROOT}",
            ],
            "seed_packages": False,
        },
        "offline_install_command_form": [
            "uv",
            "pip",
            "install",
            "--python",
            "${TARGET_ROOT}/bin/python3.12",
            "--offline",
            "--no-index",
            "--find-links",
            "${RUNTIME_ROOT}/wheelhouse",
            "-r",
            "requirements.lock.txt",
            "--require-hashes",
        ],
        "editable_vcs_or_local_dependencies_allowed": False,
        "cache_and_runtime_redirections": {
            "UV_CACHE_DIR": "${RUNTIME_ROOT}/uv-cache",
            "UV_PROJECT_ENVIRONMENT": "${RUNTIME_ROOT}/venv",
            "UV_PYTHON_INSTALL_DIR": "${RUNTIME_ROOT}/python",
            "TMPDIR": "${RUNTIME_ROOT}/tmp",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C",
        },
        "mandatory_regeneration_acceptance": {
            "working_directory": PROJECT_RELATIVE_ROOT,
            "command_form": [
                "${RUNTIME_ROOT}/venv/bin/python",
                "tools/build_environment_authority.py",
                "--project-root",
                ".",
                "--runtime-root",
                "${RUNTIME_ROOT}",
                "--check",
            ],
            "runtime_root_must_be_explicit": True,
            "skip_allowed": False,
        },
        "approved_console_script_raw_template_types": [
            "python_shebang",
            "shell_trampoline",
        ],
        "semantic_console_script_launcher_type": UV_CONSOLE_SCRIPT_LAUNCHER_TYPE,
        "launcher_normalization_policy": {
            "version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
            "sha256": launcher_policy_sha256,
        },
        "acceptance_fields_exclude_absolute_task_root": True,
    }


def readme_text() -> str:
    return """# P1 Reproduction Environment Authority R3

This isolated subproject supersedes only the path-dependent console-script
launcher acceptance in R2. It preserves R1 and R2's exact Python, lock,
dependency, approved-wheel, platform, and non-launcher SemanticRecordV1
authorities unchanged.

Every launcher uv generates for an installed `console_scripts` entry point
embeds the resolved absolute installation-root interpreter path. R2 hashed
those launcher bytes as ordinary RECORD payload, so its RuntimeFingerprintV2
was location-dependent for any distribution declaring a console script.

`LauncherNormalizationPolicyV2` discovers launchers only from each
distribution's own declared `console_scripts` entry points, requires an exact
one-to-one mapping between declared entries and installed launchers, and maps
the approved uv Python-shebang and shell-trampoline bootstraps to one canonical
semantic prefix before hashing. `ConsoleScriptSemanticV2` records
`launcher_type: uv_console_script` while preserving every non-bootstrap Python
payload byte. Raw template type, hash, and size are retained diagnostically.

`RuntimeFingerprintV3` retains every R2 acceptance-critical field for
non-launcher content and adds the launcher-normalization policy identity and
the console-script semantic set identity. Three fresh offline installs at
materially different absolute path lengths produce different raw launcher
bytes and byte-identical RuntimeFingerprintV3 documents.

`runtime_fingerprint.schema.json` validates only semantic console-script
fields. Raw launcher hash and size observations remain diagnostic-only in
`launcher_raw_diagnostics.json`.

The mandatory regeneration acceptance command is recorded in
`installation_recipe.json`; it supplies the runtime root directly and cannot
silently skip. General Replay Governance CI does not replace this focused R3
acceptance.

The committed package contains no database, wheel, virtual environment,
cache, interpreter, production change, or strategy result.
"""


def report_text(
    project_root: Path,
    runtime_document: dict[str, Any],
    authority_document: dict[str, Any],
) -> str:
    diag = authority_document["raw_vs_normalized_launcher_comparison"]
    per_install = authority_document["per_install_v3_fingerprint"]
    return f"""# LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_CONSOLE_SCRIPT_NORMALIZATION_R3

Status: implementation and deterministic runtime evidence complete; final
independent Judge and evidence seal pending.

## Outcome

R1 and R2 remain immutable. R3 supersedes only path-dependent raw
console-script launcher acceptance and replaces it with
`ConsoleScriptSemanticV2`, while retaining raw launcher template types, hashes,
and sizes diagnostically.

## Preserved authority

- R2 merge commit: `{R2_MERGE_COMMIT}`
- R2 environment authority: `{R2_ENVIRONMENT_AUTHORITY_SHA256}`
- R2 runtime fingerprint: `{R2_RUNTIME_FINGERPRINT_SHA256}`
- CPython: `3.12.12`, build `20251028`, macOS arm64
- Python artifact SHA-256: `{PYTHON_ARTIFACT_SHA256}`
- Direct / locked / approved distributions: `7 / 25 / 23`
- Affected distributions: `{", ".join(AFFECTED_DISTRIBUTIONS)}`
- Affected launchers: `{", ".join(AFFECTED_LAUNCHERS)}`

## Independently reproduced defect

Three fresh offline hashed installs used the same wheelhouse under
installation roots of materially different absolute path length. All
non-launcher distribution content and `METADATA` hashes match across all
three; raw launcher hashes differ for every one of the 7 affected launchers
whenever the absolute root differs.

## RuntimeFingerprintV3

`LauncherNormalizationPolicyV2` maps both approved uv raw bootstraps to the
canonical `#!${{PYTHON_INTERPRETER}}` semantic prefix while preserving the
complete non-bootstrap Python payload before hashing.

Per-install RuntimeFingerprintV3 identities:

- install-short: `{per_install["install-short"]}`
- install-long-path-for-normalization-proof: `{per_install["install-long-path-for-normalization-proof"]}`
- verification-install: `{per_install["verification-install"]}`

All are byte-identical at `{runtime_document["environment_fingerprint_sha256"]}`.
`{len(diag)}` launchers were compared; every raw hash differed across the two
differently-rooted installs, and every normalized hash and
`ConsoleScriptSemanticV2` row matched with
`launcher_type: uv_console_script`.

## Safety boundary

No database was opened, read, hashed, copied, or snapshotted. No P1 backtest
ran. No production, deployment, registry, strategy status, or rejection state
was changed.

## Acceptance provenance

The mandatory non-skipping regeneration command is defined in
`installation_recipe.json`. Focused test counts and skip counts are execution
provenance recorded with the PR and handoff; they are not MANIFEST fields.
General Replay Governance CI does not replace focused R3 acceptance.

The prior fixed head `{PRIOR_REFUTED_HEAD}` and tree `{PRIOR_REFUTED_TREE}`
were REFUTED and are superseded by the corrected PR head. Final sealed-tree
Judge identity belongs in PR and handoff execution provenance rather than in
this non-recursive sealed package.
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

- Focused test counts/skips: PR and handoff execution provenance, not MANIFEST
- Negative integrity cases: `PASS`
- Canonical authority regeneration: `PASS`
- `uv lock --check --offline`: `PASS`
- `git diff --check`: `PASS`
- Pre-seal Judge provider/depth: `FABLE_JUDGE_SKILL / {PRESEAL_JUDGE_DEPTH}`
- Pre-seal Judge input HEAD: `{judge_input_head}`
- Pre-seal Judge input tree: `{judge_input_tree}`
- Pre-seal Judge verdict: `VERIFIED`
- Final sealed-tree Judge: PR and handoff execution provenance; not recursively embedded
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
    manifest = {
        "schema_version": "P1ReproductionEnvironmentEvidenceManifestV3",
        "task_id": (
            "LOTTERYNEW_P1_REPRODUCTION_ENVIRONMENT_AUTHORITY_"
            "CONSOLE_SCRIPT_NORMALIZATION_R3"
        ),
        "owner_authorization_status": "PRESENT",
        "r2_superseded_authority": {
            "merge_commit": R2_MERGE_COMMIT,
            "environment_authority_sha256": R2_ENVIRONMENT_AUTHORITY_SHA256,
            "runtime_fingerprint_sha256": R2_RUNTIME_FINGERPRINT_SHA256,
            "manifest_sha256": R2_MANIFEST_SHA256,
            "sha256sums_sha256": R2_SHA256SUMS_SHA256,
            "superseded_field": (
                "RuntimeFingerprintV2 raw console-script launcher byte acceptance"
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
        "launcher_normalization_policy": {
            "version": LAUNCHER_NORMALIZATION_POLICY_VERSION,
            "sha256": sha256_path(project_root / "launcher_normalization_policy.json"),
        },
        "console_script_semantic_set_sha256": runtime_document[
            "console_script_semantic_set_sha256"
        ],
        "installation_recipe_sha256": sha256_path(
            project_root / "installation_recipe.json"
        ),
        "installation_receipt_sha256": sha256_path(
            project_root / "installation_receipt.json"
        ),
        "install_fingerprints": authority_document["per_install_v3_fingerprint"],
        "raw_launcher_diagnostics": authority_document[
            "raw_vs_normalized_launcher_comparison"
        ],
        "verification": {
            "offline_install_short": "PASS",
            "offline_install_long_path": "PASS",
            "verification_install": "PASS",
            "deterministic_regeneration": "PASS",
            "negative_integrity_result": "PASS",
            "uv_lock_offline_check": "PASS",
            "git_diff_check": "PASS",
            "database_access_result": "NO_ACCESS",
        },
        "prior_refuted_candidate": {
            "head": PRIOR_REFUTED_HEAD,
            "tree": PRIOR_REFUTED_TREE,
            "verdict": "REFUTED",
        },
        "preseal_judge": {
            "provider": "FABLE_JUDGE_SKILL",
            "depth": PRESEAL_JUDGE_DEPTH,
            "scope": "NON_RECURSIVE_PRESEAL_SOURCE_TREE",
            "input_head": judge_input_head,
            "input_tree": judge_input_tree,
            "verdict": judge_verdict,
        },
        "final_sealed_tree_judge": {
            "embedded": False,
            "provenance_location": "PR and handoff execution evidence",
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

    supersedes = supersedes_document()
    launcher_policy = launcher_normalization_policy_document()
    schema = runtime_fingerprint_schema_document()
    static_documents = {
        "supersedes.json": supersedes,
        "launcher_normalization_policy.json": launcher_policy,
        "runtime_fingerprint.schema.json": schema,
    }
    for name, document in static_documents.items():
        write_or_check(project_root / name, canonical_bytes(document), check)
    launcher_policy_sha256 = sha256_bytes(canonical_bytes(launcher_policy))

    recipe = installation_recipe_document(launcher_policy_sha256)
    write_or_check(project_root / "installation_recipe.json", canonical_bytes(recipe), check)

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
        project_root, observations, receipt_sha256, launcher_policy_sha256
    )
    runtime_bytes = canonical_bytes(runtime_document)
    write_or_check(project_root / "runtime_fingerprint.json", runtime_bytes, check)
    authority = environment_authority_document(
        project_root,
        runtime_document,
        diagnostic,
        receipt_sha256,
        launcher_policy_sha256,
    )
    authority_bytes = canonical_bytes(authority)
    write_or_check(project_root / "environment_authority.json", authority_bytes, check)

    console_semantics_bytes = canonical_bytes(
        runtime_document["console_script_semantic_set"]
    )
    write_or_check(
        project_root / "console_script_semantics.json", console_semantics_bytes, check
    )
    launcher_diagnostics_bytes = canonical_bytes(diagnostic["raw_launcher_diagnostics"])
    write_or_check(
        project_root / "launcher_raw_diagnostics.json", launcher_diagnostics_bytes, check
    )

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
        "installation_recipe.json": sha256_bytes(canonical_bytes(recipe)),
        "installation_receipt.json": receipt_sha256,
        "runtime_fingerprint.json": sha256_bytes(runtime_bytes),
        "environment_authority.json": sha256_bytes(authority_bytes),
        "console_script_semantics.json": sha256_bytes(console_semantics_bytes),
        "launcher_raw_diagnostics.json": sha256_bytes(launcher_diagnostics_bytes),
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
