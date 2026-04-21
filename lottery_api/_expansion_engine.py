#!/usr/bin/env python3
"""
Extended Research Expansion Engine — Discovery + Distribution Shaping
======================================================================
8-hour batch: Continuous hypothesis generation, lightweight validation,
distribution balancing, and learning signal activation.

PHASES:
  1. Hypothesis Expansion — diverse, under-explored feature classes
  2. Lightweight Validation — 2-window (150/300) + ≤20 perms
  3. Distribution Balancing — every 20 hypotheses
  4. Learning Signal Activation — every 30 minutes
  5. Logging & Persistence — everything to JSONL + analysis_outputs/

Feature Classes (prioritized):
  gap_derivative, entropy_rolling, cooccurrence_excess, zone_transition,
  lag_k_echo, sum_mod_k, hybrid combinations

Constraints:
  - NO modification to production thresholds
  - NO heavy validation (no McNemar, no full-window)
  - NO overwriting existing VALIDATED hypotheses
  - NO pruning
"""
import sys, os, json, time, math, random, hashlib, traceback
from datetime import datetime, timezone
from collections import Counter
from typing import Dict, List, Tuple, Optional

# ── Path setup ──
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_SCRIPT_DIR)

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

# ── Target goals ──
TARGET_TOTAL = 20       # ≥20 hypotheses per type
TARGET_PROV  = 5        # ≥5 PROVISIONAL per type
TARGET_REJ   = 3        # ≥3 REJECTED per type
MAX_RUNTIME  = 8 * 3600 # 8 hours
BALANCE_INTERVAL = 20   # check distribution every N hypotheses
LEARNING_INTERVAL = 30 * 60  # recompute learning every 30min
N_PERM = 20             # permutation runs per hypothesis
PERM_P_THRESHOLD = 0.10 # relaxed for discovery mode
MAX_CYCLES_NO_REJ = 12  # if a type can't produce REJECTED after this many cycles, relax target

# ── Feature class definitions ──
FEATURE_CLASSES = [
    'gap_derivative',
    'entropy_rolling',
    'cooccurrence_excess',
    'zone_transition',
    'lag_k_echo_2',
    'lag_k_echo_3',
    'lag_k_echo_4',
    'lag_k_echo_5',
    'sum_mod_3',
    'sum_mod_5',
    'sum_mod_7',
    'hybrid_gap_entropy',
    'hybrid_zone_lag',
    'hybrid_cooccurrence_sum',
    'baseline_uniform',
    'baseline_recency',
    'baseline_frequency',
    'risky_inverse_hot',
    'risky_extreme_cold',
    'risky_anti_pattern',
    'risky_random_walk',
]

# Category labels
RISKY_CLASSES = {c for c in FEATURE_CLASSES if c.startswith('risky_')}
BASELINE_CLASSES = {c for c in FEATURE_CLASSES if c.startswith('baseline_')}
ADVANCED_CLASSES = FEATURE_CLASSES  # all are valid

# ── Strategy modes ──
STRATEGY_MODES = ['best_300p', 'greedy_30p', 'ucb1', 'best_300p', 'greedy_30p']
PORTFOLIO_TYPES = ['coverage_only', 'coverage+concentration']


def log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════════
# Registry helpers
# ═══════════════════════════════════════════════════════════════════════

def load_all_hypotheses() -> List[Dict]:
    from engine.hypothesis_registry import list_all
    return list_all()


def count_by_type() -> Dict[str, Counter]:
    all_h = load_all_hypotheses()
    by_lt = {lt: Counter() for lt in LOTTERY_TYPES}
    for h in all_h:
        lt = h.get('lottery', '?')
        if lt in by_lt:
            by_lt[lt][h.get('status', '?')] += 1
    return by_lt


def get_refined_distribution() -> Dict[str, Dict]:
    from engine.hypothesis_registry import summarize_refined_distribution
    return summarize_refined_distribution(load_all_hypotheses())


def get_existing_configs(lottery_type: str) -> List[Dict]:
    """Get all existing policy configs for similarity checking."""
    all_h = load_all_hypotheses()
    configs = []
    for h in all_h:
        if h.get('lottery') != lottery_type:
            continue
        notes = h.get('notes', '{}')
        try:
            cfg = json.loads(notes) if isinstance(notes, str) else notes
            cfg['_feature_class'] = cfg.get('feature_class', 'unknown')
            configs.append(cfg)
        except (json.JSONDecodeError, TypeError):
            pass
    return configs


# ═══════════════════════════════════════════════════════════════════════
# Similarity checking
# ═══════════════════════════════════════════════════════════════════════

