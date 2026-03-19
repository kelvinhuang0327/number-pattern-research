# 回測報告索引

**最後更新**：2026-03-19

本索引列出所有正式回測報告與研究結案文件，依遊戲分類。

---

## 閱讀說明

- **回測 Edge** = 策略命中率相對於隨機基準的差值，非報酬率
- **三窗口**：150p / 500p / 1500p 皆通過才算有效
- **p < 0.05 + permutation test** = 統計顯著性門檻
- **McNemar gate**：替換現有策略需 p < 0.05
- 所有 ruin_prob = 1.000，所有遊戲長期負 EV

---

## 今彩 539

| 報告 | 位置 | 內容摘要 |
|------|------|---------|
| 多注策略驗證 | `docs/DAILY539_MULTI_BET_BACKTEST_REPORT.md` | 1/2/3/5注策略完整回測 |
| H001-H008 假設測試 | `tools/backtest_539_h001_*.py` 結果 | 全部 REJECT（L79-L82） |
| ACB 超參數掃描 | `tools/acb_param_scan_results.json` | fd/gs/boundary 最優確認 |
| MicroFish 結案 | `mcnemar_microfish_vs_acb_results.json` | McNemar p=0.132，未達標 |
| 信號空間窮盡宣告 | MEMORY.md L82 | 進入維護模式 |

現役策略：`acb_1bet` / `midfreq_acb_2bet` / `acb_markov_midfreq_3bet` / `f4cold_5bet`

---

## 大樂透

| 報告 | 位置 | 內容摘要 |
|------|------|---------|
| 多注策略驗證 | `docs/BIG_LOTTO_MULTI_BET_BACKTEST_REPORT.md` | 2/3/4/5注策略 |
| 信號邊界研究 | `signal_boundary_report.md` | 6項隨機性檢驗全通過（L91） |
| 全策略管線結案 | `BIG_LOTTO_strategy_report.md` | 7信號零達 p<0.05（L90） |
| MicroFish 過擬合 | `microfish_capability_analysis.md` | +3.14%→+0.303%，ratio=10.35x（L89） |
| 跨遊戲信號轉移 | `cross_game_comparison.md` | 539→大樂透轉移全部失敗（L85） |
| 策略進化過擬合 | `evolved_strategy_population.json` | +6.5%→+0.12%（L86） |

現役策略：`regime_2bet` / `ts3_regime_3bet` / `p1_dev_sum5bet`

---

## 威力彩

| 報告 | 位置 | 內容摘要 |
|------|------|---------|
| 多注策略驗證 | `docs/POWER_LOTTO_MULTI_BET_BACKTEST_REPORT.md` | 3/4/5注策略 |
| PP3+FreqOrt 驗證 | `backtest_power_ort5_refine_results.json` | perm p=0.000，McNemar net=+65 |
| Fourier Rhythm 驗證 | `backtest_power_fourier_w100_vs_w500.py` 結果 | 3注 edge=+3.16% |
| 跨遊戲信號轉移 | `cross_game_comparison.md` | MidFreq/Fourier 成功轉移（L83） |
| 進化3注評估 | `validated_evolved_strategies.json` | OOS=+3.42% p=0.005，McNemar 等效不替換（L88） |
| PP3-Z3Gap WATCH | MEMORY.md | 2026-06 重評 |

現役策略：`fourier_rhythm_3bet` / `pp3_freqort_4bet` / `orthogonal_5bet`

---

## 跨遊戲研究

| 報告 | 位置 | 內容摘要 |
|------|------|---------|
| 信號轉移研究 | `cross_game_comparison.md` | MidFreq(p=0.010) / Fourier(p=0.035) 轉移威力彩 ✅ |
| 跨遊戲比較 | `research/cross_game_transfer_study.py` | 大樂透轉移失敗，威力彩部分成功 |

---

## 系統層級研究

| 報告 | 位置 | 內容摘要 |
|------|------|---------|
| 決策層分析 | `docs/decision_payout_report.md` | Stage 1-4 框架，ADVISORY_ONLY（L99-L102） |
| 決策層嚴格驗證 | `docs/decision_payout_validation_report.md` | 無條件邊際結構性稀釋確認（L101） |
| 投資組合優化 | `docs/portfolio_optimization_report.md` | Kelly=0，所有遊戲不可操作 |
| SB3 RL Track B | `docs/sb3_final_recommendation.md` | REJECTED，PPO/DQN 零改善（L96-L98） |
| SB3 驗證報告 | `docs/sb3_validation_report.md` | MC p=0.061/0.207，McNemar net=−1/0 |

---

## 回測規範

詳細回測標準見 [docs/BACKTEST_PROTOCOL.md](BACKTEST_PROTOCOL.md)。

核心要求：
- 零資料洩漏（滾動式，不使用未來資料）
- 三窗口一致性（150/500/1500p）
- p < 0.05 + permutation test（200+ shuffles）
- walk-forward OOS 驗證
- McNemar gate（替換需 p < 0.05）
