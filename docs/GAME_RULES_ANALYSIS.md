# 彩券遊戲規則與系統實現分析

## 📋 遊戲規則對照表

### 1. **威力彩 (POWER_LOTTO)**

#### 官方規則
- 第1區：01~38 任選 6 個號碼
- 第2區：01~08 任選 1 個號碼
- 開獎：第1區開出6個號碼 + 第2區開出1個號碼

#### 系統實現狀況
✅ **後端配置** (`lottery_types.json`):
```json
"POWER_LOTTO": {
    "name": "威力彩",
    "minNumber": 1,
    "maxNumber": 38,
    "pickCount": 6,
    "hasSpecialNumber": true,
    "specialMinNumber": 1,
    "specialMaxNumber": 8
}
```

⚠️ **前端配置** (`LotteryTypes.js`):
- ID: `POWER_BALL` (應為 `POWER_LOTTO`)
- 其他配置正確

**問題**: 前後端ID不一致
**建議**: 統一使用 `POWER_LOTTO`

---

### 2. **大樂透 (BIG_LOTTO)**

#### 官方規則
- 從 01~49 任選 6 個號碼
- 開獎：隨機開出 6 個號碼 + 1 個特別號
- 中獎：對中 3 個以上號碼（特別號僅用於貳獎、肆獎、陸獎、柒獎）

#### 系統實現狀況
✅ **完全正確**
```json
"BIG_LOTTO": {
    "name": "大樂透",
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,
    "hasSpecialNumber": true,
    "specialMinNumber": 1,
    "specialMaxNumber": 49
}
```

---

### 3. **今彩539 (DAILY_539)**

#### 官方規則
- 從 01~39 任選 5 個號碼
- 開獎：隨機開出 5 個號碼
- 中獎：對中 2 個以上號碼

#### 系統實現狀況
✅ **後端配置正確**:
```json
"DAILY_539": {
    "name": "今彩539",
    "minNumber": 1,
    "maxNumber": 39,
    "pickCount": 5,
    "hasSpecialNumber": false
}
```

⚠️ **前端配置**:
- ID: `DAILY_CASH_539` (應為 `DAILY_539`)

**問題**: 前後端ID不一致
**建議**: 統一使用 `DAILY_539`

---

### 4. **39樂合彩 (39_LOTTO)**

#### 官方規則
- **依附今彩539開獎號碼**
- 玩法：二合(選2)、三合(選3)、四合(選4)
- 中獎：完全對中當日今彩539開出獎號

#### 系統實現狀況
⚠️ **配置不完整**:

後端:
```json
"39_LOTTO": {
    "name": "39樂合彩",
    "minNumber": 1,
    "maxNumber": 39,
    "pickCount": 5,  // ❌ 錯誤：應為2-4個變動
    "hasSpecialNumber": false,
    "note": "Uses DAILY_539 numbers"
}
```

前端:
```json
"LOTTO_39": {
    "pickCount": 5  // ❌ 錯誤：應為2-4個變動
}
```

**問題**:
1. `pickCount` 固定為5不正確（應根據玩法2/3/4變動）
2. 缺少依附關係標記
3. 缺少多玩法支持

**建議**:
```json
"39_LOTTO": {
    "name": "39樂合彩",
    "minNumber": 1,
    "maxNumber": 39,
    "pickCount": [2, 3, 4],  // 多玩法
    "hasSpecialNumber": false,
    "dependsOn": "DAILY_539",  // 依附今彩539
    "isSubGame": true,
    "playModes": {
        "二合": { "pickCount": 2, "matchRequired": 2 },
        "三合": { "pickCount": 3, "matchRequired": 3 },
        "四合": { "pickCount": 4, "matchRequired": 4 }
    }
}
```

---

### 5. **49樂合彩 (49_LOTTO)**

#### 官方規則
- **依附大樂透開獎號碼（不含特別號）**
- 玩法：二合(選2)、三合(選3)、四合(選4)
- 中獎：完全對中該期中獎號碼

#### 系統實現狀況
⚠️ **配置不完整**:
```json
"49_LOTTO": {
    "name": "49樂合彩",
    "minNumber": 1,
    "maxNumber": 49,
    "pickCount": 6,  // ❌ 錯誤：應為2-4個變動
    "hasSpecialNumber": false,
    "note": "Uses BIG_LOTTO numbers"
}
```

**問題**: 與39樂合彩相同
**建議**: 與39樂合彩類似的多玩法配置

---

### 6. **38樂合彩 (38_LOTTO)**

#### 官方規則
- **依附威力彩開獎號碼**（推測）
- 玩法：二合(選2)、三合(選3)、四合(選4)

