# P2D Official Big Lotto Draw Ingestion Dry-run Report

**Date:** 2026-05-15  
**Run ID:** p2d_official_draw_ingestion_dryrun_20260515  
**Branch:** chore/p2d-official-draw-ingestion-dryrun-20260515  
**Classification:** P2D_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY

---

## 1. 本輪目標

確認是否能從 api.taiwanlottery.com 補齊 BIG_LOTTO draws 115000051–115000053。
本輪為 dry-run / preview 模式，不允許任何 DB 寫入。

---

## 2. PR #112 Diagnostic Summary

- **PR:** #112 (draft, open) — `chore/ingestion-pipeline-diagnostic-20260515`
- **Final Classification:** INGESTION_PIPELINE_DIAGNOSTIC_READY
- **Root cause:** NO_AUTOMATED_INGESTION_PIPELINE
- **DB state:** draws = 14,002 rows, replay_rows = 966
- **BIG_LOTTO latest draw at time of diagnosis:** 115000050 (2026/05/05), 10d stale
- **P2C blocker:** BIG_LOTTO draw 115000051 missing → prediction_items 1090–1092 cannot be evaluated

---

## 3. Existing Scraper / Ingestion Code Paths

- `tools/scrape_lottery_data.py` — existing scraper targeting BIG_LOTTO via:
  - Single draw: `https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history?period={draw_number}`
  - Latest batch: `https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history`
  - Date-based: `https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history?date={date_str}`
  - Note: uses `content[0]['period']` field format
- `scripts/p2d_official_draw_ingestion_dryrun.py` — new dry-run wrapper (this PR), uses:
  - `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result?period={draw_number}`
  - This endpoint returns the `lotto649Res` array with `drawNumberSize` (7 items: 6 main + 1 special)
- No automated ingestion pipeline exists; all draws must be manually fetched / triggered.

---

## 4. DB Preflight Results

| Draw | Exists in DB |
|------|-------------|
| 115000051 | NO |
| 115000052 | NO |
| 115000053 | NO |

- Latest BIG_LOTTO draw in DB: **115000050** (2026/05/05), numbers=[4,17,23,28,33,37], special=15
- Total replay rows: **966**
- DB connection: read-only (file:...?mode=ro), no writes possible

---

## 5. Official Source Fetch Result

| Draw | Status | Source URL |
|------|--------|-----------|
| 115000051 | SUCCESS (FETCHED) | https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result?period=115000051 |
| 115000052 | SUCCESS (FETCHED) | https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result?period=115000052 |
| 115000053 | BLOCKED_NO_TARGET_DRAWS_FOUND | Same endpoint — draw likely not yet published |

**Overall fetch result:** PARTIAL SUCCESS — 2 of 3 target draws fetched successfully.

---

## 6. BIG_LOTTO Target Draw Preview 115000051–115000053

| Draw | Date | Numbers | Special | Exists in DB | Fetch Status | Validation |
|------|------|---------|---------|-------------|-------------|-----------|
| 115000051 | 2026/05/08 | [10, 18, 25, 28, 39, 43] | 48 | NO | FETCHED | PASS |
| 115000052 | 2026/05/12 | [6, 12, 18, 19, 32, 36] | 34 | NO | FETCHED | PASS |
| 115000053 | N/A | N/A | N/A | NO | BLOCKED_NO_TARGET_DRAWS_FOUND | FAIL (not_fetched) |

Notes:
- 115000053 is not yet available from the official API as of 2026-05-15. The draw date is likely 2026/05/15 or later — it may not have been held yet.
- Special ball for 115000051 = 48 (range 1–49, VALID); 115000052 = 34 (VALID)

---

## 7. Validation Results

BIG_LOTTO validation rules applied:
- Main numbers: 6 numbers, each in range [1, 49]
- Special: 1 number in range [1, 49] (台灣大樂透 special ball draws from 1–49 pool)
- No duplicates in main numbers

| Draw | Main Count | Main Range | Special Range | Duplicates | PASSED |
|------|-----------|-----------|--------------|-----------|--------|
| 115000051 | 6/6 OK | all in [1-49] | 48 in [1-49] | none | YES |
| 115000052 | 6/6 OK | all in [1-49] | 34 in [1-49] | none | YES |
| 115000053 | N/A | N/A | N/A | N/A | NO (not fetched) |

---

## 8. P2C Unblock Status

**P2C unblock status: READY_PENDING_IMPORT** (for 115000051 and 115000052)

- Prediction items 1090–1092 are blocked on BIG_LOTTO draw 115000051 being present in DB.
- Draw 115000051 (2026/05/08) has been fetched and validated.
- Draw 115000052 (2026/05/12) has been fetched and validated.
- After importing 115000051 and 115000052, items 1090–1092 can be evaluated.
- Draw 115000053 is not yet available; P2C evaluation of items dependent on 115000053 remains blocked until that draw is published.

---

## 9. Safety Confirmation

| Safety Check | Status |
|-------------|--------|
| db_written | FALSE |
| draw_rows_inserted | FALSE |
| replay_rows_generated | FALSE |
| prediction_items_promoted | FALSE |
| strategy_logic_changed | FALSE |
| api_ui_backend_changed | FALSE |

All operations were read-only. The dry-run script connects to DB with `file:...?mode=ro` URI — any accidental write attempt would raise `sqlite3.OperationalError`.

---

## 10. Next Step Recommendation

### Immediate (P2E)
1. **Operator approval required** for controlled draw import of 115000051 and 115000052.
2. Create a separate controlled import script (non-dry-run) with:
   - Draw data sourced from this dry-run's validated output JSON
   - Idempotent INSERT OR IGNORE logic
   - Post-import DB row verification
3. After import, re-run P2C dry-run for prediction_items 1090–1092.

### For 115000053
- Wait for draw to be published (likely 2026/05/15 evening or later).
- Re-run this dry-run script to confirm availability.

### Artifacts
- JSON preview: `outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json`
- CSV preview: `outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.csv`

---

*Generated by P2D Official Draw Ingestion Dry-run Agent — 2026-05-15*
