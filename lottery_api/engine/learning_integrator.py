"""
Learning Signal Integrator — 研究結果 → 決策層橋接器 (v2 Additive Bonus)
========================================================================
Reads validated/rejected research outcomes from hypothesis_registry.jsonl
and computes per-agent ADDITIVE learning bonuses consumed by
StrategyCoordinator.aggregate_scores().

v2 Architecture Change (2026-04-16):
  The v1 multiplicative approach was proven INEFFECTIVE by A/B validation:
  uniform multiplicative `research_multiplier` cancels out in weight
  normalization: (k·w_i) / Σ(k·w_j) = w_i / Σ(w_j) → ZERO EFFECT.

  v2 uses ADDITIVE bonuses applied directly to per-number scores AFTER
  normalized weight aggregation, bypassing the cancellation math.

Integration Points:
  - Reads: hypothesis_registry.jsonl (verdicts, edge, confidence)
  - Reads: strategy_states_*.json (edge_30p for rank-based differentiation)
  - Consumed by: StrategyCoordinator.aggregate_scores() (additive bonus path)

Additive Bonus Formula:
  1. Count VALIDATED / REJECTED / PROVISIONAL hypotheses per lottery_type
  2. research_score = (n_val + 0.5*n_prov - n_rej) / n_total
  3. Per-agent rank-based differential: agents ranked by edge_30p,
     differential ∈ [0.5, 1.0] (best agent = 1.0, worst = 0.5)
  4. bonus = λ * tanh(research_score) * differential
  5. Clamp to [-0.2, +0.2]

Safety Controls:
  - Bounded output: [-0.2, +0.2] — modest impact on score range [0, 1]
  - Rank-based differentiation ensures bonuses are NEVER uniform
  - Append-only audit log: every computation logged to research_feedback.jsonl
  - disable_learning flag: StrategyCoordinator can bypass entirely
  - Minimum samples: needs ≥3 hypotheses before generating bonuses
  - Backward compatible: returns empty dict when no signal available

2026-04-15 Created — Closing the learning loop
2026-04-16 v2 — Additive bonus replaces broken multiplicative multiplier
"""
import json
import logging
import math
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, '..', 'data')

# Constants
EMA_ALPHA = 0.2
MIN_MULTIPLIER = 0.7
MAX_MULTIPLIER = 1.3
MIN_HYPOTHESES = 3       # Need at least 3 hypotheses before generating signals
AUDIT_LOG_PATH = os.path.join(_DATA_DIR, 'research_feedback.jsonl')

# v2 Additive bonus constants
LAMBDA_LEARNING = 0.10   # λ scaling factor ∈ [0.05, 0.15]
MAX_BONUS = 0.20         # Clamp per-agent bonus to [-0.2, +0.2]

# v3 Gating constants (Phase K.5)
GATING_MIN_TOTAL = 5          # need ≥5 evaluated hypotheses for signal
GATING_WEAK_THRESHOLD = 0.05  # |research_score| < 0.05 → WEAK signal
GATING_FACTOR_DISABLED = 0.0
GATING_FACTOR_WEAK = 0.5
GATING_FACTOR_ENABLED = 1.0


def compute_learning_gate(lottery_type: str) -> Dict:
    """
    Phase K.5: Evaluate learning signal quality and return gating decision.

    Returns:
        {
            'gate': 'DISABLED' | 'WEAK' | 'ENABLED',
            'factor': 0.0 | 0.5 | 1.0,
            'reason': str,
            'n_total': int,
            'n_validated': int,
            'n_rejected': int,
            'n_provisional': int,
            'research_score': float,
            'bonus_variance': float,
        }
    """
    hypotheses = _read_hypotheses(lottery_type)
    n_total = len(hypotheses)

    status_counts = Counter(h.get('status', 'REGISTERED') for h in hypotheses)
    n_validated = status_counts.get('VALIDATED', 0)
    n_rejected = status_counts.get('REJECTED', 0)
    n_provisional = status_counts.get('PROVISIONAL', 0)

    # Compute research_score if we have enough data
    research_score = 0.0
    if n_total >= MIN_HYPOTHESES:
        try:
            from engine.hypothesis_registry import compute_research_score
            research_score = compute_research_score(hypotheses)
        except Exception:
            pass

    base_info = {
        'n_total': n_total,
        'n_validated': n_validated,
        'n_rejected': n_rejected,
        'n_provisional': n_provisional,
        'research_score': round(research_score, 6),
        'bonus_variance': 0.0,  # filled below if available
    }

    # Rule 1: Not enough hypotheses → DISABLE
    if n_total < GATING_MIN_TOTAL:
        return {**base_info, 'gate': 'DISABLED', 'factor': GATING_FACTOR_DISABLED,
                'reason': f'n_total={n_total} < {GATING_MIN_TOTAL}'}

    # Rule 2: Strong negative signal (rejected > validated) → FORCE ENABLE
    # Negative learning is still useful: it deprioritizes bad agents
    if n_rejected > n_validated and abs(research_score) >= GATING_WEAK_THRESHOLD:
        return {**base_info, 'gate': 'ENABLED', 'factor': GATING_FACTOR_ENABLED,
                'reason': f'strong negative signal: rejected({n_rejected}) > validated({n_validated})'}

    # Rule 3: Weak signal → apply at half strength
    if abs(research_score) < GATING_WEAK_THRESHOLD:
        return {**base_info, 'gate': 'WEAK', 'factor': GATING_FACTOR_WEAK,
                'reason': f'|research_score|={abs(research_score):.4f} < {GATING_WEAK_THRESHOLD}'}

    # Rule 4: Signal is reliable → full enable
    return {**base_info, 'gate': 'ENABLED', 'factor': GATING_FACTOR_ENABLED,
            'reason': f'|research_score|={abs(research_score):.4f} >= {GATING_WEAK_THRESHOLD}'}


