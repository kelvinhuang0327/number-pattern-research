# Rejected Strategies Archive

每個被暫停研究的策略以 `{strategy_name}.json` 格式歸檔。
**舊策略不得刪除，只能歸檔。**
**此目錄存放「暫停中」的研究歸檔（附重啟條件），而非墓地。(L55)**

## 暫停研究策略索引

### 威力彩 (POWER_LOTTO)

| 策略 | 日期 | 原因 | 1500p Edge | 失敗模式 |
|------|------|------|-----------|---------|
| gap_rebound_powerlotto | 2026-02-09 | Gap Pressure 在頻率窗口下無增益 | 無顯著改善 | INEFFECTIVE |
| p1_conditional_branch_powerlotto | 2026-02-09 | Bonferroni 校正後 0/16 通過 | — | STATISTICAL_ILLUSION |
| sgp_v9_apex_powerlotto | 2026-02-24 | SGP V3→V11 全敗，Gap 信號暫停研究 | 全負 | INEFFECTIVE |
| sgp_power_017_research | 2026-02-27 | MAB 注選擇器 M3+稀疏無法收斂 | -1.13% | INEFFECTIVE |
| shlc_midfreq_power | 2026-03-03 | SHLC p=0.595 無信號，PP3替換後-0.33% | +1.90% (劣化) | STATISTICAL_ILLUSION |
| special_mab_decay_adjustment_power | 2026-03-03 | V3_orig 仍最高，所有調整劣化 Top-1 | — | INEFFECTIVE |
| structural_zone_guard_pp3_power | 2026-03-03 | Z1觸發率0.11%，效果完全等同PP3_orig | +2.23% (無變化) | INEFFECTIVE |

### 大樂透 (BIG_LOTTO)

| 策略 | 日期 | 原因 | 1500p Edge | 失敗模式 |
|------|------|------|-----------|---------|
| core_satellite_biglotto | 2026-02-06 | 覆蓋損失 > 相關收益；Edge為負 | -0.89% | INEFFECTIVE |
| apriori_3bet_biglotto | 2026-01-30 | 全期Edge嚴重負向，短期亦無優勢 | — | INEFFECTIVE |
| markov_2bet_biglotto | 2026-01-30 | SHORT_MOMENTUM，150期正向但1000期負向 | — | SHORT_MOMENTUM |
| cluster_pivot_biglotto | 2026-02-10 | 150/500期良好但1500期Edge負，幸運窗口效應 | -0.45% | SHORT_MOMENTUM |
| cold_complement_biglotto | 2026-02-10 | 1500期Edge接近零，無統計意義 | -0.02% | INEFFECTIVE |
| fourier30_markov30_biglotto | 2026-02-10 | 1500期Edge為負，長期無法維持 | -0.29% | SHORT_MOMENTUM |
| markov_single_biglotto | 2026-02-10 | 1500期Edge為負，SHORT_MOMENTUM | -0.46% | SHORT_MOMENTUM |
| neighbor_injection_biglotto | 2026-02-10 | 鄰號Lift<1.0負相關；注入嚴重損害預測品質 | — | STATISTICAL_ILLUSION |
| gap_dynamic_threshold_biglotto | 2026-02-23 | 16組grid全無改善，gap信號已被頻率窗口吸收 | ≤-0.20%(Δ) | INEFFECTIVE |
| markov_repeat_exception_biglotto | 2026-02-23 | 信號真實但改善幅度<統計噪音(McNemar p=0.779) | +1.43%(Δ+0.13%) | INEFFECTIVE |
| bet2_fourier_expansion_biglotto | 2026-02-25 | Fourier擴展替換冷號bet2致信號同質化，整體退步 | +0.91%(退步) | INEFFECTIVE |
| multiwindow_fourier_biglotto | 2026-02-25 | 多窗口稀釋真實信號，劣化現行策略 | -0.16%(退步) | INEFFECTIVE |
| ts3_acb_4bet_biglotto | 2026-02-28 | 三窗口未全正(150p=-5.29%)，perm p=0.072 MARGINAL | +1.10% | MARGINAL |
| acb_hot_fourier_3bet_biglotto | 2026-02-27 | McNemar p=0.545，ACB不顯著優於TS3 | — | MARGINAL |
| ts3_markov_freq_5bet_biglotto | 2026-02-26 | 架構孤島，與新4注P1+偏差互補不一致 | +2.71% | SUPERSEDED |
| streak_boost_neighbor_bet1 | 2026-02-26 | Streak Boost組合後交互抵消 | +0.65% | INEFFECTIVE |
| zone_constraint_cold_bet2 | 2026-02-26 | Zone Constraint在冷號框架反效果 | 劣化 | INEFFECTIVE |
| short_term_hot_independent_bet | 2026-02-27 | 5期熱號獨立注 Edge=0% (p=0.522) | 0.00% | STATISTICAL_ILLUSION |
| hot_gap_return_biglotto | 2026-03-03 | Hot+HighGap命中率稍低於基準(-0.55%)，NO SIGNAL | -0.55% | INEFFECTIVE |
| hot_stop_rebound_biglotto | 2026-03-03 | 熱號休停回歸 Edge=+0.01% p=0.4924，無信號 | +0.01% | INEFFECTIVE |
| coldpool15_biglotto | 2026-03-03 | pool=15三窗口全劣化，Sum約束在小池更精準 | +1.91%(劣化) | INEFFECTIVE |
| p1_deviation_2bet_539 (移植) | 2026-02-26 | 大樂透信號不跨彩種通用 | -0.05% | INEFFECTIVE |

