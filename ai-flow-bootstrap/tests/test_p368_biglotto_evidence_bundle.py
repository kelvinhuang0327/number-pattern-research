import json
import shutil
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_bundle as bundle


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P368 evidence consumer bundle")


@pytest.fixture(scope="session")
def double_run():
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        first = bundle.build_bundle()
        second = bundle.build_bundle()
    finally:
        patcher.undo()
    return first, second


@pytest.fixture
def malformed_repo_root(tmp_path):
    root = tmp_path / "malformed_repo"
    for _stage, _role, _kind, relpath in api.SOURCE_ARTIFACTS:
        src = api.REPO_ROOT / relpath
        dst = root / relpath
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    corrupt_relpath = next(relpath for _s, _r, kind, relpath in api.SOURCE_ARTIFACTS if kind == "json")
    (root / corrupt_relpath).write_text("{not valid json", encoding="utf-8")
    return root


def test_build_bundle_deterministic_double_run(double_run):
    first, second = double_run
    assert first.manifest == second.manifest
    assert first.summary == second.summary
    assert first.summary_md == second.summary_md


def test_bundle_generation_succeeds_in_temp_dir(tmp_path, double_run):
    first, _ = double_run
    paths = bundle.write_bundle(first, tmp_path / "out")
    assert set(paths) == {"bundle_manifest", "bundle_summary", "bundle_summary_md"}
    for path in paths.values():
        assert path.is_file()


def test_manifest_contains_sha256_entries_for_artifacts(tmp_path, double_run):
    first, _ = double_run
    paths = bundle.write_bundle(first, tmp_path / "out")
    with open(paths["bundle_manifest"], encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["task"] == bundle.TASK
    assert manifest["artifact_count"] == len(manifest["artifacts"])
    assert manifest["artifact_count"] > 0
    source_entries = [row for row in manifest["artifacts"] if row["artifact_group"] == "source"]
    assert source_entries
    assert all(row["sha256"] and len(row["sha256"]) == 64 for row in source_entries)
    output_entries = [row for row in manifest["artifacts"] if row["artifact_group"] == "output"]
    assert output_entries


def test_summary_json_includes_scope_booleans(tmp_path, double_run):
    first, _ = double_run
    paths = bundle.write_bundle(first, tmp_path / "out")
    with open(paths["bundle_summary"], encoding="utf-8") as handle:
        summary = json.load(handle)
    assert summary["no_db"] is True
    assert summary["no_adapter"] is True
    assert summary["no_new_scoring_cohort"] is True
    assert summary["validation_status"] == "PASS"
    assert isinstance(summary["disclaimer"], str) and summary["disclaimer"]


def test_summary_markdown_includes_disclaimer(tmp_path, double_run):
    first, _ = double_run
    paths = bundle.write_bundle(first, tmp_path / "out")
    text = paths["bundle_summary_md"].read_text(encoding="utf-8")
    assert "## Disclaimer" in text
    assert "not proof of predictive performance" in text
    assert "not an out-of-sample (OOS) claim" in text
    assert "not betting advice" in text


def test_validation_failure_path_on_malformed_artifact(malformed_repo_root):
    output = bundle.build_bundle(repo_root=malformed_repo_root)
    assert output.summary["validation_status"] == "FAIL"
    assert output.summary["validation_fail_count"] >= 1
    assert output.summary["validation_failures"]
    assert any("JSONDecodeError" in message for message in output.summary["validation_failures"])
    assert bundle.bundle_exit_code(output) == 1
    assert "## Validation failures" in output.summary_md


def test_main_returns_nonzero_on_validation_failure(monkeypatch, malformed_repo_root, tmp_path):
    failing_output = bundle.build_bundle(repo_root=malformed_repo_root)
    monkeypatch.setattr(bundle, "build_bundle", lambda repo_root=None: failing_output)
    exit_code = bundle.main(["--output-dir", str(tmp_path / "out")])
    assert exit_code == 1


def test_no_db_and_no_adapter_source_guard(double_run):
    first, _ = double_run
    source_text = open(bundle.__file__, encoding="utf-8").read()
    assert "import sqlite3" not in source_text
    assert "recovered_strategies.biglotto.adapters" not in source_text
    assert first.summary["no_db"] is True
    assert first.summary["no_adapter"] is True


def test_no_forbidden_claim_phrases_in_bundle_output(double_run):
    first, _ = double_run
    combined = "\n".join(
        [
            json.dumps(first.manifest).lower(),
            json.dumps(first.summary).lower(),
            first.summary_md.lower(),
        ]
    )
    found = [phrase for phrase in api.FORBIDDEN_CLAIM_PHRASES if phrase in combined]
    assert not found


def test_cli_default_writes_bundle_and_exits_zero(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_bundle",
            "--output-dir",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "determinism double-run PASS" in result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created." in result.stdout
    for basename in bundle.BUNDLE_ARTIFACT_BASENAMES.values():
        assert (tmp_path / basename).is_file()


def test_cli_requires_output_dir_unless_print_mode():
    result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_bundle"],
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "--output-dir" in result.stderr


def test_cli_manifest_and_summary_print_modes():
    manifest_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_bundle", "--manifest"],
        check=True,
        text=True,
        capture_output=True,
    )
    manifest = json.loads(manifest_result.stdout)
    assert manifest["task"] == bundle.TASK

    summary_result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_bundle", "--summary"],
        check=True,
        text=True,
        capture_output=True,
    )
    summary = json.loads(summary_result.stdout)
    assert summary["task"] == bundle.TASK
    assert summary["no_db"] is True
