/**
 * 聰明包牌組件
 * 負責處理包牌邏輯和UI交互
 */
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
                    if (this.selectedNumbers.size >= 16) {
                        this.uiManager.showNotification('最多只能選擇 16 個號碼', 'error');
                        return;
                    }
                    this.selectedNumbers.add(i);
                    btn.classList.add('active');
                }
                if (selectedCountVal) selectedCountVal.textContent = this.selectedNumbers.size;
            });
            numberSelector.appendChild(btn);
        }
    }

    generateCombinations() {
        if (this.selectedNumbers.size < 8) {
            this.uiManager.showNotification('請至少選擇 8 個號碼', 'error');
            return;
        }

        const system = document.getElementById('wheeling-system').value;
        const nums = Array.from(this.selectedNumbers).sort((a, b) => a - b);

        // 根據選擇的系統生成組合 (這裡簡化處理，實際應調用更複雜的旋轉矩陣算法)
        // 暫時使用簡單的組合生成作為示例
        let combinations = this.simpleWheeling(nums, system);

        // 智慧過濾
        const filterConsecutive = document.getElementById('filter-consecutive').checked;
        const filterOddEven = document.getElementById('filter-odd-even').checked;
        const filterExtreme = document.getElementById('filter-extreme').checked;

        const originalCount = combinations.length;
        combinations = combinations.filter(combo => {
            if (filterConsecutive && this.hasConsecutive(combo, 3)) return false;
            if (filterOddEven && this.isAllOddOrEven(combo)) return false;
            if (filterExtreme && this.isExtreme(combo)) return false;
            return true;
        });

        this.renderResults(combinations, originalCount);
    }

    // 簡單的旋轉矩陣模擬 (實際專案應引入完整的旋轉矩陣庫)
    simpleWheeling(nums, system) {
        const combinations = [];
        // 這裡僅作示範：隨機選取若干組
        const countMap = {
            'pick10_win3': 10,
            'pick12_win4': 20,
            'pick10_win5': 50
        };
        const count = countMap[system] || 10;

        for (let i = 0; i < count; i++) {
            const shuffled = [...nums].sort(() => 0.5 - Math.random());
            combinations.push(shuffled.slice(0, 6).sort((a, b) => a - b));
        }
        return combinations;
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

    renderResults(combinations, originalCount) {
        const resultsDiv = document.getElementById('smart-bet-results');
        const combinationsDiv = document.getElementById('betting-combinations');

        combinationsDiv.innerHTML = '';
        if (combinations.length === 0) {
            combinationsDiv.innerHTML = '<div class="no-data">過濾後無符合條件的組合，請放寬過濾條件或增加選號。</div>';
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
        this.uiManager.showNotification(`已生成 ${combinations.length} 組聰明組合 (原 ${originalCount} 組)`, 'success');
        resultsDiv.scrollIntoView({ behavior: 'smooth' });
    }

    async generateHedging() {
        // 需要 PredictionEngine 支援
        this.uiManager.showNotification('對沖功能需要預測引擎支援', 'info');
    }
}
