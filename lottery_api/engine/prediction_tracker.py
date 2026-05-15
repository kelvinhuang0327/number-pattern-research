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

_NO_SPECIAL_TYPES = {
    "DAILY_539",
    "BIG_LOTTO_BONUS",
    "3_STAR",
    "4_STAR",
    "39_LOTTO",
    "38_LOTTO",
    "49_LOTTO",
    "BINGO_BINGO",
    "DOUBLE_WIN",
    "LOTTO_6_38",
}

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)


def _get_db():
    from database import db_manager
    return db_manager


def _normalize_special_for_output(lottery_type: str, special):
    if lottery_type in _NO_SPECIAL_TYPES:
        return None
    return special


def _load_strategy_states(lottery_type: str) -> Dict[str, Dict[str, Any]]:
    """載入 strategy_states_{lottery_type}.json。"""
    try:
        states_path = os.path.join(_api_root, "data", f"strategy_states_{lottery_type}.json")
        if not os.path.exists(states_path):
            return {}
        with open(states_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _derive_strategy_status(state: Dict[str, Any]) -> str:
    """Phase V: 優先使用 validated_status，fallback 至舊邏輯。
    RULE: VALIDATED→PRODUCTION, WATCH→WATCH (never upgrade), REJECTED→ADVISORY_ONLY
    """
    vs = state.get("validated_status")
    if vs == "VALIDATED":
        return "PRODUCTION"
    if vs == "WATCH":
        # WATCH must stay as WATCH — never promote to PRODUCTION
        return "WATCH"
    if vs in ("REJECTED", "REJECT"):
        return "ADVISORY_ONLY"
    # Legacy fallback (strategies without Phase V data)
    edge = state.get("edge_300p", 0) or 0
    trend = state.get("trend", "STABLE")
    alert = state.get("alert", False)
    if alert:
        return "WATCH"
    if edge >= 0.03 and trend in ("STABLE", "IMPROVING"):
        return "PRODUCTION"
    if edge > 0:
        return "WATCH"
    return "ADVISORY_ONLY"


def _rank_key_phase_v(state: Dict[str, Any]) -> tuple:
    """Phase V composite ranking: VALIDATED > WATCH > REJECTED, then composite_score,
    then edge_1500p, sharpe, and max_drawdown_rate (lower is better) as tiebreakers."""
    vs = state.get("validated_status")
    priority = 2 if vs == "VALIDATED" else (1 if vs == "WATCH" else 0)
    cs = float(state.get("composite_score") or 0)
    e1500 = float(state.get("edge_1500p") or 0)
    sharpe = float(state.get("sharpe") or 0)
    dd = float(state.get("max_drawdown_rate") or 0)
    return (priority, cs, e1500, sharpe, -dd)


def _get_current_best_strategy_refs(lottery_type: str) -> Dict[int, Dict[str, Any]]:
    """
    Phase V: 取得目前各注數最佳策略參考。

    規則：同一 num_bets 中，優先取 VALIDATED 策略，再按 composite_score / edge_1500p / sharpe 排序。
    不使用 edge_300p (已廢棄欄位)。
    """
    states = _load_strategy_states(lottery_type)
    # Group by num_bets
    by_nbets: Dict[int, list] = {}
    for state in states.values():
        try:
            num_bets = int(state.get("num_bets", 0))
        except Exception:
            continue
        if num_bets <= 0:
            continue
        by_nbets.setdefault(num_bets, []).append(state)

    refs: Dict[int, Dict[str, Any]] = {}
    for num_bets, candidates in by_nbets.items():
        # Phase V: rank by (validated_priority, composite_score, edge_1500p, sharpe, -drawdown)
        # Exclude REJECT strategies from being selected as best
        active = [s for s in candidates if s.get("validated_status") not in ("REJECTED", "REJECT")]
        pool = active if active else candidates  # fallback to all if every candidate is REJECT
        best = max(pool, key=_rank_key_phase_v)

        # Data completeness guard: check required Phase V fields
        missing_fields = [f for f in ("edge_150p", "edge_500p", "edge_1500p", "perm_p", "mcnemar_p")
                          if best.get(f) is None]

        refs[num_bets] = {
            "num_bets": num_bets,
            "strategy_name": best.get("name") or best.get("strategy_name", ""),
            "strategy_status": _derive_strategy_status(best),
            # Phase V fields
            "validated_status": best.get("validated_status"),
            "composite_score": round(float(best.get("composite_score") or 0), 6),
            "edge_150p": round(float(best.get("edge_150p") or 0) * 100, 3) if best.get("edge_150p") is not None else None,
            "edge_500p": round(float(best.get("edge_500p") or 0) * 100, 3) if best.get("edge_500p") is not None else None,
            "edge_1500p": round(float(best.get("edge_1500p") or 0) * 100, 3) if best.get("edge_1500p") is not None else None,
            "perm_p": best.get("perm_p"),
            "mcnemar_p": best.get("mcnemar_p"),
            "sharpe": best.get("sharpe"),
            "validation_notes": best.get("validation_notes"),
            "missing_phase_v_fields": missing_fields if missing_fields else None,
            "data_complete": len(missing_fields) == 0,
            # Legacy fields (kept for backward compat)
            "edge_300p": round(float(best.get("edge_300p", 0) or 0) * 100, 2),
            "rate_300p": round(float(best.get("rate_300p", 0) or 0) * 100, 2),
            "trend": best.get("trend", ""),
            "alert": bool(best.get("alert", False)),
            "sharpe_300p": round(float(best.get("sharpe_300p", 0) or 0), 4),
            "total_records": int(best.get("total_records", 0) or 0),
            "last_updated": (best.get("last_updated") or "")[:10],
            "note": best.get("note", ""),
        }
    return refs


def _derive_run_snapshot_state(
    snapshot_source: str,
    resolved_bets: int,
    total_bets: int,
    has_future_draw: bool,
) -> str:
    """推導 run 的解析狀態。"""
    if snapshot_source == "RECONSTRUCTED":
        return "RECONSTRUCTED"
    if total_bets > 0 and resolved_bets >= total_bets:
        return "RESOLVED"
    if has_future_draw:
        return "MISSED"
    return "PENDING"


def _build_best_bet_summary(cur, run_id: int, lottery_type: str, run_status: str, snapshot_source: str, run_strategy_name: str = "") -> Optional[Dict[str, Any]]:
    """
    從 run 的實際投注中，找出命中最好的一注（或第一注），作為歷史清單的摘要。
    不依賴 strategy_name 匹配，適用所有彩種（含無 1注策略的遊戲）。
    """
    cur.execute("""
        SELECT pi.id as item_id, pi.bet_index, pi.numbers, pi.special as pred_special,
               pi.status, pi.strategy_name as item_strategy_name, pi.num_bets as item_num_bets,
               res.actual_draw, res.actual_date, res.actual_numbers, res.actual_special,
               res.hit_count, res.matched_numbers, res.special_hit, res.resolved_at
        FROM prediction_items pi
        LEFT JOIN prediction_results res ON res.item_id = pi.id
        WHERE pi.run_id = ?
        ORDER BY COALESCE(res.hit_count, -1) DESC, pi.bet_index ASC
        LIMIT 1
    """, (run_id,))
    row = cur.fetchone()
    if not row:
        return None
    row = dict(row)
    predicted_numbers = json.loads(row["numbers"]) if row["numbers"] else []
    actual_numbers = json.loads(row["actual_numbers"]) if row.get("actual_numbers") else []
    matched_numbers = json.loads(row["matched_numbers"]) if row.get("matched_numbers") else []

    # 特別號：特別號通常只存在第一注，若最佳命中注沒有，另查 run 中任一有特別號的注
    pred_special = row.get("pred_special")
    if pred_special is None:
        cur.execute(
            "SELECT special FROM prediction_items WHERE run_id = ? AND special IS NOT NULL ORDER BY bet_index ASC LIMIT 1",
            (run_id,)
        )
        sp_row = cur.fetchone()
        if sp_row:
            pred_special = sp_row[0]

    return {
        "strategy_name": row.get("item_strategy_name") or run_strategy_name or "",
        "strategy_status": "N/A",
        "snapshot_state": snapshot_source if snapshot_source in ("RECONSTRUCTED",) else run_status,
        "predicted_numbers": predicted_numbers,
        "predicted_special": _normalize_special_for_output(lottery_type, pred_special),
        "actual_numbers": actual_numbers,
        "actual_special": _normalize_special_for_output(lottery_type, row.get("actual_special")),
        "matched_numbers": matched_numbers,
        "best_hit": int(row["hit_count"]) if row.get("hit_count") is not None else None,
        "actual_draw": row.get("actual_draw"),
        "actual_date": row.get("actual_date"),
    }


def _fetch_strategy_snapshot_rows(
    cur,
    run_id: int,
    strategy_name: str,
    num_bets: int,
    lottery_type: str,
) -> List[Dict[str, Any]]:
    """抓取某 run / 某策略名稱 / 某注數的歷史快照 rows。"""
    if not strategy_name:
        return []
    cur.execute("""
        SELECT pi.id as item_id, pi.bet_index, pi.numbers, pi.special as pred_special,
               pi.status, pi.strategy_name as item_strategy_name, pi.num_bets as item_num_bets,
               res.actual_draw, res.actual_date, res.actual_numbers, res.actual_special,
               res.hit_count, res.matched_numbers, res.special_hit, res.resolved_at,
               COALESCE(res.researched, '無') as researched
        FROM prediction_items pi
        LEFT JOIN prediction_results res ON res.item_id = pi.id
        WHERE pi.run_id = ? AND pi.strategy_name = ? AND pi.num_bets = ?
        ORDER BY pi.bet_index ASC
    """, (run_id, strategy_name, num_bets))
    rows = cur.fetchall()
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["pred_special"] = _normalize_special_for_output(lottery_type, item.get("pred_special"))
        item["actual_special"] = _normalize_special_for_output(lottery_type, item.get("actual_special"))
        normalized.append(item)
    return normalized


def _build_strategy_snapshot_slot(
    cur,
    run_id: int,
    lottery_type: str,
    latest_known_draw: str,
    snapshot_source: str,
    ref: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """建立單一注數的歷史比較槽位。"""
    if not ref:
        return {
            "num_bets": None,
            "strategy_name": None,
            "strategy_status": "N/A",
            "snapshot_state": "N/A",
            "has_formal_strategy": False,
            "is_placeholder": True,
            "note": "N/A",
            "bets": [],
        }

    run_rows = _fetch_strategy_snapshot_rows(
        cur=cur,
        run_id=run_id,
        strategy_name=ref["strategy_name"],
        num_bets=ref["num_bets"],
        lottery_type=lottery_type,
    )
    if not run_rows:
        return {
            **ref,
            "snapshot_state": "無歷史快照",
            "has_formal_strategy": True,
            "is_placeholder": False,
            "note": "無歷史快照",
            "actual_special": _normalize_special_for_output(lottery_type, None),
            "predicted_special": _normalize_special_for_output(lottery_type, ref.get("predicted_special")),
            "bets": [],
        }

    resolved_rows = [row for row in run_rows if row.get("status") == "RESOLVED"]
    if snapshot_source == "RECONSTRUCTED":
        snapshot_state = "RECONSTRUCTED"
    elif resolved_rows and len(resolved_rows) == len(run_rows):
        snapshot_state = "RESOLVED"
    else:
        cur.execute("""
            SELECT 1
            FROM draws
            WHERE lottery_type = ?
              AND CAST(draw AS INTEGER) > CAST(? AS INTEGER)
            LIMIT 1
        """, (lottery_type, latest_known_draw))
        has_future_draw = cur.fetchone() is not None
        snapshot_state = _derive_run_snapshot_state(snapshot_source, len(resolved_rows), len(run_rows), has_future_draw)

    bets: List[Dict[str, Any]] = []
    for row in run_rows:
        bet = {
            "item_id": row["item_id"],
            "bet_index": row["bet_index"],
            "predicted_numbers": json.loads(row["numbers"]) if row["numbers"] else [],
            "predicted_special": _normalize_special_for_output(lottery_type, row["pred_special"]),
            "status": row["status"],
            "item_strategy_name": row["item_strategy_name"],
            "item_num_bets": row["item_num_bets"],
        }
        if row["status"] == "RESOLVED":
            bet["actual_draw"] = row["actual_draw"]
            bet["actual_date"] = row["actual_date"]
            bet["actual_numbers"] = json.loads(row["actual_numbers"]) if row["actual_numbers"] else []
            bet["actual_special"] = _normalize_special_for_output(lottery_type, row["actual_special"])
            bet["hit_count"] = row["hit_count"]
            bet["matched_numbers"] = json.loads(row["matched_numbers"]) if row["matched_numbers"] else []
            bet["special_hit"] = bool(row["special_hit"])
            bet["resolved_at"] = row["resolved_at"]
            bet["researched"] = row["researched"] or "無"
        bets.append(bet)

    best_hit = max((int(row.get("hit_count") or 0) for row in run_rows if row.get("status") == "RESOLVED"), default=None)
    actual_source = resolved_rows[0] if resolved_rows else None
    actual_numbers = json.loads(actual_source["actual_numbers"]) if actual_source and actual_source.get("actual_numbers") else []
    matched_numbers = json.loads(actual_source["matched_numbers"]) if actual_source and actual_source.get("matched_numbers") else []

    return {
        **ref,
        "snapshot_state": snapshot_state,
        "has_formal_strategy": True,
        "is_placeholder": False,
        "note": None if snapshot_state != "無歷史快照" else "無歷史快照",
        "best_hit": best_hit,
        "actual_draw": actual_source["actual_draw"] if actual_source else None,
        "actual_date": actual_source["actual_date"] if actual_source else None,
        "actual_numbers": actual_numbers,
        "actual_special": _normalize_special_for_output(lottery_type, actual_source["actual_special"] if actual_source else None),
        "matched_numbers": matched_numbers,
        "bets": bets,
        "predicted_numbers": bets[0]["predicted_numbers"] if bets else [],
        "predicted_special": _normalize_special_for_output(lottery_type, bets[0]["predicted_special"] if bets else None),
        "special_hit": bool(actual_source.get("special_hit")) if actual_source and actual_source.get("special_hit") is not None else None,
        "status": snapshot_state,
    }


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
    snapshot_source: str = "VALID",
    notes: Optional[str] = None,
    strategy_bets: Optional[List[Dict]] = None,
) -> int:
    """
    儲存一次預測快照。回傳 run_id。
    snapshot_source: 'VALID' | 'RECONSTRUCTED' | 'MANUAL'

    strategy_bets (新格式，優先使用)：
      [{"strategy_name": str, "num_bets": int, "bets": [[...], ...], "special": int|None}, ...]
      每個元素代表一個策略的全部注數，系統一次儲存所有策略。

    bets (舊格式，向下相容)：扁平注數列表，以 strategy_name 為整體標籤。
    """
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        # 若為多策略格式，run 的 strategy_name 改為 "MULTI"
        run_label = "MULTI_STRATEGY" if strategy_bets else strategy_name
        cur.execute("""
            INSERT INTO prediction_runs
              (lottery_type, latest_known_draw, latest_known_date, strategy_name, snapshot_source, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (lottery_type, latest_known_draw, latest_known_date, run_label, snapshot_source, notes or ""))
        run_id = cur.lastrowid

        def _jaccard(a: List[int], b: List[int]) -> float:
            sa, sb = set(a), set(b)
            inter = len(sa & sb)
            union = len(sa | sb)
            return inter / union if union else 0.0

        global_idx = 0
        if strategy_bets:
            accepted_bets: List[List[int]] = []  # cross-strategy dedup tracker
            for sg in strategy_bets:
                sg_name = sg.get("strategy_name", strategy_name)
                sg_nbets = sg.get("num_bets", len(sg.get("bets", [])))
                sg_special = sg.get("special")
                sg_local_idx = 0
                for bet_nums in sg.get("bets", []):
                    # 跨策略 Jaccard 去重：若與已接受的任一注相似度 >= 0.6，跳過（fallback=保留原注，不替換）
                    bet_sorted = sorted(bet_nums)
                    is_duplicate = any(_jaccard(bet_sorted, prev) >= 0.6 for prev in accepted_bets)
                    if is_duplicate:
                        logger.debug(f"[PredictionTracker] Skipping duplicate bet {bet_sorted} for {sg_name} (Jaccard >= 0.6)")
                        sg_local_idx += 1
                        continue
                    accepted_bets.append(bet_sorted)
                    # 每個策略組的第一注儲存特別號（方便查詢）
                    sp = sg_special if (sg_local_idx == 0 and lottery_type == "POWER_LOTTO") else None
                    cur.execute("""
                        INSERT INTO prediction_items (run_id, bet_index, numbers, special, status, strategy_name, num_bets)
                        VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
                    """, (run_id, global_idx, json.dumps(bet_sorted), sp, sg_name, sg_nbets))
                    global_idx += 1
                    sg_local_idx += 1
            total_bets = global_idx
        else:
            for idx, numbers in enumerate(bets):
                sp = special if (idx == 0 and lottery_type == "POWER_LOTTO") else None
                cur.execute("""
                    INSERT INTO prediction_items (run_id, bet_index, numbers, special, status)
                    VALUES (?, ?, ?, ?, 'PENDING')
                """, (run_id, idx, json.dumps(sorted(numbers)), sp))
            total_bets = len(bets)

        # P1-3: Zone coverage logging for BIG_LOTTO
        if lottery_type == "BIG_LOTTO" and total_bets > 0:
            try:
                all_accepted = accepted_bets if strategy_bets else [sorted(b) for b in bets]
                zone_hits = [0, 0, 0, 0, 0]
                ranges = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]
                for bet in all_accepted:
                    for zi, (lo, hi) in enumerate(ranges):
                        zone_hits[zi] += sum(1 for n in bet if lo <= n <= hi)
                avg_zone = [round(z / total_bets, 2) for z in zone_hits]
                logger.info(f"[PredictionTracker] Zone coverage (avg/bet): {avg_zone} for run={run_id}")
                # Update zone_coverage on each inserted item
                cur.execute("""
                    UPDATE prediction_items SET zone_coverage=? WHERE run_id=?
                """, (json.dumps(avg_zone), run_id))
            except Exception as zex:
                logger.debug(f"[PredictionTracker] zone coverage log failed: {zex}")

        conn.commit()
        logger.info(f"[PredictionTracker] Snapshot saved: run={run_id}, {lottery_type}, {total_bets} bets")
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
    if lottery_type == "POWER_LOTTO":
        # 威力彩：第二區預測號碼直接比對
        if predicted_special is not None and actual_special is not None:
            special_hit = 1 if predicted_special == actual_special else 0
    elif lottery_type == "BIG_LOTTO":
        # 大樂透：預測主號中是否含特別號（貳獎/陸獎條件）
        if actual_special is not None and actual_special in pred_set:
            special_hit = 1
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

            # P1-1: Compute WQ score for actual draw numbers
            wq_score_val = None
            split_risk_val = None
            try:
                import sys as _sys
                _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if _base not in _sys.path:
                    _sys.path.insert(0, _base)
                from engine.winning_quality import analyze as wq_analyze
                # Pull recent 300 draws for baseline
                cur.execute("""
                    SELECT numbers FROM draws
                    WHERE lottery_type=?
                    ORDER BY CAST(draw AS INTEGER) DESC LIMIT 300
                """, (lottery_type,))
                hist_rows = cur.fetchall()
                if hist_rows:
                    wq_result = wq_analyze(actual_numbers, lottery_type, recent_n=len(hist_rows))
                    wq_score_val = int(round(wq_result.get("pop_score", 50)))
                    split_risk_val = wq_result.get("split_risk", "MED")
            except Exception as wex:
                logger.debug(f"[PredictionTracker] WQ compute failed: {wex}")

            try:
                cur.execute("""
                    INSERT OR IGNORE INTO prediction_results
                      (item_id, actual_draw, actual_date, actual_numbers, actual_special,
                       hit_count, matched_numbers, special_hit, researched, wq_score, split_risk)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, '無', ?, ?)
                """, (
                    item_id,
                    actual_draw,
                    actual_date,
                    json.dumps(actual_numbers),
                    actual_special,
                    cmp["hit_count"],
                    json.dumps(cmp["matched_numbers"]),
                    cmp["special_hit"],
                    wq_score_val,
                    split_risk_val,
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
    analyzed: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    dedup: bool = True,
) -> Dict:
    """回傳歷史預測清單（依 run），包含 snapshot_source。
    dedup=True（預設）：同一 latest_known_draw 只保留最佳 run
    （優先順序：MULTI_STRATEGY > 其他，再取 id 最大者）。
    """
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        base_conditions = []
        base_params: list = []
        if lottery_type:
            base_conditions.append("pr.lottery_type = ?")
            base_params.append(lottery_type)
        if analyzed:
            analyzed_value = "未研究" if analyzed in ("UNREVIEWED", "未研究") else analyzed
            base_conditions.append("COALESCE(pr.analyzed, '未研究') = ?")
            base_params.append(analyzed_value)
            # Single source of truth: also exclude runs already covered by
            # prediction_review_status (REVIEWED/RESOLVED) OR whose
            # latest_known_draw matches an existing review_session for the same game.
            if analyzed_value == "未研究":
                base_conditions.append(
                    "pr.id NOT IN ("
                    "  SELECT prediction_run_id FROM prediction_review_status"
                    "  WHERE review_status IN ('REVIEWED', 'RESOLVED')"
                    ")"
                )
                base_conditions.append(
                    "NOT EXISTS ("
                    "  SELECT 1 FROM review_sessions rs"
                    "  WHERE rs.game = pr.lottery_type"
                    "    AND rs.draw = pr.latest_known_draw"
                    ")"
                )

        base_where = ("WHERE " + " AND ".join(base_conditions)) if base_conditions else ""

        # status 在 SQL 層過濾（避免 LIMIT/OFFSET 在 Python 層過濾前已截斷）
        status_having = ""
        if status:
            if status == "RESOLVED":
                status_having = "HAVING SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) = COUNT(pi.id)"
            else:
                status_having = "HAVING SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) < COUNT(pi.id)"

        # dedup CTE：同一 (lottery_type, latest_known_draw) 只保留最佳 run
        # 優先順序：MULTI_STRATEGY=0 > 其他=1，再取 id 最大者
        dedup_filter = ""
        if dedup:
            dedup_filter = """
                AND pr.id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY lottery_type, latest_known_draw
                                   ORDER BY CASE WHEN strategy_name='MULTI_STRATEGY' THEN 0 ELSE 1 END ASC,
                                            id DESC
                               ) as rn
                        FROM prediction_runs
                    ) t WHERE rn = 1
                )
            """
            if base_where:
                dedup_filter = dedup_filter  # appended below
            base_where_with_dedup = (base_where + " " + dedup_filter) if base_where else ("WHERE 1=1 " + dedup_filter)
        else:
            base_where_with_dedup = base_where

        # 先算符合條件的總數
        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT pr.id
                FROM prediction_runs pr
                JOIN prediction_items pi ON pi.run_id = pr.id
                {base_where_with_dedup}
                GROUP BY pr.id
                {status_having}
            )
        """, base_params)
        total = cur.fetchone()[0]

        cur.execute(f"""
            SELECT pr.id as run_id,
                   pr.lottery_type,
                   pr.latest_known_draw,
                   pr.latest_known_date,
                   pr.strategy_name,
                   pr.snapshot_source,
                   COALESCE(pr.analyzed, '未研究') as analyzed,
                   pr.created_at,
                   COUNT(pi.id) as total_bets,
                   SUM(CASE WHEN pi.status='RESOLVED' THEN 1 ELSE 0 END) as resolved_bets,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_draw ELSE NULL END) as actual_draw,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_date ELSE NULL END) as actual_date,
                   MAX(CASE WHEN pi.status='RESOLVED' THEN res.hit_count ELSE NULL END) as best_hit,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.wq_score ELSE NULL END) as wq_score,
                   MIN(CASE WHEN pi.status='RESOLVED' THEN res.split_risk ELSE NULL END) as split_risk,
                   EXISTS(
                       SELECT 1
                       FROM draws d
                       WHERE d.lottery_type = pr.lottery_type
                         AND CAST(d.draw AS INTEGER) > CAST(pr.latest_known_draw AS INTEGER)
                   ) as has_future_draw,
                   MAX(CASE WHEN prs.review_status IN ('REVIEWED','RESOLVED') THEN prs.review_status ELSE NULL END) as prs_review_status,
                   MAX(prs.review_session_id) as prs_session_id,
                   (SELECT rs2.id FROM review_sessions rs2
                    WHERE rs2.game = pr.lottery_type
                      AND rs2.draw = pr.latest_known_draw
                    LIMIT 1) as linked_session_id
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            LEFT JOIN prediction_results res ON res.item_id = pi.id
            LEFT JOIN prediction_review_status prs ON prs.prediction_run_id = pr.id
            {base_where_with_dedup}
            GROUP BY pr.id
            {status_having}
            ORDER BY CASE WHEN MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_date ELSE NULL END) IS NULL
                          THEN '9999-99-99' ELSE MIN(CASE WHEN pi.status='RESOLVED' THEN res.actual_date ELSE NULL END) END DESC,
                     CAST(pr.latest_known_draw AS INTEGER) DESC
            LIMIT ? OFFSET ?
        """, base_params + [limit, offset])

        rows = cur.fetchall()
        runs = []
        for row in rows:
            resolved_bets = row["resolved_bets"] or 0
            total_bets = row["total_bets"] or 1
            run_status = _derive_run_snapshot_state(
                row["snapshot_source"] or "VALID",
                resolved_bets,
                total_bets,
                bool(row["has_future_draw"]),
            )
            single_bet_summary = _build_best_bet_summary(
                cur=cur,
                run_id=row["run_id"],
                lottery_type=row["lottery_type"],
                run_status=run_status,
                snapshot_source=row["snapshot_source"] or "VALID",
                run_strategy_name=row["strategy_name"] or "",
            )

            runs.append({
                "run_id": row["run_id"],
                "lottery_type": row["lottery_type"],
                "latest_known_draw": row["latest_known_draw"],
                "latest_known_date": row["latest_known_date"],
                "strategy_name": row["strategy_name"],
                "snapshot_source": row["snapshot_source"] or "VALID",
                "analyzed": row["analyzed"] or "未研究",
                "created_at": row["created_at"],
                "total_bets": total_bets,
                "resolved_bets": resolved_bets,
                "status": run_status,
                "actual_draw": row["actual_draw"],
                "actual_date": row["actual_date"],
                "best_hit": row["best_hit"],
                "wq_score": row["wq_score"],
                "split_risk": row["split_risk"],
                "single_bet_summary": single_bet_summary,
                # review linkage — derived from prediction_review_status only
                # (linked_session_id is kept for the UNREVIEWED exclusion filter above,
                #  but must NOT mark future-draw predictions as reviewed in the badge)
                "review_status": (
                    row["prs_review_status"]
                    if row["prs_review_status"] in ("REVIEWED", "RESOLVED")
                    else None
                ),
                "review_session_id": (
                    row["prs_session_id"]
                    if row["prs_review_status"] in ("REVIEWED", "RESOLVED")
                    else None
                ),
            })

        return {"total": total, "offset": offset, "limit": limit, "runs": runs}
    finally:
        conn.close()


