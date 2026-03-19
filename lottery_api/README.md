# Lottery Prophet API

基於 Facebook Prophet 的彩票號碼 AI 預測後端服務。

## 🚀 快速開始

### 1. 創建虛擬環境

```bash
cd lottery_api
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 運行服務器

```bash
# 開發模式（自動重載）
uvicorn app:app --reload --port 5000

# 或使用 Python 直接運行 python app.py
```

### 4. 訪問 API

- **API 根路徑**: http://localhost:5000
- **API 文檔**: http://localhost:5000/docs
- **健康檢查**: http://localhost:5000/health

## 📚 API 端點

### GET `/`
API 基本信息

### GET `/health`
健康檢查端點

### GET `/api/models`
列出所有可用模型

### POST `/api/predict`
預測下一期號碼

**請求示例**:
```json
{
  "history": [
    {
      "date": "2024-01-01",
      "draw": 1,
      "numbers": [5, 12, 23, 34, 41, 49],
      "lotteryType": "BIG_LOTTO"
    },
    ...
  ],
  "lotteryRules": {
    "pickCount": 6,
    "minNumber": 1,
    "maxNumber": 49
  },
  "modelType": "prophet"
}
```

**響應示例**:
```json
{
  "numbers": [7, 15, 28, 32, 40, 45],
  "confidence": 0.68,
  "method": "Prophet 時間序列分析",
  "trend": "號碼呈上升趨勢 (+3.2%)",
  "seasonality": "檢測到每週週期性模式",
  "modelInfo": {
    "trainingSize": 150,
    "version": "1.0",
    "algorithm": "Prophet (Facebook)"
  },
  "notes": "基於歷史數據的時間序列趨勢和週期性分析"
}
```

## 🧪 測試 API

### 使用 curl

```bash
curl -X POST "http://localhost:5000/api/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "history": [
      {
        "date": "2024-01-01",
        "draw": 1,
        "numbers": [5, 12, 23, 34, 41, 49],
        "lotteryType": "BIG_LOTTO"
      }
    ],
    "lotteryRules": {
      "pickCount": 6,
      "minNumber": 1,
      "maxNumber": 49
    },
    "modelType": "prophet"
  }'
```

### 使用 Python

```python
import requests

response = requests.post(
    "http://localhost:5000/api/predict",
    json={
        "history": [...],
        "lotteryRules": {...},
        "modelType": "prophet"
    }
)

result = response.json()
print(f"預測號碼: {result['numbers']}")
print(f"信心度: {result['confidence']:.2%}")
```

## 📦 項目結構

```
lottery_api/
├── app.py                      # FastAPI 主應用
├── models/
│   ├── __init__.py
│   └── prophet_model.py        # Prophet 模型實現
├── utils/
│   └── __init__.py
├── requirements.txt            # Python 依賴
├── README.md                   # 本文件
└── .env.example               # 環境變數範例（可選）
```

## 🔧 配置

### 環境變數（可選）

創建 `.env` 文件：

```env
API_HOST=0.0.0.0
API_PORT=5000
DEBUG=True
CORS_ORIGINS=*
```

## 📊 Prophet 模型說明

### 核心特性

1. **時間序列分析**: 自動檢測趨勢和週期性模式
2. **週期性檢測**: 識別每週、每月的規律性變化
3. **趨勢預測**: 分析號碼的上升/下降趨勢
4. **頻率基準**: 結合歷史高頻號碼提高穩定性

### 信心度計算

- **數據量 < 20期**: 0.3 (低)
- **數據量 20-50期**: 0.45 (中低)
- **數據量 50-100期**: 0.6 (中)
- **數據量 100-200期**: 0.7 (中高)
- **數據量 > 200期**: 0.75 (高)
 
 ## 🌟 高級預測策略 (2026/01 優化)
 
 ### 1. Wobble Strategy (近鄰擾動)
 - **功能**: 對高信心度號碼進行 ±1 微調。
 - **目標**: 解決「差一號」問題，提高實戰中獎機率。
 
 ### 2. Zone Gap Awareness (區塊斷層感知)
 - **功能**: 自動偵測長期未開出的冷門區塊。
 - **目標**: 防止預測過度聚集在過熱區塊，提高覆蓋率。
 
 ### 3. Multi-Bet Optimizer (多注優化器)
 - **功能**: 整合異構模型並確保多注組合的多樣性。
 - **配置**: 支持 6 注、8 注或自定義注數生成。
 
 > 詳細技術細節請參閱 [docs/STRATEGIES.md](./docs/STRATEGIES.md)

## 🚢 部署

### 部署到 Railway

1. 註冊 [Railway](https://railway.app)
2. 連接 GitHub 倉庫
3. Railway 會自動檢測並部署
4. 獲取 API URL 並更新前端配置

### 部署到 Render

1. 註冊 [Render](https://render.com)
2. 創建新的 Web Service
3. 連接 GitHub 倉庫
4. 設置啟動命令: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. 獲取 API URL 並更新前端配置

### Docker 部署（可選）

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
```

## 🐛 Troubleshooting

### Prophet 安裝失敗

```bash
# Mac 用戶
brew install cmake

# 然後重新安裝
pip install prophet
```

### CORS 錯誤

確認 `app.py` 中 CORS 設置包含您的前端域名：

```python
allow_origins=["http://localhost:3000", "your-frontend-domain.com"]
```

### 記憶體問題

Prophet 訓練需要一定記憶體，如果遇到問題：
- 限制歷史數據量（最多 200-300 期）
- 調整 Prophet 參數減少複雜度

## 📝 未來計劃

- [ ] 實現 XGBoost 模型
- [ ] 實現 LSTM 模型
- [ ] 添加模型緩存機制
- [ ] 添加請求速率限制
- [ ] 添加模型訓練 API
- [ ] 添加模型性能監控

## 📄 許可證

MIT License

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

---

**開發愉快！** 🎯
