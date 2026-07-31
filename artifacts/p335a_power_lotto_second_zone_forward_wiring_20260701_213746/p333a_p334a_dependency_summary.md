# P335A — P333A / P334A Dependency Summary

Both predecessor evidence roots were read in full before any code was written.

## P333A (prize-aware success reconciliation audit, read-only)

- Established POWER_LOTTO `predicted_special` coverage = **9,000 / 36,104 = 24.928%**;
  full-population POWER prize-aware scoring `BLOCKED_BY_MISSING_FIELD`.
- 4 strategies had `NO_SECOND_ZONE_SUPPORT`; canonical DB SHA `9956c3bc…` (unchanged).

## P334A (second-zone coverage feasibility, read-only)

Root cause of the 27,104 NULL rows is **generation-code omission**, not schema,
not canonical view, not artifact export. Three sub-patterns:

- **Pattern 1** (17,603 rows): 4 strategies (`fourier_rhythm_3bet`,
  `power_fourier_rhythm_2bet`, `power_precision_3bet`, `power_orthogonal_5bet`)
  never wired to any second-zone model.
- **Pattern 2** (7,500 rows): `midfreq_fourier_mk_3bet` + `pp3_freqort_4bet` had a
  real bet-1 second zone (Generation-A) but lost it in multi-bet extensions.
- **Pattern 3** (2,001 rows): Tier-B P94, a 1-row draw-ext, and 100 legacy rows.

Key design guidance adopted for P335A:

- **Option 1 (recommended):** one canonical `second_zone_predict(history)`
  reusing the **already-live** `PowerLottoSpecialPredictor`
  (`tools/quick_predict.py::power_special_v3()`), called by every future
  POWER_LOTTO row-builder — "one function, one call-site pattern" so the
  Generation-A/B divergence cannot recur.
- **Guard test** (design §5): any future POWER_LOTTO row inserted with
  `dry_run=0` must fail a test/assertion if `predicted_special IS NULL`.
- **No backfill** of the 27,104 existing NULL rows (design §6, no_backfill_policy.md).
- **BLOCKER-2:** no live POWER_LOTTO persistence pipeline has produced any row
  since 2026-05-29; resuming it is a separate, separately-authorized task.

## What P335A verified independently against `origin/main` (ce2c042)

P334A's prose named apply scripts `p132/p133/p134/p140/p141_apply_*.py` as the
Generation-B row-builders hardcoding `"predicted_special": None`. **P335A
confirmed these files are NOT on `origin/main`** — they exist only on
side-branch `claude/zen-gates-ff6802` (commit `436b2ca`, not an ancestor of
`origin/main`). Therefore:

- There is no in-tree one-shot apply script to "un-hardcode" on `origin/main`.
- The only in-tree Generation-B POWER path is the **Tier-B** dry-run adapter
  `lottery_api/models/p93_tierb_replay_adapters.py`
  (`PowerFourierRhythm2BetAdapter`, documented "special not predicted in replay
  v0.1"), which is `DRY_RUN` / `production_eligible=False` and guarded by a
  content-phrase test (`test_p93_..._bootstrap_dryrun.py`) — deliberately **not
  modified** (out of scope, risk without benefit).

This is why P335A ships the **reusable canonical helper + guard** (the single
source of truth every future row-builder must call) rather than editing
non-existent or frozen dry-run scripts. See `implementation_plan.md`.
