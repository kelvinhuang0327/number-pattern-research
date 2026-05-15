/**
 * DrawEntryManager — 快速開獎入庫 UI
 * 讓使用者在前端直接輸入單期開獎結果並寫入後端資料庫，
 * 支援今彩539 / 大樂透 / 威力彩。
 */
import { getApiUrl } from '../config/apiConfig.js';

const LOTTERY_CONFIG = {
    DAILY_539:   { label: '今彩539',  count: 5, min: 1, max: 39, hasSpecial: false, specialMax: null },
    BIG_LOTTO:   { label: '大樂透',  count: 6, min: 1, max: 49, hasSpecial: true,  specialMax: 49   },
    POWER_LOTTO: { label: '威力彩',  count: 6, min: 1, max: 38, hasSpecial: true,  specialMax: 8    },
};

export class DrawEntryManager {
    _previewRequestId = 0;

    constructor() {
        this._bindElements();
        this._bindEvents();
        this._onTypeChange();   // 初始化一次
    }

    _bindElements() {
        this.form        = document.getElementById('draw-entry-form');
        this.typeSelect  = document.getElementById('draw-entry-type');
        this.drawInput   = document.getElementById('draw-entry-draw');
        this.dateInput   = document.getElementById('draw-entry-date');
        this.numbersWrap = document.getElementById('draw-entry-numbers-wrap');
        this.specialRow  = document.getElementById('draw-entry-special-row');
        this.specialInput= document.getElementById('draw-entry-special');
        this.jackpotInput = document.getElementById('draw-entry-jackpot');
        this.previewEl    = document.getElementById('draw-entry-decision-preview');
        this.submitBtn   = document.getElementById('draw-entry-submit');
        this.statusEl    = document.getElementById('draw-entry-status');
    }

    _bindEvents() {
        if (!this.form) return;
        this.typeSelect.addEventListener('change', () => this._onTypeChange());
        this.submitBtn.addEventListener('click', () => this._onSubmit());
        this._ensureDecisionPreview();
        this._bindDecisionPreviewListeners();
        // 今天日期作為預設
        const today = new Date();
        const mm  = String(today.getMonth() + 1).padStart(2, '0');
        const dd  = String(today.getDate()).padStart(2, '0');
        this.dateInput.value = `${today.getFullYear()}/${mm}/${dd}`;
    }

    _onTypeChange() {
        const type = this.typeSelect?.value;
        const cfg  = LOTTERY_CONFIG[type];
        if (!cfg || !this.numbersWrap) return;

        // 重新渲染號碼輸入欄
        this.numbersWrap.innerHTML = '';
        for (let i = 0; i < cfg.count; i++) {
            const inp = document.createElement('input');
            inp.type        = 'number';
            inp.min         = cfg.min;
            inp.max         = cfg.max;
            inp.placeholder = `號碼 ${i + 1}`;
            inp.className   = 'draw-entry-num-input';
            inp.id          = `draw-num-${i}`;
            this.numbersWrap.appendChild(inp);
        }

        // 特別號列
        if (this.specialRow) {
            this.specialRow.style.display = cfg.hasSpecial ? '' : 'none';
            if (this.specialInput) {
                this.specialInput.min = cfg.min;
                this.specialInput.max = cfg.specialMax ?? cfg.max;
                this.specialInput.value = '';
            }
        }

        this._clearStatus();
        this._refreshDecisionPreview();
    }

