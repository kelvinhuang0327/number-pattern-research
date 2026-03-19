"""
Strategy Coordinator — 多智能體評分聚合器
==========================================
Phase 3 核心：各策略 Agent 對所有號碼評分，
Coordinator 按 RSM 30p Edge 加權聚合，輸出最終選號。

核心設計：
  1. 每個 Agent 輸出「全號碼評分 dict」，不只是 top-N
  2. Coordinator 將分數正規化 0~1 後加權求和
  3. 權重來自 StrategyStateStore 的 RSM 30p Edge（負 Edge → 權重=0）
  4. 最終從聚合分數中按排名切分多注（零重疊）

差異說明（vs 現有架構）：
  - 現有：pick ONE strategy → 各注獨立
  - Coordinator：ALL agents 共同定義號碼優先序 → 各注從同一排名切片

2026-03-12 Created (Phase 3-A, MiroFish Phase 3)
"""
import os
import sys
import json

import numpy as np
import logging
from collections import Counter
from typing import Dict, List, Optional, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from numpy.fft import fft, fftfreq
from lottery_api.engine.s2_markov_weibull import markov2_score_all, weibull_gap_score_all

logger = logging.getLogger(__name__)


# ============================================================
# 個別 Agent 評分函數 (全號碼 → {number: score})
# ============================================================

def _acb_score_all(history: list, window: int = 100, max_num: int = 39) -> Dict[int, float]:
    """ACB 全號碼評分：freq_deficit×0.4 + gap_score×0.6 + boundary_bonus"""
    recent = history[-window:] if len(history) >= window else history
    counter = Counter(n for d in recent for n in d['numbers'])
    last_seen = {n: i for i, d in enumerate(recent) for n in d['numbers']}
    expected_freq = len(recent) * 5 / max_num if max_num <= 39 else len(recent) * 6 / max_num
    scores = {}
    for n in range(1, max_num + 1):
        freq_deficit = expected_freq - counter.get(n, 0)
        gap_score = (len(recent) - last_seen.get(n, -1)) / (len(recent) / 2)
        base = freq_deficit * 0.4 + gap_score * 0.6
        boundary = 1.2 if (n <= 8 or n >= max_num - 4) else 1.0
        scores[n] = base * boundary
    return scores


def _fourier_score_all(history: list, window: int = 500, max_num: int = 39) -> Dict[int, float]:
    """Fourier 週期評分：FFT 主頻預測下次出現"""
    h = history[-window:] if len(history) >= window else history
    w = len(h)
    scores = {}
    for n in range(1, max_num + 1):
        bh = np.zeros(w)
        for idx, d in enumerate(h):
            if n in d['numbers']:
                bh[idx] = 1
        if sum(bh) < 2:
            scores[n] = 0.0
            continue
        yf = fft(bh - np.mean(bh))
        xf = fftfreq(w, 1)
        idx_pos = np.where(xf > 0)
        pos_yf = np.abs(yf[idx_pos])
        pos_xf = xf[idx_pos]
        if len(pos_yf) == 0:
            scores[n] = 0.0
            continue
        peak_idx = np.argmax(pos_yf)
        freq_val = pos_xf[peak_idx]
        if freq_val == 0:
            scores[n] = 0.0
            continue
        last_appear = np.where(bh == 1)[0]
        last_idx = last_appear[-1] if len(last_appear) > 0 else -1
        expected_gap = 1.0 / freq_val
        actual_gap = w - 1 - last_idx
        scores[n] = 1.0 / (abs(actual_gap - expected_gap) + 1.0)
    return scores


def _markov_score_all(history: list, window: int = 30, max_num: int = 39) -> Dict[int, float]:
    """Markov 轉移評分：從上期號碼出發的轉移機率"""
    recent = history[-window:] if len(history) >= window else history
    transitions: Dict[int, Counter] = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers']:
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers']:
                transitions[pn][nn] += 1
    scores: Dict[int, float] = {n: 0.0 for n in range(1, max_num + 1)}
    for pn in history[-1]['numbers']:
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, cnt in trans.items():
                scores[n] = scores.get(n, 0.0) + cnt / total
    return scores


