#!/usr/bin/env python3
"""
Core-Satellite 組注策略產生器 (Layer 2)

這不是預測方法，而是「組注結構」優化器。
給定一組候選號碼（來自任何 Layer 1 預測方法），
將它們結構化分配到多注中，平衡「穩定小獎」與「大獎機率」。

核心原理：
- 錨點 (Core): 出現在每一注中，命中時所有注都受益
- 衛星 (Satellite): 每注不同，提供覆蓋多樣性
- 大獎機率不受影響（每注都是合法的完整組合）
- 小獎穩定性提高（錨點命中時，所有注保底）

用法:
    from lottery_api.engine.core_satellite import CoreSatelliteGenerator

    gen = CoreSatelliteGenerator(max_number=38, pick_count=6)

    # 方式 1: 傳入已排序的候選池（最有信心的排前面）
    bets = gen.generate(
        pool=[7, 12, 18, 25, 31, 36, 3, 9, 15, 22, 28, 33],
        num_bets=3,
        num_anchors=3
    )

    # 方式 2: 傳入帶分數的候選池
    bets = gen.generate_from_scores(
        scores={7: 0.95, 12: 0.90, 18: 0.85, 25: 0.80, ...},
        num_bets=3,
        num_anchors=3
    )
"""

import random
from typing import List, Dict, Optional, Tuple
from collections import Counter


class CoreSatelliteGenerator:
    """
    Core-Satellite 組注產生器

    Layer 2 模組：不做預測，只負責把候選號碼分配到多注中。
    """

    def __init__(self, max_number: int, pick_count: int, min_number: int = 1):
        self.min_number = min_number
        self.max_number = max_number
        self.pick_count = pick_count
        self.all_numbers = set(range(min_number, max_number + 1))

    def generate(
        self,
        pool: List[int],
        num_bets: int = 3,
        num_anchors: int = 3,
        seed: Optional[int] = None,
    ) -> Dict:
        """
        從候選池生成 Core-Satellite 組注。

        Args:
            pool: 候選號碼列表，按優先順序排列（最有信心的在前）
            num_bets: 要產生幾注 (2-5)
            num_anchors: 共享錨點數量 (建議: 2-4)
            seed: 隨機種子（影響衛星填充，不影響錨點選擇）

        Returns:
            {
                'bets': [[1,2,3,4,5,6], [1,2,3,7,8,9], ...],
                'anchors': [1,2,3],
                'satellites': [[4,5,6], [7,8,9], ...],
                'stats': { 覆蓋統計 }
            }
        """
        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = random.Random()

        num_bets = max(2, min(num_bets, 10))
        num_anchors = max(1, min(num_anchors, self.pick_count - 1))
        sat_per_bet = self.pick_count - num_anchors

        # 過濾合法號碼
        pool = [n for n in pool if self.min_number <= n <= self.max_number]

        # --- 選錨點：池中前 num_anchors 個 ---
        anchors = pool[:num_anchors]

        # 池不夠大時，從全空間補
        if len(anchors) < num_anchors:
            remaining = sorted(self.all_numbers - set(anchors))
            rng.shuffle(remaining)
            anchors.extend(remaining[: num_anchors - len(anchors)])

        anchor_set = set(anchors)

        # --- 分配衛星 ---
        # 衛星候選：池中非錨點的號碼
        sat_candidates = [n for n in pool if n not in anchor_set]

        # 需要的衛星總數
        total_sats_needed = sat_per_bet * num_bets

        # 候選不夠時，從全空間補充
        if len(sat_candidates) < total_sats_needed:
            filler = sorted(self.all_numbers - anchor_set - set(sat_candidates))
            rng.shuffle(filler)
            sat_candidates.extend(filler)

        # 分配：每注拿 sat_per_bet 個，不重疊
        satellites = []
        used = set()
        for i in range(num_bets):
            bet_sats = []
            for n in sat_candidates:
                if n not in used and len(bet_sats) < sat_per_bet:
                    bet_sats.append(n)
                    used.add(n)
            # 極端情況：衛星用完了，隨機補
            if len(bet_sats) < sat_per_bet:
                emergency = sorted(self.all_numbers - anchor_set - used)
                rng.shuffle(emergency)
                for n in emergency:
                    if len(bet_sats) >= sat_per_bet:
                        break
                    bet_sats.append(n)
                    used.add(n)
            satellites.append(sorted(bet_sats))

        # --- 組合成完整注單 ---
        bets = []
        for sat in satellites:
            bet = sorted(set(anchors) | set(sat))
            bets.append(bet)

        # --- 統計 ---
        all_unique = set()
        for b in bets:
            all_unique.update(b)

        stats = {
            'num_bets': num_bets,
            'num_anchors': num_anchors,
            'satellites_per_bet': sat_per_bet,
            'unique_numbers': len(all_unique),
            'coverage_pct': round(len(all_unique) / (self.max_number - self.min_number + 1) * 100, 1),
            'pool_size': len(pool),
            'anchor_risk': _anchor_risk_label(num_anchors, self.pick_count),
        }

        return {
            'bets': bets,
            'anchors': sorted(anchors),
            'satellites': satellites,
            'stats': stats,
        }

    def generate_from_scores(
        self,
        scores: Dict[int, float],
        num_bets: int = 3,
        num_anchors: int = 3,
        seed: Optional[int] = None,
    ) -> Dict:
        """
        從帶分數的候選池生成組注。分數越高 = 越有信心。

        Args:
            scores: {號碼: 信心分數} 字典
            num_bets, num_anchors, seed: 同 generate()
        """
        # 按分數降序排列
        pool = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
        return self.generate(pool, num_bets, num_anchors, seed)

    def generate_from_history(
        self,
        history: List[Dict],
        num_bets: int = 3,
        num_anchors: int = 3,
        window: int = 30,
        method: str = 'mid_frequency',
        seed: Optional[int] = None,
    ) -> Dict:
        """
        從歷史數據自動建立候選池，再生成組注。

        Args:
            history: 歷史開獎記錄 [{'numbers': [...], ...}, ...]
            num_bets: 注數
            num_anchors: 錨點數
            window: 統計近幾期
            method: 候選池選擇方法
                - 'mid_frequency': 中頻號碼（出現 3-5 次），最穩定
                - 'hot': 最熱號碼
                - 'cold': 最冷號碼
                - 'balanced': 熱+冷混合
            seed: 隨機種子
        """
        recent = history[-window:] if len(history) > window else history

        freq = Counter()
        for draw in recent:
            nums = draw.get('numbers', [])
            if isinstance(nums, str):
                import json
                nums = json.loads(nums)
            for n in nums:
                if self.min_number <= n <= self.max_number:
                    freq[n] += 1

        all_nums = list(range(self.min_number, self.max_number + 1))

        if method == 'hot':
            pool = sorted(all_nums, key=lambda n: freq.get(n, 0), reverse=True)
        elif method == 'cold':
            pool = sorted(all_nums, key=lambda n: freq.get(n, 0))
        elif method == 'balanced':
            # 熱冷交替
            hot = sorted(all_nums, key=lambda n: freq.get(n, 0), reverse=True)
            cold = sorted(all_nums, key=lambda n: freq.get(n, 0))
            pool = []
            for h, c in zip(hot, cold):
                if h not in pool:
                    pool.append(h)
                if c not in pool:
                    pool.append(c)
        else:
            # mid_frequency: 中頻優先 (出現次數接近期望值的最穩定)
            expected = window * self.pick_count / (self.max_number - self.min_number + 1)
            pool = sorted(
                all_nums,
                key=lambda n: abs(freq.get(n, 0) - expected)
            )

        return self.generate(pool, num_bets, num_anchors, seed)


