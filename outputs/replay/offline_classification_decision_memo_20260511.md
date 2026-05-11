# OFFLINE Classification Decision Memo

**版本**: 1.0  
**日期**: 2026-05-11  
**基準 commit**: `7689189` (main, post PR #56 merge)  
**撰寫者**: PR #56 SOP Merge Gatekeeper + OFFLINE Classification Decision Memo Agent  
**回報對象**: CTO  
**狀態**: PENDING CTO ACCEPTANCE — 不可執行任何 code / registry 變更

---

## 1. 文件目的

本備忘錄決定 **OFFLINE lifecycle** 是否應獨立存在於 LotteryNew 的 strategy lifecycle taxonomy 中。

**決策範疇**：
- OFFLINE 是否需要獨立 lifecycle state
- OFFLINE 應否併入 RETIRED 或 REJECTED
- 目前是否應新增 OFFLINE UI filter
- 目前 fixture mode 是否應支援 OFFLINE
- 若未來要引入 OFFLINE，需要哪些 SOP / taxonomy / transition rules

**不在本文件範疇**：
- 不改 code
- 不改 registry
- 不做 migration / backfill
- 不新增 UI filter
- 不做 strategy state transition

---

## 2. 現況摘要

### 2.1 目前 Lifecycle Taxonomy

| Lifecycle State | 語意 | 說明 |
|----------------|------|------|
| `ONLINE` | 線上運行中 | 積極產生預測，參與 scheduler |
| `OBSERVATION` | 觀察中 / 未決策 | 已部署但非主動產生預測，等待評估 |
| `REJECTED` | 驗證不通過 | 策略通過驗證流程後被拒絕，不再考慮 |
| `RETIRED` | 已停用 | 曾 ONLINE，因表現不佳或策略更替而退役 |
| `OFFLINE` | **未定義 / 候選概念** | 無任何策略目前使用此狀態 |

### 2.2 OFFLINE 目前狀態

```
OFFLINE 在 registry 中目前無任何實際策略。
OFFLINE 是候選語意概念，從未正式部署。
```

### 2.3 Fixture Mode 涵蓋範圍

Fixture mode（PR #51 ~ #56）目前涵蓋：
- `REJECTED`（4 records）
- `RETIRED`（5 records）
- `OBSERVATION`（1 record）

**OFFLINE 不在 fixture mode 涵蓋範圍。**

### 2.4 使用者可視化需求

目前 dashboard replay section 已可正確可視化所有 non-ONLINE lifecycle states：
- lifecycle filter：REJECTED / RETIRED / OBSERVATION
- fixture banner：`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測`

OFFLINE 的可視化需求目前**不存在**，因為沒有使用 OFFLINE 的策略。

---

## 3. OFFLINE 候選語意定義

若 OFFLINE 未來需要引入，以下為潛在語意候選：

| 候選 | 語意定義 | 適用情境 |
|------|---------|---------|
| **A** | 暫停線上評估但仍可能恢復 | 策略暫時下線，預計在條件滿足後恢復 ONLINE |
| **B** | 無資料或暫不可驗證 | 資料源斷線、資料品質不足，無法進行驗證 |
| **C** | 已停用但未正式 retired | 停止使用，但不確定是否永久，暫不走 RETIRED |
| **D** | 不獨立存在，語意分拆至 RETIRED / REJECTED | OFFLINE 概念由現有 lifecycle 承接，不新增獨立 state |

---

## 4. 三條決策路徑

### 4.1 路徑 A — 保留 OFFLINE 作為獨立 Lifecycle State

**優點**：
- 提供語意上的中間態（暫停但可恢復，有別於 RETIRED 的永久停用）
- 符合部分 trading system 中 "paused" 狀態的慣例

**缺點**：
- 目前沒有任何策略使用，引入即產生空 filter / 空畫面
- 增加 taxonomy 複雜度，UI、API、docs 均需配套
- "暫停" 與 "OBSERVATION" 語意邊界模糊，易造成誤用
- fixture mode 需額外支援 OFFLINE（需新增 fixture records）
- 需要明確的 OFFLINE → ONLINE / OFFLINE → RETIRED 轉移 SOP

**需要新增的工作**：
- `lifecycle_status=OFFLINE` API 支援
- UI filter 新增 OFFLINE 選項
- fixture mode 新增 OFFLINE records（至少 1 筆）
- 策略狀態轉移 SOP：OFFLINE → ONLINE / OFFLINE → RETIRED / ONLINE → OFFLINE
- governance docs 更新 taxonomy

---

### 4.2 路徑 B — 併入 RETIRED

**優點**：
- RETIRED 已有明確語意：「曾 ONLINE，現已停用」
- 若 OFFLINE 的用意是「停止使用」，RETIRED 完全可以承接
- 不增加 taxonomy 複雜度
- 現有 fixture mode、UI filter、API 均無需改動

**缺點**：
- 若 OFFLINE 語意是「暫停但可恢復」，RETIRED 的「永久退役」語意不符
- 若未來需要 "暫停後恢復" 工作流，RETIRED 無法反向轉為 ONLINE（依現行 governance）

**對現有 replay lifecycle 的影響**：
- 無影響，RETIRED 路徑已通過 fixture mode 驗證（5 records）
- 若現有 OFFLINE 策略需要 migrate，直接 reclassify 為 RETIRED

---

### 4.3 路徑 C — 併入 REJECTED

**優點**：
- 若 OFFLINE 的用意是「資料不可用 / 驗證無法進行」，REJECTED 語意接近
- 不增加 taxonomy 複雜度
- 現有 fixture mode、UI filter、API 均無需改動

**缺點**：
- REJECTED 語意強烈暗示「通過驗證流程後被拒絕」，帶有明確的 governance 意涵
- 若 OFFLINE 只是「資料暫不可用」，放入 REJECTED 會誤導使用者認為策略驗證失敗
- 混淆 "技術原因停用" 與 "策略品質不佳" 的差別
- 對 governance / validation 的影響：REJECTED 的統計數字會被污染

**對 governance / validation 的影響**：
- 若 OFFLINE 策略被 reclassify 為 REJECTED，可能扭曲 rejection rate 統計
- 需要在 governance docs 明確標記哪些 REJECTED 是「技術原因」vs「驗證不通過」

---

## 5. CTO 推薦決策

### ✅ 推薦決策：**路徑 B（默認）+ OFFLINE 暫緩**

**明確推薦如下**：

> **目前不引入 OFFLINE 作為獨立 lifecycle state。**
> 語意上的「停止使用」由 **RETIRED** 承接。
> 語意上的「驗證不通過」由 **REJECTED** 承接。
> 語意上的「觀察中 / 未決策」由 **OBSERVATION** 承接。
> OFFLINE 僅作為未來候選概念，**必須有完整 SOP 後才可引入**。

**推薦理由**：

| 理由 | 說明 |
|------|------|
| 零實際用量 | registry 目前無任何 OFFLINE 策略，引入產生死 filter |
| 語意重疊 | OFFLINE 的所有潛在語意均已由現有三態（REJECTED/RETIRED/OBSERVATION）覆蓋 |
| 最小化複雜度 | 不引入不需要的 lifecycle state，保持 taxonomy 清晰 |
| fixture mode 安全 | 不需要為 OFFLINE 新增 fixture records，現有驗收不受影響 |
| 可逆性 | 若未來確實需要 OFFLINE，有明確的引入流程（見 Section 7），代價不大 |

**Lifecycle 語意對照（確認版）**：

```
ONLINE      → 積極運行中
OBSERVATION → 觀察中 / 暫緩評估 / 未決策
REJECTED    → 驗證不通過（governance判決）
RETIRED     → 已停用（曾ONLINE，現永久退役）
OFFLINE     → 不引入（暫緩，候選概念）
```

---

## 6. 推薦決策的 Acceptance Criteria

若 CTO 接受本推薦（路徑 B + OFFLINE 暫緩），以下為 acceptance criteria：

| Criteria | 說明 |
|---------|------|
| ✅ Registry 不新增 OFFLINE strategy | 不在 registry 中使用 OFFLINE state |
| ✅ UI 不新增 OFFLINE filter | dashboard 不新增 lifecycle_status=OFFLINE 的 filter 選項 |
| ✅ API 不新增 `lifecycle_status=OFFLINE` 支援 | 現有 API 維持現狀 |
| ✅ Fixture mode 暫不支援 OFFLINE | `non_online_replay_fixture_20260511.json` 不新增 OFFLINE records |
| ✅ OFFLINE 語意由 RETIRED / REJECTED / OBSERVATION 承接 | 依語意分類至對應 state |
| ✅ 若未來需要引入 OFFLINE，必須先完成 Section 7 的 SOP | 不可 ad-hoc 引入 |
| ✅ Taxonomy docs 更新以明確標記 OFFLINE 為 "暫緩候選概念" | 更新 lifecycle taxonomy doc（下一輪）|

---

## 7. 若未來要引入 OFFLINE — 必要前置條件

若未來業務需求確實需要 OFFLINE lifecycle，引入前必須完成以下全部工作：

### 7.1 語意定義 SOP（必要）
- 明確定義 OFFLINE 的語意邊界（區別於 RETIRED / OBSERVATION）
- 回答：OFFLINE 策略可否恢復 ONLINE？條件是什麼？
- 回答：OFFLINE 由誰觸發？trigger condition 是什麼？
- 更新 lifecycle taxonomy docs

### 7.2 狀態轉移圖（必要）

```
ONLINE → OFFLINE：觸發條件（停用但保留可恢復性）
OFFLINE → ONLINE：恢復條件（明確定義）
OFFLINE → RETIRED：升格為永久退役的條件
OBSERVATION → OFFLINE：是否允許此轉移？
REJECTED → OFFLINE：是否允許此轉移？
```

必須明確禁止的轉移也需列出。

### 7.3 API 支援
- `lifecycle_status=OFFLINE` query param 支援
- contract tests 更新（至少 5 tests for OFFLINE）
- 現有 44 contract tests 回歸不能 fail

### 7.4 UI 支援
- dashboard replay section 新增 OFFLINE filter 選項
- 確認 OFFLINE 無策略時的空畫面 UX
- browser smoke tests 更新

### 7.5 Fixture Mode 支援
- 新增 OFFLINE fixture records（建議至少 2 筆）
- 更新 `non_online_replay_fixture_*.json` artifact
- fixture mode contract tests 更新

### 7.6 Governance 更新
- 更新 lifecycle governance docs
- 更新 validation gate docs
- 更新 stability audit 規則

---

## 8. 風險與不確定點

| 風險 | 說明 | 緩解 |
|------|------|------|
| 語意不清導致誤用 | OFFLINE 若無清晰定義，開發者可能隨意分類策略為 OFFLINE | 本推薦：暫緩引入，先建立 SOP |
| Prematurely 加 OFFLINE filter → 空畫面 | 沒有 OFFLINE 策略時 UI 顯示空結果，用戶困惑 | 本推薦：不新增 filter |
| OFFLINE 與 OBSERVATION 語意重疊 | "暫停評估" vs "無法評估" 邊界不清 | 本推薦：OBSERVATION 承接所有中間態 |
| 併入 RETIRED 掩蓋「可恢復性」 | 若未來有策略是「暫停可恢復」，RETIRED 的語意不允許回退 ONLINE | 緩解：RETIRED = 永久退役；若有可恢復需求，必須引入 OFFLINE（按 Section 7 SOP）|
| 併入 REJECTED 污染 validation 統計 | REJECTED count 被「技術暫停」的策略拉高，誤導 governance 判斷 | 本推薦：REJECTED 保持「驗證不通過」的純粹語意 |

---

## 9. 不在本輪範圍

以下項目明確排除在本文件執行範疇之外：

| 排除事項 | 說明 |
|---------|------|
| 修改任何 code | 不動 `lottery_api/`、`index.html`、tests |
| 修改 registry | 不改任何策略的 lifecycle state |
| production DB backfill | 繼續 defer |
| 新增 OFFLINE filter | 需先接受本 memo 並完成 Section 7 |
| fixture mode OFFLINE support | 需先接受本 memo 並完成 Section 7 |
| 策略 state transition | 不做任何 promotion / retire action |
| P23 UI Toggle Button | 需等 taxonomy 決策被接受後才可啟動 |

---

## 10. 下一步建議

### 若 CTO 接受本 Memo（路徑 B + OFFLINE 暫緩）

| 優先度 | 項目 | 說明 |
|--------|------|------|
| **立即** | 更新 lifecycle taxonomy docs | 明確標記 OFFLINE = 暫緩候選，不得使用 |
| **中期** | P23 UI Toggle Button | Fixture mode toggle 由 URL param 升格為 UI button |
| **中期** | production DB backfill 評估 | 在 OFFLINE 決策確定後，評估 REJECTED/RETIRED/OBSERVATION 的真實數量 |
| **長期** | OFFLINE 引入評估 | 若業務需求出現，按 Section 7 完整 SOP 執行 |

### 若 CTO 不接受（選擇路徑 A — 保留 OFFLINE）

> 需要 CTO 明確指示，並由下一輪 Agent 執行 Section 7 全部工作。
> 本輪不執行任何 OFFLINE 引入工作。

---

## Artifact Reference

| 檔案 | 角色 |
|------|------|
| `outputs/replay/non_online_replay_fixture_20260511.json` | Fixture artifact（REJECTED/RETIRED/OBSERVATION，無 OFFLINE）|
| `lottery_api/routes/replay.py` | lifecycle filter 現況實作 |
| `outputs/replay/replay_fixture_mode_sop_user_guide_20260511.md` | PR #56 — SOP/User Guide（已 merge）|
| `outputs/replay/replay_fixture_mode_epic_closure_20260511.md` | PR #55 — epic closure（已 merge）|

---

*本備忘錄由 OFFLINE Classification Decision Memo Agent 產出，基於 main commit `7689189`。*  
*生效條件：CTO 明確接受（reply YES / ACCEPTED）。*  
*任何 code / registry 變更均需獨立 PR + YES gate。*