def _midfreq_score_all(history: list, window: int = 100, max_num: int = 39) -> Dict[int, float]:
    """中頻評分：偏離期望頻率最小 → 均值回歸信號"""
    recent = history[-window:] if len(history) >= window else history
    expected = len(recent) * 5 / max_num if max_num <= 39 else len(recent) * 6 / max_num
    freq = Counter(n for d in recent for n in d['numbers'])
    max_dev = max(abs(freq.get(n, 0) - expected) for n in range(1, max_num + 1)) or 1.0
    scores = {}
    for n in range(1, max_num + 1):
        dev = abs(freq.get(n, 0) - expected)
        scores[n] = 1.0 - dev / max_dev  # 越接近期望頻率 → 分數越高
    return scores


def _bl_fourier_score_all(history: list, window: int = 500) -> Dict[int, float]:
    """大樂透 Fourier 評分（1-49）"""
    return _fourier_score_all(history, window=window, max_num=49)


def _bl_cold_score_all(history: list, window: int = 100) -> Dict[int, float]:
    """大樂透冷號評分：gap 越大分數越高"""
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    scores = {}
    for n in range(1, 50):
        gap = len(recent) - last_seen.get(n, -1)
        scores[n] = float(gap)
    max_gap = max(scores.values()) or 1.0
    return {n: s / max_gap for n, s in scores.items()}


def _bl_neighbor_score_all(history: list) -> Dict[int, float]:
    """大樂透鄰號評分：上期 ±1 鄰域給高分"""
    scores = {n: 0.0 for n in range(1, 50)}
    prev_nums = history[-1]['numbers']
    for pn in prev_nums:
        for delta in (-1, 0, 1):
            nn = pn + delta
            if 1 <= nn <= 49:
                scores[nn] = scores.get(nn, 0.0) + (1.0 if delta == 0 else 0.7)
    return scores


def _pl_fourier_score_all(history: list, window: int = 500) -> Dict[int, float]:
    """威力彩 Fourier 評分（1-38）"""
    return _fourier_score_all(history, window=window, max_num=38)


def _pl_cold_score_all(history: list, window: int = 100) -> Dict[int, float]:
    """威力彩冷號評分（1-38）"""
    recent = history[-window:] if len(history) >= window else history
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers']:
            last_seen[n] = i
    scores = {}
    for n in range(1, 39):
        gap = len(recent) - last_seen.get(n, -1)
        scores[n] = float(gap)
    max_gap = max(scores.values()) or 1.0
    return {n: s / max_gap for n, s in scores.items()}


# ============================================================
# Normalization
# ============================================================

def _normalize(scores: Dict[int, float]) -> Dict[int, float]:
    """Min-Max 正規化到 0~1"""
    if not scores:
        return scores
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    r = mx - mn
    if r == 0:
        return {n: 0.5 for n in scores}
    return {n: (v - mn) / r for n, v in scores.items()}


def _consensus_score_all(history: list, max_num: int) -> Dict[int, float]:
    """
    Strategy consensus signal:
    agreement across four low-level scorers (acb/midfreq/fourier/markov).
    """
    s1 = _normalize(_acb_score_all(history, window=100, max_num=max_num))
    s2 = _normalize(_midfreq_score_all(history, window=100, max_num=max_num))
    s3 = _normalize(_fourier_score_all(history, window=500, max_num=max_num))
    s4 = _normalize(_markov_score_all(history, window=30, max_num=max_num))

    out: Dict[int, float] = {}
    for n in range(1, max_num + 1):
        vals = [s1.get(n, 0.0), s2.get(n, 0.0), s3.get(n, 0.0), s4.get(n, 0.0)]
        mean_v = float(np.mean(vals))
        std_v = float(np.std(vals))
        # high mean + low disagreement => strong consensus
        out[n] = max(0.0, mean_v - 0.5 * std_v)
    return out


# ============================================================
# Strategy Coordinator
# ============================================================

