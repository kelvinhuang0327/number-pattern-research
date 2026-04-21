/**
 * PredictionTracker
 * 預測追蹤頁籤的所有 UI 邏輯（含排程狀態 + 正式/重建績效篩選）
 */
import { getApiUrl } from '../config/apiConfig.js';
import { renderExplainabilityBlock } from './components/ExplainabilityRenderer.js';

export class PredictionTracker {
    constructor(app) {
        this.app = app;
        this._currentGame = 'BIG_LOTTO';
        this._histOffset = 0;
        this._histLimit = 20;
        this._histTotal = 0;
        this._perfData = [];
        this._perfSummary = null;
        this._validOnly = true;        // 正式績效篩選（只計 VALID）
        this._setupListeners();
    }

    _hasSpecialNumber(value) {
        const num = Number(value);
        return Number.isInteger(num) && num > 0;
    }

    _resolveBetCount(record) {
        const candidates = [record?.num_bets, record?.avg_bets, record?.bet_count, record?.n_bets];
        for (const candidate of candidates) {
            const num = Number(candidate);
            if (Number.isFinite(num)) return num;
        }
        return null;
    }

    _setupListeners() {
        // 同步頂部全局彩種切換
        document.getElementById('lottery-type-filter')?.addEventListener('change', e => {
            this._setGame(e.target.value);
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

    _setGame(type) {
        if (!type || type === this._currentGame) return;
        this._currentGame = type;
        this._histOffset = 0;
        this._updateGameLabel();
        const trackingSection = document.getElementById('tracking-section');
        if (trackingSection?.classList.contains('active')) {
            this.loadAll();
        }
    }

    _updateGameLabel() {
        const label = document.getElementById('pt-current-game-label');
        if (!label) return;
        const map = { BIG_LOTTO: '大樂透', POWER_LOTTO: '威力彩', DAILY_539: '今彩539' };
        label.textContent = map[this._currentGame] || this._currentGame;
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
        const latestDate = s.latest_known_date ? ` <span class="pt-draw-date">${s.latest_known_date}</span>` : '';
        const nextDate = s.next_expected_date ? ` <span class="pt-draw-date">${s.next_expected_date}</span>` : '';
        return `<div class="pt-sched-card">
            <div class="pt-sched-game">${gameLabel[s.lottery_type] || s.lottery_type}</div>
            <div class="pt-sched-info">最新期：<strong>${s.latest_known_draw || '—'}</strong>${latestDate}</div>
            <div class="pt-sched-info">下一期：<strong>${s.next_expected_draw || '—'}</strong>${nextDate}</div>
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
                body: JSON.stringify({ lottery_type: this._currentGame }),
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
        el.innerHTML = '<tr><td colspan="10" style="text-align:center">載入中…</td></tr>';
        try {
            const url = getApiUrl(`/api/tracking/performance?lottery_type=${this._currentGame}&valid_only=${this._validOnly}`);
            const res = await fetch(url);
            const data = await res.json();
            this._perfData = data.performance || [];
            this._perfSummary = this._perfData.find(p => this._resolveBetCount(p) === 1) || null;
            if (filterLabel) {
                const gameLabel = { BIG_LOTTO: '大樂透', POWER_LOTTO: '威力彩', DAILY_539: '今彩539' };
                filterLabel.textContent = `${gameLabel[this._currentGame] || this._currentGame} · ${this._validOnly ? '僅計正式快照' : '含重建快照'}`;
                filterLabel.style.color = this._validOnly ? '#27ae60' : '#e67e22';
            }
            this._renderPerformance();
        } catch (e) {
            el.innerHTML = `<tr><td colspan="10">載入失敗: ${e.message}</td></tr>`;
        }
    }

    _edgeColor(value) {
        if (value == null) return '#888';
        if (value > 0) return '#27ae60';
        if (value < 0) return '#e74c3c';
        return '#888';
    }

    _formatSignedPct(value) {
        if (value == null) return 'N/A';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${(value * 100).toFixed(1)}%`;
    }

    _renderAvailabilityBadge(availability, compact = false) {
        if (availability === 'NO_HISTORY') {
            return compact
                ? '<span class="pt-state-badge pt-state-na">無歷史快照</span>'
                : '<div class="pt-detail-small" style="color:#e67e22">無歷史快照</div>';
        }
        if (availability === 'N/A') {
            return compact
                ? '<span class="pt-state-badge pt-state-na">N/A</span>'
                : '<div class="pt-detail-small" style="color:#888">N/A</div>';
        }
        return compact
            ? '<span class="pt-state-badge pt-state-resolved">已收錄</span>'
            : `<div class="pt-detail-small">${this._renderStrategyStatusBadge(availability)}</div>`;
    }

    _renderPerformanceRow(p, pct) {
        const edge = this._formatSignedPct(p.edge);
        const strategyName = p.strategy_name ? this._stratLabel(p.strategy_name) : 'N/A';
        const availability = this._renderAvailabilityBadge(p.availability, false);
        const successRate = p.success_rate == null ? 'N/A' : pct(p.success_rate);
        const baseline = p.baseline == null ? 'N/A' : pct(p.baseline);
        const edgeValue = p.edge == null ? 'N/A' : edge;

        return `<tr>
                <td>${this._resolveBetCount(p) ?? '—'}</td>
                <td style="text-align:left">
                    <div style="font-weight:600">${strategyName}</div>
                    ${availability}
                </td>
                <td>${this._renderStrategyStatusBadge(p.strategy_status)} ${this._renderValidatedBadge(p.validated_status, p.data_complete)}</td>
                <td>${p.resolved_runs ?? 0}</td>
                <td><strong>${p.success_count ?? 0}</strong></td>
                <td class="pt-good">${successRate}</td>
                <td style="color:#888">${baseline}</td>
                <td style="color:${this._edgeColor(p.edge)};font-weight:600">${edgeValue}</td>
                <td>${p.avg_bets ?? '—'}</td>
                <td style="color:${p.pending_runs > 0 ? '#e67e22' : '#888'}">${p.pending_runs ?? 0}</td>
            </tr>`;
    }

    _renderHistoryRow(r, gameLabel, fmtStateBadge) {
        const summary = r.single_bet_summary || null;
        const latestKnownDraw = r.latest_known_draw;
        let period = '—';
        if (summary?.actual_draw) {
            period = summary.actual_draw;
        } else if (Number(latestKnownDraw)) {
            period = String(Number(latestKnownDraw) + 1);
        } else if (latestKnownDraw) {
            period = latestKnownDraw;
        }

        let drawDate = '—';
        if (summary?.actual_date) {
            drawDate = summary.actual_date.slice(0, 10);
        } else if (r.latest_known_date) {
            drawDate = `(${r.latest_known_date.slice(0, 10)})`;
        }
        const strategyName = summary?.strategy_name ? this._stratLabel(summary.strategy_name) : 'N/A';
        const strategyStatus = summary?.strategy_status ? this._renderStrategyStatusBadge(summary.strategy_status) : this._renderStrategyStatusBadge('N/A');
        const snapshotState = summary?.snapshot_state ? fmtStateBadge(summary.snapshot_state) : fmtStateBadge(r.status);
        const predictedNums = summary?.predicted_numbers || [];
        const matchedNums = summary?.matched_numbers || [];
        const actualNums = summary?.actual_numbers || [];
        const predSpecial = summary?.predicted_special ?? null;
        const actualSpecial = summary?.actual_special ?? null;
        const specialHit = this._hasSpecialNumber(predSpecial) && this._hasSpecialNumber(actualSpecial) && Number(predSpecial) === Number(actualSpecial);
        const predBalls = this._renderNumberBalls(predictedNums, new Set(matchedNums));
        const predSpecialHtml = this._renderSpecialNumberBadge(predSpecial, specialHit);
        const actualBalls = this._renderActualNumberBalls(actualNums, actualSpecial);
        const hitCell = this._renderBestHitCell(summary, specialHit);
        const isReviewed = r.review_status === 'REVIEWED' || r.review_status === 'RESOLVED' || r.analyzed === '已研究';
        const reviewBadge = isReviewed ? '<span class="pt-review-badge" title="已完成 LLM Research Board 檢討">📋</span>' : '';
        const reviewStatusHtml = isReviewed
            ? `<span class="pt-badge pt-researched-yes">已檢討 ✅</span>
                   <a href="/reviews?prediction_run_id=${r.run_id}" class="pt-review-link" data-run-id="${r.run_id}">查看檢討 →</a>`
            : '<span class="pt-badge pt-researched-no">未檢討</span>';
        const wqBadge = this._renderWqBadge(r);

        return `<tr class="pt-hist-row" data-run-id="${r.run_id}" style="cursor:pointer">
                <td>${gameLabel[r.lottery_type] || r.lottery_type}</td>
                <td style="font-size:12px;color:#8b949e;white-space:nowrap">${drawDate}</td>
                <td>${period}</td>
                <td style="text-align:left">
                    <div style="font-weight:600">${strategyName}</div>
                    <div class="pt-detail-small" style="margin-top:2px">${strategyStatus}</div>
                </td>
                <td style="text-align:left">${predBalls}${predSpecialHtml}</td>
                <td style="text-align:left">${actualBalls}</td>
                <td>${hitCell} ${reviewBadge}</td>
                <td>${reviewStatusHtml} ${wqBadge}</td>
                <td>${snapshotState}</td>
            </tr>
            <tr class="pt-detail-row" id="pt-detail-${r.run_id}" style="display:none">
                <td colspan="9" style="padding:0"></td>
            </tr>`;
    }

    _renderSpecialNumberBadge(special, specialHit) {
        if (!this._hasSpecialNumber(special)) return '';
        return ` <span class="pt-num ${specialHit ? 'pt-num-match' : 'pt-special'}">★${special}</span>`;
    }

    _renderBestHitCell(summary, specialHit) {
        if (summary?.best_hit == null) return '—';
        let hitClass = 'pt-hit-bad';
        if (summary.best_hit >= 3) hitClass = 'pt-hit-good';
        else if (summary.best_hit >= 1) hitClass = 'pt-hit-ok';
        const specialSuffix = specialHit ? '+★' : '';
        return `<span class="${hitClass}">${summary.best_hit} 中${specialSuffix}</span>`;
    }

    _renderWqBadge(r) {
        if (!r.split_risk) return '';
        let riskColor = '#e5c07b';
        if (r.split_risk === 'LOW') riskColor = '#3fb950';
        else if (r.split_risk === 'HIGH') riskColor = '#e06c75';
        return `<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:${riskColor}22;color:${riskColor};border:1px solid ${riskColor}44" title="WQ分獎風險 score=${r.wq_score}">${r.split_risk}</span>`;
    }

    _renderReviewVerdictClass(verdict) {
        if (verdict === '晉級') return 'pt-hit-good';
        if (verdict === '淘汰') return 'pt-hit-bad';
        return 'pt-hit-ok';
    }

    _renderGatePassColor(verdict) {
        if (verdict === 'WATCH') return '#e5c07b';
        if (verdict === 'REJECT') return '#e06c75';
        return '#98c379';
    }

    _renderCounterSeverityColor(severity) {
        if (severity === 'HIGH') return '#e06c75';
        if (severity === 'MED') return '#e5c07b';
        return '#8b949e';
    }

    _renderReviewFooter(detail, userReview) {
        if (!detail.review_date) return '';
        const reviewStatus = userReview ? ` | 審核: ${this._escHtml(userReview.status)}` : '';
        return `<div class="pt-review-footer">檢討日期: ${this._escHtml(detail.review_date)} | 版本: ${this._escHtml(detail.version || '—')}${reviewStatus}</div>`;
    }

    _renderWqRecommendation(wq) {
        if (!wq.recommendation) return '';
        return `<div class="pt-review-wq-rec">${this._escHtml(wq.recommendation)}</div>`;
    }

    _renderReviewUserNotes(userReview) {
        if (!userReview) return '';
        const notes = (userReview.supplementary_notes || []).map(n => `<div class="pt-review-counter">
                        <span class="pt-review-action-pri pt-review-pri-${(n.priority || 'p2').toLowerCase()}">${this._escHtml(n.priority || '')}</span>
                        <strong>${this._escHtml(n.topic || '')}</strong>: ${this._escHtml(n.note || '')}
                        ${n.trigger ? `<span style="font-size:10px;color:#7d8590;margin-left:4px">[trigger: ${this._escHtml(n.trigger)}]</span>` : ''}
                    </div>`).join('');
        return `<div class="pt-review-section">
                    <div class="pt-review-section-title">✅ 用戶審核 (${this._escHtml(userReview.date || '')})</div>
                    ${notes}
                </div>`;
    }

    _renderStrategySlotHitClass(bestHit) {
        if (bestHit >= 3) return 'pt-hit-good';
        if (bestHit >= 1) return 'pt-hit-ok';
        return 'pt-hit-bad';
    }

    _renderStrategySlotAvailability(snapshotState) {
        if (snapshotState === '無歷史快照') {
            return '<div class="pt-detail-small" style="color:#e67e22;margin-top:4px">無歷史快照</div>';
        }
        if (snapshotState === 'N/A') {
            return '<div class="pt-detail-small" style="color:#888;margin-top:4px">N/A</div>';
        }
        return '';
    }

    _renderStrategySlotSpecial(lotteryType, runPredSpecial, slotActualSpecial, betSpecialHit) {
        if (lotteryType !== 'POWER_LOTTO' || !this._hasSpecialNumber(runPredSpecial)) return '';
        return ` <span class="pt-num ${betSpecialHit ? 'pt-num-match' : 'pt-special'}">★${runPredSpecial}</span>`;
    }

    _renderStrategySlotHitText(mainHit, betSpecialHit, blSpHit) {
        if (mainHit == null) return '';
        const suffix = (betSpecialHit || blSpHit) ? '+★' : '';
        return `<span style="font-size:11px;color:#888;margin-left:8px">命中 ${mainHit}${suffix}</span>`;
    }

    _renderStrategySlotRows(bets, lotteryType, actualSet, slotActualSpecial, runPredSpecial) {
        return bets.map((bet, idx) => {
            const predicted = this._renderNumberBalls(
                bet.predicted_numbers || [], actualSet,
                lotteryType === 'BIG_LOTTO' && this._hasSpecialNumber(slotActualSpecial) ? slotActualSpecial : null
            );
            const betSpecialHit = this._hasSpecialNumber(runPredSpecial) && this._hasSpecialNumber(slotActualSpecial)
                && Number(runPredSpecial) === Number(slotActualSpecial);
            const special = this._renderStrategySlotSpecial(lotteryType, runPredSpecial, slotActualSpecial, betSpecialHit);
            const mainHit = bet.hit_count === null || bet.hit_count === undefined ? null : bet.hit_count;
            const blSpHit = lotteryType === 'BIG_LOTTO' && this._hasSpecialNumber(slotActualSpecial)
                && (bet.predicted_numbers || []).includes(slotActualSpecial);
            const perBetHit = this._renderStrategySlotHitText(mainHit, betSpecialHit, blSpHit);
            const rowStyle = bets.length > 1 ? 'border-bottom:1px solid #21262d;padding:4px 0' : '';
            const label = bets.length > 1 ? `<span style="font-size:11px;color:#7d8590;min-width:16px">注${idx + 1}</span>` : '';
            return `<div class="pt-bet-nums-row" style="${rowStyle}">
                ${label}
                ${predicted}${special}${perBetHit}
            </div>`;
        }).join('');
    }

    _renderPerformance() {
        const el = document.getElementById('pt-perf-body');
        if (!el) return;
        const summaryEl = document.getElementById('pt-perf-summary');
        if (!this._perfData.length) {
            if (summaryEl) summaryEl.innerHTML = '';
            el.innerHTML = '<tr><td colspan="10" style="text-align:center;color:#888">尚無成功記錄（正式快照尚未累積）</td></tr>';
            return;
        }
        const pct = v => v == null ? 'N/A' : (v * 100).toFixed(1) + '%';
        const summary = this._perfSummary || null;
        const summaryStrategy = summary?.strategy_name ? this._stratLabel(summary.strategy_name) : 'N/A';
        const summaryStatus = summary?.strategy_status ? this._renderStrategyStatusBadge(summary.strategy_status) : this._renderStrategyStatusBadge('N/A');
        const summaryValidatedBadge = this._renderValidatedBadge(summary?.validated_status, summary?.data_complete);
        const summaryAvailability = this._renderAvailabilityBadge(summary?.availability, true);
        const summaryEdge = this._formatSignedPct(summary?.edge);
        const summaryNotice = summary
            ? ''
            : `<div class="pt-detail-small" style="color:#e67e22;margin-top:8px">目前此彩種尚無正式單注策略，主摘要僅保留正式單注位置，不會以其他注數替代。</div>`;
        const summaryBlock = `
            <div class="pt-perf-summary">
                <div class="pt-perf-summary-head">
                    <div>
                        <div class="pt-perf-summary-kicker">主摘要</div>
                        <div class="pt-perf-summary-title">${summaryStrategy}</div>
                    </div>
                    <div style="margin-left:auto;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
                        ${summaryStatus}
                        ${summaryValidatedBadge}
                        ${summaryAvailability}
                    </div>
                </div>
                <div class="pt-perf-summary-grid">
                    <div><span class="pt-perf-summary-label">注數</span><strong>${this._resolveBetCount(summary) ?? 'N/A'}</strong></div>
                    <div><span class="pt-perf-summary-label">成功率</span><strong class="pt-good">${pct(summary?.success_rate)}</strong></div>
                    <div><span class="pt-perf-summary-label">隨機基準</span><strong>${pct(summary?.baseline)}</strong></div>
                    <div><span class="pt-perf-summary-label">Edge</span><strong style="color:${this._edgeColor(summary?.edge)}">${summaryEdge}</strong></div>
                </div>
                ${summaryNotice}
            </div>`;

        if (summaryEl) {
            summaryEl.innerHTML = summaryBlock;
        }

        el.innerHTML = this._perfData.map(p => this._renderPerformanceRow(p, pct)).join('');
    }

    // ──────────── 歷史清單 ────────────

    async loadHistory() {
        const tbody = document.getElementById('pt-hist-body');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center">載入中…</td></tr>';
        try {
            const url = getApiUrl(`/api/tracking/history?lottery_type=${this._currentGame}&limit=${this._histLimit}&offset=${this._histOffset}`);
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
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#888">尚無預測記錄</td></tr>';
            return;
        }
        const gameLabel = { BIG_LOTTO: '大樂透', POWER_LOTTO: '威力彩', DAILY_539: '今彩539' };
        const fmtStateBadge = state => this._renderSnapshotStateBadge(state);
        const resolvedRuns = runs.filter(r => r.status !== 'PENDING');
        if (!resolvedRuns.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#888">尚無已解析記錄</td></tr>';
            return;
        }
        tbody.innerHTML = resolvedRuns.map(r => this._renderHistoryRow(r, gameLabel, fmtStateBadge)).join('');

        tbody.querySelectorAll('.pt-hist-row').forEach(row => {
            row.addEventListener('click', e => {
                // 點研究狀態按鈕時不展開詳情
                if (e.target.closest('.pt-review-link')) return;
                if (e.target.classList.contains('pt-toggle-analyzed')) return;
                this._toggleDetail(Number(row.dataset.runId));
            });
        });

        tbody.querySelectorAll('.pt-review-link').forEach(link => {
            link.addEventListener('click', async e => {
                e.preventDefault();
                await this._openReviewFromHistory(Number(link.dataset.runId));
            });
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
    }

    _renderDetail(detail) {
        if (!detail) return '<div style="padding:8px">無資料</div>';

        const sourceMap = {
            RECONSTRUCTED: `<span class="pt-badge pt-sched-recon">🧪 補建</span>`,
            MANUAL:        `<span class="pt-badge pt-sched-scheduled">手動</span>`,
            VALID:         `<span class="pt-badge pt-sched-ok">✅ 正式</span>`,
        };
        const sourceBadge  = sourceMap[detail.snapshot_source] || sourceMap['VALID'];
        const reconWarning = detail.snapshot_source === 'RECONSTRUCTED'
            ? `<div class="pt-recon-warning">🧪 此預測為開獎後重建，不計入正式績效</div>` : '';

        const createdAtStr = detail.created_at
            ? new Date(detail.created_at.replace(' ', 'T') + 'Z').toLocaleString('zh-TW', {
                year: 'numeric', month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit', hour12: false })
            : '—';

        const firstResolved = detail.bets.find(b => b.status === 'RESOLVED');
        const actualArr     = firstResolved?.actual_numbers || [];
        const actualSpecial = firstResolved?.actual_special ?? null;
        const actualDraw    = firstResolved?.actual_draw    || null;
        const actualDate    = firstResolved?.actual_date    || null;

        // ── Block 1：本期開獎資訊 ─────────────────────────────────────
        const drawBallsHtml = actualArr.map(n =>
            `<span class="pt-num pt-num-actual">${n}</span>`
        ).join('');
        const drawSpecialHtml = this._hasSpecialNumber(actualSpecial)
            ? ` <span class="pt-num pt-actual-special">★${actualSpecial}</span>` : '';

        const block1 = `<div class="pt-block">
            <div class="pt-block-header">
                <span class="pt-block-title">本期開獎資訊</span>
                <span style="margin-left:auto;display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                    ${sourceBadge}
                    <span class="pt-detail-small">預測時間：${createdAtStr}</span>
                </span>
            </div>
            <div class="pt-block-body">
                <div class="pt-draw-info-row">
                    <span class="pt-draw-info-label">基於期號</span>
                    <span class="pt-draw-info-val">${detail.latest_known_draw}</span>
                    <span class="pt-draw-info-label" style="margin-left:16px">開獎期號</span>
                    <span class="pt-draw-info-val">${actualDraw || (Number.parseInt(detail.latest_known_draw, 10) + 1)}</span>
                    ${actualDate
                        ? `<span class="pt-draw-info-label" style="margin-left:16px">開獎日期</span>
                           <span class="pt-draw-info-val">${actualDate.slice(0, 10)}</span>`
                        : `<span class="pt-draw-pending" style="margin-left:12px">待開獎</span>`}
                </div>
                ${actualArr.length ? `<div class="pt-draw-info-row" style="margin-top:10px;align-items:center">
                    <span class="pt-draw-info-label">開獎號碼</span>
                    <span>${drawBallsHtml}${drawSpecialHtml}</span>
                </div>` : ''}
            </div>
        </div>`;

        // ── Block 2…N：目前各注數最佳策略歷史比對 ───────────────────
        const slots = Array.isArray(detail.current_best_strategies) ? detail.current_best_strategies : [];
        const betBlocks = [1, 2, 3, 4, 5].map(num => {
            const slot = slots[num - 1] || { num_bets: num, strategy_name: null, strategy_status: 'N/A', snapshot_state: 'N/A', bets: [] };
            return this._renderStrategySlot({ ...slot, num_bets: slot?.num_bets ?? num, _lottery_type: detail.lottery_type });
        }).join('');

        // ── Block: 研究報告 ──────────────────────────────────────
        const reviewBlock = detail.review_json ? this._renderReviewBlock(detail) : '';

        // ── Block: Phase P Explainability ────────────────────────
        const explainBlock = detail.explanation ? this._renderExplainabilityBlock(detail.explanation) : '';

        return `<div class="pt-detail-panel">
            ${reconWarning}
            ${block1}
            ${betBlocks}
            ${explainBlock}
            ${reviewBlock}
        </div>`;
    }

    _renderExplainabilityBlock(exp) {
        // Delegate to shared renderer (Phase P)
        return renderExplainabilityBlock(exp);
    }

    _renderReviewBlock(detail) {
        const r = detail.review_json;
        if (!r) return '';
        // Use real review linkage as primary; fall back to legacy analyzed field
        const isDetailReviewed = detail.review_status === 'REVIEWED' || detail.review_status === 'RESOLVED'
            || detail.analyzed === '已研究';
        const analyzed = isDetailReviewed ? '已研究' : (detail.analyzed || '未研究');
        const verdict = r.final_decision?.verdict || '—';
        const confidence = r.final_decision?.confidence || '—';
        const verdictClass = this._renderReviewVerdictClass(verdict);

        // Method comparison top3
        const top3 = (r.method_comparison?.top3_closest || []).map((m, i) => {
            const matched = (m.matched || []).join(', ');
            return `<tr>
                <td style="font-weight:600">#${m.rank || i + 1}</td>
                <td>${this._escHtml(m.method || '—')}</td>
                <td>${m.best_hit ?? '—'} 中</td>
                <td style="color:#58a6ff">${matched || '—'}</td>
                <td style="font-size:11px;color:#8b949e">${this._escHtml(m.note || '')}</td>
            </tr>`;
        }).join('');

        // Gate validation summary
        const gates = r.quantitative?.strategy_gates || {};
        const gateRows = Object.entries(gates).map(([name, g]) => {
            const passColor = this._renderGatePassColor(g.verdict);
            return `<tr>
                <td style="font-size:12px">${this._escHtml(name)}</td>
                <td>${g.num_bets ?? '—'}</td>
                <td>${g.stage1_edge || '—'}</td>
                <td>${g.gates_passed || '—'}</td>
                <td style="color:${passColor};font-weight:600">${g.verdict || '—'}</td>
            </tr>`;
        }).join('');

        // Winning quality
        const wq = r.winning_quality || {};
        const wqItems = [
            ['Split Risk', wq.split_risk],
            ['Birthday Range', wq.birthday_range],
            ['Payout Quality', wq.payout_quality],
        ].filter(([, v]) => v).map(([k, v]) => `<span class="pt-review-wq-tag">${k}: <strong>${v}</strong></span>`).join('');

        // Expert opinions
        const experts = r.expert_opinions || {};
        const expertHtml = Object.entries(experts).map(([role, expert]) => {
            const points = (expert.points || []).map(p => `<li>${this._escHtml(p)}</li>`).join('');
            return `<div class="pt-review-expert">
                <div class="pt-review-expert-role">${this._escHtml(expert.role || role)}</div>
                <ul class="pt-review-expert-points">${points}</ul>
            </div>`;
        }).join('');

        // Action items
        const actionHtml = ['P0', 'P1', 'P2'].map(pri => {
            const items = r.action_items?.[pri] || [];
            if (!items.length) return '';
            const rows = items.map(a => `<li>${this._escHtml(a.action || '—')}
                ${a.expected_lift ? `<span class="pt-review-action-lift">lift: ${a.expected_lift}</span>` : ''}
            </li>`).join('');
            return `<div class="pt-review-action-group">
                <span class="pt-review-action-pri pt-review-pri-${pri.toLowerCase()}">${pri}</span>
                <ul>${rows}</ul>
            </div>`;
        }).join('');

        // Counter evidence
        const counterHtml = (r.counter_evidence || []).map(c => {
            const sevColor = this._renderCounterSeverityColor(c.severity);
            return `<div class="pt-review-counter">
                <span class="pt-review-counter-sev" style="color:${sevColor}">[${c.severity || '—'}]</span>
                ${this._escHtml(c.claim || '')}
            </div>`;
        }).join('');

        const userReview = r.user_review;
        const approvedBadge = userReview?.status === 'APPROVED'
            ? `<span class="pt-state-badge" style="background:rgba(35,134,54,.16);color:#3fb950">✓ APPROVED</span>` : '';

        return `<div class="pt-block pt-review-block">
            <div class="pt-block-header" style="cursor:pointer" onclick="this.closest('.pt-review-block').classList.toggle('pt-review-collapsed')">
                <span class="pt-block-title">📋 LLM Research Board 檢討報告</span>
                <span style="margin-left:auto;display:flex;gap:8px;align-items:center">
                    ${approvedBadge}
                    <span class="pt-state-badge pt-state-resolved">${this._escHtml(analyzed)}</span>
                    ${analyzed === '已研究'
                        ? `<a href="/reviews?prediction_run_id=${detail.run_id}" class="pt-review-link" data-run-id="${detail.run_id}">查看檢討 →</a>`
                        : ''}
                    <span class="${verdictClass}" style="font-weight:700;font-size:14px">${this._escHtml(verdict)}</span>
                    <span style="font-size:11px;color:#8b949e">信心: ${this._escHtml(confidence)}</span>
                    <span class="pt-review-toggle-icon">▼</span>
                </span>
            </div>
            <div class="pt-review-body">
                ${r.final_decision?.reasoning ? `<div class="pt-review-reasoning">${this._escHtml(r.final_decision.reasoning)}</div>` : ''}

                ${top3 ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">🎯 最接近方法 Top3</div>
                    <table class="pt-review-table"><thead><tr><th>#</th><th>方法</th><th>命中</th><th>命中號碼</th><th>備註</th></tr></thead><tbody>${top3}</tbody></table>
                </div>` : ''}

                ${gateRows ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">🚦 Gate Validation</div>
                    <table class="pt-review-table"><thead><tr><th>策略</th><th>注數</th><th>Edge</th><th>通過</th><th>判定</th></tr></thead><tbody>${gateRows}</tbody></table>
                </div>` : ''}

                ${wqItems ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">💎 Winning Quality</div>
                    <div class="pt-review-wq-row">${wqItems}</div>
                    ${this._renderWqRecommendation(wq)}
                </div>` : ''}

                ${expertHtml ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">👥 專家意見</div>
                    ${expertHtml}
                </div>` : ''}

                ${counterHtml ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">⚠️ 反面證據</div>
                    ${counterHtml}
                </div>` : ''}

                ${actionHtml ? `<div class="pt-review-section">
                    <div class="pt-review-section-title">📌 行動項目</div>
                    ${actionHtml}
                </div>` : ''}

                ${this._renderReviewUserNotes(userReview)}

                ${this._renderReviewFooter(r, userReview)}
            </div>
        </div>`;
    }

    _escHtml(str) {
        if (typeof str !== 'string') return String(str ?? '');
        return str.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    }

    _renderStrategySlot(slot) {
        const numBets = this._resolveBetCount(slot) ?? 'N/A';
        const strategyName = slot?.strategy_name ? this._stratLabel(slot.strategy_name) : 'N/A';
        const strategyStatus = this._renderStrategyStatusBadge(slot?.strategy_status || 'N/A');
        const validatedBadge = this._renderValidatedBadge(slot?.validated_status, slot?.data_complete);
        // Phase V data completeness guard
        const missingDataWarning = slot?.data_complete === false
            ? `<div style="font-size:9px;color:#e74c3c;margin-top:3px">⚠️ 資料不足：缺少 ${(slot?.missing_phase_v_fields || []).join(', ')}</div>`
            : '';
        const snapshotState = this._renderSnapshotStateBadge(slot?.snapshot_state || 'N/A');
        const isPlaceholder = !!slot?.is_placeholder || !slot?.strategy_name;
        const bestHit = slot?.best_hit === null || slot?.best_hit === undefined ? null : slot.best_hit;
        const bets = Array.isArray(slot?.bets) ? slot.bets : [];
        const hitLabel = bestHit == null
            ? this._renderStrategySlotNullHitLabel(slot?.snapshot_state)
            : `<strong class="${this._renderStrategySlotHitClass(bestHit)}">${bestHit}</strong> 中`;
        const availability = this._renderStrategySlotAvailability(slot?.snapshot_state);

        if (isPlaceholder) {
            return `<div class="pt-block">
                <div class="pt-block-header">
                    <span class="pt-block-title">${numBets} 注</span>
                    <span class="pt-rsm-name" style="margin-left:8px;font-size:12px;color:#c9d1d9">N/A</span>
                    <span style="margin-left:auto">${snapshotState}</span>
                </div>
                <div class="pt-block-body">
                    <div class="pt-na-box">N/A</div>
                </div>
            </div>`;
        }

        if (slot?.snapshot_state === '無歷史快照') {
            return `<div class="pt-block">
                <div class="pt-block-header">
                    <span class="pt-block-title">${numBets} 注</span>
                    <span class="pt-rsm-name" style="margin-left:8px;font-size:12px;color:#c9d1d9">${strategyName}</span>
                    ${strategyStatus}${validatedBadge}
                    <span style="margin-left:6px">${snapshotState}</span>
                </div>
                ${missingDataWarning}
                <div class="pt-block-body">
                    <div class="pt-na-box">無歷史快照</div>
                </div>
            </div>`;
        }

        const lotteryType = slot?._lottery_type || '';
        const actualSet = new Set(slot?.actual_numbers || []);
        const slotActualSpecial = slot?.actual_special ?? null;
        // 特別號：POWER_LOTTO 取第一注的 predicted_special 並套用到全部注；BIG_LOTTO 無預測特別號
        const runPredSpecial = lotteryType === 'POWER_LOTTO'
            ? (bets.find(b => this._hasSpecialNumber(b.predicted_special))?.predicted_special ?? null)
            : null;
        const perBetRows = this._renderStrategySlotRows(bets, lotteryType, actualSet, slotActualSpecial, runPredSpecial);

        return `<div class="pt-block">
            <div class="pt-block-header">
                <span class="pt-block-title">${numBets} 注</span>
                <span class="pt-rsm-name" style="margin-left:8px;font-size:12px;color:#c9d1d9">${strategyName}</span>
                ${strategyStatus}${validatedBadge}
                <span style="margin-left:6px">${snapshotState}</span>
                <span style="margin-left:auto;font-size:12px">${hitLabel}</span>
            </div>
            <div class="pt-block-body" style="padding:6px 14px">
                ${availability}
                ${missingDataWarning}
                ${perBetRows}
            </div>
        </div>`;
    }

    _renderStrategyStatusBadge(status) {
        const map = {
            PRODUCTION: ['pt-status-production', 'PRODUCTION'],
            WATCH: ['pt-status-watch', 'WATCH'],
            MAINTENANCE: ['pt-status-maintenance', 'MAINTENANCE'],
            ADVISORY_ONLY: ['pt-status-advisory', 'ADVISORY'],
            'N/A': ['pt-status-na', 'N/A'],
            UNKNOWN: ['pt-status-na', 'UNKNOWN'],
        };
        const [cls, label] = map[status] || map['N/A'];
        return `<span class="pt-state-badge ${cls}">${label}</span>`;
    }
    /** Phase V: render validated_status badge alongside strategy_status */
    _renderValidatedBadge(validatedStatus, dataComplete) {
        if (!validatedStatus) return '';
        if (dataComplete === false) {
            return `<span class="pt-state-badge" style="background:rgba(231,76,60,0.15);color:#e74c3c;border:1px solid #e74c3c;font-size:9px;padding:2px 5px;border-radius:4px" title="缺少驗證所需欄位">⚠️ 資料不足</span>`;
        }
        const map = {
            'VALIDATED': ['rgba(0,200,100,0.15)', '#00c864', '#00c864', '✅ 已完整驗證'],
            'WATCH':     ['rgba(255,180,0,0.12)',  '#ffb400', '#ffb400', '⚠️ 觀察中（未完全驗證）'],
            'REJECTED':  ['rgba(231,76,60,0.10)',  '#e74c3c', '#e74c3c', '❌ 未通過驗證'],
        };
        const [bg, color, border, label] = map[validatedStatus] || ['transparent', '#888', '#888', validatedStatus];
        return `<span class="pt-state-badge" style="background:${bg};color:${color};border:1px solid ${border};font-size:9px;padding:2px 5px;border-radius:4px">${label}</span>`;
    }
    _renderSnapshotStateBadge(state) {
        const map = {
            RESOLVED: ['pt-state-resolved', 'RESOLVED'],
            PENDING: ['pt-state-pending', 'PENDING'],
            MISSED: ['pt-state-missed', 'MISSED'],
            RECONSTRUCTED: ['pt-state-reconstructed', 'RECONSTRUCTED'],
            '無歷史快照': ['pt-state-na', '無歷史快照'],
            'N/A': ['pt-state-na', 'N/A'],
        };
        const [cls, label] = map[state] || map['N/A'];
        return `<span class="pt-state-badge ${cls}">${label}</span>`;
    }

    async _openReviewFromHistory(runId) {
        if (!runId) return;
        this.app?.uiManager?.showSection('reviews');

        if (globalThis.history?.pushState) {
            globalThis.history.pushState({}, '', `/reviews?prediction_run_id=${runId}`);
        }

        if (!this.app?.reviewManager) return;
        this.app.reviewManager._currentGame = this._currentGame;
        this.app.reviewManager.init();
    }

    _renderNumberBalls(numbers, matchedSet = new Set(), specialNum = null) {
        const nums = Array.isArray(numbers) ? numbers : [];
        if (!nums.length) return '<span class="pt-na-text">N/A</span>';
        return nums.map(n => {
            if (matchedSet.has(n)) return `<span class="pt-num pt-num-match">${n}</span>`;
            if (specialNum !== null && n === specialNum) return `<span class="pt-num pt-num-sp-hit" title="命中特別號">★${n}</span>`;
            return `<span class="pt-num">${n}</span>`;
        }).join('');
    }

    _renderActualNumberBalls(numbers, special = null) {
        const nums = Array.isArray(numbers) ? numbers : [];
        if (!nums.length) return '<span class="pt-na-text">—</span>';
        const numsHtml = nums.map(n => `<span class="pt-num pt-num-actual">${n}</span>`).join('');
        const specialHtml = this._hasSpecialNumber(special) ? ` <span class="pt-num pt-actual-special">★${special}</span>` : '';
        return `${numsHtml}${specialHtml}`;
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
        return name.replaceAll('_', ' ');
    }

    _renderStrategySlotNullHitLabel(snapshotState) {
        if (snapshotState === '無歷史快照') {
            return '<span style="color:#888">無歷史快照</span>';
        }
        return '<span style="color:#888">N/A</span>';
    }
}
