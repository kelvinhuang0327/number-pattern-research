"""
大樂透 AutoML 探索系統 — 主入口
BIG_LOTTO AutoML Exploration System — Main Entry Point

用法:
    # 快速掃描（~10 分鐘）
    python3 -m ai_lab.automl_biglotto.main --quick --test-periods 50

    # 標準回測（~1 小時）
    python3 -m ai_lab.automl_biglotto.main --test-periods 150

    # 完整搜索（~3-4 小時）
    python3 -m ai_lab.automl_biglotto.main --full --test-periods 500

    # 僅 Phase 1
    python3 -m ai_lab.automl_biglotto.main --phase 1 --test-periods 150

    # 僅 Phase 2
    python3 -m ai_lab.automl_biglotto.main --phase 2 --test-periods 150
"""
import os
import sys
import time
import argparse
import json
import traceback
import numpy as np
from pathlib import Path
from typing import Dict, List, Callable, Optional

# Ensure project root is on path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .config import (SEED, TEST_WINDOWS, n_bet_baseline, SCORE_WEIGHTS,
                     GP_POPULATION, GP_GENERATIONS, MIN_HISTORY)
from .backtest_engine import RollingBacktester, BacktestResult, load_draws
from .strategies_phase1 import build_all_strategies, build_quick_strategies
from .scorer import StrategyScorer, StrategyScore, compute_synergy_data
from .feature_library import FeatureLibrary
from .genetic_engine import GeneticEngine
from .fusion import StrategyFusion
from .report import ReportGenerator
from .phase3_deep_search import build_phase3_strategies, build_phase3_quick, count_strategies


def run_phase1(backtester: RollingBacktester,
               strategies: Dict[str, Callable],
               test_periods: int = 150,
               multi_window: bool = True,
               verbose: bool = True) -> List[Dict]:
    """
    Phase 1: 已知方法極限挖掘
    回測所有策略，計算四維度分數
    """
    scorer = StrategyScorer()
    results = []
    total = len(strategies)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Phase 1: 已知方法掃描 ({total} strategies)")
        print(f"  test_periods={test_periods}, multi_window={multi_window}")
        print(f"{'='*60}")

    for idx, (name, func) in enumerate(strategies.items()):
        try:
            # Primary backtest
            result = backtester.run(func, test_periods=test_periods,
                                    strategy_name=name)

            # Multi-window (optional)
            mw_results = {}
            if multi_window:
                windows = {k: min(v, test_periods) for k, v in TEST_WINDOWS.items()
                           if v <= test_periods}
                if len(windows) > 1:
                    mw_results = backtester.run_multi_window(func, windows=windows,
                                                             strategy_name=name)

            # Score
            score = scorer.score(result, mw_results if mw_results else None)

            # Categorize
            category = _categorize_strategy(name)

            entry = {
                'name': name,
                'category': category,
                'primary_result': result.to_dict(),
                'primary_edge_pct': result.edge_pct,
                'multi_window_results': {k: r.to_dict() for k, r in mw_results.items()},
                'scores': score.to_dict(),
            }
            results.append(entry)

            if verbose and (idx + 1) % 10 == 0:
                print(f"  [{idx+1}/{total}] {name}: "
                      f"edge={result.edge_pct:+.2f}%, z={result.z_score:.2f}, "
                      f"class={score.classification}")

        except Exception as e:
            if verbose:
                print(f"  [{idx+1}/{total}] {name}: ERROR - {e}")
            continue

    # Sort by edge
    results.sort(key=lambda x: -x.get('primary_edge_pct', 0))

    if verbose:
        print(f"\n  Phase 1 Complete: {len(results)}/{total} strategies evaluated")
        if results:
            top = results[0]
            print(f"  Best: {top['name']} edge={top['primary_edge_pct']:+.2f}%")

    return results


