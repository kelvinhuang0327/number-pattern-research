# 文件治理規則（Governance）

> 本檔是文件治理 source-of-truth。所有 agent 讀取知識前必須先讀本檔。

---

## 知識入口優先順序（強制）

1. **`wiki/`** — 唯一穩定知識入口，先讀
2. **`memory/`** — 教訓與 todo，次讀
3. **`docs/`** — 僅在檔名被明確引用時才讀
4. **根目錄 `*.md`** — 預設不作為知識入口（CLAUDE.md、SYSTEM_MAP.md、AGENT_RULES.md、README.md 除外）
5. **`docs/archive/`** — 歸檔文件，僅供回溯查閱，不代表最新結論

---

## 文件分類標準

| 類型 | 位置 | 讀取條件 |
|------|------|----------|
| 穩定規則與索引 | `wiki/` | 優先讀取 |
| 教訓正文 | `memory/lessons.md` | 讀完 wiki 後補充 |
| 技術詳情報告 | `docs/` | 被明確引用時 |
| 過期/單期分析 | `docs/archive/` | 歷史回溯用 |
| 實驗結果、策略數據 | `strategies/`、`provisional/`、`rejected/` | 按需讀取 |

---

## 高風險文件類型（預設歸檔）

以下類型文件視為高風險，預設不讀，應讀對應 wiki 摘要：
- `RESEARCH_PROGRESS_*` → 讀 `wiki/system/validation_gates.md`
- `failure_analysis_*`、`draw_analysis_*` → 讀 `wiki/system/feedback_loop.md`
- `PREDICTION_REPORT_*` → 讀 `wiki/games/{game}.md`
- `DESIGN_REVIEW_*` → 讀 `wiki/system/governance.md`
- `*_strategy_report.md`（根目錄）→ 讀 `wiki/games/{game}.md`

---

## Wiki 內容原則

1. **只寫穩定規則**：不放容易過期的數值結論、實驗數字、單期分析。
2. **短摘要 + 路由**：每份 wiki 文件不超過 80 行。
3. **不重複正文**：`memory/lessons.md` 是教訓正文；wiki 只做索引與入口。
4. **版本管理**：修改 wiki 時在本檔底部記錄更新日期與摘要。

---

## 歸檔規則

- 歸檔文件移至 `docs/archive/`。
- 歸檔文件首行加入 superseded 提示，格式：
  ```
  > ⚠️ SUPERSEDED: 最新結論請先讀 wiki/... 與 memory/lessons.md
  ```
- 歸檔索引維護於 `docs/archive/INDEX.md`。
- 歸檔文件不得刪除，只能增加 superseded 標記。

## ID & Integration Rules (extracted)

- Canonical IDs: project MUST maintain a single canonical `lottery_type` ID list (source: `lottery_api/data/lottery_types.json`).
- Change process: ID changes require: (1) update `lottery_types.json`, (2) update `src/utils/LotteryTypes.js`, (3) run `verify_id_unification` test, (4) create backups and a rollback script.
- Versioning: record config version in `docs/IMPLEMENTATION_STATUS.md` and mark the canonical version in wiki when promoting changes.

## Predictor API Requirements (extracted)

- Predictors/engines must implement a minimal interface: functions like `ensemble_predict`, `zone_balance_predict`, `bayesian_predict`, `trend_predict`, `anti_consensus_predict` with signatures `(history, lottery_rules[, window_size])` returning `{numbers: list, special?: int}`.
- Implementation checklist: unit tests covering return shape, window parameter handling, and no data-leakage on sample inputs.

---

## 更新記錄

| 日期 | 摘要 |
|------|------|
| 2026-04-22 | 初版建立，配合知識層收斂重構 |
