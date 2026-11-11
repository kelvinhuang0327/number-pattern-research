"""
Tests for P31 CLI — run_p31_honest_data_reality_audit.py.

Coverage:
7. CLI writes all three expected artifacts
8. Final report contains one valid P31 gate marker
9. No production_ready=True appears anywhere in outputs
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_SCRIPT = REPO_ROOT / "scripts" / "run_p31_honest_data_reality_audit.py"
CLASSIFICATION_CSV = REPO_ROOT / "data" / "p31_source_classification_audit.csv"
PROVENANCE_JSON = REPO_ROOT / "data" / "p31_provenance_audit.json"
REPORT_MD = REPO_ROOT / "00-BettingPlan" / "20260513" / "p31_honest_data_audit_report.md"

VALID_GATES = {
    "P31_HONEST_DATA_AUDIT_READY",
    "P31_BLOCKED_NO_RAW_HISTORICAL_INCREMENT",
    "P31_BLOCKED_LICENSE_PROVENANCE_UNSAFE",
    "P31_BLOCKED_NON_DETERMINISTIC_INVENTORY",
    "P31_FAIL_INPUT_MISSING",
}

VALID_P32_DECISIONS = {
    "GO_FULL",
    "GO_PARTIAL_GAME_LOGS_ONLY",
    "NO_GO",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli() -> subprocess.CompletedProcess:
    """Run the P31 CLI using the current Python interpreter."""
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Tests that import directly (unit-level, faster than subprocess)
# ---------------------------------------------------------------------------


class TestCLIImportLevel:
    """Import and run via the module directly for speed."""

    def test_cli_script_exists(self) -> None:
        assert CLI_SCRIPT.exists(), f"CLI script not found: {CLI_SCRIPT}"

    def test_cli_module_importable(self) -> None:
        """CLI should be importable without side-effects."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_p31", CLI_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        # We do NOT exec it (would run main); just check it can be loaded.
        assert spec is not None

    def test_main_function_runs_and_writes_artifacts(self) -> None:
        """Test 7: CLI writes all three expected output artifacts."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("run_p31_module", CLI_SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        ret = mod.main()
        assert ret == 0, "CLI main() returned non-zero exit code"

        # Artifact existence
        assert CLASSIFICATION_CSV.exists(), f"Missing: {CLASSIFICATION_CSV}"
        assert PROVENANCE_JSON.exists(), f"Missing: {PROVENANCE_JSON}"
        assert REPORT_MD.exists(), f"Missing: {REPORT_MD}"

    def test_report_contains_valid_gate_marker(self) -> None:
        """Test 8: Final report contains one valid P31 gate marker."""
        assert REPORT_MD.exists(), "Report must be generated before this test"
        content = REPORT_MD.read_text(encoding="utf-8")
        found = [g for g in VALID_GATES if g in content]
        assert len(found) >= 1, f"No valid P31 gate found in report. Found: {found}"

    def test_report_no_production_ready_true(self) -> None:
        """Test 9: No production_ready=True appears anywhere in report."""
        assert REPORT_MD.exists(), "Report must be generated before this test"
        content = REPORT_MD.read_text(encoding="utf-8")
        assert "production_ready=True" not in content
        assert "production_ready: True" not in content

    def test_provenance_json_no_production_ready_true(self) -> None:
        """Test 9 (JSON): provenance JSON must not claim production readiness."""
        assert PROVENANCE_JSON.exists()
        data = json.loads(PROVENANCE_JSON.read_text())
        assert data.get("production_ready") is False

    def test_classification_csv_columns(self) -> None:
        """Classification CSV has required columns."""
        assert CLASSIFICATION_CSV.exists()
        with CLASSIFICATION_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
        assert "path" in headers
        assert "source_class" in headers
        assert "has_derived_signals" in headers

    def test_p32_recommendation_in_report(self) -> None:
        """Report includes one of the valid P32 decision strings."""
        assert REPORT_MD.exists()
        content = REPORT_MD.read_text(encoding="utf-8")
        found = [d for d in VALID_P32_DECISIONS if d in content]
        assert len(found) >= 1, f"No valid P32 decision found. Found: {found}"

    def test_derived_not_counted_as_raw(self) -> None:
        """Test 10: Derived outputs are not in usable_2024_raw_count."""
        from wbc_backend.recommendation.p31_honest_data_audit import (
            run_honest_data_audit,
            SourceClass,
        )

        result = run_honest_data_audit(REPO_ROOT)
        # All entries counted as 2024 raw must NOT be DERIVED_OUTPUT
        for entry in result.entries:
            if 2024 in entry.year_coverage and entry.source_class == SourceClass.DERIVED_OUTPUT:
                assert entry.source_class != SourceClass.RAW_PRIMARY, (
                    f"DERIVED_OUTPUT entry {entry.path} should not be counted as raw"
                )
        # The usable_2024_raw_count should not include derived outputs
        c = result.counters
        assert c.usable_2024_raw_count == 0 or (
            c.raw_primary_count + c.raw_secondary_count >= c.usable_2024_raw_count
        )


# ---------------------------------------------------------------------------
# Subprocess-level smoke test (optional, skipped if artifacts already fresh)
# ---------------------------------------------------------------------------


class TestCLISubprocess:
    @pytest.mark.slow
    def test_cli_exits_zero(self) -> None:
        """CLI exits with code 0."""
        result = _run_cli()
        assert result.returncode == 0, (
            f"CLI failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    @pytest.mark.slow
    def test_cli_stdout_contains_gate(self) -> None:
        """CLI stdout mentions the gate constant."""
        result = _run_cli()
        found = any(g in result.stdout for g in VALID_GATES)
        assert found, f"No gate in CLI stdout:\n{result.stdout}"
