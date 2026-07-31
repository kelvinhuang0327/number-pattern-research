from __future__ import annotations

import ast
import base64
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy
import pytest
import scipy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import HTTPException
from pydantic import BaseModel
from scipy.fft import fft
from sklearn.cluster import KMeans


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = PROJECT_ROOT / "tools" / "build_environment_authority.py"
SPEC = importlib.util.spec_from_file_location("p1_env_r2_builder", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
SHA256_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


def load_json(name: str) -> dict:
    return json.loads((PROJECT_ROOT / name).read_text(encoding="utf-8"))


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def record_hash(payload: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
    return "sha256=" + encoded.rstrip(b"=").decode("ascii")


def write_record(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def fixture_install(tmp_path: Path) -> tuple[Path, Path, list[list[str]]]:
    root = tmp_path / "install"
    site = root / "lib" / "python3.12" / "site-packages"
    package = site / "demo" / "__init__.py"
    dist_info = site / "demo-1.0.dist-info"
    package.parent.mkdir(parents=True)
    dist_info.mkdir()
    package.write_bytes(b"VALUE = 1\n")
    metadata = dist_info / "METADATA"
    metadata.write_bytes(b"Metadata-Version: 2.4\nName: demo\nVersion: 1.0\n")
    uv_cache = dist_info / "uv_cache.json"
    uv_cache.write_bytes(
        b'{"timestamp":{"secs_since_epoch":1,"nanos_since_epoch":2}}'
    )
    record = dist_info / "RECORD"
    rows = [
        ["demo/__init__.py", record_hash(package.read_bytes()), str(package.stat().st_size)],
        [
            "demo-1.0.dist-info/METADATA",
            record_hash(metadata.read_bytes()),
            str(metadata.stat().st_size),
        ],
        [
            "demo-1.0.dist-info/uv_cache.json",
            record_hash(uv_cache.read_bytes()),
            str(uv_cache.stat().st_size),
        ],
        ["demo-1.0.dist-info/RECORD", "", ""],
    ]
    write_record(record, rows)
    return root, dist_info, rows


def test_frozen_r1_environment_inputs_are_byte_identical() -> None:
    for name, expected in BUILDER.FROZEN_INPUT_SHA256.items():
        assert hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() == expected


def test_committed_generated_json_is_canonical() -> None:
    names = [
        "supersedes.json",
        "installer_metadata_policy.json",
        "runtime_fingerprint.schema.json",
        "approved_platform_fingerprint.json",
        "expected_distributions.json",
        "approved_artifacts.json",
        "installation_receipt.json",
        "runtime_fingerprint.json",
        "environment_authority.json",
    ]
    for name in names:
        raw = (PROJECT_ROOT / name).read_bytes()
        assert not raw.endswith(b"\n")
        assert raw == canonical_bytes(json.loads(raw))


def test_supersession_is_narrow_and_preserves_r1_facts() -> None:
    document = load_json("supersedes.json")
    assert document["r1_merge_commit"] == BUILDER.R1_MERGE_COMMIT
    assert (
        document["r1_environment_authority_sha256"]
        == BUILDER.R1_ENVIRONMENT_AUTHORITY_SHA256
    )
    assert document["superseded_acceptance_field"].endswith(
        "record_sha256_or_explicit_absence as an equality gate"
    )
    assert document["replacement_acceptance_field"] == "record_semantic_sha256"
    assert document["r2_effective_schema_version"] == "RuntimeFingerprintV2"


def test_installer_metadata_policy_has_only_two_exact_exclusions() -> None:
    policy = load_json("installer_metadata_policy.json")
    assert policy["schema_version"] == "InstallerMetadataPolicyV1"
    assert policy["wildcard_exclusions_allowed"] is False
    assert policy["all_other_package_payload_and_standard_metadata_included"] is True
    assert [row["selector"] for row in policy["semantic_record_exclusions"]] == [
        "exact_distribution_record_self_path",
        "exact_distribution_dist_info_uv_cache_json_path",
    ]
    assert "uv_cache.json" in policy[
        "installer_generated_provenance_metadata"
    ]["exact_basename"]


def test_preinstall_receipt_binds_all_approved_artifacts_and_targets() -> None:
    receipt = load_json("installation_receipt.json")
    approved = load_json("approved_artifacts.json")["artifacts"]
    assert receipt["generated_before_installation"] is True
    assert receipt["offline"] is True
    assert receipt["no_index"] is True
    assert receipt["hashes_required"] is True
    assert len(receipt["distributions"]) == len(approved) == 23
    assert {
        row["target_install_identity"] for row in receipt["targets"]
    } == {"install-a", "install-b", "verification-install"}
    for row in receipt["distributions"]:
        assert SHA256_RE.fullmatch(row["approved_wheel_sha256"])
        assert row["approved_wheel_filename"].endswith(".whl")
        assert row["wheel_platform_tags"]
        assert row["target_install_identities"] == [
            "install-a",
            "install-b",
            "verification-install",
        ]


def test_runtime_v2_required_distribution_fields_and_sets() -> None:
    runtime = load_json("runtime_fingerprint.json")
    schema = load_json("runtime_fingerprint.schema.json")
    assert runtime["schema_version"] == "RuntimeFingerprintV2"
    for field in schema["required"]:
        assert field in runtime
    assert runtime["distribution_set_match"] is True
    assert len(runtime["actual_distribution_set"]) == 23
    required = {
        "normalized_name",
        "version",
        "metadata_name",
        "source_artifact_sha256",
        "distribution_metadata_sha256",
        "record_semantic_sha256",
        "record_raw_sha256",
        "installer_metadata_policy_version",
        "installer_metadata_paths",
    }
    for distribution in runtime["actual_distribution_set"]:
        assert required <= distribution.keys()
        assert SHA256_RE.fullmatch(distribution["source_artifact_sha256"])
        assert SHA256_RE.fullmatch(distribution["distribution_metadata_sha256"])
        assert SHA256_RE.fullmatch(distribution["record_semantic_sha256"])
        assert distribution["record_raw_sha256"]["diagnostic_only"] is True


def test_two_mtime_varied_installs_have_identical_v2_fingerprints() -> None:
    authority = load_json("environment_authority.json")
    v2 = authority["v2_fingerprint"]
    assert v2["byte_identity"] is True
    assert len(set(v2["per_install_sha256"].values())) == 1
    root_cause = authority["root_cause"]
    assert root_cause["distribution_count"] == 23
    assert root_cause["metadata_match_count"] == 23
    assert root_cause["semantic_record_match_count"] == 23
    assert root_cause["raw_record_mismatch_count"] == 23
    assert root_cause["uv_cache_ctime_causal_match_count"] == 23
    classification = root_cause["uv_cache_field_classification"]
    assert classification["complete_document_fields"] == [
        "commit",
        "directories",
        "env",
        "tags",
        "timestamp",
    ]
    assert classification["stable_fields"] == [
        "commit",
        "directories",
        "env",
        "tags",
    ]
    assert classification["unstable_fields"] == ["timestamp"]
    for field in classification["stable_fields"]:
        assert classification["fields"][field][
            "install_a_install_b_equal_count"
        ] == 23
    assert classification["fields"]["timestamp"][
        "install_a_install_b_different_count"
    ] == 23
    for row in root_cause["rows"]:
        assert set(row["uv_cache_contents"]) == {
            "install-a",
            "install-b",
            "verification-install",
        }
        for document in row["uv_cache_contents"].values():
            assert set(document) == set(classification["complete_document_fields"])


def test_v1_raw_fingerprint_is_nondeterministic_and_superseded() -> None:
    v1 = load_json("environment_authority.json")["v1_raw_fingerprint"]
    assert v1["diagnostic_only"] is True
    assert v1["superseded"] is True
    assert v1["nondeterministic"] is True
    assert v1["per_install_sha256"]["install-a"] != v1["per_install_sha256"]["install-b"]


def test_historical_runtime_import_surface_remains_available() -> None:
    assert numpy.__version__ == "2.5.1"
    assert scipy.__version__ == "1.18.0"
    assert fft(numpy.array([0.0, 1.0, 0.0, -1.0])).shape == (4,)
    assert HTTPException(status_code=400).status_code == 400
    assert issubclass(BaseModel, object)
    assert AsyncIOScheduler is not None
    assert KMeans is not None


def test_changing_included_package_file_invalidates_semantic_record(
    tmp_path: Path,
) -> None:
    root, dist_info, _rows = fixture_install(tmp_path)
    (dist_info.parent / "demo" / "__init__.py").write_bytes(b"VALUE = 2\n")
    with pytest.raises(BUILDER.RecordValidationError, match="hash mismatch"):
        BUILDER.semantic_record(root, dist_info)


def test_changing_metadata_invalidates_distribution_fingerprint() -> None:
    distribution = {
        "normalized_name": "demo",
        "version": "1.0",
        "metadata_name": "demo",
        "source_artifact_sha256": "a" * 64,
        "distribution_metadata_sha256": "b" * 64,
        "record_semantic_sha256": "c" * 64,
        "installer_metadata_policy_version": "InstallerMetadataPolicyV1",
        "installer_metadata_paths": ["lib/python3.12/site-packages/demo-1.0.dist-info/uv_cache.json"],
    }
    original = BUILDER.distribution_acceptance_fingerprint(distribution)
    distribution["distribution_metadata_sha256"] = "d" * 64
    assert BUILDER.distribution_acceptance_fingerprint(distribution) != original


def test_changing_source_artifact_invalidates_environment_fingerprint() -> None:
    runtime = load_json("runtime_fingerprint.json")
    payload = runtime["environment_fingerprint_acceptance_payload"]
    original = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    mutated = json.loads(json.dumps(payload))
    mutated["actual_distribution_set"][0]["source_artifact_sha256"] = "0" * 64
    assert hashlib.sha256(canonical_bytes(mutated)).hexdigest() != original


def test_adding_included_record_row_changes_semantic_digest(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    original = BUILDER.semantic_record(root, dist_info)["record_semantic_sha256"]
    extra = dist_info.parent / "demo" / "extra.py"
    extra.write_bytes(b"EXTRA = 1\n")
    rows.insert(
        -1,
        ["demo/extra.py", record_hash(extra.read_bytes()), str(extra.stat().st_size)],
    )
    write_record(dist_info / "RECORD", rows)
    assert BUILDER.semantic_record(root, dist_info)["record_semantic_sha256"] != original


def test_removing_included_record_row_changes_semantic_digest(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    original = BUILDER.semantic_record(root, dist_info)["record_semantic_sha256"]
    write_record(dist_info / "RECORD", rows[1:])
    assert BUILDER.semantic_record(root, dist_info)["record_semantic_sha256"] != original


def test_duplicate_record_paths_invalidate(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    rows.insert(1, list(rows[0]))
    write_record(dist_info / "RECORD", rows)
    with pytest.raises(BUILDER.RecordValidationError, match="duplicate"):
        BUILDER.semantic_record(root, dist_info)


def test_malformed_csv_invalidates(tmp_path: Path) -> None:
    root, dist_info, _rows = fixture_install(tmp_path)
    (dist_info / "RECORD").write_text('"unterminated', encoding="utf-8")
    with pytest.raises(BUILDER.RecordValidationError, match="malformed"):
        BUILDER.semantic_record(root, dist_info)


def test_path_traversal_outside_target_invalidates(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    rows.insert(-1, ["../../../../outside", record_hash(b"x"), "1"])
    write_record(dist_info / "RECORD", rows)
    with pytest.raises(BUILDER.RecordValidationError, match="traverses"):
        BUILDER.semantic_record(root, dist_info)


def test_absolute_record_path_invalidates(tmp_path: Path) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    rows.insert(-1, ["/absolute", record_hash(b"x"), "1"])
    write_record(dist_info / "RECORD", rows)
    with pytest.raises(BUILDER.RecordValidationError, match="absolute"):
        BUILDER.semantic_record(root, dist_info)


def test_invalid_record_hash_and_size_invalidate(
    tmp_path: Path,
) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    bad_hash = [list(row) for row in rows]
    bad_hash[0][1] = "sha256=not-valid"
    write_record(dist_info / "RECORD", bad_hash)
    with pytest.raises(BUILDER.RecordValidationError, match="hash encoding"):
        BUILDER.semantic_record(root, dist_info)
    bad_size = [list(row) for row in rows]
    bad_size[0][2] = "-1"
    write_record(dist_info / "RECORD", bad_size)
    with pytest.raises(BUILDER.RecordValidationError, match="size"):
        BUILDER.semantic_record(root, dist_info)


def test_any_third_exclusion_invalidates(tmp_path: Path) -> None:
    root, dist_info, _rows = fixture_install(tmp_path)
    exact = {
        (dist_info / "RECORD").relative_to(root).as_posix(),
        (dist_info / "uv_cache.json").relative_to(root).as_posix(),
        (dist_info.parent / "demo" / "__init__.py").relative_to(root).as_posix(),
    }
    with pytest.raises(BUILDER.RecordValidationError, match="exactly"):
        BUILDER.semantic_record(root, dist_info, excluded_paths=exact)


def test_uv_cache_only_mutation_leaves_semantic_digest_unchanged(
    tmp_path: Path,
) -> None:
    root, dist_info, rows = fixture_install(tmp_path)
    original_result = BUILDER.semantic_record(root, dist_info)
    original = original_result["record_semantic_sha256"]
    original_raw = original_result["record_raw_sha256"]
    uv_cache = dist_info / "uv_cache.json"
    uv_cache.write_bytes(
        b'{"timestamp":{"secs_since_epoch":9,"nanos_since_epoch":8}}'
    )
    for row in rows:
        if row[0].endswith("uv_cache.json"):
            row[1] = record_hash(uv_cache.read_bytes())
            row[2] = str(uv_cache.stat().st_size)
    write_record(dist_info / "RECORD", rows)
    changed = BUILDER.semantic_record(root, dist_info)
    assert changed["record_semantic_sha256"] == original
    assert changed["record_raw_sha256"] != original_raw


def test_extra_or_missing_distribution_invalidates() -> None:
    expected = [("a", "1"), ("b", "2")]
    valid = [
        {"normalized_name": "a", "version": "1"},
        {"normalized_name": "b", "version": "2"},
    ]
    BUILDER.validate_distribution_sets(expected, valid)
    with pytest.raises(RuntimeError, match="distribution set mismatch"):
        BUILDER.validate_distribution_sets(expected, valid[:-1])
    with pytest.raises(RuntimeError, match="distribution set mismatch"):
        BUILDER.validate_distribution_sets(
            expected, [*valid, {"normalized_name": "c", "version": "3"}]
        )


def test_semantic_serialization_has_contract_order_and_no_newline(
    tmp_path: Path,
) -> None:
    root, dist_info, _rows = fixture_install(tmp_path)
    result = BUILDER.semantic_record(root, dist_info)
    assert SHA256_RE.fullmatch(result["record_semantic_sha256"])
    sample = BUILDER.semantic_canonical_bytes(
        [{"path": "a", "hash": "sha256=x", "size": 1}]
    )
    assert sample == b'[{"path":"a","hash":"sha256=x","size":1}]'
    assert not sample.endswith(b"\n")


def test_no_database_api_or_database_path_is_referenced() -> None:
    tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
    imported_roots = set()
    database_path_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if lowered.endswith((".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm")):
                database_path_literals.append(node.value)
    assert "sqlite3" not in imported_roots
    assert database_path_literals == []
    boundaries = load_json("environment_authority.json")["boundaries"]
    assert boundaries["database_opened"] is False
    assert boundaries["database_read"] is False


def test_deterministic_regeneration_check() -> None:
    runtime_root = os.environ["P1_R2_RUNTIME_ROOT"]
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--project-root",
            str(PROJECT_ROOT),
            "--runtime-root",
            runtime_root,
            "--check",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "PASS"' in result.stdout
