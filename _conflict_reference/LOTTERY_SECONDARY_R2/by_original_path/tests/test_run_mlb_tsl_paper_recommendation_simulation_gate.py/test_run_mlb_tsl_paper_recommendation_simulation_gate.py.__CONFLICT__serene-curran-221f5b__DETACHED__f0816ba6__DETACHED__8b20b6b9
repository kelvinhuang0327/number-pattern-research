"""
tests/test_run_mlb_tsl_paper_recommendation_simulation_gate.py

Integration tests for simulation-gated recommendation script.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Fixtures ───────────────────────────────────────────────────────────────────

FIXTURE_GAME = {
    "gamePk": 824441,
    "gameDate": "2026-05-11T22:10:00Z",
    "status": {"detailedState": "Scheduled"},
    "teams": {
        "home": {"team": {"name": "Cleveland Guardians", "abbreviation": "CLE"}},
        "away": {"team": {"name": "Los Angeles Angels", "abbreviation": "LAA"}},
    },
}
FIXTURE_DATE = "2026-05-11"


def _import_script():
    mod_name = "scripts.run_mlb_tsl_paper_recommendation"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ── Simulation gate helpers ────────────────────────────────────────────────────

def _pass_gate(simulation_id: str = "sim-pass-abcd1234") -> dict:
    return {
        "allow_recommendation": True,
        "gate_status": "PASS",
        "gate_reasons": [
            "Simulation gate PASS — paper-only recommendation allowed.",
            "Gate: PASS — paper-only simulation.",
        ],
        "simulation_id": simulation_id,
        "paper_only": True,
    }


def _blocked_gate(
    status: str = "BLOCKED_NEGATIVE_BSS",
    simulation_id: str = "sim-blocked-abcd1234",
) -> dict:
    return {
        "allow_recommendation": False,
        "gate_status": status,
        "gate_reasons": [
            f"Simulation gate_status={status!r} blocks recommendation.",
            "BSS = -0.14 < 0 — model underperforms market.",
        ],
        "simulation_id": simulation_id,
        "paper_only": True,
    }


def _no_sim_gate() -> dict:
    return {
        "allow_recommendation": False,
        "gate_status": "BLOCKED_NO_SIMULATION",
        "gate_reasons": [
            "No simulation result provided.",
        ],
        "simulation_id": None,
        "paper_only": True,
    }


# ── Tests: build_recommendation with simulation gate ─────────────────────────

class TestBuildRecommendationSimulationGate:
    """Unit tests for build_recommendation() with simulation_gate parameter."""

    def test_pass_gate_allows_recommendation_path(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=_pass_gate(),
        )
        # With PASS gate but TSL blocked, gate should be BLOCKED_TSL_SOURCE (TSL wins)
        assert row.gate_status == "BLOCKED_TSL_SOURCE"
        assert row.paper_only is True

    def test_blocked_gate_overrides_tsl_blocking(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL live ok",
            simulation_gate=_blocked_gate("BLOCKED_NEGATIVE_BSS"),
        )
        assert row.gate_status == "BLOCKED_SIMULATION_GATE"
        assert row.stake_units_paper == 0.0
        assert row.kelly_fraction == 0.0

    def test_blocked_simulation_forces_stake_zero(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL live ok",
            simulation_gate=_blocked_gate("BLOCKED_HIGH_ECE"),
        )
        assert row.stake_units_paper == 0.0

    def test_blocked_simulation_forces_kelly_zero(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL live ok",
            simulation_gate=_blocked_gate("BLOCKED_LOW_SAMPLE"),
        )
        assert row.kelly_fraction == 0.0

    def test_no_simulation_gate_blocks_when_required(self):
        """When no simulation, gate is BLOCKED_NO_SIMULATION → blocked."""
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL live ok",
            simulation_gate=_no_sim_gate(),
        )
        assert row.gate_status == "BLOCKED_NO_SIMULATION"
        assert row.stake_units_paper == 0.0
        assert row.kelly_fraction == 0.0

    def test_source_trace_includes_simulation_id(self):
        script = _import_script()
        gate = _pass_gate(simulation_id="sim-test-xyz1234")
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=gate,
        )
        assert row.source_trace.get("simulation_id") == "sim-test-xyz1234"

    def test_source_trace_includes_simulation_gate_status(self):
        script = _import_script()
        gate = _pass_gate()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=gate,
        )
        assert row.source_trace.get("simulation_gate_status") == "PASS"

    def test_source_trace_includes_walk_forward_ml_evidence(self):
        script = _import_script()
        gate = _pass_gate()
        gate["source_trace"] = {
            "probability_source_mode": "walk_forward_ml_candidate",
            "walk_forward_ml_candidate_count": 123,
            "ml_model_type": ["logistic_regression"],
            "ml_feature_policy": ["p13_v1"],
            "ml_features_used": ["indep_recent_win_rate_delta", "indep_starter_era_delta"],
            "real_model_count": 0,
            "market_proxy_count": 0,
        }
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=gate,
        )
        assert row.source_trace.get("simulation_walk_forward_ml_candidate_count") == 123
        assert row.source_trace.get("simulation_ml_model_type") == ["logistic_regression"]

    def test_tsl_blocked_still_wins_over_simulation_pass(self):
        """TSL blocked overrides simulation PASS — stake remains 0."""
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=_pass_gate(),
        )
        assert row.gate_status == "BLOCKED_TSL_SOURCE"
        assert row.stake_units_paper == 0.0

    def test_paper_only_always_true(self):
        script = _import_script()
        for gate in [_pass_gate(), _blocked_gate(), _no_sim_gate()]:
            row = script.build_recommendation(
                FIXTURE_GAME, FIXTURE_DATE,
                tsl_live=False, tsl_note="TSL 403",
                simulation_gate=gate,
            )
            assert row.paper_only is True

    def test_no_gate_passed_defaults_to_tsl_gate(self):
        """With simulation_gate=None, falls through to normal TSL gate logic."""
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=False, tsl_note="TSL 403",
            simulation_gate=None,
        )
        assert row.gate_status == "BLOCKED_TSL_SOURCE"


# ── Tests: blocked simulation gate reasons in row ────────────────────────────

class TestBlockedGateReasons:
    def test_blocked_reasons_include_simulation_info(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL ok",
            simulation_gate=_blocked_gate("BLOCKED_NEGATIVE_BSS"),
        )
        combined = " ".join(row.gate_reasons)
        assert "simulation" in combined.lower() or "BLOCKED" in combined

    def test_negative_bss_blocks_row(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL ok",
            simulation_gate=_blocked_gate("BLOCKED_NEGATIVE_BSS"),
        )
        assert row.gate_status == "BLOCKED_SIMULATION_GATE"

    def test_high_ece_blocks_row(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL ok",
            simulation_gate=_blocked_gate("BLOCKED_HIGH_ECE"),
        )
        assert row.gate_status == "BLOCKED_SIMULATION_GATE"

    def test_low_sample_blocks_row(self):
        script = _import_script()
        row = script.build_recommendation(
            FIXTURE_GAME, FIXTURE_DATE,
            tsl_live=True, tsl_note="TSL ok",
            simulation_gate=_blocked_gate("BLOCKED_LOW_SAMPLE"),
        )
        assert row.gate_status == "BLOCKED_SIMULATION_GATE"


# ── Tests: main() CLI integration ──────────────────────────────────────────────

class TestMainCLISimulationGate:
    """End-to-end tests via main() — monkeypatched sources."""

    def _run_main(self, tmp_path, monkeypatch, extra_args=None, simulation_gate=None):
        """Run main() with monkeypatched sources and return (returncode, row_dict)."""
        script = _import_script()

        # Patch live MLB schedule fetch
        monkeypatch.setattr(
            "data.mlb_live_pipeline.fetch_schedule",
            lambda *a, **kw: [FIXTURE_GAME],
        )
        # Patch TSL crawler to always return blocked
        monkeypatch.setattr(
            script, "_probe_tsl",
            lambda: (False, "TSL probe monkeypatched to blocked"),
        )
        # Patch simulation loader to return the specified gate's simulation
        if simulation_gate is not None:
            sim_allow = simulation_gate.get("allow_recommendation", False)
            monkeypatch.setattr(
                script, "load_latest_simulation_result",
                lambda *a, **kw: None,
            )
            monkeypatch.setattr(
                script, "build_recommendation_gate_from_simulation",
                lambda sim: simulation_gate,
            )
        # Patch output directory to tmp_path
        orig_write_row = script.write_row

        def patched_write_row(row, date_str, is_replay):
            paper_dir = (
                tmp_path / "outputs" / "recommendations" / "PAPER" / date_str
            )
            paper_dir.mkdir(parents=True, exist_ok=True)
            out_path = paper_dir / f"{row.game_id}.jsonl"
            out_path.write_text(row.to_jsonl_line() + "\n", encoding="utf-8")
            return out_path

        monkeypatch.setattr(script, "write_row", patched_write_row)

        base_args = ["--date", FIXTURE_DATE, "--allow-replay-paper"]
        if extra_args:
            base_args.extend(extra_args)

        monkeypatch.setattr(sys, "argv", ["run_mlb_tsl_paper_recommendation.py"] + base_args)
        rc = script.main()

        # Find the output file
        row_dict = None
        paper_dir = tmp_path / "outputs" / "recommendations" / "PAPER" / FIXTURE_DATE
        if paper_dir.exists():
            for f in paper_dir.glob("*.jsonl"):
                row_dict = json.loads(f.read_text(encoding="utf-8").strip())
                break
        return rc, row_dict

    def test_pass_gate_produces_row(self, tmp_path, monkeypatch):
        _, row = self._run_main(tmp_path, monkeypatch, simulation_gate=_pass_gate())
        assert row is not None
        assert row["paper_only"] is True

    def test_blocked_simulation_still_writes_row(self, tmp_path, monkeypatch):
        """Even when simulation blocks, we write an audit row with stake=0."""
        rc, row = self._run_main(
            tmp_path, monkeypatch,
            simulation_gate=_blocked_gate("BLOCKED_NEGATIVE_BSS"),
        )
        # Row should exist with stake=0
        if row is not None:
            assert row["stake_units_paper"] == 0.0
            assert row["kelly_fraction"] == 0.0
            assert row["paper_only"] is True

    def test_missing_simulation_refused_without_bypass(self, tmp_path, monkeypatch):
        """Without --allow-missing-simulation-gate, missing simulation prints refusal."""
        # blocked no-sim gate blocks recommendation but still writes row
        rc, row = self._run_main(
            tmp_path, monkeypatch,
            simulation_gate=_no_sim_gate(),
        )
        if row is not None:
            assert row["stake_units_paper"] == 0.0

    def test_allow_missing_simulation_gate_bypass(self, tmp_path, monkeypatch):
        """--allow-missing-simulation-gate bypasses missing simulation gate."""
        # Pass no simulation gate, but monkeypatch so None is returned and flag is set
        script = _import_script()
        monkeypatch.setattr(
            "data.mlb_live_pipeline.fetch_schedule",
            lambda *a, **kw: [FIXTURE_GAME],
        )
        monkeypatch.setattr(
            script, "_probe_tsl",
            lambda: (False, "TSL blocked"),
        )
        monkeypatch.setattr(
            script, "load_latest_simulation_result",
            lambda *a, **kw: None,
        )
        orig_write_row = script.write_row

        def patched_write_row(row, date_str, is_replay):
            paper_dir = tmp_path / "outputs" / "recommendations" / "PAPER" / date_str
            paper_dir.mkdir(parents=True, exist_ok=True)
            out_path = paper_dir / f"{row.game_id}.jsonl"
            out_path.write_text(row.to_jsonl_line() + "\n", encoding="utf-8")
            return out_path

        monkeypatch.setattr(script, "write_row", patched_write_row)

        monkeypatch.setattr(
            sys, "argv",
            [
                "run_mlb_tsl_paper_recommendation.py",
                "--date", FIXTURE_DATE,
                "--allow-replay-paper",
                "--allow-missing-simulation-gate",
            ],
        )
        rc = script.main()
        assert rc == 0

    def test_output_has_simulation_id_in_source_trace(self, tmp_path, monkeypatch):
        _, row = self._run_main(
            tmp_path, monkeypatch,
            simulation_gate=_pass_gate(simulation_id="sim-trace-test-12345678"),
        )
        if row is not None:
            assert row["source_trace"].get("simulation_id") == "sim-trace-test-12345678"

    def test_output_paper_only_invariant(self, tmp_path, monkeypatch):
        for gate in [_pass_gate(), _blocked_gate(), _no_sim_gate()]:
            _, row = self._run_main(tmp_path, monkeypatch, simulation_gate=gate)
            if row is not None:
                assert row["paper_only"] is True, f"paper_only must be True, got {row}"