def _get_rsm_strategies(lottery_type: str) -> List[Dict]:
    """Phase V: 從 strategy_states_*.json 取得各注數最佳策略完整分析（供明細面板顯示）。
    排名規則：VALIDATED > WATCH > REJECTED，再依 composite_score 排序（不再使用 edge_300p 排名）。
    """
    try:
        states_path = os.path.join(_api_root, "data", f"strategy_states_{lottery_type}.json")
        if not os.path.exists(states_path):
            return []
        states = json.load(open(states_path, "r", encoding="utf-8"))
        # Phase V: group by num_bets, rank by (validated_priority, composite_score)
        by_nbets: Dict[int, list] = {}
        for v in states.values():
            nb = int(v.get("num_bets", 0))
            if nb <= 0:
                continue
            by_nbets.setdefault(nb, []).append(v)

        result = []
        for nb in sorted(by_nbets.keys()):
            candidates = by_nbets[nb]
            has_phase_v = any(c.get("validated_status") for c in candidates)
            if has_phase_v:
                s = max(candidates, key=_rank_key_phase_v)
            else:
                s = max(candidates, key=lambda x: float(x.get("edge_300p", -9) or -9))

            def pct(key): return round(float(s.get(key) or 0) * 100, 3) if s.get(key) is not None else None
            def pct_legacy(key): return round(float(s.get(key, 0)) * 100, 2)
            def rate(key): return round(float(s.get(key, 0)) * 100, 1)

            missing = [f for f in ("edge_150p", "edge_500p", "edge_1500p", "perm_p", "mcnemar_p")
                       if s.get(f) is None]
            result.append({
                "num_bets":        nb,
                "strategy_name":   s.get("name") or s.get("strategy_name", ""),
                "total_records":   s.get("total_records", 0),
                # Phase V fields
                "validated_status":  s.get("validated_status"),
                "composite_score":   round(float(s.get("composite_score") or 0), 6),
                "edge_150p":         pct("edge_150p"),
                "edge_500p":         pct("edge_500p"),
                "edge_1500p":        pct("edge_1500p"),
                "perm_p":            s.get("perm_p"),
                "mcnemar_p":         s.get("mcnemar_p"),
                "sharpe":            s.get("sharpe"),
                "max_drawdown_rate": s.get("max_drawdown_rate"),
                "validation_notes":  s.get("validation_notes"),
                "data_complete":     len(missing) == 0,
                # Legacy fields
                "edge_30p":      pct_legacy("edge_30p"),
                "edge_100p":     pct_legacy("edge_100p"),
                "edge_300p":     pct_legacy("edge_300p"),
                "rate_30p":      rate("rate_30p"),
                "rate_100p":     rate("rate_100p"),
                "rate_300p":     rate("rate_300p"),
                "trend":         s.get("trend", ""),
                "z_score":       round(float(s.get("z_score", 0)), 3),
                "sharpe_300p":   round(float(s.get("sharpe_300p", 0)), 4),
                "alert":         bool(s.get("alert", False)),
                "last_updated":  (s.get("last_updated") or "")[:10],
                "note":          s.get("note", ""),
            })
        return result
    except Exception:
        return []


