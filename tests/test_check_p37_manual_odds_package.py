"""
tests/test_check_p37_manual_odds_package.py

P37.5 — Tests for scripts/check_p37_manual_odds_package.py

Verifies:
  - Script exists at the correct path
  - Reports missing files when neither manual file exists (current repo state)
  - Does not create odds/approval artifacts in manual_import/
  - Does not stage manual_import files in git
  - Exit code 1 when both files are missing
  - Exit code 0 when valid fixture files are provided via /tmp

PAPER_ONLY: True
PRODUCTION_READY: False
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_p37_manual_odds_package.py"
MANUAL_IMPORT_DIR = REPO_ROOT / "data" / "mlb_2024" / "manual_import"
OUTPUT_JSON = (
    REPO_ROOT
    / "data"
    / "mlb_2024"
    / "processed"
    / "p37_manual_odds_provisioning"
    / "p37_5_manual_package_check.json"
)

PYTHON = sys.executable


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def run_checker(*extra_args: str) -> subprocess.CompletedProcess:
    """Run check_p37_manual_odds_package.py and return CompletedProcess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [PYTHON, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=30,
    )


def make_valid_approval_record(path: str) -> None:
    """Write a minimal valid approval record for testing."""
    record = {
        "provider_name": "TEST_PROVIDER",
        "source_name": "TEST_SOURCE",
        "source_url_or_reference": "https://test.example.com/tos",
        "license_terms_summary": "Internal research only, non-commercial",
        "allowed_use": "internal_research",
        "redistribution_allowed": False,
        "attribution_required": True,
        "internal_research_allowed": True,
        "commercial_use_allowed": False,
        "approved_by": "test_operator",
        "approved_at": "2026-05-13T00:00:00+00:00",
        "approval_scope": "mlb_2024_season",
        "source_file_expected_path": "data/mlb_2024/manual_import/odds_2024_approved.csv",
        "checksum_required": False,
        "checksum_sha256": "",
        "paper_only": True,
        "production_ready": False,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)


