# ⚾️ Betting-pool: Lottery AI Quant Research Platform

由 AI 驅動的自動化彩票 (WBC/Lottery) 預測量化研究平台，核心理念是「統計驗證、數據隔離、持續探索」。

## 🛠 技術棧 (Tech Stack)
- **核心語言**: Python 3.10+
- **數據分析**: Pandas >= 2.0, NumPy, SciPy
- **機器學習**: XGBoost, LightGBM, CatBoost, Scikit-learn
- **API 通訊**: Requests, Telethon (Telegram)
- **測試框架**: Pytest

## 📁 專案架構 (Project Structure)
- `models/`: 特徵工程與 ML 模型實作。
- `wbc_backend/`: WBC 賽事領域邏輯 (Schemas, Models)。
- `strategy/`: 下注策略與 Kelly 準則管理。
- `telegram_bot/`: 通知與交易指令對話介面。
- `tests/`: 回測腳本與單元測試。
- `data/`: 存放各階段資料 (依 raw, processed, snapshot 分層管理)。
- `rejected/`: 資料夾存檔未通過驗證的策略邏輯。

## 📜 開發規範 (Dev Standards)
- **命名規範**: 檔案及變數使用 `snake_case`；類別使用 `PascalCase`。
- **強型別**: 強制在 Python 中標註 `type hints` 確保數據流正確性。
- **數據隔離**: 所有的預測函數必須經過「開賽前狀態」隔離，絕不容許數據滲透 (Look-ahead Leakage)。
- **Simplicity First**: 若統計提升不顯著，優先選擇簡單的特徵集與模型架構。

## 🚀 常用指令 (Common Commands)
- `pytest tests/`: 執行單元測試
- `python main.py --game=C01`: 執行指定場次分析
- `python telegram_bot/bot.py`: 啟動 Telegram Bot (需先設定 .env)

## 💬 回應與溝通 (Communication)
- **預設語言**: 一律使用 **繁體中文** (Traditional Chinese) 回應使用者。
- **Commit 描述**: Conventional Commits + 繁體中文說明。
- **錯誤處理**: API 呼叫必須使用 try-catch 包裹，並詳細紀錄其失敗軌跡。

## 🔄 常見任務 SOP (Common Tasks)
- **新增一個新的 WBC 預測模組**:
  1. 在 `wbc_backend/models/` 加入對應的特徵邏輯。
  2. 通過 `tests/` 中的 backtest 驗證 (樣本數需 >= 1500)。
  3. 產出 `backtest_report.md` 供審核。
- **添加新特徵**:
  1. 確保該特徵不含未來資訊。
  2. 進行特徵不穩定性與顯著性測試。
