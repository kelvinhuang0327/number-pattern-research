#!/usr/bin/env python3
"""
快速預測腳本 - 供 /predict 命令使用
用法: python3 tools/quick_predict.py [彩票類型] [注數]

策略對照 (2026-02-24 更新):
  大樂透 2注: 偏差互補+回聲 P0 (Edge +1.21%, 確定性)
  大樂透 3注: Triple Strike (Edge +0.98%, 1500期 STABLE)
  大樂透 4注: TS3+Markov(w=30) (Edge +1.23%, 1500期)
  大樂透 5注: TS3+Markov+FreqOrt (Edge +1.77%, 1500期 z=2.40 ★最佳)
  威力彩 2注: Fourier Rhythm (Edge +1.91%)
  威力彩 3注: Power Precision (Edge +2.23%, 1500期 STABLE, z=2.74)
  威力彩 特別號: V3 (Edge +2.20%)
  威力彩 冷號預警: cold_alert (監控用，McNemar不顯著故未替換PP3)
  今彩539 3注: SumRange+Bayesian+ZoneBalance
"""
import sys
import os
import random
import argparse
import numpy as np
from numpy.fft import fft, fftfreq
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


# 彩票類型對照
LOTTERY_MAP = {
    '大樂透': 'BIG_LOTTO',
    'biglotto': 'BIG_LOTTO',
    'big': 'BIG_LOTTO',
    '威力彩': 'POWER_LOTTO',
    'power': 'POWER_LOTTO',
    '今彩539': 'DAILY_539',
    '539': 'DAILY_539',
    'daily': 'DAILY_539',
}

# 默認配置 (2026-02-23 更新)
DEFAULT_CONFIG = {
    'BIG_LOTTO': {'bets': 5, 'cost': 150},
    'POWER_LOTTO': {'bets': 2, 'cost': 200},
    'DAILY_539': {'bets': 3, 'cost': 150},
}

# 各注數 Edge 和策略名稱 (2026-02-23 驗證)
STRATEGY_INFO = {
    'BIG_LOTTO': {
        2: {'strategy': '偏差互補+回聲 P0', 'edge': '+1.21%', 'verified': '1000期+10種子'},
        3: {'strategy': 'Triple Strike', 'edge': '+0.98%', 'verified': '1500期 STABLE'},
        4: {'strategy': 'TS3+Markov(w=30)', 'edge': '+1.23%', 'verified': '1500期 z=1.85'},
        5: {'strategy': 'TS3+Markov+FreqOrt', 'edge': '+1.77%', 'verified': '1500期 z=2.40 P3 p=0.030'},
    },
    'POWER_LOTTO': {
        2: {'strategy': 'Fourier Rhythm', 'edge': '+1.91%', 'verified': '1000期'},
        3: {'strategy': 'Power Precision', 'edge': '+2.23%', 'verified': '1500期 STABLE z=2.74'},
    },
    'DAILY_539': {
        3: {'strategy': 'SumRange+Bayesian+ZoneBalance', 'edge': 'N/A', 'verified': ''},
    },
}

LOTTERY_NAMES = {
    'BIG_LOTTO': '大樂透',
    'POWER_LOTTO': '威力彩',
    'DAILY_539': '今彩539',
}

# N注隨機基準 (精確計算)
BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25, 5: 8.96},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.60},
}


# ========== 大樂透策略 ==========

def biglotto_p0_2bet(history, window=50, echo_boost=1.5):
    """大樂透 2注: 偏差互補+回聲 P0 (Edge +1.21%, 確定性)"""
    MAX_NUM, PICK = 49, 6
    recent = history[-window:] if len(history) > window else history
    expected = len(recent) * PICK / MAX_NUM

    freq = Counter()
    for d in recent:
        for n in d['numbers']:
            freq[n] += 1

    scores = {}
    for n in range(1, MAX_NUM + 1):
        scores[n] = freq.get(n, 0) - expected

    # P0: Lag-2 回聲加分
    if len(history) >= 3:
        for n in history[-2]['numbers']:
            if n <= MAX_NUM:
                scores[n] += echo_boost

    hot = sorted([(n, s) for n, s in scores.items() if s > 1],
                 key=lambda x: x[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1],
                  key=lambda x: x[1], reverse=True)

    # 注1: Hot+Echo
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        mid = sorted(range(1, MAX_NUM + 1), key=lambda n: abs(scores[n]))
        for n in mid:
            if n not in used and len(bet1) < PICK:
                bet1.append(n); used.add(n)

    # 注2: Cold
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n); used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n); used.add(n)

    return [
        {'numbers': sorted(bet1[:PICK])},
        {'numbers': sorted(bet2[:PICK])},
    ]


