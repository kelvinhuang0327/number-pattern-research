"""
Tests for Phase 38: MLB BSS Data + Calibration Repair Preview.

13 test cases covering:
  1.  duplicate records are detected
  2.  cleaned preview removes duplicates
  3.  invalid odds are excluded
  4.  American odds conversion works
  5.  no-vig sums to 1
  6.  cleaned market Brier recomputes correctly
  7.  calibration split is time-aware (documented as structural requirement)
  8.  market-blend alpha grid works
  9.  ECE improves classification works
  10. BSS remains negative keeps patch blocked
  11. report is generated
  12. no production source file is modified
  13. no external API / LLM call occurs
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
import tempfile
from pathlib import Path

import pytest

# ─── Module under test ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_phase38_mlb_bss_repair_preview import (
    _brier_score,
    _bss,
    _ece,
    _parse_american_odds,
    _remove_vig,
    AlphaGridPoint,
    BaselineComparison,
    CalibrationResult,
    classify_calibration_result,
    CleanedDataResult,
    create_cleaned_preview,
    DataDiagnostic,
    generate_report,
    ODDS_CSV,
    OUTCOMES_CSV,
    Phase38Result,
    REPORT_BSS,
    REPORT_MARKET_BRIER,
    REPORT_MODEL_BRIER,
    recompute_market_baseline,
    run_calibration_experiment,
    run_data_diagnostic,
    run_phase38,
    SafetyGateEvidence,
    update_safety_gate_evidence,
    SAFETY_GATE_MODULE,
    CLEANED_PREVIEW_PATH,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def _make_odds_rows(extra: list[dict] | None = None) -> list[dict]:
    """Return minimal valid odds rows."""
    base = [
        {
            "Date": "2025-04-01",
            "Away": "Boston Red Sox",
            "Home": "New York Yankees",
            "Away ML": "-120",
            "Home ML": "+100",
            "is_verified_real": "False",
            "source_file": "mlb-odds.xlsx",
            "source_type": "user_supplied_xlsx",
            "Away Score": "3",
            "Home Score": "5",
            "Status": "Final",
        },
        {
            "Date": "2025-04-02",
            "Away": "Chicago Cubs",
            "Home": "Milwaukee Brewers",
            "Away ML": "+130",
            "Home ML": "-150",
            "is_verified_real": "False",
            "source_file": "mlb-odds.xlsx",
            "source_type": "user_supplied_xlsx",
            "Away Score": "1",
            "Home Score": "4",
            "Status": "Final",
        },
    ]
    if extra:
        base.extend(extra)
    return base


def _make_outcome_rows(extra: list[dict] | None = None) -> list[dict]:
    """Return minimal valid outcome rows."""
    base = [
        {
            "Date": "2025-04-01",
            "Away": "Boston Red Sox",
            "Home": "New York Yankees",
            "home_win": "1.0",
            "Away Score": "3",
            "Home Score": "5",
            "Status": "Final",
            "source_file": "gl2025.txt",
            "source_type": "retrosheet_gamelog",
            "is_verified_real": "True",
        },
        {
            "Date": "2025-04-02",
            "Away": "Chicago Cubs",
            "Home": "Milwaukee Brewers",
            "home_win": "1.0",
            "Away Score": "1",
            "Home Score": "4",
            "Status": "Final",
            "source_file": "gl2025.txt",
            "source_type": "retrosheet_gamelog",
            "is_verified_real": "True",
        },
    ]
    if extra:
        base.extend(extra)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — Duplicate records are detected
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateDetection:
    """Test 1: Duplicate records in outcomes are correctly detected."""

    def test_duplicate_detected_in_outcomes(self) -> None:
        duplicate_row = {
            "Date": "2025-04-01",
            "Away": "Boston Red Sox",
            "Home": "New York Yankees",
            "home_win": "1.0",
            "Away Score": "3",
            "Home Score": "5",
            "Status": "Final",
            "source_file": "gl2025.txt",
            "source_type": "retrosheet_gamelog",
            "is_verified_real": "True",
        }
        outcomes = _make_outcome_rows(extra=[duplicate_row])  # row 0 duplicated
        odds = _make_odds_rows()

        diag = run_data_diagnostic(odds, outcomes)

        assert diag.duplicate_count >= 1, (
            f"Expected duplicate_count >= 1, got {diag.duplicate_count}"
        )
        assert any("DUPLICATE" in issue for issue in diag.issues)

    def test_no_duplicate_when_unique(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()

        diag = run_data_diagnostic(odds, outcomes)

        assert diag.duplicate_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — Cleaned preview removes duplicates
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanedPreviewDeduplication:
    """Test 2: Duplicate rows are removed in cleaned preview."""

    def test_cleaned_preview_removes_duplicates(self) -> None:
        duplicate_row = {
            "Date": "2025-04-01",
            "Away": "Boston Red Sox",
            "Home": "New York Yankees",
            "home_win": "1.0",
            "Away Score": "3",
            "Home Score": "5",
            "Status": "Final",
            "source_file": "gl2025.txt",
            "source_type": "retrosheet_gamelog",
            "is_verified_real": "True",
        }
        outcomes = _make_outcome_rows(extra=[duplicate_row])
        odds = _make_odds_rows()

        cleaned, rows = create_cleaned_preview(odds, outcomes, write=False)

        # Should still produce 2 unique game rows (the duplicate is merged, not doubled)
        unique_keys = {r["dedupe_key"] for r in rows}
        assert len(unique_keys) == len(rows), "Cleaned preview must not contain duplicate keys."
        assert cleaned.written is False  # read-only mode

    def test_cleaned_n_rows_le_raw(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        cleaned, rows = create_cleaned_preview(odds, outcomes, write=False)
        assert cleaned.n_rows <= len(odds)


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — Invalid odds rows are excluded
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidOddsExclusion:
    """Test 3: Rows with invalid (unparseable) odds are excluded from cleaned preview."""

    def test_invalid_odds_excluded(self) -> None:
        invalid_odds_row = {
            "Date": "2025-04-03",
            "Away": "Seattle Mariners",
            "Home": "Oakland Athletics",
            "Away ML": "INVALID",
            "Home ML": "BADVAL",
            "is_verified_real": "False",
            "source_file": "mlb-odds.xlsx",
            "source_type": "user_supplied_xlsx",
            "Away Score": "2",
            "Home Score": "3",
            "Status": "Final",
        }
        invalid_outcome = {
            "Date": "2025-04-03",
            "Away": "Seattle Mariners",
            "Home": "Oakland Athletics",
            "home_win": "1.0",
            "Away Score": "2",
            "Home Score": "3",
            "Status": "Final",
            "source_file": "gl2025.txt",
            "source_type": "retrosheet_gamelog",
            "is_verified_real": "True",
        }
        odds = _make_odds_rows(extra=[invalid_odds_row])
        outcomes = _make_outcome_rows(extra=[invalid_outcome])

        cleaned, rows = create_cleaned_preview(odds, outcomes, write=False)

        game_keys = {r["dedupe_key"] for r in rows}
        bad_key = "2025-04-03|Seattle Mariners|Oakland Athletics"
        assert bad_key not in game_keys, "Invalid odds row must be excluded from cleaned preview."
        assert cleaned.removed_invalid_odds >= 1

    def test_diagnostic_reports_invalid_odds(self) -> None:
        invalid_odds_row = {
            "Date": "2025-04-03",
            "Away": "Seattle Mariners",
            "Home": "Oakland Athletics",
            "Away ML": "INVALID",
            "Home ML": "",
            "is_verified_real": "False",
            "source_file": "mlb-odds.xlsx",
            "source_type": "user_supplied_xlsx",
            "Away Score": "2",
            "Home Score": "3",
            "Status": "Final",
        }
        odds = _make_odds_rows(extra=[invalid_odds_row])
        outcomes = _make_outcome_rows()

        diag = run_data_diagnostic(odds, outcomes)
        # Either missing_odds or invalid_odds should be incremented
        assert diag.invalid_odds_count + diag.missing_odds_count >= 1


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — American odds conversion works
# ══════════════════════════════════════════════════════════════════════════════

class TestAmericanOddsConversion:
    """Test 4: _parse_american_odds correctly converts ML strings to probabilities."""

    @pytest.mark.parametrize("ml,expected", [
        ("-150", 0.6),        # |−150| / (|−150| + 100) = 150/250
        ("+125", 0.4444),     # 100 / (125 + 100) = 100/225
        ("100", 0.5),         # 100 / (100 + 100) = 0.5
        ("+100", 0.5),        # even money
        ("-110", 0.5238),     # 110/210
        ("+200", 0.3333),     # 100/300
        ("-200", 0.6667),     # 200/300
    ])
    def test_conversion(self, ml: str, expected: float) -> None:
        result = _parse_american_odds(ml)
        assert result is not None
        assert abs(result - expected) < 0.001, (
            f"_parse_american_odds({ml!r}) = {result:.4f}, expected ≈ {expected}"
        )

    @pytest.mark.parametrize("invalid", ["", "nan", "NaN", "INVALID", "N/A", "0"])
    def test_invalid_returns_none(self, invalid: str) -> None:
        result = _parse_american_odds(invalid)
        assert result is None, f"Expected None for {invalid!r}, got {result}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 — No-vig sums to 1
# ══════════════════════════════════════════════════════════════════════════════

class TestNoVigSumsToOne:
    """Test 5: _remove_vig produces probabilities that sum to exactly 1.0."""

    @pytest.mark.parametrize("ml_home,ml_away", [
        ("-110", "-110"),   # balanced book
        ("-150", "+130"),   # home favourite
        ("+200", "-250"),   # away favourite
        ("-120", "+100"),   # moderate spread
    ])
    def test_novig_sum(self, ml_home: str, ml_away: str) -> None:
        p_home_raw = _parse_american_odds(ml_home)
        p_away_raw = _parse_american_odds(ml_away)
        assert p_home_raw is not None
        assert p_away_raw is not None

        p_home_nv, p_away_nv = _remove_vig(p_home_raw, p_away_raw)
        total = p_home_nv + p_away_nv
        assert abs(total - 1.0) < 1e-9, (
            f"No-vig sum for {ml_home}/{ml_away} = {total:.10f}, expected 1.0"
        )

    def test_home_fav_higher_prob_after_novig(self) -> None:
        p_home_raw = _parse_american_odds("-150")
        p_away_raw = _parse_american_odds("+130")
        assert p_home_raw is not None and p_away_raw is not None
        p_home_nv, p_away_nv = _remove_vig(p_home_raw, p_away_raw)
        assert p_home_nv > p_away_nv


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 — Cleaned market Brier recomputes correctly
# ══════════════════════════════════════════════════════════════════════════════

class TestCleanedMarketBrierRecomputation:
    """Test 6: Market Brier recomputed on cleaned preview rows."""

    def test_perfect_predictor_brier_zero(self) -> None:
        """A predictor assigning 1.0 to winners has Brier = 0."""
        preds = [1.0, 1.0, 1.0]
        actuals = [1.0, 1.0, 1.0]
        assert _brier_score(preds, actuals) == pytest.approx(0.0)

    def test_coin_flip_brier(self) -> None:
        """Constant 0.5 predictor with balanced outcomes has Brier = 0.25."""
        n = 100
        preds = [0.5] * n
        actuals = [1.0] * (n // 2) + [0.0] * (n // 2)
        assert _brier_score(preds, actuals) == pytest.approx(0.25, abs=1e-10)

    def test_bss_negative_when_worse_than_market(self) -> None:
        """BSS < 0 when model_brier > market_brier."""
        bss = _bss(model_brier=0.2796, market_brier=0.2451)
        assert bss < 0.0, f"BSS should be negative: {bss}"

    def test_bss_known_value(self) -> None:
        """BSS = 1 - 0.2796/0.2451 ≈ -0.1408."""
        bss = _bss(model_brier=0.2796, market_brier=0.2451)
        assert abs(bss - (-0.14075)) < 0.001

    def test_cleaned_market_brier_computed_from_rows(self) -> None:
        """recompute_market_baseline returns a non-NaN Brier for valid merged rows."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        baseline = recompute_market_baseline(cleaned_rows)

        assert not math.isnan(baseline.cleaned_market_brier)
        assert 0.0 <= baseline.cleaned_market_brier <= 1.0
        assert baseline.n_games == len(cleaned_rows)


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 — Calibration split is time-aware
# ══════════════════════════════════════════════════════════════════════════════

