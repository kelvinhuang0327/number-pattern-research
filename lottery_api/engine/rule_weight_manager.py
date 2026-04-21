"""
Rule Weight Manager — Phase S (Feedback-to-Decision Closed Loop)

Consumes Phase R feedback data (rule effectiveness history) and produces a
weight map that Phase Q (actionable_intelligence) consults when ranking
insights.

PRINCIPLE:
  Phase R measures   → Phase S governs   → Phase Q executes

This is the FIRST module in the system that lets historical outcomes
actually change future decisions. All other feedback layers were read-only.

SAFETY:
- Feature flag: env var PHASE_S_RULE_GATING_ENABLED (default "true")
- Minimum sample threshold before any weight adjustment (SAMPLE_THRESHOLD)
- Weights are bounded and clamped; never produces negative weights
- All adjustments logged to data/rule_weights.json for audit
- When disabled, get_rule_weight_map() returns all-neutral weights → system
  behaves identically to pre-Phase-S

WEIGHT SEMANTICS:
  weight == 0.0   → DISABLED (rule hidden from user — requires hard-disable flag)
  0 < w < 1.0     → DOWNGRADED (rule still shown but deprioritized)
  weight == 1.0   → NEUTRAL (default, unchanged)
  weight >  1.0   → BOOSTED (rule surfaced with priority)

THRESHOLDS (from Phase S spec):
  rule_score < -0.3 AND n >= 5   → DOWNGRADE (weight = 0.3)
  rule_score > +0.3 AND n >= 5   → BOOST     (weight = 1.3)
  otherwise                      → NEUTRAL   (weight = 1.0)

  Additional:
  n < SAMPLE_THRESHOLD (5)       → LOW_CONFIDENCE flag (weight unchanged)
  score <= -0.7 AND n >= 10      → eligible for HARD_DISABLE when flag on
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths / Config ────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
WEIGHT_SNAPSHOT_PATH = os.path.join(DATA_DIR, 'rule_weights.json')

# ── Feature flags ─────────────────────────────────────────────────────────────

def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on', 'enabled')

# Master flag — when False, all rules get weight=1.0 (no Phase S effect)
GATING_ENABLED = _env_flag('PHASE_S_RULE_GATING_ENABLED', True)

# Secondary flag — allow hard-disable (weight=0) for severely negative rules.
# Default False: downgrade only, do not fully remove rules.
HARD_DISABLE_ENABLED = _env_flag('PHASE_S_HARD_DISABLE_ENABLED', False)

# ── Thresholds ────────────────────────────────────────────────────────────────

SAMPLE_THRESHOLD       = 5      # minimum completed evaluations to trust score
SCORE_DOWNGRADE_CUTOFF = -0.3   # score <= this & n >= 5 → DOWNGRADE
SCORE_BOOST_CUTOFF     = 0.3    # score >= this & n >= 5 → BOOST
SCORE_HARD_DISABLE     = -0.7   # score <= this & n >= 10 & HARD_DISABLE_ENABLED → weight 0

WEIGHT_DOWNGRADE = 0.3
WEIGHT_NEUTRAL   = 1.0
WEIGHT_BOOST     = 1.3
WEIGHT_DISABLED  = 0.0

# Statuses returned in the weight map
STATUS_BOOSTED     = 'BOOSTED'
STATUS_NEUTRAL     = 'NEUTRAL'
STATUS_DOWNGRADED  = 'DOWNGRADED'
STATUS_DISABLED    = 'DISABLED'
STATUS_LOW_CONF    = 'LOW_CONFIDENCE'


# ── Core ──────────────────────────────────────────────────────────────────────

def _classify(rule_score: float, samples: int) -> tuple:
    """
    Given a rule's score and sample count, decide (weight, status, reason_zh).
    Returns a 3-tuple.
    """
    if samples < SAMPLE_THRESHOLD:
        return (
            WEIGHT_NEUTRAL,
            STATUS_LOW_CONF,
            f'樣本數 {samples} < {SAMPLE_THRESHOLD}，尚無足夠數據調整權重（維持中性）'
        )

    # Sample threshold met — apply gating
    if rule_score <= SCORE_HARD_DISABLE and samples >= 10 and HARD_DISABLE_ENABLED:
        return (
            WEIGHT_DISABLED,
            STATUS_DISABLED,
            f'歷史成效極差（score={rule_score:+.2f}，n={samples}），已暫停此規則'
        )

    if rule_score <= SCORE_DOWNGRADE_CUTOFF:
        return (
            WEIGHT_DOWNGRADE,
            STATUS_DOWNGRADED,
            f'歷史成效偏負（score={rule_score:+.2f}，n={samples}），已降權 {WEIGHT_DOWNGRADE}x'
        )

    if rule_score >= SCORE_BOOST_CUTOFF:
        return (
            WEIGHT_BOOST,
            STATUS_BOOSTED,
            f'歷史成效優良（score={rule_score:+.2f}，n={samples}），已加權 {WEIGHT_BOOST}x'
        )

    return (
        WEIGHT_NEUTRAL,
        STATUS_NEUTRAL,
        f'歷史成效中性（score={rule_score:+.2f}，n={samples}），維持預設權重'
    )


def _neutral_entry(reason: str = '無歷史反饋資料，使用預設權重') -> dict:
    return {
        'weight':       WEIGHT_NEUTRAL,
        'status':       STATUS_NEUTRAL,
        'reason':       reason,
        'rule_score':   None,
        'samples':      0,
        'source':       'default',
    }


def _build_map_from_rule_stats(rule_stats: dict) -> dict:
    """
    rule_stats is the dict returned by action_feedback._aggregate_rule_stats:
      { 'R01_DEGRADING': {'total': N, 'rule_score': x, ...}, ... }
    """
    wmap = {}
    for code, stat in (rule_stats or {}).items():
        score   = float(stat.get('rule_score', 0.0) or 0.0)
        samples = int(stat.get('total', 0) or 0)
        weight, status, reason = _classify(score, samples)
        wmap[code] = {
            'weight':       weight,
            'status':       status,
            'reason':       reason,
            'rule_score':   score,
            'samples':      samples,
            'source':       'phase_r_feedback',
        }
    return wmap


def _save_snapshot(snapshot: dict) -> None:
    """Atomic JSON write for audit trail."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix='.rule_weights.', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            os.replace(tmp, WEIGHT_SNAPSHOT_PATH)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    except Exception as e:
        logger.warning(f'[RuleWeight] Failed to persist snapshot: {e}')


