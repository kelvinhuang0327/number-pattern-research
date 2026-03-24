import { getLotteryRules } from '../../utils/Constants.js';
import { QuickPredictionService } from '../../engine/QuickPredictionService.js';
import { apiClient } from '../../services/ApiClient.js';

/**
 * DataHandler - 處理數據操作相關邏輯
 */
export class DataHandler {
    constructor(app) {
        this.app = app;
        this.dataProcessor = app.dataProcessor;
        this.statisticsService = app.statisticsService;
        this.uiManager = app.uiManager;
        this.chartManager = app.chartManager;
    }

    /**
     * 處理彩券類型切換
     */
    handleLotteryTypeChange() {
        // 更新數據摘要
        this.updateDataSummary();

        // 更新樣本大小提示
        this.updateSampleSizeHint();

        // 如果在分析頁面，重新初始化圖表
        const analysisSection = document.getElementById('analysis-section');
        if (analysisSection && analysisSection.classList.contains('active')) {
            setTimeout(() => this.chartManager.initializeCharts(this.app.currentLotteryType), 100);
        }

        // 如果在歷史頁面，重新顯示歷史
        const historySection = document.getElementById('history-section');
        if (historySection && historySection.classList.contains('active')) {
            this.app.currentPage = 1; // 重置到第一頁
            this.app.displayHistory();
        }

        // 顯示通知
        const typeNames = {
            'BIG_LOTTO': '大樂透',
            'BIG_LOTTO_BONUS': '大樂透加開',
            'STAR_3': '三星彩',
            'STAR_4': '四星彩',
            'LOTTO_39': '39樂合彩',
            'DAILY_CASH_539': '今彩539',
            'DAILY_539': '今彩539',
            'POWER_BALL': '威力彩',
            'POWER_LOTTO': '威力彩'
        };
        const typeName = this.app.currentLotteryType ? typeNames[this.app.currentLotteryType] || this.app.currentLotteryType : '全部';
        this.uiManager.showNotification(`已切換至：${typeName}`, 'info');
    }

    /**
     * 更新樣本大小提示
     */
    async updateSampleSizeHint() {
        const hintElement = document.getElementById('sample-size-hint');
        if (!hintElement) return;

        const lotteryType = this.app.currentLotteryType || 'BIG_LOTTO';
        const stats = await this.dataProcessor.getStats();
        const totalDraws = stats.byType[lotteryType] || 0;

        const hint = QuickPredictionService.getSampleSizeHint(lotteryType, totalDraws);
        hintElement.textContent = hint;
    }

    /**
     * 更新數據摘要
     */
    async updateDataSummary() {
        const stats = await this.statisticsService.getDataStats(this.app.currentLotteryType);
        this.uiManager.updateDataSummary(stats, this.app.currentLotteryType);

        // 自動設定模擬月份為最新數據的月份
        if (stats && stats.latestDate) {
            const date = new Date(stats.latestDate);
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const simInput = document.getElementById('simulation-year-month');
            if (simInput) {
                simInput.value = `${year}-${month}`;
            }
        }
    }

    /**
     * 重新從後端載入數據並更新 UI
     * 用於在記錄新增/編輯/刪除後刷新數據
     */
    async loadData() {
        try {
            console.log('🔄 Reloading data from backend...');

            // 從後端重新載入數據
            await this.dataProcessor.fetchDataFromBackend();

            // 獲取最新統計資訊
            const stats = await this.dataProcessor.getStats();

            // 更新 UI 顯示
            this.updateDataSummaryFromStats(stats);
            this.showLotteryTypeSelector(stats);

            console.log('✅ Data reloaded successfully');
        } catch (error) {
            console.error('❌ Failed to reload data:', error);
            throw error;
        }
    }

