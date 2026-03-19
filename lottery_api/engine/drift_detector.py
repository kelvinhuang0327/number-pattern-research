"""
Drift Detector
==============
彩種資料漂移偵測 — PSI + KS 雙指標監控

核心功能:
  1. 號碼邊際分布 PSI（Population Stability Index）
  2. 奇偶比 / 和值分布 KS 檢定
  3. 重號率（連號、上期重號）監控
  4. Warning / Critical 雙層級，Critical 凍結策略更新

PSI 解讀:
  PSI < 0.1  → 穩定（Stable）
  0.1-0.25   → 輕微漂移（Warning）
  > 0.25     → 顯著漂移（Critical）

觸發條件:
  A. 每次新資料入庫後
  B. 每週定期檢查（由外部排程呼叫）
  C. RSM 趨勢異常時

2026-03-05 Created
"""
import os
import json
import math
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import Counter

import logging
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'lottery_v2.db'
)

# Zone 定義
ZONES = {
    'BIG_LOTTO':   [(1, 16), (17, 32), (33, 49)],
    'POWER_LOTTO': [(1, 13), (14, 26), (27, 38)],
    'DAILY_539':   [(1, 13), (14, 26), (27, 39)],
}

# 號碼池大小
NUM_POOL = {
    'BIG_LOTTO': 49,
    'POWER_LOTTO': 38,
    'DAILY_539': 39,
}

# PSI 門檻
PSI_WARNING  = 0.10
PSI_CRITICAL = 0.25


