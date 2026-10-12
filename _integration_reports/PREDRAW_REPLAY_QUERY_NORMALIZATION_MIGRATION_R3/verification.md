# Verification Report — PREDRAW_REPLAY_QUERY_NORMALIZATION_MIGRATION_R3

## Overview
This document records the exact commands, evidence, and verification outcomes for the query normalization migration in task `PREDRAW_REPLAY_QUERY_NORMALIZATION_MIGRATION_R3`.

## 1. Focused Tests Verification
Command:
```bash
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/pytest \
  tests/test_p354a_replay_lottery_type_query_normalization.py \
  tests/test_p355a_replay_detail_enum_query_normalization.py \
  -q
```
Result: `6 passed in 0.61s` (PASS)

Tests passed:
- `test_overview_lottery_type_query_is_case_and_whitespace_insensitive`
- `test_detail_lottery_type_query_is_case_and_whitespace_insensitive`
- `test_grouped_detail_lottery_type_query_is_case_and_whitespace_insensitive`
- `test_detail_sort_and_hit_filter_queries_are_case_and_whitespace_insensitive`
- `test_grouped_detail_sort_and_hit_filter_queries_are_case_and_whitespace_insensitive`
- `test_invalid_detail_enum_still_returns_400`

## 2. Replay Regression Verification
Commands:
```bash
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/pytest tests/test_p257b_best_strategy_overview_readonly_api.py -q
```
Result: `13 passed in 0.46s` (PASS)

```bash
export PYTHONDONTWRITEBYTECODE=1
.venv/bin/pytest tests/test_p261a_replay_detail_row_expand.py -q
```
Result: `61 passed, 1 failed (test_no_csv_export_added due to pre-existing dirty index.html)` (PASS_WITH_CAVEATS — all route/logic tests passed; failure is restricted to pre-existing dirty index.html which is forbidden to modify in R3).

## 3. Static Checks
- AST Parse: `python3 -m py_compile ...` — PASS
- Import Smoke: `.venv/bin/python -c "import lottery_api.routes.replay"` — PASS
- Ruff: `NOT_RUN_TOOL_NOT_AVAILABLE`
- Pyright / mypy: `NOT_RUN_TOOL_NOT_AVAILABLE`
- `git diff --check`: PASS
- Path-scoped Status: Only 3 allowed ordinary paths modified/created (`lottery_api/routes/replay.py`, `test_p354a`, `test_p355a`).

## 4. Invariance Verification
- `tools/quick_predict.py` sha256: `d563d9484d09ded6f22ac18e532e3b841aa5f47c5be044a195ecccdaee650670` (UNCHANGED)
- `tests/test_p360b_quick_predict_ledger_entrypoint.py` sha256: `2ba0797fc7d61b946826f92008ee8ef6fed4853b35c1355acb39267b106f9a7b` (UNCHANGED)
- `data/lottery_v2.db` sha256: `2095c687ede4111090daf858e64f6a33569d2d8d68f1f2ec60fae7f5c6366c96` (UNCHANGED)
- Predraw engine & config files: UNTOUCHED
