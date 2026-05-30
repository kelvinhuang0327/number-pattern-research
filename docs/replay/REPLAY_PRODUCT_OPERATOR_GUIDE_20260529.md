# LotteryNew 歷史回放功能 — Operator Guide

**版本**: P154 Release Candidate
**生成日期**: 2026-05-30
**適用範圍**: 歷史回放（Replay）功能操作與維護人員

---

## 1. 歷史回放功能目標

LotteryNew 歷史回放功能讓操作員可以查看每個已實作策略在歷史期數的預測結果，並與實際開獎號碼對照。

**核心功能**：
- 查看策略在指定期號的預測號碼 vs 實際開獎
- 查看命中數（hit_count）
- 查看策略完整 lifecycle 資訊
- 查看 multi-bet 策略的每一注紀錄（bet_index 1-5）
- 查看全策略目錄（含零回放列策略）
- 查看資料來源 provenance metadata

**非本功能範圍**（不包含）：
- 實時推薦下注（advisory only）
- Champion 評選（需獨立 live evidence 流程）
- 生成新預測（只讀歷史）

---

## 2. 全策略 Catalog 怎麼看

### 進入方式
1. 打開應用首頁
2. 點選導覽列「歷史回放」（Replay）分頁
3. 向下捲動至「📋 全策略目錄（含零回放列策略）」卡片

### 內容說明
- **策略 ID**: 系統內部 identifier
- **策略名稱**: 人類可讀名稱
- **彩種**: 支援的彩票類型（BIG_LOTTO / POWER_LOTTO / DAILY_539）
- **生命週期**: 策略目前狀態（見下方說明）
- **Rows**: 該策略在 DB 中的回放列數
- **無資料原因**: 若 Rows=0，解釋原因（見 §4）

### 生命週期狀態

| 狀態 | 顏色 | 意義 |
|------|------|------|
| ONLINE | 綠 | 目前運行中的策略 |
| OBSERVATION | 黃褐 | 觀察中，尚未正式上線 |
| RETIRED | 深灰 | 已退役，仍保留歷史資料 |
| REJECTED | 紅 | 經驗證後被拒絕，無回放資料 |
| DB_ONLY_MISSING_LIFECYCLE | 藍 | DB 有資料但 lifecycle 尚未正式登錄（待治理審核） |

**目前**: 40 個策略已在目錄中，覆蓋全部已實作策略。

---

## 3. bet_index / Bet N 怎麼看

部分策略每期會下多注（multi-bet）。`bet_index` 區分同一策略同一期號的不同注。

### 在歷史列表中
- 若 bet_index > 1，策略 ID 欄位會顯示橙色 **Bet N** 標籤（例如 `Bet 2`）
- bet_index = 1 的注不顯示標籤（為維持向後相容性）

### 在詳情展開中
- 點選「▶ 詳情」展開後，可看到「注次（bet_index）：Bet N」
- multi-bet 策略顯示 `multi-bet` 標籤
- 單注策略顯示「（單注）」

### 目前統計
- 總回放列數：94924
- multi-bet 列（bet_index > 1）：40622
- 最大 bet_index：5（即最多 5 注）

---

## 4. no_data_reason 怎麼看

在全策略目錄中，零回放列策略會顯示「無資料原因」badge：

| Badge | 顏色 | 意義 | 操作建議 |
|-------|------|------|---------|
| ⚠️ ONLINE_ZERO_REPLAY_ROWS | 橙/黃 | 策略已 ONLINE 但尚無回放資料 | 等待 controlled_apply 授權 |
| ✕ REJECTED_NO_REPLAY_DATA | 紅 | 策略經驗證後被拒絕，不產生回放 | 無需操作，歸檔記錄 |
| ℹ️ DB_ONLY_MISSING_LIFECYCLE | 藍 | DB 有資料但 lifecycle 待補 | 等待 lifecycle governance |
| 📋 ARTIFACT_ONLY | 灰 | 僅有 artifact 紀錄，無可執行 adapter | 無需操作 |
| — NO_REPLAY_DATA | 灰 | 策略存在但無回放資料 | 視需求決定是否 controlled_apply |
| ✓ 有資料 | 綠 | 有正常回放資料 | 正常查詢 |

---

## 5. truth_level 怎麼看

`truth_level` 描述回放資料的可信度與來源類型：

| Badge | 顏色 | 意義 |
|-------|------|------|
| LIVE | 綠 | Production replay 資料 |
| TIER-B | 綠 | Tier-B 策略 dry-run 通過後套用 |
| BIG LOTTO BACKFILL | 藍 | 大樂透 P14D 1500期回溯補建 |
| POWER BACKFILL | 綠 | 威力彩各波次回溯補建 |
| 539 BACKFILL | 綠 | 今彩539 回溯補建 |
| LEGACY UNVERIFIED | 橙 | 舊版 legacy 資料，未經 V3 驗證流程 |
| RETROSPECTIVE | 紫 | 回溯重建，原始預測已驗證 |
| ARTIFACT RETRO | 紫 | 從 artifact 重建，無可執行 adapter |
| FIXTURE | 藍 | 合成測試資料，不代表真實預測 |
| LEGACY ERROR | 黃 | 舊版錯誤，已保留作稽核用 |
| METADATA ONLY | 黃褐 | 僅 metadata，無 production 回放 |

