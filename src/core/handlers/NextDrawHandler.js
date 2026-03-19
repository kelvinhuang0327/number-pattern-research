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
        if (window.lucide) window.lucide.createIcons();
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
        const edgePct = bet.edge_300p != null ? (bet.edge_300p * 100).toFixed(2) : '—';
        const trendIcon = bet.trend === 'IMPROVING' ? '↑' : bet.trend === 'DECLINING' ? '↓' : '→';
        const alertIcon = bet.alert ? ' ⚠️' : '';

        // Render each bet line (numbers[0], numbers[1], ...)
        const betLinesHtml = (bet.numbers || []).map((nums, idx) => {
            const ballsHtml = nums.map(n =>
                `<span class="nd-ball">${String(n).padStart(2, '0')}</span>`
            ).join('');
            const specialHtml = (idx === 0 && bet.special != null)
                ? `<span class="nd-special-label">第二區</span><span class="nd-ball nd-ball-special">${String(bet.special).padStart(2, '0')}</span>`
                : '';
            return `<div class="nd-bet-line">
                        <span class="nd-bet-idx">第 ${idx + 1} 注</span>
                        <div class="nd-balls">${ballsHtml}${specialHtml}</div>
                    </div>`;
        }).join('');

        return `
            <div class="nd-bet-row">
                <div class="nd-bet-meta">
                    <div class="nd-bet-meta-top">
                        <span class="nd-bet-count">${bet.bet_count} 注</span>
                        <span class="nd-strategy-label" title="${bet.strategy_key}">${bet.strategy_label}</span>
                    </div>
                    <div class="nd-bet-meta-bottom">
                        <span class="nd-status-badge nd-status-sm ${stratStatus.cls}" title="${stratStatus.tip}">${stratStatus.label}</span>
                        <span class="nd-edge" title="300期 Edge">Edge ${edgePct}% ${trendIcon}${alertIcon}</span>
                    </div>
                </div>
                <div class="nd-bet-lines">
                    ${betLinesHtml}
                </div>
            </div>`;
    }
}
