"""
回測與優化 API 路由
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from common import get_lottery_rules
from models.backtest_framework import RollingBacktester, StrategyAdapter
from models.auto_optimizer import AutoOptimizer
from models.multi_bet_optimizer import MultiBetOptimizer
from models.optimized_predictor import OptimizedPredictor

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# 初始化組件
db = DatabaseManager()
backtester = RollingBacktester()
auto_optimizer = AutoOptimizer()
multi_bet_optimizer = MultiBetOptimizer()
optimized_predictor = OptimizedPredictor()


# ==================== 資料模型 ====================

class BacktestRequest(BaseModel):
    lottery_type: str = "BIG_LOTTO"
    method: Optional[str] = None
    window: Optional[int] = None
    test_year: int = 2025


class MultiBetRequest(BaseModel):
    lottery_type: str = "BIG_LOTTO"
    num_bets: int = 6


class PredictRequest(BaseModel):
    lottery_type: str = "BIG_LOTTO"
    num_bets: int = 1


class BacktestSummaryResponse(BaseModel):
    lottery_type: str
    method_name: str
    window_size: int
    test_periods: int
    win_count: int
    win_rate: float
    win_rate_display: str
    avg_matches: float
    periods_per_win: float
    expected_cost: float
    user_friendly: Dict


# ==================== API 端點 ====================

@router.get("/optimal-config/{lottery_type}")
async def get_optimal_config(lottery_type: str):
    """
    獲取最佳預測配置

    Returns:
        最佳方法和窗口配置
    """
    config = auto_optimizer.get_optimal(lottery_type)

    if config is None:
        # 嘗試運行優化
        try:
            draws = db.get_all_draws(lottery_type)
            rules = get_lottery_rules(lottery_type)
            config = auto_optimizer.find_optimal(draws, rules, lottery_type, verbose=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {
        "lottery_type": config.lottery_type,
        "optimal_method": config.method_name,
        "optimal_window": config.window_size,
        "win_rate": config.win_rate,
        "win_rate_display": f"{config.win_rate*100:.2f}%",
        "avg_matches": config.avg_matches,
        "periods_per_win": config.periods_per_win,
        "expected_cost": config.expected_cost,
        "user_friendly": {
            "description": f"每 {config.periods_per_win:.1f} 期中 1 次",
            "cost_per_win": f"${config.expected_cost:.0f}"
        },
        "last_updated": config.last_updated
    }


@router.post("/run-optimization")
async def run_optimization(request: BacktestRequest):
    """
    執行自動優化，找出最佳配置
    """
    try:
        draws = db.get_all_draws(request.lottery_type)
        rules = get_lottery_rules(request.lottery_type)

        config = auto_optimizer.find_optimal(
            draws, rules, request.lottery_type,
            test_year=request.test_year,
            verbose=False
        )

        return {
            "success": True,
            "lottery_type": config.lottery_type,
            "optimal_method": config.method_name,
            "optimal_window": config.window_size,
            "win_rate": config.win_rate,
            "win_rate_display": f"{config.win_rate*100:.2f}%",
            "test_periods": config.test_periods,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/single-method")
async def backtest_single_method(request: BacktestRequest):
    """
    回測單一預測方法
    """
    try:
        draws = db.get_all_draws(request.lottery_type)
        rules = get_lottery_rules(request.lottery_type)

        from models.unified_predictor import prediction_engine

        method_map = {
            'zone_balance': prediction_engine.zone_balance_predict,
            'sum_range': prediction_engine.sum_range_predict,
            'hot_cold_mix': prediction_engine.hot_cold_mix_predict,
            'trend_predict': prediction_engine.trend_predict,
            'bayesian': prediction_engine.bayesian_predict,
            'monte_carlo': prediction_engine.monte_carlo_predict,
            'ensemble': prediction_engine.ensemble_predict,
            'odd_even_balance': prediction_engine.odd_even_balance_predict,
        }

        method_func = method_map.get(request.method)
        if method_func is None:
            raise HTTPException(status_code=400, detail=f"未知方法: {request.method}")

        window = request.window or 100
        strategy = StrategyAdapter(request.method, method_func, window)

        summary = backtester.run(
            strategy=strategy,
            draws=draws,
            lottery_rules=rules,
            lottery_type=request.lottery_type,
            test_year=request.test_year,
            verbose=False
        )

        return {
            "lottery_type": summary.lottery_type,
            "method": summary.method_name,
            "window": summary.window_size,
            "test_periods": summary.test_periods,
            "win_count": summary.win_count,
            "win_rate": summary.win_rate,
            "win_rate_display": f"{summary.win_rate*100:.2f}%",
            "avg_matches": summary.avg_matches,
            "periods_per_win": summary.periods_per_win,
            "expected_cost": summary.expected_cost_per_win,
            "user_friendly": {
                "description": f"每 {summary.periods_per_win:.1f} 期中 1 次",
                "cost_per_win": f"${summary.expected_cost_per_win:.0f}"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-bet")
async def backtest_multi_bet(request: MultiBetRequest):
    """
    回測多注覆蓋策略
    """
    try:
        draws = db.get_all_draws(request.lottery_type)
        rules = get_lottery_rules(request.lottery_type)

        summary = backtester.run_multi_bet(
            draws=draws,
            lottery_rules=rules,
            lottery_type=request.lottery_type,
            num_bets=request.num_bets,
            test_year=2025,
            verbose=False
        )

        return {
            "lottery_type": summary.lottery_type,
            "num_bets": request.num_bets,
            "test_periods": summary.test_periods,
            "win_count": summary.win_count,
            "win_rate": summary.win_rate,
            "win_rate_display": f"{summary.win_rate*100:.2f}%",
            "avg_best_match": summary.avg_matches,
            "periods_per_win": summary.periods_per_win,
            "cost_per_bet": 50 if request.lottery_type != 'POWER_LOTTO' else 100,
            "expected_cost": summary.expected_cost_per_win,
            "user_friendly": {
                "description": f"每 {summary.periods_per_win:.1f} 期中 1 次",
                "cost_per_win": f"${summary.expected_cost_per_win:.0f} ({request.num_bets}注)"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare-all/{lottery_type}")
async def compare_all_methods(lottery_type: str, test_year: int = 2025):
    """
    比較所有預測方法
    """
    try:
        draws = db.get_all_draws(lottery_type)
        rules = get_lottery_rules(lottery_type)

        results = backtester.compare_methods(
            draws, rules, lottery_type, test_year, verbose=False
        )

        return {
            "lottery_type": lottery_type,
            "test_year": test_year,
            "methods_tested": len(results),
            "ranking": [
                {
                    "rank": i + 1,
                    "method": r.method_name,
                    "window": r.window_size,
                    "win_rate": r.win_rate,
                    "win_rate_display": f"{r.win_rate*100:.2f}%",
                    "avg_matches": r.avg_matches,
                    "periods_per_win": r.periods_per_win
                }
                for i, r in enumerate(results)
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict-optimal")
async def predict_with_optimal(request: PredictRequest):
    """
    使用最佳配置進行預測
    """
    try:
        draws = db.get_all_draws(request.lottery_type)
        rules = get_lottery_rules(request.lottery_type)

        if request.num_bets == 1:
            result = optimized_predictor.predict_single(draws, rules, request.lottery_type)
            return {
                "lottery_type": request.lottery_type,
                "prediction": {
                    "numbers": result['numbers'],
                    "special": result.get('special'),
                    "method": result['method'],
                    "window": result['window']
                },
                "expected_win_rate": result['expected_win_rate'],
                "expected_win_rate_display": f"{result['expected_win_rate']*100:.2f}%",
                "generated_at": result['generated_at']
            }
        else:
            result = optimized_predictor.predict_multi(
                draws, rules, request.lottery_type, request.num_bets
            )
            return {
                "lottery_type": request.lottery_type,
                "num_bets": request.num_bets,
                "predictions": [
                    {
                        "bet_number": i + 1,
                        "numbers": bet['numbers'],
                        "source": bet.get('source', 'unknown')
                    }
                    for i, bet in enumerate(result['bets'])
                ],
                "coverage": result['coverage'],
                "coverage_display": f"{result['coverage']*100:.1f}%",
                "expected_win_rate": result['expected_win_rate'],
                "expected_win_rate_display": f"{result['expected_win_rate']*100:.2f}%",
                "generated_at": result['generated_at']
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{lottery_type}")
async def get_recommendations(lottery_type: str, budget: int = None):
    """
    獲取投注建議
    """
    try:
        recommendations = optimized_predictor.get_recommendation(lottery_type, budget)

        return {
            "lottery_type": lottery_type,
            "bet_price": recommendations['bet_price'],
            "budget": budget,
            "recommendations": [
                {
                    "strategy": r['strategy'],
                    "strategy_display": {
                        'conservative': '保守型',
                        'economic': '經濟型',
                        'balanced': '平衡型',
                        'aggressive': '進取型',
                        'maximum': '最大覆蓋'
                    }.get(r['strategy'], r['strategy']),
                    "num_bets": r['num_bets'],
                    "cost": r['cost'],
                    "expected_win_rate": r['expected_win_rate'],
                    "expected_win_rate_display": f"{r['expected_win_rate']*100:.2f}%",
                    "description": r['description']
                }
                for r in recommendations['recommendations']
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
