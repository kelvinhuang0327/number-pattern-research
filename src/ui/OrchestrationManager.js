import { getApiUrl } from '../config/apiConfig.js';

export class OrchestrationManager {
  constructor(app) {
    this.app = app;
    this._initialized = false;
    this._schedulerEnabled = true;
    this._lastRuns = [];
    this._taskPage = 1;
    this._taskPageSize = 10;
    this._taskTotal = 0;
  }

  async init() {
    if (!this._initialized) {
      this._bindEvents();
      const dateInput = document.getElementById('orc-date-filter');
      if (dateInput) dateInput.value = '';
      this._initialized = true;
    }
    await this._loadAll();
  }

  _bindEvents() {
    document.getElementById('orc-refresh-btn')?.addEventListener('click', () => this._loadAll());
    document.getElementById('orc-status-filter')?.addEventListener('change', () => {
      this._taskPage = 1;
      this._loadTasks();
    });
    document.getElementById('orc-date-filter')?.addEventListener('change', () => {
      this._taskPage = 1;
      this._loadTasks();
    });
    document.getElementById('orc-back-btn')?.addEventListener('click', () => this._showList());
    document.getElementById('orc-scheduler-toggle-btn')?.addEventListener('click', () => this._toggleScheduler());
    document.getElementById('orc-provider-save-btn')?.addEventListener('click', () => this._saveProviders());
    document.getElementById('orc-run-planner-btn')?.addEventListener('click', () => this._triggerRunnerNow('planner'));
    document.getElementById('orc-run-worker-btn')?.addEventListener('click', () => this._triggerRunnerNow('worker'));
    document.getElementById('orc-task-prev-btn')?.addEventListener('click', () => this._changeTaskPage(-1));
    document.getElementById('orc-task-next-btn')?.addEventListener('click', () => this._changeTaskPage(1));

    document.getElementById('orc-task-tbody')?.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-task-id]');
      if (row) this._loadDetail(Number(row.dataset.taskId));
    });
  }

  async _get(path) {
    const res = await fetch(getApiUrl(path));
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  async _loadAll() {
    await Promise.all([this._loadSummary(), this._loadProviders(), this._loadTasks(), this._loadRuns()]);
  }

  async _loadSummary() {
    try {
      const data = await this._get('/api/orchestrator/summary');
      this._schedulerEnabled = Boolean(data.scheduler_enabled);
      document.getElementById('orc-total').textContent = data.total_today ?? '—';
      document.getElementById('orc-running').textContent = data.task_counts?.RUNNING ?? 0;
      document.getElementById('orc-completed').textContent = data.task_counts?.COMPLETED ?? 0;
      this._renderSchedulerState(this._schedulerEnabled);
      this._renderNextTickEstimate(this._lastRuns);
      this._renderComboLabel(data.combo_label);
      const workerEl = document.getElementById('orc-worker-status');
      if (data.worker_provider === 'copilot-daemon') {
        if (data.worker_busy) {
          workerEl.textContent = `Daemon 執行中 (PID ${data.worker_pid})`;
          workerEl.style.color = 'var(--warning-color, #f59e0b)';
        } else if (data.copilot_daemon_running) {
          workerEl.textContent = `Daemon 待命中 (PID ${data.copilot_daemon_pid})`;
          workerEl.style.color = 'var(--success-color, #10b981)';
        } else {
          workerEl.textContent = 'Copilot Daemon 未啟動';
          workerEl.style.color = 'var(--danger-color, #ef4444)';
        }
      } else if (data.worker_busy) {
        workerEl.textContent = `忙碌 (PID ${data.worker_pid})`;
        workerEl.style.color = 'var(--warning-color, #f59e0b)';
      } else {
        workerEl.textContent = '閒置';
        workerEl.style.color = 'var(--success-color, #10b981)';
      }
    } catch (e) {
      console.error('[OrchestratorManager] summary error', e);
    }
  }

  async _loadProviders() {
    try {
      const data = await this._get('/api/orchestrator/providers');
      this._populateProviderSelect('orc-planner-provider', data.planner_options || [], data.planner_provider);
      this._populateProviderSelect('orc-worker-provider', data.worker_options || [], data.worker_provider);
      this._renderProviderHint(data);
      this._renderComboLabel(data.combo_label);
    } catch (e) {
      console.error('[OrchestratorManager] provider load error', e);
      const hintEl = document.getElementById('orc-provider-hint');
      if (hintEl) hintEl.textContent = `Provider 載入失敗：${e.message}`;
    }
  }

  _populateProviderSelect(id, options, selectedValue) {
    const select = document.getElementById(id);
    if (!select) return;
    select.innerHTML = options.map((option) => {
      const label = option.available ? option.label : `${option.label}（不可用）`;
      const selected = option.value === selectedValue ? 'selected' : '';
      return `<option value="${_esc(option.value)}" ${selected}>${_esc(label)}</option>`;
    }).join('');
  }

  _renderProviderHint(data) {
    const hintEl = document.getElementById('orc-provider-hint');
    if (!hintEl) return;
    const unavailable = []
      .concat(data.planner_options || [], data.worker_options || [])
      .filter((option) => !option.available)
      .map((option) => `${option.label}：${option.reason}`);
    if (unavailable.length) {
      hintEl.textContent = unavailable.join(' | ');
      hintEl.style.color = 'var(--warning-color, #f59e0b)';
      return;
    }
    const daemonOption = (data.worker_options || []).find((option) => option.value === 'copilot-daemon');
    if (daemonOption) {
      hintEl.textContent = `切換後會影響下一次 planner / worker 啟動；不會中斷目前已在執行的任務。${daemonOption.reason ? ` Copilot Daemon：${daemonOption.reason}` : ''}`;
      hintEl.style.color = 'var(--text-muted, #8b949e)';
      return;
    }
    hintEl.textContent = '切換後會影響下一次 planner / worker 啟動；不會中斷目前已在執行的任務。';
    hintEl.style.color = 'var(--text-muted, #8b949e)';
  }

  _renderComboLabel(comboLabel) {
    const subtitle = document.getElementById('orc-subtitle');
    if (!subtitle) return;
    subtitle.textContent = comboLabel || '可切換 Planner / Worker 組合的雙 Agent 自動化排程';
  }

  _renderSchedulerState(enabled) {
    const stateEl = document.getElementById('orc-scheduler-state');
    const btn = document.getElementById('orc-scheduler-toggle-btn');
    if (!stateEl || !btn) return;

    if (enabled) {
      stateEl.textContent = '啟用中';
      stateEl.style.color = 'var(--success-color, #10b981)';
      btn.textContent = '暫停排程';
      btn.className = 'btn-sm btn-secondary';
      btn.dataset.enabled = '1';
      return;
    }

    stateEl.textContent = '已暫停';
    stateEl.style.color = 'var(--danger-color, #ef4444)';
    btn.textContent = '啟用排程';
    btn.className = 'btn-sm btn-primary';
    btn.dataset.enabled = '0';
  }

  async _toggleScheduler() {
    const btn = document.getElementById('orc-scheduler-toggle-btn');
    if (!btn) return;
    const currentEnabled = btn.dataset.enabled === '1';
    const nextEnabled = !currentEnabled;
    const nextLabel = nextEnabled ? '啟用排程' : '暫停排程';

    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = '更新中…';

    try {
      await this._post('/api/orchestrator/scheduler', { enabled: nextEnabled });
      this._renderSchedulerState(nextEnabled);
      this.app?.uiManager?.showNotification(`排程已${nextEnabled ? '啟用' : '暫停'}`, 'success');
      await this._loadAll();
    } catch (e) {
      this.app?.uiManager?.showNotification(`排程狀態更新失敗：${e.message}`, 'error');
      btn.textContent = oldText || nextLabel;
    } finally {
      btn.disabled = false;
    }
  }

  async _saveProviders() {
    const plannerSelect = document.getElementById('orc-planner-provider');
    const workerSelect = document.getElementById('orc-worker-provider');
    const btn = document.getElementById('orc-provider-save-btn');
    if (!plannerSelect || !workerSelect || !btn) return;

    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = '套用中…';

    try {
      const data = await this._post('/api/orchestrator/providers', {
        planner_provider: plannerSelect.value,
        worker_provider: workerSelect.value,
      });
      this._renderComboLabel(data.combo_label);
      this.app?.uiManager?.showNotification(`執行組合已更新為 ${data.combo_label}`, 'success');
      await this._loadAll();
    } catch (e) {
      this.app?.uiManager?.showNotification(`Provider 更新失敗：${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  async _triggerRunnerNow(runner) {
    const isPlanner = runner === 'planner';
    const btnId = isPlanner ? 'orc-run-planner-btn' : 'orc-run-worker-btn';
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const oldText = btn.textContent;
    btn.disabled = true;
    btn.textContent = isPlanner ? 'Planner 執行中…' : 'Worker 執行中…';

    try {
      const data = await this._post('/api/orchestrator/run-now', { runner });
      const msg = `${isPlanner ? 'Planner' : 'Worker'} 已觸發（PID ${data.pid}）`;
      this.app?.uiManager?.showNotification(msg, 'success');
      await this._loadAll();
    } catch (e) {
      this.app?.uiManager?.showNotification(`${isPlanner ? 'Planner' : 'Worker'} 立即執行失敗：${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  async _post(path, payload = {}) {
    const res = await fetch(getApiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const data = await res.json();
        if (data?.detail) detail = data.detail;
      } catch (_) {
        // ignore json parse failure
      }
      throw new Error(detail);
    }
    return res.json();
  }

  async _loadTasks() {
    const tbody = document.getElementById('orc-task-tbody');
    if (!tbody) return;
    try {
      const dateRaw = document.getElementById('orc-date-filter')?.value || '';
      const date = dateRaw.replace(/-/g, '');  // YYYYMMDD
      const status = document.getElementById('orc-status-filter')?.value || '';
      const params = new URLSearchParams();
      if (date) params.set('date', date);
      if (status) params.set('status', status);
      params.set('page', String(this._taskPage));
      params.set('page_size', String(this._taskPageSize));
      const data = await this._get(`/api/orchestrator/tasks?${params}`);
      this._taskTotal = Number(data.total || 0);
      this._taskPage = Number(data.page || this._taskPage);
      this._renderTaskPagination();
      if (!data.tasks.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="rv-empty">無任務資料</td></tr>';
        return;
      }
      tbody.innerHTML = data.tasks.map(t => `
        <tr data-task-id="${t.id}" style="cursor:pointer">
          <td>${t.id}</td>
          <td title="${_esc(t.slot_key || '')}">${_fmt_slot(t.slot_key)}</td>
          <td>
            ${_esc(t.title || '—')}
            ${t.planner_source === 'fallback' ? '<span class="orc-plan-badge orc-plan-badge-fallback">FALLBACK</span>' : ''}
          </td>
          <td><span class="orc-status-badge orc-status-${(t.status||'').toLowerCase()}">${t.status}</span></td>
          <td>${t.duration_seconds != null ? _fmt_dur(t.duration_seconds) : '—'}</td>
          <td title="${_esc(t.completed_at || '')}">${t.completed_at ? _fmt_utc_ts(t.completed_at) : '—'}</td>
          <td>${_changed_count(t.changed_files_json)}</td>
        </tr>
      `).join('');
    } catch (e) {
      this._renderTaskPagination();
      tbody.innerHTML = `<tr><td colspan="7" class="rv-empty">載入失敗：${e.message}</td></tr>`;
    }
  }

  async _loadRuns() {
    const tbody = document.getElementById('orc-run-tbody');
    if (!tbody) return;
    try {
      const data = await this._get('/api/orchestrator/runs?limit=100');
      this._lastRuns = data.runs || [];
      this._renderNextTickEstimate(this._lastRuns);
      const displayRuns = (data.runs || []).slice(0, 10);
      if (!displayRuns.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="rv-empty">無排程紀錄</td></tr>';
        return;
      }
      tbody.innerHTML = displayRuns.map(r => `
        <tr>
          <td style="white-space:nowrap" title="${_esc(r.tick_at || '')}">${_fmt_utc_ts(r.tick_at)}</td>
          <td>${r.runner}</td>
          <td><span class="orc-outcome-${_outcome_class(r.outcome)}">${r.outcome}</span></td>
          <td>${r.task_id ?? '—'}</td>
          <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(r.message||'')}</td>
        </tr>
      `).join('');
    } catch (e) {
      this._lastRuns = [];
      this._renderNextTickEstimate(this._lastRuns);
      tbody.innerHTML = `<tr><td colspan="5" class="rv-empty">載入失敗：${e.message}</td></tr>`;
    }
  }

  _changeTaskPage(delta) {
    const maxPage = Math.max(1, Math.ceil(this._taskTotal / this._taskPageSize));
    const nextPage = Math.min(maxPage, Math.max(1, this._taskPage + delta));
    if (nextPage === this._taskPage) return;
    this._taskPage = nextPage;
    this._loadTasks();
  }

  _renderTaskPagination() {
    const infoEl = document.getElementById('orc-task-page-info');
    const prevBtn = document.getElementById('orc-task-prev-btn');
    const nextBtn = document.getElementById('orc-task-next-btn');
    if (!infoEl || !prevBtn || !nextBtn) return;

    const total = this._taskTotal;
    const maxPage = Math.max(1, Math.ceil(total / this._taskPageSize));
    const page = Math.min(maxPage, Math.max(1, this._taskPage));
    const start = total ? (page - 1) * this._taskPageSize + 1 : 0;
    const end = total ? Math.min(page * this._taskPageSize, total) : 0;

    infoEl.textContent = total ? `${start}-${end} / 共 ${total} 筆（第 ${page}/${maxPage} 頁）` : '0 筆資料';
    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= maxPage;
  }

  _renderNextTickEstimate(runs) {
    const plannerEl = document.getElementById('orc-next-planner-at');
    const workerEl = document.getElementById('orc-next-worker-at');
    const noteEl = document.getElementById('orc-next-tick-note');
    if (!plannerEl || !workerEl || !noteEl) return;

    if (!this._schedulerEnabled) {
      plannerEl.textContent = '已暫停';
      workerEl.textContent = '已暫停';
      noteEl.textContent = '排程目前為暫停狀態';
      return;
    }

    const plannerNext = _next_tick_by_runner(runs, 'planner');
    const workerNext = _next_tick_by_runner(runs, 'worker');
    plannerEl.textContent = plannerNext ? `${_fmt_local_ts(plannerNext)}（${_fmt_remaining(plannerNext)}）` : '—';
    workerEl.textContent = workerNext ? `${_fmt_local_ts(workerNext)}（${_fmt_remaining(workerNext)}）` : '—';
    noteEl.textContent = '以最近一次 tick + 10 分鐘推估';
  }

  async _loadDetail(taskId) {
    const container = document.getElementById('orc-detail-content');
    if (!container) return;
    container.innerHTML = '<p>載入中…</p>';
    this._showDetail();
    try {
      const t = await this._get(`/api/orchestrator/tasks/${taskId}`);
      const files = _parse_files(t.changed_files_json);
      container.innerHTML = `
        <div style="margin-bottom:16px">
          <h3>${_esc(t.title || '—')}</h3>
          <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:0.85rem;color:var(--text-muted)">
            <span>ID: ${t.id}</span>
            <span>Slot: ${_fmt_slot(t.slot_key)}</span>
            <span>狀態: <b>${t.status}</b></span>
            ${t.planner_source ? `<span>Planner 來源: <b>${_esc(t.planner_source)}</b>${t.planner_provider ? ` (${_esc(t.planner_provider)})` : ''}</span>` : ''}
            ${t.worker_requested_provider ? `<span>Worker: <b>${_esc(t.worker_requested_provider)}</b>${t.worker_runtime ? ` → ${_esc(t.worker_runtime)}` : ''}${t.worker_execution_mode ? ` (${_esc(t.worker_execution_mode)})` : ''}</span>` : ''}
            ${t.gate_verdict ? `<span>Gate: <b>${_esc(t.gate_verdict)}</b>${t.gate_reason ? ` (${_esc(t.gate_reason)})` : ''}</span>` : ''}
            ${t.duration_seconds != null ? `<span>耗時: ${_fmt_dur(t.duration_seconds)}</span>` : ''}
            ${t.started_at ? `<span title="${_esc(t.started_at)}">開始: ${_fmt_utc_ts(t.started_at)}</span>` : ''}
            ${t.completed_at ? `<span title="${_esc(t.completed_at)}">結束: ${_fmt_utc_ts(t.completed_at)}</span>` : ''}
          </div>
        </div>

        <details open style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📋 Prompt（任務指令）</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:400px;font-size:0.82rem;white-space:pre-wrap">${_esc(t.prompt_text || '（無）')}</pre>
        </details>

        <details ${t.completed_text ? 'open' : ''} style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">✅ Completed（執行結果）</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:400px;font-size:0.82rem;white-space:pre-wrap">${_esc(t.completed_text || '（尚未完成）')}</pre>
        </details>

        ${t.task_contract ? `
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📐 Task Contract（規範）</summary>
          <pre style="background:#0f172a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(t.task_contract)}</pre>
        </details>` : ''}

        ${t.task_result ? `
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🧪 Task Result（Gate 驗收）</summary>
          <pre style="background:#0f172a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(t.task_result)}</pre>
        </details>` : ''}

        ${files.length ? `
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📂 異動檔案（${files.length} 個）</summary>
          <ul style="margin:0;padding-left:20px;font-size:0.85rem">
            ${files.map(f => `<li><code>${_esc(f)}</code></li>`).join('')}
          </ul>
        </details>` : ''}

        ${t.codex_stdout_tail ? `
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🖥 Worker 輸出（後 200 行）</summary>
          <pre style="background:#0d0d1a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(t.codex_stdout_tail)}</pre>
        </details>` : ''}

        ${t.worker_fallback_reason ? `
        <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.35);border-radius:6px;padding:10px;margin-bottom:12px">
          <b>Worker Fallback：</b> ${_esc(t.worker_fallback_reason)}
        </div>` : ''}

        ${t.error_message ? `
        <div style="background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.4);border-radius:6px;padding:10px;margin-bottom:12px">
          <b>錯誤訊息：</b> ${_esc(t.error_message)}
        </div>` : ''}
      `;
    } catch (e) {
      container.innerHTML = `<p style="color:red">載入失敗：${e.message}</p>`;
    }
  }

  _showList() {
    document.getElementById('orc-list-view')?.classList.remove('rv-hidden');
    document.getElementById('orc-detail-view')?.classList.add('rv-hidden');
  }

  _showDetail() {
    document.getElementById('orc-list-view')?.classList.add('rv-hidden');
    document.getElementById('orc-detail-view')?.classList.remove('rv-hidden');
  }
}

function _esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _fmt_slot(slotKey) {
  const s = String(slotKey || '').trim();
  if (!/^\d{12}$/.test(s)) return s || '—';
  const y = s.slice(0, 4);
  const mo = s.slice(4, 6);
  const d = s.slice(6, 8);
  const h = s.slice(8, 10);
  const mi = s.slice(10, 12);
  return `${y}/${mo}/${d} ${h}:${mi}`;
}

function _parse_utc_timestamp(raw) {
  const s = String(raw || '').trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(s)) {
    return new Date(s.replace(' ', 'T') + 'Z');
  }
  if (/^\d{4}-\d{2}-\d{2}T/.test(s) && !/[zZ]$|[+\-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + 'Z');
  }
  return new Date(s);
}

function _fmt_utc_ts(raw) {
  const d = _parse_utc_timestamp(raw);
  if (!d || Number.isNaN(d.getTime())) return '—';
  return _fmt_local_ts(d);
}

function _fmt_local_ts(dateObj) {
  return dateObj.toLocaleString('zh-TW', {
    timeZone: 'Asia/Taipei',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function _next_tick_by_runner(runs, runner) {
  const latest = (runs || []).find((r) => r.runner === runner);
  if (!latest?.tick_at) return null;
  const at = _parse_utc_timestamp(latest.tick_at);
  if (!at || Number.isNaN(at.getTime())) return null;
  const intervalMs = 600 * 1000;
  let nextMs = at.getTime() + intervalMs;
  const nowMs = Date.now();
  if (nextMs <= nowMs) {
    const missed = Math.floor((nowMs - nextMs) / intervalMs) + 1;
    nextMs += missed * intervalMs;
  }
  return new Date(nextMs);
}

function _fmt_remaining(targetDate) {
  const diffMs = targetDate.getTime() - Date.now();
  if (diffMs <= 0) return '即將執行';
  const totalSec = Math.floor(diffMs / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s}s 後`;
}

function _fmt_dur(s) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s/60)}m${s%60}s`;
  return `${Math.floor(s/3600)}h${Math.floor((s%3600)/60)}m`;
}

function _changed_count(json) {
  try { return JSON.parse(json || '[]').length + ' 個'; } catch { return '—'; }
}

function _parse_files(json) {
  try { return JSON.parse(json || '[]'); } catch { return []; }
}

function _outcome_class(outcome) {
  if (!outcome) return 'neutral';
  if (outcome.includes('PRODUCED') || outcome.includes('CLAIMED') || outcome.includes('FINALIZED')) return 'success';
  if (outcome.includes('FAILED')) return 'error';
  if (outcome.includes('SKIP') || outcome.includes('HEARTBEAT')) return 'muted';
  return 'neutral';
}
