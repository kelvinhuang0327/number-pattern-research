# POWER_LOTTO

## 現況

- 現役主體仍是 Fourier / PP3 / Orthogonal 三路組合。
- WATCH / PROVISIONAL 路徑保留給低頻長週期訊號與待升格候選，不直接覆蓋主線策略。

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| fourier_rhythm_3bet [WATCH↓ 2026-04-23] | 3 | 150/500/1500p OOS +1.50% / +1.63% / +2.57% | 0.045 / 0.049 / 0.075 | analysis/results/power_watch_downgrade_decision_20260423.json |
| pp3_freqort_3bet [WATCH 2026-04-23] | 3 | 150/500/1500p OOS +2.83% / +2.83% / +3.17% | 0.082 / 0.082 / 0.090 | analysis/results/power_watch_downgrade_decision_20260423.json |
| pp3_freqort_4bet | 4 | +3.28% | 0.086 | analysis/results/stage0_baseline.json |
| orthogonal_5bet | 5 | +2.94% | 0.072 | analysis/results/stage0_baseline.json |

## WATCH / PROVISIONAL

- PP3-Z3Gap：150/500/1500p Edge = +0.16% / +0.83% / +1.64%，perm p=0.045，STABLE，但低於 PP3 baseline，因此只列 WATCH。
- fourier_rhythm_3bet（2026-04-23）：補完 150 / 500 / 1500p 正式驗證後，raw Edge 為 +1.50% / +1.63% / +2.57%，1500p permutation 已過（p=0.0100, d=2.410），但 150 / 500p permutation 仍失敗（p=0.4975 / 0.2537, d=0.085 / 0.654）。failure-aware 5x300 OOS 切片雖然 5/5 都維持正 raw Edge，但有 4/5 切片 permutation 未過、最新 slice 只剩 +0.83% edge 且 p=0.5274，因此本輪結論是「維持 WATCH、但下調優先級」，不再視為主監控候選。來源：`analysis/results/power_watch_downgrade_decision_20260423.json`
- pp3_freqort_3bet（2026-04-23）：維持既有 B 方案（history-only score blend）做唯一替代前置檢查；150 / 500 / 1500p raw Edge 為 +2.83% / +2.83% / +3.17%，permutation 為 p=0.4876 / 0.1542 / 0.0050，Cohen's d = 0.063 / 1.089 / 2.822，且對 `pp3_freqort_4bet` 的 per-bet efficiency 為 79.9% / 118.2% / 129.4%。由於 150p efficiency 未達 80%，且 150 / 500p permutation 未過，因此 McNemar 不觸發，結論仍為 WATCH，不替換 `fourier_rhythm_3bet`，現役 `pp3_freqort_4bet` 也維持主力不變。下一輪應轉向新的非同家族 Layer-1 3bet 訊號，而不是重排現有 PP3/Fourier 家族。來源：`analysis/results/power_watch_downgrade_decision_20260423.json`
- PP3 Sum Regime / Sum Reversal（2026-04-23）：完成 200p 監控與 150 / 500 / 1500p 正式驗證。`pp3_sum_regime_detector` 的 200p / 150p / 500p / 1500p raw Edge 為 +2.33% / +3.50% / +1.63% / +2.17%，但 permutation p = 0.1791 / 0.2139 / 0.0398、Cohen's d = 1.124 / 0.806 / 2.155，且對 `pp3_freqort_4bet` 的 per-bet efficiency 只有 98.7% / 68.2% / 88.6%；`pp3_sum_reversal_filter` 為 +0.83% / +2.17% / +1.83% / +2.50%，permutation p = 0.3085 / 0.2090 / 0.0100、Cohen's d = 0.626 / 0.939 / 2.491，per-bet efficiency = 61.1% / 76.5% / 102.2%。兩者都只在 1500p permutation 過關，150 / 500p 顯著性與 4bet 邊際效率未全過，因此本輪結論統一改列 WATCH，不進 McNemar、不升格、不替代 `fourier_rhythm_3bet` 或 `pp3_freqort_4bet`。來源：`analysis/results/power_pp3_sum_regime_validation_20260423.json`
- midfreq_fourier_2bet：2026-04-21 升格驗證失敗，perm 通過但 McNemar 與邊際效率未達標，不能替代 fourier_rhythm_3bet。
- midfreq_fourier_2bet_regime_gate_v1（2026-04-23）：以 history-only 固定 gate（`mean10_sum_low -> cold_residual_60`，否則 `prev_hot_overlap>=4 -> hot_residual_60`，其餘維持 Fourier residual）把 150/500/1500p raw Edge 修到 +3.08% / +2.81% / +1.74%，且 leakage check PASS、per-bet efficiency 為 433.3% / 85.7% / 97.2%；但 permutation 仍為 0.0995 / 0.0249 / 0.0249，150p 未能壓到 0.05 以下，因此不進 500p McNemar，結論直接 REJECT。來源：`analysis/results/power_midfreq2bet_regime_gate_v1_20260423.json`
- PP3 + MidFreq 正交 bet4（2026-04-22）：`mf_residual_4bet` / `mf_antifourier_4bet` / `mf_stable_antifourier_4bet` 在 1500p 仍有 +3.06% / +3.06% / +2.86% Edge，perm p=0.0199 / 0.0149 / 0.0299，但 150p 與 500p permutation 皆未過，且 bet4 邊際效率僅 74.7%~77.2% < 80%，因此只列 WATCH，不觸發 McNemar、不升格。
- PP3 + MidFreq 正交 V2（2026-04-23）：6 個 history-only 候選（3bet/4bet 各 3 組）明確避開 WQ、special V3/V4 重排與 midfreq regime-gate 重試；最佳 `pp3_midfreq_residual_strata_4bet` 的 150/500/1500p raw Edge 為 +2.06% / +2.80% / +2.60%，但 permutation 只在 1500p 過關（p=0.5224 / 0.1741 / 0.0448，d=-0.002 / 1.002 / 1.770），且 per-bet efficiency 只有 71.4% / 73.1% / 65.4%。最佳 3bet `pp3_midfreq_residual_strata_3bet` 也僅有 +1.50% / +2.03% / +1.57% Edge，permutation p=0.5075 / 0.1692 / 0.1294；全案 5 個候選列 WATCH、1 個列 REJECT，無任何候選進入 McNemar，因此不替代 `fourier_rhythm_3bet` 或 `pp3_freqort_4bet`。來源：`analysis/results/power_pp3_midfreq_orthogonal_v2_20260423.json`
- 特別號 V3 orthogonal shortlist（2026-04-22）：`special_v3_drought_regime_top2` / `special_v3_markov_backoff_top2` / `special_v3_main_analog_residual_top2` 在 150/500/1500p Edge 皆維持正值，最佳 `main_analog_residual_top2` 為 +4.33% / +1.40% / +1.33%，但三者 permutation p 皆未能在全窗口壓到 0.05 以下，因此結論僅為 WATCH；不可直接升級 RSM，也不應成為下一輪主優先研究方向。來源：`analysis/results/power_special_v3_research_20260422.json`
- 特別號 V4 orthogonal reinforcement（2026-04-23）：五個 V3-based history-only top2 候選中，最佳 `special_v4_regime_orthogonal_top2` 的 150/500/1500p Edge 為 +5.67% / +1.20% / +1.80%，Cohen's d 為 1.563 / 0.652 / 1.614，但 permutation p 仍卡在 0.0796 / 0.2836 / 0.0547，未能全窗口 <0.05；而現役 V3 top2 參考仍有 +11.67% / +4.40% / +2.33% Edge，更高於所有候選，因此本輪結論為 REJECT，不觸發 McNemar、不替換現役 special V3。來源：`analysis/results/power_special_v4_validation_20260423.json`
- 非同家族 Layer-1 3bet（2026-04-23）：4 個新家族 `dispersion_state_transition_3bet`、`odd_tail_imbalance_3bet`、`zone_transition_tensor_3bet`、`residue_structure_stability_3bet` 全部完成 150/500/1500p 驗證，且 leakage check PASS。最佳 raw Edge 為 `residue_structure_stability_3bet` 的 +2.17% / +3.23% / +1.77%，以及 `zone_transition_tensor_3bet` 的 +1.50% / +1.43% / +0.97%；但四案 permutation 仍為 0.2587~0.5871 / 0.1194~0.5871 / 0.2189~0.4726，Cohen's d 最佳也只到 residue 500p 的 1.393，且對 `pp3_freqort_4bet` 的 per-bet efficiency 未有任何候選在三窗口全過 80%。因此 McNemar 對 `fourier_rhythm_3bet` 完全不觸發，總結論明確為 `REJECT_ALL_NONFAMILY_LAYER1_3BET`。來源：`analysis/results/power_layer1_nonfamily_3bet_validation_20260423.json`

