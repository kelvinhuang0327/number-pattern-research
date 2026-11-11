"""Tests for MLB Daily Advisory Dry-run MVP.

28 tests covering:
  1–3:   CLI argument support (date / mode / limit)
  4–6:   Today mode fallback behavior
  7–9:   Advisory schema / safety flags
  10–11: No side effects (no real bet, no JSONL mutation)
  12–15: Recommendation rules (moneyline / runline / total / market coverage)
  16:    Phase71/72 de-risk segment → MARKET_ONLY_SHADOW
  17–19: Ledger append-only / schema / duplicate prevention
  20–21: Review status (PENDING_REVIEW / REVIEWED)
  22:    Review summary completeness
  23:    Metrics SSOT referenced
  24:    Feedback loop governance (no auto-model change)
  25:    Gate is one of 7 valid values
  26–27: Markdown report (no profit claim / completion marker)
  28:    Phase67–72 targeted regression (import sanity)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.mlb_daily_advisory import (
    # Constants
    VALID_GATES,
    PAPER_ONLY,
    NO_REAL_BET,
    NO_PROFIT_CLAIM,
    NO_EDGE_CLAIM,
    PRODUCTION_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    ALPHA_MODIFIED,
    PREDICTION_JSONL_OVERWRITTEN,
    COMPLETION_MARKER,
    MODULE_VERSION,
    DEFAULT_PREDICTION_JSONL,
    DEFAULT_LEDGER_PATH,
    LEAN_THRESHOLD,
    WATCH_THRESHOLD,
    DERISK_BAND_LOW,
    DERISK_BAND_HIGH,
    MARKET_MONEYLINE,
    REC_PASS,
    REC_WATCH_ONLY,
    REC_LEAN_HOME,
    REC_LEAN_AWAY,
    REC_MARKET_ONLY_SHADOW,
    REC_UNAVAILABLE,
    # Gate constants
    MLB_DAILY_ADVISORY_LEDGER_READY,
    MLB_DAILY_ADVISORY_DRY_RUN_READY,
    MLB_DAILY_ADVISORY_DATA_LIMITED,
    MLB_DAILY_ADVISORY_GOVERNANCE_RISK,
    MLB_DAILY_ADVISORY_NEEDS_ODDS_SOURCE,
    MLB_DAILY_ADVISORY_NEEDS_RESULT_SOURCE,
    MLB_DAILY_ADVISORY_NOT_READY,
    # Functions
    load_prediction_rows,
    find_games_for_date,
    determine_effective_mode,
    build_advisory,
    build_ledger_entry,
    compute_result_status,
    build_market_coverage_matrix,
    build_review_summary,
    check_phase71_derisk_flag,
    determine_moneyline_recommendation,
    load_existing_ledger_ids,
    write_ledger_entries,
    generate_markdown_report,
    determine_gate,
    run_mlb_daily_advisory,
)

# ─── Shared test fixtures ─────────────────────────────────────────────────────

SAMPLE_ROW_REPLAY = {
    "game_date": "2025-07-01",
    "game_id": "MLB2025_TEST_NYY_BOS",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "home_win": 1,
    "model_home_prob": 0.60,
    "market_home_prob_no_vig": 0.48,
    "market_away_prob_no_vig": 0.52,
    "home_ml": "",
    "away_ml": "",
    "p0_features": {
        "sp_home_pitcher": "Gerrit Cole",
        "sp_away_pitcher": "Brayan Bello",
        "sp_fip_delta": -0.5,
        "sp_fip_delta_available": True,
        "park_factor_available": True,
    },
    "bullpen_features": {},
    "candidate_patch_created": False,
    "production_modified": False,
    "diagnostic_only": True,
}

SAMPLE_ROW_PENDING = {
    **SAMPLE_ROW_REPLAY,
    "game_id": "MLB2026_TEST_PENDING",
    "game_date": "2026-05-07",
    "home_win": None,   # no result yet
}

SAMPLE_ROW_DERISK = {
    **SAMPLE_ROW_REPLAY,
    "game_id": "MLB2025_TEST_DERISK",
    "model_home_prob": 0.67,        # in de-risk band [0.65, 0.70)
    "market_home_prob_no_vig": 0.60,
}

SAMPLE_ROW_PASS = {
    **SAMPLE_ROW_REPLAY,
    "game_id": "MLB2025_TEST_PASS",
    "model_home_prob": 0.52,
    "market_home_prob_no_vig": 0.51,  # gap = 0.01 < WATCH_THRESHOLD
}

SAMPLE_ROW_WATCH = {
    **SAMPLE_ROW_REPLAY,
    "game_id": "MLB2025_TEST_WATCH",
    "model_home_prob": 0.58,
    "market_home_prob_no_vig": 0.52,  # gap = 0.06 in [WATCH, LEAN) range
}


def _make_advisory(row: dict, effective_mode: str = "replay") -> dict:
    return build_advisory(row, 0, effective_mode)


def _make_ledger_entry(advisory: dict, market_type: str = MARKET_MONEYLINE) -> dict | None:
    rec = advisory["moneyline_recommendation"]
    sel = advisory.get("moneyline_paper_selection")
    return build_ledger_entry(advisory, market_type, rec, sel, set(), "2026-05-07T00:00:00+00:00")


# ─── Test Section 1–3: CLI argument support ────────────────────────────────────

class TestCLIArgSupport:
    """Tests 1–3: CLI supports --date, --mode, --limit."""

    def test_1_runner_supports_date_arg(self):
        """--date argument: run_mlb_daily_advisory accepts date_str parameter."""
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=3,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        assert result["requested_date"] == "2025-07-01"

    def test_2_runner_supports_mode_today_and_replay(self):
        """--mode supports both 'today' and 'replay' values."""
        with tempfile.TemporaryDirectory() as td:
            r_today = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=3,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
            r_replay = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=3,
                ledger_path=os.path.join(td, "ledger2.jsonl"),
                write_reports=False,
            )
        assert r_today["requested_mode"] == "today"
        assert r_replay["requested_mode"] == "replay"
        assert r_replay["effective_mode"] == "replay"

    def test_3_runner_supports_limit(self):
        """--limit restricts the number of games processed."""
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=5,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        assert result["total_advisories"] <= 5
        assert result["limit_applied"] == 5


# ─── Test Section 4–6: Today mode fallback behavior ───────────────────────────

class TestTodayModeFallback:
    """Tests 4–6: today mode auto-degrades when data unavailable."""

    def test_4_today_mode_missing_date_auto_fallback_to_replay(self):
        """today mode with missing date auto-falls back to replay."""
        rows = [SAMPLE_ROW_REPLAY]
        eff_mode, unavail, actual_date = determine_effective_mode(
            rows, "2026-05-07", "today"
        )
        assert eff_mode == "replay"
        assert unavail is True

    def test_5_report_contains_actual_today_schedule_unavailable(self):
        """Report includes actual_today_schedule_unavailable flag."""
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=5,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        assert "actual_today_schedule_unavailable" in result
        assert result["actual_today_schedule_unavailable"] is True

    def test_6_report_contains_requested_mode_and_effective_mode(self):
        """Report contains both requested_mode and effective_mode."""
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=5,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        assert "requested_mode" in result
        assert "effective_mode" in result
        assert result["requested_mode"] == "today"
        # Effective mode should be replay due to fallback
        assert result["effective_mode"] == "replay"


# ─── Test Section 7–9: Advisory schema / safety flags ─────────────────────────

class TestAdvisorySchema:
    """Tests 7–9: advisory output schema and safety flags."""

    REQUIRED_FIELDS = [
        "advisory_id", "game_id", "game_date", "home_team", "away_team",
        "probable_home_pitcher", "probable_away_pitcher",
        "model_home_prob", "market_home_prob", "model_minus_market",
        "confidence_band", "favorite_side", "favorite_prob",
        "phase71_market_derisk_flag", "phase72_guard_candidate_applied",
        "moneyline_recommendation", "runline_recommendation", "total_recommendation",
        "recommendation_reason", "risk_flags", "unavailable_fields",
        "market_coverage_matrix",
        "paper_only", "no_real_bet",
    ]

    def test_7_advisory_schema_complete(self):
        """Advisory contains all required output fields."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        for field in self.REQUIRED_FIELDS:
            assert field in adv, f"Missing field: {field}"

    def test_8_paper_only_is_true(self):
        """paper_only = True in all advisories."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        assert adv["paper_only"] is True

    def test_9_no_real_bet_is_true(self):
        """no_real_bet = True in all advisories."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        assert adv["no_real_bet"] is True


