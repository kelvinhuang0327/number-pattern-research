/**
 * ReviewManager
 * 研究檢討 — 管理檢討會議、行動項目、影子實驗、儀表板
 */
import { getApiUrl } from '../config/apiConfig.js';
import { renderCompactExplainBlock } from './components/ExplainabilityRenderer.js';

export class ReviewManager {
    constructor(app) {
        this.app = app;
        this._currentGame = 'BIG_LOTTO';
        this._sessions = [];
        this._dashboard = null;
        this._currentSession = null;
        this._filterStatus = '';
        this._filterType = '';
        this._offset = 0;
        this._limit = 20;
        this._pendingRuns = [];
        this._recentSessions = [];
        this._listenersBound = false;
    }

    /* ── 初始化（section 首次可見時呼叫） ── */
    init() {
        if (!this._listenersBound) {
            this._bindEvents();
            this._listenersBound = true;
        }
        this.loadDashboard();
        this.loadSessions();
        this.loadPendingRuns();

        const runId = new URLSearchParams(window.location.search).get('prediction_run_id');
        if (runId) {
            this.openPredictionRun(Number(runId));
        }
    }

    _bindEvents() {
        const el = (id) => document.getElementById(id);
        el('rv-filter-status')?.addEventListener('change', () => { this._filterStatus = el('rv-filter-status').value; this._offset = 0; this.loadSessions(); });
        el('rv-filter-type')?.addEventListener('change', () => { this._filterType = el('rv-filter-type').value; this._offset = 0; this.loadSessions(); });
        el('rv-prev-btn')?.addEventListener('click', () => { if (this._offset >= this._limit) { this._offset -= this._limit; this.loadSessions(); } });
        el('rv-next-btn')?.addEventListener('click', () => { this._offset += this._limit; this.loadSessions(); });
        el('rv-tab-sessions')?.addEventListener('click', () => {
            const actionsPanel = document.getElementById('rv-actions-panel');
            if (actionsPanel) actionsPanel.style.display = 'none';
            this.loadSessions();
        });
        el('rv-back-btn')?.addEventListener('click', () => this._showList());
        el('rv-tab-actions')?.addEventListener('click', () => this.loadActions());

        // Sync global game switcher
        document.getElementById('lottery-type-filter')?.addEventListener('change', e => {
            this._currentGame = e.target.value || 'BIG_LOTTO';
            this._offset = 0;
            this.loadDashboard();
            this.loadSessions();
            this.loadPendingRuns();
        });

        document.getElementById('rv-session-tbody')?.addEventListener('click', e => {
            const btn = e.target.closest('.rv-view-btn');
            if (btn) this.loadSession(Number(btn.dataset.sid));
        });

        document.getElementById('rv-actions-panel')?.addEventListener('click', e => {
            const btn = e.target.closest('.rv-view-btn');
            if (btn) this.loadSession(Number(btn.dataset.sid));
        });

        // Dashboard "查看詳情" cards — previously had NO handler (Bug #1 fix)
        document.getElementById('rv-dashboard')?.addEventListener('click', e => {
            const btn = e.target.closest('.rv-view-btn');
            if (btn) this.loadSession(Number(btn.dataset.sid));
        });

        // Detail view export buttons — dynamically rendered, need delegation (Bug #2 fix)
        document.getElementById('rv-detail-view')?.addEventListener('click', e => {
            if (e.target.closest('.rv-export-json')) {
                if (this._currentSession?.id) this._exportJson(this._currentSession.id);
            } else if (e.target.closest('.rv-export-md')) {
                if (this._currentSession?.id) this._exportMd(this._currentSession.id);
            }
        });
    }

    /* ════════════════ Dashboard ════════════════ */
    async loadDashboard() {
        const wrap = document.getElementById('rv-dashboard');
        if (!wrap) return;
        try {
            const data = await this._get(`/api/reviews/dashboard?game=${this._currentGame}`);
            this._dashboard = data;
            this._recentSessions = Array.isArray(data.recent_sessions) ? data.recent_sessions : [];
            wrap.innerHTML = this._renderDashboard(data);
        } catch (e) {
            wrap.innerHTML = `<div class="rv-empty">無法載入儀表板: ${e.message}</div>`;
        }
    }

