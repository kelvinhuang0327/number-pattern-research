# Prediction Tracker Data Flow Report
Generated: 2026-03-26

---

## 一、資料庫現狀

| 表格 | 記錄數 |
|------|--------|
| prediction_runs | 57 |
| prediction_items | 179 |
| prediction_results | 147 |

### 快照來源分布

| snapshot_source | 筆數 | strategy_name |
|----------------|------|--------------|
| RECONSTRUCTED | 46 | Coordinator-Direct (7/6 agents) — 舊格式 |
| RECONSTRUCTED | 1 | MULTI_STRATEGY — 新格式 |
| VALID | 11 | Coordinator-Direct (7/6 agents) — 舊格式 |

**關鍵發現**：目前所有 VALID 快照使用舊版 coordinator 格式（非 MULTI_STRATEGY），且均為 PENDING（待開獎）。這是因為這些 VALID 快照預測的是尚未開出的期數（115000075/115000038等），無法解析。

---

## 二、資料流程驗證

### 2.1 快照建立流程（POST /api/tracking/snapshot）

```
使用者點擊「產生預測快照」
  → POST /api/tracking/snapshot {lottery_type}
  → 系統判斷 snapshot_source:
      - target_draw (latest+1) 未在 DB → source = 'VALID'
      - target_draw 已在 DB → source = 'RECONSTRUCTED'
  → 載入 inline 策略函數（rsm_bootstrap）
  → 每個策略獨立呼叫 predict_fn(all_draws)
  → create_snapshot(strategy_bets=[...])
      → prediction_runs: id, lottery_type, latest_known_draw, strategy_name='MULTI_STRATEGY', snapshot_source
      → prediction_items: run_id, strategy_name, num_bets, numbers, status='PENDING'
  → 回傳 {run_id, snapshot_source, strategies[]}
```

✅ 流程正確。

### 2.2 解析流程（POST /api/tracking/resolve）

```
使用者點擊「比對待解析預測」
  → POST /api/tracking/resolve
  → 找所有 PENDING prediction_items
  → 對每個 item 找 actual draw (draw > latest_known_draw)
  → 計算 hit_count, matched_numbers
  → 插入 prediction_results（UNIQUE(item_id)，防重複）
  → 更新 prediction_items.status → 'RESOLVED'
```

✅ 流程正確。UNIQUE 約束防止重複解析。

### 2.3 歷史列表（GET /api/tracking/history）

```
GET /api/tracking/history?lottery_type={game}&limit=20&offset=0
  → 查 prediction_runs JOIN prediction_items JOIN prediction_results
  → 聚合每個 run：total_bets, resolved_bets, best_hit, status
  → 按 actual_date DESC 排序（無實際開獎日期的排最後）
```

✅ 正確。包含 RECONSTRUCTED 和 VALID 混合顯示。

### 2.4 績效統計（GET /api/tracking/performance）

```
GET /api/tracking/performance?valid_only=true（預設）
  → 只計入 snapshot_source='VALID' 的 runs
  → 按 (lottery_type, strategy_name) 分組
  → 計算 success_rate（best_hit >= 3 為成功）
  → 計算 baseline = 1 - (1-p1)^avg_bets
  → 計算 edge = success_rate - baseline
```

**目前狀態**：`valid_only=true` 返回 **0 筆**
- 原因：所有 VALID 快照目前都是 PENDING（預測的是未來期數，尚未開獎）
- `valid_only=false` 返回 1 筆（POWER_LOTTO，8個RECONSTRUCTED已解析）

**這是正常預期狀態**，不是 bug：
- 系統從今天起建立正式 VALID 快照
- 開獎後 resolve
- 累積足夠 VALID 解析結果後，績效統計才有意義

### 2.5 詳情展開（GET /api/tracking/run/{run_id}）

