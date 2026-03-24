"""
Prediction Tracker — 預測快照儲存 + 結果比對 + 表現聚合

設計原則：
- 不修改任何既有預測邏輯
- 純追蹤層：讀取預測輸出，存入 DB，比對結果
- 冪等：重複執行 resolve 不會產生重複結果
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


def _get_db():
    from database import db_manager
    return db_manager


# ──────────────────────────────────────────────
# 快照儲存
# ──────────────────────────────────────────────

def create_snapshot(
    lottery_type: str,
    bets: List[List[int]],
    strategy_name: str,
    latest_known_draw: str,
    latest_known_date: Optional[str] = None,
    special: Optional[int] = None,
    notes: Optional[str] = None,
) -> int:
    """
    儲存一次預測快照。
    回傳 run_id。
    每次呼叫均建立新的 run（不去重），讓每次預測都有完整記錄。
    """
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO prediction_runs
              (lottery_type, latest_known_draw, latest_known_date, strategy_name, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (lottery_type, latest_known_draw, latest_known_date, strategy_name, notes or ""))
        run_id = cur.lastrowid

        for idx, numbers in enumerate(bets):
            sp = special if (idx == 0 and lottery_type == "POWER_LOTTO") else None
            cur.execute("""
                INSERT INTO prediction_items (run_id, bet_index, numbers, special, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (run_id, idx, json.dumps(sorted(numbers)), sp))

        conn.commit()
        logger.info(f"[PredictionTracker] Snapshot saved: run={run_id}, {lottery_type}, {len(bets)} bets")
        return run_id
    except Exception as e:
        conn.rollback()
        logger.error(f"[PredictionTracker] create_snapshot failed: {e}")
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 比對邏輯
# ──────────────────────────────────────────────

def _compare(
    lottery_type: str,
    predicted: List[int],
    actual: List[int],
    predicted_special: Optional[int],
    actual_special: Optional[int],
) -> Dict:
    pred_set = set(predicted)
    actual_set = set(actual)
    matched = sorted(pred_set & actual_set)
    hit_count = len(matched)
    special_hit = 0
    if lottery_type == "POWER_LOTTO" and predicted_special is not None and actual_special is not None:
        special_hit = 1 if predicted_special == actual_special else 0
    return {
        "hit_count": hit_count,
        "matched_numbers": matched,
        "special_hit": special_hit,
    }


# ──────────────────────────────────────────────
# 結果解析（Resolution Engine）
# ──────────────────────────────────────────────

