# 檔案上傳過濾更新說明

## 📋 更新摘要

**更新日期**：2025-12-01
**更新內容**：優化檔案上傳過濾邏輯，僅允許上傳「大樂透」檔案

---

## 🎯 更新目標

根據用戶需求，檔案上傳功能現在**僅支援「大樂透」檔案**，並排除以下類型：
- ❌ 大樂透加開獎項
- ❌ 其他彩券類型（威力彩、今彩539、賓果賓果等）

---

## 🔧 修改內容

### 1. 更新過濾邏輯 ([src/core/App.js:77-112](src/core/App.js#L77-L112))

**修改前**：
```javascript
shouldIgnoreFile(filename) {
    const lowerFilename = filename.toLowerCase();
    const ignoreKeywords = [
        '賓果賓果', '賓果', 'bingo bingo', 'bingo', 'bingobingo'
    ];
    return ignoreKeywords.some(keyword => lowerFilename.includes(keyword));
}
```

**修改後**：
```javascript
shouldIgnoreFile(filename) {
    const lowerFilename = filename.toLowerCase();

    // ✅ 只允許「大樂透」的檔案（不包含「加開」）
    const allowKeywords = ['大樂透'];

    // ❌ 排除關鍵字：加開、其他彩券類型
    const rejectKeywords = [
        '加開', '賓果', 'bingo', '威力彩', '今彩', '539',
        '38樂合彩', '49樂合彩', '雙贏彩', '三星彩', '四星彩'
    ];

    const hasRejectKeyword = rejectKeywords.some(keyword =>
        lowerFilename.includes(keyword)
    );

    const hasAllowKeyword = allowKeywords.some(keyword =>
        lowerFilename.includes(keyword)
    );

    // 只有包含「大樂透」且不包含排除關鍵字的檔案才允許上傳
    return !hasAllowKeyword || hasRejectKeyword;
}
```

---

### 2. 更新提示訊息

#### 單檔上傳警告 ([src/core/App.js:355](src/core/App.js#L355))
```javascript
// 修改前
this.uiManager.showNotification(`⚠️ 已忽略檔案: ${file.name}`, 'warning');

// 修改後
this.uiManager.showNotification(`⚠️ 僅支援「大樂透」檔案上傳\n已忽略: ${file.name}`, 'warning');
```

#### 多檔上傳警告 ([src/core/App.js:464](src/core/App.js#L464))
```javascript
// 修改前
this.uiManager.showNotification(
    `⚠️ 已忽略 ${ignoredFiles.length} 個賓果檔案\n${ignoredFiles.join('\n')}`,
    'warning'
);

// 修改後
this.uiManager.showNotification(
    `⚠️ 僅支援「大樂透」檔案上傳\n已忽略 ${ignoredFiles.length} 個檔案:\n${ignoredFiles.slice(0, 5).join('\n')}${ignoredFiles.length > 5 ? '\n...' : ''}`,
    'warning'
);
```

---

### 3. 更新界面提示 ([index.html:101-102](index.html#L101-L102))

```html
<!-- 修改前 -->
<h3>上傳CSV檔案</h3>
<p>支援格式：台灣彩券官方CSV 或 期數,日期,號碼1~6,特別號</p>

<!-- 修改後 -->
<h3>上傳CSV檔案</h3>
<p>⚠️ 僅支援「大樂透」檔案（不含加開獎項）</p>
<p style="font-size: 0.85em; color: #94a3b8; margin-top: 5px;">
    支援格式：台灣彩券官方CSV 或 期數,日期,號碼1~6,特別號
</p>
```

---

## ✅ 測試驗證

### 測試腳本
創建了 [tools/test_file_filter.js](tools/test_file_filter.js) 用於驗證過濾邏輯

### 測試結果
```
╔══════════════════════════════════════════════════════════╗
║      檔案過濾邏輯測試 - 僅允許「大樂透」檔案           ║
╚══════════════════════════════════════════════════════════╝

測試案例：14 個
通過數量：14/14
成功率：100%
```

### 測試案例覆蓋

#### ✅ 允許的檔案
- `大樂透_2024.csv` - 標準大樂透檔案
- `大樂透開獎項_113.csv` - 大樂透開獎項
- `Lotto_大樂透_2023.csv` - 包含大樂透的檔案

