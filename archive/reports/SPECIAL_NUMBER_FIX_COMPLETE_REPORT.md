# 特別號邏輯修正完成報告

## 問題背景

原系統在預測階段就會生成特別號，這與大樂透的實際規則不符：

### ❌ 錯誤理解
- 玩家選擇 6 個主號碼 + 1 個特別號
- 預測系統需要預測 7 個號碼

### ✅ 正確理解
- **玩家只選擇 6 個主號碼**（不選特別號）
- **開獎時從49個號碼開6個主號碼，再從剩餘43個號碼開1個特別號**
- **特別號用於判定二獎、四獎、六獎、八獎、普獎**

## 大樂透正確規則

### 開獎方式
1. 從 1-49 號碼中開出 6 個主號碼
2. 從剩餘 43 個號碼中開出 1 個特別號

### 中獎規則
| 獎項 | 條件 |
|------|------|
| 頭獎（特獎） | 6 個主號碼全中 |
| 二獎 | 5 個主號碼 + 特別號 |
| 三獎 | 5 個主號碼 |
| 四獎 | 4 個主號碼 + 特別號 |
| 五獎 | 4 個主號碼 |
| 六獎 | 3 個主號碼 + 特別號 |
| 七獎 | 3 個主號碼 |
| 八獎 | 2 個主號碼 + 特別號 |
| 普獎 | 只中特別號 |

## 修正內容

### 1. 移除預測階段的特別號生成 ✅

**修改的檔案：**
- `lottery-api/routes/prediction.py` - 移除 `predict_from_backend_eval` 端點的特別號調用
- `lottery-api/models/xgboost_model.py` - 移除特別號預測
- `lottery-api/models/autogluon_model.py` - 移除特別號預測
- `lottery-api/models/lstm_model.py` - 移除兩處特別號預測（PyTorch 版和 Fallback 版）
- `lottery-api/models/prophet_model.py` - 移除特別號預測
- `lottery-api/models/bayesian_ensemble.py` - 移除雙注的特別號預測
- `lottery-api/models/transformer_model.py` - 移除特別號預測
- `lottery-api/models/meta_learning.py` - 移除特別號預測

**修改結果：**
```json
{
  "numbers": [1, 5, 16, 25, 39, 41],  // ✅ 只有6個號碼
  "confidence": 0.95,
  "method": "ensemble"
  // ❌ 沒有 "special" 欄位
}
```

### 2. 更新8注預測腳本 ✅

**修改檔案：** `lottery-api/tools/predict_8_bets_lotto.py`

**變更：**
- 驗證函數只檢查 6 個主號碼
- 移除特別號的顯示欄位
- 更新熱門號碼分析（只分析主號碼）
- 添加警告訊息：「特別號將在開獎時單獨抽取」

**輸出範例：**
```
🏆 8 Recommended Bets for 大樂透 (6 Main Numbers Only)
======================================================================
#   | Model                | Confidence | Numbers
----------------------------------------------------------------------
1   | ensemble             | 95.00%    | 01, 05, 16, 25, 39, 41
2   | backend_optimized    | 85.00%    | 02, 07, 15, 20, 39, 43
...
🔥 Hot Main Numbers (Most Frequent):
   39 (x6), 25 (x4), 02 (x4), 07 (x4), 15 (x4)

✅ Validation Summary:
   - ⚠️ Special number will be drawn separately during lottery
```

### 3. 創建正確的回測邏輯 ✅

**新檔案：** `lottery-api/tools/backtest_biglotto.py`

**功能：**
1. 用 6 個預測號碼去比對歷史的 7 個開獎號碼（6主+1特別）
2. 正確判定中獎等級（頭獎到普獎）
3. 計算主號碼命中數和特別號是否命中
4. 統計每個模型的最佳獎項、中獎次數、平均命中

**回測結果範例：**
```
📌 TRANSFORMER
   預測號碼: 04, 20, 32, 33, 43, 48
   最佳獎項: 6 | 總中獎: 1/10 | 平均命中: 0.6
   中獎記錄:
      • 第96000005期: 六獎 (主號碼3個 ✅)  ← 3個主號碼+特別號

📌 XGBOOST
   預測號碼: 03, 25, 26, 36, 39, 44
   最佳獎項: 7 | 總中獎: 1/10 | 平均命中: 1.3
   中獎記錄:
      • 第96000003期: 七獎 (主號碼3個 )  ← 只中3個主號碼
```

## 測試驗證

### 預測測試 ✅
```bash
python3 lottery-api/tools/predict_8_bets_lotto.py
```
**結果：** 所有模型都只返回 6 個主號碼，無特別號欄位

### 回測測試 ✅
```bash
python3 lottery-api/tools/backtest_biglotto.py
```
**結果：** 正確判定中獎等級，特別號邏輯正確（transformer 中了六獎 = 3主號碼+特別號）

## API 端點狀態

### 預測端點
- ✅ `/api/predict-from-backend-eval` - 只返回 6 個主號碼
- ✅ `/api/predict-from-backend` - 只返回 6 個主號碼
- ✅ `/api/predict` - 只返回 6 個主號碼

### 回測端點
- ✅ `/api/history?lottery_type=BIG_LOTTO` - 返回完整歷史（含特別號）

## 相容性說明

### 數據庫
- ✅ 數據庫中仍保留歷史開獎的特別號（用於回測和顯示）
- ✅ 只是預測時不生成特別號

### 前端
- ⚠️ 前端可能需要更新，顯示時說明：
  - 「玩家只需選擇6個主號碼」
  - 「特別號將在開獎時單獨抽取」
  - 「特別號用於判定二獎、四獎、六獎、八獎、普獎」

## 檔案清單

### 修改的檔案
1. `lottery-api/routes/prediction.py`
2. `lottery-api/models/xgboost_model.py`
3. `lottery-api/models/autogluon_model.py`
4. `lottery-api/models/lstm_model.py`
5. `lottery-api/models/prophet_model.py`
6. `lottery-api/models/bayesian_ensemble.py`
7. `lottery-api/models/transformer_model.py`
8. `lottery-api/models/meta_learning.py`
9. `lottery-api/tools/predict_8_bets_lotto.py`

### 新增的檔案
1. `lottery-api/tools/backtest_biglotto.py` - 正確的大樂透回測工具

## 總結

✅ **問題已完全修正**
- 預測階段只預測 6 個主號碼
- 回測邏輯正確比對 6 個預測號碼與 7 個開獎號碼
- 中獎判定符合大樂透實際規則
- 所有模型測試通過

⚠️ **注意事項**
- 這個修正只影響大樂透（BIG_LOTTO）
- 如果有其他彩種（如威力彩）也需要類似修正，請確認其規則
- 威力彩的特別號範圍不同（第二區 1-8），需要特殊處理

🎯 **用戶體驗改進**
- 用戶只需選擇 6 個號碼，更符合實際購買流程
- 回測結果更準確，能正確判定各種獎項
- 系統邏輯與實際彩票規則完全一致
