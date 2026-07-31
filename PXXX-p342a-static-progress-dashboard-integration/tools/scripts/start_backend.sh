#!/bin/bash

# 後端優化預測 - 一鍵啟動腳本

echo "======================================"
echo "🚀 後端優化預測 - 啟動服務"
echo "======================================"
echo ""

# 檢查是否在正確的目錄
if [ ! -d "lottery-api" ]; then
    echo "❌ 錯誤: 找不到 lottery-api 目錄"
    echo "   請在項目根目錄運行此腳本"
    exit 1
fi

# 檢查 Python 是否安裝
if ! command -v python3 &> /dev/null; then
    echo "❌ 錯誤: 未找到 Python 3"
    echo "   請先安裝 Python 3"
    exit 1
fi

echo "1. 檢查 Python 環境..."
python3 --version
echo ""

# 檢查依賴
echo "2. 檢查依賴..."
cd lottery-api

if [ ! -f "requirements.txt" ]; then
    echo "⚠️  未找到 requirements.txt"
else
    echo "   安裝依賴..."
    pip3 install -r requirements.txt -q
    echo "   ✅ 依賴安裝完成"
fi
echo ""

# 創建數據目錄
echo "3. 準備數據目錄..."
mkdir -p data
echo "   ✅ 數據目錄已準備"
echo ""

# 啟動服務
echo "4. 啟動後端服務..."
echo "   服務地址: http://localhost:5001"
echo "   API 文檔: http://localhost:5001/docs"
echo ""
echo "======================================"
echo "按 Ctrl+C 停止服務"
echo "======================================"
echo ""

python3 app.py