def _read_hypotheses(lottery_type: str) -> List[Dict]:
    """Read all hypotheses for a given lottery type from the registry."""
    registry_path = os.path.join(_DATA_DIR, 'hypothesis_registry.jsonl')
    if not os.path.exists(registry_path):
        return []

    seen = {}
    with open(registry_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get('lottery') == lottery_type:
                    seen[entry['hypothesis_id']] = entry
            except (json.JSONDecodeError, KeyError):
                continue

    return list(seen.values())


def _compute_research_multiplier(hypotheses: List[Dict]) -> float:
    """
    Compute a research-based multiplier from hypothesis verdicts.

    Formula:
      research_score = (n_validated - n_rejected) / max(n_total, 1)
      multiplier = 1 + 0.3 * tanh(research_score)
      clamp to [0.7, 1.3]

    Returns 1.0 if insufficient data.
    """
    if len(hypotheses) < MIN_HYPOTHESES:
        return 1.0

    from engine.hypothesis_registry import compute_research_score

    research_score = compute_research_score(hypotheses)
    if abs(research_score) < 1e-12:
        return 1.0

    multiplier = 1.0 + 0.3 * math.tanh(research_score)
    return max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, multiplier))


def _extract_edge_from_hypothesis(hypothesis: Dict) -> Optional[float]:
    """Extract edge value from hypothesis result_summary."""
    rs = hypothesis.get('result_summary')
    if not isinstance(rs, dict):
        return None
    # Use window_full as the primary edge metric
    edge = rs.get('window_full')
    if edge is not None:
        return float(edge)
    # Fallback to window_500
    edge = rs.get('window_500')
    if edge is not None:
        return float(edge)
    return None


def _compute_per_strategy_signals(
    hypotheses: List[Dict],
    strategy_names: List[str],
) -> Dict[str, float]:
    """
    (v1 DEPRECATED) Compute per-strategy research multipliers.
    Kept for backward compatibility with apply_learning_signals().
    """
    global_mult = _compute_research_multiplier(hypotheses)
    if abs(global_mult - 1.0) < 0.01:
        return dict.fromkeys(strategy_names, 1.0)
    return dict.fromkeys(strategy_names, global_mult)


def compute_learning_bonuses(
    lottery_type: str,
    agents: Dict[str, Dict],
) -> Dict[str, float]:
    """
    (v2) Compute per-agent ADDITIVE learning bonuses.

    This replaces the broken multiplicative multiplier path. Bonuses are
    rank-differentiated so they are NEVER uniform across agents.

    Args:
        lottery_type: 'DAILY_539', 'BIG_LOTTO', or 'POWER_LOTTO'
        agents: AGENT_REGISTRY[lottery_type] dict {agent_name: {rsm_key: ...}}

    Returns:
        {agent_name: bonus} where bonus ∈ [-MAX_BONUS, +MAX_BONUS]
        Empty dict if insufficient data.

    Math:
        research_score = (n_val + 0.5*n_prov - n_rej) / n_total
        per-agent differential ∈ [0.5, 1.0] based on edge_30p rank
        bonus = λ * tanh(research_score) * differential
        clamped to [-0.2, +0.2]
    """
    hypotheses = _read_hypotheses(lottery_type)
    if len(hypotheses) < MIN_HYPOTHESES:
        return {}

    from engine.hypothesis_registry import classify_refined_for_entry, compute_research_score

    status_counts = Counter(h.get('status', 'REGISTERED') for h in hypotheses)
    research_score = compute_research_score(hypotheses)
    if abs(research_score) < 1e-12:
        return {}

    refined_counts = Counter(
        classify_refined_for_entry(h, peers_same_lottery=hypotheses).get('refined_status', 'WEAK_PROVISIONAL')
        for h in hypotheses
        if h.get('status') in ('VALIDATED', 'PROVISIONAL', 'REJECTED')
    )

    # Load strategy states for per-agent edge differentiation
    states_path = os.path.join(_DATA_DIR, f'strategy_states_{lottery_type}.json')
    states: Dict = {}
    if os.path.exists(states_path):
        try:
            with open(states_path, 'r', encoding='utf-8') as f:
                states = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Collect per-agent edge for rank-based differentiation
    edge_by_agent: Dict[str, float] = {}
    for agent_name, cfg in agents.items():
        rsm_key = cfg.get('rsm_key', '')
        state = states.get(rsm_key, {})
        edge_by_agent[agent_name] = float(state.get('edge_30p', 0.0))

    # Rank agents by edge: best edge → differential=1.0, worst → 0.5
    sorted_agents = sorted(edge_by_agent.items(), key=lambda x: x[1], reverse=True)
    n_agents = len(sorted_agents)

    bonuses: Dict[str, float] = {}
    for rank, (agent_name, _edge) in enumerate(sorted_agents):
        if n_agents <= 1:
            differential = 1.0
        else:
            differential = 1.0 - 0.5 * (rank / (n_agents - 1))
        raw_bonus = LAMBDA_LEARNING * math.tanh(research_score) * differential
        bonuses[agent_name] = max(-MAX_BONUS, min(MAX_BONUS, raw_bonus))

    # Audit log
    _append_audit_log({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'lottery_type': lottery_type,
        'action': 'compute_learning_bonuses_v2',
        'research_score': round(research_score, 5),
        'n_hypotheses': len(hypotheses),
        'hypothesis_counts': dict(status_counts),
        'refined_status_counts': dict(refined_counts),
        'bonuses': {k: round(v, 6) for k, v in bonuses.items()},
    })

    return bonuses


