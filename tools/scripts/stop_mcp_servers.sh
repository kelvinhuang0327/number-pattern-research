#!/bin/bash

echo "======================================"
echo "🛑 停止所有 MCP Server 服務"
echo "======================================"
echo ""

# 停止 MCP server 進程
echo "1. 停止 MCP server 進程..."
pkill -9 -f "mcp-server-gemini" 2>/dev/null
pkill -9 -f "mcp-server-sequential-thinking" 2>/dev/null
pkill -9 -f "mcp-permissions.js" 2>/dev/null

sleep 1

# 檢查是否還有 MCP 進程
REMAINING=$(ps aux | grep -E "mcp-server" | grep -v grep | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo "   ✅ 所有 MCP server 進程已停止"
else
    echo "   ⚠️  還有 $REMAINING 個進程在運行"
    ps aux | grep -E "mcp-server" | grep -v grep
fi
echo ""

# 清空 MCP 配置
echo "2. 清空 MCP 配置文件..."
find ~/Library/Application\ Support/Code/User/workspaceStorage -name "mcp-servers.json" -exec sh -c 'echo "{\"mcpServers\": {}}" > "{}"' \; 2>/dev/null
echo "   ✅ MCP 配置已清空"
echo ""

echo "======================================"
echo "✅ MCP Server 功能已完全移除"
echo "======================================"
echo ""
echo "建議操作："
echo "1. 重新載入 VS Code 窗口（Cmd+R）"
echo "2. 或重啟 VS Code"
echo ""
