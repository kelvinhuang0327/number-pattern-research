#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_FILE="$ROOT_DIR/docs/ai_agents.md"

list_files() {
  dir="$1"
  pattern="$2"
  if [ -d "$ROOT_DIR/$dir" ]; then
    find "$ROOT_DIR/$dir" -type f -name "$pattern" | sed "s|$ROOT_DIR||" | sed "s|^|.|" | sort
  fi
}

{
  echo "# AI Agent Documentation Registry"
  echo
  echo "為了統一管理，採用「執行位置固定 + 文件集中索引」。"
  echo
  echo "## Canonical Runtime Locations (不可隨意搬移)"
  echo
  echo "- \`.claude/agents/\`: 自訂 agent 規範"
  echo "- \`.claude/skills/\`: 技能知識文件"
  echo "- \`.claude/commands/\`: slash command workflows"
  echo "- \`.github/workflows/\`: CI/CD 觸發的 agent 任務"
  echo
  echo "## Unified Documentation Entry"
  echo
  echo "### Agents"
  list_files ".claude/agents" "*.md" | sed "s/^/- \`/" | sed "s/$/\`/"
  echo
  echo "### Skills"
  if [ -f "$ROOT_DIR/.claude/skills/README.md" ]; then
    echo "- \`.claude/skills/README.md\`"
  fi
  list_files ".claude/skills" "SKILL.md" | sed "s/^/- \`/" | sed "s/$/\`/"
  echo
  echo "### Commands"
  list_files ".claude/commands" "*.md" | sed "s/^/- \`/" | sed "s/$/\`/"
  echo
  echo "### Workflow Agents"
  list_files ".github/workflows" "*.yml" | sed "s/^/- \`/" | sed "s/$/\`/"
  echo
  echo "## Naming Standard"
  echo
  echo "- 檔名: kebab-case"
  echo "- 類型前綴:"
  echo "  - agent: *-agent.md (新檔建議)"
  echo "  - skill: SKILL.md (既有慣例)"
  echo "  - workflow: scheduled-<domain>-<purpose>.yml"
  echo
  echo "## Change Policy"
  echo
  echo "- 不直接搬移 .claude/* 執行檔，避免破壞 hooks 與 workflow 參照。"
  echo "- 新增或調整 agent/skill/command/workflow 時，請先執行此腳本同步本頁。"
} > "$OUT_FILE"

echo "Updated: $OUT_FILE"
