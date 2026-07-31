"""
可預測性偵測器 (Predictability Detector)
=========================================
不預測「開什麼號碼」，而是預測「哪一期值得下注」。

流程:
1. 回顧掃描：對每一歷史期，用多策略計算可預測性分數
2. 條件特徵：為每期建立「開獎前」的環境特徵向量（嚴格無未來數據）
3. 分析：找出高可預測性期的共同特徵
4. 偵測模型：建立簡單規則 → 預測未來哪期值得下注
"""
import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field

from .config import MAX_NUM, PICK, SEED, MIN_HISTORY, P_SINGLE_M3, n_bet_baseline


# ============================================================
# 資料結構
# ============================================================
@dataclass
class DrawCondition:
    """一期開獎前的環境條件"""
    draw_idx: int = 0
    draw_id: str = ''

    # 可預測性標籤（回顧計算）
    best_match: int = 0
    n_strategies_m3: int = 0
    is_predictable: bool = False

    # 條件特徵（全部用開獎前資料計算）
    sum_volatility_10: float = 0.0   # 近10期 sum 標準差
    sum_volatility_50: float = 0.0   # 近50期 sum 標準差
    freq_dispersion_50: float = 0.0  # 近50期號碼頻率離散度
    zone_balance: float = 0.0        # 三區平衡度 (0=完美, 高=失衡)
    gap_entropy: float = 0.0         # 當前 gap 分布的 Shannon 熵
    max_gap_ratio: float = 0.0       # 最大 gap / 平均 gap
    n_overdue: int = 0               # 超過期望 gap 2倍的號碼數
    sum_trend_20: float = 0.0        # 近20期 sum 趨勢斜率
    lag1_repeat: int = 0             # 上期重複到前期的號碼數
    jaccard_trend_10: float = 0.0    # 近10期平均 Jaccard 相似度
    herfindahl_50: float = 0.0       # 號碼頻率集中度 (HHI)
    kl_divergence: float = 0.0       # 短期(20) vs 長期(200) KL散度
    streak_count: int = 0            # 連續出現 2+ 期的號碼數
    odd_even_stability: float = 0.0  # 近10期奇偶比穩定度
    consec_count_avg: float = 0.0    # 近10期平均連號數


