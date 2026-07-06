# Replay 頁面顯示語義規格（凍結版）

**文件 ID:** `replay_display_semantics_spec_20260515`
**日期:** 2026-05-15
**狀態:** ⚠️ AWAITING_CEO_DECISION（三條決策題尚待確認）
**授權來源:** CEO 直派凍結任務；依據 `wiki/system/replay_data_hygiene.md`、`wiki/system/controlled_edge_discovery.md`
**Scope:** 策略歷史回放頁面，涵蓋所有系統開發過的策略（不只 canonical 16）
**Constraint:** Read-only；不寫 DB；不動 code；不做新策略

---

## 一、CEO 前提確認（已決定，不可更改）

| 前提 | 說明 |
|------|------|
| **覆蓋範圍** | 所有系統開發過的策略（canonical 16 + extended rejected/、legacy artifacts），不只 canonical 16 |
| **顯示格式** | 每期 × 每策略 × 預測 vs 實際開獎，與「歷史預測清單」一致 |
| **不偽造 row** | 允許明示三種狀態：「事後重現 (Retrospective)」、「無資料 (No Data)」、「墓碑 (Tombstone)」 |
| **禁止** | 不寫 DB、不動 code、不動策略 |

---

## 二、Lifecycle Status × 顯示語義對照表

> 現況資料基礎：
> - ONLINE 6 策略：各 70–90 生產 replay rows（V1 live；run #1–#7 DONE）
> - REJECTED 4 策略（canonical stubs）＋ ~73 extended（rejected/ 目錄）
> - RETIRED 5 策略（canonical stubs；0 生產 rows）
> - OBSERVATION 1 策略（h6_gate_mk20_ew85；0 生產 rows）
> - OFFLINE 0 策略（目前無任何 OFFLINE registered strategy）

### 2.1 ONLINE

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `strategy_prediction_replays` table（DB）— V1 live replay rows，由 `strategy_replay_runs` DONE runs 產生 |
| **比對方式** | **live diff** — 以 `strategy_prediction_replays.predicted_numbers` 對比 `draws` table 實際開獎 |
| **UI 信任標籤** | `LIVE` |
| **顯示規則** | 每期逐行顯示預測 vs 開獎；hit count / miss 計算；`coverage_mode` 顯示（LIMITED / FULL）；FAILED_LEGACY run 的 error row 顯示 advisory，不隱藏 |
| **禁止** | 不得顯示「提高中獎率」、「推薦投注」等語言（依 `replay_data_hygiene.md §4`） |

---

### 2.2 OFFLINE

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `strategy_prediction_replays` table（DB）— 凍結的歷史 rows（下線前產生的 live replay rows） |
| **比對方式** | **live diff**（對已存 rows 執行）；新期數不再產生 |
| **UI 信任標籤** | `FROZEN` |
| **顯示規則** | 顯示下線前的全部歷史 rows；明示「此策略已暫停（OFFLINE），以下為下線前歷史回放」；不再更新；row level 不標 Retrospective |
| **空狀態（0 rows）** | 顯示 tombstone：「此策略已下線，無歷史回放資料」（`NO_DATA` 標籤） |
| **目前現況** | 0 個 OFFLINE 策略；此 spec 為預備定義 |

---

### 2.3 REJECTED

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | **組合**：(a) `strategy_prediction_replays` DB rows（若有，V2 retrospective artifact 已 apply）＋ (b) `outputs/replay/v2_artifact_only_candidate_rows_*.jsonl`（V2 artifact，artifact-only，不直接作為 UI source） |
| **比對方式** | **retrospective diff** — V2 rows 源自事後重現腳本；`history_cutoff_draw < target_draw` 完整性已驗證 |
| **UI 信任標籤** | `RETROSPECTIVE` |
| **顯示規則** | 每 row 強制標示「事後重現 Retrospective」badge；tooltip 說明「此預測為 governance 拒絕後事後重現，非上線期間實際預測」；策略卡片標示 REJECTED + 拒絕原因摘要 |
| **0 rows 的 REJECTED 策略**（extended catalog ~73 條） | 顯示 tombstone：「此策略已被拒絕（REJECTED），無回放資料」（`NO_DATA` 標籤）；拒絕原因摘要（如有 `rejected/*.json`） |
| **⚠️ 決策題 A（未決）** | REJECTED V2 artifact row 是否在 UI row level 強制標註「事後重現 Retrospective」？→ 見第三節 |

---

### 2.4 RETIRED

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | **tombstone metadata**（`replay_strategy_registry.py` lifecycle_stub）；目前 0 生產 replay rows；無 V2 artifact |
| **比對方式** | N/A（無 rows 可比對） |
| **UI 信任標籤** | `FROZEN`（若有歷史 rows）或 `NO_DATA`（0 rows） |
| **顯示規則（目前狀態）** | tombstone 顯示：策略名稱、退役說明（`provenance_note`）、lifecycle RETIRED badge；不顯示空的預測表格 |
| **⚠️ 決策題 B（未決）** | RETIRED 顯示退役前的最後 N 期預測軌跡？→ 見第三節 |

