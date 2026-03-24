/**
 * PredictionTracker
 * 預測追蹤頁籤的所有 UI 邏輯（含排程狀態 + 正式/重建績效篩選）
 */
import { getApiUrl } from '../config/apiConfig.js';

export class PredictionTracker {
    constructor(app) {
        this.app = app;
        this._currentGame = 'BIG_LOTTO';
        this._histOffset = 0;
        this._histLimit = 20;
        this._histTotal = 0;
        this._perfData = [];
        this._validOnly = true;        // 正式績效篩選（只計 VALID）
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
        document.getElementById('pt-startup-btn')?.addEventListener('click', () => this.runStartupCheck());
        document.getElementById('pt-prev-btn')?.addEventListener('click', () => this._histPagePrev());
        document.getElementById('pt-next-btn')?.addEventListener('click', () => this._histPageNext());
        document.getElementById('pt-valid-toggle')?.addEventListener('change', e => {
            this._validOnly = e.target.checked;
            this.loadPerformance();
        });
    }

    async loadAll() {
        await Promise.all([
            this.loadScheduleStatus(),
            this.loadPerformance(),
            this.loadHistory(),
            this.loadScheduleHistory(),
        ]);
    }

    // ──────────── 排程狀態 ────────────

    async loadScheduleStatus() {
        const el = document.getElementById('pt-schedule-status');
        if (!el) return;
        try {
            const res = await fetch(getApiUrl('/api/tracking/schedule/status'));
            const data = await res.json();
            el.innerHTML = (data.schedules || []).map(s => this._renderScheduleCard(s)).join('');
        } catch (e) {
            el.innerHTML = `<div style="color:red">排程狀態載入失敗: ${e.message}</div>`;
        }
    }

    _renderScheduleCard(s) {
        const gameLabel = { BIG_LOTTO: '大樂透', POWER_LOTTO: '威力彩', DAILY_539: '今彩539' };
        const sched = s.schedule;
        let statusHtml = '';
        if (!sched) {
            statusHtml = `<span class="pt-badge pt-sched-none">無排程</span>`;
        } else if (sched.status === 'SCHEDULED') {
            statusHtml = `<span class="pt-badge pt-sched-scheduled">已排程</span>`;
        } else if (sched.status === 'SNAPSHOT_CREATED') {
            statusHtml = `<span class="pt-badge pt-sched-ok">✅ 快照已建立</span>`;
        } else if (sched.status === 'MISSED_WINDOW') {
            statusHtml = `<span class="pt-badge pt-sched-missed">⚠️ 缺漏</span>`;
        } else if (sched.status === 'RECONSTRUCTED') {
            statusHtml = `<span class="pt-badge pt-sched-recon">🧪 已重建</span>`;
        }
        return `<div class="pt-sched-card">
            <div class="pt-sched-game">${gameLabel[s.lottery_type] || s.lottery_type}</div>
            <div class="pt-sched-info">最新期：<strong>${s.latest_known_draw || '—'}</strong></div>
            <div class="pt-sched-info">下一期：<strong>${s.next_expected_draw || '—'}</strong></div>
            <div>${statusHtml}</div>
        </div>`;
    }

