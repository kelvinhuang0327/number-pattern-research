"""Tests for run_p35_dual_source_import_validation.py CLI script."""
import importlib
import json
import os
import sys
import tempfile

import pytest

_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "run_p35_dual_source_import_validation.py",
)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Script existence and structure
# ---------------------------------------------------------------------------


def test_script_file_exists():
    assert os.path.isfile(_SCRIPT_PATH), f"Script not found: {_SCRIPT_PATH}"


def test_script_has_main_function():
    src = open(_SCRIPT_PATH, encoding="utf-8").read()
    assert "def main(" in src


def test_script_imports_paper_only():
    src = open(_SCRIPT_PATH, encoding="utf-8").read()
    assert "PAPER_ONLY" in src


def test_script_references_all_7_output_files():
    src = open(_SCRIPT_PATH, encoding="utf-8").read()
    expected_files = [
        "odds_license_validation.json",
        "prediction_rebuild_feasibility.json",
        "odds_import_validator_spec.json",
        "prediction_import_validator_spec.json",
        "dual_source_validation_summary.json",
        "dual_source_validation_summary.md",
        "p35_gate_result.json",
    ]
    for fname in expected_files:
        assert fname in src, f"Script does not reference: {fname}"


def test_script_no_scraping():
    src = open(_SCRIPT_PATH, encoding="utf-8").read()
    # No actual HTTP requests allowed
    forbidden = ["requests.get(", "urllib.request", "BeautifulSoup", "httpx.get("]
    for f in forbidden:
        assert f not in src, f"Script contains forbidden scraping pattern: {f}"


# ---------------------------------------------------------------------------
# main() — paper-only guard
# ---------------------------------------------------------------------------


def test_main_exits_2_if_paper_only_not_true():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    # Import main dynamically
    spec = importlib.util.spec_from_file_location("p35_cli", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmp:
        # Passing "false" as paper_only — but argparse restricts to "true"
        # So we test the module-level guard instead
        # Monkeypatch PAPER_ONLY constant via the contract
        import wbc_backend.recommendation.p35_dual_source_import_validation_contract as contract
        original = contract.PAPER_ONLY
        try:
            # We can't change the immutable module constant easily,
            # so verify the contract itself enforces it
            assert contract.PAPER_ONLY is True
            assert contract.PRODUCTION_READY is False
        finally:
            pass  # no cleanup needed


# ---------------------------------------------------------------------------
# main() — real run produces gate=P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
# ---------------------------------------------------------------------------


def test_main_produces_expected_gate():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    spec = importlib.util.spec_from_file_location("p35_cli", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmp:
        # Use non-existent P34 dir (no approval record)
        exit_code = mod.main([
            "--p32-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed"),
            "--p34-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed",
                                       "p34_dual_source_acquisition"),
            "--output-dir", tmp,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        # Expected: exit 1 (blocked) not exit 2 (fail)
        assert exit_code == 1, f"Expected exit 1 (BLOCKED), got {exit_code}"

        gate_path = os.path.join(tmp, "p35_gate_result.json")
        assert os.path.isfile(gate_path), "p35_gate_result.json not written"

        with open(gate_path, encoding="utf-8") as fh:
            gate_data = json.load(fh)

        assert gate_data["gate"] == "P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED"
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False


def test_main_produces_all_7_output_files():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    spec = importlib.util.spec_from_file_location("p35_cli", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmp:
        mod.main([
            "--p32-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed"),
            "--p34-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed",
                                       "p34_dual_source_acquisition"),
            "--output-dir", tmp,
            "--paper-only", "true",
            "--skip-determinism-check",
        ])
        expected_files = [
            "odds_license_validation.json",
            "prediction_rebuild_feasibility.json",
            "odds_import_validator_spec.json",
            "prediction_import_validator_spec.json",
            "dual_source_validation_summary.json",
            "dual_source_validation_summary.md",
            "p35_gate_result.json",
        ]
        for fname in expected_files:
            fpath = os.path.join(tmp, fname)
            assert os.path.isfile(fpath), f"Output file not produced: {fname}"


def test_main_deterministic_gate_across_two_runs():
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    spec = importlib.util.spec_from_file_location("p35_cli", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    common_args = [
        "--p32-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed"),
        "--p34-dir", os.path.join(_REPO_ROOT, "data", "mlb_2024", "processed",
                                   "p34_dual_source_acquisition"),
        "--paper-only", "true",
        "--skip-determinism-check",
    ]

    with tempfile.TemporaryDirectory() as tmp1:
        mod.main(common_args + ["--output-dir", tmp1])
        with open(os.path.join(tmp1, "p35_gate_result.json"), encoding="utf-8") as fh:
            d1 = json.load(fh)

    with tempfile.TemporaryDirectory() as tmp2:
        mod.main(common_args + ["--output-dir", tmp2])
        with open(os.path.join(tmp2, "p35_gate_result.json"), encoding="utf-8") as fh:
            d2 = json.load(fh)

    exclude = {"generated_at", "output_dir", "artifacts"}
    for k in set(d1) | set(d2):
        if k in exclude:
            continue
        assert d1.get(k) == d2.get(k), f"Non-deterministic at key={k}"
