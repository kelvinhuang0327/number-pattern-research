# P34 Screenshot Walkthrough — Display-Only Catalog
**Version:** P34 / 2026-05-13  
**Feature:** P25 Display-Only Catalog for Non-ONLINE Strategies  
**Main SHA:** `2e4c1e7`  
**Status:** 📋 SCREENSHOT PLACEHOLDER GUIDE — Actual screenshots pending

> ℹ️ **注意：** 本輪未執行實際瀏覽器截圖。本文件為 placeholder guide，定義每張截圖應包含的內容、Pass/Fail 判定標準，供後續 operator 實際操作時對照。

---

## Screenshot 目錄

```
outputs/replay/screenshots/p34/
  01_replay_online_production.png         ← PENDING
  02_replay_rejected_display_only.png     ← PENDING
  03_replay_retired_display_only.png      ← PENDING
  04_replay_observation_display_only.png  ← PENDING
  05_replay_offline_coming_soon.png       ← PENDING
  06_fixture_mode_on_banner.png           ← PENDING
  07_fixture_mode_off_clean.png           ← PENDING
```

---

## Screenshot 01 — ONLINE Production Mode

**檔名：** `01_replay_online_production.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. Lifecycle filter 選擇 **ONLINE**
2. 選擇彩券種類（任一）
3. 點擊查詢
4. 截圖整個 Replay 結果區

### 預期畫面內容
- [ ] Lifecycle filter 顯示「ONLINE」
- [ ] 頁面顯示 replay 資料列（表格有多行）
- [ ] 表格欄位包含：策略名稱、策略 ID、彩券種類、期數、日期
- [ ] 頁面底部或側欄顯示 disclaimer：「不保證任何回放結果」
- [ ] **無** fixture mode banner
- [ ] **無** catalog display-only 相關文字

### PASS 判定
- ✅ 出現 replay 資料列（非空表格）
- ✅ 無 fixture banner
- ✅ 無「無歷史回放資料」文字（此文字只在非 ONLINE 出現）

### FAIL 判定
- ❌ 頁面空白或顯示錯誤
- ❌ 出現 fixture banner（不應出現）
- ❌ 出現「無歷史回放資料」文字（不應出現在 ONLINE 模式）

---

## Screenshot 02 — REJECTED Display-Only

**檔名：** `02_replay_rejected_display_only.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. Lifecycle filter 選擇 **REJECTED**
2. 選擇彩券種類
3. 點擊查詢
4. 截圖整個 catalog 顯示區

### 預期畫面內容
- [ ] Lifecycle filter 顯示「REJECTED」
- [ ] 頁面顯示 catalog 表格（非 replay 資料列）
- [ ] 表格標題區含有：「無歷史回放資料」
- [ ] 表格行包含 🔴 badge 文字（「已拒絕 (REJECTED)」）
- [ ] 表格顯示策略名稱與策略 ID
- [ ] **無** production replay rows
- [ ] disclaimer 文字可見

### PASS 判定
- ✅ 出現 catalog 表格
- ✅ 🔴 badge 顯示
- ✅ 「無歷史回放資料」文字存在

### FAIL 判定
- ❌ 出現 production replay rows（嚴重 bug）
- ❌ 表格完全空白且無任何說明文字
- ❌ 錯誤訊息取代 catalog

---

## Screenshot 03 — RETIRED Display-Only

**檔名：** `03_replay_retired_display_only.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. Lifecycle filter 選擇 **RETIRED**
2. 選擇彩券種類
3. 點擊查詢
4. 截圖 catalog 顯示區

### 預期畫面內容
- [ ] Lifecycle filter 顯示「RETIRED」
- [ ] catalog 表格
- [ ] ⚪ badge 文字（「已退役 (RETIRED)」）
- [ ] 「無歷史回放資料」文字
- [ ] disclaimer

### PASS 判定
- ✅ catalog 表格 + ⚪ badge

### FAIL 判定
- ❌ production replay rows 出現
- ❌ badge 顯示錯誤 lifecycle（如顯示 REJECTED badge 但 filter 為 RETIRED）

---

## Screenshot 04 — OBSERVATION Display-Only

**檔名：** `04_replay_observation_display_only.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. Lifecycle filter 選擇 **OBSERVATION**
2. 選擇彩券種類
3. 點擊查詢
4. 截圖 catalog 顯示區

### 預期畫面內容
- [ ] Lifecycle filter 顯示「OBSERVATION」
- [ ] catalog 表格（僅 1 條策略，依 registry）
- [ ] 🟡 badge 文字（「觀察中 (OBSERVATION)」）
- [ ] 「無歷史回放資料」文字
- [ ] disclaimer

