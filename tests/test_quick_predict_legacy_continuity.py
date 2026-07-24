from __future__ import annotations

import random
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "lottery_api"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import quick_predict  # noqa: E402

REAL_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
RULES = {'pickCount': 6, 'minNumber': 1, 'maxNumber': 49, 'specialMaxNumber': 49}


def _synthetic_biglotto_history(n=600, seed=20260724):
    """Deterministic, fully synthetic BIG_LOTTO history — long enough (600
    draws) to exercise every window used by the 5-bet family (Fourier w=500,
    cold/tail w=100, Markov w=30, FreqOrt w=100) without touching any real
    DB. Independent of DB state, so this fixture is stable across environments.
    """
    rng = random.Random(seed)
    history = []
    for i in range(n):
        numbers = sorted(rng.sample(range(1, 50), 6))
        history.append({
            'draw': f"115{i:06d}",
            'date': f"2020/{(i % 12) + 1:02d}/{(i % 28) + 1:02d}",
            'lotteryType': 'BIG_LOTTO',
            'numbers': numbers,
            'special': None,
            'jackpot_amount': None,
        })
    return history


FIXTURE_HISTORY = _synthetic_biglotto_history()


# ---------------------------------------------------------------------------
# 12.2 — normal and dry-run share one canonical read-only loader
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not REAL_DB_PATH.exists(), reason="canonical DB fixture not present in this checkout")
def test_normal_and_dry_run_history_are_identical():
    normal = quick_predict.load_history('BIG_LOTTO', dry_run=False)
    dry = quick_predict.load_history('BIG_LOTTO', dry_run=True)

    assert len(normal) == len(dry)
    assert len(normal) > 0
    assert normal == dry, "normal and dry-run must load byte-identical canonical history"
    assert normal[-1]['draw'] == dry[-1]['draw']


@pytest.mark.skipif(not REAL_DB_PATH.exists(), reason="canonical DB fixture not present in this checkout")
def test_history_excludes_non_canonical_families():
    for dry_run in (False, True):
        history = quick_predict.load_history('BIG_LOTTO', dry_run=dry_run)
        for draw in history:
            draw_id = str(draw['draw'])
            assert '-' not in draw_id, f"hyphenated add-on draw leaked into history: {draw_id}"
            assert not (len(draw_id) == 8 and draw_id.startswith('20')), (
                f"date-format-alien draw leaked into history: {draw_id}"
            )
            assert max(draw['numbers']) > 25, f"small-pool-alien draw leaked into history: {draw_id}"


def test_load_history_never_calls_raw_get_all_draws():
    # quick_predict.py does `from database import DatabaseManager` (a bare
    # top-level module, since it prepends lottery_api/ to sys.path), which
    # is a *different* module object than `lottery_api.database` even
    # though it's the same file — patch through quick_predict's own bound
    # reference so the mock actually intercepts what load_history() calls.
    with patch.object(quick_predict.DatabaseManager, 'get_all_draws') as mocked_raw:
        mocked_raw.side_effect = AssertionError('prediction path must not call get_all_draws()')
        with patch.object(quick_predict.DatabaseManager, 'get_canonical_draws', return_value=[]) as mocked_canonical:
            quick_predict.load_history('BIG_LOTTO', dry_run=False)
            quick_predict.load_history('BIG_LOTTO', dry_run=True)
        mocked_raw.assert_not_called()
        assert mocked_canonical.call_count == 2


def test_load_history_opens_database_manager_read_only():
    captured = {}
    original_init = quick_predict.DatabaseManager.__init__

    def spy_init(self, db_path=None, read_only=False):
        captured['read_only'] = read_only
        return original_init(self, db_path=db_path, read_only=read_only)

    with patch.object(quick_predict.DatabaseManager, '__init__', spy_init):
        with patch.object(quick_predict.DatabaseManager, 'get_canonical_draws', return_value=[]):
            quick_predict.load_history('BIG_LOTTO', dry_run=False)
    assert captured['read_only'] is True

    captured.clear()
    with patch.object(quick_predict.DatabaseManager, '__init__', spy_init):
        with patch.object(quick_predict.DatabaseManager, 'get_canonical_draws', return_value=[]):
            quick_predict.load_history('BIG_LOTTO', dry_run=True)
    assert captured['read_only'] is True


