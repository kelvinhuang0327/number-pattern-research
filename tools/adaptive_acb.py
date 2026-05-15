#!/usr/bin/env python3
"""
=============================================================================
AdaptiveACB — 跨彩種異常捕捉選號引擎
=============================================================================
原始設計: 539 ACB 單注 (Edge +2.80%, p=0.002, z=3.485 → ADOPTED)
本模組: 泛化至大樂透(49選6)、威力彩(38選6)

核心公式:
  score(n) = (freq_deficit × α_freq + gap_score × α_gap)
             × boundary_bonus × mod_k_bonus
  + cross-zone 約束

可調參數:
  - max_num, pick: 號碼池和選號數
  - window: 回看窗口
  - freq_w, gap_w: 頻率/間隔權重 (default 0.4/0.6)
  - boundary_pct: 邊界百分比 (default 0.13)
  - boundary_mult: 邊界加權 (default 1.2)
  - mod_k: 取餘數 k (default 3)
  - mod_mult: mod_k 加權 (default 1.1)
  - n_zones: zone 數量 (default 3)
  - min_zones: 最少覆蓋 zone 數 (default 2)
=============================================================================
"""

from collections import Counter
import math


class AdaptiveACB:
    """跨彩種異常捕捉選號引擎"""

    # 預設參數表（基於 539 已驗證結果 + 理論推導）
    PRESETS = {
        'DAILY_539': {
            'max_num': 39, 'pick': 5, 'window': 100,
            'freq_w': 0.4, 'gap_w': 0.6,
            'boundary_pct': 0.13, 'boundary_mult': 1.2,
            'mod_k': 3, 'mod_mult': 1.1,
            'n_zones': 3, 'min_zones': 2,
        },
        'BIG_LOTTO': {
            'max_num': 49, 'pick': 6, 'window': 100,
            'freq_w': 0.4, 'gap_w': 0.6,
            'boundary_pct': 0.13, 'boundary_mult': 1.2,
            'mod_k': 3, 'mod_mult': 1.1,
            'n_zones': 3, 'min_zones': 2,
        },
        'POWER_LOTTO': {
            'max_num': 38, 'pick': 6, 'window': 100,
            'freq_w': 0.4, 'gap_w': 0.6,
            'boundary_pct': 0.13, 'boundary_mult': 1.2,
            'mod_k': 3, 'mod_mult': 1.1,
            'n_zones': 3, 'min_zones': 2,
        },
    }

    def __init__(self, lottery_type=None, **overrides):
        if lottery_type and lottery_type in self.PRESETS:
            self.params = {**self.PRESETS[lottery_type], **overrides}
        else:
            self.params = overrides
        # Validate required
        for key in ['max_num', 'pick']:
            assert key in self.params, f"Missing required parameter: {key}"

    def _get_numbers(self, draw):
        """安全取得號碼列表"""
        n = draw.get('numbers', [])
        if isinstance(n, str):
            import json
            n = json.loads(n)
        return list(n)

    def score_numbers(self, hist):
        """
        對所有號碼計算 ACB 分數
        Returns: dict {number: score}
        """
        p = self.params
        max_num = p['max_num']
        pick = p['pick']
        window = p.get('window', 100)
        freq_w = p.get('freq_w', 0.4)
        gap_w = p.get('gap_w', 0.6)
        boundary_pct = p.get('boundary_pct', 0.13)
        boundary_mult = p.get('boundary_mult', 1.2)
        mod_k = p.get('mod_k', 3)
        mod_mult = p.get('mod_mult', 1.1)

        recent = hist[-window:] if len(hist) >= window else hist
        w_len = len(recent)

        # 頻率計數
        counter = Counter()
        for n in range(1, max_num + 1):
            counter[n] = 0
        for d in recent:
            for n in self._get_numbers(d):
                counter[n] += 1

        # Gap (距上次出現的距離)
        last_seen = {}
        for i, d in enumerate(recent):
            for n in self._get_numbers(d):
                last_seen[n] = i
        current = w_len
        gaps = {n: current - last_seen.get(n, -1) for n in range(1, max_num + 1)}

        # 期望頻率
        expected_freq = w_len * pick / max_num

        # 邊界判定
        boundary_low = math.ceil(max_num * boundary_pct)
        boundary_high = max_num - boundary_low + 1

        # 計算分數
        scores = {}
        for n in range(1, max_num + 1):
            freq_deficit = expected_freq - counter[n]
            gap_score = gaps[n] / (w_len / 2) if w_len > 0 else 0

            b_bonus = boundary_mult if (n <= boundary_low or n >= boundary_high) else 1.0
            m_bonus = mod_mult if (mod_k > 0 and n % mod_k == 0) else 1.0

            scores[n] = (freq_deficit * freq_w + gap_score * gap_w) * b_bonus * m_bonus

        return scores

    def predict(self, hist):
        """
        返回一注號碼
        Returns: sorted list of numbers
        """
        p = self.params
        max_num = p['max_num']
        pick = p['pick']
        n_zones = p.get('n_zones', 3)
        min_zones = p.get('min_zones', 2)

        scores = self.score_numbers(hist)
        ranked = sorted(scores, key=lambda x: -scores[x])

        # Zone 分區
        zone_size = max_num / n_zones

        def get_zone(n):
            return min(int((n - 1) / zone_size), n_zones - 1)

        zones_selected = set()
        result = []
        for n in ranked:
            zone = get_zone(n)
            if len(result) < pick:
                result.append(n)
                zones_selected.add(zone)
            if len(result) >= pick:
                break

        # Cross-zone 修正
        if len(zones_selected) < min_zones and len(result) >= pick:
            missing_zones = set(range(n_zones)) - zones_selected
            for mz in missing_zones:
                zone_nums = [n for n in range(1, max_num + 1) if get_zone(n) == mz]
                zone_ranked = sorted(zone_nums, key=lambda x: -scores[x])
                if zone_ranked:
                    result[-1] = zone_ranked[0]
                    break

        return sorted(result[:pick])

    def predict_topk(self, hist, k=None):
        """
        返回 Top-K 排名號碼（供多注組合使用）
        k: 返回前 k 個號碼，默認 pick * 3
        """
        p = self.params
        if k is None:
            k = p['pick'] * 3
        scores = self.score_numbers(hist)
        ranked = sorted(scores, key=lambda x: -scores[x])
        return ranked[:k], scores