def run_phase2(backtester: RollingBacktester,
               all_draws: List[Dict],
               test_periods: int = 150,
               gp_population: int = None,
               gp_generations: int = None,
               n_linear: int = 500,
               verbose: bool = True) -> List[Dict]:
    """
    Phase 2: 未知方法探索引擎
    GP 演化 + 隨機線性公式
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Phase 2: 未知方法探索")
        print(f"{'='*60}")

    feature_lib = FeatureLibrary()

    gp_config = {}
    if gp_population:
        gp_config['population'] = gp_population
    if gp_generations:
        gp_config['generations'] = gp_generations

    engine = GeneticEngine(feature_lib, all_draws, config=gp_config)

    # GP Evolution
    if verbose:
        print("\n  [GP Evolution]")
    gp_results = engine.evolve(test_periods=test_periods, verbose=verbose)
    if verbose:
        print(f"  GP found {len(gp_results)} valid formulas")

    # Random Linear Formulas
    if verbose:
        print("\n  [Random Linear Formulas]")
    linear_results = engine.random_linear_formulas(
        n_formulas=n_linear, test_periods=test_periods, verbose=verbose)
    if verbose:
        print(f"  Random Linear found {len(linear_results)} valid formulas")

    # Merge and deduplicate
    all_results = []
    seen_formulas = set()

    for r in gp_results:
        r['origin'] = 'GP'
        if r.get('formula') not in seen_formulas:
            seen_formulas.add(r.get('formula'))
            all_results.append(r)

    for r in linear_results:
        r['origin'] = 'random_linear'
        if r.get('formula') not in seen_formulas:
            seen_formulas.add(r.get('formula'))
            all_results.append(r)

    all_results.sort(key=lambda x: -min(x.get('train_edge', 0), x.get('test_edge', 0)))

    if verbose:
        print(f"\n  Phase 2 Complete: {len(all_results)} total discoveries")
        if all_results:
            top = all_results[0]
            print(f"  Best: train={top['train_edge']*100:+.2f}%, "
                  f"test={top['test_edge']*100:+.2f}%")

    return all_results[:20]


def run_fusion(backtester: RollingBacktester,
               phase1_results: List[Dict],
               strategies: Dict[str, Callable],
               test_periods: int = 150,
               top_n: int = 15,
               verbose: bool = True) -> Dict:
    """
    策略融合測試
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  策略融合測試 (Strategy Fusion)")
        print(f"{'='*60}")

    fusioner = StrategyFusion(backtester)

    # Select top strategies
    sorted_results = sorted(phase1_results,
                            key=lambda x: -x.get('primary_edge_pct', 0))
    top_names = [r['name'] for r in sorted_results[:top_n]]
    top_strategies = {name: strategies[name] for name in top_names if name in strategies}

    if len(top_strategies) < 2:
        if verbose:
            print("  Not enough strategies for fusion testing")
        return {}

    fusion_results = {}

    # Pairs
    if verbose:
        print(f"\n  Testing strategy pairs (top {min(top_n, len(top_strategies))})")
    try:
        pairs = fusioner.test_all_pairs(top_strategies, test_periods=test_periods,
                                         max_pairs=100, verbose=verbose)
        fusion_results['pairs'] = pairs
        if verbose:
            print(f"  {len(pairs)} pairs evaluated")
    except Exception as e:
        if verbose:
            print(f"  Pairs error: {e}")
        fusion_results['pairs'] = []

    # Triples (only top 10)
    top10 = {k: v for i, (k, v) in enumerate(top_strategies.items()) if i < 10}
    if len(top10) >= 3:
        if verbose:
            print(f"\n  Testing strategy triples (top {len(top10)})")
        try:
            triples = fusioner.test_all_triples(top10, test_periods=test_periods,
                                                 max_triples=50, verbose=verbose)
            fusion_results['triples'] = triples
            if verbose:
                print(f"  {len(triples)} triples evaluated")
        except Exception as e:
            if verbose:
                print(f"  Triples error: {e}")
            fusion_results['triples'] = []

    # Voting Ensemble
    if verbose:
        print("\n  Testing voting ensemble")
    try:
        top5 = {k: v for i, (k, v) in enumerate(top_strategies.items()) if i < 5}
        vote_result = fusioner.voting_ensemble_backtest(top5, test_periods=test_periods,
                                                        threshold=3)
        fusion_results['voting'] = {
            'name': f"VOTE(n={len(top5)},t=3)",
            'edge_pct': vote_result.edge_pct,
            'z_score': vote_result.z_score,
            'p_value': vote_result.p_value,
            'n_bets': vote_result.n_bets,
            'result': vote_result.to_dict(),
        }
        if verbose:
            print(f"  Voting: edge={vote_result.edge_pct:+.2f}%")
    except Exception as e:
        if verbose:
            print(f"  Voting error: {e}")

    # Conditional Switching
    if verbose:
        print("  Testing conditional switching")
    try:
        switch_result = fusioner.conditional_switching_backtest(
            top_strategies, test_periods=test_periods)
        fusion_results['switching'] = {
            'name': 'COND_SWITCH',
            'edge_pct': switch_result.edge_pct,
            'z_score': switch_result.z_score,
            'p_value': switch_result.p_value,
            'n_bets': switch_result.n_bets,
            'result': switch_result.to_dict(),
        }
        if verbose:
            print(f"  Switching: edge={switch_result.edge_pct:+.2f}%")
    except Exception as e:
        if verbose:
            print(f"  Switching error: {e}")

    # Dynamic Weight
    if verbose:
        print("  Testing dynamic weight")
    try:
        top5 = {k: v for i, (k, v) in enumerate(top_strategies.items()) if i < 5}
        dyn_result = fusioner.dynamic_weight_backtest(top5, test_periods=test_periods)
        fusion_results['dynamic'] = {
            'name': 'DYN_WEIGHT',
            'edge_pct': dyn_result.edge_pct,
            'z_score': dyn_result.z_score,
            'p_value': dyn_result.p_value,
            'n_bets': dyn_result.n_bets,
            'result': dyn_result.to_dict(),
        }
        if verbose:
            print(f"  Dynamic: edge={dyn_result.edge_pct:+.2f}%")
    except Exception as e:
        if verbose:
            print(f"  Dynamic error: {e}")

    return fusion_results


