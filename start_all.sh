#!/bin/bash

# 前後台統一啟動腳本

set -e

SKIP_VERIFY=false
for arg in "$@"; do
    if [[ "$arg" == "--skip-verify" ]]; then
        SKIP_VERIFY=true
    fi
done

# 避免合約測試中的 Matplotlib 快取權限問題
export MPLCONFIGDIR="${TMPDIR:-/tmp}/matplotlib-cache"
mkdir -p "$MPLCONFIGDIR"

echo "======================================"
echo "🚀 大數據智能分析系統 - 啟動服務"
echo "======================================"
echo ""

# 檢查後台是否已在運行
BACKEND_PID=$(lsof -ti:8002 || true)
if [ ! -z "$BACKEND_PID" ]; then
    echo "⚠️  後台服務已在運行 (PID: $BACKEND_PID)"
    echo "   端口: 8002"
else
    echo "1. 啟動後台服務..."
    cd lottery_api
    
    # 檢查 Python
    if ! command -v python3 &> /dev/null; then
        echo "❌ 錯誤: 未找到 Python 3"
        exit 1
    fi
    
    # 安裝依賴
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt -q 2>/dev/null
    fi
    
    # 後台啟動服務
    nohup python3 app.py > ../backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../backend.pid
    echo "   ✅ 後台服務已啟動 (PID: $BACKEND_PID)"
    echo "   📝 日誌: backend.log"
    cd ..
fi
echo ""

# 啟動前台服務
echo "2. 啟動前台服務..."

# 檢查是否有 HTTP 服務器
if command -v python3 &> /dev/null; then
    echo "   使用 Python HTTP 服務器..."
    FRONTEND_PID=$(lsof -ti:8081 || true)
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "   ⚠️  前台已在運行 (端口: 8081)"
    else
        nohup python3 -m http.server 8081 > frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > frontend.pid
        echo "   ✅ 前台服務已啟動 (PID: $FRONTEND_PID)"
    fi
elif command -v php &> /dev/null; then
    echo "   使用 PHP 內建服務器..."
    nohup php -S localhost:8080 > frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > frontend.pid
    echo "   ✅ 前台服務已啟動 (PID: $FRONTEND_PID)"
else
    echo "   ❌ 未找到 HTTP 服務器"
    echo "   請手動開啟 index.html"
fi
echo ""

# 等待服務啟動
echo "3. 檢查服務狀態..."
sleep 3

# 檢查後台
if curl -s http://localhost:8002/health > /dev/null 2>&1; then
    echo "   ✅ 後台 API: http://localhost:8002"
else
    echo "   ⚠️  後台可能還在啟動中..."
fi

# 檢查前台
if curl -s http://localhost:8081 > /dev/null 2>&1; then
    echo "   ✅ 前台頁面: http://localhost:8081"
else
    echo "   ⚠️  前台可能還在啟動中..."
fi
echo ""

# 預測 API 回歸驗證（部署卡關）
if [ "$SKIP_VERIFY" = false ]; then
    echo "4. 執行後端預測回歸驗證..."
    if python3 tools/verify_prediction_api.py; then
        echo "   ✅ 回歸驗證通過（smoke + contract）"
    else
        echo "   ❌ 回歸驗證失敗，停止服務"
        ./stop_all.sh >/dev/null 2>&1 || true
        exit 1
    fi
else
    echo "4. 已跳過回歸驗證 (--skip-verify)"
fi
echo ""

echo "======================================"
echo "✨ 服務啟動完成"
echo "======================================"
echo ""
echo "📱 前台訪問: http://localhost:8081"
echo "🔧 後台 API: http://localhost:8002"
echo "📚 API 文檔: http://localhost:8002/docs"
echo ""
echo "📝 查看後台日誌: tail -f backend.log"
echo "📝 查看前台日誌: tail -f frontend.log"
echo ""
echo "🛑 停止服務: ./stop_all.sh"
echo "⏭️  跳過驗證啟動: ./start_all.sh --skip-verify"
echo "======================================"

# 如果是自動啟動或需要守護進程，請保持在前台
if [[ "$*" == *"--foreground"* ]] || [[ "$*" == *"-f"* ]]; then
    echo "🔔 進入前台監控模式..."
    trap "./stop_all.sh; exit 0" SIGINT SIGTERM
    # 監控後台日誌，保持腳本不退出
    tail -f backend.log
else
    echo "💡 提示: 使用 ./start_all.sh --foreground 可進入監控模式"
fi
