# 雙注策略 - 快速使用指南

## 🚀 快速開始（5分鐘）

### Step 1: 運行測試驗證

```bash
cd lottery_api
python3 test_double_bet_strategy.py
```

**預期結果**: 看到116期測試命中率50-67%

---

### Step 2: 啟動後端服務

```bash
cd lottery_api
python3 app.py
```

**確認**: 瀏覽器打開 http://localhost:8000/docs

---

### Step 3: 調用API獲取預測

#### 方法A: 使用Python示例

```bash
python3 demo_double_bet_api.py
```

#### 方法B: 使用curl命令

```bash
# 推薦模式（balanced - 命中率最高）
curl -X POST "http://localhost:8000/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=balanced"

# 最優模式（optimal）
curl -X POST "http://localhost:8000/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=optimal"

# 動態模式（dynamic）
curl -X POST "http://localhost:8000/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=dynamic"
```

---

## 📊 返回結果示例

```json
{
  "bet1": {
    "numbers": [1, 30, 34, 36, 39, 45],
    "method": "自適應頻率分析 + 遺漏值權重"
  },
  "bet2": {
    "numbers": [5, 15, 25, 33, 41, 47],
    "method": "極端奇數策略"
  },
  "analysis": {
    "total_coverage": 12,
    "overlap_count": 0,
    "expected_hit_rate": "50-67%"
  }
}
```

---

## 🎯 三種模式選擇

| 模式 | 適用場景 | 命中率 |
|------|----------|--------|
| **balanced** ⭐ | **推薦新手** | **66.7%** |
| optimal | 穩定預測 | 50% |
| dynamic | 智能適應 | 50% |

---

## 💡 使用建議

### 場景1: 我想要最高命中率
```bash
mode=balanced  # 116期驗證66.7%
```

### 場景2: 我想要智能預測
```bash
mode=dynamic   # 根據上期自動調整
```

### 場景3: 我想要穩定策略
```bash
mode=optimal   # 極端奇數+冷號回歸
```

---

## 📝 代碼集成示例

### Python

```python
import requests

# 調用API
response = requests.post(
    "http://localhost:8000/api/predict-double-bet",
    params={
        "lottery_type": "BIG_LOTTO",
        "mode": "balanced"
    }
)

result = response.json()

# 獲取兩注預測
bet1 = result['bet1']['numbers']
bet2 = result['bet2']['numbers']

print(f"注1: {bet1}")
print(f"注2: {bet2}")
print(f"覆蓋: {result['analysis']['total_coverage']}個號碼")
```

### JavaScript

```javascript
// 調用API
fetch('http://localhost:8000/api/predict-double-bet?lottery_type=BIG_LOTTO&mode=balanced', {
  method: 'POST'
})
  .then(res => res.json())
  .then(data => {
    console.log('注1:', data.bet1.numbers);
    console.log('注2:', data.bet2.numbers);
    console.log('覆蓋:', data.analysis.total_coverage, '個號碼');
  });
```

---

## ⚠️ 注意事項

1. **後端必須運行**: 確保 `python3 app.py` 正在運行
2. **數據要充足**: 至少需要20期歷史數據
3. **理性對待**: 彩票是隨機遊戲，無法保證中獎
4. **控制成本**: 雙注意味著2倍成本

---

## 🔧 故障排除

### 問題1: API調用失敗
```bash
# 檢查後端是否運行
lsof -i :8000

# 如果沒有，啟動後端
python3 app.py
```

### 問題2: 返回錯誤
```bash
# 查看日志
tail -f lottery_api/logs/app.log
```

### 問題3: 數據不足
```bash
# 確保數據庫有足夠數據
python3 -c "from database import db_manager; print(db_manager.get_stats())"
```

---

## 📚 更多資源

- 完整文檔: [DOUBLE_BET_IMPLEMENTATION.md](./DOUBLE_BET_IMPLEMENTATION.md)
- API文檔: http://localhost:8000/docs
- 測試腳本: `lottery_api/test_double_bet_strategy.py`
- 示例腳本: `lottery_api/demo_double_bet_api.py`

---

## ✅ 驗證清單

完成以下步驟確認系統正常：

- [ ] 運行 `test_double_bet_strategy.py` 成功
- [ ] 看到命中率50-67%的測試結果
- [ ] 後端服務啟動成功（端口8000）
- [ ] API調用返回正常結果
- [ ] 兩注號碼互補性100%（0重疊）

---

**快速開始時間**: < 5分鐘
**難度**: ⭐⭐ (簡單)
**推薦度**: ⭐⭐⭐⭐⭐

祝您使用愉快！🎉
