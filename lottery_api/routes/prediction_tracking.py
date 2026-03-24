"""
Prediction Tracking API Routes

POST /api/tracking/snapshot         — 手動觸發預測並儲存快照
POST /api/tracking/resolve          — 解析 PENDING 預測
GET  /api/tracking/history          — 歷史預測清單
GET  /api/tracking/performance      — 策略表現聚合
GET  /api/tracking/run/{run_id}     — 單一 run 詳情
POST /api/tracking/schedule/startup — 觸發啟動補全邏輯
GET  /api/tracking/schedule/status  — 各彩種排程狀態
GET  /api/tracking/schedule/history — 歷史排程清單
POST /api/tracking/schedule/generate/{schedule_id} — 為指定排程產生快照（重建）
"""

import logging
import os
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter()
logger = logging.getLogger(__name__)


class SnapshotRequest(BaseModel):
    lottery_type: str = "BIG_LOTTO"
    num_bets: int = Field(default=3, ge=1, le=7)
    notes: Optional[str] = None


# ──────────────────────────────────────────────
# 快照端點
# ──────────────────────────────────────────────

@router.post("/api/tracking/snapshot")
async def create_snapshot(req: SnapshotRequest):
    """
    觸發預測並立即儲存快照到 DB。
    自動判斷 snapshot_source：
      - 若目標期（latest+1）尚未入庫 → VALID
      - 若目標期已入庫                → RECONSTRUCTED（並附加警告）
    """
    try:
        from engine.prediction_tracker import create_snapshot as _create_snapshot
        from database import db_manager

        all_draws = db_manager.get_all_draws(req.lottery_type)
        if not all_draws:
            raise HTTPException(status_code=400, detail="DB 中無此彩種開獎資料")

        latest = all_draws[0]
        latest_draw = latest["draw"]
        latest_date = latest.get("date")

        # 判斷 snapshot_source
        target_draw = str(int(latest_draw) + 1)
        target_exists = db_manager.get_draw(req.lottery_type, target_draw) is not None
        snapshot_source = "RECONSTRUCTED" if target_exists else "VALID"

        # 執行預測
        try:
            from engine.strategy_coordinator import coordinator_predict
            bets, strategy_label = coordinator_predict(
                req.lottery_type, all_draws, n_bets=req.num_bets, mode="direct"
            )
        except Exception as e:
            logger.warning(f"coordinator_predict failed, fallback: {e}")
            from models.unified_predictor import UnifiedPredictionEngine
            engine = UnifiedPredictionEngine()
            result = engine.frequency_predict(all_draws, {})
            bets = [result.get("numbers", [])]
            strategy_label = "frequency_fallback"

        special = None
        if req.lottery_type == "POWER_LOTTO":
            try:
                from routes.prediction import get_enhanced_special_prediction
                sp_result = get_enhanced_special_prediction(all_draws, {}, bets[0] if bets else [])
                special = sp_result.get("special")
            except Exception:
                pass

        run_id = _create_snapshot(
            lottery_type=req.lottery_type,
            bets=bets,
            strategy_name=strategy_label,
            latest_known_draw=latest_draw,
            latest_known_date=latest_date,
            special=special,
            snapshot_source=snapshot_source,
            notes=req.notes or "",
        )

        warning = None
        if snapshot_source == "RECONSTRUCTED":
            warning = f"⚠️ 目標期 {target_draw} 已入庫，此快照標記為 RECONSTRUCTED，不計入正式績效"

        return {
            "success": True,
            "run_id": run_id,
            "lottery_type": req.lottery_type,
            "strategy_name": strategy_label,
            "latest_known_draw": latest_draw,
            "target_draw": target_draw,
            "snapshot_source": snapshot_source,
            "bets": bets,
            "special": special,
            "warning": warning,
            "message": f"快照已儲存 (run_id={run_id}, source={snapshot_source})",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_snapshot error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tracking/resolve")
async def resolve_pending(dry_run: bool = Query(False)):
    """解析所有 PENDING 預測，比對實際開獎結果。"""
    try:
        from engine.prediction_tracker import resolve_pending as _resolve
        summary = _resolve(dry_run=dry_run)
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"resolve_pending error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/history")
async def get_history(
    lottery_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """歷史預測清單，newest first，含 snapshot_source。"""
    try:
        from engine.prediction_tracker import get_history as _get_history
        return _get_history(lottery_type=lottery_type, status=status, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"get_history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/performance")
async def get_performance(
    lottery_type: Optional[str] = Query(None),
    valid_only: bool = Query(True, description="True=只計 VALID 快照（正式績效）"),
):
    """
    策略命中率聚合。
    valid_only=True（預設）：只計入開獎前產生的 VALID 快照。
    """
    try:
        from engine.prediction_tracker import get_performance as _get_perf
        return {
            "performance": _get_perf(lottery_type=lottery_type, valid_only=valid_only),
            "filter": "VALID_ONLY" if valid_only else "ALL_INCLUDING_RECONSTRUCTED",
        }
    except Exception as e:
        logger.error(f"get_performance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/run/{run_id}")
async def get_run_detail(run_id: int):
    """單一 run 的完整比對資料。"""
    try:
        from engine.prediction_tracker import get_run_detail as _get_detail
        detail = _get_detail(run_id)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_run_detail error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# 排程端點
# ──────────────────────────────────────────────

@router.post("/api/tracking/schedule/startup")
async def run_startup_check():
    """觸發啟動補全邏輯：補 MISSED_WINDOW、補 SCHEDULED、自動產生 VALID 快照。"""
    try:
        from engine.snapshot_scheduler import startup_check
        summary = startup_check()
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"startup_check error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/schedule/status")
async def get_schedule_status():
    """各彩種目前排程狀態（下一期是否已有快照）。"""
    try:
        from engine.snapshot_scheduler import get_schedule_status
        return {"schedules": get_schedule_status()}
    except Exception as e:
        logger.error(f"get_schedule_status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/schedule/history")
