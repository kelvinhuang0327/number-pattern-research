/**
 * FeedbackRenderer — Phase R: Action Feedback & Outcome Tracking
 *
 * Renders the "📊 建議成效" block with:
 * - Overall effectiveness %
 * - Rule performance ranking
 * - Recent completed actions
 * - Meta insights (KEEP / TUNE / REMOVE)
 *
 * Exported functions:
 *   renderFeedbackBlock(data, opts?) → HTML string
 *
 * Input: response from GET /api/actionable/feedback
 */

const REC_COLOR = {
    KEEP:              '#3fb950',
    TUNE:              '#ffb400',
    REMOVE:            '#e74c3c',
    INSUFFICIENT_DATA: '#888',
};
const REC_LABEL = {
    KEEP:              '✅ 保留',
    TUNE:              '⚙️ 調整',
    REMOVE:            '❌ 移除',
    INSUFFICIENT_DATA: '⏳ 資料不足',
};

const EFF_COLOR = {
    EFFECTIVE: '#3fb950',
    NEUTRAL:   '#888',
    NEGATIVE:  '#e74c3c',
};
const EFF_LABEL = {
    EFFECTIVE: '✅ 有效',
    NEUTRAL:   '➖ 無效',
    NEGATIVE:  '❌ 負效',
};

const PRIO_COLOR = { P0: '#e74c3c', P1: '#ffb400', P2: '#58a6ff' };

/**
 * Main render function.
 * @param {Object|null} feedbackData - Response from GET /api/actionable/feedback
 * @param {Object} opts - { title?: string }
 * @returns {string} HTML string
 */
export function renderFeedbackBlock(feedbackData, opts = {}) {
    const title = opts.title ?? '📊 建議成效';
    const blockId = `fb-block-${Math.random().toString(36).slice(2, 8)}`;
    const bodyId  = `${blockId}-body`;

    if (!feedbackData || !feedbackData.ok) {
        return `<div style="margin-top:10px;padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid rgba(255,255,255,0.08);font-size:11px;color:#888">📊 建議成效資料暫不可用</div>`;
    }

    const fb     = feedbackData.feedback || {};
    const totals = fb.totals || {};
    const eff    = fb.effectiveness || {};
    const meta   = fb.meta_insights || {};
    const rules  = fb.rule_stats || {};
    const recent = fb.recent_completed || [];

    const totalCompleted = totals.completed || 0;
    const effPct  = Math.round((eff.effective_pct  || 0) * 100);
    const negPct  = Math.round((eff.negative_pct   || 0) * 100);
    const neutPct = 100 - effPct - negPct;

    // Determine header health color based on effectiveness rate
    const headerColor = effPct >= 60 ? '#3fb950' : effPct >= 40 ? '#ffb400' : '#e74c3c';
    const headerBg    = effPct >= 60 ? 'rgba(0,200,100,0.08)' : effPct >= 40 ? 'rgba(255,180,0,0.08)' : 'rgba(231,76,60,0.08)';
    const headerBorder= effPct >= 60 ? '#3fb95055' : effPct >= 40 ? '#ffb40055' : '#e74c3c55';

    const hasData = totalCompleted > 0;
    const summaryLabel = eff.summary_label || '尚無已完成評估的建議';

    // ── Section: Overview ────────────────────────────────────────────────────
    const overviewHtml = `
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px">
    ${_statCard('已完成', totalCompleted, '#58a6ff')}
    ${_statCard('追蹤中', (totals.tracking || 0) + (totals.open || 0), '#888')}
    ${_statCard('有效率', hasData ? effPct + '%' : '—', headerColor)}
</div>
<div style="font-size:11px;color:${headerColor};margin-bottom:8px;padding:6px 8px;background:${headerBg};border-radius:6px;border-left:2px solid ${headerColor}">
    ${summaryLabel}
</div>`;

    // ── Section: Effectiveness bar ────────────────────────────────────────────
    const barHtml = hasData ? `
<div style="margin-bottom:10px">
    <div style="font-size:10px;color:#666;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">建議效果分布</div>
    <div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:rgba(255,255,255,0.05)">
        ${effPct  > 0 ? `<div style="width:${effPct}%;background:#3fb950" title="${effPct}% 有效"></div>` : ''}
        ${neutPct > 0 ? `<div style="width:${neutPct}%;background:#444" title="${neutPct}% 無效"></div>` : ''}
        ${negPct  > 0 ? `<div style="width:${negPct}%;background:#e74c3c" title="${negPct}% 負效"></div>` : ''}
    </div>
    <div style="display:flex;gap:10px;margin-top:4px;font-size:10px">
        <span style="color:#3fb950">■ 有效 ${effPct}%</span>
        <span style="color:#888">■ 無效 ${neutPct}%</span>
        <span style="color:#e74c3c">■ 負效 ${negPct}%</span>
    </div>
</div>` : '';

    // ── Section: Top/Worst rules ──────────────────────────────────────────────
    const topRules   = (meta.top_rules   || []).slice(0, 3);
    const worstRules = (meta.worst_rules || []).slice(0, 3);

    const rulesHtml = (topRules.length || worstRules.length) ? `
<div style="margin-bottom:10px">
    <div style="font-size:10px;color:#666;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">規則效果排名</div>
    ${topRules.length ? `
    <div style="font-size:10px;color:#3fb950;margin-bottom:3px;font-weight:600">表現最佳</div>
    ${topRules.map(r => _ruleRow(r)).join('')}` : ''}
    ${worstRules.length ? `
    <div style="font-size:10px;color:#e74c3c;margin-top:6px;margin-bottom:3px;font-weight:600">表現最差</div>
    ${worstRules.map(r => _ruleRow(r)).join('')}` : ''}
</div>` : '';

    // ── Section: KEEP / TUNE / REMOVE ─────────────────────────────────────────
    const keep   = meta.keep   || [];
    const tune   = meta.tune   || [];
    const remove = meta.remove || [];

    const recsHtml = (keep.length || tune.length || remove.length) ? `
<div style="margin-bottom:10px">
    <div style="font-size:10px;color:#666;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">建議調整</div>
    <div style="display:flex;flex-wrap:wrap;gap:4px">
        ${keep.map(c   => _tag(c, '#3fb950', 'rgba(0,200,100,0.1)', '✅')).join('')}
        ${tune.map(c   => _tag(c, '#ffb400', 'rgba(255,180,0,0.1)',  '⚙️')).join('')}
        ${remove.map(c => _tag(c, '#e74c3c', 'rgba(231,76,60,0.1)', '❌')).join('')}
    </div>
</div>` : '';

    // ── Section: Recent completed ─────────────────────────────────────────────
    const recentHtml = recent.length ? `
<div>
    <div style="font-size:10px;color:#666;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">最近完成評估</div>
    ${recent.slice(0, 5).map(a => _recentRow(a)).join('')}
</div>` : '';

    // ── Empty state ────────────────────────────────────────────────────────────
    const emptyHtml = !hasData ? `
<div style="text-align:center;padding:16px;color:#555;font-size:11px">
    ⏳ 尚無完成評估的建議<br>
    <span style="font-size:10px;color:#444">建議追蹤中，將在 30 期後完成評估</span>
</div>` : '';

    return `
<div style="margin-top:12px;border:1px solid ${headerBorder};border-radius:10px;background:${headerBg};overflow:hidden">
    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;cursor:pointer;user-select:none"
         onclick="const b=document.getElementById('${bodyId}');const open=b.style.display!=='none';b.style.display=open?'none':'block';this.querySelector('.fb-toggle').textContent=open?'▼':'▲'">
        <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;font-weight:700;color:${headerColor}">${title}</span>
            ${hasData ? `<span style="font-size:10px;padding:2px 7px;border-radius:4px;background:${headerBg};border:1px solid ${headerBorder};color:${headerColor};font-weight:700">${effPct}% 有效</span>` : `<span style="font-size:10px;color:#555">追蹤中</span>`}
        </div>
        <span class="fb-toggle" style="font-size:10px;color:#888">▼</span>
    </div>

    <!-- Body (collapsed by default, open on click) -->
    <div id="${bodyId}" style="display:none;padding:0 12px 12px">
        <div style="border-top:1px solid rgba(255,255,255,0.06);padding-top:10px">
            ${overviewHtml}
            ${barHtml}
            ${rulesHtml}
            ${recsHtml}
            ${recentHtml}
            ${emptyHtml}
        </div>
    </div>
</div>`;
}


