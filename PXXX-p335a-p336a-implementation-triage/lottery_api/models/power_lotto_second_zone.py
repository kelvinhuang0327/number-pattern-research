"""
power_lotto_second_zone.py
==========================
P335A — Canonical POWER_LOTTO second-zone (special) prediction helper.

Single source of truth for producing a prediction-time second-zone value when
generating POWER_LOTTO ``strategy_prediction_replays`` rows. Every *future*
POWER_LOTTO row-builder MUST obtain ``predicted_special`` from
``second_zone_predict()`` (and/or call ``assert_power_lotto_predicted_special()``
before persisting) instead of hardcoding ``"predicted_special": None``.

Why this module exists (P333A / P334A read-only audits, origin/main ce2c042):
  - 27,104 / 36,104 historical POWER_LOTTO replay rows carry
    ``predicted_special = NULL`` because "Generation-B" multi-bet row-builders
    hardcoded ``None`` while a real second-zone model already existed and was
    used by "Generation-A" wave adapters (the 9,000 populated rows).
  - Centralising the second-zone call here means the Generation-A/Generation-B
    divergence (two code paths, only one of which produced a value) cannot
    recur: there is now exactly one function to call.

FORWARD-ONLY (hard boundary — see P334A no_backfill_policy.md):
  - This helper is for NEW rows generated after the fix ships.
  - It must NOT be run against the 27,104 existing NULL rows' historical
    ``history_cutoff_draw`` to "fill them in" — that would be retroactive
    inference dressed as a prediction-time record, which every prior POWER
    audit in this repo forbids.

Reuse (no new algorithm is invented here — see repo CLAUDE.md "Simplicity First"):
  - Primary model: ``PowerLottoSpecialPredictor``
    (``lottery_api/models/special_predictor.py``) — the multi-strategy fused
    model (frequency + 2nd-order Markov) already live in
    ``tools/quick_predict.py::power_special_v3()`` on every human prediction.
  - Fallback: recent-second-zone frequency count — the same model family as
    ``power_special_v3()``'s own ``except`` fallback and the Generation-A
    ``_special_predict()`` frequency mean-reversion model.

Determinism: given identical ``history`` the returned value is deterministic
(no RNG on the prediction path), satisfying the repo's reproducibility rule.

NOT a prediction claim / NOT a betting recommendation: this returns one
second-zone integer purely so replay-row generation records a non-NULL
prediction-time value. It makes no claim of predictive edge — prior POWER
second-zone findings remain negative and are unchanged by this coverage fix.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

# POWER_LOTTO second-zone (special) pool is 1..8.
SPECIAL_MIN = 1
SPECIAL_MAX = 8

# Minimum causal history required before a second-zone value may be produced.
# Mirrors the most-demanding Generation-A wave-4 guard: the Markov-based
# adapter's ``min_history == _MARKOV_WINDOW == 30`` in
# ``p47_wave4_powerlotto_adapters.py``. The helper RAISES below this threshold
# rather than silently defaulting (P334A forward_only_second_zone_design.md §4).
MIN_HISTORY = 30

# Rules dict shape expected by ``PowerLottoSpecialPredictor.__init__`` — matches
# the literal used by ``tools/quick_predict.py::power_special_v3()``.
_POWER_LOTTO_RULES: Dict = {
    "name": "POWER_LOTTO",
    "specialMinNumber": SPECIAL_MIN,
    "specialMaxNumber": SPECIAL_MAX,
}


class InsufficientHistoryError(ValueError):
    """Raised when ``history`` is too short to produce a second-zone value.

    Mirrors the ``min_history`` guard in ``_P47BaseAdapter.get_one_bet``: the
    helper raises rather than silently defaulting, so a caller can never
    accidentally persist a value fabricated from empty/short history.
    """


def _frequency_fallback(history: List[Dict]) -> int:
    """Most-common recent in-range second-zone value.

    Identical family to ``tools/quick_predict.py::power_special_v3()``'s
    fallback and the Generation-A ``_special_predict()`` frequency model.
    Deterministic: ``Counter.most_common`` breaks ties by first-seen order over
    a fixed, most-recent slice.
    """
    freq: Counter = Counter()
    for draw in history[-50:]:
        special = draw.get("special")
        if isinstance(special, int) and SPECIAL_MIN <= special <= SPECIAL_MAX:
            freq[special] += 1
    if freq:
        return int(freq.most_common(1)[0][0])
    # No usable specials in the slice: use the long-term modal POWER ball (2)
    # rather than 0/None, preserving the "never NULL for sufficient history"
    # contract. This is a fixed prior, not a per-row inference.
    return 2


def second_zone_predict(history: List[Dict]) -> int:
    """Return a real, deterministic prediction-time POWER_LOTTO second-zone
    (special) value in ``[1, 8]``, given only draws strictly before the target.

    Reuses the live ``PowerLottoSpecialPredictor`` fused model; degrades to a
    recent-frequency count only if that model cannot be imported/executed, so
    the function never returns NULL for sufficient history.

    Raises ``InsufficientHistoryError`` when ``history`` is not a list or has
    fewer than ``MIN_HISTORY`` draws — it never fabricates a value from
    empty/short history.
    """
    if not isinstance(history, list) or len(history) < MIN_HISTORY:
        got = len(history) if isinstance(history, list) else type(history).__name__
        raise InsufficientHistoryError(
            f"second_zone_predict needs >= {MIN_HISTORY} draws, got {got}"
        )

    try:
        from .special_predictor import PowerLottoSpecialPredictor

        predictor = PowerLottoSpecialPredictor(_POWER_LOTTO_RULES)
        value = int(predictor.predict(history))
    except Exception:
        # Import/exec failure of the fused model — degrade to the frequency
        # model rather than persist NULL. Mirrors power_special_v3()'s except.
        value = _frequency_fallback(history)

    if not (SPECIAL_MIN <= value <= SPECIAL_MAX):
        # An out-of-range model result is a bug, not a NULL-policy case:
        # surface it loudly rather than silently clamping/persisting.
        raise ValueError(
            f"second_zone_predict produced out-of-range value {value!r}; "
            f"expected [{SPECIAL_MIN}, {SPECIAL_MAX}]"
        )
    return value


def assert_power_lotto_predicted_special(row: Dict) -> None:
    """Fail-fast null-guard for POWER_LOTTO replay-row builders.

    Any *future* code path that builds a POWER_LOTTO
    ``strategy_prediction_replays`` row for real persistence (``dry_run``
    falsy) should call this immediately before insert. It raises if
    ``predicted_special`` is NULL or out of ``[1, 8]`` — the single cheapest
    control that would have caught the Generation-B regression at the time it
    was introduced (P334A forward_only_second_zone_design.md §5).

    No-ops for non-POWER_LOTTO rows (DAILY_539 / BIG_LOTTO legitimately carry a
    NULL second zone) and for dry-run rows.

    Forward-only: this guard is for NEWLY built rows. It must not be run
    against, or used to "repair", the 27,104 existing historical NULL rows.
    """
    if row.get("lottery_type") != "POWER_LOTTO":
        return
    if row.get("dry_run"):
        return
    value = row.get("predicted_special")
    if value is None:
        raise ValueError(
            "POWER_LOTTO production replay row has NULL predicted_special; "
            "row-builders must set it from second_zone_predict(history) "
            "(P335A forward-wiring null-guard)."
        )
    if not (isinstance(value, int) and SPECIAL_MIN <= value <= SPECIAL_MAX):
        raise ValueError(
            f"POWER_LOTTO predicted_special {value!r} out of "
            f"[{SPECIAL_MIN}, {SPECIAL_MAX}]"
        )
