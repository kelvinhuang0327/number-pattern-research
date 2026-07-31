# P246D — BIG_LOTTO Add-on Record Segregation Design

**Task ID:** P246D · **Date:** 2026-06-05 · **Type:** Read-only segregation design artifact.
**DB:** `lottery_api/data/lottery_v2.db` (mode=ro, read-only confirmed)
**No DB write performed.**
**Final Classification:** `P246D_BIG_LOTTO_ADDON_SEGREGATION_DESIGN_COMPLETE`

> **How to isolate BIG_LOTTO add-on numbers (務必確認如何隔離大樂透加開號碼):** Use a phased approach. Phase 1 (no DB write): add a `get_canonical_draws()` code helper that applies `AND draw NOT LIKE '%-%'` filter — this immediately excludes 19,100 add-on records from all research/strategy paths. Phase 2 (Type D): create a canonical SQL view in the DB. Phase 3 (Type D): add a row-family annotation table. Never delete add-on rows.

---

## 1. Executive Summary

BIG_LOTTO draws table: 22,238 total rows. Only 2,113 are canonical 6/49 main draws.

| Family | Count | % | Nature |
|---|---|---|---|
| `ADD_ON_PRIZE_EXCLUDED` | 19,100 | 85.9% | Add-on/special prize records — valid, preserve |
| `DATE_FORMAT_ALIEN` | 375 | 1.7% | Non-canonical date-format IDs — non-canonical concern |
| `SMALL_POOL_ALIEN` | ~650 | 2.9% | Likely mislabeled game (max ≤ 25) — non-canonical concern |
| `CANONICAL_MAIN_DRAW` | ~2,113 | 9.5% | True 6/49 draws — intended research population |

**Current gap:** `database.py` `get_all_draws()` and `get_draws()` return all 22,238 rows. Research callers like `quick_predict.py:169` receive the mixed population.

**Gold standard already exists:** `analysis/p219_external_method_diagnostic_sweep.py` uses `draw NOT LIKE '%-%'` filter — this is the correct reference pattern.

**No canonical view exists in DB yet.** (Confirmed via `sqlite_master` read.)

---

## 2. Why Add-on Records Must Be Preserved

ADD_ON_PRIZE_EXCLUDED rows (e.g. `100000009-01`) are **valid lottery-related records** representing add-on or special prize draws associated with BIG_LOTTO draw events. Per P246B user/domain correction:

- They are NOT fake, simulated, synthetic, or invalid data.
- They may have display/history/audit value.
- They must not be deleted.
- Exclusion from research is due to **population mismatch** (different record type than canonical 6/49 main draw), not data falseness.

---

## 3. Why Add-on Records Must Be Excluded from Canonical Research

- Add-on records are not comparable to canonical 6/49 main draws for statistical analysis.
- Including them inflates the apparent draw population from ~2,113 to 22,238.
- Strategy backtests using the mixed population get ~10× wrong sample size.
- Frequency analysis, rolling-window analysis, and baseline computation are all distorted.
- P219's structural-break signals were explained by DATE_FORMAT_ALIEN and SMALL_POOL_ALIEN (not add-on rows, which P219 already filtered).

---

## 4. How to Isolate Add-on Records Safely (Recommended Path)

### Phase 1 — Code-level canonical query helper (No DB write required)

**Add `get_canonical_draws(lottery_type)` to `lottery_api/database.py`:**

```python
def get_canonical_draws(self, lottery_type: str) -> list:
    """Return only canonical main-draw rows for the given lottery type.
    For BIG_LOTTO: excludes ADD_ON_PRIZE_EXCLUDED (hyphenated IDs) and DATE_FORMAT_ALIEN.
    Note: SMALL_POOL_ALIEN requires additional Python filter: max(row['numbers']) > 25
    """
    conn = self._get_connection()
    cursor = conn.cursor()
    if lottery_type == 'BIG_LOTTO':
        cursor.execute("""
            SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount
            FROM draws
            WHERE lottery_type = 'BIG_LOTTO'
              AND draw NOT LIKE '%-%'
              AND NOT (LENGTH(draw) = 8 AND draw LIKE '20%')
            ORDER BY CAST(draw AS INTEGER) DESC
        """)
    else:
        # Other lottery types: no non-canonical rows known; use standard query
        cursor.execute(
            "SELECT id, draw, date, lottery_type, numbers, special, jackpot_amount "
            "FROM draws WHERE lottery_type = ? ORDER BY CAST(draw AS INTEGER) DESC",
            (lottery_type,)
        )
    rows = cursor.fetchall()
    # For BIG_LOTTO: Python-driven SMALL_POOL_ALIEN exclusion
    if lottery_type == 'BIG_LOTTO':
        import json as _json
        rows = [r for r in rows if max(_json.loads(r['numbers'])) > 25]
    conn.close()
    return [dict(r) for r in rows]
```

