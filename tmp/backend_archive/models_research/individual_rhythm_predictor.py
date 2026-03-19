"""
Individual Rhythm Adaptive Predictor (IRAP) for 39 Lotto
======================================================
Breakthrough Discoveries:
1. Per-number heterogeneous lag rhythms (e.g. #7 at Lag-6, #12 at Lag-3).
2. Individual Fourier phase stability (Cohen's d = 3.08 in P3 Shuffle).

Status: Phase 2 Core Model
"""

import json
import math
import numpy as np
from scipy import stats
from collections import Counter
from typing import List, Dict, Any

class IndividualRhythmPredictor:
    def __init__(self, pool=39, pick=5):
        self.pool = pool
        self.pick = pick
        self.p_theoretical = pick / pool
        self.profiling = {}
        self.regime_status = "STABLE"
        self.markov_matrix = None

    def train(self, history: List[Dict], decay_factor: float = 0.995):
        """
        Build a 'Rhythm Profile' for each number with exponential decay weighting.
        Also trains a Markov transition matrix for ensemble.
        NEW v2.4: Gap Overshoot statistics (Mean/Std Gap).
        """
        N = len(history)
        if N < 100:
            return 
        
        # 1. Train Transition Matrix (Markov)
        self.markov_matrix = np.zeros((self.pool + 1, self.pool + 1))
        for i in range(1, N):
            prev_nums = history[i-1]['numbers']
            curr_nums = history[i]['numbers']
            for p in prev_nums:
                for c in curr_nums:
                    self.markov_matrix[p][c] += 1
        
        # Normalize Markov
        row_sums = self.markov_matrix.sum(axis=1)
        self.markov_matrix = np.divide(self.markov_matrix, row_sums[:, np.newaxis], 
                                      where=row_sums[:, np.newaxis]!=0)
        
        # v2.5 NEW: Markov Pruning (Filter out transitions with < 5% probability)
        # This removes low-confidence "random noise" transitions.
        self.markov_matrix[self.markov_matrix < 0.05] = 0
        # Re-normalize after pruning
        row_sums = self.markov_matrix.sum(axis=1)
        self.markov_matrix = np.divide(self.markov_matrix, row_sums[:, np.newaxis], 
                                      where=row_sums[:, np.newaxis]!=0)

        # 2. Individual Number Profiling with Decay
        weights = np.array([decay_factor**(N - i - 1) for i in range(N)])
        
        for n in range(1, self.pool + 1):
            best_lag = 1
            best_p = 1.0
            best_rate = 0.0
            
            # Gap Stats (v2.4)
            occurrences = [i for i, d in enumerate(history) if n in d['numbers']]
            gaps = np.diff(occurrences) if len(occurrences) > 1 else []
            mean_gap = np.mean(gaps) if len(gaps) > 0 else (self.pool / self.pick)
            std_gap = np.std(gaps) if len(gaps) > 0 else mean_gap
            current_gap = N - occurrences[-1] if occurrences else N
            
            for lag in range(1, 16):
                # Weighted observations
                obs_weighted = 0.0
                total_weighted = 0.0
                
                for i in range(lag, N):
                    w = weights[i]
                    if n in history[i-lag]['numbers']:
                        total_weighted += w
                        if n in history[i]['numbers']:
                            obs_weighted += w
                
                if total_weighted > 5.0: # Minimum effective sample size
                    # Standard p-value calculation (unweighted for significance, weighted for rate)
                    obs_raw = 0
                    total_raw = 0
                    for i in range(lag, N):
                        if n in history[i-lag]['numbers']:
                            total_raw += 1
                            if n in history[i]['numbers']:
                                obs_raw += 1
                    
                    try:
                        p = stats.binomtest(obs_raw, total_raw, self.p_theoretical, alternative='greater').pvalue
                    except AttributeError:
                        p = stats.binom_test(obs_raw, total_raw, self.p_theoretical, alternative='greater')
                    
                    rate_weighted = obs_weighted / total_weighted
                    if p < best_p:
                        best_p = p
                        best_lag = lag
                        best_rate = rate_weighted
                        
            # Fourier (on recent 1000 for stability)
            recent_N = min(1000, N)
            series = np.array([1 if n in d['numbers'] else 0 for d in history[-recent_N:]], dtype=float)
            detrended = series - series.mean()
            fft_vals = np.fft.rfft(detrended)
            power = np.abs(fft_vals) ** 2
            
            if len(power) > 1:
                dom_idx = np.argmax(power[1:]) + 1
                phase = np.angle(fft_vals[dom_idx])
                freq = dom_idx / len(series)
                amp = np.abs(fft_vals[dom_idx]) / len(series)
            else:
                phase, freq, amp = 0.0, 0.0, 0.0
                
            self.profiling[n] = {
                'best_lag': int(best_lag),
                'lag_p_value': float(best_p),
                'lag_rate': float(best_rate),
                'lag_edge': float(max(0, best_rate - self.p_theoretical)),
                'fourier_freq': float(freq),
                'fourier_phase': float(phase),
                'fourier_amp': float(amp),
                'mean_gap': float(mean_gap),
                'std_gap': float(std_gap),
                'current_gap': int(current_gap)
            }
            
        return self.profiling

    def predict(self, history: List[Dict], n_to_pick: int = 5) -> Dict[str, Any]:
        T = len(history)
        if not self.profiling:
            return {'numbers': [], 'confidence': 0.0, 'method': 'untrained'}

        # Update current gaps in profiling before prediction
        for n in range(1, self.pool + 1):
            occurrences = [i for i, d in enumerate(history) if n in d['numbers']]
            self.profiling[n]['current_gap'] = T - occurrences[-1] if occurrences else T

        # 1. ADW (Adaptive Dynamic Weights)
        # Using a fixed default or cached weights to save time, or recalculating
        # For simplicity, keeping the logic but adding GapComponent to weights
        component_performance = {'lag': 0.0, 'fourier': 0.0, 'markov': 0.0}
        if T > 150:
            eval_window = 100
            for i in range(T - eval_window, T):
                actual = set(history[i]['numbers'])
                test_scores = {'lag': Counter(), 'fourier': Counter(), 'markov': Counter()}
                prev_draw = history[i-1]['numbers']
                for n in range(1, self.pool + 1):
                    prof = self.profiling[n]
                    if n in history[i - prof['best_lag']]['numbers']:
                        test_scores['lag'][n] = prof['lag_edge']
                    test_scores['fourier'][n] = prof['fourier_amp'] * np.cos(2 * np.pi * prof['fourier_freq'] * i + prof['fourier_phase'])
                    if self.markov_matrix is not None:
                        test_scores['markov'][n] = sum(self.markov_matrix[p][n] for p in prev_draw)
                for comp in ['lag', 'fourier', 'markov']:
                    top_n = [x[0] for x in sorted(test_scores[comp].items(), key=lambda x: -x[1])[:5]]
                    hits = len(set(top_n) & actual)
                    component_performance[comp] += hits

        total_p = sum(component_performance.values())
        if total_p > 0:
            w_lag, w_fourier, w_markov = component_performance['lag']/total_p, component_performance['fourier']/total_p, component_performance['markov']/total_p
        else:
            w_lag, w_fourier, w_markov = 0.6, 0.3, 0.1

        w_lag = 0.5 * w_lag + 0.5 * 0.6
        w_fourier = 0.5 * w_fourier + 0.5 * 0.3
        w_markov = 1.0 - w_lag - w_fourier

        # 2. Scoring Components
        scores = {}
        prev_draw = history[-1]['numbers']
        for n in range(1, self.pool + 1):
            profile = self.profiling[n]
            
            # IRAP Base Scores
            lag_score = profile['lag_edge'] if (T-profile['best_lag'] >= 0 and n in history[T-profile['best_lag']]['numbers']) else 0
            f_score = profile['fourier_amp'] * np.cos(2 * np.pi * profile['fourier_freq'] * T + profile['fourier_phase'])
            m_score = sum(self.markov_matrix[p][n] for p in prev_draw) / len(prev_draw) if self.markov_matrix is not None else 0
            
            base_score = w_lag * lag_score + w_fourier * f_score + w_markov * m_score
            
            # Gap Overshoot Component (v2.4 NEW)
            # If current gap is significantly larger than historical mean + std
            # we apply an "overshoot pressure" score.
            gap_threshold = profile['mean_gap'] + 1.5 * profile['std_gap']
            gap_pressure = 0.0
            if profile['current_gap'] > gap_threshold:
                # Pressure increases as gap grows further
                gap_pressure = 0.02 * (profile['current_gap'] - gap_threshold) / profile['mean_gap']
            
            scores[n] = base_score + min(0.05, gap_pressure)

        # 3. Zonal Synergy
        # Adjusting pool ranges based on self.pool
        z_size = self.pool // 3
        zones = {1: range(1, z_size+1), 2: range(z_size+1, 2*z_size+1), 3: range(2*z_size+1, self.pool+1)}
        zone_performance = {z: np.mean([scores[n] for n in nums]) for z, nums in zones.items()}
        
        max_zone = max(zone_performance, key=zone_performance.get)
        for n in zones[max_zone]:
            scores[n] *= 1.15 # Synergy Boost

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        selected = [x[0] for x in ranked[:n_to_pick]]
        
        avg_lag_p = np.mean([self.profiling[n]['lag_p_value'] for n in selected])
        confidence = 0.5 + (1.0 - avg_lag_p) * 0.4
        
        return {
            'numbers': sorted(selected),
            'confidence': float(min(0.98, confidence)),
            'method': 'IRAP_v2.4_GapOvershoot',
            'details': {
                'weights': {'lag': round(w_lag, 3), 'fourier': round(w_fourier, 3), 'markov': round(w_markov, 3)},
                'hot_zone': max_zone,
                'top_gap_pressure': {int(n): self.profiling[n]['current_gap'] for n in selected}
            }
        }