def get_run_detail(run_id: int) -> Optional[Dict]:
    """回傳單一 run 的完整比對資料"""
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT pr.*, pi.id as item_id, pi.bet_index, pi.numbers, pi.special as pred_special,
                   pi.status, pi.strategy_name as item_strategy_name, pi.num_bets as item_num_bets,
                   pi.zone_coverage,
                   res.actual_draw, res.actual_date, res.actual_numbers, res.actual_special,
                   res.hit_count, res.matched_numbers, res.special_hit, res.resolved_at,
                   COALESCE(res.researched, '無') as researched,
                   res.wq_score, res.split_risk,
                   COALESCE(pr.analyzed, '未研究') as run_analyzed,
                   pr.analysis_note,
                   pr.review_json,
                   (SELECT prs.review_status FROM prediction_review_status prs
                    WHERE prs.prediction_run_id = pr.id
                      AND prs.review_status IN ('REVIEWED','RESOLVED')
                    LIMIT 1) as prs_review_status,
                   (SELECT prs.review_session_id FROM prediction_review_status prs
                    WHERE prs.prediction_run_id = pr.id
                      AND prs.review_status IN ('REVIEWED','RESOLVED')
                    LIMIT 1) as prs_session_id
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
        # Parse review_json safely
        raw_review = first["review_json"]
        parsed_review = None
        if raw_review:
            try:
                parsed_review = json.loads(raw_review)
            except (json.JSONDecodeError, TypeError):
                parsed_review = raw_review

        result = {
            "run_id": run_id,
            "lottery_type": first["lottery_type"],
            "latest_known_draw": first["latest_known_draw"],
            "latest_known_date": first["latest_known_date"],
            "strategy_name": first["strategy_name"],
            "snapshot_source": first["snapshot_source"] or "VALID",
            "notes": first["notes"],
            "created_at": first["created_at"],
            "analyzed": first["run_analyzed"] or "未研究",
            "analysis_note": first["analysis_note"] or "",
            "review_json": parsed_review,
            "review_status": first["prs_review_status"],
            "review_session_id": first["prs_session_id"],
            "bets": [],
        }

        # 判斷是否為多策略格式（prediction_items 有 strategy_name 欄位值）
        has_strategy_per_item = any(row["item_strategy_name"] for row in rows)

        for row in rows:
            bet = {
                "item_id": row["item_id"],
                "bet_index": row["bet_index"],
                "predicted_numbers": json.loads(row["numbers"]),
                "predicted_special": _normalize_special_for_output(result["lottery_type"], row["pred_special"]),
                "status": row["status"],
                "item_strategy_name": row["item_strategy_name"],
                "item_num_bets": row["item_num_bets"],
            }
            if row["status"] == "RESOLVED":
                bet["actual_draw"] = row["actual_draw"]
                bet["actual_date"] = row["actual_date"]
                bet["actual_numbers"] = json.loads(row["actual_numbers"]) if row["actual_numbers"] else []
                bet["actual_special"] = _normalize_special_for_output(result["lottery_type"], row["actual_special"])
                bet["hit_count"] = row["hit_count"]
                bet["matched_numbers"] = json.loads(row["matched_numbers"]) if row["matched_numbers"] else []
                bet["special_hit"] = bool(row["special_hit"])
                bet["resolved_at"] = row["resolved_at"]
                bet["researched"] = row["researched"] or "無"
                bet["wq_score"] = row["wq_score"]
                bet["split_risk"] = row["split_risk"]
            if row["zone_coverage"]:
                try:
                    bet["zone_coverage"] = json.loads(row["zone_coverage"])
                except Exception:
                    pass
            result["bets"].append(bet)

        current_refs = _get_current_best_strategy_refs(result["lottery_type"])
        result["current_best_strategies"] = [
            _build_strategy_snapshot_slot(
                cur=cur,
                run_id=run_id,
                lottery_type=result["lottery_type"],
                latest_known_draw=result["latest_known_draw"],
                snapshot_source=result["snapshot_source"],
                ref=current_refs.get(num_bets),
            )
            for num_bets in range(1, 6)
        ]

        # 多策略格式：按 strategy_name + num_bets 分組
        if has_strategy_per_item:
            bets_by_strategy: List[Dict] = []
            seen: Dict[str, int] = {}  # strategy_name -> index in bets_by_strategy
            for bet in result["bets"]:
                sg_name = bet.get("item_strategy_name") or result["strategy_name"]
                sg_nbets = bet.get("item_num_bets") or 0
                key = sg_name
                if key not in seen:
                    seen[key] = len(bets_by_strategy)
                    bets_by_strategy.append({
                        "strategy_name": sg_name,
                        "num_bets": sg_nbets,
                        "bets": [],
                    })
                bets_by_strategy[seen[key]]["bets"].append(bet)
            result["bets_by_strategy"] = bets_by_strategy
        else:
            result["bets_by_strategy"] = None  # 舊格式，前端 fallback

        # 附加 RSM 各注數最佳策略參考表
        result["rsm_strategies"] = _get_rsm_strategies(result["lottery_type"])
        return result
    finally:
        conn.close()


