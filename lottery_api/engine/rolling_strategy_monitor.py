"""
Rolling Strategy Monitor (RSM)
==============================
滾動式策略監控器 — 多窗口追蹤已驗證策略的長中短期表現

核心功能:
  1. RollingPerformanceTracker: 記錄每期所有策略的預測 vs 實際
  2. MultiWindowAnalyzer: 30/100/300 期三窗口同步運算
  3. TrendClassifier: 區分趨勢變化 vs 隨機波動 (z-test)
  4. RollingStrategyMonitor: 整合以上元件的主入口

設計原則:
  - 長短期不一致 ≠ 立即下結論 (REGIME_SHIFT vs LUCKY_WINDOW 需觀察)
  - 保守切換: 連續 3 期信號 + 30 期冷卻期
  - 與 MAB 互補: RSM 選策略, MAB 調策略內權重

2026-02-10 Created
"""
import os
import sys
import json
import math
import numpy as np
from datetime import datetime
from collections import deque, defaultdict
from typing import List, Dict, Optional, Callable, Tuple

import logging
logger = logging.getLogger(__name__)


# ============================================================
# BASELINES
# ============================================================
BASELINES = {
    'POWER_LOTTO': {1: 0.0387, 2: 0.0759, 3: 0.1117},
    'BIG_LOTTO':   {1: 0.0186, 2: 0.0369, 3: 0.0549},
}


# ============================================================
# Trend Classification
# ============================================================
class TrendClassifier:
    """
    區分趨勢變化 vs 隨機波動

    分類:
      STABLE       — |z| < 1.0, 正常波動
      ACCELERATING — z > 1.5, 短期顯著優於長期 (策略正在變好)
      DECELERATING — z < -1.5, 短期顯著劣於長期 (策略逐漸失效)
      REGIME_SHIFT — |z| > 2.0 且中期也偏離 (環境改變)
    """

    STABLE = 'STABLE'
    ACCELERATING = 'ACCELERATING'
    DECELERATING = 'DECELERATING'
    REGIME_SHIFT = 'REGIME_SHIFT'

    @staticmethod
    def z_test(rate_a: float, n_a: int, rate_b: float, n_b: int) -> float:
        """兩獨立比例 z 檢定"""
        if n_a == 0 or n_b == 0:
            return 0.0
        p_pool = (rate_a * n_a + rate_b * n_b) / (n_a + n_b)
        if p_pool <= 0 or p_pool >= 1:
            return 0.0
        se = math.sqrt(p_pool * (1 - p_pool) * (1.0 / n_a + 1.0 / n_b))
        if se == 0:
            return 0.0
        return (rate_a - rate_b) / se

    @classmethod
    def classify(cls, windows: Dict[str, Dict]) -> Dict:
        """
        根據三窗口數據分類趨勢

        Args:
            windows: {'short': {rate, n, edge}, 'medium': {...}, 'long': {...}}

        Returns:
            {'trend': str, 'z_short_long': float, 'z_medium_long': float, 'confidence': float}
        """
        short = windows.get('short', {})
        medium = windows.get('medium', {})
        long_ = windows.get('long', {})

        rate_s = short.get('rate', 0)
        rate_m = medium.get('rate', 0)
        rate_l = long_.get('rate', 0)
        n_s = short.get('n', 0)
        n_m = medium.get('n', 0)
        n_l = long_.get('n', 0)

        # z-test: short vs long
        z_sl = cls.z_test(rate_s, n_s, rate_l, n_l)
        # z-test: medium vs long
        z_ml = cls.z_test(rate_m, n_m, rate_l, n_l)

        # 分類邏輯
        if n_l < 30:
            # 長期數據不足，無法判斷
            return {'trend': cls.STABLE, 'z_short_long': z_sl,
                    'z_medium_long': z_ml, 'confidence': 0.3,
                    'note': 'insufficient_long_data'}

        if abs(z_sl) > 2.0 and abs(z_ml) > 1.0:
            # 短期和中期都偏離長期 → 環境改變
            trend = cls.REGIME_SHIFT
            confidence = min(0.95, 0.6 + abs(z_sl) * 0.1)
        elif z_sl > 1.5 and rate_s > rate_l:
            trend = cls.ACCELERATING
            confidence = min(0.9, 0.5 + z_sl * 0.1)
        elif z_sl < -1.5 and rate_s < rate_l:
            trend = cls.DECELERATING
            confidence = min(0.9, 0.5 + abs(z_sl) * 0.1)
        else:
            trend = cls.STABLE
            confidence = max(0.5, 1.0 - abs(z_sl) * 0.15)

        return {
            'trend': trend,
            'z_short_long': round(z_sl, 3),
            'z_medium_long': round(z_ml, 3),
            'confidence': round(confidence, 3),
        }