def resolve_pending(dry_run: bool = False) -> Dict:
    """
    掃描所有 PENDING 的 prediction_items，
    查找對應的開獎結果，寫入 prediction_results，
    將 status 更新為 RESOLVED。

    Resolution 規則：
      找 lottery_type 相同、draw 號碼 > latest_known_draw 的「第一期」開獎。

    冪等：item_id 有 UNIQUE 約束，重跑不會重複。
    """
    db = _get_db()
    conn = db._get_connection()
    resolved = 0
    skipped = 0
    errors = 0

    try:
        cur = conn.cursor()

        # 取得所有 PENDING items + 對應 run 資訊
        cur.execute("""
            SELECT pi.id as item_id, pi.run_id, pi.bet_index, pi.numbers, pi.special,
                   pr.lottery_type, pr.latest_known_draw
            FROM prediction_items pi
            JOIN prediction_runs pr ON pi.run_id = pr.id
            WHERE pi.status = 'PENDING'
            ORDER BY pr.created_at ASC
        """)
        pending = cur.fetchall()

        for row in pending:
            item_id = row["item_id"]
            lottery_type = row["lottery_type"]
            latest_known_draw = row["latest_known_draw"]

            # 找目標開獎：draw > latest_known_draw（用整數比較）
            cur.execute("""
                SELECT draw, date, numbers, special
                FROM draws
                WHERE lottery_type = ?
                  AND CAST(draw AS INTEGER) > CAST(? AS INTEGER)
                ORDER BY CAST(draw AS INTEGER) ASC
                LIMIT 1
            """, (lottery_type, latest_known_draw))
            actual_row = cur.fetchone()

            if not actual_row:
                skipped += 1
                continue

            actual_draw = actual_row["draw"]
            actual_date = actual_row["date"]
            actual_numbers = json.loads(actual_row["numbers"])
            actual_special = actual_row["special"]
            predicted_numbers = json.loads(row["numbers"])
            predicted_special = row["special"]

            cmp = _compare(
                lottery_type,
                predicted_numbers,
                actual_numbers,
                predicted_special,
                actual_special,
            )

            if dry_run:
                resolved += 1
                continue

            try:
                cur.execute("""
                    INSERT OR IGNORE INTO prediction_results
                      (item_id, actual_draw, actual_date, actual_numbers, actual_special,
                       hit_count, matched_numbers, special_hit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id,
                    actual_draw,
                    actual_date,
                    json.dumps(actual_numbers),
                    actual_special,
                    cmp["hit_count"],
                    json.dumps(cmp["matched_numbers"]),
                    cmp["special_hit"],
                ))
                if cur.rowcount > 0:
                    cur.execute("""
                        UPDATE prediction_items SET status = 'RESOLVED' WHERE id = ?
                    """, (item_id,))
                    resolved += 1
            except Exception as e:
                logger.warning(f"[PredictionTracker] resolve item {item_id} error: {e}")
                errors += 1

        conn.commit()
        logger.info(f"[PredictionTracker] resolve_pending: resolved={resolved}, skipped={skipped}, errors={errors}, dry_run={dry_run}")
        return {"resolved": resolved, "skipped": skipped, "errors": errors, "dry_run": dry_run}

    except Exception as e:
        conn.rollback()
        logger.error(f"[PredictionTracker] resolve_pending failed: {e}")
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 歷史查詢
# ──────────────────────────────────────────────

def get_history(
    lottery_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict:
    """回傳歷史預測清單（依 run）"""
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if lottery_type:
            conditions.append("pr.lottery_type = ?")
            params.append(lottery_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # 總數
        cur.execute(f"""
            SELECT COUNT(DISTINCT pr.id)
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            {where}
        """, params)
        total = cur.fetchone()[0]

        # 清單（每個 run 彙總）
        cur.execute(f"""
            SELECT pr.id as run_id,
                   pr.lottery_type,
                   pr.latest_known_draw,
                   pr.latest_known_date,
                   pr.strategy_name,
                   pr.created_at,
                   COUNT(pi.id) as total_bets,
                   SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) as resolved_bets,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_draw ELSE NULL END) as actual_draw,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_date ELSE NULL END) as actual_date,
                   MAX(CASE WHEN pi.status='RESOLVED' THEN res.hit_count ELSE NULL END) as best_hit,
                   SUM(CASE WHEN pi.status='RESOLVED' THEN res.hit_count ELSE 0 END) as total_hits
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            LEFT JOIN prediction_results res ON res.item_id = pi.id
            {where}
            GROUP BY pr.id
            ORDER BY pr.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

        rows = cur.fetchall()
        runs = []
        for row in rows:
            resolved_bets = row["resolved_bets"] or 0
            total_bets = row["total_bets"] or 1
            run_status = "RESOLVED" if resolved_bets == total_bets else "PENDING"
            if status and run_status != status:
                continue
            runs.append({
                "run_id": row["run_id"],
                "lottery_type": row["lottery_type"],
                "latest_known_draw": row["latest_known_draw"],
                "latest_known_date": row["latest_known_date"],
                "strategy_name": row["strategy_name"],
                "created_at": row["created_at"],
                "total_bets": total_bets,
                "resolved_bets": resolved_bets,
                "status": run_status,
                "actual_draw": row["actual_draw"],
                "actual_date": row["actual_date"],
                "best_hit": row["best_hit"],
            })

        return {"total": total, "offset": offset, "limit": limit, "runs": runs}
    finally:
        conn.close()


