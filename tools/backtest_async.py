"""
Async Backtest Runner — 非阻塞回測進度追蹤
==========================================
借鑑 MiroFish SimulationRunner 設計:
  - 背景 Thread 執行，不阻塞主流程
  - JSON 狀態持久化，支援 polling
  - task_id 索引，支援多任務並行

用法:
    runner = BacktestRunner()

    # 啟動回測
    task_id = runner.start('power_fourier_1000p', run_power_backtest, periods=1000)

    # 輪詢進度
    status = runner.get_status(task_id)
    print(status['progress'], status['phase'])

    # 等待完成
    result = runner.wait(task_id, timeout=300)

2026-03-12 Created (Phase 1-B, MiroFish Phase 1)
"""
import os
import sys
import json
import time
import uuid
import threading
import traceback
from datetime import datetime
from typing import Callable, Optional, Dict, Any

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(project_root, 'lottery_api', 'data', 'backtest_tasks.json')

# 狀態常數（對應 MiroFish TaskStatus enum）
STATUS_PENDING    = 'PENDING'
STATUS_RUNNING    = 'RUNNING'
STATUS_COMPLETED  = 'COMPLETED'
STATUS_FAILED     = 'FAILED'


class BacktestRunner:
    """
    非阻塞回測執行器

    使用 threading.Thread 在背景執行回測，
    透過 JSON 持久化狀態讓主程序可以 polling 進度。
    """

    _lock = threading.Lock()

    def __init__(self, state_file: str = None):
        self.state_file = state_file or STATE_FILE
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    # ---- 狀態存取 ----

    def _load_state(self) -> Dict:
        if not os.path.exists(self.state_file):
            return {}
        with open(self.state_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_state(self, state: Dict):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _update_task(self, task_id: str, updates: Dict):
        with self._lock:
            state = self._load_state()
            if task_id in state:
                state[task_id].update(updates)
                self._save_state(state)

    # ---- 公開 API ----

    def start(
        self,
        name: str,
        backtest_func: Callable,
        **kwargs,
    ) -> str:
        """
        啟動一個異步回測任務

        Args:
            name: 任務名稱（描述用）
            backtest_func: 回測函數 callable(**kwargs) -> dict
            **kwargs: 傳給 backtest_func 的參數

        Returns:
            task_id: UUID 字串，用於後續 get_status / wait
        """
        task_id = str(uuid.uuid4())[:8]
        task = {
            'task_id': task_id,
            'name': name,
            'status': STATUS_PENDING,
            'progress': 0,
            'phase': 'queued',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None,
            'kwargs_repr': str({k: v for k, v in kwargs.items() if k != 'history'}),
        }

        with self._lock:
            state = self._load_state()
            state[task_id] = task
            self._save_state(state)

        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, backtest_func, kwargs),
            daemon=True,
            name=f'backtest-{task_id}',
        )
        thread.start()
        print(f"  [ASYNC] 回測啟動: {name} (task_id={task_id})")
        return task_id

    def get_status(self, task_id: str) -> Optional[Dict]:
        """取得任務狀態"""
        state = self._load_state()
        return state.get(task_id)

    def list_tasks(self, limit: int = 20) -> list:
        """列出近期任務（按建立時間降序）"""
        state = self._load_state()
        tasks = list(state.values())
        tasks.sort(key=lambda t: t.get('created_at', ''), reverse=True)
        return tasks[:limit]

    def wait(self, task_id: str, timeout: int = 600, poll_interval: float = 2.0) -> Optional[Dict]:
        """
        阻塞等待任務完成

        Args:
            timeout: 最大等待秒數
            poll_interval: 輪詢間隔秒數

        Returns:
            最終狀態 dict，或 None（超時）
        """
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(task_id)
            if status and status['status'] in (STATUS_COMPLETED, STATUS_FAILED):
                return status
            elapsed = int(time.time() - start)
            if status:
                print(f"  [WAIT] {status['name']}: {status['phase']} "
                      f"({status['progress']}%) [{elapsed}s]")
            time.sleep(poll_interval)
        return None

    def update_progress(self, task_id: str, progress: int, phase: str):
        """回測函數內部呼叫，更新進度（0-100）"""
        self._update_task(task_id, {'progress': progress, 'phase': phase})

    # ---- 內部執行 ----

    def _run_task(self, task_id: str, func: Callable, kwargs: Dict):
        self._update_task(task_id, {
            'status': STATUS_RUNNING,
            'started_at': datetime.now().isoformat(),
            'phase': 'running',
        })
        try:
            # 注入 task_id 讓回測函數可以更新進度（可選）
            if 'task_id' in func.__code__.co_varnames:
                kwargs['task_id'] = task_id

            result = func(**kwargs)

            self._update_task(task_id, {
                'status': STATUS_COMPLETED,
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'phase': 'done',
                'result': result,
            })
            print(f"  [ASYNC] 完成: task_id={task_id}")
        except Exception as e:
            self._update_task(task_id, {
                'status': STATUS_FAILED,
                'completed_at': datetime.now().isoformat(),
                'phase': 'failed',
                'error': traceback.format_exc(),
            })
            print(f"  [ASYNC] 失敗: task_id={task_id} — {e}")


# ============================================================
# Singleton
# ============================================================
_runner_instance: Optional[BacktestRunner] = None


def get_runner() -> BacktestRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = BacktestRunner()
    return _runner_instance


# ============================================================
# CLI: python3 tools/backtest_async.py status [task_id]
#      python3 tools/backtest_async.py list
# ============================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Async Backtest Runner CLI')
    sub = parser.add_subparsers(dest='cmd')

    p_status = sub.add_parser('status', help='查詢任務狀態')
    p_status.add_argument('task_id')

    p_list = sub.add_parser('list', help='列出近期任務')
    p_list.add_argument('--limit', type=int, default=10)

    args = parser.parse_args()
    runner = BacktestRunner()

    if args.cmd == 'status':
        s = runner.get_status(args.task_id)
        if s:
            print(json.dumps(s, indent=2, ensure_ascii=False))
        else:
            print(f"找不到 task_id={args.task_id}")

    elif args.cmd == 'list':
        tasks = runner.list_tasks(args.limit)
        print(f"{'task_id':>10}  {'status':>12}  {'progress':>8}  {'name'}")
        print('-' * 60)
        for t in tasks:
            print(f"{t['task_id']:>10}  {t['status']:>12}  {t['progress']:>7}%  {t['name']}")

    else:
        parser.print_help()