```
GET /api/tracking/run/{run_id}
  → 查 prediction_runs + prediction_items + prediction_results
  → 若 items 有 strategy_name → 分組為 bets_by_strategy
  → 載入 RSM strategy states 作為參考（rsm_strategies）
  → 回傳完整詳情
```

✅ 新格式（MULTI_STRATEGY）的 runs 會使用 `bets_by_strategy` 分組。
⚠️ 舊格式（Coordinator-Direct）的 runs，`bets_by_strategy = None`，前端以 fallback 模式顯示（rsmByN mapping）。

---

## 三、多注策略展開（逐注命中）

**前端展開邏輯**（PredictionTracker.js L428-484）：

```javascript
// 新格式（bets_by_strategy 不為 null）
const strategyGroups = detail.bets_by_strategy
    ? detail.bets_by_strategy   // 每個元素 = 一個策略
    : fallback to rsmByN mapping; // 舊格式

// 每個策略顯示：
// - 策略名稱（pt-block-title）
// - Edge 資訊
// - 每注預測號碼 + 命中高亮（pt-num-hit 綠色 / pt-num-plain 灰色）
// - 每注命中數
```

✅ 多注策略正確展開。命中號碼以綠色顯示（`pt-num-hit`），未中灰色（`pt-num-plain`）。

---

## 四、RECONSTRUCTED 處理

| 場景 | 行為 |
|------|------|
| 績效統計（valid_only=true） | ✅ RECONSTRUCTED 排除 |
| 績效統計（valid_only=false） | 包含（用於研究對照） |
| 歷史列表 | ✅ 顯示但有 source 標籤 |
| 排程重建按鈕 | 產生 source='RECONSTRUCTED' 快照 |
| 排程狀態卡 | ✅ 顯示 RECONSTRUCTED 標記 |

---

## 五、阻斷性問題（Blockers）

### BLOCKER-1：VALID 績效數據為空

**現象**：`valid_only=true` 性能統計返回 0 筆
**原因**：歷史快照全為舊版 coordinator 格式，新 MULTI_STRATEGY 格式快照為 RECONSTRUCTED

**非 bug，是歷史數據問題**：
- 舊版 VALID 快照預測的是未來期數（PENDING），目前未解析
- 新版 MULTI_STRATEGY 快照目前只有 RECONSTRUCTED 1筆

**解決路徑**（需使用者操作，非程式碼問題）：
1. 在每期開獎前，從追蹤頁點擊「產生預測快照」（建立 VALID MULTI_STRATEGY 快照）
2. 開獎後點擊「比對待解析預測」（解析 PENDING → RESOLVED）
3. 累積 10+ 期後，績效統計才有統計意義

### BLOCKER-2：舊 VALID 快照使用 coordinator 格式

**現象**：11 筆 VALID 快照 strategy_name = "Coordinator-Direct (7 agents)"，使用舊格式
**影響**：若這些快照解析後，績效統計只能按 "Coordinator-Direct" 策略分組，無法按 acb_1bet 等細分

**判斷**：這是歷史數據，根據「預測追蹤是歷史真實記錄，不能事後重算覆蓋」原則，不應修改。
接受此限制，從現在起的新 VALID 快照使用正確 MULTI_STRATEGY 格式。

---

## 六、頁面顯示現況說明

**使用者現在開啟追蹤頁會看到：**

1. **排程狀態**（3張卡）：
   - 今彩539：next=115000076，status=SNAPSHOT_CREATED
   - 大樂透：next=115000039，status=SNAPSHOT_CREATED
   - 威力彩：next=115000025，status=SNAPSHOT_CREATED

2. **績效統計**（valid_only=true，預設）：空表格（待未來 VALID 解析累積）

3. **歷史列表**：57筆，最新為 run#57（DAILY_539 115000076，MULTI_STRATEGY，RECONSTRUCTED，PENDING）

4. **展開詳情**（點擊 run#57）：顯示 4 個策略 × 各自注數（1+2+3+5=11注），含 strategy_name 分組
