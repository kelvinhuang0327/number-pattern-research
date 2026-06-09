# P259A — History Replay Overview Single-Bet First

**Date:** 2026-06-09  
**Classification:** `P259A_HISTORY_REPLAY_OVERVIEW_SINGLE_BET_FIRST_READY`

## Summary

Refactored the History Replay Overview into a replay-query-first page for all lottery types, strategies, and bet counts, with `bet_index=1` as the default priority view.

## Files Modified

| File | Change |
|------|--------|
| `lottery_api/routes/replay.py` | Added `GET /api/replay/history-overview` endpoint + `_derive_bet_count()` helper |
| `index.html` | Added nav button, `#p259a-replay-overview-section`, CSS, JS |

## Files Created

- `tests/test_p259a_history_replay_overview.py` — 46 tests
- `outputs/research/p259a_history_replay_overview_single_bet_first_20260609.json`
- `outputs/research/p259a_history_replay_overview_single_bet_first_20260609.md`

## API: `GET /api/replay/history-overview`

**Query params:**
- `lottery_type` — filter by lottery type (omit = all)
- `bet_index` — 1–5 (default `1`); `0` = all bet counts
- `replay_status_category` — `has_rows` | `no_production_replay` | `artifact_only`

**Data sources:**
- `list_strategy_lifecycle_metadata()` — registry, all lifecycle states
- `strategy_prediction_replays` DB — read-only aggregate (COUNT, MIN/MAX draw)

**Bet count derivation:** `_derive_bet_count(strategy_id)` extracts `_Nbet` suffix; special-cases `biglotto_triple_strike` → 3; default 1.

## UI Features

- **Bet count tabs:** 1注 / 2注 / 3注 / 4注 / 5注 / 全部注數 — default 1注 active
- **Lottery type filter:** 全部 / 今彩539 / 大樂透 / 威力彩
- **Replay status filter:** 全部 / 有replay rows / 無production replay / 僅artifact
- **Lifecycle filter:** badge/filter only — never excludes strategies
- **Main table:** 彩種 / 策略名稱 / strategy_id / 注數 / replay期數 / 起訖target_draw / 最近target_draw / 回放狀態 / 生命週期 / 查看明細
- **查看明細:** disabled button — "明細頁將於後續 P259B 實作，包含每一期預測比對與分頁查詢。"

## Guarantees

| Property | Status |
|----------|--------|
| No DB write | ✅ `no_db_write=true` |
| No replay backfill | ✅ `no_replay_backfill=true` |
| No strategy adapter changes | ✅ `no_strategy_adapter_changes=true` |
| No per-draw detail in overview | ✅ `no_large_per_draw_detail=true` |
| No migration | ✅ No schema changes |
| All lifecycle states discoverable | ✅ `all_strategies_included=true` |
| Lifecycle as badge only | ✅ `lifecycle_as_badge_only=true` |
| P259B detail page deferred | ✅ UI notice + disabled button |

## Test Results

- **P259A:** 46/46 PASS
- **P258/P257 regression:** 986/986 PASS

## Next Steps

- **P259B:** History Replay Detail Page — paginated per-draw query (explicit authorization required)
- **Recommended state:** HOLD / WAITING_FOR_USER_AUTHORIZATION