**Callers to update (Phase 1):**

| Caller | Line | Change |
|---|---|---|
| `tools/quick_predict.py` | 169 | `get_all_draws(BIG_LOTTO)` → `get_canonical_draws(BIG_LOTTO)` |
| `lottery_api/engine/rolling_strategy_monitor.py` | — | Verify data-load path; switch if needed |
| `lottery_api/engine/core_satellite.py` | — | Verify; switch if needed |
| `lottery_api/routes/advanced_learning.py` | — | Verify `get_data()` path |
| `tools/*.py` backtest scripts | — | Batch update for research scripts |

**Callers to NOT update (keep full population):**

| Caller | Reason |
|---|---|
| `lottery_api/database.py` `get_draws()` | Display/paged history — valid to show add-on records |
| `lottery_api/database.py` `get_all_draws()` | History endpoint — valid to return full records |
| Any `GET /draws` or `GET /history` API endpoint | Display to users — add labeling instead |

### Phase 2 — Canonical SQL view in DB (Type D required)

```sql
CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical_main AS
  SELECT * FROM draws
  WHERE lottery_type = 'BIG_LOTTO'
    AND draw NOT LIKE '%-%'
    AND NOT (LENGTH(draw) = 8 AND draw LIKE '20%');
-- Note: SMALL_POOL_ALIEN still present (~650 rows); use Phase 3 annotation for full isolation
```

> **Requires separate explicit Type D authorization.** No DB write performed in this task.

### Phase 3 — Row-family annotation table (Type D required)

```sql
CREATE TABLE IF NOT EXISTS draw_row_family_annotations (
    draw TEXT NOT NULL,
    lottery_type TEXT NOT NULL,
    row_family TEXT NOT NULL,        -- ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, etc.
    exclusion_reason TEXT,
    annotated_at TEXT,
    PRIMARY KEY (draw, lottery_type)
);
```

Python-driven population handles SMALL_POOL_ALIEN (max(numbers) ≤ 25 detection).

> **Requires separate explicit Type D authorization.**

### Phase 4 — Re-validate affected artifacts and tests

After Type D phases are executed:

1. Re-run P238B NIST audit on canonical population (~2,113 rows)
2. Update `test_p238b`: `assert BIG_LOTTO >= 22238` → `assert BIG_LOTTO >= 2113`
3. Add population note to `test_p243a` fixture (`sample_size=22238` is total, not canonical)
4. Drift guard + replay row integrity (must remain 94,924)

---

## 5. Rejected Approach: Direct Deletion

**Direct deletion of ADD_ON_PRIZE_EXCLUDED rows is REJECTED.**

- These are valid lottery-related records.
- Deletion is irreversible (without backup restore).
- Violates P246B preservation policy.
- The correct approach is isolation/filtering, not deletion.

---

## 6. API / Frontend Display Policy

| Path type | Rule |
|---|---|
| Research / strategy / replay / randomness audit | **Must use canonical filter** — `draw NOT LIKE '%-%'` + Python SMALL_POOL filter |
| Display / history / user-facing endpoints | **May show all rows** — should label add-on records as `ADD_ON_PRIZE_EXCLUDED` / `加碼/特別獎` |
| New add-on draw display field suggestion | `"row_family": "ADD_ON_PRIZE_EXCLUDED", "label": "加碼/特別獎記錄"` |

---

## 7. Future Type D Apply Checklist

Before any Phase 2/3 DB write is authorized:

- [ ] Phase 1 (code helper) implemented, tested, and merged
- [ ] Dev branch (not main) checked out
- [ ] DB backup created with SHA256
- [ ] Replay rows = 94,924 (read-only check)
- [ ] `PRAGMA integrity_check = ok`
- [ ] No other DB write in progress
- [ ] Phase 0 checks pass

After apply:

- [ ] `SELECT COUNT(*) FROM draws_big_lotto_canonical_main` — expect ~2,113
- [ ] Replay rows unchanged
- [ ] `PRAGMA integrity_check`
- [ ] Non-BIG_LOTTO counts unchanged
- [ ] Affected tests updated

---

## 8. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ read-only confirmed |
| No row deletion | ✅ rejected; preservation required |
| No strategy code change now | ✅ design only |
| No API/frontend code change now | ✅ design only |
| No P247 apply | ✅ plan only; Type D required |
| P247 apply authorization | ✅ separate explicit Type D required |
| BIG_LOTTO research gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |
| Replay rows | ✅ 94,924 unchanged |

**Final Classification:** `P246D_BIG_LOTTO_ADDON_SEGREGATION_DESIGN_COMPLETE`
