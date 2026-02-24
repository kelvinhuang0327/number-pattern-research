#!/usr/bin/env python3
"""
彩票数据深度分析：验证随机性并探索更好的预测方法
"""
import sys
import os
sys.path.insert(0, os.getcwd())

import numpy as np
from scipy import stats
from scipy.stats import chi2_contingency, ks_2samp
from collections import Counter, defaultdict
from database import db_manager
import json

def analyze_randomness(lottery_type='BIG_LOTTO'):
    """深度随机性分析"""

    print("=" * 80)
    print("【彩票数据深度分析】验证随机性与探索预测可能性")
    print("=" * 80)

    # 获取数据
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x.get('draw', ''), reverse=True)

    print(f"\n数据集: {lottery_type}")
    print(f"总期数: {len(all_draws)}期")
    print(f"日期范围: {all_draws[-1]['date']} ~ {all_draws[0]['date']}")

    # 提取所有号码
    all_numbers = []
    for draw in all_draws:
        all_numbers.extend(draw['numbers'])

    max_num = 49 if lottery_type == 'BIG_LOTTO' else 38
    pick_count = 6

    results = {}

    # ========================================
    # 测试1: 卡方检验 (Chi-Square Test)
    # ========================================
    print("\n" + "=" * 80)
    print("【测试1】卡方检验 - 检验号码出现频率是否均匀分布")
    print("=" * 80)

    observed = Counter(all_numbers)
    expected_freq = len(all_numbers) / max_num

    # 构造观测值和期望值
    observed_counts = [observed.get(i, 0) for i in range(1, max_num + 1)]
    expected_counts = [expected_freq] * max_num

    chi2_stat, p_value = stats.chisquare(observed_counts, expected_counts)

    print(f"\n卡方统计量: {chi2_stat:.4f}")
    print(f"p值: {p_value:.6f}")
    print(f"显著性水平: α = 0.05")

    if p_value > 0.05:
        print(f"✅ 结论: 无法拒绝原假设 (p={p_value:.4f} > 0.05)")
        print(f"   → 号码分布符合均匀分布，数据具有随机性")
        results['chi_square'] = {'pass': True, 'p_value': p_value}
    else:
        print(f"⚠️  结论: 拒绝原假设 (p={p_value:.4f} < 0.05)")
        print(f"   → 号码分布显著偏离均匀分布，可能存在偏差！")
        results['chi_square'] = {'pass': False, 'p_value': p_value}

    # 显示频率最高和最低的号码
    freq_sorted = sorted(observed.items(), key=lambda x: x[1], reverse=True)
    print(f"\n出现最多的5个号码: {freq_sorted[:5]}")
    print(f"出现最少的5个号码: {freq_sorted[-5:]}")

    # ========================================
    # 测试2: 游程检验 (Runs Test)
    # ========================================
    print("\n" + "=" * 80)
    print("【测试2】游程检验 - 检验号码序列是否随机")
    print("=" * 80)

    # 将号码分为高低组
    median = (max_num + 1) / 2
    sequence = [1 if n > median else 0 for n in all_numbers]

    # 计算游程数
    runs = 1
    for i in range(1, len(sequence)):
        if sequence[i] != sequence[i-1]:
            runs += 1

    n1 = sum(sequence)  # 高号数量
    n0 = len(sequence) - n1  # 低号数量

    # 理论期望游程数
    expected_runs = (2 * n0 * n1) / (n0 + n1) + 1
    variance_runs = (2 * n0 * n1 * (2 * n0 * n1 - n0 - n1)) / ((n0 + n1)**2 * (n0 + n1 - 1))

    # Z统计量
    z_stat = (runs - expected_runs) / np.sqrt(variance_runs)
    p_value_runs = 2 * (1 - stats.norm.cdf(abs(z_stat)))

    print(f"\n实际游程数: {runs}")
    print(f"期望游程数: {expected_runs:.2f}")
    print(f"Z统计量: {z_stat:.4f}")
    print(f"p值: {p_value_runs:.6f}")

    if p_value_runs > 0.05:
        print(f"✅ 结论: 序列具有随机性 (p={p_value_runs:.4f} > 0.05)")
        results['runs_test'] = {'pass': True, 'p_value': p_value_runs}
    else:
        print(f"⚠️  结论: 序列可能存在模式 (p={p_value_runs:.4f} < 0.05)")
        results['runs_test'] = {'pass': False, 'p_value': p_value_runs}

    # ========================================
    # 测试3: 熵分析 (Entropy Analysis)
    # ========================================
    print("\n" + "=" * 80)
    print("【测试3】熵分析 - 检验信息熵是否接近最大")
    print("=" * 80)

    # 计算实际熵
    total = len(all_numbers)
    probs = [observed.get(i, 0) / total for i in range(1, max_num + 1)]
    entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in probs)

    # 最大熵（完全随机）
    max_entropy = np.log2(max_num)

    # 熵比率
    entropy_ratio = entropy / max_entropy

    print(f"\n实际熵: {entropy:.4f} bits")
    print(f"最大熵: {max_entropy:.4f} bits")
    print(f"熵比率: {entropy_ratio:.4f} ({entropy_ratio*100:.2f}%)")

    if entropy_ratio > 0.95:
        print(f"✅ 结论: 熵接近最大值，数据高度随机")
        results['entropy'] = {'pass': True, 'ratio': entropy_ratio}
    elif entropy_ratio > 0.90:
        print(f"⚠️  结论: 熵较高但未达到完全随机")
        results['entropy'] = {'pass': True, 'ratio': entropy_ratio}
    else:
        print(f"❌ 结论: 熵偏低，数据可能存在模式！")
        results['entropy'] = {'pass': False, 'ratio': entropy_ratio}

    # ========================================
    # 测试4: 连号分析
    # ========================================
    print("\n" + "=" * 80)
    print("【测试4】连号模式分析")
    print("=" * 80)

    consecutive_counts = []
    for draw in all_draws:
        nums = sorted(draw['numbers'])
        consecutive = 0
        for i in range(len(nums) - 1):
            if nums[i+1] - nums[i] == 1:
                consecutive += 1
        consecutive_counts.append(consecutive)

    avg_consecutive = np.mean(consecutive_counts)

    # 理论期望：在49个数中随机选6个，期望连号数
    # 简化计算：约为 (6-1) * 6/49 ≈ 0.61
    expected_consecutive = (pick_count - 1) * pick_count / max_num

    print(f"\n平均连号组数: {avg_consecutive:.2f}")
    print(f"理论期望: {expected_consecutive:.2f}")
    print(f"偏差: {avg_consecutive - expected_consecutive:+.2f}")

    # 分布
    consecutive_dist = Counter(consecutive_counts)
    print(f"\n连号分布:")
    for i in sorted(consecutive_dist.keys()):
        count = consecutive_dist[i]
        pct = count / len(all_draws) * 100
        bar = '▓' * int(pct / 2)
        print(f"  {i}组连号: {count:4d}期 ({pct:5.1f}%) {bar}")

    results['consecutive'] = {
        'avg': avg_consecutive,
        'expected': expected_consecutive,
        'deviation': avg_consecutive - expected_consecutive
    }

    # ========================================
    # 测试5: 奇偶比分析
    # ========================================
    print("\n" + "=" * 80)
    print("【测试5】奇偶比分析")
    print("=" * 80)

    odd_even_counts = []
    for draw in all_draws:
        odd_count = sum(1 for n in draw['numbers'] if n % 2 == 1)
        odd_even_counts.append(odd_count)

    # 理论期望：3奇3偶
    expected_odd = pick_count / 2

    odd_even_dist = Counter(odd_even_counts)
    print(f"\n奇偶比分布:")
    for i in sorted(odd_even_dist.keys()):
        count = odd_even_dist[i]
        pct = count / len(all_draws) * 100
        bar = '▓' * int(pct / 2)
        print(f"  {i}奇{pick_count-i}偶: {count:4d}期 ({pct:5.1f}%) {bar}")

    # 卡方检验奇偶比分布
    # 理论分布（二项分布）
    from scipy.stats import binom
    n_draws = len(all_draws)
    expected_dist = {}
    for i in range(pick_count + 1):
        # 近似：假设奇偶号数量相等
        expected_dist[i] = n_draws * binom.pmf(i, pick_count, 0.5)

    observed_odd_even = [odd_even_dist.get(i, 0) for i in range(pick_count + 1)]
    expected_odd_even = [expected_dist[i] for i in range(pick_count + 1)]

    chi2_odd_even, p_odd_even = stats.chisquare(observed_odd_even, expected_odd_even)

    print(f"\n卡方检验:")
    print(f"  χ² = {chi2_odd_even:.4f}, p = {p_odd_even:.6f}")

    if p_odd_even > 0.05:
        print(f"  ✅ 奇偶比分布符合随机预期")
        results['odd_even'] = {'pass': True, 'p_value': p_odd_even}
    else:
        print(f"  ⚠️  奇偶比分布存在偏差")
        results['odd_even'] = {'pass': False, 'p_value': p_odd_even}

    # ========================================
    # 测试6: 自相关分析
    # ========================================
    print("\n" + "=" * 80)
    print("【测试6】自相关分析 - 检验是否存在时间依赖")
    print("=" * 80)

    # 计算每期的"特征值"（如号码和）
    draw_sums = [sum(draw['numbers']) for draw in all_draws]

    # 计算滞后1期的自相关
    from scipy.stats import pearsonr

    correlations = {}
    for lag in [1, 2, 3, 5, 10]:
        if len(draw_sums) > lag:
            corr, p_val = pearsonr(draw_sums[:-lag], draw_sums[lag:])
            correlations[lag] = {'corr': corr, 'p_value': p_val}

    print(f"\n号码和的自相关分析:")
    has_correlation = False
    for lag, data in correlations.items():
        corr = data['corr']
        p_val = data['p_value']
        if abs(corr) > 0.1 and p_val < 0.05:
            print(f"  滞后{lag}期: r={corr:+.4f}, p={p_val:.6f} ⚠️  显著相关！")
            has_correlation = True
        else:
            print(f"  滞后{lag}期: r={corr:+.4f}, p={p_val:.6f} ✓")

    if not has_correlation:
        print(f"\n✅ 结论: 无显著自相关，各期独立")
        results['autocorr'] = {'pass': True}
    else:
        print(f"\n⚠️  结论: 存在自相关，可能有时间依赖！")
        results['autocorr'] = {'pass': False}

    # ========================================
    # 最终总结
    # ========================================
    print("\n" + "=" * 80)
    print("【综合评估】数据随机性总结")
    print("=" * 80)

    tests = [
        ('卡方检验', results['chi_square']['pass']),
        ('游程检验', results['runs_test']['pass']),
        ('熵分析', results['entropy']['pass']),
        ('奇偶比检验', results['odd_even']['pass']),
        ('自相关检验', results['autocorr']['pass']),
    ]

    passed = sum(1 for _, p in tests if p)
    total = len(tests)

    print(f"\n通过测试: {passed}/{total}")
    for name, passed in tests:
        status = "✅ 通过" if passed else "❌ 未通过"
        print(f"  {name}: {status}")

    if passed == total:
        print(f"\n【结论】数据具有高度随机性，符合公平彩票预期")
        print(f"⚠️  这意味着：历史数据对未来预测的帮助极其有限！")
    elif passed >= total * 0.7:
        print(f"\n【结论】数据基本随机，但存在一些微弱模式")
        print(f"💡 可能的机会：深入分析未通过的测试项")
    else:
        print(f"\n【结论】数据存在明显的非随机模式！")
        print(f"🎯 这是好消息：存在可预测的空间")

    # 保存结果
    with open('data/randomness_analysis_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n详细结果已保存: data/randomness_analysis_results.json")

    return results


def suggest_advanced_methods(results):
    """根据分析结果推荐更好的方法"""

    print("\n" + "=" * 80)
    print("【方法论建议】基于数据特征的更好分析方法")
    print("=" * 80)

    passed_tests = sum(1 for test in results.values() if test.get('pass', False))
    total_tests = len([v for v in results.values() if 'pass' in v])

    if passed_tests == total_tests:
        print("\n🔬 情况A：数据完全随机（所有测试通过）")
        print("=" * 60)
        print("""
【现实】
历史数据对未来预测没有统计学意义的帮助。
任何声称能"预测"随机数的方法都是伪科学。

【更好的策略】
1. ❌ 停止预测号码（无意义）
2. ✅ 转向"逆向思维"策略：

   A. 避开热门号码组合
      - 分析：大多数人倾向选择生日、幸运数字
      - 策略：选择30+的大号、避免常见组合
      - 好处：中奖时减少分奖人数，提高实际收益

   B. 覆盖率最大化
      - 使用组合优化算法（如覆盖设计）
      - 以最少注数覆盖最多号码组合
      - 数学工具：Steiner系统、拉丁方阵

   C. 期望值优化
      - 当奖池累积到超高金额时才投注
      - 计算期望值 = 奖金 × 中奖概率 - 成本
      - 只在期望值为正时参与

【推荐实现】
```python
def anti_popular_strategy(lottery_type):
    \"\"\"反热门号码策略\"\"\"
    # 1. 统计历史上人们常选的号码（1-31生日范围）
    # 2. 避开这些号码
    # 3. 选择30+的大号组合

def coverage_optimization(budget, lottery_type):
    \"\"\"覆盖率优化策略\"\"\"
    # 使用整数规划求解最优覆盖问题
    # 目标：最小化成本，最大化覆盖

def expected_value_calculator(jackpot, lottery_type):
    \"\"\"期望值计算器\"\"\"
    # 只在期望值 > 0 时推荐投注
```

【结论】
在完全随机的数据上，最好的"预测方法"是：
→ 不预测号码，而是优化投注策略和资金管理
""")

    elif passed_tests >= total_tests * 0.5:
        print("\n🔬 情况B：数据基本随机，但存在微弱模式")
        print("=" * 60)
        print("""
【现实】
数据主要是随机的，但检测到一些统计异常。
这些异常可能是：
1. 随机波动（偶然）
2. 摇奖机械偏差（真实模式）
3. 样本量不足（假象）

【更好的分析方法】

A. 贝叶斯推断框架 ⭐⭐⭐⭐⭐
   目的：区分真实模式和随机噪音

   实现：
   ```python
   import pymc3 as pm

   def bayesian_bias_detection(data):
       \"\"\"贝叶斯偏差检测\"\"\"
       with pm.Model() as model:
           # 先验：假设公平（均匀分布）
           theta = pm.Dirichlet('theta', a=np.ones(49))

           # 似然：观测数据
           observations = pm.Multinomial('obs', n=len(data), p=theta, observed=data)

           # MCMC采样
           trace = pm.sample(2000)

           # 后验分析：哪些号码的后验概率显著偏离1/49？
           return trace
   ```

B. 时间序列分解 ⭐⭐⭐⭐
   目的：分离趋势、季节性、随机成分

   ```python
   from statsmodels.tsa.seasonal import seasonal_decompose

   def decompose_lottery_trend(number_freq_series):
       \"\"\"分解号码频率的时间序列\"\"\"
       result = seasonal_decompose(number_freq_series, model='additive', period=52)

       # 分析：
       # - trend: 长期趋势（机械磨损？）
       # - seasonal: 季节性（温度影响？）
       # - resid: 随机成分
   ```

C. 隐马尔可夫模型 (HMM) ⭐⭐⭐⭐
   目的：检测潜在的"状态切换"

   ```python
   from hmmlearn import hmm

   def detect_state_changes(data):
       \"\"\"检测摇奖机是否有不同状态\"\"\"
       # 假设：摇奖机可能有2-3个隐藏状态
       # 状态1：正常
       # 状态2：某些号码偏高（机械偏差）
       # 状态3：某些号码偏低

       model = hmm.GaussianHMM(n_components=3)
       model.fit(data)

       # 识别当前处于哪个状态
       states = model.predict(data)
   ```

D. 因果推断 ⭐⭐⭐
   目的：识别真正的因果关系

   ```python
   # 分析外部因素：
   # - 摇奖机更换日期
   # - 球体更换日期
   # - 温度、湿度
   # - 摇奖人员

   from dowhy import CausalModel

   def causal_analysis(lottery_data, external_factors):
       \"\"\"因果推断分析\"\"\"
       # 问题：球体更换后，频率分布是否改变？
   ```

E. 非参数统计 ⭐⭐⭐⭐
   目的：不假设任何分布

   ```python
   from scipy.stats import mannwhitneyu, kruskal

   def non_parametric_bias_test(freq_data):
       \"\"\"非参数偏差测试\"\"\"
       # Kruskal-Wallis H检验
       # 比较不同号码的出现频率是否来自同一分布
   ```

【推荐实现优先级】
1. ⭐⭐⭐⭐⭐ 贝叶斯推断（最科学）
2. ⭐⭐⭐⭐ HMM状态检测（检测系统性偏差）
3. ⭐⭐⭐⭐ 时间序列分解（检测趋势）
4. ⭐⭐⭐ 因果推断（需要外部数据）

【结论】
在微弱模式的情况下，重点是：
→ 区分真实偏差和随机噪音
→ 使用严格的统计检验避免过拟合
""")

    else:
        print("\n🔬 情况C：数据存在明显非随机模式")
        print("=" * 60)
        print("""
【警告】
如果彩票数据显著偏离随机分布，可能存在：
1. 摇奖机械偏差（可利用）
2. 数据记录错误（需修正）
3. 人为操纵（违法）

【深度分析方法】

A. 物理模拟 ⭐⭐⭐⭐⭐
   目的：模拟摇奖机械过程

   ```python
   import pymunk  # 2D物理引擎

   def simulate_lottery_machine(ball_properties, machine_config):
       \"\"\"物理模拟摇奖过程\"\"\"
       # 考虑：
       # - 球体重量差异（微小）
       # - 表面摩擦系数
       # - 气流动力学
       # - 机械磨损
   ```

B. 机器学习异常检测 ⭐⭐⭐⭐⭐

   ```python
   from sklearn.ensemble import IsolationForest
   from sklearn.svm import OneClassSVM

   def detect_anomaly_patterns(lottery_draws):
       \"\"\"异常模式检测\"\"\"
       # 特征工程：
       features = extract_features(lottery_draws)
       # - 号码和
       # - 号码方差
       # - 连号数
       # - 奇偶比
       # - 区间分布
       # - 尾数分布

       # 模型：
       iso_forest = IsolationForest(contamination=0.1)
       anomalies = iso_forest.fit_predict(features)

       # 分析异常期次的共同特征
   ```

C. 深度学习 - Transformer ⭐⭐⭐⭐

   ```python
   import torch
   import torch.nn as nn

   class LotteryTransformer(nn.Module):
       \"\"\"基于Transformer的序列预测\"\"\"
       def __init__(self, num_numbers=49, d_model=256, nhead=8):
           super().__init__()
           self.embedding = nn.Embedding(num_numbers+1, d_model)
           self.transformer = nn.TransformerEncoder(...)

       def forward(self, history_seq):
           # 输入：历史开奖序列
           # 输出：下一期概率分布
   ```

D. 集成超参数优化 ⭐⭐⭐⭐

   ```python
   import optuna

   def optimize_prediction_pipeline(data):
       \"\"\"自动调优整个预测管道\"\"\"
       def objective(trial):
           # 超参数空间：
           window_size = trial.suggest_int('window', 50, 500)
           model_type = trial.suggest_categorical('model', ['xgb', 'lstm', 'transformer'])
           ensemble_weight = trial.suggest_float('weight', 0, 1)

           # 评估指标：滚动回测命中率
           score = rolling_backtest(...)
           return score

       study = optuna.create_study(direction='maximize')
       study.optimize(objective, n_trials=100)
   ```

【终极方法：元学习】

```python
def meta_learning_lottery(all_lottery_types_data):
    \"\"\"跨彩票类型的元学习\"\"\"
    # 思路：
    # 1. 从威力彩、大乐透、今彩539学习共同模式
    # 2. 学习"如何学习"彩票规律
    # 3. 快速适应新彩票类型

    from learn2learn import MAML

    # Model-Agnostic Meta-Learning
    maml = MAML(model, lr=0.01)
```

【结论】
如果数据真的非随机：
→ 这是罕见的好机会！
→ 使用最先进的AI/ML方法深度挖掘
→ 但要警惕：可能是数据问题而非真实模式
""")

    # 输出可执行的代码建议
    print("\n" + "=" * 80)
    print("【立即可用的改进方案】")
    print("=" * 80)
    print("""
根据你的数据特征，我建议立即实施：

1. 创建 advanced_bayesian_analyzer.py
   - 贝叶斯框架检测真实偏差

2. 创建 anti_consensus_strategy.py
   - 反热门号码策略（提高中奖收益）

3. 创建 coverage_optimizer.py
   - 组合覆盖优化

4. 创建 expected_value_monitor.py
   - 期望值计算器（只在EV>0时推荐）

是否需要我帮你实现这些方案？
""")


if __name__ == "__main__":
    results = analyze_randomness('BIG_LOTTO')
    suggest_advanced_methods(results)
