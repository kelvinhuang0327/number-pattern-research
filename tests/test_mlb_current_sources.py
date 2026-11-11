"""Tests for MLB Current Schedule and Odds Source Adapter.

25 tests covering:
  1–3:   Odds math (american_odds_to_implied_prob, normalize_two_way_no_vig)
  4–6:   Dataclass schemas (MarketCoverage, GameMarketSnapshot, SourceHealth)
  7–9:   Fixture loading (load, game count, moneyline coverage)
  10–11: Unavailable field handling (runline, total)
  12–13: Validation functions (source health, market snapshot)
  14:    Current source unavailable → fallback/replay behaviour
  15:    Daily advisory today mode can use fixture source
  16:    Fixture source cannot generate LEAN when model unavailable
  17–19: Report fields (fixture_source_used, source_mode, market coverage matrix)
  20–21: No side effects (JSONL not modified, ledger not overwritten)
  22:    No real-bet side effects
  23:    Gate is one of 7 valid values
  24:    Markdown report includes no-real-bet / no profit claim
  25:    Phase67–72 + metrics + daily advisory regression not broken
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.mlb_current_sources import (
    # Constants
    COMPLETION_MARKER,
    DEFAULT_FIXTURE_PATH,
    MLB_CURRENT_SOURCE_ADAPTER_READY,
    MLB_CURRENT_SOURCE_DATA_LIMITED,
    MLB_CURRENT_SOURCE_FIXTURE_READY,
    MLB_CURRENT_SOURCE_GOVERNANCE_RISK,
    MLB_CURRENT_SOURCE_NEEDS_LIVE_API,
    MLB_CURRENT_SOURCE_NOT_READY,
    MLB_CURRENT_SOURCE_SCHEMA_CONFLICT,
    MODULE_VERSION,
    NO_EDGE_CLAIM,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    SOURCE_MODE_CURRENT,
    SOURCE_MODE_FIXTURE,
    SOURCE_MODE_REPLAY,
    VALID_GATES,
    VALID_SOURCE_MODES,
    # Dataclasses
    GameMarketSnapshot,
    MarketCoverage,
    SourceHealth,
    # Functions
    american_odds_to_implied_prob,
    build_market_coverage,
    determine_gate,
    load_fixture_schedule_odds,
    merge_current_source_with_advisory_rows,
    normalize_current_source_games,
    normalize_two_way_no_vig,
    probe_current_mlb_source,
    validate_market_snapshot,
    validate_source_health,
)
from orchestrator.mlb_daily_advisory import (
    REC_LEAN_AWAY,
    REC_LEAN_HOME,
    REC_PASS,
    run_mlb_daily_advisory,
)

# ─── Shared helpers ────────────────────────────────────────────────────────────


def _make_minimal_snapshot(
    game_id: str = "TEST_GAME_001",
    game_date: str = "2026-05-07",
    home_ml: float | None = -140.0,
    away_ml: float | None = 120.0,
    runline_spread: float | None = None,
    total_line: float | None = None,
) -> GameMarketSnapshot:
    """Helper to build a minimal valid snapshot for tests."""
    home_imp = american_odds_to_implied_prob(home_ml) if home_ml is not None else None
    away_imp = american_odds_to_implied_prob(away_ml) if away_ml is not None else None
    if home_imp and away_imp:
        market_no_vig, _ = normalize_two_way_no_vig(home_imp, away_imp)
    else:
        market_no_vig = None

    unavail = []
    if home_ml is None:
        unavail.extend(["home_moneyline_odds", "home_implied_prob",
                         "away_implied_prob", "market_home_prob_no_vig"])
    if runline_spread is None:
        unavail.extend(["runline_spread", "runline_home_odds", "runline_away_odds"])
    if total_line is None:
        unavail.extend(["total_line", "over_odds", "under_odds"])

    return GameMarketSnapshot(
        game_id=game_id,
        game_date=game_date,
        home_team="Home Team",
        away_team="Away Team",
        scheduled_start_time="19:10:00",
        home_moneyline_odds=home_ml,
        away_moneyline_odds=away_ml,
        home_implied_prob=round(home_imp, 6) if home_imp else None,
        away_implied_prob=round(away_imp, 6) if away_imp else None,
        market_home_prob_no_vig=round(market_no_vig, 6) if market_no_vig else None,
        runline_spread=runline_spread,
        runline_home_odds=-110.0 if runline_spread is not None else None,
        runline_away_odds=-110.0 if runline_spread is not None else None,
        total_line=total_line,
        over_odds=-110.0 if total_line is not None else None,
        under_odds=-110.0 if total_line is not None else None,
        result_home_score=None,
        result_away_score=None,
        result_status="scheduled",
        source_name="fixture",
        source_timestamp="2026-05-07T00:00:00+00:00",
        unavailable_fields=unavail,
    )


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1 — Odds Math
# ════════════════════════════════════════════════════════════════════════════


class TestOddsMath:
    def test_01_american_odds_positive(self):
        """Positive American odds → correct implied probability."""
        # +120: 100 / (120 + 100) = 100/220 ≈ 0.4545
        prob = american_odds_to_implied_prob(120.0)
        assert abs(prob - (100 / 220)) < 1e-9, f"Expected ~{100/220:.6f}, got {prob:.6f}"

    def test_02_american_odds_negative(self):
        """Negative American odds → correct implied probability."""
        # -140: 140 / (140 + 100) = 140/240 ≈ 0.5833
        prob = american_odds_to_implied_prob(-140.0)
        assert abs(prob - (140 / 240)) < 1e-9, f"Expected ~{140/240:.6f}, got {prob:.6f}"

    def test_03_normalize_two_way_no_vig(self):
        """Two-way no-vig normalization removes overround."""
        # Example: home implied 0.5833, away implied 0.4545 → total = 1.0378
        home_imp = 140 / 240  # 0.5833
        away_imp = 100 / 220  # 0.4545
        home_nv, away_nv = normalize_two_way_no_vig(home_imp, away_imp)
        # Must sum to 1.0
        assert abs(home_nv + away_nv - 1.0) < 1e-9, "no-vig probs must sum to 1.0"
        # Home should be larger (favorite)
        assert home_nv > away_nv
        # Check correct formula
        total = home_imp + away_imp
        assert abs(home_nv - home_imp / total) < 1e-9
        assert abs(away_nv - away_imp / total) < 1e-9


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2 — Dataclass Schemas
# ════════════════════════════════════════════════════════════════════════════


class TestDataclassSchemas:
    def test_04_market_coverage_schema_complete(self):
        """MarketCoverage has all required fields."""
        cov = MarketCoverage(
            moneyline_available=True,
            runline_available=False,
            total_available=False,
            result_available=False,
            odds_available=True,
            market_home_prob_available=True,
            closing_market_available=False,
            source_name="fixture",
            source_mode="fixture",
            unavailable_reasons=["no_runline_data_available"],
        )
        assert cov.moneyline_available is True
        assert cov.runline_available is False
        assert cov.total_available is False
        assert cov.result_available is False
        assert cov.odds_available is True
        assert cov.market_home_prob_available is True
        assert cov.closing_market_available is False
        assert cov.source_name == "fixture"
        assert cov.source_mode == "fixture"
        assert isinstance(cov.unavailable_reasons, list)

    def test_05_game_market_snapshot_schema_complete(self):
        """GameMarketSnapshot has all required fields."""
        snap = _make_minimal_snapshot(
            home_ml=-140.0,
            away_ml=120.0,
            runline_spread=-1.5,
            total_line=8.5,
        )
        required_fields = [
            "game_id", "game_date", "home_team", "away_team",
            "scheduled_start_time", "home_moneyline_odds", "away_moneyline_odds",
            "home_implied_prob", "away_implied_prob", "market_home_prob_no_vig",
            "runline_spread", "runline_home_odds", "runline_away_odds",
            "total_line", "over_odds", "under_odds",
            "result_home_score", "result_away_score", "result_status",
            "source_name", "source_timestamp", "unavailable_fields",
        ]
        for f in required_fields:
            assert hasattr(snap, f), f"GameMarketSnapshot missing field: {f}"

    def test_06_source_health_schema_complete(self):
        """SourceHealth has all required fields."""
        health = SourceHealth(
            source_name="fixture",
            source_mode=SOURCE_MODE_FIXTURE,
            checked_at="2026-05-07T00:00:00+00:00",
            reachable=False,
            total_games=4,
            moneyline_games=3,
            runline_games=2,
            total_games_with_total=1,
            result_games=0,
            errors=["test_error"],
            warnings=["test_warning"],
        )
        required_fields = [
            "source_name", "source_mode", "checked_at", "reachable",
            "total_games", "moneyline_games", "runline_games",
            "total_games_with_total", "result_games", "errors", "warnings",
        ]
        for f in required_fields:
            assert hasattr(health, f), f"SourceHealth missing field: {f}"


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3 — Fixture Loading
# ════════════════════════════════════════════════════════════════════════════


class TestFixtureLoading:
    def test_07_fixture_source_loadable(self):
        """load_fixture_schedule_odds returns a non-empty list."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        assert isinstance(snapshots, list), "Expected list of snapshots"
        assert len(snapshots) > 0, "Fixture should have at least one game"
        # All must be GameMarketSnapshot instances
        for snap in snapshots:
            assert isinstance(snap, GameMarketSnapshot)

    def test_08_fixture_has_at_least_3_games(self):
        """Fixture file contains at least 3 games."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        assert len(snapshots) >= 3, (
            f"Fixture must have >= 3 games; found {len(snapshots)}"
        )

    def test_09_fixture_moneyline_coverage_correct(self):
        """Fixture: at least 1 game with moneyline odds computed."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        games_with_ml = [
            s for s in snapshots if s.market_home_prob_no_vig is not None
        ]
        assert len(games_with_ml) >= 1, "Fixture must have >= 1 game with ML odds"
        # Verify probability is valid
        for s in games_with_ml:
            assert 0.0 < s.market_home_prob_no_vig < 1.0
            # no-vig: home_implied / (home + away) must be consistent
            h = s.home_implied_prob
            a = s.away_implied_prob
            assert h is not None and a is not None
            expected_nv = h / (h + a)
            assert abs(s.market_home_prob_no_vig - expected_nv) < 1e-4


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4 — Unavailable Field Handling
# ════════════════════════════════════════════════════════════════════════════


