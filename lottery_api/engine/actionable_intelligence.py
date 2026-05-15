"""
Actionable Intelligence Engine — Phase Q

Transforms explainability data into concrete, operator-level decision guidance.
Reads from strategy_states_*.json and cached explanation data.

CONSTRAINTS:
- Does NOT modify prediction results
- Does NOT auto-execute any action
- Only generates recommendations based on real data
- Every insight is traceable to a specific data field
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

STRATEGY_STATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

# Thresholds (all traceable to spec / validation pipeline)
EDGE_DEGRADATION_THRESHOLD = 0.005   # edge difference considered significant
SHARPE_WEAK_THRESHOLD = 0.05          # sharpe < this → weak performance
PERM_P_WATCH_ZONE = 0.15              # above 0.05 but below this → near-threshold
RESEARCH_WEAK_THRESHOLD = 0.05        # abs(research_score) < this → weak signal
MAX_DRAWDOWN_ALERT = 0.05             # drawdown rate > this → risk alert


# ── Data Loaders ─────────────────────────────────────────────────────────────

def _load_strategy_states(lottery_type: str) -> dict:
    """Load strategy states for a lottery type. Returns {} on error."""
    path = os.path.join(STRATEGY_STATES_DIR, f'strategy_states_{lottery_type}.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'[ActionableIntel] Cannot load strategy_states for {lottery_type}: {e}')
        return {}


def _load_latest_explanation(lottery_type: str) -> Optional[dict]:
    """
    Load latest explanation for a lottery type.
    Primary: DB (get_latest_explanation).
    Fallback: live computation via coordinator_predict + get_last_explanation.
    Returns None on error.
    """
    # Try DB first
    try:
        from engine.explainability import get_latest_explanation
        result = get_latest_explanation(lottery_type)
        if result:
            if isinstance(result, dict) and 'explanation' in result:
                return result['explanation']
            return result
    except Exception as e:
        logger.warning(f'[ActionableIntel] DB explanation lookup failed for {lottery_type}: {e}')

    # Fallback: live computation (no side effects — only reads explanation state)
    try:
        from database import db_manager
        from common import normalize_lottery_type
        from engine.strategy_coordinator import coordinator_predict, get_last_explanation

        lt = normalize_lottery_type(lottery_type)
        all_draws = db_manager.get_all_draws(lt)
        if not all_draws:
            return None
        history = sorted(all_draws, key=lambda x: (x.get('date', ''), x.get('draw', '')))
        coordinator_predict(lt, history, n_bets=3, mode='direct')
        exp = get_last_explanation()
        return exp
    except Exception as e:
        logger.warning(f'[ActionableIntel] Live explanation fallback failed for {lottery_type}: {e}')
        return None


# ── Phase 1: Signal Analysis ─────────────────────────────────────────────────

def _analyze_signals(strategy_states: dict, explanation: Optional[dict]) -> dict:
    """
    Compute signal analysis for a lottery.
    Returns structured signal summary.
    """
    if not strategy_states:
        return {'error': 'no_strategy_states', 'strategies': []}

    strategies = list(strategy_states.values())
    validated = [s for s in strategies if s.get('validated_status') == 'VALIDATED']
    watch = [s for s in strategies if s.get('validated_status') == 'WATCH']
    rejected = [s for s in strategies if s.get('validated_status') == 'REJECTED']

    # Best strategy = highest composite_score among VALIDATED, then WATCH
    best = None
    for pool in [validated, watch, strategies]:
        if pool:
            best = max(pool, key=lambda s: s.get('composite_score') or 0)
            break

    # Validation strength
    has_validated = len(validated) > 0
    all_watch = len(validated) == 0 and len(watch) > 0 and len(rejected) == 0
    any_rejected = len(rejected) > 0

    # Stability analysis (for best strategy)
    stability = {}
    if best:
        e150 = best.get('edge_150p') or 0
        e500 = best.get('edge_500p') or 0
        e1500 = best.get('edge_1500p') or 0
        stability['edge_150p'] = e150
        stability['edge_500p'] = e500
        stability['edge_1500p'] = e1500
        stability['sharpe'] = best.get('sharpe') or 0
        stability['max_drawdown_rate'] = best.get('max_drawdown_rate') or 0
        stability['perm_p'] = best.get('perm_p')
        stability['mcnemar_p'] = best.get('mcnemar_p')
        # Degradation: is edge decreasing across windows?
        stability['edge_degrading'] = (e1500 < e500 < e150) and (e150 - e1500) > EDGE_DEGRADATION_THRESHOLD
        stability['sharpe_weak'] = stability['sharpe'] < SHARPE_WEAK_THRESHOLD

    # Learning & quality signals (from explanation)
    learning_signal = {}
    quality_signal = {}
    if explanation:
        lr = explanation.get('learning', {})
        qr = explanation.get('quality', {})
        learning_signal['gate'] = lr.get('gate', 'UNKNOWN')
        learning_signal['research_score'] = lr.get('research_score', 0)
        learning_signal['ranking_changed'] = lr.get('ranking_changed', False)
        learning_signal['effective'] = (
            lr.get('gate') in ('ENABLED', 'WEAK') and lr.get('ranking_changed', False)
        )
        learning_signal['weak_signal'] = abs(lr.get('research_score') or 0) < RESEARCH_WEAK_THRESHOLD

        quality_signal['label'] = qr.get('quality_label', '')
        quality_signal['ranking_changed'] = qr.get('ranking_changed', False)
        quality_signal['total_abs_delta'] = qr.get('total_abs_delta', 0)
        quality_signal['dominant'] = qr.get('ranking_changed', False)

    return {
        'total': len(strategies),
        'validated_count': len(validated),
        'watch_count': len(watch),
        'rejected_count': len(rejected),
        'has_validated': has_validated,
        'all_watch': all_watch,
        'any_rejected': any_rejected,
        'best_strategy': best.get('name', '') if best else '',
        'best_validated_status': best.get('validated_status', '') if best else '',
        'stability': stability,
        'learning': learning_signal,
        'quality': quality_signal,
        'strategies': strategies,
    }


# ── Phase 2: Rule-Based Insight Engine ───────────────────────────────────────

def _apply_rules(signals: dict) -> list:
    """
    Apply all insight rules. Returns list of (priority, code, message, data_source).
    All insights trace back to specific signal fields.
    """
    insights = []
    s = signals
    stab = s.get('stability', {})
    lr = s.get('learning', {})
    qr = s.get('quality', {})

    # ── RULE 1: VALIDATED but degrading ──────────────────────────────────────
    if s.get('has_validated') and stab.get('edge_degrading'):
        insights.append({
            'code': 'R01_DEGRADING',
            'priority': 'P1',
            'title': '策略可能進入衰退期',
            'message': '策略可能進入衰退期，建議觀察或降權',
            'detail': '已驗證策略的 Edge 呈現跨窗口遞減趨勢（150>500>1500），績效持續下滑。',
            'data_source': f'edge_150p={stab.get("edge_150p",0):.4f}, edge_500p={stab.get("edge_500p",0):.4f}, edge_1500p={stab.get("edge_1500p",0):.4f}',
            'action': _make_action(
                priority='P1',
                title='觀察策略衰退趨勢',
                reason='三窗口 Edge 遞減，長期績效可能下降',
                expected_effect='避免持續使用績效衰退策略導致損失',
                risk='過度反應可能錯失短期回歸',
                condition_to_stop='edge_1500p 恢復正增長或連續 50 期無進一步下降'
            )
        })

    # ── RULE 2: WATCH but near threshold ─────────────────────────────────────
    if not s.get('has_validated') or s.get('all_watch'):
        for st in s.get('strategies', []):
            if st.get('validated_status') == 'WATCH':
                e1500 = st.get('edge_1500p') or 0
                perm_p = st.get('perm_p')
                if e1500 > 0 and perm_p is not None and perm_p < PERM_P_WATCH_ZONE:
                    insights.append({
                        'code': 'R02_NEAR_THRESHOLD',
                        'priority': 'P2',
                        'title': '策略接近驗證門檻',
                        'message': '策略接近驗證門檻，建議持續觀察或擴充樣本',
                        'detail': f'{st.get("name")} 的 Edge 為正且 perm_p={perm_p:.3f}，接近統計顯著門檻。',
                        'data_source': f'strategy={st.get("name")}, edge_1500p={e1500:.4f}, perm_p={perm_p:.3f}',
                        'action': _make_action(
                            priority='P2',
                            title='持續監控近門檻策略',
                            reason=f'{st.get("name")} perm_p 尚未達 0.05 但 Edge 為正',
                            expected_effect='若樣本增加後通過顯著性檢定可晉升為 VALIDATED',
                            risk='可能只是偶然正值，需更多數據確認',
                            condition_to_stop='perm_p < 0.05 且 mcnemar_p < 0.05（可晉升）或 edge_1500p < 0'
                        )
                    })
                    break  # one insight per rule

    # ── RULE 3: Learning ineffective (enabled but no ranking change) ──────────
    if lr.get('gate') in ('ENABLED', 'WEAK') and not lr.get('ranking_changed', True):
        insights.append({
            'code': 'R03_LEARNING_INEFFECTIVE',
            'priority': 'P2',
            'title': 'Learning 未產生實質影響',
            'message': 'Learning 未對排序產生影響，可能訊號不足或同質性過高',
            'detail': f'Learning gate={lr.get("gate")}，但 ranking_changed=False。各策略評分差異不足以被 learning bonus 改變排名。',
            'data_source': f'learning.gate={lr.get("gate")}, learning.ranking_changed={lr.get("ranking_changed")}, research_score={lr.get("research_score",0):.4f}',
            'action': _make_action(
                priority='P2',
                title='觀察 Learning 系統效益',
                reason='Learning bonus 已套用但未改變最終排名',
                expected_effect='了解 learning 影響力以決定是否調整假說或擴大樣本',
                risk='無直接損失風險，為信息類觀察',
                condition_to_stop='research_score 顯著提升後 ranking_changed=True'
            )
        })

    # ── RULE 4: Quality as dominant decision factor ───────────────────────────
    if qr.get('dominant'):
        insights.append({
            'code': 'R04_QUALITY_DOMINANT',
            'priority': 'P2',
            'title': 'Winning Quality 主導決策',
            'message': 'Winning Quality 為主要決策因子（降低分獎風險）',
            'detail': f'quality.ranking_changed=True，代表最終押注組合由 quality 調整而非純策略分數決定。',
            'data_source': f'quality.ranking_changed={qr.get("ranking_changed")}, total_abs_delta={qr.get("total_abs_delta",0):.4f}',
            'action': _make_action(
                priority='P2',
                title='確認 Quality 調整方向合理',
                reason='Quality 調整改變了原始排名，需確保方向符合預期',
                expected_effect='避免高熱門組合帶來的分獎損失',
                risk='若熱門度估算偏差，可能錯過合理組合',
                condition_to_stop='持續性監控，非需停止條件'
            )
        })

    # ── RULE 5: Weak research signal ─────────────────────────────────────────
    if lr.get('weak_signal') and lr.get('gate') != 'DISABLED':
        insights.append({
            'code': 'R05_WEAK_RESEARCH',
            'priority': 'P2',
            'title': '研究訊號弱',
            'message': '研究訊號弱，learning 僅具保護作用',
            'detail': f'research_score={lr.get("research_score",0):.4f}，接近零值，學習系統暫無強方向性訊號。',
            'data_source': f'learning.research_score={lr.get("research_score",0):.4f}, threshold={RESEARCH_WEAK_THRESHOLD}',
            'action': _make_action(
                priority='P2',
                title='擴充研究假說覆蓋率',
                reason='research_score 弱表示假說尚未形成共識方向',
                expected_effect='更多有效假說可強化 learning bonus 方向性',
                risk='強制擴充可能引入雜訊假說',
                condition_to_stop='abs(research_score) > 0.05 且 ranking_changed=True'
            )
        })

    # ── RULE 6: No VALIDATED strategy ────────────────────────────────────────
    if not s.get('has_validated'):
        insights.append({
            'code': 'R06_NO_VALIDATED',
            'priority': 'P0',
            'title': '目前無完整驗證策略',
            'message': '目前無完整驗證策略，需保守使用',
            'detail': f'所有 {s.get("total",0)} 個策略均為 WATCH 狀態，尚未通過三窗口完整驗證。',
            'data_source': f'validated_count=0, watch_count={s.get("watch_count",0)}, total={s.get("total",0)}',
            'action': _make_action(
                priority='P0',
                title='切換至保守模式',
                reason='無 VALIDATED 策略代表信號強度不足',
                expected_effect='減少在低確信策略上的過度依賴',
                risk='可能錯過 WATCH 策略中的短期機會',
                condition_to_stop='至少 1 個策略達到 VALIDATED 狀態'
            )
        })

    # ── RULE 7: All strategies in WATCH ──────────────────────────────────────
    if s.get('all_watch') and not any(ins['code'] == 'R06_NO_VALIDATED' for ins in insights):
        insights.append({
            'code': 'R07_ALL_WATCH',
            'priority': 'P1',
            'title': '所有策略仍在觀察期',
            'message': '所有策略仍在觀察期，建議謹慎投注',
            'detail': f'{s.get("total",0)} 個策略全為 WATCH，整體驗證強度較低。',
            'data_source': f'all strategies: watch_count={s.get("watch_count",0)}',
            'action': _make_action(
                priority='P1',
                title='謹慎使用觀察期策略',
                reason='WATCH 策略尚未通過完整三窗口驗證',
                expected_effect='降低在未驗證策略上的曝險',
                risk='WATCH 中部分策略可能實際表現良好',
                condition_to_stop='任一策略晉升至 VALIDATED 狀態'
            )
        })

    # ── RULE 8: Sharpe weak ───────────────────────────────────────────────────
    if stab.get('sharpe_weak') and stab.get('sharpe', 1) >= 0:
        insights.append({
            'code': 'R08_LOW_SHARPE',
            'priority': 'P2',
            'title': '風險調整後績效偏低',
            'message': '策略 Sharpe 偏低，風險調整後報酬空間有限',
            'detail': f'sharpe={stab.get("sharpe",0):.4f}，小於 {SHARPE_WEAK_THRESHOLD}，波動性相對於超越率過高。',
            'data_source': f'sharpe={stab.get("sharpe",0):.4f}, threshold={SHARPE_WEAK_THRESHOLD}',
            'action': _make_action(
                priority='P2',
                title='監控 Sharpe 趨勢',
                reason='低 Sharpe 代表回報波動性高，長期穩定性存疑',
                expected_effect='提早識別策略不穩定信號',
                risk='Sharpe 短期波動正常，不宜過度反應',
                condition_to_stop='Sharpe > 0.05 持續 100 期'
            )
        })

    # ── RULE 9: High drawdown ─────────────────────────────────────────────────
    if stab.get('max_drawdown_rate', 0) > MAX_DRAWDOWN_ALERT:
        insights.append({
            'code': 'R09_HIGH_DRAWDOWN',
            'priority': 'P1',
            'title': '近期回撤超過警戒線',
            'message': '近期回撤較大，風險偏高，建議降低依賴',
            'detail': f'max_drawdown_rate={stab.get("max_drawdown_rate",0):.4f}，超過 {MAX_DRAWDOWN_ALERT} 警戒閾值。',
            'data_source': f'max_drawdown_rate={stab.get("max_drawdown_rate",0):.4f}, threshold={MAX_DRAWDOWN_ALERT}',
            'action': _make_action(
                priority='P1',
                title='降低高回撤策略依賴',
                reason='回撤超過警戒閾值，需控制曝險',
                expected_effect='限制單一策略最大損失',
                risk='若回撤只是短期偶發，可能不必要地限制了績效',
                condition_to_stop='max_drawdown_rate < 0.03 持續 50 期'
            )
        })

    # ── RULE 10: Learning DISABLED ────────────────────────────────────────────
    if lr.get('gate') == 'DISABLED':
        insights.append({
            'code': 'R10_LEARNING_DISABLED',
            'priority': 'P1',
            'title': 'Learning 系統停用中',
            'message': 'Learning 系統停用中，缺少即時修正能力',
            'detail': 'learning.gate=DISABLED，自動學習系統未啟動，策略評分未受假說研究影響。',
            'data_source': 'learning.gate=DISABLED',
            'action': _make_action(
                priority='P1',
                title='檢查 Learning 停用原因',
                reason='Learning 停用表示系統缺少自我修正能力',
                expected_effect='重新啟用後可即時整合最新研究成果',
                risk='若停用原因為資料品質問題，強制啟用可能引入錯誤',
                condition_to_stop='調查並解決停用原因後重新啟用'
            )
        })

    # ── RULE 11: Promotable candidate — Phase T confidence layer ──────────────
    # Fires when a WATCH strategy achieves MEDIUM+ confidence tier AND adjusted
    # mcnemar_p < 0.08 (Holm–Bonferroni). Suggests shadow-test activation.
    promotable = s.get('promotable_candidates') or []
    for cand in promotable[:2]:  # show at most top 2 to avoid noise
        insights.append({
            'code': 'R11_PROMOTABLE',
            'priority': 'P2',
            'title': '近門檻候選策略',
            'message': f'{cand.get("name")} 接近統計顯著，建議啟用 shadow 測試',
            'detail': (f'{cand.get("name")} 為 WATCH 狀態，但調整後 p={cand.get("adjusted_mcnemar_p"):.3f} '
                       f'< 0.08，confidence_score={cand.get("confidence_score"):.3f} '
                       f'({cand.get("confidence_tier")})。符合 Phase T 升級候選條件。'),
            'data_source': (f'strategy={cand.get("name")}, '
                            f'adjusted_mcnemar_p={cand.get("adjusted_mcnemar_p"):.4f}, '
                            f'confidence_tier={cand.get("confidence_tier")}'),
            'action': _make_action(
                priority='P2',
                title='啟用 shadow 併行測試',
                reason=f'{cand.get("name")} 調整後 p-value 接近 0.05，信心等級為 '
                       f'{cand.get("confidence_tier")}',
                expected_effect='若 shadow 表現穩定且 mcnemar 過關，可晉升為 production 候選',
                risk='WATCH 階段策略可能只是短期回歸，shadow 需跑滿驗證週期',
                condition_to_stop='adjusted_mcnemar_p ≥ 0.10 持續 100 期，或 edge_1500p 轉負'
            )
        })

    # ── RULES 12-14: Phase U — Strategy Promotion Engine ─────────────────────
    promo = s.get('promotion') or {}

    # RULE 12: Shadow strategies active
    shadow_list = promo.get('shadow') or []
    shadow_details = promo.get('shadow_details') or []
    for sd in shadow_details[:2]:
        checks = sd.get('checks_in_shadow', 0)
        insights.append({
            'code': 'R12_SHADOW_ACTIVE',
            'priority': 'P3',
            'title': 'Shadow 策略運行中',
            'message': f'{sd.get("name")} 正在 shadow 併跑中（已 {checks} 次檢查）',
            'detail': (f'{sd.get("name")} 於 {sd.get("entered_at", "?")} 進入 shadow pool，'
                       f'已完成 {checks} 次觀察期檢查。達到 50 次後將進行正式對比評估。'),
            'data_source': f'promotion.shadow_details, checks={checks}',
            'action': _make_action(
                priority='P3',
                title='持續觀察 shadow 策略',
                reason=f'{sd.get("name")} 在 shadow pool 中累積表現數據',
                expected_effect='完成觀察期後可自動進入升級評估',
                risk='shadow 策略可能在觀察期間失去統計顯著性',
                condition_to_stop='策略不再滿足 promotable 條件時自動退出 shadow'
            )
        })

    # RULE 13: Promotable strategies tracking progress
    promo_tracking = promo.get('promotable') or {}
    for pname, pinfo in sorted(promo_tracking.items(),
                                key=lambda x: -x[1].get('progress_pct', 0))[:2]:
        pct = pinfo.get('progress_pct', 0)
        checks = pinfo.get('consecutive_checks', 0)
        insights.append({
            'code': 'R13_PROMO_TRACKING',
            'priority': 'P3',
            'title': '策略升級追蹤',
            'message': f'{pname} 已連續 {checks} 次達成升級條件（{pct:.0f}%）',
            'detail': (f'{pname} 需連續 50 次通過升級條件才能進入 shadow pool。'
                       f'目前進度 {pct:.0f}%，信心等級 {pinfo.get("confidence_tier", "?")}。'),
            'data_source': f'promotion.promotable.{pname}, consecutive={checks}',
            'action': _make_action(
                priority='P3',
                title='持續觀察升級進度',
                reason=f'{pname} 正在穩定性驗證中',
                expected_effect='達標後自動進入 shadow 併跑',
                risk='升級條件中斷會重置計數',
                condition_to_stop='不滿足條件時計數器自動歸零'
            )
        })

    # RULE 14: Demotion warning
    demote_warnings = promo.get('demote_warnings') or {}
    for dname, dcount in demote_warnings.items():
        if dcount >= 5:  # only surface if meaningful
            insights.append({
                'code': 'R14_DEMOTE_WARNING',
                'priority': 'P1',
                'title': 'Production 策略降級警告',
                'message': f'{dname} 已連續 {dcount}/20 次未通過品質檢查',
                'detail': (f'Production 策略 {dname} 連續 {dcount} 次觸發降級條件。'
                           f'達到 20 次時將自動降級至 WATCH 並回退至前一 production 策略。'),
                'data_source': f'promotion.demote_counter.{dname}={dcount}',
                'action': _make_action(
                    priority='P1',
                    title='檢查 production 策略表現',
                    reason=f'{dname} 品質指標持續惡化',
                    expected_effect='若問題持續，系統將自動降級並回退',
                    risk='若無替代策略，降級後可能無 production 策略可用',
                    condition_to_stop='指標恢復後降級計數器自動歸零'
                )
            })

    return insights


def _make_action(priority: str, title: str, reason: str,
                 expected_effect: str, risk: str, condition_to_stop: str) -> dict:
    return {
        'priority': priority,
        'title': title,
        'reason': reason,
        'expected_effect': expected_effect,
        'risk': risk,
        'condition_to_stop': condition_to_stop,
    }


# ── Phase 4: System Health ────────────────────────────────────────────────────

def _compute_health(signals: dict, insights: list) -> str:
    """
    GOOD  = at least 1 VALIDATED + no P0 + no P1 degradation
    WATCH = WATCH strategies or P1 issues present
    RISK  = P0 issue present or no validated strategies
    """
    priorities = {ins['priority'] for ins in insights}
    if 'P0' in priorities:
        return 'RISK'
    if not signals.get('has_validated'):
        return 'RISK'
    if 'P1' in priorities:
        return 'WATCH'
    return 'GOOD'


_HEALTH_LABEL = {
    'GOOD': '✅ 穩定',
    'WATCH': '⚠️ 觀察中',
    'RISK': '🔴 高風險',
}

_HEALTH_COLOR = {
    'GOOD': '#00c864',
    'WATCH': '#ffb400',
    'RISK': '#e74c3c',
}


# ── Phase 4: Per-lottery Summary ──────────────────────────────────────────────

def _build_lottery_summary(lottery_type: str) -> dict:
    """Build complete actionable summary for one lottery type."""
    states = _load_strategy_states(lottery_type)
    explanation = _load_latest_explanation(lottery_type)

    # Normalize explanation: may be wrapped or direct
    if explanation and isinstance(explanation, dict):
        if 'explanation' in explanation:
            explanation = explanation['explanation']

    signals = _analyze_signals(states, explanation)

    if signals.get('error'):
        return {
            'lottery_type': lottery_type,
            'health': 'RISK',
            'health_label': '🔴 無數據',
            'health_color': '#e74c3c',
            'insights': [],
            'top_actions': [],
            'signals': {},
            'error': signals['error'],
        }

    # ── Phase T: Attach confidence layer (additive, no breaking change) ──────
    confidence_table = {}
    best_confidence = None
    promotable_candidates = []
    try:
        from engine.confidence_scorer import get_lottery_confidence
        confidence_table = get_lottery_confidence(lottery_type) or {}
        # Best-strategy tier for signals header
        best_name = signals.get('best_strategy')
        if best_name and best_name in confidence_table:
            best_confidence = confidence_table[best_name]
        # Promotable candidates sorted by confidence_score desc
        promotable_candidates = sorted(
            [v for v in confidence_table.values() if v.get('promotable')],
            key=lambda r: -float(r.get('confidence_score') or 0.0),
        )
    except Exception as _e:
        logger.warning(f'[ActionableIntel] Phase T confidence unavailable: {_e}')

    signals['promotable_candidates'] = promotable_candidates

    # ── Phase U: Attach promotion engine state (additive) ────────────────────
    promotion_state = {}
    try:
        from engine.promotion_engine import get_promotion_status, ENABLED as PHASE_U_ENABLED
        if PHASE_U_ENABLED:
            promo_all = get_promotion_status(lottery_type)
            promotion_state = promo_all.get(lottery_type, {})
    except Exception as _e:
        logger.warning(f'[ActionableIntel] Phase U promotion unavailable: {_e}')
    signals['promotion'] = promotion_state

    insights = _apply_rules(signals)

    # ── Phase S: Apply rule weight gating ────────────────────────────────────
    # Feedback-to-Decision closed loop: historical effectiveness adjusts rule
    # weight. Disabled rules are filtered out here; downgraded rules are kept
    # but deprioritized and carry an explainability note.
    try:
        from engine.rule_weight_manager import (
            get_rule_weight_map,
            STATUS_DISABLED,
            STATUS_DOWNGRADED,
            STATUS_BOOSTED,
            STATUS_LOW_CONF,
            WEIGHT_NEUTRAL,
        )
        weight_map = get_rule_weight_map(persist=True)
    except Exception as _e:
        logger.warning(f'[ActionableIntel] Phase S weight map unavailable: {_e}')
        weight_map = {}
        STATUS_DISABLED = 'DISABLED'          # fallback constants
        STATUS_DOWNGRADED = 'DOWNGRADED'
        STATUS_BOOSTED = 'BOOSTED'
        STATUS_LOW_CONF = 'LOW_CONFIDENCE'
        WEIGHT_NEUTRAL = 1.0

    filtered_insights = []
    dropped_insights  = []   # DISABLED rules removed from display
    for ins in insights:
        entry = weight_map.get(ins['code'], {
            'weight':     WEIGHT_NEUTRAL,
            'status':     'NEUTRAL',
            'reason':     '無歷史反饋資料，使用預設權重',
            'rule_score': None,
            'samples':    0,
        })
        # Attach weight metadata to the insight for explainability
        ins['rule_weight']        = entry['weight']
        ins['weight_status']      = entry['status']
        ins['weight_reason']      = entry['reason']
        ins['feedback_samples']   = entry.get('samples', 0)
        ins['feedback_score']     = entry.get('rule_score')

        # Human-readable note surfaced in UI
        if entry['status'] == STATUS_DOWNGRADED:
            ins['weight_note'] = f"⚠️ 此規則依據歷史成效已降權（{entry['reason']}）"
        elif entry['status'] == STATUS_BOOSTED:
            ins['weight_note'] = f"✅ 此規則歷史成效良好（{entry['reason']}）"
        elif entry['status'] == STATUS_LOW_CONF:
            ins['weight_note'] = f"ℹ️ {entry['reason']}"
        else:
            ins['weight_note'] = None

        if entry['status'] == STATUS_DISABLED:
            # Remove from user view but keep for audit trail
            dropped_insights.append({
                'code':        ins['code'],
                'priority':    ins['priority'],
                'title':       ins['title'],
                'weight_reason': entry['reason'],
                'rule_score':  entry.get('rule_score'),
                'samples':     entry.get('samples', 0),
            })
            continue
        filtered_insights.append(ins)

    insights = filtered_insights

    # Sort: primary by priority (P0 → P1 → P2), secondary by weight (desc)
    # so boosted rules surface earlier within the same priority band.
    _PRIORITY_ORDER = {'P0': 0, 'P1': 1, 'P2': 2}
    insights.sort(key=lambda x: (
        _PRIORITY_ORDER.get(x['priority'], 9),
        -float(x.get('rule_weight', 1.0) or 1.0),
    ))

    health = _compute_health(signals, insights)

    # Top 3 actions
    top_actions = [ins['action'] for ins in insights[:3]]

    # Key observations (short messages for UI)
    key_observations = [ins['message'] for ins in insights[:3]]

    # Rule-gating metadata for explainability
    _gating_meta = {
        'applied':       bool(weight_map),
        'dropped_rules': dropped_insights,
        'downgraded':    [
            {'code': c, 'reason': e['reason'], 'rule_score': e.get('rule_score'),
             'samples': e.get('samples', 0)}
            for c, e in weight_map.items()
            if e.get('status') == STATUS_DOWNGRADED
        ],
        'boosted':       [
            {'code': c, 'reason': e['reason'], 'rule_score': e.get('rule_score'),
             'samples': e.get('samples', 0)}
            for c, e in weight_map.items()
            if e.get('status') == STATUS_BOOSTED
        ],
    }

    return {
        'lottery_type': lottery_type,
        'health': health,
        'health_label': _HEALTH_LABEL[health],
        'health_color': _HEALTH_COLOR[health],
        'signals_summary': {
            'validated_count': signals['validated_count'],
            'watch_count': signals['watch_count'],
            'total': signals['total'],
            'best_strategy': signals['best_strategy'],
            'best_validated_status': signals['best_validated_status'],
            'learning_gate': signals['learning'].get('gate', 'UNKNOWN'),
            'learning_effective': signals['learning'].get('effective', False),
            'quality_dominant': signals['quality'].get('dominant', False),
            # Phase T
            'best_confidence_tier':  (best_confidence or {}).get('confidence_tier'),
            'best_confidence_score': (best_confidence or {}).get('confidence_score'),
            'best_adjusted_mcnemar': (best_confidence or {}).get('adjusted_mcnemar_p'),
            'promotable_count':      len(promotable_candidates),
            # Phase U
            'promotion_production':  promotion_state.get('production'),
            'shadow_count':          len(promotion_state.get('shadow', [])),
            'promotable_tracking':   len(promotion_state.get('promotable', {})),
        },
        'insights': [
            {
                'priority': ins['priority'],
                'code': ins['code'],
                'title': ins['title'],
                'message': ins['message'],
                'detail': ins['detail'],
                'data_source': ins['data_source'],
                # Phase S — rule-gating metadata for explainability
                'rule_weight':      ins.get('rule_weight', 1.0),
                'weight_status':    ins.get('weight_status', 'NEUTRAL'),
                'weight_reason':    ins.get('weight_reason'),
                'weight_note':      ins.get('weight_note'),
                'feedback_samples': ins.get('feedback_samples', 0),
                'feedback_score':   ins.get('feedback_score'),
            }
            for ins in insights
        ],
        'top_actions': top_actions,
        'key_observations': key_observations,
        # Phase S — rule gating audit trail (explainability)
        'rule_gating': _gating_meta,
        # Phase T — confidence layer (additive)
        'confidence': {
            'best': best_confidence,
            'promotable': promotable_candidates,
            'table': confidence_table,
        },
        # Phase U — promotion engine state (additive)
        'promotion': promotion_state,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_actionable_summary() -> dict:
    """
    Returns actionable intelligence summary for all 3 lottery types.
    Reads from strategy_states files and cached explanation data.
    """
    result = {}
    for lt in LOTTERY_TYPES:
        try:
            result[lt] = _build_lottery_summary(lt)
        except Exception as e:
            logger.error(f'[ActionableIntel] Error building summary for {lt}: {e}', exc_info=True)
            result[lt] = {
                'lottery_type': lt,
                'health': 'RISK',
                'health_label': '🔴 錯誤',
                'health_color': '#e74c3c',
                'insights': [],
                'top_actions': [],
                'key_observations': ['系統錯誤，無法分析'],
                'error': str(e),
            }
    return result
