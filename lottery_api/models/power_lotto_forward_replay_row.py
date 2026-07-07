"""
power_lotto_forward_replay_row.py
=================================
P336A — ONE forward POWER_LOTTO replay-row generation path, wired to the P335A
canonical second-zone helper.

This module defines the single, isolated, forward-only row-builder that a
(separately-authorized) POWER_LOTTO pipeline-resume calls to produce a NEW
``strategy_prediction_replays`` row whose ``predicted_special`` is a real,
non-NULL prediction-time value obtained from
``lottery_api.models.power_lotto_second_zone.second_zone_predict`` — the P335A
canonical helper (which reuses the already-live ``PowerLottoSpecialPredictor``).

Why this is a NEW module rather than an edit of an existing path
---------------------------------------------------------------
P333A/P334A/P335A established that on ``origin/main`` (ce2c042):
  - Generation-A wave builders (``p47_wave4_powerlotto_adapters.generate_dryrun_rows``)
    already emit a ``predicted_special`` — but via a *local* ``_special_predict``
    frequency model, and that same function is imported by the **production
    apply** script ``scripts/p48_powerlotto_wave4_production_apply.py`` and by 6+
    test modules. Editing it in place would change the p48 production lineage and
    risk breaking those tests — i.e. NOT the smallest *safe* path.
  - The Generation-B multi-bet builders that hardcoded ``predicted_special=None``
    (p132…p141) are **not on origin/main** (side-branch only); the sole in-tree
    Generation-B path (Tier-B ``p93``) is frozen ``DRY_RUN``.
  - No POWER_LOTTO replay row has been persisted since 2026-05-29 (dormant
    pipeline / BLOCKER-2).

So the smallest *safe* forward step is an additive, isolated builder that:
  - sources the second zone from the P335A helper (never NULL for sufficient
    history; RAISES for insufficient history — no silent default), and
  - runs the P335A fail-fast NULL guard at the output boundary,
with **zero** modification to the p47/p48/p56 lineage or their tests.

Hard boundaries (see P334A no_backfill_policy / P335A docstrings)
-----------------------------------------------------------------
  - FORWARD-ONLY: builds a NEW row for a target draw from strictly-causal
    history. It MUST NOT be used to "fill in" the 27,104 existing historical
    NULL rows — that would be retroactive inference dressed as a prediction-time
    record, which every prior POWER audit forbids.
  - NO DB WRITE: this function returns a row dict only. It never opens, reads, or
    writes any database. Persisting the row is a separate, separately-authorized
    step that is deliberately out of P336A scope.
  - NOT a prediction / betting claim: the second zone exists only so the replay
    row records a non-NULL prediction-time value. Prior POWER second-zone
    findings remain negative and are unchanged by this coverage plumbing. No
    numbers are recommended and no bet is advised.

Determinism: given identical ``history`` and ``predicted_numbers`` the returned
row's prediction fields (``predicted_numbers`` / ``predicted_special``) are
deterministic. Only the ``prediction_generated_at`` wall-clock stamp varies, as
in the Generation-A ``generate_dryrun_rows`` it mirrors.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .power_lotto_second_zone import (
    InsufficientHistoryError,  # re-exported so callers catch it from one place
    SPECIAL_MAX,
    SPECIAL_MIN,
    assert_power_lotto_predicted_special,
    second_zone_predict,
)

__all__ = [
    "FIRST_ZONE_POOL",
    "FIRST_ZONE_PICK",
    "SPECIAL_MIN",
    "SPECIAL_MAX",
    "InsufficientHistoryError",
    "build_power_lotto_forward_replay_row",
]

# POWER_LOTTO first zone: pick 6 distinct numbers from 1..38.
FIRST_ZONE_POOL = 38
FIRST_ZONE_PICK = 6


def _validate_first_zone(predicted_numbers: List[int]) -> List[int]:
    """Validate first-zone numbers exactly as the Generation-A adapter does.

    Mirrors ``_P47BaseAdapter.get_one_bet``'s asserts: 6 distinct ints in
    ``[1, 38]``. Raises ``ValueError`` (not ``AssertionError``) so callers get a
    stable, catchable failure at the row-build boundary.
    """
    if not isinstance(predicted_numbers, (list, tuple)):
        raise ValueError(
            f"predicted_numbers must be a list of {FIRST_ZONE_PICK} ints, "
            f"got {type(predicted_numbers).__name__}"
        )
    nums = list(predicted_numbers)
    if len(nums) != FIRST_ZONE_PICK:
        raise ValueError(
            f"predicted_numbers must have {FIRST_ZONE_PICK} numbers, got {len(nums)}"
        )
    if not all(isinstance(n, int) and 1 <= n <= FIRST_ZONE_POOL for n in nums):
        raise ValueError(
            f"predicted_numbers must be ints in [1, {FIRST_ZONE_POOL}]: {nums}"
        )
    if len(set(nums)) != FIRST_ZONE_PICK:
        raise ValueError(f"predicted_numbers must be distinct: {nums}")
    return sorted(nums)


def build_power_lotto_forward_replay_row(
    *,
    strategy_id: str,
    target_draw_id: str,
    history: List[Dict],
    predicted_numbers: List[int],
    strategy_name: Optional[str] = None,
    strategy_version: Optional[str] = None,
    target_draw_date: Optional[str] = None,
    dry_run: bool = False,
) -> Dict:
    """Build ONE forward POWER_LOTTO ``strategy_prediction_replays`` row with a
    non-NULL ``predicted_special`` sourced from the P335A canonical helper.

    The first zone (``predicted_numbers``) is supplied by the caller from any
    existing first-zone predictor (e.g. a p47 Wave-4 ``predict_*_bet1``) — this
    builder invents no algorithm; its sole job is to attach a real second zone
    and guard the row so the Generation-B NULL regression cannot recur.

    Parameters
    ----------
    strategy_id:
        Strategy identifier for the row (e.g. ``"midfreq_fourier_mk_3bet"``).
    target_draw_id:
        The draw being predicted. The row is *forward*: the target's actual
        result is unknown at prediction time, so ``actual_*``/``hit_*`` are left
        ``None`` and ``replay_status`` is ``"PREDICTED"`` (to be resolved later).
    history:
        Strictly-causal draws BEFORE the target (same list-of-dict shape the
        P335A helper expects; each draw carries a ``"special"``). Must contain at
        least ``power_lotto_second_zone.MIN_HISTORY`` (30) draws.
    predicted_numbers:
        6 distinct ints in ``[1, 38]`` — the first-zone bet from an existing
        predictor.
    dry_run:
        If truthy, marks the row a rehearsal (the P335A guard then no-ops). The
        default is ``False`` so the guard *enforces* a non-NULL second zone.

    Returns
    -------
    dict
        A canonical POWER_LOTTO replay row (never persisted here).

    Raises
    ------
    InsufficientHistoryError
        If ``history`` has fewer than ``MIN_HISTORY`` draws — the builder fails
        fast instead of persisting a fabricated/NULL second zone.
    ValueError
        If ``predicted_numbers`` is not 6 distinct ints in ``[1, 38]``, or if the
        assembled row somehow fails the P335A NULL guard.
    """
    numbers = _validate_first_zone(predicted_numbers)

    # Second zone from the single canonical helper. This RAISES
    # InsufficientHistoryError for < MIN_HISTORY draws, so the only way past this
    # line is with a real, in-range [1, 8] value — never NULL, never a silent
    # default. This is the exact wiring P334A §4 / P335A mandated.
    predicted_special = second_zone_predict(history)

    now_str = datetime.now(timezone.utc).isoformat()
    row: Dict = {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "lottery_type": "POWER_LOTTO",
        "target_draw": str(target_draw_id),
        "draw_date": target_draw_date,
        "prediction_cutoff_date": history[-1].get("date") if history else None,
        "prediction_generated_at": now_str,
        "history_cutoff_draw": str(history[-1]["draw"]) if history else None,
        "predicted_numbers": numbers,            # 6 ints [1..38]
        "predicted_special": predicted_special,  # 1 int [1..8], NON-NULL
        # Forward row: the target's outcome is unknown at prediction time.
        "actual_numbers": None,
        "actual_special": None,
        "hit_numbers": None,
        "hit_count": None,                       # unscored until resolution
        "special_hit": None,                     # unscored until resolution
        "replay_status": "PREDICTED",
        "reject_reason": None,
        "dry_run": int(bool(dry_run)),
    }

    # Fail-fast NULL guard at the output/persistence boundary (P335A guard §5).
    # For dry_run falsy rows this raises if predicted_special is ever NULL or
    # out of [1, 8]; it is the cheapest control that would have caught the
    # Generation-B regression at introduction time.
    assert_power_lotto_predicted_special(row)
    return row