def _anchor_risk_label(num_anchors: int, pick_count: int) -> str:
    ratio = num_anchors / pick_count
    if ratio <= 0.33:
        return '低風險（錨點少，沉船機率低）'
    elif ratio <= 0.5:
        return '中等風險（推薦平衡點）'
    else:
        return '高風險（錨點多，沉船機率較高）'


# ========== 便利函式 ==========

LOTTERY_PRESETS = {
    'POWER_LOTTO': {'min_number': 1, 'max_number': 38, 'pick_count': 6},
    'BIG_LOTTO':   {'min_number': 1, 'max_number': 49, 'pick_count': 6},
    'DAILY_539':   {'min_number': 1, 'max_number': 39, 'pick_count': 5},
}


def make_generator(lottery_type: str) -> CoreSatelliteGenerator:
    """根據彩種建立產生器"""
    preset = LOTTERY_PRESETS.get(lottery_type)
    if not preset:
        raise ValueError(f"不支援的彩種: {lottery_type}, 可用: {list(LOTTERY_PRESETS.keys())}")
    return CoreSatelliteGenerator(**preset)


def quick_generate(
    lottery_type: str,
    pool: List[int],
    num_bets: int = 3,
    num_anchors: int = 3,
    seed: Optional[int] = None,
) -> List[List[int]]:
    """一行呼叫，直接回傳注單列表"""
    gen = make_generator(lottery_type)
    result = gen.generate(pool, num_bets, num_anchors, seed)
    return result['bets']


