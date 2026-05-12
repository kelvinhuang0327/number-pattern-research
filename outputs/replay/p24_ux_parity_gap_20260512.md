# P24 UX Parity Gap List — Replay Page vs. History Section
**版本:** 20260512  
**任務:** Stage C — UX parity 差距分析  
**比較對象:**  
- A: `#replay-section`（replay 頁面，`index.html` ~line 1856+）
- B: `#history-section`（歷史記錄頁面，`index.html` ~line 1167+）

---

## 一、功能矩陣比較

| 功能 / Feature | History Section | Replay Section | Gap 類型 | 優先級 |
|---|---|---|---|---|
| 文字搜尋（期數/日期）| ✅ `#search-input` | ❌ 無 | Replay 缺失 | P2 |
| 排序切換（最新/最舊）| ✅ `#sort-select` | ❌ 無 | Replay 缺失 | P2 |
| 新增記錄按鈕 | ✅ `#add-record-btn` | ❌ N/A | 刻意不加 | — |
| 分頁 | ✅ `#pagination` | ✅ `#rp-prev-btn` / `#rp-next-btn` | Parity ✅ | — |
| Lottery type filter | ❌ 無 | ✅ `#rp-lottery-select` | Replay 額外功能（+） | — |
| Lifecycle filter | ❌ 無 | ✅ `#rp-lifecycle-select` | Replay 額外功能（+） | — |
| Strategy filter | ❌ 無 | ✅ `#rp-strategy-select` | Replay 額外功能（+） | — |
| Status filter | ❌ 無 | ✅ `#rp-status-select` | Replay 額外功能（+） | — |
| 日期範圍 filter | ❌ 無 | ✅ from/to date | Replay 額外功能（+） | — |
| Fixture Mode toggle | ❌ 無 | ✅ `#rp-fixture-toggle` | Replay 額外功能（+） | — |
| Freshness / Coverage 狀態 | ❌ 無 | ✅ freshness card | Replay 額外功能（+） | — |
| **Empty state 文字** | ✅ 自然呈現 | ⚠️ 部分覆蓋 | Replay 部分缺失 | P1 |
| **Catalog display mode（無資料 fallback）** | ❌ N/A | ❌ 目前缺失 | **Replay 缺失** | **P1** |
| **Mobile layout** | ⚠️ overflow scroll | ⚠️ overflow scroll | 雙方均未最佳化 | P3 |
| **資料匯出（CSV）** | ❌ 無 | ❌ 無 | 雙方均無 | P3 |
| **Column 排序（點擊 header）** | ❌ 無 | ❌ 無 | 雙方均無 | P3 |
| **Detail panel / 展開行** | ❌ 無 | ✅ 有 detail toggle | Replay 額外功能（+）| — |
| Summary cards（命中率摘要）| ❌ 無 | ✅ `#rp-summary-cards` | Replay 額外功能（+）| — |
| Lifecycle Registry card | ❌ 無 | ✅ `#rp-lifecycle-registry-card` | Replay 額外功能（+）| — |
| Disclaimer banner | ❌ 無 | ✅ 有 | Replay 額外功能（+）| — |

---

## 二、優先級 P1 Gap 明細

### Gap #1: Catalog Display Mode（零 DB rows 時的 fallback）

**問題**: 當 lifecycle ≠ ONLINE 且 API 返回 empty，UI 完全空白。  
**影響**: 使用者無法知道 REJECTED/RETIRED/OBSERVATION 策略存在哪些；系統透明度不足。  
**解法**: 見 `p24_display_only_catalog_spec_20260512.md`  
**行動碼**: `CATALOG_DISPLAY_MODE_REQUIRED`

---

### Gap #2: Empty State 文字不一致

**問題**: 
- 初始狀態顯示「請選擇條件後按查詢」 
- 查詢後返回 0 筆也是同樣空白（無明確「查無資料」提示）

**解法**:

```js
// 在 renderHistoryTable() 中，total === 0 但 lifecycle === 'ONLINE' 時：
tbody.innerHTML = `<tr>
  <td colspan="9" style="text-align:center;color:#888;padding:20px">
    查無符合條件的回放記錄
  </td>
</tr>`;
```

**行動碼**: `EMPTY_STATE_MESSAGE_FIX_REQUIRED`

---

## 三、優先級 P2 Gap 明細（建議但非阻塞）

### Gap #3: 缺乏文字搜尋

**問題**: History section 有 `#search-input` 可搜尋期數/日期；Replay page 只能用 date range。  
**影響**: 使用者無法快速搜尋特定期號的回放記錄。  
**行動碼**: `SEARCH_INPUT_BACKLOG`

---

### Gap #4: 缺乏排序控制

**問題**: History section 有 `#sort-select`（最新/最舊）；Replay 固定為最新優先。  
**行動碼**: `SORT_CONTROL_BACKLOG`

---

## 四、優先級 P3 Gap（可延後）

### Gap #5: Mobile layout 未最佳化

兩者均使用 `overflow-x:auto` 水平捲動表格。Replay 表格欄位更多（9 欄 + detail）。  
**行動碼**: `MOBILE_LAYOUT_FUTURE`

---

### Gap #6: 無 CSV 匯出

History section 和 Replay section 均無匯出功能。  
**行動碼**: `CSV_EXPORT_FUTURE`

---

## 五、Replay-Only 功能（不需要在 History 中實作）

以下為 Replay section 特有、**不需 parity**的功能：

| 功能 | 原因 |
|---|---|
| Fixture Mode toggle | 回放系統獨有 |
| Lifecycle filter | 回放系統獨有 |
| Strategy/Status filter | 回放系統獨有 |
| Freshness card | 回放系統獨有 |
| Summary cards | 回放系統獨有 |
| Disclaimer banner | 回放系統獨有（數據安全 §4 要求）|
| Lifecycle Registry card | 回放系統獨有 |

---

## 六、行動清單

| 行動碼 | 描述 | 優先級 | 負責 Spec |
|---|---|---|---|
| `CATALOG_DISPLAY_MODE_REQUIRED` | 實作 catalog display mode fallback | **P1** | `p24_display_only_catalog_spec_20260512.md` |
| `EMPTY_STATE_MESSAGE_FIX_REQUIRED` | 修正 empty state 文字 | **P1** | 本文件 §二 |
| `SEARCH_INPUT_BACKLOG` | 增加文字搜尋（期號/日期）| P2 | 待 backlog |
| `SORT_CONTROL_BACKLOG` | 增加排序控制 | P2 | 待 backlog |
| `MOBILE_LAYOUT_FUTURE` | Mobile table layout 最佳化 | P3 | 待 backlog |
| `CSV_EXPORT_FUTURE` | CSV 匯出功能 | P3 | 待 backlog |

---

## 七、Safety Invariants

| 項目 | 值 |
|---|---|
| production DB write | ❌ 無 |
| DB schema change | ❌ 無 |
| registry schema change | ❌ 無 |
| new betting recommendation | ❌ 禁止 |
