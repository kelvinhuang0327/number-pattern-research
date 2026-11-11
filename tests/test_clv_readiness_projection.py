"""
P8-E Tests — CLV Readiness Projection

驗收條件：
- historical source available → HISTORICAL_BACKFILL_READY
- api key missing → BLOCKED_NEEDS_API_KEY
- forward coverage below threshold → BLOCKED_LOW_COVERAGE
- forward coverage above threshold → FORWARD_COLLECTION_ACCUMULATING
- no closing line → BLOCKED_NO_CLOSING_LINE
- post-game proxy only → BLOCKED_POST_GAME_PROXY_ONLY
- paper_only=false → raises CLVReadinessProjectionError
"""

from __future__ import annotations

import pytest

from wbc_backend.recommendation.clv_readiness_projection import (
    MIN_PAIR_COVERAGE_PCT,
    MIN_PREGAME_CLOSING_PAIRS,
    BackfillPath,
    CLVReadinessInput,
    CLVReadinessProjection,
    CLVReadinessProjectionError,
    CLVReadinessStatus,
    project_clv_readiness,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def historical_ready_input() -> CLVReadinessInput:
    """Historical API path — all good → HISTORICAL_BACKFILL_READY."""
    return CLVReadinessInput(
        path=BackfillPath.HISTORICAL_API,
        paper_only=True,
        historical_api_available=True,
        historical_api_key_provided=True,
        historical_has_closing_line=True,
        historical_has_pregame_timestamps=True,
        historical_projected_pairs=500,
        historical_all_post_game_proxy=False,
    )


@pytest.fixture()
def forward_accumulating_input() -> CLVReadinessInput:
    """Forward collection — above threshold → FORWARD_COLLECTION_ACCUMULATING."""
    return CLVReadinessInput(
        path=BackfillPath.FORWARD_COLLECTION,
        paper_only=True,
        forward_has_closing_line=True,
        forward_current_pair_coverage_pct=87.0,
        forward_projected_pair_coverage_pct=92.0,
        forward_current_pairs=180,
        forward_projected_pairs=250,
    )


@pytest.fixture()
def forward_low_coverage_input() -> CLVReadinessInput:
    return CLVReadinessInput(
        path=BackfillPath.FORWARD_COLLECTION,
        paper_only=True,
        forward_has_closing_line=True,
        forward_current_pair_coverage_pct=50.0,
        forward_projected_pair_coverage_pct=65.0,  # below 90%
        forward_current_pairs=50,
        forward_projected_pairs=100,  # below 200
    )


# ── P8-E-1: historical source available → HISTORICAL_BACKFILL_READY ──────────

class TestHistoricalBackfillReady:
    def test_returns_historical_backfill_ready(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.status == CLVReadinessStatus.HISTORICAL_BACKFILL_READY

    def test_api_key_required_is_false(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.api_key_required is False

    def test_ceo_action_not_required_when_ready(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.ceo_action_required is False

    def test_projected_pairs_matches_input(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.projected_pairs == 500

    def test_paper_only_true_in_projection(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.paper_only is True

    def test_reason_mentions_threshold(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert str(MIN_PREGAME_CLOSING_PAIRS) in result.reason

    def test_exactly_at_min_threshold(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_has_pregame_timestamps=True,
            historical_projected_pairs=MIN_PREGAME_CLOSING_PAIRS,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.HISTORICAL_BACKFILL_READY


# ── P8-E-2: api key missing → BLOCKED_NEEDS_API_KEY ─────────────────────────

class TestBlockedNeedsApiKey:
    def test_no_api_key_returns_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=False,
            historical_has_closing_line=True,
            historical_has_pregame_timestamps=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_NEEDS_API_KEY

    def test_blocked_api_key_requires_ceo_action(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=False,
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.ceo_action_required is True
        assert result.api_key_required is True


# ── P8-E-3: forward coverage below threshold → BLOCKED_LOW_COVERAGE ──────────

class TestBlockedLowCoverage:
    def test_low_coverage_returns_blocked(self, forward_low_coverage_input):
        result = project_clv_readiness(forward_low_coverage_input)
        assert result.status == CLVReadinessStatus.BLOCKED_LOW_COVERAGE

    def test_reason_mentions_coverage_value(self, forward_low_coverage_input):
        result = project_clv_readiness(forward_low_coverage_input)
        assert "65" in result.reason or "65.0" in result.reason

    def test_historical_low_pairs_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_has_pregame_timestamps=True,
            historical_projected_pairs=100,  # below 200
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_LOW_COVERAGE

    def test_historical_zero_pairs_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_projected_pairs=0,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_LOW_COVERAGE

    def test_forward_pairs_below_min_even_if_coverage_high(self):
        inp = CLVReadinessInput(
            path=BackfillPath.FORWARD_COLLECTION,
            paper_only=True,
            forward_has_closing_line=True,
            forward_projected_pair_coverage_pct=95.0,  # high %
            forward_projected_pairs=50,  # but low count
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_LOW_COVERAGE


# ── P8-E-4: forward coverage above threshold → FORWARD_COLLECTION_ACCUMULATING

class TestForwardCollectionAccumulating:
    def test_above_threshold_returns_accumulating(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.status == CLVReadinessStatus.FORWARD_COLLECTION_ACCUMULATING

    def test_api_key_not_required_for_forward(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.api_key_required is False

    def test_projected_pairs_matches_input(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.projected_pairs == 250

    def test_pair_coverage_pct_matches_projected(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.pair_coverage_pct == pytest.approx(92.0)

    def test_paper_only_true(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.paper_only is True

    def test_reason_mentions_coverage(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert "92" in result.reason or "92.0" in result.reason


# ── P8-E-5: no closing line → BLOCKED_NO_CLOSING_LINE ─────────────────────────

class TestBlockedNoClosingLine:
    def test_historical_no_closing_line_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=False,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_NO_CLOSING_LINE

    def test_forward_no_closing_line_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.FORWARD_COLLECTION,
            paper_only=True,
            forward_has_closing_line=False,
            forward_projected_pair_coverage_pct=95.0,
            forward_projected_pairs=300,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_NO_CLOSING_LINE

    def test_reason_mentions_closing_line(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=False,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
        )
        result = project_clv_readiness(inp)
        assert "closing" in result.reason.lower()


# ── P8-E-6: post-game proxy only → BLOCKED_POST_GAME_PROXY_ONLY ──────────────

class TestBlockedPostGameProxyOnly:
    def test_all_post_game_proxy_returns_blocked(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=True,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_POST_GAME_PROXY_ONLY

    def test_post_game_proxy_blocked_takes_priority_over_pairs(self):
        """POST_GAME_PROXY block evaluated before pair count."""
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_projected_pairs=9999,  # high pairs but all proxy
            historical_all_post_game_proxy=True,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.BLOCKED_POST_GAME_PROXY_ONLY

    def test_reason_mentions_post_game_proxy(self):
        inp = CLVReadinessInput(
            path=BackfillPath.HISTORICAL_API,
            paper_only=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=True,
        )
        result = project_clv_readiness(inp)
        assert "POST_GAME_PROXY" in result.reason or "proxy" in result.reason.lower()


# ── P8-E-7: paper_only=false → raises CLVReadinessProjectionError ────────────

class TestPaperOnlyGuard:
    def test_paper_only_false_raises_on_input(self):
        with pytest.raises(CLVReadinessProjectionError, match="paper_only must be True"):
            CLVReadinessInput(
                path=BackfillPath.HISTORICAL_API,
                paper_only=False,
                historical_api_key_provided=True,
                historical_projected_pairs=500,
            )

    def test_invalid_path_type_raises(self):
        with pytest.raises(CLVReadinessProjectionError, match="path must be BackfillPath"):
            CLVReadinessInput(
                path="HISTORICAL_API",  # type: ignore — wrong type
                paper_only=True,
            )

    def test_negative_pairs_raises(self):
        with pytest.raises(CLVReadinessProjectionError, match="historical_projected_pairs"):
            CLVReadinessInput(
                path=BackfillPath.HISTORICAL_API,
                paper_only=True,
                historical_projected_pairs=-1,
            )

    def test_coverage_pct_over_100_raises(self):
        with pytest.raises(CLVReadinessProjectionError, match="forward_projected_pair_coverage_pct"):
            CLVReadinessInput(
                path=BackfillPath.FORWARD_COLLECTION,
                paper_only=True,
                forward_projected_pair_coverage_pct=101.0,
            )

    def test_negative_coverage_pct_raises(self):
        with pytest.raises(CLVReadinessProjectionError, match="forward_current_pair_coverage_pct"):
            CLVReadinessInput(
                path=BackfillPath.FORWARD_COLLECTION,
                paper_only=True,
                forward_current_pair_coverage_pct=-5.0,
            )


# ── P8-E-8: BOTH path evaluation ─────────────────────────────────────────────

class TestBothPath:
    def test_both_historical_ready_returns_historical(self):
        inp = CLVReadinessInput(
            path=BackfillPath.BOTH,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=True,
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
            forward_has_closing_line=True,
            forward_projected_pair_coverage_pct=92.0,
            forward_projected_pairs=250,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.HISTORICAL_BACKFILL_READY

    def test_both_historical_blocked_falls_back_to_forward_accumulating(self):
        inp = CLVReadinessInput(
            path=BackfillPath.BOTH,
            paper_only=True,
            historical_api_available=True,
            historical_api_key_provided=False,  # no key
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
            forward_has_closing_line=True,
            forward_projected_pair_coverage_pct=92.0,
            forward_projected_pairs=250,
        )
        result = project_clv_readiness(inp)
        assert result.status == CLVReadinessStatus.FORWARD_COLLECTION_ACCUMULATING

    def test_both_all_blocked_returns_historical_status(self):
        """When both paths blocked, BOTH returns the historical path status."""
        inp = CLVReadinessInput(
            path=BackfillPath.BOTH,
            paper_only=True,
            historical_api_available=False,
            historical_api_key_provided=False,
            historical_has_closing_line=True,
            historical_projected_pairs=500,
            historical_all_post_game_proxy=False,
            forward_has_closing_line=True,
            forward_projected_pair_coverage_pct=50.0,  # below threshold
            forward_projected_pairs=50,  # below min
        )
        result = project_clv_readiness(inp)
        # Both blocked; should return a BLOCKED status
        assert result.status not in (
            CLVReadinessStatus.HISTORICAL_BACKFILL_READY,
            CLVReadinessStatus.FORWARD_COLLECTION_ACCUMULATING,
        )


# ── P8-E-9: Projection output shape ──────────────────────────────────────────

class TestProjectionOutputShape:
    def test_projection_is_dataclass(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert isinstance(result, CLVReadinessProjection)

    def test_projection_target_pairs_default(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert result.target_pairs == MIN_PREGAME_CLOSING_PAIRS

    def test_projection_target_coverage_pct_default(self, forward_accumulating_input):
        result = project_clv_readiness(forward_accumulating_input)
        assert result.target_coverage_pct == pytest.approx(MIN_PAIR_COVERAGE_PCT)

    def test_annotation_contains_paper_only_str(self, historical_ready_input):
        result = project_clv_readiness(historical_ready_input)
        assert "paper_only=true" in result.annotation