def run_overfitting_checks(backtester: RollingBacktester,
                            phase1_results: List[Dict],
                            strategies: Dict[str, Callable],
                            test_periods: int = 150,
                            top_n: int = 10,
                            n_shuffles: int = 100,
                            verbose: bool = True) -> Dict:
    """
    對 top N 策略做過擬合檢查
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  過擬合防護檢查 (Overfitting Protection)")
        print(f"  top_n={top_n}, n_shuffles={n_shuffles}")
        print(f"{'='*60}")

    sorted_results = sorted(phase1_results,
                            key=lambda x: -x.get('primary_edge_pct', 0))
    top_names = [r['name'] for r in sorted_results[:top_n]]

    results = {'permutation': {}, 'noise': {}, 'time_split': {}, 'multi_seed': {}}

    for name in top_names:
        if name not in strategies:
            continue
        func = strategies[name]

        if verbose:
            print(f"\n  Checking: {name}")

        # Permutation test
        try:
            perm = backtester.permutation_test(func, test_periods=test_periods,
                                                n_shuffles=n_shuffles,
                                                strategy_name=name)
            results['permutation'][name] = perm
            if verbose:
                print(f"    Permutation: p={perm['p_value']:.3f}, "
                      f"d={perm['cohens_d']:.2f}, verdict={perm['verdict']}")
        except Exception as e:
            if verbose:
                print(f"    Permutation error: {e}")

        # Noise robustness
        try:
            noise = backtester.noise_robustness_test(func, test_periods=test_periods,
                                                      strategy_name=name)
            results['noise'][name] = noise
            if verbose:
                print(f"    Noise robust: {noise['overall_robust']}")
        except Exception as e:
            if verbose:
                print(f"    Noise error: {e}")

        # Time series split
        try:
            ts = backtester.time_series_split_validation(func, n_splits=3,
                                                          strategy_name=name)
            results['time_split'][name] = ts
            if verbose:
                print(f"    Time split consistent: {ts['consistent']}, "
                      f"mean_edge={ts['mean_edge']*100:+.2f}%")
        except Exception as e:
            if verbose:
                print(f"    Time split error: {e}")

        # Multi-seed
        try:
            ms = backtester.run_multi_seed(func, test_periods=test_periods,
                                            strategy_name=name)
            results['multi_seed'][name] = ms
            if verbose:
                print(f"    Multi-seed: mean={ms['mean_edge']*100:+.2f}%, "
                      f"std={ms['std_edge']*100:.2f}%")
        except Exception as e:
            if verbose:
                print(f"    Multi-seed error: {e}")

    return results


def run_decay_filter(backtester: RollingBacktester,
                     phase1_results: List[Dict],
                     strategies: Dict[str, Callable],
                     top_n: int = 10,
                     windows: List[int] = None,
                     verbose: bool = True) -> Dict:
    """
    衰減偵測篩選 (Decay Filter)
    對 Phase 1 top N 策略跑 multi-window decay test，
    將 DECAYING 策略從排行榜降級。
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"  衰減偵測篩選 (Decay Filter)")
        print(f"  windows={windows or [50, 150, 500, 1500]}")
        print(f"{'='*60}")

    sorted_results = sorted(phase1_results,
                            key=lambda x: -x.get('primary_edge_pct', 0))
    top_names = [r['name'] for r in sorted_results[:top_n]
                 if r.get('primary_edge_pct', 0) > 0]

    decay_results = {}
    for name in top_names:
        if name not in strategies:
            continue
        func = strategies[name]

        try:
            dt = backtester.decay_test(func, windows=windows, strategy_name=name)
            decay_results[name] = dt
            trajectory = ' → '.join(f"{e:+.2f}%" for e in dt['edge_trajectory'])
            if verbose:
                print(f"  {name}: [{trajectory}] → {dt['verdict']}"
                      f" {'✓ ADOPT' if dt['adoptable'] else '✗ REJECT'}")
        except Exception as e:
            if verbose:
                print(f"  {name}: ERROR - {e}")

    n_adoptable = sum(1 for d in decay_results.values() if d.get('adoptable'))
    n_decaying = sum(1 for d in decay_results.values()
                     if d.get('verdict') == 'DECAYING')
    if verbose:
        print(f"\n  Summary: {n_adoptable} adoptable, "
              f"{n_decaying} decaying, {len(decay_results)} tested")

    return decay_results


