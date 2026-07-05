import json
import shutil
import sqlite3
import subprocess
import sys

import pytest

from recovered_strategies.biglotto import no_db_evidence_api as api
from recovered_strategies.biglotto import no_db_evidence_bundle as bundle
from recovered_strategies.biglotto import no_db_evidence_e2e_smoke as smoke


def _blocked_connect(*args, **kwargs):
    raise AssertionError("sqlite3.connect must not be called by P372 E2E smoke CLI")


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


def test_run_smoke_succeeds_in_temp_dir(tmp_path):
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        output = smoke.run_smoke(tmp_path / "bundle")
    finally:
        patcher.undo()
    assert output.summary["status"] == "PASS"
    assert smoke.smoke_exit_code(output) == 0
    assert output.summary["artifact_count"] > 0
    assert output.summary["bundle_manifest_path"] is not None
    assert output.summary["bundle_summary_path"] is not None


def test_summary_json_has_required_booleans_and_disclaimer(tmp_path):
    output = smoke.run_smoke(tmp_path / "bundle")
    paths = smoke.write_summary(output, tmp_path / "out")
    with open(paths["summary_json"], encoding="utf-8") as handle:
        summary = json.load(handle)
    assert summary["status"] == "PASS"
    assert isinstance(summary["artifact_count"], int) and summary["artifact_count"] > 0
    assert summary["bundle_manifest_path"]
    assert summary["bundle_summary_path"]
    assert summary["no_db"] is True
    assert summary["no_adapter"] is True
    assert summary["no_new_scoring_cohort"] is True
    assert isinstance(summary["disclaimer"], str) and summary["disclaimer"]


def test_summary_markdown_has_safe_wording(tmp_path):
    output = smoke.run_smoke(tmp_path / "bundle")
    paths = smoke.write_summary(output, tmp_path / "out")
    text = paths["summary_md"].read_text(encoding="utf-8")
    assert "## Disclaimer" in text
    assert "not proof of predictive performance" in text
    assert "not an out-of-sample (OOS) claim" in text
    assert "not betting advice" in text


def test_failure_path_returns_nonzero_on_malformed_artifact(malformed_repo_root, tmp_path):
    output = smoke.run_smoke(tmp_path / "bundle", repo_root=malformed_repo_root)
    assert output.summary["status"] == "FAIL"
    assert smoke.smoke_exit_code(output) == 1
    assert output.summary["error"]
    assert output.summary["bundle_manifest_path"] is None
    assert output.summary["bundle_summary_path"] is None


def test_main_returns_nonzero_on_failure(monkeypatch, tmp_path):
    failing_output = smoke.SmokeOutput(
        summary={
            "task": smoke.TASK,
            "status": "FAIL",
            "artifact_count": 0,
            "bundle_manifest_path": None,
            "bundle_summary_path": None,
            "no_db": True,
            "no_adapter": True,
            "no_new_scoring_cohort": True,
            "disclaimer": smoke.DISCLAIMER,
            "error": "synthetic failure for test",
        },
        summary_md="synthetic\n",
    )
    monkeypatch.setattr(smoke, "run_smoke", lambda bundle_dir, repo_root=None: failing_output)
    exit_code = smoke.main(["--output-dir", str(tmp_path / "out")])
    assert exit_code == 1
    assert (tmp_path / "out" / "e2e_smoke_summary.json").is_file()


def test_no_db_open_or_write_occurs(tmp_path):
    patcher = pytest.MonkeyPatch()
    patcher.setattr(sqlite3, "connect", _blocked_connect)
    try:
        output = smoke.run_smoke(tmp_path / "bundle")
    finally:
        patcher.undo()
    assert output.summary["status"] == "PASS"
    assert output.summary["no_db"] is True


def test_no_adapter_import_or_call(tmp_path):
    source_text = open(smoke.__file__, encoding="utf-8").read()
    import_lines = [line for line in source_text.splitlines() if line.strip().startswith(("import ", "from "))]
    assert "import sqlite3" not in source_text
    assert not any("adapter" in line.lower() for line in import_lines)
    smoke.run_smoke(tmp_path / "bundle")
    assert "recovered_strategies.biglotto.adapters" not in sys.modules


def test_p367_p368_focused_tests_still_pass():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_p367_biglotto_evidence_api.py",
            "tests/test_p368_biglotto_evidence_bundle.py",
        ],
        cwd=str(api.REPO_ROOT),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_output_contains_forbidden_claim_phrases(tmp_path):
    output = smoke.run_smoke(tmp_path / "bundle")
    paths = smoke.write_summary(output, tmp_path / "out")
    combined = "\n".join(
        [
            paths["summary_json"].read_text(encoding="utf-8").lower(),
            paths["summary_md"].read_text(encoding="utf-8").lower(),
        ]
    )
    found = [phrase for phrase in api.FORBIDDEN_CLAIM_PHRASES if phrase in combined]
    assert not found
    for banned_word in ("winning number", "recommended number", "bet ", "wager"):
        assert banned_word not in combined


def test_cli_default_writes_summary_and_exits_zero(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovered_strategies.biglotto.no_db_evidence_e2e_smoke",
            "--output-dir",
            str(tmp_path),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "status=PASS" in result.stdout
    assert "No DB was opened or written; no adapters were called; no new scoring cohort was created." in result.stdout
    assert (tmp_path / "e2e_smoke_summary.json").is_file()
    assert (tmp_path / "e2e_smoke_summary.md").is_file()
    assert (tmp_path / "bundle" / "bundle_manifest.json").is_file()


def test_cli_requires_output_dir():
    result = subprocess.run(
        [sys.executable, "-m", "recovered_strategies.biglotto.no_db_evidence_e2e_smoke"],
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "--output-dir" in result.stderr
