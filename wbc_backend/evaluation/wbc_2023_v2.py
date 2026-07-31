#!/usr/bin/env python3
"""
WBC 2023 回測 v2 — 套用優化後的 Elo-Heavy 權重

改進:
  1. Elo 權重提高到 45% (原 35%)
  2. Form 權重降到 5% (原 15%)
  3. Star power 保持 10%
  4. 加入 Round-Adaptive 動態權重
  5. 加入投注模擬 (edge≥5%, conf≥58%)
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


WBC_2023_GAMES = [
    # Pool A (台中)
    ("NED", "CUB", 4, 2, "Pool A"),
    ("TPE", "PAN", 5, 12, "Pool A"),
    ("NED", "PAN", 3, 1, "Pool A"),
    ("CUB", "ITA", 3, 6, "Pool A"),
    ("PAN", "CUB", 4, 13, "Pool A"),
    ("TPE", "ITA", 11, 7, "Pool A"),
    ("ITA", "PAN", 0, 2, "Pool A"),
    ("TPE", "NED", 9, 5, "Pool A"),
    ("CUB", "TPE", 7, 1, "Pool A"),
    ("ITA", "NED", 7, 1, "Pool A"),
    # Pool B (東京)
    ("KOR", "AUS", 7, 8, "Pool B"),
    ("JPN", "CHN", 8, 1, "Pool B"),
    ("CHN", "CZE", 5, 8, "Pool B"),
    ("JPN", "KOR", 13, 4, "Pool B"),
    ("AUS", "CHN", 12, 2, "Pool B"),
    ("JPN", "CZE", 10, 2, "Pool B"),
    ("KOR", "CZE", 10, 3, "Pool B"),
    ("AUS", "JPN", 1, 7, "Pool B"),
    ("CZE", "AUS", 3, 8, "Pool B"),
    ("CHN", "KOR", 2, 22, "Pool B"),
    # Pool C (Phoenix)
    ("MEX", "COL", 4, 5, "Pool C"),
    ("USA", "GBR", 6, 2, "Pool C"),
    ("CAN", "GBR", 18, 8, "Pool C"),
    ("USA", "MEX", 5, 11, "Pool C"),
    ("GBR", "COL", 7, 5, "Pool C"),
    ("USA", "CAN", 12, 1, "Pool C"),
    ("COL", "CAN", 0, 5, "Pool C"),
    ("MEX", "GBR", 2, 1, "Pool C"),
    ("CAN", "MEX", 3, 10, "Pool C"),
    ("COL", "USA", 2, 3, "Pool C"),
    # Pool D (Miami)
    ("PUR", "NIC", 9, 1, "Pool D"),
    ("VEN", "DOM", 5, 1, "Pool D"),
    ("ISR", "NIC", 3, 1, "Pool D"),
    ("PUR", "VEN", 6, 9, "Pool D"),
    ("NIC", "DOM", 1, 6, "Pool D"),
    ("PUR", "ISR", 10, 0, "Pool D"),
    ("VEN", "NIC", 4, 1, "Pool D"),
    ("DOM", "ISR", 10, 0, "Pool D"),
    ("ISR", "VEN", 1, 5, "Pool D"),
    ("DOM", "PUR", 2, 5, "Pool D"),
    # QF
    ("JPN", "ITA", 9, 3, "QF"),
    ("USA", "VEN", 9, 7, "QF"),
    ("MEX", "PUR", 5, 4, "QF"),
    ("CUB", "AUS", 4, 3, "QF"),
    # SF
    ("USA", "CUB", 14, 2, "SF"),
    ("JPN", "MEX", 6, 5, "SF"),
    # Final
    ("USA", "JPN", 2, 3, "Final"),
]

# 2023 陣容 MLB 球星數量
MLB_STARS = {
    "JPN": 8, "USA": 12, "DOM": 7, "VEN": 6, "PUR": 5, "CUB": 3,
    "KOR": 3, "MEX": 4, "NED": 2, "TPE": 2, "AUS": 1, "ITA": 3,
    "CAN": 3, "COL": 1, "PAN": 1, "GBR": 0, "ISR": 1, "CZE": 0,
    "NIC": 0, "CHN": 0,
}

# 模擬 WBC 盤口 (decimal odds)
# 用 Elo 差距推算合理盤口 + 8% vig
def make_odds(elo_h, elo_a, vig=0.08):
    diff = elo_h - elo_a
    fair = 1.0 / (1.0 + 10 ** (-diff / 400.0))
    h_dec = (1.0 / fair) * (1 - vig / 2)
    a_dec = (1.0 / (1 - fair)) * (1 - vig / 2)
    return h_dec, a_dec, fair


def poisson_wp(lam_h, lam_a):
    from scipy.stats import poisson
    r = np.arange(20)
    ph = poisson.pmf(r, max(0.5, lam_h))
    pa = poisson.pmf(r, max(0.5, lam_a))
    hw = sum(ph[h] * pa[a] for h in range(20) for a in range(h))
    draw = sum(ph[i] * pa[i] for i in range(20))
    return hw + draw * 0.5


def pythag(rpg, rapg):
    if rpg + rapg <= 0:
        return 0.5
    return rpg ** 1.83 / (rpg ** 1.83 + rapg ** 1.83)


def log5(pa, pb):
    if pa + pb == 0:
        return 0.5
    return pa * (1 - pb) / (pa * (1 - pb) + pb * (1 - pa))


def run():  # noqa: C901
    print()
    print("=" * 70)
    print("🏆 WBC 2023 回測 v2 (Elo-Heavy 優化版)")
    print("=" * 70)
    print()

    # ── v1 vs v2 Weight comparison ──
    print("  權重比較:")
    print("  Model      v1 (Pool)   v2 (Pool)   v2 (KO)")
    print("  ─────────  ──────────  ──────────  ────────")
    print("  Elo         35%         45%         40%")
    print("  Poisson     20%         20%         25%")
    print("  Pythag      15%         15%         20%")
    print("  Form        15%          5%         10%")
    print("  Stars       15%         15%          5%")
    print()

    elo = defaultdict(lambda: 1500.0)
    # Init with base Elo
    base_elo = {
        "JPN": 1650, "USA": 1640, "DOM": 1580, "VEN": 1560,
        "PUR": 1560, "CUB": 1550, "KOR": 1540, "MEX": 1530,
        "NED": 1510, "TPE": 1500, "AUS": 1480, "ITA": 1470,
        "CAN": 1460, "COL": 1450, "PAN": 1440, "GBR": 1420,
        "ISR": 1410, "CZE": 1400, "NIC": 1390, "CHN": 1380,
    }
    for t, r in base_elo.items():
        elo[t] = r

    runs_for = defaultdict(list)
    runs_against = defaultdict(list)
    results = defaultdict(list)

    total = 0
    correct = 0
    by_round = defaultdict(lambda: {"total": 0, "correct": 0})

    # Betting
    bankroll = 100_000.0
    peak = 100_000.0
    max_dd = 0.0
    bet_count = 0
    bet_wins = 0
    total_staked = 0.0
    total_pnl = 0.0
    bet_details = []

    for home, away, hs, aws, rnd in WBC_2023_GAMES:
        actual_hw = 1 if hs > aws else 0

        # 1. Elo
        p_elo = 1.0 / (1.0 + 10 ** (-(elo[home] - elo[away]) / 400.0))

        # 2. Stars
        star_diff = MLB_STARS.get(home, 0) - MLB_STARS.get(away, 0)
        p_star = 0.5 + star_diff * 0.015

        # 3. Poisson
        if runs_for[home] and runs_for[away]:
            h_rpg = sum(runs_for[home][-5:]) / len(runs_for[home][-5:])
            h_rapg = sum(runs_against[home][-5:]) / len(runs_against[home][-5:])
            a_rpg = sum(runs_for[away][-5:]) / len(runs_for[away][-5:])
            a_rapg = sum(runs_against[away][-5:]) / len(runs_against[away][-5:])
            exp_h = (h_rpg + a_rapg) / 2
            exp_a = (a_rpg + h_rapg) / 2
            p_poisson = poisson_wp(exp_h, exp_a)
        else:
            p_poisson = p_elo

        # 4. Pythagorean
        if len(runs_for[home]) >= 2 and len(runs_for[away]) >= 2:
            h = pythag(sum(runs_for[home][-5:])/len(runs_for[home][-5:]),
                       sum(runs_against[home][-5:])/len(runs_against[home][-5:]))
            a = pythag(sum(runs_for[away][-5:])/len(runs_for[away][-5:]),
                       sum(runs_against[away][-5:])/len(runs_against[away][-5:]))
            p_pythag = log5(h, a)
        else:
            p_pythag = p_elo

        # 5. Form
        if results[home] and results[away]:
            h_f = sum(results[home][-3:]) / len(results[home][-3:])
            a_f = sum(results[away][-3:]) / len(results[away][-3:])
            p_form = (h_f + 0.01) / (h_f + a_f + 0.02)
        else:
            p_form = 0.5

        # ── v2 Elo-Heavy Ensemble (Round-Adaptive) ──
        if rnd.startswith("Pool"):
            # Pool: 更依賴 Elo (資料少)
            p = (0.45 * p_elo +
                 0.20 * p_poisson +
                 0.15 * p_pythag +
                 0.05 * p_form +
                 0.15 * p_star)
        else:
            # KO: 加入更多 performance data
            p = (0.40 * p_elo +
                 0.25 * p_poisson +
                 0.20 * p_pythag +
                 0.10 * p_form +
                 0.05 * p_star)

        p = max(0.08, min(0.92, p))

        # ── Evaluate ──
        total += 1
        predicted_hw = p > 0.5
        is_correct = predicted_hw == (actual_hw == 1)
        if is_correct:
            correct += 1
        by_round[rnd]["total"] += 1
        if is_correct:
            by_round[rnd]["correct"] += 1

        # ── Betting (edge≥5%, conf≥58%) ──
        h_dec, a_dec, market_fair = make_odds(elo[home], elo[away])
        edge_h = p - market_fair
        edge_a = (1 - p) - (1 - market_fair)

        bet_side = None

        if edge_h >= 0.05 and p >= 0.58:
            bet_side = "home"
            bet_prob = p
            bet_odds = h_dec
            edge = edge_h
        elif edge_a >= 0.05 and (1 - p) >= 0.58:
            bet_side = "away"
            bet_prob = 1 - p
            bet_odds = a_dec
            edge = edge_a

        if bet_side and bet_odds > 1.0:
            b = bet_odds - 1
            k = max(0, (b * bet_prob - (1 - bet_prob)) / b) * 0.15
            stake = bankroll * min(k, 0.04)

            if stake >= 50:
                won = (bet_side == "home" and actual_hw == 1) or (bet_side == "away" and actual_hw == 0)
                pnl = stake * (bet_odds - 1) if won else -stake

                bankroll += pnl
                total_staked += stake
                total_pnl += pnl
                bet_count += 1
                if won:
                    bet_wins += 1
                peak = max(peak, bankroll)
                max_dd = max(max_dd, (peak - bankroll) / peak)

                marker = "✅" if won else "❌"
                bet_details.append(
                    f"  {marker} {away}@{home} → bet {bet_side.upper()} "
                    f"(p={bet_prob:.0%}, edge={edge:.0%}, odds={bet_odds:.2f}) "
                    f"${stake:.0f} → ${pnl:+,.0f}"
                )

        # ── Update ──
        runs_for[home].append(hs)
        runs_for[away].append(aws)
        runs_against[home].append(aws)
        runs_against[away].append(hs)
        results[home].append(actual_hw)
        results[away].append(1 - actual_hw)

        elo_exp = 1.0 / (1.0 + 10 ** (-(elo[home] - elo[away]) / 400.0))
        margin = abs(hs - aws)
        mov = 1.0 + 0.08 * min(margin, 10)
        delta = 16.0 * mov * (actual_hw - elo_exp)
        elo[home] += delta
        elo[away] -= delta

    accuracy = correct / total

    print("━" * 60)
    print(f"🎯 整體準確率: {accuracy:.1%}  ({correct}/{total})")
    print("━" * 60)
    print()

    print("━" * 60)
    print("📊 各輪準確率")
    print("━" * 60)
    for rnd in ["Pool A", "Pool B", "Pool C", "Pool D", "QF", "SF", "Final"]:
        if rnd in by_round:
            d = by_round[rnd]
            acc = d["correct"] / d["total"]
            bar = "█" * int(acc * 20)
            print(f"  {rnd:8s}: {acc:>4.0%} ({d['correct']}/{d['total']}) {bar}")
    print()

    ko = sum(by_round[r]["correct"] for r in ["QF", "SF", "Final"] if r in by_round)
    ko_t = sum(by_round[r]["total"] for r in ["QF", "SF", "Final"] if r in by_round)

    print("━" * 60)
    print("💰 投注模擬 (edge≥5%, conf≥58%)")
    print("━" * 60)
    if bet_count:
        roi = total_pnl / total_staked
        print(f"  投注場數:   {bet_count}/{total} ({bet_count/total*100:.0f}% 選擇率)")
        print(f"  投注勝率:   {bet_wins/bet_count:.1%}  ({bet_wins}/{bet_count})")
        print(f"  總下注:     ${total_staked:,.0f}")
        print(f"  淨利:       ${total_pnl:+,.0f}")
        print(f"  ROI:        {roi:+.1%}")
        print(f"  最終資金:   ${bankroll:,.0f}")
        print(f"  Max DD:     {max_dd:.1%}")
        print()
        print("  投注明細:")
        for d in bet_details:
            print(d)
    else:
        print("  ⚠️ 無符合門檻的投注")
    print()

    print("=" * 70)
    print("📋 總結:")
    print(f"  ✅ 整體: {accuracy:.1%} ({correct}/{total})")
    print(f"  ✅ 淘汰賽: {ko}/{ko_t} = {ko/ko_t:.0%}" if ko_t else "")
    if bet_count:
        print(f"  {'✅' if total_pnl > 0 else '❌'} 投注 ROI: {total_pnl/total_staked:+.1%}")
    print("=" * 70)


if __name__ == "__main__":
    run()
