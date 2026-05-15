"""
Phase U — Strategy Promotion API Routes
"""
import logging
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/strategy/promotion-status")
async def promotion_status(lottery: Optional[str] = Query(None)):
    """Read-only: current promotion state (no evaluation triggered)."""
    try:
        from engine.promotion_engine import get_promotion_status, ENABLED
        data = get_promotion_status(lottery.upper() if lottery else None)
        return {"ok": True, "enabled": ENABLED, "status": data}
    except Exception as e:
        logger.error(f"[PromotionRoute] Error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/api/strategy/promotion-evaluate")
async def promotion_evaluate(lottery: Optional[str] = Query(None)):
    """Run one promotion evaluation cycle. Call after validation refresh."""
    try:
        from engine.promotion_engine import evaluate_lottery, evaluate_all, ENABLED
        if not ENABLED:
            return {"ok": False, "enabled": False,
                    "message": "Phase U disabled (set PHASE_U_ENABLED=true)"}
        if lottery:
            result = {lottery.upper(): evaluate_lottery(lottery.upper())}
        else:
            result = evaluate_all()
        return {"ok": True, "enabled": True, "results": result}
    except Exception as e:
        logger.error(f"[PromotionRoute] Evaluate error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@router.post("/api/strategy/promotion-confirm")
async def promotion_confirm(lottery: str = Query(...), strategy: str = Query(...)):
    """Manually confirm a PRODUCTION_CANDIDATE promotion."""
    try:
        from engine.promotion_engine import confirm_promotion
        result = confirm_promotion(lottery.upper(), strategy)
        return result
    except Exception as e:
        logger.error(f"[PromotionRoute] Confirm error: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}
