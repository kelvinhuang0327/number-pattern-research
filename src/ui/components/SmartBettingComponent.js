/**
 * 聰明包牌組件
 * 負責處理包牌邏輯和UI交互
 */
import { getApiUrl } from '../../config/apiConfig.js';

export class SmartBettingComponent {
    constructor(dataProcessor, predictionEngine, uiManager) {
        this.dataProcessor = dataProcessor;
        this.predictionEngine = predictionEngine;
        this.uiManager = uiManager;
        this.selectedNumbers = new Set();
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.renderNumberSelector();
    }

    setupEventListeners() {
        const generateBtn = document.getElementById('generate-smart-bet-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateCombinations());
        }

        const hedgingBtn = document.getElementById('generate-hedging-btn');
        if (hedgingBtn) {
            hedgingBtn.addEventListener('click', () => this.generateHedging());
        }

        // 熵驅動 8 注預測按鈕
        const entropy8BetsBtn = document.getElementById('entropy-8-bets-btn');
        if (entropy8BetsBtn) {
            entropy8BetsBtn.addEventListener('click', () => this.generateEntropy8Bets());
        }
    }

    renderNumberSelector() {
        const numberSelector = document.getElementById('number-selector');
        const selectedCountVal = document.getElementById('selected-count-val');
        if (!numberSelector) return;

        numberSelector.innerHTML = '';
        for (let i = 1; i <= 49; i++) {
            const btn = document.createElement('div');
            btn.className = 'number-ball';
            btn.textContent = i;
            btn.style.cursor = 'pointer';

            btn.addEventListener('click', () => {
                if (this.selectedNumbers.has(i)) {
                    this.selectedNumbers.delete(i);
                    btn.classList.remove('active');
                } else {
                    if (this.selectedNumbers.size >= 24) {
                        this.uiManager.showNotification('最多只能選擇 24 個號碼', 'error');
                        return;
                    }
                    this.selectedNumbers.add(i);
                    btn.classList.add('active');
                }
                if (selectedCountVal) selectedCountVal.textContent = this.selectedNumbers.size;
                this.updateAvailableGuarantees();
            });
            numberSelector.appendChild(btn);
        }
    }

    async updateAvailableGuarantees() {
        const poolSize = this.selectedNumbers.size;
        const select = document.getElementById('wheeling-system');
        if (!select || poolSize < 8) {
            if (select) select.innerHTML = '<option value="">請選擇至少 8 個號碼</option>';
            return;
        }

        try {
            const response = await fetch(`/api/wheel/available-guarantees?pool_size=${poolSize}`);
            const data = await response.json();

            select.innerHTML = '';
            if (data.available_guarantees && data.available_guarantees.length > 0) {
                data.available_guarantees.forEach(g => {
                    const opt = document.createElement('option');
                    opt.value = `${g.guarantee_t}_${g.condition_m}`;
                    opt.textContent = g.description;
                    select.appendChild(opt);
                });
            } else {
                select.innerHTML = '<option value="greedy">隨機優化覆蓋 (Heuristic)</option>';
            }
        } catch (error) {
            console.error('Failed to fetch guarantees:', error);
        }
    }

    async generateCombinations() {
        if (this.selectedNumbers.size < 8) {
            this.uiManager.showNotification('請至少選擇 8 個號碼', 'error');
            return;
        }

        const systemVal = document.getElementById('wheeling-system').value;
        const [guarantee_t, condition_m] = systemVal.split('_').map(Number);
        const nums = Array.from(this.selectedNumbers).sort((a, b) => a - b);
        const generateBtn = document.getElementById('generate-smart-bet-btn');

        try {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="btn-icon">⏳</span> 運算中...';

            // 調用後端實際的旋轉矩陣生成接口
            const response = await fetch(`/api/wheel/generate?pool=${JSON.stringify(nums)}&guarantee_t=${guarantee_t || 3}&condition_m=${condition_m || 4}`);
            const data = await response.json();

            if (!response.ok) throw new Error(data.detail || '生成失敗');

            let combinations = data.tickets;
            const originalCount = combinations.length;

            // 智慧過濾 (在大規模包牌時由前端進一步篩選)
            const filterConsecutive = document.getElementById('filter-consecutive').checked;
            const filterOddEven = document.getElementById('filter-odd-even').checked;
            const filterExtreme = document.getElementById('filter-extreme').checked;

            combinations = combinations.filter(combo => {
                if (filterConsecutive && this.hasConsecutive(combo, 3)) return false;
                if (filterOddEven && this.isAllOddOrEven(combo)) return false;
                if (filterExtreme && this.isExtreme(combo)) return false;
                return true;
            });

            this.renderResults(combinations, originalCount, data);
        } catch (error) {
            console.error('Wheel generation failed:', error);
            this.uiManager.showNotification(`生成失敗: ${error.message}`, 'error');
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<span class="btn-icon">🎯</span> 產生聰明組合';
        }
    }

    hasConsecutive(numbers, count) {
        let consecutive = 1;
        for (let i = 1; i < numbers.length; i++) {
            if (numbers[i] === numbers[i - 1] + 1) {
                consecutive++;
                if (consecutive >= count) return true;
            } else {
                consecutive = 1;
            }
        }
        return false;
    }

    isAllOddOrEven(numbers) {
        const oddCount = numbers.filter(n => n % 2 !== 0).length;
        return oddCount === 0 || oddCount === numbers.length;
    }

    isExtreme(numbers) {
        const sum = numbers.reduce((a, b) => a + b, 0);
        return sum < 60 || sum > 240; // 簡單的大小判斷
    }

