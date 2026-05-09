# Lottery Prediction System

## 開發工作流

### 計劃優先
- 非平凡任務必須進入 plan mode
- 所有策略研究必須先產生 research_plan.md
- 策略決策與設計規範參見 `lottery_api/CLAUDE.md`
- 未經驗證策略不得進入 production pipeline

---

### 驗證標準
- 必須通過 1500期三窗口驗證（150 / 500 / 1500）
- 三窗口 ROI 必須皆 > baseline
- 統計顯著性 p < 0.05
- 必須通過 permutation test
- 必須通過 walk-forward OOS 測試
- Sharpe Ratio > 0 才可標記為有效策略

---

### 教訓追蹤
- 每次策略失敗必須記錄至 `memory/MEMORY.md`
- 每個 rejected 策略需生成：

  rejected/{strategy_name}.json

  包含：
  - 失敗原因
  - 統計結果
  - 適用條件
  - 未來重新測試條件

- 舊策略不得刪除，只能歸檔

---

### 策略生命週期
所有策略必須經過：

Idea → Simulation → Backtest → Validation → Deploy → Monitor → Re-evaluate

各階段必須產生：

| 階段 | 文件 |
|------|------|
| Idea | strategy.yaml |
| Simulation | sim_result.json |
| Backtest | backtest_report.md |
| Validation | stat_test.txt |
| Deploy | version_tag.txt |
| Monitor | performance_log.json |

---

### 自動研究模式
系統必須支援 discovery mode

當系統資源閒置時自動執行：
- 隨機策略生成
- 特徵組合測試
- 參數突變測試
- 特徵淘汰測試

生成策略需滿足：
- 與現有策略相似度 < 70%
- 複雜度不超過目前最佳策略 ×1.5

---

### 策略評分公式
所有策略統一評分：

Score = (ROI × Stability × Significance) ÷ Complexity

定義：
- ROI = 平均回報率
- Stability = 三窗口一致性
- Significance = −log10(p)
- Complexity = 特徵數 × 參數數

只有 Score > baseline 才可晉級

---

### 重新驗證機制
以下條件觸發全策略重新測試：

- 新資料加入
- 規則變更
- 中獎率分布異常
- 頭獎金額分布偏移
- 玩家行為分布改變

---

### 可追溯原則
所有分析必須可重現：

- 固定 random seed
- 保存資料快照
- 記錄版本號
- 記錄模型參數

不可重現結果一律視為無效

---

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `memory/MEMORY.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Plan First**: Write plan to `memory/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `memory/todo.md`
6. **Capture Lessons**: Update `memory/MEMORY.md` after corrections

---

## Core Principles

- **Simplicity First**: 優先選擇最簡單且有效策略
- **No Laziness**: 禁止跳過驗證流程
- **Minimal Impact**: 不允許策略修改影響既有系統穩定性
- **Full Traceability**: 所有結果必須可回溯
- **Fail but Record**: 允許失敗，但禁止遺失紀錄
- **Research Never Stops**: 系統需持續探索未知策略空間
