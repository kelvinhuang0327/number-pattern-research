#!/usr/bin/env python3
"""
Backfill fake-complete tasks: Re-audit completed tasks and mark quota-blocked ones as BLOCKED_ENV.

用途：修復過去 COMPLETED 但實際被 quota/rate-limit 阻擋的任務狀態。
此腳本：
1. 掃描所有 COMPLETED 任務
2. 檢查 completed artifact 是否包含 quota/rate-limit 訊息
3. 如有發現，更新狀態為 BLOCKED_ENV
4. 記錄修復日誌
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.worker_tick import _check_worker_runtime_errors, _is_environment_blocking_error
from orchestrator import db


def backfill_fake_completes(dry_run: bool = True):
    """Backfill fake-complete tasks."""
    conn = db.get_conn()
    c = conn.cursor()
    
    # 查詢所有 COMPLETED 任務
    c.execute("""
        SELECT id, title, status, completed_file_path, completed_text
        FROM agent_tasks
        WHERE status = 'COMPLETED'
        ORDER BY id DESC
    """)
    
    completed_tasks = c.fetchall()
    fixed_tasks = []
    
    for task in completed_tasks:
        task_id = task["id"]
        title = task["title"]
        completed_path = task["completed_file_path"]
        completed_text = task["completed_text"]
        
        # 優先用 completed_text（從 DB），否則從檔案讀
        content = ""
        if completed_text:
            content = completed_text
        elif completed_path and os.path.exists(completed_path):
            try:
                with open(completed_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue
        
        if not content:
            continue
        
        # 檢查 quota 標記
        output_lower = content.lower()
        markers = _check_worker_runtime_errors(output_lower)
        is_blocked = _is_environment_blocking_error(markers)
        
        if is_blocked:
            fixed_tasks.append({
                "task_id": task_id,
                "title": title,
                "markers": markers[:2],  # 只列前 2 個
            })
            
            if not dry_run:
                # 更新任務狀態為 BLOCKED_ENV
                db.update_task(
                    task_id,
                    status="BLOCKED_ENV",
                    error_message=f"quota/rate-limit: {markers[0] if markers else 'unknown'}"
                )
    
    conn.close()
    return fixed_tasks


def main():
    """Main."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill fake-complete COMPLETED tasks")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()
    
    dry_run = not args.apply
    mode = "DRY-RUN" if dry_run else "APPLY"
    
    print(f"\n{'='*60}")
    print(f"假完成回補腳本 - 模式: {mode}")
    print(f"{'='*60}\n")
    
    fixed_tasks = backfill_fake_completes(dry_run=dry_run)
    
    print(f"發現 {len(fixed_tasks)} 筆假完成 COMPLETED 任務需修復:\n")
    
    for item in fixed_tasks[:10]:  # 只顯示前 10 筆
        print(f"  Task #{item['task_id']}: {item['title']}")
        print(f"    標記: {item['markers'][0]}\n")
    
    if len(fixed_tasks) > 10:
        print(f"  ... 還有 {len(fixed_tasks) - 10} 筆任務")
    
    if dry_run:
        print(f"\n乾跑模式：狀態未修改")
        print(f"套用修改請執行: python3 tools/backfill_fake_completes.py --apply")
    else:
        print(f"\n已修復 {len(fixed_tasks)} 筆任務狀態")
        print(f"新增狀態: BLOCKED_ENV (表示外部環境阻塞，非任務失敗)")
    
    # 產出報告
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "fixed_count": len(fixed_tasks),
        "tasks": fixed_tasks
    }
    
    report_path = "runtime/agent_orchestrator/backfill_fake_completes_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n報告已寫入: {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