def submit_run_analysis(run_id: int, note: str) -> str:
    """提交分析筆記，標記 run 為已研究。note 為必填（不可為空白）。"""
    note = (note or "").strip()
    if not note:
        raise ValueError("分析筆記不可為空白，請輸入分析內容後再提交。")
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prediction_runs WHERE id = ?", (run_id,))
        if not cur.fetchone():
            raise ValueError(f"run_id {run_id} not found")
        cur.execute(
            "UPDATE prediction_runs SET analyzed = '已研究', analysis_note = ? WHERE id = ?",
            (note, run_id)
        )
        conn.commit()
        return "已研究"
    finally:
        conn.close()


def clear_run_analysis(run_id: int) -> str:
    """清除分析筆記，還原為未研究。"""
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prediction_runs WHERE id = ?", (run_id,))
        if not cur.fetchone():
            raise ValueError(f"run_id {run_id} not found")
        cur.execute(
            "UPDATE prediction_runs SET analyzed = '未研究', analysis_note = NULL WHERE id = ?",
            (run_id,)
        )
        conn.commit()
        return "未研究"
    finally:
        conn.close()


def submit_run_review(run_id: int, note: str, review_json: str = None) -> dict:
    """提交結構化檢討報告（analysis_note + review_json），標記為已研究。"""
    note = (note or "").strip()
    if not note:
        raise ValueError("分析筆記不可為空白，請輸入分析內容後再提交。")
    db = _get_db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM prediction_runs WHERE id = ?", (run_id,))
        if not cur.fetchone():
            raise ValueError(f"run_id {run_id} not found")
        cur.execute(
            "UPDATE prediction_runs SET analyzed = '已研究', analysis_note = ?, review_json = ? WHERE id = ?",
            (note, review_json, run_id)
        )
        conn.commit()
        return {"analyzed": "已研究", "analysis_note": note, "review_json": review_json}
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 策略表現聚合
# ──────────────────────────────────────────────

