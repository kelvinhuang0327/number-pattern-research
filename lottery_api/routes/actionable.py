"""
Actionable Intelligence API Routes — Phase Q / Phase R

GET /api/actionable/summary   — per-lottery actionable summary (insights + actions + health)
GET /api/actionable/feedback  — action effectiveness summary + rule performance (Phase R)
GET /api/actionable/actions   — list of tracked actions (Phase R)
GET /api/actionable/rules     — rule ranking by effectiveness (Phase R)
"""
import logging
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/actionable/summary")
async def get_actionable_summary():
    """
    Actionable Intelligence summary for all 3 lottery types.

    Returns per-lottery:
    - health: GOOD | WATCH | RISK
    - insights: rule-based observations traceable to real data
    - top_actions: top 3 recommended actions with priority, reason, risk
    - key_observations: short human-readable summaries for UI

    Side-effect: registers any NEW insights as tracked actions (Phase R).
    """
    try:
        from engine.actionable_intelligence import get_actionable_summary as _get_summary
        from engine.action_feedback import register_actions_from_summary

        summary = _get_summary()

        # Phase R: register new actions from insights (deduped by draw bucket)
        try:
            registered = register_actions_from_summary(summary)
            logger.debug(f'[ActionableRoute] Registered {registered} new action(s) for tracking')
        except Exception as reg_err:
            logger.warning(f'[ActionableRoute] Action registration failed (non-fatal): {reg_err}')

        return {
            "ok": True,
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"[ActionableRoute] Error: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "summary": {},
        }


@router.get("/api/actionable/feedback")
async def get_action_feedback():
    """
    Phase R: Action Feedback & Outcome Tracking summary.

    Returns:
    - totals: open / tracking / completed action counts
    - effectiveness: overall effective %, negative %, summary label
    - rule_stats: per-rule performance (effectiveness_rate, rule_score, recommendation)
    - meta_insights: top/worst rules + KEEP/TUNE/REMOVE lists
    - recent_completed: last 5 completed actions with outcomes
    """
    try:
        from engine.action_feedback import get_feedback_summary
        return {
            "ok": True,
            "feedback": get_feedback_summary(),
        }
    except Exception as e:
        logger.error(f"[ActionableRoute/feedback] Error: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "feedback": {},
        }


@router.get("/api/actionable/actions")
async def list_tracked_actions(
    status: Optional[str] = Query(None, description="Filter by status: OPEN | TRACKING | COMPLETED"),
    lottery: Optional[str] = Query(None, description="Filter by lottery type"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Phase R: List all tracked actions with optional filters.

    Query params:
    - status:  OPEN | TRACKING | COMPLETED
    - lottery: DAILY_539 | BIG_LOTTO | POWER_LOTTO
    - limit:   max results (default 100, max 500)
    """
    try:
        from engine.action_feedback import get_all_actions
        actions = get_all_actions(
            status_filter=status,
            lottery_filter=lottery,
            limit=limit,
        )
        return {
            "ok": True,
            "count": len(actions),
            "actions": actions,
        }
    except Exception as e:
        logger.error(f"[ActionableRoute/actions] Error: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "actions": [],
        }


@router.get("/api/actionable/rules")
async def get_rule_rankings():
    """
    Phase R: Rule performance ranking sorted by rule_score (descending).

    Each rule entry includes:
    - total, effective_count, neutral_count, negative_count
    - effectiveness_rate, rule_score
    - avg_edge_delta, avg_sharpe_delta, avg_drawdown_delta
    - recommendation: KEEP | TUNE | REMOVE | INSUFFICIENT_DATA
    """
    try:
        from engine.action_feedback import get_rule_rankings
        ranked = get_rule_rankings()
        return {
            "ok": True,
            "count": len(ranked),
            "rules": ranked,
        }
    except Exception as e:
        logger.error(f"[ActionableRoute/rules] Error: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "rules": [],
        }


@router.get("/api/actionable/rule-weights")
async def get_rule_weight_snapshot():
    """
    Phase S: Rule weight map — feedback-to-decision closed loop.

    Shows how historical action effectiveness (Phase R) currently affects
    Phase Q rule prioritization. This endpoint is read-only and surfaces the
    audit trail for explainability.

    Returns:
    - gating_enabled:        master feature flag state
    - hard_disable_enabled:  whether severely negative rules are fully muted
    - thresholds:            score cutoffs and sample threshold
    - weights:               per-rule weight map with status + reason
    - summary:               aggregated lists (boosted / downgraded / disabled / neutral)
    """
    try:
        from engine.rule_weight_manager import (
            get_rule_weight_map,
            summarize_weight_map,
            GATING_ENABLED,
            HARD_DISABLE_ENABLED,
            SAMPLE_THRESHOLD,
            SCORE_DOWNGRADE_CUTOFF,
            SCORE_BOOST_CUTOFF,
            SCORE_HARD_DISABLE,
        )
        wmap = get_rule_weight_map(persist=True)
        return {
            "ok": True,
            "gating_enabled":       GATING_ENABLED,
            "hard_disable_enabled": HARD_DISABLE_ENABLED,
            "thresholds": {
                "sample_threshold":     SAMPLE_THRESHOLD,
                "downgrade_cutoff":     SCORE_DOWNGRADE_CUTOFF,
                "boost_cutoff":         SCORE_BOOST_CUTOFF,
                "hard_disable_cutoff":  SCORE_HARD_DISABLE,
            },
            "weights": wmap,
            "summary": summarize_weight_map(wmap),
        }
    except Exception as e:
        logger.error(f"[ActionableRoute/rule-weights] Error: {e}", exc_info=True)
        return {
            "ok": False,
            "error": str(e),
            "weights": {},
        }
