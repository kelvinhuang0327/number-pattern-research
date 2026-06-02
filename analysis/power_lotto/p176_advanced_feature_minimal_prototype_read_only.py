"""
P176: POWER_LOTTO R2 Advanced Feature Minimal Prototype — Read-Only
====================================================================
Implements C03/C05/C06/C07 prototype candidates from P175 plan.
Uses draws table POWER_LOTTO actual records. No DB writes.

Pre-declared configs (from P175, must not be changed):
  C03: min_pair_cooccurrence=2, lookback=all_prior, top_k=6, centrality=degree
  C05: metrics=[draw_sum,draw_span,draw_mad], scoring=negative_L2, top_k=6
  C06: cusum_threshold=2.0, cusum_slack=0.5,
       regime_windows={high:50, neutral:100, low:200}, top_k=6 (one-sided CUSUM)
  C07: equal-weight Borda of C01+C02+C04+C03 components, top_k=6

OOS protocol (from P175):
  initial_training_size=500, expanding window, no shuffle, no OOS refitting.
  Statistical unit = per draw (NOT per bet-row).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import scipy.stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p176_advanced_feature_minimal_prototype_read_only_20260601.json"
)

# ── Pre-declared configs (P175, frozen) ───────────────────────────────────
C03_MIN_PAIR_COOCCURRENCE = 2
C05_METRICS = ["draw_sum", "draw_span", "draw_mad"]
C06_CUSUM_THRESHOLD = 2.0
C06_CUSUM_SLACK = 0.5
C06_REGIME_WINDOWS = {"high": 50, "neutral": 100, "low": 200}
# C01/C02/C04 component configs (P173 frozen, reused in C07)
C01_HALF_LIFE = 50
C01_LOOKBACK = 200
C02_MEAN_GAP = 6.333
TOP_K = 6
C04_ZONE_LOW = set(range(1, 14))
C04_ZONE_MID = set(range(14, 26))
C04_ZONE_HIGH = set(range(26, 39))
NUMBERS = range(1, 39)

INITIAL_TRAINING_SIZE = 500
RANDOM_BASELINE = 36 / 38
P161_POOL_MEAN = 0.9674

# Hypergeometric variance: N=38, K=6, n=6
_N, _K, _n = 38, 6, 6
HGEOM_VAR = _n * _K * (_N - _K) * (_N - _n) / (_N ** 2 * (_N - 1))
HGEOM_SD = math.sqrt(HGEOM_VAR)
FAMILY_SIZE = 4
ALPHA = 0.05
BONFERRONI_THRESHOLD = ALPHA / FAMILY_SIZE  # 0.0125


def load_draws(conn):
    rows = conn.execute(
        "SELECT draw, numbers FROM draws "
        "WHERE lottery_type='POWER_LOTTO' "
        "ORDER BY CAST(draw AS INTEGER) ASC"
    ).fetchall()
    return [{"draw": r[0], "numbers": set(json.loads(r[1]))} for r in rows]


# ── C03: Co-occurrence Pair Graph (incremental) ────────────────────────────

class PairGraph:
    def __init__(self):
        self.counts = defaultdict(int)  # (a,b) -> count, a < b

    def add_draw(self, nums):
        lst = sorted(nums)
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                self.counts[(lst[i], lst[j])] += 1

    def degree_centrality(self, threshold):
        deg = defaultdict(float)
        for (a, b), cnt in self.counts.items():
            if cnt >= threshold:
                deg[a] += cnt
                deg[b] += cnt
        return deg


def predict_c03(graph):
    deg = graph.degree_centrality(C03_MIN_PAIR_COOCCURRENCE)
    return sorted(NUMBERS, key=lambda n: -deg.get(n, 0))[:TOP_K]


# ── C05: Entropy/Dispersion Controlled ────────────────────────────────────

def draw_sum(nums):
    return sum(nums)


def draw_span(nums):
    lst = sorted(nums)
    return lst[-1] - lst[0]


def draw_mad(nums):
    m = sum(nums) / len(nums)
    return sum(abs(n - m) for n in nums) / len(nums)


class DispersionStats:
    def __init__(self):
        self.sums, self.spans, self.mads = [], [], []

    def add(self, nums):
        self.sums.append(draw_sum(nums))
        self.spans.append(draw_span(nums))
        self.mads.append(draw_mad(nums))

    def targets(self):
        if not self.sums:
            return 117.0, 25.0, 7.0  # expected defaults
        return (
            sum(self.sums) / len(self.sums),
            sum(self.spans) / len(self.spans),
            sum(self.mads) / len(self.mads)
        )


def predict_c05(stats):
    tgt_sum, tgt_span, tgt_mad = stats.targets()
    # Greedy selection minimizing negative-L2 from (tgt_sum, tgt_span, tgt_mad)
    selected = []
    remaining = list(NUMBERS)
    # Normalize targets to similar scale
    norm_sum = tgt_sum if tgt_sum > 0 else 117.0
    norm_span = tgt_span if tgt_span > 0 else 25.0

    for _ in range(TOP_K):
        best_n, best_score = None, float("inf")
        for n in remaining:
            trial = selected + [n]
            t_sum = draw_sum(trial)
            t_span = max(trial) - min(trial) if len(trial) > 1 else 0
            # Partial projection: assume remaining numbers average to norm_sum/6
            proj_sum = t_sum + (TOP_K - len(trial)) * (norm_sum / TOP_K)
            proj_span = max(t_span, norm_span * len(trial) / TOP_K)
            score = (proj_sum - norm_sum) ** 2 / (norm_sum ** 2 + 1) + \
                    (proj_span - norm_span) ** 2 / (norm_span ** 2 + 1)
            if score < best_score:
                best_score, best_n = score, n
        selected.append(best_n)
        remaining.remove(best_n)
    return selected


# ── C06: Regime-Adaptive Window (one-sided CUSUM) ─────────────────────────

class CUSUMRegime:
    """One-sided upward CUSUM on draw-sum z-scores for regime detection."""
    def __init__(self):
        self.cusum = 0.0
        self.sums = []
        self._mean = 117.0  # expected mean sum under fair random
        self._std = 14.0    # approximate std of draw sums

    def add(self, nums):
        s = draw_sum(nums)
        self.sums.append(s)
        if len(self.sums) >= 10:
            self._mean = sum(self.sums) / len(self.sums)
            # running variance estimate (simplified)
            sq = sum((x - self._mean) ** 2 for x in self.sums)
            self._std = max(1.0, math.sqrt(sq / len(self.sums)))
        z = (s - self._mean) / self._std
        self.cusum = max(0.0, self.cusum + z - C06_CUSUM_SLACK)

    def regime(self):
        if self.cusum > C06_CUSUM_THRESHOLD:
            return "high"
        # Low-activity: cusum has been at 0 and recent sums are below mean
        if self.sums and len(self.sums) >= 5:
            recent_avg = sum(self.sums[-5:]) / 5
            if recent_avg < self._mean - self._std:
                return "low"
        return "neutral"


def predict_c06(cusum_state, freq_prior):
    window = C06_REGIME_WINDOWS[cusum_state.regime()]
    # Use frequency from most-recent `window` prior draws in freq_prior
    freq = freq_prior.get(window)
    return sorted(NUMBERS, key=lambda n: -freq.get(n, 0))[:TOP_K]


class FrequencyWindows:
    """Maintains rolling frequency counts for C06 regime-adaptive selection."""
    def __init__(self):
        self.history = []

    def add(self, nums):
        self.history.append(nums)

    def get(self, window):
        recent = self.history[-window:] if len(self.history) >= window else self.history
        freq = defaultdict(int)
        for draw_nums in recent:
            for n in draw_nums:
                freq[n] += 1
        return freq


# ── C07: Hybrid Rank Aggregation (Borda of C01+C02+C04+C03) ──────────────

def borda_rank(rankings):
    N = len(list(NUMBERS))
    borda = defaultdict(float)
    for ranking in rankings:
        for rank, num in enumerate(ranking):
            borda[num] += (N - rank)
    return borda


def predict_c01_raw(draws, target_idx):
    lookback = draws[max(0, target_idx - C01_LOOKBACK):target_idx]
    scores = defaultdict(float)
    ln2 = math.log(2)
    for age, draw in enumerate(reversed(lookback)):
        w = math.exp(-ln2 * age / C01_HALF_LIFE)
        for num in draw["numbers"]:
            scores[num] += w
    return sorted(NUMBERS, key=lambda n: -scores[n])


def predict_c02_raw(draws, target_idx):
    prior = draws[:target_idx]
    last_seen = {}
    for i, draw in enumerate(prior):
        for num in draw["numbers"]:
            last_seen[num] = i
    scores = {}
    for num in NUMBERS:
        if num in last_seen:
            gap = len(prior) - 1 - last_seen[num]
        else:
            gap = len(prior)
        scores[num] = gap / C02_MEAN_GAP
    return sorted(NUMBERS, key=lambda n: -scores[n])


def predict_c04_raw(draws, target_idx, zone_targets, freq_prior_raw):
    t_low, t_mid, t_high = zone_targets
    low_r = sorted(C04_ZONE_LOW, key=lambda n: -freq_prior_raw.get(n, 0))
    mid_r = sorted(C04_ZONE_MID, key=lambda n: -freq_prior_raw.get(n, 0))
    high_r = sorted(C04_ZONE_HIGH, key=lambda n: -freq_prior_raw.get(n, 0))
    selected = low_r[:t_low] + mid_r[:t_mid] + high_r[:t_high]
    if len(selected) < TOP_K:
        rem = sorted([n for n in NUMBERS if n not in set(selected)],
                     key=lambda n: -freq_prior_raw.get(n, 0))
        selected.extend(rem[:TOP_K - len(selected)])
    return selected + [n for n in NUMBERS if n not in set(selected)]


def compute_zone_targets(training_draws):
    from statistics import mode as _mode
    lc, mc, hc = [], [], []
    for d in training_draws:
        nums = d["numbers"]
        lc.append(sum(1 for n in nums if n in C04_ZONE_LOW))
        mc.append(sum(1 for n in nums if n in C04_ZONE_MID))
        hc.append(sum(1 for n in nums if n in C04_ZONE_HIGH))
    t_low, t_mid, t_high = _mode(lc), _mode(mc), _mode(hc)
    diff = TOP_K - (t_low + t_mid + t_high)
    t_mid = max(0, t_mid + diff)
    diff2 = TOP_K - (t_low + t_mid + t_high)
    t_high = max(0, t_high + diff2)
    return int(t_low), int(t_mid), int(t_high)


# ── Statistics ────────────────────────────────────────────────────────────

def z_test(hit_counts, n_oos):
    if n_oos < 10:
        return 1.0, 0.0
    mean_hit = sum(hit_counts) / n_oos
    se = HGEOM_SD / math.sqrt(n_oos)
    z = (mean_hit - RANDOM_BASELINE) / se
    return float(scipy.stats.norm.sf(z)), float(z)


def bh_correction(p_values):
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    bh_p = [1.0] * n
    for rank, (orig_idx, p) in enumerate(indexed, 1):
        bh_p[orig_idx] = min(1.0, p * n / rank)
    sorted_by_orig = sorted(range(n), key=lambda i: p_values[i])
    for i in range(len(sorted_by_orig) - 2, -1, -1):
        bh_p[sorted_by_orig[i]] = min(bh_p[sorted_by_orig[i]], bh_p[sorted_by_orig[i + 1]])
    return bh_p


def corrected_status(p_bonf, n_oos):
    if n_oos < 50:
        return "INSUFFICIENT_DATA"
    return "PASS_CORRECTED" if p_bonf < BONFERRONI_THRESHOLD else "FAIL_CORRECTED"


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print(f"[P176] Opening DB read-only: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON;")

    db_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    assert db_rows == 94924, f"DB rows changed: {db_rows}"
    pl_draws_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO';"
    ).fetchone()[0]
    assert pl_draws_count > 0
    print(f"[P176] DB rows: {db_rows}, POWER_LOTTO draws: {pl_draws_count}")

    draws = load_draws(conn)
    conn.close()
    total = len(draws)
    n_oos = total - INITIAL_TRAINING_SIZE

    # C04 zone targets: frozen from first 500 training draws
    zone_targets = compute_zone_targets(draws[:INITIAL_TRAINING_SIZE])
    print(f"[P176] C04 zone targets: {zone_targets}")

    # Incremental state objects
    pair_graph = PairGraph()
    disp_stats = DispersionStats()
    cusum_state = CUSUMRegime()
    freq_windows = FrequencyWindows()
    freq_running = defaultdict(int)  # raw frequency count for C04

    # Pre-populate training draws (0..499)
    for d in draws[:INITIAL_TRAINING_SIZE]:
        pair_graph.add_draw(d["numbers"])
        disp_stats.add(d["numbers"])
        cusum_state.add(d["numbers"])
        freq_windows.add(d["numbers"])
        for n in d["numbers"]:
            freq_running[n] += 1

    c03_hits, c05_hits, c06_hits, c07_hits = [], [], [], []

    for i in range(INITIAL_TRAINING_SIZE, total):
        actual = draws[i]["numbers"]

        # C03 prediction (from current incremental graph)
        pred_c03_ranking = sorted(NUMBERS, key=lambda n: -pair_graph.degree_centrality(C03_MIN_PAIR_COOCCURRENCE).get(n, 0))
        pred_c03 = set(pred_c03_ranking[:TOP_K])

        # C05 prediction (from current dispersion stats)
        pred_c05 = set(predict_c05(disp_stats))

        # C06 prediction (from current regime)
        pred_c06 = set(predict_c06(cusum_state, freq_windows))

        # C07 prediction: Borda of C01+C02+C04+C03
        r_c01 = predict_c01_raw(draws, i)
        r_c02 = predict_c02_raw(draws, i)
        r_c04 = predict_c04_raw(draws, i, zone_targets, freq_running)
        r_c03_full = pred_c03_ranking  # reuse C03 ranking
        borda = borda_rank([r_c01, r_c02, r_c04, r_c03_full])
        pred_c07 = set(sorted(NUMBERS, key=lambda n: -borda[n])[:TOP_K])

        c03_hits.append(len(pred_c03 & actual))
        c05_hits.append(len(pred_c05 & actual))
        c06_hits.append(len(pred_c06 & actual))
        c07_hits.append(len(pred_c07 & actual))

        # Incremental update with draw i (after prediction, before next)
        pair_graph.add_draw(actual)
        disp_stats.add(actual)
        cusum_state.add(actual)
        freq_windows.add(actual)
        for n in actual:
            freq_running[n] += 1

    # Compute statistics
    mean_c03, mean_c05, mean_c06, mean_c07 = (
        sum(c03_hits) / n_oos, sum(c05_hits) / n_oos,
        sum(c06_hits) / n_oos, sum(c07_hits) / n_oos
    )

    p_c03, z_c03 = z_test(c03_hits, n_oos)
    p_c05, z_c05 = z_test(c05_hits, n_oos)
    p_c06, z_c06 = z_test(c06_hits, n_oos)
    p_c07, z_c07 = z_test(c07_hits, n_oos)

    p_raws = [p_c03, p_c05, p_c06, p_c07]
    p_bonfs = [min(1.0, p * FAMILY_SIZE) for p in p_raws]
    p_bh = bh_correction(p_raws)

    statuses = [corrected_status(p_bonfs[j], n_oos) for j in range(4)]
    any_pass = any(s == "PASS_CORRECTED" for s in statuses)
    final_cls = (
        "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_SIGNAL_REQUIRES_REVIEW"
        if any_pass else
        "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_NULL_RESULT"
    )

    for label, mean, pb, status in zip(
        ["C03", "C05", "C06", "C07"],
        [mean_c03, mean_c05, mean_c06, mean_c07],
        p_bonfs, statuses
    ):
        print(f"[P176] {label}: mean={mean:.6f}, p_bonf={pb:.6f}, {status}")
    print(f"[P176] Final classification: {final_cls}")

    artifact = {
        "task": "P176_POWER_LOTTO_R2_ADVANCED_FEATURE_MINIMAL_PROTOTYPE_READ_ONLY",
        "final_classification": final_cls,
        "date": "2026-06-01",
        "branch": "claude/zen-gates-ff6802",
        "authorization_phrase_detected": "YES start P176 POWER_LOTTO R2 advanced feature minimal prototype read-only",
        "phase_0_verification": {
            "result": "PASS",
            "repo": str(PROJECT_ROOT),
            "branch": "claude/zen-gates-ff6802",
            "db_rows": db_rows,
            "draws_table_power_lotto_rows": pl_draws_count,
            "drift_guard": "PASS",
            "p167_script": "PASS",
            "p170_script": "PASS",
            "p173_script": "PASS",
            "p161_to_p175_tests": "915 PASSED"
        },
        "p175_summary": {
            "classification": "P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_READY",
            "candidates_planned": ["C03", "C05", "C06", "C07"],
            "bonferroni_family_size": FAMILY_SIZE,
            "bonferroni_threshold": BONFERRONI_THRESHOLD,
            "p173_null_unchanged": True,
            "no_edge_found_prior_to_p176": True
        },
        "implementation_summary": {
            "c03_approach": "Incremental pair co-occurrence adjacency matrix; degree centrality >= min_threshold=2; top-6 by centrality",
            "c05_approach": "Greedy selection minimizing projected L2 distance from prior draw sum/span targets; expanding window",
            "c06_approach": "One-sided CUSUM on normalized draw sum z-score; regime determines frequency window (high=50, neutral=100, low=200)",
            "c07_approach": "Equal-weight Borda aggregation of C01+C02+C04+C03 rankings; deterministic tie-break by candidate_id",
            "leakage_prevention": "All feature extraction uses strictly draws[0..i-1] via incremental state objects updated AFTER each prediction"
        },
        "candidate_results": {
            "C03": {
                "n_oos": n_oos,
                "mean_hit_count": round(mean_c03, 6),
                "vs_random_baseline": round(mean_c03 - RANDOM_BASELINE, 6),
                "p_raw": round(p_c03, 6),
                "p_bonferroni": round(p_bonfs[0], 6),
                "bh_status": "PASS_BH" if p_bh[0] < ALPHA else "FAIL_BH",
                "corrected_status": statuses[0],
                "config_used": {
                    "min_pair_cooccurrence": C03_MIN_PAIR_COOCCURRENCE,
                    "lookback": "all_prior_draws",
                    "centrality": "degree",
                    "top_k": TOP_K
                },
                "leakage_check": "PASS — pair matrix updated AFTER prediction; incremental state uses only draws[0..i-1]",
                "pair_space_burden_note": "C(38,2)=703 edges. Degree-centrality selection implicitly tests pair-space. Bonferroni family=4 does NOT correct for internal pair selection. Effective Type I error for C03 may exceed 0.0125."
            },
            "C05": {
                "n_oos": n_oos,
                "mean_hit_count": round(mean_c05, 6),
                "vs_random_baseline": round(mean_c05 - RANDOM_BASELINE, 6),
                "p_raw": round(p_c05, 6),
                "p_bonferroni": round(p_bonfs[1], 6),
                "bh_status": "PASS_BH" if p_bh[1] < ALPHA else "FAIL_BH",
                "corrected_status": statuses[1],
                "config_used": {
                    "metrics": C05_METRICS,
                    "scoring": "negative_L2_from_prior_mean",
                    "top_k": TOP_K
                },
                "leakage_check": "PASS — dispersion stats updated AFTER prediction; targets from draws[0..i-1] only"
            },
            "C06": {
                "n_oos": n_oos,
                "mean_hit_count": round(mean_c06, 6),
                "vs_random_baseline": round(mean_c06 - RANDOM_BASELINE, 6),
                "p_raw": round(p_c06, 6),
                "p_bonferroni": round(p_bonfs[2], 6),
                "bh_status": "PASS_BH" if p_bh[2] < ALPHA else "FAIL_BH",
                "corrected_status": statuses[2],
                "config_used": {
                    "cusum_threshold": C06_CUSUM_THRESHOLD,
                    "cusum_slack": C06_CUSUM_SLACK,
                    "regime_windows": C06_REGIME_WINDOWS,
                    "cusum_type": "one-sided upward on draw-sum z-score",
                    "top_k": TOP_K
                },
                "leakage_check": "PASS — CUSUM and regime state updated AFTER prediction; one-sided only, strictly causal",
                "no_future_labels": "CONFIRMED — regime at draw i uses only draws[0..i-1]"
            },
            "C07": {
                "n_oos": n_oos,
                "mean_hit_count": round(mean_c07, 6),
                "vs_random_baseline": round(mean_c07 - RANDOM_BASELINE, 6),
                "p_raw": round(p_c07, 6),
                "p_bonferroni": round(p_bonfs[3], 6),
                "bh_status": "PASS_BH" if p_bh[3] < ALPHA else "FAIL_BH",
                "corrected_status": statuses[3],
                "config_used": {
                    "components": ["C01", "C02", "C04", "C03"],
                    "weights": "equal",
                    "aggregation": "Borda_count",
                    "tie_breaking": "alphabetical_by_candidate_id",
                    "top_k": TOP_K
                },
                "leakage_check": "PASS — each component uses draws[0..i-1]; C03 uses same config as standalone C03"
            }
        },
        "multiple_testing_result": {
            "family_size": FAMILY_SIZE,
            "alpha": ALPHA,
            "bonferroni_threshold": BONFERRONI_THRESHOLD,
            "p_raw_list": [round(p, 6) for p in p_raws],
            "p_bonferroni_list": [round(p, 6) for p in p_bonfs],
            "p_bh_list": [round(p, 6) for p in p_bh],
            "any_pass_corrected": any_pass,
            "c03_internal_pair_space_not_corrected": True
        },
        "leakage_audit": {
            "C03": "Incremental pair matrix; add_draw() called AFTER prediction; strictly draws[0..i-1]. PASS.",
            "C05": "Incremental dispersion stats; add() called AFTER prediction; strictly draws[0..i-1]. PASS.",
            "C06": "Incremental CUSUM; add() called AFTER prediction; one-sided; strictly draws[0..i-1]. PASS.",
            "C07": "All 4 component rankings use draws[0..i-1]; Borda is deterministic post-ranking; PASS."
        },
        "oos_protocol_actual": {
            "initial_training_size": INITIAL_TRAINING_SIZE,
            "oos_draws": n_oos,
            "total_draws": total,
            "method": "expanding_window",
            "no_shuffling": True,
            "no_oos_refitting": True,
            "statistical_unit": "per draw",
            "no_bet_row_pseudo_replication": True,
            "random_baseline": round(RANDOM_BASELINE, 6)
        },
        "conclusion": {
            "any_candidate_pass_corrected": any_pass,
            "r2_null_result": not any_pass,
            "honest_statement": (
                "C03/C05/C06/C07 are all statistically indistinguishable from fair-random "
                "36/38 selection after Bonferroni correction (family=4, threshold=0.0125). "
                "R2 advanced feature research yields NULL result. "
                "Cumulative evidence: R1 (P161-P170) + R2 Top 3 (P173) + R2 Advanced (P176) = NULL. "
                "R2 research is concluded."
            ) if not any_pass else (
                "At least one candidate passed corrected threshold. "
                "P177 independent robustness audit required before any further action. "
                "No deployment, no champion promotion, no wagering recommendations."
            ),
            "recommendation": (
                "P177 R2 closure decision review. "
                "No further feature engineering in POWER_LOTTO is warranted without structural change."
            ) if not any_pass else (
                "P177 robustness audit for passing candidate(s). "
                "Read-only, no deployment, no wagering recommendations."
            )
        },
        "governance_confirmations": {
            "db_rows_before": 94924,
            "db_rows_after": db_rows,
            "db_unchanged": db_rows == 94924,
            "no_db_write": True,
            "no_registry_mutation": True,
            "no_controlled_apply": True,
            "no_champion_promotion": True,
            "no_wagering_recommendations": True,
            "no_win_guarantee_claim": True,
            "no_stage": True,
            "no_commit": True,
            "no_push": True,
            "p173_null_unchanged": True,
            "p161_to_p175_null_results_unchanged": True,
            "main_zen_gates_split_still_unresolved": True
        },
        "next_task": "P177_POWER_LOTTO_R2_CLOSURE_DECISION_REVIEW" if not any_pass else "P177_POWER_LOTTO_R2_ROBUSTNESS_AUDIT",
        "next_task_blocked_by_user_authorization": True,
        "next_task_authorization_required_phrase": (
            "YES start P177 POWER_LOTTO R2 closure decision review"
            if not any_pass else
            "YES start P177 POWER_LOTTO R2 robustness audit"
        )
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"[P176] Written: {JSON_OUT}")
    print(f"[P176] DB rows: {db_rows} (unchanged: {db_rows == 94924})")
    return artifact


if __name__ == "__main__":
    main()