// ── Helper renderers ──────────────────────────────────────────────────────────

function _statCard(label, value, color) {
    return `
<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:6px 8px;text-align:center">
    <div style="font-size:14px;font-weight:900;color:${color}">${value}</div>
    <div style="font-size:9px;color:#555;margin-top:2px">${label}</div>
</div>`;
}

function _ruleRow(rule) {
    const score      = rule.rule_score || 0;
    const scoreColor = score > 0 ? '#3fb950' : score < 0 ? '#e74c3c' : '#888';
    const rec        = rule.recommendation || 'INSUFFICIENT_DATA';
    const eff        = rule.effectiveness_rate != null
        ? Math.round(rule.effectiveness_rate * 100) + '%'
        : '—';

    return `
<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px;background:rgba(255,255,255,0.03);margin-bottom:2px;font-size:10px">
    <span style="color:#ccc;font-family:monospace;flex:1">${rule.action_type}</span>
    <span style="color:#888;width:28px;text-align:center">${eff}</span>
    <span style="color:${scoreColor};width:40px;text-align:right;font-weight:700">${score >= 0 ? '+' : ''}${score.toFixed(2)}</span>
    <span style="color:${REC_COLOR[rec]};margin-left:6px;font-size:9px">${REC_LABEL[rec]}</span>
</div>`;
}

function _tag(code, color, bg, icon) {
    return `<span style="font-size:9px;padding:2px 7px;border-radius:3px;background:${bg};border:1px solid ${color}55;color:${color}">${icon} ${code}</span>`;
}

function _recentRow(action) {
    const eff    = (action.outcome || {}).effectiveness || '—';
    const delta  = (action.outcome || {}).edge_delta;
    const color  = EFF_COLOR[eff] || '#888';
    const label  = EFF_LABEL[eff] || eff;
    const deltaStr = delta != null
        ? (delta >= 0 ? '+' : '') + (delta * 100).toFixed(2) + '%'
        : '—';

    const date = action.evaluated_at
        ? action.evaluated_at.slice(0, 10)
        : '—';

    return `
<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 6px;border-radius:4px;background:rgba(255,255,255,0.03);margin-bottom:2px;font-size:10px">
    <div style="flex:1;min-width:0">
        <span style="color:#ccc;font-family:monospace">${action.action_type}</span>
        <span style="color:#555;margin-left:6px">${action.lottery_type}</span>
    </div>
    <span style="color:${PRIO_COLOR[action.priority] || '#888'};margin-right:6px;font-size:9px">${action.priority}</span>
    <span style="color:#888;margin-right:8px;font-size:9px">${date}</span>
    <span style="color:${color};font-weight:600;white-space:nowrap">${label}</span>
    <span style="color:#555;margin-left:6px;font-size:9px">${deltaStr}</span>
</div>`;
}