# ---------------------------------------------------------------------------
# 12.3 — ticket generation math/dispatch/order unchanged, deterministic
# ---------------------------------------------------------------------------

def test_prediction_deterministic_on_fixed_fixture():
    for num_bets in (2, 3, 4, 5):
        first, strategy1 = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, num_bets)
        second, strategy2 = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, num_bets)
        assert strategy1 == strategy2
        assert first == second, f"{num_bets}-bet prediction must be deterministic on a fixed fixture"


def test_prediction_tickets_are_legal():
    for num_bets in (2, 3, 4, 5):
        bets, _ = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, num_bets)
        assert len(bets) == num_bets
        for bet in bets:
            numbers = bet['numbers']
            assert len(numbers) == 6, f"each BIG_LOTTO ticket must have 6 numbers, got {numbers}"
            assert len(set(numbers)) == 6, f"ticket numbers must be unique, got {numbers}"
            assert all(1 <= n <= 49 for n in numbers), f"ticket numbers must be in 1..49, got {numbers}"


def test_4bet_is_prefix_of_5bet_family():
    bets4, strategy4 = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, 4)
    bets5, strategy5 = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, 5)
    assert bets4 == bets5[:4], "4-bet must remain exactly the first four tickets of the current 5-bet family"
    assert strategy4 == 'TS3+Markov(w=30)'
    assert strategy5 == 'TS3+Markov+FreqOrt'


def test_generator_functions_untouched_by_history_loader_change():
    """The 5-bet family's own generator function, called directly (bypassing
    load_history entirely), still returns 5 legal, non-overlapping tickets —
    proving the ticket math itself is independent of the loader change."""
    bets = quick_predict.biglotto_5bet_orthogonal(FIXTURE_HISTORY)
    assert len(bets) == 5
    seen = set()
    for bet in bets:
        seen.update(bet['numbers'])
    assert len(seen) == 30, "5 orthogonal bets of 6 unique numbers each must cover 30 distinct numbers"


# ---------------------------------------------------------------------------
# 12.4 — unsupported significance claims removed; conservative metadata present
# ---------------------------------------------------------------------------

FORBIDDEN_SUBSTRINGS = ['z=2.40', 'P3 p=0.030', '★最佳']


def _strategy_info_strings(info):
    return [str(v) for v in info.values()]


@pytest.mark.parametrize("num_bets", [4, 5])
def test_metadata_contains_no_unsupported_claims(num_bets):
    info = quick_predict.STRATEGY_INFO['BIG_LOTTO'][num_bets]
    values = _strategy_info_strings(info)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert not any(forbidden in v for v in values), (
            f"{num_bets}-bet strategy_info still contains unsupported claim '{forbidden}': {info}"
        )


@pytest.mark.parametrize("num_bets", [4, 5])
def test_metadata_has_conservative_evidence_status(num_bets):
    info = quick_predict.STRATEGY_INFO['BIG_LOTTO'][num_bets]
    assert info['evidence_status'] == 'HISTORICAL_RESEARCH_ONLY'
    assert info['current_significance'] == 'NOT_ESTABLISHED'
    assert 'No reliable predictive advantage is currently established.' in info['warning']


@pytest.mark.parametrize("num_bets", [2, 3, 4, 5])
def test_metadata_has_implementation_identity(num_bets):
    info = quick_predict.STRATEGY_INFO['BIG_LOTTO'][num_bets]
    assert isinstance(info.get('implementation_id'), str) and info['implementation_id']


def test_4bet_5bet_share_implementation_family():
    id4 = quick_predict.STRATEGY_INFO['BIG_LOTTO'][4]['implementation_id']
    id5 = quick_predict.STRATEGY_INFO['BIG_LOTTO'][5]['implementation_id']
    assert id4.split('.')[0] == id5.split('.')[0] == 'biglotto_5bet_orthogonal', (
        "4-bet and 5-bet implementation_id must show they derive from the same current family"
    )


def test_build_prediction_summary_carries_conservative_metadata():
    bets, strategy = quick_predict.predict_biglotto(FIXTURE_HISTORY, RULES, 5)
    summary = quick_predict.build_prediction_summary('BIG_LOTTO', bets, strategy, FIXTURE_HISTORY, 5)
    info = summary['strategy_info']
    assert info['evidence_status'] == 'HISTORICAL_RESEARCH_ONLY'
    assert info['current_significance'] == 'NOT_ESTABLISHED'
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in str(summary)
