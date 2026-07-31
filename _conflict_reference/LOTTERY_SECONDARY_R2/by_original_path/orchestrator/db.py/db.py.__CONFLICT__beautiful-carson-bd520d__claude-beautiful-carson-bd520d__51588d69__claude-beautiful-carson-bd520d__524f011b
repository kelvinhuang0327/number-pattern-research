"""
Betting-pool Orchestrator DB Manager
Betting-pool 任務編排 DB — agent_tasks、runs、scheduler_state 等表格的存取邏輯
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

ORCH_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "runtime", "agent_orchestrator")
DB_PATH = os.path.join(ORCH_ROOT, "orchestrator.db")

DEFAULT_SETTINGS = {
    "scheduler_enabled": "1",
    "llm_execution_mode": "safe-run",
    "planner_provider": "local",          # Phase 0: Planner 預設為本地執行
    "worker_provider": "codex",
    "worker_copilot_model": "",
    "cto_review_frequency_mode": "once_daily",
    "cto_scheduler_enabled": "1",
    "cto_planner_provider": "local",      # Phase 0: CTO Planner 預設為本地執行
    "cto_planner_model": "",
    # ── Track C/D 四軌排程設定 ──
    "track_c_enabled": "1",              # Track C 模擬壓力測試（0=停用）
    "track_c_interval_seconds": "1800",  # Track C 執行間隔（預設 30 分鐘）
    "track_d_enabled": "1",              # Track D 策略反饋迴圈（0=停用）
    "track_d_interval_seconds": "300",   # Track D 執行間隔（預設 5 分鐘）
    # ── 任務回收冷卻期設定 ──
    "task_recycle_cooldown_hours": "4",  # 已完成任務在此時間內不重建（小時）
    # ── Phase 0: 角色導向外部 LLM 配額開關 ──────────────────────────────────
    # 角色層級開關（0=封鎖, 1=允許）
    "ext_llm_role_planner": "0",         # Planner 不得呼叫外部 LLM
    "ext_llm_role_worker": "1",          # Worker 可呼叫外部 LLM（受 execution_policy 管控）
    "ext_llm_role_cto": "0",             # CTO 不得呼叫外部 LLM（本地確定性）
    # Provider × 角色細粒度開關（0=封鎖, 1=允許）
    "codex_enabled_for_planner": "0",
    "codex_enabled_for_worker": "1",
    "codex_enabled_for_cto": "0",
    "claude_enabled_for_planner": "0",
    "claude_enabled_for_worker": "1",
    "claude_enabled_for_cto": "0",
    "copilot_enabled_for_planner": "0",
    "copilot_enabled_for_worker": "1",
    "copilot_enabled_for_cto": "0",
    # Worker 配額上限
    "worker_daily_llm_cap": "100",       # Worker 每日外部 LLM 呼叫上限（0=不限制）
    "worker_hourly_llm_cap": "20",       # Worker 每小時外部 LLM 呼叫上限（0=不限制）
    "worker_max_retries_per_task": "2",  # Worker 每任務最大重試次數
    # Planner / CTO 硬性上限（永遠為 0）
    "planner_daily_llm_cap": "0",        # Planner 每日外部 LLM 上限（必須為 0）
    "cto_daily_llm_cap": "0",            # CTO 每日外部 LLM 上限（必須為 0）
}
RUN_HISTORY_RETENTION = int(os.environ.get("ORCH_RUN_HISTORY_RETENTION", "5000"))


def get_conn():
    os.makedirs(ORCH_ROOT, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migration_add_columns(cursor: sqlite3.Cursor, table: str, columns: list[tuple[str, str]]) -> None:
    """為現有表格新增欄位（若已存在則跳過）。"""
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists


def init_db():
    conn = get_conn()
    c = conn.cursor()
    try:
        # ── 主要任務表 ──
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
                dedupe_key TEXT,
                regime_state TEXT,
                confidence_snapshot REAL,
                epoch_id INTEGER NOT NULL DEFAULT 0,
                contract_json TEXT,
                focus_keys TEXT,
                signal_state_type TEXT,
                expected_duration_hours INTEGER,
                FOREIGN KEY (previous_task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_status ON agent_tasks(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_date ON agent_tasks(date_folder)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_dedupe ON agent_tasks(dedupe_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_regime ON agent_tasks(regime_state)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_at_epoch ON agent_tasks(epoch_id)")

        # ── Schema migration: add columns that may not exist in older DBs ──
        _migration_add_columns(c, "agent_tasks", [
            ("contract_json", "TEXT"),
            ("focus_keys", "TEXT"),
            ("signal_state_type", "TEXT"),
            ("expected_duration_hours", "INTEGER"),
            ("track", "TEXT"),  # A/B/C/D — 四軌排程標記
            ("task_type", "TEXT"),       # e.g. orchestration_smoke, match_monitor
            ("worker_type", "TEXT"),     # 'research' | 'light'
            ("completion_quality", "TEXT"),  # Phase 10 completion quality state
        ])

        # ── 任務執行記錄表 ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                runner TEXT NOT NULL,
                tick_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                request_id TEXT,
                task_id INTEGER,
                message TEXT,
                log_snippet TEXT,
                duration_seconds INTEGER,
                epoch_id INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_runner ON agent_task_runs(runner)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_tick_at ON agent_task_runs(tick_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_atr_epoch ON agent_task_runs(epoch_id)")

        # ── 系統設定表 ──
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── CTO 審核執行表 ──
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
                updated_at TEXT NOT NULL,
                dedupe_key TEXT,
                is_manual INTEGER NOT NULL DEFAULT 0,
                is_force_run INTEGER NOT NULL DEFAULT 0,
                run_intent TEXT,
                parent_run_id TEXT,
                epoch_id INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_started ON cto_review_runs(started_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_completed ON cto_review_runs(completed_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_dedupe ON cto_review_runs(dedupe_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cto_runs_intent ON cto_review_runs(run_intent)")

        # ── CTO Backlog 項目表 ──
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
                title TEXT,
                description TEXT,
                file_path TEXT,
                line_number INTEGER,
                status TEXT DEFAULT 'queued',
                priority_score INTEGER,
                assigned_to TEXT,
                estimated_hours REAL,
                task_id INTEGER,
                resolution_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                epoch_id INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_backlog_status ON cto_backlog_items(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_backlog_priority ON cto_backlog_items(priority_score)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_backlog_category ON cto_backlog_items(category)")

        # ── Phase 5: Exploration Routing State ──────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS exploration_routing_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_task_id INTEGER NOT NULL,
                source_lane TEXT NOT NULL,
                source_dedupe_key TEXT NOT NULL,
                source_report_path TEXT,
                decision TEXT,
                route_status TEXT NOT NULL,
                validation_task_id INTEGER,
                routed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_task_id) REFERENCES agent_tasks(id)
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_ers_source_task "
            "ON exploration_routing_state(source_task_id)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_ers_route_status "
            "ON exploration_routing_state(route_status)"
        )
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ers_source_unique "
            "ON exploration_routing_state(source_task_id)"
        )

        # 初始化預設設定
        for key, value in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

        conn.commit()
        logger.info(f"[BettingPoolOrchestratorDB] init OK — {DB_PATH}")
    except Exception as e:
        logger.error(f"[BettingPoolOrchestratorDB] init failed: {e}")
        raise
    finally:
        conn.close()


# ── Settings Management ──

def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_scheduler_enabled() -> bool:
    return get_setting("scheduler_enabled", "1") == "1"


def set_scheduler_enabled(enabled: bool) -> None:
    set_setting("scheduler_enabled", "1" if enabled else "0")


def get_llm_execution_mode() -> str:
    mode = get_setting("llm_execution_mode", "safe-run").strip().lower()
    if mode not in {"safe-run", "hard-off"}:
        return "safe-run"
    return mode


def set_llm_execution_mode(mode: str) -> None:
    normalized = str(mode or "safe-run").strip().lower()
    if normalized not in {"safe-run", "hard-off"}:
        raise ValueError(f"Unsupported llm_execution_mode: {mode!r}")
    set_setting("llm_execution_mode", normalized)


def is_hard_off_mode() -> bool:
    return get_llm_execution_mode() == "hard-off"


def get_runtime_control_state() -> dict:
    from orchestrator.execution_policy import get_state

    return get_state()


def get_planner_provider() -> str:
    return get_setting("planner_provider", "claude")


def set_planner_provider(provider: str) -> None:
    set_setting("planner_provider", provider)


def get_worker_provider() -> str:
    return get_setting("worker_provider", "codex")


def set_worker_provider(provider: str) -> None:
    set_setting("worker_provider", provider)


def get_worker_copilot_model() -> str:
    return get_setting("worker_copilot_model", "")


def set_worker_copilot_model(model: str) -> None:
    set_setting("worker_copilot_model", model)


def get_cto_scheduler_enabled() -> bool:
    return get_setting("cto_scheduler_enabled", "1") == "1"


def set_cto_scheduler_enabled(enabled: bool) -> None:
    set_setting("cto_scheduler_enabled", "1" if enabled else "0")


# ── Phase 0: 角色導向 LLM 配額開關存取器 ────────────────────────────────────

def get_ext_llm_role_enabled(role: str) -> bool:
    """回傳指定角色是否允許呼叫外部 LLM（0=封鎖, 1=允許）。"""
    key = f"ext_llm_role_{role.lower().replace('-', '_')}"
    return get_setting(key, "0") == "1"


def get_provider_enabled_for_role(provider: str, role: str) -> bool:
    """回傳指定 provider 對指定角色是否啟用（0=封鎖, 1=允許）。"""
    norm_provider = provider.lower().replace("-", "_")
    norm_role = role.lower().replace("-", "_")
    key = f"{norm_provider}_enabled_for_{norm_role}"
    return get_setting(key, "0") == "1"


def get_worker_daily_llm_cap() -> int:
    return int(get_setting("worker_daily_llm_cap", "100") or "100")


def get_worker_hourly_llm_cap() -> int:
    return int(get_setting("worker_hourly_llm_cap", "20") or "20")


def get_worker_max_retries_per_task() -> int:
    return int(get_setting("worker_max_retries_per_task", "2") or "2")


# ── Task Management ──

def create_task(**kwargs) -> int:
    """建立新任務，回傳 task_id"""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO agent_tasks (
                slot_key, date_folder, title, slug, status, previous_task_id,
                prompt_file_path, prompt_text, completed_file_path, completed_text,
                changed_files_json, worker_pid, started_at, completed_at, duration_seconds,
                error_message, created_at, updated_at, dedupe_key, regime_state,
                confidence_snapshot, epoch_id,
                contract_json, focus_keys, signal_state_type, expected_duration_hours,
                task_type, worker_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs.get("slot_key"),
            kwargs.get("date_folder"),
            kwargs.get("title"),
            kwargs.get("slug"),
            kwargs.get("status", "QUEUED"),
            kwargs.get("previous_task_id"),
            kwargs.get("prompt_file_path"),
            kwargs.get("prompt_text"),
            kwargs.get("completed_file_path"),
            kwargs.get("completed_text"),
            kwargs.get("changed_files_json"),
            kwargs.get("worker_pid"),
            kwargs.get("started_at"),
            kwargs.get("completed_at"),
            kwargs.get("duration_seconds"),
            kwargs.get("error_message"),
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
            kwargs.get("dedupe_key"),
            kwargs.get("regime_state"),
            kwargs.get("confidence_snapshot"),
            kwargs.get("epoch_id", 0),
            kwargs.get("contract_json"),
            kwargs.get("focus_keys"),
            kwargs.get("signal_state_type"),
            kwargs.get("expected_duration_hours"),
            kwargs.get("task_type"),
            kwargs.get("worker_type", "research"),
        ))
        task_id = c.lastrowid
        conn.commit()
        return task_id
    finally:
        conn.close()


def update_task(task_id: int, **kwargs) -> None:
    """更新任務"""
    if not kwargs:
        return

    sets = []
    vals = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        vals.append(value)

    sets.append("updated_at = ?")
    vals.append(datetime.now(timezone.utc).isoformat())
    vals.append(task_id)

    conn = get_conn()
    try:
        conn.execute(f"UPDATE agent_tasks SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def get_task(task_id: int) -> dict:
    """取得單一任務"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def claim_task_atomic(
    task_type: Optional[str] = None,
    worker_type: Optional[str] = None,
) -> Optional[dict]:
    """Atomically claim one QUEUED task using BEGIN IMMEDIATE to prevent double-claim.

    Returns the claimed task dict (status already set to RUNNING), or None if no task available.
    Uses isolation_level=None (autocommit) so BEGIN IMMEDIATE can be issued explicitly.
    Supports optional filtering by task_type and/or worker_type.
    """
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        where_clauses = ["status='QUEUED'"]
        params: list = []
        if task_type:
            where_clauses.append("task_type=?")
            params.append(task_type)
        if worker_type:
            where_clauses.append("worker_type=?")
            params.append(worker_type)
        where_sql = " AND ".join(where_clauses)
        row = conn.execute(
            f"SELECT * FROM agent_tasks WHERE {where_sql} ORDER BY id ASC LIMIT 1",
            params,
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return None
        task_id = row["id"]
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE agent_tasks SET status='RUNNING', started_at=?, worker_pid=?, updated_at=? "
            "WHERE id=? AND status='QUEUED'",
            (now, os.getpid(), now, task_id),
        )
        conn.execute("COMMIT")
        row2 = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row2) if row2 else None
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def get_nonfailed_task_by_dedupe_key(dedupe_key: str) -> Optional[dict]:
    """Return the most recent task with this dedupe_key that is NOT in a failed/cancelled state.

    'Non-failed' statuses that block re-creation (daily cap):
      QUEUED, RUNNING, COMPLETED, APPROVED, MERGE_READY

    'Failed' statuses that allow retry:
      FAILED, ERROR, CANCELLED, FAILED_RATE_LIMIT, FAILED_STUB, REPLAN_REQUIRED, ARCHIVED

    Used by the planner to enforce PLANNER_SKIP_DAILY_CAP logic.
    """
    _FAILED_STATUSES = (
        "FAILED", "ERROR", "CANCELLED", "FAILED_RATE_LIMIT",
        "FAILED_STUB", "REPLAN_REQUIRED", "ARCHIVED",
    )
    placeholders = ",".join(["?"] * len(_FAILED_STATUSES))
    conn = get_conn()
    try:
        row = conn.execute(
            f"SELECT * FROM agent_tasks WHERE dedupe_key=? AND status NOT IN ({placeholders})"
            " ORDER BY id DESC LIMIT 1",
            (dedupe_key, *_FAILED_STATUSES),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Phase 5: Exploration Routing State Helpers ───────────────────────────

def create_exploration_routing_state(**kwargs) -> int:
    """Insert a row into exploration_routing_state. Returns the new row id."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO exploration_routing_state (
                source_task_id, source_lane, source_dedupe_key,
                source_report_path, decision, route_status,
                validation_task_id, routed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kwargs["source_task_id"],
                kwargs["source_lane"],
                kwargs["source_dedupe_key"],
                kwargs.get("source_report_path"),
                kwargs.get("decision"),
                kwargs["route_status"],
                kwargs.get("validation_task_id"),
                kwargs.get("routed_at", now),
                kwargs.get("created_at", now),
                kwargs.get("updated_at", now),
            ),
        )
        row_id = c.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def get_exploration_routing_state_by_source_task_id(source_task_id: int) -> Optional[dict]:
    """Return the routing state row for a given source_task_id, or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM exploration_routing_state WHERE source_task_id=? LIMIT 1",
            (source_task_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_tasks(limit: int = 50, offset: int = 0, status: str = None, date_folder: str = None) -> list[dict]:
    """列出任務"""
    conn = get_conn()
    try:
        where_clauses = []
        params = []

        if status:
            where_clauses.append("status = ?")
            params.append(status)

        if date_folder:
            where_clauses.append("date_folder = ?")
            params.append(date_folder)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        params.extend([limit, offset])

        # Worker 需要最舊的任務，其他情況需要最新的任務
        order = "ASC" if status == "QUEUED" else "DESC"
        rows = conn.execute(f"SELECT * FROM agent_tasks {where_sql} ORDER BY id {order} LIMIT ? OFFSET ?", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_task() -> dict:
    """取得最新任務"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM agent_tasks ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def count_tasks_by_status() -> dict:
    """統計各狀態任務數量"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT status, COUNT(*) as count FROM agent_tasks GROUP BY status").fetchall()
        return {row["status"]: row["count"] for row in rows}
    finally:
        conn.close()


# ── Run History Management ──

def record_run(runner: str, outcome: str, **kwargs) -> int:
    """記錄執行結果"""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO agent_task_runs (
                runner, tick_at, outcome, request_id, task_id, message,
                log_snippet, duration_seconds, epoch_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            runner,
            kwargs.get("tick_at", now),
            outcome,
            kwargs.get("request_id"),
            kwargs.get("task_id"),
            kwargs.get("message"),
            kwargs.get("log_snippet"),
            kwargs.get("duration_seconds"),
            kwargs.get("epoch_id", 0),
            now
        ))
        run_id = c.lastrowid
        conn.commit()
        return run_id
    finally:
        conn.close()


def list_runs(limit: int = 20, offset: int = 0) -> list[dict]:
    """列出執行記錄"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_task_runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_runs_filtered(
    runner: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 500,
    request_id: Optional[str] = None,
) -> list[dict]:
    """列出執行記錄（帶條件過濾）"""
    conn = get_conn()
    try:
        where: list[str] = []
        params: list = []
        if runner:
            where.append("runner = ?")
            params.append(runner)
        if since:
            where.append("tick_at >= ?")
            params.append(since)
        if request_id:
            where.append("request_id = ?")
            params.append(request_id)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM agent_task_runs {where_sql} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run_by_request_id(request_id: str) -> Optional[dict]:
    """依 request_id 取得執行記錄"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM agent_task_runs WHERE request_id = ? ORDER BY id DESC LIMIT 1",
            (request_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_tasks(status: Optional[str] = None, date_folder: Optional[str] = None) -> int:
    """統計任務數量（帶條件過濾）"""
    conn = get_conn()
    try:
        where: list[str] = []
        params: list = []
        if status:
            where.append("status = ?")
            params.append(status)
        if date_folder:
            where.append("date_folder = ?")
            params.append(date_folder)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        row = conn.execute(f"SELECT COUNT(*) AS cnt FROM agent_tasks {where_sql}", params).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def get_latest_run_by_runner(runner: str) -> dict:
    """取得最新的執行記錄"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM agent_task_runs WHERE runner = ? ORDER BY id DESC LIMIT 1",
            (runner,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# ── CTO Review Management ──

def create_cto_review_run(**kwargs) -> int:
    """建立 CTO 審核執行記錄"""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO cto_review_runs (
                run_id, frequency_mode, started_at, completed_at, duration_seconds,
                checked_from, checked_until, candidate_count, approved_count,
                merged_count, rejected_count, deferred_count, superseded_count,
                duplicate_count, merge_branch, report_md_path, report_json_path,
                summary, created_at, updated_at, dedupe_key, is_manual, is_force_run,
                run_intent, parent_run_id, epoch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs.get("run_id"),
            kwargs.get("frequency_mode"),
            kwargs.get("started_at", now),
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
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
            kwargs.get("dedupe_key"),
            1 if kwargs.get("is_manual") else 0,
            1 if kwargs.get("is_force_run") else 0,
            kwargs.get("run_intent"),
            kwargs.get("parent_run_id"),
            kwargs.get("epoch_id", 0)
        ))
        cto_run_id = c.lastrowid
        conn.commit()
        return cto_run_id
    finally:
        conn.close()


def update_cto_review_run(run_id: str, **kwargs) -> None:
    """更新 CTO 審核執行記錄"""
    if not kwargs:
        return

    sets = []
    vals = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        vals.append(value)

    sets.append("updated_at = ?")
    vals.append(datetime.now(timezone.utc).isoformat())
    vals.append(run_id)

    conn = get_conn()
    try:
        conn.execute(f"UPDATE cto_review_runs SET {', '.join(sets)} WHERE run_id = ?", vals)
        conn.commit()
    finally:
        conn.close()


def get_cto_review_run(run_id: str) -> dict:
    """取得 CTO 審核執行記錄"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM cto_review_runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def list_cto_review_runs(limit: int = 20, offset: int = 0) -> list[dict]:
    """列出 CTO 審核執行記錄"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_cto_review_run() -> dict:
    """取得最新的 CTO 審核執行記錄"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM cto_review_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# ── Backlog Management ──

def create_backlog_item(**kwargs) -> int:
    """建立 Backlog 項目"""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO cto_backlog_items (
                finding_id, cto_run_id, source, severity, impact_score, urgency,
                category, title, description, file_path, line_number, status,
                priority_score, assigned_to, estimated_hours, task_id, resolution_notes,
                created_at, updated_at, completed_at, epoch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs.get("finding_id"),
            kwargs.get("cto_run_id"),
            kwargs.get("source", "cto_review"),
            kwargs.get("severity"),
            kwargs.get("impact_score"),
            kwargs.get("urgency"),
            kwargs.get("category"),
            kwargs.get("title"),
            kwargs.get("description"),
            kwargs.get("file_path"),
            kwargs.get("line_number"),
            kwargs.get("status", "queued"),
            kwargs.get("priority_score"),
            kwargs.get("assigned_to"),
            kwargs.get("estimated_hours"),
            kwargs.get("task_id"),
            kwargs.get("resolution_notes"),
            kwargs.get("created_at", now),
            kwargs.get("updated_at", now),
            kwargs.get("completed_at"),
            kwargs.get("epoch_id", 0)
        ))
        item_id = c.lastrowid
        conn.commit()
        return item_id
    finally:
        conn.close()


def get_system_state_snapshot() -> dict:
    """從最近任務記錄推算系統狀態快照，供 planner 注入 prompt 使用。"""
    conn = get_conn()
    try:
        recent = conn.execute(
            "SELECT regime_state, confidence_snapshot, status, signal_state_type "
            "FROM agent_tasks ORDER BY id DESC LIMIT 20"
        ).fetchall()
        rows = [dict(r) for r in recent]
    finally:
        conn.close()

    regime_state = next(
        (r["regime_state"] for r in rows if r.get("regime_state")),
        "UNKNOWN",
    )
    confidence_snapshot = next(
        (r["confidence_snapshot"] for r in rows if r.get("confidence_snapshot") is not None),
        None,
    )

    total = len(rows)
    completed = sum(1 for r in rows if r.get("status") == "COMPLETED")
    failed = sum(1 for r in rows if r.get("status") == "FAILED")
    merge_rate = round(completed / total, 3) if total > 0 else 0.0

    last_signal_type = next(
        (r["signal_state_type"] for r in rows if r.get("signal_state_type")),
        None,
    )

    return {
        "regime_state": regime_state,
        "confidence_snapshot": confidence_snapshot,
        "recent_merge_rate": merge_rate,
        "recent_task_count": total,
        "recent_completed": completed,
        "recent_failed": failed,
        "last_signal_state_type": last_signal_type,
    }


def list_backlog_items(limit: int = 50, offset: int = 0, status: str = None) -> list[dict]:
    """列出 Backlog 項目"""
    conn = get_conn()
    try:
        where_sql = ""
        params = []

        if status:
            where_sql = "WHERE status = ?"
            params.append(status)

        params.extend([limit, offset])

        rows = conn.execute(
            f"SELECT * FROM cto_backlog_items {where_sql} ORDER BY priority_score DESC, id DESC LIMIT ? OFFSET ?",
            params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
