# P247F — BIG_LOTTO Analysis Tool Migration to Canonical Helper

**Date:** 2026-06-06 12:18:16  
**Task:** P247F  
**Classification:** ANALYSIS_TOOL_CANONICAL_MIGRATION  

## Executive Summary

P247F migrates 9 confirmed active BIG_LOTTO research/analysis tools from `get_all_draws('BIG_LOTTO')` (raw 22,238 rows) to `get_canonical_draws('BIG_LOTTO')` (canonical 2,113 main-draw rows via DB view). Raw display/history paths are unchanged. No DB write was performed.

## Why Phase 3 Tool Migration Is Needed

- P247D identified these tools as FUTURE_SCOPE_REQUIRES_AUTHORIZATION.
- P247E made `get_canonical_draws()` view-backed (single source of truth).
- Research/analysis tools should analyze the canonical 6/49 main-draw population, not the raw 22,238 rows that include ADD_ON_PRIZE_EXCLUDED, DATE_FORMAT_ALIEN, and SMALL_POOL_ALIEN records.
- A one-line change per tool is sufficient — all tools already use the canonical DB path.

## Current View/Helper Status

- View `draws_big_lotto_canonical_main`: **2113 rows** ✅
- `get_canonical_draws('BIG_LOTTO')`: **2113 rows** ✅
- Raw BIG_LOTTO: **22238 rows** (preserved) ✅
- DB integrity: **ok** ✅

## Tools Scanned and Classification Table

| Tool | Classification | Change |
|------|---------------|--------|
| `tools/analyze_banker_accuracy.py` | UPDATED_TO_CANONICAL | get_all_draws(lottery_type='BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/analyze_banker_plus_kill.py` | UPDATED_TO_CANONICAL | get_all_draws(lottery_type='BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/analyze_biglotto_special.py` | UPDATED_TO_CANONICAL | get_all_draws(lottery_type='BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/analyze_market_temperature.py` | UPDATED_TO_CANONICAL | get_all_draws(lottery_type='BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/analyze_top_n_for_2.py` | UPDATED_TO_CANONICAL | get_all_draws(lottery_type='BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/audit_big_lotto_3bet.py` | UPDATED_TO_CANONICAL | get_all_draws('BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/audit_big_lotto_baseline.py` | UPDATED_TO_CANONICAL | get_all_draws('BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/audit_big_lotto_hyper.py` | UPDATED_TO_CANONICAL | get_all_draws('BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `tools/audit_big_lotto_rigorous.py` | UPDATED_TO_CANONICAL | get_all_draws('BIG_LOTTO') → get_canonical_draws('BIG_LOTTO') |
| `lottery_api/routes/prediction.py` | RAW_HISTORY_ALLOWED | — |
| `lottery_api/routes/history.py` | RAW_HISTORY_ALLOWED | — |
| `lottery_api/common.py` | RAW_HISTORY_ALLOWED | — |
| `lottery_api/backtest_*.py [archived BIG_LOTTO scripts]` | DEFERRED_ARCHIVED_OR_EXPLORATORY | — |
| `lottery_api/predict_*.py [archived BIG_LOTTO scripts]` | DEFERRED_ARCHIVED_OR_EXPLORATORY | — |

## Tools Updated

All 9 tools updated with a single-line change. Example diff per tool:

```diff
- all_draws = db.get_all_draws('BIG_LOTTO')
+ all_draws = db.get_canonical_draws('BIG_LOTTO')  # P247F: canonical 2,113 main-draw rows
```

| Tool | Scan Result |
|------|-------------|
| `tools/analyze_banker_accuracy.py` | OK |
| `tools/analyze_banker_plus_kill.py` | OK |
| `tools/analyze_biglotto_special.py` | OK |
| `tools/analyze_market_temperature.py` | OK |
| `tools/analyze_top_n_for_2.py` | OK |
| `tools/audit_big_lotto_3bet.py` | OK |
| `tools/audit_big_lotto_baseline.py` | OK |
| `tools/audit_big_lotto_hyper.py` | OK |
| `tools/audit_big_lotto_rigorous.py` | OK |

## Tools Deferred and Why

- **`lottery_api/routes/prediction.py`** (RAW_HISTORY_ALLOWED): API display/prediction routes must serve all BIG_LOTTO rows including add-on records.
- **`lottery_api/routes/history.py`** (RAW_HISTORY_ALLOWED): History display endpoint must expose all row families for complete historical record.
- **`lottery_api/common.py`** (RAW_HISTORY_ALLOWED): Common history loader for display paths; intentionally raw.
- **`lottery_api/backtest_*.py [archived BIG_LOTTO scripts]`** (DEFERRED_ARCHIVED_OR_EXPLORATORY): One-off historical backtest scripts (backtest_115000012_*.py, backtest_big_lotto_2025_ensemble.py, backtest_oddeven_research_biglotto.py, etc.). Not in active prediction pipeline. Migration deferred — requires dedicated scope per script.
- **`lottery_api/predict_*.py [archived BIG_LOTTO scripts]`** (DEFERRED_ARCHIVED_OR_EXPLORATORY): Archived one-off predict scripts (predict_biglotto_8_bets.py, predict_biglotto_monte_carlo_8.py, etc.). Not in active pipeline. Deferred.

## Raw Access Preservation

- `get_all_draws('BIG_LOTTO')` and `get_draws()` are **not modified**.
- Raw BIG_LOTTO rows: **22238** (unchanged) ✅
- ADD_ON_PRIZE_EXCLUDED rows: **19100** (raw-accessible) ✅
- API history/display routes remain on raw path.

## Compliance Statements

- **No DB write performed in P247F.**
- **No rows deleted, updated, or inserted** in any draws table.
- **ADD_ON_PRIZE_EXCLUDED records remain valid and raw-accessible.**   19100 hyphenated BIG_LOTTO records exist in the raw draws table.
- **No annotation table** was created.
- **No strategy/replay refactor** beyond replacing the input draw-loading call in research/analysis tools.
- **No registry or production recommendation** was modified.

---
*Generated by P247F — BIG_LOTTO analysis tool canonical migration*