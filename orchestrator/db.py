"""
Orchestrator standalone DB manager.
Uses its own SQLite file (orchestrator.db) — no dependency on lottery_api.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

ORCH_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "runtime", "agent_orchestrator")
DB_PATH = os.path.join(ORCH_ROOT, "orchestrator.db")

DEFAULT_SETTINGS = {
    "scheduler_enabled": "1",
    "planner_provider": "claude",
    "worker_provider": "codex",
}


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
                task_id INTEGER,
                message TEXT,
                duration_ms INTEGER,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_runner ON agent_task_runs(runner)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_tick ON agent_task_runs(tick_at)")

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
        now = datetime.utcnow().isoformat()
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO orchestrator_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )

        conn.commit()
        logger.info(f"[OrchestratorDB] init OK — {DB_PATH}")
    finally:
        conn.close()


def log_tick(runner: str, outcome: str, task_id=None, message: str = "", duration_ms: int = 0):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO agent_task_runs (runner, tick_at, outcome, task_id, message, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (runner, datetime.utcnow().isoformat(), outcome, task_id, message, duration_ms)
        )
        conn.execute(
            """
            DELETE FROM agent_task_runs
            WHERE id NOT IN (
                SELECT id FROM agent_task_runs ORDER BY id DESC LIMIT 10
            )
            """
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
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def update_task(task_id: int, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
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
            (datetime.utcnow().isoformat(),)
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


def list_runs(runner=None, since=None, limit=200):
    conn = get_conn()
    try:
        conds, vals = [], []
        if runner:
            conds.append("runner = ?")
            vals.append(runner)
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
            (key, str(value), datetime.utcnow().isoformat()),
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