def config_similarity(a: Dict, b: Dict) -> float:
    """
    Compute similarity between two policy configs ∈ [0, 1].
    Considers: conf_weights, thresholds, strategy_mode, feature_class.
    """
    sim = 0.0
    weight_keys = ['signal_strength', 'signal_agreement', 'regime_stability',
                   'entropy_state', 'recent_performance']

    # Weight similarity (35% of total)
    aw = a.get('conf_weights', {})
    bw = b.get('conf_weights', {})
    if aw and bw:
        diffs = [abs(aw.get(k, 0.2) - bw.get(k, 0.2)) for k in weight_keys]
        weight_sim = 1.0 - min(sum(diffs), 1.0)
        sim += 0.35 * weight_sim

    # Threshold similarity (25%)
    at = a.get('n_bets_thresholds', [0.35, 0.5, 0.65, 0.8])
    bt = b.get('n_bets_thresholds', [0.35, 0.5, 0.65, 0.8])
    if at and bt:
        t_diffs = [abs(at[i] - bt[i]) for i in range(min(len(at), len(bt)))]
        thresh_sim = 1.0 - min(sum(t_diffs), 1.0)
        sim += 0.25 * thresh_sim

    # Strategy mode match (20%)
    if a.get('strategy_mode') == b.get('strategy_mode'):
        sim += 0.20

    # Feature class match (20%)
    if a.get('feature_class') == b.get('feature_class'):
        sim += 0.20

    return sim


def is_too_similar(cfg: Dict, existing: List[Dict], threshold: float = 0.7) -> bool:
    """Check if a config is too similar to any existing one."""
    for ex in existing:
        if config_similarity(cfg, ex) > threshold:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Policy generation with feature class diversity
# ═══════════════════════════════════════════════════════════════════════

def _feature_class_to_weight_bias(feature_class: str) -> Dict[str, float]:
    """
    Map a feature class to a weight bias pattern.
    Different feature classes emphasize different confidence dimensions.
    """
    biases = {
        'gap_derivative':       {'signal_strength': 0.4, 'recent_performance': 0.3},
        'entropy_rolling':      {'entropy_state': 0.45, 'signal_agreement': 0.25},
        'cooccurrence_excess':  {'signal_agreement': 0.4, 'regime_stability': 0.25},
        'zone_transition':      {'regime_stability': 0.35, 'entropy_state': 0.25},
        'lag_k_echo_2':         {'recent_performance': 0.4, 'signal_strength': 0.25},
        'lag_k_echo_3':         {'recent_performance': 0.35, 'signal_strength': 0.3},
        'lag_k_echo_4':         {'recent_performance': 0.3, 'signal_agreement': 0.3},
        'lag_k_echo_5':         {'recent_performance': 0.25, 'signal_agreement': 0.35},
        'sum_mod_3':            {'entropy_state': 0.3, 'signal_strength': 0.3},
        'sum_mod_5':            {'entropy_state': 0.35, 'signal_strength': 0.25},
        'sum_mod_7':            {'entropy_state': 0.4, 'regime_stability': 0.2},
        'hybrid_gap_entropy':   {'signal_strength': 0.3, 'entropy_state': 0.3},
        'hybrid_zone_lag':      {'regime_stability': 0.3, 'recent_performance': 0.3},
        'hybrid_cooccurrence_sum': {'signal_agreement': 0.3, 'entropy_state': 0.3},
        'baseline_uniform':     {},  # no bias → uniform weights
        'baseline_recency':     {'recent_performance': 0.5},
        'baseline_frequency':   {'signal_strength': 0.5},
        'risky_inverse_hot':    {'signal_strength': 0.1, 'entropy_state': 0.5},
        'risky_extreme_cold':   {'recent_performance': 0.1, 'regime_stability': 0.5},
        'risky_anti_pattern':   {'signal_agreement': 0.1, 'entropy_state': 0.4},
        'risky_random_walk':    {'entropy_state': 0.15, 'signal_agreement': 0.15},
    }
    return biases.get(feature_class, {})


