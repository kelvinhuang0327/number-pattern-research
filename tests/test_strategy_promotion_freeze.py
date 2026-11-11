"""
P6-E — Strategy Promotion Freeze Rule Tests
"""
import sys, os
_WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKTREE not in sys.path:
    sys.path.insert(0, _WORKTREE)

import pytest
from wbc_backend.recommendation.strategy_promotion_freeze import (
    check_promotion_eligibility,
    current_dataset_promotion_status,
    PROMOTION_ALLOWED,
    PROMOTION_BLOCKED_POST_GAME_PROXY,
    PROMOTION_BLOCKED_CLV_NOT_READY,
    PROMOTION_BLOCKED_PAPER_ONLY_FALSE,
    PROMOTION_BLOCKED_MISSING_ODDS_TYPE,
    PromotionFreezeError,
)
from wbc_backend.recommendation.odds_contract import OddsSourceType


def _snaps(types: list[str], paper_only: bool = True) -> list[dict]:
    return [{"source_type": t, "paper_only": paper_only} for t in types]


_GOOD_RESULT  = {"paper_only": True, "roi": 0.09, "ci_low": 0.01, "p_value": 0.03}
_PROXY_SNAPS  = _snaps([OddsSourceType.POST_GAME_PROXY.value] * 100)
_VALID_SNAPS  = (
    _snaps([OddsSourceType.PREGAME.value] * 50) +
    _snaps([OddsSourceType.CLOSING.value] * 50)
)


# ── Test 1: post-game proxy result cannot be promoted ────────────────────────

def test_post_game_proxy_cannot_be_promoted():
    result = check_promotion_eligibility(_GOOD_RESULT, _PROXY_SNAPS)
    assert result["promotion_status"] == PROMOTION_BLOCKED_POST_GAME_PROXY
    assert result["paper_only"] is True


# ── Test 2: pregame+closing missing cannot be promoted ───────────────────────

def test_pregame_only_no_closing_cannot_be_promoted():
    snaps = _snaps([OddsSourceType.PREGAME.value] * 100)
    result = check_promotion_eligibility(_GOOD_RESULT, snaps)
    assert result["promotion_status"] == PROMOTION_BLOCKED_CLV_NOT_READY


# ── Test 3: statistically significant but proxy-only still blocked ───────────

def test_significant_but_proxy_still_blocked():
    # Even if roi/ci/p look great, POST_GAME_PROXY must be blocked
    great_result = {"paper_only": True, "roi": 0.20, "ci_low": 0.05, "p_value": 0.01}
    result = check_promotion_eligibility(great_result, _PROXY_SNAPS)
    assert result["promotion_status"] == PROMOTION_BLOCKED_POST_GAME_PROXY


# ── Test 4: champion preserved when CLV not ready ────────────────────────────

def test_champion_preserved_when_clv_not_ready():
    # Low coverage: only 50% pregame+closing → BLOCKED_CLV_NOT_READY
    snaps = (
        _snaps([OddsSourceType.PREGAME.value] * 25) +
        _snaps([OddsSourceType.CLOSING.value] * 25) +
        _snaps([OddsSourceType.POST_GAME_PROXY.value] * 50)
    )
    result = check_promotion_eligibility(_GOOD_RESULT, snaps)
    assert result["promotion_status"] == PROMOTION_BLOCKED_CLV_NOT_READY


# ── Test 5: valid pregame+closing allows promotion to proceed ────────────────

def test_valid_clv_data_allows_promotion():
    result = check_promotion_eligibility(_GOOD_RESULT, _VALID_SNAPS)
    assert result["promotion_status"] == PROMOTION_ALLOWED


# ── Test 6: paper_only=false in strategy_result raises ───────────────────────

def test_paper_only_false_strategy_raises():
    bad_result = {"paper_only": False, "roi": 0.05}
    with pytest.raises(PromotionFreezeError, match="paper_only=false"):
        check_promotion_eligibility(bad_result, _VALID_SNAPS)


# ── Test 7: paper_only=false in odds_snapshots raises ────────────────────────

def test_paper_only_false_snapshot_raises():
    bad_snaps = _snaps([OddsSourceType.PREGAME.value] * 10, paper_only=False)
    with pytest.raises(PromotionFreezeError, match="paper_only=false"):
        check_promotion_eligibility(_GOOD_RESULT, bad_snaps)


# ── Test 8: no odds_snapshots provided → missing odds type blocked ────────────

def test_no_snapshots_blocked():
    result = check_promotion_eligibility(_GOOD_RESULT, [])
    assert result["promotion_status"] == PROMOTION_BLOCKED_MISSING_ODDS_TYPE


# ── Test 9: current dataset returns POST_GAME_PROXY blocked ──────────────────

def test_current_dataset_promotion_status_blocked():
    result = current_dataset_promotion_status()
    assert result["promotion_status"] == PROMOTION_BLOCKED_POST_GAME_PROXY
    assert result["paper_only"] is True
    assert result["n_records"] == 2430