# ── Public API ────────────────────────────────────────────────────────────────

def get_rule_weight_map(persist: bool = True) -> dict:
    """
    Build the current rule weight map from Phase R feedback data.

    Returns a dict keyed by rule_code (e.g. 'R01_DEGRADING'):
        {
          'R01_DEGRADING': {
            'weight': 0.3,
            'status': 'DOWNGRADED',
            'reason': '歷史成效偏負（score=-0.50，n=6），已降權 0.3x',
            'rule_score': -0.5,
            'samples': 6,
            'source': 'phase_r_feedback'
          },
          ...
        }

    When GATING_ENABLED is False, ALL rules return NEUTRAL entries.
    When no feedback data exists, returns empty dict (callers treat missing
    keys as neutral).
    """
    if not GATING_ENABLED:
        logger.debug('[RuleWeight] Phase S gating is DISABLED via env flag')
        return {}

    # Pull rule stats from Phase R engine
    try:
        from engine.action_feedback import get_rule_rankings
        rankings = get_rule_rankings() or []
    except Exception as e:
        logger.warning(f'[RuleWeight] Could not load Phase R rankings: {e}')
        return {}

    # get_rule_rankings returns a list of rule stat dicts already shaped like
    # _aggregate_rule_stats values.
    rule_stats = {r.get('action_type'): r for r in rankings if r.get('action_type')}

    wmap = _build_map_from_rule_stats(rule_stats)

    if persist:
        snapshot = {
            'generated_at':  datetime.now(timezone.utc).isoformat(),
            'gating_enabled': GATING_ENABLED,
            'hard_disable_enabled': HARD_DISABLE_ENABLED,
            'sample_threshold': SAMPLE_THRESHOLD,
            'thresholds': {
                'downgrade_cutoff':   SCORE_DOWNGRADE_CUTOFF,
                'boost_cutoff':       SCORE_BOOST_CUTOFF,
                'hard_disable_cutoff': SCORE_HARD_DISABLE,
            },
            'weights': wmap,
        }
        _save_snapshot(snapshot)

    return wmap


def get_weight_for_rule(rule_code: str, weight_map: Optional[dict] = None) -> dict:
    """
    Look up a single rule's weight entry. Returns a NEUTRAL default entry if the
    rule has no feedback history yet or if gating is disabled.
    """
    if not GATING_ENABLED:
        return _neutral_entry(reason='Phase S gating 已停用（環境變數），維持預設權重')
    wmap = weight_map if weight_map is not None else get_rule_weight_map(persist=False)
    entry = wmap.get(rule_code)
    if entry is None:
        return _neutral_entry()
    return entry


def summarize_weight_map(weight_map: dict) -> dict:
    """
    Produce a human-readable summary of the current weight map for UI/debug.
    """
    if not weight_map:
        return {
            'total_rules': 0,
            'boosted':     [],
            'downgraded':  [],
            'disabled':    [],
            'low_conf':    [],
            'neutral':     [],
            'gating_enabled': GATING_ENABLED,
        }

    boosted    = []
    downgraded = []
    disabled   = []
    low_conf   = []
    neutral    = []
    for code, entry in weight_map.items():
        tag = {
            'code':       code,
            'weight':     entry['weight'],
            'rule_score': entry.get('rule_score'),
            'samples':    entry.get('samples'),
            'reason':     entry.get('reason'),
        }
        s = entry['status']
        if   s == STATUS_BOOSTED:    boosted.append(tag)
        elif s == STATUS_DOWNGRADED: downgraded.append(tag)
        elif s == STATUS_DISABLED:   disabled.append(tag)
        elif s == STATUS_LOW_CONF:   low_conf.append(tag)
        else:                        neutral.append(tag)

    return {
        'total_rules':    len(weight_map),
        'boosted':        boosted,
        'downgraded':     downgraded,
        'disabled':       disabled,
        'low_conf':       low_conf,
        'neutral':        neutral,
        'gating_enabled': GATING_ENABLED,
        'hard_disable_enabled': HARD_DISABLE_ENABLED,
    }