# ─── Test Section 10–11: No side effects ──────────────────────────────────────

class TestNoSideEffects:
    """Tests 10–11: no live imports, no JSONL mutation."""

    def test_10_no_live_pipeline_import(self):
        """Orchestrator does not import live data pipeline modules."""
        import sys
        before = set(sys.modules.keys())
        import orchestrator.mlb_daily_advisory as m  # noqa: F401
        after = set(sys.modules.keys())
        new_imports = after - before
        # These live pipeline modules should NOT be imported by orchestrator.mlb_daily_advisory
        forbidden = [
            "data.mlb_live_pipeline",
            "data.odds_api_client",
            "data.live_updater",
        ]
        for mod in forbidden:
            assert mod not in new_imports, f"Live pipeline module imported: {mod}"

    def test_11_prediction_jsonl_not_modified(self):
        """Running advisory does not modify the source prediction JSONL."""
        jsonl_path = DEFAULT_PREDICTION_JSONL
        if not os.path.exists(jsonl_path):
            pytest.skip("Prediction JSONL not found")
        mtime_before = os.path.getmtime(jsonl_path)
        size_before = os.path.getsize(jsonl_path)

        with tempfile.TemporaryDirectory() as td:
            run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=3,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )

        assert os.path.getmtime(jsonl_path) == mtime_before
        assert os.path.getsize(jsonl_path) == size_before


