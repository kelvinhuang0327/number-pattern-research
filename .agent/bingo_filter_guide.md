# 📋 賓果檔案過濾功能說明

## ✅ 功能已實現

系統現在會自動忽略包含「賓果」相關關鍵字的檔案，避免不必要的數據被匯入。

---

## 🔍 過濾規則

### 檢查的關鍵字（不區分大小寫）

檔名中包含以下任一關鍵字的檔案將被自動忽略：

- ✅ `賓果賓果`
- ✅ `賓果`
- ✅ `bingo bingo`
- ✅ `bingo`
- ✅ `bingobingo`

### 範例

**會被忽略的檔案**：
- ❌ `賓果賓果_2024.csv`
- ❌ `賓果開獎記錄.csv`
- ❌ `Bingo_Bingo_2024.csv`
- ❌ `BINGO.csv`
- ❌ `台灣彩券_賓果賓果.csv`
- ❌ `bingobingo_history.csv`

**不會被忽略的檔案**：
- ✅ `大樂透_2024.csv`
- ✅ `威力彩開獎記錄.csv`
- ✅ `今彩539_history.csv`
- ✅ `三星彩.csv`

---

## 🎯 使用方式

### 單檔案上傳

當您上傳包含「賓果」關鍵字的檔案時：

1. **系統行為**：
   - 🚫 檔案不會被處理
   - ⚠️ 顯示警告通知：「已忽略檔案: xxx.csv（包含「賓果」關鍵字）」
   - 📝 在控制台記錄：`🚫 忽略檔案: xxx.csv`

2. **用戶體驗**：
   - 不會看到錯誤訊息
   - 會收到友好的警告提示
   - 可以繼續上傳其他檔案

### 多檔案批次上傳

當您批次上傳多個檔案時：

1. **系統行為**：
   - 🔍 自動過濾所有賓果相關檔案
   - ⚠️ 顯示過濾結果通知
   - ✅ 只處理非賓果檔案

2. **通知訊息範例**：
   ```
   ⚠️ 已忽略 2 個賓果檔案
   賓果賓果_2024.csv
   Bingo_History.csv
   ```

3. **最終結果訊息**：
   ```
   批次載入完成！
   成功: 5/5 檔
   忽略: 2 檔（賓果）
   新增: 1250 筆
   ```

---

## 💻 技術實現

### 核心方法

```javascript
/**
 * 檢查檔名是否應該被忽略
 * @param {string} filename - 檔案名稱
 * @returns {boolean} - 是否應該忽略
 */
shouldIgnoreFile(filename) {
    const lowerFilename = filename.toLowerCase();
    const ignoreKeywords = [
        '賓果賓果',
        '賓果',
        'bingo bingo',
        'bingo',
        'bingobingo'
    ];
    
    return ignoreKeywords.some(keyword => lowerFilename.includes(keyword));
}
```

### 單檔案上傳檢查

```javascript
async handleFileUpload(file) {
    // 🚫 檢查檔名是否包含「賓果」相關關鍵字
    if (this.shouldIgnoreFile(file.name)) {
        this.uiManager.showNotification(
            `⚠️ 已忽略檔案: ${file.name}\n（包含「賓果」關鍵字）`,
            'warning'
        );
        console.log(`🚫 忽略檔案: ${file.name}`);
        return;  // 直接返回，不處理檔案
    }
    
    // 繼續正常的檔案處理流程...
}
```

### 多檔案上傳過濾

```javascript
async handleMultipleFileUpload(files) {
    // 🚫 過濾掉包含「賓果」的檔案
    const filteredFiles = [];
    const ignoredFiles = [];
    
    for (let i = 0; i < files.length; i++) {
        if (this.shouldIgnoreFile(files[i].name)) {
            ignoredFiles.push(files[i].name);
            console.log(`🚫 忽略檔案: ${files[i].name}`);
        } else {
            filteredFiles.push(files[i]);
        }
    }

    // 顯示過濾結果
    if (ignoredFiles.length > 0) {
        this.uiManager.showNotification(
            `⚠️ 已忽略 ${ignoredFiles.length} 個賓果檔案\n${ignoredFiles.join('\n')}`,
            'warning'
        );
    }

    // 如果所有檔案都被過濾，提示用戶
    if (filteredFiles.length === 0) {
        this.uiManager.showNotification('沒有可載入的檔案（所有檔案都被過濾）', 'warning');
        return;
    }

    // 只處理過濾後的檔案...
}
```