# ─── 便捷函數 ─────────────────────────────────────────────────────
def predict_acb_539(hist, window=100):
    """539 ACB (原始已驗證版本)"""
    acb = AdaptiveACB('DAILY_539', window=window)
    return acb.predict(hist)


def predict_acb_biglotto(hist, window=100):
    """大樂透 ACB"""
    acb = AdaptiveACB('BIG_LOTTO', window=window)
    return acb.predict(hist)


def predict_acb_power(hist, window=100):
    """威力彩 ACB"""
    acb = AdaptiveACB('POWER_LOTTO', window=window)
    return acb.predict(hist)


if __name__ == '__main__':
    import os, sys
    _base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
    sys.path.insert(0, os.path.join(_base, '..'))
    from database import DatabaseManager

    db_path = os.path.join(_base, '..', 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)

    print("=" * 70)
    print("  AdaptiveACB — 跨彩種異常捕捉選號引擎")
    print("=" * 70)

    for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
        draws = sorted(db.get_all_draws(lt), key=lambda x: (x['date'], x['draw']))
        acb = AdaptiveACB(lt)
        bet = acb.predict(draws)
        p = acb.params
        print(f"\n  {lt} ({len(draws)} draws, {p['max_num']}選{p['pick']}):")
        print(f"    預測: {bet}")
        print(f"    最新期: {draws[-1]['draw']} ({draws[-1]['date']})")
