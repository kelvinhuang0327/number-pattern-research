# P259B — History Replay Detail Page (Paginated Per-Draw Query)

**Date:** 2026-06-09
**Branch:** `p259b-history-replay-detail-paginated` (base `4910351`)
**Classification:** `P259B_HISTORY_REPLAY_DETAIL_PAGINATED_PR_OPEN_WAITING_CI`

## Summary

Implemented a read-only, server-side-paginated per-draw replay detail view reached from the P259A overview's 查看明細 button. Shows each draw's predicted-vs-actual comparison for one `(lottery_type, strategy_id)`, with hit/miss filter, sort, and exact target_draw search.

## Files Modified

| File | Change |
|------|--------|
| `lottery_api/routes/replay.py` | Added `GET /api/replay/history-detail` + `_parse_numbers_field()` + `_detail_result_label()` helpers; updated module docstring |
| `index.html` | Enabled 查看明細 button (data attrs); added inline `#p259b-detail-panel` (summary card, controls, table, pagination); added P259B detail JS; updated stale notice |

## Files Created

- `tests/test_p259b_history_replay_detail.py` — 38 tests
- `outputs/research/p259b_history_replay_detail_paginated_20260609.{json,md}`

## API: `GET /api/replay/history-detail`

**Params:** `lottery_type` (req), `strategy_id` (req), `bet_index` (1-5, default 1), `page` (≥1, default 1), `page_size` (1-200, default 100), `sort` (`target_draw_desc`|`target_draw_asc`), `hit_filter` (`all`|`hit`|`miss`), `target_draw` (optional exact).

**Returns:** `page`, `page_size`, `total_count`, `has_next`, `rows[]`, `summary{}`, plus safety flags.

## Key Decisions / Schema Realities (reported, not fabricated)

1. **DB path:** correct DB is `lottery_api/data/lottery_v2.db` (94,924 rows) via `_open_conn()`. Root `data/lottery_v2.db` is a separate **empty** DB — not used.
2. **`bet_index` = Option A (user-authorized):** strategy-level declared bet count (P259A `_derive_bet_count`). The replay table has **no per-bet `bet_index` column**; rows scoped by `(lottery_type, strategy_id)`. `derived_bet_count` + `bet_index_matches_strategy` returned for consistency. **No schema change.**
3. **`result_label`** derived from `hit_count`/`special_hit` (no stored column) — factual, advisory-free ("未命中" / "命中 N 碼[＋特別號]").
4. **All rows are `PREDICTED`** → hit/miss derived from `hit_count` (>0 hit, =0 miss).
5. **Sort** uses `CAST(target_draw AS INTEGER)` (TEXT draw column — per DB query规范).

## Frontend

Inline panel within the P259A section (no `src/main.js` navigation dependency). 查看明細 enabled only when the strategy has replay rows. Default load = latest 100 draws. Controls: hit/miss filter, sort, target_draw search, prev/next pagination. Summary card: 彩種 / 策略 / strategy_id / 注數 / replay期數 / 命中期數 / 命中率 / 起訖期數 / 最近回放期數.

## Guarantees

| Property | Status |
|----------|--------|
| Server-side pagination, never loads all rows | ✅ `server_side_pagination`, `no_full_load` |
| No DB write | ✅ `no_db_write=true` |
| No replay backfill/generation | ✅ `no_replay_backfill=true` |
| No strategy adapter changes | ✅ `no_strategy_adapter_changes=true` |
| No migration / schema change | ✅ |
| Overview API still has no per-draw detail | ✅ regression test |

## Test Results

- **P259B:** 38/38 PASS — `pytest tests/test_p259b_history_replay_detail.py -v`
- **P259A regression:** 46/46 PASS
- **P257/P258 regression:** 986/986 PASS
- **CI default validation:** 126 passed, 1 skipped, **1 pre-existing unrelated FAIL** (`test_replay_freshness_cadence` — BIG_LOTTO DONE run 16.8 days old > 14-day window; wall-clock/data staleness, fails identically with P259B changes stashed; CI skips when replay DB absent; out of P259B scope)
- **CI-relevant (api contract + browser smoke):** 93 passed, 1 skipped

## Out of Scope (intentionally not done)

CSV export, complex charts, replay generation, data backfill, adapter changes, schema change, production DB write, merging detail into overview API.

## Next Steps

- **Recommended state:** PR open → after merge HOLD / WAITING_FOR_USER_AUTHORIZATION.
- **P259C** (if later authorized): detail enhancements (export/charts) or cross-strategy comparison — separate authorization required.
