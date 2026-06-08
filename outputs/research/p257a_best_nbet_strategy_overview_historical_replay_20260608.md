# P257A — Best N-Bet Strategy Overview: Historical Replay Data + UI Contract

**Task:** P257A | **Date:** 2026-06-08 | **Type:** B (read-only artifact + UI contract)
**Classification:** `P257A_BEST_NBET_STRATEGY_OVERVIEW_HISTORICAL_REPLAY_DATA_READY`
**Final Decision:** `BEST_NBET_STRATEGY_OVERVIEW_DATA_READY_FOR_UI_DESIGN`

> ⚠️ **Historical replay only.** This page shows backtest statistics, not future win probability.
> No strategy has a proven deployable predictive edge. This document must not be used as betting advice.

---

## Executive Summary

- Lotteries with replay data: ['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']
- Lotteries without replay data: ['3_STAR', '4_STAR'] → rendered as empty-state on page
- Total replay rows: **94,924** across BIG_LOTTO (24,140), DAILY_539 (34,680), POWER_LOTTO (36,104)
- Portfolio metrics computed for bet_count N = 1..5 per lottery × strategy
- Best strategy selected per lottery × bet_count using pre-defined ranking rules
- Page contract defines tab model, summary cards, table columns, and empty-state handling
- No DB write, no replay generation, no registry mutation, no strategy promotion, no betting advice

---

## Data Source & Baseline

| Field | Value |
|---|---|
| Source table | `strategy_prediction_replays` |
| Total rows | 94,924 |
| BIG_LOTTO raw draws | 22,239 |
| BIG_LOTTO canonical draws | 2,114 |
| DAILY_539 draws | 5,882 |
| POWER_LOTTO draws | 1,917 |
| 3_STAR / 4_STAR replay rows | 0 (NO_REPLAY_ROWS) |

---

## Replay Schema Summary

Key fields used: `lottery_type`, `strategy_id`, `target_draw`, `bet_index`, `hit_count`,
`predicted_numbers`, `actual_numbers`, `replay_status`.

All computations filter on `replay_status = 'PREDICTED'` only.

---

## N-Bet Portfolio Definition

| Term | Definition |
|---|---|
| Best 1 bet | strategy with `bet_index IN (1)` per target_draw |
| Best 2 bets | strategy with `bet_index IN (1,2)` combined per target_draw |
| Best 3 bets | strategy with `bet_index IN (1,2,3)` combined per target_draw |
| Best 4 bets | strategy with `bet_index IN (1,2,3,4)` combined per target_draw |
| Best 5 bets | strategy with `bet_index IN (1,2,3,4,5)` combined per target_draw |

**Important:** portfolios are computed at the target_draw level, not as independent bet slots.
`portfolio_success_count` counts distinct draws where at least one bet achieved hit_count ≥ 1.

---

## Portfolio Metric Definitions

| Metric | Definition |
|---|---|
| portfolio_success_count | distinct draws where ≥1 bet has hit_count ≥ 1 |
| portfolio_success_rate | portfolio_success_count / distinct_draw_count |
| avg_best_hit_count_per_draw | avg of max(hit_count) per draw over included bets |
| avg_total_hit_count_per_draw | avg of sum(hit_count) per draw over included bets |
| max_single_bet_hit_count | highest single bet hit_count in the portfolio |
| max_portfolio_total_hit_count | highest sum(hit_count) across bets in one draw |
| max_hit_draw_issue | draw identifier where the max occurred |

---

## Ranking Rules

- 1. highest portfolio_success_rate
- 2. tie: highest avg_best_hit_count_per_draw
- 3. tie: highest avg_total_hit_count_per_draw
- 4. tie: highest max_single_bet_hit_count
- 5. tie: highest max_portfolio_total_hit_count
- 6. tie: larger distinct_draw_count
- 7. tie: stable lexical strategy_id (ascending)

---

## Best Strategy per Lottery × Bet-Count

### BIG_LOTTO

| 組合 | 最佳策略 | 回測期數 | 組合成功率 | 平均最佳命中 | 平均總命中 | 單注最高 | 組合最高 | 最高命中期別 | 證據標籤 |
|---|---|---|---|---|---|---|---|---|---|
| 最佳 1 注 | biglotto_deviation_2bet | 1550 | 0.5794 | 0.7574 | 0.7574 | 4 | 4 | 109000111 | ONLINE |
| 最佳 2 注 | biglotto_echo_aware_3bet | 1500 | 0.8380 | 1.2073 | 1.5213 | 4 | 5 | 104000058 | NON_EXECUTABLE_STUB |
| 最佳 3 注 | biglotto_echo_aware_3bet | 1500 | 0.9493 | 1.4600 | 2.2433 | 4 | 6 | 104000058 | NON_EXECUTABLE_STUB |
| 最佳 4 注 | biglotto_ts3_markov_4bet_w30 | 1500 | 0.9880 | 1.5853 | 2.9320 | 4 | 6 | 105000020 | NON_EXECUTABLE_STUB |
| 最佳 5 注 | — | — | — | — | — | — | — | — | 此注數組合目前資料不足 |