def _load_draws(lottery_type: str, limit: int = 3000) -> List[List[int]]:
    """從資料庫載入最新 N 期開獎號碼"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'SELECT numbers FROM draws WHERE lottery_type=? ORDER BY date ASC LIMIT ?',
        (lottery_type, limit)
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for (nums_str,) in rows:
        try:
            nums = json.loads(nums_str) if isinstance(nums_str, str) else nums_str
            result.append([int(n) for n in nums])
        except Exception:
            continue
    return result


def _compute_number_freq(draws: List[List[int]], pool_size: int) -> np.ndarray:
    """計算號碼頻率向量（歸一化為比例）"""
    counts = np.zeros(pool_size + 1)
    total = 0
    for draw in draws:
        for n in draw:
            if 1 <= n <= pool_size:
                counts[n] += 1
                total += 1
    if total == 0:
        return counts[1:]
    return counts[1:] / total


def _psi(expected: np.ndarray, actual: np.ndarray, eps: float = 1e-6) -> float:
    """計算 PSI (Population Stability Index)"""
    e = np.clip(expected, eps, None)
    a = np.clip(actual, eps, None)
    e = e / e.sum()
    a = a / a.sum()
    return float(np.sum((a - e) * np.log(a / e)))


def _ks_test(baseline: List[float], current: List[float]) -> Tuple[float, float]:
    """兩樣本 KS 檢定（近似），回傳 (statistic, p_value)"""
    try:
        from scipy import stats
        result = stats.ks_2samp(baseline, current)
        return result.statistic, result.pvalue
    except ImportError:
        # 無 scipy 時用簡單比較
        b = sorted(baseline)
        c = sorted(current)
        n1, n2 = len(b), len(c)
        if n1 == 0 or n2 == 0:
            return 0.0, 1.0
        all_vals = sorted(set(b + c))
        max_diff = 0.0
        for v in all_vals:
            cdf1 = sum(1 for x in b if x <= v) / n1
            cdf2 = sum(1 for x in c if x <= v) / n2
            max_diff = max(max_diff, abs(cdf1 - cdf2))
        # 簡單近似 p-value
        n = n1 * n2 / (n1 + n2)
        p_approx = max(0.0, 1.0 - 2 * math.exp(-2 * n * max_diff ** 2))
        return max_diff, 1.0 - p_approx


def _compute_sum_series(draws: List[List[int]]) -> List[float]:
    return [float(sum(d)) for d in draws]


def _compute_odd_even_series(draws: List[List[int]]) -> List[float]:
    """每期奇數比例"""
    result = []
    for d in draws:
        if len(d) == 0:
            continue
        odd_count = sum(1 for n in d if n % 2 == 1)
        result.append(odd_count / len(d))
    return result


def _compute_repeat_rate(draws: List[List[int]]) -> List[float]:
    """計算每期與上期的重號比例"""
    rates = []
    for i in range(1, len(draws)):
        prev = set(draws[i-1])
        curr = set(draws[i])
        rates.append(len(prev & curr) / len(curr) if curr else 0.0)
    return rates


class DriftReport:
    """單次漂移偵測報告"""

    def __init__(self, lottery_type: str, baseline_n: int, current_n: int,
                 check_time: str):
        self.lottery_type = lottery_type
        self.baseline_n = baseline_n
        self.current_n = current_n
        self.check_time = check_time
        self.metrics: Dict = {}
        self.overall_status = 'STABLE'  # STABLE | WARNING | CRITICAL

    def add_metric(self, name: str, value: float, status: str, note: str = ''):
        self.metrics[name] = {
            'value': round(value, 6),
            'status': status,
            'note': note,
        }
        # 升級整體狀態
        if status == 'CRITICAL':
            self.overall_status = 'CRITICAL'
        elif status == 'WARNING' and self.overall_status == 'STABLE':
            self.overall_status = 'WARNING'

    def to_dict(self) -> Dict:
        return {
            'lottery_type': self.lottery_type,
            'check_time': self.check_time,
            'baseline_n': self.baseline_n,
            'current_n': self.current_n,
            'overall_status': self.overall_status,
            'metrics': self.metrics,
        }

    def print_summary(self):
        icon = {'STABLE': '✅', 'WARNING': '⚠️', 'CRITICAL': '🔴'}
        print(f"\n{icon[self.overall_status]} [{self.lottery_type}] Drift Check "
              f"({self.check_time[:10]}) — {self.overall_status}")
        print(f"  Baseline: last {self.baseline_n}p | Current: last {self.current_n}p")
        for name, m in self.metrics.items():
            s_icon = {'STABLE': '  ✓', 'WARNING': '  ⚠', 'CRITICAL': '  ✗'}[m['status']]
            print(f"{s_icon} {name}: {m['value']:.4f} [{m['status']}]"
                  + (f" — {m['note']}" if m['note'] else ''))


def check_drift(
    lottery_type: str,
    baseline_n: int = 500,
    current_n: int = 100,
) -> DriftReport:
    """
    執行漂移偵測。

    Parameters
    ----------
    lottery_type : BIG_LOTTO | POWER_LOTTO | DAILY_539
    baseline_n   : 基線期數（從最新往前取，排除最近 current_n 期）
    current_n    : 當前窗口期數（最近 N 期）

    Returns
    -------
    DriftReport
    """
    all_draws = _load_draws(lottery_type, limit=10000)  # load all, then slice tail

    if len(all_draws) < baseline_n + current_n:
        logger.warning(f"[DriftDetector] Not enough data for {lottery_type}: "
                       f"{len(all_draws)} < {baseline_n + current_n}")
        report = DriftReport(lottery_type, baseline_n, current_n,
                             datetime.now().isoformat())
        return report

    baseline_draws = all_draws[-(baseline_n + current_n):-current_n]
    current_draws  = all_draws[-current_n:]

    pool_size = NUM_POOL[lottery_type]
    report = DriftReport(lottery_type, baseline_n, current_n,
                         datetime.now().isoformat())

    # ── 1. 號碼頻率 PSI ──────────────────────────────────────────────
    base_freq = _compute_number_freq(baseline_draws, pool_size)
    curr_freq = _compute_number_freq(current_draws, pool_size)
    psi_val = _psi(base_freq, curr_freq)
    psi_status = ('CRITICAL' if psi_val > PSI_CRITICAL
                  else 'WARNING' if psi_val > PSI_WARNING
                  else 'STABLE')
    report.add_metric('number_freq_PSI', psi_val, psi_status,
                      f"門檻: Warning>{PSI_WARNING}, Critical>{PSI_CRITICAL}")

    # ── 2. 和值分布 KS ───────────────────────────────────────────────
    base_sums = _compute_sum_series(baseline_draws)
    curr_sums = _compute_sum_series(current_draws)
    ks_stat, ks_p = _ks_test(base_sums, curr_sums)
    ks_status = 'CRITICAL' if ks_p < 0.01 else ('WARNING' if ks_p < 0.05 else 'STABLE')
    report.add_metric('sum_KS_stat', ks_stat, ks_status,
                      f"p={ks_p:.4f}")

    # 和值均值偏移
    base_sum_mean = float(np.mean(base_sums)) if base_sums else 0
    curr_sum_mean = float(np.mean(curr_sums)) if curr_sums else 0
    base_sum_std = float(np.std(base_sums)) if base_sums else 1
    sum_z = abs(curr_sum_mean - base_sum_mean) / (base_sum_std / math.sqrt(max(current_n, 1)))
    sum_shift_status = 'CRITICAL' if sum_z > 3.0 else ('WARNING' if sum_z > 2.0 else 'STABLE')
    report.add_metric('sum_mean_shift_z', sum_z, sum_shift_status,
                      f"base={base_sum_mean:.1f}, curr={curr_sum_mean:.1f}")

    # ── 3. 奇偶比 KS ─────────────────────────────────────────────────
    base_oe = _compute_odd_even_series(baseline_draws)
    curr_oe = _compute_odd_even_series(current_draws)
    oe_ks, oe_p = _ks_test(base_oe, curr_oe)
    oe_status = 'CRITICAL' if oe_p < 0.01 else ('WARNING' if oe_p < 0.05 else 'STABLE')
    report.add_metric('odd_even_KS', oe_ks, oe_status, f"p={oe_p:.4f}")

    # ── 4. 重號率 ─────────────────────────────────────────────────────
    base_repeat = _compute_repeat_rate(baseline_draws)
    curr_repeat = _compute_repeat_rate(current_draws)
    if base_repeat and curr_repeat:
        base_rr = float(np.mean(base_repeat))
        curr_rr = float(np.mean(curr_repeat))
        rr_std = float(np.std(base_repeat)) if len(base_repeat) > 1 else 0.01
        rr_z = abs(curr_rr - base_rr) / max(rr_std / math.sqrt(max(len(curr_repeat), 1)), 1e-6)
        rr_status = 'CRITICAL' if rr_z > 3.0 else ('WARNING' if rr_z > 2.0 else 'STABLE')
        report.add_metric('repeat_rate_z', rr_z, rr_status,
                          f"base={base_rr:.3f}, curr={curr_rr:.3f}")

    # ── 5. Zone 分布 PSI ─────────────────────────────────────────────
    zone_bounds = ZONES.get(lottery_type, [])
    if zone_bounds:
        def zone_dist(draws):
            z_counts = np.zeros(len(zone_bounds))
            total = 0
            for draw in draws:
                for n in draw:
                    for zi, (lo, hi) in enumerate(zone_bounds):
                        if lo <= n <= hi:
                            z_counts[zi] += 1
                            total += 1
                            break
            return z_counts / max(total, 1)

        base_zone = zone_dist(baseline_draws)
        curr_zone = zone_dist(current_draws)
        zone_psi = _psi(base_zone, curr_zone)
        zone_status = ('CRITICAL' if zone_psi > PSI_CRITICAL
                       else 'WARNING' if zone_psi > PSI_WARNING
                       else 'STABLE')
        report.add_metric('zone_dist_PSI', zone_psi, zone_status,
                          f"Z={[f'{v:.3f}' for v in curr_zone]}")

    return report


def check_all_lotteries(
    baseline_n: int = 500,
    current_n: int = 100,
    save_path: Optional[str] = None,
) -> Dict[str, DriftReport]:
    """檢查三彩種漂移狀態"""
    reports = {}
    for lottery in ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539']:
        r = check_drift(lottery, baseline_n=baseline_n, current_n=current_n)
        r.print_summary()
        reports[lottery] = r

    if save_path:
        result = {k: v.to_dict() for k, v in reports.items()}
        result['generated_at'] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n[DriftDetector] Report saved: {save_path}")

    return reports


if __name__ == '__main__':
    save_to = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'drift_report.json'
    )
    check_all_lotteries(baseline_n=500, current_n=100, save_path=save_to)
