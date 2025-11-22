/**
 * 主應用程式
 * 整合所有模組並處理UI互動
 */

class LotteryApp {
    constructor() {
        this.dataProcessor = new DataProcessor();
        this.analysisEngine = null;
        this.predictionEngine = null;
        this.currentPage = 1;
        this.itemsPerPage = 20;

        this.init();
    }

    /**
     * 初始化應用程式
     */
    init() {
        this.setupEventListeners();
        this.showSection('upload');
    }

    /**
     * 設置事件監聽器
     */
    setupEventListeners() {
        // 導航按鈕
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                this.showSection(section);
            });
        });

        // 檔案上傳
        const uploadBtn = document.getElementById('upload-btn');
        const fileInput = document.getElementById('file-input');

        if (uploadBtn && fileInput) {
            uploadBtn.addEventListener('click', () => {
                fileInput.click();
            });

            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (file) {
                    await this.handleFileUpload(file);
                }
            });
        }

        // 範例數據
        const sampleBtn = document.getElementById('sample-data-btn');
        if (sampleBtn) {
            sampleBtn.addEventListener('click', () => {
                this.loadSampleData();
            });
        }

        // 預測按鈕
        const predictBtn = document.getElementById('predict-btn');
        if (predictBtn) {
            predictBtn.addEventListener('click', () => {
                this.runPrediction();
            });
        }

        // 搜尋和排序
        const searchInput = document.getElementById('search-input');
        const sortSelect = document.getElementById('sort-select');

        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchHistory(e.target.value);
            });
        }

        if (sortSelect) {
            sortSelect.addEventListener('change', (e) => {
                this.sortHistory(e.target.value);
            });
        }

        // 清除數據
        const clearDataBtn = document.getElementById('clear-data-btn');
        if (clearDataBtn) {
            clearDataBtn.addEventListener('click', () => {
                this.clearData();
            });
        }
    }

    /**
     * 顯示指定區塊
     */
    showSection(sectionName) {
        // 更新導航按鈕
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.section === sectionName) {
                btn.classList.add('active');
            }
        });

        // 顯示對應區塊
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });

        const targetSection = document.getElementById(`${sectionName}-section`);
        if (targetSection) {
            targetSection.classList.add('active');
        }

        // 如果切換到分析或歷史頁面，需要有數據
        if ((sectionName === 'analysis' || sectionName === 'history') && this.dataProcessor.getData().length === 0) {
            this.showNotification('請先上傳數據或載入範例數據', 'warning');
            this.showSection('upload');
            return;
        }

        // 初始化對應功能
        if (sectionName === 'analysis' && this.dataProcessor.getData().length > 0) {
            this.initializeAnalysis();
        } else if (sectionName === 'history' && this.dataProcessor.getData().length > 0) {
            this.displayHistory();
        }
    }

    /**
     * 處理檔案上傳
     */
    async handleFileUpload(file) {
        try {
            this.showNotification('正在解析檔案...', 'info');

            await this.dataProcessor.loadCSVData(file);

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                fileInfo.textContent = `✓ 已載入: ${file.name}`;
            }

            this.updateDataSummary();
            this.showNotification('數據載入成功！', 'success');

        } catch (error) {
            this.showNotification('檔案載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    /**
     * 載入範例數據
     */
    loadSampleData() {
        this.dataProcessor.loadSampleData();

        const fileInfo = document.getElementById('file-info');
        if (fileInfo) {
            fileInfo.textContent = '✓ 已載入範例數據';
        }

        this.updateDataSummary();
        this.showNotification('範例數據載入成功！', 'success');
    }

    /**
     * 更新數據摘要
     */
    updateDataSummary() {
        const stats = this.dataProcessor.getDataStats();
        if (!stats) return;

        const summary = document.getElementById('data-summary');
        if (summary) {
            summary.style.display = 'block';
        }

        const totalDraws = document.getElementById('total-draws');
        const dateRange = document.getElementById('date-range');
        const latestDraw = document.getElementById('latest-draw');

        if (totalDraws) totalDraws.textContent = stats.totalDraws;
        if (dateRange) dateRange.textContent = `${stats.dateRange.start} ~ ${stats.dateRange.end}`;
        if (latestDraw) latestDraw.textContent = stats.latestDraw;
    }

    /**
     * 初始化分析
     */
    initializeAnalysis() {
        if (!this.analysisEngine) {
            this.analysisEngine = new AnalysisEngine(this.dataProcessor);
        }

        // 延遲一下讓DOM完全渲染
        setTimeout(() => {
            this.analysisEngine.initializeCharts();
        }, 100);
    }

    /**
     * 執行預測
     */
    runPrediction() {
        const method = document.getElementById('prediction-method').value;
        const sampleSize = document.getElementById('sample-size').value;

        if (this.dataProcessor.getData().length === 0) {
            this.showNotification('請先載入數據', 'warning');
            return;
        }

        if (!this.predictionEngine) {
            this.predictionEngine = new PredictionEngine(this.dataProcessor);
        }

        this.showNotification('正在分析預測...', 'info');

        // 模擬計算延遲，增加真實感
        setTimeout(() => {
            const prediction = this.predictionEngine.predict(method, sampleSize);
            this.predictionEngine.displayPrediction(prediction);
            this.showNotification('預測完成！', 'success');
        }, 500);
    }

    /**
     * 顯示歷史記錄
     */
    displayHistory(data = null) {
        const historyData = data || this.dataProcessor.getData();
        const tbody = document.getElementById('history-tbody');

        if (!tbody) return;

        // 計算分頁
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        const pageData = historyData.slice(startIndex, endIndex);

        // 生成表格內容
        tbody.innerHTML = pageData.map(draw => `
            <tr>
                <td><strong>${draw.draw}</strong></td>
                <td>${draw.date}</td>
                <td>
                    <div class="draw-numbers">
                        ${draw.numbers.map(num =>
            `<div class="draw-number">${num}</div>`
        ).join('')}
                    </div>
                </td>
                <td>
                    <div class="draw-numbers">
                        <div class="draw-number special">${draw.special}</div>
                    </div>
                </td>
            </tr>
        `).join('');

        // 更新分頁
        this.updatePagination(historyData.length);
    }

    /**
     * 更新分頁
     */
    updatePagination(totalItems) {
        const totalPages = Math.ceil(totalItems / this.itemsPerPage);
        const pagination = document.getElementById('pagination');

        if (!pagination) return;

        let html = '';

        // 上一頁
        if (this.currentPage > 1) {
            html += `<button class="page-btn" data-page="${this.currentPage - 1}">‹ 上一頁</button>`;
        }

        // 頁碼
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(totalPages, this.currentPage + 2);

        if (startPage > 1) {
            html += `<button class="page-btn" data-page="1">1</button>`;
            if (startPage > 2) {
                html += `<span class="page-ellipsis">...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === this.currentPage ? 'active' : '';
            html += `<button class="page-btn ${activeClass}" data-page="${i}">${i}</button>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                html += `<span class="page-ellipsis">...</span>`;
            }
            html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
        }

        // 下一頁
        if (this.currentPage < totalPages) {
            html += `<button class="page-btn" data-page="${this.currentPage + 1}">下一頁 ›</button>`;
        }

        pagination.innerHTML = html;

        // 綁定分頁按鈕事件
        pagination.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.currentPage = parseInt(e.target.dataset.page);
                this.displayHistory();
            });
        });
    }

    /**
     * 搜尋歷史記錄
     */
    searchHistory(query) {
        const results = this.dataProcessor.searchData(query);
        this.currentPage = 1;
        this.displayHistory(results);
    }

    /**
     * 排序歷史記錄
     */
    sortHistory(order) {
        const sorted = this.dataProcessor.sortData(order);
        this.currentPage = 1;
        this.displayHistory(sorted);
    }

    /**
     * 清除數據
     */
    clearData() {
        // 確認對話框
        if (!confirm('確定要清除所有已載入的數據嗎？此操作無法復原。')) {
            return;
        }

        // 清除數據
        this.dataProcessor.clearData();

        // 重置分析和預測引擎
        this.analysisEngine = null;
        this.predictionEngine = null;

        // 隱藏數據摘要
        const summary = document.getElementById('data-summary');
        if (summary) {
            summary.style.display = 'none';
        }

        // 清除檔案資訊
        const fileInfo = document.getElementById('file-info');
        if (fileInfo) {
            fileInfo.textContent = '';
        }

        // 清除檔案輸入
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.value = '';
        }

        // 清除歷史記錄表格
        const historyTbody = document.getElementById('history-tbody');
        if (historyTbody) {
            historyTbody.innerHTML = '';
        }

        // 清除分頁
        const pagination = document.getElementById('pagination');
        if (pagination) {
            pagination.innerHTML = '';
        }

        // 清除預測結果
        const predictedNumbers = document.getElementById('predicted-numbers');
        if (predictedNumbers) {
            predictedNumbers.innerHTML = '';
        }

        const predictionReport = document.getElementById('prediction-report');
        if (predictionReport) {
            predictionReport.innerHTML = '';
        }

        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');
        if (confidenceFill) {
            confidenceFill.style.width = '0%';
        }
        if (confidenceValue) {
            confidenceValue.textContent = '0%';
        }

        // 重置頁碼
        this.currentPage = 1;

        // 切換到上傳頁面
        this.showSection('upload');

        // 顯示通知
        this.showNotification('數據已清除', 'success');
    }


    /**
     * 顯示通知
     */
    showNotification(message, type = 'info') {
        // 創建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        // 添加樣式
        Object.assign(notification.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '16px 24px',
            borderRadius: '12px',
            color: 'white',
            fontWeight: '500',
            zIndex: '1000',
            animation: 'slideIn 0.3s ease',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
            maxWidth: '400px'
        });

        // 根據類型設置背景色
        const colors = {
            info: 'linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(147, 51, 234, 0.95))',
            success: 'linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(59, 130, 246, 0.95))',
            warning: 'linear-gradient(135deg, rgba(251, 191, 36, 0.95), rgba(245, 158, 11, 0.95))',
            error: 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(220, 38, 38, 0.95))'
        };

        notification.style.background = colors[type] || colors.info;

        document.body.appendChild(notification);

        // 3秒後自動移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// 添加動畫樣式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .page-ellipsis {
        padding: var(--spacing-sm) var(--spacing-md);
        color: var(--text-tertiary);
    }
    
    .report-section {
        margin-bottom: var(--spacing-lg);
    }
    
    .report-section h4 {
        color: var(--primary-light);
        margin-bottom: var(--spacing-sm);
        font-size: 1.1rem;
    }
    
    .report-section p {
        line-height: 1.8;
        margin-bottom: var(--spacing-sm);
    }
    
    .report-section ul {
        list-style: none;
        padding: 0;
    }
    
    .report-section li {
        padding: var(--spacing-xs) 0;
        border-bottom: 1px solid var(--border-color);
    }
    
    .report-section li:last-child {
        border-bottom: none;
    }
`;
document.head.appendChild(style);

// 當DOM載入完成後啟動應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.lotteryApp = new LotteryApp();
});