# ========== CLI ==========

def _print_report(result: Dict, lottery_type: str):
    """印出組注報告"""
    stats = result['stats']
    print(f"\n{'='*50}")
    print(f"  Core-Satellite 組注報告 ({lottery_type})")
    print(f"{'='*50}")
    print(f"  錨點 ({stats['num_anchors']}個): {result['anchors']}")
    print(f"  風險等級: {stats['anchor_risk']}")
    print(f"  覆蓋號碼數: {stats['unique_numbers']} ({stats['coverage_pct']}%)")
    print(f"{'='*50}")

    for i, (bet, sat) in enumerate(zip(result['bets'], result['satellites'])):
        anchor_str = ','.join(str(n) for n in result['anchors'])
        sat_str = ','.join(str(n) for n in sat)
        print(f"  注{i+1}: {bet}")
        print(f"        核心=[{anchor_str}] + 衛星=[{sat_str}]")

    print(f"{'='*50}")
    print(f"  ✓ 大獎機率 = {stats['num_bets']}/C({LOTTERY_PRESETS[lottery_type]['max_number']},{LOTTERY_PRESETS[lottery_type]['pick_count']}) (與任何{stats['num_bets']}注相同)")
    print(f"  ✓ 錨點全中時，每注保底 {stats['num_anchors']} 個")
    print(f"  ✓ 衛星互不重疊，覆蓋 {stats['unique_numbers']} 個不同號碼")
    print()


def main():
    import argparse
    import sys

    # 加入 parent path 以便獨立執行
    sys.path.insert(0, __file__.rsplit('/', 2)[0])

    parser = argparse.ArgumentParser(
        description='Core-Satellite 組注產生器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 指定候選池
  python3 core_satellite.py -l POWER_LOTTO -p 7 12 18 25 31 36 3 9 15 22 28 33

  # 從歷史自動產生 (中頻法)
  python3 core_satellite.py -l BIG_LOTTO --from-history --method mid_frequency

  # 2注 + 2錨點 (低風險)
  python3 core_satellite.py -l POWER_LOTTO --from-history -n 2 -a 2
        """
    )
    parser.add_argument('-l', '--lottery', default='POWER_LOTTO',
                        choices=list(LOTTERY_PRESETS.keys()),
                        help='彩種 (default: POWER_LOTTO)')
    parser.add_argument('-p', '--pool', nargs='+', type=int,
                        help='候選號碼池（按信心排序）')
    parser.add_argument('-n', '--num-bets', type=int, default=3,
                        help='注數 (default: 3)')
    parser.add_argument('-a', '--num-anchors', type=int, default=3,
                        help='錨點數 (default: 3)')
    parser.add_argument('-s', '--seed', type=int, default=None,
                        help='隨機種子')
    parser.add_argument('--from-history', action='store_true',
                        help='從歷史數據自動建立候選池')
    parser.add_argument('--method', default='mid_frequency',
                        choices=['mid_frequency', 'hot', 'cold', 'balanced'],
                        help='候選池方法 (搭配 --from-history)')
    parser.add_argument('--window', type=int, default=30,
                        help='統計窗口期數 (搭配 --from-history, default: 30)')

    args = parser.parse_args()
    gen = make_generator(args.lottery)

    if args.from_history:
        try:
            from database import DatabaseManager
        except ImportError:
            from lottery_api.database import DatabaseManager

        db_path = None
        import os
        for candidate in [
            os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'),
            os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery.db'),
        ]:
            if os.path.exists(candidate):
                db_path = candidate
                break

        if not db_path:
            print("找不到資料庫，請指定 --pool")
            sys.exit(1)

        db = DatabaseManager(db_path=db_path)
        history = list(reversed(db.get_all_draws(args.lottery)))
        if not history:
            print(f"找不到 {args.lottery} 的歷史數據")
            sys.exit(1)

        print(f"載入 {len(history)} 期 {args.lottery} 歷史數據")
        result = gen.generate_from_history(
            history,
            num_bets=args.num_bets,
            num_anchors=args.num_anchors,
            window=args.window,
            method=args.method,
            seed=args.seed,
        )
    elif args.pool:
        result = gen.generate(
            pool=args.pool,
            num_bets=args.num_bets,
            num_anchors=args.num_anchors,
            seed=args.seed,
        )
    else:
        print("請指定 --pool 或 --from-history")
        parser.print_help()
        sys.exit(1)

    _print_report(result, args.lottery)


if __name__ == '__main__':
    main()