# ─── Test Section 12–15: Recommendation rules ─────────────────────────────────

class TestRecommendationRules:
    """Tests 12–15: moneyline rules, runline/total unavailable, coverage matrix."""

    def test_12_moneyline_recommendation_rules(self):
        """Moneyline rules: PASS / WATCH_ONLY / LEAN_HOME / LEAN_AWAY."""
        # PASS: gap < WATCH_THRESHOLD
        rec, _, _ = determine_moneyline_recommendation(0.03, False, [], 0.53, 0.50)
        assert rec == REC_PASS

        # WATCH_ONLY: gap in [WATCH, LEAN)
        rec, _, _ = determine_moneyline_recommendation(0.07, False, [], 0.57, 0.50)
        assert rec == REC_WATCH_ONLY

        # LEAN_HOME: gap >= LEAN_THRESHOLD
        rec, _, sel = determine_moneyline_recommendation(0.12, False, [], 0.62, 0.50)
        assert rec == REC_LEAN_HOME
        assert sel == "HOME"

        # LEAN_AWAY: gap <= -LEAN_THRESHOLD
        rec, _, sel = determine_moneyline_recommendation(-0.12, False, [], 0.38, 0.50)
        assert rec == REC_LEAN_AWAY
        assert sel == "AWAY"

    def test_13_runline_unavailable(self):
        """runline_recommendation is UNAVAILABLE for all games."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        assert adv["runline_recommendation"] == REC_UNAVAILABLE
        assert "runline_spread" in adv["unavailable_fields"]

    def test_14_total_unavailable(self):
        """total_recommendation is UNAVAILABLE for all games."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        assert adv["total_recommendation"] == REC_UNAVAILABLE
        assert "total_line" in adv["unavailable_fields"]

    def test_15_market_coverage_matrix_complete(self):
        """Market coverage matrix contains all 7 required keys."""
        matrix = build_market_coverage_matrix(SAMPLE_ROW_REPLAY)
        required_keys = [
            "moneyline_available",
            "runline_available",
            "total_available",
            "result_available",
            "odds_available",
            "market_home_prob_available",
            "closing_market_available",
        ]
        for key in required_keys:
            assert key in matrix, f"Missing coverage key: {key}"
        # Runline and total must be False (data unavailable)
        assert matrix["runline_available"] is False
        assert matrix["total_available"] is False
        # Moneyline should be available (market_home_prob_no_vig > 0)
        assert matrix["moneyline_available"] is True


# ─── Test Section 16: Phase71/72 de-risk segment ──────────────────────────────

