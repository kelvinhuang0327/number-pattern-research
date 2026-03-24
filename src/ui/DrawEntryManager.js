/**
 * DrawEntryManager — 快速開獎入庫 UI
 * 讓使用者在前端直接輸入單期開獎結果並寫入後端資料庫，
 * 支援今彩539 / 大樂透 / 威力彩。
 */
import { getApiUrl } from '../config/apiConfig.js';

const LOTTERY_CONFIG = {
    DAILY_539:   { label: '今彩539',  count: 5, min: 1, max: 39, hasSpecial: false },
    BIG_LOTTO:   { label: '大樂透',  count: 6, min: 1, max: 49, hasSpecial: true  },
    POWER_LOTTO: { label: '威力彩',  count: 6, min: 1, max: 38, hasSpecial: true  },
};

export class DrawEntryManager {
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
        this.submitBtn   = document.getElementById('draw-entry-submit');
        this.statusEl    = document.getElementById('draw-entry-status');
    }

    _bindEvents() {
        if (!this.form) return;
        this.typeSelect.addEventListener('change', () => this._onTypeChange());
        this.submitBtn.addEventListener('click', () => this._onSubmit());
        // 今天日期作為預設
        const today = new Date();
        const roc = today.getFullYear() - 1911;
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
                this.specialInput.max = cfg.max;
                this.specialInput.value = '';
            }
        }

        this._clearStatus();
    }

    async _onSubmit() {
        const type = this.typeSelect.value;
        const cfg  = LOTTERY_CONFIG[type];
        if (!cfg) return;

        // --- 收集號碼 ---
        const numbers = [];
        for (let i = 0; i < cfg.count; i++) {
            const val = parseInt(document.getElementById(`draw-num-${i}`)?.value);
            if (isNaN(val) || val < cfg.min || val > cfg.max) {
                this._setStatus('error', `號碼 ${i + 1} 無效（範圍 ${cfg.min}–${cfg.max}）`);
                return;
            }
            numbers.push(val);
        }

        // 重複號碼檢查
        if (new Set(numbers).size !== numbers.length) {
            this._setStatus('error', '號碼不可重複');
            return;
        }

        // --- 特別號 ---
        let special = 0;
        if (cfg.hasSpecial) {
            special = parseInt(this.specialInput?.value);
            if (isNaN(special) || special < cfg.min || special > cfg.max) {
                this._setStatus('error', `特別號無效（範圍 ${cfg.min}–${cfg.max}）`);
                return;
            }
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
                body: JSON.stringify({ draw, date, lotteryType: type, numbers, special }),
            });
            const json = await res.json();

            if (res.ok && json.success) {
                this._setStatus('success',
                    `✅ ${cfg.label} ${draw} 已入庫　號碼：[${numbers.sort((a,b)=>a-b).join(', ')}]` +
                    (cfg.hasSpecial ? `　特別號：${special}` : '')
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
