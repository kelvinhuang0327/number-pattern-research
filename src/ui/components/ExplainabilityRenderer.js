/**
 * ExplainabilityRenderer — Phase P
 * Shared rendering logic for explainability blocks across:
 *   - PredictionTracker (prediction detail / expanded area)
 *   - NextDrawHandler (strategy backtest card)
 *   - ReviewManager (research review detail)
 *
 * All methods are pure: receive an explanation object, return HTML string.
 */

const PROFILE_LABEL = { conservative: '保守', balanced: '平衡', aggressive: '積極' };
const GATE_LABEL    = { ENABLED: '已啟用', WEAK: '弱啟用', DISABLED: '未啟用' };
const GATE_COLOR    = { ENABLED: '#3fb950', WEAK: '#e5c07b', DISABLED: '#8b949e' };
const VS_LABEL      = {
    VALIDATED: '✅ 已完整驗證',
    WATCH:     '⚠️ 觀察中（未完全驗證）',
    REJECTED:  '❌ 未通過驗證',
};
const VS_COLOR      = { VALIDATED: '#3fb950', WATCH: '#e5c07b', REJECTED: '#e06c75' };

function _esc(s) {
    const d = document.createElement('div');
    d.textContent = s ?? '';
    return d.innerHTML;
}

function _fmtNumber(value, digits = 0) {
    if (value == null || value === '') return 'N/A';
    const num = Number(value);
    if (Number.isNaN(num)) return 'N/A';
    return num.toLocaleString('zh-TW', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

function _fmtPct(value, digits = 1) {
    if (value == null || value === '') return 'N/A';
    const num = Number(value);
    if (Number.isNaN(num)) return 'N/A';
    return `${(num * 100).toFixed(digits)}%`;
}

function _fmtMaybePct(value, digits = 1) {
    if (value === null || value === undefined) return 'N/A';
    return _fmtPct(value, digits);
}

function _fmtMaybeEdge(value) {
    if (value === null || value === undefined) return '—';
    return `${(value * 100).toFixed(2)}%`;
}

function _resolveDecisionGateStatus(dec) {
    if (!dec) return null;
    if (dec.jackpot_ev_status === 'ENABLED' || dec.jackpot_ev_status === 'DISABLED') {
        return dec.jackpot_ev_status;
    }
    if (dec.ev_gate_open === true) return 'ENABLED';
    if (dec.ev_gate_open === false) return 'DISABLED';
    return null;
}

function _gateLabel(status) {
    return GATE_LABEL[status] || status || '—';
}

function _gateColor(status) {
    return GATE_COLOR[status] || '#8b949e';
}

function _renderDecisionSummaryRows(dec) {
    const gateStatus = _resolveDecisionGateStatus(dec);
    const gateLabel = _gateLabel(gateStatus);
    const gateColor = _gateColor(gateStatus);
    const betCount = dec?.base_n_bets ?? dec?.final_n_bets ?? dec?.recommended_bet_count ?? dec?.n_bets ?? null;
    const kellyValue = dec?.kelly_fraction ?? dec?.kelly ?? null;
    const evValue = dec?.expected_ev ?? dec?.ev_value ?? dec?.ev_gap ?? null;
    const stage2 = dec?.stage2_gate || {};
    const kellyText = _fmtMaybePct(kellyValue, 1);
    const stage2HitRate = _fmtMaybePct(stage2.rolling_50p_hit_rate, 1);
    let decisionRow = '';
    if (gateStatus || betCount !== null || kellyValue !== null || evValue !== null || stage2.status) {
        decisionRow = `<div class="pt-explain-row">
            <span class="pt-explain-label">V3.1 決策</span>
            <span style="color:${gateColor};font-weight:600">EV gate: ${_esc(gateLabel)}</span>
            <span class="pt-explain-meta">Kelly=${kellyText} · 預估 EV=${_fmtNumber(evValue, 0)} · 建議注數=${betCount ?? 'N/A'}</span>
        </div>`;
    }
    let stage2Row = '';
    if (stage2.status) {
        stage2Row = `<div class="pt-explain-row">
            <span class="pt-explain-label">Stage2 Gate</span>
            <span>${_esc(stage2.status)}</span>
            <span class="pt-explain-meta">hit-rate=${stage2HitRate} · sample=${stage2.sample_size ?? 'N/A'}</span>
        </div>`;
    }
    return `${decisionRow}${stage2Row}`;
}

function _renderStrategySelectionSection(exp, base, baseExt, dec, profileLabel, vsLabel, vsColor) {
    const gateStatus = _resolveDecisionGateStatus(dec);
    const gateLabel = _gateLabel(gateStatus);
    const gateColor = _gateColor(gateStatus);
    const edge150 = _fmtMaybeEdge(base.edge_150p);
    const edge500 = _fmtMaybeEdge(base.edge_500p);
    const edge1500 = _fmtMaybeEdge(base.edge_1500p);
    const baseScoreRow = (base.composite_score !== null && base.composite_score !== undefined)
        ? `<div class="pt-explain-row">
            <span class="pt-explain-label">綜合評分</span>
            <span>${base.composite_score.toFixed(4)}</span>
            <span class="pt-explain-meta">Edge: 150p=${base.edge_150p === null || base.edge_150p === undefined ? '—' : (base.edge_150p * 100).toFixed(2) + '%'} 500p=${base.edge_500p === null || base.edge_500p === undefined ? '—' : (base.edge_500p * 100).toFixed(2) + '%'} 1500p=${base.edge_1500p === null || base.edge_1500p === undefined ? '—' : (base.edge_1500p * 100).toFixed(2) + '%'}</span>
        </div>`
        : '';
    const betRow = (dec.base_n_bets !== null && dec.base_n_bets !== undefined)
        ? `<div class="pt-explain-row">
            <span class="pt-explain-label">注數</span>
            <span>${dec.base_n_bets} → ${dec.final_n_bets ?? dec.base_n_bets} 注</span>
            <span class="pt-explain-meta">集中偏差 ${dec.concentration_bias ?? '—'}</span>
        </div>`
        : '';
    return `<div class="pt-explain-row">
        <span class="pt-explain-label">選用策略</span>
        <span style="font-weight:600;font-family:monospace">${_esc(exp.selected_strategy || '—')}</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">驗證狀態</span>
        <span style="color:${vsColor};font-weight:600">${_esc(vsLabel)}</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">Profile</span>
        <span style="font-weight:600">${_esc(profileLabel)}</span>
        <span class="pt-explain-meta">(learning×${baseExt.learning_amp ?? '—'} quality×${baseExt.quality_amp ?? '—'} var_n×${baseExt.var_n_scale ?? '—'})</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">EV Gate</span>
        <span style="color:${gateColor};font-weight:600">${_esc(gateLabel)}</span>
        <span class="pt-explain-meta">Edge: 150p=${edge150} 500p=${edge500} 1500p=${edge1500}</span>
    </div>
    ${baseScoreRow}
    ${betRow}
    ${_renderDecisionSummaryRows(dec)}`;
}

function _renderLearningSection(exp, gateLabel, gateClr) {
    const lr = exp.learning || exp.learning_detail || {};
    const hyp = lr.hypotheses || {};
    const boosted = (lr.boosted_agents || []).join(', ') || '—';
    const penalized = (lr.penalized_agents || []).join(', ') || '—';
    const researchScore = lr.research_score === null || lr.research_score === undefined ? '—' : lr.research_score.toFixed(4);
    const changedColor = lr.ranking_changed ? '#e5c07b' : '#3fb950';
    const changedLabel = lr.ranking_changed ? '有' : '無';
    const summaryText = lr.bonus_summary || lr.summary || '';
    let boostedRow = '';
    if (boosted !== '—') {
        boostedRow = `<div class="pt-explain-row"><span class="pt-explain-label">提升 Agent</span><span>${_esc(boosted)}</span></div>`;
    }
    let penalizedRow = '';
    if (penalized !== '—') {
        penalizedRow = `<div class="pt-explain-row"><span class="pt-explain-label">懲罰 Agent</span><span>${_esc(penalized)}</span></div>`;
    }
    let summaryRow = '';
    if (summaryText) {
        summaryRow = `<div class="pt-explain-summary">${_esc(summaryText)}</div>`;
    }
    return `<div class="pt-explain-row">
        <span class="pt-explain-label">狀態</span>
        <span style="color:${gateClr};font-weight:600">${gateLabel}</span>
        <span class="pt-explain-meta">(factor=${lr.factor ?? '—'}, research_score=${researchScore})</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">假設統計</span>
        <span>總數 ${hyp.total ?? 0}（已驗證 ${hyp.validated ?? 0} / 已拒絕 ${hyp.rejected ?? 0} / 暫定 ${hyp.provisional ?? 0}）</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">是否改變排序</span>
        <span style="color:${changedColor};font-weight:600">${changedLabel}</span>
    </div>
    ${boostedRow}
    ${penalizedRow}
    ${summaryRow}`;
}

function _renderQualitySection(exp) {
    const qr = exp.quality || {};
    const qualityEnabled = qr.enabled !== false;
    const qualityLabel = qr.quality_label
        ?? (qualityEnabled && (qr.total_abs_delta ?? 0) > 1e-6 ? '已調整熱門度' : '未調整');
    const qualityColor = qualityEnabled && (qr.total_abs_delta ?? 0) > 1e-6 ? '#58a6ff' : '#8b949e';
    const delta = qr.total_abs_delta === null || qr.total_abs_delta === undefined ? '—' : qr.total_abs_delta.toFixed(4);
    const changedColor = qr.ranking_changed ? '#e5c07b' : '#3fb950';
    const changedLabel = qr.ranking_changed ? '有' : '無';
    const summaryText = qr.quality_summary || qr.summary || '';
    return `<div class="pt-explain-row">
        <span class="pt-explain-label">狀態</span>
        <span style="color:${qualityColor};font-weight:600">${_esc(qualityLabel)}</span>
        <span class="pt-explain-meta">(amp=${qr.quality_amp ?? '—'}, delta=${delta})</span>
    </div>
    <div class="pt-explain-row">
        <span class="pt-explain-label">是否改變排序</span>
        <span style="color:${changedColor};font-weight:600">${changedLabel}</span>
    </div>
    ${summaryText ? `<div class="pt-explain-summary">${_esc(summaryText)}</div>` : ''}`;
}

function _renderAgentSystemSection(base, baseExt) {
    const agentWeights = Object.entries(baseExt.agent_weights || {})
        .map(([a, w]) => `<span class="pt-explain-tag">${_esc(a)}: ${(w * 100).toFixed(1)}%</span>`)
        .join('');
    return `<div class="pt-explain-section">
        <div class="pt-explain-section-title">📊 Agent 權重 / 系統狀態</div>
        <div class="pt-explain-tags">${agentWeights || '—'}</div>
        <div class="pt-explain-meta" style="margin-top:4px">Drift: ${_esc(baseExt.drift_status || '—')} ×${baseExt.drift_multiplier ?? '—'} | Regime: ${_esc(baseExt.regime_status || '—')} ×${baseExt.regime_multiplier ?? '—'}</div>
    </div>`;
}

function _renderRankingSection(sel) {
    const rankChanged = sel.ranking_changed ?? false;
    const rankColor = rankChanged ? '#e5c07b' : '#3fb950';
    const rankLabel = rankChanged ? '有' : '無';
    return `<div class="pt-explain-section">
        <div class="pt-explain-section-title">🔄 排名比較</div>
        <div class="pt-explain-row">
            <span class="pt-explain-label">最終排名變動</span>
            <span style="color:${rankColor};font-weight:600">${rankLabel}</span>
        </div>
        <div class="pt-explain-row">
            <span class="pt-explain-label">Bonus 前 Top</span>
            <span class="pt-explain-nums">${(sel.top_numbers_before_bonus || []).join(', ') || '—'}</span>
        </div>
        <div class="pt-explain-row">
            <span class="pt-explain-label">Bonus 後 Top</span>
            <span class="pt-explain-nums">${(sel.top_numbers_after_bonus || []).join(', ') || '—'}</span>
        </div>
    </div>`;
}

/**
 * Full explainability block — used in prediction tracking detail panel.
 * Collapsible, shows all sections.
 */
export function renderExplainabilityBlock(exp) {
    if (!exp) return '';

    // ── Learning ─────────────────────────────────────────────────────────
    const lr = exp.learning || exp.learning_detail || {};
    const learningGateKey = lr.gate || 'DISABLED';
    const learningGateLabel = GATE_LABEL[learningGateKey] || learningGateKey;
    const gateClr   = GATE_COLOR[learningGateKey] || '#8b949e';

    // ── Quality ───────────────────────────────────────────────────────────
    const qr = exp.quality || {};
    const qualityEnabled = qr.enabled !== false;
    // prefer new field, fall back to legacy
    const qualityLabel = qr.quality_label
        ?? (qualityEnabled && (qr.total_abs_delta ?? 0) > 1e-6 ? '已調整熱門度' : '未調整');
    const qualityColor  = qualityEnabled && (qr.total_abs_delta ?? 0) > 1e-6 ? '#58a6ff' : '#8b949e';

    // ── Profile ───────────────────────────────────────────────────────────
    const pr = exp.profile_detail || {};
    const profileLabel = PROFILE_LABEL[pr.name || exp.profile] || pr.name || exp.profile || '—';

    // ── Validated status ──────────────────────────────────────────────────
    const vs = exp.validated_status || 'WATCH';
    const vsLabel = VS_LABEL[vs] || vs;
    const vsColor = VS_COLOR[vs] || '#e5c07b';

    // ── Selection / ranking ───────────────────────────────────────────────
    const sel = exp.selection || {};
    const rankChanged  = sel.ranking_changed ?? false;
    const rankColor    = rankChanged ? '#e5c07b' : '#3fb950';
    const rankLabel    = rankChanged ? '有' : '無';

    // ── Base score / strategy ─────────────────────────────────────────────
    const base    = exp.base || {};
    const baseExt = exp.base_score_summary || {};

    // ── Decision ──────────────────────────────────────────────────────────
    const dec = exp.decision || {};
    // ── Final reason ─────────────────────────────────────────────────────
    const finalReason = exp.final_reason || '';

    return `<div class="pt-block pt-explain-block">
        <div class="pt-block-header" style="cursor:pointer" onclick="this.closest('.pt-explain-block').classList.toggle('pt-explain-collapsed')">
            <span class="pt-block-title">🔍 決策解釋</span>
            <span style="margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <span style="color:${vsColor};font-size:11px">${_esc(vsLabel)}</span>
                <span style="color:${gateClr};font-size:11px">Learning: ${learningGateLabel}</span>
                <span style="color:${qualityColor};font-size:11px">Quality: ${_esc(qualityLabel)}</span>
                <span style="font-size:11px;color:#c9d1d9">Profile: ${_esc(profileLabel)}</span>
                <span style="font-size:11px;color:${rankColor}">排名變動: ${rankLabel}</span>
                <span class="pt-explain-toggle-icon">▼</span>
            </span>
        </div>
        <div class="pt-explain-body">
            ${finalReason ? `<div class="pt-explain-summary" style="margin-bottom:10px;font-style:normal;color:#c9d1d9">${_esc(finalReason)}</div>` : ''}

            <div class="pt-explain-section">
                <div class="pt-explain-section-title">📋 策略選用</div>
                ${_renderStrategySelectionSection(exp, base, baseExt, dec, profileLabel, vsLabel, vsColor)}
            </div>

            <div class="pt-explain-section">
                <div class="pt-explain-section-title">🧠 Learning</div>
                ${_renderLearningSection(exp, learningGateLabel, gateClr)}
            </div>

            <div class="pt-explain-section">
                <div class="pt-explain-section-title">💎 Quality</div>
                ${_renderQualitySection(exp)}
            </div>

            ${_renderAgentSystemSection(base, baseExt)}

            ${_renderRankingSection(sel)}
        </div>
    </div>`;
}

/**
 * Compact explainability block — used in strategy backtest card and review detail.
 * No collapsing. Shows key fields only.
 */
export function renderCompactExplainBlock(exp, opts = {}) {
    if (!exp) return '';
    const { title = '決策解釋', showStrategy = true, showBaseMetrics = false } = opts;

    const lr = exp.learning || exp.learning_detail || {};
    const qr = exp.quality || {};
    const pr = exp.profile_detail || {};
    const sel = exp.selection || {};
    const base = exp.base || {};

    const gateKey   = lr.gate || 'DISABLED';
    const gateLabel = GATE_LABEL[gateKey] || gateKey;
    const gateClr   = GATE_COLOR[gateKey] || '#8b949e';

    const qualityLabel = qr.quality_label
        ?? ((qr.enabled !== false && (qr.total_abs_delta ?? 0) > 1e-6) ? '已調整熱門度' : '未調整');
    const qualityColor = (qr.enabled !== false && (qr.total_abs_delta ?? 0) > 1e-6) ? '#58a6ff' : '#8b949e';

    const profileLabel  = PROFILE_LABEL[pr.name || exp.profile] || pr.name || exp.profile || '—';
    const vs            = exp.validated_status || 'WATCH';
    const vsLabel       = VS_LABEL[vs] || vs;
    const vsColor       = VS_COLOR[vs] || '#e5c07b';
    const lrRankChanged = lr.ranking_changed ?? false;
    const rankChanged   = sel.ranking_changed ?? false;
    const rankColor     = rankChanged ? '#e5c07b' : '#3fb950';
    const finalReason   = exp.final_reason || '';

    return `<div style="border:1px solid #30363d;border-radius:6px;padding:10px 14px;margin-top:8px;background:#0d1117">
        <div style="font-size:12px;font-weight:700;color:#7d8590;margin-bottom:8px;letter-spacing:.3px">${_esc(title)}</div>
        ${finalReason ? `<div style="font-size:12px;color:#c9d1d9;margin-bottom:8px;padding:4px 8px;background:#161b22;border-radius:4px;font-style:italic">${_esc(finalReason)}</div>` : ''}
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px">
            ${showStrategy ? `
            <div style="font-size:11px">
                <span style="color:#7d8590">本期策略：</span>
                <span style="font-weight:600;font-family:monospace">${_esc(exp.selected_strategy || '—')}</span>
            </div>
            <div style="font-size:11px">
                <span style="color:#7d8590">驗證狀態：</span>
                <span style="color:${vsColor};font-weight:600">${_esc(vsLabel)}</span>
            </div>` : ''}
            <div style="font-size:11px">
                <span style="color:#7d8590">Profile：</span>
                <span style="font-weight:600">${_esc(profileLabel)}</span>
            </div>
            <div style="font-size:11px">
                <span style="color:#7d8590">Learning：</span>
                <span style="color:${gateClr};font-weight:600">${gateLabel}</span>
            </div>
            <div style="font-size:11px">
                <span style="color:#7d8590">Learning 改變排序：</span>
                <span style="color:${lrRankChanged ? '#e5c07b' : '#3fb950'};font-weight:600">${lrRankChanged ? '有' : '無'}</span>
            </div>
            <div style="font-size:11px">
                <span style="color:#7d8590">Quality：</span>
                <span style="color:${qualityColor};font-weight:600">${_esc(qualityLabel)}</span>
            </div>
            <div style="font-size:11px">
                <span style="color:#7d8590">最終排名變動：</span>
                <span style="color:${rankColor};font-weight:600">${rankChanged ? '有' : '無'}</span>
            </div>
            ${showBaseMetrics && base.composite_score != null ? `
            <div style="font-size:11px">
                <span style="color:#7d8590">綜合評分：</span>
                <span>${base.composite_score.toFixed(4)}</span>
            </div>` : ''}
        </div>
    </div>`;
}
