"""
Research Runner API — 研究執行引擎 API
======================================
Endpoints for monitoring and triggering the autonomous research loop.

  GET  /api/research/status       — current research system status
  POST /api/research/run          — trigger a research cycle manually
  GET  /api/research/history      — recent run history
  POST /api/research/discover     — trigger discovery-only (no validation)
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class RunRequest(BaseModel):
    lottery_types: Optional[List[str]] = None
    max_per_type: int = Field(default=5, ge=1, le=20)
    n_perm: int = Field(default=50, ge=10, le=500)
    discover: bool = True
    n_discover_mutations: int = Field(default=5, ge=1, le=20)
    verbose: bool = False


class DiscoverRequest(BaseModel):
    lottery_type: str = "DAILY_539"
    n_mutations: int = Field(default=5, ge=1, le=20)


@router.get("/api/research/status")
async def research_status():
    """Current status of the research system."""
    try:
        from engine.research_runner import get_status
        return get_status()
    except Exception as e:
        logger.error(f"research_status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/research/run")
async def research_run(req: RunRequest):
    """
    Trigger a full research cycle.
    Discovery + Validation of pending hypotheses.
    """
    try:
        from engine.research_runner import run_research_cycle
        result = run_research_cycle(
            lottery_types=req.lottery_types,
            max_per_type=req.max_per_type,
            n_perm=req.n_perm,
            discover=req.discover,
            n_discover_mutations=req.n_discover_mutations,
            verbose=req.verbose,
        )
        return result
    except Exception as e:
        logger.error(f"research_run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/research/history")
async def research_history(limit: int = 20):
    """Recent research run history."""
    try:
        from engine.research_runner import get_run_history
        return {"runs": get_run_history(limit=limit)}
    except Exception as e:
        logger.error(f"research_history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/research/discover")
async def research_discover(req: DiscoverRequest):
    """
    Discovery-only: generate and register new candidate hypotheses
    without running validation.
    """
    try:
        from engine.research_runner import discover_candidates
        candidates = discover_candidates(
            lottery_type=req.lottery_type,
            n_mutations=req.n_mutations,
        )
        return {
            "lottery_type": req.lottery_type,
            "registered": len(candidates),
            "hypotheses": candidates,
        }
    except Exception as e:
        logger.error(f"research_discover error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
