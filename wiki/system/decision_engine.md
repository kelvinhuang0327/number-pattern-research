# Decision Engine

## API

- 主要入口：GET /api/decision/{lottery_type}
- 用途：回傳下期決策建議、風險/注數配置與決策層摘要。

## Stage 1-6

| Stage | 作用 | 核心結論 |
|---|---|---|
| 1 | Confidence Score + Betting Gate | 可過濾低信心期，但單獨無法創造新訊號 |
| 2 | Position Sizing | 提升 conditional edge_per_bet，但 unconditional EV 仍為負 |
| 3 | Payout Optimization / Anti-Crowd | BIG_LOTTO 有小幅 ROI uplift，但 perm 不顯著 |
| 4 | Cross-Game Allocation | Fractional Kelly 分配；三遊戲 Kelly 皆趨近 0 |
| 5 | Validation Gates | 三窗口、perm、McNemar、Sharpe 的嚴格驗證閘 |
| 6 | Integration Report | 匯總各 stage 結論並標示可部署性 |

## 核心結論

- L99-L102 結論一致：決策層可以降低損失或改善條件式表現，但無法把三款遊戲變成正 EV。
- 嚴格驗證報告顯示 Stage 2 在 DAILY_539 / BIG_LOTTO / POWER_LOTTO 全部都是 ADVISORY_ONLY。
- BIG_LOTTO Stage 3 Anti-Crowd 雖有 ROI Δ+1.04%，但 perm p=0.257，仍屬 advisory。
- Kelly 結果為 0 的原因不是公式錯，而是 jackpot variance 主導且 monetary ROI 深負。

## L99-L102 摘要

- L99：Kelly sizing 在負 EV 彩券域只會收斂到 0，不能把資訊邊際轉成正資金邊際。
- L100：Position sizing 的 improvement 主要是 exposure control，不是策略訊號提升。
- L101：選擇性下注有結構性稀釋；conditional hit rate 變好，不代表 unconditional edge 變正。
- L102：Anti-crowd / popularity 調整可做 advisory，但 effect size 太小，不宜當成主決策層。

## Planner 提示

- 若任務涉及 Decision V3，預設結論應是「risk wrapper / advisory layer」，不是「新正 EV 引擎」。
- 涉及 Stage 2-4 的修改時，必須同時檢查 conditional 與 unconditional 指標。