def generate_policy(
    feature_class: str,
    rng: random.Random,
    variant_idx: int = 0,
) -> Dict:
    """
    Generate a single policy config for a given feature class.
    Returns a dict with all policy params + feature_class metadata.
    """
    from analysis.decision_engine_v2 import PolicyConfig

    weight_keys = ['signal_strength', 'signal_agreement', 'regime_stability',
                   'entropy_state', 'recent_performance']

    # Start with small random noise
    raw = {k: rng.uniform(0.08, 0.35) for k in weight_keys}

    # Apply feature class bias
    bias = _feature_class_to_weight_bias(feature_class)
    for k, v in bias.items():
        raw[k] = v + rng.gauss(0, 0.05)

    # Ensure all positive
    for k in raw:
        raw[k] = max(0.03, raw[k])

    # Normalize
    s = sum(raw.values())
    weights = {k: round(v / s, 4) for k, v in raw.items()}

    # Thresholds: vary by risky vs baseline vs advanced
    if feature_class in RISKY_CLASSES:
        # Risky: lower thresholds → more aggressive betting
        base_t = [rng.uniform(0.15, 0.35), rng.uniform(0.3, 0.5),
                  rng.uniform(0.45, 0.65), rng.uniform(0.6, 0.8)]
    elif feature_class in BASELINE_CLASSES:
        # Baseline: standard thresholds
        base_t = [rng.uniform(0.3, 0.4), rng.uniform(0.45, 0.55),
                  rng.uniform(0.6, 0.7), rng.uniform(0.75, 0.85)]
    else:
        # Advanced: varied thresholds
        base_t = [rng.uniform(0.2, 0.45), rng.uniform(0.35, 0.6),
                  rng.uniform(0.5, 0.75), rng.uniform(0.65, 0.9)]

    thresholds = sorted([round(t, 3) for t in base_t])

    # Strategy mode: bias by feature class
    if 'lag' in feature_class or 'recency' in feature_class:
        mode = 'greedy_30p'
    elif 'baseline' in feature_class:
        mode = 'best_300p'
    else:
        mode = rng.choice(STRATEGY_MODES)

    # Portfolio type
    portfolio = rng.choice(PORTFOLIO_TYPES) if rng.random() > 0.6 else 'coverage_only'

    # Min confidence
    if feature_class in RISKY_CLASSES:
        min_conf = round(rng.uniform(0.1, 0.25), 3)
    else:
        min_conf = round(rng.uniform(0.2, 0.45), 3)

    timestamp = int(time.time() * 1000) % 1000000
    policy_id = f"exp_{feature_class}_{timestamp}_{variant_idx:02d}"

    return {
        'policy_id': policy_id,
        'conf_weights': weights,
        'n_bets_thresholds': thresholds,
        'strategy_mode': mode,
        'portfolio_type': portfolio,
        'min_confidence': min_conf,
        'feature_class': feature_class,
    }


def generate_adversarial_policy(rng: random.Random, variant_idx: int = 0) -> Dict:
    """
    Generate a deliberately adversarial policy designed to fail validation.
    Uses inverted weight priorities and extreme thresholds.
    """
    weight_keys = ['signal_strength', 'signal_agreement', 'regime_stability',
                   'entropy_state', 'recent_performance']

    # Strategy 1: Inverted weights — emphasize worst dimensions
    raw = {k: rng.uniform(0.01, 0.08) for k in weight_keys}
    # Minimize the most useful signals
    raw['signal_strength'] = rng.uniform(0.01, 0.05)
    raw['recent_performance'] = rng.uniform(0.01, 0.05)
    # Maximize noise dimensions
    raw['entropy_state'] = rng.uniform(0.5, 0.8)

    s = sum(raw.values())
    weights = {k: round(v / s, 4) for k, v in raw.items()}

    # Extreme thresholds: very high → always bet 1 (sub-baseline)
    thresholds = sorted([round(rng.uniform(0.85, 0.99), 3) for _ in range(4)])

    timestamp = int(time.time() * 1000) % 1000000
    return {
        'policy_id': f"exp_adversarial_{timestamp}_{variant_idx:02d}",
        'conf_weights': weights,
        'n_bets_thresholds': thresholds,
        'strategy_mode': 'best_300p',
        'portfolio_type': 'coverage_only',
        'min_confidence': round(rng.uniform(0.6, 0.9), 3),  # very high → skip many draws
        'feature_class': 'adversarial',
    }


def select_next_feature_class(
    existing_by_class: Counter,
    rng: random.Random,
    force_risky: bool = False,
    force_baseline: bool = False,
) -> str:
    """
    Select the next feature class to generate, prioritizing under-explored.
    Enforces: ≥30% risky, ≥30% baseline across the batch.
    """
    if force_risky:
        candidates = list(RISKY_CLASSES)
    elif force_baseline:
        candidates = list(BASELINE_CLASSES)
    else:
        candidates = list(FEATURE_CLASSES)

    # Weight inversely by how many already exist
    weights = []
    for fc in candidates:
        count = existing_by_class.get(fc, 0)
        # Inverse weight: fewer existing → higher probability
        w = 1.0 / (1.0 + count)
        weights.append(w)

    total = sum(weights)
    probs = [w / total for w in weights]

    # Weighted random choice
    r = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            return candidates[i]

    return candidates[-1]


# ═══════════════════════════════════════════════════════════════════════
# Lightweight validation
# ═══════════════════════════════════════════════════════════════════════

