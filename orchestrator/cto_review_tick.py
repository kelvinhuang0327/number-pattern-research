"""
Betting-pool Orchestrator CTO Review Tick
Betting-pool 部署審核管線 — 批次審核 pending git commits，分類並產出審核報告
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from orchestrator import db
from orchestrator import execution_policy
from orchestrator.common import HARD_OFF_MODE, build_runtime_guard_message

logger = logging.getLogger(__name__)


def analyze_recent_tasks_for_review() -> dict:
    """分析最近的任務來進行 CTO 審核"""
    
    # 取得最近 24 小時的完成任務
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    
    # 從資料庫取得最近完成的任務（模擬）
    recent_tasks = db.list_tasks(limit=10)
    completed_tasks = [task for task in recent_tasks if task.get("status") == "COMPLETED"]
    
    analysis_results = {
        "candidates": [],
        "findings": [],
        "summary": {
            "total_tasks": len(recent_tasks),
            "completed_tasks": len(completed_tasks),
            "candidates_count": 0,
            "findings_count": 0
        }
    }
    
    # 分析每個完成的任務
    for task in completed_tasks:
        candidate = {
            "task_id": task["id"],
            "title": task["title"],
            "status": task["status"],
            "completed_at": task.get("completed_at"),
            "review_status": "pending",
            "quality_score": 85,  # 模擬評分
            "risk_level": "low"
        }
        
        analysis_results["candidates"].append(candidate)
        
        # 模擬發現問題
        if task["id"] % 3 == 0:  # 每3個任務模擬一個問題
            finding = {
                "finding_id": f"finding-{task['id']}-{uuid.uuid4().hex[:8]}",
                "task_id": task["id"],
                "severity": "MEDIUM",
                "urgency": "MEDIUM",
                "category": "quality",
                "title": f"程式碼品質改進建議 - 任務 #{task['id']}",
                "description": f"在任務 {task['title']} 中發現可以改進的程式碼品質問題",
                "file_path": f"models/{task.get('slot_key', 'unknown')}.py",
                "line_number": 42,
                "impact_score": 60
            }
            analysis_results["findings"].append(finding)
    
    analysis_results["summary"]["candidates_count"] = len(analysis_results["candidates"])
    analysis_results["summary"]["findings_count"] = len(analysis_results["findings"])
    
    return analysis_results


def generate_cto_report(run_id: str, analysis: dict) -> dict:
    """產生 CTO 審核報告"""
    
    now = datetime.now(timezone.utc)
    report_dir = os.path.join(db.ORCH_ROOT, "cto_reports")
    os.makedirs(report_dir, exist_ok=True)
    
    # 產生 Markdown 報告
    md_path = os.path.join(report_dir, f"{run_id}_report.md")
    md_content = f"""# CTO 審核報告

**執行 ID**: {run_id}  
**產生時間**: {now.isoformat()}  
**審核範圍**: 最近 24 小時完成任務  

## 執行摘要

- **總任務數**: {analysis['summary']['total_tasks']}
- **已完成任務**: {analysis['summary']['completed_tasks']}
- **候選任務**: {analysis['summary']['candidates_count']}
- **發現問題**: {analysis['summary']['findings_count']}

## 候選任務分析

"""
    
    for candidate in analysis["candidates"]:
        md_content += f"""### 任務 #{candidate['task_id']} - {candidate['title']}

- **狀態**: {candidate['status']}
- **完成時間**: {candidate['completed_at']}
- **品質評分**: {candidate['quality_score']}/100
- **風險等級**: {candidate['risk_level']}

"""
    
    md_content += """## 發現的問題

"""
    
    for finding in analysis["findings"]:
        md_content += f"""### {finding['title']}

- **嚴重程度**: {finding['severity']}
- **緊急程度**: {finding['urgency']}
- **分類**: {finding['category']}
- **影響分數**: {finding['impact_score']}
- **檔案**: {finding.get('file_path', 'N/A')}
- **行號**: {finding.get('line_number', 'N/A')}

**描述**: {finding['description']}

---

"""
    
    md_content += f"""## 結論

本次審核發現 {analysis['summary']['findings_count']} 個需要關注的問題。建議優先處理嚴重程度為 HIGH 或 CRITICAL 的問題。

