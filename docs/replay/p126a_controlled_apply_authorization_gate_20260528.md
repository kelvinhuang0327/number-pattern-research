# P126A: Per-Strategy Controlled Apply Authorization Gate

**Generated:** 2026-05-28T08:08:06.753937+00:00  
**Classification:** `P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION`  
**Production DB rows (before/after):** 54462 / 54462 (no change — no apply executed)  

---

## 1. Executive Summary

P126A establishes the per-strategy authorization gate for the 5 Tier-B controlled-apply
candidates identified in P126 dry-run. This script is **read-only** — it performs no INSERT,
no replay row additions, and no strategy promotion. The gate is `WAITING` because no
per-strategy exact authorization phrase has been provided in this run.

Each of the 5 strategies requires an independent authorization phrase from Kelvin before
its apply can proceed. Strategies cannot be applied in bulk with a single authorization.

---

## 2. P129B Migration Recap

- **Classification:** `P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED`
- **Migration applied:** True
- **Backup OK:** True
- **Rows after migration:** 54462
- **bet_index column present:** True
- **What changed:** `bet_index INTEGER NOT NULL DEFAULT 1` column added; `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)` replaces old `replay_run_id`-based constraint.
- **ROW_NUMBER() COPY used:** Correct — 120 duplicate old-run groups assigned bet_index 1/2/3.

---

## 3. P126 Dry-Run Recap

- **Classification:** `P126_DRY_RUN_PLAN_READY`
- **Candidates:** 5 strategies
- **Total rows if all applied:** +18000 (→ 72462 total)
- **Provenance guard:** All 5 candidates from trusted P94 source.
- **Duplicate guard:** All 5 candidates had 0 duplicate draws at P126 time.
- **P128 storage design:** One-row-per-bet formally accepted; P129B schema migration applied.

---

## 4. Why Per-Strategy Authorization Is Required

Each strategy carry independent risk profiles and evidence levels:

| Strategy | Quality | Risk | New Rows |
|---|---|---|---:|
| `power_fourier_rhythm_2bet` | +1500 rows, 2-bet, POWER_LOTTO — smallest delta, lowest risk | lowest | +1500 |
| `biglotto_echo_aware_3bet` | +3000 rows, 3-bet, BIG_LOTTO — fallback_equivalent quality | low_to_medium | +3000 |
| `daily539_f4cold_3bet` | +3000 rows, 3-bet, DAILY_539 — watchlist quality | medium | +3000 |
| `biglotto_ts3_markov_4bet_w30` | +4500 rows, 4-bet, BIG_LOTTO — sub_baseline quality | medium | +4500 |
| `daily539_f4cold_5bet` | +6000 rows, 5-bet, DAILY_539 — watchlist quality, largest delta | medium | +6000 |

One authorization applies to one strategy only. If a single phrase authorized all five,
Kelvin would have no mechanism to approve strategies incrementally based on confidence.
P126 dry-run already established that each candidate needs its own `explicit_apply_authorization`.

---

## 5. Five Strategy Authorization Gates

### Gate 1: `power_fourier_rhythm_2bet`

- **Lottery type:** POWER_LOTTO
- **Target bet count:** 2
- **Expected insert rows:** +1500
- **Missing bet indices:** [2]
- **Risk:** lowest — +1500 rows, 2-bet, POWER_LOTTO — smallest delta, lowest risk
- **Authorization present:** False
- **Apply allowed:** False
- **Required phrase:** `YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>`

### Gate 2: `biglotto_echo_aware_3bet`

- **Lottery type:** BIG_LOTTO
- **Target bet count:** 3
- **Expected insert rows:** +3000
- **Missing bet indices:** [2, 3]
- **Risk:** low_to_medium — +3000 rows, 3-bet, BIG_LOTTO — fallback_equivalent quality
- **Authorization present:** False
- **Apply allowed:** False
- **Required phrase:** `YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>`

### Gate 3: `daily539_f4cold_3bet`

- **Lottery type:** DAILY_539
- **Target bet count:** 3
- **Expected insert rows:** +3000
- **Missing bet indices:** [2, 3]
- **Risk:** medium — +3000 rows, 3-bet, DAILY_539 — watchlist quality
- **Authorization present:** False
- **Apply allowed:** False
- **Required phrase:** `YES authorize controlled_apply for daily539_f4cold_3bet because <reason>`

### Gate 4: `biglotto_ts3_markov_4bet_w30`

- **Lottery type:** BIG_LOTTO
- **Target bet count:** 4
- **Expected insert rows:** +4500
- **Missing bet indices:** [2, 3, 4]
- **Risk:** medium — +4500 rows, 4-bet, BIG_LOTTO — sub_baseline quality
- **Authorization present:** False
- **Apply allowed:** False
- **Required phrase:** `YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>`

### Gate 5: `daily539_f4cold_5bet`

- **Lottery type:** DAILY_539
- **Target bet count:** 5
- **Expected insert rows:** +6000
- **Missing bet indices:** [2, 3, 4, 5]
- **Risk:** medium — +6000 rows, 5-bet, DAILY_539 — watchlist quality, largest delta
- **Authorization present:** False
- **Apply allowed:** False
- **Required phrase:** `YES authorize controlled_apply for daily539_f4cold_5bet because <reason>`