---

## 🧪 測試案例

### 測試 1: 單檔案上傳賓果檔案

**步驟**：
1. 上傳檔案：`賓果賓果_2024.csv`

**預期結果**：
- ⚠️ 顯示警告通知
- 📝 控制台顯示：`🚫 忽略檔案: 賓果賓果_2024.csv`
- ✅ 檔案不會被處理

### 測試 2: 單檔案上傳正常檔案

**步驟**：
1. 上傳檔案：`大樂透_2024.csv`

**預期結果**：
- ✅ 正常處理檔案
- 📊 顯示載入成功訊息
- 💾 數據儲存到系統

### 測試 3: 批次上傳混合檔案

**步驟**：
1. 選擇多個檔案：
   - `大樂透_2024.csv`
   - `賓果賓果_2024.csv`
   - `威力彩_2024.csv`
   - `Bingo_History.csv`
   - `今彩539_2024.csv`

**預期結果**：
- ⚠️ 顯示：「已忽略 2 個賓果檔案」
- ✅ 處理 3 個正常檔案
- 📊 最終訊息顯示：
  ```
  批次載入完成！
  成功: 3/3 檔
  忽略: 2 檔（賓果）
  新增: xxx 筆
  ```

### 測試 4: 批次上傳全部賓果檔案

**步驟**：
1. 選擇多個賓果檔案：
   - `賓果賓果_2024.csv`
   - `Bingo_History.csv`

**預期結果**：
- ⚠️ 顯示：「沒有可載入的檔案（所有檔案都被過濾）」
- 📝 控制台顯示所有被忽略的檔案

---

## 🔧 自訂過濾規則

如果需要添加或修改過濾關鍵字，可以編輯 `App.js` 中的 `shouldIgnoreFile` 方法：

```javascript
shouldIgnoreFile(filename) {
    const lowerFilename = filename.toLowerCase();
    const ignoreKeywords = [
        '賓果賓果',
        '賓果',
        'bingo bingo',
        'bingo',
        'bingobingo',
        // 👇 在這裡添加新的關鍵字
        // '其他關鍵字',
    ];
    
    return ignoreKeywords.some(keyword => lowerFilename.includes(keyword));
}
```

---

## 📊 統計資訊

過濾功能會在以下位置顯示統計：

1. **即時通知**：
   - 單檔案：顯示被忽略的檔案名稱
   - 多檔案：顯示被忽略的檔案數量和列表

2. **批次載入結果**：
   - 成功載入的檔案數
   - 被忽略的檔案數
   - 新增的數據筆數

3. **控制台日誌**：
   - 每個被忽略的檔案都會記錄
   - 方便開發者調試

---

## ❓ 常見問題

### Q1: 為什麼要過濾賓果檔案？

**A**: 賓果賓果的開獎規則和數據格式與其他彩券不同，混入系統會影響分析準確性。自動過濾可以避免誤操作。

### Q2: 如果我真的需要載入賓果數據怎麼辦？

**A**: 有兩種方式：
1. 重新命名檔案，移除「賓果」關鍵字
2. 修改 `shouldIgnoreFile` 方法，移除相關關鍵字

### Q3: 過濾是否區分大小寫？

**A**: 不區分。系統會將檔名轉為小寫後再比對，所以 `BINGO`、`Bingo`、`bingo` 都會被過濾。

### Q4: 過濾會影響已經載入的數據嗎？

**A**: 不會。過濾只在上傳時生效，不會影響已經儲存在系統中的數據。

### Q5: 如何知道哪些檔案被過濾了？

**A**: 系統會通過以下方式通知：
- 螢幕上的警告通知（顯示檔案名稱）
- 瀏覽器控制台的日誌記錄
- 批次上傳的統計訊息

---

## 🎉 總結

**功能特點**：
- ✅ 自動檢測賓果相關檔案
- ✅ 友好的用戶提示
- ✅ 支援中英文檔名
- ✅ 不區分大小寫
- ✅ 批次上傳智能過濾
- ✅ 詳細的統計資訊

**使用建議**：
- 📁 建議將賓果檔案放在單獨的資料夾
- 🏷️ 或使用明確的檔名標記
- 🔍 上傳前檢查檔案列表
- 📊 注意查看過濾統計訊息

現在您可以放心批次上傳檔案，系統會自動過濾掉賓果相關檔案！🎊
