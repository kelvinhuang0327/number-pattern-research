"""
Prediction Tracking API Routes

GET  /api/tracking/history       — 歷史預測清單
GET  /api/tracking/performance   — 策略表現聚合
GET  /api/tracking/run/{run_id}  — 單一 run 詳情
POST /api/tracking/snapshot      — 手動觸發預測並儲存快照
POST /api/tracking/resolve       — 解析 PENDING 預測
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


@router.post("/api/tracking/snapshot")
async def create_snapshot(req: SnapshotRequest):
    """
    觸發預測並立即儲存快照到 DB。
    使用 coordinator_predict（RSM 最佳策略）。
    """
    try:
        from engine.prediction_tracker import create_snapshot as _create_snapshot
        from database import db_manager

        # 取得最新已知開獎
        all_draws = db_manager.get_all_draws(req.lottery_type)
        if not all_draws:
            raise HTTPException(status_code=400, detail="DB 中無此彩種開獎資料")

        latest = all_draws[0]
        latest_draw = latest["draw"]
        latest_date = latest.get("date")

        # 執行預測（使用 coordinator）
        try:
            from engine.strategy_coordinator import coordinator_predict
            bets, strategy_label = coordinator_predict(
                req.lottery_type,
                all_draws,
                n_bets=req.num_bets,
                mode="direct",
            )
        except Exception as e:
            logger.warning(f"coordinator_predict failed, falling back: {e}")
            # fallback：使用基礎頻率預測
            from models.unified_predictor import UnifiedPredictionEngine
            engine = UnifiedPredictionEngine()
            result = engine.frequency_predict(all_draws, {})
            bets = [result.get("numbers", [])]
            strategy_label = "frequency_fallback"

        # 特別號（威力彩）
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
            notes=req.notes,
        )

        return {
            "success": True,
            "run_id": run_id,
            "lottery_type": req.lottery_type,
            "strategy_name": strategy_label,
            "latest_known_draw": latest_draw,
            "bets": bets,
            "special": special,
            "message": f"快照已儲存 (run_id={run_id}，目標：{latest_draw} 之後的開獎)",
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
    """歷史預測清單，newest first。"""
    try:
        from engine.prediction_tracker import get_history as _get_history
        return _get_history(lottery_type=lottery_type, status=status, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"get_history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/performance")
async def get_performance(lottery_type: Optional[str] = Query(None)):
    """策略命中率聚合。"""
    try:
        from engine.prediction_tracker import get_performance as _get_perf
        return {"performance": _get_perf(lottery_type=lottery_type)}
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
