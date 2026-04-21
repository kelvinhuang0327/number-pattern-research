"""
Action Feedback & Outcome Tracking Engine — Phase R

Closes the feedback loop:
  Actionable Intelligence → Action Tracking → Outcome Measurement
  → Effectiveness Classification → Rule Scoring → Meta Insights

CONSTRAINTS:
- Does NOT modify prediction logic
- Does NOT modify validation logic
- Does NOT modify ranking logic
- Does NOT auto-execute any action
- Only tracks and evaluates outcomes against real data

Persistence: lottery_api/data/action_feedback.json
"""

import json
import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FEEDBACK_PATH = os.path.join(DATA_DIR, 'action_feedback.json')
STRATEGY_STATES_DIR = DATA_DIR

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

# ── Evaluation windows (draws) ────────────────────────────────────────────────

TRACKING_WINDOWS = [10, 30, 100]
DEFAULT_WINDOW = 30

# Noise floor: deltas smaller than these are NEUTRAL
EDGE_NOISE = 0.003       # 0.3 percentage points
SHARPE_NOISE = 0.005
DRAWDOWN_NOISE = 0.002

# Deduplication bucket size: one action per N-draw bucket per (lottery, rule, strategy)
DEDUP_BUCKET = 10


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_feedback_store() -> dict:
    """Load the persistent feedback store. Returns empty store on missing/corrupt file."""
    if not os.path.exists(FEEDBACK_PATH):
        return {'actions': [], 'last_updated': None}
    try:
        with open(FEEDBACK_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'[ActionFeedback] Failed to load feedback store: {e}')
        return {'actions': [], 'last_updated': None}


def _save_feedback_store(store: dict) -> None:
    """Persist the feedback store atomically."""
    store['last_updated'] = datetime.now(timezone.utc).isoformat()
    tmp = FEEDBACK_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        os.replace(tmp, FEEDBACK_PATH)
    except Exception as e:
        logger.error(f'[ActionFeedback] Failed to save feedback store: {e}')


# ── Draw Count ────────────────────────────────────────────────────────────────

def _get_draw_count(lottery_type: str) -> int:
    """Return total number of draws available for this lottery type. Fallback: 0."""
    try:
        from database import db_manager
        from common import normalize_lottery_type
        lt = normalize_lottery_type(lottery_type)
        draws = db_manager.get_all_draws(lt)
        return len(draws) if draws else 0
    except Exception as e:
        logger.debug(f'[ActionFeedback] draw_count lookup failed for {lottery_type}: {e}')
        return 0


# ── Strategy Baseline Snapshot ────────────────────────────────────────────────

