"""Tests for scripts/run_p34_dual_source_acquisition_plan.py CLI"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

# Path to the CLI script
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLI_SCRIPT = os.path.join(_REPO_ROOT, "scripts", "run_p34_dual_source_acquisition_plan.py")
_VENV_PYTHON = os.path.join(_REPO_ROOT, ".venv", "bin", "python")

# Use the venv python if available
_PYTHON = _VENV_PYTHON if os.path.isfile(_VENV_PYTHON) else sys.executable

# P34 prerequisite fixtures
_P32_DIR = os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed")
_P33_DIR = os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed", "p33_joined_input_gap")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_cli(*extra_args, output_dir=None, capture=True):
    """Run the P34 CLI and return (returncode, stdout, stderr)."""
    if output_dir is None:
        raise ValueError("output_dir required")
    args = [
        _PYTHON, _CLI_SCRIPT,
        "--p32-dir", _P32_DIR,
        "--p33-dir", _P33_DIR,
        "--output-dir", output_dir,
        "--paper-only", "true",
        "--skip-determinism-check",
    ]
    args.extend(extra_args)
    result = subprocess.run(args, capture_output=capture, text=True)
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Prerequisite check
# ---------------------------------------------------------------------------

def _p32_p33_available() -> bool:
    p32_gate = os.path.join(_P32_DIR, "p32_gate_result.json")
    p33_gate = os.path.join(_P33_DIR, "p33_gate_result.json")
    return os.path.isfile(p32_gate) and os.path.isfile(p33_gate)


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path / "p34_output")


# ---------------------------------------------------------------------------
# Tests that don't require real P32/P33 artifacts (module-level unit tests)
# ---------------------------------------------------------------------------

class TestCLIModuleImportable:
    def test_script_exists(self):
        assert os.path.isfile(_CLI_SCRIPT), f"CLI script not found: {_CLI_SCRIPT}"

    def test_script_has_main(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        assert "def main(" in content

    def test_script_imports_paper_only(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        assert "PAPER_ONLY" in content
        assert "PRODUCTION_READY" in content

    def test_script_has_all_exit_codes(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        # Exit 0, 1, 2
        assert "return 0" in content
        assert "return 1" in content
        assert "return 2" in content

    def test_script_references_all_8_outputs(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        expected_outputs = [
            "prediction_acquisition_options.json",
            "odds_acquisition_options.json",
            "dual_source_acquisition_plan.json",
            "dual_source_acquisition_plan.md",
            "prediction_import_template.csv",
            "odds_import_template.csv",
            "joined_input_validation_rules.json",
            "p34_gate_result.json",
        ]
        for out_name in expected_outputs:
            assert out_name in content, f"CLI missing reference to: {out_name}"

    def test_no_scraping_in_cli(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        assert "requests.get" not in content
        assert "urllib.request" not in content
        assert "BeautifulSoup" not in content

    def test_no_live_api_calls(self):
        with open(_CLI_SCRIPT, encoding="utf-8") as fh:
            content = fh.read()
        # No live API keys or endpoint calls
        assert "api_key" not in content.lower()
        assert "THE_ODDS_API_KEY" not in content


class TestCLIMainFunction:
    """Test the main() function directly to avoid subprocess overhead."""

    def test_main_exits_with_fail_if_paper_only_false(self, output_dir):
        """main() must reject --paper-only false."""
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        with pytest.raises(SystemExit) as exc_info:
            cli_main([
                "--p32-dir", _P32_DIR,
                "--p33-dir", _P33_DIR,
                "--output-dir", output_dir,
                "--paper-only", "false",
                "--skip-determinism-check",
            ])
        assert exc_info.value.code == 2

    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_main_exits_0_when_ready(self, output_dir):
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        ret = cli_main([
            "--p32-dir", _P32_DIR,
            "--p33-dir", _P33_DIR,
            "--output-dir", output_dir,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        assert ret == 0

    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_main_writes_8_artifacts(self, output_dir):
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        cli_main([
            "--p32-dir", _P32_DIR,
            "--p33-dir", _P33_DIR,
            "--output-dir", output_dir,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        expected = [
            "prediction_acquisition_options.json",
            "odds_acquisition_options.json",
            "dual_source_acquisition_plan.json",
            "dual_source_acquisition_plan.md",
            "prediction_import_template.csv",
            "odds_import_template.csv",
            "joined_input_validation_rules.json",
            "p34_gate_result.json",
        ]
        for fname in expected:
            path = os.path.join(output_dir, fname)
            assert os.path.isfile(path), f"Missing: {fname}"

    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_main_gate_result_is_ready(self, output_dir):
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        cli_main([
            "--p32-dir", _P32_DIR,
            "--p33-dir", _P33_DIR,
            "--output-dir", output_dir,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        gate_path = os.path.join(output_dir, "p34_gate_result.json")
        data = json.loads(open(gate_path, encoding="utf-8").read())
        assert data["gate"] == "P34_DUAL_SOURCE_ACQUISITION_PLAN_READY"
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_main_deterministic(self, tmp_path):
        """Two runs with same inputs must produce identical gate result."""
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main

        dir1 = str(tmp_path / "det_run1")
        dir2 = str(tmp_path / "det_run2")

        for d in (dir1, dir2):
            cli_main([
                "--p32-dir", _P32_DIR,
                "--p33-dir", _P33_DIR,
                "--output-dir", d,
                "--paper-only", "true",
                "--skip-determinism-check",
            ])

        def _load_norm(path):
            data = json.loads(open(path, encoding="utf-8").read())
            for key in ("generated_at", "artifacts", "output_dir"):
                data.pop(key, None)
            return data

        for fname in ("p34_gate_result.json", "dual_source_acquisition_plan.json"):
            d1 = _load_norm(os.path.join(dir1, fname))
            d2 = _load_norm(os.path.join(dir2, fname))
            assert d1 == d2, f"Determinism mismatch in {fname}"

        for fname in ("prediction_import_template.csv", "odds_import_template.csv"):
            c1 = open(os.path.join(dir1, fname), encoding="utf-8").read()
            c2 = open(os.path.join(dir2, fname), encoding="utf-8").read()
            assert c1 == c2, f"Determinism mismatch in {fname}"


class TestCLIOutputFields:
    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_stdout_contains_gate(self, output_dir, capsys):
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        cli_main([
            "--p32-dir", _P32_DIR,
            "--p33-dir", _P33_DIR,
            "--output-dir", output_dir,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        captured = capsys.readouterr()
        assert "gate" in captured.out.lower()
        assert "P34_DUAL_SOURCE_ACQUISITION_PLAN_READY" in captured.out

    @pytest.mark.skipif(not _p32_p33_available(), reason="P32/P33 artifacts not available")
    def test_stdout_contains_paper_only(self, output_dir, capsys):
        from scripts.run_p34_dual_source_acquisition_plan import main as cli_main
        cli_main([
            "--p32-dir", _P32_DIR,
            "--p33-dir", _P33_DIR,
            "--output-dir", output_dir,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        captured = capsys.readouterr()
        assert "paper_only" in captured.out.lower()
        assert "production_ready" in captured.out.lower()
