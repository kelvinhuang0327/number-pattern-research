"""
Phase 6S: Odds Snapshot Alignment — Unit & Integration Tests
=============================================================
Tests:
  1. test_chooses_latest_snapshot_before_prediction_time
  2. test_rejects_snapshot_after_prediction_time
  3. test_handles_missing_snapshot_with_status_missing
  4. test_computes_implied_probability_correctly
  5. test_clv_usable_true_only_when_gates_pass
  6. test_historical_files_unchanged
  7. test_validator_passes_for_aligned_rows
  8. TestOddsTimelineLoader — unit tests for loader
  9. TestAlignOddsSnapshot — unit tests for alignment function
  10. test_adapter_row_count
  11. test_adapter_clv_usable_true_for_aligned_rows
  12. test_adapter_no_post_prediction_leakage
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from align_odds_snapshot import (
    OddsTimelineLoader,
    align_odds_snapshot_for_prediction,
    american_to_implied,
    _extract_from_game_id,
)
from build_ml_future_model_outputs_6s import _compute_clv_usable, _elo_win_prob

# ── Test fixtures / helpers ───────────────────────────────────────────────────

_APR30 = "20260430"
_PRED_TIME_STR = "2026-04-30T08:00:00Z"
_PRED_TIME_DT = datetime(2026, 4, 30, 8, 0, 0, tzinfo=timezone.utc)

# Sample record that mimics odds_timeline.jsonl format
def _make_record(
    game_id: str,
    home_ml: int = -125,
    away_ml: int = 100,
    history_entries: list[dict] | None = None,
    latest_pregame_home_ml: int | None = None,
    latest_pregame_away_ml: int | None = None,
) -> dict:
    if history_entries is None:
        history_entries = []
    return {
        "game_id": game_id,
        "source": "TSL",
        "book": "TSL",
        "market_type": "moneyline",
        "home_team": "HomeTeam",
        "away_team": "AwayTeam",
        "closing_home_ml": home_ml,
        "closing_away_ml": away_ml,
        "latest_pregame_home_ml": latest_pregame_home_ml or home_ml,
        "latest_pregame_away_ml": latest_pregame_away_ml or away_ml,
        "opening_home_ml": home_ml,
        "opening_away_ml": away_ml,
        "decision_home_ml": home_ml,
        "decision_away_ml": away_ml,
        "decision_ts": "2026-04-30T06:00:00Z",
        "opening_ts": "2026-04-29T12:00:00Z",
        "latest_pregame_ts": "2026-04-30T06:00:00Z",
        "commence_time": "2026-04-30T16:15:00Z",
        "updated_at": "2026-04-30T08:00:00Z",
        "odds_history": history_entries,
    }


def _write_timeline(records: list[dict], tmp_path: Path) -> str:
    p = tmp_path / "odds_timeline.jsonl"
    with open(p, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return str(p)


def _base_row(selection: str = "home", canonical_id: str = "baseball:mlb:20260430:ATL:DET") -> dict:
    """A minimal Phase 6S output row for testing."""
    return {
        "schema_version": "6j-1.0",
        "canonical_match_id": canonical_id,
        "selection": selection,
        "prediction_time_utc": _PRED_TIME_STR,
        "prediction_time_source": "MODEL_INFERENCE_RUNTIME",
        "timestamp_quality_flags": [],
        "clv_usable": False,
        "dry_run": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Chooses latest snapshot BEFORE prediction time
# ─────────────────────────────────────────────────────────────────────────────
def test_chooses_latest_snapshot_before_prediction_time(tmp_path: Path):
    history = [
        {"ts": "2026-04-30T05:00:00Z", "home_ml": -120, "away_ml": 100, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        {"ts": "2026-04-30T07:00:00Z", "home_ml": -130, "away_ml": 110, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        # This snapshot is AFTER prediction time — must be ignored
        {"ts": "2026-04-30T09:00:00Z", "home_ml": -140, "away_ml": 120, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
    ]
    game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
    record = _make_record(game_id, history_entries=history)
    path = _write_timeline([record], tmp_path)
    loader = OddsTimelineLoader(path=path)

    row = _base_row("home", "baseball:mlb:20260430:ATL:DET")
    result = align_odds_snapshot_for_prediction(row, loader)

    assert result["odds_snapshot_alignment_status"] == "ALIGNED"
    # Must use 07:00 snapshot (latest before 08:00 pred_time), not 09:00
    assert "07:00:00Z" in result["odds_snapshot_time_utc"]
    assert result["market_odds_at_prediction"] == -130


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rejects ALL snapshots that are after prediction time
# ─────────────────────────────────────────────────────────────────────────────
def test_rejects_snapshot_after_prediction_time(tmp_path: Path):
    # All history entries are AFTER pred_time
    history = [
        {"ts": "2026-04-30T09:00:00Z", "home_ml": -120, "away_ml": 100, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        {"ts": "2026-04-30T10:00:00Z", "home_ml": -130, "away_ml": 110, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
    ]
    game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
    record = _make_record(
        game_id,
        history_entries=history,
        latest_pregame_home_ml=-120,
    )
    # Also make the decision/opening/latest pregame after pred_time
    record["decision_ts"] = "2026-04-30T09:30:00Z"
    record["latest_pregame_ts"] = "2026-04-30T09:30:00Z"
    record["opening_ts"] = "2026-04-30T09:30:00Z"

    path = _write_timeline([record], tmp_path)
    loader = OddsTimelineLoader(path=path)

    row = _base_row("home", "baseball:mlb:20260430:ATL:DET")
    result = align_odds_snapshot_for_prediction(row, loader)

    # All history after pred_time → FUTURE_LEAK_BLOCKED
    assert result["odds_snapshot_alignment_status"] == "FUTURE_LEAK_BLOCKED"
    assert result["odds_snapshot_ref"] is None
    assert result["implied_probability_at_prediction"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Missing snapshot (no record for the game)
# ─────────────────────────────────────────────────────────────────────────────
def test_handles_missing_snapshot_with_status_missing(tmp_path: Path):
    # Write an empty timeline (no records at all)
    path = _write_timeline([], tmp_path)
    loader = OddsTimelineLoader(path=path)

    row = _base_row("home", "baseball:mlb:20260430:ATL:DET")
    result = align_odds_snapshot_for_prediction(row, loader)

    assert result["odds_snapshot_alignment_status"] == "MISSING"
    assert result["odds_snapshot_ref"] is None
    assert result["implied_probability_at_prediction"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Implied probability computed correctly from American odds
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("american_ml,expected_implied", [
    (-125, 125.0 / 225.0),    # favourites: |odds| / (|odds| + 100)
    (+110, 100.0 / 210.0),    # dogs: 100 / (100 + |odds|)
    (-200, 200.0 / 300.0),
    (+150, 100.0 / 250.0),
    (-100, 0.5),
    (+100, 0.5),
])
def test_computes_implied_probability_correctly(american_ml: int, expected_implied: float):
    result = american_to_implied(american_ml)
    # american_to_implied rounds to 6 decimal places; tolerance = 1e-5
    assert abs(result - expected_implied) < 1e-5, (
        f"american_to_implied({american_ml}) = {result}, expected {expected_implied}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. clv_usable = True ONLY when ALL gates pass
# ─────────────────────────────────────────────────────────────────────────────
class TestClvUsabilityGate:
    """Five-gate CLV usability check."""

    _pred_time = _PRED_TIME_DT

    def _aligned_alignment(self, snap_ts: str = "2026-04-30T05:00:00Z") -> dict:
        return {
            "odds_snapshot_ref": "MLB-2026_04_30-12_15_PM-DET-AT-ATL|TSL|snap@2026-04-30T05:00:00Z",
            "odds_snapshot_time_utc": snap_ts,
            "implied_probability_at_prediction": 0.55,
        }

    def _good_row(self) -> dict:
        return {
            "prediction_time_source": "MODEL_INFERENCE_RUNTIME",
            "timestamp_quality_flags": [],
        }

    def test_clv_true_all_gates_pass(self):
        assert _compute_clv_usable(self._good_row(), self._aligned_alignment(), self._pred_time) is True

    def test_gate1_fails_bad_prediction_time_source(self):
        row = {**self._good_row(), "prediction_time_source": "HISTORICAL_LOOKUP"}
        assert _compute_clv_usable(row, self._aligned_alignment(), self._pred_time) is False

    def test_gate2_fails_no_snapshot_ref(self):
        alignment = {**self._aligned_alignment(), "odds_snapshot_ref": None}
        assert _compute_clv_usable(self._good_row(), alignment, self._pred_time) is False

    def test_gate3_fails_snapshot_after_pred_time(self):
        alignment = self._aligned_alignment(snap_ts="2026-04-30T09:00:00Z")  # after pred
        assert _compute_clv_usable(self._good_row(), alignment, self._pred_time) is False

    def test_gate4_fails_invalid_implied_prob_zero(self):
        alignment = {**self._aligned_alignment(), "implied_probability_at_prediction": 0.0}
        assert _compute_clv_usable(self._good_row(), alignment, self._pred_time) is False

    def test_gate4_fails_implied_prob_none(self):
        alignment = {**self._aligned_alignment(), "implied_probability_at_prediction": None}
        assert _compute_clv_usable(self._good_row(), alignment, self._pred_time) is False

    def test_gate5_fails_hard_fail_timestamp_flag(self):
        row = {**self._good_row(), "timestamp_quality_flags": ["TIMESTAMP_MISSING"]}
        assert _compute_clv_usable(row, self._aligned_alignment(), self._pred_time) is False


def test_clv_usable_true_only_when_gates_pass():
    """Parameterised wrapper for CLV gate tests."""
    t = TestClvUsabilityGate()
    t.test_clv_true_all_gates_pass()
    t.test_gate1_fails_bad_prediction_time_source()
    t.test_gate2_fails_no_snapshot_ref()
    t.test_gate3_fails_snapshot_after_pred_time()
    t.test_gate4_fails_invalid_implied_prob_zero()
    t.test_gate4_fails_implied_prob_none()
    t.test_gate5_fails_hard_fail_timestamp_flag()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Historical files are unchanged
# ─────────────────────────────────────────────────────────────────────────────
def test_historical_files_unchanged():
    """data/derived/model_outputs_2026-04-29.jsonl must not be modified."""
    hist_path = _REPO_ROOT / "data" / "derived" / "model_outputs_2026-04-29.jsonl"
    assert hist_path.exists(), "Historical JSONL must exist"
    rows = [json.loads(l) for l in hist_path.read_text().splitlines() if l.strip()]
    assert len(rows) == 2986, f"Expected 2986 historical rows, got {len(rows)}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Validator passes for aligned rows (inline M13 + M9 check)
# ─────────────────────────────────────────────────────────────────────────────
def test_validator_passes_for_aligned_rows():
    """Load Phase 6S output and run M9 + M13 inline gate checks."""
    output_path = _REPO_ROOT / "data" / "derived" / "model_outputs_6s_future_2026-04-30.jsonl"
    assert output_path.exists(), "Phase 6S output must exist"

    rows = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    for row in rows:
        # M13: native timestamp source present and in allowed set
        pts = row.get("prediction_time_source", "")
        allowed = {"MODEL_INFERENCE_RUNTIME", "MODEL_OUTPUT_EMISSION_RUNTIME", "SCHEDULER_RUN_RUNTIME"}
        assert pts in allowed, f"M13 fail: prediction_time_source={pts!r}"

        # M9: odds_snapshot_time_utc must not exceed prediction_time_utc
        snap_ts = row.get("odds_snapshot_time_utc")
        pred_ts = row.get("prediction_time_utc")
        if snap_ts and pred_ts:
            assert snap_ts <= pred_ts, f"M9 leakage: snap {snap_ts} > pred {pred_ts}"

        # M13: no hard-fail flags
        hard_fails = {
            "TIMESTAMP_MISSING", "TIMESTAMP_SOURCE_LOW_CONFIDENCE",
            "PREDICTION_TIME_AFTER_MATCH", "FEATURE_CUTOFF_AFTER_PREDICTION",
        }
        tqf = set(row.get("timestamp_quality_flags") or [])
        assert not tqf & hard_fails, f"M13 hard-fail flag in row: {tqf & hard_fails}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. OddsTimelineLoader unit tests
# ─────────────────────────────────────────────────────────────────────────────
class TestOddsTimelineLoader:
    def test_loads_records(self, tmp_path: Path):
        game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
        record = _make_record(game_id)
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)
        assert len(loader.all_records()) == 1

    def test_find_by_home_away(self, tmp_path: Path):
        game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
        record = _make_record(game_id)
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)
        found = loader.find("20260430", "ATL", "DET")
        assert found is not None
        assert found["game_id"] == game_id

    def test_find_returns_none_for_unknown(self, tmp_path: Path):
        path = _write_timeline([], tmp_path)
        loader = OddsTimelineLoader(path=path)
        assert loader.find("20260430", "NYY", "BOS") is None

    def test_records_for_date(self, tmp_path: Path):
        records = [
            _make_record("MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"),
            _make_record("MLB-2026_04_30-1_10_PM-WASHINGTON_NATIONALS-AT-NEW_YORK_METS"),
        ]
        path = _write_timeline(records, tmp_path)
        loader = OddsTimelineLoader(path=path)
        results = loader.records_for_date("20260430")
        assert len(results) == 2

    def test_records_for_different_date_empty(self, tmp_path: Path):
        record = _make_record("MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES")
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)
        assert loader.records_for_date("20260429") == []

    def test_extract_game_id_parses_all_april30_games(self):
        game_ids = [
            "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES",
            "MLB-2026_04_30-12_35_PM-ST_LOUIS_CARDINALS-AT-PITTSBURGH_PIRATES",
            "MLB-2026_04_30-1_10_PM-WASHINGTON_NATIONALS-AT-NEW_YORK_METS",
            "MLB-2026_04_30-1_40_PM-ARIZONA_DIAMONDBACKS-AT-MILWAUKEE_BREWERS",
            "MLB-2026_04_30-3_05_PM-KANSAS_CITY_ROYALS-AT-OAKLAND_ATHLETICS",
            "MLB-2026_04_30-5_35_PM-SAN_FRANCISCO_GIANTS-AT-PHILADELPHIA_PHILLIES",
            "MLB-2026_04_30-7_40_PM-TORONTO_BLUE_JAYS-AT-MINNESOTA_TWINS",
        ]
        expected = [
            ("20260430", "DET", "ATL"),
            ("20260430", "STL", "PIT"),
            ("20260430", "WSH", "NYM"),
            ("20260430", "ARI", "MIL"),
            ("20260430", "KC", "OAK"),
            ("20260430", "SFG", "PHI"),
            ("20260430", "TOR", "MIN"),
        ]
        for gid, exp in zip(game_ids, expected):
            result = _extract_from_game_id(gid)
            assert result == exp, f"game_id={gid!r}: got {result}, expected {exp}"


# ─────────────────────────────────────────────────────────────────────────────
# 9. align_odds_snapshot_for_prediction unit tests
# ─────────────────────────────────────────────────────────────────────────────
class TestAlignOddsSnapshot:
    def test_aligned_status_for_valid_snap(self, tmp_path: Path):
        history = [
            {"ts": "2026-04-30T05:00:00Z", "home_ml": -125, "away_ml": 100, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        ]
        game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
        record = _make_record(game_id, history_entries=history)
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)

        row = _base_row("home")
        result = align_odds_snapshot_for_prediction(row, loader)
        assert result["odds_snapshot_alignment_status"] == "ALIGNED"
        assert result["odds_snapshot_ref"] is not None
        assert "|TSL|snap@" in result["odds_snapshot_ref"]
        assert result["implied_probability_at_prediction"] is not None

    def test_away_selection_uses_away_ml(self, tmp_path: Path):
        history = [
            {"ts": "2026-04-30T05:00:00Z", "home_ml": -125, "away_ml": 105, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        ]
        game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
        record = _make_record(game_id, history_entries=history)
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)

        row = _base_row("away")
        result = align_odds_snapshot_for_prediction(row, loader)
        # Away ML = +105 → implied = 100/205 ≈ 0.4878
        expected = 100.0 / 205.0
        assert abs(result["implied_probability_at_prediction"] - expected) < 1e-4
        assert result["market_odds_at_prediction"] == 105

    def test_stale_snap_status(self, tmp_path: Path):
        # Snapshot is 25 hours before prediction → STALE
        history = [
            {"ts": "2026-04-29T07:00:00Z", "home_ml": -125, "away_ml": 100, "source": "TSL", "book": "TSL", "snapshot_type": "pregame"},
        ]
        game_id = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
        record = _make_record(game_id, history_entries=history)
        record["decision_ts"] = "2026-04-29T07:00:00Z"
        record["latest_pregame_ts"] = "2026-04-29T07:00:00Z"
        record["opening_ts"] = "2026-04-29T07:00:00Z"
        path = _write_timeline([record], tmp_path)
        loader = OddsTimelineLoader(path=path)

        row = _base_row("home")
        result = align_odds_snapshot_for_prediction(row, loader)
        assert result["odds_snapshot_alignment_status"] == "STALE"


# ─────────────────────────────────────────────────────────────────────────────
# 10. Adapter row count
# ─────────────────────────────────────────────────────────────────────────────
def test_adapter_row_count():
    """Phase 6S output must have exactly 14 rows (7 games × 2 sides)."""
    output_path = _REPO_ROOT / "data" / "derived" / "model_outputs_6s_future_2026-04-30.jsonl"
    assert output_path.exists(), "Phase 6S output must be generated first"
    rows = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    assert len(rows) == 14, f"Expected 14 rows, got {len(rows)}"


# ─────────────────────────────────────────────────────────────────────────────
# 11. clv_usable = True for all aligned rows in adapter output
# ─────────────────────────────────────────────────────────────────────────────
def test_adapter_clv_usable_true_for_aligned_rows():
    output_path = _REPO_ROOT / "data" / "derived" / "model_outputs_6s_future_2026-04-30.jsonl"
    rows = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    aligned = [r for r in rows if r.get("odds_snapshot_alignment_status") == "ALIGNED"]
    not_clv = [r for r in aligned if not r.get("clv_usable")]
    assert not not_clv, (
        f"{len(not_clv)} ALIGNED rows unexpectedly have clv_usable=False: "
        + str([r.get("canonical_match_id") for r in not_clv])
    )


# ─────────────────────────────────────────────────────────────────────────────
# 12. No post-prediction leakage in adapter output
# ─────────────────────────────────────────────────────────────────────────────
def test_adapter_no_post_prediction_leakage():
    output_path = _REPO_ROOT / "data" / "derived" / "model_outputs_6s_future_2026-04-30.jsonl"
    rows = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    for row in rows:
        snap_ts = row.get("odds_snapshot_time_utc")
        pred_ts = row.get("prediction_time_utc")
        if snap_ts and pred_ts:
            assert snap_ts <= pred_ts, (
                f"POST-PREDICTION LEAKAGE: snap={snap_ts} > pred={pred_ts} "
                f"in {row.get('canonical_match_id')}"
            )