---

### 2.5 OBSERVATION

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `live_strategy_predictions` table（DB）— H6 live monitor 寫入的生產期預測；目前 `h6_gate_mk20_ew85` 有 live 記錄（POWER_LOTTO shadow eval） |
| **比對方式** | **live diff**（對 `live_strategy_predictions` rows 執行；使用 `draws` table 實際開獎） |
| **UI 信任標籤** | `LIVE`（有 live 記錄）或 `NO_DATA`（無記錄） |
| **顯示規則** | 策略卡片標示 OBSERVATION badge + 說明「此策略處於觀察期，預測僅供研究，不構成投注建議」；若有 `live_strategy_predictions` rows，逐期顯示；若無，見決策題 C |
| **⚠️ 決策題 C（未決）** | OBSERVATION 期間若無預測 row，顯示 "no data" 還是隱藏？→ 見第三節 |

---

## 三、CEO 決策題（三條）

### 決策題 A：REJECTED V2 artifact row 的 row-level 標註

**問題（≤100 字）：**
REJECTED 策略的 V2 retrospective artifact rows 是否在 UI **每一行**強制標示「事後重現 Retrospective」badge？還是僅在策略卡片層級標示一次即可？

**CTO 建議答案：** 強制 row-level 標註（每 row 都標 `RETROSPECTIVE`）。

**CTO 理由：**
V2 rows 是事後重現，不是上線期間的實際預測。若只在卡片層級標示，使用者在滾動瀏覽長表格時容易遺忘脈絡，誤將 retrospective 結果當成 live 記錄。row-level 標籤成本低（一個 badge），信任邊界收益高。

**風險：**
- 若不標：使用者可能誤讀 V2 rows 為「策略上線時的預測」→ 信任污染風險（HIGH）
- 若標：UI 較擁擠，表格行密度增加（LOW）

---

### 決策題 B：RETIRED 顯示退役前最後 N 期預測軌跡

**問題（≤100 字）：**
RETIRED 策略目前 0 生產 replay rows。若未來補填退役前軌跡，顯示：(a) 全部歷史、(b) 最後 30 期、(c) 只顯示 tombstone？

**CTO 建議答案：** 目前階段（c）只顯示 tombstone；未來擴展時優先 (b) 最後 30 期。

**CTO 理由：**
現在 0 rows，沒有資料可顯示。補填需要 V2 retrospective 流程，屬 P5 以後工作。tombstone 先行確保「不偽造 row」前提。最後 30 期軌跡是最有診斷價值的視窗，不需要全量歷史。顯示全部歷史耗費更多 render 資源，且對已退役策略的使用者價值邊際遞減。

**風險：**
- tombstone-only：使用者看不到退役前的預測表現（MEDIUM；可接受）
- 最後 30 期：需要 V2 retrospective 補填工作（工程成本 MEDIUM）
- 全部歷史：render 效能風險，且退役策略不值得投入（HIGH 成本，LOW 價值）

---

### 決策題 C：OBSERVATION 期間無預測 row 的 UI 處理

**問題（≤100 字）：**
OBSERVATION 策略若在某些期次沒有 `live_strategy_predictions` rows，UI 顯示 "no data" 空行，還是完全隱藏這些期次？

**CTO 建議答案：** 顯示 "no data" 空行（不隱藏）。

**CTO 理由：**
隱藏缺失期次會讓使用者誤以為策略每期都有預測，無法判斷覆蓋率缺口。顯示 "no data" 空行（搭配 `NO_DATA` 標籤）讓覆蓋率一目了然，符合 `replay_data_hygiene.md §3.1` 的透明原則。覆蓋率缺口本身就是 OBSERVATION 策略的重要資訊。

**風險：**
- 顯示空行：表格密度增加，使用者需理解 "no data" 含義（LOW）
- 隱藏：覆蓋率資訊遺失，可能掩蓋 H6 live monitor 的紀錄缺失（HIGH）

---

## 四、P1 盤點所需的預測資料來源清單

> 此清單供 P1（策略全集盤點）使用，指明需要盤點的資料來源。

### 4.1 DB Tables（`lottery_api/data/lottery_v2.db`）

| Table | 用途 | 覆蓋 Lifecycle |
|-------|------|----------------|
| `strategy_prediction_replays` | 主 Replay Store；V1 live rows + V2 retrospective applied rows | ONLINE、OFFLINE（凍結）、REJECTED（V2 applied） |
| `strategy_replay_runs` | Run lineage；status（DONE / FAILED / FAILED_LEGACY / CANCELLED）；coverage metadata | 所有（run provenance） |
| `live_strategy_predictions` | H6 live monitor 寫入的生產期預測 | OBSERVATION（h6_gate_mk20_ew85） |
| `draws` | 實際開獎結果（BIG_LOTTO / DAILY_539 / POWER_LOTTO） | 所有（比對基準） |

