/**
 * ActionableRenderer — Phase Q
 * Renders the "🧠 系統建議" block for each lottery game card.
 *
 * Exported functions:
 *   renderActionableBlock(data, opts?) → HTML string
 *
 * Input: per-lottery entry from /api/actionable/summary
 * All text is short, operator-readable, no technical jargon excess.
 */

const PRIORITY_LABEL = { P0: 'P0 緊急', P1: 'P1 重要', P2: 'P2 建議' };
const PRIORITY_BG    = { P0: 'rgba(231,76,60,0.15)', P1: 'rgba(255,180,0,0.12)', P2: 'rgba(0,210,255,0.08)' };
const PRIORITY_BORDER= { P0: '#e74c3c', P1: '#ffb400', P2: 'rgba(0,210,255,0.3)' };
const PRIORITY_COLOR = { P0: '#e74c3c', P1: '#ffb400', P2: '#58a6ff' };

const HEALTH_BG    = { GOOD: 'rgba(0,200,100,0.12)', WATCH: 'rgba(255,180,0,0.12)', RISK: 'rgba(231,76,60,0.12)' };
const HEALTH_BORDER= { GOOD: '#00c864', WATCH: '#ffb400', RISK: '#e74c3c' };

/**
 * Main render function.
 * @param {Object|null} data - Per-lottery entry from /api/actionable/summary
 * @param {Object} opts - { title?: string, maxActions?: number }
 * @returns {string} HTML string
 */
export function renderActionableBlock(data, opts = {}) {
    const title = opts.title ?? '🧠 系統建議';
    const maxActions = opts.maxActions ?? 3;
    const blockId = `ai-block-${Math.random().toString(36).slice(2, 8)}`;

    if (!data) {
        return `<div style="margin-top:10px;padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid rgba(255,255,255,0.08);font-size:11px;color:#888">🧠 系統建議暫不可用</div>`;
    }

    const health = data.health || 'WATCH';
    const healthLabel = data.health_label || '—';
    const healthColor = data.health_color || '#888';
    const insights = data.insights || [];
    const topActions = (data.top_actions || []).slice(0, maxActions);
    const keyObs = data.key_observations || [];
    const ruleGating = data.rule_gating || null;  // Phase S

    const hasIssues = insights.length > 0;
    const noIssueMsg = '<div style="font-size:11px;color:#3fb950;padding:4px 0">✅ 目前策略穩定，無需調整</div>';

    // Collapsible block
    const bodyId = `${blockId}-body`;

    return `
<div style="margin-top:12px;border:1px solid ${HEALTH_BORDER[health]};border-radius:10px;background:${HEALTH_BG[health]};overflow:hidden">
    <!-- Header row (always visible) -->
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;cursor:pointer;user-select:none"
         onclick="const b=document.getElementById('${bodyId}');const open=b.style.display!=='none';b.style.display=open?'none':'block';this.querySelector('.ai-toggle').textContent=open?'▼':'▲'">
        <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;font-weight:700;color:${healthColor}">${title}</span>
            <span style="font-size:10px;padding:2px 8px;border-radius:4px;background:${HEALTH_BG[health]};border:1px solid ${HEALTH_BORDER[health]};color:${healthColor};font-weight:700">${healthLabel}</span>
        </div>
        <span class="ai-toggle" style="font-size:10px;color:#888;transition:transform 0.2s">▼</span>
    </div>

    <!-- Collapsible body -->
    <div id="${bodyId}" style="display:none;border-top:1px solid rgba(255,255,255,0.06);padding:10px 12px">

        <!-- Key observations (short messages) -->
        ${hasIssues
            ? `<div style="margin-bottom:8px;display:flex;flex-direction:column;gap:4px">
                ${insights.slice(0, maxActions).map(ins => _renderObservation(ins, healthColor)).join('')}
               </div>`
            : noIssueMsg
        }

        <!-- Action cards -->
        ${topActions.length > 0 ? `
        <div style="display:flex;flex-direction:column;gap:6px;margin-top:6px">
            ${topActions.map(a => _renderActionCard(a)).join('')}
        </div>` : ''}

        <!-- Phase S: Rule gating audit -->
        ${_renderRuleGating(ruleGating)}

        <!-- Signals summary footer -->
        ${_renderSignalsSummary(data.signals_summary)}

    </div>
</div>`;
}