class TestUnavailableFields:
    def test_10_runline_missing_marks_unavailable(self):
        """When runline odds absent, runline fields appear in unavailable_fields."""
        snap = _make_minimal_snapshot(runline_spread=None)
        assert "runline_spread" in snap.unavailable_fields
        assert snap.runline_spread is None
        assert snap.runline_home_odds is None
        assert snap.runline_away_odds is None

    def test_11_total_missing_marks_unavailable(self):
        """When total odds absent, total fields appear in unavailable_fields."""
        snap = _make_minimal_snapshot(total_line=None)
        assert "total_line" in snap.unavailable_fields
        assert snap.total_line is None
        assert snap.over_odds is None
        assert snap.under_odds is None

    def test_10b_fixture_game4_all_odds_missing(self):
        """Fixture game 4 (SEA/OAK) has all odds missing → market_home_prob = None."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        no_odds_games = [s for s in snapshots if s.market_home_prob_no_vig is None]
        assert len(no_odds_games) >= 1, "Fixture should have at least 1 game with missing odds"
        snap = no_odds_games[0]
        assert snap.home_moneyline_odds is None
        assert snap.away_moneyline_odds is None
        assert "home_moneyline_odds" in snap.unavailable_fields


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 5 — Validation Functions
# ════════════════════════════════════════════════════════════════════════════


class TestValidationFunctions:
    def test_12_source_health_validates_correctly(self):
        """validate_source_health returns empty list for valid SourceHealth."""
        health = probe_current_mlb_source("2026-05-07")
        errors = validate_source_health(health)
        assert isinstance(errors, list)
        # The probed health should pass schema validation
        assert len(errors) == 0, f"Unexpected validation errors: {errors}"

    def test_13_market_snapshot_validates_correctly(self):
        """validate_market_snapshot returns empty list for valid snapshot."""
        snap = _make_minimal_snapshot(home_ml=-140.0, away_ml=120.0)
        errors = validate_market_snapshot(snap)
        assert isinstance(errors, list)
        assert len(errors) == 0, f"Unexpected validation errors: {errors}"

    def test_13b_invalid_prob_flagged(self):
        """validate_market_snapshot flags out-of-range probability."""
        snap = _make_minimal_snapshot()
        snap.market_home_prob_no_vig = 1.5  # invalid
        errors = validate_market_snapshot(snap)
        assert any("market_home_prob_no_vig_out_of_range" in e for e in errors)


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 6 — Source Unavailability / Fallback
# ════════════════════════════════════════════════════════════════════════════


class TestSourceUnavailability:
    def test_14_current_source_unavailable_returns_needs_live_api(self):
        """When current source unreachable and no snapshots, gate = NEEDS_LIVE_API."""
        health = probe_current_mlb_source("2026-05-07")
        assert health.reachable is False
        # When no snapshots provided → gate should be NEEDS_LIVE_API
        coverage = build_market_coverage([], source_name="current", source_mode=SOURCE_MODE_CURRENT)
        gate, rationale = determine_gate(health, [], coverage)
        assert gate == MLB_CURRENT_SOURCE_NEEDS_LIVE_API
        assert isinstance(rationale, str) and len(rationale) > 0

    def test_14b_probe_health_has_errors_about_no_api(self):
        """probe_current_mlb_source includes error about missing live API."""
        health = probe_current_mlb_source("2026-05-07")
        errors_text = " ".join(health.errors)
        assert "not_configured" in errors_text or "not configured" in errors_text

    def test_14c_fixture_mode_returns_fixture_ready(self):
        """When fixture source loaded with moneyline data, gate = FIXTURE_READY."""
        health = probe_current_mlb_source("2026-05-07")  # reachable=False
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        coverage = build_market_coverage(
            snapshots, source_name="fixture", source_mode=SOURCE_MODE_FIXTURE
        )
        gate, rationale = determine_gate(health, snapshots, coverage)
        assert gate == MLB_CURRENT_SOURCE_FIXTURE_READY
        assert gate in VALID_GATES


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 7 — Daily Advisory Integration
# ════════════════════════════════════════════════════════════════════════════


class TestDailyAdvisoryIntegration:
    def test_15_daily_advisory_today_mode_uses_fixture_source(self):
        """run_mlb_daily_advisory accepts override_games from fixture source."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger_path,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )

        assert result["total_advisories"] == len(snapshots)
        assert result.get("fixture_source_used") is True
        assert result.get("source_mode") == SOURCE_MODE_FIXTURE

    def test_16_fixture_source_no_lean_when_model_unavailable(self):
        """Market-only fixture games (model unavailable) produce PASS, not LEAN."""
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        # Build market-only merged rows (no advisory_rows → all market-only)
        merged = merge_current_source_with_advisory_rows(snapshots, [])

        # All merged rows should have _model_prediction_available = False
        for row in merged:
            assert row.get("_model_prediction_available") is False

        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger_path,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )

        # No LEAN recommendations when model is unavailable
        for adv in result["advisories"]:
            rec = adv.get("moneyline_recommendation")
            assert rec not in {REC_LEAN_HOME, REC_LEAN_AWAY}, (
                f"LEAN generated for market-only game {adv.get('game_id')}: {rec}"
            )


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 8 — Report Fields
# ════════════════════════════════════════════════════════════════════════════


