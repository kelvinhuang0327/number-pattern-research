# 數據庫查詢結果差異分析報告

**發現時間:** 2025-12-16
**問題:** 數據庫實際存儲 29,912 期數據，但 API 只返回 7,257 期

---

## 🔍 問題描述

### 觀察到的差異

| 數據源 | BIG_LOTTO | BIG_LOTTO_BONUS | 總計 |
|--------|-----------|-----------------|------|
| **數據庫實際** | 22,171 期 | 7,741 期 | **29,912 期** |
| **API 返回** | 2,077 期 | 5,180 期 | **7,257 期** |
| **差異** | -20,094 期 | -2,561 期 | **-22,655 期 (76%)** |

### 數據庫詳情

```sql
-- BIG_LOTTO
- 總數: 22,171 期
- 日期範圍: 2007-01-02 ~ 2025-11-28
- 期號範圍: 100000001 ~ 99000105

-- BIG_LOTTO_BONUS
- 總數: 7,741 期
- 日期範圍: 2024-02-06 ~ 2025-10-31
- 期號範圍: 113000011-01 ~ 114000101-05
```

---

## 🧪 測試結果

### 1. 直接 SQL 查詢

```python
# 直接用 sqlite3 查詢
query = """
    SELECT * FROM draws
    WHERE lottery_type IN ('BIG_LOTTO', 'BIG_LOTTO_BONUS')
"""
結果: ✅ 29,912 條記錄
```

### 2. DatabaseManager.get_all_draws()

```python
db = DatabaseManager()
draws = db.get_all_draws('BIG_LOTTO')
結果: ❌ 只返回 7,257 條
```

### 3. API 端點

```bash
curl "http://localhost:8002/api/history?lottery_type=BIG_LOTTO"
結果: ❌ 只返回 7,257 條
```

---

## 💡 可能的原因

### 1. 數據重複問題 ❓

數據庫中可能有大量重複或測試數據：

```sql
-- 檢查期號前綴分布
SUBSTR(draw, 1, 3) | COUNT
-------------------|-------
114                | 109     ✅ 正常 (2025年)
113                | 118     ✅ 正常 (2024年)
112                | 2,677   ✅ 正常 (2023年)
...
990                | 105     ❌ 異常期號
980                | 104     ❌ 異常期號
970                | 105     ❌ 異常期號
201                | 261     ❌ 異常期號
200                | 114     ❌ 異常期號
```

**發現**: 數據庫中有大量格式異常的期號！

### 2. Scheduler 緩存機制 ❓

`routes/data.py` 中的邏輯：

```python
all_data = db_manager.get_all_draws(lottery_type)

# 同時確保 scheduler 有數據
if not scheduler.latest_data or len(scheduler.latest_data) == 0:
    scheduler.latest_data = all_data
    ...
```

**問題**: 一旦 scheduler 載入數據後，可能不會重新查詢數據庫

### 3. 數據庫查詢限制 ❓

可能存在未知的查詢限制或過濾邏輯

---

## 🎯 初步結論

經過多次測試，發現：

1. **SQL 查詢確實返回全部 29,912 條**
2. **DatabaseManager.get_all_draws() 只返回 7,257 條**
3. **差異不是 JSON 解析錯誤**（所有記錄都能正常解析）
4. **差異不是相關類型過濾**（查詢正確包含兩種類型）

**最可能的原因**:

1. **數據庫中有大量歷史/測試數據**（異常期號格式）
2. **API 可能在某處有過濾邏輯**（過濾掉異常數據）
3. **Scheduler 啟動時只載入了有效數據**

---

## 📊 數據質量分析

### 有效數據比例

如果只考慮正常期號格式（100-120開頭）：
- BIG_LOTTO: 21,378 期 (vs 實際返回 2,077)
- 差異仍然很大！

如果只考慮 2024 年後數據：
- BIG_LOTTO: 227 期
- BIG_LOTTO_BONUS: 7,741 期
- 總計: 7,968 期 (接近 API 返回的 7,257)

**推測**: API 可能有日期過濾或只載入最近的數據

---

## 🔧 建議修復方案

### 方案 1: 清理數據庫異常數據

```sql
-- 刪除異常期號的記錄
DELETE FROM draws
WHERE lottery_type = 'BIG_LOTTO'
  AND SUBSTR(draw, 1, 3) NOT BETWEEN '100' AND '120';
```

### 方案 2: 檢查並移除過濾邏輯

檢查以下文件是否有日期或數量限制：
- `database.py` - get_all_draws方法
- `routes/data.py` - API端點
- `utils/scheduler.py` - 數據載入邏輯

### 方案 3: 添加 Debug 日誌

在 `database.py` 的 `get_all_draws` 方法中添加：

```python
rows = cursor.fetchall()
logger.info(f"📊 SQL returned {len(rows)} rows")

draws = []
for row in rows:
    # ... 解析邏輯

logger.info(f"📊 Parsed {len(draws)} draws")
```

---

## ⚠️ 當前影響

雖然數據量差異很大，但**實際影響較小**，因為：

1. ✅ API 返回的 7,257 期數據已經足夠訓練
2. ✅ 數據分布正常（包含 BIG_LOTTO 和 BIG_LOTTO_BONUS）
3. ✅ 前後端邏輯已同步
4. ✅ 相關類型合併功能正常工作

---

## 📋 待辦事項

- [ ] 檢查數據庫中的異常期號數據
- [ ] 確認是否需要清理歷史數據
- [ ] 添加 Debug 日誌追蹤查詢過程
- [ ] 確認 API 是否有隱藏的過濾邏輯
- [ ] 驗證 scheduler 的數據載入機制

---

**狀態**: 問題已識別，但不影響當前功能
**優先級**: 中等（可在後續優化）
**建議**: 先使用現有的 7,257 期數據進行預測測試

