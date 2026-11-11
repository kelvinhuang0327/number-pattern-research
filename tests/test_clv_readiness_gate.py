"""
P6-D — CLV Readiness Gate Tests
"""
import sys, os
_WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKTREE not in sys.path:
    sys.path.insert(0, _WORKTREE)

import pytest
from wbc_backend.recommendation.clv_readiness_gate import (
    evaluate_clv_readiness,
    CLV_READY,
    BLOCKED_POST_GAME_PROXY_ONLY,
    BLOCKED_NO_PREGAME_ODDS,
    BLOCKED_NO_CLOSING_ODDS,
    BLOCKED_LOW_TIMESTAMP_COVERAGE,
    ClvGateError,
)
from wbc_backend.recommendation.odds_contract import OddsSourceType


def _snaps(types: list[str], paper_only: bool = True) -> list[dict]:
    return [{"source_type": t, "paper_only": paper_only} for t in types]


# ── Test 1: only post-game proxy → blocked ───────────────────────────────────

def test_only_post_game_proxy_blocked():
    snaps = _snaps([OddsSourceType.POST_GAME_PROXY.value] * 100)
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == BLOCKED_POST_GAME_PROXY_ONLY
    assert result["paper_only"] is True


# ── Test 2: pregame only without closing → blocked ───────────────────────────

def test_pregame_only_without_closing_blocked():
    snaps = _snaps([OddsSourceType.PREGAME.value] * 50)
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == BLOCKED_NO_CLOSING_ODDS


# ── Test 3: closing only without pregame → blocked ───────────────────────────

def test_closing_only_without_pregame_blocked():
    snaps = _snaps([OddsSourceType.CLOSING.value] * 50)
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == BLOCKED_NO_PREGAME_ODDS


# ── Test 4: low timestamp coverage → blocked ────────────────────────────────

def test_low_timestamp_coverage_blocked():
    # 50% pregame+closing, 50% proxy → coverage < 95%
    snaps = (
        _snaps([OddsSourceType.PREGAME.value] * 25) +
        _snaps([OddsSourceType.CLOSING.value] * 25) +
        _snaps([OddsSourceType.POST_GAME_PROXY.value] * 50)
    )
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == BLOCKED_LOW_TIMESTAMP_COVERAGE
    assert result["coverage"] == pytest.approx(0.50, abs=0.01)


# ── Test 5: valid pregame+closing pair → CLV_READY ───────────────────────────

def test_valid_pregame_closing_clv_ready():
    snaps = (
        _snaps([OddsSourceType.PREGAME.value] * 50) +
        _snaps([OddsSourceType.CLOSING.value] * 50)
    )
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == CLV_READY
    assert result["coverage"] == pytest.approx(1.0, abs=0.01)


# ── Test 6: UNKNOWN excluded from coverage ───────────────────────────────────

def test_unknown_excluded_from_coverage():
    # 97 pregame+closing out of 100 valid, 100 UNKNOWN → coverage = 97%
    snaps = (
        _snaps([OddsSourceType.PREGAME.value] * 50) +
        _snaps([OddsSourceType.CLOSING.value] * 47) +
        _snaps([OddsSourceType.UNKNOWN.value] * 100)
    )
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == CLV_READY
    assert result["coverage"] >= 0.95


# ── Test 7: paper_only=false raises ─────────────────────────────────────────

def test_paper_only_false_raises():
    snaps = _snaps([OddsSourceType.PREGAME.value], paper_only=False)
    with pytest.raises(ClvGateError, match="paper_only=false"):
        evaluate_clv_readiness(snaps)


# ── Test 8: empty snapshots returns blocked ──────────────────────────────────

def test_empty_snapshots_blocked():
    result = evaluate_clv_readiness([])
    assert result["status"] == BLOCKED_NO_PREGAME_ODDS


# ── Test 9: mixed with sufficient coverage → CLV_READY ───────────────────────

def test_mixed_sufficient_coverage_clv_ready():
    # 96 pregame+closing out of 100 valid (4 proxy) → 96% >= 95%
    snaps = (
        _snaps([OddsSourceType.PREGAME.value] * 48) +
        _snaps([OddsSourceType.CLOSING.value] * 48) +
        _snaps([OddsSourceType.POST_GAME_PROXY.value] * 4)
    )
    result = evaluate_clv_readiness(snaps)
    assert result["status"] == CLV_READY
