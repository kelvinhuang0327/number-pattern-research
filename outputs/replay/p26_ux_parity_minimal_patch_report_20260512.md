# P26 UX Parity — Minimal Patch Report
**版本:** 20260512  
**任務:** Stage D — UX Parity Gap Assessment & Minimal Patch  
**參考:** `outputs/replay/p24_ux_parity_gap_20260512.md`  
**分支:** `feature/p25-replay-display-only-catalog-20260512`

---

## 一、P24 P1 Gap 狀態（合併前必須關閉）

| Gap 代碼 | 描述 | P24 狀態 | P25 狀態 |
|---|---|---|---|
| `CATALOG_DISPLAY_MODE_REQUIRED` | 非 ONLINE lifecycle 的 fallback catalog 顯示 | ❌ 缺失 | ✅ **已實作** |
| `EMPTY_STATE_MESSAGE_FIX_REQUIRED` | 空結果時顯示明確提示文字 | ❌ 不一致 | ✅ **已修正** |

### Gap 1 — CATALOG_DISPLAY_MODE_REQUIRED

**P25 實作位置：** `index.html`，`rpRenderCatalogDisplayMode()` 函式（~line 3020）

**行為：**
- 非 ONLINE lifecycle + 空 DB records → 呼叫 `rpRenderCatalogDisplayMode(lc, lt)`
- 有已登錄策略 → 顯示 catalog rows（`data-catalog-mode="true"`）+ 免責說明列
- 無已登錄策略（OFFLINE）→ 顯示 `coming soon` 訊息

**狀態：** ✅ CLOSED

---

### Gap 2 — EMPTY_STATE_MESSAGE_FIX_REQUIRED

**P25 實作位置：** `index.html`，`rpQuery()` empty state 分支（~line 3138）

**行為：**
- ONLINE + 0 records → `查無資料` 明確提示
- 非 ONLINE + 0 records → catalog display mode（更豐富的呈現）

**P24 建議的 fix：**
```js
tbody.innerHTML = `<tr>
  <td colspan="9" style="text-align:center;color:#888;padding:20px">
    查無符合條件的回放記錄
  </td>
</tr>`;
```

**P25 實際實作：**
- ONLINE empty → `查無資料`（簡短但明確）
- 非 ONLINE empty → catalog display mode（超越 P24 要求）

**評估：** 文字略有差異（`查無資料` vs `查無符合條件的回放記錄`），但功能等效且非 ONLINE case 已超越要求。不需要額外 patch。

**狀態：** ✅ CLOSED（functional parity achieved）

---

## 二、P2/P3 Backlog Gap 狀態

| Gap 代碼 | 描述 | 優先級 | P26 行動 |
|---|---|---|---|
| `SEARCH_INPUT_BACKLOG` | 文字搜尋（期號/日期）| P2 | 維持 backlog，不阻塞 merge |
| `SORT_CONTROL_BACKLOG` | 排序控制（最新/最舊）| P2 | 維持 backlog，不阻塞 merge |
| `MOBILE_LAYOUT_FUTURE` | Mobile table layout | P3 | 維持 backlog |
| `CSV_EXPORT_FUTURE` | CSV 匯出 | P3 | 維持 backlog |

---

## 三、Minimal Patch 決定

**結論：不需要 minimal patch。**

P25 已關閉所有 P1 gaps（`CATALOG_DISPLAY_MODE_REQUIRED` 和 `EMPTY_STATE_MESSAGE_FIX_REQUIRED`）。P2/P3 gaps 屬 backlog，不阻塞 merge。

任何新增修改將超出 P25/P26 scope，不符合「最小必要」原則。

---

## 四、UX Parity 摘要

| 項目 | 狀態 |
|---|---|
| P1 gaps 全部關閉 | ✅ YES |
| 無 regression 在 ONLINE display | ✅ YES |
| Catalog mode 正確隔離（data-catalog-mode）| ✅ YES |
| 不添加下注建議 | ✅ 已確認（免責說明存在）|
| Minimal patch 需要 | ❌ 不需要 |

**Gate 狀態：** `P26_UX_PARITY_MINIMAL_PATCH_COMPLETE` ✅

---

*Generated: P26 Stage D — 20260512*
