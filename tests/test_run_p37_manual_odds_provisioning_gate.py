"""
Tests for scripts/run_p37_manual_odds_provisioning_gate.py
"""
import importlib.util
import json
import os
import sys
import tempfile

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Script loader
# ---------------------------------------------------------------------------

def _load_script():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(repo_root, "scripts", "run_p37_manual_odds_provisioning_gate.py")
    spec = importlib.util.spec_from_file_location("run_p37", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_valid_approval_record(tmp_dir: str) -> str:
    record = {
        "provider_name": "TestProvider",
        "source_name": "TestSource",
        "source_url_or_reference": "https://example.com/data",
        "license_terms_summary": "Internal research use permitted",
        "allowed_use": "internal_research",
        "redistribution_allowed": False,
        "attribution_required": True,
        "internal_research_allowed": True,
        "commercial_use_allowed": False,
        "approved_by": "ResearchLead",
        "approved_at": "2024-01-01T00:00:00+00:00",
        "approval_scope": "mlb_2024_season",
        "source_file_expected_path": "data/mlb_2024/manual_import/odds_2024_approved.csv",
        "checksum_required": False,
        "paper_only": True,
        "production_ready": False,
    }
    path = os.path.join(tmp_dir, "odds_approval_record.json")
    with open(path, "w") as f:
        json.dump(record, f)
    return path


def _make_valid_odds_csv(tmp_dir: str) -> str:
    df = pd.DataFrame([{
        "game_id": "20240401_BOS_NYA",
        "game_date": "2024-04-01",
        "home_team": "BOS",
        "away_team": "NYA",
        "p_market": 0.55,
        "odds_decimal": 1.82,
        "sportsbook": "Pinnacle",
        "market_type": "moneyline",
        "closing_timestamp": "2024-04-01T17:00:00+00:00",
        "source_odds_ref": "pinnacle_row_123",
        "license_ref": "license_001",
    }])
    path = os.path.join(tmp_dir, "odds_2024_approved.csv")
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Script-level checks
# ---------------------------------------------------------------------------

class TestScriptStructure:
    def test_script_exists(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(repo_root, "scripts", "run_p37_manual_odds_provisioning_gate.py")
        assert os.path.exists(script)

    def test_script_has_main(self):
        mod = _load_script()
        assert hasattr(mod, "main")
        assert callable(mod.main)

    def test_paper_only_is_true(self):
        mod = _load_script()
        assert mod.PAPER_ONLY is True

    def test_production_ready_is_false(self):
        mod = _load_script()
        assert mod.PRODUCTION_READY is False

    def test_references_all_7_output_files(self):
        mod = _load_script()
        expected = {
            "odds_approval_record_TEMPLATE.json",
            "odds_approval_record_INSTRUCTIONS.md",
            "odds_2024_approved_TEMPLATE.csv",
            "odds_2024_approved_COLUMN_GUIDE.md",
            "manual_odds_provisioning_gate.json",
            "manual_odds_provisioning_gate.md",
            "p37_gate_result.json",
        }
        output_files_set = set(mod.P37_OUTPUT_FILES)
        assert expected == output_files_set

    def test_no_scraping_in_script(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(repo_root, "scripts", "run_p37_manual_odds_provisioning_gate.py")
        with open(script) as f:
            content = f.read()
        assert "requests.get" not in content
        assert "urllib.request" not in content
        assert "BeautifulSoup" not in content


# ---------------------------------------------------------------------------
# CLI behavior tests
# ---------------------------------------------------------------------------

class TestMainBehavior:
    def test_main_exits_2_if_paper_only_not_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _load_script()
            exit_code = mod.main(["--paper-only", "false", "--output-dir", tmp])
        assert exit_code == 2

    def test_main_returns_1_without_approval_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _load_script()
            exit_code = mod.main([
                "--paper-only", "true",
                "--output-dir", tmp,
                "--skip-determinism-check",
            ])
        assert exit_code == 1

    def test_gate_is_blocked_approval_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _load_script()
            exit_code = mod.main([
                "--paper-only", "true",
                "--output-dir", tmp,
                "--skip-determinism-check",
            ])
            result_path = os.path.join(tmp, "p37_gate_result.json")
            with open(result_path) as f:
                data = json.load(f)
        assert data["gate"] == "P37_BLOCKED_APPROVAL_RECORD_MISSING"
        assert data["paper_only"] is True
        assert data["production_ready"] is False
        assert data["raw_odds_commit_allowed"] is False

    def test_templates_written_on_blocked_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _load_script()
            mod.main([
                "--paper-only", "true",
                "--output-dir", tmp,
                "--skip-determinism-check",
            ])
            for fname in [
                "odds_approval_record_TEMPLATE.json",
                "odds_approval_record_INSTRUCTIONS.md",
                "odds_2024_approved_TEMPLATE.csv",
                "odds_2024_approved_COLUMN_GUIDE.md",
            ]:
                assert os.path.exists(os.path.join(tmp, fname)), f"Missing: {fname}"

    def test_all_7_outputs_written_on_blocked_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = _load_script()
            mod.main([
                "--paper-only", "true",
                "--output-dir", tmp,
                "--skip-determinism-check",
            ])
            for fname in mod.P37_OUTPUT_FILES:
                assert os.path.exists(os.path.join(tmp, fname)), f"Missing output: {fname}"

    def test_main_returns_0_with_valid_approval_and_odds(self):
        with tempfile.TemporaryDirectory() as tmp_data, tempfile.TemporaryDirectory() as tmp_out:
            approval_path = _make_valid_approval_record(tmp_data)
            odds_path = _make_valid_odds_csv(tmp_data)
            mod = _load_script()
            exit_code = mod.main([
                "--paper-only", "true",
                "--output-dir", tmp_out,
                "--approval-record", approval_path,
                "--manual-odds-file", odds_path,
                "--skip-determinism-check",
            ])
        assert exit_code == 0

    def test_gate_ready_with_valid_approval_and_odds(self):
        with tempfile.TemporaryDirectory() as tmp_data, tempfile.TemporaryDirectory() as tmp_out:
            approval_path = _make_valid_approval_record(tmp_data)
            odds_path = _make_valid_odds_csv(tmp_data)
            mod = _load_script()
            mod.main([
                "--paper-only", "true",
                "--output-dir", tmp_out,
                "--approval-record", approval_path,
                "--manual-odds-file", odds_path,
                "--skip-determinism-check",
            ])
            result_path = os.path.join(tmp_out, "p37_gate_result.json")
            with open(result_path) as f:
                data = json.load(f)
        assert data["gate"] == "P37_MANUAL_ODDS_PROVISIONING_GATE_READY"


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_across_two_runs(self):
        _EXCLUDE = frozenset({"generated_at", "artifacts"})
        with tempfile.TemporaryDirectory() as run1, tempfile.TemporaryDirectory() as run2:
            mod = _load_script()
            mod.main([
                "--paper-only", "true",
                "--output-dir", run1,
                "--skip-determinism-check",
            ])
            mod.main([
                "--paper-only", "true",
                "--output-dir", run2,
                "--skip-determinism-check",
            ])
            for fname in ("manual_odds_provisioning_gate.json", "p37_gate_result.json"):
                with open(os.path.join(run1, fname)) as f1:
                    d1 = {k: v for k, v in json.load(f1).items() if k not in _EXCLUDE}
                with open(os.path.join(run2, fname)) as f2:
                    d2 = {k: v for k, v in json.load(f2).items() if k not in _EXCLUDE}
                assert d1 == d2, f"Non-deterministic output in {fname}"

            for fname in ("odds_approval_record_INSTRUCTIONS.md",
                          "odds_2024_approved_TEMPLATE.csv",
                          "odds_2024_approved_COLUMN_GUIDE.md"):
                with open(os.path.join(run1, fname)) as f1:
                    c1 = f1.read()
                with open(os.path.join(run2, fname)) as f2:
                    c2 = f2.read()
                assert c1 == c2, f"Non-deterministic content in {fname}"
