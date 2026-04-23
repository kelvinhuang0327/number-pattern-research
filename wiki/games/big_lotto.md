# BIG_LOTTO

## Regime Status (2026-04-23) — COLD_PHASE_NORMAL

> **Stable Maintenance**: 2/12 strategies in cold (16.7%), uniform 7-period synchronized streak. Main production strategies positive (`p1_dev_sum5bet` +4.373% edge_30p, `p1_deviation_4bet` +2.75% edge_30p). Portfolio diversification intact. **Classification: NORMAL_MEDIAN** — exactly at 50th percentile. **Expected recovery: 2 weeks** (confidence: high). **Action: MAINTENANCE_MODE** — continue RSM monitoring, no research allocation. Analysis: `analysis/results/cold_phase_regime_analysis_20260423.md`

## 現況

- 維護模式；L90 宣告全信號空間窮盡，L91 確認 49C6 與公平隨機過程統計不可區分。
- Planner/decision tier 仍保留 2注/3注/5注參考策略，供監控與決策層使用。

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| regime_2bet | 2 | +3.57% | 0.138 | analysis/results/stage0_baseline.json |
| ts3_regime_3bet | 3 | +3.42% | 0.120 | analysis/results/stage0_baseline.json |
| p1_dev_sum5bet | 5 | +3.74% | 0.112 | analysis/results/stage0_baseline.json |

## PSI / DriftDetector

- 檢查時間：2026-03-18T10:39:41.183057
- DriftDetector overall_status：STABLE
- number_freq_PSI：0.097311（門檻 Warning>0.1, Critical>0.25）
- zone_dist_PSI：0.003091
- sum_mean_shift_z：1.301788（base=150.7, curr=146.6）
- repeat_rate_z：0.202988（base=0.120, curr=0.123）

## 重要教訓索引

- L85：49C6 稀釋所有頻率信號到偵測閾值以下。
- L86：低基準率遊戲做策略進化時會嚴重過擬合。
- L89：MicroFish 在 BIG_LOTTO 無法挽救低基準率結構。
- L90：大樂透全信號空間窮盡，進入維護模式。
- L91：完整信號邊界研究確認無可利用訊號。

## 2026-04-23 信號窮盡審計

- **結論**: 全域審計確認 BIG_LOTTO 無新可行研究方向
- **理由**: L90/L91 已宣告全信號空間窮盡；2026-04-23 500p 監控顯示 DOWNGRADE_TRIGGERED，無 McNemar 替換候選
- **維護模式確認**: 繼續保留 2/3/5 注參考策略供監控使用，無新升格訊號
- **審計參考**: analysis/results/signal_exhaustion_audit_20260423.md (games.big_lotto 章節)

## Planner 提示

- 若 backlog 提到大樂透新研究，先假設是維護/監控任務，不預設有新可部署訊號。
- 若要重啟探索，必須明確指出「非頻率型新信號」或「規則/池大小變更」。