def lightweight_validate(hypothesis: Dict, lottery_type: str) -> Tuple[str, Dict]:
    """
    Lightweight validation: 2 windows (150, 300), ≤20 permutations.
    NO full-window, NO McNemar.
    """
    import numpy as np
    from analysis.decision_engine_v2 import (
        PolicyConfig, PolicyValidator, ConfidenceEngine,
        BASELINES, METRIC_THRESHOLD, POOL_SIZE, MAX_BETS,
    )
    from engine.research_runner import _get_history, _get_coordinator

    notes = hypothesis.get('notes', '{}')
    try:
        cfg = json.loads(notes) if isinstance(notes, str) else notes
    except json.JSONDecodeError:
        return 'REJECTED', {'reason': 'bad_notes'}

    policy = PolicyConfig(
        policy_id=hypothesis['name'],
        conf_weights=cfg.get('conf_weights', {}),
        n_bets_thresholds=cfg.get('n_bets_thresholds', [0.35, 0.5, 0.65, 0.8]),
        strategy_mode=cfg.get('strategy_mode', 'best_300p'),
        portfolio_type=cfg.get('portfolio_type', 'coverage_only'),
        min_confidence=cfg.get('min_confidence', 0.3),
    )

    history = _get_history(lottery_type, limit=600)
    coordinator = _get_coordinator(lottery_type)
    validator = PolicyValidator()
    conf_engine = ConfidenceEngine(os.path.join(_SCRIPT_DIR, 'data'))

    # 2 windows: 150 and 300
    e150 = validator._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 150)
    e300 = validator._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 300)
    two_window_ok = (e150 > 0) and (e300 > 0)

    # Permutation test: N_PERM runs
    obs_edge, perm_p = validator._permutation_test(
        policy, lottery_type, history, conf_engine, coordinator,
        n_perm=N_PERM, test_window=200,
    )
    perm_ok = perm_p < PERM_P_THRESHOLD

    # Sharpe
    baseline_1 = BASELINES[lottery_type][1]
    avg_bets = 3.0
    baseline = 1.0 - (1.0 - baseline_1) ** avg_bets
    vol = math.sqrt(baseline * (1 - baseline) + 1e-9)
    sharpe = obs_edge / vol if vol > 0 else 0.0

    # Verdict: 3 gates
    gates = sum([two_window_ok, perm_ok, sharpe > 0])
    if gates >= 3:
        status = 'VALIDATED'
    elif gates == 2:
        status = 'PROVISIONAL'
    else:
        status = 'REJECTED'

    summary = {
        'window_150': round(e150, 5),
        'window_300': round(e300, 5),
        'edge_150': round(e150, 5),
        'edge_300': round(e300, 5),
        'edge_full': None,
        'two_window_ok': two_window_ok,
        'perm_p': round(perm_p, 4),
        'perm_n': N_PERM,
        'sharpe': round(sharpe, 4),
        'obs_edge': round(obs_edge, 5),
        'verdict': {3: 'ADOPT', 2: 'WATCH', 1: 'REJECT', 0: 'REJECT'}[gates],
        'mode': 'expansion_lightweight',
        'feature_class': cfg.get('feature_class', 'unknown'),
    }
    return status, summary


# ═══════════════════════════════════════════════════════════════════════
# Distribution balancing
# ═══════════════════════════════════════════════════════════════════════

def check_distribution(counts: Dict[str, Counter]) -> Dict[str, Dict]:
    """
    Check distribution balance per lottery type.
    Returns adjustment recommendations.
    """
    adjustments = {}
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        total = sum(c.values())
        n_val = c.get('VALIDATED', 0)
        n_prov = c.get('PROVISIONAL', 0)
        n_rej = c.get('REJECTED', 0)
        n_reg = c.get('REGISTERED', 0)

        adj = {
            'total': total,
            'needs_more': total < TARGET_TOTAL,
            'needs_prov': n_prov < TARGET_PROV,
            'needs_rej': n_rej < TARGET_REJ,
            'action': 'continue',
        }

        if total > 0:
            val_ratio = (n_val + n_prov) / (total - n_reg) if (total - n_reg) > 0 else 0
            rej_ratio = n_rej / (total - n_reg) if (total - n_reg) > 0 else 0

            if val_ratio > 0.8 and n_rej < TARGET_REJ:
                adj['action'] = 'inject_noise'
                adj['reason'] = f'Too many VALIDATED ({val_ratio:.0%}), need more REJECTED'
            elif rej_ratio > 0.8 and n_prov < TARGET_PROV:
                adj['action'] = 'inject_simple'
                adj['reason'] = f'Too many REJECTED ({rej_ratio:.0%}), need simpler variants'
            elif total < TARGET_TOTAL:
                adj['action'] = 'increase_rate'
        else:
            adj['action'] = 'increase_rate'

        if not adj['needs_more'] and not adj['needs_prov'] and not adj['needs_rej']:
            adj['action'] = 'satisfied'

        adjustments[lt] = adj
    return adjustments