## 重要教訓索引

- L83：MidFreq 可成功轉移到威力彩。
- L84：ACB 啟發式不可跨遊戲轉移到威力彩。
- L87：即使有預測邊際，經濟上仍是負 EV。
- L88：通過全閘門不代表能超越現役策略；替換仍需 McNemar。
- L92：Z1 drought detector 無可操作均值回歸。
- L93：H9 Pure MidFreq 2注 perm 通過但 McNemar 未達標，只能 shadow/watch。
- L115：PP3 的 MidFreq 殘餘池 bet4 若只在 1500p 有訊號、但短窗 perm 與 bet4 效率未過，結論仍只能是 WATCH。
- L116：特別號 shortlist 若只有 raw Edge 連三窗為正、但 permutation p 未過 0.05，全案仍只能列 WATCH，不得升級或擠掉現役 special V3。
- L121：特別號 V3-based V4 重排若連現役 V3 top2 參考都無法超越，且 permutation 只差臨門一腳（如 1500p p=0.0547），結論仍是 REJECT，不應再以同家族微調作為優先主線。
- L122：威力彩 2 注 regime gate 即使把短窗 raw Edge 與邊際效率修回全正，只要 150p permutation 未過，就應直接 REJECT，不把條件分流誤當成穩定時序訊號。
- L123：威力彩 PP3 + MidFreq 正交 V2 若只在 1500p 保留 permutation 訊號、但 150/500p permutation 與 per-bet efficiency 仍未過，代表此家族僅剩弱長窗可遷移性，結論應停在 WATCH/REJECT，而不是再做同家族微調升格。
- L124：威力彩 PP3 Sum Regime / Sum Reversal 即使 200p 監控與 1500p 長窗仍有正 raw Edge，若 150/500p permutation 或對 `pp3_freqort_4bet` 的 per-bet efficiency 未全過，結論仍只能列 WATCH，不進 McNemar，也不該再保留「快可升格」敘事。
- L126：威力彩 WATCH 主線若 1500p 仍保留顯著性、但 5x300 rolling slice 有 >=80% permutation 失敗率，應保留 WATCH 並降權，而不是因 raw Edge 全正就繼續維持主監控優先級。
- L127：威力彩非同家族 Layer-1 3bet 即使多案 raw Edge 三窗全正，只要 permutation 與對 `pp3_freqort_4bet` 的 per-bet efficiency 沒有任何候選全窗過關，整體結論仍應是 `REJECT_ALL_NONFAMILY_LAYER1_3BET`。
- L106：目前 checkout 無正式正文；現有 lesson 編號自 L95 直接跳到 L108。

## Planner 提示

- 優先任務是 WATCH / PROVISIONAL 升格驗證，而非任意替換 Fourier / PP3 主線。
- 若新結果只改善 perm 而未過 McNemar，結論應維持 WATCH 或 SHADOW。
- 特別號 V4 orthogonal reinforcement 已 REJECT；若無新特徵家族，不再把 special V3 同家族重排列為優先主線。
- `fourier_rhythm_3bet` 已完成 failure-aware 降權驗證；下一輪主題應改做新的非同家族 POWER_LOTTO Layer-1 3bet 訊號，而非延伸現有 Fourier / PP3 / midfreq / special 家族。
- 非同家族 Layer-1 3bet 四個結構族（dispersion / odd-tail / zone tensor / residue stability）已完成正式驗證且整體 REJECT；若未引入新的特徵來源或新的驗證框架，不應立即重跑這四個家族的微調版。