---

## 6. Recommended Apply Order

Start with the lowest-risk, smallest row-count strategy:

| Order | Strategy | Lottery | New Rows | Risk |
|---:|---|---|---:|---|
| 1 | `power_fourier_rhythm_2bet` | POWER_LOTTO | +1500 | lowest |
| 2 | `biglotto_echo_aware_3bet` | BIG_LOTTO | +3000 | low_to_medium |
| 3 | `daily539_f4cold_3bet` | DAILY_539 | +3000 | medium |
| 4 | `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | +4500 | medium |
| 5 | `daily539_f4cold_5bet` | DAILY_539 | +6000 | medium |

Each apply task should be independent. Verify drift guard after each strategy's apply.
Update drift guard expected row count before moving to the next strategy.

---

## 7. Duplicate Guard and Preconditions

**Unique key:** `['lottery_type', 'target_draw', 'strategy_id', 'bet_index']`  
**Constraint active:** `True`  

The UNIQUE(lottery_type, target_draw, strategy_id, bet_index) constraint is now active in the production schema (applied by P129B). Any multi-bet apply INSERT must supply bet_index 2, 3, ... for new rows; inserting bet_index=1 for an existing (strategy, draw) pair will be rejected by the constraint.

**Apply preconditions (all must PASS before any strategy apply):**

- `p129b_schema_migrated`: **PASS** — P129B classification = P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED
- `bet_index_column_present`: **PASS** — bet_index column in production DB: True
- `unique_constraint_ready`: **PASS** — UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active
- `db_invariant_confirmed`: **PASS** — replay_rows = 54462 (expected 54462)
- `backup_exists`: **PASS** — Backup created by P129B: /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/backups/lottery_v2.db.p129b_backup_20260528T080035Z.db
- `drift_guard_pass`: **REQUIRED** — Run scripts/replay_lifecycle_drift_guard.py before any apply. Must return PASS.
- `strategy_specific_authorization`: **REQUIRED** — Each strategy requires its own exact authorization phrase from Kelvin before apply.
- `staging_whitelist_clean`: **REQUIRED** — git diff --cached --name-only must contain only whitelisted files before apply.

---

## 8. Known Obsolete / Pre-Existing Regression Failures After Schema Migration

The following test failures are **not caused by P126A**. They are pre-existing or obsolete guards:

**`tests/test_p129a_production_migration_authorization_gate.py`** — KNOWN_OBSOLETE:
  - `TestProductionDBRows::test_live_no_bet_index_column`
  - `TestIdempotency::test_script_reruns_cleanly`
  *Reason: Pre-migration guard — expected 'no bet_index column'; now obsolete after P129B applied migration.*

**`tests/test_p129_bet_index_schema_migration_rehearsal.py`** — KNOWN_OBSOLETE:
  - `TestProductionDBRows::test_production_no_bet_index_column`
  - `TestIdempotency::test_script_reruns_cleanly`
  *Reason: Pre-migration guard — expected production DB without bet_index; now obsolete after P129B.*

**`tests/test_p128_native_multi_bet_storage_design.py`** — KNOWN_PRE_EXISTING:
  - `TestDBInvariantsLive::test_3star_count`
  - `TestDBInvariantsLive::test_4star_count`
  - `TestDBInvariantsLive::test_no_bet_index_column_currently`
  - `TestDBInvariantsLive::test_current_unique_constraint`
  - `TestIdempotency::test_script_reruns_cleanly`
  *Reason: Stale draw counts (3_STAR/4_STAR not present in this worktree DB) + obsolete bet_index guard.*

**`tests/test_p126_controlled_apply_plan_tier_b_multi_bet.py`** — KNOWN_PRE_EXISTING:
  - `TestDBInvariantsBeforeRun::test_3star_count`
  - `TestDBInvariantsBeforeRun::test_3star_max_draw`
  - `TestDBInvariantsBeforeRun::test_4star_count`
  - `TestDBInvariantsBeforeRun::test_4star_max_draw`
  - `TestIdempotency::test_script_reruns_cleanly`
  *Reason: Stale 3_STAR/4_STAR draw count expectations (worktree DB lacks canonical draw data).*

---

## 9. Explicit Non-Actions

This P126A task did **not**:

- **controlled_apply**: No apply executed in P126A — all 5 strategies waiting for per-strategy authorization
- **4_STAR**: Explicitly excluded from all Tier-B multi-bet work per governance
- **P108**: P108 execution blocked — 100-draw threshold not met
- **P117**: P117 execution blocked — POWER_LOTTO draw threshold not met
- **P118**: P118 execution blocked — exact authorization phrase absent
- **rejected_strategies**: No rejected strategies included or promoted
- **scheduler_cron_launchd**: No scheduler installation in P126A
- **lifecycle_champion_registry**: No strategy promotion / lifecycle / champion / registry mutation

---

## 10. Final Classification

```
P126A_WAITING_FOR_PER_STRATEGY_APPLY_AUTHORIZATION
```

**Strategies authorized:** 0 / 5  
**Strategies waiting:** 5 / 5  
**Apply executed:** False  
**Replay rows inserted:** 0  

To proceed, provide the exact per-strategy phrase for the desired strategy.
Recommended first: `power_fourier_rhythm_2bet` (+1500 rows, lowest risk).
