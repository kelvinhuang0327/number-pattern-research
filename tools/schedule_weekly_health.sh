#!/bin/bash
# 啟用：launchctl load -w ~/Library/LaunchAgents/com.kelvin.lottery.weekly.plist

set -euo pipefail

cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
mkdir -p logs

if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  source venv/bin/activate
fi

python3 tools/weekly_health_report.py >> logs/weekly_health.log 2>&1
