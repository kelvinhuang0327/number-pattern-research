"""
Research Review API Routes
===========================
POST /api/reviews/create             — 建立檢討會議
GET  /api/reviews/history            — 查詢檢討會議清單
GET  /api/reviews/:id                — 取得完整會議詳情
GET  /api/reviews/actions            — 查詢行動項目
POST /api/reviews/:id/mark-resolved  — 標記會議已解決
POST /api/reviews/:id/reopen         — 重新開啟會議
POST /api/reviews/:id/create-shadow  — 從假說建立影子實驗
GET  /api/reviews/prediction-status  — 查詢預測檢討狀態
GET  /api/reviews/dashboard          — 檢討儀表板摘要
PUT  /api/reviews/:id                — 更新會議內容
PUT  /api/reviews/actions/:id/status — 更新行動狀態
PUT  /api/reviews/hypotheses/:id/status — 更新假說狀態
GET  /api/reviews/:id/export/json    — 匯出 JSON
GET  /api/reviews/:id/export/markdown — 匯出 Markdown
GET  /api/reviews/shadow-experiments — 查詢影子實驗
GET  /api/reviews/shadow-experiments/:id — 取得影子實驗詳情
PUT  /api/reviews/shadow-experiments/:id — 更新影子實驗
GET  /api/reviews/shadow-experiments/:id/comparison — 影子 vs production 比較
"""

import logging
import os
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])
logger = logging.getLogger(__name__)


# ============================================================
# Request / Response Models
# ============================================================

class ReviewFindingInput(BaseModel):
    section_type: str = "other"
    title: Optional[str] = None
    content: Optional[str] = None
    evidence_type: str = "UNSURE"
    sort_order: int = 0

class ReviewHypothesisInput(BaseModel):
    hypothesis_type: str = "other"
    description: Optional[str] = None
    expected_impact: Optional[str] = None
    validation_method: Optional[str] = None
    kill_condition: Optional[str] = None
    status: str = "PENDING"

class ReviewActionInput(BaseModel):
    priority: str = "P2"
    action_title: Optional[str] = None
    action_description: Optional[str] = None
    expected_gain: Optional[str] = None
    cost_level: Optional[str] = None
    risk_level: Optional[str] = None
    validation_method: Optional[str] = None
    stop_condition: Optional[str] = None
    status: str = "OPEN"

class CreateReviewRequest(BaseModel):
    game: str
    draw: Optional[str] = None
    draw_date: Optional[str] = None
    session_type: str = "daily_review"
    summary: Optional[str] = None
    final_decision: str = "NO_ACTION"
    confidence_level: str = "LOW"
    raw_report_text: Optional[str] = None
    findings: List[ReviewFindingInput] = []
    hypotheses: List[ReviewHypothesisInput] = []
    actions: List[ReviewActionInput] = []
    prediction_run_ids: List[int] = []

class UpdateReviewRequest(BaseModel):
    summary: Optional[str] = None
    final_decision: Optional[str] = None
    confidence_level: Optional[str] = None
    raw_report_text: Optional[str] = None
    status: Optional[str] = None

class CreateShadowRequest(BaseModel):
    hypothesis_id: Optional[int] = None
    experiment_name: str
    base_strategy: Optional[str] = None
    experiment_strategy: Optional[str] = None
    experiment_config_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    prediction_run_ids: List[int] = []

class UpdateShadowRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    experiment_config_json: Optional[Dict[str, Any]] = None
    experiment_strategy: Optional[str] = None
    experiment_name: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str


# ============================================================
# ROUTES
# ============================================================

