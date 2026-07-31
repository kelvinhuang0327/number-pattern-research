#!/usr/bin/env python3
"""Build deterministic P1 reproduction environment authority artifacts.

This tool inventories an already-created, offline-installed verification
environment. It never imports LotteryNew production modules, opens a database,
or executes a strategy/backtest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import sysconfig
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename


SCHEMA_VERSION = "RuntimeFingerprintV1"
PROJECT_RELATIVE_ROOT = "research/p1_reproduction_environment_authority_r1"
APPROVED_PLATFORM_EXCLUDED_LOCK_DISTRIBUTIONS = {"colorama", "tzdata"}
DIRECT_DEPENDENCIES = [
    {"normalized_name": "apscheduler", "version": "3.11.3", "purpose": "historical local import chain"},
    {"normalized_name": "fastapi", "version": "0.140.0", "purpose": "historical local import chain"},
    {"normalized_name": "numpy", "version": "2.5.1", "purpose": "historical strategy runtime"},
    {"normalized_name": "pydantic", "version": "2.13.4", "purpose": "historical local import chain"},
    {"normalized_name": "pytest", "version": "9.1.1", "purpose": "focused authority verification"},
    {"normalized_name": "scikit-learn", "version": "1.9.0", "purpose": "historical local import chain"},
    {"normalized_name": "scipy", "version": "1.18.0", "purpose": "historical strategy runtime"},
]
PYTHON_AUTHORITY = {
    "implementation": "CPython",
    "version": "3.12.12",
    "uv_identity": "cpython-3.12.12-macos-aarch64-none",
    "build": "20251028",
    "artifact": "cpython-3.12.12+20251028-aarch64-apple-darwin-install_only_stripped.tar.gz",
    "artifact_sha256": "194997bc8cc08f1ed19a7e6a72544d8ce6688ef5e8969d61de2848aeb68fbf6c",
    "source_url": (
        "https://github.com/astral-sh/python-build-standalone/releases/download/20251028/"
        "cpython-3.12.12%2B20251028-aarch64-apple-darwin-install_only_stripped.tar.gz"
    ),
    "minor_selection": {
        "dependency_requires_python": {
            "apscheduler==3.11.3": ">=3.8",
            "fastapi==0.140.0": ">=3.10",
            "numpy==2.5.1": ">=3.12",
            "pydantic==2.13.4": ">=3.9",
            "pytest==9.1.1": ">=3.10",
            "scikit-learn==1.9.0": ">=3.11",
            "scipy==1.18.0": ">=3.12",
        },
        "lowest_common_supported_minor": "3.12",
        "selected_patch": "3.12.12",
        "selection_reason": (
            "Python 3.12 is the lowest minor accepted by every exact direct dependency; "
            "3.12.12 is the newest uv-catalogued patch in that minor."
        ),
    },
}
SOURCE_IDENTITIES = {
    "contract_authority_commit": "2aaa1874320ac50f2a08ed1414094faac7098146",
    "contract_authority_tree": "806cd3aec4a2b290f40b647f0310aa51b010039a",
    "historical_source_commit": "28940a2572c051c6ba8b2ab6a077f706e800477d",
    "four_bet": {
        "path": "tools/backtest_p1_deviation_4bet.py",
        "blob": "2efa426d7f24d9baefb6ed6dcedf467fa2542dee",
    },
    "five_bet": {
        "path": "tools/backtest_p1dev_5bet.py",
        "blob": "5ece590b40bd3d731dc98f5cfdd7c85aa3a5b347",
    },
    "baseline_calculator": {
        "path": "lottery_api/utils/baseline_calculator.py",
        "blob": "be203a05e01cb211c7101137ab2ff7968e5d5bd1",
    },
    "permutation_test": {
        "path": "lottery_api/utils/permutation_test.py",
        "blob": "ebf5b7eb13edb79f456320f4626c88cce9a330f7",
    },
    "database": {
        "path": "lottery_api/database.py",
        "blob": "1a1077eaa59906b0b11e1c430eec61fb5675ab38",
    },
    "common": {
        "path": "lottery_api/common.py",
        "blob": "e58de590e04f543126eaa2cae16e75aede824220",
    },
    "scheduler": {
        "path": "lottery_api/utils/scheduler.py",
        "blob": "37f58cd170ae5155eb787e59aa26c1055d16c59d",
    },
    "config": {
        "path": "lottery_api/config.py",
        "blob": "03a59af4642e0b9c0fd97b30493c832a5d9fb32d",
    },
    "advanced_auto_learning": {
        "path": "lottery_api/models/advanced_auto_learning.py",
        "blob": "840e06e5ed2d3116be1e20b7a23874598b085023",
    },
    "advanced_strategies": {
        "path": "lottery_api/models/advanced_strategies.py",
        "blob": "02dfb9fa99571fdef768c78500f6d83285e64508",
    },
}
DEPENDENCY_IMPORT_GRAPH = [
    {
        "source": "tools/backtest_p1_deviation_4bet.py",
        "third_party_imports": ["numpy", "scipy"],
        "local_imports": ["lottery_api.database.DatabaseManager"],
        "local_transitive_third_party_imports": [
            "apscheduler",
            "fastapi",
            "numpy",
            "pydantic",
            "scikit-learn",
            "scipy",
        ],
    },
    {
        "source": "tools/backtest_p1dev_5bet.py",
        "third_party_imports": ["numpy", "scipy"],
        "local_imports": ["lottery_api.database.DatabaseManager"],
        "local_transitive_third_party_imports": [
            "apscheduler",
            "fastapi",
            "numpy",
            "pydantic",
            "scikit-learn",
            "scipy",
        ],
    },
    {
        "source": "lottery_api/database.py:DatabaseManager.get_all_draws",
        "third_party_imports": [],
        "local_imports": ["lottery_api.common.get_related_lottery_types"],
        "local_transitive_third_party_imports": [
            "apscheduler",
            "fastapi",
            "numpy",
            "pydantic",
            "scikit-learn",
            "scipy",
        ],
    },
    {
        "source": "lottery_api/common.py",
        "third_party_imports": ["fastapi"],
        "local_imports": ["lottery_api.utils.scheduler", "lottery_api.config"],
        "local_transitive_third_party_imports": [
            "apscheduler",
            "numpy",
            "pydantic",
            "scikit-learn",
            "scipy",
        ],
    },
    {
        "source": "lottery_api/utils/scheduler.py",
        "third_party_imports": ["apscheduler"],
        "local_imports": ["lottery_api.models.advanced_auto_learning"],
        "local_transitive_third_party_imports": [
            "numpy",
            "scikit-learn",
            "scipy",
        ],
    },
    {
        "source": "lottery_api/models/advanced_auto_learning.py",
        "third_party_imports": ["numpy"],
        "local_imports": ["lottery_api.models.advanced_strategies"],
        "local_transitive_third_party_imports": ["scikit-learn", "scipy"],
    },
    {
        "source": "lottery_api/models/advanced_strategies.py",
        "third_party_imports": ["numpy", "scikit-learn", "scipy"],
        "local_imports": [],
        "local_transitive_third_party_imports": [],
    },
    {
        "source": "lottery_api/config.py",
        "third_party_imports": ["pydantic"],
        "local_imports": [],
        "local_transitive_third_party_imports": [],
    },
    {
        "source": "lottery_api/utils/baseline_calculator.py",
        "third_party_imports": [],
        "local_imports": [],
        "local_transitive_third_party_imports": [],
    },
    {
        "source": "lottery_api/utils/permutation_test.py",
        "third_party_imports": [],
        "local_imports": [],
        "local_transitive_third_party_imports": [],
    },
]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
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


def require_regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"required regular file is absent or unsafe: {path}")


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        if not path.is_file():
            raise RuntimeError(f"deterministic check missing output: {path}")
        if path.read_bytes() != payload:
            raise RuntimeError(f"deterministic check mismatch: {path}")
        return
    path.write_bytes(payload)


def load_lock(project_root: Path) -> dict[str, Any]:
    lock_path = project_root / "uv.lock"
    require_regular_file(lock_path)
    with lock_path.open("rb") as handle:
        return tomllib.load(handle)


def lock_registry_packages(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for package in lock["package"]:
        source = package.get("source", {})
        if "registry" not in source:
            continue
        normalized = canonicalize_name(package["name"])
        if normalized in result:
            raise RuntimeError(f"duplicate normalized lock distribution: {normalized}")
        result[normalized] = package
    return result


def installed_distributions() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for distribution in importlib.metadata.distributions():
        metadata_name = distribution.metadata["Name"]
        normalized = canonicalize_name(metadata_name)
        if normalized in seen:
            raise RuntimeError(f"duplicate normalized installed distribution: {normalized}")
        seen.add(normalized)
        dist_info = Path(getattr(distribution, "_path"))
        metadata_path = dist_info / "METADATA"
        record_path = dist_info / "RECORD"
        require_regular_file(metadata_path)
        records.append(
            {
                "normalized_name": normalized,
                "version": distribution.version,
                "metadata_name": metadata_name,
                "distribution_metadata_sha256": sha256_path(metadata_path),
                "record_sha256_or_explicit_absence": (
                    sha256_path(record_path) if record_path.is_file() else "ABSENT"
                ),
            }
        )
    return sorted(records, key=lambda item: item["normalized_name"])


def wheelhouse_artifacts(
    runtime_root: Path,
    lock_packages: dict[str, dict[str, Any]],
    installed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    wheelhouse = runtime_root / "wheelhouse"
    if not wheelhouse.is_dir() or wheelhouse.is_symlink():
        raise RuntimeError(f"wheelhouse is absent or unsafe: {wheelhouse}")

    compatible_tag_order = {tag: index for index, tag in enumerate(sys_tags())}
    artifacts: list[dict[str, Any]] = []
    wheel_files = sorted(wheelhouse.glob("*.whl"), key=lambda path: path.name)
    if len(wheel_files) != len(installed):
        raise RuntimeError(
            f"wheelhouse count {len(wheel_files)} does not match installed count {len(installed)}"
        )

    installed_keys = {
        (record["normalized_name"], record["version"]) for record in installed
    }
    artifact_keys: set[tuple[str, str]] = set()
    for wheel_path in wheel_files:
        require_regular_file(wheel_path)
        parsed_name, parsed_version, _build, parsed_tags = parse_wheel_filename(wheel_path.name)
        normalized = canonicalize_name(parsed_name)
        version = str(parsed_version)
        key = (normalized, version)
        if key not in installed_keys:
            raise RuntimeError(f"unapproved wheelhouse artifact: {wheel_path.name}")
        if key in artifact_keys:
            raise RuntimeError(f"duplicate wheelhouse distribution: {wheel_path.name}")
        artifact_keys.add(key)

        compatible_ranks = [
            compatible_tag_order[tag] for tag in parsed_tags if tag in compatible_tag_order
        ]
        if not compatible_ranks:
            raise RuntimeError(f"incompatible wheel for this interpreter: {wheel_path.name}")

        lock_package = lock_packages.get(normalized)
        if lock_package is None or lock_package["version"] != version:
            raise RuntimeError(f"wheel is absent from exact lock: {wheel_path.name}")

        lock_wheel: dict[str, Any] | None = None
        for candidate in lock_package.get("wheels", []):
            candidate_filename = Path(urllib.parse.unquote(candidate["url"])).name
            if candidate_filename == wheel_path.name:
                lock_wheel = candidate
                break
        if lock_wheel is None:
            raise RuntimeError(f"wheel filename is absent from exact lock: {wheel_path.name}")

        best_locked_rank: int | None = None
        for candidate in lock_package.get("wheels", []):
            candidate_filename = Path(urllib.parse.unquote(candidate["url"])).name
            try:
                _name, _version, _build, candidate_tags = parse_wheel_filename(
                    candidate_filename
                )
            except ValueError:
                continue
            candidate_ranks = [
                compatible_tag_order[tag]
                for tag in candidate_tags
                if tag in compatible_tag_order
            ]
            if candidate_ranks:
                candidate_rank = min(candidate_ranks)
                best_locked_rank = (
                    candidate_rank
                    if best_locked_rank is None
                    else min(best_locked_rank, candidate_rank)
                )
        selected_rank = min(compatible_ranks)
        if best_locked_rank is None or selected_rank != best_locked_rank:
            raise RuntimeError(
                f"wheel is compatible but not the best-ranked exact locked artifact: "
                f"{wheel_path.name}"
            )

        actual_sha256 = sha256_path(wheel_path)
        approved_sha256 = lock_wheel["hash"].removeprefix("sha256:")
        if actual_sha256 != approved_sha256:
            raise RuntimeError(f"wheel hash mismatch: {wheel_path.name}")

        artifacts.append(
            {
                "normalized_name": normalized,
                "version": version,
                "filename": wheel_path.name,
                "artifact_type": "wheel",
                "platform_tags": sorted(str(tag) for tag in parsed_tags),
                "sha256": actual_sha256,
                "source_url": lock_wheel["url"],
                "selection_reason": (
                    "lowest packaging.tags.sys_tags rank among the exact locked artifacts "
                    f"selected by hashed download for {platform.system()} {platform.machine()} "
                    f"CPython {platform.python_version()}"
                ),
                "compatible_tag_rank": selected_rank,
            }
        )

    if artifact_keys != installed_keys:
        raise RuntimeError("wheelhouse and installed distribution sets differ")
    return sorted(artifacts, key=lambda item: (item["filename"], item["sha256"]))


def platform_fingerprint() -> dict[str, Any]:
    tags = [str(tag) for tag in sys_tags()]
    return {
        "schema_version": "ApprovedPlatformFingerprintV1",
        "sys_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "python_build": list(platform.python_build()),
        "platform_platform": platform.platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "platform_machine": platform.machine(),
        "platform_processor": platform.processor(),
        "sysconfig_platform": sysconfig.get_platform(),
        "byteorder": sys.byteorder,
        "compatible_tags": tags,
        "compatible_tags_sha256": sha256_bytes(canonical_bytes(tags)),
    }


def create_receipt(
    runtime_root: Path,
    artifacts: list[dict[str, Any]],
    installed: list[dict[str, Any]],
    check: bool,
) -> tuple[dict[str, Any], str]:
    artifact_by_key = {
        (artifact["normalized_name"], artifact["version"]): artifact for artifact in artifacts
    }
    installed_from = []
    for distribution in installed:
        key = (distribution["normalized_name"], distribution["version"])
        artifact = artifact_by_key.get(key)
        if artifact is None:
            raise RuntimeError(f"installed distribution has no wheel receipt: {key}")
        installed_from.append(
            {
                "normalized_name": key[0],
                "version": key[1],
                "source_artifact_filename": artifact["filename"],
                "source_artifact_sha256": artifact["sha256"],
            }
        )
    receipt = {
        "schema_version": "OfflineInstallationReceiptV1",
        "installer": "uv 0.9.6",
        "network_allowed": False,
        "offline": True,
        "no_index": True,
        "hashes_required": True,
        "wheelhouse_only": True,
        "result": "PASS",
        "installed_from": sorted(
            installed_from, key=lambda item: item["normalized_name"]
        ),
    }
    receipt_path = runtime_root / "tmp" / "offline-install-receipt.json"
    receipt_bytes = canonical_bytes(receipt)
    write_or_check(receipt_path, receipt_bytes, check)
    return receipt, sha256_bytes(receipt_bytes)


def build_outputs(project_root: Path, runtime_root: Path, check: bool) -> dict[str, str]:
    if project_root.is_symlink() or runtime_root.is_symlink():
        raise RuntimeError("project or runtime root must not be a symlink")
    lock = load_lock(project_root)
    lock_packages = lock_registry_packages(lock)
    installed = installed_distributions()

    actual_basic = [
        {
            "normalized_name": item["normalized_name"],
            "version": item["version"],
        }
        for item in installed
    ]
    lock_selected = {
        (name, package["version"])
        for name, package in lock_packages.items()
        if name not in APPROVED_PLATFORM_EXCLUDED_LOCK_DISTRIBUTIONS
    }
    actual_keys = {
        (item["normalized_name"], item["version"]) for item in actual_basic
    }
    if actual_keys != lock_selected:
        raise RuntimeError(
            f"installed distributions differ from approved platform lock: "
            f"actual={sorted(actual_keys)!r} expected={sorted(lock_selected)!r}"
        )

    artifacts = wheelhouse_artifacts(runtime_root, lock_packages, installed)
    receipt, receipt_sha256 = create_receipt(runtime_root, artifacts, installed, check)
    receipt_by_name = {
        item["normalized_name"]: item for item in receipt["installed_from"]
    }

    expected_document = {
        "schema_version": "ExpectedDistributionSetV1",
        "platform_marker": "sys_platform == 'darwin' and platform_machine == 'arm64'",
        "distributions": actual_basic,
    }
    artifacts_document = {
        "schema_version": "ApprovedArtifactSetV1",
        "artifacts": artifacts,
    }
    platform_document = platform_fingerprint()

    actual_fingerprint_distributions = []
    for item in installed:
        receipt_item = receipt_by_name[item["normalized_name"]]
        actual_fingerprint_distributions.append(
            {
                **item,
                "source_artifact_sha256": receipt_item["source_artifact_sha256"],
            }
        )

    lock_path = project_root / "uv.lock"
    runtime_document = {
        "schema_version": SCHEMA_VERSION,
        "sys_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "python_build": list(platform.python_build()),
        "platform_platform": platform.platform(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "platform_machine": platform.machine(),
        "platform_processor": platform.processor(),
        "byteorder": sys.byteorder,
        "hash_algorithm": "sha256",
        "project_lockfile_path": f"{PROJECT_RELATIVE_ROOT}/uv.lock",
        "project_lockfile_sha256": sha256_path(lock_path),
        "expected_distribution_set": actual_basic,
        "actual_distribution_set": actual_fingerprint_distributions,
        "distribution_set_match": True,
    }

    documents = {
        "approved_platform_fingerprint.json": platform_document,
        "expected_distributions.json": expected_document,
        "approved_artifacts.json": artifacts_document,
        "runtime_fingerprint.json": runtime_document,
    }
    document_bytes = {
        name: canonical_bytes(document) for name, document in documents.items()
    }
    environment_document = {
        "schema_version": "P1ReproductionEnvironmentAuthorityV1",
        "task_id": "LOTTERYNEW_BIG_LOTTO_P1_REPRODUCTION_ENVIRONMENT_BOOTSTRAP_R1",
        "source_identities": SOURCE_IDENTITIES,
        "dependency_import_graph": DEPENDENCY_IMPORT_GRAPH,
        "direct_dependencies": DIRECT_DEPENDENCIES,
        "python_authority": PYTHON_AUTHORITY,
        "lockfile": {
            "path": f"{PROJECT_RELATIVE_ROOT}/uv.lock",
            "sha256": sha256_path(lock_path),
            "requires_python": lock["requires-python"],
            "registry_distribution_count_all_platforms": len(lock_packages),
            "approved_platform_distribution_count": len(installed),
            "approved_platform_excluded_marker_distributions": sorted(
                APPROVED_PLATFORM_EXCLUDED_LOCK_DISTRIBUTIONS
            ),
        },
        "hashed_export": {
            "path": f"{PROJECT_RELATIVE_ROOT}/requirements.lock.txt",
            "sha256": sha256_path(project_root / "requirements.lock.txt"),
        },
        "expected_distribution_set_sha256": sha256_bytes(
            document_bytes["expected_distributions.json"]
        ),
        "approved_artifact_set_sha256": sha256_bytes(
            document_bytes["approved_artifacts.json"]
        ),
        "platform_fingerprint_sha256": sha256_bytes(
            document_bytes["approved_platform_fingerprint.json"]
        ),
        "runtime_fingerprint_sha256": sha256_bytes(
            document_bytes["runtime_fingerprint.json"]
        ),
        "offline_installation_receipt": {
            "sha256": receipt_sha256,
            "result": "PASS",
            "network_allowed": False,
            "wheelhouse_only": True,
            "installed_from": receipt["installed_from"],
        },
        "boundaries": {
            "environment_bootstrap_only": True,
            "strategy_semantics_modified": False,
            "database_opened": False,
            "database_copied": False,
            "database_snapshot_created": False,
            "p1_backtest_run": False,
            "production_code_modified": False,
        },
    }
    document_bytes["environment_authority.json"] = canonical_bytes(environment_document)

    output_digests: dict[str, str] = {}
    for name, payload in sorted(document_bytes.items()):
        write_or_check(project_root / name, payload, check)
        output_digests[name] = sha256_bytes(payload)
    return output_digests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    runtime_root = args.runtime_root.resolve()
    digests = build_outputs(project_root, runtime_root, args.check)
    print(
        json.dumps(
            {
                "mode": "check" if args.check else "write",
                "result": "PASS",
                "digests": digests,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
