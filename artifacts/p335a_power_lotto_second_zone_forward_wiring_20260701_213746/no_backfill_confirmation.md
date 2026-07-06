# P335A — No-Backfill Confirmation

**Confirmed: no historical row was backfilled, mutated, or fabricated.**

## What was NOT done (all forbidden items honored)

- ❌ No write to the 27,104 existing NULL `predicted_special` POWER_LOTTO rows.
- ❌ No running of any model against a historical `history_cutoff_draw` to
  "recover" a value (that would be retroactive inference dressed as history —
  forbidden by P334A `no_backfill_policy.md`, P333A, P298A, P271G).
- ❌ No default/random/most-frequent fill of historical rows.
- ❌ No copying of `actual_special` into `predicted_special`.
- ❌ No DB write / migration / checkpoint / restore / backup-staging.

## Why the deliverable is structurally forward-only

- `second_zone_predict()` and `assert_power_lotto_predicted_special()` are pure
  functions with **no DB access** and **no historical-row iteration**. They
  cannot, by construction, touch existing rows.
- Both functions' docstrings state the forward-only boundary explicitly:
  "must NOT be run against the 27,104 existing NULL rows."
- `assert_power_lotto_predicted_special()` deliberately **no-ops on dry-run rows**
  and on non-POWER_LOTTO rows, and only *validates* (never writes) a
  newly-built row dict.

## Scope of "forward-only"

Consistent with P334A: only `strategy_prediction_replays` rows generated **after**
a future, separately-authorized pipeline-resume adopts this helper will carry a
real `predicted_special`. Every row existing as of 2026-07-01 remains excluded
from full prize-aware scoring under
`EXCLUSION_MISSING_PREDICTED_SECOND_ZONE`, exactly as
`lottery_api/prize_aware_replay_adapter.py` already handles it. P335A changes
none of that historical state.

## No prediction / betting / recommended-number claim

The helper returns a single integer purely so a *future* replay row records a
non-NULL prediction-time value. It makes **no** predictive-edge claim, produces
**no** recommended numbers, and gives **no** betting advice. Prior POWER
second-zone findings (negative after Bonferroni) are unchanged.
