# P246J — BIG_LOTTO Add-on Isolation Arc Closure

**Task ID:** P246J · **Date:** 2026-06-06 · **Type:** Arc closure summary (read-only).
**No DB write performed. No deletion. No migration.**
**Final Classification:** `P246J_BIG_LOTTO_ADDON_ISOLATION_ARC_CLOSED`

> **務必確認大樂透加開號碼已被隔離於策略/研究/回測之外。Confirmed:** 6 active production research callers now use `get_canonical_draws()` or equivalent canonical BIG_LOTTO filter. Add-on records are preserved, valid, and raw-accessible. GATE_RED remains pending DB-level separation.

---

## 1. Executive Summary

The P246B–I arc corrected the BIG_LOTTO data taxonomy, designed a preserve-and-isolate architecture, implemented code-level canonical filters across all identified active production research paths, and annotated outdated population assumptions in tests/artifacts.

**Key outcome:** Strategy/research/replay/learning callers that were consuming raw BIG_LOTTO draws (including 19,100 add-on/special prize records) now receive only canonical 6/49 main draws (~2,113) via `get_canonical_draws()` or equivalent.

**ADD_ON_PRIZE_EXCLUDED records are valid lottery-related records.** They remain in the raw DB and are accessible via `get_all_draws()` for display/history. They are excluded from canonical research due to population mismatch, NOT data falseness.

---

## 2. P246B–I Timeline

| Task | Title | Outcome | PR |
|---|---|---|---|
| **P246** | Data-Integrity Audit | 22,238 total; 2,113 canonical; 3 non-canonical families identified | #316 |
| **P246B** | Taxonomy Correction | SIM_HYPHEN → ADD_ON_PRIZE_EXCLUDED (valid add-on records, not fake) | #317 |
| **P246C** | Impact Audit | database.py DIRECTLY_AFFECTED; P219 NOT_AFFECTED (already filtered) | #318 |
| **P246D** | Segregation Design | Phase 1 code helper / Phase 2 SQL view (Type D) / Phase 3 annotation (Type D) | #319 |
| **P246E** | Canonical Draw Helper | `get_canonical_draws()` + `quick_predict.py` | #320 |
| **P246F** | Research Caller Sweep | `rsm_bootstrap.py` + `core_satellite.py` | #321 |
| **P246G** | Remaining Callers | `drift_detector._load_draws()` + `backtest_framework.py` | #322 |
| **P246H** | Scheduler Trace | `scheduler.get_data()` → all advanced_learning callers | #323 |
| **P246I** | Population Assertion Cleanup | Added inline comments to `test_p238b` and `test_p243a` | #324 |
| **P246J** | Arc Closure | This document | #325 |

---

## 3. Canonicalized Caller Table

| File | Function | Change | Task | Status |
|---|---|---|---|---|
| `lottery_api/database.py` | `get_canonical_draws()` [NEW] | New helper: SQL filter + Python max>25 | P246E | ✅ CANONICAL |
| `tools/quick_predict.py` | `load_history()` | `get_all_draws` → `get_canonical_draws` | P246E | ✅ CANONICAL |
| `tools/rsm_bootstrap.py` | `run_rsm()` | `get_all_draws` → `get_canonical_draws` | P246F | ✅ CANONICAL |
| `lottery_api/engine/core_satellite.py` | `--from-history` | `get_all_draws` → `get_canonical_draws` | P246F | ✅ CANONICAL |
| `lottery_api/engine/drift_detector.py` | `_load_draws()` | Direct SQL: BIG_LOTTO branch + Python filter | P246G | ✅ CANONICAL |
| `lottery_api/backtest_framework.py` | `BacktestEngine.backtest()` | `get_all_draws` → `get_canonical_draws` | P246G | ✅ CANONICAL |
| `lottery_api/utils/scheduler.py` | `get_data()` | Return-time canonical filter for BIG_LOTTO | P246H | ✅ CANONICAL |
| `analysis/p219_external_method_diagnostic_sweep.py` | query | Pre-existing `draw NOT LIKE '%-%'` filter | pre-P246 | ✅ ALREADY CANONICAL |