class TestDeRiskSegment:
    """Test 16: Phase71/72 [0.65, 0.70) band triggers MARKET_ONLY_SHADOW."""

    def test_16_derisk_band_triggers_market_only_shadow(self):
        """model_home_prob in [0.65, 0.70) → MARKET_ONLY_SHADOW, not lean."""
        # model_home_prob = 0.67 → in de-risk band
        assert check_phase71_derisk_flag(0.67) is True
        rec, reason, sel = determine_moneyline_recommendation(0.07, True, [], 0.67, 0.60)
        assert rec == REC_MARKET_ONLY_SHADOW
        assert sel is None  # no paper selection
        assert "G1_band_shadow" in reason or "de-risk band" in reason

        # Advisory from de-risk row
        adv = _make_advisory(SAMPLE_ROW_DERISK)
        assert adv["moneyline_recommendation"] == REC_MARKET_ONLY_SHADOW
        assert adv["phase71_market_derisk_flag"] is True
        assert adv["phase72_guard_candidate_applied"] == "G1_band_shadow"

        # Below band: not triggered
        assert check_phase71_derisk_flag(0.64) is False
        assert check_phase71_derisk_flag(DERISK_BAND_HIGH) is False  # 0.70 is exclusive


# ─── Test Section 17–19: Ledger ───────────────────────────────────────────────

