"""
進階自動學習 API 路由
提供多階段優化和自適應窗口優化的 API 端點
"""

async def run_multi_stage_optimization(advanced_engine, scheduler, request):
    """
    執行多階段優化

    Args:
        advanced_engine: 進階學習引擎實例
        scheduler: 排程器實例
        request: 請求對象（包含 lotteryType）

    Returns:
        優化結果
    """
    try:
        # 從後端加載數據
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        history = scheduler.get_data(lottery_type)

        if not history or len(history) < 100:
            return {
                'success': False,
                'error': f'數據不足（目前 {len(history)} 期，至少需要 100 期）'
            }

        lottery_rules = scheduler.lottery_rules or {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49
        }

        # 執行多階段優化
        result = await advanced_engine.multi_stage_optimize(
            history=history,
            lottery_rules=lottery_rules
        )

        return result

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


async def run_adaptive_window_optimization(advanced_engine, scheduler, request):
    """
    執行自適應窗口優化

    Args:
        advanced_engine: 進階學習引擎實例
        scheduler: 排程器實例
        request: 請求對象（包含 lotteryType）

    Returns:
        優化結果
    """
    try:
        # 從後端加載數據
        lottery_type = request.get('lotteryType', 'BIG_LOTTO')
        history = scheduler.get_data(lottery_type)

        if not history or len(history) < 100:
            return {
                'success': False,
                'error': f'數據不足（目前 {len(history)} 期，至少需要 100 期）'
            }

        lottery_rules = scheduler.lottery_rules or {
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 49
        }

        # 執行自適應窗口優化
        result = await advanced_engine.adaptive_window_optimize(
            history=history,
            lottery_rules=lottery_rules
        )

        return result

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