def run_phase3(backtester: RollingBacktester,
               test_periods: int = 150,
               quick: bool = False,
               verbose: bool = True) -> List[Dict]:
    """
    Phase 3: 極限搜尋研究AI
    6 大類別策略 + 7 項搜尋升級
    條件策略支援（返回 [] = 跳過此期）
    """
    scorer = StrategyScorer()

    if quick:
        p3_strategies = build_phase3_quick()
    else:
        p3_strategies = build_phase3_strategies()

    total = len(p3_strategies)
    if verbose:
        stats = count_strategies()
        print(f"\n{'='*60}")
        print(f"  Phase 3: 極限搜尋研究AI")
        print(f"  {total} strategies ({stats['categories']})")
        print(f"  test_periods={test_periods}")
        print(f"{'='*60}")

    results = []
    conditional_stats = {'total_conditional': 0, 'total_skipped_draws': 0}

    for idx, (name, func) in enumerate(p3_strategies.items()):
        try:
            result = backtester.run(func, test_periods=test_periods,
                                    strategy_name=name)

            # 偵測條件策略 (有跳過的期)
            bet_frequency = result.total_valid / test_periods if test_periods > 0 else 1.0
            is_conditional = bet_frequency < 0.95

            # Score
            score = scorer.score(result)
            category = _categorize_p3_strategy(name)

            entry = {
                'name': name,
                'category': category,
                'primary_result': result.to_dict(),
                'primary_edge_pct': result.edge_pct,
                'scores': score.to_dict(),
                'is_conditional': is_conditional,
                'bet_frequency': bet_frequency,
                'expected_edge_per_draw': result.edge_pct * bet_frequency / 100,
            }
            results.append(entry)

            if is_conditional:
                conditional_stats['total_conditional'] += 1
                conditional_stats['total_skipped_draws'] += test_periods - result.total_valid

            if verbose and (idx + 1) % 10 == 0:
                cond_tag = f" [COND freq={bet_frequency:.0%}]" if is_conditional else ""
                print(f"  [{idx+1}/{total}] {name}: "
                      f"edge={result.edge_pct:+.2f}%, z={result.z_score:.2f}"
                      f"{cond_tag}")

        except Exception as e:
            if verbose:
                print(f"  [{idx+1}/{total}] {name}: ERROR - {e}")
            continue

    results.sort(key=lambda x: -x.get('primary_edge_pct', 0))

    if verbose:
        print(f"\n  Phase 3 Complete: {len(results)}/{total} strategies evaluated")
        print(f"  Conditional strategies: {conditional_stats['total_conditional']}")
        if results:
            top = results[0]
            cond = " [CONDITIONAL]" if top.get('is_conditional') else ""
            print(f"  Best: {top['name']} edge={top['primary_edge_pct']:+.2f}%{cond}")
        # Show top 5
        print(f"\n  Top 5:")
        for r in results[:5]:
            cond = f" [freq={r['bet_frequency']:.0%}]" if r.get('is_conditional') else ""
            print(f"    {r['name']}: edge={r['primary_edge_pct']:+.2f}%{cond}")

    return results


