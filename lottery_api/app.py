print(">>> [START] app.py loading...")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Import Routers
from routes import prediction, data, optimization, admin, backtest, ingest, prediction_tracking, decision, reviews, research, explainability, actionable, confidence, promotion

# Import System Utilities
from utils.scheduler import scheduler

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="Lottery AI Prediction API",
    description="基於深度學習的彩票預測系統 API",
    version="2.0.0"
)

# Configure CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*"  # 開發環境允許所有來源
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Event
def _run_research_job():
    """Sync wrapper for the APScheduler cron job."""
    try:
        from engine.research_runner import run_research_cycle
        result = run_research_cycle(n_perm=50, verbose=False)
        logger.info(f"[ResearchJob] Cycle done: {result.get('summary', {})}")
    except Exception as e:
        logger.error(f"[ResearchJob] Failed: {e}")

@app.on_event("startup")
async def startup_event():
    """Application Startup Logic"""
    logger.info(">>> Application starting up...")
    try:
        scheduler.load_data()
        logger.info(">>> Scheduler data loaded.")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
    try:
        from engine.snapshot_scheduler import startup_check
        summary = startup_check()
        logger.info(f">>> Snapshot startup_check: {summary}")
    except Exception as e:
        logger.warning(f">>> snapshot_scheduler startup_check failed (non-fatal): {e}")

    # ── Research Runner: schedule daily auto-research at 04:00 ──
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        research_scheduler = AsyncIOScheduler()
        research_scheduler.add_job(
            _run_research_job,
            trigger=CronTrigger(hour=4, minute=0),
            id='daily_research',
            name='Daily Auto-Research Cycle',
            replace_existing=True,
        )
        research_scheduler.start()
        logger.info(">>> Research scheduler started (daily at 04:00)")
    except Exception as e:
        logger.warning(f">>> Research scheduler setup failed (non-fatal): {e}")

# Register Routers
# admin: / and /health and /api/ping (no common prefix)
app.include_router(admin.router, tags=["System"])

# prediction: /api/predict (routes already have /api prefix)
app.include_router(prediction.router, tags=["Prediction"])

# data: /api/history (routes already have /api prefix)
app.include_router(data.router, tags=["Data"])

# optimization: /api/auto-learning/* (routes already have /api prefix)
app.include_router(optimization.router, tags=["Optimization"])

# backtest: /api/backtest/* (routes already have /api prefix)
app.include_router(backtest.router, tags=["Backtest"])

# ingest: /api/ingest/* — automated fetch, scan, backfill
app.include_router(ingest.router, tags=["Ingest"])

# tracking: /api/tracking/* — prediction snapshot & result tracking
app.include_router(prediction_tracking.router, tags=["Tracking"])

# decision: /api/decision/* — Decision Layer V3 per-draw recommendations
app.include_router(decision.router, tags=["Decision"])

# reviews: /api/reviews/* — Research Review System
app.include_router(reviews.router, tags=["Reviews"])

# research: /api/research/* — Autonomous Research Runner
app.include_router(research.router, tags=["Research"])

# explainability: /api/explainability/* — Phase P Decision Trace
app.include_router(explainability.router, tags=["Explainability"])

# actionable: /api/actionable/* — Phase Q Actionable Intelligence
app.include_router(actionable.router, tags=["Actionable"])

# confidence: /api/confidence/* — Phase T Statistical Confidence Layer
app.include_router(confidence.router, tags=["Confidence"])

# promotion: /api/strategy/promotion-* — Phase U Strategy Promotion Engine
app.include_router(promotion.router, tags=["Promotion"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
