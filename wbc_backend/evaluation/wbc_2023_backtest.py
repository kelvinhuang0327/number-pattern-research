#!/usr/bin/env python3
"""
WBC 2023 真實回測 — 使用完整 2023 WBC 比賽數據

所有 55 場比賽 (Pool Play + Quarter + Semi + Final)
用我們的 Elo + Poisson + Pythagorean + Form 模型預測
與真實結果對比
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


# ═══════════════════════════════════════════════════════════════
# 2023 WBC 完整比賽數據 (55 場)
# ═══════════════════════════════════════════════════════════════

WBC_2023_GAMES = [
    # Pool A (台中)
    # (home, away, home_score, away_score, round)
    ("NED", "CUB", 4, 2, "Pool A"),
    ("TPE", "PAN", 5, 12, "Pool A"),
    ("NED", "PAN", 3, 1, "Pool A"),
    ("CUB", "ITA", 3, 6, "Pool A"),   # F/10
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
    ("AUS", "CHN", 12, 2, "Pool B"),   # F/7
    ("JPN", "CZE", 10, 2, "Pool B"),
    ("KOR", "CZE", 10, 3, "Pool B"),
    ("AUS", "JPN", 1, 7, "Pool B"),
    ("CZE", "AUS", 3, 8, "Pool B"),
    ("CHN", "KOR", 2, 22, "Pool B"),   # F/5

    # Pool C (Phoenix)
    ("MEX", "COL", 4, 5, "Pool C"),    # F/10
    ("USA", "GBR", 6, 2, "Pool C"),
    ("CAN", "GBR", 18, 8, "Pool C"),   # F/7
    ("USA", "MEX", 5, 11, "Pool C"),
    ("GBR", "COL", 7, 5, "Pool C"),
    ("USA", "CAN", 12, 1, "Pool C"),   # F/7
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
    ("PUR", "ISR", 10, 0, "Pool D"),   # F/8
    ("VEN", "NIC", 4, 1, "Pool D"),
    ("DOM", "ISR", 10, 0, "Pool D"),   # F/7
    ("ISR", "VEN", 1, 5, "Pool D"),
    ("DOM", "PUR", 2, 5, "Pool D"),

    # Quarterfinals
    ("JPN", "ITA", 9, 3, "QF"),
    ("USA", "VEN", 9, 7, "QF"),
    ("MEX", "PUR", 5, 4, "QF"),
    ("CUB", "AUS", 4, 3, "QF"),

    # Semifinals
    ("USA", "CUB", 14, 2, "SF"),
    ("JPN", "MEX", 6, 5, "SF"),

    # Final
    ("USA", "JPN", 2, 3, "Final"),
]

# ── 各國基礎 Elo (根據歷史實力 + 2023 陣容) ──
BASE_ELO = {
    "JPN": 1650, "USA": 1640, "DOM": 1580, "VEN": 1560,
    "PUR": 1560, "CUB": 1550, "KOR": 1540, "MEX": 1530,
    "NED": 1510, "TPE": 1500, "AUS": 1480, "ITA": 1470,
    "CAN": 1460, "COL": 1450, "PAN": 1440, "GBR": 1420,
    "ISR": 1410, "CZE": 1400, "NIC": 1390, "CHN": 1380,
}

# ── 各國 2023 陣容 MLB 球星數量 (影響實力) ──
MLB_STARS = {
    "JPN": 8,   # Ohtani, Darvish, Senga, Suzuki, Yoshida, etc.
    "USA": 12,  # Trout, Goldschmidt, Turner, DeGrom, etc.
    "DOM": 7,   # Soto, Machado, Ramirez, etc.
    "VEN": 6,   # Altuve, Acuña, Torres, etc.
    "PUR": 5,
    "CUB": 3,
    "KOR": 3,
    "MEX": 4,
    "NED": 2,
    "TPE": 2,
    "AUS": 1,
    "ITA": 3,   # Frelick, etc.
    "CAN": 3,   # Freddie Freeman, etc.
    "COL": 1,
    "PAN": 1,
    "GBR": 0,
    "ISR": 1,
    "CZE": 0,
    "NIC": 0,
    "CHN": 0,
}


def poisson_win_prob(lam_h: float, lam_a: float) -> float:
    from scipy.stats import poisson
    r = np.arange(20)
    ph = poisson.pmf(r, max(0.5, lam_h))
    pa = poisson.pmf(r, max(0.5, lam_a))
    hw = sum(ph[h] * pa[a] for h in range(20) for a in range(h))
    draw = sum(ph[i] * pa[i] for i in range(20))
    return hw + draw * 0.5


def pythag_wp(rpg: float, rapg: float) -> float:
    if rpg + rapg <= 0:
        return 0.5
    return rpg ** 1.83 / (rpg ** 1.83 + rapg ** 1.83)


def log5(pa: float, pb: float) -> float:
    if pa + pb == 0:
        return 0.5
    return pa * (1 - pb) / (pa * (1 - pb) + pb * (1 - pa))


def run_wbc_backtest():  # noqa: C901
    print()
    print("=" * 70)
    print("🏆 2023 WBC 真實回測")
    print(f"   {len(WBC_2023_GAMES)} 場比賽 (Pool Play + QF + SF + Final)")
    print("=" * 70)
    print()

    # ── Init Elo ──
    elo = {team: rating for team, rating in BASE_ELO.items()}
    runs_for: dict[str, list[int]] = defaultdict(list)
    runs_against: dict[str, list[int]] = defaultdict(list)
    results: dict[str, list[int]] = defaultdict(list)

    total = 0
    correct = 0
    by_round: dict[str, dict] = defaultdict(lambda: {"total": 0, "correct": 0})
    by_model: dict[str, dict] = defaultdict(lambda: {"total": 0, "correct": 0})
    upset_correct = 0
    upset_total = 0
    favourite_correct = 0
    favourite_total = 0

    # Confidence-band tracking
    conf_bands = defaultdict(lambda: {"total": 0, "correct": 0})

    all_predictions = []

    for i, (home, away, hs, aws, rnd) in enumerate(WBC_2023_GAMES):
        actual_hw = 1 if hs > aws else 0

        # ── 1. Elo prediction ──
        elo_diff = elo.get(home, 1500) - elo.get(away, 1500)
        # WBC 多數是中立場
        p_elo = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))

        # ── 2. Star power adjustment ──
        star_diff = MLB_STARS.get(home, 0) - MLB_STARS.get(away, 0)
        star_adj = star_diff * 0.015  # Each star ≈ 1.5% edge

        # ── 3. Poisson (if we have history) ──
        if runs_for[home] and runs_for[away]:
            h_rpg = sum(runs_for[home][-5:]) / len(runs_for[home][-5:])
            h_rapg = sum(runs_against[home][-5:]) / len(runs_against[home][-5:])
            a_rpg = sum(runs_for[away][-5:]) / len(runs_for[away][-5:])
            a_rapg = sum(runs_against[away][-5:]) / len(runs_against[away][-5:])
            # Cross-calc: home offense vs away defense
            exp_h = (h_rpg + a_rapg) / 2
            exp_a = (a_rpg + h_rapg) / 2
            p_poisson = poisson_win_prob(exp_h, exp_a)
        else:
            # No history yet → use Elo as proxy
            p_poisson = p_elo

        # ── 4. Pythagorean (if history) ──
        if len(runs_for[home]) >= 2 and len(runs_for[away]) >= 2:
            h_rpg = sum(runs_for[home][-5:]) / len(runs_for[home][-5:])
            h_rapg = sum(runs_against[home][-5:]) / len(runs_against[home][-5:])
            a_rpg = sum(runs_for[away][-5:]) / len(runs_for[away][-5:])
            a_rapg = sum(runs_against[away][-5:]) / len(runs_against[away][-5:])
            h_pyth = pythag_wp(h_rpg, h_rapg)
            a_pyth = pythag_wp(a_rpg, a_rapg)
            p_pythag = log5(h_pyth, a_pyth)
        else:
            p_pythag = p_elo

        # ── 5. Recent form (if history) ──
        if results[home] and results[away]:
            h_form = sum(results[home][-3:]) / len(results[home][-3:])
            a_form = sum(results[away][-3:]) / len(results[away][-3:])
            p_form = (h_form + 0.01) / (h_form + a_form + 0.02)
        else:
            p_form = p_elo

        # ── Ensemble ──
        # Pool stage (less data): rely more on Elo + Stars
        # Knockout: balance with form
        if rnd.startswith("Pool"):
            p_final = (0.35 * p_elo + 0.20 * p_poisson + 0.15 * p_pythag +
                       0.15 * p_form + 0.15 * (0.5 + star_adj))
        else:
            p_final = (0.25 * p_elo + 0.25 * p_poisson + 0.20 * p_pythag +
                       0.20 * p_form + 0.10 * (0.5 + star_adj))

        p_final = max(0.08, min(0.92, p_final))

        # ── Evaluate ──
        total += 1
        predicted_hw = p_final > 0.5
        is_correct = predicted_hw == (actual_hw == 1)
        if is_correct:
            correct += 1

        by_round[rnd]["total"] += 1
        if is_correct:
            by_round[rnd]["correct"] += 1

        # Track per-model accuracy
        models = {"elo": p_elo, "poisson": p_poisson, "pythag": p_pythag,
                  "form": p_form, "ensemble": p_final}
        for name, prob in models.items():
            by_model[name]["total"] += 1
            if (prob > 0.5) == (actual_hw == 1):
                by_model[name]["correct"] += 1

        # Favourite/Upset tracking
        if p_final > 0.55 or p_final < 0.45:
            favourite_total += 1
            if is_correct:
                favourite_correct += 1
        if (p_final > 0.55 and actual_hw == 0) or (p_final < 0.45 and actual_hw == 1):
            upset_total += 1
            # Did we predict the upset?
            if not is_correct:
                upset_correct += 0  # We got the upset wrong
            # Upsets are inherently hard to predict

        # Confidence band
        max_p = max(p_final, 1 - p_final)
        if max_p < 0.55:
            band = "coin_flip"
        elif max_p < 0.60:
            band = "lean"
        elif max_p < 0.70:
            band = "moderate"
        else:
            band = "strong"
        conf_bands[band]["total"] += 1
        if is_correct:
            conf_bands[band]["correct"] += 1

        winner = home if hs > aws else away
        pred_winner = home if p_final > 0.5 else away
        marker = "✅" if is_correct else "❌"

        all_predictions.append({
            "game": i + 1,
            "round": rnd,
            "matchup": f"{away} @ {home}",
            "score": f"{hs}-{aws}",
            "winner": winner,
            "pred_winner": pred_winner,
            "prob": p_final,
            "correct": is_correct,
            "marker": marker,
        })

        # ── Update ──
        runs_for[home].append(hs)
        runs_for[away].append(aws)
        runs_against[home].append(aws)
        runs_against[away].append(hs)
        results[home].append(actual_hw)
        results[away].append(1 - actual_hw)

        # Elo update (higher K for international)
        elo_exp = 1.0 / (1.0 + 10 ** (-(elo.get(home, 1500) - elo.get(away, 1500)) / 400.0))
        margin = abs(hs - aws)
        mov = 1.0 + 0.08 * min(margin, 10)
        k = 16.0  # Higher K for WBC (fewer games, more info per game)
        delta = k * mov * (actual_hw - elo_exp)
        elo[home] = elo.get(home, 1500) + delta
        elo[away] = elo.get(away, 1500) - delta

    # ═══════════════════════════════════════════════════════
    #  RESULTS
    # ═══════════════════════════════════════════════════════
    accuracy = correct / total
    print("━" * 60)
    print(f"🎯 模型預測準確度: {accuracy:.1%}  ({correct}/{total})")
    print("━" * 60)
    print()

    # Per round
    print("━" * 60)
    print("📊 各輪準確率")
    print("━" * 60)
    round_order = ["Pool A", "Pool B", "Pool C", "Pool D", "QF", "SF", "Final"]
    for rnd in round_order:
        if rnd in by_round:
            d = by_round[rnd]
            acc = d["correct"] / d["total"]
            bar = "█" * int(acc * 20)
            print(f"  {rnd:8s}: {acc:.0%} ({d['correct']}/{d['total']}) {bar}")
    print()

    # Per model
    print("━" * 60)
    print("🧠 各子模型準確率")
    print("━" * 60)
    for name in ["elo", "poisson", "pythag", "form", "ensemble"]:
        d = by_model[name]
        acc = d["correct"] / d["total"]
        marker = "🏆" if name == "ensemble" else "  "
        print(f"  {marker} {name:10s}: {acc:.1%}  ({d['correct']}/{d['total']})")
    print()

    # Confidence bands
    print("━" * 60)
    print("📐 信心度分析")
    print("━" * 60)
    for band in ["coin_flip", "lean", "moderate", "strong"]:
        if band in conf_bands:
            d = conf_bands[band]
            acc = d["correct"] / d["total"]
            marker = "🎯" if acc >= 0.60 else "✅" if acc >= 0.55 else "  "
            print(f"  {marker} {band:12s}: {acc:.0%} ({d['correct']}/{d['total']})")
    print()

    # ── Game-by-game details ──
    print("━" * 60)
    print("📋 逐場預測結果")
    print("━" * 60)
    current_round = ""
    for p in all_predictions:
        if p["round"] != current_round:
            current_round = p["round"]
            print(f"\n  ── {current_round} ──")
        conf = max(p["prob"], 1 - p["prob"])
        print(f"  {p['marker']} {p['matchup']:18s} {p['score']:>5s}  "
              f"預測:{p['pred_winner']:4s} 實際:{p['winner']:4s}  "
              f"信心:{conf:.0%}")

    # ── Final Elo rankings ──
    print()
    print("━" * 60)
    print("📈 賽後 Elo 排名")
    print("━" * 60)
    sorted_elo = sorted(elo.items(), key=lambda x: -x[1])
    for i, (team, rating) in enumerate(sorted_elo[:10], 1):
        base = BASE_ELO.get(team, 1500)
        change = rating - base
        marker = "↑" if change > 0 else "↓"
        print(f"  {i:2d}. {team:4s}: {rating:.0f}  ({marker}{abs(change):.0f})")

    print()
    print("=" * 70)
    print("✅ WBC 2023 回測結論:")
    print(f"   整體準確率: {accuracy:.1%}  ({correct}/{total})")
    fav_acc = favourite_correct / favourite_total if favourite_total else 0
    print(f"   有較強預測時 (>55%): {fav_acc:.0%}")
    print("   淘汰賽準確率: ", end="")
    ko_correct = sum(by_round[r]["correct"] for r in ["QF", "SF", "Final"] if r in by_round)
    ko_total = sum(by_round[r]["total"] for r in ["QF", "SF", "Final"] if r in by_round)
    print(f"{ko_correct}/{ko_total} = {ko_correct/ko_total:.0%}" if ko_total else "N/A")
    print("=" * 70)


if __name__ == "__main__":
    run_wbc_backtest()