### 4.2 Artifact 路徑（`outputs/replay/`）

| 路徑 | 用途 | 狀態 |
|------|------|------|
| `outputs/replay/v2_artifact_only_candidate_rows_*.jsonl` | V2 retrospective candidate rows（REJECTED 4 canonical stubs；200 rows） | Artifact-only；非 UI source |
| `outputs/replay/p3_retrospective_candidate_rows_20260513.jsonl` | 早期 retrospective candidate（300 rows；已被 V2 取代） | 歸檔參考 |
| `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` | 策略全集快照（91 candidates；含 lifecycle 分類） | P1 輸入參考 |
| `outputs/replay/strategy_catalog_inventory_20260512.md` | Canonical 16 + extended rejected 盤點 | P1 輸入參考 |
| `outputs/replay/replay_coverage_report_20260507.json` | Coverage report（LIMITED；50-draw window） | Freshness 參考 |

### 4.3 策略定義檔案路徑

| 路徑 | 用途 | 覆蓋 Lifecycle |
|------|------|----------------|
| `lottery_api/models/replay_strategy_registry.py` | Canonical 16 adapter + lifecycle_stub 定義；LIFECYCLE_STATUSES SSOT | ONLINE、REJECTED、RETIRED、OBSERVATION |
| `rejected/*.json`（~73 檔） | Extended rejected 策略定義（governance 正式拒絕記錄） | REJECTED（extended） |
| `lottery_api/data/rejected/*.json`（4 檔：sgp_v3/v9/v10/v11） | API 層 rejected 策略 | REJECTED（extended） |
| `strategies/`、`provisional/` | 研究中 / 暫存策略（需 P1 分類後確認 lifecycle） | UNKNOWN（需 P1 確認） |

### 4.4 Log 檔位置

| 路徑 | 用途 |
|------|------|
| `logs/` | 系統 runtime logs（含 H6 live monitor 執行記錄） |
| `outputs/replay/p6_lite_apply_log_*.jsonl` | V2 controlled apply log（可追溯哪些 rows 被寫入） |

### 4.5 P1 盤點分母定義

> P1 必須解決的核心問題：「策略全集」的邊界是什麼？

| 分母候選 | 估計數量 | 說明 |
|----------|----------|------|
| Canonical registry（`replay_strategy_registry.py`） | 16 | 目前唯一 SSOT；ONLINE 6 + REJECTED 4 + RETIRED 5 + OBSERVATION 1 |
| Canonical + extended rejected/（去重） | ~85 | canonical 16 + extended ~73（扣除重複 ~4） |
| Canonical + rejected/ + strategies/ + provisional/ | TBD（P1 任務） | 需 P1 read-only 掃描確認 |
| 曾產生過 `live_strategy_predictions` rows 的策略 | TBD（P1 DB query） | H6 live monitor 寫入的實際運作策略 |

---

## 五、信任標籤定義（UI 實作參考）

| 標籤 | 中文 | 說明 | 視覺建議 |
|------|------|------|----------|
| `LIVE` | 即時回放 | 由 DONE run 在嚴格 causal slice 下產生的 V1 rows | 綠色 badge |
| `RETROSPECTIVE` | 事後重現 | V2 artifact rows；事後以 causal slice 重現；已通過 `history_cutoff_draw < target_draw` 驗證 | 黃色 badge；必須顯示 tooltip |
| `FROZEN` | 已凍結 | OFFLINE 策略的下線前歷史 rows；不再更新 | 灰色 badge |
| `NO_DATA` | 無資料 | 無任何 replay rows；顯示 tombstone 或空行 | 淺灰 badge |

---

## 六、不允許的 UI 語言（依 `replay_data_hygiene.md §4`）

以下語言在 Replay 頁面中一律禁用：

- `SIGNAL` / `NO_SIGNAL` / `NO_VALIDATED_EDGE`
- "best strategy" / "最佳策略"
- "提高中獎率"
- "推薦投注"
- 任何 promotion / edge ranking 用語

---

## 七、待 CEO 決定後的下一步

| 項目 | 前置條件 | 執行者 |
|------|----------|--------|
| code：row-level `RETROSPECTIVE` badge | 決策題 A 確認 | Frontend |
| code：RETIRED tombstone vs 最後 N 期 | 決策題 B 確認 | Replay backend + Frontend |
| code：OBSERVATION no-data row vs 隱藏 | 決策題 C 確認 | Frontend |
| P1：策略全集盤點 | 本文件 §4 清單 | P1 盤點 Agent（read-only） |
| P3：CEO 驗收 current main replay 頁 | P0 規格凍結（本文件） | CEO |

---

*本文件為 P0 規格凍結輸出。在三條決策題獲得 CEO 答案前，不得啟動對應 code 修改。*
