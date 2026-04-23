## 知識讀取規則（強制 / Knowledge Gate System）

本系統採用「唯一入口 + 白名單 + 禁止 fallback」的 Knowledge Gate 機制。

Agent 在任何任務中 **必須遵守以下規則**：

---

### 【一、唯一入口（強制順序）】

1. **必須從 `wiki/README.md` 開始**
   - 這是唯一知識入口（Single Source of Truth）
   - 所有推論必須建立在 wiki routing 上

2. **再讀 `wiki/*`**
   - validation → `wiki/validation_gates.md`
   - decision / UI → `wiki/governance.md`
   - stability → `wiki/stability_audit.md`
   - learning / feedback → `wiki/feedback_loop.md`

3. **再讀 `memory/`**
   - lessons → `memory/lessons.md`
   - history → `memory/MEMORY.md`

4. **`docs/` 僅在「明確指定檔名」時才可讀**
   - 不得主動掃描 docs
   - 僅允許使用：
     - `decision_layer_v3_report.md`
     - 其他被 wiki 明確引用文件

---

### 【二、預設禁止讀取（UNTRUSTED）】

以下全部預設為「不可信來源」，不得用於決策：

- 根目錄散落 `*.md`（除以下例外）
  - `CLAUDE.md`
  - `SYSTEM_MAP.md`
  - `AGENT_RULES.md`
  - `README.md`
- `archive/`、`docs/archive/`
- `legacy/`
- 所有 `*_report.md`（除非被白名單允許）
- 所有帶有以下標記文件：
  - SUPERSEDED
  - DEPRECATED
  - ARCHIVED
  - DO NOT USE

---

### 【三、嚴格禁止行為】

- 不得將以下文件視為最新結論：
  - `RESEARCH_PROGRESS_*`
  - `failure_analysis_*`
  - `draw_analysis_*`
  - `PREDICTION_REPORT_*`
- 不得從 archive / legacy 推論現況
- 不得建立新的 knowledge 入口（入口只能是 wiki + memory）
- 不得為了補齊答案去讀未授權文件

---

### 【四、衝突處理（強制優先順序）】

若不同來源出現衝突：

優先順序為：

1. `wiki/governance.md`
2. `wiki/validation_gates.md`
3. `wiki/stability_audit.md`
4. `wiki/feedback_loop.md`
5. docs（白名單）
6. 其他（全部忽略）

---

### 【五、STOP 條件（必須中止）】

若發生以下情況，必須停止並回覆：

> "INSUFFICIENT TRUSTED DATA"

條件：

- 必要資訊只存在於 untrusted 文件
- wiki 未覆蓋該問題
- trusted sources 彼此矛盾且無法解決
- 無法透過 active code / data 驗證

嚴禁使用舊報告或 archive 補推論

---

### 【六、Anti-Hallucination 規則】

不得因以下原因認定文件為可信：

- 文件很完整
- 文件名稱看起來專業
- 與過去結論一致
- 包含詳細分析

👉 只有「被 wiki routing 指向」才是可信

---

### 【七、多 Agent 一致性（重要）】

所有子 agent 必須遵守相同 Knowledge Gate：

- 不得各自掃描 repo
- 不得跨角色使用未授權文件
- 每個 agent 只能使用其 routing 指定文件

---

### 【八、最終原則】

本系統原則：

👉 **讀少，但讀對**

優先正確性 > 完整性  
禁止為了完整答案而使用錯誤來源