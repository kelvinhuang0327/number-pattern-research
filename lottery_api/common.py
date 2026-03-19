from fastapi import HTTPException
try:
    from .utils.scheduler import scheduler
except ImportError:
    from utils.scheduler import scheduler
try:
    from .config import lottery_config
except ImportError:
    from config import lottery_config

def normalize_lottery_type(lottery_type: str) -> str:
    """
    將中文彩券名稱或前端 ID 轉換為後端使用的標準英文代碼
    """
    if lottery_type is None:
        return lottery_type

    raw = str(lottery_type).strip()
    if not raw:
        return raw

    normalized = raw.replace("-", "_").replace(" ", "_").upper()
    canonical = {
        "BIG_LOTTO",
        "BIG_LOTTO_BONUS",
        "POWER_LOTTO",
        "DAILY_539",
        "DOUBLE_WIN",
        "3_STAR",
        "4_STAR",
        "38_LOTTO",
        "39_LOTTO",
        "49_LOTTO",
        "BINGO_BINGO",
        "LOTTO_6_38",
    }

    mapping = {
        # 中文映射
        "大樂透": "BIG_LOTTO",
        "大樂透加開獎項": "BIG_LOTTO_BONUS",
        "威力彩": "POWER_LOTTO",
        "今彩539": "DAILY_539",
        "雙贏彩": "DOUBLE_WIN",
        "3星彩": "3_STAR",
        "4星彩": "4_STAR",
        "38樂合彩": "38_LOTTO",
        "49樂合彩": "49_LOTTO",
        "39樂合彩": "39_LOTTO",

        # 前端 ID 映射 (處理 index.html 中的定義不一致)
        "DAILY_CASH_539": "DAILY_539",
        "DAILY539": "DAILY_539",
        "POWER_BALL": "POWER_LOTTO",
        "POWERLOTTO": "POWER_LOTTO",
        "BIGLOTTO": "BIG_LOTTO",
        "STAR3": "3_STAR",
        "STAR4": "4_STAR",
        "STAR_3": "3_STAR",
        "STAR_4": "4_STAR",
        "LOTTO_38": "38_LOTTO",
        "LOTTO_49": "49_LOTTO",
        "LOTTO_39": "39_LOTTO"
    }

    if raw in mapping:
        return mapping[raw]
    if normalized in mapping:
        return mapping[normalized]
    if normalized in canonical:
        return normalized
    return raw

def get_related_lottery_types(lottery_type: str) -> list:
    """
    獲取相關彩券類型（用於訓練數據合併）
    例如: BIG_LOTTO -> [BIG_LOTTO, BIG_LOTTO_BONUS]

    Args:
        lottery_type: 彩券類型 ID

    Returns:
        包含基礎類型和所有相關類型的列表
    """
    # 定義相關類型映射（與前端 LotteryTypes.js 保持一致）
    # [MODIFIED] User requested to separate BONUS data into a distinct game
    RELATED_TYPES = {
        # 'BIG_LOTTO': ['BIG_LOTTO'], # Default behavior is self only, so we can remove this
        # 'BIG_LOTTO_BONUS': ['BIG_LOTTO_BONUS'],
    }

    # 先標準化類型名稱
    normalized_type = normalize_lottery_type(lottery_type)

    # 返回相關類型，如果沒有定義則只返回自己
    related = RELATED_TYPES.get(normalized_type, [normalized_type])
    return related

def get_lottery_rules(lottery_type: str) -> dict:
    """獲取彩券規則 (優先從配置獲取)"""
    normalized = normalize_lottery_type(lottery_type)
    
    # 1. Try Config
    rules = lottery_config.get_rules_dict(normalized)
    if rules:
        return rules
        
    # 2. Try Scheduler (Legacy)
    if scheduler.lottery_rules:
        return scheduler.lottery_rules
        
    # 3. Fallback Default
    default = lottery_config.get_rules_dict("BIG_LOTTO")
    if default: return default
    
    # 4. Hard Fallback
    return {
        'pickCount': 6,
        'minNumber': 1,
        'maxNumber': 49,
        'hasSpecialNumber': True,
        'specialMinNumber': 1,
        'specialMaxNumber': 49
    }

def load_backend_history(lottery_type: str, min_required: int = 10):
    """載入後端已同步的歷史數據與規則, 不足時回傳 HTTPException"""
    # Normalize lottery type
    lottery_type = normalize_lottery_type(lottery_type)

    # 規則優先從 Config 獲取
    rules = get_lottery_rules(lottery_type)

    # 優先從資料庫載入（資料最完整）
    history = []
    try:
        from database import db_manager
        history = db_manager.get_all_draws(lottery_type)
    except Exception as e:
        print(f"DB load failed: {e}")

    # Fallback: 從 scheduler 載入（JSON 檔案）
    if not history:
        history = scheduler.get_data(lottery_type)

    # Fallback 2: Check legacy structure
    if not history and scheduler.latest_data:
         history = [d for d in scheduler.latest_data if normalize_lottery_type(d.get('lotteryType', '')) == lottery_type]

    if len(history) < min_required:
        raise HTTPException(status_code=400, detail=f"彩券類型 {lottery_type} 的數據不足（需要至少 {min_required} 期，目前 {len(history)} 期）")
        
    return history, rules

def get_data_range_info(history: list) -> dict:
    """生成數據區間信息"""
    if not history:
        return {
            "total_count": 0,
            "date_range": "無數據",
            "draw_range": "無數據"
        }
    
    first_draw = history[0]
    last_draw = history[-1]
    
    return {
        "total_count": len(history),
        "date_range": f"{first_draw.get('date', 'N/A')} ~ {last_draw.get('date', 'N/A')}",
        "draw_range": f"{first_draw.get('draw', 'N/A')} ~ {last_draw.get('draw', 'N/A')}",
        "first_date": first_draw.get('date', 'N/A'),
        "last_date": last_draw.get('date', 'N/A'),
        "first_draw": first_draw.get('draw', 'N/A'),
        "last_draw": last_draw.get('draw', 'N/A')
    }
