# P19 — Power Lotto Single Strategy Replay Dry-Run

**Date:** 2026-05-20  
**Phase:** P19_POWERLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN  
**Classification:** P19_POWERLOTTO_SINGLE_STRATEGY_DRY_RUN_READY

---

## 1. Objective

Extend the BIG_LOTTO replay pipeline (P14B–P18) to POWER_LOTTO. This P19
dry-run validates that the same approach — 1500 causal predictions, real adapter,
real draw results, hit-count math, and timestamp fields — works for POWER_LOTTO
before any production DB write.

---

## 2. Why POWER_LOTTO Next

BIG_LOTTO replay pipeline is complete:
- P14B (dry-run) → P14C (temp rehearsal) → P14D (apply) → P15 (API)
- P16 (remaining BIG_LOTTO strategies) → P17/P17B (timestamps) → P18 (UI)

POWER_LOTTO is the natural next target:
- 1912 draws available (>1500 ✓)
- 3 ONLINE adapters verified (fourier_rhythm_3bet, power_precision_3bet, power_orthogonal_5bet)
- RSM production strategy (fourier_rhythm_3bet) is available
- Extends page coverage to a second lottery type

---

## 3. POWER_LOTTO Draw Data Status

| Metric | Value |
|--------|-------|
| Total POWER_LOTTO draws | 1912 |
| Draw range | 97000001 – 115000040 |
| Earliest draw date | 2012/01/05 |
| Latest draw date | 2026/05/18 |
| numbers parseable | ✓ (JSON array of 6 ints) |
| special parseable | ✓ (int) |
| Target window | 1500 (full) |

---

## 4. Strategy Selection

| Criterion | Result |
|-----------|--------|
| Lottery type | POWER_LOTTO |
| lifecycle_status | ONLINE |
| Selected strategy_id | **`fourier_rhythm_3bet`** |
| Selected strategy_name | 威力彩 Fourier Rhythm 3注 |
| min_history | 100 |
| External source required | No |
| Adapter callable | ✓ `_PowerFourierRhythm3BetAdapter` |
| get_one_bet returns | `([6 main nums], None)` |

`fourier_rhythm_3bet` was selected per task specification (preferred priority).
It is the current RSM production strategy for POWER_LOTTO (Edge +1.91%, 1000期).

Note: `predicted_special = None` — the adapter does not predict the special
number. `special_hit` is therefore always `False`.

---

## 5. Target Draw Window

| Metric | Value |
|--------|-------|
| target_draw_window | 1500 |
| available_draw_count | 1500 |
| Window | Draws 101000002 – 115000040 |

---

## 6. Generated / Ready / Blocked Statistics

| Metric | Value |
|--------|-------|
| generated_candidates | 1500 |
| ready_candidates | **1500** |
| blocked_candidates | 0 |
| BLOCKED_INSUFFICIENT_HISTORY | 0 |
| BLOCKED_NO_STRATEGY_RUNNER | 0 |
| BLOCKED_NO_PREDICTION_PAYLOAD | 0 |
| BLOCKED_DRAW_PARSE_ERROR | 0 |
| BLOCKED_DUPLICATE_REPLAY_ROW | 0 |
| fake_success_count | 0 |

---

## 7. hit_count Calculation

```
hit_numbers = sorted(set(predicted_numbers) & set(actual_numbers))
hit_count   = len(hit_numbers)
special_hit = (predicted_special == actual_special)
              if both are not None, else False
```

For `fourier_rhythm_3bet`, `predicted_special = None` always → `special_hit = False`.

Sample from most recent draw:

```
target_draw:          115000040 (2026/05/18)
predicted_numbers:    [14, 23, 24, 27, 28, 36]
actual_numbers:       [6, 7, 14, 25, 29, 34]
hit_numbers:          [14]
hit_count:            1
prediction_cutoff_date: 2026/05/14
```

---

## 8. Timestamp Semantics

| Field | Derivation |
|-------|-----------|
| `prediction_cutoff_date` | `history[-1]["date"]` — the date of the last historical draw used by the adapter |
| `prediction_generated_at` | UTC timestamp when the P19 script ran |

Invariant: `prediction_cutoff_date <= target_date` verified for all 1500 READY rows.

---

## 9. page_ready_sample Explanation

`page_ready_sample` (20 most recent READY rows) matches the API contract:

```json
{
  "target_draw": "115000040",
  "target_date": "2026/05/18",
  "strategy_name": "威力彩 Fourier Rhythm 3注",
  "predicted_numbers": [14, 23, 24, 27, 28, 36],
  "actual_numbers": [6, 7, 14, 25, 29, 34],
  "hit_numbers": [14],
  "hit_count": 1,
  "special_hit": false,
  "prediction_cutoff_date": "2026/05/14",
  "prediction_generated_at": "2026-05-20T13:58:53Z",
  "display_status": "SHOW_REPLAY_DRY_RUN",
  "truth_level": "DRY_RUN_REPLAY_BACKFILL"
}
```

---

## 10. Why No DB Write

This is a **dry-run verification pass**:
- Validates adapter execution, hit-count math, and timestamp derivation
- All candidates: `dry_run_only=True`, `would_insert=False`, `counts_as_success=False`
- `production_rows_before == production_rows_after == 4960`

Writing to production requires a full P19B temp DB rehearsal → P19C apply cycle.

---

## 11. Next Recommendations

### P19B — Power Lotto Temp-DB Rehearsal

Rehearse inserting 1500 `fourier_rhythm_3bet` POWER_LOTTO rows into a
temp SQLite copy of the production DB. Verify:
- 4960 → 6460 rows
- Idempotency: rerun = 0 inserts
- Rollback: 6460 → 4960

### P19C — Power Lotto Production Apply

If P19B passes, apply with explicit authorization:
`YES apply POWER_LOTTO replay rows`

### P20 — DAILY_539 Strategy Replay Backfill

After POWER_LOTTO pipeline completes, extend to DAILY_539 ONLINE strategies
to achieve full three-lottery-type replay coverage.
