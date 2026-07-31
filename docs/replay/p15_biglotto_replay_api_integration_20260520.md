# P15 — Big Lotto Replay API Integration Verification

**Date:** 2026-05-20  
**Phase:** P15_BIGLOTTO_REPLAY_API_INTEGRATION  
**Classification:** P15_BIGLOTTO_REPLAY_API_INTEGRATION_READY

---

## 1. Objective

Verify that the replay list API (`GET /api/replay/history`) correctly serves
the 1500 `ts3_regime_3bet` BIG_LOTTO rows inserted in P14D, with all required
fields present, correct hit-count math, and full pagination support.

---

## 2. P14D Production Rows Status

| Metric | Value |
|--------|-------|
| Total production rows | 1960 |
| P14D rows (ts3_regime_3bet, BIG_LOTTO) | 1500 |
| controlled_apply_id | `P14D_BIGLOTTO_TS3_1500_PROD_20260520` |
| truth_level | `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` |
| legacy rows (unchanged) | 460 |

---

## 3. API Endpoint Checked

| Field | Value |
|-------|-------|
| Endpoint | `GET /api/replay/history` |
| Query | `lottery_type=BIG_LOTTO&strategy_id=ts3_regime_3bet` |
| Test method | Direct FastAPI route call via asyncio (no live HTTP) |
| `total` returned | **1500** ✓ |
| `pages` returned | 300 (at page_size=5) |

---

## 4. Query / Filter Behavior

| Filter | Behavior |
|--------|----------|
| `lottery_type=BIG_LOTTO` | Returns only BIG_LOTTO rows ✓ |
| `strategy_id=ts3_regime_3bet` | Returns only ts3_regime_3bet rows ✓ |
| `lifecycle_status=ONLINE` | Supported; ts3_regime_3bet is ONLINE ✓ |
| No filter | Returns all 1960 rows (mixed strategies + legacy) |
| `date_from` / `date_to` | Supported (not tested in P15) |

---

## 5. Pagination Behavior

| Test | Result |
|------|--------|
| `page_size=5, page=1` → 5 records | ✓ |
| `page_size=5, page=2` → different draws | ✓ no overlap |
| `page_size=10` → `pages=150` | ✓ |
| `total=1500` across pages | ✓ |
| `page`, `page_size`, `pages`, `total` all present | ✓ |

Pagination supports up to `page_size=200` (API hard limit).
To retrieve all 1500 rows: 8 pages at `page_size=200`.

---

## 6. Required Fields — All Present

All 15 required fields verified present in every record:

| Field | Value in Sample |
|-------|----------------|
| `strategy_id` | `ts3_regime_3bet` |
| `strategy_name` | 大樂透 TS3+Regime 3注 |
| `lottery_type` | `BIG_LOTTO` |
| `target_draw` | e.g. `115000053` |
| `target_date` | e.g. `2026/05/15` |
| `predicted_numbers` | e.g. `[7, 8, 15, 23, 37, 40]` |
| `actual_numbers` | e.g. `[16, 29, 30, 35, 42, 43]` |
| `hit_numbers` | e.g. `[]` |
| `hit_count` | e.g. `0` |
| `special_hit` | `0` or `1` |
| `truth_level` | `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` |
| `controlled_apply_id` | `P14D_BIGLOTTO_TS3_1500_PROD_20260520` |
| `display_status` | `SHOW_REPLAY_RESULT` |
| `visibility_state` | `ROW_BACKED` |
| `should_count_as_success` | `True` (actual_numbers + hit_count present) |

**Missing fields:** none.

---

## 7. hit_count Verification

```
hit_numbers = sorted(set(predicted_numbers) & set(actual_numbers))
hit_count   = len(hit_numbers)
```

All 1500 rows checked: `hit_count == len(hit_numbers)` for every row.
**Issues: 0**.

---

## 8. truth_level / controlled_apply_id Display Readiness

| Check | Result |
|-------|--------|
| All P14D rows have correct truth_level | ✓ |
| truth_level = `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` | ✓ all 1500 rows |
| controlled_apply_id = `P14D_BIGLOTTO_TS3_1500_PROD_20260520` | ✓ all 1500 rows |
| display_status = `SHOW_REPLAY_RESULT` | ✓ — rows are display-eligible |
| visibility_state = `ROW_BACKED` | ✓ — backed by real DB row |
| should_count_as_success | ✓ `True` for all rows with actual_numbers + hit_count |

---

## 9. Cross-Check vs P14B page_ready_sample

| Metric | Result |
|--------|--------|
| P14B sample draws checked | 5 (most recent) |
| hit_count mismatches | 0 |
| hit_numbers mismatches | 0 |
| predicted_numbers mismatches | 0 |
| actual_numbers mismatches | 0 |

The API values are byte-for-byte consistent with the P14B dry-run output,
confirming that the production apply preserved all computed fields correctly.

---

## 10. UI / Page Readiness Conclusion

**P15_BIGLOTTO_REPLAY_API_INTEGRATION_READY**

The `GET /api/replay/history` endpoint:
- Returns all 1500 P14D rows with correct fields
- Supports filtering by `lottery_type` and `strategy_id`
- Supports pagination with full metadata
- `display_status = SHOW_REPLAY_RESULT` — rows are ready for the replay list UI
- `visibility_state = ROW_BACKED` — rows are backed by real production DB entries
- `hit_count` verified correct for all 1500 rows
- `truth_level` correctly identifies provenance

No API patch was needed — all required fields were already present.

---

## 11. Next Recommendations

### P16 — Extend BIG_LOTTO Replay to Other ONLINE Strategies

Apply the same P14B → P14C → P14D pipeline to the two remaining ONLINE
BIG_LOTTO strategies:
- `biglotto_triple_strike` (already has 70 legacy rows — duplicate detection handles this)
- `biglotto_deviation_2bet` (already has 70 legacy rows)

Each strategy would add 1500 new rows. After P16:
- `biglotto_triple_strike`: up to 1500 new rows (minus 70 legacy duplicates by draw)
- `biglotto_deviation_2bet`: up to 1500 new rows (minus 70 legacy duplicates by draw)
- Total production rows: ~4960

### P17 — POWER_LOTTO and DAILY_539 Replay Backfill

Apply the same pipeline to POWER_LOTTO and DAILY_539 ONLINE strategies to
complete the full replay store coverage.
