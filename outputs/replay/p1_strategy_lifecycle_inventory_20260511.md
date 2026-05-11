# P1 Strategy Lifecycle Inventory — 2026-05-11

**Generated:** 2026-05-11  
**Total candidates:** 91  

## Lifecycle Status Counts

| Status | Count |
|--------|-------|
| ONLINE | 6 |
| OFFLINE | 0 |
| REJECTED | 71 |
| OBSERVATION | 0 |
| RETIRED | 0 |
| UNKNOWN | 14 |

## Lottery Type Counts

| Lottery | Count |
|---------|-------|
| BIG_LOTTO | 27 |
| DAILY_539 | 32 |
| POWER_LOTTO | 16 |
| UNKNOWN | 16 |

## Registry vs DB Gap Analysis

**Registry adapters:** ['biglotto_deviation_2bet', 'biglotto_triple_strike', 'daily539_f4cold', 'daily539_markov_cold', 'power_orthogonal_5bet', 'power_precision_3bet']  
**DB strategy_ids (with rows):** ['biglotto_deviation_2bet', 'biglotto_triple_strike', 'daily539_f4cold', 'daily539_markov_cold', 'power_orthogonal_5bet', 'power_precision_3bet']  

**Registry-only (registered but no DB rows):** `[]`  
**DB-only (DB rows but no registry adapter):** `[]`  

## Strategy Catalog

