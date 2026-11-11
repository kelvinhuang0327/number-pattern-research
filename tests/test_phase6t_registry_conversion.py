"""
Phase 6T — Prediction Registry Conversion Tests
================================================
Tests for scripts/convert_ml_output_to_registry_6t.py

Test scenarios:
  1  Eligible row converts without error
  2  Converted row has correct governance fields (RESEARCH_ONLY, VALIDATED_ML_ONLY)
  3  No live bet fields are activated
  4  clv_usable=False row is rejected (G1)
  5  Non-ALIGNED alignment status is rejected (G2)
  6  Missing odds_snapshot_ref is rejected (G3)
  7  Missing expected_value is rejected (G4)
  8  Future odds leakage is rejected (G5)
  9  Hard-fail timestamp flag is rejected (G6)
  10 Invalid prediction_time_source (M13) is rejected (G7)
  11 Idempotency — duplicate key is skipped on second run
  12 run_converter writes 14 rows from real Phase 6S file
  13 run_converter is idempotent — second run produces 0 new rows
  14 Registry row has all critical fields non-null
  15 prediction_id is stable (deterministic from model_output_id)
  16 event_start_time_utc maps from match_time_utc
  17 Timestamp chain (6O fields) fully preserved
  18 validate_registry_row passes for a valid row
  19 validate_registry_row catches null critical field
  20 validate_registry_row catches live_bet_submitted=True
  21 validate_registry_row catches invalid execution_mode
  22 Full-stack test: registry_schema_version = "6t-1.0"
  23 Full-stack test: all 14 rows have clv_usable=True
  24 Full-stack test: all 14 rows have ALIGNED odds snapshot
  25 Full-stack test: all 14 rows have positive or negative EV (non-null)
"""
from __future__ import annotations

import json
import copy
import tempfile
from pathlib import Path

import pytest

