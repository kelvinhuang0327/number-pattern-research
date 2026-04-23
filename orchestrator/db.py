"""
Orchestrator standalone DB manager.
Uses its own SQLite file (orchestrator.db) — no dependency on lottery_api.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ORCH_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "runtime", "agent_orchestrator")
DB_PATH = os.path.join(ORCH_ROOT, "orchestrator.db")

DEFAULT_SETTINGS = {
    "scheduler_enabled": "1",
    "planner_provider": "claude",
    "worker_provider": "codex",
    "worker_copilot_model": "",
    "cto_review_frequency_mode": "once_daily",
    "cto_scheduler_enabled": "1",
    "cto_planner_provider": "claude",
    "cto_planner_model": "",
}
RUN_HISTORY_RETENTION = int(os.environ.get("ORCH_RUN_HISTORY_RETENTION", "5000"))


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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_status ON task_git_commits(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_task_id ON task_git_commits(task_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_commit_sha ON task_git_commits(commit_sha)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tgc_group ON task_git_commits(integration_group)")

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
        ]:
            if col_def[0] not in existing_cto_run_cols:
                c.execute(f"ALTER TABLE cto_review_runs ADD COLUMN {col_def[0]} {col_def[1]}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_dedupe ON cto_review_runs(dedupe_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_intent ON cto_review_runs(run_intent)")

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

        conn.commit()
        logger.info(f"[OrchestratorDB] init OK — {DB_PATH}")
    finally:
        conn.close()


def log_tick(runner: str, outcome: str, task_id=None, message: str = "", duration_ms: int = 0, request_id: str = None):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO agent_task_runs (runner, tick_at, outcome, request_id, task_id, message, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (runner, datetime.now(timezone.utc).isoformat(), outcome, request_id, task_id, message, duration_ms)
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


def create_task(slot_key, date_folder, title, slug, prompt_text, prompt_file_path, previous_task_id=None):
    conn = get_conn()
    try:
        c = conn.execute(
            """INSERT INTO agent_tasks
               (slot_key, date_folder, title, slug, status, prompt_text, prompt_file_path,
                previous_task_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?, ?, ?)""",
            (slot_key, date_folder, title, slug, prompt_text, prompt_file_path,
             previous_task_id,
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        return c.lastrowid
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
                gate_reason, created_at, updated_at
            ) VALUES (
                :task_id, :slot_key, :task_title, :source_branch, :commit_sha, :commit_message,
                :integration_group, :review_priority, :safe_to_autocommit, :status, :reviewer_role,
                :reviewed_at, :merge_branch, :merge_commit_sha, :reject_reason, :superseded_by_task_id,
                :superseded_by_commit_sha, :changed_files_json, :depends_on_tasks_json,
                :depends_on_commits_json, :high_conflict_paths_json, :task_status, :gate_verdict,
                :gate_reason, :created_at, :updated_at
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
                run_intent, parent_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_inflight_cto_run_by_dedupe_key(dedupe_key: str):
    """Return the most recent non-completed run with the given dedupe_key, or None."""
    if not dedupe_key:
        return None
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cto_review_runs WHERE dedupe_key = ? AND completed_at IS NULL ORDER BY id DESC LIMIT 1",
            (dedupe_key,),
        ).fetchone()
        return dict(row) if row else None
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
    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO classifier_calibration_log
                (classified_at, state, confidence_score, confidence_label,
                 reason, features_json, thresholds_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now, state, confidence_score, confidence_label,
             reason, features_json, thresholds_json),
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
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cto_review_runs WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_latest_cto_review_run():
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_cto_review_runs(limit: int = 20, offset: int = 0):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
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