    renderResults(combinations, originalCount, metadata = {}) {
        const resultsDiv = document.getElementById('smart-bet-results');
        const combinationsDiv = document.getElementById('betting-combinations');

        combinationsDiv.innerHTML = '';

        // 新增：顯示生成元數據 (來源與驗證)
        const metaInfo = document.createElement('div');
        metaInfo.style.cssText = 'margin-bottom: 15px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px; font-size: 0.9em;';
        const isVerified = metadata.coverage_verified ? '✅ 已通過組合數學驗證' : '⚠️ 隨機優化結果 (未完全覆蓋)';
        const source = metadata.source === 'lookup_table' ? '精確矩陣 (Optimal Table)' : '啟發式搜索 (Heuristic)';

        metaInfo.innerHTML = `
            <div style="display: flex; justify-content: space-between;">
                <span>策略來源: <b>${source}</b></span>
                <span style="color: ${metadata.coverage_verified ? '#10B981' : '#F59E0B'}">${isVerified}</span>
            </div>
            <div style="margin-top: 5px; opacity: 0.8; font-size: 0.85em;">
                ${metadata.honest_disclaimer || ''}
            </div>
        `;
        combinationsDiv.appendChild(metaInfo);

        if (combinations.length === 0) {
            combinationsDiv.innerHTML += '<div class="no-data">過濾後無符合條件的組合，請放寬過濾條件或增加選號。</div>';
        } else {
            combinations.forEach((combo, index) => {
                const row = document.createElement('div');
                row.className = 'combination-row';
                row.innerHTML = `
                    <span class="combo-index">#${index + 1}</span>
                    <div class="combo-numbers">
                        ${combo.map(n => `<span class="combo-num">${n}</span>`).join('')}
                    </div>
                `;
                combinationsDiv.appendChild(row);
            });
        }

        resultsDiv.style.display = 'block';
        this.uiManager.showNotification(`已生成 ${combinations.length} 組聰明組合 (來自 ${originalCount} 組)`, 'success');
        resultsDiv.scrollIntoView({ behavior: 'smooth' });
    }

    async generateHedging() {
        // 需要 PredictionEngine 支援
        this.uiManager.showNotification('對沖功能需要預測引擎支援', 'info');
    }

    /**
     * 熵驅動 8 注預測
     * 調用後端 API 生成 8 注熵優化號碼
     */
    async generateEntropy8Bets() {
        const btn = document.getElementById('entropy-8-bets-btn');
        const resultsDiv = document.getElementById('entropy-8-bets-results');
        const gridDiv = document.getElementById('entropy-8-bets-grid');
        const strategy = document.getElementById('entropy-8-bets-strategy')?.value || 'balanced';

        // 獲取當前彩券類型
        const lotteryTypeSelect = document.getElementById('lottery-type-filter');
        const lotteryType = lotteryTypeSelect?.value || 'BIG_LOTTO';

        try {
            // 顯示載入狀態
            btn.disabled = true;
            btn.innerHTML = '<span class="btn-icon">⏳</span> 生成中...';
            this.uiManager.showNotification('正在生成熵優化 8 注...', 'info');

            // 調用後端 API
            const response = await fetch(getApiUrl('/api/predict-entropy-8-bets'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lotteryType, strategy })
            });

            if (!response.ok) {
                throw new Error(`API 錯誤: ${response.status}`);
            }

            const data = await response.json();

            // 渲染 8 注號碼
            gridDiv.innerHTML = '';
            data.bets.forEach((bet, idx) => {
                const betCard = document.createElement('div');
                betCard.style.cssText = 'background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;';

                const typeIcon = bet.type === 'hot' ? '🔥' : '❄️';
                const typeLabel = bet.type === 'hot' ? '熱門' : '冷門';

                betCard.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: bold;">第${idx + 1}注 ${typeIcon} ${typeLabel}</span>
                        <span style="font-size: 0.85em; opacity: 0.8;">概率: ${(bet.avg_prob * 100).toFixed(1)}%</span>
                    </div>
                    <div class="predicted-numbers" style="display: flex; gap: 6px; flex-wrap: wrap;">
                        ${bet.numbers.map(n => `<span class="number-ball" style="background: linear-gradient(135deg, #10B981, #059669); color: white; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-weight: bold;">${String(n).padStart(2, '0')}</span>`).join('')}
                    </div>
                    <div style="margin-top: 6px; font-size: 0.8em; opacity: 0.7;">奇數: ${bet.odd_count}/6 | 和值: ${bet.sum}</div>
                `;
                gridDiv.appendChild(betCard);
            });

            // 更新分析數據
            document.getElementById('entropy-coverage-rate').textContent =
                `${(data.analysis.coverage_rate * 100).toFixed(1)}%`;
            document.getElementById('entropy-unique-numbers').textContent =
                `${data.analysis.unique_numbers}/${data.analysis.total_numbers}`;
            document.getElementById('entropy-diversity-score').textContent =
                data.analysis.diversity_score.toFixed(3);

            // 顯示結果區域
            resultsDiv.style.display = 'block';
            resultsDiv.scrollIntoView({ behavior: 'smooth' });

            this.uiManager.showNotification('✅ 已生成 8 注熵優化號碼', 'success');

        } catch (error) {
            console.error('熵 8 注預測失敗:', error);
            this.uiManager.showNotification(`預測失敗: ${error.message}`, 'error');
        } finally {
            // 恢復按鈕狀態
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">🎲</span> 生成熵優化 8 注';
        }
    }
}
