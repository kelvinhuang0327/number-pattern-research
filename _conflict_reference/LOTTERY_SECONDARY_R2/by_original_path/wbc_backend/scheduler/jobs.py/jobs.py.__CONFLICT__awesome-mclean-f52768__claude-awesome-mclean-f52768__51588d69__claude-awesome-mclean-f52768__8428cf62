"""
Automated Scheduler — § 七 自動訓練排程系統

Task                Frequency
────────────────    ────────────
Data refresh        Every 1 hour
Model retrain       Daily
Weight adjustment   Weekly
Backtest            Daily
Self-improvement    Weekly
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from wbc_backend.config.settings import AppConfig

logger = logging.getLogger(__name__)


class ScheduledTask:
    """A single scheduled task with interval and callback."""

    def __init__(self, name: str, interval_seconds: int, callback: Callable):
        self.name = name
        self.interval_seconds = interval_seconds
        self.callback = callback
        self.last_run: float = 0.0
        self.run_count: int = 0
        self.last_error: str | None = None

    @property
    def is_due(self) -> bool:
        return (time.time() - self.last_run) >= self.interval_seconds

    def execute(self):
        logger.info("[SCHEDULER] Running task: %s", self.name)
        try:
            self.callback()
            self.last_run = time.time()
            self.run_count += 1
            self.last_error = None
            logger.info("[SCHEDULER] Task %s completed (run #%d)", self.name, self.run_count)
        except Exception as e:
            self.last_error = str(e)
            logger.error("[SCHEDULER] Task %s failed: %s", self.name, e)


class AutoScheduler:
    """
    Non-blocking scheduler that runs tasks at configured intervals.

    Usage:
        scheduler = AutoScheduler()
        scheduler.setup_default_tasks()
        scheduler.start()        # Runs in background
        ...
        scheduler.stop()
    """

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()
        self.tasks: list[ScheduledTask] = []
        self._running = False
        self._thread: threading.Thread | None = None

    def add_task(self, name: str, interval_seconds: int, callback: Callable):
        self.tasks.append(ScheduledTask(name, interval_seconds, callback))
        logger.info("[SCHEDULER] Task registered: %s (every %ds)", name, interval_seconds)

    def setup_default_tasks(self):
        """Register all default automated tasks."""
        sc = self.config.scheduler

        # ── Data Refresh (hourly) ────────────────────────
        def data_refresh():
            from wbc_backend.data.validator import auto_fetch_missing_data
            auto_fetch_missing_data("MLB_2025", self.config)

        self.add_task("data_refresh", sc.data_refresh_interval_hours * 3600, data_refresh)

        # ── Model Retrain (daily) ────────────────────────
        def model_retrain():
            from wbc_backend.models.trainer import auto_train_models
            auto_train_models(self.config)

        self.add_task("model_retrain", sc.model_retrain_interval_hours * 3600, model_retrain)

        # ── Weight Adjustment (weekly) ───────────────────
        def weight_adjust():
            from wbc_backend.models.stacking import optimize_model_weights
            optimize_model_weights()

        self.add_task("weight_adjust", sc.weight_adjust_interval_hours * 3600, weight_adjust)

        # ── Backtest (daily) ─────────────────────────────
        def backtest():
            from wbc_backend.evaluation.backtester import run_full_backtest
            run_full_backtest()

        self.add_task("backtest", sc.backtest_interval_hours * 3600, backtest)

        # ── Self-improvement (weekly) ────────────────────
        def self_improve():
            from wbc_backend.optimization.self_improve import self_improve as si
            si(config=self.config)

        self.add_task("self_improve", sc.self_improve_interval_hours * 3600, self_improve)

        # ── V3 Research Cycle (daily) ────────────────────
        def research_cycle():
            from wbc_backend.research.runtime import run_research_cycle
            run_research_cycle(seed=42)

        self.add_task("research_cycle", sc.research_cycle_interval_hours * 3600, research_cycle)

        # ── Postgame Sync (every 2h) — 賽後閉環核心 ─────
        def postgame_sync():
            from scripts.run_postgame_sync import sync_completed_games
            synced = sync_completed_games(config=self.config)
            if synced:
                logger.info("[SCHEDULER] Postgame sync: %d new games recorded", len(synced))

        self.add_task("postgame_sync", sc.postgame_sync_interval_hours * 3600, postgame_sync)

        # ── ML Artifact Rebuild (weekly) — gate artifact 保鮮 ──
        def artifact_rebuild():
            from scripts.rebuild_ml_artifacts import rebuild_walkforward, rebuild_calibration, verify_artifacts
            data_path = self.config.sources.mlb_2025_csv
            wf = rebuild_walkforward(data_path)
            cal = rebuild_calibration(data_path)
            ok = verify_artifacts(wf, cal)
            logger.info(
                "[SCHEDULER] Artifact rebuild %s: wf_ece=%.4f",
                "OK" if ok else "FAILED",
                wf.get("ece", float("nan")),
            )

        self.add_task("artifact_rebuild", sc.artifact_rebuild_interval_hours * 3600, artifact_rebuild)

    def run_once(self):
        """Run all due tasks once (non-blocking)."""
        for task in self.tasks:
            if task.is_due:
                task.execute()

    def run_all_now(self):
        """Force run all tasks immediately."""
        logger.info("[SCHEDULER] Force-running all %d tasks", len(self.tasks))
        for task in self.tasks:
            task.execute()

    def start(self, poll_interval: int = 60):
        """Start the scheduler in a background thread."""
        if self._running:
            logger.warning("[SCHEDULER] Already running")
            return

        self._running = True

        def _loop():
            logger.info("[SCHEDULER] Started with %d tasks", len(self.tasks))
            while self._running:
                self.run_once()
                time.sleep(poll_interval)
            logger.info("[SCHEDULER] Stopped")

        self._thread = threading.Thread(target=_loop, daemon=True, name="wbc-scheduler")
        self._thread.start()

    def stop(self):
        """Stop the background scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def status(self) -> dict:
        """Return current scheduler status."""
        return {
            "running": self._running,
            "tasks": [
                {
                    "name": t.name,
                    "interval_seconds": t.interval_seconds,
                    "run_count": t.run_count,
                    "last_error": t.last_error,
                    "is_due": t.is_due,
                }
                for t in self.tasks
            ],
        }
