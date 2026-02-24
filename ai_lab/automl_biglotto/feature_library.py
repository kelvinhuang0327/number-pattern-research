"""
特徵庫：35+ 特徵提取器
Feature Library: Extract per-number features for GP and ML strategies
"""
import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict

from .config import MAX_NUM, PICK, PRIMES, FEATURE_NAMES


class FeatureLibrary:
    """
    為每個候選號碼 (1-49) 提取特徵向量。
    回傳 shape (49, N_features) 的矩陣。
    """

    def __init__(self):
        self.max_num = MAX_NUM
        self.pick = PICK
        self._primes = PRIMES

    def extract_all(self, history: List[Dict]) -> np.ndarray:
        """
        提取所有特徵，回傳 (49, 35) 矩陣
        Row i = 號碼 (i+1) 的特徵向量
        """
        n_features = len(FEATURE_NAMES)
        features = np.zeros((self.max_num, n_features), dtype=np.float32)

        if len(history) < 5:
            return features

        # 預計算各窗口頻率
        freq_maps = {}
        for w in [20, 50, 100, 200, 500]:
            recent = history[-w:] if len(history) >= w else history
            freq = Counter()
            for d in recent:
                for n in d['numbers'][:self.pick]:
                    freq[n] += 1
            freq_maps[w] = freq

        # 預計算 gap 和 last_seen
        last_seen = {}
        all_gaps = defaultdict(list)
        for i, d in enumerate(history):
            for n in d['numbers'][:self.pick]:
                if n in last_seen:
                    all_gaps[n].append(i - last_seen[n])
                last_seen[n] = i
        current_idx = len(history)

        # 預計算 lag 出現
        lag1_set = set(history[-1]['numbers'][:self.pick]) if len(history) >= 1 else set()
        lag2_set = set(history[-2]['numbers'][:self.pick]) if len(history) >= 2 else set()
        lag3_set = set(history[-3]['numbers'][:self.pick]) if len(history) >= 3 else set()

        # 預計算 Markov 轉移分數
        markov1 = self._build_markov(history, order=1)
        markov2 = self._build_markov(history, order=2)

        # 預計算 Fourier 分數
        fourier_scores = self._compute_fourier_scores(history)

        # 預計算條件機率
        cond_probs = self._compute_conditional_probs(history)

        # 預計算共現分數
        cooc_scores = self._compute_cooccurrence(history)

        # 預計算 pair transition
        pair_trans = self._compute_pair_transition(history)

        # 預計算資訊理論特徵
        info_features = self._compute_info_theory(history)

        # 預計算 zone trend
        zone_trends = self._compute_zone_trends(history)

        # 預計算 rank 排序
        freq_100 = freq_maps[100]
        sorted_by_freq = sorted(range(1, self.max_num + 1),
                                key=lambda x: -freq_100.get(x, 0))
        all_nums_by_gap = sorted(range(1, self.max_num + 1),
                                 key=lambda x: -(current_idx - last_seen.get(x, 0)))

        # 逐號碼填入特徵
        for num in range(1, self.max_num + 1):
            idx = num - 1
            col = 0

            # Group 1: 頻率 (5)
            for w in [20, 50, 100, 200, 500]:
                actual_w = min(w, len(history))
                features[idx, col] = freq_maps[w].get(num, 0) / actual_w if actual_w > 0 else 0
                col += 1

            # Group 2: 間距 (3)
            gap = current_idx - last_seen.get(num, 0)
            features[idx, col] = gap
            col += 1
            features[idx, col] = max(all_gaps.get(num, [0])) if all_gaps.get(num) else 0
            col += 1
            streak = 0
            for j in range(len(history) - 1, -1, -1):
                if num in history[j]['numbers'][:self.pick]:
                    streak += 1
                else:
                    break
            features[idx, col] = streak
            col += 1

            # Group 3: 滯後 (3)
            features[idx, col] = 1.0 if num in lag1_set else 0.0
            col += 1
            features[idx, col] = 1.0 if num in lag2_set else 0.0
            col += 1
            features[idx, col] = 1.0 if num in lag3_set else 0.0
            col += 1

            # Group 4: 偏差 (2)
            expected = self.pick / self.max_num
            for w in [50, 100]:
                actual_w = min(w, len(history))
                observed = freq_maps[w].get(num, 0) / actual_w if actual_w > 0 else 0
                se = np.sqrt(expected * (1 - expected) / actual_w) if actual_w > 0 else 1
                features[idx, col] = (observed - expected) / se if se > 0 else 0
                col += 1

            # Group 5: 條件機率 (2)
            features[idx, col] = cond_probs.get((num, 'lag1'), 0)
            col += 1
            features[idx, col] = cond_probs.get((num, 'lag2'), 0)
            col += 1

            # Group 6: 共現 (2)
            features[idx, col] = cooc_scores.get(num, 0)
            col += 1
            features[idx, col] = pair_trans.get(num, 0)
            col += 1

            # Group 7: 資訊理論 (3)
            features[idx, col] = info_features.get((num, 'entropy'), 0)
            col += 1
            features[idx, col] = info_features.get((num, 'mi'), 0)
            col += 1
            features[idx, col] = info_features.get((num, 'surprise'), 0)
            col += 1

            # Group 8: 結構 (3)
            zone_id = 0 if num <= 16 else (1 if num <= 33 else 2)
            features[idx, col] = zone_id
            col += 1
            features[idx, col] = num % 10
            col += 1
            features[idx, col] = 1.0 if num in self._primes else 0.0
            col += 1

            # Group 9: 區間 (2)
            features[idx, col] = zone_trends.get((zone_id, 'deficit'), 0)
            col += 1
            features[idx, col] = zone_trends.get((zone_id, 'trend'), 0)
            col += 1

            # Group 10: Markov (2)
            features[idx, col] = markov1.get(num, 0)
            col += 1
            features[idx, col] = markov2.get(num, 0)
            col += 1

            # Group 11: 頻譜/回聲 (2)
            features[idx, col] = fourier_scores.get(num, 0)
            col += 1
            features[idx, col] = 1.5 if num in lag2_set else 0.0
            col += 1

            # Group 12: 加權 (3)
            ema = 0
            for j, d in enumerate(history[-200:]):
                if num in d['numbers'][:self.pick]:
                    age = min(200, len(history)) - 1 - j
                    ema += np.exp(-0.05 * age)
            features[idx, col] = ema
            col += 1
            rank_f = sorted_by_freq.index(num) + 1 if num in sorted_by_freq else self.max_num
            features[idx, col] = rank_f / self.max_num
            col += 1
            rank_g = all_nums_by_gap.index(num) + 1
            features[idx, col] = rank_g / self.max_num
            col += 1

            # Group 13: 衰減 (1)
            decay = 0
            for j, d in enumerate(history[-200:]):
                if num in d['numbers'][:self.pick]:
                    age = min(200, len(history)) - 1 - j
                    decay += np.exp(-0.05 * age)
            features[idx, col] = decay
            col += 1

            # Group 14: 鄰域 (1)
            n_freq = 0
            count = 0
            for neighbor in [num - 1, num + 1]:
                if 1 <= neighbor <= self.max_num:
                    n_freq += freq_maps[100].get(neighbor, 0)
                    count += 1
            features[idx, col] = n_freq / count if count > 0 else 0
            col += 1

            # Group 15: 是否5的倍數 (1)
            features[idx, col] = 1.0 if num % 5 == 0 else 0.0
            col += 1

        return features

    def _build_markov(self, history, order=1, window=50):
        """建立 Markov 轉移分數"""
        recent = history[-window:] if len(history) >= window else history
        if len(recent) < order + 1:
            return {}

        scores = Counter()
        if order == 1:
            trans = Counter()
            for i in range(len(recent) - 1):
                for p in recent[i]['numbers'][:self.pick]:
                    for n in recent[i + 1]['numbers'][:self.pick]:
                        trans[(p, n)] += 1
            last_nums = recent[-1]['numbers'][:self.pick]
            for prev in last_nums:
                for n in range(1, self.max_num + 1):
                    scores[n] += trans.get((prev, n), 0)
        elif order == 2:
            if len(recent) < 3:
                return {}
            trans = Counter()
            for i in range(len(recent) - 2):
                for p1 in recent[i]['numbers'][:self.pick]:
                    for p2 in recent[i + 1]['numbers'][:self.pick]:
                        for n in recent[i + 2]['numbers'][:self.pick]:
                            trans[(p1, p2, n)] += 1
            if len(recent) >= 2:
                prev1 = recent[-2]['numbers'][:self.pick]
                prev2 = recent[-1]['numbers'][:self.pick]
                for p1 in prev1:
                    for p2 in prev2:
                        for n in range(1, self.max_num + 1):
                            scores[n] += trans.get((p1, p2, n), 0)

        max_s = max(scores.values()) if scores else 1
        return {n: scores.get(n, 0) / max_s if max_s > 0 else 0
                for n in range(1, self.max_num + 1)}

    def _compute_fourier_scores(self, history, window=500):
        """FFT 頻譜分析分數"""
        scores = {}
        recent = history[-window:] if len(history) >= window else history
        if len(recent) < 20:
            return {n: 0 for n in range(1, self.max_num + 1)}

        for num in range(1, self.max_num + 1):
            seq = np.array([1.0 if num in d['numbers'][:self.pick] else 0.0
                           for d in recent])
            seq = seq - seq.mean()
            if np.std(seq) < 1e-6:
                scores[num] = 0
                continue
            fft_result = np.fft.rfft(seq)
            power = np.abs(fft_result) ** 2
            if len(power) > 1:
                freqs = np.fft.rfftfreq(len(seq))
                main_idx = np.argmax(power[1:]) + 1
                period = 1.0 / freqs[main_idx] if freqs[main_idx] > 0 else len(seq)
                last_seen_idx = 0
                for i in range(len(recent) - 1, -1, -1):
                    if num in recent[i]['numbers'][:self.pick]:
                        last_seen_idx = i
                        break
                gap_from_last = len(recent) - 1 - last_seen_idx
                alignment = 1.0 / (abs(gap_from_last - period) + 1)
                scores[num] = alignment * (power[main_idx] / np.sum(power + 1e-10))
            else:
                scores[num] = 0

        max_s = max(scores.values()) if scores else 1
        return {n: scores.get(n, 0) / max_s if max_s > 0 else 0
                for n in range(1, self.max_num + 1)}

    def _compute_conditional_probs(self, history, window=100):
        """計算條件機率"""
        recent = history[-window:] if len(history) >= window else history
        probs = {}

        for num in range(1, self.max_num + 1):
            seq = [1 if num in d['numbers'][:self.pick] else 0 for d in recent]

            for lag, label in [(1, 'lag1'), (2, 'lag2')]:
                if len(seq) <= lag:
                    probs[(num, label)] = 0
                    continue
                appeared_after = 0
                total_after = 0
                for i in range(lag, len(seq)):
                    if seq[i - lag] == 1:
                        total_after += 1
                        if seq[i] == 1:
                            appeared_after += 1
                probs[(num, label)] = appeared_after / total_after if total_after > 0 else 0

        return probs

    def _compute_cooccurrence(self, history, window=100):
        """與上期號碼的共現強度"""
        recent = history[-window:] if len(history) >= window else history
        if len(recent) < 2:
            return {}

        pair_freq = Counter()
        for i in range(len(recent) - 1):
            for p in recent[i]['numbers'][:self.pick]:
                for n in recent[i + 1]['numbers'][:self.pick]:
                    pair_freq[(p, n)] += 1

        last_nums = recent[-1]['numbers'][:self.pick]
        scores = Counter()
        for prev in last_nums:
            for n in range(1, self.max_num + 1):
                scores[n] += pair_freq.get((prev, n), 0)

        max_s = max(scores.values()) if scores else 1
        return {n: scores.get(n, 0) / max_s if max_s > 0 else 0
                for n in range(1, self.max_num + 1)}

    def _compute_pair_transition(self, history, window=50):
        """對轉移分數"""
        recent = history[-window:] if len(history) >= window else history
        if len(recent) < 2:
            return {}

        trans = Counter()
        for i in range(len(recent) - 1):
            prev_set = set(recent[i]['numbers'][:self.pick])
            next_set = set(recent[i + 1]['numbers'][:self.pick])
            for p in prev_set:
                for n in next_set:
                    trans[(p, n)] += 1

        last_nums = set(recent[-1]['numbers'][:self.pick])
        scores = Counter()
        for p in last_nums:
            for n in range(1, self.max_num + 1):
                scores[n] += trans.get((p, n), 0)

        max_s = max(scores.values()) if scores else 1
        return {n: scores.get(n, 0) / max_s if max_s > 0 else 0
                for n in range(1, self.max_num + 1)}

    def _compute_info_theory(self, history, window=100):
        """資訊理論特徵"""
        recent = history[-window:] if len(history) >= window else history
        features = {}

        freq = Counter()
        for d in recent:
            for n in d['numbers'][:self.pick]:
                freq[n] += 1
        total_appearances = sum(freq.values())

        for num in range(1, self.max_num + 1):
            seq = [1 if num in d['numbers'][:self.pick] else 0 for d in recent]

            # Conditional entropy
            counts = {'00': 0, '01': 0, '10': 0, '11': 0}
            for i in range(len(seq) - 1):
                key = f'{seq[i]}{seq[i + 1]}'
                counts[key] += 1
            total_0 = counts['00'] + counts['01']
            total_1 = counts['10'] + counts['11']
            h = 0
            for prev in [0, 1]:
                t = total_0 if prev == 0 else total_1
                if t == 0:
                    continue
                p_w = t / (len(seq) - 1) if len(seq) > 1 else 0
                for nv in [0, 1]:
                    k = f'{prev}{nv}'
                    if counts[k] > 0:
                        p = counts[k] / t
                        h -= p_w * p * np.log2(p + 1e-10)
            features[(num, 'entropy')] = h

            # Mutual information
            if len(seq) > 1:
                x = np.array(seq[:-1])
                y = np.array(seq[1:])
                joint = Counter(zip(x.tolist(), y.tolist()))
                mi = 0
                n_total = len(x)
                px = Counter(x.tolist())
                py = Counter(y.tolist())
                for (xi, yi), c in joint.items():
                    p_xy = c / n_total
                    p_x = px[xi] / n_total
                    p_y = py[yi] / n_total
                    if p_xy > 0 and p_x > 0 and p_y > 0:
                        mi += p_xy * np.log2(p_xy / (p_x * p_y) + 1e-10)
                features[(num, 'mi')] = mi
            else:
                features[(num, 'mi')] = 0

            # Surprise
            p = freq.get(num, 0.5) / total_appearances if total_appearances > 0 else 1.0 / self.max_num
            features[(num, 'surprise')] = -np.log2(p + 1e-10)

        return features

    def _compute_zone_trends(self, history, window=50):
        """區間趨勢"""
        recent = history[-window:] if len(history) >= window else history
        zones = {0: (1, 16), 1: (17, 33), 2: (34, 49)}
        expected_per_zone = {0: 16 / 49 * self.pick, 1: 17 / 49 * self.pick, 2: 16 / 49 * self.pick}

        features = {}
        zone_counts_per_draw = {0: [], 1: [], 2: []}

        for d in recent:
            nums = d['numbers'][:self.pick]
            for z_id, (lo, hi) in zones.items():
                cnt = sum(1 for n in nums if lo <= n <= hi)
                zone_counts_per_draw[z_id].append(cnt)

        for z_id in range(3):
            counts = zone_counts_per_draw[z_id]
            if counts:
                avg = np.mean(counts)
                expected = expected_per_zone[z_id]
                features[(z_id, 'deficit')] = expected - avg
                if len(counts) > 1:
                    x = np.arange(len(counts))
                    slope = np.polyfit(x, counts, 1)[0]
                    features[(z_id, 'trend')] = slope
                else:
                    features[(z_id, 'trend')] = 0
            else:
                features[(z_id, 'deficit')] = 0
                features[(z_id, 'trend')] = 0

        return features
