from fastapi import APIRouter, HTTPException, Query, Path, File, UploadFile, Form
from typing import List, Dict, Optional
import logging
import os
import json
import sys

from schemas import (
    OptimizationRequest, CreateDrawRequest, UpdateDrawRequest, DrawData
)
from database import db_manager
from utils.scheduler import scheduler
from utils.model_cache import model_cache
from common import normalize_lottery_type
from utils.csv_validator import csv_validator 

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
from analysis.payout.sync import refresh_hedge_fund_outputs

router = APIRouter()
logger = logging.getLogger(__name__)

# 各彩種號碼上限（主號 / 特別號）
_LOTTERY_NUM_MAX = {
    'BIG_LOTTO':   {'main': 49, 'special': 49},
    'POWER_LOTTO': {'main': 38, 'special': 8},   # 威力彩特別號池為 1-8
    'DAILY_539':   {'main': 39, 'special': None},
}

@router.get("/api/history")
async def get_history(
    lottery_type: Optional[str] = Query(None, description="彩券類型篩選")
):
    """
    獲取所有歷史數據
    """
    try:
        if lottery_type:
            lottery_type = normalize_lottery_type(lottery_type)
            logger.info(f"🔍 [get_history] lottery_type={lottery_type}")

        logger.info(f"🔍 [get_history] Calling db_manager.get_all_draws()...")
        all_data = db_manager.get_all_draws(lottery_type)
        logger.info(f"🔍 [get_history] db_manager returned {len(all_data)} draws")

        # 同時確保 scheduler 有數據
        if not scheduler.latest_data or len(scheduler.latest_data) == 0:
            logger.info(f"🔍 [get_history] Loading data to scheduler...")
            scheduler.latest_data = all_data
            scheduler.data_by_type = {}
            for draw in all_data:
                lt = draw.get('lotteryType', 'UNKNOWN')
                if lt not in scheduler.data_by_type:
                    scheduler.data_by_type[lt] = []
                scheduler.data_by_type[lt].append(draw)
            logger.info(f"🔍 [get_history] Scheduler loaded {len(scheduler.latest_data)} draws")

        logger.info(f"🔍 [get_history] Returning {len(all_data)} draws to client")
        return all_data
    except Exception as e:
        logger.error(f"Error reading history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/data/upload")
async def upload_data(request: OptimizationRequest):
    """
    上傳開獎數據到數據庫
    """
    try:
        history = [draw.dict() for draw in request.history]
        logger.info(f"📤 開始上傳 {len(history)} 筆數據...")
        
        inserted, duplicates = db_manager.insert_draws(history)
        logger.info(f"✅ 數據插入完成: 新增 {inserted} 筆，重複 {duplicates} 筆")
        
        scheduler.update_data(history, request.lotteryRules)
        if inserted > 0:
            refresh_hedge_fund_outputs(project_root)
        
        return {
            "success": True,
            "inserted": inserted,
            "duplicates": duplicates,
            "total": inserted + duplicates,
            "message": f"成功上傳 {inserted} 筆新數據，{duplicates} 筆重複"
        }
    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/data/validate-csv")
async def validate_csv(
    file: UploadFile = File(...),
    lottery_type: str = Form(...),
    play_mode: Optional[str] = Form(None)
):
    """
    驗證 CSV/TXT 文件格式並返回詳細錯誤報告
    支援：
    - CSV: 標準逗號分隔格式
    - TXT: 今彩539官方格式

    Args:
        file: 上傳的文件
        lottery_type: 彩券類型
        play_mode: 玩法模式（可選，僅適用於樂合彩系列，例如：'二合', '三合', '四合'）
    """
    try:
        content = await file.read()
        l_type = normalize_lottery_type(lottery_type)

        # 根據文件副檔名判斷類型
        file_ext = file.filename.lower().split('.')[-1] if file.filename else 'csv'
        file_type = 'txt' if file_ext == 'txt' else 'csv'

        logger.info(f"📄 驗證文件: {file.filename}, 類型: {file_type}, 彩券: {l_type}, 玩法: {play_mode or 'N/A'}")
        result = csv_validator.validate(content, l_type, file_type, play_mode)

        # 在解析結果中添加玩法模式信息
        if result.get("valid") and play_mode:
            for data in result.get("parsed_data", []):
                data["playMode"] = play_mode

        return result
    except Exception as e:
        logger.error(f"File Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data/draws")