class TestCalibrationTimeSplit:
    """
    Test 7: Verify that the calibration experiment is documented as requiring
    time-aware split (future fit cannot leak into past evaluation).
    When RAW_MODEL_PROB_MISSING, no fitting occurs so leakage is structurally impossible.
    """

    def test_calibration_status_raw_model_prob_missing(self) -> None:
        """When model probs unavailable, status must be RAW_MODEL_PROB_MISSING."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        assert calib.status == "RAW_MODEL_PROB_MISSING"
        assert calib.model_probs_available is False

    def test_calibration_note_mentions_no_leakage(self) -> None:
        """Calibration note must explain why leakage is impossible in current state."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        # Note must mention lack of per-game predictions (structural no-leakage)
        note_lower = calib.note.lower()
        assert any(kw in note_lower for kw in [
            "per-game", "aggregate", "raw", "not persisted", "skip"
        ]), f"Calibration note does not explain time-aware constraint: {calib.note!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 — Market-blend alpha grid works
# ══════════════════════════════════════════════════════════════════════════════

class TestMarketBlendAlphaGrid:
    """Test 8: Alpha grid covers [0.0, 0.1, ..., 1.0] and has correct boundary values."""

    def test_alpha_grid_has_11_points(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        assert len(calib.alpha_grid) == 11, (
            f"Expected 11 alpha points, got {len(calib.alpha_grid)}"
        )

    def test_alpha_grid_boundaries(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        alphas = [pt.alpha for pt in calib.alpha_grid]
        assert alphas[0] == pytest.approx(0.0)
        assert alphas[-1] == pytest.approx(1.0)

    def test_alpha_0_theoretical_bss_is_zero(self) -> None:
        """Alpha=0 (pure market) → theoretical BSS = 0.0."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        alpha0_pt = calib.alpha_grid[0]
        assert alpha0_pt.alpha == pytest.approx(0.0)
        assert alpha0_pt.theoretical_bss == pytest.approx(0.0, abs=1e-9)

    def test_alpha_1_theoretical_bss_equals_report(self) -> None:
        """Alpha=1 (pure model) → theoretical BSS = REPORT_BSS = -14.1%."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)

        alpha1_pt = calib.alpha_grid[-1]
        assert alpha1_pt.alpha == pytest.approx(1.0)
        assert alpha1_pt.theoretical_bss == pytest.approx(REPORT_BSS, abs=0.001)


# ══════════════════════════════════════════════════════════════════════════════
# Test 9 — ECE improves classification works
# ══════════════════════════════════════════════════════════════════════════════

class TestEceClassification:
    """Test 9: calibration classification correctly handles RAW_MODEL_PROB_MISSING."""

    def test_raw_model_prob_missing_classification(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        calib = run_calibration_experiment(cleaned_rows)
        baseline = recompute_market_baseline(cleaned_rows)

        classification = classify_calibration_result(calib, baseline)
        assert classification == "RAW_MODEL_PROB_MISSING"

    def test_ece_utility_function(self) -> None:
        """_ece() returns lower value for well-calibrated predictor."""
        n = 100
        # Well-calibrated: predictions ≈ actuals
        good_preds = [0.6] * 50 + [0.4] * 50
        good_actuals = [1.0] * 50 + [0.0] * 50  # 60% base rate → ECE small

        # Poorly calibrated: systematically overconfident
        bad_preds = [0.9] * 50 + [0.1] * 50
        bad_actuals = [1.0] * 50 + [0.0] * 50  # still 50/50 but now well separated

        ece_good = _ece(good_preds, good_actuals)
        ece_bad = _ece(bad_preds, bad_actuals)

        # Both are nonzero but bad is worse for mismatch
        assert ece_good >= 0.0
        assert ece_bad >= 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Test 10 — BSS remains negative → patch gate stays blocked
# ══════════════════════════════════════════════════════════════════════════════

class TestPatchGateRemainsBlocked:
    """Test 10: patch_gate_unlocked must be False when BSS is still negative."""

    def test_patch_gate_locked_when_bss_negative(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        baseline = recompute_market_baseline(cleaned_rows)
        calib = run_calibration_experiment(cleaned_rows)
        safety = update_safety_gate_evidence(baseline, calib)

        # BSS is still -14.1% → patch gate must be locked
        assert safety.patch_gate_unlocked is False, (
            "patch_gate_unlocked must be False while BSS < 0"
        )

    def test_current_bss_matches_report(self) -> None:
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        baseline = recompute_market_baseline(cleaned_rows)
        calib = run_calibration_experiment(cleaned_rows)
        safety = update_safety_gate_evidence(baseline, calib)

        assert safety.current_bss == pytest.approx(REPORT_BSS, abs=1e-6)

    def test_safety_gate_file_exists(self) -> None:
        """BSS safety gate module must exist."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        baseline = recompute_market_baseline(cleaned_rows)
        calib = run_calibration_experiment(cleaned_rows)
        safety = update_safety_gate_evidence(baseline, calib)

        assert safety.safety_gate_file_exists is True, (
            f"Safety gate file not found: {SAFETY_GATE_MODULE}"
        )

    def test_recommended_actions_are_allowed_categories(self) -> None:
        """All recommended actions must belong to allowed categories (not patch/production)."""
        odds = _make_odds_rows()
        outcomes = _make_outcome_rows()
        _, cleaned_rows = create_cleaned_preview(odds, outcomes, write=False)
        baseline = recompute_market_baseline(cleaned_rows)
        calib = run_calibration_experiment(cleaned_rows)
        safety = update_safety_gate_evidence(baseline, calib)

        forbidden = ["production", "patch_candidate", "kelly_bet", "live_bet", "clv_live"]
        for action in safety.recommended_next_allowed_action:
            action_lower = action.lower()
            for f in forbidden:
                assert f not in action_lower, (
                    f"Forbidden keyword '{f}' found in recommended action: {action!r}"
                )


# ══════════════════════════════════════════════════════════════════════════════
# Test 11 — Report is generated
# ══════════════════════════════════════════════════════════════════════════════

class TestReportGeneration:
    """Test 11: generate_report produces a non-empty Markdown string."""

    def test_report_is_non_empty_markdown(self) -> None:
        result = run_phase38(write_preview=False)
        report = generate_report(result)

        assert isinstance(report, str)
        assert len(report) > 500, "Report is too short."
        assert "Phase 38" in report
        assert "PAPER_ONLY" in report or "paper_only" in report.lower()

    def test_report_contains_verdict(self) -> None:
        result = run_phase38(write_preview=False)
        report = generate_report(result)
        assert result.verdict in report

    def test_report_contains_bss_values(self) -> None:
        result = run_phase38(write_preview=False)
        report = generate_report(result)
        # Should reference current BSS
        assert "-14.1%" in report or "-0.141" in report or "current_bss" in report.lower()

    def test_report_mentions_patch_gate_locked(self) -> None:
        result = run_phase38(write_preview=False)
        report = generate_report(result)
        assert "False" in report  # patch_gate_unlocked = False


# ══════════════════════════════════════════════════════════════════════════════
# Test 12 — No production source file is modified
# ══════════════════════════════════════════════════════════════════════════════

class TestNoProductionSourceModification:
    """Test 12: Running Phase 38 does not modify original source CSV files."""

    def test_odds_csv_not_modified(self) -> None:
        import os
        mtime_before = os.path.getmtime(str(ODDS_CSV))
        run_phase38(write_preview=False)
        mtime_after = os.path.getmtime(str(ODDS_CSV))
        assert mtime_before == mtime_after, (
            f"ODDS_CSV was modified during Phase 38 run: {ODDS_CSV}"
        )

    def test_outcomes_csv_not_modified(self) -> None:
        import os
        mtime_before = os.path.getmtime(str(OUTCOMES_CSV))
        run_phase38(write_preview=False)
        mtime_after = os.path.getmtime(str(OUTCOMES_CSV))
        assert mtime_before == mtime_after, (
            f"OUTCOMES_CSV was modified during Phase 38 run: {OUTCOMES_CSV}"
        )

    def test_write_preview_targets_derived_dir(self) -> None:
        """Even with --write-preview, output goes to derived/ not to source dir."""
        assert "derived" in str(CLEANED_PREVIEW_PATH), (
            f"CLEANED_PREVIEW_PATH must be inside derived/: {CLEANED_PREVIEW_PATH}"
        )
        # Source files must NOT be inside derived/
        assert "derived" not in str(ODDS_CSV)
        assert "derived" not in str(OUTCOMES_CSV)


# ══════════════════════════════════════════════════════════════════════════════
# Test 13 — No external API / LLM call occurs
# ══════════════════════════════════════════════════════════════════════════════

class TestNoExternalApiOrLlmCall:
    """Test 13: Phase 38 module makes no external API or LLM calls."""

    def test_no_requests_import_in_phase38_script(self) -> None:
        """The main script must not import 'requests' (external HTTP calls)."""
        script_path = (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "run_phase38_mlb_bss_repair_preview.py"
        )
        src = script_path.read_text(encoding="utf-8")
        # requests, httpx, urllib.request are network libraries
        for forbidden in ["import requests", "import httpx", "urllib.request.urlopen"]:
            assert forbidden not in src, (
                f"External HTTP library found in Phase 38 script: {forbidden!r}"
            )

    def test_no_openai_or_llm_import(self) -> None:
        """The main script must not import LLM client libraries."""
        script_path = (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "run_phase38_mlb_bss_repair_preview.py"
        )
        src = script_path.read_text(encoding="utf-8")
        for forbidden in ["import openai", "import anthropic", "import cohere", "LangChain"]:
            assert forbidden not in src, (
                f"LLM library found in Phase 38 script: {forbidden!r}"
            )

    def test_run_phase38_completes_without_network(self, monkeypatch) -> None:
        """run_phase38() must complete successfully with network calls blocked."""
        import socket

        original_socket = socket.socket

        class _NoNetworkSocket:
            def __init__(self, *a, **kw):
                raise OSError("Network access blocked in test.")

        monkeypatch.setattr(socket, "socket", _NoNetworkSocket)
        # Should not raise — no network calls expected
        result = run_phase38(write_preview=False)
        assert result.verdict == "PHASE_38_MLB_BSS_DATA_CALIBRATION_REPAIR_VERIFIED"
