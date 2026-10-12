"""Smoke tests for run_mlb_tsl_paper_recommendation.py.

Monkeypatches live sources to fixtures so the smoke can run offline.
Asserts:
  - one row produced
  - output file written under PAPER/ path
  - paper_only is True
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _import_script():
    """Import the script module (reload if already cached)."""
    mod_name = "scripts.run_mlb_tsl_paper_recommendation"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSmokeOneRowProduced:
    """End-to-end smoke: monkeypatched sources, one row, correct path."""

    def test_smoke_produces_one_row(self, tmp_path, monkeypatch):
        script = _import_script()

        # Patch live MLB schedule fetch to return our fixture game
        monkeypatch.setattr(
            "data.mlb_live_pipeline.fetch_schedule",
            lambda *a, **kw: [FIXTURE_GAME],
        )
        # Also patch at import level inside the script module
        monkeypatch.setattr(
            script,
            "fetch_schedule",
            lambda *a, **kw: [FIXTURE_GAME],
        )
        # Patch TSL probe to simulate blocked (403)
        monkeypatch.setattr(
            script,
            "_probe_tsl",
            lambda: (False, "TSL live: 0 games (mocked)"),
        )

        row = script.build_recommendation(
            game=FIXTURE_GAME,
            date_str=FIXTURE_DATE,
            tsl_live=False,
            tsl_note="TSL live: 0 games (mocked)",
        )

        assert row is not None
        assert row.game_id.startswith(FIXTURE_DATE)

    def test_smoke_paper_only_is_true(self, tmp_path, monkeypatch):
        script = _import_script()
        monkeypatch.setattr(
            script, "fetch_schedule", lambda *a, **kw: [FIXTURE_GAME]
        )
        monkeypatch.setattr(
            script, "_probe_tsl", lambda: (False, "mocked")
        )

        row = script.build_recommendation(
            game=FIXTURE_GAME,
            date_str=FIXTURE_DATE,
            tsl_live=False,
            tsl_note="mocked",
        )
        assert row.paper_only is True

    def test_smoke_output_file_written_under_paper_path(self, tmp_path, monkeypatch):
        script = _import_script()
        monkeypatch.setattr(
            script, "fetch_schedule", lambda *a, **kw: [FIXTURE_GAME]
        )
        monkeypatch.setattr(
            script, "_probe_tsl", lambda: (False, "mocked")
        )

        row = script.build_recommendation(
            game=FIXTURE_GAME,
            date_str=FIXTURE_DATE,
            tsl_live=False,
            tsl_note="mocked",
        )

        # Patch ROOT so output goes to tmp_path
        monkeypatch.setattr(script, "ROOT", tmp_path)

        out_path = script.write_row(row, FIXTURE_DATE, is_replay=False)

        # Verify path is under PAPER/
        assert "PAPER" in str(out_path)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8").strip()
        parsed = json.loads(content)
        assert parsed["paper_only"] is True

    def test_smoke_replay_suffix_when_flagged(self, tmp_path, monkeypatch):
        script = _import_script()
        monkeypatch.setattr(
            script, "fetch_schedule", lambda *a, **kw: [FIXTURE_GAME]
        )
        monkeypatch.setattr(
            script, "_probe_tsl", lambda: (False, "mocked")
        )

        row = script.build_recommendation(
            game=FIXTURE_GAME,
            date_str=FIXTURE_DATE,
            tsl_live=False,
            tsl_note="mocked",
        )
        monkeypatch.setattr(script, "ROOT", tmp_path)

        out_path = script.write_row(row, FIXTURE_DATE, is_replay=True)
        assert out_path.name.endswith(".replay_fallback.jsonl")

    def test_smoke_gate_status_blocked_when_tsl_down(self, monkeypatch):
        script = _import_script()
        monkeypatch.setattr(
            script, "fetch_schedule", lambda *a, **kw: [FIXTURE_GAME]
        )

        row = script.build_recommendation(
            game=FIXTURE_GAME,
            date_str=FIXTURE_DATE,
            tsl_live=False,
            tsl_note="TSL 403 mocked",
        )
        # When TSL is down, gate should be BLOCKED_TSL_SOURCE
        assert row.gate_status == "BLOCKED_TSL_SOURCE"
        assert row.kelly_fraction == 0.0
        assert row.stake_units_paper == 0.0


class TestScriptRefusals:
    """Verify the script refuses when constraints violated."""

    def test_refuses_when_no_games_without_allow_flag(self, monkeypatch):
        """main() should return 1 when no games and --allow-replay-paper not set."""
        script = _import_script()
        monkeypatch.setattr(
            script, "fetch_schedule", lambda *a, **kw: []
        )
        monkeypatch.setattr(
            script, "_probe_tsl", lambda: (False, "mocked")
        )

        with patch.object(sys, "argv", ["run_mlb_tsl_paper_recommendation.py", "--date", FIXTURE_DATE]):
            result = script.main()
        assert result == 1