### PASS 判定
- ✅ catalog 表格 + 🟡 badge
- ✅ 策略數量為 1（依目前 registry）

### FAIL 判定
- ❌ production replay rows 出現
- ❌ 策略數量異常（超過 registry 登錄數）

> ⚠️ **重要提醒：** OBSERVATION 策略不代表推薦候選。🟡 badge 只代表「觀察中」狀態，截圖不得用於對外宣稱任何投注相關結論。

---

## Screenshot 05 — OFFLINE Coming Soon

**檔名：** `05_replay_offline_coming_soon.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. Lifecycle filter 選擇 **OFFLINE**
2. 點擊查詢
3. 截圖整個結果區

### 預期畫面內容
- [ ] Lifecycle filter 顯示「OFFLINE」
- [ ] 頁面顯示「OFFLINE 策略目前無已登錄項目（coming soon）」
- [ ] ⚫ 符號
- [ ] **無** catalog 表格（目前 0 entries）
- [ ] **無** replay 資料列

### PASS 判定
- ✅ coming soon 文字可見
- ✅ 無表格、無資料列

### FAIL 判定
- ❌ 出現任何資料列（不應有）
- ❌ 頁面空白且無任何說明文字

---

## Screenshot 06 — Fixture Mode ON（Banner 確認）

**檔名：** `06_fixture_mode_on_banner.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. 開啟 fixture mode（URL parameter 或 toggle）
2. 選擇任一 lifecycle
3. 截圖頁面頂端（確保 banner 可見）
4. 必須截取到 banner 與部分資料列

### 預期畫面內容
- [ ] 頁面頂端 **fixture mode banner** 清晰可見
- [ ] Banner 文字包含 synthetic / fixture / non-production / demo 等語意
- [ ] Banner 與一般內容區有明顯視覺區別（顏色/邊框）
- [ ] 資料列顯示合成數據格式

### PASS 判定
- ✅ Banner 存在且文字清楚標示 fixture/synthetic
- ✅ Banner 視覺顯眼，不易被忽略

### FAIL 判定
- ❌ 無 banner（嚴重 bug，必須立即回報）
- ❌ Banner 文字未表達 non-production 語意
- ❌ Banner 顏色與背景相同，肉眼難以辨識

> 🚨 **若截圖時發現 fixture mode 無 banner：** 立即停止操作，記錄截圖，回報 CTO 工程團隊。此為重大 UI 安全問題，可能導致 fixture 數據被誤認為 production truth。

---

## Screenshot 07 — Fixture Mode OFF（乾淨切回）

**檔名：** `07_fixture_mode_off_clean.png`  
**狀態：** 📋 PENDING

### 操作步驟
1. 關閉 fixture mode
2. 重新查詢（同一 lifecycle、同一彩券種類）
3. 截圖整個結果區

### 預期畫面內容
- [ ] **無** fixture mode banner
- [ ] 資料顯示回復 production 模式（或正確的 display-only catalog）
- [ ] 無合成數據殘留

### PASS 判定
- ✅ Banner 消失
- ✅ 資料顯示與 Screenshot 01/02/03/04/05（對應 lifecycle）一致

### FAIL 判定
- ❌ Banner 仍然顯示（fixture mode 未成功關閉）
- ❌ 資料與 fixture mode ON 時完全相同（未正確切換）

---

## Screenshots 執行 Checklist

```
[ ] 01 ONLINE production        — PENDING
[ ] 02 REJECTED display-only    — PENDING
[ ] 03 RETIRED display-only     — PENDING
[ ] 04 OBSERVATION display-only — PENDING
[ ] 05 OFFLINE coming soon      — PENDING
[ ] 06 Fixture mode ON banner   — PENDING
[ ] 07 Fixture mode OFF clean   — PENDING
```

**執行條件：**
- 需要可存取的前端瀏覽器環境
- 需要 backend 服務運作（或 fixture mode 運作的情況）
- 截圖工具（OS 截圖 / browser dev tools）

**建議執行時機：**
- Operator 首次正式驗收 P25 display-only catalog 時
- 每次 production 部署後的 smoke walkthrough
- CTO/CEO 展示前的 pre-demo check

---

## 文件版本控制

| 版本 | 日期 | 說明 |
|------|------|------|
| P34 / v1.0 | 2026-05-13 | 初版 placeholder guide，screenshots pending |
