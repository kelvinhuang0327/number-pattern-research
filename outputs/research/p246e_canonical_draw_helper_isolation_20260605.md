# P246E — Canonical Draw Helper Isolation

**Task ID:** P246E · **Date:** 2026-06-05 · **Type:** Phase 1 code implementation (no DB write).
**Final Classification:** `P246E_CANONICAL_DRAW_HELPER_ISOLATION_COMPLETE`

> **務必真正隔離大樂透加開號碼 — Implemented:** `get_canonical_draws()` now excludes all three non-canonical BIG_LOTTO row families. Canonical count confirmed: **2,113 rows**. Raw records (22,238) preserved. No DB write.

---

## 1. Executive Summary

Phase 1 isolation is complete:
- `get_canonical_draws(lottery_type)` added to `lottery_api/database.py`
- `tools/quick_predict.py` `load_history()` updated to use canonical helper
- BIG_LOTTO canonical draw count: **2,113** (was 22,238 — 90.5% non-canonical rows excluded)
- Add-on/special prize records preserved in raw DB; accessible via `get_all_draws()`
- **No DB write. No deletion. No migration.**

---

## 2. What Code Was Changed

### `lottery_api/database.py` — new method `get_canonical_draws()`

Added after `get_all_draws()`. For BIG_LOTTO, applies a three-family exclusion filter:

```python
def get_canonical_draws(self, lottery_type: str, limit: Optional[int] = None) -> List[Dict]:
    """
    Return only canonical main-draw rows for the given lottery type.

    For BIG_LOTTO, excludes:
      - ADD_ON_PRIZE_EXCLUDED: hyphenated draw IDs (e.g. 103000009-01)
        These are valid lottery-related add-on/special prize records.
        Excluded due to population mismatch, NOT data falseness.
      - DATE_FORMAT_ALIEN: 8-digit YYYYMMDD draw IDs (e.g. 20090727)
      - SMALL_POOL_ALIEN: serial IDs where max(numbers) <= 25
    Raw history: get_all_draws() and get_draws() remain unchanged.
    """
```

### `tools/quick_predict.py` — `load_history()` updated

**Before:**
```python
history = db.get_all_draws(lottery_type=lottery_type)  # 22,238 BIG_LOTTO rows
```

**After:**
```python
history = db.get_canonical_draws(lottery_type=lottery_type)  # 2,113 canonical rows
```

---

## 3. Exact Isolation Rules

| Step | Filter | Family excluded | Count |
|---|---|---|---|
| SQL | `draw NOT LIKE '%-%'` | ADD_ON_PRIZE_EXCLUDED | 19,100 |
| SQL | `NOT (LENGTH(draw)=8 AND draw LIKE '20%')` | DATE_FORMAT_ALIEN | 375 |
| Python | `max(numbers) > 25` (post-parse) | SMALL_POOL_ALIEN | ~650 |
| **Result** | | **CANONICAL_MAIN_DRAW** | **2,113** |

---

## 4. How Add-on Rows Are Preserved

`get_all_draws('BIG_LOTTO')` and `get_draws(lottery_type='BIG_LOTTO')` are **unchanged** and continue to return all 22,238 rows including 19,100 ADD_ON_PRIZE_EXCLUDED rows.

Add-on/special prize records are **valid lottery-related records**. They are excluded from canonical research due to **population mismatch**, not because they are fake or invalid. They remain in the DB and are accessible for display/history/audit purposes.

---

## 5. Which Callers Were Updated

| Caller | Change |
|---|---|
| `tools/quick_predict.py` `load_history()` | `get_all_draws()` → `get_canonical_draws()` |

**Callers that were NOT changed (display/history — correct):**

| Caller | Reason |
|---|---|
| `lottery_api/database.py` `get_draws()` | Paged display endpoint — shows all records |
| `lottery_api/database.py` `get_all_draws()` | History endpoint — shows all records |
| Any API/frontend draw history endpoint | Valid to show add-on records with labeling |

---

## 6. What Remains for Future Work

| Phase | Action | Authorization |
|---|---|---|
| **2** | `CREATE VIEW draws_big_lotto_canonical_main` | Type D required |
| **3** | `CREATE TABLE draw_row_family_annotations` | Type D required |
| **4** | Re-run P238B NIST on canonical population (~2,113 rows) | No DB write |
| **4** | Update `test_p238b` assertion `>= 22238` → `>= 2113` | No DB write |
| — | Verify RSM / engine callers use canonical helper | Code review |

---

## 7. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| No migration | ✅ confirmed |
| Add-on rows preserved | ✅ `get_all_draws()` returns all 22,238 |
| No registry mutation | ✅ confirmed |
| No production recommendation change | ✅ confirmed |
| No strategy promotion | ✅ confirmed |
| BIG_LOTTO research gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |
| Type D for Phase 2/3 | ✅ required — not authorized here |

**Final Classification:** `P246E_CANONICAL_DRAW_HELPER_ISOLATION_COMPLETE`