# 各彩種單注 M3+ 隨機基準（至少命中 3 個主球）
_BASELINE_P1: Dict[str, float] = {
    "BIG_LOTTO":   0.0186,   # C(6,3)…/C(49,6)
    "POWER_LOTTO": 0.0387,   # C(6,3)…/C(38,6)
    "DAILY_539":   0.01004,  # C(5,3)…/C(39,5)
}


def get_performance(lottery_type: Optional[str] = None,
                    valid_only: bool = True) -> List[Dict]:
    """
    以「目前各注數最佳策略」為單位統計各策略成功率。
    valid_only=True（預設）：只計入 snapshot_source='VALID' 的快照。
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
        if valid_only:
            conditions.append("(pr.snapshot_source = 'VALID' OR pr.snapshot_source IS NULL)")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT pr.id AS run_id,
                   pr.lottery_type,
                   pr.snapshot_source,
                   pr.latest_known_draw,
                   pr.created_at,
                   pi.strategy_name AS item_strategy_name,
                   pi.num_bets AS item_num_bets,
                   pi.status AS item_status,
                   res.hit_count,
                   res.actual_draw,
                   res.actual_date
            FROM prediction_runs pr
            JOIN prediction_items pi ON pi.run_id = pr.id
            LEFT JOIN prediction_results res ON res.item_id = pi.id
            {where}
            ORDER BY pr.created_at DESC, pi.bet_index ASC
        """, params)

        rows = cur.fetchall()

        from collections import defaultdict
        current_refs_by_lt: Dict[str, Dict[int, Dict[str, Any]]] = {}
        aggregates: Dict[tuple, Dict[int, Dict[str, Any]]] = defaultdict(dict)

        def _ensure_ref_map(lt: str) -> Dict[int, Dict[str, Any]]:
            if lt not in current_refs_by_lt:
                current_refs_by_lt[lt] = _get_current_best_strategy_refs(lt)
            return current_refs_by_lt[lt]

        for row in rows:
            lt = row["lottery_type"]
            ref_map = _ensure_ref_map(lt)
            for num_bets, ref in ref_map.items():
                if not ref:
                    continue
                if row["item_strategy_name"] != ref["strategy_name"]:
                    continue
                if int(row["item_num_bets"] or 0) != int(num_bets):
                    continue
                key = (lt, num_bets, ref["strategy_name"])
                run_bucket = aggregates.setdefault(key, {})
                run_stat = run_bucket.setdefault(row["run_id"], {
                    "run_id": row["run_id"],
                    "snapshot_source": row["snapshot_source"] or "VALID",
                    "resolved": 0,
                    "total": 0,
                    "best_hit": None,
                    "latest_known_draw": row["latest_known_draw"],
                })
                run_stat["total"] += 1
                if row["item_status"] == "RESOLVED":
                    run_stat["resolved"] += 1
                    run_hit = int(row["hit_count"] or 0)
                    run_stat["best_hit"] = run_hit if run_stat["best_hit"] is None else max(run_stat["best_hit"], run_hit)

        result = []
        lottery_types = [lottery_type] if lottery_type else ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]
        for lt in lottery_types:
            ref_map = _ensure_ref_map(lt)
            p1 = _BASELINE_P1.get(lt, 0.0186)
            for num_bets in range(1, 6):
                ref = ref_map.get(num_bets)
                if not ref:
                    result.append({
                        "lottery_type": lt,
                        "num_bets": num_bets,
                        "strategy_name": None,
                        "strategy_status": "N/A",
                        "total_runs": 0,
                        "resolved_runs": 0,
                        "pending_runs": 0,
                        "success_count": 0,
                        "success_rate": None,
                        "baseline": None,
                        "edge": None,
                        "avg_bets": num_bets,
                        "availability": "N/A",
                        "note": "N/A",
                    })
                    continue

                key = (lt, num_bets, ref["strategy_name"])
                run_bucket = aggregates.get(key, {})
                total_runs = len(run_bucket)
                resolved_runs = [r for r in run_bucket.values() if r["total"] > 0 and r["resolved"] == r["total"]]
                pending_runs = total_runs - len(resolved_runs)
                success_runs = [r for r in resolved_runs if (r["best_hit"] or 0) >= 3]
                success_count = len(success_runs)
                success_rate = success_count / len(resolved_runs) if resolved_runs else None
                baseline = 1.0 - (1.0 - p1) ** num_bets
                edge = (success_rate - baseline) if success_rate is not None else None

                result.append({
                    "lottery_type": lt,
                    "num_bets": num_bets,
                    "strategy_name": ref["strategy_name"],
                    "strategy_status": ref["strategy_status"],
                    "validated_status": ref.get("validated_status"),
                    "data_complete": ref.get("data_complete", True),
                    "total_runs": total_runs,
                    "resolved_runs": len(resolved_runs),
                    "pending_runs": pending_runs,
                    "success_count": success_count,
                    "success_rate": round(success_rate, 4) if success_rate is not None else None,
                    "baseline": round(baseline, 4),
                    "edge": round(edge, 4) if edge is not None else None,
                    "avg_bets": num_bets,
                    "availability": "HAS_HISTORY" if total_runs > 0 else "NO_HISTORY",
                    "note": ref.get("note", ""),
                })

        # 以彩種與注數排序，保持 UI 穩定
        result.sort(key=lambda x: (x["lottery_type"], x["num_bets"]))
        return result
    finally:
        conn.close()