    _renderDashboard(d) {
        const counts = d.session_status_counts || {};
        const summary = {
            total: Object.values(counts).reduce((sum, n) => sum + Number(n || 0), 0),
            open: Number(counts.OPEN || 0),
            resolved: Number(counts.RESOLVED || 0),
        };
        const recentSessions = Array.isArray(d.recent_sessions) ? d.recent_sessions.slice(0, 3) : [];
        const pendingRuns = Array.isArray(this._pendingRuns) ? this._pendingRuns.slice(0, 5) : [];
        const hasData = recentSessions.length > 0 || pendingRuns.length > 0 || summary.total > 0;
        const summaryParts = [];
        if (summary.total > 0) summaryParts.push(`總檢討：${summary.total}`);
        if (summary.open > 0) summaryParts.push(`進行中：${summary.open}`);
        if (summary.resolved > 0) summaryParts.push(`已解決：${summary.resolved}`);
        return `
        ${!hasData ? `
        <div class="rv-empty-state">
            <div class="rv-empty-title">目前尚無檢討會議</div>
            <div class="rv-empty-copy">本頁顯示由 AI Agent 自動產生的檢討結果</div>
            <div class="rv-empty-copy">👉 請先執行檢討流程（外部）</div>
        </div>` : ''}
        ${recentSessions.length ? `
        <div class="rv-panel">
            <div class="rv-panel-title">📌 最近檢討結果</div>
            <div class="rv-recent-grid">
                ${recentSessions.map(s => this._renderRecentSessionCard(s)).join('')}
            </div>
        </div>` : ''}
        ${pendingRuns.length ? `
        <div class="rv-panel">
            <div class="rv-panel-title">⏳ 尚未檢討期數</div>
            <div class="rv-pending-list">
                ${pendingRuns.map(r => this._renderPendingRunRow(r)).join('')}
            </div>
        </div>` : ''}
        ${summaryParts.length ? `<div class="rv-dashboard-summary">${summaryParts.map(s => `<span>${s}</span>`).join('')}</div>` : ''}`;
    }

    /* ════════════════ Session List ════════════════ */
    async loadSessions() {
        const tbody = document.getElementById('rv-session-tbody');
        if (!tbody) return;
        try {
            const qs = new URLSearchParams({ game: this._currentGame, limit: this._limit, offset: this._offset });
            if (this._filterStatus) qs.set('status', this._filterStatus);
            if (this._filterType) qs.set('session_type', this._filterType);
            const data = await this._get(`/api/reviews/history?${qs}`);
            this._sessions = data.sessions || [];
            tbody.innerHTML = this._sessions.length
                ? this._sessions.map(s => this._renderSessionRow(s)).join('')
                : `<tr><td colspan="7" class="rv-empty">尚無檢討會議</td></tr>`;
            const total = Number(data.total || 0);
            const start = total === 0 ? 0 : this._offset + 1;
            const end = this._offset + this._sessions.length;
            document.getElementById('rv-page-info').textContent = `${start} – ${end} / ${total}`;
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7" class="rv-empty">載入失敗: ${e.message}</td></tr>`;
        }
    }

    _renderSessionRow(s) {
        const statusCls = s.status === 'RESOLVED' ? 'rv-st-resolved' : s.status === 'OPEN' ? 'rv-st-open' : 'rv-st-other';
        const gameLabel = this._gameLabel(s.game);
        const decision = this._decisionLabel(s.final_decision);
        const confidence = this._confidenceLabel(s.confidence_level);
        const viewBtn = s.id
            ? `<button class="btn-sm btn-primary rv-view-btn" data-sid="${s.id}" style="cursor:pointer">查看</button>`
            : `<span class="rv-no-record" title="無對應紀錄" style="color:#484f58;font-size:12px">無對應紀錄</span>`;
        return `<tr class="rv-row" data-sid="${s.id || ''}">
            <td>${this._esc(gameLabel)}</td>
            <td>${this._esc(s.draw || '-')}</td>
            <td>${this._esc(s.draw_date || '-')}</td>
            <td><span class="rv-decision rv-decision-${this._decisionClass(s.final_decision)}">${this._esc(decision)}</span></td>
            <td>${this._esc(confidence)}</td>
            <td><span class="rv-status ${statusCls}">${s.status}</span></td>
            <td>${viewBtn}</td>
        </tr>`;
    }