def biglotto_triple_strike(history):
    """大樂透 3注: Triple Strike (Edge +0.98%, 1500期 STABLE)"""
    from tools.predict_biglotto_triple_strike import generate_triple_strike
    bets_raw = generate_triple_strike(history)
    return [{'numbers': b} for b in bets_raw]


def biglotto_5bet_orthogonal(history):
    """大樂透 5注正交: TS3+Markov(w=30)+FreqOrt (Edge +1.77%, 1500期 z=2.40 ★最佳)"""
    from tools.backtest_biglotto_markov_4bet import (
        fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet, markov_orthogonal_bet
    )
    MAX_NUM = 49

    # 注1: Fourier Rhythm
    bet1 = fourier_rhythm_bet(history, window=500)
    used = set(bet1)

    # 注2: Cold Numbers (排除注1)
    bet2 = cold_numbers_bet(history, window=100, exclude=used)
    used.update(bet2)

    # 注3: Tail Balance (排除注1+2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    used.update(bet3)

    # 注4: Markov(w=30) 正交 (排除注1-3)
    bet4 = markov_orthogonal_bet(history, exclude=used, markov_window=30)
    used.update(bet4)

    # 注5: FreqOrt — 剩餘號碼按近100期頻率排序取前6
    recent = history[-100:] if len(history) >= 100 else history
    freq = Counter(n for d in recent for n in d['numbers'])
    remaining = sorted([n for n in range(1, MAX_NUM + 1) if n not in used],
                       key=lambda x: -freq.get(x, 0))
    bet5 = sorted(remaining[:6])

    return [
        {'numbers': bet1},
        {'numbers': bet2},
        {'numbers': bet3},
        {'numbers': bet4},
        {'numbers': bet5},
    ]


# ========== 威力彩策略 ==========

def power_precision_3bet(history):
    """威力彩 3注: Power Precision (Edge +2.30%, 1500期 STABLE)"""
    from tools.predict_power_precision_3bet import generate_power_precision_3bet
    bets_raw = generate_power_precision_3bet(history)
    return [{'numbers': b} for b in bets_raw]



def power_fourier_rhythm_2bet(history):
    """威力彩 2注: Fourier Rhythm (Edge +1.91%)"""
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    bets_raw = fourier_rhythm_predict(history, n_bets=2, window=500)
    return [{'numbers': b} for b in bets_raw]


def power_p0p1_3bet(history, window=50, echo_boost=1.5, sample_attempts=200):
    """(已過時) 威力彩 3注: P0+P1 灰色地帶 (Edge +1.01%)"""
    # 僅保留作代碼參考
    pass


def power_special_v3(history):
    """威力彩特別號 V3 (Edge +2.20%)"""
    try:
        from models.special_predictor import PowerLottoSpecialPredictor
        rules = {'name': 'POWER_LOTTO', 'specialMinNumber': 1, 'specialMaxNumber': 8}
        sp = PowerLottoSpecialPredictor(rules)
        return sp.predict_top_n(history, n=3)
    except Exception:
        # Fallback: 近50期頻率
        freq = Counter(d.get('special', 0) for d in history[-50:])
        return [n for n, _ in freq.most_common(3)]


# ========== 預測主函數 ==========

def predict_biglotto(history, rules, num_bets=5):
    """大樂透預測 (2026-02-23 策略)"""
    if num_bets <= 2:
        bets = biglotto_p0_2bet(history)[:num_bets]
        return bets, '偏差互補+回聲 P0'
    elif num_bets == 3:
        bets = biglotto_triple_strike(history)
        return bets, 'Triple Strike'
    else:
        # 4注或5注：用5注正交，再切片
        bets = biglotto_5bet_orthogonal(history)[:num_bets]
        if num_bets == 4:
            return bets, 'TS3+Markov(w=30)'
        return bets, 'TS3+Markov+FreqOrt'