def get_run_detail(run_id: int) -> Optional[Dict]:
    """回傳單一 run 的完整比對資料"""
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT pr.*, pi.id as item_id, pi.bet_index, pi.numbers, pi.special as pred_special,
                   pi.status,
                   res.actual_draw, res.actual_date, res.actual_numbers, res.actual_special,
                   res.hit_count, res.matched_numbers, res.special_hit, res.resolved_at
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            LEFT JOIN prediction_results res ON res.item_id = pi.id
            WHERE pr.id = ?
            ORDER BY pi.bet_index ASC
        """, (run_id,))
        rows = cur.fetchall()
        if not rows:
            return None

        first = rows[0]
        result = {
            "run_id": run_id,
            "lottery_type": first["lottery_type"],
            "latest_known_draw": first["latest_known_draw"],
            "latest_known_date": first["latest_known_date"],
            "strategy_name": first["strategy_name"],
            "notes": first["notes"],
            "created_at": first["created_at"],
            "bets": [],
        }
        for row in rows:
            bet = {
                "item_id": row["item_id"],
                "bet_index": row["bet_index"],
                "predicted_numbers": json.loads(row["numbers"]),
                "predicted_special": row["pred_special"],
                "status": row["status"],
            }
            if row["status"] == "RESOLVED":
                bet["actual_draw"] = row["actual_draw"]
                bet["actual_date"] = row["actual_date"]
                bet["actual_numbers"] = json.loads(row["actual_numbers"]) if row["actual_numbers"] else []
                bet["actual_special"] = row["actual_special"]
                bet["hit_count"] = row["hit_count"]
                bet["matched_numbers"] = json.loads(row["matched_numbers"]) if row["matched_numbers"] else []
                bet["special_hit"] = bool(row["special_hit"])
                bet["resolved_at"] = row["resolved_at"]
            result["bets"].append(bet)
        return result
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 策略表現聚合
# ──────────────────────────────────────────────

def get_performance(lottery_type: Optional[str] = None) -> List[Dict]:
    """
    回傳各策略的命中率統計。
    支援 recent 30/100/300 視窗。
    """
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if lottery_type:
            conditions.append("pr.lottery_type = ?")
            params.append(lottery_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT pr.lottery_type, pr.strategy_name,
                   pi.id as item_id,
                   res.hit_count,
                   pr.created_at
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            LEFT JOIN prediction_results res ON res.item_id = pi.id
            {where}
            ORDER BY pr.created_at DESC
        """, params)

        rows = cur.fetchall()

        # 依 strategy 分組
        from collections import defaultdict
        groups: Dict[str, List] = defaultdict(list)
        for row in rows:
            key = f"{row['lottery_type']}|{row['strategy_name']}"
            groups[key].append({
                "hit_count": row["hit_count"],  # None if PENDING
                "created_at": row["created_at"],
            })

        result = []
        for key, items in groups.items():
            lt, strat = key.split("|", 1)
            resolved = [x for x in items if x["hit_count"] is not None]
            total = len(items)
            res_count = len(resolved)

            def window_stats(items_subset):
                if not items_subset:
                    return {"count": 0, "hit1": 0, "hit2": 0, "hit3": 0, "avg_hit": 0.0}
                c = len(items_subset)
                return {
                    "count": c,
                    "hit1": sum(1 for x in items_subset if x["hit_count"] >= 1) / c,
                    "hit2": sum(1 for x in items_subset if x["hit_count"] >= 2) / c,
                    "hit3": sum(1 for x in items_subset if x["hit_count"] >= 3) / c,
                    "avg_hit": sum(x["hit_count"] for x in items_subset) / c,
                }

            result.append({
                "lottery_type": lt,
                "strategy_name": strat,
                "total_bets": total,
                "resolved_bets": res_count,
                "pending_bets": total - res_count,
                "all": window_stats(resolved),
                "recent_30": window_stats(resolved[:30]),
                "recent_100": window_stats(resolved[:100]),
                "recent_300": window_stats(resolved[:300]),
            })

        # 依 all.hit3 降序排列
        result.sort(key=lambda x: x["all"].get("hit3", 0), reverse=True)
        return result
    finally:
        conn.close()