from scripts.convert_ml_output_to_registry_6t import (
    EXECUTION_MODE,
    GOVERNANCE_STATUS,
    REGISTRY_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    RejectionReason,
    _check_eligibility,
    _dedup_key,
    convert_ml_output_to_prediction_registry,
    run_converter,
    validate_registry_row,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_valid_6s_row(**overrides) -> dict:
    """Return a minimal valid Phase 6S row eligible for conversion."""
    row = {
        "schema_version": "6j-1.0",
        "model_output_id": "6s-test-abc123",
        "prediction_run_id": "run-001",
        "model_family": "mlb_ml_elo_stub",
        "model_version": "mlb_ml_elo_stub_v1.1.0",
        "feature_version": "features_elo_ratings_v1.1.0",
        "leakage_guard_version": "1.0",
        "training_window_id": None,
        "walk_forward_split_id": None,
        "sport": "baseball",
        "league": "mlb",
        "canonical_match_id": "baseball:mlb:20260430:ATL:DET",
        "raw_match_id": "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES",
        "match_time_utc": "2026-04-30T16:15:00Z",
        "home_team_code": "ATL",
        "away_team_code": "DET",
        "market_type": "ML",
        "market_key": "baseball:mlb:20260430:ATL:DET:ml",
        "selection": "home",
        "selection_key": "baseball:mlb:20260430:ATL:DET:ml:home",
        "market_line": None,
        "predicted_probability": 0.619941,
        "confidence_score": None,
        "model_quality_flags": ["ELO_STUB_MODEL_PHASE_6S"],
        "data_quality_flags": [],
        "phase": "6S",
        "adapter_version": "6s-1.0.0",
        "dry_run": False,
        # Phase 6S odds snapshot fields
        "odds_snapshot_ref": "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES|TSL|snap@2026-04-30T05:16:54Z",
        "odds_snapshot_time_utc": "2026-04-30T05:16:54Z",
        "implied_probability_at_prediction": 0.555556,
        "market_odds_at_prediction": -125,
        "odds_snapshot_source": "TSL",
        "odds_snapshot_alignment_status": "ALIGNED",
        "expected_value": 0.064385,
        "clv_usable": True,
        # Phase 6O timestamp fields
        "prediction_run_started_at_utc": "2026-04-30T08:35:10Z",
        "feature_cutoff_time_utc": "2026-04-30T08:35:10Z",
        "prediction_time_utc": "2026-04-30T08:35:10Z",
        "prediction_run_completed_at_utc": "2026-04-30T08:35:10Z",
        "model_output_written_at_utc": "2026-04-30T08:35:11Z",
        "prediction_time_source": "MODEL_INFERENCE_RUNTIME",
        "feature_cutoff_source": "MLB_SCHEDULE_LOAD_TIME",
        "timestamp_capture_version": "6R-1.0",
        "timestamp_quality_flags": [],
    }
    row.update(overrides)
    return row


# ── Gate tests ─────────────────────────────────────────────────────────────────

class TestEligibilityGates:
    """Tests 1–10: eligibility gate checks."""

    # 1 — eligible row converts without error
    def test_eligible_row_no_rejection(self):
        row = _make_valid_6s_row()
        assert _check_eligibility(row) is None

    # 4 — G1: clv_usable=False
    def test_rejects_clv_unusable(self):
        row = _make_valid_6s_row(clv_usable=False)
        assert _check_eligibility(row) == RejectionReason.CLV_UNUSABLE

    # 5 — G2: non-ALIGNED status
    @pytest.mark.parametrize("status", ["MISSING", "STALE", "FUTURE_LEAK_BLOCKED"])
    def test_rejects_non_aligned_status(self, status: str):
        row = _make_valid_6s_row(odds_snapshot_alignment_status=status)
        assert _check_eligibility(row) == RejectionReason.NOT_ALIGNED

    # 6 — G3: missing odds_snapshot_ref
    @pytest.mark.parametrize("ref", [None, ""])
    def test_rejects_missing_snap_ref(self, ref):
        row = _make_valid_6s_row(odds_snapshot_ref=ref)
        assert _check_eligibility(row) == RejectionReason.NO_SNAP_REF

    # 7 — G4: missing expected_value
    def test_rejects_missing_ev(self):
        row = _make_valid_6s_row(expected_value=None)
        assert _check_eligibility(row) == RejectionReason.NO_EV

    # 8 — G5: future odds leakage (snap_ts > pred_ts)
    def test_rejects_future_odds_leakage(self):
        row = _make_valid_6s_row(
            odds_snapshot_time_utc="2026-04-30T10:00:00Z",  # after prediction
            prediction_time_utc="2026-04-30T08:35:10Z",
        )
        assert _check_eligibility(row) == RejectionReason.FUTURE_LEAK

    # 9 — G6: hard-fail timestamp flag
    @pytest.mark.parametrize("flag", [
        "TIMESTAMP_MISSING",
        "PREDICTION_TIME_AFTER_MATCH",
        "FEATURE_CUTOFF_AFTER_PREDICTION",
        "HISTORICAL_TIMESTAMP_RECOVERY",
    ])
    def test_rejects_hard_fail_timestamp_flag(self, flag: str):
        row = _make_valid_6s_row(timestamp_quality_flags=[flag])
        assert _check_eligibility(row) == RejectionReason.HARD_FAIL_FLAG

    # 10 — G7: invalid prediction_time_source
    @pytest.mark.parametrize("src", ["MANUAL_OVERRIDE", "UNKNOWN", "", None])
    def test_rejects_invalid_prediction_time_source(self, src):
        row = _make_valid_6s_row(prediction_time_source=src)
        assert _check_eligibility(row) == RejectionReason.M13_FAIL


# ── Conversion content tests ───────────────────────────────────────────────────

class TestConversionContent:
    """Tests 2, 3, 15, 16, 17, 22: output field correctness."""

    def test_governance_fields_correct(self):
        # Test 2
        row = _make_valid_6s_row()
        reg = convert_ml_output_to_prediction_registry(row)
        assert reg["execution_mode"] == EXECUTION_MODE          # RESEARCH_ONLY
        assert reg["governance_status"] == GOVERNANCE_STATUS    # VALIDATED_ML_ONLY
        assert reg["signal_state_type"] == "ML_ONLY_FUTURE_PREGAME"

    def test_no_live_bet_fields_activated(self):
        # Test 3
        row = _make_valid_6s_row()
        reg = convert_ml_output_to_prediction_registry(row)
        assert reg["live_bet_submitted"] is False
        assert reg["live_bet_stake"] is None
        assert reg["live_bet_ref"] is None

    def test_prediction_id_is_stable(self):
        # Test 15 — same model_output_id → same prediction_id
        row = _make_valid_6s_row(model_output_id="6s-fixed-id-xyz")
        id_a = convert_ml_output_to_prediction_registry(row)["prediction_id"]
        id_b = convert_ml_output_to_prediction_registry(row)["prediction_id"]
        assert id_a == id_b
        assert id_a.startswith("6t-")

    def test_different_source_ids_different_prediction_ids(self):
        row_a = _make_valid_6s_row(model_output_id="6s-id-A")
        row_b = _make_valid_6s_row(model_output_id="6s-id-B")
        id_a = convert_ml_output_to_prediction_registry(row_a)["prediction_id"]
        id_b = convert_ml_output_to_prediction_registry(row_b)["prediction_id"]
        assert id_a != id_b

    def test_event_start_time_from_match_time_utc(self):
        # Test 16
        row = _make_valid_6s_row(match_time_utc="2026-04-30T16:15:00Z")
        reg = convert_ml_output_to_prediction_registry(row)
        assert reg["event_start_time_utc"] == "2026-04-30T16:15:00Z"

    def test_timestamp_chain_fully_preserved(self):
        # Test 17
        row = _make_valid_6s_row()
        reg = convert_ml_output_to_prediction_registry(row)
        assert reg["prediction_run_started_at_utc"] == row["prediction_run_started_at_utc"]
        assert reg["feature_cutoff_time_utc"] == row["feature_cutoff_time_utc"]
        assert reg["prediction_time_utc"] == row["prediction_time_utc"]
        assert reg["prediction_run_completed_at_utc"] == row["prediction_run_completed_at_utc"]
        assert reg["model_output_written_at_utc"] == row["model_output_written_at_utc"]
        assert reg["prediction_time_source"] == row["prediction_time_source"]
        assert reg["feature_cutoff_source"] == row["feature_cutoff_source"]
        assert reg["timestamp_capture_version"] == row["timestamp_capture_version"]
        assert reg["timestamp_quality_flags"] == []

    def test_registry_schema_version(self):
        # Test 22
        row = _make_valid_6s_row()
        reg = convert_ml_output_to_prediction_registry(row)
        assert reg["registry_schema_version"] == REGISTRY_SCHEMA_VERSION  # "6t-1.0"
        assert reg["validation_schema_version"] == VALIDATION_SCHEMA_VERSION  # "6j-1.0"

    def test_convert_raises_for_ineligible(self):
        row = _make_valid_6s_row(clv_usable=False)
        with pytest.raises(ValueError, match="ineligible"):
            convert_ml_output_to_prediction_registry(row)


# ── Validate registry row tests ────────────────────────────────────────────────

class TestValidateRegistryRow:
    """Tests 18–21: post-conversion validation."""

    def _valid_reg_row(self) -> dict:
        row = _make_valid_6s_row()
        return convert_ml_output_to_prediction_registry(row)

    def test_valid_row_passes(self):
        # Test 18
        reg = self._valid_reg_row()
        assert validate_registry_row(reg) == []

    def test_catches_null_critical_field(self):
        # Test 19
        reg = self._valid_reg_row()
        reg["canonical_match_id"] = None
        errors = validate_registry_row(reg)
        assert any("NULL_CRITICAL_FIELD" in e for e in errors)

    def test_catches_live_bet_activated(self):
        # Test 20
        reg = self._valid_reg_row()
        reg["live_bet_submitted"] = True
        errors = validate_registry_row(reg)
        assert any("LIVE_BET_ACTIVATED" in e for e in errors)

    def test_catches_invalid_execution_mode(self):
        # Test 21
        reg = self._valid_reg_row()
        reg["execution_mode"] = "LIVE_BETTING"
        errors = validate_registry_row(reg)
        assert any("INVALID_EXECUTION_MODE" in e for e in errors)

    def test_catches_live_bet_ref_set(self):
        reg = self._valid_reg_row()
        reg["live_bet_ref"] = "bet-abc123"
        errors = validate_registry_row(reg)
        assert any("LIVE_BET_ACTIVATED" in e for e in errors)


# ── Idempotency test ───────────────────────────────────────────────────────────

class TestIdempotency:
    """Test 11: duplicate key detection."""

    def test_dedup_key_matches_identical_rows(self):
        # Test 11
        row = _make_valid_6s_row()
        assert _dedup_key(row) == _dedup_key(copy.deepcopy(row))

    def test_dedup_key_differs_by_selection(self):
        row_home = _make_valid_6s_row(selection="home")
        row_away = _make_valid_6s_row(selection="away")
        assert _dedup_key(row_home) != _dedup_key(row_away)

    def test_run_converter_idempotent(self, tmp_path):
        # Build a minimal one-row source file
        row = _make_valid_6s_row()
        src = tmp_path / "source.jsonl"
        src.write_text(json.dumps(row) + "\n")

        out = tmp_path / "registry.jsonl"
        summary_path = tmp_path / "summary.json"

        # First run
        r1 = run_converter(
            input_path=str(src),
            output_path=str(out),
            summary_path=str(summary_path),
        )
        assert r1["converted"] == 1
        assert r1["rejected_total"] == 0

        # Second run — same row must be deduped
        r2 = run_converter(
            input_path=str(src),
            output_path=str(out),
            summary_path=str(summary_path),
        )
        assert r2["converted"] == 0
        assert r2["rejected_by_reason"].get(RejectionReason.DUPLICATE) == 1

        # Output file must have exactly 1 line
        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 1


# ── Full-stack integration tests ───────────────────────────────────────────────

PHASE_6S_SOURCE = Path("data/derived/model_outputs_6s_future_2026-04-30.jsonl")

@pytest.mark.skipif(
    not PHASE_6S_SOURCE.exists(),
    reason="Phase 6S source file not present"
)
class TestFullStackApril30:
    """Tests 12–14, 23–25: run against real Phase 6S JSONL."""

    @pytest.fixture(scope="class")
    def registry_rows(self, tmp_path_factory) -> list[dict]:
        tmp = tmp_path_factory.mktemp("6t_test")
        out = tmp / "registry.jsonl"
        summary = tmp / "summary.json"
        run_converter(
            input_path=str(PHASE_6S_SOURCE),
            output_path=str(out),
            summary_path=str(summary),
        )
        return [json.loads(l) for l in out.read_text().splitlines() if l.strip()]

    def test_14_rows_written(self, registry_rows):
        # Test 12
        assert len(registry_rows) == 14

    def test_all_critical_fields_non_null(self, registry_rows):
        # Test 14
        from scripts.convert_ml_output_to_registry_6t import _CRITICAL_REGISTRY_FIELDS
        for row in registry_rows:
            for field in _CRITICAL_REGISTRY_FIELDS:
                assert row.get(field) is not None, (
                    f"NULL critical field {field!r} in row {row.get('canonical_match_id')}"
                )

    def test_all_clv_usable_true(self, registry_rows):
        # Test 23
        assert all(r["clv_usable"] is True for r in registry_rows)

    def test_all_aligned(self, registry_rows):
        # Test 24
        assert all(r["odds_snapshot_alignment_status"] == "ALIGNED" for r in registry_rows)

    def test_all_ev_non_null(self, registry_rows):
        # Test 25
        for r in registry_rows:
            assert r["expected_value"] is not None
            assert isinstance(r["expected_value"], float)

    def test_governance_all_research_only(self, registry_rows):
        # Test 13 governance side: all rows are RESEARCH_ONLY (not live)
        assert all(r["execution_mode"] == "RESEARCH_ONLY" for r in registry_rows)
        assert all(r["governance_status"] == "VALIDATED_ML_ONLY" for r in registry_rows)

    def test_no_live_betting_in_any_row(self, registry_rows):
        # No row activates live betting
        assert not any(r["live_bet_submitted"] for r in registry_rows)
        assert not any(r["live_bet_ref"] for r in registry_rows)

    def test_idempotency_full_stack(self, tmp_path_factory):
        # Test 13: run again into same file → no new rows
        tmp = tmp_path_factory.mktemp("6t_idem")
        out = tmp / "registry.jsonl"
        summary = tmp / "summary.json"

        r1 = run_converter(
            input_path=str(PHASE_6S_SOURCE),
            output_path=str(out),
            summary_path=str(summary),
        )
        assert r1["converted"] == 14

        r2 = run_converter(
            input_path=str(PHASE_6S_SOURCE),
            output_path=str(out),
            summary_path=str(summary),
        )
        assert r2["converted"] == 0
        assert r2["rejected_by_reason"].get(RejectionReason.DUPLICATE) == 14

        lines = [l for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 14