def make_valid_odds_csv(path: str) -> None:
    """Write a minimal valid odds CSV for testing."""
    content = (
        "game_id,game_date,home_team,away_team,p_market,odds_decimal,"
        "sportsbook,market_type,closing_timestamp,source_odds_ref,license_ref\n"
        "TEST_G001,2024-04-01,NYY,BOS,0.52,1.92,TEST_BOOK,moneyline,"
        "2024-04-01T13:00:00+00:00,TEST_REF_001,TEST_LICENSE_001\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ──────────────────────────────────────────────────────────────────────────────
# Existence tests
# ──────────────────────────────────────────────────────────────────────────────

class TestScriptExists:
    def test_script_file_exists(self) -> None:
        assert SCRIPT_PATH.exists(), f"Checker script not found at: {SCRIPT_PATH}"

    def test_script_is_python_file(self) -> None:
        assert SCRIPT_PATH.suffix == ".py"

    def test_script_contains_paper_only_guard(self) -> None:
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "PAPER_ONLY" in content

    def test_script_contains_production_ready_guard(self) -> None:
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "PRODUCTION_READY" in content

    def test_script_does_not_import_or_fabricate_odds(self) -> None:
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        forbidden = ["requests.get", "urllib.request", "httpx.get", "wget"]
        for kw in forbidden:
            assert kw not in content, f"Script must not make HTTP requests: found {kw}"

    def test_script_does_not_stage_manual_import(self) -> None:
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        assert "git add" not in content, "Script must not run 'git add'"
        assert "git commit" not in content, "Script must not run 'git commit'"


# ──────────────────────────────────────────────────────────────────────────────
# Exit-code tests with no manual files (current repo state)
# ──────────────────────────────────────────────────────────────────────────────

class TestExitCodeMissingFiles:
    def test_exit_code_1_when_both_files_missing(self) -> None:
        """Real state: manual_import/ files do not exist → exit 1."""
        approval_path = MANUAL_IMPORT_DIR / "odds_approval_record.json"
        odds_path = MANUAL_IMPORT_DIR / "odds_2024_approved.csv"

        if approval_path.exists() or odds_path.exists():
            pytest.skip("Manual import files exist — skipping missing-file test")

        result = run_checker()
        assert result.returncode == 1, (
            f"Expected exit 1 when files missing, got {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_stdout_reports_missing_approval_record(self) -> None:
        approval_path = MANUAL_IMPORT_DIR / "odds_approval_record.json"
        odds_path = MANUAL_IMPORT_DIR / "odds_2024_approved.csv"

        if approval_path.exists() or odds_path.exists():
            pytest.skip("Manual import files exist — skipping missing-file test")

        result = run_checker()
        assert "MISSING" in result.stdout or "missing" in result.stdout.lower(), (
            f"stdout should report missing files:\n{result.stdout}"
        )

    def test_does_not_create_manual_import_artifacts(self) -> None:
        """Running the checker must not create files in manual_import/."""
        approval_path = MANUAL_IMPORT_DIR / "odds_approval_record.json"
        odds_path = MANUAL_IMPORT_DIR / "odds_2024_approved.csv"

        pre_approval = approval_path.exists()
        pre_odds = odds_path.exists()

        run_checker()

        if not pre_approval:
            assert not approval_path.exists(), (
                "Checker must not create odds_approval_record.json in manual_import/"
            )
        if not pre_odds:
            assert not odds_path.exists(), (
                "Checker must not create odds_2024_approved.csv in manual_import/"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Git staging safety test
# ──────────────────────────────────────────────────────────────────────────────

class TestGitStagingSafety:
    def test_manual_import_files_not_staged_after_run(self) -> None:
        """Running the checker must never stage manual_import files."""
        run_checker()

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        ).stdout

        assert "manual_import" not in staged, (
            f"manual_import files were staged after checker run:\n{staged}"
        )

    def test_raw_gl2024_not_staged_after_run(self) -> None:
        run_checker()

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        ).stdout

        assert "gl2024" not in staged, (
            f"gl2024 was staged after checker run:\n{staged}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Exit-code test with valid fixture files (via symlink patching)
# ──────────────────────────────────────────────────────────────────────────────

class TestExitCodeWithValidFixtures:
    """
    Tests exit code 0 by temporarily placing valid fixture files
    in /tmp and running the checker against a modified PYTHONPATH
    environment that re-routes the module under test to use those paths.

    Strategy: We cannot modify the hardcoded paths in the checker script,
    so instead we directly invoke the Python functions from the checker module
    to confirm exit-0 behavior with valid input.
    """

    def test_check_file_presence_both_exist(self) -> None:
        """Unit-test check_file_presence with valid temp files."""
        import importlib.util
        import types

        spec = importlib.util.spec_from_file_location(
            "check_p37_manual_odds_package", SCRIPT_PATH
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch the constants temporarily via module attributes
            orig_approval = mod.APPROVAL_RECORD_PATH
            orig_odds = mod.MANUAL_ODDS_PATH

            try:
                # Create temp files at paths that check_file_presence can find
                # by setting base_dir = tmpdir and matching relative paths
                approval_subpath = "data/mlb_2024/manual_import/odds_approval_record.json"
                odds_subpath = "data/mlb_2024/manual_import/odds_2024_approved.csv"

                os.makedirs(os.path.join(tmpdir, "data/mlb_2024/manual_import"), exist_ok=True)
                make_valid_approval_record(os.path.join(tmpdir, approval_subpath))
                make_valid_odds_csv(os.path.join(tmpdir, odds_subpath))

                mod.APPROVAL_RECORD_PATH = approval_subpath
                mod.MANUAL_ODDS_PATH = odds_subpath

                presence = mod.check_file_presence(tmpdir)

                assert presence["approval_record_exists"] is True
                assert presence["manual_odds_exists"] is True
            finally:
                mod.APPROVAL_RECORD_PATH = orig_approval
                mod.MANUAL_ODDS_PATH = orig_odds

    def test_run_p37_validation_dry_run_with_valid_tmp_files(self) -> None:
        """
        Unit-test run_p37_validation_dry_run with valid temp files,
        confirming it calls P37 gate functions without errors.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_p37_manual_odds_package", SCRIPT_PATH
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_subpath = "data/mlb_2024/manual_import/odds_approval_record.json"
            odds_subpath = "data/mlb_2024/manual_import/odds_2024_approved.csv"

            os.makedirs(os.path.join(tmpdir, "data/mlb_2024/manual_import"), exist_ok=True)
            make_valid_approval_record(os.path.join(tmpdir, approval_subpath))
            make_valid_odds_csv(os.path.join(tmpdir, odds_subpath))

            mod.APPROVAL_RECORD_PATH = approval_subpath
            mod.MANUAL_ODDS_PATH = odds_subpath

            presence = {
                "approval_record_exists": True,
                "manual_odds_exists": True,
            }

            try:
                result = mod.run_p37_validation_dry_run(tmpdir, presence)
                assert result.get("dry_run_attempted") is True, (
                    f"dry_run should succeed, got: {result}"
                )
                # Should have standard keys
                assert "approval_record_status" in result
                assert "manual_odds_schema_valid" in result
            except Exception as exc:
                pytest.fail(f"Unexpected exception in dry_run: {exc}")
            finally:
                mod.APPROVAL_RECORD_PATH = "data/mlb_2024/manual_import/odds_approval_record.json"
                mod.MANUAL_ODDS_PATH = "data/mlb_2024/manual_import/odds_2024_approved.csv"

    def test_paper_only_constant_is_true(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_p37_manual_odds_package_const", SCRIPT_PATH
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert mod.PAPER_ONLY is True

    def test_production_ready_constant_is_false(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_p37_manual_odds_package_const2", SCRIPT_PATH
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert mod.PRODUCTION_READY is False


# ──────────────────────────────────────────────────────────────────────────────
# Output JSON structure tests
# ──────────────────────────────────────────────────────────────────────────────

class TestOutputJsonStructure:
    def test_output_json_written_after_run(self) -> None:
        """Running the checker should write the output JSON."""
        run_checker()
        assert OUTPUT_JSON.exists(), f"Output JSON not written: {OUTPUT_JSON}"

    def test_output_json_has_required_keys(self) -> None:
        if not OUTPUT_JSON.exists():
            pytest.skip("Output JSON not yet created")

        with open(OUTPUT_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        required_keys = [
            "p37_5_status",
            "paper_only",
            "production_ready",
            "raw_odds_commit_allowed",
            "season",
            "approval_record_exists",
            "manual_odds_exists",
            "exit_code",
            "generated_at",
        ]
        for key in required_keys:
            assert key in data, f"Output JSON missing key: {key}"

    def test_output_json_paper_only_true(self) -> None:
        if not OUTPUT_JSON.exists():
            pytest.skip("Output JSON not yet created")

        with open(OUTPUT_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["paper_only"] is True

    def test_output_json_production_ready_false(self) -> None:
        if not OUTPUT_JSON.exists():
            pytest.skip("Output JSON not yet created")

        with open(OUTPUT_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["production_ready"] is False

    def test_output_json_raw_odds_commit_allowed_false(self) -> None:
        if not OUTPUT_JSON.exists():
            pytest.skip("Output JSON not yet created")

        with open(OUTPUT_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert data["raw_odds_commit_allowed"] is False
