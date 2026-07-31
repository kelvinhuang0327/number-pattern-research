# P246G — Remaining BIG_LOTTO Research Caller Canonicalization

**Task ID:** P246G · **Date:** 2026-06-05 · **Type:** Targeted code updates + classification.
**No DB write performed.**
**Final Classification:** `P246G_REMAINING_BIG_LOTTO_CALLER_CANONICALIZATION_COMPLETE`

---

## 1. Executive Summary

P246G handles the three deferred paths from P246F and completes the main active research caller sweep.

| File | Status | P246G Action |
|---|---|---|
| `lottery_api/engine/drift_detector._load_draws()` | **UPDATED** | Added BIG_LOTTO canonical SQL + Python filter |
| `lottery_api/backtest_framework.BacktestEngine.backtest()` | **UPDATED** | `get_all_draws` → `get_canonical_draws` |
| `lottery_api/routes/advanced_learning.py` | **DEFERRED** | `scheduler.get_data()` path opaque |
| `lottery_api/*.py` (30+ archived) | DEFERRED | Archived/exploratory |

**Total P246E–G: 5 confirmed active research callers canonicalized.**

---

## 2. P246F Baseline

Already updated:
- `tools/quick_predict.py` (P246E)
- `tools/rsm_bootstrap.py` (P246F)
- `lottery_api/engine/core_satellite.py` (P246F)

Already canonical: `analysis/p219_external_method_diagnostic_sweep.py`

---

## 3. Deferred Callers Inspected

### `drift_detector._load_draws()` — UPDATED

**Problem:** Direct SQLite `SELECT numbers FROM draws WHERE lottery_type=? ORDER BY date ASC LIMIT ?` — no hyphen filter. Feeds PSI analysis (`check_drift()`) for drift/randomness detection.

**Fix applied:**
```python
# BIG_LOTTO: SQL canonical filter
c.execute(
    "SELECT numbers FROM draws "
    "WHERE lottery_type=? "
    "AND draw NOT LIKE '%-%' "
    "AND NOT (LENGTH(draw)=8 AND draw LIKE '20%') "
    "ORDER BY date ASC LIMIT ?",
    (lottery_type, limit)
)
# Python post-filter: exclude SMALL_POOL_ALIEN
if lottery_type == 'BIG_LOTTO' and parsed and max(parsed) <= 25:
    continue
```

Non-BIG_LOTTO: original SQL unchanged.

### `backtest_framework.BacktestEngine.backtest()` — UPDATED

**Before:** `all_history = self.db.get_all_draws(lottery_type)`  
**After:** `all_history = self.db.get_canonical_draws(lottery_type)`

### `advanced_learning.py` — DEFERRED

Both `run_multi_stage_optimization()` and `run_adaptive_window_optimization()` call `scheduler.get_data(lottery_type)`. The scheduler implementation is not a direct DatabaseManager call — tracing it requires reading the scheduler module and potentially editing production API route behavior. **Deferred** to avoid unintended API behavior change.

---

## 4. Add-on Records Preserved

`get_all_draws("BIG_LOTTO")` returns all 22,238 rows including 19,100 ADD_ON_PRIZE_EXCLUDED.  
These are valid lottery-related records excluded from research due to **population mismatch**, not data falseness.

---

## 5. Remaining Future Work

| Task | Scope |
|---|---|
| Trace `scheduler.get_data()` | Understand data path; add canonical filter if applicable |
| Bulk update 60+ archived scripts | Low priority; not active production |
| Phase 2 (Type D) | `CREATE VIEW draws_big_lotto_canonical_main` |
| Phase 3 (Type D) | `CREATE TABLE draw_row_family_annotations` |
| Phase 4 | Re-run P238B NIST; update test assertions |

---

## 6. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| No migration | ✅ confirmed |
| Add-on rows preserved | ✅ get_all_draws() unchanged |
| No frontend/display change | ✅ confirmed |
| No registry mutation | ✅ confirmed |
| BIG_LOTTO gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |

**Final Classification:** `P246G_REMAINING_BIG_LOTTO_CALLER_CANONICALIZATION_COMPLETE`