    /**
     * 根據 IndexedDB 統計資訊更新數據概覽
     */
    updateDataSummaryFromStats(stats) {
        const summaryElement = document.getElementById('data-summary');
        if (!summaryElement) return;

        summaryElement.style.display = 'block';
        const summaryContent = document.getElementById('summary-content');
        if (!summaryContent) return;

        let html = `
            <div class="summary-item">
                <div class="summary-label">總數據量</div>
                <div class="summary-value">${stats.total.toLocaleString()}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">彩券類型</div>
                <div class="summary-value">${Object.keys(stats.byType).length} 種</div>
            </div>
        `;

        // 顯示各類型數量
        Object.entries(stats.byType).forEach(([type, count]) => {
            const typeNames = {
                'BIG_LOTTO': '大樂透',
                'BIG_LOTTO_BONUS': '大樂透加開',
                'POWER_BALL': '威力彩',
                'DAILY_CASH_539': '今彩539',
                'STAR_3': '三星彩',
                'STAR_4': '四星彩',
                'LOTTO_39': '39樂合彩',
                'LOTTO_49': '49樂合彩',
                'LOTTO_38': '38樂合彩',
                'BINGO_BINGO': '賓果賓果',
                'DOUBLE_WIN': '雙贏彩'
            };

            html += `
                <div class="summary-item">
                    <div class="summary-label">${typeNames[type] || type}</div>
                    <div class="summary-value">${count.toLocaleString()} 筆</div>
                </div>
            `;
        });

        summaryContent.innerHTML = html;
    }

    /**
     * 顯示彩券類型選擇器
     */
    showLotteryTypeSelector(stats) {
        const container = document.getElementById('lottery-type-container');
        if (!container) return;

        container.style.display = 'block';

        const grid = document.getElementById('lottery-type-grid');
        if (!grid) return;

        const typeNames = {
            'BIG_LOTTO': { name: '大樂透', icon: '🎱', color: 'linear-gradient(135deg, #F59E0B, #D97706)' },
            'BIG_LOTTO_BONUS': { name: '大樂透加開', icon: '🎁', color: 'linear-gradient(135deg, #EC4899, #DB2777)' },
            'POWER_BALL': { name: '威力彩', icon: '💪', color: 'linear-gradient(135deg, #EF4444, #DC2626)' },
            'DAILY_CASH_539': { name: '今彩539', icon: '📅', color: 'linear-gradient(135deg, #10B981, #059669)' },
            'STAR_3': { name: '三星彩', icon: '3️⃣', color: 'linear-gradient(135deg, #3B82F6, #2563EB)' },
            'STAR_4': { name: '四星彩', icon: '4️⃣', color: 'linear-gradient(135deg, #8B5CF6, #7C3AED)' },
            'LOTTO_39': { name: '39樂合彩', icon: '🔢', color: 'linear-gradient(135deg, #6366F1, #4F46E5)' },
            'LOTTO_49': { name: '49樂合彩', icon: '🔢', color: 'linear-gradient(135deg, #8B5CF6, #7C3AED)' },
            'LOTTO_38': { name: '38樂合彩', icon: '🔢', color: 'linear-gradient(135deg, #EC4899, #DB2777)' },
            'BINGO_BINGO': { name: '賓果賓果', icon: '🎰', color: 'linear-gradient(135deg, #F59E0B, #D97706)' },
            'DOUBLE_WIN': { name: '雙贏彩', icon: '🏆', color: 'linear-gradient(135deg, #10B981, #059669)' }
        };

        const lotteryTypes = Object.keys(stats.byType);

        grid.innerHTML = lotteryTypes.map(type => {
            const info = typeNames[type] || { name: type, icon: '🎲', color: 'var(--gradient-primary)' };
            const count = stats.byType[type] || 0;
            const isActive = this.app.currentLotteryType === type ? 'active' : '';

            return `
            <div class="lottery-type-card ${isActive}" data-type="${type}" style="--card-gradient: ${info.color}">
                <div class="card-bg"></div>
                <div class="type-icon">${info.icon}</div>
                <div class="type-info">
                    <div class="type-name">${info.name}</div>
                    <div class="type-count">${count.toLocaleString()} 筆數據</div>
                </div>
                <div class="selected-indicator">
                    <span class="check-icon">✓</span>
                </div>
            </div>
            `;
        }).join('');

        // 綁定點擊事件
        grid.querySelectorAll('.lottery-type-card').forEach(card => {
            card.addEventListener('click', () => {
                const type = card.dataset.type;
                this.app.currentLotteryType = type;

                // 更新按鈕狀態
                grid.querySelectorAll('.lottery-type-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');

                // 更新顯示
                this.handleLotteryTypeChange();
            });
        });
    }