# ═══════════════════════════════════════════════════════════════════════
# Learning signal recomputation
# ═══════════════════════════════════════════════════════════════════════

def recompute_learning_signals():
    """Recompute learning bonuses for all lottery types."""
    from engine.learning_integrator import compute_learning_bonuses, apply_learning_signals

    results = {}
    for lt in LOTTERY_TYPES:
        try:
            # Apply learning signals (updates strategy_states)
            r = apply_learning_signals(lt, dry_run=False)
            results[lt] = r
        except Exception as e:
            results[lt] = {'status': 'error', 'error': str(e)}

    return results


def compute_research_scores() -> Dict[str, float]:
    """Compute research_score per lottery type using refined_status weights."""
    from engine.hypothesis_registry import compute_research_score, reclassify_existing_refined_status

    # Reclassify persisted outputs only; no re-validation.
    reclassify_existing_refined_status()

    all_h = load_all_hypotheses()
    scores = {}
    for lt in LOTTERY_TYPES:
        hyps = [h for h in all_h if h.get('lottery') == lt]
        if not hyps:
            scores[lt] = 0.0
            continue
        scores[lt] = compute_research_score(hyps)
    return scores


# ═══════════════════════════════════════════════════════════════════════
# Logging helpers
# ═══════════════════════════════════════════════════════════════════════

def log_to_feedback(entry: Dict):
    """Append to research_feedback.jsonl."""
    path = os.path.join(_SCRIPT_DIR, 'data', 'research_feedback.jsonl')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')


def save_analysis_output(data: Dict, filename: str):
    """Save to research/analysis_outputs/."""
    outdir = os.path.join(_PROJECT_ROOT, 'research', 'analysis_outputs')
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return path


# ═══════════════════════════════════════════════════════════════════════
# Main expansion loop
# ═══════════════════════════════════════════════════════════════════════

