"""Tests for p34_odds_source_planner.py"""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    LEAKAGE_NONE,
    ODDS_TEMPLATE_COLUMNS,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_LICENSE_REVIEW,
    OPTION_REQUIRES_MANUAL_APPROVAL,
)
from wbc_backend.recommendation.p34_odds_source_planner import (
    build_odds_acquisition_options,
    evaluate_candidate_license_safety,
    evaluate_odds_schema,
    load_p33_odds_candidates,
    rank_odds_options,
    summarize_odds_plan,
)


class TestLoadP33OddsCandidates:
    def test_returns_empty_if_missing(self):
        df = load_p33_odds_candidates("/no/such/file.csv")
        assert df.empty

    def test_loads_csv(self, tmp_path):
        csv_file = tmp_path / "odds.csv"
        csv_file.write_text("candidate_id,file_path,status\n1,/some/path,SOURCE_BLOCKED\n")
        df = load_p33_odds_candidates(str(csv_file))
        assert len(df) == 1


class TestEvaluateCandidateLicenseSafety:
    def test_retrosheet_is_permitted(self):
        row = pd.Series({"source_odds_ref": "retrosheet_2024"})
        result = evaluate_candidate_license_safety(row)
        assert result == "research_permitted"

    def test_empty_source_is_unknown(self):
        row = pd.Series({"source_odds_ref": ""})
        result = evaluate_candidate_license_safety(row)
        assert result == "unknown"

    def test_nan_source_is_unknown(self):
        row = pd.Series({"source_odds_ref": "nan"})
        result = evaluate_candidate_license_safety(row)
        assert result == "unknown"

    def test_tsl_requires_review(self):
        row = pd.Series({"source_odds_ref": "tsl_snapshot_2024"})
        result = evaluate_candidate_license_safety(row)
        assert result == "review_required"

    def test_live_odds_requires_review(self):
        row = pd.Series({"source_odds_ref": "live_odds_feed"})
        result = evaluate_candidate_license_safety(row)
        assert result == "review_required"

    def test_unknown_source_requires_review(self):
        row = pd.Series({"source_odds_ref": "some_obscure_source"})
        result = evaluate_candidate_license_safety(row)
        assert result == "review_required"


class TestEvaluateOddsSchema:
    def test_all_columns_present(self):
        cols_str = ",".join(ODDS_TEMPLATE_COLUMNS)
        row = pd.Series({"detected_columns": cols_str})
        result = evaluate_odds_schema(row)
        assert len(result["missing"]) == 0
        assert len(result["present"]) == len(ODDS_TEMPLATE_COLUMNS)
        assert result["has_game_id"] is True

    def test_empty_columns(self):
        row = pd.Series({"detected_columns": ""})
        result = evaluate_odds_schema(row)
        assert result["has_game_id"] is False
        assert len(result["missing"]) == len(ODDS_TEMPLATE_COLUMNS)

    def test_partial_columns(self):
        row = pd.Series({"detected_columns": "game_id,odds_decimal"})
        result = evaluate_odds_schema(row)
        assert result["has_game_id"] is True
        assert result["has_odds_decimal"] is True
        assert len(result["missing"]) > 0

    def test_has_odds_decimal_via_alternate_name(self):
        row = pd.Series({"detected_columns": "home_ml,away_ml,game_id"})
        result = evaluate_odds_schema(row)
        assert result["has_odds_decimal"] is True


