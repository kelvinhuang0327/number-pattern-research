# P17B — P14D Timestamp Metadata Backfill

**Date:** 2026-05-20  
**Phase:** P17B_P14D_TIMESTAMP_BACKFILL  
**Classification:** P17B_P14D_TIMESTAMP_BACKFILL_APPLIED

---

## 1. Objective

Backfill `prediction_cutoff_date` and `prediction_generated_at` for the 1500
`ts3_regime_3bet` BIG_LOTTO rows applied via P14D, which predate the timestamp
columns added in P16A.

---

## 2. P17 Legacy Timestamp Gap

P17 documented that:
- P16 rows (3000): `prediction_cutoff_date` and `prediction_generated_at` populated ✓
- P14D rows (1500): both fields `NULL` — schema added after P14D apply
- The API returned `null` for these fields — displayed as "unknown" on the page

P17B resolves this gap.

---

## 3. P14D Target Rows

| Metric | Value |
|--------|-------|
| controlled_apply_id | `P14D_BIGLOTTO_TS3_1500_PROD_20260520` |
| strategy_id | `ts3_regime_3bet` |
| lottery_type | `BIG_LOTTO` |
| target rows | **1500** |
| rows with NULL timestamps (before P17B) | 1500 |
| `history_cutoff_draw` JOIN success | 1500/1500 |

---

## 4. prediction_cutoff_date Derivation

```sql
prediction_cutoff_date =
  (SELECT d.date FROM draws d
   WHERE d.lottery_type = r.lottery_type
     AND d.draw = r.history_cutoff_draw
   LIMIT 1)
```

For each row, this is the actual draw date of the last historical draw that
was visible when the prediction was made. This is a faithful, deterministic
derivation from existing data — not fabricated.

Example:
```
target_draw = 115000053
target_date = 2026/05/15
history_cutoff_draw = 115000052
prediction_cutoff_date = 2026/05/12  ← draw date of 115000052
```

Invariant verified: `prediction_cutoff_date <= target_date` for all 1500 rows.
**Violations: 0**

---

## 5. prediction_generated_at Semantics

| Semantics | Value |
|-----------|-------|
| Value set | P17B backfill execution timestamp |
| Example | `2026-05-20T13:33:33.614367+00:00` |
| Meaning | When the P17B backfill script ran |
| NOT | The original prediction generation time from 2026-05-20 P14D apply |

Documented as `P17B_METADATA_BACKFILL_TIME_NOT_ORIGINAL_PREDICTION_TIME` in all
output JSON files.

The page/UI should treat this field as "data last updated at" for P14D rows,
not "when the prediction was originally generated."

---

## 6. Temp DB Rehearsal Results

| Phase | Metric | Value |
|-------|--------|-------|
| R1 Apply | `updated_count` | **1500** ✓ |
| R1 Apply | `inserted_count` | 0 ✓ |
| R1 Apply | `cutoff_violations` | 0 ✓ |
| R1 Apply | `rows_after` | 4960 ✓ |
| R2 Rerun | `updated_count` | **0** ✓ (idempotent) |
| Rollback | `rollback_updated_count` | **1500** ✓ |
| Rollback | timestamps restored to NULL | ✓ |

---

## 7. Production Apply Results

| Metric | Value |
|--------|-------|
| `updated_count` | **1500** ✓ |
| `inserted_count` | 0 ✓ |
| `deleted_count` | 0 ✓ |
| `cutoff_violations` | 0 ✓ |
| `rows_before` | 4960 |
| `rows_after` | 4960 ✓ |
| `production_apply` | true |

---

## 8. API Impact

Before P17B:

```
GET /api/replay/history?lottery_type=BIG_LOTTO&strategy_id=ts3_regime_3bet
→ prediction_cutoff_date: null
→ prediction_generated_at: null
```

After P17B:

```
GET /api/replay/history?lottery_type=BIG_LOTTO&strategy_id=ts3_regime_3bet
→ prediction_cutoff_date: "2026/05/12"
→ prediction_generated_at: "2026-05-20T13:33:33.614367+00:00"
```

All three BIG_LOTTO ONLINE strategies now return non-NULL timestamps.

---

## 9. Post-Apply Verification

| Check | Result |
|-------|--------|
| production rows | 4960 ✓ |
| P14D rows with timestamps | 1500/1500 ✓ |
| cutoff > target_date violations | 0 ✓ |
| API returns timestamps for ts3_regime_3bet | ✓ |
| predicted_numbers/actual_numbers/hit_count untouched | ✓ |
| drift guard PASS | ✓ |
| governance guard PASS | ✓ |

---

## 10. Next Recommendations

### P18 — UI Timestamp Display Patch

Update the replay list page to display the prediction timestamp badge:
- If `prediction_cutoff_date` is set: "Predicted based on data up to {date}"
- `prediction_generated_at` shown as "Record generated at {timestamp}"
- For P14D rows: note that `prediction_generated_at` reflects P17B backfill time

### P19 — POWER_LOTTO and DAILY_539 Replay Backfill

Extend the P14B→P14C→P14D pipeline to POWER_LOTTO and DAILY_539 ONLINE
strategies to complete full replay store coverage across all lottery types.