class TestReportFields:
    def _run_fixture_advisory(self, tmp: str) -> dict:
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        ledger_path = os.path.join(tmp, "ledger.jsonl")
        return run_mlb_daily_advisory(
            date_str="2026-05-07",
            mode="today",
            limit=10,
            ledger_path=ledger_path,
            override_games=merged,
            source_mode=SOURCE_MODE_FIXTURE,
            fixture_source_used=True,
            current_source_reachable=False,
            model_prediction_available=False,
            write_reports=False,
        )

    def test_17_report_includes_fixture_source_used(self):
        """Report payload includes fixture_source_used = True."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_fixture_advisory(tmp)
        assert result.get("fixture_source_used") is True

    def test_18_report_includes_source_mode(self):
        """Report payload includes source_mode field."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_fixture_advisory(tmp)
        assert "source_mode" in result
        assert result["source_mode"] == SOURCE_MODE_FIXTURE

    def test_19_report_includes_market_coverage_matrix(self):
        """Report payload includes market_coverage_matrix_summary with source fields."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_fixture_advisory(tmp)
        cov = result.get("market_coverage_matrix_summary", {})
        required_fields = [
            "source_name",
            "source_mode",
            "fixture_source_used",
            "current_source_reachable",
            "model_prediction_available",
            "moneyline_available",
            "runline_available",
            "total_available",
            "result_available",
            "odds_available",
            "market_home_prob_available",
            "closing_market_available",
        ]
        for f in required_fields:
            assert f in cov, (
                f"market_coverage_matrix_summary missing field: {f}"
            )


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 9 — Side Effects / Safety
# ════════════════════════════════════════════════════════════════════════════


class TestSideEffects:
    def test_20_production_prediction_jsonl_not_modified(self):
        """Loading fixture source does not write to or modify the prediction JSONL."""
        from orchestrator.mlb_daily_advisory import DEFAULT_PREDICTION_JSONL
        if not os.path.exists(DEFAULT_PREDICTION_JSONL):
            pytest.skip("Prediction JSONL not present in this environment")
        mtime_before = os.path.getmtime(DEFAULT_PREDICTION_JSONL)
        size_before = os.path.getsize(DEFAULT_PREDICTION_JSONL)

        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        _ = merge_current_source_with_advisory_rows(snapshots, [])

        mtime_after = os.path.getmtime(DEFAULT_PREDICTION_JSONL)
        size_after = os.path.getsize(DEFAULT_PREDICTION_JSONL)

        assert mtime_before == mtime_after, "Prediction JSONL mtime changed — not allowed"
        assert size_before == size_after, "Prediction JSONL size changed — not allowed"

    def test_21_append_only_ledger_not_overwritten(self):
        """Fixture-mode advisory uses a separate temp ledger; does not overwrite existing."""
        from orchestrator.mlb_daily_advisory import DEFAULT_LEDGER_PATH
        exists_before = os.path.exists(DEFAULT_LEDGER_PATH)
        size_before = (
            os.path.getsize(DEFAULT_LEDGER_PATH) if exists_before else None
        )

        with tempfile.TemporaryDirectory() as tmp:
            # Use explicitly separate temp ledger path
            ledger_path = os.path.join(tmp, "test_fixture_ledger.jsonl")
            snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
            merged = merge_current_source_with_advisory_rows(snapshots, [])
            run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger_path,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=True,
            )

        # Default ledger must not have been touched
        if exists_before:
            size_after = os.path.getsize(DEFAULT_LEDGER_PATH)
            assert size_before == size_after, "Default ledger size changed — not allowed"

    def test_22_no_real_bet_side_effects(self):
        """Source adapter constants confirm no-real-bet safety."""
        assert NO_REAL_BET is True
        assert PAPER_ONLY is True
        assert NO_PROFIT_CLAIM is True
        assert NO_EDGE_CLAIM is True

        # Advisory output also confirms
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger_path,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )
        safety = result.get("safety", {})
        assert safety.get("no_real_bet") is True
        assert safety.get("paper_only") is True


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 10 — Gate and Markdown
# ════════════════════════════════════════════════════════════════════════════


class TestGateAndMarkdown:
    def test_23_gate_is_one_of_seven_valid(self):
        """determine_gate always returns a value in VALID_GATES."""
        assert len(VALID_GATES) == 7

        # Case 1: fixture source with moneyline → FIXTURE_READY
        health = probe_current_mlb_source("2026-05-07")
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        coverage = build_market_coverage(
            snapshots, source_name="fixture", source_mode=SOURCE_MODE_FIXTURE
        )
        gate1, _ = determine_gate(health, snapshots, coverage)
        assert gate1 in VALID_GATES

        # Case 2: no snapshots, no live API → NEEDS_LIVE_API
        coverage_empty = build_market_coverage(
            [], source_name="current", source_mode=SOURCE_MODE_CURRENT
        )
        gate2, _ = determine_gate(health, [], coverage_empty)
        assert gate2 in VALID_GATES

    def test_24_markdown_report_includes_no_profit_claim(self):
        """Probe markdown report contains no-profit-claim and no-real-bet markers."""
        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "probe_report.md")
            # Generate probe report via script-level generate function
            from scripts.run_mlb_current_source_probe import generate_markdown_report

            health = probe_current_mlb_source("2026-05-07")
            snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
            coverage = build_market_coverage(
                snapshots, source_name="fixture", source_mode=SOURCE_MODE_FIXTURE
            )
            gate, rationale = determine_gate(health, snapshots, coverage)

            payload = {
                "module_version": MODULE_VERSION,
                "run_timestamp_utc": "2026-05-07T00:00:00+00:00",
                "probe_date": "2026-05-07",
                "source_mode": SOURCE_MODE_FIXTURE,
                "fixture_source_used": True,
                "current_source_reachable": False,
                "model_prediction_available": False,
                "total_snapshots": len(snapshots),
                "source_health": {},
                "market_coverage": {
                    "moneyline_available": coverage.moneyline_available,
                    "source_name": coverage.source_name,
                    "source_mode": coverage.source_mode,
                },
                "snapshots": [],
                "validation_errors": [],
                "gate": gate,
                "gate_rationale": rationale,
                "safety": {
                    "no_real_bet": True,
                    "paper_only": True,
                    "no_profit_claim": True,
                    "no_edge_claim": True,
                },
                "completion_marker": COMPLETION_MARKER,
            }
            generate_markdown_report(payload, md_path)

            with open(md_path, encoding="utf-8") as fh:
                content = fh.read()

        assert "NO_PROFIT_CLAIM = True" in content, "Missing NO_PROFIT_CLAIM in markdown"
        assert "NO_REAL_BET = True" in content, "Missing NO_REAL_BET in markdown"
        assert "PAPER_ONLY = True" in content, "Missing PAPER_ONLY in markdown"


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 11 — Regression
# ════════════════════════════════════════════════════════════════════════════


class TestRegression:
    def test_25_phase67_72_metrics_daily_advisory_regression(self):
        """Phase67–72, metrics_ssot, mlb_daily_advisory, mlb_current_sources importable."""
        import orchestrator.phase67_context_failure_attribution as p67
        import orchestrator.phase68_model_architecture_ensemble_failure_audit as p68
        import orchestrator.phase69_calibration_objective_redesign_counterfactual as p69
        import orchestrator.phase70_strong_home_favorite_underconfidence_audit as p70
        import orchestrator.phase71_market_dominance_model_derisk_audit as p71
        import orchestrator.phase72_market_derisk_guard_proposal as p72
        import orchestrator.metrics_ssot as ssot
        import orchestrator.mlb_daily_advisory as adv
        import orchestrator.mlb_current_sources as src

        # Phase completion markers
        assert isinstance(p67.COMPLETION_MARKER, str) and "PHASE" in p67.COMPLETION_MARKER
        assert isinstance(p68.COMPLETION_MARKER, str) and "PHASE" in p68.COMPLETION_MARKER
        assert isinstance(p69.COMPLETION_MARKER, str) and "PHASE" in p69.COMPLETION_MARKER
        assert isinstance(p70.COMPLETION_MARKER, str) and "PHASE" in p70.COMPLETION_MARKER
        assert isinstance(p71.COMPLETION_MARKER, str) and "PHASE" in p71.COMPLETION_MARKER
        assert isinstance(p72.COMPLETION_MARKER, str) and "PHASE" in p72.COMPLETION_MARKER

        # Phase gates
        assert p69.CALIBRATION_OBJECTIVE_NOT_PROMISING == "CALIBRATION_OBJECTIVE_NOT_PROMISING"
        assert p70.MARKET_ONLY_SUPERIOR == "MARKET_ONLY_SUPERIOR"
        assert p71.MARKET_DE_RISK_GUARD_PROMISING == "MARKET_DE_RISK_GUARD_PROMISING"
        assert p72.PHASE71_GATE_ANCHOR == "MARKET_DE_RISK_GUARD_PROMISING"

        # Metrics SSOT
        assert ssot.METRICS_SSOT_FOUNDATION_READY == "METRICS_SSOT_FOUNDATION_READY"

        # Daily advisory module
        assert adv.COMPLETION_MARKER == "MLB_DAILY_ADVISORY_REPLAY_LEDGER_VERIFIED"
        assert len(adv.VALID_GATES) == 7

        # Current sources module
        assert src.COMPLETION_MARKER == "MLB_CURRENT_SOURCE_ADAPTER_VERIFIED"
        assert len(src.VALID_GATES) == 7

        # Safety constants not mutated
        assert src.NO_REAL_BET is True
        assert src.PRODUCTION_MODIFIED is False
        assert adv.PRODUCTION_MODIFIED is False
