from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy
import pytest
import scipy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import HTTPException
from pydantic import BaseModel
from scipy.fft import fft, fftfreq
from scipy.stats import chi2, norm
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIRECT = {
    "apscheduler": "3.11.3",
    "fastapi": "0.140.0",
    "numpy": "2.5.1",
    "pydantic": "2.13.4",
    "pytest": "9.1.1",
    "scikit-learn": "1.9.0",
    "scipy": "1.18.0",
}


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


def test_direct_dependencies_are_exact_and_minimal() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    parsed = {}
    for requirement in project["dependencies"]:
        assert "==" in requirement
        name, version = requirement.split("==", 1)
        assert not any(token in requirement for token in ("git+", "://", "../", "./", "-e "))
        parsed[name] = version
    assert parsed == DIRECT
    assert project["requires-python"] == "==3.12.*"


def test_lock_and_hashed_export_are_complete() -> None:
    with (PROJECT_ROOT / "uv.lock").open("rb") as handle:
        lock = tomllib.load(handle)
    registry = {
        package["name"]: package["version"]
        for package in lock["package"]
        if "registry" in package.get("source", {})
    }
    expected = {
        item["normalized_name"]: item["version"]
        for item in load_json("expected_distributions.json")["distributions"]
    }
    assert registry == {
        **expected,
        "colorama": "0.4.6",
        "tzdata": "2026.3",
    }
    assert lock["requires-python"] == "==3.12.*"

    exported = (PROJECT_ROOT / "requirements.lock.txt").read_text(encoding="utf-8")
    assert "--hash=sha256:" in exported
    assert "git+" not in exported
    assert " @ file:" not in exported
    assert "\n-e " not in exported
    for name, version in registry.items():
        assert f"{name}=={version}" in exported


def test_committed_json_is_canonical_and_distribution_sets_match() -> None:
    names = [
        "approved_platform_fingerprint.json",
        "expected_distributions.json",
        "approved_artifacts.json",
        "runtime_fingerprint.json",
        "environment_authority.json",
    ]
    for name in names:
        raw = (PROJECT_ROOT / name).read_bytes()
        assert not raw.endswith(b"\n")
        assert raw == canonical_bytes(json.loads(raw))

    expected_document = load_json("expected_distributions.json")
    expected = {
        item["normalized_name"]: item["version"]
        for item in expected_document["distributions"]
    }
    runtime = load_json("runtime_fingerprint.json")
    actual = {
        item["normalized_name"]: item["version"]
        for item in runtime["actual_distribution_set"]
    }
    assert runtime["distribution_set_match"] is True
    assert actual == expected
    assert len(actual) == len(runtime["actual_distribution_set"])


def test_runtime_fingerprint_required_fields_and_hashes() -> None:
    runtime = load_json("runtime_fingerprint.json")
    schema = load_json("runtime_fingerprint.schema.json")
    for field in schema["required"]:
        assert field in runtime
        assert runtime[field] is not None
    assert runtime["schema_version"] == "RuntimeFingerprintV1"
    assert runtime["hash_algorithm"] == "sha256"
    assert runtime["python_version"] == "3.12.12"
    assert runtime["python_implementation"] == "CPython"
    assert runtime["platform_system"] == "Darwin"
    assert runtime["platform_machine"] == "arm64"
    assert SHA256_RE.fullmatch(runtime["project_lockfile_sha256"])

    for distribution in runtime["actual_distribution_set"]:
        assert SHA256_RE.fullmatch(distribution["source_artifact_sha256"])
        assert SHA256_RE.fullmatch(distribution["distribution_metadata_sha256"])
        record = distribution["record_sha256_or_explicit_absence"]
        assert record == "ABSENT" or SHA256_RE.fullmatch(record)


def test_approved_artifacts_are_unique_locked_wheels() -> None:
    artifacts = load_json("approved_artifacts.json")["artifacts"]
    expected = {
        item["normalized_name"]: item["version"]
        for item in load_json("expected_distributions.json")["distributions"]
    }
    keys = {(item["normalized_name"], item["version"]) for item in artifacts}
    assert keys == set(expected.items())
    assert len(keys) == len(artifacts)
    assert artifacts == sorted(artifacts, key=lambda item: (item["filename"], item["sha256"]))
    for artifact in artifacts:
        assert artifact["artifact_type"] == "wheel"
        assert artifact["filename"].endswith(".whl")
        assert SHA256_RE.fullmatch(artifact["sha256"])
        assert artifact["source_url"].startswith("https://files.pythonhosted.org/")
        assert artifact["platform_tags"]


