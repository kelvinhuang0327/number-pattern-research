"""
Orchestrator standalone DB manager.
Uses its own SQLite file (orchestrator.db) — no dependency on lottery_api.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

ORCH_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "runtime", "agent_orchestrator")
DB_PATH = os.path.join(ORCH_ROOT, "orchestrator.db")

DEFAULT_SETTINGS = {
    "scheduler_enabled": "1",
    "llm_hard_off": "0",
    "llm_execution_mode": "safe-run",
    "planner_provider": "claude",
    "worker_provider": "codex",
    "worker_copilot_model": "",
    "cto_review_frequency_mode": "once_daily",
    "cto_scheduler_enabled": "1",
    "cto_planner_provider": "claude",
    "cto_planner_model": "",
}
RUN_HISTORY_RETENTION = int(os.environ.get("ORCH_RUN_HISTORY_RETENTION", "5000"))
CTO_REVIEW_STALE_SECONDS = int(os.environ.get("CTO_REVIEW_STALE_SECONDS", "3600"))
CTO_RUN_TERMINAL_STATUSES = {
    "COMPLETED",
    "SKIPPED",
    "FAILED",
    "FAILED_STALE",
    "SKIPPED_STALE",
}


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _is_pid_alive(pid) -> bool:
    if pid in (None, "", 0):
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _derive_cto_run_status(row: dict) -> str:
    status = str(row.get("status") or "").strip().upper()
    if status:
        return status
    if row.get("completed_at"):
        return "SKIPPED" if int(row.get("candidate_count") or 0) == 0 else "COMPLETED"
    return "RUNNING"


def _enrich_cto_review_run(row):
    if not row:
        return None
    data = dict(row)
    data["status"] = _derive_cto_run_status(data)
    data["outcome"] = data.get("outcome") or None
    data["outcome_message"] = data.get("outcome_message") or data.get("summary") or ""
    data["pid_alive"] = _is_pid_alive(data.get("pid")) if data.get("status") == "RUNNING" else False
    return data


def _is_cto_run_stale(row, stale_seconds: Optional[int] = None):
    stale_after = int(stale_seconds or CTO_REVIEW_STALE_SECONDS)
    data = dict(row)
    if _derive_cto_run_status(data) in CTO_RUN_TERMINAL_STATUSES:
        return False
    if data.get("completed_at"):
        return False
    pid = data.get("pid")
    if pid:
        return not _is_pid_alive(pid)
    started_at = _parse_iso(data.get("started_at")) or _parse_iso(data.get("created_at"))
    if not started_at:
        return False
    return (datetime.now(timezone.utc) - started_at) >= timedelta(seconds=stale_after)


def cleanup_stale_cto_review_runs(dedupe_key: str = None, stale_seconds: int = None, stale_reason: str = "stale in-flight run blocked duplicate guard"):
    stale_after = int(stale_seconds or CTO_REVIEW_STALE_SECONDS)
    conn = get_conn()
    stale_runs = []
    try:
        params = []
        sql = "SELECT * FROM cto_review_runs WHERE completed_at IS NULL"
        if dedupe_key:
            sql += " AND dedupe_key = ?"
            params.append(dedupe_key)
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            data = dict(row)
            if not _is_cto_run_stale(data, stale_after):
                continue
            now = datetime.now(timezone.utc).isoformat()
            started_at = _parse_iso(data.get("started_at")) or datetime.now(timezone.utc)
            duration = max(0, int((datetime.now(timezone.utc) - started_at).total_seconds()))
            summary = data.get("summary") or f"Stale in-flight run auto-terminalized: {stale_reason}"
            conn.execute(
                """
                UPDATE cto_review_runs
                   SET completed_at = ?,
                       duration_seconds = ?,
                       summary = ?,
                       status = ?,
                       outcome = ?,
                       outcome_message = ?,
                       updated_at = ?
                 WHERE run_id = ?
                """,
                (now, duration, summary, "FAILED_STALE", "CTO_REVIEW_STALE", stale_reason, now, data["run_id"]),
            )
            stale_runs.append(data["run_id"])
        conn.commit()
    finally:
        conn.close()
    for run_id in stale_runs:
        log_tick("cto-review", "CTO_REVIEW_STALE", message=f"{run_id}: {stale_reason}")
    return stale_runs


def get_conn():
    os.makedirs(ORCH_ROOT, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_key TEXT UNIQUE NOT NULL,
                date_folder TEXT NOT NULL,
                title TEXT,
                slug TEXT,
                status TEXT NOT NULL DEFAULT 'QUEUED',
                previous_task_id INTEGER,
                prompt_file_path TEXT,
                prompt_text TEXT,
                completed_file_path TEXT,
                completed_text TEXT,
                changed_files_json TEXT,
                worker_pid INTEGER,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds INTEGER,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (previous_task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_status ON agent_tasks(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_date ON agent_tasks(date_folder)")

        # Migration: add dedupe_key + regime columns to agent_tasks if upgrading existing DB
        existing_at_cols = {row["name"] for row in c.execute("PRAGMA table_info(agent_tasks)").fetchall()}
        for col_def in [
            ("dedupe_key", "TEXT"),
            ("regime_state", "TEXT"),
            ("confidence_snapshot", "REAL"),
            ("epoch_id", "INTEGER NOT NULL DEFAULT 0"),
            ("failure_category", "TEXT"),
            ("failure_weight", "REAL"),
            ("repair_target_task_id", "INTEGER"),
            ("repair_success", "INTEGER"),
            ("repair_attempt", "INTEGER"),
            ("repair_effectiveness_score", "REAL"),
            ("value_score", "REAL"),
            ("gate_verdict", "TEXT"),
        ]:
            if col_def[0] not in existing_at_cols:
                c.execute(f"ALTER TABLE agent_tasks ADD COLUMN {col_def[0]} {col_def[1]}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_dedupe ON agent_tasks(dedupe_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_regime ON agent_tasks(regime_state)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_epoch  ON agent_tasks(epoch_id)")

        # Migration: multi-worker concurrency — worker_type column on agent_tasks
        existing_at_cols2 = {row["name"] for row in c.execute("PRAGMA table_info(agent_tasks)").fetchall()}
        if "worker_type" not in existing_at_cols2:
            c.execute("ALTER TABLE agent_tasks ADD COLUMN worker_type TEXT DEFAULT 'research'")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_worker_type ON agent_tasks(worker_type)")

        # Planner dedupe state table (one row per dedupe_key, tracks last confidence)
        c.execute("""
            CREATE TABLE IF NOT EXISTS planner_dedupe_state (
                dedupe_key         TEXT PRIMARY KEY,
                last_regime_state  TEXT,
                last_confidence    REAL,
                last_task_id       INTEGER,
                last_emitted_at    TEXT,
                skip_count         INTEGER NOT NULL DEFAULT 0,
                updated_at         TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                runner TEXT NOT NULL,
                tick_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                request_id TEXT,
                task_id INTEGER,
                message TEXT,
                duration_ms INTEGER,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_runner ON agent_task_runs(runner)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_tick ON agent_task_runs(tick_at)")
        existing_run_cols = {row["name"] for row in c.execute("PRAGMA table_info(agent_task_runs)").fetchall()}
        if "request_id" not in existing_run_cols:
            c.execute("ALTER TABLE agent_task_runs ADD COLUMN request_id TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_request_id ON agent_task_runs(request_id)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_locks (
                runner TEXT PRIMARY KEY,
                pid INTEGER,
                task_id INTEGER,
                started_at TEXT,
                heartbeat_at TEXT
            )
        """)

        # Migration: multi-worker concurrency — lock_type column on agent_locks
        existing_lock_cols = {row["name"] for row in c.execute("PRAGMA table_info(agent_locks)").fetchall()}
        if "lock_type" not in existing_lock_cols:
            c.execute("ALTER TABLE agent_locks ADD COLUMN lock_type TEXT DEFAULT 'research'")

        # Adaptive scheduling — worker_metrics table
        c.execute("""
            CREATE TABLE IF NOT EXISTS worker_metrics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sampled_at  TEXT NOT NULL,
                worker_type TEXT NOT NULL,          -- 'research' | 'light'
                active_count    INTEGER NOT NULL DEFAULT 0,
                queued_count    INTEGER NOT NULL DEFAULT 0,
                completed_count INTEGER NOT NULL DEFAULT 0,
                failed_count    INTEGER NOT NULL DEFAULT 0,
                avg_latency_s   REAL,               -- avg task duration over last window
                throughput_ph   REAL,               -- tasks completed per hour
                cpu_pct         REAL,               -- system CPU % at sample time
                slot_limit      INTEGER NOT NULL DEFAULT 3,  -- MAX_LIGHT_WORKERS in effect
                backpressure    INTEGER NOT NULL DEFAULT 0,  -- 1 if backpressure active
                -- v2: extended metrics
                cpu_share_pct   REAL,               -- estimated CPU% attributed to this worker_type
                research_latency_s REAL,            -- avg research task latency at sample time
                starvation_incidents INTEGER NOT NULL DEFAULT 0,  -- light queue>threshold while active=0
                slot_decision_reason TEXT            -- human-readable reason string from adaptive scheduler
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_wm_sampled ON worker_metrics(sampled_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wm_type ON worker_metrics(worker_type)")
        # Migrate existing tables: add v2 columns if they don't exist yet
        _existing_wm_cols = {r[1] for r in c.execute('PRAGMA table_info(worker_metrics)').fetchall()}
        for _col, _typedef in [
            ("cpu_share_pct",           "REAL"),
            ("research_latency_s",      "REAL"),
            ("starvation_incidents",    "INTEGER NOT NULL DEFAULT 0"),
            ("slot_decision_reason",    "TEXT"),
        ]:
            if _col not in _existing_wm_cols:
                c.execute(f"ALTER TABLE worker_metrics ADD COLUMN {_col} {_typedef}")

        # Adaptive scheduling — scheduling_state table (one row per key)
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduling_state (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        now = datetime.now(timezone.utc).isoformat()
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO orchestrator_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )

        c.execute("""
            CREATE TABLE IF NOT EXISTS task_git_commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER UNIQUE NOT NULL,
                slot_key TEXT NOT NULL,
                task_title TEXT,
                source_branch TEXT,
                commit_sha TEXT UNIQUE,
                commit_message TEXT,
                integration_group TEXT,
                review_priority TEXT,
                safe_to_autocommit INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                reviewer_role TEXT,
                reviewed_at TEXT,
                merge_branch TEXT,
                merge_commit_sha TEXT,
                reject_reason TEXT,
                superseded_by_task_id INTEGER,
                superseded_by_commit_sha TEXT,
                changed_files_json TEXT,
                depends_on_tasks_json TEXT,
                depends_on_commits_json TEXT,
                high_conflict_paths_json TEXT,
                task_status TEXT,
                gate_verdict TEXT,
                gate_reason TEXT,
                manual_merge_required INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_status ON task_git_commits(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_task_id ON task_git_commits(task_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_commit_sha ON task_git_commits(commit_sha)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_group ON task_git_commits(integration_group)")

        # Migration: add manual_merge_required column if upgrading existing DB
        existing_tgc_cols = {row["name"] for row in c.execute("PRAGMA table_info(task_git_commits)").fetchall()}
        if "manual_merge_required" not in existing_tgc_cols:
            c.execute("ALTER TABLE task_git_commits ADD COLUMN manual_merge_required INTEGER NOT NULL DEFAULT 0")

        c.execute("""
            CREATE TABLE IF NOT EXISTS task_git_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commit_sha TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                review_run_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                checked_from TEXT,
                checked_until TEXT,
                review_summary TEXT,
                decision_steps_json TEXT,
                reviewer_role TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgr_commit_sha ON task_git_reviews(commit_sha)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgr_task_id ON task_git_reviews(task_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgr_run_id ON task_git_reviews(review_run_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgr_decision ON task_git_reviews(decision)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS cto_review_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                frequency_mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_seconds INTEGER,
                checked_from TEXT,
                checked_until TEXT,
                candidate_count INTEGER DEFAULT 0,
                approved_count INTEGER DEFAULT 0,
                merged_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0,
                deferred_count INTEGER DEFAULT 0,
                superseded_count INTEGER DEFAULT 0,
                duplicate_count INTEGER DEFAULT 0,
                merge_branch TEXT,
                report_md_path TEXT,
                report_json_path TEXT,
                summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_started ON cto_review_runs(started_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_completed ON cto_review_runs(completed_at)")

        # Migration: add dedupe_key, is_manual, is_force_run, run_intent, parent_run_id columns if upgrading existing DB
        existing_cto_run_cols = {row["name"] for row in c.execute("PRAGMA table_info(cto_review_runs)").fetchall()}
        for col_def in [
            ("dedupe_key", "TEXT"),
            ("is_manual", "INTEGER NOT NULL DEFAULT 0"),
            ("is_force_run", "INTEGER NOT NULL DEFAULT 0"),
            ("run_intent", "TEXT"),
            ("parent_run_id", "TEXT"),
            ("status", "TEXT"),
            ("outcome", "TEXT"),
            ("outcome_message", "TEXT"),
            ("pid", "INTEGER"),
            ("request_id", "TEXT"),
        ]:
            if col_def[0] not in existing_cto_run_cols:
                c.execute(f"ALTER TABLE cto_review_runs ADD COLUMN {col_def[0]} {col_def[1]}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_dedupe ON cto_review_runs(dedupe_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_intent ON cto_review_runs(run_intent)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_status ON cto_review_runs(status)")

        # Intent outcome learning signal table
        c.execute("""
            CREATE TABLE IF NOT EXISTS cto_intent_signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT NOT NULL,
                run_intent  TEXT NOT NULL,
                outcome     TEXT NOT NULL,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                merged_count    INTEGER NOT NULL DEFAULT 0,
                rejected_count  INTEGER NOT NULL DEFAULT 0,
                deferred_count  INTEGER NOT NULL DEFAULT 0,
                approved_count  INTEGER NOT NULL DEFAULT 0,
                is_compare_only INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_intent_signals_intent ON cto_intent_signals(run_intent)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_intent_signals_created ON cto_intent_signals(created_at)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS cto_backlog_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id TEXT UNIQUE NOT NULL,
                cto_run_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'cto_review',
                severity TEXT,
                impact_score INTEGER,
                urgency TEXT,
                category TEXT,
                suggested_action TEXT,
                task_id INTEGER,
                task_slot_key TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                priority_score REAL NOT NULL DEFAULT 0,
                priority_level TEXT NOT NULL DEFAULT 'P3',
                rank INTEGER,
                -- Execution policy fields
                last_selected_at TEXT,
                selection_count INTEGER NOT NULL DEFAULT 0,
                aging_bonus REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cbi_cto_run_id ON cto_backlog_items(cto_run_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cbi_finding_id ON cto_backlog_items(finding_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cbi_status ON cto_backlog_items(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cbi_task_id ON cto_backlog_items(task_id)")
        # NOTE: idx_cbi_priority is created AFTER migration (see below) because
        # priority_level may not exist yet in an existing DB at this point.

        # Execution policy state table (single-row config + rolling window)
        c.execute("""
            CREATE TABLE IF NOT EXISTS execution_policy_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT NOT NULL DEFAULT 'balanced',
                consecutive_high INTEGER NOT NULL DEFAULT 0,
                consecutive_category TEXT,
                consecutive_category_count INTEGER NOT NULL DEFAULT 0,
                recent_selections TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Seed with one row if not present
        c.execute(
            "INSERT OR IGNORE INTO execution_policy_state (id, mode, updated_at) VALUES (1, 'balanced', ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )

        # Self-Optimizing Decision Architect: adaptive policy state (single-row)
        c.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_policy_state (
                id                     INTEGER PRIMARY KEY CHECK (id = 1),
                retry_coverage_limit   INTEGER NOT NULL DEFAULT 200,
                retry_merge_rate       REAL    NOT NULL DEFAULT 0.0,
                override_merge_rate    REAL    NOT NULL DEFAULT 0.0,
                compare_approved_rate  REAL    NOT NULL DEFAULT 0.0,
                overall_merge_rate     REAL    NOT NULL DEFAULT 0.0,
                category_priority_boosts TEXT  NOT NULL DEFAULT '{}',
                suggestions            TEXT    NOT NULL DEFAULT '[]',
                policy_confidence      TEXT    NOT NULL DEFAULT 'low',
                runs_analyzed          INTEGER NOT NULL DEFAULT 0,
                computed_at            TEXT
            )
        """)
        c.execute(
            "INSERT OR IGNORE INTO adaptive_policy_state (id, computed_at) VALUES (1, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        # Migration: new columns for existing DBs
        existing_aps_cols = {r["name"] for r in c.execute("PRAGMA table_info(adaptive_policy_state)").fetchall()}
        for _col in [
            ("compare_approved_rate", "REAL NOT NULL DEFAULT 0.0"),
            ("overall_merge_rate",    "REAL NOT NULL DEFAULT 0.0"),
        ]:
            if _col[0] not in existing_aps_cols:
                c.execute(f"ALTER TABLE adaptive_policy_state ADD COLUMN {_col[0]} {_col[1]}")

        # ── Signal Classifier Calibration ─────────────────────────────────────
        # Records each classification event + outcome for accuracy tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS classifier_calibration_log (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                classified_at          TEXT    NOT NULL,
                state                  TEXT    NOT NULL,
                confidence_score       REAL    NOT NULL DEFAULT 0.5,
                confidence_label       TEXT    NOT NULL DEFAULT 'uncertain',
                reason                 TEXT,
                features_json          TEXT    NOT NULL DEFAULT '{}',
                thresholds_json        TEXT    NOT NULL DEFAULT '{}',
                outcome_verified_at    TEXT,
                outcome_state          TEXT,
                outcome_draws_checked  INTEGER,
                is_correct             INTEGER,
                fp_fn_type             TEXT,
                threshold_adjusted     INTEGER NOT NULL DEFAULT 0,
                notes                  TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ccl_state      ON classifier_calibration_log(state)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ccl_classified ON classifier_calibration_log(classified_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ccl_outcome    ON classifier_calibration_log(is_correct)")

        # ── Classifier Thresholds (single-row, dynamically adjusted) ─────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS classifier_thresholds (
                id                          INTEGER PRIMARY KEY CHECK (id = 1),
                cold_streak_ratio           REAL    NOT NULL DEFAULT 0.5,
                cold_edge_long_min          REAL    NOT NULL DEFAULT 0.0,
                cold_edge_short_max         REAL    NOT NULL DEFAULT 0.0,
                cold_edge_absolute_max      REAL    NOT NULL DEFAULT -0.05,
                cold_min_total_strategies   INTEGER NOT NULL DEFAULT 2,
                exhausted_max_runs_analyzed INTEGER NOT NULL DEFAULT 0,
                weight_cold_streak          REAL    NOT NULL DEFAULT 1.0,
                weight_edge_divergence      REAL    NOT NULL DEFAULT 1.5,
                weight_policy_support       REAL    NOT NULL DEFAULT 0.5,
                total_classifications       INTEGER NOT NULL DEFAULT 0,
                correct_classifications     INTEGER NOT NULL DEFAULT 0,
                cold_fp_count               INTEGER NOT NULL DEFAULT 0,
                cold_fn_count               INTEGER NOT NULL DEFAULT 0,
                saturated_fp_count          INTEGER NOT NULL DEFAULT 0,
                last_calibrated_at          TEXT,
                updated_at                  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute(
            "INSERT OR IGNORE INTO classifier_thresholds (id, updated_at) VALUES (1, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )

        # Migration: add columns if upgrading existing DB
        existing_cbi_cols = {row["name"] for row in c.execute("PRAGMA table_info(cto_backlog_items)").fetchall()}
        for col_def in [
            ("task_slot_key", "TEXT"),
            ("priority_score", "REAL NOT NULL DEFAULT 0"),
            ("priority_level", "TEXT NOT NULL DEFAULT 'P3'"),
            ("rank", "INTEGER"),
            ("last_selected_at", "TEXT"),
            ("selection_count", "INTEGER NOT NULL DEFAULT 0"),
            ("aging_bonus", "REAL NOT NULL DEFAULT 0"),
        ]:
            if col_def[0] not in existing_cbi_cols:
                c.execute(f"ALTER TABLE cto_backlog_items ADD COLUMN {col_def[0]} {col_def[1]}")

        # Create priority index AFTER migration so priority_level is guaranteed to exist
        c.execute("CREATE INDEX IF NOT EXISTS idx_cbi_priority ON cto_backlog_items(priority_level, priority_score DESC)")

        # ── System Epochs ─────────────────────────────────────────────────────
        # Tracks learning baseline resets.  epoch_id=0 = pre-baseline (legacy).
        c.execute("""
            CREATE TABLE IF NOT EXISTS system_epochs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                epoch_label TEXT    NOT NULL,
                epoch_note  TEXT,
                started_at  TEXT    NOT NULL,
                is_current  INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_epochs_current ON system_epochs(is_current)")
        # Seed epoch 0 (pre-baseline) if no epochs exist yet
        if not c.execute("SELECT 1 FROM system_epochs LIMIT 1").fetchone():
            c.execute(
                "INSERT INTO system_epochs (id, epoch_label, epoch_note, started_at, is_current) VALUES (0, 'pre_baseline', 'Legacy data before epoch system', ?, 0)",
                (datetime.now(timezone.utc).isoformat(),),
            )

        # Migration: add epoch_id to key learning tables
        for _tbl, _default in [
            ("agent_task_runs",          "INTEGER NOT NULL DEFAULT 0"),
            ("cto_review_runs",          "INTEGER NOT NULL DEFAULT 0"),
            ("cto_intent_signals",       "INTEGER NOT NULL DEFAULT 0"),
            ("classifier_calibration_log", "INTEGER NOT NULL DEFAULT 0"),
            ("cto_backlog_items",        "INTEGER NOT NULL DEFAULT 0"),
        ]:
            _existing = {r["name"] for r in c.execute(f"PRAGMA table_info({_tbl})").fetchall()}
            if "epoch_id" not in _existing:
                c.execute(f"ALTER TABLE {_tbl} ADD COLUMN epoch_id {_default}")
            _idx_name = f"idx_{_tbl[:12]}_epoch"
            c.execute(f"CREATE INDEX IF NOT EXISTS {_idx_name} ON {_tbl}(epoch_id)")

        # ── Strategy Review ────────────────────────────────────────────────────
        # Independent of code review; evaluates Deep Research tasks for strategy quality.
        c.execute("""
            CREATE TABLE IF NOT EXISTS strategy_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                task_title TEXT,
                review_run_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                game_type TEXT,
                strategy_name TEXT,
                edge_score REAL,
                sharpe_ratio REAL,
                drawdown REAL,
                mc_passed INTEGER,
                comparison_summary TEXT,
                reviewer_role TEXT NOT NULL DEFAULT 'cto-strategy',
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sr_task_id   ON strategy_reviews(task_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sr_decision  ON strategy_reviews(decision)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sr_run_id    ON strategy_reviews(review_run_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sr_game_type ON strategy_reviews(game_type)")

        # ── Active Strategy State ─────────────────────────────────────────────
        # One row per game_type; tracks active / shadow strategy per game.
        c.execute("""
            CREATE TABLE IF NOT EXISTS active_strategy_state (
                game_type TEXT PRIMARY KEY,
                active_strategy TEXT,
                active_edge REAL,
                active_task_id INTEGER,
                shadow_strategy TEXT,
                shadow_edge REAL,
                shadow_task_id INTEGER,
                planner_focus TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # ── Planner Directives (CTO → Planner) ───────────────────────────────
        # CTO writes directives after strategy reviews; Planner reads them on
        # each planning cycle to avoid dead signal families and focus research.
        c.execute("""
            CREATE TABLE IF NOT EXISTS planner_directives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                directive_id TEXT UNIQUE NOT NULL,
                game_type TEXT,
                focus_direction TEXT NOT NULL,
                forbidden_families TEXT NOT NULL DEFAULT '[]',
                required_validation TEXT NOT NULL DEFAULT '[]',
                promotion_targets TEXT NOT NULL DEFAULT '[]',
                kill_targets TEXT NOT NULL DEFAULT '[]',
                budget_hint TEXT,
                note TEXT,
                expires_after_cycles INTEGER NOT NULL DEFAULT 10,
                cycle_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_pd_game_type  ON planner_directives(game_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pd_is_active  ON planner_directives(is_active)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pd_created    ON planner_directives(created_at)")

        # ── Planner Negative Space Memory ─────────────────────────────────────
        # Tracks per-key quality-failure history for progressive suppression.
        c.execute("""
            CREATE TABLE IF NOT EXISTS planner_negative_space (
                dedupe_key          TEXT    NOT NULL,
                scope               TEXT    NOT NULL DEFAULT 'key',
                fail_count          INTEGER NOT NULL DEFAULT 0,
                last_outcome        TEXT,
                last_fail_at        TEXT,
                suppressed_until    TEXT,
                suppression_reason  TEXT,
                updated_at          TEXT    NOT NULL,
                PRIMARY KEY (dedupe_key, scope)
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_pns_scope ON planner_negative_space(scope)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_pns_until ON planner_negative_space(suppressed_until)"
        )

        # ── Self-tuning scheduler tables ──────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_tunable_params (
                param           TEXT PRIMARY KEY,
                value           REAL NOT NULL,
                default_value   REAL NOT NULL,
                min_value       REAL NOT NULL,
                max_value       REAL NOT NULL,
                step_size       REAL NOT NULL DEFAULT 1.0,
                last_direction  INTEGER NOT NULL DEFAULT 0,   -- +1, -1, or 0
                cooldown_until  TEXT,                         -- ISO ts; block changes until this
                update_count    INTEGER NOT NULL DEFAULT 0,
                ewma_reward     REAL,                         -- smoothed reward signal
                last_reward     REAL,                         -- instantaneous reward at last update
                updated_at      TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_tuning_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at       TEXT NOT NULL,
                action          TEXT NOT NULL,     -- 'adjust' | 'skip' | 'explore'
                param           TEXT,
                old_value       REAL,
                new_value       REAL,
                direction       INTEGER,
                reward          REAL,
                ewma_reward     REAL,
                reason          TEXT,
                is_exploration  INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_stl_logged ON scheduler_tuning_log(logged_at DESC)")

        # Migrate: add governance columns to scheduler_tunable_params if not present
        _existing_stp_cols = {r[1] for r in c.execute('PRAGMA table_info(scheduler_tunable_params)').fetchall()}
        for _col, _typedef in [
            ("previous_value",  "REAL"),
            ("rollback_count",  "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if _col not in _existing_stp_cols:
                c.execute(f"ALTER TABLE scheduler_tunable_params ADD COLUMN {_col} {_typedef}")

        # ── Outcome-aware scheduler: task outcomes + per-type ROI state ──────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS task_outcomes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id             INTEGER NOT NULL,
                task_type           TEXT NOT NULL,          -- 'deep_research' | 'monitoring' | 'governance' | …
                success             INTEGER NOT NULL DEFAULT 0,   -- 1=success  0=failure
                quality_score       REAL,                   -- 0..1 task output quality
                roi_score           REAL,                   -- 0..1 return on investment
                edge_score          REAL,                   -- best raw strategy edge (research tasks)
                extraction_method   TEXT DEFAULT 'heuristic',  -- 'real' | 'heuristic' | 'fallback'
                best_edge           REAL,                   -- normalised best edge vs incumbent [0..1]
                strategies_found    INTEGER DEFAULT 0,      -- # strategies with positive edge
                mc_pass_count       INTEGER DEFAULT 0,      -- # strategies that passed MC robustness
                confidence_score    REAL DEFAULT 1.0,       -- 0..1 validation layer trust score
                recorded_at         TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_to_task_id   ON task_outcomes(task_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_to_task_type ON task_outcomes(task_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_to_recorded  ON task_outcomes(recorded_at DESC)")
        # Migrate: add new columns to existing table if they don't exist yet
        _to_cols = {r[1] for r in c.execute("PRAGMA table_info(task_outcomes)").fetchall()}
        for _col, _typ in [
            ("extraction_method", "TEXT DEFAULT 'heuristic'"),
            ("best_edge",         "REAL"),
            ("strategies_found",  "INTEGER DEFAULT 0"),
            ("mc_pass_count",     "INTEGER DEFAULT 0"),
            ("confidence_score",  "REAL DEFAULT 1.0"),
        ]:
            if _col not in _to_cols:
                c.execute(f"ALTER TABLE task_outcomes ADD COLUMN {_col} {_typ}")

        c.execute("""
            CREATE TABLE IF NOT EXISTS task_type_roi_state (
                task_type       TEXT PRIMARY KEY,
                ewma_quality    REAL NOT NULL DEFAULT 0.5,   -- smoothed quality score
                ewma_roi        REAL NOT NULL DEFAULT 0.5,   -- smoothed ROI
                ewma_success    REAL NOT NULL DEFAULT 0.5,   -- smoothed success rate
                sample_count    INTEGER NOT NULL DEFAULT 0,
                priority_boost  REAL NOT NULL DEFAULT 0.0,   -- scheduler priority bonus
                slot_hint       INTEGER NOT NULL DEFAULT 0,  -- +1 allocate more  -1 throttle
                updated_at      TEXT NOT NULL
            )
        """)

        # ── Live Outcome Tracking: per-draw results + EWMA state ──────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS live_strategy_outcomes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id     TEXT NOT NULL,
                game_type       TEXT NOT NULL,
                draw_id         TEXT NOT NULL,          -- e.g. "20260428"
                recorded_at     TEXT NOT NULL,
                predicted_json  TEXT NOT NULL DEFAULT '[]',   -- JSON list of predicted numbers
                actual_json     TEXT NOT NULL DEFAULT '[]',   -- JSON list of actual draw numbers
                match_count     INTEGER NOT NULL DEFAULT 0,
                bet_units       REAL NOT NULL DEFAULT 1.0,
                payout_units    REAL NOT NULL DEFAULT 0.0,
                pnl             REAL NOT NULL DEFAULT 0.0,    -- payout - bet
                roi             REAL NOT NULL DEFAULT -1.0,   -- pnl / bet
                accuracy_score  REAL NOT NULL DEFAULT 0.0,    -- match_count / len(actual)  [0..1]
                UNIQUE(strategy_id, draw_id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_lso_strategy  ON live_strategy_outcomes(strategy_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lso_game_type ON live_strategy_outcomes(game_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lso_draw_id   ON live_strategy_outcomes(draw_id)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS strategy_live_state (
                strategy_id         TEXT PRIMARY KEY,
                game_type           TEXT NOT NULL,
                backtest_edge       REAL,                          -- reference edge from backtest
                ewma_live_roi       REAL NOT NULL DEFAULT -1.0,   -- EWMA of per-draw ROI
                ewma_accuracy       REAL NOT NULL DEFAULT 0.0,    -- EWMA of accuracy_score
                ewma_pnl            REAL NOT NULL DEFAULT 0.0,    -- EWMA of pnl
                sample_count        INTEGER NOT NULL DEFAULT 0,
                drift_score         REAL NOT NULL DEFAULT 0.0,    -- normalised backtest vs live divergence [0..1]
                decay_weight        REAL NOT NULL DEFAULT 1.0,    -- scheduler multiplier [0.20..1.0]
                consecutive_losses  INTEGER NOT NULL DEFAULT 0,   -- draws in a row with roi < 0
                last_draw_id        TEXT,
                updated_at          TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sls_game_type   ON strategy_live_state(game_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sls_drift_score ON strategy_live_state(drift_score DESC)")

        # Exploration result router state (prevents duplicate follow-up routing)
        c.execute("""
            CREATE TABLE IF NOT EXISTS exploration_routing_state (
                source_task_id    INTEGER PRIMARY KEY,         -- agent_tasks.id
                source_dedupe_key TEXT NOT NULL,
                source_lane       TEXT NOT NULL,
                decision          TEXT NOT NULL,               -- WORTH_VALIDATION / WATCH_ONLY / REJECT_FOR_NOW / INCONCLUSIVE_NEED_DATA
                route_action      TEXT NOT NULL,               -- VALIDATION_CREATED / WATCH_ONLY_RECORDED / ARCHIVED_RECORDED / DATA_TASK_CREATED / VALIDATION_DEDUPE_SKIPPED
                source_report     TEXT,
                followup_task_id  INTEGER,
                note              TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ers_lane ON exploration_routing_state(source_lane)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ers_decision ON exploration_routing_state(decision)")

        conn.commit()
        logger.info(f"[OrchestratorDB] init OK — {DB_PATH}")
    finally:
        conn.close()


# ── Epoch management ──────────────────────────────────────────────────────────

def get_current_epoch_id() -> int:
    """Return the id of the currently active epoch (0 = pre-baseline/fallback)."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM system_epochs WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else 0
    finally:
        conn.close()


def get_current_epoch() -> dict:
    """Return the full current epoch row, or a synthetic epoch-0 dict if none is active."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM system_epochs WHERE is_current = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
        return {"id": 0, "epoch_label": "pre_baseline", "epoch_note": None, "started_at": None, "is_current": 0}
    finally:
        conn.close()


def create_epoch(epoch_label: str, epoch_note: str = "") -> int:
    """
    Deactivate all current epochs and create a new active epoch.
    Returns the new epoch id.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute("UPDATE system_epochs SET is_current = 0")
        cursor = conn.execute(
            "INSERT INTO system_epochs (epoch_label, epoch_note, started_at, is_current) VALUES (?, ?, ?, 1)",
            (epoch_label, epoch_note, now),
        )
        new_id = cursor.lastrowid
        conn.commit()
        logger.info("[Epoch] New epoch created: id=%d label=%r started_at=%s", new_id, epoch_label, now)
        return new_id
    finally:
        conn.close()


def list_epochs() -> list:
    """Return all epochs ordered by id."""
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM system_epochs ORDER BY id ASC").fetchall()]
    finally:
        conn.close()


def log_tick(runner: str, outcome: str, task_id=None, message: str = "", duration_ms: int = 0, request_id: str = None):
    conn = get_conn()
    try:
        epoch_id = get_current_epoch_id()
        conn.execute(
            "INSERT INTO agent_task_runs (runner, tick_at, outcome, request_id, task_id, message, duration_ms, epoch_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (runner, datetime.now(timezone.utc).isoformat(), outcome, request_id, task_id, message, duration_ms, epoch_id)
        )
        if RUN_HISTORY_RETENTION > 0:
            conn.execute(
                """
                DELETE FROM agent_task_runs
                WHERE id NOT IN (
                    SELECT id FROM agent_task_runs ORDER BY id DESC LIMIT ?
                )
                """,
                (RUN_HISTORY_RETENTION,),
            )
        conn.commit()
    finally:
        conn.close()


def get_latest_task():
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_task(task_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_task(
    slot_key,
    date_folder,
    title,
    slug,
    prompt_text,
    prompt_file_path,
    previous_task_id=None,
    dedupe_key: str = None,
    regime_state: str = None,
    confidence_snapshot: float = None,
    value_score: float = None,
    worker_type: str = "research",
):
    now = datetime.now(timezone.utc).isoformat()
    epoch_id = get_current_epoch_id()
    conn = get_conn()
    try:
        c = conn.execute(
            """INSERT INTO agent_tasks
               (slot_key, date_folder, title, slug, status, prompt_text, prompt_file_path,
                previous_task_id, dedupe_key, regime_state, confidence_snapshot,
                epoch_id, value_score, worker_type, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                slot_key, date_folder, title, slug, prompt_text, prompt_file_path,
                previous_task_id, dedupe_key, regime_state, confidence_snapshot,
                epoch_id, value_score, worker_type, now, now,
            )
        )
        task_id = c.lastrowid
        conn.commit()
        # Update dedupe state table if a dedupe_key was provided
        if dedupe_key:
            conn2 = get_conn()
            try:
                conn2.execute(
                    """
                    INSERT INTO planner_dedupe_state
                        (dedupe_key, last_regime_state, last_confidence, last_task_id,
                         last_emitted_at, skip_count, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    ON CONFLICT(dedupe_key) DO UPDATE SET
                        last_regime_state = excluded.last_regime_state,
                        last_confidence   = excluded.last_confidence,
                        last_task_id      = excluded.last_task_id,
                        last_emitted_at   = excluded.last_emitted_at,
                        skip_count        = 0,
                        updated_at        = excluded.updated_at
                    """,
                    (dedupe_key, regime_state, confidence_snapshot, task_id, now, now),
                )
                conn2.commit()
            finally:
                conn2.close()
        return task_id
    finally:
        conn.close()


def get_inflight_task_by_dedupe_key(dedupe_key: str, stale_queued_minutes: int = 120):
    """Return the most recent QUEUED or RUNNING task with the given dedupe_key, or None.

    QUEUED tasks older than *stale_queued_minutes* (default 2 h) are ignored —
    this prevents a permanent in-flight lock when the worker/daemon never executes
    the task (e.g. WORKER_SKIP_DAEMON_PROVIDER).  RUNNING tasks always block.
    """
    if not dedupe_key:
        return None
    from datetime import timedelta
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stale_queued_minutes)).isoformat()
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key = ?
               AND (
                   status = 'RUNNING'
                   OR (status = 'QUEUED' AND created_at >= ?)
               )
               ORDER BY id DESC LIMIT 1""",
            (dedupe_key, stale_cutoff),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_inflight_auto_monitor_by_source_task_type(
    source_task_type: str,
    stale_queued_minutes: int = 120,
):
    """Return earliest live AUTO-MONITOR task for a source task_type, or None.

    Matches dedupe_key prefix: ``monitoring:{source_task_type}:`` and applies
    the same stale QUEUED cutoff policy as get_inflight_task_by_dedupe_key().
    """
    source = (source_task_type or "").strip()
    if not source:
        return None

    from datetime import timedelta
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=stale_queued_minutes)).isoformat()
    key_prefix = f"monitoring:{source}:%"

    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE title LIKE '[AUTO-MONITOR]%'
                 AND dedupe_key LIKE ?
                 AND (
                     status = 'RUNNING'
                     OR (status = 'QUEUED' AND created_at >= ?)
                 )
               ORDER BY id ASC LIMIT 1""",
            (key_prefix, stale_cutoff),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_completed_task_by_dedupe_key(dedupe_key: str, within_seconds: int = 1800):
    """Return the most recent COMPLETED task with the given dedupe_key within the cooldown, or None."""
    if not dedupe_key:
        return None
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat()
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key = ? AND status = 'COMPLETED'
               AND completed_at IS NOT NULL AND completed_at >= ?
               ORDER BY id DESC LIMIT 1""",
            (dedupe_key, cutoff),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_today_auto_monitor_by_dedupe_key(dedupe_key: str):
    """Return earliest non-FAILED AUTO-MONITOR task with given dedupe_key created today (UTC), or None.

    Used for daily cap enforcement: one monitoring task per (source_type, calendar_day).
    Statuses checked: QUEUED, RUNNING, COMPLETED.
    FAILED tasks are excluded so a failed run does not permanently block the day.
    """
    if not dedupe_key:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key = ?
                 AND status IN ('QUEUED', 'RUNNING', 'COMPLETED')
                 AND DATE(created_at) = DATE('now')
               ORDER BY id ASC LIMIT 1""",
            (dedupe_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_today_task_by_dedupe_key(dedupe_key: str):
    """Return earliest non-FAILED task with given dedupe_key created today (UTC), or None.

    Generic daily cap check for any date-keyed task (monitoring, fallback, etc.).
    Statuses: QUEUED, RUNNING, COMPLETED.  FAILED excluded so a bad run allows retry.
    """
    if not dedupe_key:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key = ?
                 AND status IN ('QUEUED', 'RUNNING', 'COMPLETED')
                 AND DATE(created_at) = DATE('now')
               ORDER BY id ASC LIMIT 1""",
            (dedupe_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_nonfailed_task_by_dedupe_key(dedupe_key: str):
    """Return the earliest active/completed task with the given dedupe_key (any date), or None.

    This is the STRONG daily cap guard for tasks whose dedupe_key already embeds a
    date string (e.g. forced_exploration:{lane}:{YYYY-MM-DD}).  Unlike
    get_today_task_by_dedupe_key(), this does NOT filter by DATE(created_at) — it
    matches purely by key, making it immune to manual row deletions or UTC midnight
    boundary edge cases.

    Blocked statuses (prevent re-creation):
        QUEUED, RUNNING, COMPLETED, SKIPPED_DUPLICATE, SKIPPED_DUPLICATE_DAILY_CAP

    Allowed to retry (task failed cleanly):
        FAILED, FAILED_*, REPLAN_REQUIRED, BLOCKED_ENV
    """
    if not dedupe_key:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key = ?
                 AND status IN (
                     'QUEUED', 'RUNNING', 'COMPLETED',
                     'SKIPPED_DUPLICATE', 'SKIPPED_DUPLICATE_DAILY_CAP'
                 )
               ORDER BY id ASC LIMIT 1""",
            (dedupe_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_last_forced_exploration_task():
    """Return the most recently created forced_exploration task (any date/status), or None.

    Used for lane rotation: inspect dedupe_key to determine which lane ran last,
    then pick the next one in A→B→C→D→E→F→A order.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM agent_tasks
               WHERE dedupe_key LIKE 'forced_exploration:%'
               ORDER BY id DESC LIMIT 1""",
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_planner_dedupe_state(dedupe_key: str):
    """Return the last-emitted state for a dedupe_key (confidence, regime, task_id), or None."""
    if not dedupe_key:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM planner_dedupe_state WHERE dedupe_key = ?",
            (dedupe_key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def increment_dedupe_skip_count(dedupe_key: str):
    """Increment the skip counter for a dedupe_key (for observability)."""
    if not dedupe_key:
        return
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO planner_dedupe_state (dedupe_key, skip_count, updated_at)
            VALUES (?, 1, ?)
            ON CONFLICT(dedupe_key) DO UPDATE SET
                skip_count = skip_count + 1,
                updated_at = excluded.updated_at
            """,
            (dedupe_key, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_task(task_id: int, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    conn = get_conn()
    try:
        conn.execute(f"UPDATE agent_tasks SET {sets} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def get_worker_lock():
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_locks WHERE runner = 'worker'").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_worker_lock(pid: int, task_id: int):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO agent_locks (runner, pid, task_id, started_at, heartbeat_at)
               VALUES ('worker', ?, ?, ?, ?)""",
            (pid, task_id, now, now)
        )
        conn.commit()
    finally:
        conn.close()


def update_worker_heartbeat():
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE agent_locks SET heartbeat_at = ? WHERE runner = 'worker'",
            (datetime.now(timezone.utc).isoformat(),)
        )
        conn.commit()
    finally:
        conn.close()


def clear_worker_lock():
    conn = get_conn()
    try:
        conn.execute("DELETE FROM agent_locks WHERE runner = 'worker'")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Light worker concurrency lock helpers
# ---------------------------------------------------------------------------

def get_light_worker_locks():
    """Return all active light-worker lock rows."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_locks WHERE lock_type = 'light'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_active_light_workers():
    """Return how many light workers are currently holding locks."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM agent_locks WHERE lock_type = 'light'"
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def acquire_light_lock(pid: int, task_id: int):
    """Insert a light-worker lock row; returns the runner key string."""
    runner_key = f"light:{task_id}"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO agent_locks
               (runner, pid, task_id, started_at, heartbeat_at, lock_type)
               VALUES (?, ?, ?, ?, ?, 'light')""",
            (runner_key, pid, task_id, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return runner_key


def release_light_lock(runner_key: str):
    """Delete a light-worker lock row by its runner key."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM agent_locks WHERE runner = ?", (runner_key,))
        conn.commit()
    finally:
        conn.close()


def update_light_heartbeat(runner_key: str):
    """Update heartbeat timestamp for a light-worker lock row."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE agent_locks SET heartbeat_at = ? WHERE runner = ?",
            (now, runner_key),
        )
        conn.commit()
    finally:
        conn.close()


def get_next_light_task():
    """Return the highest-priority QUEUED light task.

    Priority order (within worker_type='light'):
    repair (0) > system_recovery (1) > governance/data_quality/audit (2) >
    report/health_check (3) > monitoring (4).
    Resolved via CASE expression so no Python-side sorting is needed.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT *,
                   CASE
                       WHEN dedupe_key LIKE 'validation_repair%' THEN 0
                       WHEN dedupe_key LIKE 'template_repair%'   THEN 0
                       WHEN dedupe_key LIKE 'system_recovery%'   THEN 1
                       WHEN dedupe_key LIKE 'governance%'        THEN 2
                       WHEN dedupe_key LIKE 'data_quality%'      THEN 2
                       WHEN dedupe_key LIKE 'audit%'             THEN 2
                       WHEN dedupe_key LIKE 'report%'            THEN 3
                       WHEN dedupe_key LIKE 'health_check%'      THEN 3
                       ELSE 4
                   END AS _light_prio
               FROM agent_tasks
               WHERE status = 'QUEUED'
                 AND (worker_type = 'light')
               ORDER BY _light_prio ASC, id ASC
               LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_next_research_task_by_priority():
    """Return highest-priority QUEUED research task (worker_type='research' or NULL)."""
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT at.*,
                   COALESCE(cbi.priority_score, 0)   AS _p_score,
                   COALESCE(cbi.priority_level, 'P3') AS _p_level
            FROM agent_tasks at
            LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
            WHERE at.status = 'QUEUED'
              AND (at.worker_type = 'research' OR at.worker_type IS NULL)
            ORDER BY
                CASE COALESCE(cbi.priority_level,'P3')
                     WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END ASC,
                COALESCE(cbi.priority_score, 0) DESC,
                at.id ASC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Adaptive scheduling — metrics + state helpers
# ---------------------------------------------------------------------------

def log_worker_metrics(
    worker_type: str,
    active_count: int,
    queued_count: int,
    completed_count: int,
    failed_count: int,
    avg_latency_s: float = None,
    throughput_ph: float = None,
    cpu_pct: float = None,
    slot_limit: int = 3,
    backpressure: int = 0,
    # v2 extended fields
    cpu_share_pct: float = None,
    research_latency_s: float = None,
    starvation_incidents: int = 0,
    slot_decision_reason: str = None,
):
    """Insert one row into worker_metrics for trend tracking."""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO worker_metrics
               (sampled_at, worker_type, active_count, queued_count,
                completed_count, failed_count, avg_latency_s, throughput_ph,
                cpu_pct, slot_limit, backpressure,
                cpu_share_pct, research_latency_s, starvation_incidents, slot_decision_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                worker_type, active_count, queued_count,
                completed_count, failed_count, avg_latency_s, throughput_ph,
                cpu_pct, slot_limit, backpressure,
                cpu_share_pct, research_latency_s, starvation_incidents, slot_decision_reason,
            ),
        )
        # Keep only last 1440 rows per worker_type (~24 h at 1-min sampling)
        conn.execute(
            """DELETE FROM worker_metrics WHERE id NOT IN (
                   SELECT id FROM worker_metrics
                   WHERE worker_type = ?
                   ORDER BY id DESC LIMIT 1440
               ) AND worker_type = ?""",
            (worker_type, worker_type),
        )
        conn.commit()
    finally:
        conn.close()


def get_worker_metrics_snapshot(worker_type: str = None, limit: int = 60):
    """Return the most recent metric rows, optionally filtered by worker_type."""
    conn = get_conn()
    try:
        if worker_type:
            rows = conn.execute(
                "SELECT * FROM worker_metrics WHERE worker_type=? ORDER BY id DESC LIMIT ?",
                (worker_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM worker_metrics ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_queue_depth_by_type():
    """Return {worker_type: count} for QUEUED tasks."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT COALESCE(worker_type,'research') AS wtype, COUNT(1) AS cnt
               FROM agent_tasks WHERE status='QUEUED' GROUP BY wtype"""
        ).fetchall()
        return {r["wtype"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_avg_task_latency(worker_type: str, window_hours: int = 6):
    """Return average duration_seconds for COMPLETED tasks in the last window_hours."""
    conn = get_conn()
    try:
        cutoff = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff -= timedelta(hours=window_hours)
        row = conn.execute(
            """SELECT AVG(duration_seconds) AS avg_s
               FROM agent_tasks
               WHERE (worker_type=? OR (? = 'research' AND worker_type IS NULL))
                 AND status='COMPLETED'
                 AND completed_at >= ?""",
            (worker_type, worker_type, cutoff.isoformat()),
        ).fetchone()
        v = row["avg_s"] if row else None
        return float(v) if v is not None else None
    finally:
        conn.close()


def get_throughput_per_hour(worker_type: str, window_hours: int = 1):
    """Return tasks completed per hour for the given worker_type over window_hours."""
    conn = get_conn()
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        row = conn.execute(
            """SELECT COUNT(1) AS cnt
               FROM agent_tasks
               WHERE (worker_type=? OR (? = 'research' AND worker_type IS NULL))
                 AND status='COMPLETED'
                 AND completed_at >= ?""",
            (worker_type, worker_type, cutoff),
        ).fetchone()
        cnt = row["cnt"] if row else 0
        return round(cnt / max(window_hours, 1), 2)
    finally:
        conn.close()


def get_research_latency_s(window_hours: int = 6):
    """Return average duration_seconds for COMPLETED research tasks over window_hours."""
    return get_avg_task_latency("research", window_hours=window_hours)


def count_starvation_incidents(window_hours: int = 1) -> int:
    """Return the count of worker_metrics rows where light was queued but active=0.

    This counts ticks where light tasks existed but no worker was running them —
    a proxy for starvation events.
    """
    conn = get_conn()
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        row = conn.execute(
            """SELECT COUNT(1) AS cnt
               FROM worker_metrics
               WHERE worker_type = 'light'
                 AND queued_count > 0
                 AND active_count = 0
                 AND sampled_at >= ?""",
            (cutoff,),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Self-tuning scheduler — tunable params + tuning log
# ---------------------------------------------------------------------------

_SCHEDULER_PARAM_DEFAULTS = {
    # param: (default, min, max, step)
    "queue_boost_threshold": (4.0,  2.0, 12.0, 1.0),
    "high_cpu_floor":        (90.0, 82.0, 96.0, 2.0),
    "fairness_ratio":        (0.0,  0.0,  3.0,  0.5),
}


def get_tunable_param(param: str):
    """Return the current row for a tunable param, or None if not seeded."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM scheduler_tunable_params WHERE param=?", (param,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_tunable_params() -> dict:
    """Return {param: row_dict} for all seeded tunable params."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM scheduler_tunable_params").fetchall()
        return {r["param"]: dict(r) for r in rows}
    finally:
        conn.close()


def seed_tunable_param(param: str, default: float, min_v: float, max_v: float, step: float):
    """Insert a tunable param with its default if it doesn't already exist."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO scheduler_tunable_params
               (param, value, default_value, min_value, max_value, step_size,
                last_direction, update_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)""",
            (param, default, default, min_v, max_v, step, now),
        )
        conn.commit()
    finally:
        conn.close()


def seed_default_tunable_params():
    """Ensure all default tunable params exist in the DB."""
    for param, (default, min_v, max_v, step) in _SCHEDULER_PARAM_DEFAULTS.items():
        seed_tunable_param(param, default, min_v, max_v, step)


def update_tunable_param_ewma(param: str, last_reward: float, new_ewma: float):
    """Update the EWMA reward for a param without changing its value or cooldown."""
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE scheduler_tunable_params
               SET last_reward=?, ewma_reward=?, updated_at=?
               WHERE param=?""",
            (last_reward, new_ewma, datetime.now(timezone.utc).isoformat(), param),
        )
        conn.commit()
    finally:
        conn.close()


def update_tunable_param_value(
    param: str,
    new_value: float,
    reward: float,
    direction: int,
    cooldown_seconds: int = 300,
    is_exploration: bool = False,
):
    """Update a tunable param's value, set cooldown, increment update_count.

    Saves the current value into previous_value so rollback_tunable_param() can
    restore it if performance deteriorates.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cooldown_until = (now + timedelta(seconds=cooldown_seconds)).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE scheduler_tunable_params
               SET previous_value=value, value=?, last_reward=?, last_direction=?,
                   cooldown_until=?, update_count=update_count+1, updated_at=?
               WHERE param=?""",
            (new_value, reward, direction, cooldown_until,
             now.isoformat(), param),
        )
        conn.commit()
    finally:
        conn.close()


def rollback_tunable_param(param: str) -> bool:
    """Restore a param to its previous_value.

    Returns True if rollback was committed, False if no previous_value exists.
    Swaps value ↔ previous_value so a second rollback can undo the rollback.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT value, previous_value FROM scheduler_tunable_params WHERE param=?",
            (param,),
        ).fetchone()
        if not row or row["previous_value"] is None:
            return False
        conn.execute(
            """UPDATE scheduler_tunable_params
               SET value=previous_value, previous_value=value,
                   rollback_count=rollback_count+1,
                   cooldown_until=NULL, updated_at=?
               WHERE param=?""",
            (datetime.now(timezone.utc).isoformat(), param),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_worker_metrics_window(worker_type: str = "light", window_hours: float = 1.0) -> dict:
    """Return aggregate statistics for worker_metrics over the past window_hours.

    Used by the tuner for 1h baseline and 24h trend checks.
    Returns keys: row_count, avg_tph, avg_latency_s, avg_starvation, avg_research_latency_s.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS row_count,
                   AVG(throughput_ph) AS avg_tph,
                   AVG(avg_latency_s) AS avg_latency_s,
                   AVG(COALESCE(starvation_incidents, 0)) AS avg_starvation,
                   AVG(COALESCE(research_latency_s, 0)) AS avg_research_latency_s
               FROM worker_metrics
               WHERE worker_type=? AND sampled_at >= ?""",
            (worker_type, cutoff),
        ).fetchone()
        return dict(row) if row else {"row_count": 0}
    finally:
        conn.close()


# ── Outcome-aware scheduler — outcome recording + ROI state ───────────────────

def record_task_outcome(
    task_id: int,
    task_type: str,
    success: bool,
    quality_score: float = None,
    roi_score: float = None,
    edge_score: float = None,
    extraction_method: str = "heuristic",
    best_edge: float = None,
    strategies_found: int = 0,
    mc_pass_count: int = 0,
    confidence_score: float = 1.0,
):
    """Record the outcome of a completed task for outcome-aware scheduling.

    Called by worker_tick / light_worker_tick after a task finishes.
    All score fields are optional [0..1]; omit any that the task type doesn't produce.
    extraction_method: 'real' (extracted from output files) | 'heuristic' | 'fallback'.
    best_edge: normalised edge vs incumbent, [0..1].
    confidence_score: 0..1 trustworthiness from validation layer.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO task_outcomes
               (task_id, task_type, success, quality_score, roi_score, edge_score,
                extraction_method, best_edge, strategies_found, mc_pass_count,
                confidence_score, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_type, 1 if success else 0,
             quality_score, roi_score, edge_score,
             extraction_method, best_edge, strategies_found, mc_pass_count,
             confidence_score, now),
        )
        # Retain last 2000 rows globally
        conn.execute(
            "DELETE FROM task_outcomes WHERE id NOT IN "
            "(SELECT id FROM task_outcomes ORDER BY id DESC LIMIT 2000)"
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_task_outcomes(task_type: str = None, limit: int = 50) -> list:
    """Return the most recent task_outcomes rows, optionally filtered by task_type."""
    conn = get_conn()
    try:
        if task_type:
            rows = conn.execute(
                "SELECT * FROM task_outcomes WHERE task_type=? ORDER BY id DESC LIMIT ?",
                (task_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM task_outcomes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_task_type_roi_state(task_type: str = None):
    """Return ROI state for one task_type (dict), or all types ({task_type: dict})."""
    conn = get_conn()
    try:
        if task_type:
            row = conn.execute(
                "SELECT * FROM task_type_roi_state WHERE task_type=?", (task_type,)
            ).fetchone()
            return dict(row) if row else None
        rows = conn.execute("SELECT * FROM task_type_roi_state").fetchall()
        return {r["task_type"]: dict(r) for r in rows}
    finally:
        conn.close()


def update_task_type_roi(
    task_type: str,
    quality_score: float,
    roi_score: float,
    success: bool,
    ewma_alpha: float = 0.20,
):
    """EWMA-update the ROI state for a task_type; upsert if not present."""
    now = datetime.now(timezone.utc).isoformat()
    success_val = 1.0 if success else 0.0
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM task_type_roi_state WHERE task_type=?", (task_type,)
        ).fetchone()
        if row:
            q_prev = float(row["ewma_quality"] or 0.5)
            r_prev = float(row["ewma_roi"]     or 0.5)
            s_prev = float(row["ewma_success"] or 0.5)
            new_q  = round(ewma_alpha * quality_score + (1 - ewma_alpha) * q_prev, 4)
            new_r  = round(ewma_alpha * roi_score     + (1 - ewma_alpha) * r_prev, 4)
            new_s  = round(ewma_alpha * success_val   + (1 - ewma_alpha) * s_prev, 4)
            n      = int(row["sample_count"]) + 1
            conn.execute(
                """UPDATE task_type_roi_state
                   SET ewma_quality=?, ewma_roi=?, ewma_success=?,
                       sample_count=?, updated_at=?
                   WHERE task_type=?""",
                (new_q, new_r, new_s, n, now, task_type),
            )
        else:
            conn.execute(
                """INSERT INTO task_type_roi_state
                   (task_type, ewma_quality, ewma_roi, ewma_success,
                    sample_count, priority_boost, slot_hint, updated_at)
                   VALUES (?, ?, ?, ?, 1, 0.0, 0, ?)""",
                (task_type,
                 round(quality_score, 4), round(roi_score, 4), round(success_val, 4),
                 now),
            )
        conn.commit()
    finally:
        conn.close()


def set_task_type_slot_hint(task_type: str, slot_hint: int, priority_boost: float):
    """Upsert scheduler slot hint + priority boost for a task_type (written by feedback loop)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO task_type_roi_state
               (task_type, ewma_quality, ewma_roi, ewma_success,
                sample_count, priority_boost, slot_hint, updated_at)
               VALUES (?, 0.5, 0.5, 0.5, 0, ?, ?, ?)
               ON CONFLICT(task_type) DO UPDATE SET
                   priority_boost=excluded.priority_boost,
                   slot_hint=excluded.slot_hint,
                   updated_at=excluded.updated_at""",
            (task_type, priority_boost, slot_hint, now),
        )
        conn.commit()
    finally:
        conn.close()


def log_tuning_decision(
    action: str,
    param: str = None,
    old_value: float = None,
    new_value: float = None,
    direction: int = None,
    reward: float = None,
    ewma_reward: float = None,
    reason: str = None,
    is_exploration: bool = False,
):
    """Append one row to scheduler_tuning_log for audit trail."""
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO scheduler_tuning_log
               (logged_at, action, param, old_value, new_value, direction,
                reward, ewma_reward, reason, is_exploration)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                action, param, old_value, new_value, direction,
                reward, ewma_reward, reason, 1 if is_exploration else 0,
            ),
        )
        # Keep last 2000 rows
        conn.execute(
            """DELETE FROM scheduler_tuning_log WHERE id NOT IN (
                   SELECT id FROM scheduler_tuning_log ORDER BY id DESC LIMIT 2000
               )"""
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_worker_metrics(worker_type: str = "light", limit: int = 20) -> list:
    """Return the N most recent worker_metrics rows for a given worker_type."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM worker_metrics
               WHERE worker_type=?
               ORDER BY id DESC LIMIT ?""",
            (worker_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_set_scheduling_state(key: str, value: str = None):
    """Read or write a scheduling_state key. Pass value=None to read."""
    conn = get_conn()
    try:
        if value is None:
            row = conn.execute(
                "SELECT value FROM scheduling_state WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else None
        else:
            conn.execute(
                """INSERT INTO scheduling_state (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, value, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return value
    finally:
        conn.close()


def count_tasks(date_folder=None, status=None):
    conn = get_conn()
    try:
        conds, vals = [], []
        if date_folder:
            conds.append("date_folder = ?")
            vals.append(date_folder)
        if status:
            conds.append("status = ?")
            vals.append(status)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        row = conn.execute(
            f"SELECT COUNT(1) AS cnt FROM agent_tasks {where}", vals
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def count_tasks_by_status(date_folder=None):
    conn = get_conn()
    try:
        conds, vals = [], []
        if date_folder:
            conds.append("date_folder = ?")
            vals.append(date_folder)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        rows = conn.execute(
            f"SELECT status, COUNT(1) AS cnt FROM agent_tasks {where} GROUP BY status",
            vals,
        ).fetchall()
        return {str(r["status"]): int(r["cnt"]) for r in rows}
    finally:
        conn.close()


def list_tasks(date_folder=None, status=None, limit=50, offset=0):
    conn = get_conn()
    try:
        conds, vals = [], []
        if date_folder:
            conds.append("date_folder = ?")
            vals.append(date_folder)
        if status:
            conds.append("status = ?")
            vals.append(status)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        vals.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM agent_tasks {where} ORDER BY id DESC LIMIT ? OFFSET ?", vals
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_runs(runner=None, since=None, limit=200, request_id=None):
    conn = get_conn()
    try:
        conds, vals = [], []
        if runner:
            conds.append("runner = ?")
            vals.append(runner)
        if request_id:
            conds.append("request_id = ?")
            vals.append(request_id)
        if since:
            conds.append("tick_at >= ?")
            vals.append(since)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        vals.append(limit)
        rows = conn.execute(
            f"SELECT * FROM agent_task_runs {where} ORDER BY id DESC LIMIT ?", vals
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_setting(key: str, default: str = None) -> str:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT value FROM orchestrator_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return default
        return row["value"]
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO orchestrator_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, str(value), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def is_scheduler_enabled() -> bool:
    value = get_setting("scheduler_enabled", DEFAULT_SETTINGS["scheduler_enabled"])
    return str(value).strip() in ("1", "true", "TRUE", "yes", "on")


def set_scheduler_enabled(enabled: bool):
    set_setting("scheduler_enabled", "1" if enabled else "0")


def is_llm_hard_off() -> bool:
    value = get_setting("llm_hard_off", DEFAULT_SETTINGS["llm_hard_off"])
    return str(value).strip() in ("1", "true", "TRUE", "yes", "on")


def set_llm_hard_off(enabled: bool):
    set_setting("llm_hard_off", "1" if enabled else "0")
    set_setting("llm_execution_mode", "hard-off" if enabled else "safe-run")


def get_planner_provider() -> str:
    value = get_setting("planner_provider", DEFAULT_SETTINGS["planner_provider"]) or DEFAULT_SETTINGS["planner_provider"]
    return str(value).strip().lower()


def set_planner_provider(provider: str):
    set_setting("planner_provider", provider)


def get_worker_provider() -> str:
    value = get_setting("worker_provider", DEFAULT_SETTINGS["worker_provider"]) or DEFAULT_SETTINGS["worker_provider"]
    return str(value).strip().lower()


def set_worker_provider(provider: str):
    set_setting("worker_provider", provider)


def get_worker_copilot_model() -> str:
    value = get_setting("worker_copilot_model", DEFAULT_SETTINGS["worker_copilot_model"])
    return str(value or "").strip()


def set_worker_copilot_model(model: str):
    set_setting("worker_copilot_model", str(model or "").strip())


def get_cto_review_frequency_mode() -> str:
    value = get_setting("cto_review_frequency_mode", DEFAULT_SETTINGS["cto_review_frequency_mode"]) or DEFAULT_SETTINGS["cto_review_frequency_mode"]
    normalized = str(value).strip().lower()
    return normalized if normalized in ("once_daily", "twice_daily") else DEFAULT_SETTINGS["cto_review_frequency_mode"]


def set_cto_review_frequency_mode(mode: str):
    normalized = str(mode or "").strip().lower()
    if normalized not in ("once_daily", "twice_daily"):
        normalized = DEFAULT_SETTINGS["cto_review_frequency_mode"]
    set_setting("cto_review_frequency_mode", normalized)


def is_cto_scheduler_enabled() -> bool:
    value = get_setting("cto_scheduler_enabled", DEFAULT_SETTINGS["cto_scheduler_enabled"])
    return str(value).strip() in ("1", "true", "TRUE", "yes", "on")


def set_cto_scheduler_enabled(enabled: bool):
    set_setting("cto_scheduler_enabled", "1" if enabled else "0")


def get_cto_planner_provider() -> str:
    value = get_setting("cto_planner_provider", DEFAULT_SETTINGS["cto_planner_provider"]) or DEFAULT_SETTINGS["cto_planner_provider"]
    return str(value).strip().lower()


def set_cto_planner_provider(provider: str):
    set_setting("cto_planner_provider", provider)


def get_cto_planner_model() -> str:
    value = get_setting("cto_planner_model", DEFAULT_SETTINGS["cto_planner_model"])
    return str(value or "").strip()


def set_cto_planner_model(model: str):
    set_setting("cto_planner_model", str(model or "").strip())


def _json_dumps(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def upsert_task_git_commit(**kwargs):
    required = ["task_id", "slot_key", "status"]
    for field in required:
        if field not in kwargs or kwargs[field] is None:
            raise ValueError(f"missing required field: {field}")

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "task_id": kwargs["task_id"],
        "slot_key": kwargs["slot_key"],
        "task_title": kwargs.get("task_title"),
        "source_branch": kwargs.get("source_branch"),
        "commit_sha": kwargs.get("commit_sha"),
        "commit_message": kwargs.get("commit_message"),
        "integration_group": kwargs.get("integration_group"),
        "review_priority": kwargs.get("review_priority"),
        "safe_to_autocommit": 1 if kwargs.get("safe_to_autocommit") else 0,
        "status": kwargs["status"],
        "reviewer_role": kwargs.get("reviewer_role"),
        "reviewed_at": kwargs.get("reviewed_at"),
        "merge_branch": kwargs.get("merge_branch"),
        "merge_commit_sha": kwargs.get("merge_commit_sha"),
        "reject_reason": kwargs.get("reject_reason"),
        "superseded_by_task_id": kwargs.get("superseded_by_task_id"),
        "superseded_by_commit_sha": kwargs.get("superseded_by_commit_sha"),
        "changed_files_json": _json_dumps(kwargs.get("changed_files")),
        "depends_on_tasks_json": _json_dumps(kwargs.get("depends_on_tasks")),
        "depends_on_commits_json": _json_dumps(kwargs.get("depends_on_commits")),
        "high_conflict_paths_json": _json_dumps(kwargs.get("high_conflict_paths")),
        "task_status": kwargs.get("task_status"),
        "gate_verdict": kwargs.get("gate_verdict"),
        "gate_reason": kwargs.get("gate_reason"),
        "manual_merge_required": 1 if kwargs.get("manual_merge_required") else 0,
        "created_at": kwargs.get("created_at") or now,
        "updated_at": now,
    }

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO task_git_commits (
                task_id, slot_key, task_title, source_branch, commit_sha, commit_message,
                integration_group, review_priority, safe_to_autocommit, status, reviewer_role,
                reviewed_at, merge_branch, merge_commit_sha, reject_reason, superseded_by_task_id,
                superseded_by_commit_sha, changed_files_json, depends_on_tasks_json,
                depends_on_commits_json, high_conflict_paths_json, task_status, gate_verdict,
                gate_reason, manual_merge_required, created_at, updated_at
            ) VALUES (
                :task_id, :slot_key, :task_title, :source_branch, :commit_sha, :commit_message,
                :integration_group, :review_priority, :safe_to_autocommit, :status, :reviewer_role,
                :reviewed_at, :merge_branch, :merge_commit_sha, :reject_reason, :superseded_by_task_id,
                :superseded_by_commit_sha, :changed_files_json, :depends_on_tasks_json,
                :depends_on_commits_json, :high_conflict_paths_json, :task_status, :gate_verdict,
                :gate_reason, :manual_merge_required, :created_at, :updated_at
            )
            ON CONFLICT(task_id) DO UPDATE SET
                slot_key = excluded.slot_key,
                task_title = excluded.task_title,
                source_branch = excluded.source_branch,
                commit_sha = excluded.commit_sha,
                commit_message = excluded.commit_message,
                integration_group = excluded.integration_group,
                review_priority = excluded.review_priority,
                safe_to_autocommit = excluded.safe_to_autocommit,
                status = excluded.status,
                reviewer_role = excluded.reviewer_role,
                reviewed_at = excluded.reviewed_at,
                merge_branch = excluded.merge_branch,
                merge_commit_sha = excluded.merge_commit_sha,
                reject_reason = excluded.reject_reason,
                superseded_by_task_id = excluded.superseded_by_task_id,
                superseded_by_commit_sha = excluded.superseded_by_commit_sha,
                changed_files_json = excluded.changed_files_json,
                depends_on_tasks_json = excluded.depends_on_tasks_json,
                depends_on_commits_json = excluded.depends_on_commits_json,
                high_conflict_paths_json = excluded.high_conflict_paths_json,
                task_status = excluded.task_status,
                gate_verdict = excluded.gate_verdict,
                gate_reason = excluded.gate_reason,
                manual_merge_required = excluded.manual_merge_required,
                updated_at = excluded.updated_at
            """,
            payload,
        )
        conn.commit()
    finally:
        conn.close()


def get_task_git_commit_for_task(task_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM task_git_commits WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_task_git_commit_by_sha(commit_sha: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM task_git_commits WHERE commit_sha = ? ORDER BY id DESC LIMIT 1",
            (commit_sha,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_task_git_commits(status: str = None, limit: int = 100, offset: int = 0):
    conn = get_conn()
    try:
        conds, vals = [], []
        if status:
            conds.append("status = ?")
            vals.append(status)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        vals.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM task_git_commits {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            vals,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_task_git_commits(status: str = None):
    conn = get_conn()
    try:
        conds, vals = [], []
        if status:
            conds.append("status = ?")
            vals.append(status)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        row = conn.execute(f"SELECT COUNT(1) AS cnt FROM task_git_commits {where}", vals).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def list_waiting_manual_approval(limit: int = 100, offset: int = 0):
    """Return all task_git_commits in WAITING_MANUAL_APPROVAL status."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM task_git_commits WHERE status = 'WAITING_MANUAL_APPROVAL' ORDER BY reviewed_at ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_task_manual_merge_required(task_id: int, required: bool) -> None:
    """Set the manual_merge_required flag for a task's git commit record."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE task_git_commits SET manual_merge_required = ?, updated_at = ? WHERE task_id = ?",
            (1 if required else 0, now, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_task_git_review(**kwargs):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO task_git_reviews (
                commit_sha, task_id, review_run_id, decision, reason, checked_from, checked_until,
                review_summary, decision_steps_json, reviewer_role, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kwargs.get("commit_sha"),
                kwargs.get("task_id"),
                kwargs.get("review_run_id"),
                kwargs.get("decision"),
                kwargs.get("reason"),
                kwargs.get("checked_from"),
                kwargs.get("checked_until"),
                kwargs.get("review_summary"),
                _json_dumps(kwargs.get("decision_steps")),
                kwargs.get("reviewer_role"),
                kwargs.get("created_at") or now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_task_git_review_for_commit(commit_sha: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM task_git_reviews WHERE commit_sha = ? ORDER BY id DESC LIMIT 1",
            (commit_sha,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_task_git_reviews(commit_sha: str = None, task_id: int = None, review_run_id: str = None, limit: int = 100, offset: int = 0):
    conn = get_conn()
    try:
        conds, vals = [], []
        if commit_sha:
            conds.append("commit_sha = ?")
            vals.append(commit_sha)
        if task_id is not None:
            conds.append("task_id = ?")
            vals.append(task_id)
        if review_run_id:
            conds.append("review_run_id = ?")
            vals.append(review_run_id)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        vals.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM task_git_reviews {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            vals,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_cto_review_run(**kwargs):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO cto_review_runs (
                run_id, frequency_mode, started_at, completed_at, duration_seconds, checked_from,
                checked_until, candidate_count, approved_count, merged_count, rejected_count,
                deferred_count, superseded_count, duplicate_count, merge_branch, report_md_path,
                report_json_path, summary, created_at, updated_at, dedupe_key, is_manual, is_force_run,
                run_intent, parent_run_id, status, outcome, outcome_message, pid, request_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kwargs.get("run_id"),
                kwargs.get("frequency_mode"),
                kwargs.get("started_at") or now,
                kwargs.get("completed_at"),
                kwargs.get("duration_seconds"),
                kwargs.get("checked_from"),
                kwargs.get("checked_until"),
                kwargs.get("candidate_count", 0),
                kwargs.get("approved_count", 0),
                kwargs.get("merged_count", 0),
                kwargs.get("rejected_count", 0),
                kwargs.get("deferred_count", 0),
                kwargs.get("superseded_count", 0),
                kwargs.get("duplicate_count", 0),
                kwargs.get("merge_branch"),
                kwargs.get("report_md_path"),
                kwargs.get("report_json_path"),
                kwargs.get("summary"),
                kwargs.get("created_at") or now,
                kwargs.get("updated_at") or now,
                kwargs.get("dedupe_key"),
                1 if kwargs.get("is_manual") else 0,
                1 if kwargs.get("is_force_run") else 0,
                kwargs.get("run_intent"),
                kwargs.get("parent_run_id"),
                kwargs.get("status"),
                kwargs.get("outcome"),
                kwargs.get("outcome_message"),
                kwargs.get("pid"),
                kwargs.get("request_id"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_inflight_cto_run_by_dedupe_key(dedupe_key: str):
    """Return the most recent live RUNNING run with the given dedupe_key, or None."""
    if not dedupe_key:
        return None
    cleanup_stale_cto_review_runs(dedupe_key=dedupe_key)
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT *
              FROM cto_review_runs
             WHERE dedupe_key = ?
               AND completed_at IS NULL
               AND COALESCE(status, 'RUNNING') NOT IN ('COMPLETED', 'SKIPPED', 'FAILED', 'FAILED_STALE', 'SKIPPED_STALE')
             ORDER BY id DESC
             LIMIT 1
            """,
            (dedupe_key,),
        ).fetchone()
        return _enrich_cto_review_run(row) if row else None
    finally:
        conn.close()


def get_recent_completed_cto_run_by_dedupe_key(dedupe_key: str, within_seconds: int = 1800):
    """Return the most recent completed run with the given dedupe_key within within_seconds, or None."""
    if not dedupe_key:
        return None
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cto_review_runs WHERE dedupe_key = ? AND completed_at IS NOT NULL AND completed_at >= ? ORDER BY id DESC LIMIT 1",
            (dedupe_key, cutoff),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_recent_force_runs(within_seconds: int = 600) -> int:
    """Count force runs started within the past `within_seconds` seconds (default: 10 min)."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM cto_review_runs WHERE is_force_run = 1 AND started_at >= ?",
            (cutoff,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def record_intent_signal(
    *,
    run_id: str,
    run_intent: str,
    outcome: str,
    candidate_count: int = 0,
    merged_count: int = 0,
    rejected_count: int = 0,
    deferred_count: int = 0,
    approved_count: int = 0,
    is_compare_only: bool = False,
) -> None:
    """Persist one intent+outcome data point for learning/stats."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO cto_intent_signals
                (run_id, run_intent, outcome, candidate_count, merged_count, rejected_count,
                 deferred_count, approved_count, is_compare_only, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, run_intent, outcome, candidate_count, merged_count,
                rejected_count, deferred_count, approved_count,
                1 if is_compare_only else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_intent_stats() -> dict:
    """Return per-intent aggregated outcome stats for learning dashboard."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT
                run_intent,
                COUNT(*)                                     AS total_runs,
                SUM(CASE WHEN outcome = 'CTO_REVIEW_COMPLETED' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN is_compare_only = 1             THEN 1 ELSE 0 END) AS compare_only_runs,
                SUM(merged_count)                            AS total_merged,
                SUM(rejected_count)                          AS total_rejected,
                SUM(approved_count)                          AS total_approved,
                SUM(candidate_count)                         AS total_candidates,
                AVG(CASE WHEN candidate_count > 0
                         THEN CAST(merged_count AS REAL) / candidate_count
                         ELSE NULL END)                      AS avg_merge_rate
            FROM cto_intent_signals
            GROUP BY run_intent
            ORDER BY run_intent
            """,
        ).fetchall()
        return {
            row["run_intent"]: {
                "total_runs":       row["total_runs"],
                "completed":        row["completed"],
                "compare_only_runs": row["compare_only_runs"],
                "total_merged":     row["total_merged"],
                "total_rejected":   row["total_rejected"],
                "total_approved":   row["total_approved"],
                "total_candidates": row["total_candidates"],
                "avg_merge_rate":   round(row["avg_merge_rate"] or 0.0, 3),
            }
            for row in rows
        }
    finally:
        conn.close()


# ─── Self-Optimizing Decision Architect ──────────────────────────────────────
#
# Analyzes historical cto_intent_signals, recent run outcomes, and backlog
# category completion rates to derive adaptive weights applied at runtime.
#
# Key outputs:
#   retry_coverage_limit  — how many REPLAN/CONFLICT commits to fetch for retry runs
#   category_priority_boosts — {category: score_delta} applied during backlog rescoring
#   suggestions           — human-readable policy recommendations
# ─────────────────────────────────────────────────────────────────────────────

# ─── Classifier Calibration & Dynamic Thresholds ─────────────────────────────

def record_classifier_event(
    state: str,
    confidence_score: float,
    confidence_label: str,
    reason: str,
    features_json: str,
    thresholds_json: str,
) -> int:
    """
    Record a classifier classification event for accuracy tracking.
    Returns the new calibration_log id for later outcome recording.
    """
    now = datetime.now(timezone.utc).isoformat()
    epoch_id = get_current_epoch_id()
    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO classifier_calibration_log
                (classified_at, state, confidence_score, confidence_label,
                 reason, features_json, thresholds_json, epoch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, state, confidence_score, confidence_label,
             reason, features_json, thresholds_json, epoch_id),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def record_classifier_outcome(
    calibration_id: int,
    outcome_state: str,
    draws_checked: int,
    is_correct: bool,
    fp_fn_type: str,  # 'TP', 'FP', 'FN', 'TN'
    notes: str = "",
) -> None:
    """
    Record the observed outcome for a past classification event.
    Marks TP/FP/FN/TN and increments accuracy counters in classifier_thresholds.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        # Update the log entry
        conn.execute(
            """
            UPDATE classifier_calibration_log
            SET outcome_verified_at   = ?,
                outcome_state         = ?,
                outcome_draws_checked = ?,
                is_correct            = ?,
                fp_fn_type            = ?,
                notes                 = ?
            WHERE id = ?
            """,
            (now, outcome_state, draws_checked, 1 if is_correct else 0,
             fp_fn_type, notes, calibration_id),
        )
        # Update counters in classifier_thresholds
        if fp_fn_type in ("TP", "TN"):
            conn.execute(
                """
                UPDATE classifier_thresholds
                SET correct_classifications = correct_classifications + 1,
                    total_classifications   = total_classifications + 1,
                    updated_at              = ?
                WHERE id = 1
                """,
                (now,),
            )
        elif fp_fn_type == "FP":
            # Determine which counter to increment based on original state
            row = conn.execute(
                "SELECT state FROM classifier_calibration_log WHERE id = ?",
                (calibration_id,),
            ).fetchone()
            orig_state = (dict(row).get("state") or "") if row else ""
            if orig_state == "COLD_REGIME":
                conn.execute(
                    """
                    UPDATE classifier_thresholds
                    SET total_classifications = total_classifications + 1,
                        cold_fp_count         = cold_fp_count + 1,
                        updated_at            = ?
                    WHERE id = 1
                    """,
                    (now,),
                )
            else:
                conn.execute(
                    """
                    UPDATE classifier_thresholds
                    SET total_classifications   = total_classifications + 1,
                        saturated_fp_count      = saturated_fp_count + 1,
                        updated_at              = ?
                    WHERE id = 1
                    """,
                    (now,),
                )
        elif fp_fn_type == "FN":
            conn.execute(
                """
                UPDATE classifier_thresholds
                SET total_classifications = total_classifications + 1,
                    cold_fn_count         = cold_fn_count + 1,
                    updated_at            = ?
                WHERE id = 1
                """,
                (now,),
            )
        conn.commit()
    finally:
        conn.close()


def compute_classifier_thresholds() -> dict:
    """
    Dynamically recompute classifier thresholds based on calibration accuracy history.

    Adjustment logic:
    - High cold_fp_rate (>20%) → raise cold_streak_ratio (less aggressive cold detection)
    - High cold_fn_rate (>20%) → lower cold_streak_ratio (more sensitive)
    - High saturated_fp_rate   → raise evidence bar for SATURATED

    Returns the updated threshold dict.
    """
    import json as _json

    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM classifier_thresholds WHERE id = 1").fetchone()
        if not row:
            return _default_classifier_thresholds()
        t = dict(row)

        total = t.get("total_classifications") or 0
        cold_fp = t.get("cold_fp_count") or 0
        cold_fn = t.get("cold_fn_count") or 0
        saturated_fp = t.get("saturated_fp_count") or 0

        # ── Current baseline thresholds ───────────────────────────────────────
        cold_streak_ratio = float(t.get("cold_streak_ratio") or 0.5)
        cold_edge_long_min = float(t.get("cold_edge_long_min") or 0.0)
        cold_edge_short_max = float(t.get("cold_edge_short_max") or 0.0)
        cold_edge_absolute_max = float(t.get("cold_edge_absolute_max") or -0.05)
        cold_min_total = int(t.get("cold_min_total_strategies") or 2)

        # ── Adaptive adjustment (min 10 classified events to adjust) ──────────
        _MIN_CALIBRATION = 10
        if total >= _MIN_CALIBRATION:
            cold_total_classified = total - (cold_fn)  # all events we called something
            cold_fp_rate = cold_fp / max(cold_total_classified, 1)
            cold_fn_rate = cold_fn / max(total, 1)
            sat_fp_rate  = saturated_fp / max(cold_total_classified, 1)

            # Too many cold false positives → raise the bar
            if cold_fp_rate > 0.20:
                cold_streak_ratio = min(0.70, cold_streak_ratio + 0.05)
                cold_edge_short_max = min(-0.02, cold_edge_short_max - 0.02)
                cold_min_total = min(4, cold_min_total + 1)

            # Too many cold misses → lower the bar
            elif cold_fn_rate > 0.20:
                cold_streak_ratio = max(0.30, cold_streak_ratio - 0.05)
                cold_edge_short_max = max(0.02, cold_edge_short_max + 0.02)
                cold_min_total = max(1, cold_min_total - 1)

        # ── Confidence weights ────────────────────────────────────────────────
        # Edge divergence is the most reliable signal — keep weight highest
        weight_cold_streak    = round(float(t.get("weight_cold_streak") or 1.0), 3)
        weight_edge_div       = round(float(t.get("weight_edge_divergence") or 1.5), 3)
        weight_policy_support = round(float(t.get("weight_policy_support") or 0.5), 3)

        now = datetime.now(timezone.utc).isoformat()
        thresholds = {
            "cold_streak_ratio":           round(cold_streak_ratio, 3),
            "cold_edge_long_min":          round(cold_edge_long_min, 3),
            "cold_edge_short_max":         round(cold_edge_short_max, 3),
            "cold_edge_absolute_max":      round(cold_edge_absolute_max, 3),
            "cold_min_total_strategies":   cold_min_total,
            "exhausted_max_runs_analyzed": int(t.get("exhausted_max_runs_analyzed") or 0),
            "weight_cold_streak":          weight_cold_streak,
            "weight_edge_divergence":      weight_edge_div,
            "weight_policy_support":       weight_policy_support,
            "total_classifications":       total,
            "correct_classifications":     int(t.get("correct_classifications") or 0),
            "cold_fp_count":               cold_fp,
            "cold_fn_count":               cold_fn,
            "saturated_fp_count":          saturated_fp,
            "last_calibrated_at":          now,
        }

        conn.execute(
            """
            UPDATE classifier_thresholds SET
                cold_streak_ratio       = ?,
                cold_edge_long_min      = ?,
                cold_edge_short_max     = ?,
                cold_edge_absolute_max  = ?,
                cold_min_total_strategies = ?,
                last_calibrated_at      = ?,
                updated_at              = ?
            WHERE id = 1
            """,
            (
                thresholds["cold_streak_ratio"],
                thresholds["cold_edge_long_min"],
                thresholds["cold_edge_short_max"],
                thresholds["cold_edge_absolute_max"],
                thresholds["cold_min_total_strategies"],
                now, now,
            ),
        )
        conn.commit()
        return thresholds
    finally:
        conn.close()


def _default_classifier_thresholds() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "cold_streak_ratio": 0.5,
        "cold_edge_long_min": 0.0,
        "cold_edge_short_max": 0.0,
        "cold_edge_absolute_max": -0.05,
        "cold_min_total_strategies": 2,
        "exhausted_max_runs_analyzed": 0,
        "weight_cold_streak": 1.0,
        "weight_edge_divergence": 1.5,
        "weight_policy_support": 0.5,
        "total_classifications": 0,
        "correct_classifications": 0,
        "cold_fp_count": 0,
        "cold_fn_count": 0,
        "saturated_fp_count": 0,
        "last_calibrated_at": now,
    }


def get_classifier_thresholds(max_age_seconds: int = 3600) -> dict:
    """
    Return current classifier thresholds. Recomputes if stale or missing.
    """
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM classifier_thresholds WHERE id = 1").fetchone()
        if row:
            row = dict(row)
            last_cal = row.get("last_calibrated_at") or row.get("updated_at")
            if last_cal:
                try:
                    age_s = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(last_cal.replace("Z", "+00:00"))
                    ).total_seconds()
                    if age_s < max_age_seconds:
                        return {
                            "cold_streak_ratio":           float(row.get("cold_streak_ratio") or 0.5),
                            "cold_edge_long_min":          float(row.get("cold_edge_long_min") or 0.0),
                            "cold_edge_short_max":         float(row.get("cold_edge_short_max") or 0.0),
                            "cold_edge_absolute_max":      float(row.get("cold_edge_absolute_max") or -0.05),
                            "cold_min_total_strategies":   int(row.get("cold_min_total_strategies") or 2),
                            "exhausted_max_runs_analyzed": int(row.get("exhausted_max_runs_analyzed") or 0),
                            "weight_cold_streak":          float(row.get("weight_cold_streak") or 1.0),
                            "weight_edge_divergence":      float(row.get("weight_edge_divergence") or 1.5),
                            "weight_policy_support":       float(row.get("weight_policy_support") or 0.5),
                            "total_classifications":       int(row.get("total_classifications") or 0),
                            "correct_classifications":     int(row.get("correct_classifications") or 0),
                            "cold_fp_count":               int(row.get("cold_fp_count") or 0),
                            "cold_fn_count":               int(row.get("cold_fn_count") or 0),
                            "saturated_fp_count":          int(row.get("saturated_fp_count") or 0),
                            "last_calibrated_at":          last_cal,
                        }
                except Exception:
                    pass
    finally:
        conn.close()

    return compute_classifier_thresholds()


def get_classifier_accuracy_report() -> dict:
    """
    Return a summary accuracy report from classifier_calibration_log.
    Covers: overall accuracy, per-state breakdown, recent calibration events.
    """
    import json as _json

    conn = get_conn()
    try:
        # ── Overall accuracy ──────────────────────────────────────────────────
        total_verified = conn.execute(
            "SELECT COUNT(*) FROM classifier_calibration_log WHERE is_correct IS NOT NULL"
        ).fetchone()[0]
        correct = conn.execute(
            "SELECT COUNT(*) FROM classifier_calibration_log WHERE is_correct = 1"
        ).fetchone()[0]
        accuracy = round(correct / max(total_verified, 1), 4) if total_verified > 0 else None

        # ── Per-state breakdown ───────────────────────────────────────────────
        per_state: dict[str, dict] = {}
        for row in conn.execute("""
            SELECT state,
                   COUNT(*)                                          AS total,
                   SUM(CASE WHEN is_correct IS NOT NULL THEN 1 ELSE 0 END) AS verified,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END)        AS correct,
                   SUM(CASE WHEN fp_fn_type = 'FP' THEN 1 ELSE 0 END)     AS fp,
                   SUM(CASE WHEN fp_fn_type = 'FN' THEN 1 ELSE 0 END)     AS fn,
                   AVG(confidence_score)                                   AS avg_confidence
            FROM classifier_calibration_log
            GROUP BY state
        """).fetchall():
            s = dict(row)
            verified = s.get("verified") or 0
            corr = s.get("correct") or 0
            per_state[s["state"]] = {
                "total":         s.get("total") or 0,
                "verified":      verified,
                "accuracy":      round(corr / max(verified, 1), 4) if verified > 0 else None,
                "fp_count":      s.get("fp") or 0,
                "fn_count":      s.get("fn") or 0,
                "avg_confidence": round(float(s.get("avg_confidence") or 0.0), 4),
            }

        # ── FP/FN rate for cold regime ────────────────────────────────────────
        cold = per_state.get("COLD_REGIME", {})
        cold_fp_rate = (
            round(cold["fp_count"] / max(cold["verified"], 1), 4)
            if cold.get("verified", 0) > 0 else None
        )
        cold_fn_rate = (
            round(cold["fn_count"] / max(cold["verified"], 1), 4)
            if cold.get("verified", 0) > 0 else None
        )

        # ── Recent 10 calibration events ─────────────────────────────────────
        recent_rows = conn.execute("""
            SELECT id, classified_at, state, confidence_score, confidence_label,
                   reason, outcome_state, fp_fn_type, is_correct
            FROM classifier_calibration_log
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        recent = [dict(r) for r in recent_rows]

        # ── Threshold snapshot ────────────────────────────────────────────────
        thresholds = get_classifier_thresholds()

        return {
            "total_verified":  total_verified,
            "correct":         correct,
            "accuracy":        accuracy,
            "per_state":       per_state,
            "cold_fp_rate":    cold_fp_rate,
            "cold_fn_rate":    cold_fn_rate,
            "recent_events":   recent,
            "current_thresholds": thresholds,
        }
    finally:
        conn.close()


def compute_adaptive_policy(lookback_runs: int = 20) -> dict:
    """
    Derive adaptive execution weights from historical signal data.
    Persists the result to adaptive_policy_state and returns it.
    Called after each run with a recorded intent signal.
    """
    import json as _json

    conn = get_conn()
    try:
        # ── 1. Per-intent stats from cto_intent_signals ──────────────────────
        intent_stats = {}
        for row in conn.execute("""
            SELECT
                run_intent,
                COUNT(*)                                          AS total_runs,
                SUM(merged_count)                                 AS total_merged,
                SUM(approved_count)                               AS total_approved,
                SUM(rejected_count)                               AS total_rejected,
                SUM(candidate_count)                              AS total_candidates,
                SUM(is_compare_only)                              AS compare_only_runs,
                CASE WHEN SUM(candidate_count) > 0
                     THEN ROUND(SUM(merged_count) * 1.0 / SUM(candidate_count), 4)
                     ELSE 0 END                                   AS merge_rate,
                CASE WHEN SUM(candidate_count) > 0
                     THEN ROUND(SUM(approved_count) * 1.0 / SUM(candidate_count), 4)
                     ELSE 0 END                                   AS approved_rate
            FROM cto_intent_signals
            GROUP BY run_intent
        """).fetchall():
            intent_stats[row["run_intent"]] = dict(row)

        # ── 2. Recent N completed runs for overall merge rate ─────────────────
        recent = conn.execute("""
            SELECT merged_count, candidate_count
            FROM cto_review_runs
            WHERE completed_at IS NOT NULL AND candidate_count > 0
            ORDER BY started_at DESC LIMIT ?
        """, (lookback_runs,)).fetchall()
        total_merged_recent = sum(r["merged_count"] or 0 for r in recent)
        total_cand_recent   = sum(r["candidate_count"] or 0 for r in recent)
        overall_merge_rate  = round(total_merged_recent / max(total_cand_recent, 1), 4)
        runs_analyzed = len(recent)

        # ── 3. Backlog category completion signal ─────────────────────────────
        cat_rows = conn.execute("""
            SELECT category,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS done
            FROM cto_backlog_items
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            HAVING total >= 3
        """).fetchall()
        # boost range: -0.3 to +0.3  (centered at 0.5 completion rate)
        category_completion: dict[str, float] = {}
        category_priority_boosts: dict[str, float] = {}
        for r in cat_rows:
            rate = round(r["done"] / max(r["total"], 1), 4)
            category_completion[r["category"]] = rate
            category_priority_boosts[r["category"]] = round((rate - 0.5) * 0.6, 3)

        # ── 4. Compute intent adjustments ─────────────────────────────────────
        retry    = intent_stats.get("retry",    {})
        override = intent_stats.get("override", {})
        compare  = intent_stats.get("compare",  {})

        retry_runs    = int(retry.get("total_runs")    or 0)
        override_runs = int(override.get("total_runs") or 0)
        compare_runs  = int(compare.get("total_runs")  or 0)

        retry_merge_rate       = float(retry.get("merge_rate")     or 0.0)
        override_merge_rate    = float(override.get("merge_rate")   or 0.0)
        compare_approved_rate  = float(compare.get("approved_rate") or 0.0)

        # Retry coverage limit: scale with historical retry merge success
        _MIN_RUNS = 3
        if retry_runs >= _MIN_RUNS:
            if retry_merge_rate >= 0.6:
                retry_coverage_limit = 400   # proven high return → cast a wide net
            elif retry_merge_rate >= 0.4:
                retry_coverage_limit = 300
            elif retry_merge_rate < 0.2:
                retry_coverage_limit = 100   # poor return → stay conservative
            else:
                retry_coverage_limit = 200
        else:
            retry_coverage_limit = 200   # not enough data — use default

        # ── 5. Generate policy suggestions ────────────────────────────────────
        suggestions: list[dict] = []

        if retry_runs >= _MIN_RUNS and override_runs >= _MIN_RUNS:
            if retry_merge_rate > override_merge_rate + 0.15:
                diff_pct = round((retry_merge_rate - override_merge_rate) * 100)
                suggestions.append({
                    "level": "recommend",
                    "intent": "retry",
                    "text": (
                        f"建議多用 retry：合併率較 override 高 {diff_pct}%"
                        f"（retry {retry_merge_rate:.0%} vs override {override_merge_rate:.0%}）"
                    ),
                })

        if override_runs >= _MIN_RUNS and override_merge_rate < 0.30:
            suggestions.append({
                "level": "warn",
                "intent": "override",
                "text": (
                    f"override 合併率偏低（{override_merge_rate:.0%}）"
                    "，建議先用 compare 確認再決定是否重試"
                ),
            })

        if compare_runs >= 5 and compare_approved_rate < 0.01:
            suggestions.append({
                "level": "info",
                "intent": "compare",
                "text": "compare run 尚未發現可合併候選，考慮減少使用頻率",
            })
        elif compare_runs >= 3 and compare_approved_rate >= 0.5:
            suggestions.append({
                "level": "recommend",
                "intent": "compare",
                "text": (
                    f"compare run 分析準確率高（{compare_approved_rate:.0%}）"
                    "，可作為執行前預覽工具"
                ),
            })

        if runs_analyzed >= 5 and overall_merge_rate < 0.30:
            suggestions.append({
                "level": "warn",
                "intent": "system",
                "text": (
                    f"整體合併率偏低（{overall_merge_rate:.0%}，最近 {runs_analyzed} 次 run）"
                    "，建議檢查 gate 設定或提交品質"
                ),
            })
        elif runs_analyzed >= 5 and overall_merge_rate >= 0.70:
            suggestions.append({
                "level": "ok",
                "intent": "system",
                "text": (
                    f"系統整體合併率良好（{overall_merge_rate:.0%}，"
                    f"最近 {runs_analyzed} 次 run）"
                ),
            })

        for cat, boost in sorted(category_priority_boosts.items(), key=lambda x: abs(x[1]), reverse=True):
            rate = category_completion.get(cat, 0.0)
            if boost >= 0.2:
                suggestions.append({
                    "level": "info",
                    "intent": "backlog",
                    "text": f"backlog 類別「{cat}」完成率高（{rate:.0%}），優先權已自動 +{round(boost * 20, 1)} 分",
                })
            elif boost <= -0.2:
                suggestions.append({
                    "level": "info",
                    "intent": "backlog",
                    "text": f"backlog 類別「{cat}」完成率低（{rate:.0%}），優先權已自動 {round(boost * 20, 1)} 分",
                })

        # ── 6. Confidence level ───────────────────────────────────────────────
        if runs_analyzed >= 10 and (retry_runs + override_runs) >= 5:
            confidence = "high"
        elif runs_analyzed >= 5 or (retry_runs + override_runs) >= 3:
            confidence = "medium"
        else:
            confidence = "low"

        now = datetime.now(timezone.utc).isoformat()
        policy = {
            "retry_coverage_limit":    retry_coverage_limit,
            "retry_merge_rate":        round(retry_merge_rate, 4),
            "override_merge_rate":     round(override_merge_rate, 4),
            "compare_approved_rate":   round(compare_approved_rate, 4),
            "overall_merge_rate":      round(overall_merge_rate, 4),
            "category_priority_boosts": category_priority_boosts,
            "intent_stats":            intent_stats,
            "suggestions":             suggestions,
            "policy_confidence":       confidence,
            "runs_analyzed":           runs_analyzed,
            "computed_at":             now,
        }

        # ── 7. Persist ────────────────────────────────────────────────────────
        conn.execute("""
            INSERT OR REPLACE INTO adaptive_policy_state
                (id, retry_coverage_limit, retry_merge_rate, override_merge_rate,
                 compare_approved_rate, overall_merge_rate,
                 category_priority_boosts, suggestions,
                 policy_confidence, runs_analyzed, computed_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            retry_coverage_limit,
            round(retry_merge_rate, 4),
            round(override_merge_rate, 4),
            round(compare_approved_rate, 4),
            round(overall_merge_rate, 4),
            _json.dumps(category_priority_boosts, ensure_ascii=False),
            _json.dumps(suggestions, ensure_ascii=False),
            confidence, runs_analyzed, now,
        ))
        conn.commit()
        return policy
    finally:
        conn.close()


def get_adaptive_policy(max_age_seconds: int = 3600) -> dict:
    """
    Return the current adaptive policy.  Recomputes if data is older than
    `max_age_seconds` (default: 1 hour).
    """
    import json as _json

    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM adaptive_policy_state WHERE id = 1").fetchone()
        if row:
            row = dict(row)
            computed_at = row.get("computed_at")
            if computed_at:
                try:
                    age_s = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
                    ).total_seconds()
                    if age_s < max_age_seconds:
                        return {
                            "retry_coverage_limit":    row.get("retry_coverage_limit", 200),
                            "retry_merge_rate":        row.get("retry_merge_rate", 0.0),
                            "override_merge_rate":     row.get("override_merge_rate", 0.0),
                            "compare_approved_rate":   row.get("compare_approved_rate", 0.0),
                            "overall_merge_rate":      row.get("overall_merge_rate", 0.0),
                            "category_priority_boosts": _json.loads(
                                row.get("category_priority_boosts") or "{}"
                            ),
                            "suggestions":  _json.loads(row.get("suggestions") or "[]"),
                            "policy_confidence":  row.get("policy_confidence", "low"),
                            "runs_analyzed":      row.get("runs_analyzed", 0),
                            "computed_at":        computed_at,
                            "intent_stats":       {},   # not persisted — use get_intent_stats()
                        }
                except Exception:
                    pass
    finally:
        conn.close()

    return compute_adaptive_policy()


def update_cto_review_run(run_id: str, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [run_id]
    conn = get_conn()
    try:
        conn.execute(f"UPDATE cto_review_runs SET {sets} WHERE run_id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def get_cto_review_run(run_id: str):
    cleanup_stale_cto_review_runs()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cto_review_runs WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return _enrich_cto_review_run(row) if row else None
    finally:
        conn.close()


def get_latest_cto_review_run():
    cleanup_stale_cto_review_runs()
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT 1").fetchone()
        return _enrich_cto_review_run(row) if row else None
    finally:
        conn.close()


def list_cto_review_runs(limit: int = 20, offset: int = 0):
    cleanup_stale_cto_review_runs()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_enrich_cto_review_run(r) for r in rows]
    finally:
        conn.close()


# ─── CTO Backlog Items ────────────────────────────────────────────────────────

# ── Priority Scoring Engine ───────────────────────────────────────────────────
#
#  priority_score = (severity_pts × 35) + (impact × 0.30) + (urgency_pts × 20)
#                + (category_weight × 10) + recency_pts
#
#  Capped at 100. CRITICAL items are recency-immune.
#
_SEVERITY_PTS = {"CRITICAL": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
_URGENCY_PTS  = {"IMMEDIATE": 100, "HIGH": 80, "SHORT": 55, "MEDIUM": 30, "LOW": 10}
_CATEGORY_WEIGHT = {
    "architecture":  1.0,
    "validation":    1.0,
    "security":      1.0,
    "performance":   0.8,
    "quality":       0.7,
    "tech_debt":     0.6,
    "uiux":          0.5,
    "knowledge":     0.3,
    "other":         0.4,
}
_PRIORITY_THRESHOLDS = [
    ("P0", 80),   # P0: score >= 80
    ("P1", 58),   # P1: score >= 58
    ("P2", 35),   # P2: score >= 35
    ("P3",  0),   # P3: everything else
]


def compute_priority_score(severity, impact_score, urgency, category, created_at=None):
    """
    Compute a 0-100 priority score and return (priority_score, priority_level).

    Formula:
      score = sev_pts*0.35 + impact*0.30 + urg_pts*0.20 + cat_w*10 + recency_pts
    CRITICAL items are recency-immune; others get up to +5 pts for being recent (≤7 days).
    """
    sev = (severity or "LOW").upper()
    urg = (urgency or "MEDIUM").upper()
    cat = (category or "other").lower()

    sev_pts = _SEVERITY_PTS.get(sev, 15)
    imp_pts = min(100, max(0, int(impact_score or 0)))
    urg_pts = _URGENCY_PTS.get(urg, 30)
    cat_w   = _CATEGORY_WEIGHT.get(cat, 0.4)

    score = sev_pts * 0.35 + imp_pts * 0.30 + urg_pts * 0.20 + cat_w * 10.0

    # Recency bonus (≤3 days → +5, ≤7 days → +3); CRITICAL immune to recency (always max)
    if sev != "CRITICAL" and created_at:
        try:
            created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days
            if age_days <= 3:
                score += 5
            elif age_days <= 7:
                score += 3
        except Exception:
            pass
    elif sev == "CRITICAL":
        score = max(score, 85)  # CRITICAL always sits at the top

    score = min(100.0, max(0.0, round(score, 2)))

    # Determine priority level
    for level, threshold in _PRIORITY_THRESHOLDS:
        if score >= threshold:
            return score, level

    return score, "P3"


def _rerank_items(conn, items):
    """
    Assign rank 1..N by (priority_level asc, priority_score desc, id asc).
    Updates DB rows in one transaction.
    """
    _level_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    sorted_items = sorted(
        items,
        key=lambda x: (_level_order.get(x.get("priority_level", "P3"), 9),
                        -float(x.get("priority_score") or 0),
                        int(x.get("id") or 0)),
    )
    now = datetime.now(timezone.utc).isoformat()
    for rank, item in enumerate(sorted_items, start=1):
        conn.execute(
            "UPDATE cto_backlog_items SET rank = ?, updated_at = ? WHERE id = ?",
            (rank, now, item["id"]),
        )
    return sorted_items


def rescore_all_backlog_items():
    """
    Recompute priority_score, priority_level, and rank for every backlog item.
    Applies adaptive policy category boosts on top of the base formula.
    Called after batch inserts or on demand via API.
    Returns list of updated items sorted by rank.
    """
    import json as _json

    # Load category boosts from adaptive policy (use cached, 2h TTL)
    try:
        _policy = get_adaptive_policy(max_age_seconds=7200)
        _cat_boosts: dict = _policy.get("category_priority_boosts") or {}
    except Exception:
        _cat_boosts = {}

    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM cto_backlog_items").fetchall()
        items = [dict(r) for r in rows]
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            base_score, level = compute_priority_score(
                item.get("severity"),
                item.get("impact_score"),
                item.get("urgency"),
                item.get("category"),
                item.get("created_at"),
            )
            # Apply adaptive category boost: boost * 20 → ±6 pts max
            _boost = _cat_boosts.get(item.get("category") or "other", 0.0)
            score = min(100.0, max(0.0, round(base_score + _boost * 20, 2)))
            # Re-derive level after boost
            for _lv, _thr in _PRIORITY_THRESHOLDS:
                if score >= _thr:
                    level = _lv
                    break
            conn.execute(
                "UPDATE cto_backlog_items SET priority_score = ?, priority_level = ?, updated_at = ? WHERE id = ?",
                (score, level, now, item["id"]),
            )
            item["priority_score"] = score
            item["priority_level"] = level
        sorted_items = _rerank_items(conn, items)
        conn.commit()
        return sorted_items
    finally:
        conn.close()


def insert_cto_backlog_item(
    finding_id,
    cto_run_id,
    severity=None,
    impact_score=None,
    urgency=None,
    category=None,
    suggested_action=None,
    task_id=None,
    task_slot_key=None,
    status="pending",
    source="cto_review",
):
    """Insert a new CTO backlog item with computed priority. Raises sqlite3.IntegrityError on dup."""
    now = datetime.now(timezone.utc).isoformat()
    p_score, p_level = compute_priority_score(severity, impact_score, urgency, category, now)
    conn = get_conn()
    try:
        c = conn.execute(
            """INSERT INTO cto_backlog_items
               (finding_id, cto_run_id, source, severity, impact_score, urgency, category,
                suggested_action, task_id, task_slot_key, status,
                priority_score, priority_level,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (finding_id, cto_run_id, source, severity, impact_score, urgency, category,
             suggested_action, task_id, task_slot_key, status,
             p_score, p_level,
             now, now),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def get_cto_backlog_item_by_finding(finding_id):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cto_backlog_items WHERE finding_id = ?", (finding_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_cto_backlog_items(cto_run_id=None, status=None, limit=200):
    conds, vals = [], []
    if cto_run_id:
        conds.append("cto_run_id = ?")
        vals.append(cto_run_id)
    if status:
        conds.append("status = ?")
        vals.append(status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    vals.append(limit)
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT * FROM cto_backlog_items {where} ORDER BY id DESC LIMIT ?", vals
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_cto_backlog_items_prioritized(status_filter=None, limit=200):
    """
    Return backlog items sorted by (priority_level asc, priority_score desc, id asc).
    Optional status_filter: list of status strings, e.g. ['queued', 'pending'].
    """
    conn = get_conn()
    try:
        _level_order_sql = "CASE priority_level WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END"
        if status_filter:
            placeholders = ",".join("?" * len(status_filter))
            rows = conn.execute(
                f"""SELECT cbi.*, at.status AS task_live_status
                    FROM cto_backlog_items cbi
                    LEFT JOIN agent_tasks at ON at.id = cbi.task_id
                    WHERE at.status IN ({placeholders}) OR (cbi.task_id IS NULL AND 'pending' IN ({placeholders}))
                    ORDER BY {_level_order_sql}, priority_score DESC, cbi.id ASC
                    LIMIT ?""",
                status_filter + status_filter + [limit],
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT cbi.*, at.status AS task_live_status
                    FROM cto_backlog_items cbi
                    LEFT JOIN agent_tasks at ON at.id = cbi.task_id
                    ORDER BY {_level_order_sql}, priority_score DESC, cbi.id ASC
                    LIMIT ?""",
                [limit],
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_next_queued_task_by_priority():
    """
    Claim-aware: return the highest-priority QUEUED agent_task.
    Joins cto_backlog_items to get priority_score; falls back to id ordering.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT at.*,
                   COALESCE(cbi.priority_score, 0)  AS _p_score,
                   COALESCE(cbi.priority_level, 'P3') AS _p_level
            FROM agent_tasks at
            LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
            WHERE at.status = 'QUEUED'
            ORDER BY
                CASE COALESCE(cbi.priority_level,'P3')
                     WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END ASC,
                COALESCE(cbi.priority_score, 0) DESC,
                at.id ASC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_cto_backlog_item(item_id, **kwargs):
    if not kwargs:
        return
    # If severity/impact/urgency/category changed → recompute priority
    priority_fields = {"severity", "impact_score", "urgency", "category"}
    if priority_fields.intersection(kwargs):
        # fetch current state then merge
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM cto_backlog_items WHERE id = ?", (item_id,)).fetchone()
        finally:
            conn.close()
        if row:
            merged = dict(row)
            merged.update(kwargs)
            score, level = compute_priority_score(
                merged.get("severity"), merged.get("impact_score"),
                merged.get("urgency"), merged.get("category"),
                merged.get("created_at"),
            )
            kwargs["priority_score"] = score
            kwargs["priority_level"] = level
    kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [item_id]
    conn = get_conn()
    try:
        conn.execute(f"UPDATE cto_backlog_items SET {sets} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def get_cto_backlog_item_task_status(item):
    """
    Derive a display status for a cto_backlog_item by joining with agent_tasks.
    Returns: pending | queued | running | completed | failed | cancelled
    """
    task_id = item.get("task_id")
    if not task_id:
        return item.get("status") or "pending"
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM agent_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return item.get("status") or "pending"
        ts = (row["status"] or "").upper()
        mapping = {
            "QUEUED": "queued",
            "RUNNING": "running",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "FAILED_NO_EDGE": "failed",
            "FAILED_WEAK_EDGE": "failed",
            "CANCELLED": "cancelled",
            "REPLAN_REQUIRED": "failed",
        }
        return mapping.get(ts, ts.lower())
    finally:
        conn.close()


# ─── Execution Policy Engine ──────────────────────────────────────────────────
#
#  Scheduler modes:
#   strict_priority — always pick highest P0 → P1 → P2 → P3 (greedy, can starve)
#   balanced        — 70% from P0/P1 pool, 30% from P2/P3 pool; category quota
#   fairness        — round-robin categories + aging; prevents all forms of starvation
#
#  Policy constants
_POLICY_HIGH_POOL_RATIO = 0.70   # fraction of ticks devoted to P0/P1
_POLICY_FAIRNESS_EVERY  = 7      # every N ticks at least 1 non-P0 in strict/balanced
_CATEGORY_MAX_CONSECUTIVE = 5    # same category ≤ 5 consecutive ticks
_AGING_INTERVAL_HOURS   = 6      # apply aging bonus every 6h of inactivity
_AGING_PTS_PER_INTERVAL = 3.0    # +3 pts per interval, capped at +30
_AGING_CAP              = 30.0

_VALID_MODES = {"strict_priority", "balanced", "fairness"}


def get_policy_state():
    """Return the single execution_policy_state row as a dict."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM execution_policy_state WHERE id = 1").fetchone()
        if not row:
            return {
                "mode": "balanced",
                "consecutive_high": 0,
                "consecutive_category": None,
                "consecutive_category_count": 0,
                "recent_selections": [],
            }
        d = dict(row)
        try:
            d["recent_selections"] = json.loads(d.get("recent_selections") or "[]")
        except Exception:
            d["recent_selections"] = []
        return d
    finally:
        conn.close()


def set_policy_mode(mode):
    """Set execution policy mode ('strict_priority' | 'balanced' | 'fairness')."""
    if mode not in _VALID_MODES:
        raise ValueError(f"Unknown policy mode: {mode!r}. Valid: {sorted(_VALID_MODES)}")
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE execution_policy_state SET mode = ?, updated_at = ? WHERE id = 1",
            (mode, now),
        )
        conn.commit()
    finally:
        conn.close()


def _update_policy_state_after_selection(conn, task_id, priority_level, category):
    """Update rolling state after a task is selected. Called inside a transaction."""
    row = conn.execute("SELECT * FROM execution_policy_state WHERE id = 1").fetchone()
    if not row:
        return
    state = dict(row)

    is_high = priority_level in ("P0", "P1")
    new_consec_high = (state["consecutive_high"] + 1) if is_high else 0

    cat = (category or "other").lower()
    if cat == state.get("consecutive_category"):
        new_cat_count = (state["consecutive_category_count"] or 0) + 1
    else:
        new_cat_count = 1

    # Maintain recent_selections as a rolling list of last 20 (level, category, task_id)
    try:
        recent = json.loads(state.get("recent_selections") or "[]")
    except Exception:
        recent = []
    recent.append({"level": priority_level, "category": cat, "task_id": task_id})
    recent = recent[-20:]  # keep last 20

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE execution_policy_state
           SET consecutive_high = ?,
               consecutive_category = ?,
               consecutive_category_count = ?,
               recent_selections = ?,
               updated_at = ?
           WHERE id = 1""",
        (new_consec_high, cat, new_cat_count, json.dumps(recent), now),
    )

    # Also update the backlog item's selection tracking
    conn.execute(
        """UPDATE cto_backlog_items
           SET last_selected_at = ?,
               selection_count = COALESCE(selection_count, 0) + 1,
               updated_at = ?
           WHERE task_id = ?""",
        (now, now, task_id),
    )


def apply_aging_bonus():
    """
    Award aging_bonus to backlog items that have been waiting too long.
    +_AGING_PTS_PER_INTERVAL per _AGING_INTERVAL_HOURS of waiting, capped at _AGING_CAP.
    Only applies to items whose linked task is still QUEUED.
    Returns count of updated items.
    """
    now = datetime.now(timezone.utc)
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT cbi.id, cbi.aging_bonus, cbi.last_selected_at, cbi.created_at,
                   cbi.priority_level
            FROM cto_backlog_items cbi
            LEFT JOIN agent_tasks at ON at.id = cbi.task_id
            WHERE (at.status = 'QUEUED' OR cbi.task_id IS NULL)
              AND COALESCE(cbi.aging_bonus, 0) < ?
            """,
            (_AGING_CAP,),
        ).fetchall()

        updated = 0
        now_iso = now.isoformat()
        for row in rows:
            # Reference point: last_selected_at or created_at
            ref_ts = row["last_selected_at"] or row["created_at"]
            try:
                ref_dt = datetime.fromisoformat(str(ref_ts).replace("Z", "+00:00"))
                if ref_dt.tzinfo is None:
                    ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            hours_waiting = (now - ref_dt).total_seconds() / 3600.0
            intervals = int(hours_waiting / _AGING_INTERVAL_HOURS)
            if intervals < 1:
                continue

            new_bonus = min(_AGING_CAP, (row["aging_bonus"] or 0) + intervals * _AGING_PTS_PER_INTERVAL)
            if new_bonus <= (row["aging_bonus"] or 0):
                continue

            conn.execute(
                "UPDATE cto_backlog_items SET aging_bonus = ?, updated_at = ? WHERE id = ?",
                (new_bonus, now_iso, row["id"]),
            )
            updated += 1

        conn.commit()
        return updated
    finally:
        conn.close()


def get_next_task_by_policy():
    """
    Policy-based task selection. Returns the single highest-priority QUEUED agent_task
    chosen according to the active execution policy mode.

    Modes:
      strict_priority — ORDER BY level, score DESC (pure greedy)
      balanced        — 70% high-pool (P0/P1), 30% low-pool (P2/P3)
                        enforced by consecutive_high counter
      fairness        — category round-robin + aging; every 7 ticks forces a non-P0
    """
    import random

    conn = get_conn()
    try:
        state = dict(conn.execute("SELECT * FROM execution_policy_state WHERE id = 1").fetchone() or {})
        mode = state.get("mode", "balanced")
        consecutive_high = state.get("consecutive_high", 0)
        consec_cat = (state.get("consecutive_category") or "").lower()
        consec_cat_count = state.get("consecutive_category_count", 0)

        # Effective score = priority_score + aging_bonus (used for sorting)
        _eff_score_sql = "COALESCE(cbi.priority_score, 0) + COALESCE(cbi.aging_bonus, 0)"
        _level_order_sql = (
            "CASE COALESCE(cbi.priority_level,'P3') "
            "WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END"
        )

        # Category quota guard: skip dominant category if over limit
        cat_exclude_clause = ""
        cat_exclude_params = []
        if consec_cat and consec_cat_count >= _CATEGORY_MAX_CONSECUTIVE:
            cat_exclude_clause = "AND LOWER(COALESCE(cbi.category,'other')) != ?"
            cat_exclude_params = [consec_cat]

        def _fetch_pool(level_filter_sql, extra_params=None):
            """Fetch candidate tasks from a given pool (high or low priority)."""
            params = []
            if cat_exclude_params:
                params.extend(cat_exclude_params)
            if extra_params:
                params.extend(extra_params)
            params.append(10)  # LIMIT
            row = conn.execute(
                f"""
                SELECT at.*,
                       COALESCE(cbi.priority_score, 0)   AS _p_score,
                       COALESCE(cbi.priority_level, 'P3') AS _p_level,
                       COALESCE(cbi.category, 'other')    AS _category,
                       COALESCE(cbi.aging_bonus, 0)       AS _aging_bonus,
                       {_eff_score_sql}                   AS _eff_score
                FROM agent_tasks at
                LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
                WHERE at.status = 'QUEUED'
                  {cat_exclude_clause}
                  {level_filter_sql}
                ORDER BY {_level_order_sql} ASC,
                         {_eff_score_sql} DESC,
                         at.id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(r) for r in row]

        # ── strict_priority ────────────────────────────────────────────────────
        if mode == "strict_priority":
            candidates = _fetch_pool("", [])
            # Still enforce fairness gate every _POLICY_FAIRNESS_EVERY ticks
            if consecutive_high >= _POLICY_FAIRNESS_EVERY:
                low_candidates = _fetch_pool(
                    "AND COALESCE(cbi.priority_level, 'P3') IN ('P2','P3')", []
                )
                if low_candidates:
                    chosen = low_candidates[0]
                    _update_policy_state_after_selection(
                        conn, chosen["id"], chosen.get("_p_level", "P3"), chosen.get("_category", "other")
                    )
                    conn.commit()
                    return chosen
            if candidates:
                chosen = candidates[0]
                _update_policy_state_after_selection(
                    conn, chosen["id"], chosen.get("_p_level", "P3"), chosen.get("_category", "other")
                )
                conn.commit()
                return chosen
            return None

        # ── balanced ──────────────────────────────────────────────────────────
        if mode == "balanced":
            high_pool = _fetch_pool(
                "AND COALESCE(cbi.priority_level, 'P3') IN ('P0','P1')", []
            )
            low_pool = _fetch_pool(
                "AND COALESCE(cbi.priority_level, 'P3') IN ('P2','P3')", []
            )

            # After _POLICY_FAIRNESS_EVERY consecutive high picks, force low
            force_low = consecutive_high >= _POLICY_FAIRNESS_EVERY
            # Otherwise weighted random: 70% high, 30% low
            use_high = (not force_low) and (not low_pool or random.random() < _POLICY_HIGH_POOL_RATIO)

            chosen = None
            if use_high and high_pool:
                chosen = high_pool[0]
            elif low_pool:
                chosen = low_pool[0]
            elif high_pool:
                chosen = high_pool[0]  # all low exhausted — fall back to high

            if chosen:
                _update_policy_state_after_selection(
                    conn, chosen["id"], chosen.get("_p_level", "P3"), chosen.get("_category", "other")
                )
                conn.commit()
            return chosen

        # ── fairness ──────────────────────────────────────────────────────────
        if mode == "fairness":
            # Get all QUEUED tasks (with effective scores)
            all_rows = conn.execute(
                f"""
                SELECT at.*,
                       COALESCE(cbi.priority_level, 'P3') AS _p_level,
                       COALESCE(cbi.category, 'other')    AS _category,
                       {_eff_score_sql}                   AS _eff_score,
                       COALESCE(cbi.selection_count, 0)   AS _sel_count
                FROM agent_tasks at
                LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
                WHERE at.status = 'QUEUED'
                """,
                [],
            ).fetchall()

            if not all_rows:
                return None

            # Group by category; within each category sort by priority then eff_score
            _level_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            from collections import defaultdict
            by_cat = defaultdict(list)
            for r in all_rows:
                by_cat[r["_category"]].append(dict(r))

            # Sort each category's candidates by priority then eff_score
            for cat in by_cat:
                by_cat[cat].sort(key=lambda x: (_level_rank.get(x["_p_level"], 3), -x["_eff_score"]))

            # Choose: first pick category with least recent usage, then best candidate
            # Recent category usage: count occurrences in recent_selections window
            try:
                recent = json.loads(state.get("recent_selections") or "[]")
            except Exception:
                recent = []
            recent_cat_counts = {}
            for sel in recent[-10:]:
                c = sel.get("category", "other")
                recent_cat_counts[c] = recent_cat_counts.get(c, 0) + 1

            # Score each category: lower recent_count + best candidate's eff_score
            def _cat_priority(cat):
                recent_count = recent_cat_counts.get(cat, 0)
                best_candidate = by_cat[cat][0]
                level_rank = _level_rank.get(best_candidate["_p_level"], 3)
                # Primary: level of best task; Secondary: recency penalty; Tertiary: eff_score desc
                return (level_rank, recent_count, -best_candidate["_eff_score"])

            # Exclude over-represented category
            eligible_cats = [c for c in by_cat if not (c == consec_cat and consec_cat_count >= _CATEGORY_MAX_CONSECUTIVE)]
            if not eligible_cats:
                eligible_cats = list(by_cat.keys())  # all cats exhausted quota — allow any

            chosen_cat = min(eligible_cats, key=_cat_priority)
            chosen = by_cat[chosen_cat][0]
            _update_policy_state_after_selection(
                conn, chosen["id"], chosen.get("_p_level", "P3"), chosen.get("_category", "other")
            )
            conn.commit()
            return chosen

        # Unknown mode — fall back to strict
        return None

    finally:
        conn.close()


def get_policy_stats():
    """Return policy state + queue snapshot for the API."""
    conn = get_conn()
    try:
        state = dict(conn.execute("SELECT * FROM execution_policy_state WHERE id = 1").fetchone() or {})
        try:
            state["recent_selections"] = json.loads(state.get("recent_selections") or "[]")
        except Exception:
            state["recent_selections"] = []

        # Queue snapshot grouped by priority level
        level_counts = {}
        for row in conn.execute(
            """SELECT COALESCE(cbi.priority_level,'P3') AS lvl, COUNT(*) AS cnt
               FROM agent_tasks at
               LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
               WHERE at.status = 'QUEUED'
               GROUP BY lvl"""
        ).fetchall():
            level_counts[row["lvl"]] = row["cnt"]

        # Category distribution
        cat_counts = {}
        for row in conn.execute(
            """SELECT COALESCE(cbi.category,'other') AS cat, COUNT(*) AS cnt
               FROM agent_tasks at
               LEFT JOIN cto_backlog_items cbi ON cbi.task_id = at.id
               WHERE at.status = 'QUEUED'
               GROUP BY cat"""
        ).fetchall():
            cat_counts[row["cat"]] = row["cnt"]

        # Items with aging_bonus > 0
        aging_count = (conn.execute(
            "SELECT COUNT(*) FROM cto_backlog_items WHERE aging_bonus > 0"
        ).fetchone() or [0])[0]

        return {
            "mode": state.get("mode", "balanced"),
            "consecutive_high": state.get("consecutive_high", 0),
            "consecutive_category": state.get("consecutive_category"),
            "consecutive_category_count": state.get("consecutive_category_count", 0),
            "recent_selections": state.get("recent_selections", [])[-10:],
            "queue_by_level": level_counts,
            "queue_by_category": cat_counts,
            "aging_items_count": aging_count,
            "policy_constants": {
                "high_pool_ratio": _POLICY_HIGH_POOL_RATIO,
                "fairness_every_n": _POLICY_FAIRNESS_EVERY,
                "category_max_consecutive": _CATEGORY_MAX_CONSECUTIVE,
                "aging_interval_hours": _AGING_INTERVAL_HOURS,
                "aging_pts_per_interval": _AGING_PTS_PER_INTERVAL,
                "aging_cap": _AGING_CAP,
            },
        }
    finally:
        conn.close()



    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM task_git_commits WHERE status = 'PENDING_REVIEW'",
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


# ── Strategy Review DB functions ──────────────────────────────────────────────

def list_strategy_review_candidates(since: Optional[str] = None, limit: int = 100) -> list:
    """Return completed tasks not yet strategy-reviewed (gate_verdict PASS or NULL)."""
    conn = get_conn()
    try:
        params: list = []
        sql = """
            SELECT t.id, t.slot_key, t.date_folder, t.title, t.slug,
                   t.status, t.completed_at, t.gate_verdict
              FROM agent_tasks t
         LEFT JOIN strategy_reviews sr ON sr.task_id = t.id
             WHERE t.status = 'COMPLETED'
               AND (t.gate_verdict = 'PASS' OR t.gate_verdict IS NULL)
               AND sr.id IS NULL
        """
        if since:
            sql += " AND t.completed_at >= ?"
            params.append(since)
        sql += " ORDER BY t.completed_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def insert_strategy_review(
    task_id: int,
    slot_key: str,
    review_run_id: str,
    decision: str,
    reason: str = None,
    game_type: str = None,
    strategy_name: str = None,
    edge_score: float = None,
    sharpe_ratio: float = None,
    drawdown: float = None,
    mc_passed: int = None,
    comparison_summary: str = None,
    task_title: str = None,
) -> int:
    """Insert a strategy review record and return its id."""
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """
            INSERT INTO strategy_reviews
                (task_id, slot_key, task_title, review_run_id, decision, reason,
                 game_type, strategy_name, edge_score, sharpe_ratio, drawdown,
                 mc_passed, comparison_summary, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id, slot_key, task_title, review_run_id, decision, reason,
                game_type, strategy_name, edge_score, sharpe_ratio, drawdown,
                mc_passed, comparison_summary, now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_strategy_review_for_task(task_id: int) -> Optional[dict]:
    """Return the latest strategy review for a task, or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM strategy_reviews WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_strategy_state(game_type: str) -> Optional[dict]:
    """Return the active/shadow strategy state for a game_type, or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM active_strategy_state WHERE game_type = ?",
            (game_type,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_active_strategy_states() -> list:
    """Return all game strategy states ordered by game_type."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM active_strategy_state ORDER BY game_type"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def set_active_strategy_state(
    game_type: str,
    active_strategy: Optional[str] = None,
    active_edge: Optional[float] = None,
    active_task_id: Optional[int] = None,
    shadow_strategy: Optional[str] = None,
    shadow_edge: Optional[float] = None,
    shadow_task_id: Optional[int] = None,
    planner_focus: Optional[str] = None,
) -> None:
    """Upsert the active/shadow strategy state for a game_type (partial update)."""
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        existing = conn.execute(
            "SELECT game_type FROM active_strategy_state WHERE game_type = ?",
            (game_type,),
        ).fetchone()
        if existing:
            updates: dict = {"updated_at": now}
            if active_strategy is not None:
                updates["active_strategy"] = active_strategy
            if active_edge is not None:
                updates["active_edge"] = active_edge
            if active_task_id is not None:
                updates["active_task_id"] = active_task_id
            if shadow_strategy is not None:
                updates["shadow_strategy"] = shadow_strategy
            if shadow_edge is not None:
                updates["shadow_edge"] = shadow_edge
            if shadow_task_id is not None:
                updates["shadow_task_id"] = shadow_task_id
            if planner_focus is not None:
                updates["planner_focus"] = planner_focus
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [game_type]
            conn.execute(
                f"UPDATE active_strategy_state SET {set_clause} WHERE game_type = ?",
                vals,
            )
        else:
            conn.execute(
                """
                INSERT INTO active_strategy_state
                    (game_type, active_strategy, active_edge, active_task_id,
                     shadow_strategy, shadow_edge, shadow_task_id, planner_focus, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    game_type, active_strategy, active_edge, active_task_id,
                    shadow_strategy, shadow_edge, shadow_task_id, planner_focus, now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ── Planner Directives ────────────────────────────────────────────────────────

def write_planner_directive(
    game_type: str,
    focus_direction: str,
    forbidden_families: list = None,
    required_validation: list = None,
    promotion_targets: list = None,
    kill_targets: list = None,
    budget_hint: str = None,
    note: str = None,
    expires_after_cycles: int = 10,
) -> str:
    """
    Write a CTO → Planner directive.

    Deactivation rules (per-focus_direction, not per-game_type):
    - Only deactivates a previous directive with the SAME (game_type, focus_direction).
    - Different focus_directions for the same game_type co-exist.
      e.g. avoid_rejected_family + shadow_validation can both be active simultaneously.
    Returns the new directive_id.
    """
    import uuid as _uuid
    now = datetime.now(timezone.utc).isoformat()
    directive_id = f"pd_{game_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{_uuid.uuid4().hex[:6]}"
    conn = get_conn()
    try:
        # Only deactivate directives with the SAME game_type AND focus_direction
        conn.execute(
            "UPDATE planner_directives SET is_active = 0, updated_at = ? "
            "WHERE game_type = ? AND focus_direction = ? AND is_active = 1",
            (now, game_type, focus_direction),
        )
        conn.execute(
            """
            INSERT INTO planner_directives
                (directive_id, game_type, focus_direction, forbidden_families,
                 required_validation, promotion_targets, kill_targets,
                 budget_hint, note, expires_after_cycles, cycle_count,
                 is_active, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,0,1,?,?)
            """,
            (
                directive_id, game_type, focus_direction,
                json.dumps(forbidden_families or [], ensure_ascii=False),
                json.dumps(required_validation or [], ensure_ascii=False),
                json.dumps(promotion_targets or [], ensure_ascii=False),
                json.dumps(kill_targets or [], ensure_ascii=False),
                budget_hint, note, expires_after_cycles, now, now,
            ),
        )
        conn.commit()
        logger.info("[PlannerDirective] written: %s game=%s focus=%s", directive_id, game_type, focus_direction)
        return directive_id
    finally:
        conn.close()


def get_active_planner_directives(game_type: str = None) -> list:
    """
    Return all active planner directives, optionally filtered by game_type.
    Also auto-expires directives that have exceeded expires_after_cycles.
    """
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        params = []
        sql = "SELECT * FROM planner_directives WHERE is_active = 1"
        if game_type:
            sql += " AND game_type = ?"
            params.append(game_type)
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        result = []
        expired_ids = []
        for row in rows:
            d = dict(row)
            if d.get("cycle_count", 0) >= d.get("expires_after_cycles", 10):
                expired_ids.append(d["directive_id"])
            else:
                try:
                    d["forbidden_families"] = json.loads(d.get("forbidden_families") or "[]")
                    d["required_validation"] = json.loads(d.get("required_validation") or "[]")
                    d["promotion_targets"] = json.loads(d.get("promotion_targets") or "[]")
                    d["kill_targets"] = json.loads(d.get("kill_targets") or "[]")
                except Exception:
                    pass
                result.append(d)
        if expired_ids:
            conn.execute(
                f"UPDATE planner_directives SET is_active = 0, updated_at = ? WHERE directive_id IN ({','.join('?' * len(expired_ids))})",
                [now] + expired_ids,
            )
            conn.commit()
        return result
    finally:
        conn.close()


def tick_planner_directive_cycles(directive_ids: list) -> None:
    """Increment cycle_count for given directive IDs (called by planner on each cycle)."""
    if not directive_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute(
            f"UPDATE planner_directives SET cycle_count = cycle_count + 1, updated_at = ? "
            f"WHERE directive_id IN ({','.join('?' * len(directive_ids))})",
            [now] + directive_ids,
        )
        conn.commit()
    finally:
        conn.close()
