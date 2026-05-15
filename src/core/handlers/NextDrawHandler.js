/**
 * NextDrawHandler
 * Fetches and renders the NEXT DRAW PREDICTION page.
 * All predictions come from GET /api/next-draw-summary (backend coordinator).
 * No frontend prediction computation.
 */
import { getApiUrl } from '../../config/apiConfig.js';

const GAME_LABELS = {
    DAILY_539:   { name: '今彩 539',  icon: '🟢', pick: 5, pool: 39 },
    BIG_LOTTO:   { name: '大樂透',   icon: '🔵', pick: 6, pool: 49 },
    POWER_LOTTO: { name: '威力彩',   icon: '🟣', pick: 6, pool: 38 },
};

const STATUS_CONFIG = {
    PRODUCTION:    { label: 'PRODUCTION', cls: 'status-production', tip: '已驗證有效策略（300p Edge ≥ 3%）' },
    WATCH:         { label: 'WATCH',       cls: 'status-watch',      tip: '信號正向但 Edge 較弱或近期趨勢下滑' },
    ADVISORY_ONLY: { label: 'ADVISORY',    cls: 'status-advisory',   tip: '僅供參考，尚未達驗證門檻' },
    MAINTENANCE:   { label: 'MAINTENANCE', cls: 'status-maintenance', tip: '信號空間已窮盡，策略持續監控中' },
    ERROR:         { label: 'ERROR',       cls: 'status-error',       tip: '數據載入失敗' },
};