def _categorize_p3_strategy(name: str) -> str:
    """Phase 3 策略分類"""
    if any(k in name for k in ['stacked', 'borda', 'consensus', 'z_ensemble']):
        return 'UltraWeakSignal'
    if any(k in name for k in ['feat_cross', 'multiplicative', 'quadratic']):
        return 'NonLinearCombo'
    if any(k in name for k in ['skip', 'regime_gated', 'anomaly', 'gap_trigger', 'vol_gate']):
        return 'ConditionalTrigger'
    if any(k in name for k in ['extreme', 'consec_follow', 'drought', 'zone_burst']):
        return 'RareEvent'
    if any(k in name for k in ['drift', 'changepoint', 'kl_drift', 'regime_momentum']):
        return 'NonStationary'
    if any(k in name for k in ['anti_', 'entropy', 'coverage', 'contrarian']):
        return 'CounterIntuitive'
    if any(k in name for k in ['skewness', 'kurtosis', 'pca', 'set_', 'local_peak',
                                'ucb1', 'thompson', 'oe_regime']):
        return 'SearchUpgrade'
    return 'Phase3_Other'


def _categorize_strategy(name: str) -> str:
    """根據策略名稱推斷類別"""
    name_lower = name.lower()
    if any(k in name_lower for k in ['frequency', 'cold_', 'deviation', 'hot_cold', 'echo_p0']):
        return 'Statistical'
    if any(k in name_lower for k in ['bayesian', 'entropy', 'mutual_info', 'surprise', 'mle']):
        return 'Probabilistic'
    if any(k in name_lower for k in ['sum_range', 'odd_even', 'mod_arith', 'prime', 'ac_value']):
        return 'Mathematical'
    if any(k in name_lower for k in ['markov', 'lag2', 'pattern', 'cycle']):
        return 'Sequence'
    if any(k in name_lower for k in ['trend', 'adaptive', 'multi_window']):
        return 'Window'
    if any(k in name_lower for k in ['zone', 'tail', 'consec', 'spread']):
        return 'Distribution'
    if any(k in name_lower for k in ['monte', 'constraint', 'weighted_random']):
        return 'MonteCarlo'
    if any(k in name_lower for k in ['random_forest', 'gradient', 'logistic', 'clustering']):
        return 'ML'
    if any(k in name_lower for k in ['voting', 'stacking']):
        return 'Ensemble'
    if any(k in name_lower for k in ['neg_', 'anti_', 'contrarian']):
        return 'Negative'
    if any(k in name_lower for k in ['cooc', 'graph', 'anti_pairs']):
        return 'Graph'
    if any(k in name_lower for k in ['fourier', 'triple_strike', 'ts3']):
        return 'Validated'
    return 'Other'


