"""
Betting-pool Orchestrator Scheduler — 四軌自我訓練排程器

軌道架構：
  A/B (planner + worker) : 現有邏輯，處理深度研究 + 模型補丁任務
  Track C (simulation)   : 每 30 分鐘執行模擬壓力測試
  Track D (strategy)     : 每 5 分鐘檢查是否有新驗證結果，有則調整策略參數
"""
from __future__ import annotations

import time
import threading
import logging
from datetime import datetime, timezone
from typing import Optional

from orchestrator import db
from orchestrator import execution_policy
from orchestrator.planner_tick import run_planner_tick
from orchestrator.worker_tick import run_worker_tick
from orchestrator.cto_review_tick import run_cto_review_tick
from orchestrator.simulation_tick import run_simulation_tick
from orchestrator.strategy_tick import run_strategy_tick
from orchestrator.closing_odds_monitor import run_closing_odds_monitor

logger = logging.getLogger(__name__)


class OrchestrationScheduler:
    """任務編排排程器"""
    
    def __init__(self):
        self.planner_interval = 600   # 10 分鐘（Track A+B 深度研究）
        self.worker_interval = 600    # 10 分鐘（執行任務）
        self.cto_interval = 86400     # 24 小時（CTO 審核）
        self.simulation_interval = 1800  # 30 分鐘（Track C 模擬壓力測試）
        self.strategy_interval = 300     # 5 分鐘（Track D 策略反饋，有新洞見才實際調整）
        self.closing_monitor_interval = 900  # 15 分鐘（Phase 7 收盤監控）

        self.planner_thread: Optional[threading.Thread] = None
        self.worker_thread: Optional[threading.Thread] = None
        self.cto_thread: Optional[threading.Thread] = None
        self.simulation_thread: Optional[threading.Thread] = None
        self.strategy_thread: Optional[threading.Thread] = None
        self.closing_monitor_thread: Optional[threading.Thread] = None

        self.running = False
        self.last_planner_run: Optional[datetime] = None
        self.last_worker_run: Optional[datetime] = None
        self.last_cto_run: Optional[datetime] = None
        self.last_simulation_run: Optional[datetime] = None
        self.last_strategy_run: Optional[datetime] = None
        self.last_closing_monitor_run: Optional[datetime] = None
    
    def start(self):
        """啟動排程器"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting Orchestration Scheduler...")
        
        # 啟動 Planner 排程
        self.planner_thread = threading.Thread(
            target=self._run_planner_loop,
            name="OrchestratorPlannerScheduler",
            daemon=True
        )
        self.planner_thread.start()
        
        # 啟動 Worker 排程
        self.worker_thread = threading.Thread(
            target=self._run_worker_loop,
            name="OrchestratorWorkerScheduler",
            daemon=True
        )
        self.worker_thread.start()
        
        # 啟動 CTO 排程
        self.cto_thread = threading.Thread(
            target=self._run_cto_loop,
            name="OrchestratorCTOScheduler",
            daemon=True
        )
        self.cto_thread.start()

        # Track C — 模擬壓力測試
        self.simulation_thread = threading.Thread(
            target=self._run_simulation_loop,
            name="OrchestratorSimulationScheduler",
            daemon=True
        )
        self.simulation_thread.start()

        # Track D — 策略反饋迴圈
        self.strategy_thread = threading.Thread(
            target=self._run_strategy_loop,
            name="OrchestratorStrategyScheduler",
            daemon=True
        )
        self.strategy_thread.start()

        # Phase 7 — 收盤監控：PENDING_CLOSING → COMPUTED
        self.closing_monitor_thread = threading.Thread(
            target=self._run_closing_monitor_loop,
            name="OrchestratorClosingMonitor",
            daemon=True
        )
        self.closing_monitor_thread.start()

        logger.info("Orchestration Scheduler started successfully (5 tracks active)")
    
    def stop(self):
        """停止排程器"""
        if not self.running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping Orchestration Scheduler...")
        self.running = False
        
        # 等待執行緒結束
        if self.planner_thread:
            self.planner_thread.join(timeout=5)
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        if self.cto_thread:
            self.cto_thread.join(timeout=5)
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
        if self.strategy_thread:
            self.strategy_thread.join(timeout=5)
        if self.closing_monitor_thread:
            self.closing_monitor_thread.join(timeout=5)

        logger.info("Orchestration Scheduler stopped")
    
    def _run_planner_loop(self):
        """Planner 排程迴圈"""
        logger.info("Planner scheduler loop started")
        
        while self.running:
            try:
                # 檢查是否應該執行
                if self._should_run_planner():
                    logger.info("Triggering planner tick...")
                    result = run_planner_tick()
                    self.last_planner_run = datetime.now(timezone.utc)
                    logger.info(f"Planner tick completed: {result.get('status')}")
                
                # 等待下次檢查
                time.sleep(30)  # 每30秒檢查一次
                
            except Exception as e:
                logger.error(f"Planner scheduler error: {e}")
                time.sleep(60)  # 錯誤時等待更久
    
    def _run_worker_loop(self):
        """Worker 排程迴圈"""
        logger.info("Worker scheduler loop started")
        
        while self.running:
            try:
                # 檢查是否應該執行
                if self._should_run_worker():
                    logger.info("Triggering worker tick...")
                    result = run_worker_tick()
                    self.last_worker_run = datetime.now(timezone.utc)
                    logger.info(f"Worker tick completed: {result.get('status')}")
                
                # 等待下次檢查
                time.sleep(30)  # 每30秒檢查一次
                
            except Exception as e:
                logger.error(f"Worker scheduler error: {e}")
                time.sleep(60)  # 錯誤時等待更久
    
    def _run_cto_loop(self):
        """CTO Review 排程迴圈"""
        logger.info("CTO scheduler loop started")
        
        while self.running:
            try:
                # 檢查是否應該執行
                if self._should_run_cto():
                    logger.info("Triggering CTO review tick...")
                    result = run_cto_review_tick()
                    self.last_cto_run = datetime.now(timezone.utc)
                    logger.info(f"CTO review tick completed: {result.get('status')}")
                
                # CTO 檢查間隔較長
                time.sleep(300)  # 每5分鐘檢查一次

            except Exception as e:
                logger.error(f"CTO scheduler error: {e}")
                time.sleep(600)  # 錯誤時等待更久

    def _run_simulation_loop(self):
        """Track C — 模擬壓力測試排程迴圈（每 30 分鐘）"""
        logger.info("Simulation scheduler loop started (Track C, interval=%ds)", self.simulation_interval)

        while self.running:
            try:
                if self._should_run_simulation():
                    logger.info("[TrackC] Triggering simulation tick...")
                    result = run_simulation_tick()
                    self.last_simulation_run = datetime.now(timezone.utc)
                    weakness = result.get("weakness_detected", False)
                    logger.info(
                        "[TrackC] Simulation tick completed: status=%s  weakness=%s",
                        result.get("status"), weakness,
                    )

                time.sleep(30)  # 每 30 秒檢查一次

            except Exception as e:
                logger.error("[TrackC] Simulation scheduler error: %s", e)
                time.sleep(60)

    def _run_strategy_loop(self):
        """Track D — 策略反饋排程迴圈（每 5 分鐘，有新洞見才實際調整）"""
        logger.info("Strategy scheduler loop started (Track D, interval=%ds)", self.strategy_interval)

        while self.running:
            try:
                if self._should_run_strategy():
                    result = run_strategy_tick()
                    self.last_strategy_run = datetime.now(timezone.utc)
                    if result.get("status") == "SUCCESS":
                        logger.info(
                            "[TrackD] Strategy tick: processed %d insights  "
                            "confidence=%.2f  exposure=%.2f  revert=%s",
                            result.get("new_insights_processed", 0),
                            result.get("confidence_weight", 1.0),
                            result.get("exposure_level", 0.75),
                            result.get("revert_flag", False),
                        )

                time.sleep(30)  # 每 30 秒輪詢一次

            except Exception as e:
                logger.error("[TrackD] Strategy scheduler error: %s", e)
                time.sleep(60)

    def _run_closing_monitor_loop(self):
        """Phase 7 — 收盤監控排程迴圈（每 15 分鐘）.

        僅掃描 PENDING_CLOSING 紀錄，尋找 closing_ts > prediction_time_utc 的
        有效收盤賠率，升級為 COMPUTED。不重新計算已經 COMPUTED 的紀錄。
        """
        logger.info(
            "Closing monitor loop started (Phase 7, interval=%ds)",
            self.closing_monitor_interval,
        )

        while self.running:
            try:
                if self._should_run_closing_monitor():
                    logger.info("[Phase7] Triggering closing odds monitor...")
                    result = run_closing_odds_monitor()
                    self.last_closing_monitor_run = datetime.now(timezone.utc)
                    stats = result.get("total_stats", {})
                    logger.info(
                        "[Phase7] Closing monitor: dates=%s  pending=%d  upgraded=%d  still_pending=%d",
                        result.get("dates_scanned", []),
                        stats.get("total_pending", 0),
                        stats.get("upgraded", 0),
                        stats.get("still_pending", 0),
                    )

                time.sleep(30)

            except Exception as e:
                logger.error("[Phase7] Closing monitor error: %s", e)
                time.sleep(60)
    
    def _should_run_planner(self) -> bool:
        """判斷是否應該執行 Planner（Track A+B）"""
        decision = execution_policy.evaluate_execution(runner="planner_tick", background=True)
        if not decision["allowed"]:
            return False
        if not self.last_planner_run:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_planner_run).total_seconds()
        return elapsed >= self.planner_interval

    def _should_run_worker(self) -> bool:
        """判斷是否應該執行 Worker"""
        decision = execution_policy.evaluate_execution(runner="worker_tick", background=True)
        if not decision["allowed"]:
            return False
        if not self.last_worker_run:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_worker_run).total_seconds()
        return elapsed >= self.worker_interval

    def _should_run_cto(self) -> bool:
        """判斷是否應該執行 CTO Review"""
        decision = execution_policy.evaluate_execution(
            runner="cto_review_tick",
            background=True,
            scheduler_scope="cto",
        )
        if not decision["allowed"]:
            return False
        if not self.last_cto_run:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_cto_run).total_seconds()
        return elapsed >= self.cto_interval

    def _should_run_simulation(self) -> bool:
        """判斷是否應該執行 Track C 模擬測試"""
        decision = execution_policy.evaluate_execution(runner="simulation_tick", background=True)
        if not decision["allowed"]:
            return False
        track_c_enabled = db.get_setting("track_c_enabled", "1")
        if track_c_enabled != "1":
            return False
        if not self.last_simulation_run:
            return True
        interval = int(db.get_setting("track_c_interval_seconds", str(self.simulation_interval)))
        elapsed = (datetime.now(timezone.utc) - self.last_simulation_run).total_seconds()
        return elapsed >= interval

    def _should_run_strategy(self) -> bool:
        """判斷是否應該執行 Track D 策略反饋"""
        decision = execution_policy.evaluate_execution(runner="strategy_tick", background=True)
        if not decision["allowed"]:
            return False
        track_d_enabled = db.get_setting("track_d_enabled", "1")
        if track_d_enabled != "1":
            return False
        if not self.last_strategy_run:
            return True
        interval = int(db.get_setting("track_d_interval_seconds", str(self.strategy_interval)))
        elapsed = (datetime.now(timezone.utc) - self.last_strategy_run).total_seconds()
        return elapsed >= interval

    def _should_run_closing_monitor(self) -> bool:
        """判斷是否應該執行 Phase 7 收盤監控（每 15 分鐘）"""
        enabled = db.get_setting("phase7_closing_monitor_enabled", "1")
        if enabled != "1":
            return False
        if not self.last_closing_monitor_run:
            return True
        interval = int(db.get_setting(
            "phase7_closing_monitor_interval_seconds",
            str(self.closing_monitor_interval),
        ))
        elapsed = (datetime.now(timezone.utc) - self.last_closing_monitor_run).total_seconds()
        return elapsed >= interval
    
    def get_status(self) -> dict:
        """取得排程器狀態（含四軌 + Phase 7 收盤監控資訊）"""
        runtime_state = execution_policy.get_state()
        return {
            "running": self.running,
            "scheduler_enabled": runtime_state["scheduler_enabled"],
            "cto_scheduler_enabled": runtime_state["cto_scheduler_enabled"],
            "llm_execution_mode": runtime_state["llm_execution_mode"],
            "llm_blocked_count": runtime_state["llm_blocked_count"],
            "track_c_enabled": db.get_setting("track_c_enabled", "1") == "1",
            "track_d_enabled": db.get_setting("track_d_enabled", "1") == "1",
            "phase7_closing_monitor_enabled": db.get_setting("phase7_closing_monitor_enabled", "1") == "1",
            "last_planner_run": self.last_planner_run.isoformat() if self.last_planner_run else None,
            "last_worker_run": self.last_worker_run.isoformat() if self.last_worker_run else None,
            "last_cto_run": self.last_cto_run.isoformat() if self.last_cto_run else None,
            "last_simulation_run": self.last_simulation_run.isoformat() if self.last_simulation_run else None,
            "last_strategy_run": self.last_strategy_run.isoformat() if self.last_strategy_run else None,
            "last_closing_monitor_run": self.last_closing_monitor_run.isoformat() if self.last_closing_monitor_run else None,
            "intervals": {
                "planner": self.planner_interval,
                "worker": self.worker_interval,
                "cto": self.cto_interval,
                "simulation": int(db.get_setting("track_c_interval_seconds", str(self.simulation_interval))),
                "strategy": int(db.get_setting("track_d_interval_seconds", str(self.strategy_interval))),
                "closing_monitor": int(db.get_setting("phase7_closing_monitor_interval_seconds", str(self.closing_monitor_interval))),
            },
        }
    
    def trigger_planner_now(self) -> dict:
        """立即觸發 Planner"""
        logger.info("Manual planner trigger requested")
        result = run_planner_tick()
        self.last_planner_run = datetime.now(timezone.utc)
        return result
    
    def trigger_worker_now(self) -> dict:
        """立即觸發 Worker"""
        logger.info("Manual worker trigger requested")
        result = run_worker_tick()
        self.last_worker_run = datetime.now(timezone.utc)
        return result
    
    def trigger_cto_now(self, force: bool = False) -> dict:
        """立即觸發 CTO Review"""
        logger.info(f"Manual CTO review trigger requested (force={force})")
        result = run_cto_review_tick(force=force)
        self.last_cto_run = datetime.now(timezone.utc)
        return result

    def trigger_simulation_now(self) -> dict:
        """立即觸發 Track C 模擬壓力測試"""
        logger.info("Manual Track C simulation trigger requested")
        result = run_simulation_tick()
        self.last_simulation_run = datetime.now(timezone.utc)
        return result

    def trigger_strategy_now(self) -> dict:
        """立即觸發 Track D 策略反饋"""
        logger.info("Manual Track D strategy trigger requested")
        result = run_strategy_tick()
        self.last_strategy_run = datetime.now(timezone.utc)
        return result

    def trigger_closing_monitor_now(self) -> dict:
        """手動立即觸發 Phase 7 收盤監控（升級 PENDING_CLOSING → COMPUTED）"""
        logger.info("[Phase7] Manual closing monitor trigger requested")
        result = run_closing_odds_monitor()
        self.last_closing_monitor_run = datetime.now(timezone.utc)
        return result


# 全域排程器實例
_scheduler_instance: Optional[OrchestrationScheduler] = None


def get_scheduler() -> OrchestrationScheduler:
    """取得排程器實例（單例模式）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = OrchestrationScheduler()
    return _scheduler_instance


def start_scheduler():
    """啟動排程器"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """停止排程器"""
    scheduler = get_scheduler()
    scheduler.stop()


def get_scheduler_status() -> dict:
    """取得排程器狀態"""
    scheduler = get_scheduler()
    return scheduler.get_status()


if __name__ == "__main__":
    # 直接測試執行
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 初始化資料庫
    db.init_db()
    
    # 啟動排程器
    scheduler = get_scheduler()
    scheduler.start()
    
    try:
        # 保持運行
        while True:
            status = scheduler.get_status()
            logger.info(f"Scheduler status: {status}")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()