def _append_audit_log(entry: Dict):
    """Append to research_feedback.jsonl audit log."""
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    with open(AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')


def apply_learning_signals(
    lottery_type: str,
    dry_run: bool = False,
) -> Dict:
    """
    Read hypothesis registry → compute research multiplier → write to strategy_states.

    This is the main entry point. Called after research cycles or on data ingest.

    Returns dict with details of what was applied.
    """
    states_path = os.path.join(_DATA_DIR, f'strategy_states_{lottery_type}.json')
    if not os.path.exists(states_path):
        return {'lottery_type': lottery_type, 'status': 'no_states_file'}

    with open(states_path, 'r', encoding='utf-8') as f:
        states = json.load(f)

    hypotheses = _read_hypotheses(lottery_type)

    if len(hypotheses) < MIN_HYPOTHESES:
        return {
            'lottery_type': lottery_type,
            'status': 'insufficient_hypotheses',
            'count': len(hypotheses),
            'min_required': MIN_HYPOTHESES,
        }

    strategy_names = list(states.keys())
    signals = _compute_per_strategy_signals(hypotheses, strategy_names)
    global_mult = _compute_research_multiplier(hypotheses)

    adjustments = []
    for name, mult in signals.items():
        if name not in states:
            continue
        state = states[name]

        # EMA smooth with previous research_multiplier
        prev_mult = float(state.get('research_multiplier', 1.0))
        smoothed = (1 - EMA_ALPHA) * prev_mult + EMA_ALPHA * mult
        smoothed = max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, smoothed))

        if not dry_run:
            # Save original for reversibility
            if 'research_multiplier_original' not in state:
                state['research_multiplier_original'] = prev_mult
            state['research_multiplier'] = round(smoothed, 5)
            state['research_updated_at'] = datetime.now(timezone.utc).isoformat()

        adjustments.append({
            'strategy': name,
            'prev': round(prev_mult, 5),
            'new': round(smoothed, 5),
            'raw_signal': round(mult, 5),
        })

    if not dry_run and adjustments:
        with open(states_path, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=2, ensure_ascii=False)

        _append_audit_log({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'lottery_type': lottery_type,
            'global_multiplier': round(global_mult, 5),
            'n_hypotheses': len(hypotheses),
            'adjustments': adjustments,
        })

    status_counts = Counter(h.get('status', 'REGISTERED') for h in hypotheses)

    return {
        'lottery_type': lottery_type,
        'status': 'applied' if not dry_run else 'dry_run',
        'global_multiplier': round(global_mult, 5),
        'hypothesis_counts': dict(status_counts),
        'adjustments': adjustments,
    }


def apply_all_types(dry_run: bool = False) -> Dict[str, Dict]:
    """Apply learning signals for all lottery types."""
    results = {}
    for lt in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
        try:
            results[lt] = apply_learning_signals(lt, dry_run=dry_run)
        except Exception as e:
            logger.error(f"apply_learning_signals({lt}) failed: {e}")
            results[lt] = {'error': str(e)}
    return results


def revert_signals(lottery_type: str) -> Dict:
    """Revert research_multiplier to original values for all strategies."""
    states_path = os.path.join(_DATA_DIR, f'strategy_states_{lottery_type}.json')
    if not os.path.exists(states_path):
        return {'status': 'no_states_file'}

    with open(states_path, 'r', encoding='utf-8') as f:
        states = json.load(f)

    reverted = []
    for name, state in states.items():
        orig = state.get('research_multiplier_original')
        if orig is not None:
            state['research_multiplier'] = orig
            del state['research_multiplier_original']
            if 'research_updated_at' in state:
                del state['research_updated_at']
            reverted.append(name)

    with open(states_path, 'w', encoding='utf-8') as f:
        json.dump(states, f, indent=2, ensure_ascii=False)

    _append_audit_log({
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'lottery_type': lottery_type,
        'action': 'revert',
        'reverted': reverted,
    })

    return {'status': 'reverted', 'count': len(reverted), 'strategies': reverted}