function _renderActionCard(action) {
    const p = action.priority || 'P2';
    const bg = PRIORITY_BG[p] || PRIORITY_BG.P2;
    const border = PRIORITY_BORDER[p] || PRIORITY_BORDER.P2;
    const color = PRIORITY_COLOR[p] || PRIORITY_COLOR.P2;
    const label = PRIORITY_LABEL[p] || p;

    const detailId = `ac-${Math.random().toString(36).slice(2, 8)}`;

    return `
<div style="background:${bg};border:1px solid ${border};border-radius:8px;padding:8px 10px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div style="display:flex;flex-direction:column;gap:2px;flex:1">
            <div style="display:flex;align-items:center;gap:6px">
                <span style="font-size:9px;padding:1px 6px;border-radius:3px;background:${border};color:#fff;font-weight:800">${_escHtml(label)}</span>
                <span style="font-size:11px;font-weight:700;color:${color}">${_escHtml(action.title)}</span>
            </div>
            <div style="font-size:10px;color:var(--color-text-muted);margin-top:2px">${_escHtml(action.reason)}</div>
        </div>
        <span style="font-size:9px;color:#888;cursor:pointer;white-space:nowrap;margin-left:8px"
              onclick="const d=document.getElementById('${detailId}');d.style.display=d.style.display==='none'?'block':'none'">詳情▾</span>
    </div>
    <div id="${detailId}" style="display:none;margin-top:6px;font-size:10px;color:var(--color-text-muted);border-top:1px solid rgba(255,255,255,0.06);padding-top:6px">
        <div style="margin-bottom:3px"><span style="color:#58a6ff">預期效果：</span>${_escHtml(action.expected_effect)}</div>
        <div style="margin-bottom:3px"><span style="color:#e5c07b">風險：</span>${_escHtml(action.risk)}</div>
        <div><span style="color:#8b949e">停止條件：</span>${_escHtml(action.condition_to_stop)}</div>
    </div>
</div>`;
}

function _renderSignalsSummary(sig) {
    if (!sig) return '';
    const gateColor = { ENABLED: '#3fb950', WEAK: '#e5c07b', DISABLED: '#e74c3c', UNKNOWN: '#888' };
    const gate = sig.learning_gate || 'UNKNOWN';

    // Phase T — confidence tier chip
    const tier = sig.best_confidence_tier || null;
    const tierLabel = {
        HIGH_CONFIDENCE:   '高信心',
        MEDIUM_CONFIDENCE: '中信心',
        LOW_CONFIDENCE:    '低信心',
        UNRELIABLE:        '不可靠',
    }[tier] || null;
    const tierColor = {
        HIGH_CONFIDENCE:   '#3fb950',
        MEDIUM_CONFIDENCE: '#58a6ff',
        LOW_CONFIDENCE:    '#e5c07b',
        UNRELIABLE:        '#e74c3c',
    }[tier] || '#888';
    const adjMc = (sig.best_adjusted_mcnemar !== null && sig.best_adjusted_mcnemar !== undefined)
        ? `p*=${Number(sig.best_adjusted_mcnemar).toFixed(3)}` : null;
    const promoCount = Number(sig.promotable_count || 0);

    return `
<div style="margin-top:8px;padding:6px 8px;background:rgba(0,0,0,0.2);border-radius:6px;display:flex;flex-wrap:wrap;gap:10px;font-size:10px;color:#888">
    <span>策略：${sig.validated_count || 0}✅ ${sig.watch_count || 0}⚠️</span>
    <span>Learning：<span style="color:${gateColor[gate] || '#888'}">${gate}</span></span>
    <span>Quality：${sig.quality_dominant ? '<span style="color:#ffb400">主導</span>' : '輔助'}</span>
    ${tierLabel ? `<span title="Phase T 統計信心等級">信心：<span style="color:${tierColor};font-weight:700">${tierLabel}</span>${sig.best_confidence_score ? ` (${Number(sig.best_confidence_score).toFixed(2)})` : ''}</span>` : ''}
    ${adjMc ? `<span title="Holm-Bonferroni 校正後 mcnemar p-value">${adjMc}</span>` : ''}
    ${promoCount > 0 ? `<span style="color:#58a6ff">★ ${promoCount} 候選可晉升</span>` : ''}
</div>
${_renderPromotionBar(sig)}`;
}

