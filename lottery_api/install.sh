#!/bin/bash

# Lottery Prophet API - 快速安裝腳本

echo "🚀 開始安裝 Lottery Prophet API..."

# 檢查 Python 版本
echo "📍 檢查 Python 版本..."
python3 --version

if [ $? -ne 0 ]; then
    echo "❌ 錯誤: 未找到 Python 3"
    echo "請先安裝 Python 3.9 或更高版本"
    exit 1
fi

# 創建虛擬環境
echo "📦 創建虛擬環境..."
python3 -m venv venv

# 啟動虛擬環境
echo "🔌 啟動虛擬環境..."
source venv/bin/activate

# 升級 pip
echo "⬆️  升級 pip..."
pip install --upgrade pip

# 安裝依賴
echo "📥 安裝依賴套件..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ 依賴安裝失敗"
    echo "💡 如果是 Prophet 安裝問題，請嘗試："
    echo "   brew install cmake (Mac 用戶)"
    echo "   然後重新運行此腳本"
    exit 1
fi

echo ""
echo "✅ 安裝完成！"
echo ""
echo "🎯 下一步："
echo "   1. 啟動虛擬環境: source venv/bin/activate"
echo "   2. 運行服務器: uvicorn app:app --reload --port 5000"
echo "   3. 訪問文檔: http://localhost:5000/docs"
echo ""
echo "📝 或直接使用: ./start.sh"
