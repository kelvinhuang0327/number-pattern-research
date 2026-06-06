# P247D — BIG_LOTTO Canonical View Consumer Adoption Audit

**Date:** 2026-06-06 11:57:52  
**Task:** P247D  
**Classification:** CONSUMER_ADOPTION_AUDIT_READ_ONLY  

## Executive Summary

P247D audits which code paths already adopt `draws_big_lotto_canonical_main` or its equivalent helper `get_canonical_draws()`, and which should be updated in future scopes. The DB view (2,113 rows) is confirmed present. The production prediction pipeline (`backtest_framework.py`, `rsm_bootstrap.py`, `quick_predict.py`) is already correctly canonical via the helper. No DB write was performed in this task.

## Current DB View Status

| Metric | Value | Expected |
|--------|-------|----------|
| View `draws_big_lotto_canonical_main` exists | True | True |
| View row count | 2113 | 2113 |
| Raw BIG_LOTTO rows | 22238 | 22238 |
| ADD_ON_PRIZE_EXCLUDED raw rows | 19100 | 19100 |
| DB integrity | ok | ok |
| Annotation table exists | False | False |

## Consumer Scan Table

| Path | Classification | Action |
|------|---------------|--------|
| `analysis/p247c_big_lotto_view_post_apply_reconciliation.py` | ALREADY_VIEW_BACKED | NONE_NEEDED |
| `tests/test_p247b_apply_big_lotto_canonical_view.py` | ALREADY_VIEW_BACKED | NONE_NEEDED |
| `tests/test_p247c_big_lotto_view_post_apply_reconciliation.py` | ALREADY_VIEW_BACKED | NONE_NEEDED |
| `lottery_api/backtest_framework.py` | ALREADY_HELPER_CANONICAL | NONE_NEEDED |
| `tools/rsm_bootstrap.py` | ALREADY_HELPER_CANONICAL | NONE_NEEDED |
| `tools/quick_predict.py` | ALREADY_HELPER_CANONICAL | NONE_NEEDED |
| `analysis/p246k_canonical_big_lotto_nist_reaudit.py` | ALREADY_HELPER_CANONICAL | NONE_NEEDED |
| `lottery_api/engine/rolling_strategy_monitor.py` | SHOULD_KEEP_HELPER | NONE_NEEDED |
| `lottery_api/routes/prediction.py` | RAW_HISTORY_ALLOWED | DO_NOT_CHANGE |
| `lottery_api/routes/history.py` | RAW_HISTORY_ALLOWED | DO_NOT_CHANGE |
| `lottery_api/common.py` | RAW_HISTORY_ALLOWED | DO_NOT_CHANGE |
| `lottery_api/database.py [get_canonical_draws]` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_TYPE_D_OR_EQUIVALENT |
| `tools/analyze_banker_accuracy.py` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `tools/analyze_banker_plus_kill.py` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `tools/analyze_biglotto_special.py` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `tools/analyze_market_temperature.py` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `tools/analyze_top_n_for_2.py` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `tools/audit_big_lotto_*.py [group]` | FUTURE_SCOPE_REQUIRES_AUTHORIZATION | FUTURE_SCOPE |
| `lottery_api/backtest_*.py [POWER_LOTTO/DAILY_539 group]` | NOT_AFFECTED | NONE_NEEDED |
| `lottery_api/predict_*.py [archived BIG_LOTTO scripts]` | NOT_AFFECTED | NONE_NEEDED |
| `tools/post_draw_pipeline.py` | NOT_AFFECTED | NONE_NEEDED |

## Recommended Adoption Plan

### Phase 1 — Immediate (P247D, no code changes)

P247D audit complete. All production research paths are already canonical.
No further action required in this task.

### Phase 2 — FUTURE SCOPE: Update database.py (needs authorization)

Update `lottery_api/database.py get_canonical_draws()` to query `draws_big_lotto_canonical_main` VIEW internally:

```sql
-- Replaces: SQL filter + Python SMALL_POOL_ALIEN filter
SELECT * FROM draws_big_lotto_canonical_main
ORDER BY CAST(draw AS INTEGER) DESC [LIMIT N]
```

**Benefit:** Single source of truth, eliminates Python-level filter.  
**Risk:** LOW — same 2,113 output rows, no behavioral change for callers.  
**Requires:** database.py change authorization (outside P247D whitelist).

### Phase 3 — FUTURE SCOPE: Update BIG_LOTTO analysis tools

Six active BIG_LOTTO analysis tools use `get_all_draws()` and could adopt `get_canonical_draws()` for correct canonical research population:

- `tools/analyze_banker_accuracy.py`
- `tools/analyze_banker_plus_kill.py`
- `tools/analyze_biglotto_special.py`
- `tools/analyze_market_temperature.py`
- `tools/analyze_top_n_for_2.py`
- `tools/audit_big_lotto_*.py [group]`

## What Should Continue Using Helper

These paths correctly use `get_canonical_draws()` and need no change:

- `lottery_api/backtest_framework.py` — BacktestEngine.backtest() uses db.get_canonical_draws(lottery_type). This is the
- `tools/rsm_bootstrap.py` — RSM strategy monitor bootstrap uses db.get_canonical_draws(). Correctly excludes
- `tools/quick_predict.py` — Unified prediction entry point uses db.get_canonical_draws(). Production predict
- `analysis/p246k_canonical_big_lotto_nist_reaudit.py` — P246K NIST re-audit uses db.get_canonical_draws('BIG_LOTTO'). Research path is c
- `lottery_api/engine/rolling_strategy_monitor.py` — RSM engine (P246F/G migrated). Already uses get_canonical_draws(). No view adopt

## What Should Adopt DB View

The view is currently used directly only by P247B/C test and analysis files. Phase 2 would make `get_canonical_draws()` itself adopt the view internally, so all existing helper callers automatically gain the benefit without code change.

## What Should Remain Raw

These paths must remain raw — they serve full draw history including add-on records:

- `lottery_api/routes/prediction.py` — API prediction routes use get_all_draws() to build draw history for strategy con
- `lottery_api/routes/history.py` — History display API endpoint. Must expose all BIG_LOTTO rows including ADD_ON_PR
- `lottery_api/common.py` — Common history loader used by display/API paths. Intentionally raw — serves all 

## What Is Deferred

- **Annotation table** (`draw_row_family_annotations`): remains deferred,   requires separate Type D authorization.
- **Phase 2** (database.py update): requires authorization outside P247D scope.
- **Phase 3** (analysis tools): requires dedicated scope per tool, with test updates.

## Compliance Statements

- **No DB write performed in P247D.** This task is read-only audit only.
- **No rows deleted, updated, or inserted** in any draws table.
- **ADD_ON_PRIZE_EXCLUDED records remain valid and raw-accessible.**   19100 hyphenated BIG_LOTTO records exist in the raw draws table.
- **No annotation table** was created.
- **No strategy/replay refactor** was performed.
- **No registry or production recommendation** was modified.

---
*Generated by P247D — read-only consumer adoption audit*