# 各彩種的 Agent 設定
AGENT_REGISTRY = {
    'DAILY_539': {
        'acb':     {'fn': lambda h: _acb_score_all(h, window=100, max_num=39),
                    'rsm_key': 'acb_1bet'},
        'midfreq': {'fn': lambda h: _midfreq_score_all(h, window=100, max_num=39),
                    'rsm_key': 'midfreq_acb_2bet'},
        'fourier': {'fn': lambda h: _fourier_score_all(h, window=500, max_num=39),
                    'rsm_key': 'acb_markov_fourier_3bet'},
        'markov':  {'fn': lambda h: _markov_score_all(h, window=30, max_num=39),
                    'rsm_key': 'acb_markov_fourier_3bet'},
        'markov2': {'fn': lambda h: markov2_score_all(h, max_num=39),
                    'rsm_key': 'acb_markov_fourier_3bet'},
        'weibull_gap': {'fn': lambda h: weibull_gap_score_all(h, max_num=39),
                        'rsm_key': 'midfreq_acb_2bet'},
        'consensus_signal': {'fn': lambda h: _consensus_score_all(h, max_num=39),
                             'rsm_key': 'acb_markov_midfreq_3bet'},
    },
    'BIG_LOTTO': {
        'fourier':  {'fn': lambda h: _bl_fourier_score_all(h, window=500),
                     'rsm_key': 'triple_strike_3bet'},
        'cold':     {'fn': lambda h: _bl_cold_score_all(h, window=100),
                     'rsm_key': 'p1_neighbor_cold_2bet'},
        'neighbor': {'fn': lambda h: _bl_neighbor_score_all(h),
                     'rsm_key': 'p1_neighbor_cold_2bet'},
        'markov':   {'fn': lambda h: _markov_score_all(h, window=30, max_num=49),
                     'rsm_key': 'triple_strike_3bet'},
        'markov2':  {'fn': lambda h: markov2_score_all(h, max_num=49),
                     'rsm_key': 'triple_strike_3bet'},
        'weibull_gap': {'fn': lambda h: weibull_gap_score_all(h, max_num=49),
                        'rsm_key': 'p1_neighbor_cold_2bet'},
        'consensus_signal': {'fn': lambda h: _consensus_score_all(h, max_num=49),
                             'rsm_key': 'ts3_regime_3bet'},
    },
    'POWER_LOTTO': {
        'fourier': {'fn': lambda h: _pl_fourier_score_all(h, window=500),
                    'rsm_key': 'fourier_rhythm_3bet'},
        'cold':    {'fn': lambda h: _pl_cold_score_all(h, window=100),
                    'rsm_key': 'fourier_rhythm_2bet'},
        'markov':  {'fn': lambda h: _markov_score_all(h, window=30, max_num=38),
                    'rsm_key': 'fourier_rhythm_3bet'},
        'markov2': {'fn': lambda h: markov2_score_all(h, max_num=38),
                    'rsm_key': 'fourier_rhythm_3bet'},
        'weibull_gap': {'fn': lambda h: weibull_gap_score_all(h, max_num=38),
                        'rsm_key': 'fourier_rhythm_2bet'},
        'consensus_signal': {'fn': lambda h: _consensus_score_all(h, max_num=38),
                             'rsm_key': 'fourier_rhythm_3bet'},
    },
}

# 號碼池大小
NUM_POOL = {'DAILY_539': 39, 'BIG_LOTTO': 49, 'POWER_LOTTO': 38}
BET_SIZE = {'DAILY_539': 5, 'BIG_LOTTO': 6, 'POWER_LOTTO': 6}