function _escHtml(s) {
    if (!s) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── Phase U: Promotion status bar ────────────────────────────────────────────

function _renderPromotionBar(sig) {
    const prod = sig.promotion_production;
    const shadowN = Number(sig.shadow_count || 0);
    const trackN = Number(sig.promotable_tracking || 0);
    if (!prod && !shadowN && !trackN) return '';

    const chips = [];
    if (prod) chips.push(`<span style="color:#3fb950" title="Current production strategy">🟢 ${_escHtml(prod)}</span>`);
    if (shadowN > 0) chips.push(`<span style="color:#e5c07b">🟡 ${shadowN} shadow</span>`);
    if (trackN > 0) chips.push(`<span style="color:#58a6ff">🔵 ${trackN} 追蹤中</span>`);

    return `
<div style="margin-top:4px;padding:4px 8px;background:rgba(0,0,0,0.15);border-radius:4px;display:flex;flex-wrap:wrap;gap:10px;font-size:10px;color:#888">
    <span style="color:#666">升級引擎：</span>${chips.join('')}
</div>`;
}

// ── Phase S helpers ──────────────────────────────────────────────────────────

const WEIGHT_STATUS_BG = {
    BOOSTED:        'rgba(63,185,80,0.12)',
    DOWNGRADED:     'rgba(231,76,60,0.10)',
    LOW_CONFIDENCE: 'rgba(229,192,123,0.08)',
    NEUTRAL:        'transparent',
};
const WEIGHT_STATUS_COLOR = {
    BOOSTED:        '#3fb950',
    DOWNGRADED:     '#e74c3c',
    LOW_CONFIDENCE: '#e5c07b',
    NEUTRAL:        '#888',
};

function _renderObservation(ins, defaultColor) {
    const status = ins.weight_status || 'NEUTRAL';
    const bg     = WEIGHT_STATUS_BG[status] || 'transparent';
    const color  = WEIGHT_STATUS_COLOR[status] || defaultColor;
    const border = status === 'NEUTRAL' ? defaultColor : color;

    const weightTag = (status === 'DOWNGRADED' || status === 'BOOSTED' || status === 'LOW_CONFIDENCE')
        ? `<span style="margin-left:6px;font-size:9px;padding:1px 5px;border-radius:3px;background:${color};color:#fff;font-weight:700">
             ${status === 'DOWNGRADED' ? '已降權' : status === 'BOOSTED' ? '加權' : '低信心'}
           </span>`
        : '';

    const noteRow = ins.weight_note
        ? `<div style="font-size:10px;color:${color};margin-top:2px">${_escHtml(ins.weight_note)}</div>`
        : '';

    return `
<div style="font-size:11px;color:var(--color-text-secondary);padding:4px 0 4px 8px;border-left:2px solid ${border};background:${bg};border-radius:0 4px 4px 0">
    <div style="display:flex;align-items:center;flex-wrap:wrap">
        <span>${_escHtml(ins.message)}</span>
        ${weightTag}
    </div>
    ${noteRow}
</div>`;
}

function _renderRuleGating(gating) {
    if (!gating || !gating.applied) return '';
    const downgraded = gating.downgraded || [];
    const boosted    = gating.boosted    || [];
    const dropped    = gating.dropped_rules || [];
    if (downgraded.length === 0 && boosted.length === 0 && dropped.length === 0) {
        return '';
    }
    const gid = `gating-${Math.random().toString(36).slice(2, 8)}`;
    const chip = (c, color, bg) =>
        `<span style="display:inline-block;margin:2px 4px 0 0;padding:2px 6px;border-radius:3px;background:${bg};color:${color};font-size:9px;font-weight:700;border:1px solid ${color}">${_escHtml(c)}</span>`;

    return `
<div style="margin-top:8px;border-top:1px dashed rgba(255,255,255,0.1);padding-top:6px">
    <div style="font-size:10px;color:#8b949e;cursor:pointer;user-select:none"
         onclick="const d=document.getElementById('${gid}');d.style.display=d.style.display==='none'?'block':'none'">
        🔁 反饋自動調權 (${boosted.length} 加權 / ${downgraded.length} 降權 / ${dropped.length} 停用) ▾
    </div>
    <div id="${gid}" style="display:none;margin-top:6px;font-size:10px;color:#8b949e;background:rgba(0,0,0,0.2);border-radius:6px;padding:6px 8px">
        ${boosted.length ? `<div style="margin-bottom:4px"><b style="color:#3fb950">加權：</b>${boosted.map(r => chip(r.code, '#3fb950', 'rgba(63,185,80,0.15)')).join('')}</div>` : ''}
        ${downgraded.length ? `<div style="margin-bottom:4px"><b style="color:#e74c3c">降權：</b>${downgraded.map(r => chip(r.code, '#e74c3c', 'rgba(231,76,60,0.15)')).join('')}</div>` : ''}
        ${dropped.length ? `<div style="margin-bottom:4px"><b style="color:#e74c3c">已停用：</b>${dropped.map(r => chip(r.code, '#e74c3c', 'rgba(231,76,60,0.2)')).join('')}</div>` : ''}
        ${(downgraded[0] || boosted[0]) ? `
        <div style="margin-top:4px;font-size:9px;color:#6a737d">
            依據：近期動作結果的 rule_score 統計（Phase R → Phase S）
        </div>` : ''}
    </div>
</div>`;
}
