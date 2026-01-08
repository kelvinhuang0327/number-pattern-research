#!/bin/bash

# 後端優化預測功能測試腳本

echo "======================================"
echo "後端優化預測功能測試"
echo "======================================"
echo ""

# 1. 檢查後端服務是否運行
echo "1. 檢查後端服務..."
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo "✅ 後端服務運行中"
else
    echo "❌ 後端服務未運行"
    echo "   請執行: cd lottery-api && python app.py"
    exit 1
fi
echo ""

# 2. 檢查是否有優化配置
echo "2. 檢查優化配置..."
if [ -f "lottery-api/data/best_config.json" ]; then
    echo "✅ 找到優化配置文件"
    echo "   配置內容:"
    cat lottery-api/data/best_config.json | python -m json.tool | head -20
else
    echo "⚠️  未找到優化配置文件"
    echo "   請先執行自動優化"
fi
echo ""

# 3. 檢查是否有數據文件
echo "3. 檢查數據文件..."
if [ -f "lottery-api/data/lottery_data.json" ]; then
    echo "✅ 找到數據文件"
    DATA_COUNT=$(cat lottery-api/data/lottery_data.json | python -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    echo "   數據量: $DATA_COUNT 期"
else
    echo "⚠️  未找到數據文件"
    echo "   請先同步數據到後端"
fi
echo ""

# 4. 測試 API 端點
echo "4. 測試 API 端點..."
echo "   測試 /api/predict-optimized (大樂透)..."

RESPONSE=$(curl -s -X POST http://localhost:5001/api/predict-optimized \
  -H "Content-Type: application/json" \
  -d '{"lotteryType": "BIG_LOTTO"}')

if echo "$RESPONSE" | grep -q "numbers"; then
    echo "✅ API 調用成功"
    echo "   預測結果:"
    echo "$RESPONSE" | python -m json.tool
else
    echo "❌ API 調用失敗"
    echo "   錯誤信息:"
    echo "$RESPONSE" | python -m json.tool
fi
echo ""

echo "======================================"
echo "測試完成"
echo "======================================"
