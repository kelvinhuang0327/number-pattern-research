# DAILY_539

## 現況

- 維護模式；L82 確認 H001~H008 全部 REJECT，既有頻率族信號空間高度飽和。
- 目前保留 ACB / MidFreq / Markov-MidFreq 組合作為主監控策略。
- 2026-04-22：H011 weekday / calendar regime 驗證結論為 **REJECT**；weekday 全局 chi-square p=0.9281、Bonferroni survivors=0，calendar overlay 雖有 1500p raw edge，但 150/500p permutation 與對現役 McNemar 未過，維持不進 RSM。
- 2026-04-22：H012 cross-draw cluster / transition 驗證結論為 **REJECT**；lag-1/2/3 overlap 幾乎等於隨機基準，2bet/3bet 只在 1500p 出現正 raw edge，但 150/500p permutation 未過，無一候選進入 McNemar 替換閘。
- 2026-04-23：**H013 pool-size / market-behavior 驗證結論為 REJECT（弱訊號）**；官方 API 已補齊 100% trusted pool-size data (`sell_amount`, `total_amount`)，正式驗證完成。H013、H013b、H013c 三個候選在 150/500/1500 三窗口全數失敗：edge≈0%、p=1.0、Cohen's d≈0。結論：pool-size 對 539 無預測力，不是資料問題而是假說本身不成立。詳見：`analysis/results/daily539_h013_backfill_final_report_20260423.md`
- 2026-04-23：`microfish_midfreq_2bet` 升格驗證結論為 **REJECT**；active-code mapping 為 `MicroFish+MidFreq 2-bet`，雖 150/500/1500p raw edge、permutation 與 bet2 邊際效率全過，且 leakage audit PASS，但 150p 對 `midfreq_acb_2bet` 的 McNemar 僅 `p=0.1797`（net `+5`），未證明短窗穩定替換優勢，因此維持現役 2 注主線不變。結果檔：`analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json`

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| acb_1bet | 1 | +3.38% | 0.095 | analysis/results/stage0_baseline.json |
| midfreq_acb_2bet | 2 | +8.65% | 0.188 | analysis/results/stage0_baseline.json |
| acb_markov_midfreq_3bet | 3 | +8.81% | 0.180 | analysis/results/stage0_baseline.json |

## 近期候選驗證

| 候選 | 注數 | 結論 | 關鍵阻塞 | 來源 |
|---|---:|---|---|---|
| microfish_midfreq_2bet | 2 | REJECT | 150p McNemar vs `midfreq_acb_2bet` `p=0.1797` | analysis/results/daily539_microfish_midfreq_promotion_validation_20260423.json |

## MicroFish WATCH 條件

- 目前唯一具行動價值的 MicroFish 路徑是「MicroFish+MidFreq 2-bet」。
- 只有在 McNemar 驗證可穩定優於 MidFreq+ACB 時才可升格；否則不重新分配 539 主策略。
- 若無新外部資料源，停止投入 meta-selection / skip model 類研究。

## 重要教訓索引

- L73：539 的 Zone / Sum 序列是白噪音，ZPI v1/v2 全數 REJECT。
- L74：Consecutive Streak 不具可操作訊號。
- L79：ACB × MidFreq 乘積分數因定義互斥而失敗。
- L80：數學構造的自相關不等於預測訊號。
- L81：弱信號乘法疊加不會放大 Edge，反而常退化。
- L82：H001~H008 全軍覆沒，539 進入維護模式。
- L117：weekday / calendar overlay 在 539 缺乏可升格的穩定正交訊號，不要重試 weekday 題。
- L118：cross-draw cluster / transition 在 539 長窗可出現 raw edge，但若跨期 overlap 與隨機近乎一致且 150/500p permutation 未過，仍應直接 REJECT。
- L125：539 的 pool-size / market-behavior 題若 trusted active data 沒有 pool/sales 欄位，就應做資料可用性 REJECT，不得用 proxy 補做偽驗證。
- L128：MicroFish+MidFreq 2-bet 即使三窗口 raw edge / permutation / 邊際效率全過，只要 150p McNemar 未證明穩定優於 `midfreq_acb_2bet`，仍應維持現役不升格。
- **L129：539 的 pool-size 研究即使補齊了 100% trusted data (sell_amount, total_amount from official API)，也未必產生預測訊號。此案例中 H013/H013b/H013c 全部 p=1.0、edge≈0，說明外生市場特徵對 539 的數字生成無預測力。不重試此家族除非有新假說方向。**
- L103：目前 checkout 無正文；backlog 仍保留 L79~L106 範圍引用，需待原始來源補回。
- L104：目前 checkout 無正文；僅有其他研究類比引用，未見正式 lesson 條目。
- L105：目前 checkout 無正文；無法在現有倉庫中還原原文。

## Planner 提示

- 新 539 任務預設為監控、McNemar 驗證、外部新信號或 pool-size / market-behavior 類研究；不重複 H001~H008 類頻率變體，也不重試 H011/H012 已否決家族。
- 若要重啟 pool-size / market-behavior 題，前置條件是先補齊 trusted ingestion/backfill 的 pool 或 sales 欄位；在資料未補齊前，不派同家族重測。
- 若要動到現役策略，必須附帶三窗口、perm、McNemar 三重驗證。