def predict_power(history, rules, num_bets=2):
    """威力彩預測 (2026-02-11 策略)"""
    special_top = power_special_v3(history)
    special = special_top[0] if special_top else 1

    if num_bets <= 2:
        bets = power_fourier_rhythm_2bet(history)[:num_bets]
        strategy = 'Fourier Rhythm (Edge +1.91%)'
    else:
        bets = power_precision_3bet(history)[:num_bets]
        strategy = 'Power Precision (Edge +2.23%)'

    # 附加特別號到每注
    for bet in bets:
        bet['special'] = special

    return bets, strategy


def predict_539(history, rules, num_bets=3):
    """今彩539預測"""
    from models.unified_predictor import UnifiedPredictionEngine

    engine = UnifiedPredictionEngine()
    bets = []
    methods = ['sum_range_predict', 'bayesian_predict', 'zone_balance_predict']

    for method in methods[:num_bets]:
        try:
            func = getattr(engine, method)
            result = func(history, rules)
            bets.append({'numbers': result['numbers']})
        except Exception:
            continue

    return bets, 'SumRange+Bayesian+ZoneBalance'


# ========== 顯示 ==========

def get_next_draw_number(history):
    """計算下期期號"""
    if not history:
        return 'N/A'
    last_draw = history[-1].get('draw', '')
    if not last_draw:
        return 'N/A'
    try:
        last_num = int(str(last_draw)[-3:])
        prefix = str(last_draw)[:-3]
        return f"{prefix}{last_num + 1:03d}"
    except Exception:
        return 'N/A'


def format_numbers(numbers):
    """格式化號碼顯示"""
    return ', '.join([f'{n:02d}' for n in sorted(numbers)])


def print_prediction(lottery_type, bets, strategy, history, num_bets):
    """打印預測結果"""
    name = LOTTERY_NAMES.get(lottery_type, lottery_type)
    config = DEFAULT_CONFIG.get(lottery_type, {})
    next_draw = get_next_draw_number(history)
    last_draw = history[-1] if history else {}

    # 查詢基準和 Edge
    info = STRATEGY_INFO.get(lottery_type, {}).get(num_bets, {})
    baseline = BASELINES.get(lottery_type, {}).get(num_bets, 0)

    print()
    print('=' * 60)
    print(f'  {name} {next_draw} 期預測報告')
    print('=' * 60)

    # 上期開獎
    if last_draw:
        last_nums = format_numbers(last_draw.get('numbers', []))
        last_special = last_draw.get('special', '')
        print(f'  上期開獎: {last_draw.get("draw", "N/A")} - {last_nums}', end='')
        if last_special:
            print(f' | 特別號: {int(last_special):02d}')
        else:
            print()

    print('-' * 60)
    print(f'  預測號碼 ({num_bets}注):')
    print()

    strategy_labels = {
        'BIG_LOTTO': {
            2: ['Hot+Echo (高頻+回聲)', 'Cold (冷號均值回歸)'],
            3: ['Fourier Rhythm (FFT 週期)', 'Cold Numbers (冷號逆向)', 'Tail Balance (尾數平衡)'],
            4: ['Fourier Rhythm', 'Cold Numbers', 'Tail Balance', 'Markov(w=30) 正交'],
            5: ['Fourier Rhythm', 'Cold Numbers', 'Tail Balance', 'Markov(w=30) 正交', 'FreqOrt 正交'],
        },
        'POWER_LOTTO': {
            2: ['Fourier Rhythm 注1', 'Fourier Rhythm 注2'],
            3: ['Fourier Rhythm 注1', 'Fourier Rhythm 注2', 'Echo/Cold (回聲+冷號)'],
            4: ['Fourier Rhythm 1', 'Fourier Rhythm 2', 'Echo/Cold (回聲補償)', 'Gray Zone Gap (盲區填補)'],
        },
    }
    labels = strategy_labels.get(lottery_type, {}).get(num_bets, [])

    for i, bet in enumerate(bets, 1):
        nums = format_numbers(bet.get('numbers', []))
        special = bet.get('special')
        label = f'  <- {labels[i-1]}' if i <= len(labels) else ''
        if special:
            print(f'  注{i}: {nums} | 特別號: {int(special):02d}{label}')
        else:
            print(f'  注{i}: {nums}{label}')

    # 覆蓋統計
    all_nums = set()
    for bet in bets:
        all_nums.update(bet.get('numbers', []))
    max_num = 49 if lottery_type == 'BIG_LOTTO' else 38
    print()
    print(f'  覆蓋: {len(all_nums)}/{max_num} 號碼 ({len(all_nums)/max_num*100:.1f}%)')

    # 特別號 Top 3 (威力彩)
    if lottery_type == 'POWER_LOTTO':
        sp_top = power_special_v3(history)
        print(f'  特別號 Top3 (V3): {sp_top}')

        # 冷號預警 (P3: 監控用，不影響選號)
        try:
            from tools.cold_alert import get_cold_alert_info
            cold_info = get_cold_alert_info(history)
            print(f'  冷號預警: {cold_info["message"]}')
            if cold_info['is_alert']:
                top6 = ', '.join(f'{n:02d}' for n in cold_info['top_cold'])
                print(f'  冷號參考: {top6} (score={cold_info["alert_score"]:.2f})')
        except Exception:
            pass

    print('-' * 60)
    print(f'  策略: {strategy}')
    if info:
        print(f'  驗證: {info.get("verified", "")} | Edge: {info.get("edge", "")}')
    if baseline > 0:
        print(f'  隨機基準: {baseline:.2f}% ({num_bets}注)')
    print(f'  成本: NT${config.get("cost", 0) // config.get("bets", 1) * num_bets}')
    print('=' * 60)
    print()


