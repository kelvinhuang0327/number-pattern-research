# RSR-6 Orphan bet_index=2 Audit Report

**Task ID**: RSR6  
**Date**: 2026-05-28  
**Classification**: RSR6_ORPHAN_BET_INDEX2_AUDIT_READY  
**Branch**: `claude/zen-gates-ff6802`  
**HEAD at audit**: `8374df8`

---

## 1. Executive Summary

RSR-6 is the blocking condition that prevents `power_precision_3bet` (P10) and
`power_orthogonal_5bet` (P12) from advancing to `apply_ready` in the P128 Wave 2
pipeline. This audit formally identifies, characterizes, and recommends resolution
for 40 orphan `bet_index=2` rows (20 per strategy) that were written by a pre-P126
batch runner (`replay_run_id=6`, 2026-05-07) without `source`, `controlled_apply_id`,
or `provenance_hash`.

**Result**: Orphan rows are safe to delete under authorization. Each affected draw
already has a valid `bet_index=1` row from `replay_run_id=2`. Cleanup requires an
authorization phrase; this document does not execute the DELETE.

**DB row count**: 72,462 before = 72,462 after (no writes in RSR-6 audit).

---

## 2. P128 Phase 2 Recap

P128 Phase 2 (committed `8374df8`) implemented 6 `get_all_bets()` adapters for
priority 7-12. RSR-6 was identified as the blocker for P10 and P12:

| Priority | Strategy ID | Bet Count | RSR-6 Status |
|----------|-------------|-----------|--------------|
| P7 | `acb_markov_midfreq_3bet` | 3 | Not affected |
| P8 | `midfreq_fourier_mk_3bet` | 3 | Not affected |
| P9 | `fourier_rhythm_3bet` | 3 | Not affected (RSR-7 noted, lower priority) |
| **P10** | `power_precision_3bet` | **3** | **RSR-6 BLOCKED** |
| P11 | `pp3_freqort_4bet` | 4 | Not affected |
| **P12** | `power_orthogonal_5bet` | **5** | **RSR-6 BLOCKED** |

---

## 3. Why RSR-6 Is Required Before P10/P12 Apply

When `controlled_apply` writes a multi-bet strategy's predictions, it inserts rows
for each bet slot (`bet_index = 1, 2, 3, …`). If orphan rows already occupy a
`(strategy_id, target_draw, bet_index)` slot, the INSERT will collide (UNIQUE
constraint violation or duplicate data).

For draws `99000085–99000104`, `power_precision_3bet` and `power_orthogonal_5bet`
already have `bet_index=2` rows from `replay_run_id=6`. Any future adapter run
attempting to write `bet_index=2` predictions for those draws would conflict.

---

## 4. Orphan bet_index=2 Row Audit Table

All 40 orphan rows share:
- `bet_index = 2`
- `source = ''` (blank)
- `replay_run_id = 6`
- `controlled_apply_id = NULL`
- `provenance_hash = NULL`
- `truth_level = NULL`
- `dry_run = 0` (live rows)
- `generated_at ≈ 2026-05-07T08:54:18+00:00`

### power_precision_3bet orphan rows (20)

| target_draw | predicted_numbers |
|-------------|------------------|
| 99000085 | [1, 10, 17, 20, 35, 37] |
| 99000086 | [17, 20, 21, 25, 35, 36] |
| 99000087 | [11, 17, 19, 33, 37, 38] |
| 99000088 | [11, 19, 33, 34, 37, 38] |
| 99000089 | [9, 11, 15, 32, 34, 37] |
| 99000090 | [9, 13, 15, 25, 32, 34] |
| 99000091 | [9, 13, 15, 25, 33, 38] |
| 99000092 | [3, 6, 10, 18, 33, 38] |
| 99000093 | [1, 3, 6, 10, 16, 18] |
| 99000094 | [1, 11, 12, 16, 26, 37] |
| 99000095 | [1, 11, 12, 20, 29, 37] |
| 99000096 | [11, 12, 17, 24, 37, 38] |
| 99000097 | [7, 17, 24, 32, 33, 38] |
| 99000098 | [15, 17, 24, 32, 33, 38] |
| 99000099 | [15, 17, 24, 27, 32, 33] |
| 99000100 | [2, 11, 15, 25, 32, 33] |
| 99000101 | [2, 3, 10, 11, 15, 23] |
| 99000102 | [3, 10, 11, 23, 32, 38] |
| 99000103 | [3, 18, 23, 27, 32, 38] |
| 99000104 | [10, 12, 18, 27, 32, 38] |

### power_orthogonal_5bet orphan rows (20)

Identical `target_draw` range and same `predicted_numbers` pattern (same run).

---

## 5. Provenance / Source Audit

### replay_run_id=6 Scope

`replay_run_id=6` wrote the following rows for RSR-6 strategies:

| strategy_id | bet_index | count | draw range |
|-------------|-----------|-------|------------|
| power_precision_3bet | 1 | 30 | 99000055–99000084 |
| power_precision_3bet | **2** | **20** | **99000085–99000104** ← orphans |
| power_orthogonal_5bet | 1 | 30 | 99000055–99000084 |
| power_orthogonal_5bet | **2** | **20** | **99000085–99000104** ← orphans |

### Interpretation

