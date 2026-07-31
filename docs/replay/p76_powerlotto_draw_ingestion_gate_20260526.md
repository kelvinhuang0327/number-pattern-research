# P76 POWER_LOTTO Draw Ingestion Gate

**PROJECT_CONTEXT_LOCK = LotteryNew**

---

## Identity

| Field | Value |
|-------|-------|
| Task ID | P76 |
| Task Name | POWER_LOTTO Draw Ingestion Gate |
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| Branch | `p76-powerlotto-draw-ingestion-gate` |
| HEAD | `a73906d` |
| Created | 2026-05-26 |

---

## Replay Row Invariant

| Checkpoint | Count |
|------------|-------|
| Replay rows before P76 | **46960** |
| Replay rows after P76 | **46960** |
| No replay row write in P76 | ✅ CONFIRMED |

---

## POWER_LOTTO Draw Status

| Field | Value |
|-------|-------|
| Min draw (CAST int) | 97000001 |
| Max draw (CAST int) | **115000040** |
| Total POWER_LOTTO draws | 1912 |
| Draws after 115000040 | **0** |
| Last draw date | 2026/05/18 |
| Last ingest (POWER_LOTTO) | 2026-05-18T14:53:53Z (draw 115000040) |
| Analysis date | 2026-05-26 |

**SQL used:**
```sql
SELECT MIN(CAST(draw AS INTEGER)), MAX(CAST(draw AS INTEGER)), COUNT(*)
FROM draws WHERE lottery_type='POWER_LOTTO';
-- Result: 97000001 | 115000040 | 1912

SELECT COUNT(*) FROM draws
WHERE lottery_type='POWER_LOTTO'
AND CAST(draw AS INTEGER) > 115000040;
-- Result: 0
```

> **Note:** `draws.draw` column is TEXT type. Text comparison of `draw > '115000040'` yields false positives from 97xxx/98xxx/99xxx draws. All numeric comparisons MUST use `CAST(draw AS INTEGER)`.

---

## P75 Source-Data Blocker Summary

- **Classification:** `P75_BLOCKED_BY_SOURCE_DATA_GAP`
- **PR:** #197 (merged, HEAD=a73906d)
- **Strategies blocked:** `fourier_rhythm_3bet` (P19B, 1500 rows), `fourier30_markov30_2bet` (P58, 1500 rows)
- Both strategies already cover draws 101000002–115000040 (all 1500 available POWER_LOTTO draws).
- DB max POWER_LOTTO draw = 115000040. Zero draws exist beyond this in the `draws` table.
- P74 apply script dry-run returned 0 eligible rows → no DB write → Batch A apply is blocked.
- P76 goal: resolve this blocker by establishing draw ingestion gate.

---

## Draw Ingestion Source Discovery

### Official API Source

| Field | Value |
|-------|-------|
| Source type | Taiwan Lottery Official JSON API |
| API base | `https://api.taiwanlottery.com/TLCAPIWeB` |
| POWER_LOTTO endpoint | `/Lottery/SuperLotto638Result` |
| Result key | `superLotto638Res` |
| API available | ✅ YES |

### Ingestion Infrastructure (in-repo)

| Component | File |
|-----------|------|
| Fetcher module | `lottery_api/fetcher/taiwan_lottery_fetcher.py` |
| Backfill engine | `lottery_api/fetcher/backfill_engine.py` |
| Missing issue detector | `lottery_api/fetcher/missing_issue_detector.py` |
| Ingest logger | `lottery_api/fetcher/ingest_logger.py` |
| Ingest API routes | `lottery_api/routes/ingest.py` |
| Dry-run reference script | `scripts/p3bb_official_draw_ingestion_dryrun.py` |
| Controlled import reference | `scripts/p3bc_controlled_draw_import.py` |
| Ingest log | `lottery_api/data/ingest_log.jsonl` |

### Estimated Missing Draws (as of 2026-05-26)

POWER_LOTTO draws on Monday and Thursday:

| Estimated Draw ID | Estimated Date | Day | Status |
|-------------------|---------------|-----|--------|
| 115000041 | 2026-05-21 | Thursday | NOT_IN_DB — official API likely available |
| 115000042 | 2026-05-25 | Monday | NOT_IN_DB — official API likely available |

> **Important:** These are estimates based on the Mon/Thu draw schedule. Actual draw IDs and dates must be confirmed via official API dry-run fetch before any ingestion.

### Pipeline Status

- Last POWER_LOTTO ingestion: `2026-05-18T14:53:53Z` (draw `115000040`)
- Last overall ingestion: `2026-05-25T08:25:32Z` (DAILY_539 only — 5 draws inserted)
- Pipeline status: **FUNCTIONAL_BUT_NOT_RECENTLY_RUN_FOR_POWER_LOTTO**

---

## Ingestion-Readiness Classification

**`INGESTION_POSSIBLE_PENDING_OFFICIAL_API_FETCH`**

The official Taiwan Lottery API (`api.taiwanlottery.com`) is the canonical and available source for POWER_LOTTO draw data. The in-repo fetcher infrastructure (`taiwan_lottery_fetcher.py`, `backfill_engine.py`, `routes/ingest.py`) is functional and follows established patterns. An estimated 2 new POWER_LOTTO draws (115000041 and 115000042) should be available at the official API endpoint but have not yet been fetched and ingested into the local DB.

