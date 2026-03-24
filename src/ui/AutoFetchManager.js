/**
 * AutoFetchManager — 自動抓取 / 掃描缺漏 / 補入回填 UI 控制器
 *
 * 管理三個面板：
 *   1. 自動抓取最新開獎 (fetch-latest)
 *   2. 掃描缺漏期數   (scan-missing)
 *   3. 自動補入缺漏   (backfill)
 *
 * 不破壞現有 DrawEntryManager（手動快速入庫）。
 */
import { getApiUrl } from '../config/apiConfig.js';

const LOTTERY_LABELS = {
    BIG_LOTTO:   '大樂透',
    POWER_LOTTO: '威力彩',
    DAILY_539:   '今彩539',
};

/** Escape a string for safe HTML interpolation. */
function _esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                          .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export class AutoFetchManager {
    constructor() {
        this._bindElements();
        this._bindEvents();
    }

    // ─── Element binding ────────────────────────────────────────────────

    _bindElements() {
        // Fetch Latest
        this.fetchTypeSelect   = document.getElementById('af-fetch-type');
        this.fetchInsertCheck  = document.getElementById('af-fetch-insert');
        this.fetchDryRunCheck  = document.getElementById('af-fetch-dryrun');
        this.fetchBtn          = document.getElementById('af-fetch-btn');
        this.fetchStatus       = document.getElementById('af-fetch-status');

        // Scan Missing
        this.scanTypeSelect    = document.getElementById('af-scan-type');
        this.scanBtn           = document.getElementById('af-scan-btn');
        this.scanStatus        = document.getElementById('af-scan-status');
        this.scanResults       = document.getElementById('af-scan-results');

        // Backfill
        this.bfTypeSelect      = document.getElementById('af-bf-type');
        this.bfDryRunCheck     = document.getElementById('af-bf-dryrun');
        this.bfConfirmCheck    = document.getElementById('af-bf-confirm');
        this.bfBtn             = document.getElementById('af-bf-btn');
        this.bfStatus          = document.getElementById('af-bf-status');
        this.bfResults         = document.getElementById('af-bf-results');

        // Log panel
        this.logRefreshBtn     = document.getElementById('af-log-refresh');
        this.logTable          = document.getElementById('af-log-table');
        this.logBody           = document.getElementById('af-log-body');
        this.logStats          = document.getElementById('af-log-stats');
        this.logPrevBtn        = document.getElementById('af-log-prev');
        this.logNextBtn        = document.getElementById('af-log-next');
        this.logPageInfo       = document.getElementById('af-log-page-info');
    }

    _bindEvents() {
        this.fetchBtn?.addEventListener('click',      () => this._onFetchLatest());
        this.scanBtn?.addEventListener('click',       () => this._onScanMissing());
        this.bfBtn?.addEventListener('click',         () => this._onBackfill());
        this.logRefreshBtn?.addEventListener('click', () => { this._logOffset = 0; this._loadLog(); });
        this.logPrevBtn?.addEventListener('click',    () => this._logPagePrev());
        this.logNextBtn?.addEventListener('click',    () => this._logPageNext());

        // Pagination state
        this._logOffset   = 0;
        this._logPageSize = 20;
        this._logTotal    = 0;

        // Auto-load log on init
        this._loadLog();
    }

    // ─── Fetch Latest ───────────────────────────────────────────────────

    async _onFetchLatest() {
        const lt        = this.fetchTypeSelect?.value || 'BIG_LOTTO';
        const insertNew = this.fetchInsertCheck?.checked || false;
        const dryRun    = this.fetchDryRunCheck?.checked || false;

        this._setBtnLoading(this.fetchBtn, true);
        this._setStatus(this.fetchStatus, 'loading', '⏳ 正在從台灣彩券官網抓取最新開獎...');

        try {
            const res = await fetch(getApiUrl('/api/ingest/fetch-latest'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lottery_type:  lt,
                    insert_if_new: insertNew,
                    dry_run:       dryRun,
                }),
            });
            const json = await res.json();

            if (!res.ok) {
                this._setStatus(this.fetchStatus, 'error',
                    `❌ 抓取失敗：${json.detail || res.statusText}`);
                return;
            }

            const d = json.draw_data || {};
            const statusMap = {
                inserted:     '✅',
                already_exists: '⏩',
                fetched_only: '🔎',
                dry_run:      '🔎 DRY-RUN',
                conflict:     '⚡',
            };
            const icon   = statusMap[json.status] || '✅';
            const numStr = d.numbers ? `[${d.numbers.join(', ')}]` : '';
            const spStr  = d.special ? `　特別號：${d.special}` : '';
            const dateStr = d.date   ? `　日期：${d.date}` : '';

            this._setStatus(this.fetchStatus, json.status === 'conflict' ? 'warn' : 'success',
                `${icon} ${json.message}` +
                (numStr ? `\n期號：${d.draw}${dateStr}　號碼：${numStr}${spStr}` : '')
            );
            this._loadLog();
        } catch (err) {
            this._setStatus(this.fetchStatus, 'error', `❌ 網路錯誤：${err.message}`);
        } finally {
            this._setBtnLoading(this.fetchBtn, false);
        }
    }

    // ─── Scan Missing ───────────────────────────────────────────────────

    async _onScanMissing() {
        const lt = this.scanTypeSelect?.value || '';   // '' = all games

        this._setBtnLoading(this.scanBtn, true);
        this._setStatus(this.scanStatus, 'loading', '⏳ 正在比對資料庫與官網期數...');
        if (this.scanResults) this.scanResults.innerHTML = '';

        try {
            const url = getApiUrl('/api/ingest/scan-missing') +
                (lt ? `?lottery_type=${encodeURIComponent(lt)}` : '');
            const res  = await fetch(url);
            const json = await res.json();

            if (!res.ok) {
                this._setStatus(this.scanStatus, 'error',
                    `❌ 掃描失敗：${json.detail || res.statusText}`);
                return;
            }

            const results       = json.results || {};
            const totalMissing  = json.total_missing ?? 0;
            const totalErrors   = Object.values(results).filter(r => r.scan_error).length;

            let overallType, overallMsg;
            if (totalErrors > 0 && totalMissing > 0) {
                overallType = 'warn';
                overallMsg  = `⚠️ 共找到 ${totalMissing} 期缺漏，且 ${totalErrors} 個彩種抓取失敗（請查看下方錯誤欄）`;
            } else if (totalErrors > 0) {
                overallType = 'warn';
                overallMsg  = `⚠️ ${totalErrors} 個彩種無法從官網抓取資料，無法確認是否有缺漏（請查看下方錯誤欄）`;
            } else if (totalMissing > 0) {
                overallType = 'warn';
                overallMsg  = `⚠️ 共找到 ${totalMissing} 期缺漏，請確認後執行補入`;
            } else {
                overallType = 'success';
                overallMsg  = '✅ 資料庫與官網資料一致，無缺漏期數';
            }
            this._setStatus(this.scanStatus, overallType, overallMsg);

            if (this.scanResults) {
                this.scanResults.innerHTML = this._buildScanResultsHtml(results);
            }
            this._loadLog();
        } catch (err) {
            this._setStatus(this.scanStatus, 'error', `❌ 網路錯誤：${err.message}`);
        } finally {
            this._setBtnLoading(this.scanBtn, false);
        }
    }

    _buildScanResultsHtml(results) {
        const rows = Object.entries(results).map(([lt, r]) => {
            const label    = LOTTERY_LABELS[lt] || lt;
            const gapCount = (r.internal_gaps || []).length;
            const errStr   = r.scan_error ? `<span class="af-err">${_esc(r.scan_error)}</span>` : '';
            const officialLatestStr = r.official_latest
                ? _esc(r.official_latest) + (r.official_latest_date ? `<br><span class="af-muted">${_esc(r.official_latest_date)}</span>` : '')
                : '—';

            let missingStr = '—';
            if (r.missing_count > 0) {
                const detail = r.missing_draws_detail || [];
                if (detail.length > 0) {
                    missingStr = detail.map(m =>
                        `${_esc(m.draw)}${m.date ? `<span class="af-muted"> (${_esc(m.date)})</span>` : ''}`
                    ).join('<br>');
                } else {
                    missingStr = (r.missing_draws || []).join(', ');
                }
            }

            return `
            <tr>
              <td><strong>${_esc(label)}</strong></td>
              <td>${r.db_count ?? '—'}</td>
              <td>${_esc(r.db_latest_draw || '—')}</td>
              <td>${officialLatestStr}</td>
              <td class="${r.missing_count > 0 ? 'af-warn' : ''}">${r.missing_count ?? 0}</td>
              <td class="af-missing-list">${r.missing_count > 0 ? missingStr : '—'}</td>
              <td>${gapCount > 0 ? `⚠️ ${gapCount} 個內部缺口` : '✅'}</td>
              <td>${errStr}</td>
            </tr>`;
        }).join('');

        return `
        <table class="af-scan-table">
          <thead>
            <tr>
              <th>彩種</th><th>DB 期數</th><th>DB 最新期</th>
              <th>官網最新期</th><th>缺漏數</th><th>缺漏開獎日期</th>
              <th>內部缺口</th><th>錯誤</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>`;
    }

    // ─── Backfill ────────────────────────────────────────────────────────

    async _onBackfill() {
        const lt     = this.bfTypeSelect?.value || 'BIG_LOTTO';
        const dryRun = this.bfDryRunCheck?.checked || false;
        const confirmed = this.bfConfirmCheck?.checked || false;

        if (!dryRun && !confirmed) {
            this._setStatus(this.bfStatus, 'warn',
                '⚠️ 請先勾選「確認執行補入」，或啟用 Dry-Run 模式預覽');
            return;
        }

        this._setBtnLoading(this.bfBtn, true);
        this._setStatus(this.bfStatus, 'loading',
            dryRun ? '⏳ DRY-RUN 模式：預覽缺漏期數（不寫入）...'
                   : '⏳ 正在自動補入缺漏期數...');
        if (this.bfResults) this.bfResults.innerHTML = '';

        try {
            const res = await fetch(getApiUrl('/api/ingest/backfill'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lottery_type: lt,
                    dry_run:      dryRun,
                    max_draws:    30,
                }),
            });
            const json = await res.json();

            if (!res.ok) {
                this._setStatus(this.bfStatus, 'error',
                    `❌ 補入失敗：${json.detail || res.statusText}`);
                return;
            }

            const s = json.summary || {};
            if (s.error) {
                this._setStatus(this.bfStatus, 'error',
                    `❌ 補入失敗：${s.error}`);
                return;
            }
            const icon = s.failed > 0 ? '⚠️' : '✅';
            this._setStatus(this.bfStatus,
                s.failed > 0 ? 'warn' : 'success',
                `${icon} 完成${dryRun ? '（DRY-RUN）' : ''}：` +
                `寫入 ${s.inserted}　跳過 ${s.skipped}　` +
                `衝突 ${s.conflict}　失敗 ${s.failed}　/ 共 ${s.total} 期`
            );

            if (this.bfResults && s.details?.length) {
                this.bfResults.innerHTML = this._buildBackfillResultsHtml(s.details);
            }
            this._loadLog();
        } catch (err) {
            this._setStatus(this.bfStatus, 'error', `❌ 網路錯誤：${err.message}`);
        } finally {
            this._setBtnLoading(this.bfBtn, false);
        }
    }

    _buildBackfillResultsHtml(details) {
        const statusIcon = { inserted:'✅', skipped:'⏩', conflict:'⚡', failed:'❌', dry_run:'🔎' };
        const rows = details.map(d => {
            const icon    = statusIcon[d.status] || '?';
            const date    = d.data?.date || '';
            const nums    = d.data?.numbers ? `[${d.data.numbers.join(',')}]` : '';
            const special = d.data?.special  ? ` SP:${d.data.special}`        : '';
            return `
            <tr class="af-bf-row af-bf-${d.status}">
              <td>${d.draw}</td>
              <td class="af-muted">${date}</td>
              <td>${icon} ${d.status}</td>
              <td>${nums}${special}</td>
              <td class="af-muted">${d.message || ''}</td>
            </tr>`;
        }).join('');

        return `
        <table class="af-bf-table">
          <thead><tr><th>期號</th><th>開獎日期</th><th>結果</th><th>號碼</th><th>備註</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
    }

    // ─── Ingest Log ──────────────────────────────────────────────────────

    _logPagePrev() {
        if (this._logOffset <= 0) return;
        this._logOffset = Math.max(0, this._logOffset - this._logPageSize);
        this._loadLog();
    }

    _logPageNext() {
        if (this._logOffset + this._logPageSize >= this._logTotal) return;
        this._logOffset += this._logPageSize;
        this._loadLog();
    }

    async _loadLog() {
        if (!this.logBody) return;
        try {
            const url = getApiUrl(
                `/api/ingest/log?limit=${this._logPageSize}&offset=${this._logOffset}`
            );
            const res  = await fetch(url);
            const json = await res.json();
            if (!res.ok) return;

            const entries = json.entries || [];
            const stats   = json.stats   || {};
            this._logTotal = stats.total || 0;

            if (this.logStats) {
                const ok  = stats.by_status?.ok  || 0;
                const err = (stats.by_status?.error || 0) + (stats.by_status?.conflict || 0);
                this.logStats.textContent =
                    `共 ${this._logTotal} 筆　✅ ${ok}　⚡ ${err}`;
            }

            // Pagination info
            const page    = Math.floor(this._logOffset / this._logPageSize) + 1;
            const total   = Math.ceil(this._logTotal / this._logPageSize) || 1;
            if (this.logPageInfo) {
                this.logPageInfo.textContent = `第 ${page} / ${total} 頁`;
            }
            if (this.logPrevBtn) this.logPrevBtn.disabled = this._logOffset <= 0;
            if (this.logNextBtn) this.logNextBtn.disabled =
                this._logOffset + this._logPageSize >= this._logTotal;

            if (!entries.length) {
                this.logBody.innerHTML =
                    '<tr><td colspan="6" class="af-muted" style="text-align:center">尚無記錄</td></tr>';
                return;
            }

            const statusIcon = {
                ok:'✅', skip:'⏩', error:'❌', conflict:'⚡', dry_run:'🔎', partial:'⚠️'
            };
            const actionLabel = {
                fetch_latest: '抓取最新',
                scan_missing: '掃描缺漏',
                backfill:     '補入缺漏',
                conflict:     '資料衝突',
            };

            this.logBody.innerHTML = entries.map(e => {
                // Convert UTC timestamp to local time
                const localTs = e.timestamp
                    ? new Date(e.timestamp).toLocaleString('zh-TW', {
                        year: 'numeric', month: '2-digit', day: '2-digit',
                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                        hour12: false,
                      }).replace(/\//g, '-')
                    : '—';
                const icon     = statusIcon[e.status] || '•';
                const lt       = _esc(LOTTERY_LABELS[e.lottery_type] || e.lottery_type || '—');
                const action   = _esc(actionLabel[e.action] || e.action || '—');
                const drawDate = _esc(e.data?.date || '—');
                return `
                <tr>
                  <td class="af-muted">${_esc(localTs)}</td>
                  <td>${action}</td>
                  <td>${lt}</td>
                  <td>${_esc(e.draw || '—')}</td>
                  <td class="af-muted">${drawDate}</td>
                  <td>${icon} ${_esc(e.message || '')}</td>
                </tr>`;
            }).join('');
        } catch (_) {
            // silently fail log refresh
        }
    }

    // ─── Utilities ───────────────────────────────────────────────────────

    _setStatus(el, type, msg) {
        if (!el) return;
        el.className = `af-status af-status--${type}`;
        el.style.display  = 'block';
        el.style.whiteSpace = 'pre-wrap';
        el.textContent = msg;
    }

    _setBtnLoading(btn, loading) {
        if (!btn) return;
        btn.disabled = loading;
        if (loading) btn.dataset._origText = btn.textContent;
        btn.textContent = loading ? '處理中...' : (btn.dataset._origText || btn.textContent);
    }
}
