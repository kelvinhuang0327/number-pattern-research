# Claude Code 配置說明

## 配置檔案

### .claude/settings.json
- **PreToolUse Hooks**: 編輯前檢查（防止在 main 分支編輯）
- **PostToolUse Hooks**: 編輯後執行（Python 語法檢查、數據洩漏檢測）

### Skills（技能）
1. **prediction-methods** - 預測方法完整指南
2. **backtest-framework** - 回測框架使用
3. **data-leakage-prevention** - 數據洩漏防護

### Commands（指令）
1. **/predict** - 預測下期號碼
2. **/backtest** - 回測驗證

### Agents（代理）
1. **prediction-analyzer** - 預測結果分析

## Hooks 說明

### PreToolUse - 編輯前檢查

#### 1. Main 分支保護
```bash
# 防止在 main 分支直接編輯
[ "$(git branch --show-current)" != "main" ]
```
- 觸發: 任何 Edit 或 Write 操作
- 效果: 阻止在 main 分支編輯，強制使用開發分支

### PostToolUse - 編輯後執行

#### 1. Python 語法檢查
```bash
python3 -m py_compile "$FILE"
```
- 觸發: 寫入 .py 檔案後
- 效果: 立即檢查 Python 語法錯誤

#### 2. 回測數據洩漏檢測
```bash
grep -q 'assert.*date.*<.*target' "$FILE"
```
- 觸發: 寫入包含 "backtest" 的 .py 檔案後
- 效果: 檢查是否有數據洩漏防護邏輯

## 使用範例

### 激活 Skill
Claude 會根據提示自動激活相關技能：

```
你: 我想實作一個新的預測方法
Claude: [自動激活 prediction-methods 技能]

你: 如何確保回測沒有數據洩漏？
Claude: [自動激活 data-leakage-prevention 技能]
```

### 使用 Command
```
/predict 大樂透 3
/backtest 威力彩 四注組合
```

### 調用 Agent
```
@prediction-analyzer 分析這次回測結果
```

## 自訂配置

### 個人設定
創建 `.claude/settings.local.json`（不會提交到 Git）：
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write.*\\.md$",
        "hooks": [
          {
            "type": "command",
            "command": "echo '✅ Markdown 已儲存'",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

## 最佳實踐

1. **開發新功能前切換分支**
   ```bash
   git checkout -b feature/new-prediction-method
   ```

2. **回測前檢查數據洩漏**
   ```bash
   python3 tools/verify_no_data_leakage.py
   ```

3. **提交前驗證**
   - Python 檔案無語法錯誤（自動檢查）
   - 回測腳本有洩漏防護（自動提醒）
   - 更新 CLAUDE.md（如有重大變更）

## Hook 退出碼

- `0` - 成功
- `2` - 阻止操作（PreToolUse）
- 其他 - 非阻止錯誤

## 故障排除

### Hook 不執行
1. 檢查 settings.json 語法
2. 確認命令路徑正確
3. 檢查 timeout 是否足夠

### 誤報錯誤
調整 matcher 正則表達式或增加條件判斷