def test_environment_authority_binds_outputs_and_protected_boundary() -> None:
    authority = load_json("environment_authority.json")
    digest_fields = {
        "expected_distribution_set_sha256": "expected_distributions.json",
        "approved_artifact_set_sha256": "approved_artifacts.json",
        "platform_fingerprint_sha256": "approved_platform_fingerprint.json",
        "runtime_fingerprint_sha256": "runtime_fingerprint.json",
    }
    for field, filename in digest_fields.items():
        actual = hashlib.sha256((PROJECT_ROOT / filename).read_bytes()).hexdigest()
        assert authority[field] == actual

    assert authority["offline_installation_receipt"]["result"] == "PASS"
    assert authority["offline_installation_receipt"]["network_allowed"] is False
    assert authority["offline_installation_receipt"]["wheelhouse_only"] is True
    assert authority["boundaries"] == {
        "database_copied": False,
        "database_opened": False,
        "database_snapshot_created": False,
        "environment_bootstrap_only": True,
        "p1_backtest_run": False,
        "production_code_modified": False,
        "strategy_semantics_modified": False,
    }


def test_runtime_wheelhouse_matches_receipt_when_available() -> None:
    runtime_root_value = os.environ.get("P1_RUNTIME_ROOT")
    if runtime_root_value is None:
        pytest.skip("task runtime root is intentionally absent outside focused bootstrap verification")
    runtime_root = Path(runtime_root_value)
    artifacts = load_json("approved_artifacts.json")["artifacts"]
    for artifact in artifacts:
        wheel = runtime_root / "wheelhouse" / artifact["filename"]
        assert wheel.is_file()
        assert not wheel.is_symlink()
        assert hashlib.sha256(wheel.read_bytes()).hexdigest() == artifact["sha256"]


def test_deterministic_regeneration_check_when_available() -> None:
    runtime_root_value = os.environ.get("P1_RUNTIME_ROOT")
    if runtime_root_value is None:
        pytest.skip("task runtime root is intentionally absent outside focused bootstrap verification")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "build_environment_authority.py"),
        "--project-root",
        str(PROJECT_ROOT),
        "--runtime-root",
        runtime_root_value,
        "--check",
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "PASS"' in result.stdout


def test_historical_scientific_import_surface_is_available() -> None:
    assert numpy.__version__ == "2.5.1"
    assert scipy.__version__ == "1.18.0"
    signal = numpy.array([0.0, 1.0, 0.0, -1.0])
    transformed = fft(signal)
    frequencies = fftfreq(len(signal), 1)
    assert transformed.shape == signal.shape
    assert frequencies.shape == signal.shape
    assert 0.0 < norm.cdf(0.0) < 1.0
    assert 0.0 < chi2.cdf(1.0, df=1) < 1.0


def test_get_all_draws_transitive_import_graph_is_covered() -> None:
    authority = load_json("environment_authority.json")
    graph = {
        row["source"]: row
        for row in authority["dependency_import_graph"]
    }
    database_row = graph["lottery_api/database.py:DatabaseManager.get_all_draws"]
    assert database_row["local_imports"] == [
        "lottery_api.common.get_related_lottery_types"
    ]
    required = {
        "apscheduler",
        "fastapi",
        "numpy",
        "pydantic",
        "scikit-learn",
        "scipy",
    }
    assert set(database_row["local_transitive_third_party_imports"]) == required

    expected = {
        item["normalized_name"]
        for item in load_json("expected_distributions.json")["distributions"]
    }
    direct = {
        item["normalized_name"]
        for item in authority["direct_dependencies"]
    }
    assert required <= expected
    assert required <= direct

    assert HTTPException(status_code=400).status_code == 400
    assert issubclass(BaseModel, object)
    assert AsyncIOScheduler is not None
    assert KMeans is not None
    assert DBSCAN is not None
    assert StandardScaler is not None
