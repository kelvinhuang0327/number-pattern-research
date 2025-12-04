#!/bin/bash

# Lottery Prophet API - 啟動腳本

echo "🚀 啟動 Lottery Prophet API..."

# 啟動虛擬環境 (如果存在)
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 檢查端口是否被佔用
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  端口 5001 已被佔用"
    echo "請終止佔用的程序或修改端口"
    exit 1
fi

echo "✅ 環境就緒，啟動服務器..."
echo "📡 API 地址: http://localhost:5001"
echo "📚 API 文檔: http://localhost:5001/docs"
echo "❌ 按 Ctrl+C 停止服務器"
echo ""

# 啟動 API
uvicorn app:app --reload --port 5001