    /* ════════════════ Session Detail ════════════════ */
    async loadSession(sessionId) {
        const detail = document.getElementById('rv-detail');
        if (!detail) return;
        try {
            const data = await this._get(`/api/reviews/${sessionId}`);
            this._currentSession = data;

            // Phase P: fetch explainability for linked prediction run (if any)
            let explanation = null;
            const predRunId = data.prediction_run_id || data.metadata?.prediction_run_id;
            if (predRunId) {
                try {
                    const expData = await this._get(`/api/explainability/run/${predRunId}`);
                    explanation = expData?.explanation || null;
                } catch (_) {
                    // non-fatal — explanation block simply won't render
                }
            }

            detail.innerHTML = this._renderDetail(data, explanation);
            this._showDetail();
        } catch (e) {
            detail.innerHTML = `<div class="rv-empty">載入失敗: ${e.message}</div>`;
            this._showDetail();
        }
    }

    _renderDetail(s, explanation = null) {
        const findings = s.findings || [];
        const hypotheses = s.hypotheses || [];
        const actions = s.actions || [];
        const gameLabel = this._gameLabel(s.game);
        const decision = this._decisionLabel(s.final_decision);
        const confidence = this._confidenceLabel(s.confidence_level);

        // Phase P: compact explainability block
        const explainHtml = explanation
            ? renderCompactExplainBlock(explanation, { title: '🔍 本期決策解釋', showStrategy: true, showBaseMetrics: false })
            : '';

        return `
        <div class="rv-detail-header">
            <h3>${this._esc(gameLabel)} 第${this._esc(s.draw || '?')}期</h3>
            <div class="rv-detail-meta">
                <span class="rv-status ${s.status==='RESOLVED'?'rv-st-resolved':'rv-st-open'}">${s.status}</span>
                <span>決策: ${this._esc(decision)}</span>
                <span>信心: ${this._esc(confidence)}</span>
                <span>類型: ${this._esc(s.session_type)}</span>
                <span>建立: ${this._esc(s.created_at || '')}</span>
            </div>
            <div class="rv-detail-actions-bar">
                <button class="btn-sm btn-secondary rv-export-json">📄 匯出 JSON</button>
                <button class="btn-sm btn-secondary rv-export-md">📝 匯出 Markdown</button>
            </div>
        </div>
        ${s.summary ? `<div class="rv-summary-box">${this._esc(s.summary)}</div>` : ''}

        ${explainHtml}

        <div class="rv-section">
            <h4>🔍 發現 (${findings.length})</h4>
            ${findings.length ? `<table class="rv-table"><thead><tr><th>類型</th><th>標題</th><th>內容</th><th>證據</th></tr></thead><tbody>
                ${findings.map(f => `<tr><td>${this._esc(f.section_type)}</td><td>${this._esc(f.title||'')}</td><td>${this._esc(f.content||'')}</td><td>${this._esc(f.evidence_type)}</td></tr>`).join('')}
            </tbody></table>` : '<div class="rv-empty">無發現</div>'}
        </div>

        <div class="rv-section">
            <h4>💡 假說 (${hypotheses.length})</h4>
            ${hypotheses.length ? `<table class="rv-table"><thead><tr><th>類型</th><th>描述</th><th>預期影響</th><th>驗證方法</th><th>狀態</th></tr></thead><tbody>
                ${hypotheses.map(h => `<tr>
                    <td>${this._esc(h.hypothesis_type)}</td>
                    <td>${this._esc(h.description||'')}</td>
                    <td>${this._esc(h.expected_impact||'')}</td>
                    <td>${this._esc(h.validation_method||'')}</td>
                    <td><span class="rv-hyp-status">${h.status}</span></td>
                </tr>`).join('')}
            </tbody></table>` : '<div class="rv-empty">無假說</div>'}
        </div>

        <div class="rv-section">
            <h4>⚡ 行動 (${actions.length})</h4>
            ${actions.length ? `<table class="rv-table"><thead><tr><th>優先</th><th>標題</th><th>說明</th><th>預期增益</th><th>狀態</th></tr></thead><tbody>
                ${actions.map(a => `<tr>
                    <td><span class="rv-pri rv-pri-${(a.priority||'P2').toLowerCase()}">${a.priority}</span></td>
                    <td>${this._esc(a.action_title||'')}</td>
                    <td>${this._esc(a.action_description||'')}</td>
                    <td>${this._esc(a.expected_gain||'')}</td>
                    <td>${a.status}</td>
                </tr>`).join('')}
            </tbody></table>` : '<div class="rv-empty">無行動</div>'}
        </div>`;
    }

