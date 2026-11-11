"""
P6-C — MlbOddsSnapshot Contract Tests
"""
import sys, os
_WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKTREE not in sys.path:
    sys.path.insert(0, _WORKTREE)

import pytest
from datetime import datetime, timezone, timedelta
from wbc_backend.recommendation.odds_contract import (
    MlbOddsSnapshot, OddsSourceType, OddsContractError, classify_odds_record,
)

_GAME_START = datetime(2025, 7, 4, 18, 0, 0, tzinfo=timezone.utc)
_PREGAME    = _GAME_START - timedelta(hours=2)
_CLOSING    = _GAME_START - timedelta(minutes=15)
_POSTGAME   = _GAME_START + timedelta(hours=3)


def _snap(**kwargs) -> MlbOddsSnapshot:
    defaults = dict(
        game_id="TEST_001",
        game_start_utc=_GAME_START,
        captured_at_utc=_PREGAME,
        market="ML",
        side="HOME",
        decimal_odds=1.91,
        source="TSL",
        source_type=OddsSourceType.PREGAME,
        paper_only=True,
        source_trace="TSL capture 2h before game",
    )
    defaults.update(kwargs)
    return MlbOddsSnapshot(**defaults)


# ── Test 1: valid pregame snapshot accepted ──────────────────────────────────

def test_valid_pregame_snapshot_accepted():
    s = _snap(captured_at_utc=_PREGAME, source_type=OddsSourceType.PREGAME)
    assert s.source_type == OddsSourceType.PREGAME
    assert s.paper_only is True


# ── Test 2: valid closing snapshot accepted ──────────────────────────────────

def test_valid_closing_snapshot_accepted():
    s = _snap(captured_at_utc=_CLOSING, source_type=OddsSourceType.CLOSING)
    assert s.source_type == OddsSourceType.CLOSING


# ── Test 3: post-game timestamp cannot be pregame ────────────────────────────

def test_post_game_timestamp_cannot_be_pregame():
    with pytest.raises(OddsContractError, match="AFTER game_start"):
        _snap(captured_at_utc=_POSTGAME, source_type=OddsSourceType.PREGAME)


# ── Test 4: post-game timestamp cannot be closing ────────────────────────────

def test_post_game_timestamp_cannot_be_closing():
    with pytest.raises(OddsContractError, match="AFTER game_start"):
        _snap(captured_at_utc=_POSTGAME, source_type=OddsSourceType.CLOSING)


# ── Test 5: missing timestamp becomes UNKNOWN ────────────────────────────────

def test_missing_timestamp_becomes_unknown():
    s = _snap(captured_at_utc=None, source_type=OddsSourceType.UNKNOWN)
    assert s.source_type == OddsSourceType.UNKNOWN


# ── Test 6: missing timestamp with PREGAME type raises ───────────────────────

def test_missing_timestamp_with_pregame_type_raises():
    with pytest.raises(OddsContractError, match="requires captured_at_utc"):
        _snap(captured_at_utc=None, source_type=OddsSourceType.PREGAME)


# ── Test 7: POST_GAME_PROXY blocked from CLV (via classify) ──────────────────

def test_post_game_proxy_classification():
    rec = {
        "game_id": "TEST_002",
        "captured_at_utc": _POSTGAME.isoformat(),
        "game_start_utc": _GAME_START.isoformat(),
    }
    st = classify_odds_record(rec)
    assert st == OddsSourceType.POST_GAME_PROXY


# ── Test 8: paper_only=false raises ─────────────────────────────────────────

def test_paper_only_false_raises():
    with pytest.raises(OddsContractError, match="paper_only must be True"):
        _snap(paper_only=False)


# ── Test 9: decimal_odds invalid raises ──────────────────────────────────────

def test_decimal_odds_below_one_raises():
    with pytest.raises(OddsContractError, match="decimal_odds must be >= 1.0"):
        _snap(decimal_odds=0.5)


# ── Test 10: source_trace required ──────────────────────────────────────────

def test_source_trace_required():
    with pytest.raises(OddsContractError, match="source_trace is required"):
        _snap(source_trace="")


# ── Test 11: pre-game snapshot cannot be POST_GAME_PROXY ────────────────────

def test_pregame_time_cannot_be_post_game_proxy():
    with pytest.raises(OddsContractError, match="Cannot be POST_GAME_PROXY"):
        _snap(captured_at_utc=_PREGAME, source_type=OddsSourceType.POST_GAME_PROXY)


# ── Test 12: infer_source_type works correctly ───────────────────────────────

def test_infer_source_type_post_game():
    st = MlbOddsSnapshot.infer_source_type(_POSTGAME, _GAME_START)
    assert st == OddsSourceType.POST_GAME_PROXY


def test_infer_source_type_pregame():
    st = MlbOddsSnapshot.infer_source_type(_PREGAME, _GAME_START)
    assert st == OddsSourceType.PREGAME


def test_infer_source_type_none_timestamp():
    st = MlbOddsSnapshot.infer_source_type(None, _GAME_START)
    assert st == OddsSourceType.UNKNOWN