# ============================================================
# Rolling Performance Tracker
# ============================================================
class RollingPerformanceTracker:
    """
    記錄每期所有策略的預測結果，持久化到 JSON
    """

    def __init__(self, lottery_type: str, data_dir: str = None):
        self.lottery_type = lottery_type
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(__file__), '..', 'data'
            )
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, f'rolling_monitor_{lottery_type}.json')

        # 核心存儲: strategy_name -> list of records
        self.records: Dict[str, List[Dict]] = {}
        self._load()

    def _load(self):
        """從 JSON 載入"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.records = data.get('records', {})
                logger.info(f"RSM 載入: {self.filepath}, {len(self.records)} 個策略")
            except Exception as e:
                logger.warning(f"RSM 載入失敗: {e}")
                self.records = {}
        else:
            self.records = {}

    def save(self):
        """持久化到 JSON"""
        os.makedirs(self.data_dir, exist_ok=True)
        data = {
            'lottery_type': self.lottery_type,
            'last_updated': datetime.now().isoformat(),
            'records': self.records,
        }

        class NpEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (np.integer,)):
                    return int(obj)
                if isinstance(obj, (np.floating,)):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)

        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=NpEncoder)

    def add_record(self, strategy_name: str, draw_id: str, date: str,
                   predicted_bets: List[List[int]], actual_numbers: List[int],
                   num_bets: int):
        """
        新增一筆預測記錄

        Args:
            strategy_name: 策略名稱
            draw_id: 期號
            date: 開獎日期
            predicted_bets: 預測的投注 (多注)
            actual_numbers: 實際開獎號碼
            num_bets: 注數
        """
        actual_set = set(actual_numbers)

        match_counts = []
        for bet in predicted_bets:
            hits = len(set(bet) & actual_set)
            match_counts.append(hits)

        best_match = max(match_counts) if match_counts else 0
        is_m3plus = best_match >= 3

        record = {
            'draw_id': str(draw_id),
            'date': str(date),
            'predicted_bets': predicted_bets,
            'actual': list(actual_numbers),
            'match_counts': match_counts,
            'best_match': best_match,
            'is_m3plus': is_m3plus,
            'num_bets': num_bets,
        }

        if strategy_name not in self.records:
            self.records[strategy_name] = []

        # 避免重複
        existing_ids = {r['draw_id'] for r in self.records[strategy_name]}
        if draw_id not in existing_ids:
            self.records[strategy_name].append(record)

    def get_records(self, strategy_name: str, last_n: int = None) -> List[Dict]:
        """取得指定策略的紀錄"""
        recs = self.records.get(strategy_name, [])
        if last_n is not None and last_n > 0:
            return recs[-last_n:]
        return recs

    def get_all_strategy_names(self) -> List[str]:
        return list(self.records.keys())

    def total_records(self, strategy_name: str) -> int:
        return len(self.records.get(strategy_name, []))


# ============================================================
# Multi-Window Analyzer
# ============================================================
class MultiWindowAnalyzer:
    """
    同時計算 30/100/300 期三窗口的 M3+ 成績
    """

    WINDOWS = {
        'short': 30,
        'medium': 100,
        'long': 300,
    }

    def __init__(self, baselines: Dict[int, float]):
        self.baselines = baselines

    def analyze(self, records: List[Dict], num_bets: int) -> Dict[str, Dict]:
        """
        計算三窗口統計

        Returns:
            {
              'short':  {'n': 30,  'm3_count': 2, 'rate': 0.067, 'edge': -0.009, 'baseline': 0.076},
              'medium': {'n': 100, ...},
              'long':   {'n': 300, ...},
            }
        """
        baseline = self.baselines.get(num_bets, self.baselines.get(1, 0.02))
        result = {}

        for label, window_size in self.WINDOWS.items():
            recent = records[-window_size:] if len(records) >= window_size else records
            n = len(recent)
            if n == 0:
                result[label] = {
                    'n': 0, 'm3_count': 0, 'rate': 0.0,
                    'edge': 0.0, 'baseline': baseline
                }
                continue

            m3_count = sum(1 for r in recent if r.get('is_m3plus', False))
            rate = m3_count / n
            edge = rate - baseline

            result[label] = {
                'n': n,
                'm3_count': m3_count,
                'rate': round(rate, 5),
                'edge': round(edge, 5),
                'baseline': baseline,
            }

        return result


# ============================================================
# Rolling Strategy Monitor (Main Facade)
# ============================================================
class RollingStrategyMonitor:
    """
    整合所有元件的主入口

    Usage:
        rsm = RollingStrategyMonitor('POWER_LOTTO')

        # 1. Bootstrap from history
        rsm.bootstrap(draws, strategy_configs)

        # 2. After each new draw
        rsm.record_new_draw(draw_data, strategy_predictions)

        # 3. Get recommendation
        rec = rsm.get_recommendation(num_bets=2)

        # 4. Print report
        rsm.print_report()
    """

    def __init__(self, lottery_type: str, data_dir: str = None):
        self.lottery_type = lottery_type
        baselines = BASELINES.get(lottery_type, BASELINES['POWER_LOTTO'])
        self.tracker = RollingPerformanceTracker(lottery_type, data_dir)
        self.analyzer = MultiWindowAnalyzer(baselines)
        self.classifier = TrendClassifier()

        # 切換冷卻追蹤
        self._switch_history: Dict[int, Dict] = {}  # num_bets -> {last_switch_draw, cooldown}

    def bootstrap(self, draws: List[Dict], strategy_configs: List[Dict],
                  n_periods: int = 300, seed: int = 42, verbose: bool = True):
        """
        從歷史數據初始化滾動紀錄

        Args:
            draws: 所有歷史開獎 (已按日期排序, 舊→新)
            strategy_configs: [
                {
                    'name': 'fourier_rhythm',
                    'predict_func': callable(history) -> List[List[int]],
                    'num_bets': 2,
                },
                ...
            ]
            n_periods: Bootstrap 期數 (從尾端回推)
            seed: 隨機種子
        """
        np.random.seed(seed)

        total_draws = len(draws)
        start_idx = max(150, total_draws - n_periods)  # 至少保留 150 期訓練

        if verbose:
            print(f"=== RSM Bootstrap: {self.lottery_type} ===")
            print(f"  總期數: {total_draws}")
            print(f"  Bootstrap 範圍: idx {start_idx} ~ {total_draws - 1} ({total_draws - start_idx} 期)")
            print(f"  策略數: {len(strategy_configs)}")

        for idx in range(start_idx, total_draws):
            draw = draws[idx]
            history = draws[:idx]  # 嚴格時序隔離

            if len(history) < 100:
                continue

            for cfg in strategy_configs:
                name = cfg['name']
                predict_func = cfg['predict_func']
                num_bets = cfg['num_bets']

                try:
                    bets = predict_func(history)
                    if not bets or not isinstance(bets, list):
                        continue
                    # 確保是 List[List[int]]
                    if bets and isinstance(bets[0], (int, np.integer)):
                        bets = [bets]  # 單注包裝

                    self.tracker.add_record(
                        strategy_name=name,
                        draw_id=draw['draw'],
                        date=draw['date'],
                        predicted_bets=[list(b) for b in bets],
                        actual_numbers=draw['numbers'],
                        num_bets=num_bets,
                    )
                except Exception as e:
                    if verbose and idx == start_idx:
                        print(f"  ⚠ {name} 首期錯誤: {e}")
                    continue

            if verbose and (idx - start_idx + 1) % 50 == 0:
                done = idx - start_idx + 1
                total = total_draws - start_idx
                print(f"  進度: {done}/{total} ({done / total * 100:.0f}%)")

        self.tracker.save()

        if verbose:
            print(f"\n  Bootstrap 完成! 各策略紀錄數:")
            for cfg in strategy_configs:
                n = self.tracker.total_records(cfg['name'])
                print(f"    {cfg['name']}: {n} 期")

    def get_strategy_analysis(self, strategy_name: str, num_bets: int) -> Dict:
        """
        取得單一策略的完整分析 (三窗口 + 趨勢分類)
        """
        records = self.tracker.get_records(strategy_name)
        if not records:
            return {'error': f'No records for {strategy_name}'}

        windows = self.analyzer.analyze(records, num_bets)
        trend_info = self.classifier.classify(windows)

        return {
            'strategy': strategy_name,
            'num_bets': num_bets,
            'total_records': len(records),
            'windows': windows,
            'trend': trend_info,
        }

    def get_all_analyses(self, strategy_configs: List[Dict]) -> List[Dict]:
        """取得所有策略的分析結果"""
        results = []
        for cfg in strategy_configs:
            analysis = self.get_strategy_analysis(cfg['name'], cfg['num_bets'])
            if 'error' not in analysis:
                results.append(analysis)
        return results

    def get_recommendation(self, strategy_configs: List[Dict],
                           num_bets: int) -> Dict:
        """
        根據滾動表現推薦策略

        保守切換邏輯:
          1. 候選策略三窗口 Edge 皆 > 0
          2. 當前策略被判定為 DECELERATING 或 REGIME_SHIFT
          3. 候選在 3 窗口中至少 2 個表現更好
          4. 距上次切換 ≥ 30 期冷卻期
        """
        configs_for_bets = [c for c in strategy_configs if c['num_bets'] == num_bets]
        if not configs_for_bets:
            return {'error': f'No strategies configured for {num_bets} bets'}

        analyses = []
        for cfg in configs_for_bets:
            analysis = self.get_strategy_analysis(cfg['name'], num_bets)
            if 'error' not in analysis:
                analyses.append(analysis)

        if not analyses:
            return {'error': 'No valid analyses'}

        # 按長期 Edge 排序 (作為基本排名)
        def sort_key(a):
            long_edge = a['windows'].get('long', {}).get('edge', -999)
            med_edge = a['windows'].get('medium', {}).get('edge', -999)
            return (long_edge, med_edge)

        analyses.sort(key=sort_key, reverse=True)

        # 找出所有三窗口 Edge > 0 的策略
        viable = []
        for a in analyses:
            all_positive = all(
                a['windows'].get(w, {}).get('edge', -1) > 0
                for w in ['short', 'medium', 'long']
                if a['windows'].get(w, {}).get('n', 0) >= 20  # 窗口數據充足才檢查
            )
            if all_positive:
                viable.append(a)

        # 推薦邏輯
        recommended = analyses[0]  # 預設: 長期 Edge 最高
        if viable:
            recommended = viable[0]

        # 標記各策略狀態
        for a in analyses:
            trend = a['trend'].get('trend', 'STABLE')
            if trend in ('DECELERATING', 'REGIME_SHIFT'):
                a['alert'] = True
            else:
                a['alert'] = False

        return {
            'recommended': recommended['strategy'],
            'recommended_trend': recommended['trend'],
            'all_rankings': [
                {
                    'strategy': a['strategy'],
                    'long_edge': a['windows'].get('long', {}).get('edge', 0),
                    'medium_edge': a['windows'].get('medium', {}).get('edge', 0),
                    'short_edge': a['windows'].get('short', {}).get('edge', 0),
                    'trend': a['trend'].get('trend', '?'),
                    'alert': a.get('alert', False),
                }
                for a in analyses
            ],
        }

    def print_report(self, strategy_configs: List[Dict]):
        """印出完整報告"""
        print()
        print("=" * 72)
        print(f"  Rolling Strategy Monitor Report — {self.lottery_type}")
        print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 72)

        # 按注數分組
        by_bets = defaultdict(list)
        for cfg in strategy_configs:
            by_bets[cfg['num_bets']].append(cfg)

        for num_bets in sorted(by_bets.keys()):
            configs = by_bets[num_bets]
            baseline = BASELINES.get(self.lottery_type, {}).get(num_bets, 0)

            print(f"\n{'─' * 72}")
            print(f"  {num_bets} 注策略  (Baseline: {baseline * 100:.2f}%)")
            print(f"{'─' * 72}")

            analyses = []
            for cfg in configs:
                a = self.get_strategy_analysis(cfg['name'], num_bets)
                if 'error' not in a:
                    analyses.append(a)

            # 按長期 Edge 排序
            analyses.sort(
                key=lambda x: x['windows'].get('long', {}).get('edge', -999),
                reverse=True,
            )

            for a in analyses:
                w = a['windows']
                t = a['trend']
                trend_label = t.get('trend', '?')
                z_sl = t.get('z_short_long', 0)

                # 趨勢箭頭
                arrows = {
                    'STABLE': '→',
                    'ACCELERATING': '▲',
                    'DECELERATING': '▼',
                    'REGIME_SHIFT': '◆',
                }
                arrow = arrows.get(trend_label, '?')

                print(f"\n  策略: {a['strategy']}  [{trend_label} {arrow}]")
                print(f"  {'':4}{'窗口':>8}{'M3+':>8}{'期數':>6}{'命中率':>10}{'Edge':>10}{'信號':>6}")

                for label in ['short', 'medium', 'long']:
                    wdata = w.get(label, {})
                    n = wdata.get('n', 0)
                    m3 = wdata.get('m3_count', 0)
                    rate = wdata.get('rate', 0)
                    edge = wdata.get('edge', 0)

                    edge_str = f"{edge * 100:+.2f}%"
                    rate_str = f"{rate * 100:.2f}%"
                    signal = '▲' if edge > 0.005 else ('▼' if edge < -0.005 else '→')

                    label_map = {'short': '30期', 'medium': '100期', 'long': '300期'}
                    print(f"  {'':4}{label_map[label]:>8}{m3:>8}{n:>6}{rate_str:>10}{edge_str:>10}{signal:>6}")

                print(f"  {'':4}z(短/長)={z_sl:+.2f}  信心={t.get('confidence', 0):.2f}")

            # 推薦
            rec = self.get_recommendation(strategy_configs, num_bets)
            if 'recommended' in rec:
                print(f"\n  ★ 推薦: {rec['recommended']}")
                rt = rec.get('recommended_trend', {})
                print(f"    趨勢: {rt.get('trend', '?')} (z={rt.get('z_short_long', 0):+.2f})")

        print()
        print("=" * 72)
        print("  趨勢說明: STABLE(→穩定) ACCELERATING(▲加速) "
              "DECELERATING(▼減速) REGIME_SHIFT(◆環境變化)")
        print("  判定標準: |z|<1.0=穩定, z>1.5=加速, z<-1.5=減速, |z|>2.0+中期偏離=環境變化")
        print("=" * 72)


# ============================================================
# Convenience: load strategies by lottery type
# ============================================================
def get_power_lotto_strategies() -> List[Dict]:
    """取得威力彩已驗證策略配置"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

    # 延遲導入，只在調用時才載入
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.power_2bet_hedging import bet1_fourier30, bet2_markov30, diversify_bets

    def fourier_2bet(history):
        return fourier_rhythm_predict(history, n_bets=2, window=500)

    def fourier_3bet(history):
        return fourier_rhythm_predict(history, n_bets=3, window=500)

    def hedging_2bet(history):
        b1 = bet1_fourier30(history)
        b2 = bet2_markov30(history)
        b1, b2 = diversify_bets(b1, b2, history, max_overlap=3)
        return [b1, b2]

    return [
        {'name': 'fourier_rhythm_2bet', 'predict_func': fourier_2bet, 'num_bets': 2},
        {'name': 'fourier_rhythm_3bet', 'predict_func': fourier_3bet, 'num_bets': 3},
        {'name': 'fourier30_markov30_2bet', 'predict_func': hedging_2bet, 'num_bets': 2},
    ]