    _ensureDecisionPreview() {
        if (!this.form || document.getElementById('draw-entry-decision-row')) return;

        const previewRow = document.createElement('div');
        previewRow.id = 'draw-entry-decision-row';
        previewRow.className = 'draw-entry-row';
        previewRow.innerHTML = `
            <label>頭獎 / EV 預覽</label>
            <div style="display:grid;gap:8px">
                <input type="number" id="draw-entry-jackpot"
                       class="draw-entry-text-input"
                       min="0" step="1000"
                       placeholder="可選：自訂頭獎金額（留空則使用後端最新值）">
                <div id="draw-entry-decision-preview"
                     style="font-size:12px;line-height:1.6;color:#8b949e;padding:10px 12px;border-radius:8px;background:rgba(0,0,0,0.18);border:1px solid rgba(255,255,255,0.08)">
                    載入決策預覽中…
                </div>
            </div>`;

        this.form.insertBefore(previewRow, this.submitBtn);
        this.jackpotInput = document.getElementById('draw-entry-jackpot');
        this.previewEl = document.getElementById('draw-entry-decision-preview');
    }

    _bindDecisionPreviewListeners() {
        if (this.jackpotInput && !this.jackpotInput._bound) {
            this.jackpotInput.addEventListener('input', () => this._refreshDecisionPreview());
            this.jackpotInput._bound = true;
        }
    }

    _formatDecisionPreview(json, manualJackpot) {
        const hasManualJackpot = Number.isFinite(manualJackpot) && manualJackpot > 0;
        const currentJackpot = hasManualJackpot ? manualJackpot : Number(json.current_jackpot ?? json.currentJackpot ?? 0);
        const breakeven = Number(json.breakeven_jackpot ?? json.breakevenJackpot ?? 0);
        const evGap = currentJackpot && breakeven ? currentJackpot - breakeven : Number(json.ev_gap ?? 0);
        const gateOpen = json.jackpot_ev_status
            ? json.jackpot_ev_status === 'ENABLED'
            : Boolean(json.ev_gate_open);
        const gateLabel = json.jackpot_ev_status || (gateOpen ? 'ENABLED' : 'DISABLED');
        const gateColor = gateOpen ? '#3fb950' : '#e5c07b';
        const betCount = json.kelly_optimal_bets ?? json.recommended_bet_count ?? json.n_bets_after_gate ?? json.n_bets ?? 'N/A';
        const kelly = json.kelly_fraction === undefined || json.kelly_fraction === null
            ? 'N/A'
            : `${(Number(json.kelly_fraction) * 100).toFixed(1)}%`;
        const stage2 = json.stage2_gate || {};
        const stage2Sample = stage2.sample_size === undefined || stage2.sample_size === null
            ? ''
            : ` / sample ${stage2.sample_size}`;
        const stage2Text = stage2.status ? `${stage2.status}${stage2Sample}` : 'N/A';
        const evText = Number.isFinite(evGap) ? evGap.toLocaleString('zh-TW', { maximumFractionDigits: 0 }) : 'N/A';

        return `
            <div><strong style="color:${gateColor}">EV gate: ${gateLabel}</strong> · 建議注數: ${betCount} · Kelly: ${kelly}</div>
            <div>頭獎: ${currentJackpot.toLocaleString('zh-TW', { maximumFractionDigits: 0 })} · 損益兩平: ${breakeven ? breakeven.toLocaleString('zh-TW', { maximumFractionDigits: 0 }) : 'N/A'} · EV差距: ${evText}</div>
            <div>Stage2: ${stage2Text} · 月預算: ${Number(json.monthly_budget_after_gate ?? 0).toLocaleString('zh-TW', { maximumFractionDigits: 0 })}</div>
            ${json.notes ? `<div style="opacity:0.85;margin-top:2px">${json.notes}</div>` : ''}
        `;
    }

