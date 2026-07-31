import traceback
import sys
sys.path.insert(0, '.')

from orchestrator import db, planner_tick
from unittest.mock import patch

db.init_db()
conn = db.get_conn()
conn.execute('DELETE FROM agent_task_runs')
conn.execute('DELETE FROM agent_tasks')
conn.commit()
conn.close()
db.set_setting('scheduler_enabled', '1')
db.set_setting('llm_execution_mode', 'safe-run')

short_task = {
    'slot_key': '20260423-short-task',
    'date_folder': '20260423',
    'title': '更新 MLB 2025 歷史數據回測報告',
    'slug': '20260423-short-task',
    'prompt_text': '# 任務\n\n更新 MLB 2025 歷史數據回測報告。',
    'prompt_file_path': '',
    'focus_area': 'test-short',
    'market_scope': 'test',
    'analysis_family': 'test',
}
planner_tick.TASK_BLUEPRINTS = (short_task,)
planner_tick._mine_tasks_from_wiki = lambda: []

# Temporarily patch to show full traceback inside planner
orig_except_handler = None
import orchestrator.planner_tick as _pt

# Monkey-patch exception handler to show traceback
import logging
orig_error = _pt.logger.error
import traceback as _tb
def loud_error(msg, *args, **kwargs):
    orig_error(msg, *args, **kwargs)
    _tb.print_exc()
_pt.logger.error = loud_error

with patch('orchestrator.usage_budget_guard.evaluate_usage_budget', return_value={'budget_status': 'OK', 'scheduler_mode': 'NORMAL'}):
    result = _pt.run_planner_tick()
    print("Result:", result)
