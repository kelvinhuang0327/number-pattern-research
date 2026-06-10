# P265A — D3 Success Metric Recontract: M3+ Real Replay Success Rate

_Read-only metric semantics change to `/api/replay/d3-strategy-status-coverage`. No DB/registry/adapter/migration change. Legacy `/api/replay/d3-strategy-status-audit` contract untouched._

## Problem

P263B's D3 SSOT success-rate columns (30/100/500/1500) used an **any-hit** rule:

```
draw_success = MAX(hit_count >= 1 OR special_hit = 1)
```

For BIG_LOTTO this is essentially the random baseline (~55% of draws hit ≥1 of 6 numbers from a 49-pool), and multi-bet cells looked even higher (90%+) because any of 3–5 bets hitting one number counted. Users read "94% 成功率" as a strategy quality signal — misleading.

## Change

The success criterion becomes **M3+** (real replay M3+ success):

```
draw_success = MAX(hit_count >= 3)        -- at least 3 main-number hits, any bet
```

- **special_hit excluded:** a special-only draw (`special_hit = 1`, `hit_count < 3`) is now a **non-success**. Only `hit_count >= 3` counts.
- **Multi-bet draw-level any-bet:** the existing `GROUP BY lottery_type, strategy_id, target_draw` already collapses all bet_indices for a draw into one entry, so a draw is a success if **any** bet_index reached `hit_count >= 3`. Denominator stays **distinct target_draw**, never replay row count.
- **Field names preserved:** `success_rate_{30,100,500,1500}` and `available_draws_{…}` keep their names (no consumer break). New contract fields declare the M3+ semantics.

### New `success_rate_contract` fields

| field | value |
|---|---|
| `success_metric` | `"M3_PLUS"` |
| `metric_label` | `"M3+ 成功率"` |
| `draw_success_rule` | `"any bet_index for the draw has hit_count >= 3 (>= 3 main-number hits)"` |
| `special_hit_excluded` | `true` |
| `denominator` | `"distinct target_draw in the window (not replay row count)"` |
| `metric_history` | `"P263B used any-hit …; P265A recontracted to M3+ (hit_count>=3)"` |

## Before / after (API sanity check)

| cell | bets | old any-hit (≈sr100) | new M3+ sr100 | new M3+ sr1500 |
|---|---|---|---|---|
| `BIG_LOTTO/markov_single_biglotto` | 1 | ~54% | **0.0%** | 1.53% |
| `BIG_LOTTO/biglotto_echo_aware_3bet` | 3 | ~94% | **5.0%** | 6.47% |
| `BIG_LOTTO/biglotto_ts3_markov_4bet_w30` | 4 | ~99% | 8.0% | 8.67% |
| `DAILY_539/daily539_f4cold_5bet` | 5 (7500 rows) | — | 5.0% | 6.33% (avail=**1500** distinct draws, not 7500 rows) |

## UI

- P263B section column headers: `30期 → 30期 M3+`, etc. (substring `30期` preserved so P263B/P264A/P264B column tests stay green), each with a tooltip explaining M3+.
- Section description and disclaimer banner now state: **M3+ 成功率 = replay 中每期任一注命中主號 3 顆以上 (hit_count ≥ 3) 的比例；special_hit 不單獨計入 M3+；不代表 D3 核准或投注建議**.

## Preserved

- Legacy `/api/replay/d3-strategy-status-audit` — artifact-backed, `no_db_query=true`, 14 rows, fixed schema. **Untouched.**
- D3 SSOT endpoint `/api/replay/d3-strategy-status-coverage` — preserved (metric semantics only).
- `d3_contract_status = NOT_EVALUATED_BY_D3` for every row — M3+ is read-only evidence, not approval.
- P258N/O/P locked contract — intact.

## Test results

| Suite | Result |
|---|---|
| `test_p265a_d3_m3_real_replay_success_rate.py` | **23/23 PASS** |
| `test_p263b_d3_strategy_status_ssot_rebuild.py` | PASS |
| `test_p264a_hide_legacy_d3_artifact_default_ui.py` | PASS |
| `test_p264b_hide_empty_legacy_d3_tab_default_navigation.py` | PASS |
| `test_replay_api_contract.py` | PASS |
| **Five-suite total** | **152 passed** |
| P258M/N/O/P locked contract | 238 passed |
| `git diff --check` | CLEAN |
| API sanity check | PASS |
| Browser check | NOT RUN (live SSOT backend not guaranteed; static wording verified via HTML) |
