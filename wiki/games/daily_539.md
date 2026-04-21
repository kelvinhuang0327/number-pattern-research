# DAILY_539

## 現況

- 維護模式；L82 確認 H001~H008 全部 REJECT，既有頻率族信號空間高度飽和。
- 目前保留 ACB / MidFreq / Markov-MidFreq 組合作為主監控策略。

## 策略表

| 策略 | 注數 | Edge | Sharpe | 來源 |
|---|---:|---:|---:|---|
| acb_1bet | 1 | +3.38% | 0.095 | analysis/results/stage0_baseline.json |
| midfreq_acb_2bet | 2 | +8.65% | 0.188 | analysis/results/stage0_baseline.json |
| acb_markov_midfreq_3bet | 3 | +8.81% | 0.180 | analysis/results/stage0_baseline.json |

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
- L103：目前 checkout 無正文；backlog 仍保留 L79~L106 範圍引用，需待原始來源補回。
- L104：目前 checkout 無正文；僅有其他研究類比引用，未見正式 lesson 條目。
- L105：目前 checkout 無正文；無法在現有倉庫中還原原文。

## Planner 提示

- 新 539 任務預設為監控、McNemar 驗證或外部新信號研究，不重複 H001~H008 類頻率變體。
- 若要動到現役策略，必須附帶三窗口、perm、McNemar 三重驗證。