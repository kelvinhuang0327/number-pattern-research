# P334A — Forward-Only Second-Zone Design (proposal, NOT implemented)

Design only. No code in this repo was changed to implement any of this.

## 1. Design goal

Every **new** `strategy_prediction_replays` row created for `lottery_type =
'POWER_LOTTO'`, from now on, must have a non-NULL, genuinely
prediction-time-computed `predicted_special`, regardless of which strategy
or which bet index produced the row. Historical rows are untouched (see
`no_backfill_policy.md`).

## 2. Building block that already exists (reuse, don't reinvent)

Two working second-zone models are already in the codebase:

1. `_special_predict(history, window=100)` — frequency mean-reversion,
   defined identically in `lottery_api/models/p47_wave4_powerlotto_adapters.py`
   and `lottery_api/models/p56_wave5_powerlotto_adapters.py`. Proven on
   9,000 real historical rows.
2. `PowerLottoSpecialPredictor` (`lottery_api/models/special_predictor.py`)
   — multi-strategy fusion (frequency + 2nd-order Markov via
   `MarkovChain2ndOrderPredictor`), already the **live, currently-used**
   model inside `tools/quick_predict.py`'s `power_special_v3()` /
   `predict_power()` — i.e. it is already what a human sees today when
   they run a POWER_LOTTO prediction. It is the natural forward-only choice
   because it is already the most current/maintained model, and adopting
   it does not require inventing a third model.

## 3. Where to wire it in (two independent gaps, both need closing)

### 3a. Any future multi-bet / batch-extension generation path

Any future script in the shape of the Generation-B family (`get_all_bets_*`
adapters + a row-builder) must call a canonical second-zone function once
per row and bind its result to `predicted_special`, instead of the literal
`None`. Concretely: replace

```python
"predicted_special": None,
```

with

```python
"predicted_special": second_zone_predict(history),
```

where `second_zone_predict` is a single, shared, canonical function (see
§4) — not a re-implementation per script. This closes Pattern 1 and
Pattern 2 from `predicted_special_gap_analysis.md` for all *future* rows of
the 4 previously-second-zone-blind strategies and all future multi-bet
extensions of the 2 strategies that briefly had it.

### 3b. Resuming a live/scheduled POWER_LOTTO persistence pipeline

Independently of 3a, `power_lotto_pipeline_inventory.md` §3 established
that **no** POWER_LOTTO row (main or second-zone) has been persisted into
`strategy_prediction_replays` since 2026-05-29 — there is currently no
live path at all. A forward-only second-zone fix is only meaningful once
*some* live path exists to create new POWER_LOTTO replay rows going
forward (analogous to whatever mechanism keeps DAILY_539/BIG_LOTTO rows
current, given their `MAX(target_draw)` is materially newer). Whatever
that resumed/rebuilt pipeline turns out to be, it must call the same
canonical `second_zone_predict()` function as part of its row-builder —
this is the single integration point that guarantees 3a and 3b share one
source of truth and cannot silently diverge again the way Generation A/B
did.

## 4. Proposed canonical function contract (design only)

```python
def second_zone_predict(history: list[dict]) -> int:
    """Return an int in [1, 8] — a real, deterministic, prediction-time
    second-zone (special) forecast for POWER_LOTTO, given only draws
    strictly before the target (no look-ahead).
    Must raise (not silently default) if `history` is insufficient,
    mirroring the existing min_history guard in _P47BaseAdapter.
    """
```

Implementation choice (recommend `PowerLottoSpecialPredictor`, since it is
already the live model — see §2) is a decision for the future
implementation task, not this audit. The important structural point is:
**one function, one call site pattern, reused by every POWER_LOTTO
row-builder**, so the Generation-A/Generation-B divergence cannot recur.

## 5. Guard test (mirrors the existing Policy-A pattern)

`tests/test_p48_powerlotto_special_null_policy.py` already established the
precedent of a null-policy guard test for `actual_special`. The future
implementation task should add an equivalent guard: any code path that
inserts a new `strategy_prediction_replays` row with `lottery_type =
'POWER_LOTTO'` and `dry_run = 0` must fail a test (or an assertion) if
`predicted_special IS NULL`. This is the single cheapest control that
would have caught the Generation-B regression at the time it was
introduced.

## 6. What this design explicitly does NOT do

- Does not touch any of the 27,104 existing NULL rows.
- Does not change `prize_aware_scorer.py`, `prize_aware_replay_adapter.py`,
  or any scoring logic — those already correctly treat NULL
  `predicted_special` as `EXCLUSION_MISSING_PREDICTED_SECOND_ZONE`
  (see `power_lotto_pipeline_inventory.md` for the adapter code).
- Does not create a POWER_LOTTO canonical source view (P298A's separate,
  independent blocker) — out of scope for this design.
- Does not generate, recommend, or publish any actual number.
