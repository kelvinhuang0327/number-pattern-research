# P78 — Batch A Plan Regeneration / Dry-run Readiness

**Phase:** P78 — Batch A Plan Regeneration (Dry-run Only)
**Branch:** `p78-batch-a-plan-regeneration`
**Date:** 2026-05-26
**Classification:** `P78_BATCH_A_PLAN_REGENERATION_COMPLETE`
**Final Plan Status:** `PLAN_READY_FOR_P79_APPLY`

---

## 1. Purpose

P77B (PR #200) confirmed that POWER_LOTTO draw **115000041** now exists in the
production DB (`controlled_import_id=P77B_POWERLOTTO_DRAW_REFRESH_20260526`).

P78 regenerates the Batch A apply plan in **dry-run mode only** for both strategies:

1. `fourier_rhythm_3bet` (P19B, 1500 rows — max draw previously 115000040)
2. `fourier30_markov30_2bet` (P58, 1500 rows — max draw previously 115000040)

**No replay rows are inserted in P78.**  
**No `draws` table writes occur in P78.**  
P79 is the controlled apply phase (requires explicit authorization).

---

## 2. Pre-flight State

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Branch (governance) | `main` ✅ |
| Production replay rows | `46960` ✅ |
| POWER_LOTTO max draw | `115000041` (via CAST(draw AS INTEGER)) ✅ |
| POWER_LOTTO draw count | `1913` |
| Draw 115000041 in DB | ✅ PRESENT (P77B confirmed) |
| Draw 115000041 data | date=2026/05/21, numbers=[6,14,22,28,35,38], special=1 |
| Batch A rows for 115000041 (before) | `0` (safe to plan) |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Branch governance | `BRANCH_GOVERNANCE_PASS — main rows=46960` ✅ |

---

## 3. Target Draw

| Field | Value |
|---|---|
| Draw | `115000041` |
| Lottery type | `POWER_LOTTO` |
| Date | `2026/05/21` (Wednesday) |
| Numbers | `[6, 14, 22, 28, 35, 38]` |
| Special | `1` |
| Source | `P77B_POWERLOTTO_DRAW_REFRESH_20260526` |

---

## 4. History Cutoff

| Field | Value |
|---|---|
| Cutoff draw | `115000040` (2026/05/18) |
| History rows used | `1912` |
| Method | `CAST(draw AS INTEGER) <= 115000040` |

---

## 5. Prediction Generation

### 5a. fourier_rhythm_3bet

- **Adapter:** `_PowerFourierRhythm3BetAdapter`
- **Function:** `fourier_rhythm_predict(history, n_bets=3, window=500)`
- **All 3 bets generated:**
  - Bet 0: `[3, 23, 24, 28, 30, 36]`
  - Bet 1: `[1, 4, 14, 15, 27, 38]`
  - Bet 2: `[6, 13, 17, 32, 34, 35]`
- **Stored bet (per adapter contract `_extract_first_bet`):** `[3, 23, 24, 28, 30, 36]`

### 5b. fourier30_markov30_2bet

- **Adapter:** `Fourier30Markov30_2BetAdapter`
- **Function:** `predict_fourier30_markov30_2bet_bet0(history)` (Fourier30 weighted frequency)
- **Stored bet:** `[13, 14, 27, 29, 34, 38]`

---

## 6. Actual vs Prediction Comparison

| Strategy | Predicted | Actual | Hits | Hit Count | M3+? |
|---|---|---|---|---|---|
| `fourier_rhythm_3bet` | `[3, 23, 24, 28, 30, 36]` | `[6, 14, 22, 28, 35, 38]` | `[28]` | **1** | No |
| `fourier30_markov30_2bet` | `[13, 14, 27, 29, 34, 38]` | `[6, 14, 22, 28, 35, 38]` | `[14, 38]` | **2** | No |

Special: actual=1, neither strategy predicts special → `special_hit=0` for both.

---

## 7. Duplicate Check

```sql
SELECT COUNT(*) FROM strategy_prediction_replays
WHERE controlled_apply_id IN (
  'P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526',
  'P78_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_DRAWEXT_20260526'
);
-- Result: 0
```

**DUPLICATE CHECK PASS** — no collision risk.

---

## 8. Dry-run Row Summary

| Strategy | Target Draw | Predicted | Hits | Eligible | Controlled Apply ID |
|---|---|---|---|---|---|
| `fourier_rhythm_3bet` | 115000041 | `[3, 23, 24, 28, 30, 36]` | 1 | **1** | `P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526` |
| `fourier30_markov30_2bet` | 115000041 | `[13, 14, 27, 29, 34, 38]` | 2 | **1** | `P78_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_DRAWEXT_20260526` |

**Total plan rows: 2**  
**Eligible rows: 2**  
**Skipped rows: 0**

---

## 9. Governance Confirmation

| Constraint | Status |
|---|---|
| No replay row insert | ✅ CONFIRMED (46960 unchanged) |
| No draws table write | ✅ CONFIRMED |
| No lifecycle promotion | ✅ CONFIRMED |
| No registry mutation | ✅ CONFIRMED |
| No champion replacement | ✅ CONFIRMED |
| No new tables created | ✅ CONFIRMED |
| No official API insert | ✅ CONFIRMED |
| No force push | ✅ CONFIRMED |
| No git reset --hard | ✅ CONFIRMED |
| No git clean | ✅ CONFIRMED |
| CEO-Decision.md not modified | ✅ CONFIRMED |
| active_task.md not modified | ✅ CONFIRMED |
| CAST(draw AS INTEGER) used | ✅ CONFIRMED |
| Dry-run only | ✅ CONFIRMED |

---

## 10. P79 Readiness

| Item | Status |
|---|---|
| Total eligible rows | **2** |
| Expected P79 insert delta | **+2** |
| Rows before P79 | `46960` |
| Rows after P79 (expected) | `46962` |
| Duplicate risk | **NONE** |
| Draw 115000042+ | Still absent — not in scope for P79 |
| P79 proceed | **YES — requires explicit authorization** |

**Authorization phrase required to proceed to P79:**

```
YES proceed with P79 Batch A controlled apply for draw 115000041
```

---

## 11. Files Created

- `outputs/replay/p78_batch_a_plan_regeneration_20260526.json`
- `docs/replay/p78_batch_a_plan_regeneration_20260526.md`
- `tests/test_p78_batch_a_plan_regeneration.py`
