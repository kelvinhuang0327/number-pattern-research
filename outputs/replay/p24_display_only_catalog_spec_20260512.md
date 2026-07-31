# P24 Replay Page Display-Only Catalog Spec
**版本:** 20260512  
**任務:** Stage B — Replay Page 顯示完整性 Spec + 實作規格  
**前置文件:** `outputs/replay/strategy_catalog_inventory_20260512.md`  
**知識來源:** wiki/system/replay_data_hygiene.md §4  

---

## 一、問題陳述

### 當前行為（as-is）

當使用者在 Replay 頁面的 `rp-lifecycle-select` 篩選選擇 **REJECTED / RETIRED / OBSERVATION / OFFLINE** 時：

1. 前端呼叫 `GET /api/replay/history?lifecycle_status=REJECTED&...`
2. API 從 `strategy_prediction_replays` 查詢
3. 因為這些策略無 production replay rows → 返回 `{"total": 0, "records": []}`
4. 前端 `#rp-hist-body` 顯示空白或「請選擇條件後按查詢」

**根本原因**: 非 ONLINE 策略在 production DB 無 replay rows，但這些策略仍是 catalog 的一部分，應在 UI 上可見。

---

## 二、目標行為（to-be）

當 `/api/replay/history` 返回 empty 但 lifecycle 篩選有明確值時，前端**必須**從 strategy catalog 補充「顯示用佔位行」（display-only placeholder rows）。

**Rule**: 只要 `rp-lifecycle-select ≠ ""（全部）` AND API 返回 `total === 0` → 觸發 catalog display mode。

---

## 三、API 支援（已有）

### `GET /api/replay/strategies`

此 endpoint 已存在於 `lottery_api/routes/replay.py`。  
呼叫格式（由前端使用）：

```
GET /api/replay/strategies?lifecycle_status=REJECTED
GET /api/replay/strategies?lifecycle_status=REJECTED&lottery_type=BIG_LOTTO
```

**期待回傳格式**（需確認 route schema，若不符需更新）：

```json
{
  "strategies": [
    {
      "strategy_id": "biglotto_ts3_acb_4bet",
      "strategy_name": "大樂透 TS3+ACB 4注",
      "lifecycle_status": "REJECTED",
      "supported_lottery_types": ["BIG_LOTTO"],
      "description": "..."
    }
  ]
}
```

---

## 四、前端顯示規格

### 4.1 觸發條件

```js
const lifecycleFilter = document.getElementById('rp-lifecycle-select').value;
// 觸發 catalog display mode when:
// 1. lifecycleFilter !== '' AND lifecycleFilter !== 'ONLINE'
// 2. AND API /history 返回 total === 0
```

### 4.2 Catalog Placeholder 行格式

| 欄位 | Catalog Mode 顯示內容 |
|---|---|
| 期號 | — |
| 日期 | — |
| 策略 | `{strategy_name}` |
| 預測號碼 | — |
| 實際開獎 | — |
| 命中號碼 | — |
| 命中數 | — |
| 狀態 | lifecycle badge（見 §4.3） |
| detail | —（無展開） |

### 4.3 Lifecycle Badge 規格

| lifecycle | badge HTML | badge style |
|---|---|---|
| REJECTED | `🔴 已拒絕 (REJECTED)` | color:#c0392b, bg: rgba(192,57,43,.1) |
| RETIRED | `⚪ 已退役 (RETIRED)` | color:#7f8c8d, bg: rgba(127,140,141,.1) |
| OBSERVATION | `🟡 觀察中 (OBSERVATION)` | color:#d4a20c, bg: rgba(212,162,12,.1) |
| OFFLINE | `⚫ 下線 (OFFLINE)` | color:#2c3e50, bg: rgba(44,62,80,.1) |

### 4.4 空狀態訊息（列表下方）

```html
<tr>
  <td colspan="9" style="text-align:center;color:#888;padding:16px;font-style:italic">
    此生命週期 (REJECTED) 策略目前無歷史回放資料，以下為完整策略目錄。
  </td>
</tr>
```

> **安全規則（replay_data_hygiene.md §4）**: 任何 placeholder 行**不得包含**：
> - 「建議購買」或任何下注推薦語句
> - 預期命中率聲明
> - 任何可被解讀為「此策略有效」的表述

---

## 五、實作規格（JavaScript）

### 5.1 修改點：`index.html` replay section JS

修改 `rp-query-btn` click 事件 handler（或 `loadReplayHistory()` 函數）：

