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


def _h6_gate_mk20_ew88_score_all(history: list, max_num: int = 39) -> Dict[int, float]:
    """H6 Gate (gate_size=20, ewma_decay=0.88): Markov-gated EWMA underdue signal.

    Strategy: ACB anchor + Markov top-20 candidate pool + EWMA(0.88) re-ranking.
    Validated 2026-04-29: edge_150p=+7.13%, Cohen d=1.60, MC p=0.0578.
    Param-optimised: gate_size=20, ewma_decay=0.88 (task 325).
    """
    PICK = 5 if max_num <= 39 else 6

    # --- ACB anchor scores ---
    acb = _acb_score_all(history, window=100, max_num=max_num)

    # --- Markov gate (window=40, top-20) ---
    mk = _markov_score_all(history, window=40, max_num=max_num)
    mk_sorted = sorted(range(1, max_num + 1), key=lambda n: -mk.get(n, 0.0))
    mk_gate = set(mk_sorted[:20])  # gate_size=20

    # --- EWMA underdue score (decay=0.88, window=80) ---
    recent = history[-80:] if len(history) >= 80 else history
    ewma: Dict[int, float] = {n: 0.0 for n in range(1, max_num + 1)}
    w = 1.0
    total_w = 0.0
    for d in reversed(recent):
        for n in d['numbers']:
            if 1 <= n <= max_num:
                ewma[n] += w
        total_w += w
        w *= 0.88  # param-optimised decay
    expected_w = total_w * (PICK / max_num)
    ewma_score = {n: expected_w - ewma[n] for n in range(1, max_num + 1)}

    # --- Combine: gate-in = ACB×0.4 + EWMA×0.6; gate-out = ACB×0.15 ---
    acb_n = _normalize(acb)
    ew_n = _normalize(ewma_score)
    out: Dict[int, float] = {}
    for n in range(1, max_num + 1):
        if n in mk_gate:
            out[n] = 0.4 * acb_n.get(n, 0.0) + 0.6 * ew_n.get(n, 0.0)
        else:
            out[n] = 0.15 * acb_n.get(n, 0.0)
    return out


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
        'h6_gate':          {'fn': lambda h: _h6_gate_mk20_ew88_score_all(h, max_num=39),
                             'rsm_key': 'H6_gate_mk20_ew85'},
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
                 weight_window: int = 100, disable_learning: bool = False,
                 disable_quality: bool = False, profile: str = None):
        """
        Args:
            weight_window: RSM 權重來源窗口 (30=短期, 100=中期推薦, 300=長期)
            disable_learning: If True, skip additive learning bonus entirely
            disable_quality: If True, skip winning quality (anti-crowd + payout) bonus
            profile: Decision profile name ('conservative'|'balanced'|'aggressive')
        """
        self.lottery_type = lottery_type
        self.agents = AGENT_REGISTRY.get(lottery_type, {})
        self.max_num = NUM_POOL.get(lottery_type, 39)
        self.bet_size = BET_SIZE.get(lottery_type, 5)
        self.weight_window = weight_window
        self.disable_learning = disable_learning
        self.disable_quality = disable_quality

        # Phase N: Decision profile
        from lottery_api.engine.decision_profiles import get_profile
        self._profile = get_profile(profile, lottery_type)

        # 載入 RSM 狀態
        self._weights: Dict[str, float] = {}
        self._weight_source: Dict[str, str] = {}
        self._drift_status: str = 'UNKNOWN'
        self._drift_multiplier: float = 1.0
        self._regime_status: str = 'UNKNOWN'
        self._regime_multiplier: float = 1.0
        self._load_weights(rsm_data_dir)

        # v2: Load additive learning bonuses
        # Phase K.5: Apply dynamic gating to learning signal
        self._learning_bonuses: Dict[str, float] = {}
        self._learning_gate: Dict = {'gate': 'DISABLED', 'factor': 0.0, 'reason': 'not loaded'}
        if not disable_learning:
            try:
                from lottery_api.engine.learning_integrator import (
                    compute_learning_bonuses, compute_learning_gate,
                )
                self._learning_gate = compute_learning_gate(lottery_type)
                gate_factor = self._learning_gate['factor']
                if gate_factor > 1e-8:
                    raw_bonuses = compute_learning_bonuses(lottery_type, self.agents)
                    # Apply gate factor to bonuses at load time
                    self._learning_bonuses = {
                        agent: bonus * gate_factor
                        for agent, bonus in raw_bonuses.items()
                    }
                    logger.info(f"Learning gate={self._learning_gate['gate']} "
                                f"factor={gate_factor} for {lottery_type}")
                else:
                    logger.info(f"Learning DISABLED by gate: {self._learning_gate['reason']}")
            except Exception as e:
                logger.warning(f"Learning bonus load failed: {e}")
                self._learning_bonuses = {}

        # Phase M: Winning quality scorer (anti-crowd + payout quality)
        self._quality_scorer = None
        if not disable_quality:
            try:
                from lottery_api.engine.winning_quality import WinningQualityScorer
                self._quality_scorer = WinningQualityScorer(lottery_type, enabled=True)
            except Exception as e:
                logger.warning(f"Quality scorer load failed: {e}")
                self._quality_scorer = None

        # Phase P: Explainability trace (populated by aggregate_scores)
        self._last_trace: Dict = {}

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

        # v1 multiplicative research_multiplier REMOVED (v2: additive bonus)
        # The multiplicative path was proven ineffective by A/B validation:
        # uniform k cancels in weight normalization: (k·w_i)/Σ(k·w_j) = w_i/Σw_j

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
        """
        執行所有 Agent，加權聚合回全號碼評分。

        v2: After normalized weight aggregation, applies per-agent additive
        learning bonus. Because the bonus is additive (not multiplicative on
        weights), it bypasses the normalization that killed v1's signal.
        """
        total_weights = sum(self._weights.values()) or 1.0
        final: Dict[int, float] = {n: 0.0 for n in range(1, self.max_num + 1)}

        # Cache normalized scores per agent for bonus application
        agent_norm_scores: Dict[str, Dict[int, float]] = {}

        # Phase P: track per-agent weighted contribution for explainability
        agent_weighted_contrib: Dict[str, float] = {}

        for agent_name, cfg in self.agents.items():
            raw_scores = cfg['fn'](history)
            norm_scores = _normalize(raw_scores)
            agent_norm_scores[agent_name] = norm_scores
            w = self._weights.get(agent_name, 1.0) / total_weights

            contrib_sum = 0.0
            for n, s in norm_scores.items():
                final[n] = final.get(n, 0.0) + w * s
                contrib_sum += w * s
            agent_weighted_contrib[agent_name] = contrib_sum

        # Phase P: snapshot scores BEFORE learning bonus
        scores_before_learning = dict(final)

        # v2: Additive learning bonus — applied AFTER normalization
        # Phase N: scaled by profile.learning_amp

        learning_amp = self._profile.learning_amp
        learning_applied_agents: Dict[str, float] = {}
        if self._learning_bonuses and abs(learning_amp) > 1e-8:
            for agent_name, norm_scores in agent_norm_scores.items():
                bonus = self._learning_bonuses.get(agent_name, 0.0)
                if abs(bonus) < 1e-8:
                    continue
                learning_applied_agents[agent_name] = learning_amp * bonus
                for n, s in norm_scores.items():
                    final[n] += learning_amp * bonus * s

        # Phase P: snapshot scores BEFORE quality bonus
        scores_before_quality = dict(final)

        # Phase M: Winning quality bonus (anti-crowd + payout quality)
        # Phase N: scaled by profile.quality_amp
        quality_delta_summary: Dict[str, float] = {}
        if self._quality_scorer is not None:
            quality_amp = self._profile.quality_amp
            if abs(quality_amp - 1.0) < 1e-6:
                final = self._quality_scorer.apply(final)
            else:
                # Apply with custom amplitude
                base_final = dict(final)
                adjusted = self._quality_scorer.apply(final)
                for n in final:
                    delta = adjusted[n] - base_final[n]
                    final[n] = base_final[n] + quality_amp * delta
            # Phase P: summarize quality delta
            total_quality_delta = sum(abs(final[n] - scores_before_quality[n]) for n in final)
            quality_delta_summary = {
                'total_abs_delta': total_quality_delta,
                'quality_amp': self._profile.quality_amp,
            }

        # Phase P: build ranking comparison (top-N before/after bonuses)
        top_before = sorted(scores_before_learning, key=lambda n: -scores_before_learning[n])[:self.bet_size * 3]
        top_after_learning_only = sorted(scores_before_quality, key=lambda n: -scores_before_quality[n])[:self.bet_size * 3]
        top_after = sorted(final, key=lambda n: -final[n])[:self.bet_size * 3]
        ranking_changed_by_learning = top_before[:self.bet_size] != top_after_learning_only[:self.bet_size]
        ranking_changed_by_quality = top_after_learning_only[:self.bet_size] != top_after[:self.bet_size]
        ranking_changed = top_before[:self.bet_size] != top_after[:self.bet_size]

        # Phase P: store trace on instance for later retrieval
        self._last_trace = {
            'agent_weights': {a: round(self._weights.get(a, 0) / total_weights, 6)
                              for a in self.agents},
            'agent_weighted_contrib': {a: round(v, 6) for a, v in agent_weighted_contrib.items()},
            'learning_applied_agents': {a: round(v, 6) for a, v in learning_applied_agents.items()},
            'quality_delta_summary': quality_delta_summary,
            'top_agents_before_bonus': top_before[:self.bet_size],
            'top_agents_after_bonus': top_after[:self.bet_size],
            'ranking_changed': ranking_changed,
            'ranking_changed_by_learning': ranking_changed_by_learning,
            'ranking_changed_by_quality': ranking_changed_by_quality,
        }

        return final

    def rank_numbers(self, history: list) -> List[int]:
        """輸出按聚合分數排序的號碼列表（高分在前）"""
        scores = self.aggregate_scores(history)
        return sorted(scores, key=lambda n: -scores[n])

    def predict(self, history: list, n_bets: int = 3) -> List[List[int]]:
        """
        生成 N 注正交預測

        從聚合分數排名中依序切片，每注互不重疊。
        注意：不同 n_bets 的前 n-1 注保持一致（設計行為）。
        若需要依 n_bets 獨立預測，請在呼叫端直接使用對應驗證策略。
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

    def get_explanation(self) -> Dict:
        """
        Phase P: Build structured explanation object from last aggregate_scores() run.

        Must be called AFTER predict() or aggregate_scores() to get meaningful data.
        Returns the complete explainability snapshot.
        """
        gate = self._learning_gate
        profile = self._profile
        trace = self._last_trace

        # ── Best strategy from strategy_states ─────────────────────────────
        selected_strategy = 'coordinator_direct'
        validated_status = 'WATCH'
        base_composite_score = None
        base_edge_150p = None
        base_edge_500p = None
        base_edge_1500p = None
        try:
            states_path = os.path.join(
                project_root, 'lottery_api', 'data',
                f'strategy_states_{self.lottery_type}.json'
            )
            if not os.path.exists(states_path):
                states_path = os.path.join(project_root, 'data',
                                           f'strategy_states_{self.lottery_type}.json')
            if os.path.exists(states_path):
                with open(states_path, 'r', encoding='utf-8') as _f:
                    states = json.load(_f)
                # Rank: VALIDATED=2, WATCH=1, else=0; then by composite_score desc
                def _rank_state(item):
                    vs = item.get('validated_status', '').upper()
                    pri = 2 if vs == 'VALIDATED' else (1 if vs == 'WATCH' else 0)
                    cs = item.get('composite_score') or 0.0
                    return (pri, cs)
                best_state = max(states.values(), key=_rank_state) if states else {}
                if best_state:
                    selected_strategy = best_state.get('name', 'coordinator_direct')
                    validated_status = best_state.get('validated_status', 'WATCH') or 'WATCH'
                    base_composite_score = best_state.get('composite_score')
                    base_edge_150p = best_state.get('edge_150p')
                    base_edge_500p = best_state.get('edge_500p')
                    base_edge_1500p = best_state.get('edge_1500p')
        except Exception as _e:
            logger.debug(f"Strategy states read failed (non-fatal): {_e}")

        # ── Learning explanation ────────────────────────────────────────────
        learning_bonuses_by_agent = {}
        for agent in self.agents:
            raw = self._learning_bonuses.get(agent, 0.0)
            if abs(raw) > 1e-8:
                learning_bonuses_by_agent[agent] = round(raw, 6)

        learning_enabled = gate.get('gate', 'DISABLED') != 'DISABLED'
        ranking_changed_by_learning = bool(trace.get('ranking_changed_by_learning', False))
        ranking_changed_by_quality = bool(trace.get('ranking_changed_by_quality', False))
        boosted = [a for a, v in trace.get('learning_applied_agents', {}).items() if v > 0]
        penalized = [a for a, v in trace.get('learning_applied_agents', {}).items() if v < 0]

        # Build learning summary text
        gate_label = gate.get('gate', 'DISABLED')
        if gate_label == 'DISABLED':
            learning_summary = f"{self.lottery_type} learning disabled: {gate.get('reason', 'unknown')}"
        elif gate_label == 'WEAK':
            learning_summary = (f"{self.lottery_type} learning weak: low research_score, "
                                f"bonus scaled to {gate.get('factor', 0.5)}")
        else:
            if ranking_changed_by_learning:
                parts = []
                if boosted:
                    parts.append(f"boosted {', '.join(boosted)}")
                if penalized:
                    parts.append(f"penalized {', '.join(penalized)}")
                learning_summary = (f"{self.lottery_type} learning active: "
                                    f"{' and '.join(parts)}")
            else:
                learning_summary = f"{self.lottery_type} learning active but ranking unchanged"

        # ── Quality explanation ─────────────────────────────────────────────
        qd = trace.get('quality_delta_summary', {})
        quality_enabled = self._quality_scorer is not None
        total_quality_delta = round(qd.get('total_abs_delta', 0.0), 6)
        quality_label = '已調整熱門度' if (quality_enabled and total_quality_delta > 1e-6) else '未調整'
        if quality_enabled and total_quality_delta > 1e-6:
            quality_summary = (f"quality bonus applied (amp={qd.get('quality_amp', 1.0)}, "
                                f"total abs delta={total_quality_delta:.4f})")
        elif not quality_enabled:
            quality_summary = "quality scoring disabled"
        else:
            quality_summary = "quality scoring enabled but no delta"

        # ── Profile explanation ─────────────────────────────────────────────
        profile_effects = []
        if profile.learning_amp != 1.0:
            profile_effects.append(f"learning×{profile.learning_amp}")
        if profile.quality_amp != 1.0:
            profile_effects.append(f"quality×{profile.quality_amp}")
        if profile.var_n_scale != 1.0:
            profile_effects.append(f"var_n×{profile.var_n_scale}")
        if profile.concentration_bias != 1.0:
            if profile.concentration_bias > 1.0:
                profile_effects.append("concentration increased")
            else:
                profile_effects.append("diversification favored")
        profile_summary = (f"profile={profile.name}: {', '.join(profile_effects)}"
                           if profile_effects
                           else f"profile={profile.name}: no amplification changes")

        # ── Hypothesis info ─────────────────────────────────────────────────
        n_total = gate.get('n_total', 0)
        n_validated = gate.get('n_validated', 0)
        n_rejected = gate.get('n_rejected', 0)
        n_provisional = gate.get('n_provisional', 0)

        # ── Decision fields ─────────────────────────────────────────────────
        last_n_bets = getattr(self, '_last_n_bets', 3)
        # final_n_bets = actual bets in last predict call (profile may scale via apply_var_n_scale)
        final_n_bets = getattr(self, '_last_final_n_bets', last_n_bets)

        # ── Final reason (one-sentence human-readable) ──────────────────────
        profile_label_map = {'conservative': '保守', 'balanced': '平衡', 'aggressive': '積極'}
        vs_label_map = {'VALIDATED': '✅ 已完整驗證', 'WATCH': '⚠️ 觀察中', 'REJECTED': '❌ 未通過驗證'}
        profile_zh = profile_label_map.get(profile.name, profile.name)
        vs_zh = vs_label_map.get(validated_status, validated_status)

        reasons = []
        if ranking_changed_by_learning and gate_label in ('ENABLED', 'WEAK'):
            reasons.append(f"learning({gate_label})" + ("壓低弱策略" if penalized else "提升強策略"))
        if ranking_changed_by_quality and quality_enabled:
            reasons.append("quality降低熱門度")
        if not reasons:
            reasons.append("基礎 agent 加權排序")

        final_reason = (f"採用 {selected_strategy}（{vs_zh}，{profile_zh}模式）。"
                        f"因{'、'.join(reasons)}，最終排名{'有' if trace.get('ranking_changed', False) else '無'}變動。")

        return {
            'lottery_type': self.lottery_type,
            'profile': profile.name,
            'selected_strategy': selected_strategy,
            'validated_status': validated_status,
            'base': {
                'composite_score': round(float(base_composite_score), 6) if base_composite_score is not None else None,
                'edge_150p': round(float(base_edge_150p), 6) if base_edge_150p is not None else None,
                'edge_500p': round(float(base_edge_500p), 6) if base_edge_500p is not None else None,
                'edge_1500p': round(float(base_edge_1500p), 6) if base_edge_1500p is not None else None,
            },
            'learning': {
                'enabled': learning_enabled,
                'gate': gate_label,
                'factor': gate.get('factor', 0.0),
                'research_score': round(gate.get('research_score', 0.0), 6),
                'bonus_by_agent': learning_bonuses_by_agent,
                'boosted_agents': boosted,
                'penalized_agents': penalized,
                'ranking_changed': ranking_changed_by_learning,
                'bonus_summary': learning_summary,
                'hypotheses': {
                    'total': n_total,
                    'validated': n_validated,
                    'rejected': n_rejected,
                    'provisional': n_provisional,
                },
            },
            'quality': {
                'enabled': quality_enabled,
                'quality_amp': profile.quality_amp,
                'total_abs_delta': total_quality_delta,
                'ranking_changed': ranking_changed_by_quality,
                'quality_label': quality_label,
                'quality_summary': quality_summary,
            },
            'decision': {
                'base_n_bets': last_n_bets,
                'final_n_bets': final_n_bets,
                'concentration_bias': profile.concentration_bias,
            },
            'final_reason': final_reason,
            # ── Extended fields (for detailed UI) ──────────────────────────
            'base_score_summary': {
                'agent_weights': trace.get('agent_weights', {}),
                'drift_status': self._drift_status,
                'drift_multiplier': round(self._drift_multiplier, 4),
                'regime_status': self._regime_status,
                'regime_multiplier': round(self._regime_multiplier, 4),
            },
            'learning_detail': {
                'gate': gate_label,
                'factor': gate.get('factor', 0.0),
                'research_score': round(gate.get('research_score', 0.0), 6),
                'bonus_by_agent': learning_bonuses_by_agent,
                'boosted_agents': boosted,
                'penalized_agents': penalized,
                'ranking_changed': ranking_changed_by_learning,
                'summary': learning_summary,
            },
            'profile_detail': {
                'name': profile.name,
                'learning_amp': profile.learning_amp,
                'quality_amp': profile.quality_amp,
                'var_n_scale': profile.var_n_scale,
                'concentration_bias': profile.concentration_bias,
                'risk_mode': profile.risk_mode,
                'summary': profile_summary,
            },
            'selection': {
                'top_numbers_before_bonus': trace.get('top_agents_before_bonus', []),
                'top_numbers_after_bonus': trace.get('top_agents_after_bonus', []),
                'ranking_changed': trace.get('ranking_changed', False),
            },
        }


# ============================================================
# 快速預測包裝
# ============================================================

def coordinator_predict(lottery_type: str, history: list, n_bets: int,
                        mode: str = 'direct',
                        rsm_data_dir: str = None,
                        profile: str = None) -> Tuple[List[List[int]], str]:
    """
    對外統一介面

    Args:
        mode: 'direct' = 排名切片; 'hybrid' = 候選池縮小後再選
        profile: Decision profile ('conservative'|'balanced'|'aggressive')

    Returns:
        (bets, description)
    """
    if rsm_data_dir is None:
        rsm_data_dir = os.path.join(project_root, 'data')

    coord = StrategyCoordinator(lottery_type, rsm_data_dir=rsm_data_dir,
                                profile=profile)

    if mode == 'hybrid':
        bets = coord.predict_hybrid(history, n_bets=n_bets)
        desc = f'Coordinator-Hybrid ({len(coord.agents)} agents)'
    else:
        bets = coord.predict(history, n_bets=n_bets)
        desc = f'Coordinator-Direct ({len(coord.agents)} agents)'

    # Phase P: store n_bets metadata for explanation
    coord._last_n_bets = n_bets
    coord._last_final_n_bets = len(bets)

    # Phase P: attach explanation to module-level cache for retrieval
    global _last_explanation
    try:
        _last_explanation = coord.get_explanation()
    except Exception as e:
        logger.warning(f"Explanation build failed: {e}")
        _last_explanation = None

    return bets, desc


# Phase P: Module-level explanation cache
_last_explanation: Optional[Dict] = None


def get_last_explanation() -> Optional[Dict]:
    """Retrieve the explanation from the most recent coordinator_predict() call."""
    return _last_explanation


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