# ============================================================
# 快速策略集（用於回顧掃描）
# ============================================================
def _freq_predict(history, window=50):
    freq = Counter(n for d in history[-window:] for n in d['numbers'][:PICK])
    ranked = sorted(freq.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


def _cold_predict(history, window=100):
    freq = Counter(n for d in history[-window:] for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    coldest = sorted(freq.items(), key=lambda x: x[1])
    return sorted([n for n, _ in coldest[:PICK]])


def _hot_cold_mix(history, window=50):
    freq = Counter(n for d in history[-window:] for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        if n not in freq:
            freq[n] = 0
    ranked = sorted(freq.items(), key=lambda x: -x[1])
    hot3 = [n for n, _ in ranked[:3]]
    cold3 = [n for n, _ in ranked[-3:]]
    return sorted(hot3 + cold3)


def _deviation_predict(history, window=50):
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'][:PICK])
    expected = len(recent) * PICK / MAX_NUM
    scores = {n: abs(freq.get(n, 0) - expected) for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


def _gap_predict(history):
    last_seen = {}
    for i, d in enumerate(history):
        for n in d['numbers'][:PICK]:
            last_seen[n] = i
    current = len(history)
    scores = {n: current - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


def _echo_predict(history):
    if len(history) < 2:
        return list(range(1, PICK + 1))
    lag1 = set(history[-1]['numbers'][:PICK])
    lag2 = set(history[-2]['numbers'][:PICK])
    scores = {}
    freq = Counter(n for d in history[-50:] for n in d['numbers'][:PICK])
    for n in range(1, MAX_NUM + 1):
        s = freq.get(n, 0)
        if n in lag2:
            s += 10
        if n in lag1:
            s += 3
        scores[n] = s
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


def _ewma_predict(history, alpha=0.1, window=200):
    recent = history[-window:] if len(history) >= window else history
    ewma = {n: 0.0 for n in range(1, MAX_NUM + 1)}
    for d in recent:
        appeared = set(d['numbers'][:PICK])
        for n in range(1, MAX_NUM + 1):
            x = 1.0 if n in appeared else 0.0
            ewma[n] = alpha * x + (1 - alpha) * ewma[n]
    ranked = sorted(ewma.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


def _contrarian_predict(history, window=20):
    freq = Counter(n for d in history[-window:] for n in d['numbers'][:PICK])
    scores = {n: -freq.get(n, 0) for n in range(1, MAX_NUM + 1)}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return sorted([n for n, _ in ranked[:PICK]])


SCAN_STRATEGIES = [
    ('freq_50', lambda h: _freq_predict(h, 50)),
    ('freq_100', lambda h: _freq_predict(h, 100)),
    ('cold_100', lambda h: _cold_predict(h, 100)),
    ('hot_cold_50', _hot_cold_mix),
    ('deviation_50', _deviation_predict),
    ('gap', _gap_predict),
    ('echo_lag2', _echo_predict),
    ('ewma_0.1', _ewma_predict),
    ('contrarian_20', _contrarian_predict),
]


# ============================================================
# Step 1: 回顧掃描 — 計算每期可預測性
# ============================================================
def retrospective_scan(all_draws: List[Dict],
                       min_history: int = MIN_HISTORY,
                       verbose: bool = True) -> List[DrawCondition]:
    """
    對每一歷史期回顧計算可預測性分數。
    strategy(history[:i]) → bets → match vs actual draw[i]
    """
    results = []
    total = len(all_draws) - min_history

    if verbose:
        print(f"Retrospective scan: {total} draws, {len(SCAN_STRATEGIES)} strategies")

    for i in range(min_history, len(all_draws)):
        hist = all_draws[:i]
        actual = set(all_draws[i]['numbers'][:PICK])

        best_match = 0
        n_m3 = 0

        for name, func in SCAN_STRATEGIES:
            try:
                bet = func(hist)
                mc = len(set(bet) & actual)
                best_match = max(best_match, mc)
                if mc >= 3:
                    n_m3 += 1
            except Exception:
                continue

        dc = DrawCondition(
            draw_idx=i,
            draw_id=all_draws[i].get('draw', ''),
            best_match=best_match,
            n_strategies_m3=n_m3,
            is_predictable=(best_match >= 3),
        )
        results.append(dc)

        if verbose and (i - min_history + 1) % 200 == 0:
            done = i - min_history + 1
            pred_rate = sum(1 for r in results if r.is_predictable) / len(results) * 100
            print(f"  [{done}/{total}] predictable_rate={pred_rate:.1f}%")

    if verbose:
        pred_count = sum(1 for r in results if r.is_predictable)
        print(f"  Scan complete: {pred_count}/{len(results)} predictable "
              f"({pred_count/len(results)*100:.1f}%)")

    return results


# ============================================================
# Step 2: 條件特徵提取（嚴格只用開獎前資料）
# ============================================================
def extract_conditions(all_draws: List[Dict],
                       scan_results: List[DrawCondition],
                       verbose: bool = True) -> List[DrawCondition]:
    """
    為每期計算「開獎前」的環境特徵。
    all_draws[:draw_idx] = 可用歷史（不含當期）
    """
    if verbose:
        print(f"Extracting pre-draw conditions for {len(scan_results)} draws...")

    for dc in scan_results:
        idx = dc.draw_idx
        hist = all_draws[:idx]  # 嚴格不含當期

        if len(hist) < 50:
            continue

        # --- Feature 1: Sum volatility ---
        recent_sums = [sum(d['numbers'][:PICK]) for d in hist[-50:]]
        dc.sum_volatility_10 = float(np.std(recent_sums[-10:])) if len(recent_sums) >= 10 else 0
        dc.sum_volatility_50 = float(np.std(recent_sums))

        # --- Feature 2: Frequency dispersion ---
        freq = Counter(n for d in hist[-50:] for n in d['numbers'][:PICK])
        all_freqs = [freq.get(n, 0) for n in range(1, MAX_NUM + 1)]
        dc.freq_dispersion_50 = float(np.std(all_freqs))

        # --- Feature 3: Zone balance ---
        zone_counts = [0, 0, 0]
        for d in hist[-50:]:
            for n in d['numbers'][:PICK]:
                z = 0 if n <= 16 else (1 if n <= 33 else 2)
                zone_counts[z] += 1
        total_z = sum(zone_counts) + 1e-10
        zone_props = [c / total_z for c in zone_counts]
        expected = 1.0 / 3
        dc.zone_balance = float(sum(abs(p - expected) for p in zone_props))

        # --- Feature 4: Gap entropy ---
        last_seen = {}
        for j, d in enumerate(hist):
            for n in d['numbers'][:PICK]:
                last_seen[n] = j
        current_idx = len(hist)
        gaps = [current_idx - last_seen.get(n, 0) for n in range(1, MAX_NUM + 1)]
        gap_array = np.array(gaps, dtype=float)
        gap_prob = gap_array / (gap_array.sum() + 1e-10)
        gap_prob = gap_prob[gap_prob > 0]
        dc.gap_entropy = float(-np.sum(gap_prob * np.log2(gap_prob + 1e-10)))

        # --- Feature 5: Max gap ratio ---
        avg_gap = np.mean(gaps)
        dc.max_gap_ratio = float(max(gaps) / (avg_gap + 1e-10))

        # --- Feature 6: N overdue ---
        expected_gap = MAX_NUM / PICK  # ~8.17
        dc.n_overdue = sum(1 for g in gaps if g > expected_gap * 2)

        # --- Feature 7: Sum trend ---
        if len(recent_sums) >= 20:
            x = np.arange(20)
            y = np.array(recent_sums[-20:], dtype=float)
            dc.sum_trend_20 = float(np.polyfit(x, y, 1)[0])

        # --- Feature 8: Lag-1 repeat ---
        if len(hist) >= 2:
            prev = set(hist[-2]['numbers'][:PICK])
            cur = set(hist[-1]['numbers'][:PICK])
            dc.lag1_repeat = len(prev & cur)

        # --- Feature 9: Jaccard trend ---
        if len(hist) >= 11:
            jaccards = []
            for j in range(1, min(11, len(hist))):
                a = set(hist[-j - 1]['numbers'][:PICK])
                b = set(hist[-j]['numbers'][:PICK])
                jaccards.append(len(a & b) / len(a | b) if len(a | b) > 0 else 0)
            dc.jaccard_trend_10 = float(np.mean(jaccards))

        # --- Feature 10: Herfindahl index ---
        total_appearances = sum(all_freqs)
        if total_appearances > 0:
            shares = [(f / total_appearances) ** 2 for f in all_freqs]
            dc.herfindahl_50 = float(sum(shares))

        # --- Feature 11: KL divergence (short vs long) ---
        freq_short = Counter(n for d in hist[-20:] for n in d['numbers'][:PICK])
        freq_long = Counter(n for d in hist[-200:] for n in d['numbers'][:PICK])
        total_s = sum(freq_short.values()) + 1e-10
        total_l = sum(freq_long.values()) + 1e-10
        kl = 0
        for n in range(1, MAX_NUM + 1):
            p = (freq_short.get(n, 0) + 0.5) / (total_s + MAX_NUM * 0.5)
            q = (freq_long.get(n, 0) + 0.5) / (total_l + MAX_NUM * 0.5)
            kl += p * np.log(p / q + 1e-10)
        dc.kl_divergence = float(kl)

        # --- Feature 12: Streak count ---
        streaks = 0
        for n in range(1, MAX_NUM + 1):
            count = 0
            for j in range(len(hist) - 1, max(len(hist) - 5, -1), -1):
                if n in hist[j]['numbers'][:PICK]:
                    count += 1
                else:
                    break
            if count >= 2:
                streaks += 1
        dc.streak_count = streaks

        # --- Feature 13: Odd-even stability ---
        if len(hist) >= 10:
            oe_ratios = [sum(1 for n in d['numbers'][:PICK] if n % 2 == 1) / PICK
                         for d in hist[-10:]]
            dc.odd_even_stability = float(np.std(oe_ratios))

        # --- Feature 14: Consecutive count avg ---
        if len(hist) >= 10:
            consec_counts = []
            for d in hist[-10:]:
                nums = sorted(d['numbers'][:PICK])
                cc = sum(1 for j in range(len(nums) - 1) if nums[j + 1] - nums[j] == 1)
                consec_counts.append(cc)
            dc.consec_count_avg = float(np.mean(consec_counts))

    if verbose:
        print("  Condition extraction complete.")

    return scan_results


# ============================================================
# Step 3: 分析 — 找出可預測性與條件的關聯
# ============================================================
FEATURE_NAMES = [
    'sum_volatility_10', 'sum_volatility_50', 'freq_dispersion_50',
    'zone_balance', 'gap_entropy', 'max_gap_ratio', 'n_overdue',
    'sum_trend_20', 'lag1_repeat', 'jaccard_trend_10',
    'herfindahl_50', 'kl_divergence', 'streak_count',
    'odd_even_stability', 'consec_count_avg',
]


def to_feature_matrix(conditions: List[DrawCondition]) -> Tuple[np.ndarray, np.ndarray]:
    """轉換為特徵矩陣 X 和標籤 y"""
    X = np.zeros((len(conditions), len(FEATURE_NAMES)))
    y = np.zeros(len(conditions))

    for i, dc in enumerate(conditions):
        for j, fname in enumerate(FEATURE_NAMES):
            X[i, j] = getattr(dc, fname, 0)
        y[i] = 1 if dc.is_predictable else 0

    return X, y


def analyze_correlations(conditions: List[DrawCondition],
                         verbose: bool = True) -> Dict:
    """分析每個條件特徵與可預測性的相關性"""
    X, y = to_feature_matrix(conditions)

    results = {}
    if verbose:
        print(f"\n{'='*70}")
        print(f"  Condition-Predictability Correlation Analysis")
        print(f"  {len(conditions)} draws, {int(y.sum())} predictable ({y.mean()*100:.1f}%)")
        print(f"{'='*70}")
        print(f"  {'Feature':<25} {'Corr':>8} {'Pred_mean':>10} {'Unpred_mean':>12} {'Ratio':>8}")
        print(f"  {'-'*63}")

    for j, fname in enumerate(FEATURE_NAMES):
        col = X[:, j]

        # Point-biserial correlation
        if np.std(col) > 1e-10:
            corr = float(np.corrcoef(col, y)[0, 1])
        else:
            corr = 0.0

        pred_mask = y == 1
        pred_mean = float(col[pred_mask].mean()) if pred_mask.sum() > 0 else 0
        unpred_mean = float(col[~pred_mask].mean()) if (~pred_mask).sum() > 0 else 0
        ratio = pred_mean / (unpred_mean + 1e-10) if unpred_mean != 0 else 0

        results[fname] = {
            'correlation': corr,
            'pred_mean': pred_mean,
            'unpred_mean': unpred_mean,
            'ratio': ratio,
        }

        if verbose:
            marker = ' ***' if abs(corr) > 0.05 else ''
            print(f"  {fname:<25} {corr:+8.4f} {pred_mean:10.4f} {unpred_mean:12.4f} {ratio:8.3f}{marker}")

    return results


# ============================================================
# Step 4: 多分位分析 — 切割條件特徵找最佳門檻
# ============================================================
def quantile_analysis(conditions: List[DrawCondition],
                      verbose: bool = True) -> Dict:
    """
    對每個特徵做分位切割，找出哪個區間的可預測率最高。
    """
    X, y = to_feature_matrix(conditions)
    base_rate = y.mean()

    results = {}
    if verbose:
        print(f"\n{'='*70}")
        print(f"  Quantile Analysis (base predictable rate = {base_rate*100:.1f}%)")
        print(f"{'='*70}")

    for j, fname in enumerate(FEATURE_NAMES):
        col = X[:, j]
        if np.std(col) < 1e-10:
            continue

        # 分成 5 個 quantile
        try:
            quantiles = np.percentile(col, [20, 40, 60, 80])
        except Exception:
            continue

        bins = np.digitize(col, quantiles)  # 0-4
        bin_rates = {}
        for b in range(5):
            mask = bins == b
            if mask.sum() > 10:
                bin_rates[b] = float(y[mask].mean())

        if not bin_rates:
            continue

        best_bin = max(bin_rates, key=bin_rates.get)
        best_rate = bin_rates[best_bin]
        lift = best_rate / (base_rate + 1e-10)

        results[fname] = {
            'bin_rates': bin_rates,
            'best_bin': best_bin,
            'best_rate': best_rate,
            'lift': lift,
            'quantiles': quantiles.tolist(),
        }

        if verbose and lift > 1.1:
            bin_str = ' | '.join(f'Q{b}:{r*100:.1f}%' for b, r in sorted(bin_rates.items()))
            print(f"  {fname:<25} lift={lift:.2f}x  best=Q{best_bin}({best_rate*100:.1f}%)  [{bin_str}]")

    return results


# ============================================================
# Step 5: 建立規則偵測器
# ============================================================
@dataclass
class DetectorRule:
    feature: str
    operator: str  # '>' or '<'
    threshold: float
    lift: float
    pred_rate: float
    coverage: float  # 符合條件的比例


def build_rule_detector(conditions: List[DrawCondition],
                        min_lift: float = 1.15,
                        min_coverage: float = 0.10,
                        verbose: bool = True) -> List[DetectorRule]:
    """
    暴力搜尋：對每個特徵 × 每個百分位門檻，找出 lift > min_lift 的規則。
    """
    X, y = to_feature_matrix(conditions)
    base_rate = y.mean()
    n = len(y)

    rules = []

    for j, fname in enumerate(FEATURE_NAMES):
        col = X[:, j]
        if np.std(col) < 1e-10:
            continue

        for pct in [10, 20, 30, 40, 50, 60, 70, 80, 90]:
            th = np.percentile(col, pct)

            # 測試 > threshold
            mask_gt = col > th
            if mask_gt.sum() > 20:
                rate = float(y[mask_gt].mean())
                coverage = mask_gt.sum() / n
                lift = rate / (base_rate + 1e-10)
                if lift >= min_lift and coverage >= min_coverage:
                    rules.append(DetectorRule(
                        feature=fname, operator='>', threshold=float(th),
                        lift=lift, pred_rate=rate, coverage=coverage
                    ))

            # 測試 < threshold
            mask_lt = col < th
            if mask_lt.sum() > 20:
                rate = float(y[mask_lt].mean())
                coverage = mask_lt.sum() / n
                lift = rate / (base_rate + 1e-10)
                if lift >= min_lift and coverage >= min_coverage:
                    rules.append(DetectorRule(
                        feature=fname, operator='<', threshold=float(th),
                        lift=lift, pred_rate=rate, coverage=coverage
                    ))

    # 去重，保留每個 feature 最佳 lift
    rules.sort(key=lambda r: -r.lift)

    if verbose:
        print(f"\n{'='*70}")
        print(f"  Rule Detector (min_lift={min_lift}, min_coverage={min_coverage})")
        print(f"  Base rate: {base_rate*100:.1f}%")
        print(f"  Found {len(rules)} rules")
        print(f"{'='*70}")
        seen_features = set()
        for r in rules[:20]:
            tag = ' [NEW]' if r.feature not in seen_features else ''
            seen_features.add(r.feature)
            print(f"  {r.feature:<25} {r.operator} {r.threshold:8.3f} → "
                  f"rate={r.pred_rate*100:.1f}%, lift={r.lift:.2f}x, "
                  f"coverage={r.coverage:.0%}{tag}")

    return rules


# ============================================================
# Step 6: 時間切分驗證
# ============================================================
def time_split_validate(conditions: List[DrawCondition],
                        rules: List[DetectorRule],
                        train_ratio: float = 0.7,
                        verbose: bool = True) -> Dict:
    """
    時間切分驗證：前 70% 建立規則，後 30% 驗證。
    """
    n = len(conditions)
    split_idx = int(n * train_ratio)
    train_conds = conditions[:split_idx]
    test_conds = conditions[split_idx:]

    X_train, y_train = to_feature_matrix(train_conds)
    X_test, y_test = to_feature_matrix(test_conds)

    train_base = y_train.mean()
    test_base = y_test.mean()

    if verbose:
        print(f"\n{'='*70}")
        print(f"  Time-Split Validation")
        print(f"  Train: {len(train_conds)} draws (base={train_base*100:.1f}%)")
        print(f"  Test:  {len(test_conds)} draws (base={test_base*100:.1f}%)")
        print(f"{'='*70}")

    # 在 test set 上測試每條規則
    validated_rules = []
    for r in rules:
        fidx = FEATURE_NAMES.index(r.feature) if r.feature in FEATURE_NAMES else -1
        if fidx < 0:
            continue

        col_test = X_test[:, fidx]
        if r.operator == '>':
            mask = col_test > r.threshold
        else:
            mask = col_test < r.threshold

        if mask.sum() < 10:
            continue

        test_rate = float(y_test[mask].mean())
        test_coverage = mask.sum() / len(y_test)
        test_lift = test_rate / (test_base + 1e-10)

        validated_rules.append({
            'feature': r.feature,
            'operator': r.operator,
            'threshold': r.threshold,
            'train_lift': r.lift,
            'train_rate': r.pred_rate,
            'test_lift': test_lift,
            'test_rate': test_rate,
            'test_coverage': test_coverage,
            'is_validated': test_lift > 1.05,  # test 上也必須有正 lift
        })

    validated_rules.sort(key=lambda x: -x['test_lift'])

    if verbose:
        valid_count = sum(1 for v in validated_rules if v['is_validated'])
        print(f"\n  {valid_count}/{len(validated_rules)} rules validated on test set")
        print(f"\n  {'Feature':<25} {'Rule':>12} {'Train':>7} {'Test':>7} {'Lift_T':>7} {'Cover':>7} {'Valid':>6}")
        print(f"  {'-'*75}")
        for v in validated_rules[:15]:
            op_str = f"{v['operator']}{v['threshold']:.2f}"
            val_tag = 'YES' if v['is_validated'] else 'NO'
            print(f"  {v['feature']:<25} {op_str:>12} {v['train_rate']*100:6.1f}% "
                  f"{v['test_rate']*100:6.1f}% {v['test_lift']:6.2f}x "
                  f"{v['test_coverage']:6.0%}  {val_tag}")

    return {
        'train_base': train_base,
        'test_base': test_base,
        'rules': validated_rules,
        'n_validated': sum(1 for v in validated_rules if v['is_validated']),
    }


# ============================================================
# Step 7: 組合規則偵測器
# ============================================================
def combo_rule_test(conditions: List[DrawCondition],
                    validated_rules: List[Dict],
                    train_ratio: float = 0.7,
                    verbose: bool = True) -> Dict:
    """
    測試規則組合（AND 邏輯）：同時滿足多條規則時的可預測率。
    """
    n = len(conditions)
    split_idx = int(n * train_ratio)
    test_conds = conditions[split_idx:]
    X_test, y_test = to_feature_matrix(test_conds)
    test_base = y_test.mean()

    # 只取已驗證的規則
    good_rules = [r for r in validated_rules if r.get('is_validated')]
    if len(good_rules) < 2:
        if verbose:
            print("\n  Not enough validated rules for combo testing.")
        return {}

    if verbose:
        print(f"\n{'='*70}")
        print(f"  Combo Rule Testing ({len(good_rules)} validated rules)")
        print(f"  Test base rate: {test_base*100:.1f}%")
        print(f"{'='*70}")

    # 測試所有二規則組合
    from itertools import combinations as combos
    combo_results = []

    for r1, r2 in combos(good_rules[:10], 2):  # 最多 top-10
        f1_idx = FEATURE_NAMES.index(r1['feature'])
        f2_idx = FEATURE_NAMES.index(r2['feature'])

        if f1_idx == f2_idx:
            continue  # 同特徵跳過

        col1 = X_test[:, f1_idx]
        col2 = X_test[:, f2_idx]

        mask1 = col1 > r1['threshold'] if r1['operator'] == '>' else col1 < r1['threshold']
        mask2 = col2 > r2['threshold'] if r2['operator'] == '>' else col2 < r2['threshold']
        mask_combo = mask1 & mask2

        if mask_combo.sum() < 10:
            continue

        combo_rate = float(y_test[mask_combo].mean())
        combo_coverage = mask_combo.sum() / len(y_test)
        combo_lift = combo_rate / (test_base + 1e-10)

        combo_results.append({
            'rule1': f"{r1['feature']}{r1['operator']}{r1['threshold']:.2f}",
            'rule2': f"{r2['feature']}{r2['operator']}{r2['threshold']:.2f}",
            'combo_rate': combo_rate,
            'combo_lift': combo_lift,
            'combo_coverage': combo_coverage,
            'n_selected': int(mask_combo.sum()),
        })

    combo_results.sort(key=lambda x: -x['combo_lift'])

    if verbose:
        print(f"\n  Top combo rules (test set):")
        for c in combo_results[:10]:
            print(f"  {c['rule1']} AND {c['rule2']}")
            print(f"    → rate={c['combo_rate']*100:.1f}%, lift={c['combo_lift']:.2f}x, "
                  f"coverage={c['combo_coverage']:.0%} ({c['n_selected']} draws)")

    return {'combos': combo_results}


# ============================================================
# 主入口：完整流程
# ============================================================
def run_full_analysis(all_draws: List[Dict],
                      verbose: bool = True) -> Dict:
    """
    完整流程：掃描 → 特徵 → 相關性 → 分位 → 規則 → 驗證 → 組合
    """
    # Step 1: Retrospective scan
    conditions = retrospective_scan(all_draws, verbose=verbose)

    # Step 2: Extract conditions
    conditions = extract_conditions(all_draws, conditions, verbose=verbose)

    # Step 3: Correlation analysis
    correlations = analyze_correlations(conditions, verbose=verbose)

    # Step 4: Quantile analysis
    quantiles = quantile_analysis(conditions, verbose=verbose)

    # Step 5: Build rule detector
    rules = build_rule_detector(conditions, verbose=verbose)

    # Step 6: Time-split validation
    validation = time_split_validate(conditions, rules, verbose=verbose)

    # Step 7: Combo rules
    combos = combo_rule_test(conditions, validation.get('rules', []),
                             verbose=verbose)

    return {
        'n_draws': len(conditions),
        'base_predictable_rate': sum(1 for c in conditions if c.is_predictable) / len(conditions),
        'correlations': correlations,
        'quantiles': quantiles,
        'n_rules': len(rules),
        'validation': validation,
        'combos': combos,
    }