### DAILY_539

| 組合 | 最佳策略 | 回測期數 | 組合成功率 | 平均最佳命中 | 平均總命中 | 單注最高 | 組合最高 | 最高命中期別 | 證據標籤 |
|---|---|---|---|---|---|---|---|---|---|
| 最佳 1 注 | 539_3bet_orthogonal | 1500 | 0.5420 | 0.6720 | 0.6720 | 3 | 3 | 110000308 | NON_EXECUTABLE_STUB |
| 最佳 2 注 | daily539_f4cold_5bet | 1500 | 0.7920 | 1.0647 | 1.3127 | 3 | 5 | 110000281 | NON_EXECUTABLE_STUB |
| 最佳 3 注 | daily539_f4cold_5bet | 1500 | 0.9200 | 1.3160 | 1.9673 | 3 | 5 | 110000281 | NON_EXECUTABLE_STUB |
| 最佳 4 注 | daily539_f4cold_5bet | 1500 | 0.9760 | 1.4740 | 2.5733 | 3 | 5 | 110000215 | NON_EXECUTABLE_STUB |
| 最佳 5 注 | daily539_f4cold_5bet | 1500 | 0.9953 | 1.6140 | 3.2460 | 4 | 5 | 110000308 | NON_EXECUTABLE_STUB |

### POWER_LOTTO

| 組合 | 最佳策略 | 回測期數 | 組合成功率 | 平均最佳命中 | 平均總命中 | 單注最高 | 組合最高 | 最高命中期別 | 證據標籤 |
|---|---|---|---|---|---|---|---|---|---|
| 最佳 1 注 | midfreq_fourier_mk_3bet | 1500 | 0.7073 | 1.0273 | 1.0273 | 4 | 4 | 105000082 | NON_EXECUTABLE_STUB |
| 最佳 2 注 | power_fourier_rhythm_2bet | 1500 | 0.9287 | 1.4700 | 1.9267 | 4 | 5 | 101000062 | NON_EXECUTABLE_STUB |
| 最佳 3 注 | power_precision_3bet | 1550 | 0.9710 | 1.6394 | 2.8123 | 4 | 7 | 103000048 | ONLINE |
| 最佳 4 注 | pp3_freqort_4bet | 1500 | 0.9807 | 1.6673 | 3.8840 | 4 | 11 | 103000048 | NON_EXECUTABLE_STUB |
| 最佳 5 注 | power_orthogonal_5bet | 1550 | 0.9716 | 1.6477 | 4.6923 | 4 | 13 | 103000048 | ONLINE |

### No-Data Lotteries: ['3_STAR', '4_STAR']
顯示：此彩種目前沒有可用回測資料。

---

## Historical High-Hit Events (per lottery × bet_count)

> 歷史最高命中 — 回測資料中的命中數紀錄。未必等同實際獎級或獎金。

| Lottery | Bet Count | Target Draw | Strategy | Pred. Numbers | Actual Numbers | Best Single Hit | Portfolio Total |
|---|---|---|---|---|---|---|---|
| BIG_LOTTO | 1 | 105000020 | biglotto_ts3_markov_4bet_w30 | [11, 29, 31, 33, 34, 44] | [11, 23, 29, 33, 34, 40] | 4 | 4 |
| BIG_LOTTO | 2 | 99000103 | biglotto_triple_strike | [16, 18, 33, 34, 43, 49] | [16, 27, 39, 43, 48, 49] | 3 | 6 |
| BIG_LOTTO | 3 | 112000067 | biglotto_ts3_markov_4bet_w30 | [5, 10, 21, 23, 32, 34] | [10, 21, 26, 34, 48, 49] | 3 | 6 |
| BIG_LOTTO | 4 | 105000020 | biglotto_ts3_markov_4bet_w30 | [11, 29, 31, 33, 34, 44] | [11, 23, 29, 33, 34, 40] | 4 | 6 |
| BIG_LOTTO | 5 | 105000020 | biglotto_ts3_markov_4bet_w30 | [11, 29, 31, 33, 34, 44] | [11, 23, 29, 33, 34, 40] | 4 | 6 |
| DAILY_539 | 1 | 111000171 | acb_markov_midfreq | [2, 11, 13, 16, 25] | [2, 11, 16, 25, 38] | 4 | 4 |
| DAILY_539 | 2 | 112000040 | daily539_f4cold_5bet | [5, 6, 17, 27, 39] | [5, 17, 25, 35, 39] | 3 | 5 |
| DAILY_539 | 3 | 111000171 | acb_markov_midfreq_3bet | [2, 11, 13, 16, 25] | [2, 11, 16, 25, 38] | 4 | 6 |
| DAILY_539 | 4 | 111000171 | acb_markov_midfreq_3bet | [2, 11, 13, 16, 25] | [2, 11, 16, 25, 38] | 4 | 6 |
| DAILY_539 | 5 | 111000171 | acb_markov_midfreq_3bet | [2, 11, 13, 16, 25] | [2, 11, 16, 25, 38] | 4 | 6 |
| POWER_LOTTO | 1 | 110000008 | power_orthogonal_5bet | [14, 19, 30, 32, 34, 36] | [1, 9, 19, 30, 34, 36] | 4 | 4 |
| POWER_LOTTO | 2 | 110000008 | power_orthogonal_5bet | [14, 19, 30, 32, 34, 36] | [1, 9, 19, 30, 34, 36] | 4 | 8 |
| POWER_LOTTO | 3 | 114000015 | power_orthogonal_5bet | [6, 8, 14, 15, 32, 37] | [5, 6, 15, 19, 32, 37] | 4 | 10 |
| POWER_LOTTO | 4 | 114000015 | power_orthogonal_5bet | [6, 8, 14, 15, 32, 37] | [5, 6, 15, 19, 32, 37] | 4 | 11 |
| POWER_LOTTO | 5 | 104000086 | power_orthogonal_5bet | [7, 14, 19, 20, 31, 35] | [2, 9, 19, 20, 31, 32] | 3 | 13 |