### 今彩 539 (DAILY_539)

| 策略 | 日期 | 原因 | 1500p Edge | 失敗模式 |
|------|------|------|-----------|---------|
| markov_1bet_539 | 2026-03-01 | z=1.22 p≈0.11 不顯著 | — | MARGINAL |
| consecutive_pair_detector_539 | 2026-02-28 | Lift=1.08x 不可操作 | — | STATISTICAL_ILLUSION |
| 539_3bet_orthogonal | 2026-02-26 | 正交化後個別信號不足，perm p=0.2388 | +4.22%(150p) | INEFFECTIVE |
| zone_gap_3bet_539 | — | Zone+Gap 三窗口不穩定 | — | SHORT_MOMENTUM |
| p0_neighbor_injection | — | 鄰號共現 Lift<1.0 負相關 | — | STATISTICAL_ILLUSION |
| neighbor_acb_2bet_539 | 2026-03-04 | 弱於MidFreq+ACB，4注合體Edge=-0.83%，邊際效率64.7% | +2.79% | INEFFECTIVE |
| p0b_539_3bet_f_cold_fmid | — | LATE_BLOOMER 模式 | — | LATE_BLOOMER |
| p0c_539_3bet_f_cold_x2 | — | 劣化，不如 F4Cold | — | INEFFECTIVE |
| bandit_ucb1_2bet_539 | — | MAB 無法收斂 (同 L32) | — | INEFFECTIVE |
| lift_pair_single_539 | — | 個號 Lift<1.3x 不可操作 | — | STATISTICAL_ILLUSION |
| acb_single_539 | — | 嵌入 F4Cold 殘餘池後效率<70% | — | INEFFECTIVE |
| p1_deviation_2bet_539 | 2026-02-26 | P1鄰號是大樂透特有信號，Edge≈0% | -0.05% | INEFFECTIVE |
| p2_mab_fusion | — | MAB稀疏問題，L32同樣失敗 | — | INEFFECTIVE |
| p3_state_aware | — | 觸發率太低 | — | INEFFECTIVE |

---

## Schema

```json
{
  "name": "策略名稱",
  "lottery": "BIG_LOTTO | POWER_LOTTO | DAILY_539",
  "rejected_date": "YYYY-MM-DD",
  "failure_reason": "失敗原因摘要",
  "pattern": "SHORT_MOMENTUM | INEFFECTIVE | STATISTICAL_ILLUSION | LATE_BLOOMER | SUPERSEDED",
  "stats": {
    "edge_150p": null,
    "edge_500p": null,
    "edge_1500p": null,
    "baseline": null,
    "p_value": null,
    "z_score": null
  },
  "applicable_conditions": "此策略在哪些條件下曾短暫有效",
  "retest_conditions": "什麼情況下可重新測試",
  "notes": "補充說明"
}
```