def run_expansion():
    from engine.hypothesis_registry import register, list_by_status, update_status, list_all

    start_time = time.time()
    last_learning_time = start_time
    total_generated = 0
    total_validated = 0
    generation_log = []

    log("=" * 70)
    log("  EXTENDED RESEARCH EXPANSION ENGINE")
    log("  Discovery + Distribution Shaping Mode")
    log(f"  Max Runtime: {MAX_RUNTIME/3600:.0f} hours")
    log(f"  Target: ≥{TARGET_TOTAL} hypotheses, ≥{TARGET_PROV} PROV, ≥{TARGET_REJ} REJ per type")
    log("=" * 70)

    # Initial state
    counts = count_by_type()
    log("\nINITIAL STATE:")
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        log(f"  {lt:<14} total={sum(c.values())} {dict(c)}")

    # Track feature class coverage globally
    feature_class_counts = {lt: Counter() for lt in LOTTERY_TYPES}
    for h in list_all():
        lt = h.get('lottery', '?')
        if lt not in feature_class_counts:
            continue
        notes = h.get('notes', '{}')
        try:
            cfg = json.loads(notes) if isinstance(notes, str) else notes
            fc = cfg.get('feature_class', 'legacy')
            feature_class_counts[lt][fc] += 1
        except (json.JSONDecodeError, TypeError):
            feature_class_counts[lt]['legacy'] += 1

    rng = random.Random(int(time.time()))
    cycle = 0
    cycles_per_type = dict.fromkeys(LOTTERY_TYPES, 0)  # track per-type attempts
    relaxed_rej = set()  # types where REJ target is relaxed

    while True:
        elapsed = time.time() - start_time
        if elapsed >= MAX_RUNTIME:
            log(f"\n⏰ MAX RUNTIME REACHED ({elapsed/3600:.1f}h)")
            break

        # Check if all targets are met (with relaxation)
        counts = count_by_type()
        all_satisfied = True
        for lt in LOTTERY_TYPES:
            c = counts[lt]
            total = sum(c.values())
            n_prov = c.get('PROVISIONAL', 0) + c.get('VALIDATED', 0)
            n_rej = c.get('REJECTED', 0)
            rej_target = 0 if lt in relaxed_rej else TARGET_REJ
            if total < TARGET_TOTAL or n_prov < TARGET_PROV or n_rej < rej_target:
                all_satisfied = False
                break

        if all_satisfied:
            log(f"\n✅ ALL TARGETS MET after {elapsed/60:.1f} min")
            break

        # Relax REJ target for types that can't produce REJECTED
        for lt in LOTTERY_TYPES:
            if lt not in relaxed_rej and cycles_per_type[lt] >= MAX_CYCLES_NO_REJ:
                c = counts.get(lt, Counter())
                if c.get('REJECTED', 0) == 0:
                    log(f"\n⚠️  {lt}: No REJECTED after {cycles_per_type[lt]} cycles — relaxing REJ target")
                    relaxed_rej.add(lt)

        cycle += 1
        log(f"\n{'─'*60}")
        log(f"  CYCLE {cycle} — Elapsed: {elapsed/60:.1f} min")
        log(f"{'─'*60}")

        # Distribution check every BALANCE_INTERVAL generations
        if total_generated > 0 and total_generated % BALANCE_INTERVAL == 0:
            log("\n📊 Distribution Balance Check:")
            adjustments = check_distribution(counts)
            for lt, adj in adjustments.items():
                log(f"  {lt}: {adj['action']} (total={adj['total']})")

        # Learning signal recomputation
        if time.time() - last_learning_time >= LEARNING_INTERVAL:
            log("\n🧠 Recomputing Learning Signals...")
            scores = compute_research_scores()
            for lt, sc in scores.items():
                log(f"  {lt}: research_score = {sc:.4f}")
            refined_dist = get_refined_distribution()
            log("\n📦 Refined Status Distribution:")
            for lt in LOTTERY_TYPES:
                d = refined_dist.get(lt, {'counts': {}, 'warnings': []})
                log(f"  {lt}: {d.get('counts', {})}")
                for w in d.get('warnings', []):
                    log(f"    ⚠ {w}")
            lr = recompute_learning_signals()
            for lt, r in lr.items():
                log(f"  {lt}: {r.get('status', 'ok')}")
            last_learning_time = time.time()

            # Log to feedback
            log_to_feedback({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'action': 'expansion_learning_recompute',
                'cycle': cycle,
                'research_scores': scores,
                'elapsed_min': round(elapsed / 60, 1),
            })

        # Process each lottery type
        for lt in LOTTERY_TYPES:
            c = counts.get(lt, Counter())
            total = sum(c.values())
            n_prov = c.get('PROVISIONAL', 0) + c.get('VALIDATED', 0)
            n_rej = c.get('REJECTED', 0)

            # Check if this type is satisfied
            rej_target = 0 if lt in relaxed_rej else TARGET_REJ
            if total >= TARGET_TOTAL and n_prov >= TARGET_PROV and n_rej >= rej_target:
                continue

            cycles_per_type[lt] += 1

            log(f"\n  [{lt}] total={total} PROV+VAL={n_prov} REJ={n_rej}")

            # Determine how many to generate this cycle
            remaining = max(TARGET_TOTAL - total, 2)
            batch_size = min(3, remaining)  # 3 per cycle per type

            # Decide distribution enforcement
            adjustments = check_distribution(counts)
            adj = adjustments.get(lt, {})
            force_risky = adj.get('action') == 'inject_noise'
            force_baseline = adj.get('action') == 'inject_simple'

            # If we need REJECTED and have many cycles, generate adversarial policies
            need_adversarial = (n_rej < TARGET_REJ and cycles_per_type[lt] > 5
                                and lt not in relaxed_rej)

            # Enforce 30% risky / 30% baseline across the batch
            fc_total = sum(feature_class_counts[lt].values())
            fc_risky = sum(feature_class_counts[lt].get(c, 0) for c in RISKY_CLASSES)
            fc_baseline = sum(feature_class_counts[lt].get(c, 0) for c in BASELINE_CLASSES)

            risky_ratio = fc_risky / max(fc_total, 1)
            baseline_ratio = fc_baseline / max(fc_total, 1)

            policies_to_register = []
            existing_configs = get_existing_configs(lt)

            for bi in range(batch_size):
                # If adversarial needed, generate deliberately bad policies
                if need_adversarial and bi == 0:
                    cfg = generate_adversarial_policy(rng, total_generated + bi)
                    policies_to_register.append(cfg)
                    existing_configs.append(cfg)
                    feature_class_counts[lt]['adversarial'] += 1
                    continue

                # Force risky/baseline if needed for distribution
                fr = force_risky or (risky_ratio < 0.30 and rng.random() < 0.5)
                fb = force_baseline or (baseline_ratio < 0.30 and rng.random() < 0.5 and not fr)

                fc = select_next_feature_class(
                    feature_class_counts[lt], rng,
                    force_risky=fr, force_baseline=fb,
                )

                # Generate policy with diversity check
                max_attempts = 5
                for _ in range(max_attempts):
                    cfg = generate_policy(fc, rng, variant_idx=total_generated + bi)
                    if not is_too_similar(cfg, existing_configs):
                        break
                    # Try different feature class
                    fc = select_next_feature_class(
                        feature_class_counts[lt], rng,
                        force_risky=fr, force_baseline=fb,
                    )
                else:
                    # Use it anyway after max attempts
                    pass

                policies_to_register.append(cfg)
                existing_configs.append(cfg)
                feature_class_counts[lt][fc] += 1

            # Register hypotheses
            registered = []
            for cfg in policies_to_register:
                try:
                    hyp = register(
                        name=cfg['policy_id'],
                        lottery=lt,
                        theory_basis=f"Expansion [{cfg['feature_class']}] ({cfg['strategy_mode']})",
                        expected_direction="2-window Edge > 0, perm p < 0.10",
                        test_thresholds={
                            'perm_p': PERM_P_THRESHOLD,
                            'two_window': True,
                            'min_edge': 0.0,
                            'sharpe_gt_0': True,
                        },
                        seed=42,
                        n_periods=600,
                        notes=json.dumps(cfg),
                    )
                    registered.append(hyp)
                    total_generated += 1
                except Exception as e:
                    log(f"    Register failed: {cfg['policy_id']}: {e}")

            log(f"    Registered {len(registered)} (total generated: {total_generated})")

            # Validate all REGISTERED for this type (up to batch_size)
            pending = [h for h in list_by_status('REGISTERED') if h['lottery'] == lt]
            pending = pending[:batch_size]

            for i, hyp in enumerate(pending):
                hid = hyp['hypothesis_id']
                short_id = hid[:55]
                t0 = time.time()

                try:
                    status, summary = lightweight_validate(hyp, lt)
                    update_status(hid, status, summary)
                    total_validated += 1

                    vtime = time.time() - t0
                    fc = summary.get('feature_class', '?')
                    log(f"    [{i+1}/{len(pending)}] {short_id}")
                    log(f"      → {status:<12} fc={fc} e150={summary.get('window_150',0):.4f} "
                        f"e300={summary.get('window_300',0):.4f} perm_p={summary.get('perm_p',1):.3f} "
                        f"({vtime:.1f}s)")

                    # Log to feedback
                    log_to_feedback({
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'action': 'expansion_validate',
                        'hypothesis_id': hid,
                        'lottery_type': lt,
                        'feature_class': fc,
                        'status': status,
                        'edge_150': summary.get('window_150', 0),
                        'edge_300': summary.get('window_300', 0),
                        'perm_p': summary.get('perm_p', 1),
                        'sharpe': summary.get('sharpe', 0),
                        'elapsed_s': round(vtime, 1),
                    })

                    generation_log.append({
                        'cycle': cycle,
                        'lottery': lt,
                        'hypothesis_id': hid,
                        'feature_class': fc,
                        'status': status,
                        'edge_150': summary.get('window_150', 0),
                        'edge_300': summary.get('window_300', 0),
                        'perm_p': summary.get('perm_p', 1),
                        'sharpe': summary.get('sharpe', 0),
                    })

                except Exception as e:
                    log(f"    [{i+1}/{len(pending)}] FAILED: {short_id}")
                    log(f"      Error: {e}")
                    try:
                        update_status(hid, 'REJECTED', {'reason': 'validation_error', 'error': str(e)})
                    except Exception:
                        pass

        # Refresh counts after this cycle
        counts = count_by_type()

    # ── Final learning signal update ──
    log("\n🧠 Final Learning Signal Update...")
    scores = compute_research_scores()
    for lt, sc in scores.items():
        log(f"  {lt}: research_score = {sc:.4f}")
    refined_dist = get_refined_distribution()
    log("\n📦 Refined Status Distribution:")
    for lt in LOTTERY_TYPES:
        d = refined_dist.get(lt, {'counts': {}, 'warnings': []})
        log(f"  {lt}: {d.get('counts', {})}")
        for w in d.get('warnings', []):
            log(f"    ⚠ {w}")
    recompute_learning_signals()

    # ── End-of-run report ──
    total_elapsed = time.time() - start_time
    final_counts = count_by_type()

    log("\n" + "=" * 70)
    log("  END-OF-RUN REPORT")
    log("=" * 70)
    log(f"\n  Runtime: {total_elapsed/60:.1f} min ({total_elapsed/3600:.2f} h)")
    log(f"  Hypotheses Generated: {total_generated}")
    log(f"  Hypotheses Validated: {total_validated}")
    log(f"  Cycles: {cycle}")

    # 1. Hypothesis counts per type
    log(f"\n  {'Type':<14} {'Total':>5} {'REG':>5} {'PROV':>5} {'VAL':>5} {'REJ':>5}")
    log(f"  {'─'*14} {'─'*5} {'─'*5} {'─'*5} {'─'*5} {'─'*5}")
    for lt in LOTTERY_TYPES:
        c = final_counts[lt]
        log(f"  {lt:<14} {sum(c.values()):>5} {c.get('REGISTERED',0):>5} "
            f"{c.get('PROVISIONAL',0):>5} {c.get('VALIDATED',0):>5} {c.get('REJECTED',0):>5}")

    # 2. Target check
    log("\n  TARGET CHECK:")
    for lt in LOTTERY_TYPES:
        c = final_counts[lt]
        total = sum(c.values())
        n_pv = c.get('PROVISIONAL', 0) + c.get('VALIDATED', 0)
        n_rej = c.get('REJECTED', 0)
        ok_t = "✅" if total >= TARGET_TOTAL else "❌"
        ok_p = "✅" if n_pv >= TARGET_PROV else "❌"
        ok_r = "✅" if n_rej >= TARGET_REJ else "❌"
        log(f"  {lt}: total={total}{ok_t}  PROV+VAL={n_pv}{ok_p}  REJ={n_rej}{ok_r}")

    # 3. Top 10 hypotheses by edge
    all_h = load_all_hypotheses()
    all_with_edge = []
    for h in all_h:
        rs = h.get('result_summary')
        if not isinstance(rs, dict):
            continue
        edge = rs.get('window_300', rs.get('window_full', rs.get('window_500', 0)))
        if edge is None:
            continue
        all_with_edge.append((edge, h))
    all_with_edge.sort(key=lambda x: x[0], reverse=True)

    log("\n  TOP 10 HYPOTHESES BY EDGE:")
    log(f"  {'#':>2} {'Type':<14} {'Feature Class':<24} {'Edge300':>8} {'perm_p':>7} {'Status':<12}")
    log(f"  {'─'*2} {'─'*14} {'─'*24} {'─'*8} {'─'*7} {'─'*12}")
    for i, (edge, h) in enumerate(all_with_edge[:10]):
        rs = h.get('result_summary', {})
        notes = h.get('notes', '{}')
        try:
            cfg = json.loads(notes) if isinstance(notes, str) else notes
            fc = cfg.get('feature_class', 'legacy')
        except (json.JSONDecodeError, TypeError):
            fc = 'legacy'
        log(f"  {i+1:>2} {h['lottery']:<14} {fc:<24} {edge:>+8.5f} {rs.get('perm_p',1):>7.3f} {h['status']:<12}")

    # 4. Learning multiplier per type
    log("\n  LEARNING SCORES:")
    for lt, sc in scores.items():
        bonus = 0.10 * math.tanh(sc)
        log(f"  {lt}: research_score={sc:.4f} → λ·tanh(r)={bonus:.4f}")

    # 5. Feature class distribution
    log("\n  FEATURE CLASS COVERAGE:")
    for lt in LOTTERY_TYPES:
        fcc = feature_class_counts[lt]
        if fcc:
            top5 = fcc.most_common(5)
            log(f"  {lt}: {dict(top5)}")

    # 6. Emerging strong signals
    log("\n  EMERGING STRONG SIGNALS:")
    strong = [(e, h) for e, h in all_with_edge if e > 0.02 and h['status'] in ('VALIDATED', 'PROVISIONAL')]
    if strong:
        for edge, h in strong[:5]:
            rs = h.get('result_summary', {})
            log(f"  ⭐ {h['lottery']} | edge={edge:+.4f} | perm_p={rs.get('perm_p',1):.3f} | {h['name'][:40]}")
    else:
        log("  (No signals with edge > 0.02 yet)")

    # ── Save analysis output ──
    report = {
        'run_timestamp': datetime.now(timezone.utc).isoformat(),
        'runtime_seconds': round(total_elapsed, 1),
        'total_generated': total_generated,
        'total_validated': total_validated,
        'cycles': cycle,
        'counts': {lt: dict(c) for lt, c in final_counts.items()},
        'refined_distribution': refined_dist,
        'research_scores': scores,
        'top_10': [
            {
                'lottery': h['lottery'],
                'hypothesis_id': h['hypothesis_id'],
                'edge': round(e, 5),
                'perm_p': h.get('result_summary', {}).get('perm_p', 1),
                'status': h['status'],
            }
            for e, h in all_with_edge[:10]
        ],
        'generation_log': generation_log,
        'feature_class_coverage': {lt: dict(fcc) for lt, fcc in feature_class_counts.items()},
    }
    fname = f"expansion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = save_analysis_output(report, fname)
    log(f"\n  Report saved: {path}")

    log("\n" + "=" * 70)
    log("  EXPANSION ENGINE COMPLETE")
    log("=" * 70)

    return report


if __name__ == '__main__':
    run_expansion()
