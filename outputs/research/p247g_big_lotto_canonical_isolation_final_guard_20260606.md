# P247G — BIG_LOTTO Canonical Isolation Final Guard

**Date:** 2026-06-06 12:26:19  
**Task:** P247G  
**Classification:** CANONICAL_ISOLATION_FINAL_GUARD  

## Executive Summary

P247G is the final verification task in the P247 arc (A→F). The DB view, helper, and all active research/analysis/strategy paths are confirmed to use the canonical BIG_LOTTO 2,113-row main-draw sample. Raw 22,238-row access is preserved for display/history paths. A regression guard test is added to prevent future regressions. No DB write was performed.

## Current DB/Helper State

| Metric | Value | Expected |
|--------|-------|----------|
| View `draws_big_lotto_canonical_main` rows | 2113 | 2113 |
| `get_canonical_draws('BIG_LOTTO')` rows | 2113 | 2113 |
| Raw BIG_LOTTO rows | 22238 | 22238 |
| ADD_ON_PRIZE_EXCLUDED raw | 19100 | 19100 |
| DB integrity | ok | ok |
| Annotation table | False | False |

## Active Canonicalized Path Table

| Path | Classification | Status |
|------|---------------|--------|
| `tools/quick_predict.py` | ALREADY_HELPER_CANONICAL | OK |
| `tools/rsm_bootstrap.py` | ALREADY_HELPER_CANONICAL | OK |
| `lottery_api/backtest_framework.py` | ALREADY_HELPER_CANONICAL | OK |
| `lottery_api/engine/core_satellite.py` | ALREADY_HELPER_CANONICAL | OK |
| `lottery_api/engine/drift_detector.py` | ALREADY_OWN_CANONICAL_FILTER | OK |
| `lottery_api/utils/scheduler.py` | ALREADY_OWN_CANONICAL_FILTER | OK |
| `tools/analyze_banker_accuracy.py` | UPDATED_TO_CANONICAL | OK |
| `tools/analyze_banker_plus_kill.py` | UPDATED_TO_CANONICAL | OK |
| `tools/analyze_biglotto_special.py` | UPDATED_TO_CANONICAL | OK |
| `tools/analyze_market_temperature.py` | UPDATED_TO_CANONICAL | OK |
| `tools/analyze_top_n_for_2.py` | UPDATED_TO_CANONICAL | OK |
| `tools/audit_big_lotto_3bet.py` | UPDATED_TO_CANONICAL | OK |
| `tools/audit_big_lotto_baseline.py` | UPDATED_TO_CANONICAL | OK |
| `tools/audit_big_lotto_hyper.py` | UPDATED_TO_CANONICAL | OK |
| `tools/audit_big_lotto_rigorous.py` | UPDATED_TO_CANONICAL | OK |

## Raw Preserved Path Table

| Path | Classification | Reason |
|------|---------------|--------|
| `lottery_api/routes/prediction.py` | RAW_HISTORY_ALLOWED | API prediction routes serve all lottery types including raw  |
| `lottery_api/routes/history.py` | RAW_HISTORY_ALLOWED | History display endpoint must show all row families |
| `lottery_api/common.py` | RAW_HISTORY_ALLOWED | Common history loader for display paths |

## Regression Guard Behavior

The test `tests/test_p247g_big_lotto_canonical_isolation_final_guard.py` contains:

- **`test_active_paths_use_canonical`** (15 parametrized cases): fails if any active BIG_LOTTO research path uses `get_all_draws('BIG_LOTTO')` raw call.
- **`test_active_paths_have_canonical_pattern`**: confirms each active path contains the expected canonical pattern string.
- **`test_view_still_canonical`**: live DB check, view=2,113 rows.
- **`test_raw_preserved`**: confirms get_all_draws/get_draws still exist in database.py.

Deferred archived scripts (`lottery_api/backtest_115000*.py` etc.) are explicitly excluded from the guard — they are not in the active pipeline.

## Deferred Archived/Exploratory Risks

- **`lottery_api/backtest_115000*.py`** (DEFERRED_ARCHIVED): One-off historical backtest scripts, not in active pipeline
- **`lottery_api/backtest_big_lotto_2025_ensemble.py`** (DEFERRED_ARCHIVED): Archived ensemble backtest script
- **`lottery_api/predict_*.py`** (DEFERRED_ARCHIVED): Archived one-off predict scripts
- **`lottery_api/compare_*.py`** (DEFERRED_ARCHIVED): Historical comparison scripts, not in active pipeline

**Risk:** If archived scripts are reactivated without migration, they will use raw `get_all_draws('BIG_LOTTO')` which returns 22,238 rows including add-on records. Mitigation: run the P247G guard tests when reactivating any archived BIG_LOTTO script.

## Recommended Next Task

P247 arc (A→G) is complete. Remaining work is DEFERRED:
1. Archived scripts in `lottery_api/` — migrate to `get_canonical_draws()` if/when reactivated.
2. Annotation table (`draw_row_family_annotations`) — requires separate Type D authorization.

## P247 Arc Summary

| Task | Description |
|------|-------------|
| P247A | Dry-run plan for DB canonical view |
| P247B | CREATE VIEW `draws_big_lotto_canonical_main` (Type D apply) |
| P247C | Post-apply reconciliation + P247A test cleanup |
| P247D | Consumer adoption audit (21 paths classified) |
| P247E | `get_canonical_draws()` updated to use view internally |
| P247F | 9 analysis tools migrated to `get_canonical_draws()` |
| **P247G** | **Final verification and regression guard** |

## Compliance Statements

- **No DB write performed in P247G.**
- **No rows deleted, updated, or inserted** in any draws table.
- **ADD_ON_PRIZE_EXCLUDED records remain valid and raw-accessible.**   19100 hyphenated BIG_LOTTO records exist in the raw draws table.
- **No annotation table** was created.
- **No strategy logic change** was made.
- **No registry or production recommendation** was modified.

---
*Generated by P247G — BIG_LOTTO canonical isolation final guard*