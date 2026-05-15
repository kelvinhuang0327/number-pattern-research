#!/usr/bin/env python3
"""
熵驱动 Transformer 8注预测
Entropy-Driven 8-Bet Prediction

使用创新的熵最大化方法生成8注差异化的号码组合
目标：最大化小奖中奖率
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import db_manager
from models.unified_predictor import prediction_engine
from models.entropy_transformer import EntropyTransformerModel
from models.anti_consensus_sampler import EntropyMaximizedSampler, DiversityCalculator, AntiConsensusFilter
from common import get_lottery_rules
import numpy as np


def predict_entropy_8_bets(lottery_type='BIG_LOTTO', strategy='balanced'):
    """
    生成8注熵优化的预测

    Args:
        lottery_type: 彩票类型
        strategy: 'balanced' (平衡), 'aggressive' (激进), 'conservative' (保守)

    Returns:
        8注预测结果
    """
    print('=' * 100)
    print('🎯 熵驱动 Transformer 8注预测（革命性创新方法）')
    print('=' * 100)
    print()

    # 1. 载入历史数据
    print('📊 载入历史数据...')
    all_draws = db_manager.get_all_draws(lottery_type)

    if not all_draws:
        print(f'❌ 找不到 {lottery_type} 的历史数据')
        return []

    # 使用最近100期
    history = all_draws[:100]
    print(f'✅ 载入 {len(history)} 期数据')
    print(f'   最新开奖: {history[0]["date"]} - 期号 {history[0]["draw"]}')
    print(f'   训练范围: {history[-1]["date"]} ~ {history[0]["date"]}')
    print()

    lottery_rules = get_lottery_rules(lottery_type)

    # 2. 初始化模型和采样器
    print('🧠 初始化熵驱动 Transformer 模型...')
    max_num = lottery_rules.get('maxNumber', 49)
    pick_count = lottery_rules.get('pickCount', 6)
    model = EntropyTransformerModel(max_num=max_num)
    sampler = EntropyMaximizedSampler(n_bets=8, numbers_per_bet=pick_count)
    anti_filter = AntiConsensusFilter(penalty_factor=0.7)

    # 3. 获取模型预测概率
    print('🔮 生成概率分布...')
    probs = model.predict(history)

    # 4. 获取传统方法的共识号码
    print('🔍 识别传统方法的共识号码...')
    consensus_numbers = set()

    try:
        freq_result = prediction_engine.frequency_predict(history, lottery_rules)
        consensus_numbers.update(freq_result['numbers'])
        print(f'   频率分析: {sorted(freq_result["numbers"])}')
    except:
        pass

    try:
        trend_result = prediction_engine.trend_predict(history, lottery_rules)
        consensus_numbers.update(trend_result['numbers'])
        print(f'   趋势分析: {sorted(trend_result["numbers"])}')
    except:
        pass

    print(f'   📌 共识号码: {sorted(list(consensus_numbers))} (共{len(consensus_numbers)}个)')
    print()

    # 5. 应用反向共识过滤
    print('🎭 应用反向共识过滤（降权共识号码30%）...')
    filtered_probs = anti_filter.filter(probs, consensus_numbers)
    print('✅ 过滤完成')
    print()

    # 6. 生成8注号码
    print(f'🎲 生成8注号码（策略: {strategy}）...')
    print('=' * 100)
    print()

    bets, metadata = sampler.generate_diverse_8_bets(filtered_probs, strategy=strategy)

    # 7. 显示结果
    print('📊 预测结果')
    print('=' * 100)
    print()

    strategy_desc = {
        'balanced': '平衡策略（4注热门 + 4注冷门）',
        'aggressive': '激进策略（偏向冷门号码，最大覆盖率）',
        'conservative': '保守策略（偏向热门号码，稳健投注）'
    }

    print(f'🎯 策略: {strategy_desc.get(strategy, strategy)}')
    print()

    for idx, bet_meta in enumerate(metadata, 1):
        numbers_str = ', '.join(f'{n:02d}' for n in bet_meta['numbers'])
        bet_type = '🔥 热门' if bet_meta['type'] == 'hot' else '❄️  冷门'
        avg_prob = bet_meta['avg_prob'] * 100

        print(f'第{idx}注 {bet_type} [{numbers_str}]')
        print(f'       平均概率: {avg_prob:.2f}% | 奇数: {bet_meta["odd_count"]}/6 | 和值: {bet_meta["sum"]}')
        print()

    # 8. 多样性分析
    print('=' * 100)
    print('📈 多样性分析')
    print('=' * 100)
    print()

    DiversityCalculator.print_diversity_report(bets)

    # 9. 与传统方法对比
    print()
    print('=' * 100)
    print('🔬 与传统方法对比')
    print('=' * 100)
    print()

    print(f'🆕 熵方法 Top 10 号码:')
    top_10_indices = np.argsort(filtered_probs)[-10:][::-1]
    top_10_nums = [idx + 1 for idx in top_10_indices]
    print(f'   {sorted(top_10_nums)}')
    print()

    print(f'🔁 传统共识 Top 号码:')
    print(f'   {sorted(list(consensus_numbers))[:10]}')
    print()

    # 计算差异度
    entropy_set = set(top_10_nums)
    consensus_set = set(list(consensus_numbers)[:10])
    diff_count = len(entropy_set - consensus_set)

    print(f'✨ 差异度: {diff_count}/10 个号码不同 ({diff_count/10*100:.0f}% 独特性)')
    print()

    # 10. 投注建议
    print('=' * 100)
    print('💡 投注建议')
    print('=' * 100)
    print()

    print('✓ 这8注号码使用革命性的熵驱动方法生成')
    print('✓ 核心创新：')
    print('  • 12维特征工程（随机性度量、反向信号、覆盖率、时序动态）')
    print('  • 反向共识过滤（避开传统方法的"陷阱"）')
    print('  • 熵最大化采样（覆盖更广的号码空间）')
    print()

    print(f'✓ 策略特点：')
    if strategy == 'balanced':
        print('  • 4注热门号码 + 4注冷门号码')
        print('  • 平衡风险与回报')
    elif strategy == 'aggressive':
        print('  • 重点关注被传统方法忽略的号码')
        print('  • 最大化覆盖率（通常达到70%+）')
    elif strategy == 'conservative':
        print('  • 保留部分传统方法的信号')
        print('  • 稳健投注，适合谨慎型玩家')
    print()

    print(f'💰 投注金额: NT$ {len(bets) * 100}')
    print(f'🎯 优化目标: 最大化小奖中奖率（柒奖、普奖）')
    print()

    print('⚠️  重要提醒:')
    print('   • 彩券为机率游戏，无法保证中奖')
    print('   • 本方法针对114000113期失败教训设计，但仍需回测验证')
    print('   • 预测仅供参考，请理性投注')
    print()

    print('=' * 100)
    print('📅 预测基准: 期号 {} ({})'.format(history[0]['draw'], history[0]['date']))
    print('🔬 方法: Entropy-Driven Transformer (12D Features + Anti-Consensus)')
    print('=' * 100)

    return bets


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='熵驱动 8注预测')
    parser.add_argument('--lottery', default='BIG_LOTTO', help='彩票类型 (默认: BIG_LOTTO)')
    parser.add_argument('--strategy', default='balanced',
                       choices=['balanced', 'aggressive', 'conservative'],
                       help='策略: balanced (平衡), aggressive (激进), conservative (保守)')

    args = parser.parse_args()

    predict_entropy_8_bets(lottery_type=args.lottery, strategy=args.strategy)
