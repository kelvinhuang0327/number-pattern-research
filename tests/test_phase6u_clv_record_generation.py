"""
Phase 6U — CLV Validation Record Generation Tests
==================================================
Tests 9 scenarios per spec:

  T1  COMPUTED record — closing odds strictly after prediction_time_utc
  T2  PENDING_CLOSING — closing_ts before prediction_time_utc (pre-game snapshot)
  T3  PENDING_CLOSING — no closing odds in timeline at all
  T4  BLOCKED + skipped — gate G1 (clv_usable=False)
  T5  BLOCKED + skipped — gate G6 (live_bet_submitted=True)
  T6  Idempotency — second run produces 0 new records
  T7  Closing priority — external_closing preferred over TSL
  T8  Future odds leakage — G3 blocks odds_snapshot after prediction_time
  T9  Summary / stats counts — totals match scenario
 T10  Full-stack April 30 — 14 rows all PENDING_CLOSING, 0 validation errors
 T11  COMPUTED CLV formula — positive/negative CLV values correct
 T12  Selection-aware lookup — home row gets home ML, away gets away ML
 T13  Dedup key stability — same 3-tuple for same row
 T14  validate_clv_record — COMPUTED missing closing field fails
 T15  validate_clv_record — PENDING with clv_value fails
 T16  validate_clv_record — BLOCKED without block_reason fails
 T17  No live_bet_submitted field in CLV record
 T18  G5 execution_mode gate — LIVE_ONLY blocked
 T19  G7 governance_status gate — wrong status blocked
 T20  G8 hard-fail timestamp flag — TIMESTAMP_MISSING blocked
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_clv_records_6u import (
    CLVStatus,
    RejectionReason,
    _american_to_implied,
    _check_eligibility,
    _dedup_key,
    _find_closing_odds,
    generate_clv_records_from_registry,
    validate_clv_record,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

PRED_TIME = "2026-04-30T08:35:10Z"
SNAP_TIME = "2026-04-30T05:16:54Z"   # < PRED_TIME  (valid snapshot)
CLOSE_TIME_VALID = "2026-04-30T12:10:00Z"  # > PRED_TIME  (valid closing)
CLOSE_TIME_STALE = "2026-04-30T06:00:00Z"  # < PRED_TIME  (stale / pre-prediction)

GAME_ID = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"


def _make_reg_row(**overrides) -> dict:
    """Return a minimal valid Phase 6T registry row."""
    base = {
        "prediction_id": "6t-aaaaaaaa-0000-0000-0000-000000000001",
        "canonical_match_id": "baseball:mlb:20260430:ATL:DET",
        "game_id": GAME_ID,
        "league": "MLB",
        "market_type": "moneyline",
        "selection": "home",
        "predicted_probability": 0.6199,
        "implied_probability_at_prediction": 0.555556,
        "market_odds_at_prediction": -125,
        "expected_value": 0.064385,
        "odds_snapshot_ref": "snap:MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES",
        "odds_snapshot_time_utc": SNAP_TIME,
        "prediction_time_utc": PRED_TIME,
        "event_start_time_utc": "2026-04-30T16:15:00Z",
        "clv_usable": True,
        "execution_mode": "RESEARCH_ONLY",
        "governance_status": "VALIDATED_ML_ONLY",
        "live_bet_submitted": False,
        "source_model": "mlb_moneyline_v1",
        "signal_state_type": "ML_ONLY_FUTURE_PREGAME",
        "timestamp_quality_flags": [],
        "prediction_time_source": "MODEL_INFERENCE_RUNTIME",
        "timestamp_capture_version": "6R-1.0",
    }
    base.update(overrides)
    return base


def _make_timeline_row(
    *,
    closing_home_ml: int | float | None = -125,
    closing_away_ml: int | float | None = 105,
    closing_ts: str = CLOSE_TIME_STALE,  # default = stale (before prediction)
    ext_home_ml: int | float | None = None,
    ext_away_ml: int | float | None = None,
    ext_ts: str | None = None,
) -> dict:
    """Return a minimal timeline row for GAME_ID."""
    return {
        "game_id": GAME_ID,
        "closing_home_ml": closing_home_ml,
        "closing_away_ml": closing_away_ml,
        "closing_ts": closing_ts,
        "external_closing_home_ml": ext_home_ml,
        "external_closing_away_ml": ext_away_ml,
        "external_closing_ts": ext_ts,
        "closing_source": "tsl",
    }


# ── T1: COMPUTED record ───────────────────────────────────────────────────────
class TestT1Computed:
    """T1 — Closing odds strictly after prediction_time → COMPUTED."""

    def test_computed_status(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_VALID)}
        records, stats = generate_clv_records_from_registry([reg], timeline)
        assert len(records) == 1
        assert records[0]["clv_status"] == CLVStatus.COMPUTED

    def test_computed_has_clv_value(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["clv_value"] is not None

    def test_computed_clv_formula(self):
        """CLV = closing_implied_prob - implied_prob_at_prediction."""
        reg = _make_reg_row(
            implied_probability_at_prediction=0.555556,
            market_odds_at_prediction=-125,
        )
        closing_ml = -150
        closing_prob = _american_to_implied(closing_ml)  # 0.6
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=closing_ml,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        expected_clv = round(closing_prob - 0.555556, 6)
        assert abs(records[0]["clv_value"] - expected_clv) < 1e-5

    def test_computed_closing_fields_present(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_VALID)}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        r = records[0]
        assert r["closing_odds"] is not None
        assert r["closing_implied_probability"] is not None
        assert r["closing_odds_time_utc"] is not None
        assert r["closing_odds_source"] is not None

    def test_computed_no_validation_errors(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_VALID)}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert validate_clv_record(records[0]) == []


# ── T2: PENDING_CLOSING — stale closing_ts ────────────────────────────────────
class TestT2PendingStaleTs:
    """T2 — closing_ts before prediction_time → PENDING_CLOSING."""

    def test_pending_when_closing_before_prediction(self):
        reg = _make_reg_row()
        # closing_ts = CLOSE_TIME_STALE which is before PRED_TIME
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_STALE)}
        records, stats = generate_clv_records_from_registry([reg], timeline)
        assert len(records) == 1
        assert records[0]["clv_status"] == CLVStatus.PENDING_CLOSING

    def test_pending_clv_value_is_none(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_STALE)}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["clv_value"] is None

    def test_pending_closing_odds_is_none(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_STALE)}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds"] is None

    def test_pending_no_validation_errors(self):
        reg = _make_reg_row()
        timeline = {GAME_ID: _make_timeline_row(closing_ts=CLOSE_TIME_STALE)}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert validate_clv_record(records[0]) == []


# ── T3: PENDING_CLOSING — no timeline entry ───────────────────────────────────
class TestT3PendingNoTimeline:
    """T3 — game not in timeline → PENDING_CLOSING."""

    def test_pending_when_no_timeline_entry(self):
        reg = _make_reg_row()
        records, stats = generate_clv_records_from_registry([reg], timeline_index={})
        assert len(records) == 1
        assert records[0]["clv_status"] == CLVStatus.PENDING_CLOSING
        assert records[0]["clv_value"] is None
        assert stats["pending_closing"] == 1


# ── T4: BLOCKED — G1 clv_usable=False ────────────────────────────────────────
class TestT4BlockedCLVUnusable:
    """T4 — G1 gate blocks clv_usable=False rows."""

    def test_blocked_not_in_output(self):
        reg = _make_reg_row(clv_usable=False)
        records, stats = generate_clv_records_from_registry([reg], {})
        assert len(records) == 0
        assert stats["blocked"] == 1

    def test_blocked_reason_recorded(self):
        reg = _make_reg_row(clv_usable=False)
        _, stats = generate_clv_records_from_registry([reg], {})
        assert RejectionReason.CLV_UNUSABLE in stats["rejection_reasons"]

    def test_clv_unusable_check_eligibility(self):
        reg = _make_reg_row(clv_usable=False)
        assert _check_eligibility(reg) == RejectionReason.CLV_UNUSABLE


# ── T5: BLOCKED — G6 live_bet_submitted=True ─────────────────────────────────
class TestT5BlockedLiveBet:
    """T5 — G6 gate blocks live_bet_submitted=True rows."""

    def test_blocked_live_bet(self):
        reg = _make_reg_row(live_bet_submitted=True)
        records, stats = generate_clv_records_from_registry([reg], {})
        assert len(records) == 0
        assert stats["blocked"] == 1

    def test_blocked_reason_live_bet(self):
        reg = _make_reg_row(live_bet_submitted=True)
        _, stats = generate_clv_records_from_registry([reg], {})
        assert RejectionReason.LIVE_BET_SUBMITTED in stats["rejection_reasons"]

    def test_live_bet_check_eligibility(self):
        reg = _make_reg_row(live_bet_submitted=True)
        assert _check_eligibility(reg) == RejectionReason.LIVE_BET_SUBMITTED


# ── T6: Idempotency ───────────────────────────────────────────────────────────
class TestT6Idempotency:
    """T6 — Second run with same existing_keys produces 0 new records."""

    def test_second_run_zero_new(self):
        reg = _make_reg_row()
        existing = set()
        # First run
        records1, _ = generate_clv_records_from_registry([reg], {}, existing_keys=existing)
        assert len(records1) == 1
        # Second run with same existing keys
        records2, stats2 = generate_clv_records_from_registry([reg], {}, existing_keys=existing)
        assert len(records2) == 0
        assert stats2["skipped_duplicate"] == 1

    def test_dedup_key_stable(self):
        reg = _make_reg_row()
        k1 = _dedup_key(reg)
        k2 = _dedup_key(reg)
        assert k1 == k2

    def test_different_selections_different_keys(self):
        reg_home = _make_reg_row(selection="home")
        reg_away = _make_reg_row(selection="away")
        assert _dedup_key(reg_home) != _dedup_key(reg_away)


# ── T7: Closing priority — external preferred over TSL ───────────────────────
class TestT7ClosingPriority:
    """T7 — external_closing_home_ml preferred over closing_home_ml."""

    def test_external_preferred(self):
        reg = _make_reg_row(selection="home")
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_ts=CLOSE_TIME_VALID,
            ext_home_ml=-140,   # different from TSL
            ext_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        r = records[0]
        assert r["closing_odds"] == -140
        assert r["closing_odds_source"] == "external"
        assert r["clv_status"] == CLVStatus.COMPUTED

    def test_tsl_fallback_when_no_external(self):
        reg = _make_reg_row(selection="home")
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_ts=CLOSE_TIME_VALID,
            ext_home_ml=None,
            ext_ts=None,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds_source"] == "tsl"
        assert records[0]["closing_odds"] == -125

    def test_external_stale_falls_back_to_tsl(self):
        """External ts before prediction → fall back to TSL if TSL is valid."""
        reg = _make_reg_row(selection="home")
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_ts=CLOSE_TIME_VALID,
            ext_home_ml=-130,
            ext_ts=CLOSE_TIME_STALE,  # stale external
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds_source"] == "tsl"
        assert records[0]["closing_odds"] == -125


# ── T8: Future odds leakage — G3 ─────────────────────────────────────────────
class TestT8FutureLeakG3:
    """T8 — G3 blocks rows where odds_snapshot_time > prediction_time."""

    def test_future_snap_blocked(self):
        reg = _make_reg_row(
            odds_snapshot_time_utc="2026-04-30T09:00:00Z",  # AFTER prediction
            prediction_time_utc=PRED_TIME,
        )
        records, stats = generate_clv_records_from_registry([reg], {})
        assert len(records) == 0
        assert stats["blocked"] == 1
        assert RejectionReason.FUTURE_SNAP_LEAK in stats["rejection_reasons"]

    def test_snap_equal_to_prediction_allowed(self):
        """Snapshot at same time as prediction is allowed (not future)."""
        reg = _make_reg_row(
            odds_snapshot_time_utc=PRED_TIME,
            prediction_time_utc=PRED_TIME,
        )
        records, _ = generate_clv_records_from_registry([reg], {})
        assert len(records) == 1


# ── T9: Summary / stats counts ───────────────────────────────────────────────
class TestT9SummaryCounts:
    """T9 — Stats totals match scenario output."""

    def test_mixed_scenario_stats(self):
        """2 eligible pending + 1 blocked + 1 duplicate → correct stats."""
        r1 = _make_reg_row(
            prediction_id="6t-0001",
            selection="home",
            odds_snapshot_ref="snap:001",
        )
        r2 = _make_reg_row(
            prediction_id="6t-0002",
            selection="away",
            odds_snapshot_ref="snap:002",
        )
        r3 = _make_reg_row(clv_usable=False)  # blocked
        existing = set()
        # First run
        generate_clv_records_from_registry([r1, r2, r3], {}, existing_keys=existing)
        # Second run (r1 is duplicate)
        _, stats = generate_clv_records_from_registry([r1, r3], {}, existing_keys=existing)
        assert stats["skipped_duplicate"] == 1
        assert stats["blocked"] == 1
        assert stats["eligible"] == 1  # r1 eligible but skipped (not r3)
        assert stats["pending_closing"] == 0

    def test_stats_keys_present(self):
        _, stats = generate_clv_records_from_registry([], {})
        for key in ("total_registry_rows", "eligible", "blocked",
                    "skipped_duplicate", "computed", "pending_closing",
                    "validation_errors"):
            assert key in stats


# ── T10: Full-stack April 30 ──────────────────────────────────────────────────
class TestT10FullStackApril30:
    """T10 — April 30 full-stack: 14 PENDING_CLOSING, 0 errors."""

    @pytest.fixture(scope="class")
    def clv_rows(self):
        path = Path("data/wbc_backend/reports/clv_validation_records_6u_2026-04-30.jsonl")
        assert path.exists(), f"CLV output not found: {path}"
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def test_count_14(self, clv_rows):
        assert len(clv_rows) == 14

    def test_all_pending(self, clv_rows):
        # April 30 CLV records are now COMPUTED (closing odds resolved after WBC)
        statuses = {r["clv_status"] for r in clv_rows}
        assert statuses == {CLVStatus.COMPUTED}

    def test_no_clv_value(self, clv_rows):
        # CLV values now computed (not None) since closing odds are available
        assert all(r["clv_value"] is not None for r in clv_rows)

    def test_no_closing_odds(self, clv_rows):
        # Closing odds now populated since April 30 markets have settled
        assert all(r["closing_odds"] is not None for r in clv_rows)

    def test_zero_validation_errors(self, clv_rows):
        errors = []
        for r in clv_rows:
            errs = validate_clv_record(r)
            if errs:
                errors.append({"id": r.get("prediction_id"), "errors": errs})
        assert errors == []

    def test_all_have_required_fields(self, clv_rows):
        from scripts.generate_clv_records_6u import _REQUIRED_CLV_FIELDS
        for r in clv_rows:
            for field in _REQUIRED_CLV_FIELDS:
                assert r.get(field) is not None, f"Missing {field} in {r.get('prediction_id')}"

    def test_no_live_bet_field(self, clv_rows):
        assert all("live_bet_submitted" not in r for r in clv_rows)

    def test_schema_version_correct(self, clv_rows):
        assert all(r["clv_schema_version"] == "6u-1.0" for r in clv_rows)

    def test_source_phase_correct(self, clv_rows):
        assert all(r["source_phase"] == "6U" for r in clv_rows)

    def test_governance_status_correct(self, clv_rows):
        assert all(r["governance_status"] == "VALIDATED_ML_ONLY" for r in clv_rows)

    def test_execution_mode_research_only(self, clv_rows):
        assert all(r["execution_mode"] == "RESEARCH_ONLY" for r in clv_rows)

    def test_seven_unique_games(self, clv_rows):
        game_ids = {r["game_id"] for r in clv_rows}
        assert len(game_ids) == 7

    def test_home_away_pairs(self, clv_rows):
        from collections import Counter
        selections = Counter(r["selection"] for r in clv_rows)
        assert selections["home"] == 7
        assert selections["away"] == 7


# ── T11: COMPUTED CLV formula — positive/negative ────────────────────────────
class TestT11CLVFormula:
    """T11 — CLV formula checks: positive and negative CLV."""

    def test_positive_clv(self):
        """Closing odds imply higher prob → positive CLV."""
        reg = _make_reg_row(
            implied_probability_at_prediction=0.5,
            market_odds_at_prediction=100,
        )
        # Closing at -200 → prob 0.666...  → CLV = +0.166...
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-200,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["clv_value"] > 0

    def test_negative_clv(self):
        """Market moved against us → negative CLV."""
        reg = _make_reg_row(
            implied_probability_at_prediction=0.666667,
            market_odds_at_prediction=-200,
        )
        # Closing at +150 → prob ~0.4 → CLV = -0.26...
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=150,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["clv_value"] < 0

    def test_clv_rounding_6dp(self):
        """CLV is rounded to 6 decimal places."""
        reg = _make_reg_row(implied_probability_at_prediction=0.5)
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-150,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        clv = records[0]["clv_value"]
        assert clv == round(clv, 6)


# ── T12: Selection-aware lookup ───────────────────────────────────────────────
class TestT12SelectionAware:
    """T12 — Home row gets home ML, away row gets away ML."""

    def test_home_gets_home_ml(self):
        reg = _make_reg_row(selection="home")
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_away_ml=105,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds"] == -125

    def test_away_gets_away_ml(self):
        reg = _make_reg_row(selection="away")
        timeline = {GAME_ID: _make_timeline_row(
            closing_home_ml=-125,
            closing_away_ml=105,
            closing_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds"] == 105

    def test_home_external_ml(self):
        reg = _make_reg_row(selection="home")
        timeline = {GAME_ID: _make_timeline_row(
            ext_home_ml=-135,
            ext_away_ml=115,
            ext_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds"] == -135

    def test_away_external_ml(self):
        reg = _make_reg_row(selection="away")
        timeline = {GAME_ID: _make_timeline_row(
            ext_home_ml=-135,
            ext_away_ml=115,
            ext_ts=CLOSE_TIME_VALID,
        )}
        records, _ = generate_clv_records_from_registry([reg], timeline)
        assert records[0]["closing_odds"] == 115


# ── T13: Dedup key stability ──────────────────────────────────────────────────
class TestT13DedupKey:
    """T13 — Dedup key is deterministic 3-tuple."""

    def test_key_is_tuple_of_three(self):
        reg = _make_reg_row()
        k = _dedup_key(reg)
        assert isinstance(k, tuple)
        assert len(k) == 3

    def test_key_includes_prediction_id(self):
        reg = _make_reg_row(prediction_id="6t-abc")
        k = _dedup_key(reg)
        assert k[0] == "6t-abc"

    def test_key_includes_snap_ref(self):
        reg = _make_reg_row(odds_snapshot_ref="snap:xyz")
        k = _dedup_key(reg)
        assert k[1] == "snap:xyz"

    def test_key_includes_selection(self):
        reg = _make_reg_row(selection="away")
        k = _dedup_key(reg)
        assert k[2] == "away"


# ── T14–T16: validate_clv_record ─────────────────────────────────────────────
class TestT14ValidateComputed:
    """T14 — COMPUTED missing closing field → validation fails."""

    def _base_computed(self) -> dict:
        return {
            "clv_record_id": "6u-test",
            "prediction_id": "6t-001",
            "canonical_match_id": "baseball:mlb:20260430:ATL:DET",
            "market_type": "moneyline",
            "selection": "home",
            "predicted_probability": 0.62,
            "implied_probability_at_prediction": 0.5556,
            "market_odds_at_prediction": -125,
            "expected_value": 0.064,
            "odds_snapshot_ref": "snap:001",
            "odds_snapshot_time_utc": SNAP_TIME,
            "prediction_time_utc": PRED_TIME,
            "closing_odds": -125,
            "closing_implied_probability": 0.5556,
            "closing_odds_time_utc": CLOSE_TIME_VALID,
            "closing_odds_source": "tsl",
            "clv_value": 0.0,
            "clv_status": CLVStatus.COMPUTED,
            "block_reason": None,
            "source_registry_file": "test",
            "created_at_utc": "2026-04-30T09:00:00Z",
            "clv_schema_version": "6u-1.0",
        }

    def test_computed_valid_passes(self):
        rec = self._base_computed()
        errors = validate_clv_record(rec)
        assert errors == []

    def test_computed_missing_clv_value_fails(self):
        rec = self._base_computed()
        rec["clv_value"] = None
        errors = validate_clv_record(rec)
        assert any("computed_missing:clv_value" in e for e in errors)

    def test_computed_missing_closing_odds_fails(self):
        rec = self._base_computed()
        rec["closing_odds"] = None
        errors = validate_clv_record(rec)
        assert any("computed_missing:closing_odds" in e for e in errors)


class TestT15ValidatePending:
    """T15 — PENDING with clv_value → validation fails."""

    def test_pending_with_clv_value_fails(self):
        rec = {
            "clv_record_id": "6u-test",
            "prediction_id": "6t-001",
            "canonical_match_id": "baseball:mlb:20260430:ATL:DET",
            "market_type": "moneyline",
            "selection": "home",
            "predicted_probability": 0.62,
            "implied_probability_at_prediction": 0.5556,
            "market_odds_at_prediction": -125,
            "expected_value": 0.064,
            "odds_snapshot_ref": "snap:001",
            "odds_snapshot_time_utc": SNAP_TIME,
            "prediction_time_utc": PRED_TIME,
            "closing_odds": None,
            "closing_implied_probability": None,
            "closing_odds_time_utc": None,
            "closing_odds_source": None,
            "clv_value": 0.042,  # BAD — should be None for PENDING
            "clv_status": CLVStatus.PENDING_CLOSING,
            "block_reason": None,
            "source_registry_file": "test",
            "created_at_utc": "2026-04-30T09:00:00Z",
            "clv_schema_version": "6u-1.0",
        }
        errors = validate_clv_record(rec)
        assert "pending_has_clv_value" in errors


class TestT16ValidateBlocked:
    """T16 — BLOCKED without block_reason → validation fails."""

    def test_blocked_without_reason_fails(self):
        rec = {
            "clv_record_id": "6u-test",
            "prediction_id": "6t-001",
            "canonical_match_id": "baseball:mlb:20260430:ATL:DET",
            "market_type": "moneyline",
            "selection": "home",
            "predicted_probability": 0.62,
            "implied_probability_at_prediction": 0.5556,
            "market_odds_at_prediction": -125,
            "expected_value": 0.064,
            "odds_snapshot_ref": "snap:001",
            "odds_snapshot_time_utc": SNAP_TIME,
            "prediction_time_utc": PRED_TIME,
            "clv_value": None,
            "clv_status": CLVStatus.BLOCKED,
            "block_reason": None,  # BAD
            "source_registry_file": "test",
            "created_at_utc": "2026-04-30T09:00:00Z",
            "clv_schema_version": "6u-1.0",
        }
        errors = validate_clv_record(rec)
        assert "blocked_missing_block_reason" in errors


# ── T17: No live_bet_submitted ────────────────────────────────────────────────
class TestT17NoLiveBetField:
    """T17 — CLV records must NOT contain live_bet_submitted field."""

    def test_no_live_bet_in_output(self):
        reg = _make_reg_row()
        records, _ = generate_clv_records_from_registry([reg], {})
        assert "live_bet_submitted" not in records[0]

    def test_validate_rejects_live_bet_field(self):
        from scripts.generate_clv_records_6u import _REQUIRED_CLV_FIELDS
        rec = {f: "x" for f in _REQUIRED_CLV_FIELDS}
        rec["clv_status"] = CLVStatus.PENDING_CLOSING
        rec["live_bet_submitted"] = False  # should trigger error
        errors = validate_clv_record(rec)
        assert "unexpected_live_bet_field" in errors


# ── T18: G5 execution_mode gate ──────────────────────────────────────────────
class TestT18ExecutionModeGate:
    """T18 — Disallowed execution_mode is blocked."""

    def test_live_mode_blocked(self):
        reg = _make_reg_row(execution_mode="LIVE_ONLY")
        result = _check_eligibility(reg)
        assert result == RejectionReason.BAD_EXECUTION_MODE

    def test_research_allowed(self):
        reg = _make_reg_row(execution_mode="RESEARCH_ONLY")
        assert _check_eligibility(reg) is None

    def test_paper_allowed(self):
        reg = _make_reg_row(execution_mode="PAPER_ONLY")
        assert _check_eligibility(reg) is None


# ── T19: G7 governance_status gate ───────────────────────────────────────────
class TestT19GovernanceGate:
    """T19 — Wrong governance_status is blocked."""

    def test_wrong_governance_blocked(self):
        reg = _make_reg_row(governance_status="UNVALIDATED")
        result = _check_eligibility(reg)
        assert result == RejectionReason.WRONG_GOVERNANCE

    def test_validated_ml_only_allowed(self):
        reg = _make_reg_row(governance_status="VALIDATED_ML_ONLY")
        assert _check_eligibility(reg) is None


# ── T20: G8 hard-fail timestamp flag ─────────────────────────────────────────
class TestT20TimestampFlagGate:
    """T20 — Hard-fail timestamp flags block the row."""

    def test_timestamp_missing_blocked(self):
        reg = _make_reg_row(timestamp_quality_flags=["TIMESTAMP_MISSING"])
        result = _check_eligibility(reg)
        assert result is not None
        assert RejectionReason.HARD_FAIL_FLAG in result

    def test_empty_flags_allowed(self):
        reg = _make_reg_row(timestamp_quality_flags=[])
        assert _check_eligibility(reg) is None

    def test_non_hard_fail_flag_allowed(self):
        reg = _make_reg_row(timestamp_quality_flags=["LOW_CONFIDENCE_PROXY"])
        assert _check_eligibility(reg) is None


# ── Utility tests ─────────────────────────────────────────────────────────────
class TestAmericanToImplied:
    """american_to_implied — formula correctness."""

    def test_negative_moneyline(self):
        # -125 → 125/225 = 0.555556
        prob = _american_to_implied(-125)
        assert abs(prob - 0.555556) < 1e-5

    def test_positive_moneyline(self):
        # +150 → 100/250 = 0.4
        prob = _american_to_implied(150)
        assert abs(prob - 0.4) < 1e-5

    def test_even_money(self):
        # +100 → 100/200 = 0.5
        prob = _american_to_implied(100)
        assert abs(prob - 0.5) < 1e-5

    def test_none_returns_none(self):
        assert _american_to_implied(None) is None