function _fmtMoney(value) {
    if (value == null || value === '') return 'N/A';
    const num = Number(value);
    if (Number.isNaN(num)) return 'N/A';
    return num.toLocaleString('zh-TW', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

function _fmtPct(value, digits = 1) {
    if (value == null || value === '') return 'N/A';
    const num = Number(value);
    if (Number.isNaN(num)) return 'N/A';
    return `${(num * 100).toFixed(digits)}%`;
}

function _resolveDecisionBetCount(decision) {
    return decision?.kelly_optimal_bets
        ?? decision?.recommended_bet_count
        ?? decision?.n_bets_after_gate
        ?? decision?.n_bets
        ?? decision?.final_n_bets
        ?? decision?.base_n_bets
        ?? null;
}

function _resolveDecisionGateLabel(decision) {
    if (decision?.jackpot_ev_status) return decision.jackpot_ev_status;
    if (decision?.ev_gate_open === true) return 'ENABLED';
    if (decision?.ev_gate_open === false) return 'DISABLED';
    return 'N/A';
}

function _resolveDecisionGateColor(label) {
    if (label === 'ENABLED') return '#3fb950';
    if (label === 'DISABLED') return '#8b949e';
    return '#e5c07b';
}

function _resolveDecisionTone(label) {
    if (label === 'ENABLED') return 'var(--color-success)';
    if (label === 'DISABLED') return '#8b949e';
    return 'var(--color-warning)';
}

function _resolveDecisionIcon(label) {
    if (label === 'ENABLED') return '✅';
    if (label === 'DISABLED') return '⛔';
    return 'ℹ️';
}

export class NextDrawHandler {
    constructor(app) {
        this.app = app;
        this.apiClient = app.apiClient || null;
        this._lastData = null;
    }

    /** Called when the next-draw nav button is clicked. */
    async onShow() {
        const container = document.getElementById('next-draw-content');
        if (!container) return;

        // Load Best Strategy Summary panel (always refresh on first show)
        this._loadBestStrategySummary();

        // Bind Decision V3 refresh button
        const decBtn = document.getElementById('decision-refresh-btn');
        if (decBtn && !decBtn._bound) {
            decBtn.addEventListener('click', () => this._loadBestStrategySummary(true));
            decBtn._bound = true;
        }

        // If we already have data from this session, just re-render
        if (this._lastData) {
            this._render(container, this._lastData);
            return;
        }

        this._renderLoading(container);
        await this._fetchAndRender(container);
    }

    /** Refresh button handler. */
    async onRefresh() {
        this._lastData = null;
        const container = document.getElementById('next-draw-content');
        if (!container) return;
        this._renderLoading(container);
        await this._fetchAndRender(container);
    }

    /** Load Best Strategy Summary panel */
    async _loadBestStrategySummary(force = false) {
        const panel = document.getElementById('decision-v3-content');
        if (!panel) return;
        if (!force && panel.dataset.loaded) return;

        panel.innerHTML = '<div style="text-align:center;color:#888;padding:20px;grid-column:1/-1">載入策略摘要…</div>';

        try {
            const resp = await fetch(getApiUrl('/api/decision/best-strategy-summary'));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            panel.dataset.loaded = '1';
            this._renderBestStrategySummary(panel, data);
        } catch (err) {
            panel.innerHTML = `<div style="color:#e74c3c;padding:12px;grid-column:1/-1">⚠️ 策略總覽載入失敗：${err.message}</div>`;
        }
    }

    _renderBestStrategySummary(panel, summaries) {
        const list = Array.isArray(summaries) ? summaries : [];
        let html = '';
        for (const summary of list) {
            html += this._renderBestStrategyCard(summary);
        }
        panel.innerHTML = html || '<div style="color:#888;padding:12px;grid-column:1/-1">無策略總覽資料</div>';
        if (globalThis.lucide) globalThis.lucide.createIcons();
    }

    _renderBestStrategyCard(summary) {
        const gameId = summary?.game_id || summary?.lottery_type || '';
        const game = GAME_LABELS[gameId] || { name: gameId || 'N/A', icon: '🎲', pick: 6, pool: 49 };
        const best = summary?.best_strategy || null;
        const strategies = Array.isArray(summary?.all_strategies) ? summary.all_strategies : [];
        const strategyStatus = best?.status || 'N/A';
        const strategyStatusConfig = STATUS_CONFIG[strategyStatus] || STATUS_CONFIG.ADVISORY_ONLY;
        const validatedStatus = best?.validated_status || 'N/A';
        const validatedClass = validatedStatus === 'VALIDATED'
            ? 'status-production'
            : validatedStatus === 'WATCH'
                ? 'status-watch'
                : 'status-advisory';
        const bestName = best?.strategy_name || 'N/A';
        const bestBetCount = best?.bet_count ?? 'N/A';
        const compositeScore = best?.composite_score === null || best?.composite_score === undefined
            ? 'N/A'
            : Number(best.composite_score).toFixed(6);
        const edge1500 = best?.edge_1500p === null || best?.edge_1500p === undefined
            ? 'N/A'
            : `${Number(best.edge_1500p).toFixed(3)}%`;
        const edge500 = best?.edge_500p === null || best?.edge_500p === undefined
            ? 'N/A'
            : `${Number(best.edge_500p).toFixed(3)}%`;
        const edge150 = best?.edge_150p === null || best?.edge_150p === undefined
            ? 'N/A'
            : `${Number(best.edge_150p).toFixed(3)}%`;
        const cpScore = best?.cp_score === null || best?.cp_score === undefined ? 'N/A' : Number(best.cp_score).toFixed(3);
        const successRate = best?.success_rate_300 === null || best?.success_rate_300 === undefined
            ? 'N/A'
            : `${Number(best.success_rate_300).toFixed(2)}%`;
        const warningHtml = best?.validation_warning
            ? `<div style="margin-top:8px;padding:8px 10px;border-radius:8px;background:rgba(229,193,7,0.08);border:1px solid rgba(229,193,7,0.25);color:#e5c07b;font-size:11px">${best.validation_warning}</div>`
            : '';
        const strategyPills = strategies.length
            ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
                ${strategies.map(s => {
                    const isBest = best?.strategy_name && s.strategy_name === best.strategy_name;
                    const pillBg = isBest ? 'rgba(63,185,80,0.14)' : 'rgba(255,255,255,0.05)';
                    const pillBorder = isBest ? '#3fb950' : 'rgba(255,255,255,0.08)';
                    const pillColor = isBest ? '#3fb950' : '#c9d1d9';
                    const pillStatus = s.validated_status || 'N/A';
                    return `<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border-radius:999px;background:${pillBg};border:1px solid ${pillBorder};color:${pillColor};font-size:11px">
                        <strong>${s.bet_count ?? 'N/A'}注</strong>
                        <span>${s.strategy_name || 'N/A'}</span>
                        <span style="color:#7d8590">·</span>
                        <span>${pillStatus}</span>
                    </span>`;
                }).join('')}
            </div>`
            : '';
        const allRows = strategies.length
            ? strategies.map(s => {
                const rowCls = best?.strategy_name && s.strategy_name === best.strategy_name ? 'nd-best-row' : '';
                const sStatus = s.status || 'N/A';
                const sValidated = s.validated_status || 'N/A';
                const sComposite = s.composite_score === null || s.composite_score === undefined ? 'N/A' : Number(s.composite_score).toFixed(6);
                const sCp = s.cp_score === null || s.cp_score === undefined ? 'N/A' : Number(s.cp_score).toFixed(3);
                const sEdge300 = s.edge === null || s.edge === undefined ? 'N/A' : `${Number(s.edge).toFixed(2)}%`;
                const sBetCount = s.bet_count ?? 'N/A';
                const sSuccessRate = s.success_rate_300 === null || s.success_rate_300 === undefined
                    ? 'N/A'
                    : `${Number(s.success_rate_300).toFixed(2)}%`;
                return `<tr class="${rowCls}">
                    <td>${sBetCount}</td>
                    <td style="text-align:left">
                        <div style="font-weight:600">${s.strategy_name || 'N/A'}</div>
                    </td>
                    <td><span class="nd-status-badge ${sValidated === 'VALIDATED' ? 'status-production' : sValidated === 'WATCH' ? 'status-watch' : 'status-advisory'}">${sValidated}</span></td>
                    <td><span class="nd-status-badge ${STATUS_CONFIG[sStatus]?.cls || 'status-advisory'}">${sStatus}</span></td>
                    <td>${sSuccessRate}</td>
                    <td>${sCp}</td>
                    <td>${sComposite}</td>
                    <td>${sEdge300}</td>
                </tr>`;
            }).join('')
            : '<tr><td colspan="8" style="text-align:center;color:#888">無策略資料</td></tr>';
        const currentLabel = summary?.game || game.name;
        return `
            <div class="strategy-summary-card" style="
                background: var(--color-surface);
                backdrop-filter: blur(12px);
                border: 1px solid var(--border-glow);
                border-radius: 14px;
                padding: 16px;
                box-shadow: var(--shadow-neon);
                display: flex;
                flex-direction: column;
                gap: 12px;
                position: relative;
                width: 100%;
                max-width: 520px;
                margin-bottom: 24px;
                transition: var(--transition-base);
            ">
                <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:10px">
                    <span style="font-family:var(--font-heading);font-weight:800;font-size:20px;color:var(--color-primary);letter-spacing:1px">${game.icon} ${currentLabel}</span>
                    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end">
                        <span class="nd-status-badge ${strategyStatusConfig.cls}" title="${strategyStatusConfig.tip}">${strategyStatusConfig.label}</span>
                        <span class="nd-status-badge ${validatedClass}">${validatedStatus}</span>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;background:rgba(0,0,0,0.2);padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.05)">
                    <div>
                        <div style="font-size:10px;color:var(--color-text-muted)">最佳策略</div>
                        <div style="font-size:13px;font-weight:700;color:var(--color-text-primary)">${bestName}</div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:var(--color-text-muted)">注數</div>
                        <div style="font-size:15px;font-weight:800;color:var(--color-success)">${bestBetCount} <small style="font-size:11px;font-weight:400">注</small></div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:var(--color-text-muted)">Composite</div>
                        <div style="font-size:13px;font-weight:700">${compositeScore}</div>
                    </div>
                    <div>
                        <div style="font-size:10px;color:var(--color-text-muted)">300p / CP</div>
                        <div style="font-size:13px;font-weight:700">${successRate} · ${cpScore}</div>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:8px;background:rgba(255,255,255,0.03);padding:12px;border-radius:10px">
                    <div style="text-align:center">
                        <div style="font-size:10px;color:var(--color-text-secondary);margin-bottom:4px">Edge 150p</div>
                        <div style="font-size:13px">${edge150}</div>
                    </div>
                    <div style="text-align:center;border-left:1px solid rgba(255,255,255,0.05);border-right:1px solid rgba(255,255,255,0.05)">
                        <div style="font-size:10px;color:var(--color-text-secondary);margin-bottom:4px">Edge 500p</div>
                        <div style="font-size:13px">${edge500}</div>
                    </div>
                    <div style="text-align:center">
                        <div style="font-size:10px;color:var(--color-text-secondary);margin-bottom:4px">Edge 1500p</div>
                        <div style="font-size:13px">${edge1500}</div>
                    </div>
                </div>

                ${strategyPills}

                ${warningHtml}

                <div style="overflow-x:auto">
                    <div style="font-size:11px;color:#7d8590;margin:8px 0 6px">正式策略清單（含所有注數）</div>
                    <table class="data-table" style="width:100%;font-size:11px">
                        <thead>
                            <tr>
                                <th>注數</th>
                                <th>策略</th>
                                <th>驗證</th>
                                <th>狀態</th>
                                <th>300p%</th>
                                <th>CP</th>
                                <th>Composite</th>
                                <th>Edge</th>
                            </tr>
                        </thead>
                        <tbody>${allRows}</tbody>
                    </table>
                </div>
            </div>`;
    }

    _renderDecisionCard(decision) {
        return this._renderBestStrategyCard(decision);
    }

    _formatStrategySummaryValue(value, digits = 3) {
        if (value === null || value === undefined || value === '') return 'N/A';
        const num = Number(value);
        if (Number.isNaN(num)) return 'N/A';
        return num.toFixed(digits);
    }

    _renderStrategyStatusBadge(status) {
        const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.ADVISORY_ONLY;
        return `<span class="nd-status-badge ${cfg.cls}">${cfg.label}</span>`;
    }

    async _fetchAndRender(container) {
        try {
            const url = getApiUrl('/api/next-draw-summary?mode=direct&recent_count=500');
            const resp = await fetch(url, { method: 'GET' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this._lastData = data;
            this._render(container, data);
        } catch (err) {
            console.error('NextDraw fetch failed:', err);
            container.innerHTML = this._renderError(err.message);
        }
    }

    _renderLoading(container) {
        container.innerHTML = `
            <div class="next-draw-loading">
                <div class="loading-spinner"></div>
                <p>正在從 RSM Coordinator 生成預測…</p>
            </div>`;
    }

    _renderError(message) {
        return `
            <div class="next-draw-error">
                <span class="error-icon">⚠️</span>
                <p>無法載入預測：${message}</p>
                <button class="btn btn-sm" onclick="document.querySelector('[data-section=next-draw]')?.click()">重試</button>
            </div>`;
    }

    _render(container, data) {
        const ts = data.generated_at ? new Date(data.generated_at).toLocaleString('zh-TW') : '—';
        let html = `
            <div class="next-draw-header-bar">
                <span class="nd-generated-at">更新時間：${ts}</span>
                <button class="btn btn-sm btn-outline nd-refresh-btn" id="nd-refresh-btn">
                    <i data-lucide="refresh-cw" class="icon-xs"></i> 重新生成
                </button>
            </div>
            <div class="nd-games-grid">`;

        const order = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO'];
        for (const lt of order) {
            const game = data.games?.[lt];
            if (!game) continue;
            html += this._renderGameCard(lt, game);
        }
        html += `</div>`;

        container.innerHTML = html;

        // Bind refresh
        const refreshBtn = document.getElementById('nd-refresh-btn');
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.onRefresh());

        // Re-init lucide icons if available
        if (globalThis.lucide) globalThis.lucide.createIcons();
    }

    _renderGameCard(lt, game) {
        const gInfo = GAME_LABELS[lt] || { name: lt, icon: '🎲', pick: 6, pool: 49 };
        const gameStatus = STATUS_CONFIG[game.game_status] || STATUS_CONFIG.ERROR;

        const periodHtml = game.next_period
            ? `<span class="nd-period">第 <strong>${game.next_period}</strong> 期</span>`
            : '';

        const noteHtml = game.game_status_note
            ? `<div class="nd-game-note">${game.game_status_note}</div>`
            : '';

        const errorHtml = game.error
            ? `<div class="nd-game-error">⚠️ ${game.error}</div>`
            : '';

        const betsHtml = (game.bets || []).map(b => this._renderBetRow(b, gInfo)).join('');

        return `
            <div class="nd-game-card">
                <div class="nd-game-card-header">
                    <div class="nd-game-title">
                        <span class="nd-game-icon">${gInfo.icon}</span>
                        <span class="nd-game-name">${gInfo.name}</span>
                        ${periodHtml}
                    </div>
                    <span class="nd-status-badge ${gameStatus.cls}" title="${gameStatus.tip}">${gameStatus.label}</span>
                </div>
                ${noteHtml}
                ${errorHtml}
                <div class="nd-bets-list">
                    ${betsHtml || '<p class="nd-no-data">無可用預測</p>'}
                </div>
            </div>`;
    }

    _renderBetRow(bet, gInfo) {
        const stratStatus = STATUS_CONFIG[bet.strategy_status] || STATUS_CONFIG.ADVISORY_ONLY;
        const trendIcon = bet.trend === 'IMPROVING' ? '↑' : bet.trend === 'DECLINING' ? '↓' : '→';
        const alertIcon = bet.alert ? ' ⚠️' : '';
        // Only show trend meta if there is something meaningful to show
        const trendMeta = (trendIcon !== '→' || alertIcon) ? ` ${trendIcon}${alertIcon}` : alertIcon;

        // Render each bet line (numbers[0], numbers[1], ...)
        const betLinesHtml = (bet.numbers || []).map((nums, idx) => {
            const ballsHtml = nums.map(n =>
                `<span class="nd-ball">${String(n).padStart(2, '0')}</span>`
            ).join('');
            return `<div class="nd-bet-line">
                        <span class="nd-bet-idx">第 ${idx + 1} 注</span>
                        <div class="nd-balls">${ballsHtml}</div>
                    </div>`;
        }).join('');

        // Special number row — last line (威力彩 第二區)
        const specialRowHtml = Number(bet.special) > 0
            ? `<div class="nd-bet-line nd-special-row">
                   <span class="nd-bet-idx nd-special-hint">建議第二區號碼</span>
                   <div class="nd-balls"><span class="nd-ball nd-ball-special">${String(bet.special).padStart(2, '0')}</span></div>
               </div>`
            : '';

        return `
            <div class="nd-bet-row">
                <div class="nd-bet-meta">
                    <div class="nd-bet-meta-top">
                        <span class="nd-bet-count">${bet.bet_count} 注</span>
                        <span class="nd-strategy-label" title="${bet.strategy_key}">${bet.strategy_label}</span>
                    </div>
                    <div class="nd-bet-meta-bottom">
                        <span class="nd-status-badge nd-status-sm ${stratStatus.cls}" title="${stratStatus.tip}">${stratStatus.label}</span>
                        ${trendMeta ? `<span class="nd-edge">${trendMeta}</span>` : ''}
                    </div>
                </div>
                <div class="nd-bet-lines">
                    ${betLinesHtml}${specialRowHtml}
                </div>
            </div>`;
    }
}