@router.post("/create")
async def create_review(request: CreateReviewRequest):
    """建立檢討會議"""
    from engine.review_service import create_review_session
    try:
        payload = request.dict()
        # Convert Pydantic models to dicts
        payload["findings"] = [f.dict() for f in request.findings]
        payload["hypotheses"] = [h.dict() for h in request.hypotheses]
        payload["actions"] = [a.dict() for a in request.actions]
        result = create_review_session(payload)
        return result
    except Exception as e:
        logger.error(f"Failed to create review: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def list_reviews(
    game: Optional[str] = Query(None),
    draw: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查詢檢討會議清單"""
    from engine.review_service import list_review_sessions
    return list_review_sessions(
        game=game, draw=draw, status=status,
        session_type=session_type, limit=limit, offset=offset,
    )


@router.get("/actions")
async def get_actions(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    game: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """查詢行動項目"""
    from engine.review_service import list_actions
    return {"actions": list_actions(status=status, priority=priority, game=game, limit=limit)}


@router.get("/prediction-status")
async def get_prediction_status(
    prediction_run_id: Optional[int] = Query(None),
    review_status: Optional[str] = Query(None),
    game: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查詢預測的檢討狀態"""
    from engine.review_service import get_prediction_review_status
    return get_prediction_review_status(
        prediction_run_id=prediction_run_id,
        review_status=review_status,
        game=game, limit=limit, offset=offset,
    )


@router.get("/dashboard")
async def get_dashboard(game: Optional[str] = Query(None)):
    """檢討儀表板摘要"""
    from engine.review_service import get_review_dashboard
    return get_review_dashboard(game=game)


@router.get("/shadow-experiments")
async def list_shadows(
    game: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查詢影子實驗列表"""
    from engine.shadow_service import list_shadow_experiments
    return list_shadow_experiments(
        game=game, status=status, session_id=session_id,
        limit=limit, offset=offset,
    )


@router.get("/shadow-experiments/{experiment_id}")
async def get_shadow(experiment_id: int):
    """取得影子實驗詳情"""
    from engine.shadow_service import get_shadow_experiment
    exp = get_shadow_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Shadow experiment not found")
    return exp


@router.put("/shadow-experiments/{experiment_id}")
async def update_shadow(experiment_id: int, request: UpdateShadowRequest):
    """更新影子實驗"""
    from engine.shadow_service import update_shadow_experiment
    updates = {k: v for k, v in request.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = update_shadow_experiment(experiment_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Shadow experiment not found or no changes")
    return {"status": "updated"}


@router.get("/shadow-experiments/{experiment_id}/comparison")
async def shadow_comparison(experiment_id: int):
    """影子實驗 vs production 比較"""
    from engine.shadow_service import get_shadow_vs_production_comparison
    return get_shadow_vs_production_comparison(experiment_id)


@router.get("/{session_id}")
async def get_review(session_id: int):
    """取得完整會議詳情"""
    from engine.review_service import get_review_session
    session = get_review_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")
    return session


@router.put("/{session_id}")
async def update_review(session_id: int, request: UpdateReviewRequest):
    """更新會議內容"""
    from engine.review_service import update_review_session
    updates = {k: v for k, v in request.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = update_review_session(session_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found or no changes")
    return {"status": "updated"}


@router.post("/{session_id}/mark-resolved")
async def mark_resolved(session_id: int):
    """標記會議已解決"""
    from engine.review_service import mark_session_resolved
    ok = mark_session_resolved(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "resolved"}


@router.post("/{session_id}/reopen")
async def reopen(session_id: int):
    """重新開啟會議"""
    from engine.review_service import reopen_session
    ok = reopen_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "reopened"}


@router.post("/{session_id}/create-shadow")
async def create_shadow_from_review(session_id: int, request: CreateShadowRequest):
    """從檢討假說建立影子實驗"""
    from engine.review_service import get_review_session
    from engine.shadow_service import create_shadow_experiment

    session = get_review_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")

    payload = request.dict()
    payload["session_id"] = session_id
    payload["game"] = session["game"]
    result = create_shadow_experiment(payload)
    return result


@router.put("/actions/{action_id}/status")
async def update_action(action_id: int, request: StatusUpdateRequest):
    """更新行動狀態"""
    from engine.review_service import update_action_status
    ok = update_action_status(action_id, request.status)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid status or action not found")
    return {"status": "updated"}


@router.put("/hypotheses/{hypothesis_id}/status")
async def update_hypothesis(hypothesis_id: int, request: StatusUpdateRequest):
    """更新假說狀態"""
    from engine.review_service import update_hypothesis_status
    ok = update_hypothesis_status(hypothesis_id, request.status)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid status or hypothesis not found")
    return {"status": "updated"}


@router.get("/{session_id}/export/json")
async def export_json(session_id: int):
    """匯出完整 session 為 JSON"""
    from engine.review_service import export_session_json
    result = export_session_json(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/{session_id}/export/markdown")
async def export_markdown(session_id: int):
    """匯出 session 為 Markdown"""
    from engine.review_service import export_session_markdown
    result = export_session_markdown(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return PlainTextResponse(content=result, media_type="text/markdown")