    async loadScheduleHistory() {
        const el = document.getElementById('pt-sched-hist-body');
        if (!el) return;
        try {
            const url = getApiUrl(`/api/tracking/schedule/history?lottery_type=${this._currentGame}&limit=20`);
            const res = await fetch(url);
            const data = await res.json();
            const schedules = data.schedules || [];
            if (!schedules.length) {
                el.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#888">尚無排程記錄</td></tr>';
                return;
            }
            el.innerHTML = schedules.map(s => {
                const statusMap = {
                    SCHEDULED: '<span class="pt-badge pt-sched-scheduled">已排程</span>',
                    SNAPSHOT_CREATED: '<span class="pt-badge pt-sched-ok">✅ 已快照</span>',
                    MISSED_WINDOW: '<span class="pt-badge pt-sched-missed">⚠️ 缺漏</span>',
                    RECONSTRUCTED: '<span class="pt-badge pt-sched-recon">🧪 重建</span>',
                };
                const schedAt = new Date((s.scheduled_at || '').replace(' ', 'T') + 'Z').toLocaleString('zh-TW', {
                    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
                });
                const rebuildBtn = s.status === 'MISSED_WINDOW' && !s.run_id
                    ? `<button class="btn btn-xs btn-secondary pt-rebuild-btn" data-sched-id="${s.id}">🧪 重建</button>`
                    : '';
                return `<tr>
                    <td>${s.target_draw}</td>
                    <td>${s.target_date || '—'}</td>
                    <td>${schedAt}</td>
                    <td>${statusMap[s.status] || s.status}</td>
                    <td>${s.run_id ? `run#${s.run_id}` : '—'} ${rebuildBtn}</td>
                </tr>`;
            }).join('');

            // 重建按鈕事件
            el.querySelectorAll('.pt-rebuild-btn').forEach(btn => {
                btn.addEventListener('click', () => this._rebuildSchedule(Number(btn.dataset.schedId)));
            });
        } catch (e) {
            el.innerHTML = `<tr><td colspan="5">載入失敗: ${e.message}</td></tr>`;
        }
    }

    async _rebuildSchedule(scheduleId) {
        if (!confirm(`確定要重建排程 #${scheduleId} 的預測快照？\n此快照將標記為 RECONSTRUCTED，不計入正式績效。`)) return;
        try {
            const res = await fetch(getApiUrl(`/api/tracking/schedule/generate/${scheduleId}?source=RECONSTRUCTED`), { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '重建失敗');
            this.app?.uiManager?.showNotification(data.message || '🧪 重建完成', 'info');
            await this.loadAll();
        } catch (e) {
            this.app?.uiManager?.showNotification('重建失敗: ' + e.message, 'error');
        }
    }

    // ──────────── 啟動補全 ────────────

    async runStartupCheck() {
        const btn = document.getElementById('pt-startup-btn');
        if (btn) { btn.disabled = true; btn.textContent = '執行中…'; }
        try {
            const res = await fetch(getApiUrl('/api/tracking/schedule/startup'), { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '執行失敗');
            const msgs = Object.entries(data.summary || {}).map(([g, r]) =>
                `${g}: ${r.action || r.status || JSON.stringify(r)}`
            );
            this.app?.uiManager?.showNotification('補全完成\n' + msgs.join(' | '), 'success');
            await this.loadAll();
        } catch (e) {
            this.app?.uiManager?.showNotification('補全失敗: ' + e.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🚀 啟動補全'; }
        }
    }

    // ──────────── 快照 ────────────

    async createSnapshot() {
        const btn = document.getElementById('pt-snapshot-btn');
        if (btn) { btn.disabled = true; btn.textContent = '預測中…'; }
        try {
            const res = await fetch(getApiUrl('/api/tracking/snapshot'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lottery_type: this._currentGame, num_bets: 3 }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '快照失敗');
            const notifType = data.snapshot_source === 'RECONSTRUCTED' ? 'warning' : 'success';
            this.app?.uiManager?.showNotification(data.warning || data.message || '快照已儲存', notifType);
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
            const res = await fetch(getApiUrl('/api/tracking/resolve'), { method: 'POST' });
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
        const filterLabel = document.getElementById('pt-perf-filter-label');
        el.innerHTML = '<tr><td colspan="8" style="text-align:center">載入中…</td></tr>';
        try {
            const url = getApiUrl(`/api/tracking/performance?lottery_type=${this._currentGame}&valid_only=${this._validOnly}`);
            const res = await fetch(url);
            const data = await res.json();
            this._perfData = data.performance || [];
            if (filterLabel) {
                filterLabel.textContent = this._validOnly ? '（僅計正式快照）' : '（含重建快照）';
                filterLabel.style.color = this._validOnly ? '#27ae60' : '#e67e22';
            }
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
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">載入中…</td></tr>';
        try {
            const url = getApiUrl(`/api/tracking/history?lottery_type=${this._currentGame}&limit=${this._histLimit}&offset=${this._histOffset}`);
            const res = await fetch(url);
            const data = await res.json();
            this._histTotal = data.total || 0;
            this._renderHistory(data.runs || []);
            this._updateHistPagination();
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8">載入失敗: ${e.message}</td></tr>`;
        }
    }

    _renderHistory(runs) {
        const tbody = document.getElementById('pt-hist-body');
        if (!tbody) return;
        if (!runs.length) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888">尚無預測記錄</td></tr>';
            return;
        }
        tbody.innerHTML = runs.map(r => {
            const statusBadge = r.status === 'RESOLVED'
                ? `<span class="pt-badge pt-resolved">已比對</span>`
                : `<span class="pt-badge pt-pending">待比對</span>`;
            const sourceBadge = r.snapshot_source === 'RECONSTRUCTED'
                ? `<span class="pt-badge pt-sched-recon" title="開獎後補建，不計入正式績效">🧪</span>`
                : r.snapshot_source === 'MANUAL'
                    ? `<span class="pt-badge pt-sched-scheduled" title="手動建立">手動</span>`
                    : `<span class="pt-badge pt-sched-ok" title="開獎前正式預測">✅</span>`;
            const hitCell = r.best_hit != null
                ? `<span class="${r.best_hit >= 3 ? 'pt-hit-good' : r.best_hit >= 1 ? 'pt-hit-ok' : 'pt-hit-bad'}">${r.best_hit} 中</span>`
                : '—';
            const createdAt = new Date((r.created_at || '').replace(' ', 'T') + 'Z').toLocaleString('zh-TW', {
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
                <td>${sourceBadge}</td>
            </tr>
            <tr class="pt-detail-row" id="pt-detail-${r.run_id}" style="display:none">
                <td colspan="8" style="padding:0"></td>
            </tr>`;
        }).join('');

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
            const res = await fetch(getApiUrl(`/api/tracking/run/${runId}`));
            const data = await res.json();
            this._renderDetailInCell(cell, data, runId);
        } catch (e) {
            cell.innerHTML = `<div style="padding:8px;color:red">載入失敗: ${e.message}</div>`;
        }
    }

    _renderDetailInCell(cell, data, runId) {
        cell.innerHTML = this._renderDetail(data);
        cell.querySelectorAll('.pt-researched-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const itemId = Number(btn.dataset.itemId);
                const current = btn.dataset.current;
                const newVal = current === '有' ? '無' : '有';
                btn.disabled = true;
                try {
                    const r = await fetch(
                        getApiUrl(`/api/tracking/result/${itemId}/researched?value=${encodeURIComponent(newVal)}`),
                        { method: 'PATCH' }
                    );
                    if (!r.ok) throw new Error((await r.json()).detail || '更新失敗');
                    const r2 = await fetch(getApiUrl(`/api/tracking/run/${runId}`));
                    this._renderDetailInCell(cell, await r2.json(), runId);
                } catch (e) {
                    this.app?.uiManager?.showNotification('更新失敗: ' + e.message, 'error');
                    btn.disabled = false;
                }
            });
        });
    }

    _renderDetail(detail) {
        if (!detail) return '<div style="padding:8px">無資料</div>';
        const sourceWarning = detail.snapshot_source === 'RECONSTRUCTED'
            ? `<div class="pt-recon-warning">🧪 此預測為開獎後重建（RECONSTRUCTED），不計入正式績效</div>`
            : '';
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
            const researched = bet.researched || '無';
            const researchedBadge = researched === '有'
                ? `<span class="pt-badge pt-researched-yes">已研究特徵</span>`
                : `<span class="pt-badge pt-researched-no">未研究</span>`;
            const toggleLabel = researched === '有' ? '取消研究' : '標記已研究';
            const researchedBtn = bet.status === 'RESOLVED'
                ? `<button class="btn btn-xs btn-secondary pt-researched-btn" style="margin-left:6px;font-size:11px" data-item-id="${bet.item_id}" data-current="${researched}">${toggleLabel}</button>`
                : '';
            return `<div class="pt-bet-row">
                <div class="pt-bet-label">注 ${i + 1}</div>
                <div>
                    <div class="pt-nums-line">預測：${predNumsHtml}${bet.predicted_special != null ? `<span class="pt-num pt-special">★${bet.predicted_special}</span>` : ''}</div>
                    ${actual.length ? `<div class="pt-nums-line">實際：${actualNumsHtml}${bet.actual_special != null ? `<span class="pt-num pt-actual-special">★${bet.actual_special}</span>` : ''}</div>` : ''}
                    <div class="pt-hit-summary">${hitLabel} &nbsp; ${researchedBadge}${researchedBtn}</div>
                </div>
            </div>`;
        }).join('');
        return `<div class="pt-detail-panel">
            ${sourceWarning}
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