#### 系統實現狀況
⚠️ **配置不完整**:
```json
"38_LOTTO": {
    "name": "38樂合彩",
    "minNumber": 1,
    "maxNumber": 38,
    "pickCount": 6,  // ❌ 錯誤：應為2-4個變動
    "hasSpecialNumber": false,
    "note": "Uses POWER_LOTTO numbers"
}
```

**問題**: 與39樂合彩相同

---

### 7. **3星彩 (3_STAR)**

#### 官方規則
- 從 000~999 選出一組三位數
- 號碼可重複
- 開獎：開出一組三位數號碼
- 順序有意義（排列組合）

#### 系統實現狀況
✅ **配置正確**:
```json
"3_STAR": {
    "name": "3星彩",
    "minNumber": 0,
    "maxNumber": 9,
    "pickCount": 3,
    "hasSpecialNumber": false,
    "repeatsAllowed": true,
    "isPermutation": true
}
```

⚠️ **前端ID不一致**: `STAR_3` vs `3_STAR`

---

### 8. **4星彩 (4_STAR)**

#### 官方規則
- 從 0000~9999 選出一組四位數
- 號碼可重複
- 開獎：開出一組四位數號碼
- 順序有意義（排列組合）

#### 系統實現狀況
✅ **配置正確**:
```json
"4_STAR": {
    "name": "4星彩",
    "minNumber": 0,
    "maxNumber": 9,
    "pickCount": 4,
    "hasSpecialNumber": false,
    "repeatsAllowed": true,
    "isPermutation": true
}
```

⚠️ **前端ID不一致**: `STAR_4` vs `4_STAR`

---

### 9. **雙贏彩 (DOUBLE_WIN)**

#### 系統實現狀況
✅ **配置存在**:
```json
"DOUBLE_WIN": {
    "name": "雙贏彩",
    "minNumber": 1,
    "maxNumber": 24,
    "pickCount": 12,
    "hasSpecialNumber": false
}
```

❓ **缺少官方規則說明**

---

## 🔍 問題總結

### 嚴重問題 ❌

1. **前後端ID不一致**
   - `POWER_BALL` ↔ `POWER_LOTTO`
   - `DAILY_CASH_539` ↔ `DAILY_539`
   - `STAR_3` ↔ `3_STAR`
   - `STAR_4` ↔ `4_STAR`
   - `LOTTO_39` ↔ `39_LOTTO`
   - `LOTTO_49` ↔ `49_LOTTO`
   - `LOTTO_38` ↔ `38_LOTTO`

2. **樂合彩系列配置錯誤**
   - `pickCount` 應為動態（2/3/4），而非固定值
   - 缺少多玩法支持
   - 缺少依附關係標記

### 中等問題 ⚠️

3. **缺少遊戲邏輯實現**
   - 樂合彩的多玩法選號邏輯
   - 星彩的排列組合邏輯
   - 依附遊戲的數據同步邏輯

4. **數據上傳支持不完整**
   - 只有今彩539有TXT格式支持
   - 其他遊戲缺少專用上傳工具

### 輕微問題 ℹ️

5. **缺少中獎規則實現**
   - 各遊戲的中獎條件檢查
   - 特別號在不同獎項的應用邏輯

---

## ✅ 建議修正順序

### Phase 1: 統一命名（緊急）
1. 統一前後端彩券類型ID
2. 更新所有引用處

### Phase 2: 完善配置（重要）
1. 修正樂合彩系列配置
2. 添加多玩法支持
3. 標記遊戲依附關係

### Phase 3: 實現邏輯（中期）
1. 實現樂合彩多玩法選號
2. 實現依附遊戲數據同步
3. 實現星彩排列組合

### Phase 4: 完整測試（長期）
1. 各遊戲類型上傳測試
2. 預測引擎支持測試
3. 中獎規則驗證測試

---

## 🎯 當前系統支持狀況

| 遊戲 | 配置 | 上傳 | 預測 | 中獎檢查 |
|------|------|------|------|----------|
| 大樂透 | ✅ | ✅ | ✅ | ⚠️ |
| 威力彩 | ✅ | ✅ | ✅ | ⚠️ |
| 今彩539 | ✅ | ✅ | ✅ | ⚠️ |
| 39樂合彩 | ⚠️ | ❌ | ❌ | ❌ |
| 49樂合彩 | ⚠️ | ❌ | ❌ | ❌ |
| 38樂合彩 | ⚠️ | ❌ | ❌ | ❌ |
| 3星彩 | ✅ | ❌ | ⚠️ | ❌ |
| 4星彩 | ✅ | ❌ | ⚠️ | ❌ |
| 雙贏彩 | ✅ | ❌ | ⚠️ | ❌ |

圖例：
- ✅ 完整支持
- ⚠️ 部分支持
- ❌ 不支持
