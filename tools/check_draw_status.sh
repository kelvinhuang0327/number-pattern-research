#!/bin/bash
# 使用方式：./tools/check_draw_status.sh
# 輸出：各彩種最新入庫期數、是否可能有新開獎尚未執行 pipeline、以及 milestone 狀態

set -euo pipefail

cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew

python3 - <<'PY'
import sqlite3
from datetime import datetime

from tools.milestone_monitor import check_milestones

DB_PATH = 'lottery_api/data/lottery_v2.db'
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('[DRAW STATUS]')
for lottery_type, label, frequency in [
    ('BIG_LOTTO', '大樂透', '週一/週五'),
    ('DAILY_539', '今彩539', '每日'),
    ('POWER_LOTTO', '威力彩', '週一/週四'),
]:
    row = cur.execute(
        'SELECT draw, date FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1',
        (lottery_type,),
    ).fetchone()
    if row:
        draw, draw_date = row
        print(f'{label}: 最新期 {draw}，開獎日 {draw_date}，預期頻率 {frequency}')
    else:
        print(f'{label}: 尚無入庫資料')

conn.close()

milestones = check_milestones()
print('\n[MILESTONES]')
if not milestones:
    print('  None')
else:
    for item in milestones:
        print(
            f"  {item['name']} ({item['lottery_type']}): {item['status']} "
            f"current={item.get('current_draw')} evaluate_at={item.get('evaluate_at_draw')} "
            f"remaining={item.get('draws_remaining')} ~{item.get('weeks_remaining')} weeks"
        )

print('\n[REMINDER]')
print('  若官方已開獎但 DB 尚未更新，請先執行 tools/post_draw_pipeline.py')
PY