**Raw display callers intentionally NOT changed:**
- `lottery_api/database.py get_all_draws()` — returns all 22,238 rows for display/history
- `lottery_api/database.py get_draws()` — paged display endpoint

---

## 4. Raw vs Canonical BIG_LOTTO Population

| Population | Count | Nature | Use |
|---|---|---|---|
| **raw_total** | 22,238 | All DB rows | Display/history, DB integrity tests |
| **ADD_ON_PRIZE_EXCLUDED** | 19,100 | Valid add-on/special prize records | Raw display with labeling |
| DATE_FORMAT_ALIEN | 375 | Non-canonical (numbers ≠ 6/49) | Non-canonical concern |
| SMALL_POOL_ALIEN | ~650 | Likely mislabeled game (max≤25) | Non-canonical concern |
| **CANONICAL_MAIN_DRAW** | **~2,113** | True 6/49 main draws | Research, strategy, backtest, PSI |

---

## 5. Evidence That Add-on Records Are Preserved

- `lottery_api/data/lottery_v2.db` raw DB: 22,238 BIG_LOTTO rows unchanged. No deletion performed.
- `lottery_api/database.py get_all_draws('BIG_LOTTO')` still returns all 22,238 rows.
- `lottery_api/utils/scheduler.py data_by_type['BIG_LOTTO']` raw cache preserved; canonical filter applied only at `get_data()` return time.
- ADD_ON_PRIZE_EXCLUDED records (e.g. `103000009-01`) remain accessible for display/audit.

---

## 6. Remaining Risks

| Risk | Severity | Resolution |
|---|---|---|
| No DB-level canonical view yet (Phase 2 Type D) | MEDIUM | P247 Type D — separate authorization required |
| No row-family annotation table yet (Phase 3 Type D) | LOW | P247 Phase 3 Type D |
| `optimization.py:90` still calls `get_all_draws()` unfiltered | LOW | Mitigated by `scheduler.get_data()` filter; lower-priority cleanup |
| 60+ archived/exploratory scripts not updated | LOW | Non-production; bulk sweep if activated |
| P238B NIST artifact reflects raw 22,238-row population | MEDIUM | P246K canonical re-audit after P247 Type D |
| GATE_RED_PENDING_CANONICAL_SEPARATION active | BY DESIGN | Lifted only after P247 Type D + canonical re-audit + authorization |

---

## 7. Gate Status

**Current: `GATE_RED_PENDING_CANONICAL_SEPARATION`**

The code-level isolation (P246E–H) ensures active production research paths do not consume add-on records. However, the DB-level canonical view and annotation table (Phase 2/3 Type D) have not been executed. The gate remains RED for new BIG_LOTTO research directions.

**Unblock conditions:**
1. P247 Type D executed (canonical view + annotation table)
2. Canonical re-audit (P246K equivalent) passes
3. Explicit governance authorization
4. Drift guard + replay integrity confirmed

---

## 8. Recommended Next Step

**Primary (no DB write): P246K** — Run canonical NIST randomness audit on ~2,113 BIG_LOTTO canonical draws. Confirm whether P238B YELLOW finding stands on the clean population. No Type D needed.

**Alternative (Type D required): P247** — Execute DB-level `CREATE VIEW draws_big_lotto_canonical_main` and `CREATE TABLE draw_row_family_annotations`.

---

## 9. Governance

| Rule | Status |
|---|---|
| No DB write (P246B–J) | ✅ confirmed |
| No row deletion | ✅ confirmed |
| No migration | ✅ confirmed |
| Add-on rows preserved | ✅ raw DB and scheduler cache unchanged |
| No registry mutation | ✅ confirmed |
| No production recommendation change | ✅ confirmed |
| GATE_RED maintained | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |

**Final Classification:** `P246J_BIG_LOTTO_ADDON_ISOLATION_ARC_CLOSED`
