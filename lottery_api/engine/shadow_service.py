"""
Shadow Experiment Service — 影子實驗管理
==========================================
負責：
1. 建立影子實驗（從檢討假說產生）
2. 獨立追蹤影子實驗的預測結果
3. 與 production 完全隔離
4. 比較影子實驗 vs production 的績效

設計原則：
- 影子實驗結果永遠不會覆蓋 production metrics
- 只有通過驗證才能考慮晉升
- 實驗結果獨立儲存與查詢
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)


def _db():
    from database import db_manager
    return db_manager


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# CREATE
# ============================================================

def create_shadow_experiment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    從檢討假說建立影子實驗。

    payload:
    {
        "session_id": 1,           // optional: 來源檢討會議
        "hypothesis_id": 5,        // optional: 來源假說
        "game": "BIG_LOTTO",
        "experiment_name": "test_cold_pool_15",
        "base_strategy": "P1+Dev+Sum 5-bet",
        "experiment_strategy": "P1+Dev+Sum+ColdPool15 5-bet",
        "experiment_config_json": {...},
        "notes": "..."
    }
    """
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        config_json = payload.get("experiment_config_json")
        if isinstance(config_json, dict):
            config_json = json.dumps(config_json, ensure_ascii=False)

        cursor.execute("""
            INSERT INTO shadow_experiments
                (session_id, game, experiment_name, base_strategy,
                 experiment_strategy, experiment_config_json, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?)
        """, (
            payload.get("session_id"),
            payload.get("game", ""),
            payload.get("experiment_name", "unnamed_experiment"),
            payload.get("base_strategy"),
            payload.get("experiment_strategy"),
            config_json,
            payload.get("notes"),
        ))
        exp_id = cursor.lastrowid

        # If hypothesis_id provided, update hypothesis status to TESTING
        hypothesis_id = payload.get("hypothesis_id")
        if hypothesis_id:
            cursor.execute(
                "UPDATE review_hypotheses SET status = 'TESTING', updated_at = ? WHERE id = ?",
                (_now_utc(), hypothesis_id)
            )

        # If session_id and prediction_run_ids, mark as SHADOW_TRACKED
        session_id = payload.get("session_id")
        run_ids = payload.get("prediction_run_ids", [])
        for rid in run_ids:
            cursor.execute("""
                INSERT OR IGNORE INTO prediction_review_status
                    (prediction_run_id, review_session_id, review_status)
                VALUES (?, ?, 'SHADOW_TRACKED')
            """, (rid, session_id))

        conn.commit()
        logger.info(f"✅ Shadow experiment #{exp_id} created: {payload.get('experiment_name')}")
        return {"experiment_id": exp_id, "status": "created"}
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to create shadow experiment: {e}")
        raise
    finally:
        conn.close()


# ============================================================
# READ
# ============================================================

def get_shadow_experiment(experiment_id: int) -> Optional[Dict[str, Any]]:
    """取得單一影子實驗詳情"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM shadow_experiments WHERE id = ?", (experiment_id,))
        row = cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        # Parse config JSON
        if result.get("experiment_config_json"):
            try:
                result["experiment_config"] = json.loads(result["experiment_config_json"])
            except (json.JSONDecodeError, TypeError):
                result["experiment_config"] = None
        return result
    finally:
        conn.close()


def list_shadow_experiments(
    game: Optional[str] = None,
    status: Optional[str] = None,
    session_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """查詢影子實驗列表"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []
        if game:
            conditions.append("se.game = ?")
            params.append(game)
        if status:
            conditions.append("se.status = ?")
            params.append(status)
        if session_id:
            conditions.append("se.session_id = ?")
            params.append(session_id)
        where = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"SELECT COUNT(*) FROM shadow_experiments se WHERE {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT se.*, rs.draw, rs.draw_date, rs.final_decision
            FROM shadow_experiments se
            LEFT JOIN review_sessions rs ON se.session_id = rs.id
            WHERE {where}
            ORDER BY se.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        experiments = []
        for row in cursor.fetchall():
            exp = dict(row)
            if exp.get("experiment_config_json"):
                try:
                    exp["experiment_config"] = json.loads(exp["experiment_config_json"])
                except (json.JSONDecodeError, TypeError):
                    exp["experiment_config"] = None
            experiments.append(exp)

        return {
            "experiments": experiments,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


# ============================================================
# UPDATE
# ============================================================

def update_shadow_experiment(experiment_id: int, updates: Dict[str, Any]) -> bool:
    """更新影子實驗"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        allowed_fields = {
            "status", "notes", "experiment_config_json",
            "experiment_strategy", "experiment_name",
        }
        set_parts = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                if k == "experiment_config_json" and isinstance(v, dict):
                    v = json.dumps(v, ensure_ascii=False)
                set_parts.append(f"{k} = ?")
                params.append(v)
        if not set_parts:
            return False

        set_parts.append("updated_at = ?")
        params.append(_now_utc())
        params.append(experiment_id)

        cursor.execute(
            f"UPDATE shadow_experiments SET {', '.join(set_parts)} WHERE id = ?",
            params
        )
        conn.commit()

        # If status changed to PASSED/FAILED, update linked hypothesis
        new_status = updates.get("status")
        if new_status in ("PASSED", "FAILED"):
            cursor2 = conn.cursor()
            cursor2.execute("SELECT session_id FROM shadow_experiments WHERE id = ?", (experiment_id,))
            row = cursor2.fetchone()
            if row and row["session_id"]:
                hyp_status = "ACCEPTED" if new_status == "PASSED" else "REJECTED"
                cursor2.execute("""
                    UPDATE review_hypotheses SET status = ?, updated_at = ?
                    WHERE session_id = ? AND status = 'TESTING'
                """, (hyp_status, _now_utc(), row["session_id"]))
                conn.commit()

        return cursor.rowcount > 0
    finally:
        conn.close()


# ============================================================
# COMPARISON
# ============================================================

def get_shadow_vs_production_comparison(experiment_id: int) -> Dict[str, Any]:
    """
    比較影子實驗 vs production 績效。
    NOTE: 完整比較需要影子實驗產生預測歷史，
    此處提供基礎結構，可擴展整合實際回測數據。
    """
    exp = get_shadow_experiment(experiment_id)
    if not exp:
        return {"error": "experiment not found"}

    return {
        "experiment_id": experiment_id,
        "experiment_name": exp.get("experiment_name"),
        "game": exp.get("game"),
        "base_strategy": exp.get("base_strategy"),
        "experiment_strategy": exp.get("experiment_strategy"),
        "status": exp.get("status"),
        "comparison": {
            "note": "Full comparison requires shadow predictions to be generated and resolved. "
                    "Use the backtest framework to compare strategies.",
            "production_edge": None,
            "shadow_edge": None,
            "delta": None,
        },
    }
