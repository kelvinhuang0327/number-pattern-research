#!/usr/bin/env python3
"""
偵測與記錄假完成任務（COMPLETED + quota/rate-limit markers）。
此工具用於治理層面，辨識哪些 COMPLETED 任務實際上被 quota 訊號阻擋，
並統計主題級的假完成。
"""

import sys
import os
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define quota/rate-limit markers
QUOTA_MARKERS = [
    r"weekly rate limit",
    r"reached your weekly",
    r"no quota",
    r"you have no quota",
    r"switch to auto model to continue",
    r"please wait for your limit to reset",
    r"rate limit",
]

# Theme detection patterns (extract from title or prompt)
THEME_PATTERNS = {
    "POWER_LOTTO_WQ_P2": r"(?:winning quality|wq|p2[\s-]?1)",
    "POWER_LOTTO_HEALTH": r"(?:rsm.*monitor|main.*health|降權)",
    "DAILY_539_POOL": r"(?:pool.*data|彩池|trusted.*pool)",
    "DAILY_539_H013": r"(?:h013|poolsize|payout)",
    "BIG_LOTTO_500P": r"(?:big.*lotto|500p|大樂透.*監控)",
    "SYSTEM_GOVERNANCE": r"(?:quota|fake.*complet|fallback|governance)",
}


def get_db_conn():
    """連接到 orchestrator DB."""
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runtime", "agent_orchestrator", "orchestrator.db"
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def extract_theme(title: str, prompt_text: str = "") -> str:
    """根據 title 和 prompt 判斷任務主題."""
    full_text = (title + " " + prompt_text).lower()
    
    for theme, pattern in THEME_PATTERNS.items():
        if re.search(pattern, full_text):
            return theme
    return "UNKNOWN"


def check_quota_markers(text: str) -> list[str]:
    """檢查文本中是否包含 quota 標記."""
    text_lower = text.lower()
    found = []
    for marker in QUOTA_MARKERS:
        if re.search(marker, text_lower):
            found.append(marker)
    return list(set(found))


def analyze_fake_completions():
    """主分析函數：掃描所有 COMPLETED 任務，記錄假完成."""
    conn = get_db_conn()
    c = conn.cursor()
    
    # 查詢所有 COMPLETED 任務
    c.execute("""
        SELECT id, title, status, completed_file_path, prompt_text
        FROM agent_tasks
        WHERE status = 'COMPLETED'
        ORDER BY id DESC
    """)
    
    completed_tasks = c.fetchall()
    
    fake_completes = []
    theme_stats = defaultdict(lambda: {"count": 0, "task_ids": []})
    
    for task in completed_tasks:
        task_id = task["id"]
        title = task["title"]
        completed_path = task["completed_file_path"]
        prompt_text = task["prompt_text"] or ""
        
        if not completed_path or not os.path.exists(completed_path):
            continue
        
        # 讀取 completed 檔案
        try:
            with open(completed_path, 'r', encoding='utf-8') as f:
                completed_content = f.read()
        except Exception:
            continue
        
        # 檢查 quota 標記
        markers = check_quota_markers(completed_content)
        
        if markers:
            theme = extract_theme(title, prompt_text)
            
            fake_completes.append({
                "task_id": task_id,
                "title": title,
                "markers": markers,
                "theme": theme,
                "file": completed_path,
                "suggested_status": "REPLAN_REQUIRED"
            })
            
            # 累計主題統計
            theme_stats[theme]["count"] += 1
            theme_stats[theme]["task_ids"].append(task_id)
    
    conn.close()
    
    return fake_completes, dict(theme_stats)


def generate_governance_report(fake_completes: list, theme_stats: dict) -> dict:
    """產出治理報告."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_fake_completes": len(fake_completes),
        "themes": theme_stats,
        "tasks_by_theme": defaultdict(list),
        "all_fake_complete_tasks": []
    }
    
    # 按主題分組
    for item in fake_completes:
        theme = item["theme"]
        report["tasks_by_theme"][theme].append({
            "id": item["task_id"],
            "title": item["title"],
            "markers": item["markers"][:2]  # 只列前 2 個標記
        })
        report["all_fake_complete_tasks"].append({
            "id": item["task_id"],
            "title": item["title"],
            "theme": theme,
            "markers": item["markers"][:1]
        })
    
    return report


def print_summary(fake_completes: list, theme_stats: dict):
    """輸出摘要."""
    print("\n" + "="*60)
    print("假完成偵測結果 (Fake Completion Detection)")
    print("="*60)
    print(f"\n總假完成任務數: {len(fake_completes)}\n")
    
    print("按主題分類:")
    for theme in sorted(theme_stats.keys()):
        stats = theme_stats[theme]
        task_ids = stats["task_ids"]
        print(f"  {theme}: {stats['count']} 筆 (Task #{min(task_ids)}-#{max(task_ids)})")
    
    print("\n最近 10 筆假完成任務:")
    for item in fake_completes[:10]:
        print(f"  Task #{item['task_id']}: {item['title']}")
        print(f"    主題: {item['theme']}, 標記: {item['markers'][0]}")
    
    print("\n"+"="*60)


if __name__ == "__main__":
    fake_completes, theme_stats = analyze_fake_completions()
    report = generate_governance_report(fake_completes, theme_stats)
    
    # 輸出摘要
    print_summary(fake_completes, theme_stats)
    
    # 產出 JSON 報告
    report_path = "runtime/agent_orchestrator/fake_completion_audit.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n詳細報告已寫入: {report_path}")
    
    # 輸出命令行統計
    print(f"\n相關環境和命令:")
    print(f"  本地驗證工具: tools/detect_fake_completion.py")
    print(f"  治理規則需更新: orchestrator/worker_tick.py (_build_and_gate_task_result)")
    print(f"  回補邏輯: orchestrator/db.py (update_task_status_from_audit)")