def main():
    parser = argparse.ArgumentParser(description='彩票預測工具 (2026-02-11 策略更新)')
    parser.add_argument('lottery', nargs='?', default='all',
                        help='彩票類型 (大樂透/威力彩/今彩539/all)')
    parser.add_argument('bets', nargs='?', type=int, default=None,
                        help='預測注數')
    args = parser.parse_args()

    # 初始化數據庫
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))

    # 確定要預測的彩票類型
    if args.lottery.lower() == 'all':
        lottery_types = ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']
    else:
        lottery_type = LOTTERY_MAP.get(args.lottery.lower(), args.lottery.upper())
        lottery_types = [lottery_type]

    # 執行預測
    for lottery_type in lottery_types:
        try:
            history = db.get_all_draws(lottery_type=lottery_type)

            if not history or len(history) < 50:
                print(f'\n  {LOTTERY_NAMES.get(lottery_type, lottery_type)}: '
                      f'數據不足 ({len(history) if history else 0} 期)，跳過預測')
                continue

            # get_all_draws 返回 DESC 排序，策略需要 ASC (舊→新)
            history = sorted(history, key=lambda x: (x['date'], x['draw']))

            # 獲取規則 (本地硬編碼以避免 import 阻塞)
            rules_map = {
                'BIG_LOTTO': {'pickCount': 6, 'minNumber': 1, 'maxNumber': 49, 'specialMaxNumber': 49},
                'POWER_LOTTO': {'pickCount': 6, 'minNumber': 1, 'maxNumber': 38, 'specialMaxNumber': 8},
                'DAILY_539': {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39, 'specialMaxNumber': 0},
            }
            rules = rules_map.get(lottery_type, {'pickCount': 6, 'minNumber': 1, 'maxNumber': 49})
            num_bets = args.bets or DEFAULT_CONFIG.get(lottery_type, {}).get('bets', 3)

            if lottery_type == 'BIG_LOTTO':
                bets, strategy = predict_biglotto(history, rules, num_bets)
            elif lottery_type == 'POWER_LOTTO':
                bets, strategy = predict_power(history, rules, num_bets)
            elif lottery_type == 'DAILY_539':
                bets, strategy = predict_539(history, rules, num_bets)
            else:
                print(f'  不支援的彩票類型: {lottery_type}')
                continue

            print_prediction(lottery_type, bets, strategy, history, num_bets)

        except Exception as e:
            print(f'  {lottery_type} 預測失敗: {e}')
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()
