# P14B — Big Lotto Single Strategy Replay Dry-Run

**Date:** 2026-05-20  
**Phase:** P14B_BIGLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN  
**Classification:** P14B_BIGLOTTO_SINGLE_STRATEGY_DRY_RUN_READY

---

## 1. Why Scope Was Reduced to One Big Lotto Strategy

P13 produced 3000 candidate rows (2 strategies × 1500 draws) but was designed
as a cataloguing and metadata pass, not a page-validation pass. The CEO
recalibrated direction before P14 was started:

- The goal of P14B is **page/API format validation** — proving we can generate
  causal predictions and compare them against real draw results in the exact
  shape the replay list UI expects.
- One strategy × 1500 draws is sufficient to verify all fields, hit-count math,
  and `page_ready_sample` format.
- Smaller scope = faster iteration, lower blast radius, easier verification.
- `ts3_regime_3bet` is the current RSM production strategy for Big Lotto
  (Sharpe 0.123, 300p edge +3.51%), making it the most representative choice.

---

## 2. BIG_LOTTO Draw Data Status

| Field | Value |
|-------|-------|
| Total BIG_LOTTO draws in DB | 2135 |
| Draw range | 96000001 – 115000053 |
| Earliest draw date | 2007/01/02 |
| Latest draw date | 2026/05/15 |
| `numbers` field | JSON array of 6 ints, parseable |
| `special` field | integer, parseable |
| Draws available for 1500-draw window | 1500 (sufficient) |

All draws parsed without error. No `BLOCKED_DRAW_PARSE_ERROR` records.

---

## 3. Strategy Selection

| Criterion | Result |
|-----------|--------|
| Lottery type | BIG_LOTTO |
| Lifecycle status | ONLINE |
| Selected strategy_id | `ts3_regime_3bet` |
| Selected strategy_name | 大樂透 TS3+Regime 3注 |
| min_history | 100 |
| External source required | No |
| Adapter callable | Yes — `_BigLottoTs3Regime3BetAdapter` |
| Reconstruction basis | `tools/backtest_biglotto_enhancements.py` (fourier + cold + tail_balance) |

Other ONLINE BIG_LOTTO strategies available (not selected):

| strategy_id | Status | Existing replay rows |
|-------------|--------|---------------------|
| biglotto_triple_strike | ONLINE | 70 |
| biglotto_deviation_2bet | ONLINE | 70 |
| ts3_regime_3bet | ONLINE | 0 (selected — RSM production) |

`ts3_regime_3bet` was selected because it is the current RSM production strategy.
The adapter was verified callable before the replay loop began.

---

## 4. Target Draw Window

| Field | Value |
|-------|-------|
| target_draw_window | 1500 |
| available_draw_count | 1500 |
| Window status | Full window (not partial) |
| Draws processed | Draws 102000010 – 115000053 |

---

## 5. Generated / Ready / Blocked Statistics

| Metric | Value |
|--------|-------|
| generated_candidates | 1500 |
| ready_candidates | 1500 |
| blocked_candidates | 0 |
| fake_success_count | 0 |
| BLOCKED_INSUFFICIENT_HISTORY | 0 |
| BLOCKED_NO_STRATEGY_RUNNER | 0 |
| BLOCKED_NO_PREDICTION_PAYLOAD | 0 |
| BLOCKED_DRAW_PARSE_ERROR | 0 |
| BLOCKED_DUPLICATE_REPLAY_ROW | 0 |

All 1500 draws produced READY candidates with real predicted_numbers and real
actual_numbers. The first 100 draws in the **full** dataset (before the 1500-draw
window) provided the necessary min_history=100, so no draws were blocked.

---

## 6. hit_count Calculation

```
hit_numbers = sorted(set(predicted_numbers) & set(actual_numbers))
hit_count   = len(hit_numbers)
special_hit = (predicted_special == actual_special)
              if both are not None, else False
```

For `ts3_regime_3bet`, `predicted_special` is always `None` (the adapter does
not generate a special number), so `special_hit` is always `False`.

Example candidate from the output:

```json
{
  "draw_number": "102000010",
  "predicted_numbers": [4, 8, 30, 33, 37, 44],
  "actual_numbers":    [1, 26, 28, 37, 39, 46],
  "hit_numbers":       [37],
  "hit_count":         1,
  "special_hit":       false,
  "counts_as_success": false,
  "would_insert":      false
}
```

---

## 7. page_ready_sample Explanation

The output JSON includes a `page_ready_sample` of the 20 most recent READY rows
in the following format:

```json
{
  "draw_number": "115000053",
  "draw_date": "2026/05/15",
  "strategy_name": "大樂透 TS3+Regime 3注",
  "predicted_numbers": [7, 8, 15, 23, 37, 40],
  "actual_numbers":    [16, 29, 30, 35, 42, 43],
  "hit_numbers":       [],
  "hit_count":         0,
  "special_hit":       false,
  "display_status":    "SHOW_REPLAY_DRY_RUN",
  "truth_level":       "DRY_RUN_REPLAY_BACKFILL"
}
```

This shape mirrors the replay list API contract. The next phase (P14C or P15)
can pass this sample directly to the page/API integration test to verify that
the replay list renders correctly without any production DB apply.

---

## 8. Why No DB Write

This is a **dry-run verification pass**:

- Goal is to prove the script can generate correct predictions and hit-count math,
  not to populate the production replay store.
- Every candidate has `dry_run_only=True`, `would_insert=False`,
  `counts_as_success=False`.
- `production_rows_before == production_rows_after == 460` (verified post-run).
- No `strategy_prediction_replays` rows were inserted, updated, or deleted.

Writing to production requires an explicit controlled-apply step (P14C) with
full DB rehearsal, STOP conditions, and post-apply drift guard verification.

---

## 9. Next Recommendations

### Option A — P14C Big Lotto Temp-DB Rehearsal

Before writing to the production DB, rehearse the apply using a temporary SQLite
copy of `lottery_v2.db`. Verify:
- 1500 rows insert cleanly into the temp copy.
- drift guard PASS on temp DB.
- No duplicate key violations.
- Rollback works correctly.

Then, if temp-DB rehearsal passes, schedule a controlled production apply.

### Option B — P15 Page/API Integration Verification

Skip the DB apply for now and use the `page_ready_sample` from this JSON to
verify that the replay list API and frontend page can render dry-run rows
correctly. This gates out any display bugs before production apply.

**Recommended order:** P14C (temp DB rehearsal) → P15 (page/API integration)
→ P16 (production apply for ts3_regime_3bet 1500 rows).

---

## 10. Verification Summary

| Check | Result |
|-------|--------|
| production_rows before | 460 |
| production_rows after | 460 |
| drift guard pre | PASS |
| governance guard pre | PASS |
| drift guard post | PASS |
| governance guard post | PASS |
| baseline tests | 65 PASS |
| P14B tests | PASS |
| no DB / backup / pid staged | ✓ |
| no production apply | ✓ |
| final_classification | P14B_BIGLOTTO_SINGLE_STRATEGY_DRY_RUN_READY |