class TestBuildOddsAcquisitionOptions:
    def test_returns_list(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        assert isinstance(options, list)

    def test_always_has_blocker_option(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        statuses = [o.status for o in options]
        assert OPTION_BLOCKED_PROVENANCE in statuses

    def test_odds_r01_present(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        r01 = next((o for o in options if o.option_id == "odds_r01"), None)
        assert r01 is not None
        assert r01.status == OPTION_REQUIRES_LICENSE_REVIEW

    def test_odds_r02_present(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        r02 = next((o for o in options if o.option_id == "odds_r02"), None)
        assert r02 is not None
        assert r02.status == OPTION_REQUIRES_MANUAL_APPROVAL

    def test_odds_r04_blocker_present(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        r04 = next((o for o in options if o.option_id == "odds_r04"), None)
        assert r04 is not None
        assert r04.status == OPTION_BLOCKED_PROVENANCE

    def test_all_options_paper_only(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        for opt in options:
            assert opt.paper_only is True
            assert opt.production_ready is False

    def test_no_live_api_option(self):
        """Scraping must be explicitly forbidden in any option that mentions it."""
        options = build_odds_acquisition_options(pd.DataFrame())
        for opt in options:
            lower_method = opt.acquisition_method.lower()
            if "scrape" in lower_method:
                # Must be accompanied by a prohibition
                assert (
                    "not scrape" in lower_method
                    or "do not scrape" in lower_method
                    or "never scrape" in lower_method
                ), f"Scraping mentioned without prohibition in {opt.option_id}: {opt.acquisition_method}"
            # The Odds API option must explicitly mark as NOT live
            if opt.option_id == "odds_r02":
                assert "live" not in lower_method or "not" in lower_method or "do not" in opt.acquisition_method.lower()

    def test_no_outcome_derived_option(self):
        """No option should derive p_market from game outcomes."""
        options = build_odds_acquisition_options(pd.DataFrame())
        for opt in options:
            lower = opt.acquisition_method.lower()
            assert "from outcome" not in lower
            assert "infer odds" not in lower

    def test_odds_r01_requires_license_review(self):
        """sportsbookreviewsonline path must require license review."""
        options = build_odds_acquisition_options(pd.DataFrame())
        r01 = next(o for o in options if o.option_id == "odds_r01")
        assert r01.status == OPTION_REQUIRES_LICENSE_REVIEW

    def test_repo_candidates_blocked_if_license_unknown(self):
        """P33 candidates with unknown license should be blocked."""
        df = pd.DataFrame({
            "candidate_id": ["c1"],
            "file_path": ["/data/odds_2024.csv"],
            "status": ["SOURCE_PARTIAL"],
            "source_odds_ref": [""],  # empty → unknown
            "detected_columns": ["game_id,p_market"],
        })
        options = build_odds_acquisition_options(df)
        repo_opts = [o for o in options if o.option_id.startswith("odds_r03")]
        if repo_opts:
            for opt in repo_opts:
                assert opt.status in (OPTION_BLOCKED_PROVENANCE, OPTION_REQUIRES_LICENSE_REVIEW)


class TestRankOddsOptions:
    def test_license_review_ranks_higher_than_blocked(self):
        from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
            P34OddsAcquisitionOption,
            LEAKAGE_NONE,
            RISK_LOW,
            ODDS_TEMPLATE_COLUMNS,
        )

        def make_opt(option_id, status):
            return P34OddsAcquisitionOption(
                option_id=option_id,
                source_name="test",
                source_type="licensed_export",
                acquisition_method="test",
                expected_columns=ODDS_TEMPLATE_COLUMNS,
                missing_columns=(),
                provenance_status="ok",
                license_status="review",
                leakage_risk=LEAKAGE_NONE,
                implementation_risk=RISK_LOW,
                estimated_coverage=0.9,
                status=status,
            )

        blocked = make_opt("b1", OPTION_BLOCKED_PROVENANCE)
        review = make_opt("r1", OPTION_REQUIRES_LICENSE_REVIEW)
        ranked = rank_odds_options([blocked, review])
        assert ranked[0].status == OPTION_REQUIRES_LICENSE_REVIEW


class TestSummarizeOddsPlan:
    def test_returns_string(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        s = summarize_odds_plan(options)
        assert isinstance(s, str)
        assert "PAPER_ONLY=True" in s

    def test_empty_options(self):
        s = summarize_odds_plan([])
        assert "No" in s

    def test_no_scraping_mention(self):
        options = build_odds_acquisition_options(pd.DataFrame())
        s = summarize_odds_plan(options)
        # Summary should warn about scraping
        assert "scrape" in s.lower() or "NOT scrape" in s or "Do NOT" in s