class StrategyCoordinator:
    """
    多智能體策略協調器

    Usage:
        coord = StrategyCoordinator('DAILY_539', rsm_data_dir='data')

        # 取得加權聚合後的號碼排名
        ranked = coord.rank_numbers(history)

        # 生成 N 注正交預測
        bets = coord.predict(history, n_bets=3)
        # → [[5,13,27,33,40], [2,8,19,25,36], [1,14,21,30,38]]
    """

    def __init__(self, lottery_type: str, rsm_data_dir: str = None,
                 weight_window: int = 100):
        """
        Args:
            weight_window: RSM 權重來源窗口 (30=短期, 100=中期推薦, 300=長期)
        """
        self.lottery_type = lottery_type
        self.agents = AGENT_REGISTRY.get(lottery_type, {})
        self.max_num = NUM_POOL.get(lottery_type, 39)
        self.bet_size = BET_SIZE.get(lottery_type, 5)
        self.weight_window = weight_window

        # 載入 RSM 狀態
        self._weights: Dict[str, float] = {}
        self._weight_source: Dict[str, str] = {}
        self._drift_status: str = 'UNKNOWN'
        self._drift_multiplier: float = 1.0
        self._regime_status: str = 'UNKNOWN'
        self._regime_multiplier: float = 1.0
        self._load_weights(rsm_data_dir)

    def _candidate_data_dirs(self, data_dir: Optional[str]) -> List[str]:
        candidates = []
        if data_dir:
            candidates.append(data_dir)
        candidates.append(os.path.join(project_root, 'data'))
        candidates.append(os.path.join(project_root, 'lottery_api', 'data'))

        uniq = []
        seen = set()
        for d in candidates:
            ad = os.path.abspath(d)
            if ad in seen:
                continue
            seen.add(ad)
            uniq.append(ad)
        return uniq

    def _load_first_json(self, dirs: List[str], filename: str) -> Optional[dict]:
        for d in dirs:
            p = os.path.join(d, filename)
            if not os.path.exists(p):
                continue
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data
            except Exception as e:
                logger.warning(f"讀取失敗: {p} ({e})")
        return None

    def _resolve_drift_multiplier(self, dirs: List[str]) -> float:
        """根據 drift_report 取得全域降權倍率。"""
        report = self._load_first_json(dirs, 'drift_report.json')
        if not isinstance(report, dict):
            self._drift_status = 'UNKNOWN'
            self._drift_multiplier = 1.0
            return 1.0

        node = report.get(self.lottery_type)
        if not isinstance(node, dict) and report.get('lottery_type') == self.lottery_type:
            node = report
        if not isinstance(node, dict):
            self._drift_status = 'UNKNOWN'
            self._drift_multiplier = 1.0
            return 1.0

        status = str(node.get('overall_status', 'STABLE')).upper()
        mult = {'STABLE': 1.0, 'WARNING': 0.85, 'CRITICAL': 0.65}.get(status, 1.0)

        metrics = node.get('metrics', {})
        if isinstance(metrics, dict):
            nf = metrics.get('number_freq_PSI', {})
            if isinstance(nf, dict):
                nf_status = str(nf.get('status', 'STABLE')).upper()
                if nf_status == 'WARNING':
                    mult *= 0.92
                elif nf_status == 'CRITICAL':
                    mult *= 0.80
            zf = metrics.get('zone_dist_PSI', {})
            if isinstance(zf, dict):
                zf_status = str(zf.get('status', 'STABLE')).upper()
                if zf_status == 'WARNING':
                    mult *= 0.95
                elif zf_status == 'CRITICAL':
                    mult *= 0.85

        self._drift_status = status
        self._drift_multiplier = max(0.5, min(mult, 1.0))
        return self._drift_multiplier

    def _resolve_regime_multiplier(self) -> float:
        """
        Read M1 PoC regime output and derive global multiplier:
        if current regime differs from best-edge regime => mild risk-down.
        """
        fname = {
            'BIG_LOTTO': 'm1_regime_detector_poc.json',
            'POWER_LOTTO': 'm1_regime_detector_poc_power.json',
            'DAILY_539': 'm1_regime_detector_poc_539.json',
        }.get(self.lottery_type, '')
        if not fname:
            self._regime_status = 'UNKNOWN'
            self._regime_multiplier = 1.0
            return 1.0

        p = os.path.join(project_root, 'research', fname)
        if not os.path.exists(p):
            self._regime_status = 'UNKNOWN'
            self._regime_multiplier = 1.0
            return 1.0

        try:
            with open(p, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            rr = raw.get('regime_result', {})
            cur = int(rr.get('current_regime', -1))
            means = rr.get('means', [])
            if not isinstance(means, list) or not means:
                self._regime_status = 'UNKNOWN'
                self._regime_multiplier = 1.0
                return 1.0
            # means[*][1] is edge in m1_regime_detector_poc.py feature design.
            edge_by_regime = []
            for i, m in enumerate(means):
                try:
                    edge_by_regime.append((i, float(m[1])))
                except Exception:
                    edge_by_regime.append((i, -1e9))
            best_regime = max(edge_by_regime, key=lambda x: x[1])[0]
            if cur == best_regime:
                mult = 1.05
                status = 'FAVORABLE'
            else:
                mult = 0.90
                status = 'UNFAVORABLE'
            self._regime_status = status
            self._regime_multiplier = mult
            return mult
        except Exception:
            self._regime_status = 'UNKNOWN'
            self._regime_multiplier = 1.0
            return 1.0

    def _weight_from_strategy_state(self, state: dict) -> float:
        edge = float(state.get('edge_30p', 0.0))
        w = max(edge, 0.0) + 0.1  # keep minimum exploration weight

        sharpe = float(state.get('sharpe_300p', 0.0))
        if sharpe <= 0:
            w *= 0.9

        trend = str(state.get('trend', 'STABLE')).upper()
        if trend == 'DECELERATING':
            w *= 0.85
        elif trend == 'REGIME_SHIFT':
            w *= 0.70

        if bool(state.get('alert', False)):
            w *= 0.75

        neg = int(state.get('consecutive_neg_30p', 0))
        if neg >= 10:
            w *= 0.5
        elif neg >= 5:
            w *= 0.8

        return max(w, 0.02)

    def _load_weights(self, data_dir: str = None):
        """從 StrategyStateStore / rolling_monitor 載入權重，並疊加 drift 降權。"""
        if data_dir is None:
            data_dir = os.path.join(project_root, 'data')
        dirs = self._candidate_data_dirs(data_dir)

        states_raw = self._load_first_json(dirs, f'strategy_states_{self.lottery_type}.json')
        states = states_raw if isinstance(states_raw, dict) else {}

        monitor_raw = self._load_first_json(dirs, f'rolling_monitor_{self.lottery_type}.json')
        records = monitor_raw.get('records', {}) if isinstance(monitor_raw, dict) else {}

        from lottery_api.engine.rolling_strategy_monitor import (
            BASELINES, METRIC_KEY
        )
        baselines = BASELINES.get(self.lottery_type, BASELINES['POWER_LOTTO'])
        metric = METRIC_KEY.get(self.lottery_type, 'is_m3plus')

        for agent_name, cfg in self.agents.items():
            rsm_key = cfg['rsm_key']
            state = states.get(rsm_key)

            if isinstance(state, dict):
                self._weights[agent_name] = self._weight_from_strategy_state(state)
                self._weight_source[agent_name] = 'strategy_state'
                continue

            recs = records.get(rsm_key, [])
            if not recs:
                self._weights[agent_name] = 1.0
                self._weight_source[agent_name] = 'fallback'
                continue

            baseline = baselines.get(1, 0.03)
            recent_w = recs[-self.weight_window:] if len(recs) >= self.weight_window else recs
            if not recent_w:
                self._weights[agent_name] = 1.0
                self._weight_source[agent_name] = 'fallback'
                continue

            hit_w = sum(1 for r in recent_w if r.get(metric, False))
            rate_w = hit_w / len(recent_w)
            edge_w = rate_w - baseline
            self._weights[agent_name] = max(edge_w, 0.0) + 0.1
            self._weight_source[agent_name] = 'rolling_monitor'

        drift_mult = self._resolve_drift_multiplier(dirs)
        if drift_mult < 0.999:
            for k in list(self._weights.keys()):
                self._weights[k] = max(0.02, self._weights[k] * drift_mult)

        regime_mult = self._resolve_regime_multiplier()
        if abs(regime_mult - 1.0) > 1e-6:
            for k in list(self._weights.keys()):
                self._weights[k] = max(0.02, self._weights[k] * regime_mult)


    def aggregate_scores(self, history: list) -> Dict[int, float]:
        """執行所有 Agent，加權聚合回全號碼評分"""
        total_weights = sum(self._weights.values()) or 1.0
        final: Dict[int, float] = {n: 0.0 for n in range(1, self.max_num + 1)}

        for agent_name, cfg in self.agents.items():
            raw_scores = cfg['fn'](history)
            norm_scores = _normalize(raw_scores)
            w = self._weights.get(agent_name, 1.0) / total_weights

            for n, s in norm_scores.items():
                final[n] = final.get(n, 0.0) + w * s

        return final

    def rank_numbers(self, history: list) -> List[int]:
        """輸出按聚合分數排序的號碼列表（高分在前）"""
        scores = self.aggregate_scores(history)
        return sorted(scores, key=lambda n: -scores[n])

    def predict(self, history: list, n_bets: int = 3) -> List[List[int]]:
        """
        生成 N 注正交預測

        從聚合分數排名中依序切片，每注互不重疊。
        """
        ranked = self.rank_numbers(history)
        bets = []
        for i in range(n_bets):
            start = i * self.bet_size
            end = start + self.bet_size
            if start >= len(ranked):
                break
            bet = sorted(ranked[start:end])
            bets.append(bet)
        return bets

    def predict_hybrid(self, history: list, n_bets: int = 3,
                       top_n_from_coord: int = 15) -> List[List[int]]:
        """
        混合模式：Coordinator 先縮小候選池，再讓各 Agent 從池中選號

        top_n_from_coord: Coordinator 提供的候選池大小
        """
        ranked = self.rank_numbers(history)
        candidate_pool = set(ranked[:top_n_from_coord])

        # Agent 1 (最強信號): ACB 或 Fourier
        agent_names = list(self.agents.keys())
        bets = []
        used = set()

        for i, agent_name in enumerate(agent_names[:n_bets]):
            cfg = self.agents[agent_name]
            raw_scores = cfg['fn'](history)
            # 只從候選池選號
            filtered = {n: s for n, s in raw_scores.items()
                        if n in candidate_pool and n not in used}
            full_available = {n: s for n, s in raw_scores.items() if n not in used}
            if not filtered:
                filtered = full_available

            top_nums = sorted(filtered, key=lambda n: -filtered[n])[:self.bet_size]

            # 候選池耗盡時，從全域可用號碼補滿 bet_size，避免產生短注
            if len(top_nums) < self.bet_size:
                extras = [n for n in sorted(full_available, key=lambda x: -full_available[x])
                          if n not in top_nums]
                top_nums.extend(extras[:self.bet_size - len(top_nums)])

            bet = sorted(top_nums)
            bets.append(bet)
            used.update(bet)

        return bets

    def agent_hit_analysis(self, history: list, actual_numbers: list) -> Dict[str, dict]:
        """
        Per-agent hit tracking: for each agent, report which actual numbers
        it ranked in its top-5 and top-10, and their individual scores.

        Returns dict: {agent_name: {top5_hits, top10_hits, rankings, scores}}
        """
        actual_set = set(actual_numbers)
        result = {}
        for agent_name, cfg in self.agents.items():
            raw = cfg['fn'](history)
            ranked = sorted(raw, key=lambda n: -raw[n])
            top5 = set(ranked[:self.bet_size])
            top10 = set(ranked[:self.bet_size * 2])
            t5_hits = top5 & actual_set
            t10_hits = top10 & actual_set
            rankings = {}
            for n in actual_numbers:
                try:
                    rankings[n] = ranked.index(n) + 1
                except ValueError:
                    rankings[n] = self.max_num + 1
            result[agent_name] = {
                'top5_hits': sorted(t5_hits),
                'top5_count': len(t5_hits),
                'top10_hits': sorted(t10_hits),
                'top10_count': len(t10_hits),
                'rankings': rankings,
                'weight': self._weights.get(agent_name, 0),
            }
        return result

    def get_weight_summary(self) -> str:
        """回傳目前權重設定的摘要"""
        lines = [f"  [{self.lottery_type}] Coordinator 權重：",
                 f"    drift: {self._drift_status} ×{self._drift_multiplier:.3f}",
                 f"    regime: {self._regime_status} ×{self._regime_multiplier:.3f}"]
        for name, w in self._weights.items():
            src = self._weight_source.get(name, '?')
            lines.append(f"    {name:12s}: {w:.4f} ({'+' if w>0.1 else '~'}, {src})")
        return '\n'.join(lines)


# ============================================================
# 快速預測包裝
# ============================================================

def coordinator_predict(lottery_type: str, history: list, n_bets: int,
                        mode: str = 'direct',
                        rsm_data_dir: str = None) -> Tuple[List[List[int]], str]:
    """
    對外統一介面

    Args:
        mode: 'direct' = 排名切片; 'hybrid' = 候選池縮小後再選

    Returns:
        (bets, description)
    """
    if rsm_data_dir is None:
        rsm_data_dir = os.path.join(project_root, 'data')

    coord = StrategyCoordinator(lottery_type, rsm_data_dir=rsm_data_dir)

    if mode == 'hybrid':
        bets = coord.predict_hybrid(history, n_bets=n_bets)
        desc = f'Coordinator-Hybrid ({len(coord.agents)} agents)'
    else:
        bets = coord.predict(history, n_bets=n_bets)
        desc = f'Coordinator-Direct ({len(coord.agents)} agents)'

    return bets, desc


# ============================================================
# CLI 測試
# ============================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('lottery', choices=['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'])
    parser.add_argument('--bets', type=int, default=3)
    parser.add_argument('--mode', choices=['direct', 'hybrid'], default='direct')
    args = parser.parse_args()

    sys.path.insert(0, project_root)
    from database import DatabaseManager
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = sorted(db.get_all_draws(lottery_type=args.lottery),
                     key=lambda x: (x['date'], x['draw']))

    coord = StrategyCoordinator(args.lottery)
    print(coord.get_weight_summary())
    print()

    bets, desc = coordinator_predict(args.lottery, history, args.bets, mode=args.mode)
    print(f"策略: {desc}")
    for i, b in enumerate(bets, 1):
        print(f"  注{i}: {b}")
