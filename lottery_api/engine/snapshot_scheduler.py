"""
Snapshot Scheduler — 預測快照排程管理

職責：
1. startup_check()   — 系統啟動時掃描缺漏，補發 SCHEDULED / MISSED_WINDOW
2. ensure_scheduled() — 確保每個彩種有一個 SCHEDULED 條目指向下一期
3. generate_snapshot_for_schedule() — 為指定排程產生預測快照（僅在 VALID 時機）
4. get_schedule_status() — 回傳各彩種目前排程狀態

核心設計原則：
- 只預測「下一期尚未開獎」的期號（VALID）
- 若目標期號已在 DB → 標記 MISSED_WINDOW
- 不允許覆蓋已存在的快照（冪等）
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

ALL_GAMES = ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]


def _db():
    from database import db_manager
    return db_manager


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_draw(current_draw: str) -> str:
    """下一期號 = 當前期號 + 1（三個彩種均適用）"""
    return str(int(current_draw) + 1)


def _draw_in_db(lottery_type: str, draw_number: str) -> bool:
    """檢查某期號是否已在 draws 表中"""
    db = _db()
    row = db.get_draw(lottery_type, draw_number)
    return row is not None


def _get_latest_draw(lottery_type: str) -> Optional[Dict]:
    """取得 DB 中最新一期開獎資料"""
    db = _db()
    draws = db.get_all_draws(lottery_type)
    if not draws:
        return None
    return draws[0]  # get_all_draws 回傳 DESC 順序


# ──────────────────────────────────────────────
# 排程 CRUD
# ──────────────────────────────────────────────

def _get_schedule(lottery_type: str, target_draw: str) -> Optional[Dict]:
    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, lottery_type, target_draw, target_date, scheduled_at, status, run_id, notes
            FROM snapshot_schedule
            WHERE lottery_type = ? AND target_draw = ?
        """, (lottery_type, target_draw))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def _create_schedule(lottery_type: str, target_draw: str,
                     target_date: Optional[str] = None, notes: str = "") -> Dict:
    """建立 SCHEDULED 條目（若已存在則回傳現有）"""
    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO snapshot_schedule
              (lottery_type, target_draw, target_date, status, notes)
            VALUES (?, ?, ?, 'SCHEDULED', ?)
        """, (lottery_type, target_draw, target_date, notes))
        conn.commit()
        return _get_schedule(lottery_type, target_draw)
    finally:
        conn.close()


def _update_schedule_status(schedule_id: int, status: str,
                             run_id: Optional[int] = None, notes: Optional[str] = None):
    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        if run_id is not None and notes is not None:
            cur.execute("""
                UPDATE snapshot_schedule
                SET status = ?, run_id = ?, notes = ?
                WHERE id = ?
            """, (status, run_id, notes, schedule_id))
        elif run_id is not None:
            cur.execute("""
                UPDATE snapshot_schedule SET status = ?, run_id = ? WHERE id = ?
            """, (status, run_id, schedule_id))
        elif notes is not None:
            cur.execute("""
                UPDATE snapshot_schedule SET status = ?, notes = ? WHERE id = ?
            """, (status, notes, schedule_id))
        else:
            cur.execute("""
                UPDATE snapshot_schedule SET status = ? WHERE id = ?
            """, (status, schedule_id))
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 快照產生（僅限 VALID 視窗）
# ──────────────────────────────────────────────

def _rsm_best_label(lottery_type: str, num_bets: int) -> Optional[str]:
    """從 strategy_states_*.json 查詢最佳 RSM 策略名稱（用於覆蓋 Coordinator 通用標籤）。"""
    try:
        import json as _json
        p = os.path.join(_api_root, "data", f"strategy_states_{lottery_type}.json")
        if not os.path.exists(p):
            return None
        states = _json.load(open(p, "r", encoding="utf-8"))
        candidates = [v for v in states.values() if int(v.get("num_bets", 0)) == int(num_bets)]
        if not candidates:
            return None
        best = max(candidates, key=lambda s: float(s.get("edge_300p", -9)))
        return best.get("name") or best.get("strategy_name")
    except Exception:
        return None


def _run_prediction(lottery_type: str, history: List[Dict],
                    num_bets: int = 3) -> tuple:
    """執行 RSM 協調器預測，回傳 (bets, strategy_label, special)"""
    try:
        from engine.strategy_coordinator import coordinator_predict
        bets, label = coordinator_predict(lottery_type, history, n_bets=num_bets, mode="direct")
        # 以 RSM 最佳策略名取代通用 Coordinator 標籤
        if label and label.startswith("Coordinator-"):
            rsm_name = _rsm_best_label(lottery_type, num_bets)
            if rsm_name:
                label = rsm_name
    except Exception as e:
        logger.warning(f"[Scheduler] coordinator_predict failed ({e}), fallback to frequency")
        from models.unified_predictor import UnifiedPredictionEngine
        engine = UnifiedPredictionEngine()
        result = engine.frequency_predict(history, {})
        bets = [result.get("numbers", [])]
        label = "frequency_fallback"

    special = None
    if lottery_type == "POWER_LOTTO":
        try:
            from routes.prediction import get_enhanced_special_prediction
            sp = get_enhanced_special_prediction(history, {}, bets[0] if bets else [])
            special = sp.get("special")
        except Exception:
            pass

    return bets, label, special


def generate_snapshot_for_schedule(schedule_id: int,
                                   source: str = "VALID",
                                   num_bets: int = 3) -> Optional[int]:
    """
    為指定排程產生預測快照。
    source: 'VALID' | 'RECONSTRUCTED'
    回傳 run_id，若已有快照則回傳 None（不重複建立）。
    """
    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM snapshot_schedule WHERE id = ?", (schedule_id,))
        sched = cur.fetchone()
    finally:
        conn.close()

    if not sched:
        raise ValueError(f"Schedule {schedule_id} not found")

    # 若已有關聯 run_id → 不重複
    if sched["run_id"]:
        logger.info(f"[Scheduler] Schedule {schedule_id} already has run_id={sched['run_id']}, skip")
        return None

    lottery_type = sched["lottery_type"]
    target_draw = sched["target_draw"]

    # 取得截至目標期前的歷史資料
    # latest_known = target_draw - 1（即已知最新期）
    latest_known_draw = str(int(target_draw) - 1)
    db2 = _db()
    all_draws = db2.get_all_draws(lottery_type)
    # 只用 draw <= latest_known_draw 的資料；策略函數預期 ASC（history[-1] = 最新）
    history = sorted(
        [d for d in all_draws if int(d["draw"]) <= int(latest_known_draw)],
        key=lambda d: (d.get("date", ""), d.get("draw", ""))
    )

    if not history:
        logger.warning(f"[Scheduler] No history for {lottery_type} up to {latest_known_draw}")
        return None

    # 最新已知期的資料（ASC 排序後最後一筆）
    latest_data = history[-1]

    bets, strategy_label, special = _run_prediction(lottery_type, history, num_bets)

    from engine.prediction_tracker import create_snapshot
    run_id = create_snapshot(
        lottery_type=lottery_type,
        bets=bets,
        strategy_name=strategy_label,
        latest_known_draw=latest_data["draw"],
        latest_known_date=latest_data.get("date"),
        special=special,
        snapshot_source=source,
        notes=f"schedule_id={schedule_id}",
    )

    new_status = "SNAPSHOT_CREATED" if source == "VALID" else "RECONSTRUCTED"
    _update_schedule_status(
        schedule_id,
        new_status,
        run_id=run_id,
        notes=f"run_id={run_id} source={source}",
    )
    logger.info(f"[Scheduler] {lottery_type} target={target_draw} → run_id={run_id} ({new_status})")
    return run_id


# ──────────────────────────────────────────────
# 啟動時自動補全邏輯
# ──────────────────────────────────────────────

def startup_check() -> Dict:
    """
    系統啟動時執行：
    1. 標記所有過期的 SCHEDULED 條目（目標期已入庫）為 MISSED_WINDOW
    2. 確保每個彩種有一個指向下一期的 SCHEDULED 條目
    3. 若 SCHEDULED 條目的目標期尚未入庫 → 自動產生 VALID 快照
    4. 補全近 30 天已開獎但缺少預測快照的期號（RECONSTRUCTED）

    回傳每個彩種的處理摘要。
    """
    summary = {}
    for game in ALL_GAMES:
        result = _startup_check_game(game)
        backfill = _backfill_30days(game)
        result["backfill"] = backfill
        summary[game] = result
        logger.info(f"[Scheduler] startup_check {game}: {result}")
    return summary


def _backfill_30days(lottery_type: str) -> Dict:
    """補全近 30 天已開獎但缺少預測快照的期號（RECONSTRUCTED）。"""
    from datetime import date
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y/%m/%d")

    db = _db()
    all_draws = db.get_all_draws(lottery_type)
    # 只取近 30 天的已開獎期
    recent = [d for d in all_draws if (d.get("date") or "") >= cutoff]
    recent_sorted = sorted(recent, key=lambda d: int(d["draw"]))

    if not recent_sorted:
        return {"checked": 0, "created": 0}

    # 取得所有已有預測快照的 latest_known_draw 集合
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT latest_known_draw FROM prediction_runs WHERE lottery_type = ?",
            (lottery_type,)
        )
        existing_known = {row["latest_known_draw"] for row in cur.fetchall()}
    finally:
        conn.close()

    created = 0
    for draw_info in recent_sorted:
        draw = draw_info["draw"]
        # 要預測 draw，需要 latest_known = draw-1 的快照
        prev_draw = str(int(draw) - 1)
        if prev_draw in existing_known:
            continue  # 已有快照，跳過

        # 確認 prev_draw 確實在 DB 中（有歷史資料可用）
        history = sorted(
            [d for d in all_draws if int(d["draw"]) <= int(prev_draw)],
            key=lambda d: (d.get("date", ""), d.get("draw", ""))
        )
        if not history:
            continue

        # 建立排程條目並產生 RECONSTRUCTED 快照
        try:
            sched = _get_schedule(lottery_type, draw)
            if not sched:
                sched = _create_schedule(lottery_type, draw,
                                         target_date=draw_info.get("date"),
                                         notes="backfill_30days")
            if sched["status"] not in ("SNAPSHOT_CREATED", "RECONSTRUCTED"):
                run_id = generate_snapshot_for_schedule(sched["id"], source="RECONSTRUCTED")
                if run_id:
                    existing_known.add(prev_draw)
                    created += 1
                    logger.info(f"[Backfill] {lottery_type} draw {draw} → run_id={run_id}")
        except Exception as e:
            logger.warning(f"[Backfill] {lottery_type} draw {draw} failed: {e}")

    return {"checked": len(recent_sorted), "created": created}


def _startup_check_game(lottery_type: str) -> Dict:
    latest = _get_latest_draw(lottery_type)
    if not latest:
        return {"status": "no_data", "message": "DB 中無此彩種資料"}

    latest_draw = latest["draw"]
    next_draw = _next_draw(latest_draw)

    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()

        # ── Step 1: 標記所有 SCHEDULED 但目標期已入庫的條目為 MISSED_WINDOW
        cur.execute("""
            SELECT id, target_draw FROM snapshot_schedule
            WHERE lottery_type = ? AND status = 'SCHEDULED'
        """, (lottery_type,))
        scheduled_rows = cur.fetchall()
    finally:
        conn.close()

    missed = []
    for row in scheduled_rows:
        if _draw_in_db(lottery_type, row["target_draw"]):
            _update_schedule_status(row["id"], "MISSED_WINDOW",
                                    notes="目標期已入庫，無預先快照")
            missed.append(row["target_draw"])
            logger.info(f"[Scheduler] {lottery_type} draw {row['target_draw']} → MISSED_WINDOW")

    # ── Step 2: 確保下一期有 SCHEDULED 條目
    existing = _get_schedule(lottery_type, next_draw)
    if not existing:
        _create_schedule(lottery_type, next_draw,
                         notes=f"startup_check, latest_known={latest_draw}")
        existing = _get_schedule(lottery_type, next_draw)

    # ── Step 3: 若 SCHEDULED 且目標期尚未入庫 → 產生 VALID 快照
    action = "already_handled"
    run_id = None
    if existing["status"] == "SCHEDULED":
        if not _draw_in_db(lottery_type, next_draw):
            try:
                run_id = generate_snapshot_for_schedule(existing["id"], source="VALID")
                action = "snapshot_created" if run_id else "snapshot_already_exists"
            except Exception as e:
                logger.error(f"[Scheduler] generate snapshot failed for {lottery_type}: {e}")
                action = f"snapshot_error: {e}"
        else:
            _update_schedule_status(existing["id"], "MISSED_WINDOW",
                                    notes="startup_check: 目標期已入庫")
            action = "missed_window"

    return {
        "latest_draw": latest_draw,
        "next_draw": next_draw,
        "missed_draws": missed,
        "action": action,
        "run_id": run_id,
        "schedule_id": existing["id"] if existing else None,
    }


# ──────────────────────────────────────────────
# 排程狀態查詢
# ──────────────────────────────────────────────

def _compute_next_draw_date(lottery_type: str, latest_date_str: Optional[str]) -> Optional[str]:
    """根據彩種開獎週期計算下一期預計日期。
    大樂透/威力彩：週一、週四；今彩539：週一~週五。
    """
    if not latest_date_str:
        return None
    try:
        # 支援 YYYY/MM/DD 或 YYYY-MM-DD
        date_str = latest_date_str.replace("/", "-")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    if lottery_type == "DAILY_539":
        draw_weekdays = {0, 1, 2, 3, 4}   # 週一~週五
    else:
        draw_weekdays = {0, 3}             # 週一(0)、週四(3)

    next_dt = dt + timedelta(days=1)
    for _ in range(7):
        if next_dt.weekday() in draw_weekdays:
            return next_dt.strftime("%Y/%m/%d")
        next_dt += timedelta(days=1)
    return None


def get_schedule_status() -> List[Dict]:
    """回傳各彩種最新排程狀態（供 UI 顯示）"""
    result = []
    for game in ALL_GAMES:
        latest = _get_latest_draw(game)
        if not latest:
            result.append({"lottery_type": game, "status": "no_data"})
            continue

        next_draw = _next_draw(latest["draw"])
        sched = _get_schedule(game, next_draw)
        latest_date = latest.get("date")
        next_date = (sched or {}).get("target_date") or _compute_next_draw_date(game, latest_date)

        result.append({
            "lottery_type": game,
            "latest_known_draw": latest["draw"],
            "latest_known_date": latest_date,
            "next_expected_draw": next_draw,
            "next_expected_date": next_date,
            "schedule": sched,
        })
    return result


def get_schedule_history(lottery_type: Optional[str] = None,
                         limit: int = 30) -> List[Dict]:
    """回傳歷史排程清單（最新在前）"""
    db = _db()
    conn = db._get_connection()
    try:
        cur = conn.cursor()
        if lottery_type:
            cur.execute("""
                SELECT * FROM snapshot_schedule
                WHERE lottery_type = ?
                ORDER BY CAST(target_draw AS INTEGER) DESC
                LIMIT ?
            """, (lottery_type, limit))
        else:
            cur.execute("""
                SELECT * FROM snapshot_schedule
                ORDER BY CAST(target_draw AS INTEGER) DESC, lottery_type
                LIMIT ?
            """, (limit,))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# 在 ingest 後呼叫：確保下一期排程存在
def ensure_next_schedule(lottery_type: str, ingested_draw: str):
    """
    新開獎入庫後呼叫：
    1. 將此期的 SCHEDULED 排程（若存在）標為 MISSED_WINDOW（已來不及預測）
    2. 建立下一期的 SCHEDULED 條目
    """
    # 標記本期為 MISSED_WINDOW（若有 SCHEDULED 條目）
    existing = _get_schedule(lottery_type, ingested_draw)
    if existing and existing["status"] == "SCHEDULED":
        _update_schedule_status(existing["id"], "MISSED_WINDOW",
                                notes=f"draw {ingested_draw} ingested without prior snapshot")
        logger.info(f"[Scheduler] {lottery_type} draw {ingested_draw} SCHEDULED → MISSED_WINDOW")

    # 建立下一期排程
    next_draw = _next_draw(ingested_draw)
    if not _get_schedule(lottery_type, next_draw):
        _create_schedule(lottery_type, next_draw,
                         notes=f"auto-created after ingestion of {ingested_draw}")
        logger.info(f"[Scheduler] {lottery_type} created schedule for draw {next_draw}")
