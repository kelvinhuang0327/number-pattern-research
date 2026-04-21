"""
Confidence API Routes — Phase T
"""
import logging
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/confidence/summary")
async def confidence_summary(lottery: Optional[str] = Query(None)):
    """
    Phase T: statistical confidence table.

    Returns, per lottery:
      - adjusted_mcnemar_p (Holm–Bonferroni, per-lottery family)
      - confidence_score (0..1, weighted: 0.35 significance + 0.25 perm +
        0.20 stability + 0.20 sample-size)
      - confidence_tier  (HIGH / MEDIUM / LOW / UNRELIABLE)
      - promotable flag  (WATCH && tier>=MEDIUM && adj_mc < 0.08)
    """
    try:
        from engine.confidence_scorer import (
            get_lottery_confidence, get_all_confidence,
            ENABLED, TIER_HIGH, TIER_MED, TIER_LOW,
            PROMOTABLE_ADJ_MCNEMAR,
        )
        if lottery:
            data = {lottery.upper(): get_lottery_confidence(lottery.upper())}
        else:
            data = get_all_confidence()

        # Flatten promotable list
        promotable = []
        for lt, table in data.items():
            for s in table.values():
                if s.get('promotable'):
                    promotable.append({'lottery': lt, **s})

        return {
            "ok": True,
            "enabled": ENABLED,
            "thresholds": {
                "tier_high":            TIER_HIGH,
                "tier_medium":          TIER_MED,
                "tier_low":             TIER_LOW,
                "promotable_adj_mc":    PROMOTABLE_ADJ_MCNEMAR,
            },
            "confidence": data,
            "promotable": promotable,
        }
    except Exception as e:
        logger.error(f"[ConfidenceRoute] Error: {e}", exc_info=True)
        return {"ok": False, "error": str(e), "confidence": {}}
