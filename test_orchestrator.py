#!/usr/bin/env python3
"""
Betting-pool Orchestrator 完整功能測試
驗證與 SOURCE 系統的流程一致性
"""

import os
import sys
import time
import json
import requests
import logging
from datetime import datetime, timezone

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API 基礎 URL
API_BASE = "http://127.0.0.1:8787"

class OrchestrationTest:
    """編排系統測試類別"""
    
    def __init__(self):
        self.test_results = []
        self.failed_tests = []
    
    def run_test(self, test_name: str, test_func):
        """執行單一測試"""
        logger.info(f"🧪 執行測試: {test_name}")
        
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "duration": round(duration, 2),
                "result": result
            })
            logger.info(f"✅ {test_name} - PASS ({duration:.2f}s)")
            return True
            
        except Exception as e:
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            self.failed_tests.append(test_name)
            logger.error(f"❌ {test_name} - FAIL: {e}")
            return False
    
    def test_database_initialization(self):
        """測試資料庫初始化"""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from orchestrator import db
        
        # 初始化資料庫
        db.init_db()
        
        # 檢查表格是否存在
        conn = db.get_conn()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [row[0] for row in tables]
            
            required_tables = [
                "agent_tasks",
                "agent_task_runs", 
                "settings",
                "cto_review_runs",
                "cto_backlog_items"
            ]
            
            for table in required_tables:
                if table not in table_names:
                    raise AssertionError(f"Required table {table} not found")
            
            return {"tables_created": len(table_names), "required_tables": required_tables}
        finally:
            conn.close()
    
    def test_api_server_health(self):
        """測試 API 服務器健康狀態"""
        response = requests.get(f"{API_BASE}/health", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") != "healthy":
            raise AssertionError(f"API server unhealthy: {data}")
        
        return data
    
    def test_summary_api(self):
        """測試 Summary API"""
        response = requests.get(f"{API_BASE}/api/summary", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        required_fields = ["project", "scheduler", "counts"]
        
        for field in required_fields:
            if field not in data:
                raise AssertionError(f"Missing field in summary: {field}")
        
        return {
            "project_name": data["project"]["name"],
            "scheduler_enabled": data["scheduler"]["enabled"],
            "task_counts": data["counts"]
        }
    
    def test_planner_trigger(self):
        """測試 Planner 手動觸發"""
        response = requests.post(f"{API_BASE}/api/planner/run-now", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if not data.get("ok"):
            raise AssertionError("Planner trigger failed")
        
        # 等待 Planner 執行
        time.sleep(2)
        
        # 檢查任務是否被建立
        tasks_response = requests.get(f"{API_BASE}/api/tasks?limit=1")
        tasks_response.raise_for_status()
        tasks_data = tasks_response.json()
        
        if not tasks_data.get("tasks"):
            raise AssertionError("No tasks created by planner")
        
        return {
            "run_status": data.get("result", {}).get("status"),
            "task_id": data.get("result", {}).get("task_id"),
            "tasks_created": len(tasks_data["tasks"])
        }
    
    def test_worker_trigger(self):
        """測試 Worker 手動觸發"""
        response = requests.post(f"{API_BASE}/api/worker/run-now", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if not data.get("ok"):
            raise AssertionError("Worker trigger failed")
        
        # 等待 Worker 執行
        time.sleep(3)
        
        # 檢查執行記錄
        runs_response = requests.get(f"{API_BASE}/api/runs?limit=5")
        runs_response.raise_for_status()
        runs_data = runs_response.json()
        
        worker_runs = [run for run in runs_data["runs"] if "worker" in run.get("runner", "")]
        
        return {
            "run_status": data.get("result", {}).get("status"),
            "task_id": data.get("result", {}).get("task_id"),
            "worker_runs": len(worker_runs)
        }
    
    def test_cto_review_trigger(self):
        """測試 CTO Review 手動觸發"""
        response = requests.post(
            f"{API_BASE}/api/cto/run-now",
            json={"force": True, "intent": "test"},
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        if not data.get("ok"):
            raise AssertionError("CTO review trigger failed")
        
        run_id = data.get("run_id")
        
        # 等待 CTO Review 執行
        time.sleep(5)
        
        # 檢查 CTO 執行記錄
        cto_runs_response = requests.get(f"{API_BASE}/api/cto/runs?limit=1")
        cto_runs_response.raise_for_status()
        cto_data = cto_runs_response.json()
        
        return {
            "run_id": run_id,
            "cto_runs": len(cto_data.get("runs", []))
        }
    
    def test_scheduler_control(self):
        """測試調度器控制"""
        # 測試停用調度器
        response = requests.post(
            f"{API_BASE}/api/scheduler/enable",
            json={"enabled": False}
        )
        response.raise_for_status()
        
        # 檢查狀態
        status_response = requests.get(f"{API_BASE}/api/scheduler")
        status_response.raise_for_status()
        status_data = status_response.json()
        
        if status_data.get("enabled") is not False:
            raise AssertionError("Scheduler disable failed")
        
        # 重新啟用
        enable_response = requests.post(
            f"{API_BASE}/api/scheduler/enable",
            json={"enabled": True}
        )
        enable_response.raise_for_status()
        
        return {"scheduler_control": "working"}
    
    def test_provider_configuration(self):
        """測試 Provider 設定"""
        # 取得當前設定
        response = requests.get(f"{API_BASE}/api/providers")
        response.raise_for_status()
        original_config = response.json()
        
        # 更新設定
        new_config = {
            "planner_provider": "claude",
            "worker_provider": "codex"
        }
        
        update_response = requests.post(f"{API_BASE}/api/providers", json=new_config)
        update_response.raise_for_status()
        
        # 驗證更新
        verify_response = requests.get(f"{API_BASE}/api/providers")
        verify_response.raise_for_status()
        updated_config = verify_response.json()
        
        if updated_config["planner_provider"] != "claude":
            raise AssertionError("Provider configuration update failed")
        
        return {
            "original": original_config,
            "updated": updated_config
        }
    
    def test_task_flow(self):
        """測試完整任務流程"""
        # 1. 觸發 Planner 建立任務
        planner_response = requests.post(f"{API_BASE}/api/planner/run-now")
        planner_response.raise_for_status()
        
        time.sleep(2)
        
        # 2. 取得最新任務
        tasks_response = requests.get(f"{API_BASE}/api/tasks?limit=1&status=QUEUED")
        tasks_response.raise_for_status()
        tasks_data = tasks_response.json()
        
        if not tasks_data.get("tasks"):
            raise AssertionError("No queued tasks found")
        
        task = tasks_data["tasks"][0]
        task_id = task["id"]
        
        # 3. 觸發 Worker 執行任務
        worker_response = requests.post(f"{API_BASE}/api/worker/run-now")
        worker_response.raise_for_status()
        
        time.sleep(3)
        
        # 4. 檢查任務是否完成
        task_detail_response = requests.get(f"{API_BASE}/api/tasks/{task_id}")
        task_detail_response.raise_for_status()
        task_detail = task_detail_response.json()
        
        final_status = task_detail["task"]["status"]
        
        return {
            "task_id": task_id,
            "initial_status": task["status"],
            "final_status": final_status,
            "execution_successful": final_status in ["COMPLETED", "FAILED"]  # 任一結果都表示執行了
        }
    
    def run_all_tests(self):
        """執行所有測試"""
        logger.info("🚀 開始 Betting-pool Orchestrator 完整功能測試")
        logger.info("="*60)
        
        tests = [
            ("資料庫初始化", self.test_database_initialization),
            ("API 服務器健康檢查", self.test_api_server_health),
            ("Summary API", self.test_summary_api),
            ("調度器控制", self.test_scheduler_control),
            ("Provider 設定", self.test_provider_configuration),
            ("Planner 觸發", self.test_planner_trigger),
            ("Worker 觸發", self.test_worker_trigger),
            ("CTO Review 觸發", self.test_cto_review_trigger),
            ("完整任務流程", self.test_task_flow),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            if self.run_test(test_name, test_func):
                passed_tests += 1
            print()  # 空行分隔
        
        # 輸出測試摘要
        logger.info("="*60)
        logger.info("📊 測試結果摘要")
        logger.info(f"總測試數: {total_tests}")
        logger.info(f"通過測試: {passed_tests}")
        logger.info(f"失敗測試: {total_tests - passed_tests}")
        logger.info(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        if self.failed_tests:
            logger.error("❌ 失敗的測試:")
            for test in self.failed_tests:
                logger.error(f"  - {test}")
        else:
            logger.info("🎉 所有測試通過！")
        
        # 保存測試報告
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": passed_tests/total_tests*100
            },
            "test_results": self.test_results,
            "failed_tests": self.failed_tests
        }
        
        report_path = "orchestrator_test_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 測試報告已保存至: {report_path}")
        
        return passed_tests == total_tests


if __name__ == "__main__":
    # 檢查 API 服務器是否運行
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        logger.info("✅ API 服務器已運行")
    except requests.exceptions.RequestException:
        logger.error("❌ API 服務器未運行，請先啟動服務器:")
        logger.error("   python app.py")
        sys.exit(1)
    
    # 執行測試
    tester = OrchestrationTest()
    success = tester.run_all_tests()
    
    # 設定退出碼
    sys.exit(0 if success else 1)