def _load_strategy_states(lottery_type: str) -> dict:
    path = os.path.join(STRATEGY_STATES_DIR, f'strategy_states_{lottery_type}.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _snapshot_strategy_metrics(lottery_type: str, strategy_name: str) -> dict:
    """
    Capture current metric snapshot for a strategy.
    Returns dict with edge_1500p, sharpe, drawdown (zeroed if not found).
    """
    states = _load_strategy_states(lottery_type)
    state = states.get(strategy_name, {})
    return {
        'edge_1500p': float(state.get('edge_1500p') or 0),
        'sharpe':     float(state.get('sharpe') or 0),
        'drawdown':   float(state.get('max_drawdown_rate') or 0),
    }


def _get_best_strategy_name(lottery_type: str) -> str:
    """Return the name of the current best strategy for a lottery."""
    states = _load_strategy_states(lottery_type)
    if not states:
        return ''
    validated = [s for s in states.values() if s.get('validated_status') == 'VALIDATED']
    pool = validated or [s for s in states.values() if s.get('validated_status') == 'WATCH']
    if not pool:
        return ''
    best = max(pool, key=lambda s: float(s.get('composite_score') or 0))
    return best.get('name', '') or best.get('strategy_name', '')


# ── Deduplication ─────────────────────────────────────────────────────────────

def _action_fingerprint(lottery_type: str, action_code: str,
                        strategy: str, draw_ref: int) -> str:
    """
    Unique fingerprint for deduplication.
    Actions with the same lottery+code+strategy in the same 10-draw bucket are deduplicated.
    """
    bucket = (draw_ref // DEDUP_BUCKET) * DEDUP_BUCKET
    return f'{lottery_type}|{action_code}|{strategy}|{bucket}'


def _existing_fingerprints(actions: list) -> set:
    return {a.get('_fingerprint', '') for a in actions}


# ── Action Creation ───────────────────────────────────────────────────────────

def _create_action_record(
    lottery_type: str,
    action_code: str,
    priority: str,
    action_title: str,
    strategy: str,
    draw_ref: int,
    baseline: dict,
    tracking_window: int = DEFAULT_WINDOW,
) -> dict:
    """Build a new action tracking record."""
    fp = _action_fingerprint(lottery_type, action_code, strategy, draw_ref)
    return {
        'action_id':       str(uuid.uuid4()),
        '_fingerprint':    fp,
        'lottery_type':    lottery_type,
        'strategy':        strategy,
        'priority':        priority,
        'action_type':     action_code,
        'action_title':    action_title,
        'created_at':      datetime.now(timezone.utc).isoformat(),
        'created_draw_ref': draw_ref,
        'baseline': {
            'edge_1500p': baseline.get('edge_1500p', 0.0),
            'sharpe':     baseline.get('sharpe', 0.0),
            'drawdown':   baseline.get('drawdown', 0.0),
        },
        'tracking_window': tracking_window,
        'status':          'OPEN',
        'evaluated_at':    None,
        'outcome':         None,
    }


def register_actions_from_summary(actionable_summary: dict) -> int:
    """
    Given the output of get_actionable_summary(), create tracking records for new insights.
    Returns count of newly created actions.
    """
    store = _load_feedback_store()
    existing_fps = _existing_fingerprints(store['actions'])
    new_actions = []

    for lt, lt_data in actionable_summary.items():
        if not isinstance(lt_data, dict) or lt_data.get('error'):
            continue

        draw_ref = _get_draw_count(lt)
        best_strategy = (lt_data.get('signals_summary') or {}).get('best_strategy') or \
                        _get_best_strategy_name(lt)

        for insight in lt_data.get('insights', []):
            code  = insight.get('code', 'UNKNOWN')
            prio  = insight.get('priority', 'P2')
            title = insight.get('title', '')

            # Determine which strategy this insight refers to
            # For per-strategy insights the detail may name a strategy;
            # default to the lottery's best strategy.
            strategy = _resolve_strategy_for_insight(insight, lt, best_strategy)
            baseline = _snapshot_strategy_metrics(lt, strategy)

            fp = _action_fingerprint(lt, code, strategy, draw_ref)
            if fp in existing_fps:
                continue  # already tracked in this draw bucket

            record = _create_action_record(
                lottery_type=lt,
                action_code=code,
                priority=prio,
                action_title=title,
                strategy=strategy,
                draw_ref=draw_ref,
                baseline=baseline,
                tracking_window=DEFAULT_WINDOW,
            )
            new_actions.append(record)
            existing_fps.add(fp)

    if new_actions:
        store['actions'].extend(new_actions)
        _save_feedback_store(store)
        logger.info(f'[ActionFeedback] Registered {len(new_actions)} new action(s)')

    return len(new_actions)


def _resolve_strategy_for_insight(insight: dict, lottery_type: str,
                                  default_strategy: str) -> str:
    """Extract the relevant strategy name for an insight, if determinable."""
    # R02 data_source may contain 'strategy=NAME'
    data_src = insight.get('data_source', '')
    if 'strategy=' in data_src:
        parts = {kv.split('=')[0].strip(): kv.split('=')[1].strip()
                 for kv in data_src.split(',') if '=' in kv}
        if 'strategy' in parts:
            return parts['strategy']
    return default_strategy or ''


# ── Outcome Evaluation ────────────────────────────────────────────────────────

def _classify_effectiveness(edge_delta: float, sharpe_delta: float,
                             drawdown_delta: float) -> str:
    """
    Classify action effectiveness:
    EFFECTIVE: edge + sharpe both improved AND drawdown not worsened significantly
    NEUTRAL:   all changes within noise floor
    NEGATIVE:  edge OR sharpe decreased beyond noise, OR drawdown worsened beyond noise
    """
    edge_ok    = edge_delta > EDGE_NOISE
    sharpe_ok  = sharpe_delta > SHARPE_NOISE
    dd_neutral = drawdown_delta <= DRAWDOWN_NOISE    # drawdown increase is bad

    edge_neg   = edge_delta < -EDGE_NOISE
    sharpe_neg = sharpe_delta < -SHARPE_NOISE
    dd_neg     = drawdown_delta > DRAWDOWN_NOISE

    if edge_neg or sharpe_neg or dd_neg:
        return 'NEGATIVE'

    if edge_ok and sharpe_ok and dd_neutral:
        return 'EFFECTIVE'

    return 'NEUTRAL'


def evaluate_pending_actions() -> int:
    """
    Evaluate all OPEN/TRACKING actions whose tracking window has been reached.
    Returns count of newly completed actions.
    """
    store = _load_feedback_store()
    completed = 0

    # Cache draw counts (avoid calling DB multiple times per lottery)
    draw_counts: dict = {}

    for action in store['actions']:
        if action.get('status') == 'COMPLETED':
            continue

        lt = action.get('lottery_type', '')
        if lt not in draw_counts:
            draw_counts[lt] = _get_draw_count(lt)
        current_draws = draw_counts[lt]

        created_ref = action.get('created_draw_ref', 0) or 0
        window      = action.get('tracking_window', DEFAULT_WINDOW)

        draws_elapsed = current_draws - created_ref
        if draws_elapsed < window:
            # Mark as TRACKING if at least 5 draws have passed
            if draws_elapsed >= 5 and action['status'] == 'OPEN':
                action['status'] = 'TRACKING'
            continue

        # Window reached — evaluate
        strategy = action.get('strategy', '')
        current = _snapshot_strategy_metrics(lt, strategy)
        baseline = action.get('baseline', {})

        edge_delta     = current['edge_1500p'] - float(baseline.get('edge_1500p', 0))
        sharpe_delta   = current['sharpe']     - float(baseline.get('sharpe', 0))
        drawdown_delta = current['drawdown']   - float(baseline.get('drawdown', 0))

        effectiveness = _classify_effectiveness(edge_delta, sharpe_delta, drawdown_delta)

        action['status']       = 'COMPLETED'
        action['evaluated_at'] = datetime.now(timezone.utc).isoformat()
        action['outcome'] = {
            'edge_delta':       round(edge_delta, 6),
            'sharpe_delta':     round(sharpe_delta, 6),
            'drawdown_delta':   round(drawdown_delta, 6),
            'effectiveness':    effectiveness,
            'draws_elapsed':    draws_elapsed,
            'current_metrics':  {k: round(v, 6) for k, v in current.items()},
        }
        completed += 1

    if completed:
        _save_feedback_store(store)
        logger.info(f'[ActionFeedback] Evaluated {completed} completed action(s)')

    return completed


# ── Rule Performance Aggregation ──────────────────────────────────────────────

def _aggregate_rule_stats(actions: list) -> dict:
    """
    Aggregate completed actions by action_type (rule code) to compute per-rule stats.
    Returns {action_type: {total, effective_count, neutral_count, negative_count,
                           effectiveness_rate, avg_edge_delta, avg_sharpe_delta,
                           avg_drawdown_delta, rule_score, recommendation}}
    """
    from collections import defaultdict
    stats: dict = defaultdict(lambda: {
        'total': 0,
        'effective_count': 0,
        'neutral_count': 0,
        'negative_count': 0,
        'edge_deltas': [],
        'sharpe_deltas': [],
        'drawdown_deltas': [],
    })

    for action in actions:
        if action.get('status') != 'COMPLETED' or not action.get('outcome'):
            continue
        code = action.get('action_type', 'UNKNOWN')
        eff  = action['outcome'].get('effectiveness', 'NEUTRAL')
        s = stats[code]
        s['total'] += 1
        if eff == 'EFFECTIVE':
            s['effective_count'] += 1
        elif eff == 'NEGATIVE':
            s['negative_count'] += 1
        else:
            s['neutral_count'] += 1
        s['edge_deltas'].append(action['outcome'].get('edge_delta', 0))
        s['sharpe_deltas'].append(action['outcome'].get('sharpe_delta', 0))
        s['drawdown_deltas'].append(action['outcome'].get('drawdown_delta', 0))

    result = {}
    for code, s in stats.items():
        total = s['total']
        eff_count = s['effective_count']
        neg_count = s['negative_count']

        effectiveness_rate = round(eff_count / total, 4) if total else 0.0
        # rule_score: +1 per EFFECTIVE, 0 per NEUTRAL, -1 per NEGATIVE, normalized by total
        rule_score = round((eff_count - neg_count) / total, 4) if total else 0.0

        avg_edge    = round(sum(s['edge_deltas']) / total, 6) if total else 0.0
        avg_sharpe  = round(sum(s['sharpe_deltas']) / total, 6) if total else 0.0
        avg_dd      = round(sum(s['drawdown_deltas']) / total, 6) if total else 0.0

        # Recommendation (requires >=2 samples for reliability)
        if total < 2:
            rec = 'INSUFFICIENT_DATA'
        elif rule_score > 0.5:
            rec = 'KEEP'
        elif rule_score > 0:
            rec = 'TUNE'
        else:
            rec = 'REMOVE'

        result[code] = {
            'action_type':       code,
            'total':             total,
            'effective_count':   eff_count,
            'neutral_count':     s['neutral_count'],
            'negative_count':    neg_count,
            'effectiveness_rate': effectiveness_rate,
            'avg_edge_delta':    avg_edge,
            'avg_sharpe_delta':  avg_sharpe,
            'avg_drawdown_delta': avg_dd,
            'rule_score':        rule_score,
            'recommendation':    rec,
        }

    return result


# ── Meta Insights ─────────────────────────────────────────────────────────────

def _build_meta_insights(rule_stats: dict) -> dict:
    """
    Identify top/worst performing rules and generate keep/tune/remove recommendations.
    Only considers rules with >= 1 completed evaluation.
    """
    if not rule_stats:
        return {'top_rules': [], 'worst_rules': [], 'keep': [], 'tune': [], 'remove': [],
                'summary': '無已完成評估的建議'}

    rules = list(rule_stats.values())
    # Sort by rule_score descending
    rules_sorted = sorted(rules, key=lambda r: r['rule_score'], reverse=True)

    top_rules   = [r for r in rules_sorted if r['rule_score'] > 0][:3]
    worst_rules = [r for r in reversed(rules_sorted) if r['rule_score'] <= 0][:3]

    keep   = [r['action_type'] for r in rules if r['recommendation'] == 'KEEP']
    tune   = [r['action_type'] for r in rules if r['recommendation'] == 'TUNE']
    remove = [r['action_type'] for r in rules if r['recommendation'] == 'REMOVE']

    # Overall effectiveness %
    total_evaluated = sum(r['total'] for r in rules)
    total_effective = sum(r['effective_count'] for r in rules)
    overall_rate    = round(total_effective / total_evaluated, 4) if total_evaluated else 0.0

    if total_evaluated == 0:
        summary = '尚無完成評估的建議'
    elif overall_rate >= 0.6:
        summary = f'{int(overall_rate*100)}% 建議有效 — 系統整體表現穩健'
    elif overall_rate >= 0.4:
        summary = f'{int(overall_rate*100)}% 建議有效 — 部分規則需調整'
    else:
        summary = f'僅 {int(overall_rate*100)}% 建議有效 — 多數規則效果有限，需重新檢視'

    return {
        'total_evaluated':   total_evaluated,
        'total_effective':   total_effective,
        'overall_rate':      overall_rate,
        'top_rules':         top_rules,
        'worst_rules':       worst_rules,
        'keep':              keep,
        'tune':              tune,
        'remove':            remove,
        'summary':           summary,
    }


# ── Public API Functions ──────────────────────────────────────────────────────

def get_feedback_summary() -> dict:
    """
    Full feedback summary:
    - overall action effectiveness
    - per-rule stats
    - meta insights (top/worst/keep/tune/remove)

    Also triggers evaluation of any pending actions.
    """
    # First: evaluate pending actions
    evaluate_pending_actions()

    store = _load_feedback_store()
    actions = store.get('actions', [])

    completed_actions = [a for a in actions if a.get('status') == 'COMPLETED']
    open_actions      = [a for a in actions if a.get('status') == 'OPEN']
    tracking_actions  = [a for a in actions if a.get('status') == 'TRACKING']

    rule_stats   = _aggregate_rule_stats(actions)
    meta         = _build_meta_insights(rule_stats)

    # Recent completed (most recent 5)
    recent = sorted(
        completed_actions,
        key=lambda a: a.get('evaluated_at') or '',
        reverse=True
    )[:5]

    # Effectiveness breakdown
    eff_counts = {'EFFECTIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0}
    for a in completed_actions:
        eff = (a.get('outcome') or {}).get('effectiveness')
        if eff in eff_counts:
            eff_counts[eff] += 1

    total_completed = len(completed_actions)
    eff_pct  = round(eff_counts['EFFECTIVE'] / total_completed, 4) if total_completed else 0
    neg_pct  = round(eff_counts['NEGATIVE']  / total_completed, 4) if total_completed else 0

    return {
        'totals': {
            'all':       len(actions),
            'open':      len(open_actions),
            'tracking':  len(tracking_actions),
            'completed': total_completed,
        },
        'effectiveness': {
            'effective_count':  eff_counts['EFFECTIVE'],
            'neutral_count':    eff_counts['NEUTRAL'],
            'negative_count':   eff_counts['NEGATIVE'],
            'effective_pct':    eff_pct,
            'negative_pct':     neg_pct,
            'summary_label':    meta['summary'],
        },
        'rule_stats':   rule_stats,
        'meta_insights': meta,
        'recent_completed': [
            {
                'action_id':    a['action_id'],
                'lottery_type': a['lottery_type'],
                'strategy':     a['strategy'],
                'action_type':  a['action_type'],
                'action_title': a.get('action_title', ''),
                'priority':     a['priority'],
                'evaluated_at': a['evaluated_at'],
                'outcome':      a['outcome'],
            }
            for a in recent
        ],
        'last_updated': store.get('last_updated'),
    }


def get_all_actions(status_filter: Optional[str] = None,
                    lottery_filter: Optional[str] = None,
                    limit: int = 100) -> list:
    """Return tracked actions with optional filtering."""
    store = _load_feedback_store()
    actions = store.get('actions', [])

    if status_filter:
        actions = [a for a in actions if a.get('status') == status_filter]
    if lottery_filter:
        actions = [a for a in actions if a.get('lottery_type') == lottery_filter]

    # Sort newest first
    actions = sorted(actions, key=lambda a: a.get('created_at') or '', reverse=True)
    return actions[:limit]


def get_rule_rankings() -> list:
    """Return rules sorted by rule_score descending."""
    store = _load_feedback_store()
    actions = store.get('actions', [])
    rule_stats = _aggregate_rule_stats(actions)

    ranked = sorted(rule_stats.values(), key=lambda r: r['rule_score'], reverse=True)
    return ranked