def main():
    parser = argparse.ArgumentParser(
        description='大樂透 AutoML 探索系統 (BIG_LOTTO AutoML Exploration System)')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3], default=None,
                        help='Run only Phase 1, 2, or 3 (default: all)')
    parser.add_argument('--test-periods', type=int, default=150,
                        help='Number of test periods (default: 150)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: fewer strategies, shorter test')
    parser.add_argument('--full', action='store_true',
                        help='Full mode: all strategies, longer test, more shuffles')
    parser.add_argument('--seed', type=int, default=SEED,
                        help=f'Random seed (default: {SEED})')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON report path')
    parser.add_argument('--no-fusion', action='store_true',
                        help='Skip fusion testing')
    parser.add_argument('--no-overfit-check', action='store_true',
                        help='Skip overfitting checks')
    parser.add_argument('--db-path', type=str, default=None,
                        help='Custom database path')
    parser.add_argument('--verbose', action='store_true', default=True,
                        help='Verbose output (default: True)')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress verbose output')

    args = parser.parse_args()

    if args.quiet:
        args.verbose = False

    # Quick/Full mode adjustments
    if args.quick:
        args.test_periods = min(args.test_periods, 50)
    if args.full and args.test_periods < 500:
        args.test_periods = 500

    # Default output path
    if args.output is None:
        output_dir = Path(__file__).parent.parent.parent / 'ai_lab' / 'automl_biglotto'
        args.output = str(output_dir / 'report_output.json')

    np.random.seed(args.seed)

    print("\n" + "=" * 60)
    print("  大樂透 AutoML 探索系統")
    print("  BIG_LOTTO AutoML Exploration System")
    print("=" * 60)
    print(f"  Mode: {'Quick' if args.quick else 'Full' if args.full else 'Standard'}")
    print(f"  Test Periods: {args.test_periods}")
    print(f"  Seed: {args.seed}")
    print(f"  Phase: {args.phase if args.phase else 'Both'}")
    print(f"  Output: {args.output}")

    # Initialize
    start_time = time.time()

    if args.verbose:
        print("\n  Loading data...")
    backtester = RollingBacktester(db_path=args.db_path)
    all_draws = backtester.all_draws
    if args.verbose:
        print(f"  Loaded {len(all_draws)} draws")

    report_gen = ReportGenerator(total_draws=len(all_draws), seed=args.seed)

    # Build strategies
    if args.quick:
        strategies = build_quick_strategies()
    else:
        strategies = build_all_strategies()
    if args.verbose:
        print(f"  Built {len(strategies)} strategy configurations")

    # === Phase 1 ===
    phase1_results = []
    if args.phase is None or args.phase == 1:
        phase1_results = run_phase1(
            backtester, strategies,
            test_periods=args.test_periods,
            multi_window=not args.quick,
            verbose=args.verbose)

    # === Phase 2 ===
    phase2_results = []
    if args.phase is None or args.phase == 2:
        gp_pop = 50 if args.quick else (GP_POPULATION if not args.full else 200)
        gp_gen = 20 if args.quick else (GP_GENERATIONS if not args.full else 80)
        n_linear = 100 if args.quick else (500 if not args.full else 1000)

        phase2_results = run_phase2(
            backtester, all_draws,
            test_periods=args.test_periods,
            gp_population=gp_pop,
            gp_generations=gp_gen,
            n_linear=n_linear,
            verbose=args.verbose)

    # === Phase 3: 極限搜尋研究AI ===
    phase3_results = []
    if args.phase is None or args.phase == 3:
        phase3_results = run_phase3(
            backtester,
            test_periods=args.test_periods,
            quick=args.quick,
            verbose=args.verbose)

        # Merge Phase 3 into Phase 1 results for fusion/decay
        if phase3_results:
            p3_strategies = build_phase3_quick() if args.quick else build_phase3_strategies()
            strategies.update(p3_strategies)
            phase1_results.extend(phase3_results)

    # === Fusion ===
    fusion_results = {}
    if not args.no_fusion and phase1_results and (args.phase is None or args.phase == 1):
        top_n_fusion = 10 if args.quick else 15
        fusion_results = run_fusion(
            backtester, phase1_results, strategies,
            test_periods=args.test_periods,
            top_n=top_n_fusion,
            verbose=args.verbose)

    # === Overfitting Checks ===
    overfitting_results = {}
    if not args.no_overfit_check and phase1_results and (args.phase is None or args.phase == 1):
        top_n_check = 5 if args.quick else 10
        n_shuffles = 30 if args.quick else (100 if not args.full else 200)
        overfitting_results = run_overfitting_checks(
            backtester, phase1_results, strategies,
            test_periods=args.test_periods,
            top_n=top_n_check,
            n_shuffles=n_shuffles,
            verbose=args.verbose)

    # === Decay Filter (multi-window longevity check) ===
    decay_results = {}
    if not args.no_overfit_check and phase1_results and (args.phase is None or args.phase == 1):
        decay_top = 5 if args.quick else 10
        decay_windows = [50, 150, 500] if args.quick else [50, 150, 500, 1500]
        decay_results = run_decay_filter(
            backtester, phase1_results, strategies,
            top_n=decay_top,
            windows=decay_windows,
            verbose=args.verbose)
        # Inject decay verdicts into overfitting_results for report
        overfitting_results['decay'] = decay_results

    # === Report ===
    if args.verbose:
        print(f"\n{'='*60}")
        print(f"  Generating Report...")
        print(f"{'='*60}")

    report = report_gen.generate_json_report(
        phase1_results=phase1_results,
        phase2_results=phase2_results,
        fusion_results=fusion_results,
        overfitting_results=overfitting_results,
        output_path=args.output)

    report_gen.print_console_report(report)

    elapsed = time.time() - start_time
    print(f"\nTotal runtime: {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"Report saved to: {args.output}")


if __name__ == '__main__':
    main()
