import { getApiUrl } from '../config/apiConfig.js';

export class OrchestrationManager {
  constructor(app) {
    this.app = app;
    this._initialized = false;
    this._schedulerEnabled = true;
    this._lastRuns = [];
    this._ctoRuns = [];
    this._nextPlannerTickEstimate = null;
    this._nextWorkerTickEstimate = null;
    this._taskPage = 1;
    this._taskPageSize = 10;
    this._taskTotal = 0;
    this._plannerNextAt = null;
    this._workerNextAt = null;
    this._countdownTimer = null;
    this._countdownRefreshPromise = null;
    this._countdownRefreshRetryAt = 0;
    this._lastProviderData = null;
    this._providerHintOverride = null;
    this._providerHintResetTimer = null;
    this._ctoSelectedRunId = null;
    // CTO-specific state
    this._ctoSchedulerEnabled = true;
    this._ctoNextPlannerAt = null;
    this._ctoCountdownTimer = null;
    this._ctoCountdownRefreshPromise = null;
    this._ctoCountdownRefreshRetryAt = 0;
    this._lastCtoProviderData = null;
    this._ctoProviderHintOverride = null;
    this._ctoProviderHintResetTimer = null;
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
    document.getElementById('orc-cto-refresh-btn')?.addEventListener('click', () => this._loadCtoAll());
    document.getElementById('orc-cto-date-filter')?.addEventListener('change', () => this._loadCtoRuns());
    document.getElementById('orc-cto-status-filter')?.addEventListener('change', () => this._loadCtoRuns());
    document.getElementById('orc-cto-back-btn')?.addEventListener('click', () => this._showCtoList());
    document.getElementById('cto-scheduler-toggle-btn')?.addEventListener('click', () => this._toggleCtoScheduler());
    document.getElementById('orc-cto-run-now-btn')?.addEventListener('click', () => this._triggerCtoRunNow());
    document.getElementById('orc-cto-provider-save-btn')?.addEventListener('click', () => this._saveCtoProviders());

    document.getElementById('orc-task-tbody')?.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-task-id]');
      if (row) this._loadDetail(Number(row.dataset.taskId));
    });

    document.getElementById('orc-cto-run-tbody')?.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-cto-run-id]');
      if (row) this._loadCtoRunDetail(row.dataset.ctoRunId);
    });
  }

  async _get(path) {
    const res = await fetch(getApiUrl(path));
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  }

  async _loadAll() {
    await Promise.all([this._loadSummary(), this._loadProviders(), this._loadTasks(), this._loadRuns(), this._loadCtoAll()]);
  }

  _renderPlannerTriggerTrace({ requestId = '—', outcome = '—', taskId = '—', note = '' } = {}) {
    const requestEl = document.getElementById('orc-planner-last-request-id');
    const outcomeEl = document.getElementById('orc-planner-last-outcome');
    const taskEl = document.getElementById('orc-planner-last-task-id');
    const noteEl = document.getElementById('orc-planner-last-note');
    if (requestEl) requestEl.textContent = requestId || '—';
    if (outcomeEl) outcomeEl.textContent = outcome || '—';
    if (taskEl) taskEl.textContent = taskId == null ? '—' : String(taskId);
    if (noteEl) noteEl.textContent = note || '—';
  }

  _syncPlannerTraceFromRuns(runs = []) {
    const latestPlannerRun = (runs || []).find((run) => String(run?.runner || '').toLowerCase() === 'planner');
    if (!latestPlannerRun) return;
    this._renderPlannerTriggerTrace({
      requestId: latestPlannerRun.request_id || '—',
      outcome: latestPlannerRun.outcome || '—',
      taskId: latestPlannerRun.task_id,
      note: latestPlannerRun.message || '—',
    });
  }

  async _loadCtoAll() {
    await Promise.all([this._loadCtoSummary(), this._loadCtoPending(), this._loadCtoRuns(), this._loadCtoProviders()]);
  }

  _startCountdownTimer() {
    if (this._countdownTimer) return;
    this._countdownTimer = setInterval(() => {
      this._tickCountdown();
    }, 1000);
  }

  _stopCountdownTimer() {
    if (!this._countdownTimer) return;
    clearInterval(this._countdownTimer);
    this._countdownTimer = null;
  }

  _tickCountdown() {
    const plannerState = _countdown_state(this._plannerNextAt);
    const workerState = _countdown_state(this._workerNextAt);
    this._renderCountdownValues(plannerState, workerState);

    if (!plannerState.due && !workerState.due) {
      this._countdownRefreshRetryAt = 0;
      return;
    }

    const nowMs = Date.now();
    if (this._countdownRefreshPromise || nowMs < this._countdownRefreshRetryAt) return;
    this._countdownRefreshRetryAt = nowMs + 5000;
    this._countdownRefreshPromise = this._loadAll()
      .catch((error) => {
        console.error('[OrchestratorManager] auto refresh error', error);
      })
      .finally(() => {
        this._countdownRefreshPromise = null;
      });
    this._renderCountdownValues(plannerState, workerState);
  }

  _renderCountdownValues(plannerState = _countdown_state(this._plannerNextAt), workerState = _countdown_state(this._workerNextAt)) {
    const plannerEl = document.getElementById('orc-next-planner-at');
    const workerEl = document.getElementById('orc-next-worker-at');
    const noteEl = document.getElementById('orc-next-tick-note');
    if (!plannerEl || !workerEl || !noteEl) return;

    plannerEl.textContent = plannerState.label;
    workerEl.textContent = workerState.label;

    if (this._countdownRefreshPromise && (plannerState.due || workerState.due)) {
      noteEl.textContent = '排程到點，正在自動刷新…';
      return;
    }

    noteEl.textContent = '每秒倒數，歸零後自動刷新';
  }

  async _loadSummary() {
    try {
      const data = await this._get('/api/orchestrator/summary');
      const daemonMode = String(data.copilot_daemon_status || '').toLowerCase();
      const workerState = data.worker_state || (
        data.worker_busy || ['busy', 'claiming', 'finalizing'].includes(daemonMode)
          ? '執行中'
          : data.copilot_daemon_running
            ? '待命中'
            : '未啟動'
      );
      this._schedulerEnabled = Boolean(data.scheduler_enabled);
      this._nextPlannerTickEstimate = data.next_planner_tick_estimate || null;
      this._nextWorkerTickEstimate = data.next_worker_tick_estimate || null;
      document.getElementById('orc-total').textContent = data.total_today ?? '—';
      document.getElementById('orc-running').textContent = data.task_counts?.RUNNING ?? 0;
      document.getElementById('orc-completed').textContent = data.task_counts?.COMPLETED ?? 0;
      this._renderSchedulerState(this._schedulerEnabled);
      this._renderNextTickEstimate(this._lastRuns, this._nextPlannerTickEstimate, this._nextWorkerTickEstimate);
      this._renderComboLabel(data.combo_label);
      const workerEl = document.getElementById('orc-worker-status');
      if (data.worker_provider === 'copilot-daemon') {
        if (workerState === '執行中') {
          workerEl.textContent = `執行中 (PID ${data.worker_pid || data.copilot_daemon_pid || '—'})`;
          workerEl.style.color = 'var(--warning-color, #f59e0b)';
        } else if (workerState === '待命中') {
          workerEl.textContent = `待命中 (PID ${data.copilot_daemon_pid || '—'})`;
          workerEl.style.color = 'var(--success-color, #10b981)';
        } else {
          workerEl.textContent = '未啟動';
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
      this._lastProviderData = data;
      this._populateProviderSelect('orc-planner-provider', data.planner_options || [], data.planner_provider);
      this._populateProviderSelect('orc-worker-provider', data.worker_options || [], data.worker_provider);
      const copilotModelInput = document.getElementById('orc-worker-copilot-model');
      if (copilotModelInput) copilotModelInput.value = data.worker_copilot_model || '';
      this._populateCopilotModelPresets(data.worker_copilot_model_presets || []);
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

  _populateCopilotModelPresets(options) {
    const datalist = document.getElementById('orc-worker-copilot-model-options');
    if (!datalist) return;
    const presetValues = (options || [])
      .map((option) => String(option?.value || '').trim())
      .filter(Boolean);
    const merged = Array.from(new Set(['auto', 'gpt-5-mini', ...presetValues]));
    datalist.innerHTML = merged.map((value) => `<option value="${_esc(value)}"></option>`).join('');
  }

  _renderProviderHint(data) {
    const hintEl = document.getElementById('orc-provider-hint');
    if (!hintEl) return;
    const override = this._providerHintOverride;
    if (override && override.until > Date.now()) {
      hintEl.textContent = override.message;
      hintEl.style.color = override.color;
      return;
    }
    if (override) this._providerHintOverride = null;
    const unavailable = []
      .concat(data.planner_options || [], data.worker_options || [])
      .filter((option) => !option.available)
      .map((option) => `${option.label}：${option.reason}`);
    if (unavailable.length) {
      hintEl.textContent = unavailable.join(' | ');
      hintEl.style.color = 'var(--warning-color, #f59e0b)';
      return;
    }
    const workerProvider = document.getElementById('orc-worker-provider')?.value || data.worker_provider;
    const copilotModel = data.worker_copilot_model || document.getElementById('orc-worker-copilot-model')?.value || '';
    const copilotModelText = (
      (workerProvider === 'copilot' || workerProvider === 'copilot-daemon')
        ? ` Copilot Model：${copilotModel || '預設'}`
        : ''
    );
    const daemonOption = (data.worker_options || []).find((option) => option.value === 'copilot-daemon');
    if (daemonOption) {
      hintEl.textContent = `切換後會影響下一次 planner / worker 啟動；不會中斷目前已在執行的任務。${daemonOption.reason ? ` Copilot Daemon：${daemonOption.reason}` : ''}${copilotModelText}`;
      hintEl.style.color = 'var(--text-muted, #8b949e)';
      return;
    }
    hintEl.textContent = `切換後會影響下一次 planner / worker 啟動；不會中斷目前已在執行的任務。${copilotModelText}`;
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
    const workerCopilotModelInput = document.getElementById('orc-worker-copilot-model');
    const btn = document.getElementById('orc-provider-save-btn');
    if (!plannerSelect || !workerSelect || !btn) return;

    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = '套用中…';

    try {
      const normalizedCopilotModel = _normalizeCopilotModel(workerCopilotModelInput?.value || '');
      const workerProvider = workerSelect.value;
      if ((workerProvider === 'copilot' || workerProvider === 'copilot-daemon') && !_isValidCopilotModel(normalizedCopilotModel)) {
        throw new Error('Copilot model 格式無效，建議使用 auto 或 gpt-5-mini');
      }
      if (workerCopilotModelInput) workerCopilotModelInput.value = normalizedCopilotModel;
      const data = await this._post('/api/orchestrator/providers', {
        planner_provider: plannerSelect.value,
        worker_provider: workerSelect.value,
        worker_copilot_model: normalizedCopilotModel,
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
      const pidText = data.pid ? `（PID ${data.pid}）` : '';
      const msg = (!isPlanner && data.delegated_to === 'copilot-daemon')
        ? `Worker 已委派給 Copilot Daemon${pidText}`
        : `${isPlanner ? 'Planner' : 'Worker'} 已觸發${pidText}`;
      if (isPlanner) {
        this._renderPlannerTriggerTrace({
          requestId: data.request_id || '—',
          outcome: 'RUNNING',
          taskId: '—',
          note: msg,
        });
      }
      this.app?.uiManager?.showNotification(msg, 'success');
      this._showInlineRunnerFeedback('success', msg);
      if (isPlanner) this._showInlineRunnerFeedback('info', 'Planner 已送出，正在等待結果…', 20000);
      await this._loadAll();
      if (isPlanner) {
        const outcome = await this._waitForRunnerOutcome('planner', data.request_id, data.triggered_at);
        if (outcome) {
          this._renderPlannerTriggerTrace({
            requestId: data.request_id || outcome.request_id || '—',
            outcome: outcome.outcome || '—',
            taskId: outcome.task_id,
            note: outcome.message || '—',
          });
          const feedback = _runner_outcome_feedback(outcome);
          this.app?.uiManager?.showNotification(feedback.message, feedback.level);
          this._showInlineRunnerFeedback(feedback.level, feedback.message);
          await this._loadAll();
        } else {
          this._renderPlannerTriggerTrace({
            requestId: data.request_id || '—',
            outcome: 'TIMEOUT',
            taskId: '—',
            note: 'Planner 已送出，但等待期間內尚未取得最終結果。',
          });
          this._showInlineRunnerFeedback('warning', 'Planner 已送出，但尚未取得最終結果。請稍後重新整理。');
        }
      }
    } catch (e) {
      this.app?.uiManager?.showNotification(`${isPlanner ? 'Planner' : 'Worker'} 立即執行失敗：${e.message}`, 'error');
      if (isPlanner) {
        this._renderPlannerTriggerTrace({
          requestId: '—',
          outcome: 'REQUEST_FAILED',
          taskId: '—',
          note: `Planner 立即執行失敗：${e.message}`,
        });
        this._showInlineRunnerFeedback('error', `Planner 立即執行失敗：${e.message}`);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  async _waitForRunnerOutcome(runner, requestId, triggeredAt, timeoutMs = 70000) {
    const triggerMs = _parse_utc_timestamp(triggeredAt)?.getTime() ?? Date.now();
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      try {
        if (requestId) {
          const data = await this._get(`/api/orchestrator/run-status?runner=${encodeURIComponent(runner)}&request_id=${encodeURIComponent(requestId)}`);
          if (data?.final && data?.run) return data.run;
        } else {
          const data = await this._get('/api/orchestrator/runs?limit=20');
          const outcome = _find_recent_runner_outcome(data.runs || [], runner, triggerMs);
          if (outcome) return outcome;
        }
      } catch (error) {
        console.error('[OrchestratorManager] wait outcome error', error);
      }

      await _sleep(1500);
    }

    return null;
  }

  _showInlineRunnerFeedback(level, message, ttlMs = 12000) {
    const palette = {
      info: 'var(--accent-color, #58a6ff)',
      success: 'var(--success-color, #10b981)',
      warning: 'var(--warning-color, #f59e0b)',
      error: 'var(--danger-color, #ef4444)',
    };

    this._providerHintOverride = {
      message,
      color: palette[level] || 'var(--text-muted, #8b949e)',
      until: Date.now() + ttlMs,
    };
    if (this._providerHintResetTimer) clearTimeout(this._providerHintResetTimer);
    this._providerHintOverride.until = Date.now() + ttlMs;
    this._providerHintResetTimer = setTimeout(() => {
      this._providerHintOverride = null;
      this._providerHintResetTimer = null;
      if (this._lastProviderData) this._renderProviderHint(this._lastProviderData);
    }, ttlMs);
    if (this._lastProviderData) {
      this._renderProviderHint(this._lastProviderData);
      return;
    }
    const hintEl = document.getElementById('orc-provider-hint');
    if (!hintEl) return;
    hintEl.textContent = this._providerHintOverride.message;
    hintEl.style.color = this._providerHintOverride.color;
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
          <td title="${_esc(t.planner_published_at || t.created_at || '')}">${_fmt_utc_ts(t.planner_published_at || t.created_at)}</td>
          <td>
            ${_esc(t.title || '—')}
            ${t.planner_source === 'fallback' ? '<span class="orc-plan-badge orc-plan-badge-fallback">FALLBACK</span>' : ''}
            ${t.status === 'RUNNING' ? `
              <div style="margin-top:4px;font-size:0.75rem;color:var(--text-muted,#8b949e)">
                ${t.last_output_at ? `最後輸出：${_fmt_utc_ts(t.last_output_at)}` : '最後輸出：—'}
                ${t.last_progress_summary ? ` · ${_esc(t.last_progress_summary)}` : ''}
                ${t.progress_note ? ` · ${_esc(t.progress_note)}` : ''}
                ${(t.progress_state === 'stale' || t.progress_state_code === 'STUCK_SUSPECTED' || t.progress_stale) ? ` · <span style="color:#f59e0b">疑似卡住</span>` : ''}
                ${(t.progress_state === 'no_output' || t.progress_state_code === 'RUNNING_NO_OUTPUT') ? ` · <span style="color:#f59e0b">尚無輸出</span>` : ''}
              </div>` : ''}
          </td>
          <td><span class="orc-status-badge orc-status-${(t.status||'').toLowerCase()}">${t.status}</span></td>
          <td>${t.duration_seconds != null ? _fmt_dur(t.duration_seconds) : '—'}</td>
          <td title="${_esc(t.worker_completed_at || t.completed_at || '')}">${(t.worker_completed_at || t.completed_at) ? _fmt_utc_ts(t.worker_completed_at || t.completed_at) : '—'}</td>
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
      const data = await this._get('/api/orchestrator/runs?limit=500');
      this._lastRuns = data.runs || [];
      this._syncPlannerTraceFromRuns(this._lastRuns);
      this._renderNextTickEstimate(this._lastRuns, this._nextPlannerTickEstimate, this._nextWorkerTickEstimate);
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
      this._renderNextTickEstimate(this._lastRuns, this._nextPlannerTickEstimate, this._nextWorkerTickEstimate);
      tbody.innerHTML = `<tr><td colspan="5" class="rv-empty">載入失敗：${e.message}</td></tr>`;
    }
  }

  async _loadCtoSummary() {
    try {
      const data = await this._get('/api/orchestrator/cto/summary');
      const latestRun = data.latest_run || {};
      const latestAt = latestRun.completed_at || latestRun.started_at || '—';
      const _setT = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
      _setT('cto-frequency-mode', data.frequency_mode || '—');
      _setT('cto-pending-count', data.pending_count ?? 0);
      _setT('cto-approved-count', data.approved_count ?? 0);
      _setT('cto-merged-count', data.merged_count ?? 0);
      _setT('cto-rejected-count', data.rejected_count ?? 0);
      _setT('cto-deferred-count', data.deferred_count ?? 0);
      _setT('cto-superseded-count', data.superseded_count ?? 0);
      _setT('cto-duplicate-count', data.duplicate_count ?? 0);
      _setT('cto-latest-run-at', latestAt ? _fmt_utc_ts(latestAt) : '—');
      _setT('cto-next-run-at', data.next_run_estimate ? _fmt_utc_ts(data.next_run_estimate) : '—');
      _setT('cto-latest-run-summary', latestRun.summary || '—');
      this._selectedCtoRunId = this._selectedCtoRunId || latestRun.run_id || null;
      // Scheduler state
      this._ctoSchedulerEnabled = !!data.scheduler_enabled;
      this._renderCtoSchedulerState(this._ctoSchedulerEnabled);
      // Next planner countdown
      this._renderCtoNextTickEstimate(data.next_run_estimate || null);
    } catch (e) {
      console.error('[OrchestrationManager] CTO summary error', e);
    }
  }

  async _loadCtoPending() {
    const tbody = document.getElementById('orc-cto-pending-tbody');
    if (!tbody) return;
    try {
      const data = await this._get('/api/orchestrator/cto/pending?limit=100');
      const commits = data.commits || [];
      if (!commits.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="rv-empty">目前沒有待審核提交</td></tr>';
        return;
      }
      tbody.innerHTML = commits.map((item) => `
        <tr>
          <td>${item.task_id ?? '—'}</td>
          <td>${_esc(item.task_title || '—')}</td>
          <td>${_esc(item.integration_group || '—')}</td>
          <td>${_esc(item.review_priority || '—')}</td>
          <td>${_esc(item.source_branch || '—')}</td>
          <td title="${_esc(item.commit_sha || '')}">${_esc((item.commit_sha || '—').slice(0, 12))}</td>
          <td>${_fmt_utc_ts(item.created_at || item.updated_at)}</td>
        </tr>
      `).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="rv-empty">載入失敗：${e.message}</td></tr>`;
    }
  }

  async _loadCtoRuns() {
    const tbody = document.getElementById('orc-cto-run-tbody');
    if (!tbody) return;
    try {
      const date = document.getElementById('orc-cto-date-filter')?.value || '';
      const status = document.getElementById('orc-cto-status-filter')?.value || '';
      const params = new URLSearchParams();
      params.set('limit', '20');
      if (date) params.set('date', date.replace(/-/g, ''));
      if (status) params.set('status', status);
      const data = await this._get(`/api/orchestrator/cto/runs?${params}`);
      this._ctoRuns = data.runs || [];
      if (!this._ctoRuns.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="rv-empty">尚無 CTO 批次紀錄</td></tr>';
        return;
      }
      tbody.innerHTML = this._ctoRuns.map((run) => `
        <tr data-cto-run-id="${_esc(run.run_id)}" style="cursor:pointer">
          <td>${_esc(run.run_id || '—')}</td>
          <td>${_fmt_utc_ts(run.started_at)}</td>
          <td>${_fmt_utc_ts(run.completed_at)}</td>
          <td>${_esc(run.frequency_mode || '—')}</td>
          <td>${run.candidate_count ?? 0}</td>
          <td>${run.approved_count ?? 0}</td>
          <td>${run.merged_count ?? 0}</td>
          <td>${run.rejected_count ?? 0}</td>
          <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(run.summary || '—')}</td>
        </tr>
      `).join('');
      if (!this._selectedCtoRunId || !this._ctoRuns.some((run) => run.run_id === this._selectedCtoRunId)) {
        this._selectedCtoRunId = this._ctoRuns[0]?.run_id || null;
      }
      if (this._selectedCtoRunId) {
        await this._loadCtoRunDetail(this._selectedCtoRunId, false);
      }
    } catch (e) {
      this._ctoRuns = [];
      tbody.innerHTML = `<tr><td colspan="9" class="rv-empty">載入失敗：${e.message}</td></tr>`;
    }
  }

  async _loadCtoRunDetail(runId, showDetail = true) {
    const container = document.getElementById('orc-cto-detail-content');
    if (!container) return;
    container.innerHTML = '<p>載入中…</p>';
    if (showDetail) this._showCtoDetail();
    try {
      this._selectedCtoRunId = runId;
      const data = await this._get(`/api/orchestrator/cto/runs/${encodeURIComponent(runId)}`);
      const run = data.run || {};
      const reviews = data.reviews || [];
      const report = await this._get(`/api/orchestrator/cto/reports/${encodeURIComponent(runId)}`);
      const reportJson = report.report_json || {};
      const reportMd = report.report_md || '';
      const intel = reportJson.intelligence || {};
      const exec = intel.executive_summary || {};
      const enrichedDecisions = reportJson.decisions || [];
      const roadmap = intel.roadmap || [];
      const healthScore = intel.health_score ?? exec.health_score ?? null;
      const verdict = intel.verdict || exec.verdict || null;

      const _verdictStyle = (v) => ({ GO: 'color:#3fb950', CAUTION: 'color:#d29922', STOP: 'color:#f85149' }[v] || '');
      const _verdictIcon = (v) => ({ GO: '✅', CAUTION: '⚠️', STOP: '🛑' }[v] || '—');
      const _sevColor = (s) => ({ CRITICAL: '#f85149', HIGH: '#d29922', MEDIUM: '#58a6ff', LOW: '#3fb950' }[s] || '#8b949e');
      const _priIcon = (p) => ({ IMMEDIATE: '🚨', HIGH: '🟠', SHORT: '⏰', MEDIUM: '—', LOW: '🟢' }[p] || '—');
      const _healthBar = (n) => { const v = Math.max(0, Math.min(100, n ?? 0)); const b = Math.round(v / 10); return `${'█'.repeat(b)}${'░'.repeat(10 - b)}`; };

      // ── Intelligence Panel ─────────────────────────────────────────────────
      const intelHtml = (intel.schema_version || enrichedDecisions.length > 0) ? `
        <div class="card" style="margin-bottom:16px;border:1px solid ${verdict ? _sevColor(verdict === 'STOP' ? 'CRITICAL' : verdict === 'CAUTION' ? 'HIGH' : 'LOW') : 'var(--border-color)'}">
          <div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--border-color)">
            <span style="font-size:1.1rem;font-weight:700">${_verdictIcon(verdict)} CTO Verdict: <span style="${_verdictStyle(verdict)}">${verdict || '—'}</span></span>
            <span>Health Score: <b style="font-size:1.05rem">${healthScore != null ? healthScore + '/100' : '—'}</b></span>
            ${healthScore != null ? `<span style="font-family:monospace;letter-spacing:1px;color:#58a6ff">[${_healthBar(healthScore)}]</span>` : ''}
          </div>

          <!-- Top Risks -->
          ${exec.top_risks && exec.top_risks.length ? `
          <div style="padding:10px 14px;border-bottom:1px solid var(--border-color)">
            <div style="font-weight:600;margin-bottom:8px">🔺 Top Risks</div>
            ${exec.top_risks.map((r, i) => `
              <div style="margin-bottom:8px;padding:8px;background:rgba(248,81,73,.06);border-radius:6px;border-left:3px solid ${_sevColor(r.severity)}">
                <span style="font-size:0.8rem;font-weight:600;color:${_sevColor(r.severity)}">${r.severity}</span>
                <span style="margin-left:8px;font-size:0.82rem">Task #${r.task_id} | Impact: ${r.impact_score}/100 | ${r.urgency}</span>
                <div style="font-size:0.82rem;color:var(--text-muted,#8b949e);margin-top:4px">${_esc(r.description || r.decision || '—')}</div>
              </div>
            `).join('')}
          </div>` : ''}

          <!-- Top Actions -->
          ${exec.top_actions && exec.top_actions.length ? `
          <div style="padding:10px 14px;border-bottom:1px solid var(--border-color)">
            <div style="font-weight:600;margin-bottom:8px">⚡ Top Actions</div>
            ${exec.top_actions.map((a) => `
              <div style="margin-bottom:6px;padding:7px 10px;background:rgba(56,139,253,.06);border-radius:6px">
                <span style="font-size:0.8rem;font-weight:600">${_priIcon(a.priority)} [${a.priority}]</span>
                <span style="margin-left:6px;font-size:0.82rem">${_esc(a.action || '—')}</span>
                ${a.create_task ? '<span style="margin-left:8px;font-size:0.75rem;background:rgba(63,185,80,.15);color:#3fb950;border-radius:3px;padding:1px 5px">⬡ 建議建立任務</span>' : ''}
                <div style="font-size:0.78rem;color:var(--text-muted,#8b949e);margin-top:3px">${_esc(a.expected_benefit || '')}</div>
              </div>
            `).join('')}
          </div>` : ''}

          <!-- Roadmap -->
          ${roadmap.length ? `
          <div style="padding:10px 14px">
            <div style="font-weight:600;margin-bottom:8px">🗺 Recommended Roadmap</div>
            <ol style="margin:0;padding-left:18px">
              ${roadmap.map((item) => `
                <li style="margin-bottom:5px;font-size:0.82rem">
                  ${_priIcon(item.priority)} <b>[${item.priority || '—'}]</b> ${_esc(item.title || '—')}
                  <span style="color:var(--text-muted,#8b949e);margin-left:6px">Task #${item.task_id} · ${_esc(item.category || '—')} · ${item.urgency || '—'}</span>
                </li>
              `).join('')}
            </ol>
          </div>` : ''}
        </div>
      ` : '';

      // ── Enriched Findings ──────────────────────────────────────────────────
      const findingsHtml = enrichedDecisions.length ? `
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📋 Detailed Findings (${enrichedDecisions.length})</summary>
          ${enrichedDecisions.map((d) => {
            const sc = d.scoring || {};
            const ac = d.action || {};
            return `
              <div style="border:1px solid var(--border-color,#30363d);border-radius:8px;padding:11px 13px;margin-bottom:10px;border-left:3px solid ${_sevColor(sc.severity)}">
                <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:6px">
                  <span style="font-weight:600;font-size:0.88rem">Task #${d.task_id ?? '—'}</span>
                  <span style="font-size:0.78rem;font-weight:700;color:${_sevColor(sc.severity)};background:rgba(0,0,0,.25);padding:1px 6px;border-radius:3px">${sc.severity || '—'}</span>
                  <span style="font-size:0.78rem;color:var(--text-muted,#8b949e)">${_esc(d.decision || '—')}</span>
                  <span style="font-size:0.78rem;color:#58a6ff">cat: ${_esc(d.category || '—')}</span>
                  <span style="font-size:0.78rem;color:var(--text-muted,#8b949e)">impact: ${sc.impact_score ?? '—'}/100</span>
                  <span style="font-size:0.78rem;color:var(--text-muted,#8b949e)">conf: ${sc.confidence != null ? Math.round(sc.confidence * 100) + '%' : '—'}</span>
                  <span style="font-size:0.78rem;color:var(--text-muted,#8b949e)">${sc.urgency || '—'}</span>
                </div>
                <div style="font-size:0.82rem;color:var(--text-muted,#8b949e);margin-bottom:6px">${_esc(d.reason || '—')}</div>
                <div style="font-size:0.82rem;background:rgba(56,139,253,.06);border-radius:5px;padding:6px 9px">
                  ${_priIcon(ac.priority)} <b>[${ac.priority || '—'}]</b> ${_esc(ac.action || '—')}
                  ${ac.create_task ? '<span style="margin-left:8px;font-size:0.75rem;background:rgba(63,185,80,.15);color:#3fb950;border-radius:3px;padding:1px 5px">⬡ 建議建立任務</span>' : ''}
                  <div style="font-size:0.78rem;color:var(--text-muted,#8b949e);margin-top:3px">${_esc(ac.expected_benefit || '')}</div>
                </div>
              </div>
            `;
          }).join('')}
        </details>
      ` : '';

      container.innerHTML = `
        <div style="margin-bottom:16px">
          <h3>${_esc(run.run_id || runId)}</h3>
          <div style="display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;font-size:0.85rem;color:var(--text-muted)">
            <span>Frequency: <b>${_esc(run.frequency_mode || '—')}</b></span>
            <span>Started: <b>${_fmt_utc_ts(run.started_at)}</b></span>
            <span>Completed: <b>${_fmt_utc_ts(run.completed_at)}</b></span>
            <span>Duration: <b>${run.duration_seconds != null ? _fmt_dur(run.duration_seconds) : '—'}</b></span>
            <span>Window: <b>${_fmt_utc_ts(run.checked_from)} → ${_fmt_utc_ts(run.checked_until)}</b></span>
            <span>Merge Branch: <b>${_esc(run.merge_branch || '—')}</b></span>
          </div>
        </div>
        <div class="pt-perf-summary" style="margin-bottom:16px">
          <div class="pt-perf-summary-grid">
            <div><span class="pt-perf-summary-label">Candidates</span><strong>${run.candidate_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Approved</span><strong>${run.approved_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Merged</span><strong>${run.merged_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Rejected</span><strong>${run.rejected_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Deferred</span><strong>${run.deferred_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Superseded</span><strong>${run.superseded_count ?? 0}</strong></div>
            <div><span class="pt-perf-summary-label">Duplicate</span><strong>${run.duplicate_count ?? 0}</strong></div>
          </div>
          <div style="margin-top:10px;color:var(--text-muted,#8b949e)">${_esc(run.summary || '—')}</div>
        </div>

        ${intelHtml}
        ${findingsHtml}

        <details open style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🧾 Report Markdown</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:340px;font-size:0.82rem;white-space:pre-wrap">${_esc(reportMd || '（無）')}</pre>
        </details>
        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🗂 Report JSON</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:340px;font-size:0.82rem;white-space:pre-wrap">${_esc(JSON.stringify(reportJson || {}, null, 2))}</pre>
        </details>
        <div style="margin-bottom:16px">
          <h4 style="margin:0 0 8px">Decision Timeline</h4>
          ${reviews.length ? reviews.map((review) => {
            const steps = _parseGitDecisionSteps(review.decision_steps_json);
            return `
              <div style="border:1px solid var(--border-color,#30363d);border-radius:8px;padding:12px;margin-bottom:10px;background:rgba(13,17,23,.55)">
                <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:0.82rem;color:var(--text-muted,#8b949e)">
                  <span>Task #${review.task_id ?? '—'}</span>
                  <span>Decision: <b>${_esc(review.decision || '—')}</b></span>
                  <span>Commit: <b>${_esc((review.commit_sha || '—').slice(0, 12))}</b></span>
                  <span>Run: <b>${_esc(review.review_run_id || '—')}</b></span>
                </div>
                <div style="margin-top:8px;font-size:0.84rem;color:var(--text-muted,#8b949e)">${_esc(review.review_summary || review.reason || '—')}</div>
                <ol style="margin:10px 0 0;padding-left:18px">
                  ${steps.map((step) => `<li style="margin-bottom:8px"><b>${_esc(step.step || 'step')}</b> · ${_esc(step.status || '—')}<br><span style="color:var(--text-muted,#8b949e)">${_esc(step.summary || '')}</span>${step.evidence != null ? `<pre style="white-space:pre-wrap;background:#0f172a;border:1px solid #30363d;border-radius:6px;padding:8px;margin:6px 0 0">${_esc(JSON.stringify(step.evidence, null, 2))}</pre>` : ''}</li>`).join('')}
                </ol>
              </div>
            `;
          }).join('') : '<div class="rv-empty">尚無決策記錄</div>'}
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<p style="color:red">載入失敗：${e.message}</p>`;
    }
  }

  _showCtoList() {
    document.getElementById('cto-list-view')?.classList.remove('rv-hidden');
    document.getElementById('cto-detail-view')?.classList.add('rv-hidden');
  }

  _showCtoDetail() {
    document.getElementById('cto-list-view')?.classList.add('rv-hidden');
    document.getElementById('cto-detail-view')?.classList.remove('rv-hidden');
  }

  // ─── CTO Scheduler / Countdown ────────────────────────────────────────────

  _renderCtoSchedulerState(enabled) {
    const stateEl = document.getElementById('cto-scheduler-state');
    const toggleBtn = document.getElementById('cto-scheduler-toggle-btn');
    if (stateEl) stateEl.textContent = enabled ? '啟動中' : '已暫停';
    if (toggleBtn) {
      toggleBtn.textContent = enabled ? '暫停' : '啟動';
      toggleBtn.dataset.enabled = enabled ? '1' : '0';
    }
  }

  _renderCtoNextTickEstimate(nextRunEstimate) {
    const el = document.getElementById('cto-next-planner-at');
    const noteEl = document.getElementById('cto-next-tick-note');
    if (!this._ctoSchedulerEnabled) {
      this._ctoNextPlannerAt = null;
      this._stopCtoCountdownTimer();
      if (el) el.textContent = '已暫停';
      if (noteEl) noteEl.textContent = 'CTO 排程目前為暫停狀態';
      return;
    }
    this._ctoNextPlannerAt = _parse_utc_timestamp(nextRunEstimate);
    this._renderCtoCountdownValues();
    if (this._ctoNextPlannerAt) {
      this._startCtoCountdownTimer();
    } else {
      this._stopCtoCountdownTimer();
      if (noteEl) noteEl.textContent = '尚無可用的下一次 CTO 排程時間';
    }
  }

  _startCtoCountdownTimer() {
    if (this._ctoCountdownTimer) return;
    this._ctoCountdownTimer = setInterval(() => this._tickCtoCountdown(), 1000);
  }

  _stopCtoCountdownTimer() {
    if (!this._ctoCountdownTimer) return;
    clearInterval(this._ctoCountdownTimer);
    this._ctoCountdownTimer = null;
  }

  _tickCtoCountdown() {
    const state = _countdown_state(this._ctoNextPlannerAt);
    this._renderCtoCountdownValues(state);
    if (!state.due) {
      this._ctoCountdownRefreshRetryAt = 0;
      return;
    }
    const nowMs = Date.now();
    if (this._ctoCountdownRefreshPromise || nowMs < this._ctoCountdownRefreshRetryAt) return;
    this._ctoCountdownRefreshRetryAt = nowMs + 5000;
    this._ctoCountdownRefreshPromise = this._loadCtoAll()
      .catch((err) => console.error('[OrchestrationManager] CTO auto refresh error', err))
      .finally(() => { this._ctoCountdownRefreshPromise = null; });
  }

  _renderCtoCountdownValues(state = _countdown_state(this._ctoNextPlannerAt)) {
    const el = document.getElementById('cto-next-planner-at');
    const noteEl = document.getElementById('cto-next-tick-note');
    if (el) el.textContent = state.label;
    if (noteEl) {
      if (this._ctoCountdownRefreshPromise && state.due) {
        noteEl.textContent = 'CTO 排程到點，正在自動刷新…';
      } else {
        noteEl.textContent = '每秒倒數，歸零後自動刷新';
      }
    }
  }

  async _toggleCtoScheduler() {
    const enabled = !this._ctoSchedulerEnabled;
    try {
      await this._post('/api/orchestrator/cto/scheduler', { enabled });
      this._ctoSchedulerEnabled = enabled;
      this._renderCtoSchedulerState(enabled);
      if (!enabled) {
        this._stopCtoCountdownTimer();
        this._ctoNextPlannerAt = null;
        const el = document.getElementById('cto-next-planner-at');
        if (el) el.textContent = '已暫停';
      }
    } catch (e) {
      console.error('[OrchestrationManager] CTO toggle scheduler error', e);
    }
  }

  // ─── CTO Providers ────────────────────────────────────────────────────────

  async _loadCtoProviders() {
    try {
      const data = await this._get('/api/orchestrator/cto/providers');
      this._lastCtoProviderData = data;
      const plannerSel = document.getElementById('orc-cto-planner-provider');
      const modelInput = document.getElementById('orc-cto-planner-model');
      const datalist = document.getElementById('orc-cto-planner-model-options');
      const hintEl = document.getElementById('orc-cto-provider-hint');
      if (plannerSel) {
        // Populate options
        const opts = data.planner_options || [];
        if (opts.length) {
          plannerSel.innerHTML = opts.map((o) =>
            `<option value="${_esc(o.value)}"${o.value === data.planner_provider ? ' selected' : ''}>${_esc(o.label)}</option>`
          ).join('');
        } else {
          plannerSel.value = data.planner_provider || 'claude';
        }
      }
      if (modelInput) modelInput.value = data.planner_model || '';
      if (datalist && data.planner_model_presets) {
        datalist.innerHTML = data.planner_model_presets.map((m) => `<option value="${_esc(m)}"></option>`).join('');
      }
      if (hintEl && !this._ctoProviderHintOverride) {
        hintEl.textContent = `目前：${data.planner_provider_label || data.planner_provider || '—'}${data.planner_model ? ' / ' + data.planner_model : ''}`;
      }
    } catch (e) {
      console.error('[OrchestrationManager] CTO providers error', e);
    }
  }

  async _saveCtoProviders() {
    const plannerProvider = document.getElementById('orc-cto-planner-provider')?.value || '';
    const plannerModel = document.getElementById('orc-cto-planner-model')?.value || '';
    try {
      const data = await this._post('/api/orchestrator/cto/providers', {
        planner_provider: plannerProvider,
        planner_model: plannerModel,
      });
      this._showCtoPlannerInlineFeedback('ok', `已套用：${data.planner_provider_label || data.planner_provider}${data.planner_model ? ' / ' + data.planner_model : ''}`);
    } catch (e) {
      this._showCtoPlannerInlineFeedback('error', `儲存失敗：${e.message}`);
    }
  }

  _showCtoPlannerInlineFeedback(level, message, ttlMs = 12000) {
    const hintEl = document.getElementById('orc-cto-provider-hint');
    if (!hintEl) return;
    if (this._ctoProviderHintResetTimer) clearTimeout(this._ctoProviderHintResetTimer);
    hintEl.textContent = message;
    hintEl.style.color = level === 'ok' ? '#3fb950' : level === 'error' ? '#f85149' : '#d29922';
    this._ctoProviderHintOverride = message;
    this._ctoProviderHintResetTimer = setTimeout(() => {
      this._ctoProviderHintOverride = null;
      hintEl.style.color = '';
      if (this._lastCtoProviderData) {
        const d = this._lastCtoProviderData;
        hintEl.textContent = `目前：${d.planner_provider_label || d.planner_provider || '—'}${d.planner_model ? ' / ' + d.planner_model : ''}`;
      }
    }, ttlMs);
  }

  // ─── CTO Run-Now / Trace ──────────────────────────────────────────────────

  async _triggerCtoRunNow() {
    const btn = document.getElementById('orc-cto-run-now-btn');
    if (btn) { btn.disabled = true; btn.textContent = '觸發中…'; }
    try {
      const data = await this._post('/api/orchestrator/cto/run-now', {});
      const requestId = data.request_id;
      const triggeredAt = data.triggered_at;
      this._renderCtoRunnerTrace({ requestId, outcome: '等待中…', note: '已觸發 CTO Planner，等待結果…' });
      await this._waitForCtoRunOutcome(requestId, triggeredAt);
    } catch (e) {
      this._renderCtoRunnerTrace({ requestId: '—', outcome: 'ERROR', note: `觸發失敗：${e.message}` });
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Planner 立即執行'; }
    }
  }

  async _waitForCtoRunOutcome(requestId, triggeredAt, timeoutMs = 70000) {
    const terminal = new Set([
      'CTO_REVIEW_COMPLETED',
      'CTO_REVIEW_SKIP_DISABLED',
      'CTO_REVIEW_SKIP_FREQUENCY',
      'CTO_REVIEW_NO_CANDIDATES',
      'CTO_REVIEW_ERROR',
    ]);
    const triggerMs = _parse_utc_timestamp(triggeredAt)?.getTime() ?? Date.now();
    const deadline = triggerMs + timeoutMs;
    const poll = async () => {
      const data = await this._get(`/api/orchestrator/cto/run-status?request_id=${encodeURIComponent(requestId)}`);
      const run = data.run || {};
      const outcome = run.outcome || data.status || '…';
      const note = run.message || '等待中…';
      this._renderCtoRunnerTrace({ requestId, outcome, note });
      if (data.final) {
        const level = outcome === 'CTO_REVIEW_COMPLETED' || outcome === 'CTO_REVIEW_NO_CANDIDATES' ? 'ok'
          : outcome.includes('ERROR') ? 'error' : 'warn';
        const label = {
          CTO_REVIEW_COMPLETED: 'CTO 審核完成',
          CTO_REVIEW_NO_CANDIDATES: '無候選，略過',
          CTO_REVIEW_SKIP_DISABLED: 'CTO 排程已暫停',
          CTO_REVIEW_SKIP_FREQUENCY: '頻率限制，略過本次',
          CTO_REVIEW_ERROR: 'CTO 執行錯誤',
        }[outcome] || outcome;
        this._showCtoPlannerInlineFeedback(level, label);
        await this._loadCtoAll();
        return;
      }
      if (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 3000));
        await poll();
      } else {
        this._renderCtoRunnerTrace({ requestId, outcome: 'TIMEOUT', note: '超時未收到結果，請稍後手動刷新' });
      }
    };
    await poll();
  }

  _renderCtoRunnerTrace({ requestId, outcome, note }) {
    const ridEl = document.getElementById('orc-cto-planner-last-request-id');
    const outEl = document.getElementById('orc-cto-planner-last-outcome');
    const noteEl = document.getElementById('orc-cto-planner-last-note');
    if (ridEl) ridEl.textContent = requestId || '—';
    if (outEl) outEl.textContent = outcome || '—';
    if (noteEl) noteEl.textContent = note || '—';
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

  _renderNextTickEstimate(runs, plannerTickEstimate = null, workerTickEstimate = null) {
    const plannerEl = document.getElementById('orc-next-planner-at');
    const workerEl = document.getElementById('orc-next-worker-at');
    const noteEl = document.getElementById('orc-next-tick-note');
    if (!plannerEl || !workerEl || !noteEl) return;

    if (!this._schedulerEnabled) {
      this._plannerNextAt = null;
      this._workerNextAt = null;
      this._stopCountdownTimer();
      plannerEl.textContent = '已暫停';
      workerEl.textContent = '已暫停';
      noteEl.textContent = '排程目前為暫停狀態';
      return;
    }

    this._plannerNextAt = _parse_utc_timestamp(plannerTickEstimate) || _next_tick_by_runner(runs, 'planner');
    this._workerNextAt = _parse_utc_timestamp(workerTickEstimate) || _next_tick_by_runner(runs, 'worker');
    this._renderCountdownValues();

    if (this._plannerNextAt || this._workerNextAt) {
      this._startCountdownTimer();
    } else {
      this._stopCountdownTimer();
      noteEl.textContent = '尚無可用的下一次排程時間';
    }
  }

  async _loadDetail(taskId) {
    const container = document.getElementById('orc-detail-content');
    if (!container) return;
    container.innerHTML = '<p>載入中…</p>';
    this._showDetail();
    try {
      const t = await this._get(`/api/orchestrator/tasks/${taskId}`);
      const files = _parse_files(t.changed_files_json);
      const plannerSource = t.planner_source || '—';
      const plannerProvider = t.planner_provider ? ` (${_esc(t.planner_provider)})` : '';
      const workerRequested = t.worker_requested_provider || t.worker_provider || '—';
      const workerRuntime = t.worker_runtime || '—';
      const workerModel = t.worker_model ? ` / ${_esc(t.worker_model)}` : '';
      const workerMode = t.worker_execution_mode || '—';
      const gateVerdict = t.gate_verdict || '—';
      const gateReason = t.gate_reason || '—';
      const commitSha = t.commit_sha || '—';
      const sourceBranch = t.source_branch || '—';
      const reviewStatus = t.review_status || '—';
      const reviewedAt = t.reviewed_at || '—';
      const mergeBranch = t.merge_branch || '—';
      const mergeCommitSha = t.merge_commit_sha || '—';
      const rejectReason = t.reject_reason || '—';
      const integrationGroup = t.integration_group || '—';
      const reviewPriority = t.review_priority || '—';
      const workerTail = t.worker_stdout_tail || t.codex_stdout_tail || '';
      const progressSummary = t.last_progress_summary || '—';
      const progressLabel = _progress_state_label(t.progress_state, t.progress_note, t.last_output_age_seconds);
      container.innerHTML = `
        <div style="margin-bottom:16px">
          <h3>${_esc(t.title || '—')}</h3>
          <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:0.85rem;color:var(--text-muted)">
            <span>ID: ${t.id}</span>
            <span>Slot: ${_fmt_slot(t.slot_key)}</span>
            <span>狀態: <b>${t.status}</b></span>
            <span>Planner 來源: <b>${_esc(plannerSource)}</b>${plannerProvider}</span>
            <span>Worker: <b>${_esc(workerRequested)}</b> → ${_esc(workerRuntime)}${workerModel} (${_esc(workerMode)})</span>
            <span>Gate: <b>${_esc(gateVerdict)}</b> (${_esc(gateReason)})</span>
            <span>Commit SHA: <b>${_esc(commitSha)}</b></span>
            <span>Source Branch: <b>${_esc(sourceBranch)}</b></span>
            <span>Review Status: <b>${_esc(reviewStatus)}</b></span>
            <span>Reviewed At: <b>${_esc(reviewedAt)}</b></span>
            <span>Merge Branch: <b>${_esc(mergeBranch)}</b></span>
            <span>Merge SHA: <b>${_esc(mergeCommitSha)}</b></span>
            <span>Integration Group: <b>${_esc(integrationGroup)}</b></span>
            <span>Review Priority: <b>${_esc(reviewPriority)}</b></span>
            <span>Reject Reason: <b>${_esc(rejectReason)}</b></span>
            ${t.duration_seconds != null ? `<span>耗時: ${_fmt_dur(t.duration_seconds)}</span>` : ''}
            <span title="${_esc(t.started_at || '')}">開始: ${t.started_at ? _fmt_utc_ts(t.started_at) : '—'}</span>
            <span title="${_esc(t.worker_completed_at || t.completed_at || '')}">結束: ${(t.worker_completed_at || t.completed_at) ? _fmt_utc_ts(t.worker_completed_at || t.completed_at) : '—'}</span>
            <span title="${_esc(t.last_output_at || '')}">最後輸出: ${t.last_output_at ? _fmt_utc_ts(t.last_output_at) : '—'}</span>
            <span>執行判讀: ${_esc(progressLabel)}</span>
          </div>
        </div>

        <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.22);border-radius:6px;padding:10px;margin-bottom:16px">
          <b>最新進度：</b> ${_esc(progressSummary)}
        </div>

        <details open style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📋 Prompt（任務指令）</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:400px;font-size:0.82rem;white-space:pre-wrap">${_esc(t.prompt_text || '（無）')}</pre>
        </details>

        <details ${t.completed_text ? 'open' : ''} style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">✅ Completed（執行結果）</summary>
          <pre style="background:var(--card-bg,#1a1a2e);padding:12px;border-radius:6px;overflow:auto;max-height:400px;font-size:0.82rem;white-space:pre-wrap">${_esc(t.completed_text || '（尚未完成）')}</pre>
        </details>

        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📐 Task Contract（規範）</summary>
          <pre style="background:#0f172a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(t.task_contract || '（無）')}</pre>
        </details>

        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🧪 Task Result（Gate 驗收）</summary>
          <pre style="background:#0f172a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(t.task_result || '（無）')}</pre>
        </details>

        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">📂 異動檔案（${files.length} 個）</summary>
          ${files.length ? `
          <ul style="margin:0;padding-left:20px;font-size:0.85rem">
            ${files.map(f => `<li><code>${_esc(f)}</code></li>`).join('')}
          </ul>` : '<div style="font-size:0.85rem;color:var(--text-muted,#8b949e)">（無）</div>'}
        </details>

        <details style="margin-bottom:16px">
          <summary style="cursor:pointer;font-weight:600;margin-bottom:8px">🖥 Worker 輸出（後 200 行）</summary>
          <pre style="background:#0d0d1a;padding:12px;border-radius:6px;overflow:auto;max-height:300px;font-size:0.78rem;white-space:pre-wrap">${_esc(workerTail || '（無）')}</pre>
        </details>

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

export function _parse_utc_timestamp(raw) {
  const s = String(raw || '').trim();
  if (!s) return null;

  const parts = s.match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?([zZ]|[+\-]\d{2}:\d{2})?$/
  );
  if (parts) {
    const [, year, month, day, hour, minute, second, fraction = '', tz = 'Z'] = parts;
    const millis = Number((fraction + '000').slice(0, 3));
    const utcMs = Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second),
      millis
    );

    if (tz === 'Z' || tz === 'z') {
      return new Date(utcMs);
    }

    const sign = tz[0] === '-' ? -1 : 1;
    const [offsetHour, offsetMinute] = tz.slice(1).split(':').map(Number);
    const offsetMs = sign * ((offsetHour * 60) + offsetMinute) * 60 * 1000;
    return new Date(utcMs - offsetMs);
  }

  const date = new Date(s);
  return Number.isNaN(date.getTime()) ? null : date;
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

export function _next_tick_by_runner(runs, runner) {
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

export function _find_recent_runner_outcome(runs, runner, sinceMs = 0) {
  const relevant = (runs || []).filter((item) => {
    if ((item?.runner || '').toLowerCase() !== runner) return false;
    const tickAt = _parse_utc_timestamp(item?.tick_at);
    return tickAt && !Number.isNaN(tickAt.getTime()) && tickAt.getTime() >= sinceMs;
  });

  for (const outcome of ['PLANNER_PRODUCED', 'PLANNER_SKIP_PROVIDER_FAILURE', 'PLANNER_SKIP_PREV_RUNNING', 'PLANNER_SKIP_DISABLED', 'PLANNER_SKIP_NO_BACKLOG', 'PLANNER_INVALID_CONTRACT']) {
    const match = relevant.find((item) => item?.outcome === outcome);
    if (match) return match;
  }
  return null;
}

export function _runner_outcome_feedback(run) {
  const outcome = String(run?.outcome || '');
  const message = String(run?.message || '');
  const lowered = message.toLowerCase();

  if (outcome === 'PLANNER_PRODUCED') {
    return { level: 'success', message: 'Planner 已建立新任務。' };
  }
  if (outcome === 'PLANNER_SKIP_PROVIDER_FAILURE') {
    if (lowered.includes('usage limit') || lowered.includes('hit your limit') || lowered.includes('quota')) {
      return { level: 'warning', message: 'Planner 未建立任務：Codex / Claude 額度已用完。' };
    }
    if (lowered.includes('not logged in') || lowered.includes('auth failed')) {
      return { level: 'warning', message: 'Planner 未建立任務：Planner provider 尚未登入。' };
    }
    return { level: 'warning', message: 'Planner 未建立任務：Planner provider 目前不可用。' };
  }
  if (outcome === 'PLANNER_SKIP_PREV_RUNNING') {
    return { level: 'warning', message: 'Planner 已略過：上一筆任務仍在執行中。' };
  }
  if (outcome === 'PLANNER_SKIP_DISABLED') {
    return { level: 'warning', message: 'Planner 已略過：排程目前是暫停狀態。' };
  }
  if (outcome === 'PLANNER_SKIP_NO_BACKLOG') {
    return { level: 'warning', message: 'Planner 已略過：目前沒有可用 backlog。' };
  }
  if (outcome === 'PLANNER_INVALID_CONTRACT') {
    return { level: 'error', message: 'Planner 產出任務契約無效，未建立新任務。' };
  }
  if (outcome === 'PLANNER_FALLBACK_LOCAL') {
    return { level: 'warning', message: 'Planner 輸出格式無效，已退回 fallback。' };
  }
  return { level: 'info', message: message || 'Planner 已執行完成。' };
}

export function _countdown_state(targetDate, nowMs = Date.now()) {
  if (!targetDate || Number.isNaN(targetDate.getTime())) {
    return { label: '—', due: false };
  }

  const diffMs = targetDate.getTime() - nowMs;
  if (diffMs <= 0) {
    return { label: '0m 0s 後', due: true };
  }

  const totalSec = Math.floor(diffMs / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return { label: `${m}m ${s}s 後`, due: false };
}

function _sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function _fmt_dur(s) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s/60)}m${s%60}s`;
  return `${Math.floor(s/3600)}h${Math.floor((s%3600)/60)}m`;
}

function _changed_count(json) {
  try {
    if (Array.isArray(json)) return `${json.length} 個`;
    return `${JSON.parse(json || '[]').length} 個`;
  } catch {
    return '—';
  }
}

function _parse_files(json) {
  try {
    if (Array.isArray(json)) return json;
    return JSON.parse(json || '[]');
  } catch {
    return [];
  }
}

function _parseGitDecisionSteps(raw) {
  try {
    if (Array.isArray(raw)) return raw;
    return JSON.parse(raw || '[]');
  } catch {
    return [];
  }
}

function _progress_state_label(state, note, ageSeconds) {
  if (note) return note;
  if (state === 'stale' || state === 'STUCK_SUSPECTED') {
    return ageSeconds != null ? `已 ${ageSeconds}s 無新輸出，疑似卡住` : '疑似卡住';
  }
  if (state === 'active' || state === 'RUNNING_ACTIVE') {
    return ageSeconds != null ? `${ageSeconds}s 前有輸出，持續執行中` : '持續執行中';
  }
  if (state === 'no_output' || state === 'RUNNING_NO_OUTPUT') return '執行中但尚無輸出';
  return '—';
}

function _normalizeCopilotModel(raw) {
  const value = String(raw || '').trim();
  if (!value) return '';
  const lowered = value.toLowerCase().trim();
  if (['default', '預設', 'system', 'builtin'].includes(lowered)) return '';
  if (lowered === 'auto') return 'auto';
  const aliases = {
    'gpt-5 mini': 'gpt-5-mini',
    'gpt5 mini': 'gpt-5-mini',
    'gpt 5 mini': 'gpt-5-mini',
    'gpt_5_mini': 'gpt-5-mini',
    'gpt5-mini': 'gpt-5-mini',
  };
  if (aliases[lowered]) return aliases[lowered];
  return lowered
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9._-]/g, '')
    .replace(/-{2,}/g, '-')
    .replace(/^-+|-+$/g, '');
}

function _isValidCopilotModel(model) {
  if (!model) return true;
  if (model === 'auto' || model === 'gpt-5-mini') return true;
  return /^[a-z0-9][a-z0-9._-]{1,63}$/.test(model);
}

function _outcome_class(outcome) {
  if (!outcome) return 'neutral';
  if (outcome.includes('PRODUCED') || outcome.includes('CLAIMED') || outcome.includes('FINALIZED')) return 'success';
  if (outcome.includes('FAILED')) return 'error';
  if (outcome.includes('SKIP') || outcome.includes('HEARTBEAT')) return 'muted';
  return 'neutral';
}
