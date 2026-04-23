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
                report_json_path, summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()
    finally:
        conn.close()


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


def count_pending_git_commits():
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM task_git_commits WHERE status = 'PENDING_REVIEW'",
        ).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()
