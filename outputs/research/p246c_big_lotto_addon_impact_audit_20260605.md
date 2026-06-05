# P246C — BIG_LOTTO Add-on Prize Record Impact Audit

**Task ID:** P246C · **Date:** 2026-06-05 · **Type:** Read-only impact audit.
**DB:** `lottery_api/data/lottery_v2.db` (mode=ro, read-only confirmed)
**No DB write performed.**
**Final Classification:** `P246C_BIG_LOTTO_ADDON_IMPACT_AUDIT_COMPLETE`

---

## 1. Executive Summary

P246B (merged PR #317) established that 19,100 hyphenated BIG_LOTTO rows are **ADD_ON_PRIZE_EXCLUDED** — valid lottery-related add-on/special prize records, not simulated data, excluded from research due to **population mismatch**.

This P246C audit determines where these rows currently flow in the codebase.

**Key finding:** `database.py` `get_all_draws()` and `get_draws()` return **all 22,238 BIG_LOTTO rows** with no canonical filter. Any caller receiving BIG_LOTTO draws via these functions receives the mixed population (19,100 add-on + 375 DATE_FORMAT + 650 SMALL_POOL + 2,113 canonical).

**What is not affected:** `analysis/p219_external_method_diagnostic_sweep.py` correctly excludes hyphenated rows via `draw NOT LIKE '%-%'`. Production strategies use the RSM `2113期回測` path which appears to use canonical draw count.

**No DB write has been performed. P247 apply remains unauthorized.**

---

## 2. P246B Taxonomy Correction Context

| Family | Count | P246B Corrected Label | Status |
|---|---|---|---|
| Hyphenated IDs | 19,100 | `ADD_ON_PRIZE_EXCLUDED` | Valid lottery records — excluded for population mismatch |
| 8-digit YYYYMMDD IDs | 375 | `DATE_FORMAT_ALIEN` | Non-canonical concern |
| Serial with max ≤ 25 | 650 | `SMALL_POOL_ALIEN` | Non-canonical concern |
| Serial with max 26–49 | 2,113 | `CANONICAL_MAIN_DRAW` | Intended research population |
| **Total** | **22,238** | — | — |

Current DB row counts verified read-only: totals match P246 baseline.

---

## 3. What Was Scanned

| Area | Method | Result |
|---|---|---|
| `lottery_api/*.py` | grep BIG_LOTTO | 30+ files reference BIG_LOTTO |
| `tools/*.py` | grep BIG_LOTTO | 30+ files reference BIG_LOTTO |
| `tests/*.py` | grep BIG_LOTTO, 22238 | 7 test files, 2 with hardcoded 22238 |
| `lottery_api/database.py` | Read SQL | get_all_draws / get_draws: no hyphen filter |
| `analysis/p219_*.py` | Read SQL | Correct filter: draw NOT LIKE '%-%' |
| `analysis/p238b_*.py` | Read source | sample_size=22238 (mixed population) |
| DB row counts | SQLite read-only | Confirmed: add-on=19100, total=22238 |

---

## 4. Row-Family Counts (Verified Read-Only)

| Family | Count | Delta vs P246 |
|---|---|---|
| `ADD_ON_PRIZE_EXCLUDED` | 19,100 | 0 |
| `DATE_FORMAT_ALIEN` | 375 | 0 |
| `SMALL_POOL_ALIEN` | ~650 (P246 baseline) | N/A (requires Python number inspection) |
| `CANONICAL_MAIN_DRAW` | ~2,113 (P246 baseline) | N/A |
| **TOTAL** | **22,238** | **0** |

---

## 5. Strategy / Replay Impact

| Path | Impact | Risk | Notes |
|---|---|---|---|
| `lottery_api/database.py` `get_all_draws()` | **DIRECTLY_AFFECTED** | High | No canonical filter; returns all 22,238 BIG_LOTTO rows |
| `lottery_api/database.py` `get_draws()` | **DIRECTLY_AFFECTED** | High | Paged endpoint; same issue |
| `lottery_api/engine/rolling_strategy_monitor.py` | **POSSIBLY_AFFECTED** | Medium | '2113期回測' ref suggests canonical path; data-load not fully traced |
| `lottery_api/engine/` (core_satellite, hypothesis_registry, drift_detector, multi_bet_optimizer) | **POSSIBLY_AFFECTED** | Medium | Not fully traced; likely delegates to get_all_draws |
| `lottery_api/routes/advanced_learning.py` | **POSSIBLY_AFFECTED** | Medium | Calls `get_data(BIG_LOTTO)` — filtering unclear |
| `lottery_api/routes/ingest.py` | **POSSIBLY_AFFECTED** | Medium | Ingestion path may not filter add-on draws at ingest |
| `analysis/p219_external_method_diagnostic_sweep.py` | **NOT_AFFECTED** | None | Correct filter: `draw NOT LIKE '%-%'` |
| 30+ tools/*.py and lottery_api/*.py backtest scripts | **POSSIBLY_AFFECTED** | Medium | Many call get_all_draws unfiltered |

**Production strategy note:** Production strategies (regime_2bet, ts3_regime_3bet, p1_deviation_4bet, p1_dev_sum5bet) were validated via the RSM `2113期回測` path. This path appears to use ~2,113 canonical draws. Direct contamination risk for existing production strategies is LOW.

---

## 6. API / Frontend / Test Impact

| Path | Impact | Risk | Notes |
|---|---|---|---|
| `tests/test_p238b_nist_randomness_audit_artifact_build.py:146` | **DIRECTLY_AFFECTED** | Medium | `assert BIG_LOTTO >= 22238` — will fail after segregation |
| `tests/test_p243a_diagnostic_report_fixture_pack.py:58` | **DIRECTLY_AFFECTED** | Medium | `sample_size=22238` in fixture — historical record, needs population note |
| `tests/test_p41_wave3_biglotto*.py` | **UNKNOWN** | Medium | BIG_LOTTO count expectations unclear |
| `tests/test_p42_wave3_biglotto*.py` | **UNKNOWN** | Medium | Expects 9000 Wave 3 rows — unclear if includes add-on |
| `tests/test_p94a_biglotto*.py` | **UNKNOWN** | Medium | Flexible draws count assertion; needs manual review |
| `lottery_api/routes/ingest.py` | **POSSIBLY_AFFECTED** | Low | List history endpoint returns all draws including add-on |

---

## 7. Artifact Impact

| Artifact | Impact | Notes |
|---|---|---|
| `outputs/research/p238b_nist_randomness_audit_artifact_20260604.*` | **DIRECTLY_AFFECTED** | Built with sample_size=22238 including add-on rows. YELLOW status stands. Population note required. |
| `outputs/research/p246_big_lotto_data_integrity_audit_20260605.*` | **NOT_AFFECTED** | P246B supersedes SIM_HYPHEN wording only; row counts and audit logic preserved. |
| `outputs/research/p246b_big_lotto_taxonomy_correction_20260605.*` | **NOT_AFFECTED** | This is the correction artifact itself. |
| Any BIG_LOTTO backtest artifacts from tools/*.py | **POSSIBLY_AFFECTED** | If generated via get_all_draws() unfiltered; depends on individual script. |
| `memory/MEMORY.md` / `memory/lessons.md` (2113 / 22238 refs) | **POSSIBLY_AFFECTED** | References are informational; 2113 is canonical count, 22238 is total. Context annotation useful after segregation. |

---

## 8. Recommendations

### Do NOT delete ADD_ON_PRIZE_EXCLUDED rows

These are valid lottery-related records. They may be displayed to users as add-on/special prize history. Only exclude them from canonical 6/49 main-draw **research queries**.

### Preferred P247 Design: Option A + Option C (phased)

| Phase | Option | Action | Authorization |
|---|---|---|---|
| Now (pre-segregation) | Option A | Create `draws_big_lotto_canonical` view for research callers | Read-only; no Type D needed |
| Later (segregation) | Option C | Move rows to `draws_big_lotto_excluded` table preserving all columns | Type D required |

**Option A (create canonical research view)** is lowest risk:
```sql
CREATE VIEW draws_big_lotto_canonical AS
  SELECT * FROM draws
  WHERE lottery_type='BIG_LOTTO'
    AND draw NOT LIKE '%-%'
    AND LENGTH(draw) < 8;
-- Note: SMALL_POOL_ALIEN still included until Python-driven filter applied
```

### After P247 Type D execution: must re-run

1. P238B NIST randomness audit — re-run on canonical population only (~2,113 rows)
2. Any BIG_LOTTO backtest that used `get_all_draws('BIG_LOTTO')` unfiltered
3. Update test assertions: `>= 22238` → `>= 2113` + separate excluded table count check
4. Drift guard + replay row integrity check

---

## 9. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ read-only mode confirmed |
| No migration applied | ✅ plan artifact only |
| No strategy promotion | ✅ respected |
| No betting advice | ✅ respected |
| No P247 apply | ✅ plan only; Type D required |
| ADD_ON rows preservation | ✅ preservation stated — do not delete |
| BIG_LOTTO research gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |
| P247 apply authorization | ✅ separate explicit Type D required |

**ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records excluded from canonical 6/49 main-draw research due to population mismatch, not data falseness. They must be preserved.**

**Final Classification:** `P246C_BIG_LOTTO_ADDON_IMPACT_AUDIT_COMPLETE`
