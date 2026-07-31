# P17 — Big Lotto Replay Timestamp API Readiness

**Date:** 2026-05-20  
**Phase:** P17_BIGLOTTO_REPLAY_TIMESTAMP_API  
**Classification:** P17_BIGLOTTO_REPLAY_TIMESTAMP_API_READY

---

## 1. Objective

Verify that `prediction_cutoff_date` and `prediction_generated_at` timestamp
fields are (a) present in the DB schema, (b) populated in P16 rows, and
(c) exposed by the replay history API so the page can display prediction timing.

---

## 2. Current Production Rows

| Metric | Value |
|--------|-------|
| Total production rows | 4960 |
| Legacy rows (apply_id IS NULL) | 460 |
| P14D ts3_regime_3bet rows | 1500 |
| P16 biglotto_triple_strike rows | 1500 |
| P16 biglotto_deviation_2bet rows | 1500 |
| Total BIG_LOTTO ONLINE backfill rows | 4500 |

---

## 3. Big Lotto 3 Strategies × 1500 Status

| strategy_id | P16/P14D rows | API total | Queryable |
|-------------|---------------|-----------|-----------|
| `ts3_regime_3bet` | 1500 (P14D) | 1500 | ✓ |
| `biglotto_triple_strike` | 1500 (P16) + 70 legacy | 1570 | ✓ |
| `biglotto_deviation_2bet` | 1500 (P16) + 70 legacy | 1570 | ✓ |

All three strategies are queryable with `>=1500` rows each. ✓

---

## 4. Timestamp Schema Status

| Column | Present |
|--------|---------|
| `prediction_cutoff_date` | ✓ (TEXT, nullable) |
| `prediction_generated_at` | ✓ (TEXT, nullable) |

Columns were added in P16A. Both schema checks PASS.

---

## 5. P16 Timestamp Status

| Metric | Value |
|--------|-------|
| P16 rows with `prediction_cutoff_date` IS NOT NULL | **3000 / 3000** ✓ |
| P16 rows with `prediction_generated_at` IS NOT NULL | **3000 / 3000** ✓ |
| `prediction_cutoff_date > target_date` violations | **0** ✓ |

Sample P16 timestamp values:
```
strategy_id:           biglotto_triple_strike
target_draw:           102000010
prediction_cutoff_date: 2013/01/29
prediction_generated_at: 2026-05-20T13:01:31.624608+00:00
```

---

## 6. P14D Timestamp Gap

| Metric | Value |
|--------|-------|
| P14D rows with `prediction_cutoff_date` IS NOT NULL | **0 / 1500** |
| Gap reason | P14D applied before P16A added timestamp columns |
| Fabricated? | **NO — NULL values are correct and honest** |

The `ts3_regime_3bet` rows applied via P14D predate the timestamp columns.
The API correctly returns `prediction_cutoff_date: null` for these rows.
This is the documented legacy gap, not an error.

**Proposed remediation:** P17B — backfill `prediction_cutoff_date` and
`prediction_generated_at` for P14D rows using the `history_cutoff_draw`
draw date and a synthetic `prediction_generated_at` timestamp.

---

## 7. API Endpoint Checked

| Field | Value |
|-------|-------|
| Endpoint | `GET /api/replay/history` |
| Strategies queried | ts3_regime_3bet, biglotto_triple_strike, biglotto_deviation_2bet |
| Test method | Direct FastAPI route call via asyncio |

---

## 8. API Timestamp Field Status

Before P17: `prediction_cutoff_date` and `prediction_generated_at` were **missing** from the API response.

**P17 additive-only patch applied to `lottery_api/routes/replay.py`:**
1. Added both columns to the SELECT statement.
2. Added both fields to the response dict.

After P17 patch:

| Field | ts3_regime_3bet | biglotto_triple_strike | biglotto_deviation_2bet |
|-------|-----------------|----------------------|------------------------|
| `prediction_cutoff_date` | `null` (legacy gap) | e.g. `2026/05/12` | e.g. `2026/05/12` |
| `prediction_generated_at` | `null` (legacy gap) | e.g. `2026-05-20T13:01:31Z` | e.g. `2026-05-20T13:01:31Z` |

The patch is additive (no existing fields removed or modified). All prior
API contract tests continue to pass. ✓

---

## 9. Page Readiness Conclusion

**P17_BIGLOTTO_REPLAY_TIMESTAMP_API_READY**

The API now exposes:
- `prediction_cutoff_date` — the draw date used as history cutoff for the prediction
- `prediction_generated_at` — when the prediction was generated (replay apply time)

For P16 rows (biglotto_triple_strike, biglotto_deviation_2bet): both fields populated ✓  
For P14D rows (ts3_regime_3bet): both fields `null` — documented legacy gap

The page can display prediction timing for P16 rows immediately. For P14D rows,
timestamps will show as "unknown" until P17B backfill is completed.

---

## 10. Next Recommendations

### P17B — P14D Timestamp Metadata Backfill

Backfill `prediction_cutoff_date` and `prediction_generated_at` for the 1500
P14D `ts3_regime_3bet` rows:
- `prediction_cutoff_date` = `target_date` of the preceding draw
  (can be derived from `history_cutoff_draw` joined to the `draws` table)
- `prediction_generated_at` = a documented synthetic timestamp indicating
  it was set during P17B backfill, not at original prediction time

Requires explicit production DB write authorization.

### P18 — UI Timestamp Display Patch

Update the replay list page to display the timestamp badge:
- If `prediction_cutoff_date` is set: show "Predicted based on data up to {date}"
- If `null`: show "Prediction date unknown (legacy row)"

### P19 — POWER_LOTTO and DAILY_539 Replay Backfill

Apply the same P14B→P14C→P14D pipeline to extend replay coverage to
POWER_LOTTO and DAILY_539 ONLINE strategies.