    async loadPendingRuns() {
        try {
            const data = await this._get(`/api/tracking/history?lottery_type=${this._currentGame}&analyzed=UNREVIEWED&limit=5&offset=0&dedup=true`);
            this._pendingRuns = data.runs || [];
            const wrap = document.getElementById('rv-dashboard');
            if (wrap) wrap.innerHTML = this._renderDashboard(this._dashboard || { recent_sessions: this._recentSessions, session_status_counts: {} });
        } catch (e) {
            this._pendingRuns = [];
        }
    }

    /* ════════════════ Actions Tab ════════════════ */
    async loadActions() {
        const wrap = document.getElementById('rv-actions-panel');
        if (!wrap) return;
        try {
            const data = await this._get(`/api/reviews/actions?game=${this._currentGame}&limit=100`);
            const actions = data.actions || [];
            wrap.style.display = 'block';
            wrap.innerHTML = actions.length
                ? `<table class="rv-table"><thead><tr><th>ID</th><th>優先</th><th>標題</th><th>狀態</th><th>Session</th></tr></thead><tbody>
                    ${actions.map(a => `<tr>
                        <td>${a.id}</td>
                        <td><span class="rv-pri rv-pri-${(a.priority||'P2').toLowerCase()}">${a.priority}</span></td>
                        <td>${this._esc(a.action_title||'')}</td>
                        <td><span class="rv-status ${a.status==='DONE'?'rv-st-resolved':a.status==='OPEN'?'rv-st-open':'rv-st-other'}">${a.status}</span></td>
                        <td><button class="btn-sm rv-view-btn" data-sid="${a.session_id}">查看</button></td>
                    </tr>`).join('')}
                </tbody></table>`
                : '<div class="rv-empty">尚無行動項目</div>';
        } catch (e) {
            wrap.innerHTML = `<div class="rv-empty">載入失敗: ${e.message}</div>`;
        }
    }

    async openPredictionRun(runId) {
        if (!runId || Number.isNaN(Number(runId))) return;
        try {
            const data = await this._get(`/api/reviews/prediction-status?prediction_run_id=${Number(runId)}&limit=5&offset=0`);
            const item = (data.items || []).find(x => Number(x.prediction_run_id) === Number(runId));
            const sessionId = item?.review_session_id;
            if (sessionId) {
                if (item?.game && item.game !== this._currentGame) {
                    this._currentGame = item.game;
                    await Promise.all([
                        this.loadDashboard(),
                        this.loadSessions(),
                        this.loadPendingRuns(),
                    ]);
                }
                this.loadSession(Number(sessionId));
                return;
            }
            this._showList();
            const detail = document.getElementById('rv-detail');
            if (detail) {
                detail.innerHTML = `<div class="rv-empty">此預測已標記檢討，但尚未找到對應的檢討會議。</div>`;
            }
        } catch (e) {
            this._showList();
            const detail = document.getElementById('rv-detail');
            if (detail) {
                detail.innerHTML = `<div class="rv-empty">無法載入對應檢討：${this._esc(e.message)}</div>`;
            }
        }
    }

