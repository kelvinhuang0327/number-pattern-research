# P335A — Implementation Plan (as executed)

## Objective

Smallest safe code change preventing **future** POWER_LOTTO
prediction-generation paths from persisting `predicted_special = None` when a
real prediction-time second-zone value can be produced. No DB write, no
backfill, no prediction, no pipeline resume.

## Scope decision (given origin/main reality)

At `origin/main` (`ce2c042`):
- Generation-A wave scripts (`p48/p58/p59`) already emit `predicted_special` — no fix needed.
- The Generation-B apply scripts P334A named (`p132…p141`) are **not on origin/main** (side-branch only) — nothing to un-hardcode here.
- The one in-tree Generation-B POWER path (Tier-B `p93_tierb_replay_adapters.py`) is `DRY_RUN`/`production_eligible=False` and content-phrase-guarded — **not modified** (out of scope, risky, no active benefit).
- `tools/quick_predict.py` already computes a real value via `PowerLottoSpecialPredictor` and only prints it (stdout tool, zero DB writes).
- The persistence pipeline is **dormant** (no POWER row since 2026-05-29); resume is out of scope.

Therefore the smallest change that actually satisfies the goal is to add the
**single canonical building block + a reusable null-guard + a guard test** that
every future row-builder must use — the "one function, one call-site" mandate
from P334A design §4/§5. This is additive only (2 new files, 0 modifications).

## Deliverables (Option 1, per P334A)

1. **`lottery_api/models/power_lotto_second_zone.py`** (new)
   - `second_zone_predict(history) -> int`:
     - Reuses the live fused model `PowerLottoSpecialPredictor`
       (`special_predictor.py`) — same model as `power_special_v3()`.
     - Frequency fallback (same family as `power_special_v3()`'s `except` and the
       Generation-A `_special_predict()`) only if the fused model can't run —
       never returns NULL for sufficient history.
     - Raises `InsufficientHistoryError` when `history` is not a list or has
       `< MIN_HISTORY (=30)` draws — mirrors `_P47BaseAdapter` min-history guard
       (raise, not silent default). Deterministic (no RNG).
   - `assert_power_lotto_predicted_special(row)`:
     - Fail-fast null-guard for future row-builders (design §5). Raises if a
       POWER_LOTTO, non-dry-run row has NULL/out-of-range `predicted_special`;
       no-ops for DAILY_539/BIG_LOTTO and dry-run rows.
   - Explicit forward-only docstrings: must not be used to backfill the 27,104
     historical NULL rows.

2. **`tests/test_p335a_power_lotto_second_zone_forward_wiring.py`** (new)
   - Pure unit tests (synthetic history, **no DB**): non-null in-range output,
     determinism, raise-on-insufficient, fallback path, guard behavior, and an
     end-to-end "row-builder wired through the helper is never NULL" +
     "old Generation-B `None` literal now fails the guard".

## Explicit non-goals (forbidden / out of scope)

No DB write/migration/checkpoint/restore; no backfill of historical rows; no
generated numbers / betting / prediction claim; no roadmap/governance edits; no
broad refactor; no Tier-B adapter edit; no dormant-pipeline resume; no push.

## Reuse / dependency note

No new algorithm invented; no new third-party dependency added. Reuses in-repo
`PowerLottoSpecialPredictor` (+ `MarkovChain2ndOrderPredictor`) and stdlib
`collections.Counter`. Test runtime uses the repo venv (`pytest 9.0.3`, `numpy
2.4.4`, Python 3.14.4) — no dependency change.