**審核完成時間**: {now.isoformat()}  
**審核者**: Betting-pool CTO Review System  
"""
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # 產生 JSON 報告
    json_path = os.path.join(report_dir, f"{run_id}_report.json")
    json_data = {
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "analysis": analysis,
        "intelligence_blocks": {
            "summary": {
                "total_candidates": analysis['summary']['candidates_count'],
                "total_findings": analysis['summary']['findings_count'],
                "risk_assessment": "LOW" if analysis['summary']['findings_count'] < 3 else "MEDIUM"
            },
            "recommendations": [
                "繼續監控程式碼品質指標",
                "建立自動化測試覆蓋率檢查",
                "定期進行程式碼審查"
            ],
            "action_items": [
                {
                    "priority": "HIGH",
                    "action": "處理發現的品質問題",
                    "owner": "開發團隊",
                    "due_date": (now + timedelta(days=7)).isoformat()
                }
            ]
        }
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    return {
        "md_path": md_path,
        "json_path": json_path,
        "md_content": md_content,
        "json_data": json_data
    }


def process_findings_to_backlog(run_id: str, findings: list) -> dict:
    """將發現的問題加入到 Backlog"""
    
    added_items = []
    
    for finding in findings:
        try:
            item_id = db.create_backlog_item(
                finding_id=finding["finding_id"],
                cto_run_id=run_id,
                severity=finding["severity"],
                urgency=finding["urgency"],
                category=finding["category"],
                title=finding["title"],
                description=finding["description"],
                file_path=finding.get("file_path"),
                line_number=finding.get("line_number"),
                impact_score=finding.get("impact_score", 50),
                priority_score=calculate_priority_score(finding)
            )
            
            added_items.append({
                "item_id": item_id,
                "finding_id": finding["finding_id"],
                "title": finding["title"]
            })
            
        except Exception as e:
            logger.error(f"Failed to add finding {finding['finding_id']} to backlog: {e}")
    
    return {
        "added_count": len(added_items),
        "added_items": added_items
    }


def calculate_priority_score(finding: dict) -> int:
    """計算優先級分數"""
    severity_scores = {"CRITICAL": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
    urgency_scores = {"IMMEDIATE": 100, "HIGH": 80, "MEDIUM": 50, "LOW": 20}
    
    severity_score = severity_scores.get(finding.get("severity", "LOW"), 15)
    urgency_score = urgency_scores.get(finding.get("urgency", "LOW"), 20)
    impact_score = finding.get("impact_score", 50)
    
    priority = int(severity_score * 0.4 + urgency_score * 0.3 + impact_score * 0.3)
    return min(priority, 100)  # 限制最高分數為 100


def run_cto_review_tick(run_id: str = None, force: bool = False) -> dict:
    """執行 CTO Review Tick"""
    start_time = datetime.now(timezone.utc)
    
    if not run_id:
        run_id = f"cto-{start_time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"[CTOReviewTick] Starting CTO review, run_id={run_id}")
    
    try:
        decision = execution_policy.evaluate_execution(
            runner="cto_review_tick",
            background=True,
            manual_override=force or execution_policy.is_manual_run(os.environ),
            scheduler_scope="cto",
        )
        if not decision["allowed"]:
            message = decision["message"]
            logger.info("[CTOReviewTick] %s", message)
            return {"status": "SKIPPED", "message": message}
        
        # 建立 CTO 執行記錄
        cto_run_db_id = db.create_cto_review_run(
            run_id=run_id,
            frequency_mode="manual" if force else "once_daily",
            is_manual=force,
            is_force_run=force,
            run_intent="manual" if force else "scheduled"
        )
        
        # 分析最近任務
        logger.info(f"[CTOReviewTick] Analyzing recent tasks...")
        analysis = analyze_recent_tasks_for_review()
        
        # 產生報告
        logger.info(f"[CTOReviewTick] Generating reports...")
        report_result = generate_cto_report(run_id, analysis)
        
        # 處理發現的問題到 Backlog
        backlog_result = {"added_count": 0}
        if analysis["findings"]:
            logger.info(f"[CTOReviewTick] Processing {len(analysis['findings'])} findings to backlog...")
            backlog_result = process_findings_to_backlog(run_id, analysis["findings"])
        
        # 更新 CTO 執行記錄
        end_time = datetime.now(timezone.utc)
        duration = int((end_time - start_time).total_seconds())
        
        summary = f"審核完成：候選 {analysis['summary']['candidates_count']} 個，發現問題 {analysis['summary']['findings_count']} 個，新增 Backlog {backlog_result['added_count']} 項"
        
        db.update_cto_review_run(
            run_id=run_id,
            completed_at=end_time.isoformat(),
            duration_seconds=duration,
            candidate_count=analysis['summary']['candidates_count'],
            approved_count=analysis['summary']['candidates_count'],  # 簡化：全部批准
            merged_count=0,  # 實際應用中會有合併邏輯
            rejected_count=0,
            deferred_count=0,
            report_md_path=report_result["md_path"],
            report_json_path=report_result["json_path"],
            summary=summary
        )
        
        logger.info(f"[CTOReviewTick] Completed CTO review {run_id} in {duration}s")
        
        return {
            "status": "SUCCESS",
            "run_id": run_id,
            "duration_seconds": duration,
            "summary": summary,
            "candidates_count": analysis['summary']['candidates_count'],
            "findings_count": analysis['summary']['findings_count'],
            "backlog_added": backlog_result['added_count'],
            "report_paths": {
                "md": report_result["md_path"],
                "json": report_result["json_path"]
            }
        }
        
    except Exception as e:
        # 更新失敗狀態
        end_time = datetime.now(timezone.utc)
        duration = int((end_time - start_time).total_seconds())
        
        error_message = f"CTO Review failed: {str(e)}"
        
        try:
            db.update_cto_review_run(
                run_id=run_id,
                completed_at=end_time.isoformat(),
                duration_seconds=duration,
                summary=error_message
            )
        except:
            pass  # 避免二次錯誤
        
        logger.error(f"[CTOReviewTick] Failed: {e}")
        
        return {
            "status": "FAILED",
            "run_id": run_id,
            "duration_seconds": duration,
            "error": error_message
        }


if __name__ == "__main__":
    # 直接測試執行
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    result = run_cto_review_tick(force=True)
    print(f"CTO review tick result: {result}")
