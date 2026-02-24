print(">>> [START] app.py loading...")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Import Routers
from routes import prediction, data, optimization, admin, backtest

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
@app.on_event("startup")
async def startup_event():
    """Application Startup Logic"""
    logger.info(">>> Application starting up...")
    try:
        # Load Data
        scheduler.load_data()
        logger.info(">>> Scheduler data loaded.")
    except Exception as e:
        logger.error(f"Error during startup: {e}")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