---

## Best N-Bet Strategy Overview Page Contract

**Page Name:** Best Strategy Overview / 最佳策略總覽
**Route:** /strategy/best-overview (implement in P257B; adapt to actual frontend convention)

### Lottery Tabs
['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO', '3_STAR', '4_STAR']
Empty-state tab: *顯示：此彩種目前沒有可用回測資料。*

### Summary Cards
| Key | 中文標籤 |
|---|---|
| best_strategy | 歷史最佳策略 |
| best_success_rate | 最高組合成功率 |
| avg_best_hit | 平均單期最佳命中 |
| avg_total_hit | 平均單期總命中 |
| max_hit | 歷史最高命中 |
| replay_draws | 回測期數 |

### Best N-Bet Portfolio Table Columns
| Key | 中文標籤 | Note |
|---|---|---|
| bet_count_label | 組合 | 最佳 1 注 / 最佳 2 注 / ... / 最佳 5 注 |
| strategy_id | 最佳策略 |  |
| distinct_draw_count | 回測期數 |  |
| replay_row_count | 回測筆數 |  |
| portfolio_success_rate | 組合成功率 | 至少 1 注命中的期數比例 |
| avg_best_hit_count_per_draw | 平均單期最佳命中 |  |
| avg_total_hit_count_per_draw | 平均單期總命中 |  |
| max_single_bet_hit_count | 單注最高命中 |  |
| max_portfolio_total_hit_count | 組合最高總命中 |  |
| max_hit_draw_issue | 最高命中期別 |  |
| evidence_label | 證據標籤 |  |

### Historical High-Hit Event Table Columns
| Key | 中文標籤 |
|---|---|
| target_draw | 期別 |
| bet_count | 組合 |
| best_single_bet_index | 注序 |
| strategy_id | 策略 |
| predicted_numbers | 預測號碼 |
| actual_numbers | 開獎號碼 |
| best_single_hit_count | 單注命中數 |
| portfolio_total_hit_count | 組合總命中數 |
| prize_tier_note | 備註 |

### Empty States
- **no_replay_lottery:** 此彩種目前沒有可用回測資料。
- **no_data_for_bet_count:** 此注數組合目前資料不足。
- **missing_predicted_numbers:** 號碼明細 unavailable，不影響統計排名。
- **no_prize_tier:** 未提供獎級資料，因此僅顯示命中數，不標示大獎或獎金。

### Fixed Warning Copy (繁體中文)
- 本頁為歷史回測統計，不代表未來中獎機率。
- 最佳策略依歷史資料排序，可能存在過度擬合。
- 目前沒有任何策略被證明具有可部署預測優勢。
- 本頁不提供投注建議。
- 歷史最高命中僅代表回測資料中的命中數紀錄，未必等同實際獎級或獎金。

### Fixed Warning Copy (English)
- This page shows historical replay statistics only; it does not represent future win probability.
- Best strategies are ranked by historical data and may reflect overfitting.
- No strategy has been proven to have a deployable predictive edge.
- This page does not provide betting advice.
- Historical high-hit events refer only to hit counts in replay data and do not imply any prize tier or payout.

---

## Explicit Non-Actions

- **No DB write** — read-only `mode=ro` sqlite3
- **No replay generation** — only existing `strategy_prediction_replays` rows used
- **No registry mutation** — `replay_strategy_registry.py` not touched
- **No strategy promotion** — historical ranking ≠ deployment authorization
- **No recommendation-logic change** — recommendation endpoints not modified
- **No betting advice** — this document must not be used for gambling decisions
- **No frontend/API implementation** — route and UI implementation deferred to P257B

---

## Required Completion Check

| Item | Result |
|---|---|
| Completed | YES |
| Test Result | PASS (see pytest output) |
| Single Blocking Issue | NONE |
| DB write | NO |
| Registry mutation | NO |
| Strategy promotion | NO |
| Betting advice | NO |
| Final Classification | `P257A_BEST_NBET_STRATEGY_OVERVIEW_HISTORICAL_REPLAY_DATA_READY` |
| Strong Model Needed | NO |