```js
async function loadReplayHistory(params) {
  const lifecycleFilter = document.getElementById('rp-lifecycle-select').value;
  const lotteryFilter = document.getElementById('rp-lottery-select').value;

  const response = await fetch(`/api/replay/history?${queryString}`);
  const data = await response.json();

  if (data.total === 0 && lifecycleFilter && lifecycleFilter !== 'ONLINE') {
    // Catalog display mode
    await renderCatalogDisplayMode(lifecycleFilter, lotteryFilter);
  } else {
    renderHistoryTable(data.records);
  }
}

async function renderCatalogDisplayMode(lifecycle, lotteryType) {
  const url = `/api/replay/strategies?lifecycle_status=${lifecycle}` + 
              (lotteryType ? `&lottery_type=${lotteryType}` : '');
  const res = await fetch(url);
  const data = await res.json();
  const strategies = data.strategies || [];

  const tbody = document.getElementById('rp-hist-body');
  const totalLabel = document.getElementById('rp-total-label');

  if (strategies.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#888">
      此篩選條件下無已登錄策略</td></tr>`;
    return;
  }

  // Render info row
  const infoRow = `<tr>
    <td colspan="9" style="text-align:center;color:#888;padding:16px;font-style:italic">
      此生命週期 (${lifecycle}) 策略目前無歷史回放資料，以下為完整策略目錄。
    </td>
  </tr>`;

  const strategyRows = strategies.map(s => `
    <tr data-catalog-mode="true">
      <td>—</td>
      <td>—</td>
      <td>${escapeHtml(s.strategy_name)}</td>
      <td>—</td>
      <td>—</td>
      <td>—</td>
      <td>—</td>
      <td>${renderLifecycleBadge(s.lifecycle_status)}</td>
      <td>—</td>
    </tr>
  `).join('');

  tbody.innerHTML = infoRow + strategyRows;
  totalLabel.textContent = `目錄模式：顯示 ${strategies.length} 個已登錄策略`;
}

function renderLifecycleBadge(lifecycle) {
  const map = {
    REJECTED: { icon: '🔴', label: '已拒絕', color: '#c0392b', bg: 'rgba(192,57,43,.1)' },
    RETIRED:  { icon: '⚪', label: '已退役', color: '#7f8c8d', bg: 'rgba(127,140,141,.1)' },
    OBSERVATION: { icon: '🟡', label: '觀察中', color: '#d4a20c', bg: 'rgba(212,162,12,.1)' },
    OFFLINE: { icon: '⚫', label: '下線', color: '#2c3e50', bg: 'rgba(44,62,80,.1)' },
  };
  const b = map[lifecycle] || { icon: '⬜', label: lifecycle, color: '#666', bg: 'rgba(0,0,0,.05)' };
  return `<span style="padding:2px 8px;border-radius:4px;background:${b.bg};color:${b.color};font-size:11px;font-weight:700">
    ${b.icon} ${b.label} (${lifecycle})
  </span>`;
}
```

### 5.2 修改點：`lottery_api/routes/replay.py`

確認 `GET /api/replay/strategies` 已支援 `lifecycle_status` 和 `lottery_type` query params。  
若不支援，需新增：

```python
@router.get("/api/replay/strategies")
async def list_replay_strategies(
    lifecycle_status: Optional[str] = None,
    lottery_type: Optional[str] = None,
):
    strategies = list_strategies(
        lifecycle_filter=lifecycle_status,
        lottery_type_filter=lottery_type,
    )
    return {"strategies": [s.to_dict() for s in strategies]}
```

---

## 六、OFFLINE 特殊處理

OFFLINE lifecycle 是預留狀態（目前 0 個策略）。  
當 `rp-lifecycle-select = "OFFLINE"` 且 catalog 返回空：

```html
<tr>
  <td colspan="9" style="text-align:center;color:#888;padding:20px">
    ⚫ OFFLINE 策略目前無已登錄項目（coming soon）
  </td>
</tr>
```

---

## 七、Fixture Mode 互動

- Catalog display mode 與 fixture mode **獨立**，不互相影響
- 若 fixture mode ON + lifecycle = REJECTED → 優先顯示 fixture rows（若有）
- 若 fixture mode ON + lifecycle = REJECTED + fixture 無 rows → 回退到 catalog display mode
- Fixture mode banner 在 catalog mode 下仍按規則顯示（若 fixture mode 是 ON）

---

## 八、Safety Invariants

| 項目 | 值 |
|---|---|
| production DB write | ❌ 無 |
| DB schema change | ❌ 無 |
| registry schema change | ❌ 無 |
| new betting recommendation | ❌ 禁止 |
| new DB backfill | ❌ 無（display-only）|
| new fixture rows creation | ❌ 無 |
| OFFLINE capability | ❌ 僅顯示 placeholder |