Ingestion is not blocked by source unavailability — it is blocked by pipeline not being run since 2026-05-18.

---

## Required Draw-Ingestion Gates

All gates must pass before any draw insert is committed.

### Pre-Ingestion Gates

| # | Gate | Description |
|---|------|-------------|
| 1 | **Source Provenance** | All fetched data MUST originate from `https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result`. No manually fabricated draw data allowed. |
| 2 | **DB Backup** | Full SQLite backup of `lottery_api/data/lottery_v2.db` required before any write. Filename must include branch name and timestamp (e.g. `lottery_v2.db.bak_p76_draw_ingest_<YYYYMMDD_HHMMSS>`). |
| 3 | **Dry-Run Fetch** | Execute official API fetch in dry-run mode (no DB write). Verify returned draw data schema: `lottery_type=POWER_LOTTO`, `draw` is integer string, `date` is `YYYY/MM/DD`, `numbers` is sorted list of 6 ints in range 1–38, `special` is int 1–8. |
| 4 | **Duplicate Draw Check** | For each candidate draw: `SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' AND draw=?` must return 0. |
| 5 | **Schema Validation** | Each draw: lottery_type='POWER_LOTTO', draw is 9-digit string starting with '115', date format 'YYYY/MM/DD', numbers is 6 sorted integers (1–38), special is integer (1–8). |
| 6 | **Lottery-Type Validation** | lottery_type must equal exactly `'POWER_LOTTO'`. Reject any DAILY_539 or BIG_LOTTO rows from this ingestion pipeline. |
| 7 | **Controlled Import ID** | Ingestion must use a unique `controlled_import_id` (e.g. `P76_POWERLOTTO_DRAW_INGEST_20260526`) for idempotency and audit trail. |

### Post-Ingestion Gates

| # | Gate | Description |
|---|------|-------------|
| 8 | **Post-Ingestion Draw Count** | After import: `SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000040` must return > 0. Total POWER_LOTTO count must equal 1912 + inserted draw count. |
| 9 | **Drift Guard** | `scripts/replay_lifecycle_drift_guard.py --strict` must pass after ingestion. |
| 10 | **Branch Governance Guard** | `scripts/replay_branch_governance_guard.py --expected-rows 46960` must pass after draw ingestion (replay rows must remain 46960 until P74 Batch A apply runs separately). |

---

## Required P75 Plan Regeneration Gates

After draw ingestion is complete and all post-ingestion gates pass:

| Step | Action |
|------|--------|
| 1 | Verify `SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000040 > 0` |
| 2 | Generate `prediction_items` for `fourier_rhythm_3bet` and `fourier30_markov30_2bet` for each new draw > 115000040 via prediction engine |
| 3 | Regenerate `outputs/replay/p74_batch_a_apply_plan_20260526.json` with `plan_insert_rows_by_strategy` populated and `final_plan_status="PLAN_READY_FOR_P76_APPLY"` |
| 4 | Run dry-run: `.venv/bin/python scripts/p74_batch_a_controlled_apply.py --dry-run` → confirm `eligible_rows > 0`, `0 duplicate controlled_apply_ids` |
| 5 | Obtain authorization phrase: `YES apply P71 controlled replay rows` |
| 6 | Run: `.venv/bin/python scripts/p74_batch_a_controlled_apply.py --backup lottery_api/data/lottery_v2.db.bak_p76_pre_batch_a_<DATE> --apply` |
| 7 | Verify replay rows = **49960** (46960 + 1500 fourier_rhythm_3bet + 1500 fourier30_markov30_2bet for new draws) |

---

## Safety Confirmations

| Guard | Status |
|-------|--------|
| No replay DB write in P76 | ✅ CONFIRMED |
| No fake draws generated | ✅ CONFIRMED |
| No fake prediction rows generated | ✅ CONFIRMED |
| No force push | ✅ CONFIRMED |
| No `git reset --hard` | ✅ CONFIRMED |
| No `git clean` | ✅ CONFIRMED |
| No lifecycle promotion | ✅ CONFIRMED |
| No champion replacement | ✅ CONFIRMED |
| No registry mutation | ✅ CONFIRMED |
| `draws.draw` TEXT → CAST for numeric | ✅ NOTED (always use `CAST(draw AS INTEGER)`) |
| Cross-project contamination | ✅ NONE (false positive in P63 doc: "novel signal axis" = strategy language) |

---

## Final Classification

**`P76_POWERLOTTO_DRAW_INGESTION_GATE_MERGED_TO_MAIN`**

P76 is a read-only gate document. It confirms:
- The P75 source-data blocker is caused by POWER_LOTTO draws 115000041+ not being ingested (not by API unavailability).
- The official API source IS available and the ingestion pipeline IS functional.
- Ingestion can proceed via controlled dry-run → validate → backup → import pattern.
- No DB mutation occurred in P76.
- P74 Batch A apply can be unblocked once ingestion + prediction generation + plan regeneration gates are complete.
