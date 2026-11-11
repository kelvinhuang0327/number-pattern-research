"""
Tests for P33 Safe Source Recommendation Builder
"""

import pytest

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    P33SourceGapSummary,
)
from wbc_backend.recommendation.p33_safe_source_recommendation_builder import (
    P33SourceRecommendation,
    P33SourceRecommendationSet,
    _ODDS_RECOMMENDATIONS,
    _PREDICTION_RECOMMENDATIONS,
    build_odds_source_recommendations,
    build_prediction_source_recommendations,
    build_recommendation_set,
    validate_recommendation_safety,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _gap_summary_all_missing() -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=True,
        odds_missing=True,
    )


def _gap_summary_none_missing() -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=False,
        odds_missing=False,
        prediction_ready_count=1,
        odds_ready_count=1,
    )


def _gap_summary_only_pred_missing() -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=True,
        odds_missing=False,
        odds_ready_count=1,
    )


def _gap_summary_only_odds_missing() -> P33SourceGapSummary:
    return P33SourceGapSummary(
        prediction_missing=False,
        odds_missing=True,
        prediction_ready_count=1,
    )


# ---------------------------------------------------------------------------
# Static catalogue tests
# ---------------------------------------------------------------------------


class TestStaticRecommendationCatalogues:
    def test_prediction_catalogue_not_empty(self):
        assert len(_PREDICTION_RECOMMENDATIONS) > 0

    def test_odds_catalogue_not_empty(self):
        assert len(_ODDS_RECOMMENDATIONS) > 0

    def test_all_prediction_recs_paper_only(self):
        for r in _PREDICTION_RECOMMENDATIONS:
            assert r.paper_only is True, f"Prediction rec not paper_only: {r.recommendation_id}"

    def test_all_odds_recs_paper_only(self):
        for r in _ODDS_RECOMMENDATIONS:
            assert r.paper_only is True, f"Odds rec not paper_only: {r.recommendation_id}"

    def test_all_prediction_recs_not_production_ready(self):
        for r in _PREDICTION_RECOMMENDATIONS:
            assert r.production_ready is False

    def test_all_odds_recs_not_production_ready(self):
        for r in _ODDS_RECOMMENDATIONS:
            assert r.production_ready is False

    def test_prediction_rec_ids_unique(self):
        ids = [r.recommendation_id for r in _PREDICTION_RECOMMENDATIONS]
        assert len(ids) == len(set(ids))

    def test_odds_rec_ids_unique(self):
        ids = [r.recommendation_id for r in _ODDS_RECOMMENDATIONS]
        assert len(ids) == len(set(ids))

    def test_prediction_recs_target_type(self):
        for r in _PREDICTION_RECOMMENDATIONS:
            assert r.target_data_type == "prediction"

    def test_odds_recs_target_type(self):
        for r in _ODDS_RECOMMENDATIONS:
            assert r.target_data_type == "odds"

    def test_priorities_positive(self):
        for r in _PREDICTION_RECOMMENDATIONS + _ODDS_RECOMMENDATIONS:
            assert r.priority >= 1

    def test_recs_are_frozen(self):
        r = _PREDICTION_RECOMMENDATIONS[0]
        with pytest.raises((AttributeError, TypeError)):
            r.priority = 99  # type: ignore[misc]

    def test_required_schema_fields_not_empty(self):
        for r in _PREDICTION_RECOMMENDATIONS + _ODDS_RECOMMENDATIONS:
            assert len(r.required_schema_fields) > 0, (
                f"No required schema fields in {r.recommendation_id}"
            )

    def test_blocker_if_skipped_populated_for_top_priority(self):
        top_pred = min(_PREDICTION_RECOMMENDATIONS, key=lambda r: r.priority)
        assert len(top_pred.blocker_if_skipped) > 0
        top_odds = min(_ODDS_RECOMMENDATIONS, key=lambda r: r.priority)
        assert len(top_odds.blocker_if_skipped) > 0


# ---------------------------------------------------------------------------
# build_prediction_source_recommendations
# ---------------------------------------------------------------------------


class TestBuildPredictionSourceRecommendations:
    def test_returns_list_when_missing(self):
        recs = build_prediction_source_recommendations(_gap_summary_all_missing())
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_returns_empty_when_not_missing(self):
        recs = build_prediction_source_recommendations(_gap_summary_none_missing())
        assert recs == []

    def test_sorted_by_priority(self):
        recs = build_prediction_source_recommendations(_gap_summary_all_missing())
        priorities = [r.priority for r in recs]
        assert priorities == sorted(priorities)

    def test_all_returned_are_prediction_type(self):
        recs = build_prediction_source_recommendations(_gap_summary_all_missing())
        for r in recs:
            assert r.target_data_type == "prediction"


