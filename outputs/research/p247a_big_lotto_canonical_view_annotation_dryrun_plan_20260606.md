# P247A — BIG_LOTTO Canonical DB Separation Dry-run Plan

**Task ID:** P247A · **Date:** 2026-06-06 · **Type:** Type D preparation (read-only dry-run).
**No DB write. No CREATE VIEW/TABLE executed. Dry-run only.**
**Final Classification:** `P247A_BIG_LOTTO_CANONICAL_DB_SEPARATION_DRYRUN_PLAN_COMPLETE`

> **Dry-run result:** Proposed canonical view SQL returns exactly **2,113 rows** on current DB. JSON1/json_each is available for SMALL_POOL_ALIEN filtering. All counts verified. No DB modification performed.

---

## 1. Why DB-Level Separation Is Still Useful After Code-Level Isolation

P246E–H implemented code-level canonical filtering via `get_canonical_draws()`. This ensures active research callers receive only canonical draws. However:

1. Any new caller that uses `get_all_draws()` directly will still get 22,238 rows.
2. Display/API callers cannot easily label row families without a metadata table.
3. A DB-level canonical view makes the separation explicit at the schema level — it cannot be bypassed by accident.
4. A row-family annotation table enables labeling (e.g. API/frontend can display add-on records with `加碼/特別獎` label).

---

## 2. Current Row Counts (Verified Read-Only)

| Family | Count | Notes |
|---|---|---|
| Raw BIG_LOTTO total | 22,238 | All rows in draws table |
| ADD_ON_PRIZE_EXCLUDED | 19,100 | Hyphenated IDs — valid add-on records, preserved |
| DATE_FORMAT_ALIEN | 375 | 8-digit YYYYMMDD IDs |
| SMALL_POOL_ALIEN | 650 | max(numbers)≤25; json_each filter |
| **CANONICAL_MAIN_DRAW** | **2,113** | View dry-run confirms exactly this |
| Replay rows | 94,924 | Must be unchanged after apply |
| JSON1/json_each | Available | SMALL_POOL_ALIEN can be filtered in view |

---

## 3. Proposed Canonical View (Option A)

```sql
-- Dry-run validated: returns 2,113 rows on current DB
-- DO NOT EXECUTE without explicit Type D authorization

CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical_main AS
SELECT d.*
FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO'
  AND d.draw NOT LIKE '%-%'
  AND NOT (LENGTH(d.draw) = 8 AND d.draw LIKE '20%')
  AND (
    SELECT MAX(CAST(j.value AS INTEGER))
    FROM json_each(d.numbers) j
  ) > 25;
```

**Dry-run count:** `SELECT COUNT(*) FROM (...) tmp` = **2,113** ✅

---

## 4. Proposed Annotation Table (Option B)

```sql
-- DO NOT EXECUTE without explicit Type D authorization

CREATE TABLE IF NOT EXISTS draw_row_family_annotations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_type  TEXT    NOT NULL,
    draw          TEXT    NOT NULL,
    row_family    TEXT    NOT NULL,
    reason        TEXT,
    source_task   TEXT,
    created_at    TEXT    DEFAULT (datetime('now')),
    UNIQUE(lottery_type, draw)
);
```

Populated via Python script (handles SMALL_POOL_ALIEN via `max(json.loads(numbers)) <= 25`).

---

## 5. SMALL_POOL Handling

JSON1/json_each is available in this SQLite instance. The canonical view can filter SMALL_POOL_ALIEN directly:
```sql
AND (SELECT MAX(CAST(j.value AS INTEGER)) FROM json_each(d.numbers) j) > 25
```
This handles all three non-canonical families in a single SQL view — no Python post-filter needed at the DB level.

---

## 6. Future Type D Apply Checklist

> **IMPORTANT: No step below may be executed without explicit Type D human gate authorization.**

1. **Backup:** `cp lottery_api/data/lottery_v2.db backups/p247a_backup_YYYYMMDD.db && sha256sum backups/p247a_backup_*.db`
2. **Create view:** Execute `CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical_main AS ...`
3. **Create annotation table:** Execute DDL + Python populate script
4. **Post-apply validation:**
   - `SELECT COUNT(*) FROM draws_big_lotto_canonical_main;` → expect 2,113
   - `SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO';` → expect 22,238 (unchanged)
   - `SELECT COUNT(*) FROM strategy_prediction_replays;` → expect 94,924 (unchanged)
   - `PRAGMA integrity_check;` → expect `ok`
   - Non-BIG_LOTTO draw counts unchanged
5. **Update test assertion:** `test_p238b` `>= 22238` → `>= 2113` (canonical view)
6. **Confirm GATE_RED stays** until separate re-authorization after validation

---

## 7. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No CREATE VIEW/TABLE executed | ✅ dry-run only |
| No row deletion | ✅ confirmed |
| No migration applied | ✅ plan only |
| Add-on rows preserved | ✅ view is additive; raw table unchanged |
| Type D authorization required | ✅ explicit gate required |
| GATE_RED maintained | ✅ no change without authorization + validation |

**ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records. They remain in the raw DB and are accessible via `get_all_draws()`. The canonical view excludes them from research but does not delete them.**

**Final Classification:** `P247A_BIG_LOTTO_CANONICAL_DB_SEPARATION_DRYRUN_PLAN_COMPLETE`