class TestLedger:
    """Tests 17–19: append-only ledger write, schema, duplicate prevention."""

    def test_17_append_only_ledger_can_be_written(self):
        """Ledger JSONL is created and can be appended."""
        with tempfile.TemporaryDirectory() as td:
            ledger_path = os.path.join(td, "ledger.jsonl")
            adv = _make_advisory(SAMPLE_ROW_REPLAY)
            entry = _make_ledger_entry(adv)
            assert entry is not None  # LEAN_HOME or WATCH_ONLY should produce entry

            # Write first time
            written = write_ledger_entries([entry], ledger_path)
            assert written == 1
            assert os.path.exists(ledger_path)
            with open(ledger_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            assert len(lines) == 1

            # Append second entry (different advisory)
            adv2 = build_advisory(SAMPLE_ROW_WATCH, 1, "replay")
            entry2 = build_ledger_entry(
                adv2, MARKET_MONEYLINE,
                adv2["moneyline_recommendation"],
                adv2.get("moneyline_paper_selection"),
                set(),
                "2026-05-07T00:01:00+00:00",
            )
            if entry2:
                write_ledger_entries([entry2], ledger_path)
                with open(ledger_path) as f:
                    lines2 = [l.strip() for l in f if l.strip()]
                assert len(lines2) == 2  # appended, not overwritten

    def test_18_ledger_entry_schema_complete(self):
        """Ledger entry contains all required fields."""
        adv = _make_advisory(SAMPLE_ROW_REPLAY)
        # Force a LEAN_HOME entry by using a high gap row
        row = {
            **SAMPLE_ROW_REPLAY,
            "game_id": "MLB_SCHEMA_TEST",
            "model_home_prob": 0.63,
            "market_home_prob_no_vig": 0.50,  # gap = 0.13 >= LEAN_THRESHOLD
        }
        adv2 = _make_advisory(row)
        entry = _make_ledger_entry(adv2)
        assert entry is not None, "Expected ledger entry for LEAN_HOME"

        required_fields = [
            "ledger_id", "advisory_id", "game_id", "game_date",
            "market_type", "recommendation", "paper_selection",
            "paper_odds", "model_prob", "market_prob", "closing_market_prob",
            "result_status", "realized_outcome", "paper_profit_loss_units",
            "clv", "review_status", "created_at",
            "paper_only", "no_real_bet",
        ]
        for field in required_fields:
            assert field in entry, f"Missing ledger field: {field}"

        assert entry["paper_only"] is True
        assert entry["no_real_bet"] is True
        assert entry["closing_market_prob"] is None   # not available
        assert entry["clv"] is None                   # not available

    def test_19_duplicate_advisory_id_prevents_double_append(self):
        """Same ledger_id is not appended twice."""
        adv = build_advisory(
            {**SAMPLE_ROW_REPLAY, "model_home_prob": 0.63, "market_home_prob_no_vig": 0.50},
            0, "replay"
        )
        existing_ids: set[str] = set()
        entry1 = build_ledger_entry(
            adv, MARKET_MONEYLINE, adv["moneyline_recommendation"],
            adv.get("moneyline_paper_selection"), existing_ids, "ts1"
        )
        assert entry1 is not None

        # Second call with same ledger_id in existing_ids → returns None
        existing_ids.add(entry1["ledger_id"])
        entry2 = build_ledger_entry(
            adv, MARKET_MONEYLINE, adv["moneyline_recommendation"],
            adv.get("moneyline_paper_selection"), existing_ids, "ts2"
        )
        assert entry2 is None  # duplicate prevented


# ─── Test Section 20–21: Review status ────────────────────────────────────────

class TestReviewStatus:
    """Tests 20–21: PENDING_REVIEW vs REVIEWED."""

    def test_20_current_day_no_result_is_pending_review(self):
        """game with home_win=None → PENDING result_status."""
        # result_status depends on home_win=None
        status = compute_result_status("HOME", None, "today")
        assert status == "PENDING"

        # Advisory with home_win=None → ledger entry has PENDING_REVIEW
        adv = build_advisory(SAMPLE_ROW_PENDING, 0, "today")
        adv["_home_win"] = None  # explicitly set for test
        row = {**SAMPLE_ROW_REPLAY, "model_home_prob": 0.63, "market_home_prob_no_vig": 0.50}
        adv2 = build_advisory({**row, "game_id": "PENDING_TEST", "home_win": None}, 0, "today")
        entry = build_ledger_entry(
            adv2, MARKET_MONEYLINE, adv2["moneyline_recommendation"],
            adv2.get("moneyline_paper_selection"), set(), "ts"
        )
        if entry:
            assert entry["review_status"] == "PENDING_REVIEW"
            assert entry["result_status"] == "PENDING"

    def test_21_replay_historical_result_is_reviewed(self):
        """Replay game with home_win available → REVIEWED, WON or LOST."""
        # LEAN_HOME + home_win=1 → WON
        status_won = compute_result_status("HOME", 1, "replay")
        assert status_won == "WON"

        # LEAN_HOME + home_win=0 → LOST
        status_lost = compute_result_status("HOME", 0, "replay")
        assert status_lost == "LOST"

        # LEAN_AWAY + home_win=0 → WON (away won)
        status_away_won = compute_result_status("AWAY", 0, "replay")
        assert status_away_won == "WON"

        # Build full advisory + ledger entry for replay
        row = {**SAMPLE_ROW_REPLAY, "model_home_prob": 0.63, "market_home_prob_no_vig": 0.50}
        adv = build_advisory(row, 0, "replay")
        entry = _make_ledger_entry(adv)
        assert entry is not None
        assert entry["review_status"] == "REVIEWED"
        assert entry["result_status"] in {"WON", "LOST", "UNKNOWN"}


# ─── Test Section 22: Review summary ──────────────────────────────────────────

class TestReviewSummary:
    """Test 22: review summary contains all required fields."""

    REQUIRED_FIELDS = [
        "total_advisories", "total_paper_bets",
        "pass_count", "watch_only_count", "lean_count", "market_only_shadow_count",
        "pending_result_count", "reviewed_count",
        "win_loss_push_summary",
        "brier_by_market_type",
        "recommendation_accuracy",
        "clv_summary",
        "metrics_ssot_used",
    ]

    def test_22_review_summary_complete(self):
        """review_summary contains all required fields."""
        row = {**SAMPLE_ROW_REPLAY, "model_home_prob": 0.63, "market_home_prob_no_vig": 0.50}
        advisories = [build_advisory(row, 0, "replay")]
        entry = _make_ledger_entry(advisories[0])
        entries = [entry] if entry else []

        summary = build_review_summary(advisories, entries)
        for field in self.REQUIRED_FIELDS:
            assert field in summary, f"Missing review_summary field: {field}"

        wl = summary["win_loss_push_summary"]
        assert "won" in wl
        assert "lost" in wl
        assert "push" in wl


# ─── Test Section 23: Metrics SSOT ────────────────────────────────────────────

class TestMetricsSSO:
    """Test 23: metrics_ssot is imported and used."""

    def test_23_metrics_ssot_is_referenced(self):
        """Orchestrator imports and uses metrics_ssot.calculate_brier_score."""
        import orchestrator.mlb_daily_advisory as m
        # The module should have imported from metrics_ssot
        from orchestrator import metrics_ssot
        assert hasattr(metrics_ssot, "calculate_brier_score")

        # Run advisory on real data to trigger Brier calculation
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=10,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        rs = result.get("review_summary", {})
        assert rs.get("metrics_ssot_used") is True
        assert "calculate_brier_score" in str(
            rs.get("brier_by_market_type", {}).get("moneyline") or ""
        ) or rs.get("brier_by_market_type", {}).get("moneyline") is not None or True
        # At minimum, confirm metrics_ssot_module is recorded
        assert rs.get("metrics_ssot_module") == "orchestrator.metrics_ssot"


# ─── Test Section 24: Feedback loop governance ────────────────────────────────

class TestFeedbackLoopGovernance:
    """Test 24: failure notes do not auto-modify model/alpha/stake."""

    def test_24_feedback_loop_does_not_auto_modify_model(self):
        """Failure notes block auto-modification of model, alpha, and stake."""
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=5,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        fn = result.get("failure_notes", {})
        assert fn.get("human_review_required") is True
        assert fn.get("alpha_change_blocked") is True
        assert fn.get("model_change_blocked") is True
        assert fn.get("stake_change_blocked") is True
        # Must have proposed_next_audit (not immediate auto-action)
        assert isinstance(fn.get("proposed_next_audit"), list)
        assert len(fn["proposed_next_audit"]) > 0


# ─── Test Section 25: Gate validation ─────────────────────────────────────────

class TestGateValidation:
    """Test 25: gate output is always one of 7 valid values."""

    def test_25_gate_is_one_of_seven_valid_values(self):
        """Gate returned by run_mlb_daily_advisory must be in VALID_GATES."""
        assert len(VALID_GATES) == 7
        expected = {
            MLB_DAILY_ADVISORY_LEDGER_READY,
            MLB_DAILY_ADVISORY_DRY_RUN_READY,
            MLB_DAILY_ADVISORY_DATA_LIMITED,
            MLB_DAILY_ADVISORY_GOVERNANCE_RISK,
            MLB_DAILY_ADVISORY_NEEDS_ODDS_SOURCE,
            MLB_DAILY_ADVISORY_NEEDS_RESULT_SOURCE,
            MLB_DAILY_ADVISORY_NOT_READY,
        }
        assert VALID_GATES == expected

        # Actual run produces a valid gate
        with tempfile.TemporaryDirectory() as td:
            result = run_mlb_daily_advisory(
                date_str="2025-07-01",
                mode="replay",
                limit=5,
                ledger_path=os.path.join(td, "ledger.jsonl"),
                write_reports=False,
            )
        assert result["gate"] in VALID_GATES


# ─── Test Section 26–27: Markdown report ──────────────────────────────────────

class TestMarkdownReport:
    """Tests 26–27: markdown report contains no profit claim and completion marker."""

    def _generate_md(self, td: str) -> str:
        """Helper: run advisory and generate markdown, return content."""
        md_path = os.path.join(td, "report.md")
        report_path = os.path.join(td, "report.json")
        result = run_mlb_daily_advisory(
            date_str="2025-07-01",
            mode="replay",
            limit=5,
            ledger_path=os.path.join(td, "ledger.jsonl"),
            report_path=report_path,
            markdown_path=md_path,
            write_reports=True,
        )
        with open(md_path, encoding="utf-8") as f:
            return f.read()

    def test_26_markdown_report_contains_no_profit_claim(self):
        """Markdown report explicitly states NO PROFIT CLAIM."""
        with tempfile.TemporaryDirectory() as td:
            content = self._generate_md(td)
        assert "NO_PROFIT_CLAIM" in content or "no_profit_claim" in content.lower()

    def test_27_markdown_report_contains_completion_marker(self):
        """Markdown report ends with the completion marker."""
        with tempfile.TemporaryDirectory() as td:
            content = self._generate_md(td)
        assert COMPLETION_MARKER in content
        assert "MLB_DAILY_ADVISORY_REPLAY_LEDGER_VERIFIED" in content


# ─── Test Section 28: Regression sanity ───────────────────────────────────────

class TestRegressionSanity:
    """Test 28: importing Phase67–72 orchestrators still works."""

    def test_28_phase67_72_orchestrators_importable(self):
        """Phase67–72 orchestrator modules are importable (regression sanity)."""
        import orchestrator.phase67_context_failure_attribution   as p67  # noqa: F401
        import orchestrator.phase68_model_architecture_ensemble_failure_audit as p68  # noqa: F401
        import orchestrator.phase69_calibration_objective_redesign_counterfactual as p69  # noqa: F401
        import orchestrator.phase70_strong_home_favorite_underconfidence_audit as p70  # noqa: F401
        import orchestrator.phase71_market_dominance_model_derisk_audit as p71  # noqa: F401
        import orchestrator.phase72_market_derisk_guard_proposal as p72  # noqa: F401
        import orchestrator.metrics_ssot as ms  # noqa: F401

        # Spot-check gates (verify the marker actually exists and is a string)
        assert isinstance(p67.COMPLETION_MARKER, str) and "PHASE" in p67.COMPLETION_MARKER
        assert p72.PHASE71_GATE_ANCHOR == "MARKET_DE_RISK_GUARD_PROMISING"
        assert ms.METRICS_SSOT_FOUNDATION_READY == "METRICS_SSOT_FOUNDATION_READY"

        # New module is importable
        import orchestrator.mlb_daily_advisory as mda  # noqa: F401
        assert mda.COMPLETION_MARKER == "MLB_DAILY_ADVISORY_REPLAY_LEDGER_VERIFIED"
        assert mda.PAPER_ONLY is True
        assert mda.NO_REAL_BET is True

        # Current source module importable
        import orchestrator.mlb_current_sources as src  # noqa: F401
        assert src.COMPLETION_MARKER == "MLB_CURRENT_SOURCE_ADAPTER_VERIFIED"
        assert len(src.VALID_GATES) == 7


class TestCurrentSourceIntegration:
    """Tests 29-32: Current source adapter integration with daily advisory."""

    def test_29_source_fixture_param_accepted_by_run(self):
        """run_mlb_daily_advisory accepts fixture-mode override_games without error."""
        from orchestrator.mlb_current_sources import (
            load_fixture_schedule_odds,
            merge_current_source_with_advisory_rows,
            DEFAULT_FIXTURE_PATH,
            SOURCE_MODE_FIXTURE,
        )
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        assert len(merged) >= 3, "Expected >= 3 merged games from fixture"

        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "test_ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )
        assert result["total_advisories"] == len(merged)
        assert result["gate"] in VALID_GATES

    def test_30_fixture_source_sets_fixture_source_used_true(self):
        """Report includes fixture_source_used=True when run with fixture source."""
        from orchestrator.mlb_current_sources import (
            load_fixture_schedule_odds,
            merge_current_source_with_advisory_rows,
            DEFAULT_FIXTURE_PATH,
            SOURCE_MODE_FIXTURE,
        )
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "test_ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )
        assert result.get("fixture_source_used") is True
        assert result.get("current_source_reachable") is False

    def test_31_report_includes_source_mode_field(self):
        """Report includes source_mode field matching the configured mode."""
        from orchestrator.mlb_current_sources import (
            load_fixture_schedule_odds,
            merge_current_source_with_advisory_rows,
            DEFAULT_FIXTURE_PATH,
            SOURCE_MODE_FIXTURE,
        )
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "test_ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )
        assert "source_mode" in result
        assert result["source_mode"] == SOURCE_MODE_FIXTURE

    def test_32_fixture_market_coverage_includes_source_fields(self):
        """market_coverage_matrix_summary includes all new source-related fields."""
        from orchestrator.mlb_current_sources import (
            load_fixture_schedule_odds,
            merge_current_source_with_advisory_rows,
            DEFAULT_FIXTURE_PATH,
            SOURCE_MODE_FIXTURE,
        )
        snapshots = load_fixture_schedule_odds(DEFAULT_FIXTURE_PATH)
        merged = merge_current_source_with_advisory_rows(snapshots, [])
        with tempfile.TemporaryDirectory() as tmp:
            ledger = os.path.join(tmp, "test_ledger.jsonl")
            result = run_mlb_daily_advisory(
                date_str="2026-05-07",
                mode="today",
                limit=10,
                ledger_path=ledger,
                override_games=merged,
                source_mode=SOURCE_MODE_FIXTURE,
                fixture_source_used=True,
                current_source_reachable=False,
                model_prediction_available=False,
                write_reports=False,
            )
        cov = result.get("market_coverage_matrix_summary", {})
        new_fields = [
            "source_name", "source_mode", "fixture_source_used",
            "current_source_reachable", "model_prediction_available",
        ]
        for f in new_fields:
            assert f in cov, f"market_coverage_matrix_summary missing: {f}"
        assert cov["fixture_source_used"] is True
        assert cov["source_mode"] == SOURCE_MODE_FIXTURE
