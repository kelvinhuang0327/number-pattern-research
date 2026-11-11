"""Tests for P36 CLI script: scripts/run_p36_odds_approval_import_gate.py."""
import importlib.util
import json
import os
import sys
import tempfile
import types

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_PATH = os.path.join(
    _REPO_ROOT, "scripts", "run_p36_odds_approval_import_gate.py"
)

P36_OUTPUT_FILES = (
    "odds_approval_validation.json",
    "manual_odds_import_schema.json",
    "manual_odds_import_validation.json",
    "odds_import_gate_plan.json",
    "odds_import_gate_plan.md",
    "p36_gate_result.json",
)


def _load_script() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("p36_cli", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------


def test_script_file_exists():
    assert os.path.isfile(_SCRIPT_PATH), f"Script not found: {_SCRIPT_PATH}"


def test_script_has_main_function():
    mod = _load_script()
    assert hasattr(mod, "main"), "Script must define main()"
    assert callable(mod.main)


def test_script_imports_paper_only_true():
    mod = _load_script()
    assert hasattr(mod, "PAPER_ONLY"), "Script must import PAPER_ONLY"
    assert mod.PAPER_ONLY is True


def test_script_references_all_6_output_files():
    with open(_SCRIPT_PATH, encoding="utf-8") as fh:
        source = fh.read()
    for fname in P36_OUTPUT_FILES:
        assert fname in source, f"Script must reference output file: {fname}"


def test_script_no_scraping():
    with open(_SCRIPT_PATH, encoding="utf-8") as fh:
        source = fh.read()
    for forbidden in ("requests.get", "urllib.request", "BeautifulSoup"):
        assert forbidden not in source, f"Script must not use scraping: {forbidden}"


# ---------------------------------------------------------------------------
# Runtime checks
# ---------------------------------------------------------------------------


def test_main_exits_2_if_paper_only_not_true():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _load_script()
        exit_code = mod.main(["--paper-only", "false", "--output-dir", tmp])
    assert exit_code == 2


def test_main_exits_1_no_approval_record():
    """Without any approval record, gate should be BLOCKED with exit 1."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _load_script()
        exit_code = mod.main([
            "--paper-only", "true",
            "--output-dir", tmp,
            "--skip-determinism-check",
        ])
    assert exit_code == 1


def test_main_gate_blocked_approval_missing():
    """Without approval record, gate must be P36_BLOCKED_APPROVAL_RECORD_MISSING."""
    with tempfile.TemporaryDirectory() as tmp:
        mod = _load_script()
        mod.main([
            "--paper-only", "true",
            "--output-dir", tmp,
            "--skip-determinism-check",
        ])
        gate_path = os.path.join(tmp, "p36_gate_result.json")
        assert os.path.isfile(gate_path)
        with open(gate_path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["gate"] == "P36_BLOCKED_APPROVAL_RECORD_MISSING"


def test_main_produces_all_6_output_files():
    with tempfile.TemporaryDirectory() as tmp:
        mod = _load_script()
        mod.main([
            "--paper-only", "true",
            "--output-dir", tmp,
            "--skip-determinism-check",
        ])
        produced = set(os.listdir(tmp))
        for fname in P36_OUTPUT_FILES:
            assert fname in produced, f"Missing output file: {fname}"


def test_main_deterministic():
    """Two runs (different output dirs) must produce identical p36_gate_result.json
    excluding generated_at, output_dir, artifacts keys."""
    exclude = frozenset({"generated_at", "output_dir", "artifacts"})
    mod = _load_script()
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        mod.main(["--paper-only", "true", "--output-dir", t1, "--skip-determinism-check"])
        mod.main(["--paper-only", "true", "--output-dir", t2, "--skip-determinism-check"])
        with open(os.path.join(t1, "p36_gate_result.json"), encoding="utf-8") as fh:
            d1 = {k: v for k, v in json.load(fh).items() if k not in exclude}
        with open(os.path.join(t2, "p36_gate_result.json"), encoding="utf-8") as fh:
            d2 = {k: v for k, v in json.load(fh).items() if k not in exclude}
        assert d1 == d2, f"Non-determinism detected:\nd1={d1}\nd2={d2}"