    /* ════════════════ API helpers ════════════════ */
    async _exportJson(id) {
        const data = await this._get(`/api/reviews/${id}/export/json`);
        this._download(JSON.stringify(data, null, 2), `review_${id}.json`, 'application/json');
    }
    async _exportMd(id) {
        const resp = await fetch(getApiUrl(`/api/reviews/${id}/export/markdown`));
        const text = await resp.text();
        this._download(text, `review_${id}.md`, 'text/markdown');
    }

    /* ════════════════ View toggling ════════════════ */
    _showList() {
        document.getElementById('rv-list-view')?.classList.remove('rv-hidden');
        document.getElementById('rv-detail-view')?.classList.add('rv-hidden');
    }
    _showDetail() {
        document.getElementById('rv-list-view')?.classList.add('rv-hidden');
        const dv = document.getElementById('rv-detail-view');
        if (dv) {
            dv.classList.remove('rv-hidden');
            dv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /* ════════════════ Utilities ════════════════ */
    _esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }

    _gameLabel(game) {
        const map = { BIG_LOTTO: '大樂透', POWER_LOTTO: '威力彩', DAILY_539: '今彩539' };
        return map[game] || game || '-';
    }

    _decisionLabel(value) {
        const map = {
            PRODUCTION: '上線',
            WATCH: '觀察',
            ADVISORY_ONLY: '退回',
            NO_ACTION: '退回',
            REJECT: '退回',
            CANCELLED: '退回',
            ACCEPTED: '上線',
        };
        return map[value] || value || '-';
    }

    _decisionClass(value) {
        if (value === 'PRODUCTION' || value === 'ACCEPTED') return 'production';
        if (value === 'WATCH') return 'watch';
        return 'rejected';
    }

    _confidenceLabel(value) {
        const map = {
            HIGH: '高',
            MEDIUM: '中',
            LOW: '低',
            H: '高',
            M: '中',
            L: '低',
        };
        return map[value] || value || '-';
    }

    _renderRecentSessionCard(s) {
        const statusCls = s.status === 'RESOLVED' ? 'rv-st-resolved' : s.status === 'OPEN' ? 'rv-st-open' : 'rv-st-other';
        const decision = this._decisionLabel(s.final_decision);
        const confidence = this._confidenceLabel(s.confidence_level);
        const gameLabel = this._gameLabel(s.game);
        const drawDate = this._formatDate(s.draw_date);
        return `
            <div class="rv-recent-card">
                <div class="rv-recent-head">
                    <div class="rv-recent-game">${this._esc(gameLabel)}</div>
                    <span class="rv-status ${statusCls}">${this._esc(s.status || '-')}</span>
                </div>
                <div class="rv-recent-draw">第${this._esc(s.draw || '-')}期</div>
                <div class="rv-recent-meta">開獎日期：${this._esc(drawDate)}</div>
                <div class="rv-recent-meta">狀態：${this._esc(s.status || '-')}｜決策：${this._esc(decision)}｜信心：${this._esc(confidence)}</div>
                ${s.id
                    ? `<button class="btn-sm btn-primary rv-view-btn" data-sid="${s.id}" style="cursor:pointer">查看詳情</button>`
                    : `<span style="color:#484f58;font-size:12px">無對應紀錄</span>`}
            </div>`;
    }

    _renderPendingRunRow(r) {
        const gameLabel = this._gameLabel(r.lottery_type);
        return `
            <div class="rv-pending-row">
                <span class="rv-pending-game">${this._esc(gameLabel)}</span>
                <span class="rv-pending-draw">｜${this._esc(r.latest_known_draw || '-')}</span>
                <span class="rv-pending-state">未檢討</span>
            </div>`;
    }

    _formatDate(value) {
        if (!value) return '-';
        return String(value).slice(0, 10);
    }

    _download(content, filename, mime) {
        const blob = new Blob([content], { type: mime });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    async _get(path) {
        const resp = await fetch(getApiUrl(path));
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    async _post(path, body, method = 'POST') {
        const resp = await fetch(getApiUrl(path), { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }
}