`replay_run_id=6` was a pre-P126 batch run (2026-05-07). It wrote `bet_index=1` rows
for draws 99000055–99000084, then overflowed into `bet_index=2` for draws
99000085–99000104 — likely because the batch runner did not enforce the one-slot-per-bet
constraint. No `source`, `controlled_apply_id`, or `provenance_hash` was set.

**Subsequently**, `replay_run_id=2` wrote fresh `bet_index=1` rows for draws
99000085–99000104 (these are the valid canonical rows). As a result, each orphan draw
has a valid `bet_index=1` counterpart.

### bi=1 Coverage for Orphan Draws

| Strategy | bi=1 exists for orphan draws |
|----------|------------------------------|
| power_precision_3bet | ✓ 20/20 (replay_run_id=2) |
| power_orthogonal_5bet | ✓ 20/20 (replay_run_id=2) |

---

## 6. Resolution Options

### Option A — Quarantine Delete (Recommended)

Delete 40 orphan rows:
```sql
DELETE FROM strategy_prediction_replays
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
  AND bet_index = 2
  AND (source IS NULL OR source = '')
  AND replay_run_id = 6;
```

- **Risk**: LOW — all 20 affected draws have valid `bet_index=1` rows. No prediction
  coverage is lost.
- **Post-cleanup rows**: 72,422 (72,462 − 40)
- **Effect**: Unblocks apply gate for P10/P12.
- **Requires**: Authorization phrase (see Section 9).

### Option B — Tag as Legacy

Update `source='LEGACY_ORPHAN_RSR6'` and `controlled_apply_id='RSR6_QUARANTINE'`.
Does not delete rows. Apply gate remains blocked for `bet_index≥2` slots until legacy
rows reconciled.

- **Risk**: MEDIUM — future adapter runs may still collide on `bet_index=2` slots.

### Option C — Permanent Block

Keep rows indefinitely. Mark P10/P12 permanently unable to use multi-bet apply
(`bet_index≥2`). Only `bet_index=1` apply allowed.

- **Risk**: HIGH — discards 4-bet / 5-bet capability for these strategies.

---

## 7. Recommended Resolution

**Option A** — DELETE 40 orphan rows under authorization.

Rationale:
1. Each orphan draw already has a valid canonical `bet_index=1` row.
2. Orphan rows lack all provenance fields (source, controlled_apply_id, provenance_hash).
3. Orphan rows are from a pre-P126 batch runner that no longer exists in the pipeline.
4. Keeping them indefinitely risks UNIQUE constraint collisions in future apply runs.

---

## 8. Apply Gate Impact

| Strategy | Apply Ready? | Condition to Unlock |
|----------|-------------|---------------------|
| `power_precision_3bet` (P10) | **NO** | Execute Option A + drift guard PASS at 72,422 |
| `power_orthogonal_5bet` (P12) | **NO** | Execute Option A + drift guard PASS at 72,422 |
| `acb_markov_midfreq_3bet` (P7) | Not evaluated in RSR-6 | Not blocked by RSR-6 |
| `midfreq_fourier_mk_3bet` (P8) | Not evaluated in RSR-6 | Not blocked by RSR-6 |
| `fourier_rhythm_3bet` (P9) | Not evaluated in RSR-6 | Not blocked by RSR-6 |
| `pp3_freqort_4bet` (P11) | Not evaluated in RSR-6 | Not blocked by RSR-6 |

**Important**: P7/P8/P9/P11 are NOT blocked by RSR-6. Their apply readiness must be
evaluated separately in the next controlled_apply phase.

---

## 9. Required Authorization Phrase (If Cleanup Approved)

Before executing the DELETE, a human operator must present the following phrase:

```
RSR6_CLEANUP_AUTHORIZED_DELETE_40_ORPHAN_BET_INDEX2_ROWS_POWER_PRECISION_AND_ORTHOGONAL_20260528
```

**This RSR-6 audit does not execute the DELETE. No DB mutation has been performed.**

---

## 10. Explicit Non-Actions in This Audit

- ✗ No rows deleted, updated, or moved
- ✗ No `controlled_apply` executed
- ✗ No replay rows inserted
- ✗ No scheduler / cron / launchd installed
- ✗ No 4_STAR / P108 / P117 / P118 operations
- ✗ No strategy promotion / lifecycle / champion / registry mutation

---

## 11. Remaining Risks

1. **Apply gate blocked**: P10/P12 remain blocked until Option A is authorized and executed.
2. **UNIQUE collision risk**: If Option A is not executed and a future run tries to write
   `bet_index=2` rows for draws 99000085–99000104, UNIQUE constraint violations will occur.
3. **replay_run_id=6 documentation**: The pre-P126 batch that created these rows should
   be documented to prevent re-confusion in future audits.
4. **Drift guard row count**: After Option A, drift guard will report 72,422 rows.
   All downstream expected-row-count assertions must be updated to 72,422.

---

## 12. Next Recommended Task

**RSR6_CLEANUP_EXECUTION**: Obtain authorization phrase, execute Option A DELETE SQL,
re-run drift guard (must PASS at 72,422), update apply gate for P10/P12, then proceed to
P128 Phase 3 — `controlled_apply` for P7/P8/P9/P11 (not RSR-6 blocked).

---

## 13. Final Classification

```
RSR6_ORPHAN_BET_INDEX2_AUDIT_READY
```

*Marker: `CTO_ROADMAP_UPDATED_AFTER_RSR6_ORPHAN_BET_INDEX2_AUDIT_20260528`*
