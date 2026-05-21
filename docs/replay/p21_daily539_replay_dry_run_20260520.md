# P21 — Daily 539 Replay Dry-Run

**Date:** 2026-05-21  
**Phase:** P21_DAILY539_REPLAY_DRY_RUN  
**Classification:** P21_DAILY539_DRY_RUN_READY

---

## 1. Objective

Extend the replay pipeline to DAILY_539 — the third lottery type. This dry-run
validates that both ONLINE strategies produce correct predictions over the most
recent 1500 draws before any production DB write.

---

## 2. Why DAILY_539 Next

BIG_LOTTO and POWER_LOTTO pipelines are complete (P14B–P20). DAILY_539 is the
remaining lottery type with ONLINE strategies in the registry, completing full
three-lottery-type replay coverage.

---

## 3. DAILY_539 Draw Data Status

| Metric | Value |
|--------|-------|
| Total DAILY_539 draws | 5865 |
| Draw range | 96000001 – 115000121 |
| Latest draw date | 2026/05/18 |
| Numbers per draw | 5 (pool 1-39) |
| Special number | None (DAILY_539 has no special) |
| 1500-draw window | 110000190 – 115000121 |

---

## 4. Strategy Selection

| strategy_id | lifecycle_status | adapter | min_history | Legacy rows |
|-------------|-----------------|---------|-------------|-------------|
| `daily539_f4cold` | ONLINE ✓ | `_Daily539F4ColdAdapter` | 100 | 90 (outside window) |
| `daily539_markov_cold` | ONLINE ✓ | `_Daily539MarkovColdAdapter` | 100 | 90 (outside window) |

Both strategies selected — 0 duplicate overlap with the 1500-window.

---

## 5. Target Draw Window

| Metric | Value |
|--------|-------|
| target_draw_window | 1500 |
| available_draw_count | 1500 |
| Per-strategy new inserts | 1500 |
| Total candidates | 3000 |

---

## 6. Generated / Ready / Blocked

| Metric | Value |
|--------|-------|
| generated_candidates | 3000 |
| ready_candidates | **3000** ✓ |
| blocked_candidates | 0 |
| fake_success_count | 0 |
| BLOCKED_DUPLICATE_REPLAY_ROW | 0 |

---

## 7. hit_count Calculation

```
hit_numbers = sorted(set(predicted_numbers) & set(actual_numbers))
hit_count   = len(hit_numbers)
special_hit = False   ← DAILY_539 has no special number
```

DAILY_539 uses 5 numbers per draw (not 6). The `predicted_special` and
`actual_special` fields are `None`/`null`. `special_hit` is always `False`.

---

## 8. Special Number Handling

DAILY_539 draws do not have a meaningful special number:
- `draws.special` is NULL, 0, or empty for DAILY_539
- The script treats all of these as `None`
- `predicted_special = None` (adapter returns `(numbers, None)`)
- `special_hit = False` for all candidates

---

## 9. Timestamp Semantics

| Field | Value |
|-------|-------|
| `prediction_cutoff_date` | `history[-1]["date"]` — the last draw date before the target |
| `prediction_generated_at` | UTC timestamp of the P21 dry-run execution |

Invariant: `prediction_cutoff_date <= target_date` verified for all 3000 rows.

---

## 10. page_ready_sample

20 most recent READY rows in the page-ready format:

```json
{
  "target_draw": "115000121",
  "target_date": "2026/05/18",
  "strategy_id": "daily539_markov_cold",
  "strategy_name": "今彩539 Markov Cold",
  "predicted_numbers": [6, 18, 25, 27, 30],
  "actual_numbers": [8, 15, 20, 32, 33],
  "hit_numbers": [],
  "hit_count": 0,
  "special_hit": false,
  "prediction_cutoff_date": "2026/05/16",
  "prediction_generated_at": "2026-05-21T01:36:25Z",
  "display_status": "SHOW_REPLAY_DRY_RUN",
  "truth_level": "DRY_RUN_REPLAY_BACKFILL"
}
```

---

## 11. Why No DB Write

This is a **dry-run verification pass**:
- Validates adapter execution, hit-count math (5 numbers), and timestamp derivation
- All candidates: `dry_run_only=True`, `would_insert=False`, `counts_as_success=False`
- `production_rows_before == production_rows_after == 9460`

---

## 12. Next Recommendations

### P21B — Daily 539 Temp-DB Rehearsal

Rehearse inserting 3000 DAILY_539 rows into a temp copy of the production DB:
- Expected: 9460 → 12460 rows
- Idempotency: rerun = 0 inserts
- Rollback: 12460 → 9460

Requires: `YES create new branch for P21B DAILY_539 temp DB rehearsal`

### P21C — Daily 539 Production Apply

After P21B passes, apply with:
`YES apply DAILY_539 replay rows`

Drift guard update: p21_count=3000, total_count=12460, new truth_level.

### P22 — Daily 539 API/UI Verification

Verify `GET /api/replay/history?lottery_type=DAILY_539` returns all fields
correctly, including the timestamp and 5-number format.
