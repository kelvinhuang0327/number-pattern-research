"""
Betting-pool FastAPI Application
整合 Orchestrator 與 WBC 預測系統
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
import sys

# 加入 orchestrator 模組到 Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 匯入 orchestrator 模組
from orchestrator import api as orchestrator_api
from orchestrator import db as orchestrator_db
from orchestrator.scheduler import get_scheduler, start_scheduler

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 建立 FastAPI 應用
app = FastAPI(
    title="Betting-pool AI System",
    description="WBC 預測系統整合任務編排與排程管理",
    version="1.0.0"
)

# 設定 CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173", 
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8787",
    "http://127.0.0.1:8788",
    "http://127.0.0.1:8789",
    "*"  # 開發環境允許所有來源
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 應用啟動事件
@app.on_event("startup")
async def startup_event():
    """應用啟動邏輯"""
    logger.info(">>> Betting-pool Application starting up...")
    
    try:
        # 初始化 Orchestrator 資料庫
        orchestrator_db.init_db()
        logger.info(">>> Orchestrator DB initialized")
        
        # 啟動排程器
        start_scheduler()
        logger.info(">>> Orchestrator Scheduler started")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        # 不要讓啟動失敗阻止應用程式運行
        logger.warning("Application will continue despite startup errors")

# 應用關閉事件
@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉邏輯"""
    logger.info(">>> Betting-pool Application shutting down...")
    
    try:
        from orchestrator.scheduler import stop_scheduler
        stop_scheduler()
        logger.info(">>> Orchestrator Scheduler stopped")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# 根路由
@app.get("/")
async def root():
    """根路由 - 應用程式資訊"""
    return {
        "name": "Betting-pool AI System",
        "version": "1.0.0",
        "description": "WBC 預測系統整合任務編排與排程管理",
        "status": "running",
        "endpoints": {
            "orchestrator": "/api/*",
            "health": "/health",
            "docs": "/docs"
        }
    }

# 健康檢查
@app.get("/health")
async def health_check():
    """健康檢查端點"""
    try:
        # 檢查資料庫連線
        from orchestrator.db import get_conn
        conn = get_conn()
        conn.close()
        
        # 檢查排程器狀態
        scheduler = get_scheduler()
        scheduler_status = scheduler.get_status()
        
        return {
            "status": "healthy",
            "timestamp": orchestrator_db.get_setting("updated_at", "unknown"),
            "database": "connected",
            "scheduler": {
                "running": scheduler_status["running"],
                "enabled": scheduler_status["scheduler_enabled"]
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

# 系統資訊
@app.get("/api/system/info")
async def system_info():
    """系統資訊"""
    try:
        scheduler = get_scheduler()
        scheduler_status = scheduler.get_status()
        
        # 取得任務統計
        task_counts = orchestrator_db.count_tasks_by_status()
        
        return {
            "system": {
                "name": "Betting-pool Orchestrator",
                "version": "1.0.0",
                "environment": os.environ.get("ENVIRONMENT", "development")
            },
            "scheduler": scheduler_status,
            "tasks": {
                "counts": task_counts,
                "total": sum(task_counts.values())
            },
            "settings": {
                "planner_provider": orchestrator_db.get_setting("planner_provider", "local"),
                "worker_provider": orchestrator_db.get_setting("worker_provider", "claude"),
                "cto_frequency_mode": orchestrator_db.get_setting("cto_review_frequency_mode", "once_daily")
            }
        }
    except Exception as e:
        logger.error(f"System info error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")

# 手動觸發端點
@app.post("/api/system/trigger/planner")
async def trigger_planner():
    """手動觸發 Planner"""
    try:
        scheduler = get_scheduler()
        result = scheduler.trigger_planner_now()
        return {"triggered": True, "result": result}
    except Exception as e:
        logger.error(f"Manual planner trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger planner: {str(e)}")

@app.post("/api/system/trigger/worker")
async def trigger_worker():
    """手動觸發 Worker"""
    try:
        scheduler = get_scheduler()
        result = scheduler.trigger_worker_now()
        return {"triggered": True, "result": result}
    except Exception as e:
        logger.error(f"Manual worker trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger worker: {str(e)}")

@app.post("/api/system/trigger/cto")
async def trigger_cto(force: bool = False):
    """手動觸發 CTO Review"""
    try:
        scheduler = get_scheduler()
        result = scheduler.trigger_cto_now(force=force)
        return {"triggered": True, "result": result}
    except Exception as e:
        logger.error(f"Manual CTO trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger CTO review: {str(e)}")

# 整合 Orchestrator API 路由
app.include_router(orchestrator_api.router, tags=["Orchestrator"])

# 錯誤處理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    
    # 開發環境設定
    port = int(os.environ.get("PORT", "8787"))
    host = os.environ.get("HOST", "127.0.0.1")
    
    logger.info(f"Starting Betting-pool FastAPI server on {host}:{port}")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