#### ❌ 拒絕的檔案
- `大樂透加開獎項_2024.csv` - 大樂透加開（包含「加開」）
- `賓果賓果_2024.csv` - 賓果賓果
- `bingo_2024.csv` - Bingo
- `威力彩_2024.csv` - 威力彩
- `今彩539_2024.csv` - 今彩539
- `38樂合彩_2024.csv` - 38樂合彩
- `49樂合彩_2024.csv` - 49樂合彩
- `雙贏彩_2024.csv` - 雙贏彩
- `三星彩_2024.csv` - 三星彩
- `四星彩_2024.csv` - 四星彩
- `random_file.csv` - 無關檔案

---

## 📝 過濾邏輯說明

### 雙重檢查機制

1. **允許檢查**：檔案名稱必須包含「大樂透」
2. **排除檢查**：檔案名稱不能包含排除關鍵字

### 過濾流程

```
檔案 → 檢查是否包含「大樂透」
         ↓
      是 → 檢查是否包含排除關鍵字
              ↓
           是 → ❌ 拒絕
              ↓
          否 → ✅ 允許
         ↓
      否 → ❌ 拒絕
```

### 排除關鍵字列表

```javascript
const rejectKeywords = [
    '加開',      // 排除大樂透加開獎項
    '賓果',      // 排除賓果賓果
    'bingo',     // 排除 Bingo
    '威力彩',    // 排除威力彩
    '今彩',      // 排除今彩539
    '539',       // 排除今彩539
    '38樂合彩',  // 排除38樂合彩
    '49樂合彩',  // 排除49樂合彩
    '雙贏彩',    // 排除雙贏彩
    '三星彩',    // 排除三星彩
    '四星彩'     // 排除四星彩
];
```

---

## 🎯 用戶體驗改善

### 1. 明確的界面提示
- 上傳區域顯示：「⚠️ 僅支援『大樂透』檔案（不含加開獎項）」
- 用戶在上傳前就能清楚了解限制

### 2. 即時反饋
- 單檔上傳：顯示被拒絕的檔案名稱
- 多檔上傳：顯示被拒絕的檔案數量和前5個檔案名稱

### 3. 友善的錯誤訊息
```
⚠️ 僅支援「大樂透」檔案上傳
已忽略: 大樂透加開獎項_2024.csv
```

---

## 🔄 使用方式

### 開發環境測試

1. **啟動開發伺服器**：
   ```bash
   npm run dev
   ```

2. **打開瀏覽器**：
   - 訪問 http://localhost:8081

3. **測試上傳**：
   - 嘗試上傳「大樂透_2024.csv」→ ✅ 成功
   - 嘗試上傳「大樂透加開_2024.csv」→ ❌ 被拒絕
   - 嘗試上傳「威力彩_2024.csv」→ ❌ 被拒絕

### 運行過濾邏輯測試

```bash
node tools/test_file_filter.js
```

---

## 📊 影響範圍

### 修改的檔案
1. [src/core/App.js](src/core/App.js) - 主要邏輯
2. [index.html](index.html) - 界面提示

### 新增的檔案
1. [tools/test_file_filter.js](tools/test_file_filter.js) - 測試腳本
2. [FILE_UPLOAD_FILTER_UPDATE.md](FILE_UPLOAD_FILTER_UPDATE.md) - 本說明文檔

---

## ⚠️ 注意事項

### 檔案命名規範

為確保檔案能正確上傳，請確保：
1. ✅ 檔案名稱包含「大樂透」
2. ❌ 檔案名稱不包含「加開」或其他彩券類型關鍵字

### 範例

#### ✅ 正確的檔案名稱
- `大樂透_2024.csv`
- `大樂透開獎項_113年.csv`
- `Taiwan_Lotto_大樂透_2023-2024.csv`

#### ❌ 錯誤的檔案名稱
- `大樂透加開獎項_2024.csv` (包含「加開」)
- `威力彩_2024.csv` (不包含「大樂透」)
- `lotto_2024.csv` (不包含「大樂透」)

---

## 🔮 未來擴展

如需支援更多彩券類型，可修改 `allowKeywords` 和 `rejectKeywords`：

```javascript
// 範例：同時支援大樂透和威力彩
const allowKeywords = ['大樂透', '威力彩'];

// 範例：排除加開和賓果
const rejectKeywords = ['加開', '賓果', 'bingo'];
```

---

**更新完成時間**：2025-12-01
**測試狀態**：✅ 全部通過 (14/14)
**部署狀態**：✅ 已生效（重新整理頁面即可）