async def get_schedule_history(
    lottery_type: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
):
    """歷史排程清單（最新在前）。"""
    try:
        from engine.snapshot_scheduler import get_schedule_history
        return {"schedules": get_schedule_history(lottery_type=lottery_type, limit=limit)}
    except Exception as e:
        logger.error(f"get_schedule_history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/tracking/result/{item_id}/researched")
async def set_researched(item_id: int, value: str = Query("有", description="有 or 無")):
    """標記/取消標記某一注預測結果為「已研究特徵」。"""
    if value not in ("有", "無"):
        raise HTTPException(status_code=400, detail="value 必須為 有 或 無")
    try:
        from database import db_manager
        conn = db_manager._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE prediction_results SET researched = ? WHERE item_id = ?",
                (value, item_id)
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"item_id {item_id} 無對應比對結果")
            conn.commit()
            return {"success": True, "item_id": item_id, "researched": value}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"set_researched error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tracking/schedule/generate/{schedule_id}")
async def generate_from_schedule(
    schedule_id: int,
    source: str = Query("RECONSTRUCTED", description="VALID or RECONSTRUCTED"),
):
    """
    為指定排程產生快照。
    正常情況請用 'RECONSTRUCTED'（補建，不計入正式績效）。
    只有在 startup_check 中才自動用 'VALID'。
    """
    if source not in ("VALID", "RECONSTRUCTED"):
        raise HTTPException(status_code=400, detail="source 必須為 VALID 或 RECONSTRUCTED")
    try:
        from engine.snapshot_scheduler import generate_snapshot_for_schedule
        run_id = generate_snapshot_for_schedule(schedule_id, source=source)
        if run_id is None:
            return {"success": True, "message": "此排程已有快照，不重複建立", "run_id": None}
        return {
            "success": True,
            "run_id": run_id,
            "source": source,
            "message": f"快照已建立 (run_id={run_id}, source={source})",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"generate_from_schedule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
