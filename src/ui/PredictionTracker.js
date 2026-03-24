/**
 * PredictionTracker
 * 預測追蹤頁籤的所有 UI 邏輯
 */
export class PredictionTracker {
    constructor(app) {
        this.app = app;
        this._currentGame = 'BIG_LOTTO';
        this._histOffset = 0;
        this._histLimit = 20;
        this._histTotal = 0;
        this._perfData = [];
        this._setupListeners();
    }

    _setupListeners() {
        document.getElementById('pt-game-select')?.addEventListener('change', e => {
            this._currentGame = e.target.value;
            this._histOffset = 0;
            this.loadAll();
        });
        document.getElementById('pt-snapshot-btn')?.addEventListener('click', () => this.createSnapshot());
        document.getElementById('pt-resolve-btn')?.addEventListener('click', () => this.resolvePending());
        document.getElementById('pt-prev-btn')?.addEventListener('click', () => this._histPagePrev());
        document.getElementById('pt-next-btn')?.addEventListener('click', () => this._histPageNext());
    }

    async loadAll() {
        await Promise.all([this.loadPerformance(), this.loadHistory()]);
    }

    // ──────────── 快照 ────────────

    async createSnapshot() {
        const btn = document.getElementById('pt-snapshot-btn');
        if (btn) { btn.disabled = true; btn.textContent = '預測中…'; }
        try {
            const res = await fetch('/api/tracking/snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lottery_type: this._currentGame, num_bets: 3 }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '快照失敗');
            this.app?.uiManager?.showNotification(data.message || '快照已儲存', 'success');
            this._histOffset = 0;
            await this.loadAll();
        } catch (e) {
            this.app?.uiManager?.showNotification('快照失敗: ' + e.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🎯 產生預測快照'; }
        }
    }

    // ──────────── Resolve ────────────

    async resolvePending() {
        const btn = document.getElementById('pt-resolve-btn');
        if (btn) { btn.disabled = true; btn.textContent = '比對中…'; }
        try {
            const res = await fetch('/api/tracking/resolve', { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '比對失敗');
            const s = data.summary;
            this.app?.uiManager?.showNotification(
                `比對完成：解析 ${s.resolved} 筆，等待中 ${s.skipped} 筆`, 'success'
            );
            await this.loadAll();
        } catch (e) {
            this.app?.uiManager?.showNotification('比對失敗: ' + e.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🔄 比對待解析預測'; }
        }
    }

    // ──────────── 表現統計 ────────────

    async loadPerformance() {
        const el = document.getElementById('pt-perf-body');
        if (!el) return;
        el.innerHTML = '<tr><td colspan="8" style="text-align:center">載入中…</td></tr>';
        try {
            const res = await fetch(`/api/tracking/performance?lottery_type=${this._currentGame}`);
            const data = await res.json();
            this._perfData = data.performance || [];
            this._renderPerformance();
        } catch (e) {
            el.innerHTML = `<tr><td colspan="8">載入失敗: ${e.message}</td></tr>`;
        }
    }

    _renderPerformance() {
        const el = document.getElementById('pt-perf-body');
        if (!el) return;
        if (!this._perfData.length) {
            el.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888">尚無資料</td></tr>';
            return;
        }
        el.innerHTML = this._perfData.map(p => {
            const all = p.all;
            const r30 = p.recent_30;
            const pct = v => (v * 100).toFixed(1) + '%';
            return `<tr>
                <td>${this._stratLabel(p.strategy_name)}</td>
                <td>${p.total_bets}</td>
                <td>${p.resolved_bets}</td>
                <td>${pct(all.hit1 || 0)}</td>
                <td>${pct(all.hit2 || 0)}</td>
                <td class="${(all.hit3||0) > 0.05 ? 'pt-good' : ''}">${pct(all.hit3 || 0)}</td>
                <td>${(all.avg_hit || 0).toFixed(2)}</td>
                <td style="color:${(r30.hit3||0) > (all.hit3||0) ? '#27ae60' : '#e74c3c'}">${pct(r30.hit3 || 0)}</td>
            </tr>`;
        }).join('');
    }

    // ──────────── 歷史清單 ────────────

    async loadHistory() {
        const tbody = document.getElementById('pt-hist-body');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center">載入中…</td></tr>';
        try {
            const url = `/api/tracking/history?lottery_type=${this._currentGame}&limit=${this._histLimit}&offset=${this._histOffset}`;
            const res = await fetch(url);
            const data = await res.json();
            this._histTotal = data.total || 0;
            this._renderHistory(data.runs || []);
            this._updateHistPagination();
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7">載入失敗: ${e.message}</td></tr>`;
        }
    }

    _renderHistory(runs) {
        const tbody = document.getElementById('pt-hist-body');
        if (!tbody) return;
        if (!runs.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888">尚無預測記錄</td></tr>';
            return;
        }
        tbody.innerHTML = runs.map(r => {
            const statusBadge = r.status === 'RESOLVED'
                ? `<span class="pt-badge pt-resolved">已比對</span>`
                : `<span class="pt-badge pt-pending">待比對</span>`;
            const hitCell = r.best_hit != null
                ? `<span class="${r.best_hit >= 3 ? 'pt-hit-good' : r.best_hit >= 1 ? 'pt-hit-ok' : 'pt-hit-bad'}">${r.best_hit} 中</span>`
                : '—';
            const createdAt = new Date(r.created_at + 'Z').toLocaleString('zh-TW', {
                month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
            });
            return `<tr class="pt-hist-row" data-run-id="${r.run_id}" style="cursor:pointer">
                <td>${createdAt}</td>
                <td>${r.latest_known_draw}</td>
                <td>${r.actual_draw || '—'}</td>
                <td>${this._stratLabel(r.strategy_name)}</td>
                <td>${r.total_bets} 注</td>
                <td>${hitCell}</td>
                <td>${statusBadge}</td>
            </tr>
            <tr class="pt-detail-row" id="pt-detail-${r.run_id}" style="display:none">
                <td colspan="7" style="padding:0">
                    <div class="pt-detail-loading" style="padding:8px;color:#888">點擊展開</div>
                </td>
            </tr>`;
        }).join('');

        // 點擊展開
        tbody.querySelectorAll('.pt-hist-row').forEach(row => {
            row.addEventListener('click', () => this._toggleDetail(Number(row.dataset.runId)));
        });
    }

    async _toggleDetail(runId) {
        const detailRow = document.getElementById(`pt-detail-${runId}`);
        if (!detailRow) return;
        if (detailRow.style.display !== 'none') {
            detailRow.style.display = 'none';
            return;
        }
        detailRow.style.display = '';
        const cell = detailRow.querySelector('td');
        cell.innerHTML = '<div style="padding:8px;color:#888">載入中…</div>';
        try {
            const res = await fetch(`/api/tracking/run/${runId}`);
            const data = await res.json();
            cell.innerHTML = this._renderDetail(data);
        } catch (e) {
            cell.innerHTML = `<div style="padding:8px;color:red">載入失敗: ${e.message}</div>`;
        }
    }

    _renderDetail(detail) {
        if (!detail) return '<div style="padding:8px">無資料</div>';
        const betsHtml = detail.bets.map((bet, i) => {
            const predicted = bet.predicted_numbers || [];
            const matched = new Set(bet.matched_numbers || []);
            const actual = bet.actual_numbers || [];

            const predNumsHtml = predicted.map(n =>
                `<span class="pt-num ${matched.has(n) ? 'pt-num-match' : ''}">${n}</span>`
            ).join('');
            const actualNumsHtml = actual.map(n =>
                `<span class="pt-num ${matched.has(n) ? 'pt-num-match' : 'pt-num-actual'}">${n}</span>`
            ).join('');

            const hitLabel = bet.hit_count != null
                ? `命中 <strong>${bet.hit_count}</strong> 個 ${bet.special_hit ? '+ 特別號 ✓' : ''}`
                : '待比對';

            return `<div class="pt-bet-row">
                <div class="pt-bet-label">注 ${i + 1}</div>
                <div>
                    <div class="pt-nums-line">預測：${predNumsHtml}${bet.predicted_special != null ? `<span class="pt-num pt-special">★${bet.predicted_special}</span>` : ''}</div>
                    ${actual.length ? `<div class="pt-nums-line">實際：${actualNumsHtml}${bet.actual_special != null ? `<span class="pt-num pt-actual-special">★${bet.actual_special}</span>` : ''}</div>` : ''}
                    <div class="pt-hit-summary">${hitLabel}</div>
                </div>
            </div>`;
        }).join('');

        return `<div class="pt-detail-panel">
            <div class="pt-detail-meta">
                策略：<strong>${this._stratLabel(detail.strategy_name)}</strong>
                　預測時基於：<strong>第 ${detail.latest_known_draw} 期</strong>
                ${detail.bets[0]?.actual_draw ? `　比對期：<strong>第 ${detail.bets[0].actual_draw} 期</strong>` : ''}
            </div>
            <div class="pt-bets-list">${betsHtml}</div>
        </div>`;
    }

    _updateHistPagination() {
        const info = document.getElementById('pt-page-info');
        const prev = document.getElementById('pt-prev-btn');
        const next = document.getElementById('pt-next-btn');
        const page = Math.floor(this._histOffset / this._histLimit) + 1;
        const totalPages = Math.ceil(this._histTotal / this._histLimit) || 1;
        if (info) info.textContent = `第 ${page} / ${totalPages} 頁（共 ${this._histTotal} 筆）`;
        if (prev) prev.disabled = this._histOffset <= 0;
        if (next) next.disabled = this._histOffset + this._histLimit >= this._histTotal;
    }

    _histPagePrev() {
        if (this._histOffset <= 0) return;
        this._histOffset = Math.max(0, this._histOffset - this._histLimit);
        this.loadHistory();
    }

    _histPageNext() {
        if (this._histOffset + this._histLimit >= this._histTotal) return;
        this._histOffset += this._histLimit;
        this.loadHistory();
    }

    _stratLabel(name) {
        if (!name) return '—';
        return name.replace(/_/g, ' ');
    }
}