**操作提示**：
- LEGACY UNVERIFIED 是受 P144D 治理的 baseline，不是錯誤
- 正常查詢應以 TIER-B / BACKFILL / LIVE 為主

---

## 6. source / controlled_apply_id / provenance_hash 怎麼看

在詳情展開面板（點選「▶ 詳情」）可看到：

### source（來源）
- 顯示資料的來源程序 ID
- 例：`P94_TIERB_CONTROLLED_APPLY`、`P37_WAVE2_PRODUCTION_APPLY`
- null → 顯示「— (legacy/unknown)」（320 筆 legacy 資料）

### Controlled Apply ID
- 顯示 controlled_apply 操作的具體 ID
- 例：`P94_TIERB_CONTROLLED_APPLY_20260526`
- null → 顯示「N/A（legacy/uncontrolled）」

### Provenance Hash
- 顯示前 8 字元的 hash（完整 hash 可查 API）
- 用於驗證資料完整性

### 在歷史列表中
- strategy_id 欄位下方會顯示 `source` 的縮短版（前 28 字元）

---

## 7. LEGACY_UNVERIFIED 與 DB_ONLY_MISSING_LIFECYCLE 的意義

### LEGACY_UNVERIFIED
- **定義**: 早期版本產生的資料，未經 V3 治理驗證流程
- **數量**: 100 筆
- **來源**: `source = P138B_LEGACY_REMARK`
- **處理**: 保留作歷史基準，以橙色 badge 標示，不視為錯誤
- **governed by**: P144D

### DB_ONLY_MISSING_LIFECYCLE
- **定義**: DB 中有回放資料，但 lifecycle 尚未正式登錄在 source-controlled registry
- **數量**: 22 個策略
- **顯示**: 藍色 `ℹ️ DB_ONLY_MISSING_LIFECYCLE` badge
- **狀態**: 待 lifecycle governance 審核（P156）
- **影響**: 不影響 replay display，資料正常可查

---

## 8. historical actual_numbers 與 LIVE_MONITORING_VERIFIED 的差異

| 概念 | 用途 | 來源 | 是否阻塞 replay |
|------|------|------|---------------|
| `actual_numbers`（DB 欄位）| 歷史回放顯示實際開獎 | DB 中的歷史資料 | **不阻塞** |
| `LIVE_MONITORING_VERIFIED` | Champion 評選的 live evidence | 觀察期實時收集 | **僅用於 champion** |

**關鍵說明**：
- 歷史回放功能使用 DB 中已儲存的 `actual_numbers`，**不需要** `LIVE_MONITORING_VERIFIED`
- Champion evaluation（P147）被 BLOCKED 是獨立的 governance 流程，**不影響**歷史回放功能的正常運作

---

## 9. 已知限制

| 限制 | 嚴重度 | 說明 |
|------|--------|------|
| h6_gate_mk20_ew85 無回放資料 | 低 | OBSERVATION 策略，尚未獲授權 controlled_apply |
| 22 DB_ONLY 策略 lifecycle 待正式登錄 | 低 | 不影響 replay，待 P156 治理 |
| provenance_source 欄位未在 UI 顯示 | 極低 | 可從 API 取得，UI 非必要 |
| bet_index == 1 的注不顯示 Bet N badge | 無 | Intentional backwards compatibility |
| Champion 評選需獨立 live evidence 流程 | N/A | 非 replay product 範疇 |

---

## 10. 操作驗收 Checklist

回放功能投入使用前，請確認以下項目：

- [ ] 開啟 replay 頁面，選擇 BIG_LOTTO，查詢近期回放，確認有記錄顯示
- [ ] 確認有 Bet N badge 顯示（multi-bet 策略，如 biglotto_ts3_markov_4bet_w30）
- [ ] 點選「▶ 詳情」，確認 bet_index、source、Controlled Apply ID 欄位可見
- [ ] 確認全策略目錄 (📋 全策略目錄) 顯示 40 個策略
- [ ] 確認 h6_gate_mk20_ew85 在目錄中，顯示 ⚠️ ONLINE_ZERO_REPLAY_ROWS badge
- [ ] 確認 REJECTED 策略在目錄中，顯示 ✕ REJECTED_NO_REPLAY_DATA badge
- [ ] 確認 DB_ONLY 策略在目錄中，顯示 ℹ️ DB_ONLY_MISSING_LIFECYCLE badge
- [ ] 確認 LEGACY UNVERIFIED rows 顯示橙色 badge（可選擇 lifecycle=ONLINE 查詢）
- [ ] 確認 drift guard PASS（`uv run python scripts/replay_lifecycle_drift_guard.py`）
- [ ] 確認 DB rows = 94924（`sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"`）

---

*本 Guide 由 P154 Replay Product Release Candidate Closure 自動生成。*
*如需更新，請執行相應 P-task 並重新生成。*
