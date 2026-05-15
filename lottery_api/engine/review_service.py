"""
Review Service — 檢討會議持久化與查詢服務
==========================================
負責：
1. 建立檢討會議 (review session)
2. 解析並儲存結構化發現、假說、行動
3. 關聯預測記錄與檢討狀態
4. 查詢歷史檢討紀錄
5. 支援手動編輯 / 修正

設計原則：
- 不修改 production prediction 邏輯
- raw_report_text 永不遺失
- 即使解析部分失敗也會存入原始文字
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

def create_review_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    建立一個檢討會議並存入相關子記錄。

    payload 結構:
    {
        "game": "BIG_LOTTO",
        "draw": "115000023",
        "draw_date": "2026-03-28",
        "session_type": "daily_review",
        "summary": "...",
        "final_decision": "WATCH",
        "confidence_level": "MEDIUM",
        "raw_report_text": "...",  // 原始 LLM 輸出
        "findings": [...],
        "hypotheses": [...],
        "actions": [...],
        "prediction_run_ids": [123, 456]   // optional: 關聯的 prediction_run
    }
    """
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()

    try:
        # 1. 建立 session
        parsed_ok = 1  # assume success, flip on error
        findings = payload.get("findings", [])
        hypotheses = payload.get("hypotheses", [])
        actions = payload.get("actions", [])

        cursor.execute("""
            INSERT INTO review_sessions
                (game, draw, draw_date, session_type, summary, final_decision,
                 confidence_level, raw_report_text, parsed_successfully, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """, (
            payload.get("game", ""),
            payload.get("draw"),
            payload.get("draw_date"),
            payload.get("session_type", "daily_review"),
            payload.get("summary"),
            payload.get("final_decision", "NO_ACTION"),
            payload.get("confidence_level", "LOW"),
            payload.get("raw_report_text"),
            parsed_ok,
        ))
        session_id = cursor.lastrowid

        # 2. 儲存 findings
        for i, f in enumerate(findings):
            cursor.execute("""
                INSERT INTO review_findings
                    (session_id, section_type, title, content, evidence_type, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                f.get("section_type", "other"),
                f.get("title"),
                f.get("content"),
                f.get("evidence_type", "UNSURE"),
                f.get("sort_order", i),
            ))

        # 3. 儲存 hypotheses
        for h in hypotheses:
            cursor.execute("""
                INSERT INTO review_hypotheses
                    (session_id, hypothesis_type, description, expected_impact,
                     validation_method, kill_condition, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                h.get("hypothesis_type", "other"),
                h.get("description"),
                h.get("expected_impact"),
                h.get("validation_method"),
                h.get("kill_condition"),
                h.get("status", "PENDING"),
            ))

        # 4. 儲存 actions
        for a in actions:
            cursor.execute("""
                INSERT INTO review_actions
                    (session_id, priority, action_title, action_description,
                     expected_gain, cost_level, risk_level, validation_method,
                     stop_condition, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                a.get("priority", "P2"),
                a.get("action_title"),
                a.get("action_description"),
                a.get("expected_gain"),
                a.get("cost_level"),
                a.get("risk_level"),
                a.get("validation_method"),
                a.get("stop_condition"),
                a.get("status", "OPEN"),
            ))

        # 5. 關聯 prediction runs
        run_ids = payload.get("prediction_run_ids", [])
        for rid in run_ids:
            cursor.execute("""
                INSERT OR REPLACE INTO prediction_review_status
                    (prediction_run_id, review_session_id, review_status, resolved_at)
                VALUES (?, ?, 'REVIEWED', ?)
            """, (rid, session_id, _now_utc()))

        conn.commit()
        logger.info(f"✅ Review session #{session_id} created: game={payload.get('game')}, draw={payload.get('draw')}")

        return {
            "session_id": session_id,
            "findings_count": len(findings),
            "hypotheses_count": len(hypotheses),
            "actions_count": len(actions),
            "linked_runs": len(run_ids),
            "status": "created",
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to create review session: {e}")

        # Fallback: save raw text even if parsing fails
        try:
            cursor.execute("""
                INSERT INTO review_sessions
                    (game, draw, draw_date, session_type, raw_report_text,
                     parsed_successfully, status)
                VALUES (?, ?, ?, ?, ?, 0, 'OPEN')
            """, (
                payload.get("game", ""),
                payload.get("draw"),
                payload.get("draw_date"),
                payload.get("session_type", "daily_review"),
                payload.get("raw_report_text"),
            ))
            fallback_id = cursor.lastrowid
            conn.commit()
            logger.warning(f"⚠️ Saved raw report as fallback session #{fallback_id}")
            return {
                "session_id": fallback_id,
                "status": "partial_failure",
                "error": str(e),
                "raw_text_saved": True,
            }
        except Exception as e2:
            conn.rollback()
            raise RuntimeError(f"Critical failure: {e}; fallback also failed: {e2}")
    finally:
        conn.close()


# ============================================================
# READ
# ============================================================

def get_review_session(session_id: int) -> Optional[Dict[str, Any]]:
    """取得完整檢討會議詳情（含所有子記錄）"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM review_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        session = dict(row)

        # findings
        cursor.execute(
            "SELECT * FROM review_findings WHERE session_id = ? ORDER BY sort_order",
            (session_id,)
        )
        session["findings"] = [dict(r) for r in cursor.fetchall()]

        # hypotheses
        cursor.execute(
            "SELECT * FROM review_hypotheses WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        session["hypotheses"] = [dict(r) for r in cursor.fetchall()]

        # actions
        cursor.execute(
            "SELECT * FROM review_actions WHERE session_id = ? ORDER BY priority, id",
            (session_id,)
        )
        session["actions"] = [dict(r) for r in cursor.fetchall()]

        # shadow experiments
        cursor.execute(
            "SELECT * FROM shadow_experiments WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        session["shadow_experiments"] = [dict(r) for r in cursor.fetchall()]

        # linked predictions
        cursor.execute(
            "SELECT * FROM prediction_review_status WHERE review_session_id = ?",
            (session_id,)
        )
        session["linked_predictions"] = [dict(r) for r in cursor.fetchall()]

        return session
    finally:
        conn.close()


def list_review_sessions(
    game: Optional[str] = None,
    draw: Optional[str] = None,
    status: Optional[str] = None,
    session_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """查詢檢討會議列表"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []
        if game:
            conditions.append("game = ?")
            params.append(game)
        if draw:
            conditions.append("draw = ?")
            params.append(draw)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if session_type:
            conditions.append("session_type = ?")
            params.append(session_type)

        where = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"SELECT COUNT(*) FROM review_sessions WHERE {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT rs.*,
                   (SELECT COUNT(*) FROM review_findings WHERE session_id = rs.id) as findings_count,
                   (SELECT COUNT(*) FROM review_hypotheses WHERE session_id = rs.id) as hypotheses_count,
                   (SELECT COUNT(*) FROM review_actions WHERE session_id = rs.id) as actions_count,
                   (SELECT COUNT(*) FROM shadow_experiments WHERE session_id = rs.id) as shadow_count
            FROM review_sessions rs
            WHERE {where}
            ORDER BY rs.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        sessions = [dict(r) for r in cursor.fetchall()]

        return {
            "sessions": sessions,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


def list_actions(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    game: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """查詢所有行動項目（跨 session）"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("ra.status = ?")
            params.append(status)
        if priority:
            conditions.append("ra.priority = ?")
            params.append(priority)
        if game:
            conditions.append("rs.game = ?")
            params.append(game)
        where = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT ra.*, rs.game, rs.draw, rs.draw_date, rs.session_type
            FROM review_actions ra
            JOIN review_sessions rs ON ra.session_id = rs.id
            WHERE {where}
            ORDER BY
                CASE ra.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
                ra.created_at DESC
            LIMIT ?
        """, params + [limit])
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_prediction_review_status(
    prediction_run_id: Optional[int] = None,
    review_status: Optional[str] = None,
    game: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """查詢預測的檢討狀態"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []
        if prediction_run_id:
            conditions.append("prs.prediction_run_id = ?")
            params.append(prediction_run_id)
        if review_status:
            conditions.append("prs.review_status = ?")
            params.append(review_status)
        if game:
            conditions.append("rs.game = ?")
            params.append(game)
        where = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"SELECT COUNT(*) FROM prediction_review_status prs LEFT JOIN review_sessions rs ON prs.review_session_id = rs.id WHERE {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(f"""
            SELECT prs.*, rs.game, rs.draw, rs.summary, rs.final_decision, rs.confidence_level
            FROM prediction_review_status prs
            LEFT JOIN review_sessions rs ON prs.review_session_id = rs.id
            WHERE {where}
            ORDER BY prs.id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        return {
            "items": [dict(r) for r in cursor.fetchall()],
            "total": total,
        }
    finally:
        conn.close()


# ============================================================
# UPDATE
# ============================================================

def update_review_session(session_id: int, updates: Dict[str, Any]) -> bool:
    """更新檢討會議（支援手動編輯/修正）"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        allowed_fields = {
            "summary", "final_decision", "confidence_level",
            "raw_report_text", "status", "parsed_successfully",
        }
        set_parts = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_parts.append(f"{k} = ?")
                params.append(v)
        if not set_parts:
            return False
        set_parts.append("updated_at = ?")
        params.append(_now_utc())
        params.append(session_id)

        cursor.execute(
            f"UPDATE review_sessions SET {', '.join(set_parts)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def mark_session_resolved(session_id: int) -> bool:
    """將檢討會議標記為已解決"""
    return update_review_session(session_id, {"status": "RESOLVED"})


def reopen_session(session_id: int) -> bool:
    """重新開啟檢討會議"""
    return update_review_session(session_id, {"status": "OPEN"})


def update_action_status(action_id: int, new_status: str) -> bool:
    """更新行動項目狀態"""
    if new_status not in ("OPEN", "IN_PROGRESS", "DONE", "CANCELLED"):
        return False
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE review_actions SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, _now_utc(), action_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_hypothesis_status(hypothesis_id: int, new_status: str) -> bool:
    """更新假說狀態"""
    if new_status not in ("PENDING", "TESTING", "ACCEPTED", "REJECTED", "EXPIRED"):
        return False
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE review_hypotheses SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, _now_utc(), hypothesis_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def mark_prediction_reviewed(prediction_run_id: int, session_id: int, status: str = "REVIEWED") -> bool:
    """標記預測為已檢討"""
    if status not in ("UNREVIEWED", "REVIEWED", "RESOLVED", "ACTION_CREATED", "SHADOW_TRACKED"):
        return False
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        # UPSERT: update if exists, insert if not
        cursor.execute("""
            INSERT INTO prediction_review_status
                (prediction_run_id, review_session_id, review_status, resolved_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(prediction_run_id) DO UPDATE SET
                review_session_id = excluded.review_session_id,
                review_status = excluded.review_status,
                resolved_at = excluded.resolved_at
        """, (prediction_run_id, session_id, status, _now_utc() if status in ("RESOLVED",) else None))
        conn.commit()
        return True
    except Exception:
        # prediction_review_status has no unique on prediction_run_id, use simpler approach
        try:
            cursor.execute(
                "SELECT id FROM prediction_review_status WHERE prediction_run_id = ? AND review_session_id = ?",
                (prediction_run_id, session_id)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE prediction_review_status SET review_status = ?, resolved_at = ? WHERE id = ?",
                    (status, _now_utc() if status == "RESOLVED" else None, existing["id"])
                )
            else:
                cursor.execute(
                    "INSERT INTO prediction_review_status (prediction_run_id, review_session_id, review_status, resolved_at) VALUES (?, ?, ?, ?)",
                    (prediction_run_id, session_id, status, _now_utc() if status == "RESOLVED" else None)
                )
            conn.commit()
            return True
        except Exception as e2:
            conn.rollback()
            logger.error(f"Failed to mark prediction reviewed: {e2}")
            return False
    finally:
        conn.close()


# ============================================================
# DASHBOARD / SUMMARY
# ============================================================

def get_review_dashboard(game: Optional[str] = None) -> Dict[str, Any]:
    """檢討儀表板摘要"""
    db = _db()
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        game_filter = "WHERE game = ?" if game else ""
        params = [game] if game else []

        # Session counts by status
        cursor.execute(f"""
            SELECT status, COUNT(*) as cnt
            FROM review_sessions {game_filter}
            GROUP BY status
        """, params)
        status_counts = {r["status"]: r["cnt"] for r in cursor.fetchall()}

        # Session counts by decision
        cursor.execute(f"""
            SELECT final_decision, COUNT(*) as cnt
            FROM review_sessions {game_filter}
            GROUP BY final_decision
        """, params)
        decision_counts = {r["final_decision"]: r["cnt"] for r in cursor.fetchall()}

        # Action counts by status + priority
        action_filter = "WHERE rs.game = ?" if game else ""
        cursor.execute(f"""
            SELECT ra.priority, ra.status, COUNT(*) as cnt
            FROM review_actions ra
            JOIN review_sessions rs ON ra.session_id = rs.id
            {action_filter}
            GROUP BY ra.priority, ra.status
        """, params)
        action_summary = {}
        for r in cursor.fetchall():
            key = f"{r['priority']}_{r['status']}"
            action_summary[key] = r["cnt"]

        # Open actions count
        cursor.execute(f"""
            SELECT COUNT(*) FROM review_actions ra
            JOIN review_sessions rs ON ra.session_id = rs.id
            {action_filter}
            AND ra.status IN ('OPEN', 'IN_PROGRESS')
        """, params)
        open_actions = cursor.fetchone()[0]

        # Active hypotheses
        cursor.execute(f"""
            SELECT COUNT(*) FROM review_hypotheses rh
            JOIN review_sessions rs ON rh.session_id = rs.id
            {action_filter}
            AND rh.status IN ('PENDING', 'TESTING')
        """, params)
        active_hypotheses = cursor.fetchone()[0]

        # Active shadow experiments
        cursor.execute(f"""
            SELECT COUNT(*) FROM shadow_experiments se
            JOIN review_sessions rs ON se.session_id = rs.id
            {action_filter}
            AND se.status IN ('DRAFT', 'RUNNING')
        """, params if game else [])
        active_shadows = cursor.fetchone()[0]

        recent_sessions = list_review_sessions(
            game=game,
            limit=3,
            offset=0,
        ).get("sessions", [])

        return {
            "session_status_counts": status_counts,
            "decision_counts": decision_counts,
            "action_summary": action_summary,
            "open_actions": open_actions,
            "active_hypotheses": active_hypotheses,
            "active_shadow_experiments": active_shadows,
            "recent_sessions": recent_sessions,
        }
    finally:
        conn.close()


# ============================================================
# EXPORT
# ============================================================

def export_session_json(session_id: int) -> Optional[Dict]:
    """匯出完整 session 為 JSON"""
    return get_review_session(session_id)


def export_session_markdown(session_id: int) -> Optional[str]:
    """匯出 session 為 Markdown"""
    session = get_review_session(session_id)
    if not session:
        return None

    lines = [
        f"# Review Session #{session['id']}",
        f"",
        f"- **Game:** {session['game']}",
        f"- **Draw:** {session.get('draw', 'N/A')}",
        f"- **Date:** {session.get('draw_date', 'N/A')}",
        f"- **Type:** {session.get('session_type', 'N/A')}",
        f"- **Decision:** {session.get('final_decision', 'N/A')}",
        f"- **Confidence:** {session.get('confidence_level', 'N/A')}",
        f"- **Status:** {session.get('status', 'N/A')}",
        f"- **Created:** {session.get('created_at', 'N/A')}",
        f"",
        f"## Summary",
        f"",
        session.get("summary") or "(no summary)",
        f"",
    ]

    if session.get("findings"):
        lines.append("## Findings")
        lines.append("")
        for f in session["findings"]:
            evidence = f.get("evidence_type", "")
            lines.append(f"### [{evidence}] {f.get('title', 'Untitled')}")
            lines.append(f"**Type:** {f.get('section_type', '')}")
            lines.append("")
            lines.append(f.get("content", ""))
            lines.append("")

    if session.get("hypotheses"):
        lines.append("## Hypotheses")
        lines.append("")
        for h in session["hypotheses"]:
            lines.append(f"### {h.get('description', 'Untitled')} [{h.get('status', '')}]")
            lines.append(f"- **Type:** {h.get('hypothesis_type', '')}")
            lines.append(f"- **Expected Impact:** {h.get('expected_impact', '')}")
            lines.append(f"- **Validation:** {h.get('validation_method', '')}")
            lines.append(f"- **Kill Condition:** {h.get('kill_condition', '')}")
            lines.append("")

    if session.get("actions"):
        lines.append("## Actions")
        lines.append("")
        for a in session["actions"]:
            lines.append(f"### [{a.get('priority', '')}] {a.get('action_title', 'Untitled')} [{a.get('status', '')}]")
            lines.append(f"- **Description:** {a.get('action_description', '')}")
            lines.append(f"- **Expected Gain:** {a.get('expected_gain', '')}")
            lines.append(f"- **Cost:** {a.get('cost_level', '')} / Risk: {a.get('risk_level', '')}")
            lines.append(f"- **Validation:** {a.get('validation_method', '')}")
            lines.append(f"- **Stop Condition:** {a.get('stop_condition', '')}")
            lines.append("")

    if session.get("raw_report_text"):
        lines.append("## Raw Report")
        lines.append("")
        lines.append("```")
        lines.append(session["raw_report_text"])
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
