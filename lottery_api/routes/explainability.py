"""
Explainability API Routes — Phase P

GET /api/explainability/run/{prediction_run_id}  — full explanation for one run
GET /api/explainability/latest                   — latest explanation snapshot
GET /api/explainability/summary                  — aggregated statistics
GET /api/explainability/live                     — compute live explanation (no persistence)
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/explainability/run/{prediction_run_id}")
async def get_explanation_for_run(prediction_run_id: int):
    """Full explanation for a specific prediction run."""
    from engine.explainability import get_explanation_by_run
    result = get_explanation_by_run(prediction_run_id)
    if not result:
        raise HTTPException(status_code=404, detail="No explanation found for this run")
    return result


@router.get("/api/explainability/latest")
async def get_latest_explanation(lottery_type: str = Query(..., description="DAILY_539 | BIG_LOTTO | POWER_LOTTO")):
    """Latest explanation snapshot for a lottery type."""
    from engine.explainability import get_latest_explanation
    result = get_latest_explanation(lottery_type)
    if not result:
        raise HTTPException(status_code=404, detail=f"No explanation found for {lottery_type}")
    return result


@router.get("/api/explainability/summary")
async def get_explanation_summary():
    """Aggregated counts of learning enabled/disabled, ranking changes, etc."""
    from engine.explainability import get_summary
    return get_summary()


@router.get("/api/explainability/live")
async def get_live_explanation(
    lottery_type: str = Query(..., description="DAILY_539 | BIG_LOTTO | POWER_LOTTO"),
    profile: Optional[str] = Query(None, description="conservative | balanced | aggressive"),
):
    """
    Compute a live explanation for the current state (no persistence).
    Runs the coordinator predict pipeline and returns the explanation object.
    """
    try:
        from database import db_manager
        from common import normalize_lottery_type
        from engine.strategy_coordinator import coordinator_predict, get_last_explanation

        lt = normalize_lottery_type(lottery_type)
        all_draws = db_manager.get_all_draws(lt)
        if not all_draws:
            raise HTTPException(status_code=400, detail=f"No draw history for {lt}")

        history = sorted(all_draws, key=lambda x: (x.get('date', ''), x.get('draw', '')))

        # Run prediction to populate explanation
        coordinator_predict(lt, history, n_bets=3, mode='direct', profile=profile)
        explanation = get_last_explanation()

        if not explanation:
            raise HTTPException(status_code=500, detail="Explanation generation failed")

        return {
            'lottery_type': lt,
            'profile': profile or 'auto',
            'explanation': explanation,
            'source': 'live',
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Live explanation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
