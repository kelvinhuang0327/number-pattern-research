"""
Phase U — Strategy Promotion Engine

Safe, evidence-based strategy lifecycle management:

    WATCH → PROMOTABLE → SHADOW → PRODUCTION_CANDIDATE → PRODUCTION
                                                       ↘ (fallback)

DESIGN DECISIONS (deviations from spec, with rationale)
------------------------------------------------------
1. DEMOTION uses **raw** mcnemar_p, NOT Holm-adjusted.
   Reason: current VALIDATED strategies were validated under binary testing.
   Holm is a new additive layer. Retroactive demotion would immediately
   demote BIG_LOTTO's only VALIDATED strategy (adj_mc=0.278).

2. DEMOTION requires CONSECUTIVE failures (default N=20, not instant).
   Reason: a single bad window is noise, not signal.

3. Final promotion to PRODUCTION is gated by PHASE_U_AUTO_PROMOTE (default false).
   When false, engine generates PRODUCTION_CANDIDATE proposals that surface
   in actionable intelligence. User confirms via manual trigger.
   When true, engine auto-switches — use only in mature deployments.

4. Shadow tracking is observational (compares validation metrics over time),
   NOT parallel prediction. Spec says "DO NOT change prediction logic".

5. Cooldown uses "check count" not "draw count" since the engine runs
   periodically (via scheduler or API call), not per draw.

SAFETY
------
- Kill switch: PHASE_U_ENABLED (default false — must opt in)
- Max switch frequency: 1 per 100 checks
- Post-promotion freeze: 50 checks
- All decisions persisted to audit trail
- Previous production always kept as fallback
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths / flags ─────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
PROMOTIONS_FILE = os.path.join(DATA_DIR, 'strategy_promotions.json')


def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on', 'enabled')


ENABLED         = _env_flag('PHASE_U_ENABLED', False)           # kill switch
AUTO_PROMOTE    = _env_flag('PHASE_U_AUTO_PROMOTE', False)      # manual by default

# ── Thresholds ────────────────────────────────────────────────────────────────

# Promotion: WATCH → SHADOW
PROMO_ADJ_MCNEMAR   = 0.08     # Holm-adjusted
PROMO_MIN_TIER       = 'MEDIUM_CONFIDENCE'
PROMO_MIN_EDGE_1500  = 0.0     # must be positive
PROMO_MIN_SHARPE     = 0.0     # must be positive
PROMO_MIN_SAMPLES    = 300

# Stability: consecutive checks meeting promotion criteria
STABILITY_CHECKS     = 50      # N consecutive qualifying checks

# Shadow window: checks before shadow can be evaluated
SHADOW_WINDOW        = 50

# Shadow → PRODUCTION_CANDIDATE: shadow must be ≥ production
SHADOW_EDGE_TOLERANCE    = 0.90   # shadow edge ≥ 90% of production edge
SHADOW_SHARPE_TOLERANCE  = 0.90   # shadow sharpe ≥ 90% of production sharpe
SHADOW_DD_TOLERANCE      = 1.20   # shadow drawdown ≤ 120% of production drawdown

# Demotion: PRODUCTION → WATCH (uses RAW mcnemar, see design note 1)
DEMOTE_RAW_MCNEMAR   = 0.20    # raw mcnemar_p above this → degrading
DEMOTE_MIN_TIER      = 'LOW_CONFIDENCE'    # confidence below this → degrading
DEMOTE_CONSEC_CHECKS = 20      # must fail N consecutive checks to demote

# Safety
MAX_SWITCH_PER_CHECKS = 100    # at most 1 switch per N checks
POST_PROMOTE_FREEZE   = 50     # freeze after promotion

# ── Tier helpers ──────────────────────────────────────────────────────────────

_TIER_RANK = {
    'HIGH_CONFIDENCE': 3,
    'MEDIUM_CONFIDENCE': 2,
    'LOW_CONFIDENCE': 1,
    'UNRELIABLE': 0,
}

def _tier_rank(tier: str) -> int:
    return _TIER_RANK.get(tier, 0)


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_promotions() -> dict:
    """Load the promotion state file. Returns default structure if missing."""
    if os.path.exists(PROMOTIONS_FILE):
        try:
            with open(PROMOTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f'[PromotionEngine] Failed to load promotions: {e}')
    return {}


def _save_promotions(data: dict) -> None:
    """Atomic write of promotion state."""
    tmp = PROMOTIONS_FILE + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, PROMOTIONS_FILE)
    except Exception as e:
        logger.error(f'[PromotionEngine] Failed to save promotions: {e}')
        if os.path.exists(tmp):
            os.remove(tmp)


def _default_lottery_state() -> dict:
    return {
        'production':           None,     # strategy name
        'production_since':     None,
        'previous_production':  None,
        'shadow':               [],       # list of {name, entered_at, checks}
        'promotable':           {},       # {name: {consecutive_checks, first_seen}}
        'cooldown_until_check': 0,        # global check counter
        'total_checks':         0,
        'last_switch_check':    0,
        'demote_counter':       {},       # {name: consecutive_fail_checks}
        'history':              [],       # audit trail
    }


def _now_str() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Strategy state loading ────────────────────────────────────────────────────

def _load_strategy_states(lottery_type: str) -> dict:
    path = os.path.join(DATA_DIR, f'strategy_states_{lottery_type}.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


# ── Core engine ───────────────────────────────────────────────────────────────

def _check_promotion_eligible(state: dict, conf: dict) -> bool:
    """Check if a strategy meets promotion criteria (WATCH → SHADOW)."""
    vs = (state.get('validated_status') or '').upper()
    if vs != 'WATCH':
        return False

    # Phase T confidence
    tier = conf.get('confidence_tier', 'UNRELIABLE')
    if _tier_rank(tier) < _tier_rank(PROMO_MIN_TIER):
        return False

    adj_mc = conf.get('adjusted_mcnemar_p')
    if adj_mc is None or adj_mc >= PROMO_ADJ_MCNEMAR:
        return False

    # Validation metrics
    e1500 = state.get('edge_1500p')
    if e1500 is None or e1500 <= PROMO_MIN_EDGE_1500:
        return False

    sharpe = state.get('sharpe')
    if sharpe is None or sharpe <= PROMO_MIN_SHARPE:
        return False

    total_rec = state.get('total_records') or 0
    if total_rec < PROMO_MIN_SAMPLES:
        return False

    return True


def _check_demotion_criteria(state: dict, conf: dict) -> bool:
    """
    Check if production strategy is degrading.
    Uses RAW mcnemar_p (not Holm-adjusted) — see design note 1.
    """
    raw_mc = state.get('mcnemar_p')
    tier = conf.get('confidence_tier', 'UNRELIABLE')

    # Trigger: raw mcnemar too high OR confidence too low
    mc_fail = (raw_mc is not None and raw_mc > DEMOTE_RAW_MCNEMAR)
    tier_fail = (_tier_rank(tier) < _tier_rank(DEMOTE_MIN_TIER))

    # Also check edge: all three windows negative is very bad
    e150 = state.get('edge_150p') or 0
    e500 = state.get('edge_500p') or 0
    e1500 = state.get('edge_1500p') or 0
    edge_fail = (e150 < 0 and e500 < 0 and e1500 < 0)

    return mc_fail or tier_fail or edge_fail


def _compare_shadow_vs_production(shadow_state: dict, prod_state: dict) -> dict:
    """Compare shadow strategy metrics against production."""
    se = shadow_state.get('edge_1500p') or 0
    pe = prod_state.get('edge_1500p') or 0
    ss = shadow_state.get('sharpe') or 0
    ps = prod_state.get('sharpe') or 0
    sd = shadow_state.get('max_drawdown_rate') or 0
    pd = prod_state.get('max_drawdown_rate') or 0.001  # avoid div/0

    edge_ok = (se >= pe * SHADOW_EDGE_TOLERANCE) if pe > 0 else (se > 0)
    sharpe_ok = (ss >= ps * SHADOW_SHARPE_TOLERANCE) if ps > 0 else (ss > 0)
    dd_ok = (sd <= pd * SHADOW_DD_TOLERANCE) if pd > 0 else True

    return {
        'edge_ok':      edge_ok,
        'sharpe_ok':    sharpe_ok,
        'drawdown_ok':  dd_ok,
        'all_pass':     edge_ok and sharpe_ok and dd_ok,
        'shadow_edge':  se,
        'prod_edge':    pe,
        'shadow_sharpe': ss,
        'prod_sharpe':  ps,
        'shadow_dd':    sd,
        'prod_dd':      pd,
    }


def evaluate_lottery(lottery_type: str) -> dict:
    """
    Run one promotion evaluation cycle for a lottery.

    Returns a report dict with actions taken and current state.
    Call periodically (e.g., after each validation refresh).
    """
    if not ENABLED:
        return {'enabled': False, 'lottery_type': lottery_type,
                'message': 'Phase U disabled (PHASE_U_ENABLED=false)'}

    strategy_states = _load_strategy_states(lottery_type)
    if not strategy_states:
        return {'enabled': True, 'lottery_type': lottery_type,
                'message': 'No strategy states', 'actions': []}

    # Load Phase T confidence
    try:
        from engine.confidence_scorer import get_lottery_confidence
        confidence_table = get_lottery_confidence(lottery_type) or {}
    except Exception as e:
        logger.warning(f'[PromotionEngine] Phase T unavailable: {e}')
        confidence_table = {}

    # Load / init promotion state
    all_promos = _load_promotions()
    lt_state = all_promos.get(lottery_type)
    if not lt_state:
        lt_state = _default_lottery_state()

    lt_state['total_checks'] = lt_state.get('total_checks', 0) + 1
    check_num = lt_state['total_checks']
    now = _now_str()
    actions = []

    # ── Auto-detect current production (if not yet tracked) ──────────────
    if lt_state['production'] is None:
        # Inherit from existing VALIDATED best
        validated = [(n, s) for n, s in strategy_states.items()
                     if s.get('validated_status') == 'VALIDATED']
        if validated:
            best = max(validated, key=lambda x: float(x[1].get('composite_score') or 0))
            lt_state['production'] = best[0]
            lt_state['production_since'] = now
            actions.append({
                'type': 'INIT_PRODUCTION',
                'strategy': best[0],
                'reason': 'Inherited from existing VALIDATED best',
                'at': now,
            })

    prod_name = lt_state['production']
    prod_state = strategy_states.get(prod_name, {}) if prod_name else {}
    prod_conf = confidence_table.get(prod_name, {}) if prod_name else {}

    # ── Phase: Check demotion of current production ──────────────────────
    if prod_name and prod_state:
        demote_counters = lt_state.get('demote_counter', {})
        if _check_demotion_criteria(prod_state, prod_conf):
            count = demote_counters.get(prod_name, 0) + 1
            demote_counters[prod_name] = count
            if count >= DEMOTE_CONSEC_CHECKS:
                # Demote!
                prev = lt_state.get('previous_production')
                prev_state = strategy_states.get(prev, {}) if prev else {}
                fallback = prev if prev and prev_state.get('validated_status') in ('VALIDATED', 'WATCH') else None

                actions.append({
                    'type': 'DEMOTE',
                    'strategy': prod_name,
                    'fallback': fallback,
                    'reason': (f'Failed demotion criteria for {count} consecutive checks. '
                               f'raw_mc={prod_state.get("mcnemar_p")}, '
                               f'tier={prod_conf.get("confidence_tier")}'),
                    'at': now,
                    'check': check_num,
                })
                lt_state['previous_production'] = prod_name
                lt_state['production'] = fallback
                lt_state['production_since'] = now
                lt_state['last_switch_check'] = check_num
                lt_state['cooldown_until_check'] = check_num + POST_PROMOTE_FREEZE
                demote_counters[prod_name] = 0

                # Log to history
                lt_state['history'].append({
                    'event': 'DEMOTE',
                    'strategy': prod_name,
                    'fallback': fallback,
                    'check': check_num,
                    'at': now,
                    'metrics': {
                        'raw_mcnemar': prod_state.get('mcnemar_p'),
                        'confidence_tier': prod_conf.get('confidence_tier'),
                        'confidence_score': prod_conf.get('confidence_score'),
                        'edge_1500p': prod_state.get('edge_1500p'),
                    },
                })
            else:
                actions.append({
                    'type': 'DEMOTE_WARNING',
                    'strategy': prod_name,
                    'consecutive_fails': count,
                    'threshold': DEMOTE_CONSEC_CHECKS,
                    'reason': f'Demotion criteria met ({count}/{DEMOTE_CONSEC_CHECKS})',
                })
        else:
            # Reset counter if criteria no longer met
            demote_counters[prod_name] = 0
        lt_state['demote_counter'] = demote_counters

    # ── Phase: Check cooldown ────────────────────────────────────────────
    in_cooldown = check_num < lt_state.get('cooldown_until_check', 0)
    switch_too_recent = (
        check_num - lt_state.get('last_switch_check', 0) < MAX_SWITCH_PER_CHECKS
    ) if lt_state.get('last_switch_check', 0) > 0 else False

    # ── Phase: Identify promotable candidates ────────────────────────────
    promotable_tracker = lt_state.get('promotable', {})
    current_promotable = {}

    for name, state in strategy_states.items():
        if name == prod_name:
            continue  # production doesn't self-promote
        conf = confidence_table.get(name, {})
        if _check_promotion_eligible(state, conf):
            # Increment consecutive check counter
            prev_entry = promotable_tracker.get(name, {})
            checks = prev_entry.get('consecutive_checks', 0) + 1
            first_seen = prev_entry.get('first_seen') or now
            current_promotable[name] = {
                'consecutive_checks': checks,
                'first_seen': first_seen,
                'confidence_score': conf.get('confidence_score'),
                'confidence_tier': conf.get('confidence_tier'),
                'adjusted_mcnemar_p': conf.get('adjusted_mcnemar_p'),
                'edge_1500p': state.get('edge_1500p'),
                'sharpe': state.get('sharpe'),
            }
        # else: not eligible this check → counter resets (not persisted)

    lt_state['promotable'] = current_promotable

    # ── Phase: Promote to shadow pool ────────────────────────────────────
    existing_shadow_names = {s['name'] for s in lt_state.get('shadow', [])}

    for name, pinfo in current_promotable.items():
        if pinfo['consecutive_checks'] >= STABILITY_CHECKS and name not in existing_shadow_names:
            # Ready for shadow!
            lt_state['shadow'].append({
                'name': name,
                'entered_at': now,
                'entered_check': check_num,
                'checks_in_shadow': 0,
            })
            actions.append({
                'type': 'ENTER_SHADOW',
                'strategy': name,
                'reason': f'Met promotion criteria for {pinfo["consecutive_checks"]} consecutive checks',
                'at': now,
                'check': check_num,
                'metrics': {
                    'confidence_score': pinfo.get('confidence_score'),
                    'confidence_tier': pinfo.get('confidence_tier'),
                    'adjusted_mcnemar_p': pinfo.get('adjusted_mcnemar_p'),
                    'edge_1500p': pinfo.get('edge_1500p'),
                    'sharpe': pinfo.get('sharpe'),
                },
            })
            lt_state['history'].append({
                'event': 'ENTER_SHADOW',
                'strategy': name,
                'check': check_num,
                'at': now,
            })

    # ── Phase: Evaluate shadow strategies ────────────────────────────────
    updated_shadow = []
    for shadow_entry in lt_state.get('shadow', []):
        sname = shadow_entry['name']
        shadow_entry['checks_in_shadow'] = shadow_entry.get('checks_in_shadow', 0) + 1
        s_state = strategy_states.get(sname, {})
        s_conf = confidence_table.get(sname, {})

        # Drop shadow if no longer promotable
        if sname not in current_promotable:
            actions.append({
                'type': 'EXIT_SHADOW',
                'strategy': sname,
                'reason': 'No longer meets promotion criteria',
                'at': now,
                'check': check_num,
            })
            lt_state['history'].append({
                'event': 'EXIT_SHADOW',
                'strategy': sname,
                'reason': 'criteria_lost',
                'check': check_num,
                'at': now,
            })
            continue

        # Check if shadow window complete
        if shadow_entry['checks_in_shadow'] >= SHADOW_WINDOW:
            # Compare with production
            if prod_state:
                comparison = _compare_shadow_vs_production(s_state, prod_state)
            else:
                # No production → shadow wins by default
                comparison = {'all_pass': True, 'shadow_edge': s_state.get('edge_1500p'),
                              'prod_edge': 0, 'shadow_sharpe': s_state.get('sharpe'),
                              'prod_sharpe': 0, 'shadow_dd': 0, 'prod_dd': 0,
                              'edge_ok': True, 'sharpe_ok': True, 'drawdown_ok': True}

            if comparison['all_pass'] and not in_cooldown and not switch_too_recent:
                if AUTO_PROMOTE:
                    # Auto-promote: switch production
                    old_prod = lt_state['production']
                    lt_state['previous_production'] = old_prod
                    lt_state['production'] = sname
                    lt_state['production_since'] = now
                    lt_state['last_switch_check'] = check_num
                    lt_state['cooldown_until_check'] = check_num + POST_PROMOTE_FREEZE

                    actions.append({
                        'type': 'PROMOTE_TO_PRODUCTION',
                        'strategy': sname,
                        'previous': old_prod,
                        'reason': f'Shadow evaluation passed after {shadow_entry["checks_in_shadow"]} checks',
                        'comparison': comparison,
                        'at': now,
                        'check': check_num,
                    })
                    lt_state['history'].append({
                        'event': 'PROMOTE_TO_PRODUCTION',
                        'strategy': sname,
                        'previous': old_prod,
                        'check': check_num,
                        'at': now,
                        'comparison': comparison,
                    })
                    # Remove from shadow
                    continue
                else:
                    # Manual mode: create PRODUCTION_CANDIDATE proposal
                    actions.append({
                        'type': 'PRODUCTION_CANDIDATE',
                        'strategy': sname,
                        'current_production': prod_name,
                        'reason': f'Shadow passed evaluation. Manual confirmation required.',
                        'comparison': comparison,
                        'at': now,
                        'check': check_num,
                    })
            elif comparison['all_pass'] and (in_cooldown or switch_too_recent):
                actions.append({
                    'type': 'PROMOTION_BLOCKED',
                    'strategy': sname,
                    'reason': ('Cooldown active' if in_cooldown else
                               f'Switch too recent (min {MAX_SWITCH_PER_CHECKS} checks)'),
                    'at': now,
                })
            else:
                # Shadow failed comparison
                actions.append({
                    'type': 'SHADOW_UNDERPERFORM',
                    'strategy': sname,
                    'reason': 'Shadow metrics did not surpass production',
                    'comparison': comparison,
                    'at': now,
                    'check': check_num,
                })

        updated_shadow.append(shadow_entry)

    lt_state['shadow'] = updated_shadow

    # Trim history to last 200 entries
    if len(lt_state['history']) > 200:
        lt_state['history'] = lt_state['history'][-200:]

    # ── Persist ──────────────────────────────────────────────────────────
    all_promos[lottery_type] = lt_state
    _save_promotions(all_promos)

    # ── Build report ─────────────────────────────────────────────────────
    return {
        'enabled': True,
        'lottery_type': lottery_type,
        'check_number': check_num,
        'production': lt_state['production'],
        'production_since': lt_state['production_since'],
        'previous_production': lt_state['previous_production'],
        'shadow': [s['name'] for s in lt_state['shadow']],
        'shadow_details': lt_state['shadow'],
        'promotable': {
            name: {
                'consecutive_checks': info['consecutive_checks'],
                'stability_target': STABILITY_CHECKS,
                'progress_pct': round(100 * info['consecutive_checks'] / STABILITY_CHECKS, 1),
                'confidence_score': info.get('confidence_score'),
                'confidence_tier': info.get('confidence_tier'),
            }
            for name, info in current_promotable.items()
        },
        'in_cooldown': in_cooldown,
        'cooldown_remaining': max(0, lt_state.get('cooldown_until_check', 0) - check_num),
        'demote_warnings': {
            name: count for name, count in lt_state.get('demote_counter', {}).items()
            if count > 0
        },
        'actions': actions,
        'settings': {
            'auto_promote': AUTO_PROMOTE,
            'stability_checks': STABILITY_CHECKS,
            'shadow_window': SHADOW_WINDOW,
            'promo_adj_mcnemar': PROMO_ADJ_MCNEMAR,
            'demote_raw_mcnemar': DEMOTE_RAW_MCNEMAR,
            'demote_consec_checks': DEMOTE_CONSEC_CHECKS,
            'max_switch_per_checks': MAX_SWITCH_PER_CHECKS,
            'post_promote_freeze': POST_PROMOTE_FREEZE,
        },
    }


def evaluate_all() -> dict:
    """Run evaluation cycle for all lotteries."""
    return {lt: evaluate_lottery(lt) for lt in LOTTERY_TYPES}


# ── Manual promotion trigger ─────────────────────────────────────────────────

def confirm_promotion(lottery_type: str, strategy_name: str) -> dict:
    """
    Manually confirm a PRODUCTION_CANDIDATE promotion.
    Used when AUTO_PROMOTE is false.
    """
    if not ENABLED:
        return {'ok': False, 'error': 'Phase U disabled'}

    all_promos = _load_promotions()
    lt_state = all_promos.get(lottery_type)
    if not lt_state:
        return {'ok': False, 'error': f'No promotion state for {lottery_type}'}

    # Verify strategy is in shadow
    shadow_names = {s['name'] for s in lt_state.get('shadow', [])}
    if strategy_name not in shadow_names:
        return {'ok': False, 'error': f'{strategy_name} not in shadow pool'}

    now = _now_str()
    check_num = lt_state.get('total_checks', 0)

    old_prod = lt_state['production']
    lt_state['previous_production'] = old_prod
    lt_state['production'] = strategy_name
    lt_state['production_since'] = now
    lt_state['last_switch_check'] = check_num
    lt_state['cooldown_until_check'] = check_num + POST_PROMOTE_FREEZE

    # Remove from shadow
    lt_state['shadow'] = [s for s in lt_state['shadow'] if s['name'] != strategy_name]

    lt_state['history'].append({
        'event': 'MANUAL_PROMOTE',
        'strategy': strategy_name,
        'previous': old_prod,
        'check': check_num,
        'at': now,
    })

    all_promos[lottery_type] = lt_state
    _save_promotions(all_promos)

    return {
        'ok': True,
        'promoted': strategy_name,
        'previous': old_prod,
        'lottery_type': lottery_type,
    }


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_promotion_status(lottery_type: Optional[str] = None) -> dict:
    """Read-only: current promotion state without running evaluation."""
    all_promos = _load_promotions()
    if lottery_type:
        lt = all_promos.get(lottery_type, _default_lottery_state())
        return {lottery_type: _format_status(lt)}
    return {lt: _format_status(st) for lt, st in all_promos.items()}


def _format_status(lt_state: dict) -> dict:
    return {
        'production': lt_state.get('production'),
        'production_since': lt_state.get('production_since'),
        'previous_production': lt_state.get('previous_production'),
        'shadow': [s['name'] for s in lt_state.get('shadow', [])],
        'shadow_details': lt_state.get('shadow', []),
        'promotable': {
            name: {
                'consecutive_checks': info.get('consecutive_checks', 0),
                'progress_pct': round(100 * info.get('consecutive_checks', 0) / STABILITY_CHECKS, 1),
                'confidence_score': info.get('confidence_score'),
                'confidence_tier': info.get('confidence_tier'),
            }
            for name, info in lt_state.get('promotable', {}).items()
        },
        'total_checks': lt_state.get('total_checks', 0),
        'in_cooldown': lt_state.get('cooldown_until_check', 0) > lt_state.get('total_checks', 0),
        'demote_warnings': {
            n: c for n, c in lt_state.get('demote_counter', {}).items() if c > 0
        },
        'last_actions': lt_state.get('history', [])[-5:],
    }