    /**
     * 清除所有數據
     */
    async clearData() {
        if (!confirm('確定要清除所有已載入的數據嗎？')) return;

        // 清除記憶體中的資料
        this.dataProcessor.clearData();
        this.chartManager.destroyCharts();

        // 清除後端數據
        try {
            await apiClient.clearAllData();
            console.log('✅ Backend data cleared');
            this.uiManager.showNotification('✅ 所有數據已清除', 'success');
        } catch (error) {
            console.error('Failed to clear backend data:', error);
            this.uiManager.showNotification('清除後端數據失敗: ' + error.message, 'error');
        }

        // 更新 UI
        this.updateDataSummary();
        const fileInfo = document.getElementById('file-info');
        if (fileInfo) fileInfo.textContent = '';

        // 回到上傳頁面
        this.uiManager.showSection('upload');

        this.uiManager.showNotification('✅ 所有數據已清除（包含 IndexedDB）', 'success');

        console.log('📊 清除完成 - 記憶體、IndexedDB、localStorage 已全部清空');
    }

    /**
     * 評估預測結果
     * @param {Array} actualNumbers - 實際開獎號碼
     * @param {Array} predictedNumbers - 預測號碼
     * @param {string} lotteryType - 彩券類型
     * @returns {Object} { hits, isSuccess }
     */
    evaluatePrediction(actualNumbers, predictedNumbers, lotteryType, actualSpecial = null) {
        // 判斷是否為順序遊戲（3星彩、4星彩）
        const isOrderedGame = ['STAR_3', 'STAR_4'].includes(lotteryType);

        let hits;
        let isSuccess;

        if (isOrderedGame) {
            // 順序遊戲：比較每個位置是否相同
            hits = 0;
            for (let i = 0; i < actualNumbers.length; i++) {
                if (actualNumbers[i] === predictedNumbers[i]) {
                    hits++;
                }
            }
            // 順序遊戲通常需要完全對中才算成功（4個全對或3個全對）
            isSuccess = hits === actualNumbers.length;

        } else {
            // 非順序遊戲（大樂透、威力彩等）：檢查號碼是否出現（不考慮順序）
            // 🔧 大樂透/威力彩：把特別號也加入目標集合 (6+1=7個目標)
            const actualSet = new Set(actualNumbers);
            if (actualSpecial !== null && actualSpecial !== undefined &&
                ['BIG_LOTTO', 'POWER_LOTTO'].includes(lotteryType)) {
                actualSet.add(parseInt(actualSpecial));  // 加入特別號
            }

            const predictedSet = new Set(predictedNumbers);

            hits = 0;
            for (const num of actualSet) {
                if (predictedSet.has(num)) {
                    hits++;
                }
            }

            // 大樂透等遊戲：中3個以上算成功（對7個目標）
            isSuccess = hits >= 3;
        }

        return { hits, isSuccess };
    }

    /**
     * 根據彩券類型獲取規則
     */
    getLotteryRulesFromType(lotteryType) {
        return getLotteryRules(lotteryType);
    }

    /**
     * 顯示歷史記錄
     */
    async displayHistory() {
        let data;

        // 從 IndexedDB 載入數據（如果啟用）
        if (this.dataProcessor.useIndexedDB && this.app.indexedDBManager && this.app.indexedDBManager.db) {
            if (this.app.currentLotteryType) {
                data = await this.app.indexedDBManager.loadDataByType(this.app.currentLotteryType);
            } else {
                data = await this.app.indexedDBManager.loadAllData();
            }
        } else {
            data = this.dataProcessor.getData();

            // 根據選擇的彩券類型篩選數據
            if (this.app.currentLotteryType) {
                data = data.filter(draw => draw.lotteryType === this.app.currentLotteryType);
            }
        }

        this.uiManager.updateHistoryTable(data, this.app.currentPage, this.app.itemsPerPage);
        this.uiManager.updatePagination(data.length, this.app.currentPage, this.app.itemsPerPage, (page) => {
            this.app.currentPage = page;
            this.displayHistory();
        });
    }
}