async def get_draws(
    lottery_type: Optional[str] = Query(None, description="彩券類型篩選"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(50, ge=1, le=500, description="每頁數量"),
    start_date: Optional[str] = Query(None, description="開始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="結束日期 (YYYY-MM-DD)")
):
    """分頁查詢開獎記錄"""
    try:
        result = db_manager.get_draws(
            lottery_type=lottery_type,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date
        )
        logger.info(f"📊 Query: type={lottery_type}, page={page}, returned {len(result['draws'])} draws")
        return result
    except Exception as e:
        logger.error(f"❌ Query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data/stats")
async def get_data_stats(lottery_type: Optional[str] = Query(None)):
    """獲取數據統計信息"""
    try:
        stats = db_manager.get_stats(lottery_type)
        logger.info(f"📊 Stats: {stats['total']} total draws")
        return stats
    except Exception as e:
        logger.error(f"❌ Get stats failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/data/clear")
async def clear_backend_data():
    """清除後端存儲的所有數據"""
    try:
        count = db_manager.clear_all_data()

        # lottery_api/data/ 目錄
        api_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

        data_files = [
            "data/lottery_data.json",
            "data/lottery_rules.json",
            os.path.join(api_data_dir, "lottery_history.json"),     # scheduler 重啟後從此回載
            os.path.join(api_data_dir, "predictions_BIG_LOTTO.jsonl"),
            os.path.join(api_data_dir, "predictions_DAILY_539.jsonl"),
            os.path.join(api_data_dir, "predictions_POWER_LOTTO.jsonl"),
            os.path.join(api_data_dir, "performance_history.json"),
            os.path.join(api_data_dir, "llm_analysis_log.jsonl"),
            os.path.join(api_data_dir, "ingest_log.jsonl"),
        ]
        deleted_files = []
        for file_path in data_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_files.append(file_path)

        scheduler.latest_data = None
        scheduler.lottery_rules = None
        scheduler.data_by_type = {}
        model_cache.clear()

        # 確保 scheduler 不會在重啟後從磁碟回載殘留資料
        # lottery_history.json 已在上方 data_files 中刪除

        return {
            "success": True,
            "message": f"已清除 {count} 筆數據庫記錄",
            "deleted_db_records": count,
            "deleted_files": deleted_files
        }
    except Exception as e:
        logger.error(f"清除數據失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/draws")
async def create_draw(request: CreateDrawRequest):
    """新增開獎記錄"""
    try:
        draw_data = request.dict()
        if db_manager.get_draw(request.lotteryType, request.draw):
            raise HTTPException(status_code=400, detail=f"期號 {request.draw} 已存在")
        
        inserted, _ = db_manager.insert_draws([draw_data])
        if inserted > 0:
            scheduler.load_data() # Reload to sync
            refresh_hedge_fund_outputs(project_root)
            return {"success": True, "message": "新增成功", "data": draw_data}
        else:
            raise HTTPException(status_code=500, detail="新增失敗")
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Create draw error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/draws/{draw_id}")
async def update_draw(draw_id: str, request: UpdateDrawRequest):
    """更新開獎記錄"""
    try:
        logger.info(f"✏️ 更新記錄: ID={draw_id}")

        conn = db_manager._get_connection()
        cursor = conn.cursor()

        try:
            # 先用 id 精確查找；找不到再用 draw + lottery_type 縮小範圍
            cursor.execute("SELECT * FROM draws WHERE id = ?", (draw_id,))
            existing = cursor.fetchone()

            if not existing:
                lt = normalize_lottery_type(request.lotteryType) if request.lotteryType else None
                if lt:
                    cursor.execute(
                        "SELECT * FROM draws WHERE draw = ? AND lottery_type = ?",
                        (draw_id, lt),
                    )
                    existing = cursor.fetchone()
                else:
                    cursor.execute("SELECT * FROM draws WHERE draw = ?", (draw_id,))
                    rows = cursor.fetchall()
                    if len(rows) > 1:
                        raise HTTPException(
                            status_code=400,
                            detail=f"期號 {draw_id} 存在於多個彩種，請在請求中加入 lotteryType 以指定",
                        )
                    existing = rows[0] if rows else None

            if not existing:
                raise HTTPException(status_code=404, detail=f"找不到記錄: {draw_id}")

            # 決定最終彩種，用於驗證上限
            final_type = normalize_lottery_type(request.lotteryType) if request.lotteryType else existing['lottery_type']
            limits = _LOTTERY_NUM_MAX.get(final_type, {'main': 49, 'special': 49})

            # 驗證號碼
            if request.numbers:
                expected_count = 5 if final_type == 'DAILY_539' else 6
                if len(request.numbers) != expected_count:
                    raise HTTPException(status_code=400, detail=f"必須提供 {expected_count} 個開獎號碼")
                for num in request.numbers:
                    if num < 1 or num > limits['main']:
                        raise HTTPException(status_code=400, detail=f"號碼 {num} 超出範圍 (1-{limits['main']})")

            # 驗證特別號
            if request.special is not None:
                sp_max = limits['special']
                if sp_max is None:
                    raise HTTPException(status_code=400, detail=f"{final_type} 沒有特別號")
                if request.special < 1 or request.special > sp_max:
                    raise HTTPException(status_code=400, detail=f"特別號 {request.special} 超出範圍 (1-{sp_max})")

            update_data = {
                'draw': request.draw if request.draw else existing['draw'],
                'date': request.date if request.date else existing['date'],
                'lotteryType': final_type,
                'numbers': request.numbers if request.numbers else json.loads(existing['numbers']),
                'special': request.special if request.special is not None else existing['special']
            }

            # 用 DB 主鍵刪除，避免同期號跨彩種誤刪
            cursor.execute("DELETE FROM draws WHERE id = ?", (existing['id'],))

            numbers_json = json.dumps(update_data['numbers'])
            cursor.execute("""
                INSERT INTO draws (draw, date, lottery_type, numbers, special)
                VALUES (?, ?, ?, ?, ?)
            """, (
                update_data['draw'],
                update_data['date'],
                update_data['lotteryType'],
                numbers_json,
                update_data['special']
            ))

            conn.commit()
            logger.info(f"✅ 更新成功: {draw_id}")
            refresh_hedge_fund_outputs(project_root)

            return {
                "success": True,
                "message": "更新成功"
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 更新失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失敗: {str(e)}")


@router.delete("/api/draws/{draw_id}")
async def delete_draw(draw_id: str, lottery_type: Optional[str] = Query(None)):
    """刪除開獎記錄（lottery_type 可選，用於期號存在於多個彩種時消除歧義）"""
    try:
        logger.info(f"🗑️ 刪除記錄: ID={draw_id}, lottery_type={lottery_type}")

        conn = db_manager._get_connection()
        cursor = conn.cursor()

        try:
            # 先用 id 精確查找
            cursor.execute("SELECT id FROM draws WHERE id = ?", (draw_id,))
            row = cursor.fetchone()

            if not row:
                lt = normalize_lottery_type(lottery_type) if lottery_type else None
                if lt:
                    cursor.execute(
                        "SELECT id FROM draws WHERE draw = ? AND lottery_type = ?",
                        (draw_id, lt),
                    )
                    row = cursor.fetchone()
                else:
                    cursor.execute("SELECT id FROM draws WHERE draw = ?", (draw_id,))
                    rows = cursor.fetchall()
                    if len(rows) > 1:
                        raise HTTPException(
                            status_code=400,
                            detail=f"期號 {draw_id} 存在於多個彩種，請加上 ?lottery_type= 參數指定",
                        )
                    row = rows[0] if rows else None

            if not row:
                raise HTTPException(status_code=404, detail=f"找不到記錄: {draw_id}")

            # 用 DB 主鍵刪除，避免跨彩種誤刪
            cursor.execute("DELETE FROM draws WHERE id = ?", (row['id'],))
            conn.commit()
            logger.info(f"✅ 刪除成功: {draw_id}")

            return {"success": True, "message": "刪除成功"}

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    except HTTPException: raise
    except Exception as e:
        logger.error(f"刪除失敗: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