| strategy_id | lottery_type | lifecycle_status | replay_rows | display_eligible | gen_eligible | blocked_reason |
|-------------|--------------|-----------------|-------------|-----------------|--------------|----------------|
| biglotto_deviation_2bet | BIG_LOTTO | ONLINE | 70 | True | True |  |
| biglotto_triple_strike | BIG_LOTTO | ONLINE | 70 | True | True |  |
| daily539_f4cold | DAILY_539 | ONLINE | 90 | True | True |  |
| daily539_markov_cold | DAILY_539 | ONLINE | 90 | True | True |  |
| power_orthogonal_5bet | POWER_LOTTO | ONLINE | 70 | True | True |  |
| power_precision_3bet | POWER_LOTTO | ONLINE | 70 | True | True |  |
| acb_hot_fourier_3bet_biglotto | BIG_LOTTO | REJECTED | 0 | True | False | McNemar p=0.545 遠超0.05，無法確認優於現有 Triple Strike (L04: McNemar不 |
| apriori_3bet_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| bet2_fourier_expansion_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| biglotto_6bet_zone_residual | BIG_LOTTO | REJECTED | 0 | True | False |  |
| cluster_pivot_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| cold_complement_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| coldpool15_biglotto | BIG_LOTTO | REJECTED | 0 | True | False | 三窗口全部劣化: 150p=-2.67%, 500p=-1.20%, 1500p=-0.73%。pool=15的C(15 |
| core_satellite_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| fourier30_markov30_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| gap_dynamic_threshold_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| hot_gap_return_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| hot_stop_rebound_biglotto | BIG_LOTTO | REJECTED | 0 | True | False | 1500期 Edge=+0.01% (幾乎精確等於0)，z=+0.02，p=0.4924。信號統計上不顯著，三窗口雖全正 |
| hot_streak_override_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| markov_2bet_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| markov_repeat_exception_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| markov_single_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| multiwindow_fourier_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| neighbor_injection_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| ts3_acb_4bet_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| ts3_markov_freq_5bet_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| zone_cascade_guard_biglotto | BIG_LOTTO | REJECTED | 0 | True | False |  |
| 539_3bet_orthogonal | DAILY_539 | REJECTED | 0 | True | False | 正交化解決 overlap (13.4→15 unique), 但個別信號品質不足以通過 permutation tes |
| acb_extremecol_2bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| acb_lag_echo_2bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| acb_markov_extremecol_3bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| acb_single_539 | DAILY_539 | REJECTED | 0 | True | False | McNemar vs Cold p=0.0527 (MARGINAL), vs StateSpace p=0.194,  |
| bandit_ucb1_2bet_539 | DAILY_539 | REJECTED | 0 | True | False | Edge +1.84% 遠低於人工設計的 MidFreq+ACB (+4.44%)，Bandit 無法有效學習最佳固定策 |
| cold_burst_3bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| condfourier_3bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| conditional_fourier_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| consecutive_pair_detector_539 | DAILY_539 | REJECTED | 0 | True | False | Lift 1.08x 不可操作 — 連號對出現率僅比隨機基準高 3.2pp，無法轉化為選號策略。即使強制加入連號對約束， |
| ewma_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| extreme_col_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| extremecol_1bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| habit_aware_fourier_v8_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| lag_echo_1bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| lag_echo_acb_markov_3bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| lift_pair_single_539 | DAILY_539 | REJECTED | 0 | True | False | 1500期 Edge 為負 (-0.38%)，三窗口不一致 |
| mab_ucb1_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| markov_1bet_539 | DAILY_539 | REJECTED | 0 | True | False | z=1.22 (p≈0.11)，未通過統計顯著性門檻 (p<0.05) |
| midfreq_extremecol_2bet_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| momentum_regime_switching_539 | DAILY_539 | REJECTED | 0 | True | False |  |
| neighbor_acb_2bet_539 | DAILY_539 | REJECTED | 0 | True | False | 1) 單獨作為2注: 弱於現有MidFreq+ACB (2.79% vs 5.13%，McNemar p=0.0743不 |
| p0b_539_3bet_f_cold_fmid | DAILY_539 | REJECTED | 0 | True | False | Permutation Signal Edge = -0.976%（負），三窗口全正來自非重疊分布偏好(+2.13%)而 |
| p0c_539_3bet_f_cold_x2 | DAILY_539 | REJECTED | 0 | True | False | Signal Edge = -0.176%（負），幾何覆蓋效益(+2.13%)偽造三窗口Edge。與P0-B相同根因。 |
| zone_gap_3bet_539 | DAILY_539 | REJECTED | 0 | True | False | 未通過 permutation test — 策略 M2+ 不優於 random 3-bet baseline |
| fourier_w100_pp3_power | POWER_LOTTO | REJECTED | 0 | True | False |  |
| gap_rebound_powerlotto | POWER_LOTTO | REJECTED | 0 | True | False |  |
| p1_conditional_branch_powerlotto | POWER_LOTTO | REJECTED | 0 | True | False |  |
| power_echo_boost | POWER_LOTTO | REJECTED | 0 | True | False |  |
| power_pp3v2_combined | POWER_LOTTO | REJECTED | 0 | True | False |  |
| power_z3gap_watch | POWER_LOTTO | REJECTED | 0 | True | False |  |
| sgp_power_017_research | POWER_LOTTO | REJECTED | 0 | True | False |  |
| sgp_v9_apex_powerlotto | POWER_LOTTO | REJECTED | 0 | True | False | 3注聯集 M3+ 實測 7.0% vs 基準 11.17%，Edge -37.3%。聯集平均覆蓋 2.68 vs 隨機  |
| shlc_midfreq_power | POWER_LOTTO | REJECTED | 0 | True | False |  |
| special_mab_decay_adjustment_power | POWER_LOTTO | REJECTED | 0 | True | False |  |
| structural_zone_guard_pp3_power | POWER_LOTTO | REJECTED | 0 | True | False |  |
| H001 | UNKNOWN | REJECTED | 0 | True | False | 1500p Edge 劣化：Baseline +0.59pp → H001 -0.01pp（差距 -0.60pp） |
| H002 | UNKNOWN | REJECTED | 0 | True | False | 參數掃描 mult=[0.1,0.2,0.3,0.5,0.8,1.0] 全部不顯著。最佳 McNemar net=+13 |
| H003 | UNKNOWN | REJECTED | 0 | True | False | 參數掃描 alpha=[0.2,0.5,1.0,2.0] 全部不顯著。最佳 alpha=1.0: McNemar net |
| H004 | UNKNOWN | REJECTED | 0 | True | False | Ljung-Box p=0.8497（白噪音），Gap Entropy 序列無時間結構，不具可預測性 |
| H005 | UNKNOWN | REJECTED | 0 | True | False | 741 對中 0 對達到 Lift ≥ 1.3x。最高 Lift=1.054（pair 16,21）遠低於門檻。0 對通 |
| H006 | UNKNOWN | REJECTED | 0 | True | False | McNemar net=+12 p=0.450 不顯著。1500p Edge +0.87pp 看似改善，但統計上無意義。 |
| H007 | UNKNOWN | REJECTED | 0 | True | False | McNemar w1000 vs w500: net=-7 p=0.835（w500 略優），1500p: w500=- |
| H008 | UNKNOWN | REJECTED | 0 | True | False | 參數掃描 gap^{1.2,1.5,2.0} 全部 McNemar p>0.19。最佳 gap^1.2 net=+7 p |
| p0_neighbor_injection | UNKNOWN | REJECTED | 0 | True | False |  |
| p2_mab_fusion | UNKNOWN | REJECTED | 0 | True | False |  |
| p3_state_aware | UNKNOWN | REJECTED | 0 | True | False |  |
| short_term_hot_independent_bet | UNKNOWN | REJECTED | 0 | True | False |  |
| streak_boost_neighbor_bet1 | UNKNOWN | REJECTED | 0 | True | False | 與多窗口Fusion組合時出現交互抵消效應，1500期Edge僅+0.65%低於原始+1.05%，perm p=0.10 |
| zone_constraint_cold_bet2 | UNKNOWN | REJECTED | 0 | True | False | 加入Zone Constraint (Z3>=3後限制Z3名額)後命中率反降: D+Zone=71 < D=74，損失1 |
| big_lotto | BIG_LOTTO | UNKNOWN | 0 | False | False |  |
| biglotto_ts3_acb_4bet | BIG_LOTTO | UNKNOWN | 0 | False | False |  |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | UNKNOWN | 0 | False | False |  |
| strategy | BIG_LOTTO | UNKNOWN | 0 | False | False |  |
| acb_1bet | DAILY_539 | UNKNOWN | 0 | False | False |  |
| acb_markov_midfreq | DAILY_539 | UNKNOWN | 0 | False | False |  |
| acb_markov_midfreq_3bet | DAILY_539 | UNKNOWN | 0 | False | False |  |
| daily_539 | DAILY_539 | UNKNOWN | 0 | False | False |  |
| midfreq_acb_2bet | DAILY_539 | UNKNOWN | 0 | False | False |  |
| h6_gate_mk20_ew85 | POWER_LOTTO | UNKNOWN | 0 | False | False |  |
| power_lotto | POWER_LOTTO | UNKNOWN | 0 | False | False |  |
| power_shlc_midfreq | POWER_LOTTO | UNKNOWN | 0 | False | False |  |
| midfreq_fourier_2bet | UNKNOWN | UNKNOWN | 0 | False | False |  |
| p1_deviation_2bet_539 | UNKNOWN | UNKNOWN | 0 | False | False | PARSE_ERROR: Expecting value: line 12 column 25 (char 423) |

## Source Details

- **Source A:** `lottery_api/models/replay_strategy_registry.py` — canonical adapters with lifecycle_status
- **Source B:** `rejected/` — 72 JSON files (71 parsed, 1 parse error: `p1_deviation_2bet_539.json`)
- **Source C:** `strategies/` — game subdirectory .py/.yaml files
- **Source D:** `lottery_api/data/lottery_v2.db` — strategy_prediction_replays distinct strategy_id
- **Source E:** `memory/MEMORY.md` — strategy mentions

## Notes

- `lifecycle_status = UNKNOWN` means the strategy exists in source files but has no explicit lifecycle declaration.
- `replay_display_eligible = True` means the strategy has a defined non-UNKNOWN lifecycle status and can appear in UI dropdowns.
- `generation_eligible = True` means the strategy is ONLINE and eligible for replay generation.
- Parse error in `rejected/p1_deviation_2bet_539.json` (line 12, col 25) — JSON syntax error, strategy excluded from clean count.

## Final Marker

```
P1_STRATEGY_LIFECYCLE_INVENTORY_READY
```