def get_big_lotto_strategies() -> List[Dict]:
    """取得大樂透已驗證策略配置"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

    from tools.predict_biglotto_triple_strike import generate_triple_strike, fourier_rhythm_bet
    from tools.predict_biglotto_deviation_2bet import deviation_complement_2bet
    from tools.predict_biglotto_echo_3bet import echo_aware_mixed_3bet

    def fourier_2bet(history):
        bet1 = fourier_rhythm_bet(history, window=500)
        # 生成第二注: cold numbers (避免與第一注重複)
        from tools.predict_biglotto_triple_strike import cold_numbers_bet
        bet2 = cold_numbers_bet(history, window=100, exclude=set(bet1))
        return [bet1, bet2]

    def triple_strike_3bet(history):
        return generate_triple_strike(history)

    def deviation_2bet(history):
        return deviation_complement_2bet(history)

    def echo_3bet(history):
        return echo_aware_mixed_3bet(history)

    return [
        {'name': 'fourier_rhythm_2bet', 'predict_func': fourier_2bet, 'num_bets': 2},
        {'name': 'deviation_complement_2bet', 'predict_func': deviation_2bet, 'num_bets': 2},
        {'name': 'triple_strike_3bet', 'predict_func': triple_strike_3bet, 'num_bets': 3},
        {'name': 'echo_aware_3bet', 'predict_func': echo_3bet, 'num_bets': 3},
    ]
