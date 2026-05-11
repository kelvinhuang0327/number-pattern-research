# Replay Lifecycle Taxonomy Update

**Version**: 1.0  
**Date**: 2026-05-11  
**Base commit**: `f845ab7` (main, post PR #57 merge)  
**Status**: ACTIVE — supersedes any prior informal OFFLINE references  
**Authority**: CTO-accepted decision (PR #57, merged `2026-05-11T14:11:17Z`)  
**Related docs**:
- `docs/replay/strategy_lifecycle_endpoint_contract.md` — API contract
- `outputs/replay/offline_classification_decision_memo_20260511.md` — decision memo (PR #57)
- `outputs/replay/replay_fixture_mode_sop_user_guide_20260511.md` — SOP/User Guide (PR #56)

---

## 1. 正式 Lifecycle Taxonomy（鎖定版）

以下為 LotteryNew replay system 唯一授權的 lifecycle state 定義。

### 1.1 ONLINE

| 屬性 | 值 |
|------|---|
| **語意** | 目前有效、積極參與 production replay path 的策略 |
| **可執行** | `is_executable = true` |
| **可被 scheduler 選取** | 是 |
| **DB replay path** | 是（production DB read + write path 允許） |
| **Fixture mode** | 不適用（fixture mode 只用於 non-ONLINE lifecycle） |

### 1.2 OBSERVATION

| 屬性 | 值 |
|------|---|
| **語意** | 觀察中 / 未決策，不代表正式採用 |
| **可執行** | `is_executable = false` |
| **可被 scheduler 選取** | 否 |
| **DB replay path** | 否（non-executable） |
| **Fixture mode** | ✅ 支援（fixture artifact 含 1 record） |
| **轉移至** | ONLINE（升格）/ REJECTED（驗證不通過）/ RETIRED（決定退役）|
| **適用情境** | 策略已部署但尚未完成驗證，或正等待 CTO 決策 |

### 1.3 REJECTED

| 屬性 | 值 |
|------|---|
| **語意** | 驗證不通過 / governance 判決不採用 |
| **可執行** | `is_executable = false` |
| **可被 scheduler 選取** | 否 |
| **DB replay path** | 否 |
| **Fixture mode** | ✅ 支援（fixture artifact 含 4 records） |
| **轉移至** | 終態 — 不轉移（除非重新命名為新策略） |
| **適用情境** | 通過 validation gate 後被拒絕；或 governance 主動判決不採用 |
| **注意** | 不得將「技術原因暫停」分類為 REJECTED（應使用 RETIRED 或 OBSERVATION） |

### 1.4 RETIRED

| 屬性 | 值 |
|------|---|
| **語意** | 停止使用 / 永久退役（曾為 ONLINE） |
| **可執行** | `is_executable = false` |
| **可被 scheduler 選取** | 否 |
| **DB replay path** | 否 |
| **Fixture mode** | ✅ 支援（fixture artifact 含 5 records） |
| **轉移至** | 終態 — 不恢復 ONLINE |
| **適用情境** | 曾 ONLINE 但因表現不佳、策略更替、或業務決策而永久退役 |
| **注意** | RETIRED = 永久退役，不可逆。若有可恢復需求，不使用 RETIRED |

### 1.5 OFFLINE（暫緩 — 不作為正式 Lifecycle State）

| 屬性 | 值 |
|------|---|
| **語意** | 候選概念 — 尚未定義 |
| **正式狀態** | ❌ **不作為正式 lifecycle state** |
| **Registry 使用** | ❌ 禁止 |
| **UI filter** | ❌ 禁止 |
| **Fixture mode** | ❌ 不支援 |
| **API** | ❌ `lifecycle_status=OFFLINE` 不接受 |
| **決策依據** | PR #57 — OFFLINE Classification Decision Memo（CTO accepted） |

> OFFLINE 的所有語意由現有三態承接：
> - 停止使用 → **RETIRED**
> - 驗證不通過 → **REJECTED**
> - 觀察中 / 未決策 → **OBSERVATION**

---

## 2. Lifecycle State 快速對照表

| 語意需求 | 使用狀態 |
|---------|---------|
| 策略正在產生預測 | `ONLINE` |
| 策略觀察中，尚未決策 | `OBSERVATION` |
| 策略驗證失敗 / governance 拒絕 | `REJECTED` |
| 策略已停用 / 永久退役 | `RETIRED` |
| 策略暫停可恢復 | ⚠️ 目前無對應 state → 使用 `OBSERVATION`，並記錄暫停原因 |
| 策略資料暫不可用 | ⚠️ 目前無對應 state → 使用 `OBSERVATION`，並記錄原因 |
| OFFLINE | ❌ 不得使用 |

---

## 3. OFFLINE 決策正式記錄

本節為 CTO 接受的 OFFLINE classification decision 的正式 taxonomy 入口。

### 3.1 決策摘要

> **目前不引入 OFFLINE 作為獨立 lifecycle state。**

### 3.2 OFFLINE 禁止清單（強制）

| 禁止事項 | 說明 |
|---------|------|
| ❌ Registry 新增 OFFLINE strategy | 不在 registry 中使用 OFFLINE state |
| ❌ UI 新增 OFFLINE filter | Dashboard 不得新增 `lifecycle_status=OFFLINE` filter |
| ❌ API 新增 `lifecycle_status=OFFLINE` 支援 | 現有 API 不接受 OFFLINE 作為合法值 |
| ❌ Fixture mode 新增 OFFLINE records | `non_online_replay_fixture_*.json` 不含 OFFLINE rows |
| ❌ 把 "暫停" 或 "資料不可用" 分類為 OFFLINE | 應使用 OBSERVATION |
| ❌ 把 OFFLINE 當 REJECTED / RETIRED 別名 | 必須使用語意正確的 state |

### 3.3 未來引入 OFFLINE 的必要前置條件

若業務需求確實需要 OFFLINE lifecycle，引入前**全部**必須完成：

1. **語意定義 SOP** — 明確定義 OFFLINE vs RETIRED vs OBSERVATION 的邊界
2. **狀態轉移規則** — 明確列出所有允許與禁止的 state transition（含 OFFLINE → ONLINE 條件）
3. **API 支援** — `lifecycle_status=OFFLINE` contract tests（≥5 tests）
4. **UI 支援** — OFFLINE filter + 空畫面 UX + browser smoke tests
5. **Fixture mode 支援** — 新增 OFFLINE fixture records（≥2 筆）+ contract tests 更新
6. **Governance docs 更新** — taxonomy、validation gate、stability audit 全部更新
7. **CTO explicit YES gate** — 以上全部完成後，等待 CTO 明確授權

---

## 4. Fixture Mode Scope（鎖定版）

### 4.1 目前支援範圍

| Lifecycle | Fixture 支援 | 筆數 |
|-----------|------------|------|
| REJECTED | ✅ | 4 |
| RETIRED | ✅ | 5 |
| OBSERVATION | ✅ | 1 |
| ONLINE | ❌（不適用） | — |
| OFFLINE | ❌（不支援）| — |

### 4.2 Fixture Mode 核心規則

| 規則 | 說明 |
|------|------|
| `fixture_mode=false`（預設）| 維持 production DB read path，不讀 fixture artifact |
| `fixture_mode=true` | Advisory-only validation path，讀 synthetic fixture records |
| `source` | `"synthetic_fixture"`（fixture mode 下每筆 record 必含） |
| `advisory_only` | `true`（fixture mode 下每筆 record 必含） |
| `production_db_write` | `false`（fixture mode 下每筆 record 必含） |
| `fixture_mode` flag | `true`（fixture mode 下每筆 record 必含） |

### 4.3 Fixture Mode 解讀規則

> **Synthetic fixture records 不代表 production replay outcome。**

| 禁止 | 說明 |
|------|------|
| ❌ 以 fixture records 評估 strategy 表現 | 資料為合成，`advisory_only=true` |
| ❌ 以 fixture records 做 promotion 決策 | 不代表 production 結果 |
| ❌ 以 fixture counts（4/5/1）視為實際 replay 次數 | 為驗收用 artifact 固定值 |
| ❌ 在 `fixture_mode=false` 時看到 `synthetic_fixture` | 若發生，視為嚴重路由錯誤 |

### 4.4 Fixture Artifact 路徑

```
outputs/replay/non_online_replay_fixture_20260511.json
```

此 artifact 為唯一授權的 fixture source，不可被替換為 production DB 資料。

---

## 5. Agent 禁止事項（強制）

所有後續 agent 在操作 replay lifecycle 時，必須遵守：

| 禁止 | 說明 |
|------|------|
| ❌ 自行新增 OFFLINE state | 需完整 SOP + CTO YES gate |
| ❌ 自行新增 OFFLINE UI filter | 需先接受 Section 3.3 全部前置條件 |
| ❌ 把 OFFLINE 當 REJECTED 或 RETIRED 別名寫入 registry | 語意不同，不可混用 |
| ❌ 把 synthetic fixture records 作為 strategy performance evidence | `advisory_only=true` |
| ❌ 用本 taxonomy docs 作為 production DB backfill 授權 | 本文件僅為 taxonomy 定義 |
| ❌ 在未收到 explicit YES 前 merge 任何 lifecycle-related PR | 必須遵守 YES gate |
| ❌ 不做 P23 UI Toggle Button（除非 CTO 明確授權）| 須等本 PR merge 後評估 |

---

## 6. 與現有文件的關係

| 文件 | 角色 | 關係 |
|------|------|------|
| `docs/replay/strategy_lifecycle_endpoint_contract.md` | API contract | 本文件補充 taxonomy 語意；API contract 定義 schema |
| `outputs/replay/offline_classification_decision_memo_20260511.md` | Decision memo | 本文件實施該決策，taxonomy 以此為基礎 |
| `outputs/replay/replay_fixture_mode_sop_user_guide_20260511.md` | SOP/User Guide | 本文件補充 fixture mode scope；SOP 定義操作步驟 |
| `outputs/replay/replay_fixture_mode_epic_closure_20260511.md` | Epic closure | 本文件為 epic closure 後的 taxonomy 鎖定 |

### 文件優先順序（衝突時）

1. 本文件（`replay_lifecycle_taxonomy_update_20260511.md`）— 最終 taxonomy 定義
2. `offline_classification_decision_memo_20260511.md` — OFFLINE 決策依據
3. `replay_fixture_mode_sop_user_guide_20260511.md` — 操作 SOP
4. `strategy_lifecycle_endpoint_contract.md` — API schema contract
5. 其他文件 — 參考，不作為 taxonomy 決策依據

---

## 7. 不在本輪範圍

| 排除事項 | 說明 |
|---------|------|
| 修改任何 code | 不動 `lottery_api/`、`index.html`、tests |
| 修改 registry | 不改任何策略的 lifecycle state |
| Production DB backfill | 繼續 defer |
| 新增 OFFLINE filter | 已禁止（Section 3.2）|
| Fixture mode OFFLINE support | 已禁止（Section 4.1）|
| P23 UI Toggle Button | 需等本 PR merge 後 CTO 評估 |
| 策略 state transition | 不做任何 promotion / retire action |

---

## 8. 下一步建議

| 優先度 | 項目 | 說明 |
|--------|------|------|
| **立即（本 PR merge 後）** | CTO 接受本 taxonomy update | 回覆 YES / ACCEPTED |
| **中期** | P23 UI Toggle Button | Fixture mode toggle 由 URL param 升格為 UI button；需本 PR merge 後才可啟動 |
| **中期** | Production DB backfill 評估 | 評估 REJECTED/RETIRED/OBSERVATION 的實際數量，決定 backfill 策略 |
| **長期** | OFFLINE lifecycle 引入評估 | 若業務需求出現，按 Section 3.3 完整 SOP 執行 |

---

## Acceptance Criteria

本文件被接受的標準：

| Criteria | 說明 |
|---------|------|
| ✅ Lifecycle taxonomy 明確 | ONLINE/OBSERVATION/REJECTED/RETIRED 定義清晰無歧義 |
| ✅ OFFLINE deferred 明確 | 禁止清單（Section 3.2）無例外 |
| ✅ Fixture mode scope 明確 | 支援範圍（Section 4.1）固定，不含 OFFLINE |
| ✅ 不改 code | 純 docs 變更 |
| ✅ 不改 registry | 零 registry 修改 |
| ✅ 不寫 DB | `data/lottery_v2.db` 維持 clean |

---

*本文件由 Replay Lifecycle Taxonomy Docs Agent 產出，基於 main commit `f845ab7`。*  
*生效條件：CTO 明確接受（PR #58 merge）。*  
*任何 taxonomy 變更均需獨立 PR + YES gate。*