# ---------------------------------------------------------------------------
# build_odds_source_recommendations
# ---------------------------------------------------------------------------


class TestBuildOddsSourceRecommendations:
    def test_returns_list_when_missing(self):
        recs = build_odds_source_recommendations(_gap_summary_all_missing())
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_returns_empty_when_not_missing(self):
        recs = build_odds_source_recommendations(_gap_summary_none_missing())
        assert recs == []

    def test_sorted_by_priority(self):
        recs = build_odds_source_recommendations(_gap_summary_all_missing())
        priorities = [r.priority for r in recs]
        assert priorities == sorted(priorities)

    def test_all_returned_are_odds_type(self):
        recs = build_odds_source_recommendations(_gap_summary_all_missing())
        for r in recs:
            assert r.target_data_type == "odds"


# ---------------------------------------------------------------------------
# validate_recommendation_safety
# ---------------------------------------------------------------------------


class TestValidateRecommendationSafety:
    def test_all_safe_returns_true(self):
        all_recs = list(_PREDICTION_RECOMMENDATIONS) + list(_ODDS_RECOMMENDATIONS)
        assert validate_recommendation_safety(all_recs) is True

    def test_unsafe_rec_returns_false(self):
        unsafe = P33SourceRecommendation(
            recommendation_id="unsafe_r01",
            target_data_type="prediction",
            priority=1,
            source_name="Unsafe Source",
            url_or_reference="",
            format_hint="",
            license_note="",
            required_schema_fields=(),
            acquisition_method="manual_download",
            estimated_effort="low",
            paper_only=False,  # NOT paper_only
            production_ready=False,
        )
        assert validate_recommendation_safety([unsafe]) is False

    def test_production_ready_rec_returns_false(self):
        unsafe = P33SourceRecommendation(
            recommendation_id="unsafe_r02",
            target_data_type="odds",
            priority=1,
            source_name="Prod Source",
            url_or_reference="",
            format_hint="",
            license_note="",
            required_schema_fields=(),
            acquisition_method="api_key_required",
            estimated_effort="medium",
            paper_only=True,
            production_ready=True,  # Production ready — unsafe
        )
        assert validate_recommendation_safety([unsafe]) is False

    def test_empty_list_returns_true(self):
        assert validate_recommendation_safety([]) is True


# ---------------------------------------------------------------------------
# build_recommendation_set
# ---------------------------------------------------------------------------


class TestBuildRecommendationSet:
    def test_returns_set_all_missing(self):
        gap = _gap_summary_all_missing()
        rec_set = build_recommendation_set(gap)
        assert isinstance(rec_set, P33SourceRecommendationSet)
        assert len(rec_set.prediction_recommendations) > 0
        assert len(rec_set.odds_recommendations) > 0

    def test_returns_empty_recs_when_none_missing(self):
        gap = _gap_summary_none_missing()
        rec_set = build_recommendation_set(gap)
        assert rec_set.prediction_recommendations == []
        assert rec_set.odds_recommendations == []

    def test_only_prediction_missing(self):
        gap = _gap_summary_only_pred_missing()
        rec_set = build_recommendation_set(gap)
        assert len(rec_set.prediction_recommendations) > 0
        assert rec_set.odds_recommendations == []

    def test_only_odds_missing(self):
        gap = _gap_summary_only_odds_missing()
        rec_set = build_recommendation_set(gap)
        assert len(rec_set.odds_recommendations) > 0
        assert rec_set.prediction_recommendations == []

    def test_total_count_correct(self):
        gap = _gap_summary_all_missing()
        rec_set = build_recommendation_set(gap)
        assert rec_set.total_count == (
            len(rec_set.prediction_recommendations) + len(rec_set.odds_recommendations)
        )

    def test_paper_only_flag(self):
        gap = _gap_summary_all_missing()
        rec_set = build_recommendation_set(gap)
        assert rec_set.paper_only is True
        assert rec_set.production_ready is False

    def test_summary_message_not_empty(self):
        gap = _gap_summary_all_missing()
        rec_set = build_recommendation_set(gap)
        assert len(rec_set.summary_message) > 0
