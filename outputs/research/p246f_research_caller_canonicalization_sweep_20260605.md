# P246F — Research Caller Canonicalization Sweep

**Task ID:** P246F · **Date:** 2026-06-05 · **Type:** Source scan + targeted code updates.
**No DB write performed.**
**Final Classification:** `P246F_RESEARCH_CALLER_CANONICALIZATION_SWEEP_COMPLETE`

> **務必持續確認大樂透加開號碼已被隔離於策略/研究/回測之外.** P246F updates `tools/rsm_bootstrap.py` and `lottery_api/engine/core_satellite.py` to use `get_canonical_draws()`. Combined with P246E (`tools/quick_predict.py`), 3 confirmed research callers are now canonicalized.

---

## 1. Executive Summary

P246E established `get_canonical_draws()` and updated `quick_predict.py`. P246F extends isolation to two more confirmed research/strategy callers and documents the full caller classification for the codebase.

| File | Classification | Updated | Notes |
|---|---|---|---|
| `tools/quick_predict.py:169` | UPDATED_TO_CANONICAL | P246E | Primary prediction entry point |
| `tools/rsm_bootstrap.py:118` | UPDATED_TO_CANONICAL | **P246F** | RSM strategy bootstrap |
| `lottery_api/engine/core_satellite.py:373` | UPDATED_TO_CANONICAL | **P246F** | Strategy generation from history |
| `analysis/p219_external_method_diagnostic_sweep.py` | ALREADY_CANONICAL | — | Uses `draw NOT LIKE '%-%'` |
| `lottery_api/database.py get_all_draws()` | RAW_DISPLAY_ALLOWED | — | Raw history endpoint, intentional |
| `lottery_api/engine/drift_detector.py` | POSSIBLY_AFFECTED_NEEDS_SCOPE | Deferred | Direct SQL `_load_draws()` |
| `lottery_api/routes/advanced_learning.py` | POSSIBLY_AFFECTED_NEEDS_SCOPE | Deferred | Scheduler path untraced |
| `lottery_api/backtest_framework.py` | POSSIBLY_AFFECTED_NEEDS_SCOPE | Deferred | Cascade risk |
| 60+ archived backtest/analysis scripts | POSSIBLY_AFFECTED_NEEDS_SCOPE | Deferred | Exploratory, bulk sweep needed |

**No DB write. No deletion. Raw add-on records preserved.**

---

## 2. What P246E Already Isolated

`get_canonical_draws("BIG_LOTTO")` filters:
- `draw NOT LIKE '%-%'` — 19,100 ADD_ON_PRIZE_EXCLUDED rows (add-on/special prize records, valid but excluded)
- `NOT (LENGTH(draw)=8 AND draw LIKE '20%')` — 375 DATE_FORMAT_ALIEN rows
- Python `max(numbers) > 25` — ~650 SMALL_POOL_ALIEN rows

Result: **2,113 canonical main draws** (confirmed by live DB read).

`tools/quick_predict.py` `load_history()` was updated in P246E.

---

## 3. Which Callers Were Updated in P246F

### `tools/rsm_bootstrap.py:118`

**Before:**
```python
draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
```

**After:**
```python
# Use canonical helper for BIG_LOTTO to exclude add-on/special prize records
draws = sorted(db.get_canonical_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
```

**Why:** RSM bootstrap feeds historical draws into `RollingStrategyMonitor.bootstrap()` to train and validate strategies. Using the mixed 22,238-row population would feed add-on records into strategy backtests.

### `lottery_api/engine/core_satellite.py:373`

**Before:**
```python
history = list(reversed(db.get_all_draws(args.lottery)))
```

**After:**
```python
# Use canonical helper so BIG_LOTTO research excludes add-on/special prize records.
history = list(reversed(db.get_canonical_draws(args.lottery)))
```

**Why:** Core-satellite generates prediction bets from history via `--from-history` flag. Using canonical ensures the strategy input excludes add-on records.

---

## 4. Which Callers Were Intentionally Not Changed

| Caller | Reason |
|---|---|
| `lottery_api/database.py get_all_draws()` | Display/history endpoint — valid to return all records |
| `lottery_api/database.py get_draws()` | Paged display endpoint — valid to return all records |
| `lottery_api/routes/ingest.py` | Ingestion and display routes — not research sample |
| `lottery_api/engine/drift_detector._load_draws()` | Uses direct SQLite; different update pattern; deferred to P246G |
| `lottery_api/routes/advanced_learning.py` | Scheduler `get_data()` path not fully traced; deferred |
| `lottery_api/backtest_framework.py` | Framework change cascades; dedicated scope needed |
| 60+ archived `lottery_api/*.py` and `tools/*.py` | Exploratory/historical; bulk sweep outside minimal P246F scope |

---

## 5. Which Callers Need Future Scope

| Future Task | Scope |
|---|---|
| **P246G** | `drift_detector._load_draws()` — add `AND draw NOT LIKE '%-%'` to direct SQL |
| **P246G** | Trace `advanced_learning.py` scheduler path |
| **P246G** | Bulk update `backtest_framework.py` + 60+ archived backtest/analysis scripts |
| **Phase 2 (Type D)** | `CREATE VIEW draws_big_lotto_canonical_main` |
| **Phase 3 (Type D)** | `CREATE TABLE draw_row_family_annotations` |
| **Phase 4** | Re-run P238B NIST on canonical population; update test assertions |

---

## 6. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| No migration | ✅ confirmed |
| Add-on rows preserved | ✅ get_all_draws() returns all 22,238 rows |
| No frontend/display change | ✅ display callers intentionally not changed |
| No registry mutation | ✅ confirmed |
| No production recommendation change | ✅ confirmed |
| BIG_LOTTO research gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |

**ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records. They remain in the DB and are accessible via `get_all_draws()` for display/history purposes. Strategy/research/replay callers must use `get_canonical_draws()`.**

**Final Classification:** `P246F_RESEARCH_CALLER_CANONICALIZATION_SWEEP_COMPLETE`
