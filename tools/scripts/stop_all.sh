#!/bin/bash

# 停止前後台服務腳本

echo "======================================"
echo "🛑 停止服務"
echo "======================================"
echo ""

# 停止後台
if [ -f "backend.pid" ]; then
    BACKEND_PID=$(cat backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "停止後台服務 (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
        rm backend.pid
        echo "   ✅ 後台已停止"
    else
        echo "   ℹ️  後台未運行"
        rm backend.pid
    fi
else
    # 嘗試通過端口停止
    BACKEND_PID=$(lsof -ti:8002)
    if [ ! -z "$BACKEND_PID" ]; then
        echo "停止後台服務 (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
        echo "   ✅ 後台已停止"
    else
        echo "   ℹ️  後台未運行"
    fi
fi

# 停止前台
if [ -f "frontend.pid" ]; then
    FRONTEND_PID=$(cat frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "停止前台服務 (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
        rm frontend.pid
        echo "   ✅ 前台已停止"
    else
        echo "   ℹ️  前台未運行"
        rm frontend.pid
    fi
else
    # 嘗試通過端口停止（檢查 8080 和 8081）
    for PORT in 8080 8081; do
        FRONTEND_PID=$(lsof -ti:$PORT)
        if [ ! -z "$FRONTEND_PID" ]; then
            echo "停止前台服務 (端口 $PORT, PID: $FRONTEND_PID)..."
            kill $FRONTEND_PID 2>/dev/null
            echo "   ✅ 前台已停止"
        fi
    done
    if [ -z "$FRONTEND_PID" ]; then
        echo "   ℹ️  前台未運行"
    fi
fi

echo ""
echo "✅ 所有服務已停止"
echo "======================================"