    async _refreshDecisionPreview() {
        if (!this.previewEl) return;
        const type = this.typeSelect?.value;
        if (!type) return;

        const requestId = ++this._previewRequestId;
        this.previewEl.textContent = '更新決策預覽中…';

        try {
            const res = await fetch(getApiUrl(`/api/decision/${type}`));
            const json = await res.json();
            if (requestId !== this._previewRequestId) return;
            if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`);

            const manualJackpot = Number(this.jackpotInput?.value);
            this.previewEl.innerHTML = this._formatDecisionPreview(json, manualJackpot);
        } catch (error) {
            if (requestId !== this._previewRequestId) return;
            this.previewEl.innerHTML = `<span style="color:#e74c3c">決策預覽載入失敗：${error.message}</span>`;
        }
    }

    _collectDrawNumbers(cfg) {
        const numbers = [];
        for (let i = 0; i < cfg.count; i++) {
            const value = Number.parseInt(document.getElementById(`draw-num-${i}`)?.value, 10);
            if (Number.isNaN(value) || value < cfg.min || value > cfg.max) {
                return { error: `號碼 ${i + 1} 無效（範圍 ${cfg.min}–${cfg.max}）` };
            }
            numbers.push(value);
        }

        if (new Set(numbers).size !== numbers.length) {
            return { error: '號碼不可重複' };
        }

        return { numbers };
    }

    _collectSpecialNumber(cfg) {
        if (!cfg.hasSpecial) return { special: 0 };

        const spMax = cfg.specialMax ?? cfg.max;
        const special = Number.parseInt(this.specialInput?.value, 10);
        if (Number.isNaN(special) || special < cfg.min || special > spMax) {
            return { error: `特別號無效（範圍 ${cfg.min}–${spMax}）` };
        }

        return { special };
    }

    async _onSubmit() {
        const type = this.typeSelect.value;
        const cfg  = LOTTERY_CONFIG[type];
        if (!cfg) return;

        const drawNumbers = this._collectDrawNumbers(cfg);
        if (drawNumbers.error) {
            this._setStatus('error', drawNumbers.error);
            return;
        }

        const specialNumber = this._collectSpecialNumber(cfg);
        if (specialNumber.error) {
            this._setStatus('error', specialNumber.error);
            return;
        }

        // --- 期號 ---
        const draw = this.drawInput.value.trim();
        if (!/^\d{9,10}$/.test(draw)) {
            this._setStatus('error', '期號格式錯誤（例：115000073）');
            return;
        }

        // --- 日期 ---
        const date = this.dateInput.value.trim();
        if (!date) {
            this._setStatus('error', '請輸入開獎日期');
            return;
        }

        // --- 送出 ---
        this.submitBtn.disabled = true;
        this._setStatus('loading', '寫入中...');

        try {
            const res = await fetch(getApiUrl('/api/draws'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ draw, date, lotteryType: type, numbers: drawNumbers.numbers, special: specialNumber.special }),
            });
            const json = await res.json();

            if (res.ok && json.success) {
                const sortedNumbers = [...drawNumbers.numbers].sort((a, b) => a - b);
                this._setStatus('success',
                    `✅ ${cfg.label} ${draw} 已入庫　號碼：[${sortedNumbers.join(', ')}]` +
                    (cfg.hasSpecial ? `　特別號：${specialNumber.special}` : '')
                );
                this._resetForm();
            } else {
                const msg = json.detail || json.message || '未知錯誤';
                this._setStatus('error', `❌ 入庫失敗：${msg}`);
            }
        } catch (err) {
            this._setStatus('error', `❌ 網路錯誤：${err.message}`);
        } finally {
            this.submitBtn.disabled = false;
        }
    }

    _resetForm() {
        this.drawInput.value = '';
        const today = new Date();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        this.dateInput.value = `${today.getFullYear()}/${mm}/${dd}`;
        if (this.jackpotInput) this.jackpotInput.value = '';
        this._onTypeChange();   // 清空號碼
    }

    _setStatus(type, msg) {
        if (!this.statusEl) return;
        this.statusEl.className = `draw-entry-status draw-entry-status--${type}`;
        this.statusEl.textContent = msg;
        this.statusEl.style.display = 'block';
    }

    _clearStatus() {
        if (!this.statusEl) return;
        this.statusEl.style.display = 'none';
        this.statusEl.textContent = '';
    }
}
