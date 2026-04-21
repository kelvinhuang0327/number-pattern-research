# POWER_LOTTO

## 現況

- 現役主體仍是 Fourier / PP3 / Orthogonal 三路組合。
- WATCH / PROVISIONAL 路徑保留給低頻長週期訊號與待升格候選，不直接覆蓋主線策略。

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| fourier_rhythm_3bet | 3 | +3.02% | 0.087 | analysis/results/stage0_baseline.json |
| pp3_freqort_4bet | 4 | +3.28% | 0.086 | analysis/results/stage0_baseline.json |
| orthogonal_5bet | 5 | +2.94% | 0.072 | analysis/results/stage0_baseline.json |

## WATCH / PROVISIONAL

- PP3-Z3Gap：150/500/1500p Edge = +0.16% / +0.83% / +1.64%，perm p=0.045，STABLE，但低於 PP3 baseline，因此只列 WATCH。
- PP3 Sum Regime / Sum Reversal：PROVISIONAL / MONITORING 路徑，需等 200 期監控與 McNemar 結論，不直接升格。
- midfreq_fourier_2bet：2026-04-21 升格驗證失敗，perm 通過但 McNemar 與邊際效率未達標，不能替代 fourier_rhythm_3bet。

## 重要教訓索引

- L83：MidFreq 可成功轉移到威力彩。
- L84：ACB 啟發式不可跨遊戲轉移到威力彩。
- L87：即使有預測邊際，經濟上仍是負 EV。
- L88：通過全閘門不代表能超越現役策略；替換仍需 McNemar。
- L92：Z1 drought detector 無可操作均值回歸。
- L93：H9 Pure MidFreq 2注 perm 通過但 McNemar 未達標，只能 shadow/watch。
- L106：目前 checkout 無正式正文；現有 lesson 編號自 L95 直接跳到 L108。

## Planner 提示

- 優先任務是 WATCH / PROVISIONAL 升格驗證，而非任意替換 Fourier / PP3 主線。
- 若新結果只改善 perm 而未過 McNemar，結論應維持 WATCH 或 SHADOW。