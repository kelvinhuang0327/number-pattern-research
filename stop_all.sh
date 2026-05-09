#!/bin/bash

echo "======================================"
echo "🛑 停止 Lottery 服務..."
echo "======================================"

# 停止後台
if [ -f "backend.pid" ]; then
    PID=$(cat backend.pid)
    echo "停止後台服務 (PID: $PID)..."
    kill $PID 2>/dev/null
    rm backend.pid
fi

# 端口清理 (8002)
BACKEND_PID=$(lsof -ti:8002)
if [ ! -z "$BACKEND_PID" ]; then
    echo "清理端口 8002 (PID: $BACKEND_PID)..."
    kill -9 $BACKEND_PID 2>/dev/null
fi

# 停止前台
if [ -f "frontend.pid" ]; then
    PID=$(cat frontend.pid)
    echo "停止前台服務 (PID: $PID)..."
    kill $PID 2>/dev/null
    rm frontend.pid
fi

# 端口清理 (8081)
FRONTEND_PID=$(lsof -ti:8081)
if [ ! -z "$FRONTEND_PID" ]; then
    echo "清理端口 8081 (PID: $FRONTEND_PID)..."
    kill -9 $FRONTEND_PID 2>/dev/null
fi

echo "✅ 服務已停止。"
echo "======================================"
