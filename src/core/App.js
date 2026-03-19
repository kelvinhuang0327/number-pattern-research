import { DataProcessor } from './DataProcessor.js';
import { StatisticsService } from '../data/StatisticsService.js';
import { PredictionEngine } from '../engine/PredictionEngine.js';
import { UIManager } from '../ui/UIManager.js';
import { ChartManager } from '../ui/ChartManager.js';
import { SmartBettingComponent } from '../ui/components/SmartBettingComponent.js';
import { QuickPredictionService } from '../engine/QuickPredictionService.js';
import { getLotteryRules } from '../utils/Constants.js';
import { AutoLearningManager } from '../ui/AutoLearningManager.js';
import { apiClient } from '../services/ApiClient.js';
import { progressManager } from '../ui/ProgressManager.js';
import { RecordManager } from '../ui/RecordManager.js';
import { FileUploadHandler } from './handlers/FileUploadHandler.js';
import { DataHandler } from './handlers/DataHandler.js';
import { UIDisplayHandler } from './handlers/UIDisplayHandler.js';
import { SimulationHandler } from './handlers/SimulationHandler.js';
import { PredictionHandler } from './handlers/PredictionHandler.js';
import { getApiUrl } from '../config/apiConfig.js';

/**
 * 主應用程式
 * 整合所有模組並處理UI互動
 */
export class App {
    constructor() {
        this.dataProcessor = new DataProcessor();
        this.statisticsService = new StatisticsService(this.dataProcessor);
        this.uiManager = new UIManager();
        this.chartManager = new ChartManager(this.statisticsService);
        this.predictionEngine = new PredictionEngine(this.dataProcessor, this.statisticsService);
        this.smartBetting = new SmartBettingComponent(this.dataProcessor, this.predictionEngine, this.uiManager);
        console.log('🏗️ Instantiating AutoLearningManager...');
        this.autoLearningManager = new AutoLearningManager(this.dataProcessor, this.uiManager);
        console.log('✅ AutoLearningManager instantiated');
        this.recordManager = new RecordManager(this);

        this.currentPage = 1;
        this.itemsPerPage = 20;
        this.currentLotteryType = ''; // '' means all types

        // Debounce timers for buttons
        this.debounceTimers = {};

        // 初始化 Handlers（模塊化處理）
        this.fileUploadHandler = new FileUploadHandler(this);
        this.dataHandler = new DataHandler(this);
        this.uiDisplayHandler = new UIDisplayHandler(this);
        this.simulationHandler = new SimulationHandler(this);
        this.predictionHandler = new PredictionHandler(this);

        // 不在 constructor 中自動初始化，由外部呼叫
        // this.init();
    }
    /**
     * 解析日期字串中的年份（支援 YYYY-MM-DD / YYYY/MM/DD）
     */
    getYearFromDate(dateStr) {
        if (!dateStr) return '';
        const normalized = String(dateStr).replace(/\//g, '-');
        const m = normalized.match(/^(\d{4})-/);
        if (m) return m[1];
        const d = new Date(normalized);
        if (!isNaN(d.getTime())) return String(d.getFullYear());
        const m2 = String(dateStr).match(/(\d{4})/);
        return m2 ? m2[1] : '';
    }

    /**
     * Debounce utility function
     */
    debounce(key, func, delay = 300) {
        if (this.debounceTimers[key]) {
            clearTimeout(this.debounceTimers[key]);
        }
        this.debounceTimers[key] = setTimeout(func, delay);
    }

    /**
     * Set button loading state
     */
    setButtonLoading(button, isLoading) {
        if (!button) return;

        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.innerHTML;
            const icon = button.querySelector('.btn-icon');
            if (icon) {
                icon.textContent = '⏳';
            }
        } else {
            button.disabled = false;
            if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    }

    /**
     * 檢查檔名是否應該被忽略（委託給 FileUploadHandler）
     */
    shouldIgnoreFile(filename) {
        return this.fileUploadHandler.shouldIgnoreFile(filename);
    }


    async init() {
        // 🚀 初始化：直接從後端獲取數據
        console.log('🔄 Initializing App (Backend-Driven Mode)...');

        // 設置 DataProcessor 的 app 引用
        this.dataProcessor.app = this;

        // 設置 AutoLearningManager 的 app 引用
        this.autoLearningManager.setApp(this);

        this.setupEventListeners();

        // 立即顯示 UI
        this.uiManager.showSection('upload');

        // 從後端載入數據
        try {
            const data = await this.dataProcessor.fetchDataFromBackend();
            if (data.length > 0) {
                console.log(`📦 Loaded ${data.length} records from backend`);
                this.updateDataSummary();

                // 更新統計資訊
                const stats = await this.dataProcessor.getStats();
                this.updateDataSummaryFromStats(stats);
                this.showLotteryTypeSelector(stats);

                // 預設選擇第一個類型
                if (!this.currentLotteryType && data.length > 0) {
                    this.currentLotteryType = data[0].lotteryType || 'BIG_LOTTO';
                    this.handleLotteryTypeChange();
                }
            } else {
                console.log('📭 Backend has no data');
            }
        } catch (err) {
            console.error('❌ Failed to load data from backend:', err);
        }

        // 啟動後端健康檢查
        this._backendRetryDelay = 15000;
        this._backendRetryMax = 120000;
        this._backendHealthTimer = null;
        this._backendWasDown = false;
        this.scheduleBackendHealthCheck(false);
    }

    /**
     * 檢查後端健康狀態，若失效則停用 AI/後端相關策略
     * @param {boolean} silent - 是否靜默（避免每次輪詢都提示）
     */
    async checkBackendStatus(silent = false) {
        const methodSelect = document.getElementById('prediction-method');
        if (!methodSelect) return;

        let backendOk = true;
        try {
            const res = await fetch(getApiUrl('/health'), { cache: 'no-store' });
            backendOk = res.ok;
        } catch (e) {
            backendOk = false;
        }

        // 需要被管理的策略 value 前綴 / 名稱
        const backendDependent = [
            'ai_prophet', 'ai_xgboost', 'ai_autogluon', 'ai_lstm', // API 策略
            'auto_optimize', 'backend_optimized', // 後端優化相關
            'coordinator', 'coordinator_direct', 'coordinator_hybrid'
        ];

        Array.from(methodSelect.options).forEach(opt => {
            if (backendDependent.includes(opt.value)) {
                if (!backendOk) {
                    opt.disabled = true;
                    opt.title = '後端未啟動，該策略暫不可用';
                    opt.classList.add('backend-disabled');
                } else {
                    opt.disabled = false;
                    opt.title = '';
                    opt.classList.remove('backend-disabled');
                }
            }
        });

        if (!backendOk) {
            if (!silent) {
                this.uiManager.showNotification('後端服務未啟動，AI 與優化策略已停用（重試中）', 'warning');
            }
            this._backendWasDown = true;
        } else {
            // 後端恢復：重置退避時間
            if (this._backendWasDown && !silent) {
                this.uiManager.showNotification('後端服務恢復，AI 與優化策略已啟用', 'success');
            }
            this._backendRetryDelay = 15000; // 重置為最小
            this._backendWasDown = false;
        }
        // 重新排程下一次檢查（依狀態動態延遲）
        this.scheduleBackendHealthCheck(true, backendOk);
    }

    /**
     * 指數退避排程：後端失敗 → 延長間隔；成功 → 重置最小間隔
     */
    scheduleBackendHealthCheck(fromCheck = false, lastStatusOk = true) {
        if (fromCheck) {
            if (!lastStatusOk) {
                // 失敗：延長（乘 2，直到上限）
                this._backendRetryDelay = Math.min(this._backendRetryDelay * 2, this._backendRetryMax);
            } else {
                // 成功：保持最小值
                this._backendRetryDelay = 15000;
            }
        }
        if (this._backendHealthTimer) {
            clearTimeout(this._backendHealthTimer);
        }
        this._backendHealthTimer = setTimeout(() => this.checkBackendStatus(true), this._backendRetryDelay);
    }

    /**
     * 啟動記憶體監控
     */
    startMemoryMonitoring() {
        memoryOptimizer.startMonitoring((stats) => {
            // 記憶體使用率過高時的警告
            if (!this.memoryWarningShown) {
                console.warn('⚠️ 記憶體使用率過高:', stats);
                this.uiManager.showNotification(
                    `記憶體使用率過高 (${stats.usagePercent}%)，建議清除部分數據或重新整理頁面`,
                    'warning'
                );
                this.memoryWarningShown = true;

                // 30 秒後重置警告標記
                setTimeout(() => {
                    this.memoryWarningShown = false;
                }, 30000);
            }
        });

        console.log('✅ 記憶體監控已啟動');
    }


    setupEventListeners() {
        // 檔案上傳
        const uploadBtn = document.getElementById('upload-btn');
        const fileInput = document.getElementById('file-input');

        if (uploadBtn && fileInput) {
            uploadBtn.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (file) await this.handleFileUpload(file);
                // Reset input
                e.target.value = '';
            });
        }

        // 多檔案上傳
        const folderBtn = document.getElementById('folder-btn');
        const multipleInput = document.getElementById('multiple-input');

        if (folderBtn && multipleInput) {
            folderBtn.addEventListener('click', () => multipleInput.click());
            multipleInput.addEventListener('change', async (e) => {
                const files = e.target.files;
                if (files && files.length > 0) await this.handleMultipleFileUpload(files);
                // Reset input
                e.target.value = '';
            });
        }

        // 範例數據
        const sampleBtn = document.getElementById('sample-data-btn');
        if (sampleBtn) {
            sampleBtn.addEventListener('click', () => this.loadSampleData());
        }

        // 清除數據
        const clearDataBtn = document.getElementById('clear-data-btn');
        if (clearDataBtn) {
            clearDataBtn.addEventListener('click', () => this.clearData());
        }

        // 預測按鈕 (with debounce)
        const predictBtn = document.getElementById('predict-btn');
        if (predictBtn) {
            predictBtn.addEventListener('click', () => {
                this.debounce('predict', () => this.runPrediction(), 300);
            });
        }

        // Coordinator 控制項顯示邏輯（僅 coordinator* 策略顯示）
        const predictionMethodSelect = document.getElementById('prediction-method');
        if (predictionMethodSelect) {
            this.updateCoordinatorControlsVisibility(predictionMethodSelect.value);
            predictionMethodSelect.addEventListener('change', (e) => {
                this.updateCoordinatorControlsVisibility(e.target.value);
            });
        }

        // 快速預測按鈕
        const quickPredictBtn = document.getElementById('quick-predict-btn');
        if (quickPredictBtn) {
            quickPredictBtn.addEventListener('click', () => this.handleQuickPredict());
        }

        // 雙注優化預測按鈕
        const dualBetPredictBtn = document.getElementById('dual-bet-predict-btn');
        if (dualBetPredictBtn) {
            dualBetPredictBtn.addEventListener('click', () => this.handleDualBetPredict());
        }

        // 聰明包牌 - 智能雙注預測按鈕
        const smartDualBetBtn = document.getElementById('smart-dual-bet-btn');
        if (smartDualBetBtn) {
            smartDualBetBtn.addEventListener('click', () => this.handleSmartDualBetPredict());
        }

        // 模擬按鈕 (with debounce)
        const simulationBtn = document.getElementById('simulation-btn');
        if (simulationBtn) {
            simulationBtn.addEventListener('click', () => {
                this.debounce('simulation', () => this.runSimulation(), 300);
            });
        }

        // 🆕 預測方法說明卡片
        const simulationMethodSelect = document.getElementById('simulation-method');
        console.log('🔍 Looking for simulation-method element:', simulationMethodSelect);

        if (simulationMethodSelect) {
            console.log('✅ Found simulation-method, setting up event listener');

            // 初始化時顯示第一個方法的說明
            console.log('🎯 Initial method:', simulationMethodSelect.value);
            this.updateMethodDescription(simulationMethodSelect.value);

            // 監聽下拉選單變更
            simulationMethodSelect.addEventListener('change', (e) => {
                console.log('📢 Change event fired! New value:', e.target.value);
                this.updateMethodDescription(e.target.value);
            });
        } else {
            console.error('❌ simulation-method element not found!');
        }

        // 彩券類型篩選
        const lotteryTypeFilter = document.getElementById('lottery-type-filter');
        if (lotteryTypeFilter) {
            lotteryTypeFilter.addEventListener('change', (e) => {
                this.currentLotteryType = e.target.value;
                this.handleLotteryTypeChange();
            });
        }

        // 導航切換時的額外邏輯
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                if (section === 'analysis') {
                    // 確保圖表正確渲染
                    setTimeout(() => this.chartManager.initializeCharts(this.currentLotteryType), 100);
                    this.updateDataSummary();
                } else if (section === 'autolearning') {
                    if (this.autoLearningManager) {
                        this.autoLearningManager.refreshStatus(true);
                    }
                } else if (section === 'history') {
                    this.displayHistory();
                }
            });
        });
    }

    updateCoordinatorControlsVisibility(method) {
        const modeGroup = document.getElementById('coord-mode-group');
        const betsGroup = document.getElementById('coord-bets-group');
        if (!modeGroup || !betsGroup) return;

        const isCoordinator = String(method || '').startsWith('coordinator');
        modeGroup.style.display = isCoordinator ? '' : 'none';
        betsGroup.style.display = isCoordinator ? '' : 'none';
    }

    /**
     * 處理文件上傳（委託給 FileUploadHandler）
     */
    async handleFileUpload(file) {
        return this.fileUploadHandler.handleFileUpload(file);
    }

    /**
     * 顯示上傳引導（委託給 FileUploadHandler）
     */
    showUploadGuidance(stats) {
        return this.fileUploadHandler.showUploadGuidance(stats);
    }

    async handleMultipleFileUpload(files) {
        try {
            // 🔍 過濾檔案：根據下拉選項進行過濾
            const filteredFiles = [];
            const ignoredFiles = [];
            const filterSelect = document.getElementById('upload-filter-select');
            const filterValue = filterSelect ? filterSelect.value : 'ALL';

            console.log(`📂 Upload Filter Mode: ${filterValue}`);

            for (let i = 0; i < files.length; i++) {
                const fileName = files[i].name;
                let shouldProcess = false;

                // 檢查是否為系統忽略檔案
                if (this.shouldIgnoreFile(fileName)) {
                    ignoredFiles.push(fileName);
                    continue;
                }

                // 根據篩選器判斷
                if (filterValue === 'ALL') {
                    // 全部模式：忽略賓果賓果
                    const isBingo = fileName.includes('賓果') || fileName.includes('BINGO');
                    if (!isBingo) {
                        shouldProcess = true;
                    } else {
                        console.log(`🚫 忽略賓果檔案 (ALL模式): ${fileName}`);
                        ignoredFiles.push(fileName + ' (賓果)');
                    }
                } else if (filterValue === 'BIG_LOTTO') {
                    // 大樂透 (不含加開) -> 這裡使用嚴格過濾或寬鬆過濾? 
                    // 通常"大樂透"檔案名就是"大樂透_xxxx.csv"。 "大樂透加開"是"大樂透加開獎項_xxxx.csv"
                    // 如果用戶選"大樂透"，是否要包含加開? 用戶分開列了，所以這裡分開處理
                    if (fileName.includes('大樂透') && !fileName.includes('加開')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'BIG_LOTTO_BONUS') {
                    // 大樂透加開
                    if (fileName.includes('大樂透') && fileName.includes('加開')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'DAILY_539') {
                    // 今彩539
                    if (fileName.includes('今彩539') || fileName.includes('539')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'POWER_LOTTO') {
                    // 威力彩
                    if (fileName.includes('威力彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'STAR_3') {
                    // 3星彩
                    if (fileName.includes('3星彩') || fileName.includes('三星彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'STAR_4') {
                    // 4星彩
                    if (fileName.includes('4星彩') || fileName.includes('四星彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'LOTTO_39') {
                    // 39樂合彩
                    if (fileName.includes('39樂合彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'LOTTO_49') {
                    // 49樂合彩
                    if (fileName.includes('49樂合彩')) {
                        shouldProcess = true;
                    }
                }

                if (shouldProcess) {
                    filteredFiles.push(files[i]);
                } else {
                    ignoredFiles.push(fileName);
                }
            }

            // 顯示過濾結果
            if (ignoredFiles.length > 0) {
                const ignoredList = ignoredFiles.slice(0, 10).join('\n• ');
                const moreCount = ignoredFiles.length > 10 ? `\n• ...及其他 ${ignoredFiles.length - 10} 個檔案` : '';

                let filterName = '自訂';
                if (filterValue === 'ALL') filterName = '全部(忽略賓果)';
                if (filterValue === 'BIG_LOTTO') filterName = '大樂透';
                if (filterValue === 'BIG_LOTTO_BONUS') filterName = '大樂透加開';
                if (filterValue === 'DAILY_539') filterName = '今彩539';
                if (filterValue === 'POWER_LOTTO') filterName = '威力彩';
                if (filterValue === 'STAR_3') filterName = '3星彩';
                if (filterValue === 'STAR_4') filterName = '4星彩';
                if (filterValue === 'LOTTO_39') filterName = '39樂合彩';
                if (filterValue === 'LOTTO_49') filterName = '49樂合彩';

                this.uiManager.showNotification(
                    `⚠️ 已根據「${filterName}」過濾檔案\n\n` +
                    `📋 將載入: ${filteredFiles.length} 個檔案\n` +
                    `🚫 已忽略: ${ignoredFiles.length} 個檔案\n\n` +
                    `忽略的檔案:\n• ${ignoredList}${moreCount}`,
                    'warning',
                    8000  // 顯示 8 秒
                );
            }

            if (filteredFiles.length === 0) {
                this.uiManager.showNotification(
                    '❌ 沒有可載入的檔案\n\n' +
                    '所選資料夾中沒有符合條件的檔案。\n' +
                    `當前過濾模式: ${filterValue}`,
                    'error'
                );
                return;
            }

            // 顯示進度
            progressManager.show(`正在解析 ${filteredFiles.length} 個檔案...`, 5);
            let totalParsed = 0;
            let successCount = 0;
            const fileResults = [];
            let allParsedData = [];

            for (let i = 0; i < filteredFiles.length; i++) {
                const progress = 5 + (i / filteredFiles.length) * 40; // 5-45%
                progressManager.updateProgress(progress, `正在解析第 ${i + 1}/${filteredFiles.length} 個檔案...`);

                try {
                    const result = await this.dataProcessor.loadCSVData(filteredFiles[i]);
                    if (result.data && result.data.length > 0) {
                        allParsedData = allParsedData.concat(result.data);
                        totalParsed += result.data.length;
                        successCount++;
                        fileResults.push({
                            name: filteredFiles[i].name,
                            count: result.data.length,
                            success: true
                        });
                    }
                } catch (err) {
                    console.warn(`File ${filteredFiles[i].name} failed:`, err);
                    fileResults.push({ name: filteredFiles[i].name, error: err.message, success: false });
                }
            }

            // 上傳到後端
            if (allParsedData.length > 0) {
                progressManager.updateProgress(50, `正在上傳 ${totalParsed} 筆數據...`);
                const lotteryRules = getLotteryRules(allParsedData[0].lotteryType);
                await apiClient.uploadDraws(allParsedData, lotteryRules);
                progressManager.updateProgress(75, '上傳完成，正在刷新數據...');
                await this.dataProcessor.fetchDataFromBackend();
            }

            // 更新 UI
            progressManager.updateProgress(90, '更新統計資訊...');
            const stats = await this.dataProcessor.getStats();
            this.updateDataSummaryFromStats(stats);
            this.showLotteryTypeSelector(stats);

            // 建立詳細訊息
            let detailMsg = `批次載入完成！\n✅ 成功: ${successCount}/${filteredFiles.length} 個檔案`;
            if (ignoredFiles.length > 0) {
                detailMsg += `\n⚠️ 已忽略: ${ignoredFiles.length} 個不符條件的檔案`;
            }
            detailMsg += `\n📊 共解析: ${totalParsed} 筆\n📦 目前總數: ${stats.total} 筆\n\n`;

            if (stats && stats.byType) {
                detailMsg += '各彩券類型總數：\n';
                const typeNames = {
                    'BIG_LOTTO': '大樂透',
                    'BIG_LOTTO_BONUS': '大樂透加開',
                    'STAR_3': '三星彩',
                    'STAR_4': '四星彩',
                    'LOTTO_39': '39樂合彩',
                    'DAILY_CASH_539': '今彩539'
                };
                Object.entries(stats.byType).forEach(([type, count]) => {
                    detailMsg += `• ${typeNames[type] || type}: ${count} 筆\n`;
                });
            }

            progressManager.updateProgress(100, '完成！');
            progressManager.hide(1000);

            this.uiManager.showNotification(detailMsg, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                const successFiles = fileResults.filter(f => f.success);
                const failedFiles = fileResults.filter(f => !f.success);

                let html = `<div style="color: #22c55e; font-weight: 500;">`;
                html += `✓ 已批次載入 ${successCount} 個檔案<br>`;
                html += `<div style="font-size: 0.85em; margin-top: 8px; line-height: 1.6;">`;

                successFiles.forEach(f => {
                    const displayCount = f.parsed || f.count;
                    html += `• ${f.name}: ${displayCount} 筆`;
                    if (f.parsed && f.parsed > f.count) {
                        html += ` <span style="color: #f59e0b;">(${f.count} 新增)</span>`;
                    }
                    html += `<br>`;
                });

                if (failedFiles.length > 0) {
                    html += `</div><div style="color: #ef4444; margin-top: 8px;">`;
                    html += `✗ 失敗 ${failedFiles.length} 個檔案<br>`;
                    failedFiles.forEach(f => {
                        html += `• ${f.name}<br>`;
                    });
                }

                html += `</div></div>`;
                fileInfo.innerHTML = html;
            }

        } catch (error) {
            progressManager.hide(0);
            this.uiManager.showNotification('批次載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    async loadSampleData() {
        try {
            progressManager.show('正在加載範例數據...', 10);

            this.dataProcessor.loadSampleData();
            const sampleData = this.dataProcessor.getData();
            progressManager.updateProgress(30, '範例數據已生成...');

            // 上傳到後端
            progressManager.updateProgress(50, '正在上傳到後端...');
            const lotteryRules = getLotteryRules('BIG_LOTTO');
            await apiClient.uploadDraws(sampleData, lotteryRules);
            progressManager.updateProgress(75, '上傳完成，正在刷新...');

            // 重新從後端獲取
            await this.dataProcessor.fetchDataFromBackend();
            progressManager.updateProgress(90, '更新顯示...');
            await this.updateDataSummary();

            progressManager.updateProgress(100, '完成！');
            progressManager.hide(1000);

            this.uiManager.showNotification('範例數據載入成功！', 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) fileInfo.textContent = '✓ 已載入範例數據';
        } catch (error) {
            progressManager.hide(0);
            this.uiManager.showNotification('範例數據加載失敗: ' + error.message, 'error');
        }
    }

    handleLotteryTypeChange() {
        // 更新數據摘要
        this.updateDataSummary();

        // 更新樣本大小提示
        this.updateSampleSizeHint();

        // 如果在分析頁面，重新初始化圖表
        const analysisSection = document.getElementById('analysis-section');
        if (analysisSection && analysisSection.classList.contains('active')) {
            setTimeout(() => this.chartManager.initializeCharts(this.currentLotteryType), 100);
        }

        // 如果在歷史頁面，重新顯示歷史
        const historySection = document.getElementById('history-section');
        if (historySection && historySection.classList.contains('active')) {
            this.currentPage = 1; // 重置到第一頁
            this.displayHistory();
        }

        // 顯示通知
        const typeNames = {
            'BIG_LOTTO': '大樂透',
            'BIG_LOTTO_BONUS': '大樂透加開',
            'STAR_3': '三星彩',
            'STAR_4': '四星彩',
            'LOTTO_39': '39樂合彩',
            'DAILY_CASH_539': '今彩539',
            'POWER_BALL': '威力彩'
        };
        const typeName = this.currentLotteryType ? typeNames[this.currentLotteryType] || this.currentLotteryType : '全部';
        this.uiManager.showNotification(`已切換至：${typeName}`, 'info');
    }

    /**
     * 更新樣本大小提示
     */
    async updateSampleSizeHint() {
        const hintElement = document.getElementById('sample-size-hint');
        if (!hintElement) return;

        const lotteryType = this.currentLotteryType || 'BIG_LOTTO';
        const stats = await this.dataProcessor.getStats();
        const totalDraws = stats.byType[lotteryType] || 0;

        const hint = QuickPredictionService.getSampleSizeHint(lotteryType, totalDraws);
        hintElement.textContent = hint;
    }

    /**
     * 處理快速預測
     */
    async handleQuickPredict() {
        const quickPredictBtn = document.getElementById('quick-predict-btn');

        try {
            this.setButtonLoading(quickPredictBtn, true);
            const lotteryType = this.currentLotteryType || 'BIG_LOTTO';
            const stats = await this.dataProcessor.getStats();
            const totalDraws = stats.byType[lotteryType] || 0;

            if (totalDraws < 10) {
                this.uiManager.showNotification('數據量不足，無法進行預測（至少需要 10 期）', 'warning');
                return;
            }

            // 獲取快速預測配置
            const config = QuickPredictionService.getQuickPredictConfig(lotteryType, totalDraws);

            // 自動設置預測方法和樣本大小
            const methodSelect = document.getElementById('prediction-method');
            const sampleSizeSelect = document.getElementById('sample-size');

            if (methodSelect) methodSelect.value = config.method;
            if (sampleSizeSelect) sampleSizeSelect.value = config.sampleSize;
            if (methodSelect) this.updateCoordinatorControlsVisibility(methodSelect.value);

            // 顯示配置訊息
            this.uiManager.showNotification(
                `⚡ 快速預測\n${config.description}`,
                'info'
            );

            // 執行預測
            await this.runPrediction();

        } catch (error) {
            this.uiManager.showNotification('快速預測失敗: ' + error.message, 'error');
            console.error(error);
        } finally {
            this.setButtonLoading(quickPredictBtn, false);
        }
    }

    async updateDataSummary() {
        const stats = await this.statisticsService.getDataStats(this.currentLotteryType);
        this.uiManager.updateDataSummary(stats, this.currentLotteryType);

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
            const isActive = this.currentLotteryType === type ? 'active' : '';

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
                this.currentLotteryType = type;

                // 更新按鈕狀態
                grid.querySelectorAll('.lottery-type-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');

                // 更新顯示
                this.handleLotteryTypeChange();
            });
        });
    }

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
     * 更新預測方法說明卡片
     */
    updateMethodDescription(method) {
        console.log('🔄 updateMethodDescription called with method:', method);

        const card = document.getElementById('method-description-card');
        const icon = document.getElementById('method-icon');
        const title = document.getElementById('method-title');
        const description = document.getElementById('method-description');

        if (!card || !title || !description) {
            console.warn('⚠️ Some elements for method description card are missing, but continuing...');
            // We proceed if we have the core title and description
        }

        // 定義所有預測方法的說明
        const methodDescriptions = {
            'frequency': {
                icon: '📊',
                title: '頻率分析',
                desc: '分析歷史開獎號碼的出現頻率，選擇高頻號碼作為預測依據。',
                logic: [
                    '統計每個號碼在歷史記錄中的出現次數',
                    '計算出現頻率並排序',
                    '選擇頻率最高的號碼組合'
                ]
            },
            'trend': {
                icon: '📈',
                title: '趨勢分析',
                desc: '追蹤號碼的出現趨勢，識別上升或下降的模式。',
                logic: [
                    '分析近期號碼的出現趨勢',
                    '計算趨勢斜率和動量',
                    '選擇趨勢向上的號碼'
                ]
            },
            'bayesian': {
                icon: '🎲',
                title: '貝葉斯機率',
                desc: '基於貝葉斯定理，計算條件機率來預測號碼。',
                logic: [
                    '計算先驗機率（歷史頻率）',
                    '根據最近開獎更新後驗機率',
                    '選擇後驗機率最高的號碼'
                ]
            },
            'montecarlo': {
                icon: '🎯',
                title: '蒙地卡羅模擬',
                desc: '使用隨機模擬方法，產生大量可能組合並評估。',
                logic: [
                    '基於歷史數據生成機率分布',
                    '進行 10000+ 次隨機模擬',
                    '選擇出現頻率最高的組合'
                ]
            },
            'markov': {
                icon: '🔗',
                title: '馬可夫鏈',
                desc: '基於狀態轉移機率，預測下一期號碼。',
                logic: [
                    '建立號碼間的轉移機率矩陣',
                    '計算從當前狀態到下一狀態的機率',
                    '選擇轉移機率最高的號碼'
                ]
            },
            'deviation': {
                icon: '📉',
                title: '偏差追蹤',
                desc: '追蹤號碼的理論頻率與實際頻率的偏差。',
                logic: [
                    '計算每個號碼的理論出現頻率',
                    '比較實際頻率與理論頻率的差距',
                    '選擇負偏差（冷門）號碼進行回歸'
                ]
            },
            'ensemble_weighted': {
                icon: '🎯',
                title: '集成預測 (Ensemble)',
                desc: '結合多種策略的加權平均，提高預測穩定性。',
                logic: [
                    '同時運行 8+ 種核心策略',
                    '根據歷史表現分配權重',
                    '加權平均所有策略的預測結果'
                ]
            },
            'ensemble_combined': {
                icon: '⭐',
                title: '綜合集成 (最強)',
                desc: '結合統計、機器學習和民間策略的綜合預測。',
                logic: [
                    '融合 15+ 種不同類型的策略',
                    '使用動態權重調整機制',
                    '多層投票決策選出最優組合'
                ]
            },
            'ensemble_advanced': {
                icon: '🚀',
                title: '進階集成 (Boosting+關聯+特徵)',
                desc: '使用 Boosting、號碼關聯性和特徵加權的進階集成。',
                logic: [
                    'Boosting：迭代加強弱預測器',
                    '號碼關聯性：分析號碼間的共現模式',
                    '特徵加權：根據多維特徵動態調整'
                ]
            },
            'ml_forest': {
                icon: '🌲',
                title: '隨機森林 (Random Forest)',
                desc: '使用隨機森林機器學習算法進行預測。',
                logic: [
                    '構建多棵決策樹組成森林',
                    '每棵樹使用不同的特徵子集',
                    '投票決定最終預測結果'
                ]
            },
            'ml_genetic': {
                icon: '🧬',
                title: '遺傳優化 (Genetic)',
                desc: '使用遺傳算法優化號碼組合。',
                logic: [
                    '生成初始號碼組合種群',
                    '通過選擇、交叉、突變進化',
                    '適應度函數評估並保留最優解'
                ]
            },
            'collaborative_hybrid': {
                icon: '🤝',
                title: '混合協作模式',
                desc: '多個預測引擎協作，互相驗證和修正。',
                logic: [
                    '多個獨立引擎並行預測',
                    '交叉驗證並修正異常結果',
                    '協商決定最終預測組合'
                ]
            },
            'auto_optimize': {
                icon: '🤖',
                title: '智能自動優化',
                desc: '使用遺傳算法自動優化策略參數。',
                logic: [
                    '自動調整所有策略的權重參數',
                    '基於歷史數據進行回測驗證',
                    '迭代優化至最佳配置'
                ]
            },
            'backend_optimized': {
                icon: '🚀',
                title: '後端優化預測',
                desc: '使用後端計算資源進行深度優化（目標 10% 成功率）。',
                logic: [
                    '後端大規模並行計算',
                    '深度優化算法（30 代種群 50）',
                    '持久化最佳配置並應用'
                ]
            },
            'ai_prophet': {
                icon: '🔮',
                title: 'Prophet 時間序列',
                desc: 'Facebook 開源的時間序列預測模型。',
                logic: [
                    '分解趨勢、季節性、節假日效應',
                    '自動檢測變點（changepoints）',
                    '基於加法模型進行預測'
                ]
            },
            'ai_xgboost': {
                icon: '⚡',
                title: 'XGBoost 梯度提升',
                desc: '強大的梯度提升決策樹算法。',
                logic: [
                    '構建多個弱學習器（決策樹）',
                    '梯度下降優化殘差',
                    '正則化防止過擬合'
                ]
            },
            'ai_autogluon': {
                icon: '🤖',
                title: 'AutoGluon AutoML',
                desc: '自動機器學習框架，自動選擇最佳模型。',
                logic: [
                    '自動嘗試多種模型（XGBoost、CatBoost 等）',
                    '自動超參數調優',
                    '集成多個最佳模型'
                ]
            },
            'ai_lstm': {
                icon: '🧠',
                title: 'LSTM 神經網絡',
                desc: '長短期記憶神經網絡，擅長序列預測。',
                logic: [
                    '學習歷史序列的長期依賴關係',
                    '記憶門控制信息流動',
                    '輸出門生成預測結果'
                ]
            },
            'coordinator': {
                icon: '🧭',
                title: 'Coordinator (RSM 加權)',
                desc: '多代理評分聚合，權重來自 RSM 滾動表現。',
                logic: [
                    '多策略代理對全號碼打分',
                    '以 RSM 視窗 edge 作為動態權重',
                    '聚合排序後切分多注'
                ]
            },
            'coordinator_direct': {
                icon: '🧭',
                title: 'Coordinator Direct',
                desc: '直接按聚合排序切分注單，重視全域覆蓋。',
                logic: [
                    '全號碼加權聚合',
                    '按排名切分各注',
                    '偏向穩定、低重疊'
                ]
            },
            'coordinator_hybrid': {
                icon: '🧭',
                title: 'Coordinator Hybrid',
                desc: '先縮小候選池，再由代理挑選，重視局部強信號。',
                logic: [
                    'Coordinator 先定候選池',
                    '各代理在池中選號',
                    '訊號更集中但波動略高'
                ]
            },
            'odd_even': {
                icon: '⚖️',
                title: '奇偶比例',
                desc: '根據奇數偶數的黃金比例進行預測。',
                logic: [
                    '分析歷史奇偶數比例分布',
                    '選擇接近 3:3 或 4:2 的組合',
                    '平衡奇偶數分布'
                ]
            },
            'zone_balance': {
                icon: '📍',
                title: '區間平衡',
                desc: '平衡不同號碼區間的分布。',
                logic: [
                    '將號碼範圍分為 3 個區間',
                    '每個區間選擇 2 個號碼',
                    '確保區間均勻分布'
                ]
            },
            'hot_cold': {
                icon: '🔥',
                title: '冷熱號混合',
                desc: '結合熱門號碼和冷門號碼的平衡策略。',
                logic: [
                    '識別最近 10 期的熱號',
                    '識別長期未出現的冷號',
                    '按 4:2 或 3:3 比例混合'
                ]
            },
            'sum_range': {
                icon: '➕',
                title: '和值+AC值',
                desc: '基於號碼總和與 AC 值（算術複雜度）的預測。',
                logic: [
                    '計算歷史和值的分布範圍',
                    '計算 AC 值評估號碼離散度',
                    '選擇和值與 AC 值在正常範圍的組合'
                ]
            },
            'number_pairs': {
                icon: '👥',
                title: '連號配對',
                desc: '分析連續號碼出現的模式。',
                logic: [
                    '統計連號（如 12-13）出現頻率',
                    '識別常見的號碼對',
                    '優先選擇高頻連號組合'
                ]
            },
            'statistical': {
                icon: '📐',
                title: '多維統計',
                desc: '綜合多種統計指標的多維分析。',
                logic: [
                    '計算均值、標準差、偏度、峰度',
                    '分析號碼分布的多維特徵',
                    '選擇統計特徵最優的組合'
                ]
            }
        };

        // 獲取對應方法的說明
        const info = methodDescriptions[method] || {
            icon: '❓',
            title: '未知方法',
            desc: '此方法暫無說明。',
            logic: ['暫無詳細邏輯說明']
        };

        // Lucide Icon Mapping for methods
        const iconMapping = {
            'frequency': 'bar-chart-2',
            'trend': 'trending-up',
            'bayesian': 'target',
            'montecarlo': 'dice-5',
            'markov': 'git-branch',
            'deviation': 'activity',
            'ensemble_weighted': 'layers',
            'ensemble_combined': 'zap',
            'auto_optimize': 'cpu',
            'backend_optimized': 'server',
            'ai_prophet': 'sparkles',
            'ai_xgboost': 'fast-forward',
            'ai_autogluon': 'bot',
            'ai_lstm': 'brain',
            'ai_transformer': 'star',
            'ai_bayesian_ensemble': 'crosshair',
            'ai_maml': 'dna',
            'coordinator': 'compass',
            'coordinator_direct': 'navigation',
            'coordinator_hybrid': 'map',
            'odd_even': 'scale',
            'zone_balance': 'map-pin',
            'hot_cold': 'flame',
            'sum_range': 'plus-circle',
            'number_pairs': 'users',
            'statistical': 'ruler'
        };

        const lucideName = iconMapping[method] || 'help-circle';

        // 更新卡片內容
        if (icon) {
            icon.innerHTML = `<i data-lucide="${lucideName}" style="width: 32px; height: 32px; color: var(--color-primary);"></i>`;
        }
        if (title) title.textContent = info.title;

        // 構建描述 HTML
        const logicList = info.logic.map(item => `<li>${item}</li>`).join('');
        if (description) {
            description.innerHTML = `
                <p style="margin-bottom: var(--space-sm); font-size: 0.95rem; color: var(--color-text);">${info.desc}</p>
                <div class="logic-panel">
                    <strong style="display: block; margin-bottom: var(--space-xs); color: var(--color-primary); font-size: 0.9rem;">
                        <i data-lucide="shield-check" class="icon-sm" style="display: inline-block; vertical-align: middle;"></i>
                        📌 策略邏輯分析：
                    </strong>
                    <ul class="logic-list">
                        ${logicList}
                    </ul>
                </div>
            `;
            // Re-initialize Lucide icons
            if (window.lucide) {
                window.lucide.createIcons();
            }
        }
    }

    async runSimulation() {
        return this.simulationHandler.runSimulation();
    }

    async getSimulationAllData() {
        let allData = await this.dataProcessor.getDataSmart(this.currentLotteryType, 'all');

        if (this.currentLotteryType) {
            allData = allData.filter(d => d.lotteryType === this.currentLotteryType);
        }

        if (allData.length < 50) {
            throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
        }

        return allData;
    }

    getSimulationTargetsByYear(allData, targetYear) {
        const testTargets = allData.filter(draw => this.getYearFromDate(draw.date) === targetYear);

        if (testTargets.length === 0) {
            const years = allData.map(d => this.getYearFromDate(d.date)).filter(Boolean);
            const uniqueYears = Array.from(new Set(years)).sort();
            throw new Error(`該年份 (${targetYear}) 無開獎資料。可用年份: ${uniqueYears.join(', ')}`);
        }

        testTargets.sort((a, b) => a.date.replace(/\//g, '-').localeCompare(b.date.replace(/\//g, '-')));
        return testTargets;
    }

    async runSimulationByTargets(method, allData, testTargets) {
        const results = [];
        let successCount = 0;

        for (let idx = 0; idx < testTargets.length; idx++) {
            const targetDraw = testTargets[idx];
            console.log(`\n🔄 ========== 模擬測試階段：第 ${idx + 1}/${testTargets.length} 期 ==========`);

            const simulationResult = await this.runSingleSimulationTarget(method, allData, targetDraw);
            if (!simulationResult) {
                continue;
            }

            results.push(simulationResult.result);
            if (simulationResult.result.isSuccess) {
                successCount++;
            }
        }

        return { results, successCount };
    }

    async runSingleSimulationTarget(method, allData, targetDraw) {
        const targetDate = targetDraw.date.replace(/\//g, '-');
        const trainingData = allData.filter(d => d.date.replace(/\//g, '-') < targetDate);

        if (trainingData.length < 30) {
            console.warn(`期數 ${targetDraw.draw} 訓練資料不足 (${trainingData.length} 期)，跳過`);
            return null;
        }

        const sortedTraining = [...trainingData].sort((a, b) => {
            const drawA = parseInt((a.draw || '').toString().replace(/\D/g, ''), 10) || 0;
            const drawB = parseInt((b.draw || '').toString().replace(/\D/g, ''), 10) || 0;
            return drawA - drawB;
        });

        console.log(`🔍 目標期數 ${targetDraw.draw} (${targetDate}): 訓練資料 ${trainingData.length} 期`);
        console.log(`   期數範圍: ${sortedTraining[0]?.draw} ~ ${sortedTraining[sortedTraining.length - 1]?.draw}`);
        console.log(`   日期範圍: ${sortedTraining[0]?.date} ~ ${sortedTraining[sortedTraining.length - 1]?.date}`);

        const predictionResult = await this.predictionEngine.predictWithData(
            method,
            trainingData,
            targetDraw.lotteryType,
            true
        );

        const prediction = {
            numbers: predictionResult.numbers,
            special: predictionResult.special
        };

        console.log(`📊 目標期數 ${targetDraw.draw}: 使用 ${trainingData.length} 期資料預測`);

        const { hits, isSuccess } = this.evaluatePrediction(
            targetDraw.numbers,
            prediction.numbers,
            targetDraw.lotteryType,
            targetDraw.special
        );

        try {
            await apiClient.recordPerformanceHit(hits >= 3 ? 1 : 0);
            this.uiManager.updateWaterline();
        } catch (e) {
            console.warn('錄入水線績效失敗:', e);
        }

        const refRange = sortedTraining.length > 0
            ? `${sortedTraining[0].draw} - ${sortedTraining[sortedTraining.length - 1].draw} (共${trainingData.length}期)`
            : '-';

        return {
            result: {
                draw: targetDraw.draw,
                date: targetDraw.date,
                predicted: prediction.numbers,
                predictedSpecial: prediction.special || null,
                actual: targetDraw.numbers,
                actualSpecial: targetDraw.special || null,
                hits,
                isSuccess,
                refRange
            }
        };
    }

    async runCollaborativeSimulation() {
        return this.simulationHandler.runCollaborativeSimulation();
    }




    async runRollingTest(allData, strategy, params, testTargets) {
        // 暫時應用參數
        const originalWeights = { ...strategy.weights };
        strategy.weights = params;

        let successCount = 0;

        for (const targetDraw of testTargets) {
            const targetDate = targetDraw.date.replace(/\//g, '-');
            const trainingData = allData.filter(d => {
                const drawDate = d.date.replace(/\//g, '-');
                return drawDate < targetDate;
            });

            if (trainingData.length < 30) continue;

            // 執行預測
            const prediction = await strategy.predict(trainingData);

            // 驗證
            const hits = targetDraw.numbers.filter(n => prediction.numbers.includes(n));
            if (hits.length >= 3) successCount++;
        }

        // 恢復參數 (雖然外部迴圈可能會再次覆蓋，但保持乾淨是好的)
        strategy.weights = originalWeights;

        return {
            rate: (successCount / testTargets.length) * 100
        };
    }

    displaySimulationResults(results, successCount) {
        const resultsDiv = document.getElementById('simulation-results');
        const rateSpan = document.getElementById('simulation-rate');
        const tbody = document.querySelector('#simulation-table tbody');

        if (resultsDiv && rateSpan && tbody) {
            const rate = results.length > 0 ? Math.round((successCount / results.length) * 100) : 0;
            rateSpan.textContent = rate;

            // === 計算命中率分佈 ===
            const hitDistribution = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
            results.forEach(r => {
                if (hitDistribution.hasOwnProperty(r.hits)) {
                    hitDistribution[r.hits]++;
                }
            });

            // === 理論機率（大樂透 C(6,k) * C(43, 6-k) / C(49, 6)）===
            const theoreticalProb = {
                0: 43.596,  // 一個都沒中
                1: 41.302,  // 中1個
                2: 13.238,  // 中2個
                3: 1.765,   // 中3個（普獎）
                4: 0.097,   // 中4個
                5: 0.002,   // 中5個
                6: 0.0000072 // 全中（頭獎）
            };

            // === 計算實際機率 ===
            const actualProb = {};
            Object.keys(hitDistribution).forEach(key => {
                actualProb[key] = results.length > 0
                    ? ((hitDistribution[key] / results.length) * 100).toFixed(2)
                    : '0.00';
            });

            // === 在表格前插入統計面板 ===
            const existingStats = document.getElementById('simulation-stats-panel');
            if (existingStats) {
                existingStats.remove();
            }

            const statsPanel = document.createElement('div');
            statsPanel.id = 'simulation-stats-panel';
            statsPanel.className = 'simulation-stats-panel';
            statsPanel.innerHTML = `
                <h3>📊 詳細統計分析</h3>
                <div class="stats-summary">
                    <div class="stat-card">
                        <div class="stat-label">總測試期數</div>
                        <div class="stat-value">${results.length}</div>
                    </div>
                    <div class="stat-card success">
                        <div class="stat-label">成功期數（≥3個）</div>
                        <div class="stat-value">${successCount}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">成功率</div>
                        <div class="stat-value">${rate}%</div>
                    </div>
                    <div class="stat-card highlight">
                        <div class="stat-label">vs 純隨機</div>
                        <div class="stat-value">${(rate / 1.765).toFixed(1)}x</div>
                        <div class="stat-note">（理論值 1.765%）</div>
                    </div>
                </div>

                <h4>🎯 命中率分佈對比</h4>
                <div class="hit-distribution">
                    ${Object.keys(hitDistribution).map(hits => {
                const count = hitDistribution[hits];
                const actualPct = actualProb[hits];
                const theorPct = theoreticalProb[hits];
                const diff = (parseFloat(actualPct) - theorPct).toFixed(2);
                const isHigher = parseFloat(diff) > 0;
                const isBetter = parseInt(hits) >= 3 ? isHigher : !isHigher; // ≥3 希望更高，<3 希望更低

                return `
                            <div class="hit-row ${parseInt(hits) >= 3 ? 'success-zone' : ''}">
                                <div class="hit-label">
                                    <span class="hit-num">${hits} 個</span>
                                    ${parseInt(hits) >= 3 ? '<span class="badge">中獎</span>' : ''}
                                </div>
                                <div class="hit-stats">
                                    <div class="stat-item">
                                        <span class="label">實際:</span>
                                        <span class="value">${count} 期 (${actualPct}%)</span>
                                    </div>
                                    <div class="stat-item">
                                        <span class="label">理論:</span>
                                        <span class="value">${theorPct}%</span>
                                    </div>
                                    <div class="stat-item ${isBetter ? 'better' : 'worse'}">
                                        <span class="label">差異:</span>
                                        <span class="value">${isHigher ? '+' : ''}${diff}%</span>
                                        ${isBetter ? '📈' : '📉'}
                                    </div>
                                </div>
                                <div class="progress-bar">
                                    <div class="progress-actual" style="width: ${Math.min(parseFloat(actualPct) * 2, 100)}%"></div>
                                    <div class="progress-theory" style="left: ${Math.min(theorPct * 2, 100)}%"></div>
                                </div>
                            </div>
                        `;
            }).join('')}
                </div>

                <div class="stats-note">
                    <p><strong>💡 解讀說明：</strong></p>
                    <ul>
                        <li>✅ <strong>「3個」以上</strong>的實際機率 <strong>高於理論</strong> = 表現優於隨機</li>
                        <li>📊 您的系統在「3個」的實際機率是 <strong>${actualProb[3]}%</strong>，理論值是 <strong>1.765%</strong></li>
                        <li>🎯 這表示您的預測系統比純隨機猜測好 <strong>${(rate / 1.765).toFixed(1)} 倍</strong></li>
                        <li>⚠️ 但彩票本質是隨機，即使是最好的系統也無法保證高成功率</li>
                    </ul>
                </div>
            `;

            // 插入到表格前
            const table = document.getElementById('simulation-table');
            if (table && table.parentNode) {
                table.parentNode.insertBefore(statsPanel, table);
            }

            // === 原有的表格顯示（倒序顯示，最新的在上面） ===
            tbody.innerHTML = results.slice().reverse().map(r => `
                <tr class="${r.isSuccess ? 'success-row' : ''}">
                    <td>${r.draw}</td>
                    <td>${r.date}</td>
                    <td>${r.predicted.join(', ')}${r.predictedSpecial ? ' <strong style="color: #e74c3c;">+ ' + r.predictedSpecial + '</strong>' : ''}</td>
                    <td>${r.actual.join(', ')}${r.actualSpecial ? ' <strong style="color: #e74c3c;">+ ' + r.actualSpecial + '</strong>' : ''}</td>
                    <td><span class="hit-badge ${r.hits >= 3 ? 'high-hit' : ''}">${r.hits}</span></td>
                    <td>${r.refRange || '-'}</td>
                    <td>${r.isSuccess ? '✅' : '❌'}</td>
                </tr>
            `).join('');

            resultsDiv.style.display = 'block';
        }
    }

    async runPrediction() {
        return this.predictionHandler.runPrediction();
    }

    /**
     * 生成最新一期的雙注預測（使用全部歷史資料）
     */
    async generateNextPeriodPrediction(allData) {
        return this.predictionHandler.generateNextPeriodPrediction(allData);
    }

    /**
     * 顯示最新一期的雙注預測結果
     */
    displayNextPeriodPrediction(result) {
        // 顯示第一注號碼
        const bet1Container = document.getElementById('next-bet-numbers-1');
        if (bet1Container) {
            bet1Container.innerHTML = result.bet1.numbers
                .map(num => `<div class="predicted-number">${num}</div>`)
                .join('');
        }

        // 顯示第二注號碼
        const bet2Container = document.getElementById('next-bet-numbers-2');
        if (bet2Container) {
            bet2Container.innerHTML = result.bet2.numbers
                .map(num => `<div class="predicted-number">${num}</div>`)
                .join('');
        }

        // 更新信心度
        const bet1ConfidenceEl = document.getElementById('next-bet-confidence-1');
        if (bet1ConfidenceEl) {
            bet1ConfidenceEl.textContent = `${result.bet1.confidence}%`;
        }

        const bet2ConfidenceEl = document.getElementById('next-bet-confidence-2');
        if (bet2ConfidenceEl) {
            bet2ConfidenceEl.textContent = `${result.bet2.confidence}%`;
        }

        // 更新統計資訊
        const strategyCountEl = document.getElementById('next-bet-strategy-count');
        if (strategyCountEl) {
            strategyCountEl.textContent = result.strategyCount;
        }

        const overallConfidenceEl = document.getElementById('next-bet-overall-confidence');
        if (overallConfidenceEl) {
            overallConfidenceEl.textContent = `${result.overallConfidence}%`;
        }

        const basePeriodEl = document.getElementById('next-bet-base-period');
        if (basePeriodEl) {
            basePeriodEl.textContent = result.basePeriod;
        }

        // 生成詳細報告
        const reportEl = document.getElementById('next-bet-report');
        if (reportEl) {
            reportEl.innerHTML = `
                <h4>📊 預測分析</h4>
                <p style="color: #9aa3af; margin: 10px 0;">
                    此預測整合了 ${result.strategyCount} 種策略，基於全部歷史資料進行分析。
                    由於沒有實際開獎資料，這是純粹的預測結果，建議結合其他因素判斷。
                </p>
                <p style="color: #9aa3af; margin: 10px 0;">
                    <strong>參考資料範圍：</strong>${result.basePeriod}
                </p>
                <p style="color: #9aa3af; margin: 10px 0;">
                    <strong>主要策略：</strong>${result.topStrategies.join(', ')}
                </p>
                <div style="background: rgba(255, 193, 7, 0.1); padding: 12px; border-radius: 8px; border-left: 3px solid #ffc107; margin-top: 15px;">
                    <strong style="color: #ffc107;">⚠️ 重要提醒</strong>
                    <p style="color: #9aa3af; margin: 8px 0 0 0; font-size: 0.9em;">
                        此預測僅供參考，樂透本質為隨機事件，無法保證中獎。請理性投注，量力而為。
                    </p>
                </div>
            `;
        }
    }

    /**
     * 雙注優化預測：整合所有策略，選出最佳12個號碼
     */
    async handleDualBetPredict() {
        const dualBetBtn = document.getElementById('dual-bet-predict-btn');
        const sampleSize = document.getElementById('sample-size').value;
        const lotteryType = this.currentLotteryType;

        try {
            this.setButtonLoading(dualBetBtn, true);
            this.uiManager.showNotification('正在執行雙注優化預測，整合所有策略中...', 'info');

            // 所有可用策略列表（包含後端優化策略）
            const strategies = [
                'frequency', 'trend', 'bayesian', 'markov', 'montecarlo', 'deviation',
                'odd_even', 'zone_balance', 'hot_cold', 'sum_range', 'number_pairs',
                'ensemble_weighted', 'ensemble_combined', 'ensemble_advanced',
                'backend_optimized'  // 添加後端優化策略
            ];

            // 收集所有策略的預測結果
            const allResults = [];
            for (const strategy of strategies) {
                try {
                    const result = await this.predictionEngine.predict(strategy, sampleSize, lotteryType, true);
                    allResults.push({
                        strategy,
                        numbers: result.numbers,
                        confidence: result.confidence,
                        method: result.method
                    });
                } catch (err) {
                    console.warn(`策略 ${strategy} 執行失敗:`, err);
                }
            }

            if (allResults.length === 0) {
                throw new Error('無可用策略結果');
            }

            // 統計所有號碼的出現次數和加權分數
            const numberScores = {};
            const lotteryRules = this.getLotteryRulesFromType(lotteryType);
            const minNum = lotteryRules.minNumber || 1;
            const maxNum = lotteryRules.maxNumber || 49;

            for (let i = minNum; i <= maxNum; i++) {
                numberScores[i] = 0;
            }

            allResults.forEach(result => {
                const weight = (result.confidence <= 1 ? result.confidence : result.confidence / 100);
                result.numbers.forEach((num, idx) => {
                    // 排名越前分數越高
                    const rankScore = (6 - idx) / 6;
                    numberScores[num] += weight * rankScore * 10;
                });
            });

            // 選出分數最高的12個號碼
            const sortedNumbers = Object.entries(numberScores)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 12)
                .map(([num]) => parseInt(num));

            // 將12個號碼分成兩注（前6個和後6個）
            const bet1Numbers = sortedNumbers.slice(0, 6).sort((a, b) => a - b);
            const bet2Numbers = sortedNumbers.slice(6, 12).sort((a, b) => a - b);

            // 計算各自的信心度（根據號碼的平均分數）
            const bet1Score = bet1Numbers.reduce((sum, num) => sum + numberScores[num], 0) / 6;
            const bet2Score = bet2Numbers.reduce((sum, num) => sum + numberScores[num], 0) / 6;
            const totalScore = (bet1Score + bet2Score) / 2;

            // 正規化信心度到0-100
            const maxScore = Math.max(...Object.values(numberScores));
            const bet1Confidence = Math.min(95, (bet1Score / maxScore) * 100);
            const bet2Confidence = Math.min(95, (bet2Score / maxScore) * 100);
            const overallConfidence = Math.min(95, (totalScore / maxScore) * 100);

            // 顯示結果
            this.displayDualBetResult({
                bet1: { numbers: bet1Numbers, confidence: bet1Confidence },
                bet2: { numbers: bet2Numbers, confidence: bet2Confidence },
                overall: {
                    confidence: overallConfidence,
                    strategyCount: allResults.length,
                    topStrategies: allResults.slice(0, 5).map(r => r.method || r.strategy)
                }
            });

            this.uiManager.showNotification('雙注優化預測完成！', 'success');
        } catch (error) {
            console.error('雙注預測錯誤:', error);
            this.uiManager.showNotification('雙注預測失敗: ' + error.message, 'error');
        } finally {
            this.setButtonLoading(dualBetBtn, false);
        }
    }

    /**
     * 聰明包牌 - 智能雙注預測
     * 使用選定的預測方法，基於該遊戲的全部歷史數據，生成最有機會的雙注號碼
     */
    async handleSmartDualBetPredict() {
        const smartDualBetBtn = document.getElementById('smart-dual-bet-btn');
        const strategySelect = document.getElementById('dual-bet-strategy-select');
        const selectedStrategy = strategySelect ? strategySelect.value : 'dual_bet_hybrid';
        const lotteryType = this.currentLotteryType || 'BIG_LOTTO';

        try {
            this.setButtonLoading(smartDualBetBtn, true);
            this.uiManager.showNotification(`正在使用「${this.getStrategyDisplayName(selectedStrategy)}」預測雙注號碼...`, 'info');

            // 獲取彩券規則
            const lotteryRules = this.getLotteryRulesFromType(lotteryType);
            const pickCount = lotteryRules.pickCount || 6;
            const minNum = lotteryRules.minNumber || 1;
            const maxNum = lotteryRules.maxNumber || 49;

            // 使用全部數據進行預測
            const sampleSize = 'all';
            let result;

            // 根據策略類型選擇不同的處理方式
            switch (selectedStrategy) {
                case 'optimized_ensemble':
                    result = await this.predictOptimizedEnsemble(lotteryType, pickCount);
                    break;
                case 'dual_bet_hybrid':
                    result = await this.predictDualBetHybrid(lotteryType, sampleSize, pickCount, minNum, maxNum);
                    break;
                case 'hot_cold_split':
                    result = await this.predictHotColdSplit(lotteryType, sampleSize, pickCount, minNum, maxNum);
                    break;
                default:
                    result = await this.predictGenericDualBet(selectedStrategy, lotteryType, sampleSize, pickCount, minNum, maxNum);
                    break;
            }

            // 顯示結果
            this.displaySmartDualBetResult(result);
            this.uiManager.showNotification(`智能雙注預測完成！使用「${result.method}」策略`, 'success');

        } catch (error) {
            console.error('智能雙注預測錯誤:', error);
            this.uiManager.showNotification('智能雙注預測失敗: ' + error.message, 'error');
        } finally {
            this.setButtonLoading(smartDualBetBtn, false);
        }
    }

    /**
     * 優化集成預測 - 調用後端動態權重集成
     */
    async predictOptimizedEnsemble(lotteryType, pickCount) {
        console.log('🏆 正在調用優化集成預測 (動態權重回測)...');

        // 獲取數據範圍（使用全部數據）
        const data = await this.dataProcessor.getDataRange('all', lotteryType);
        if (!data || data.length < 50) {
            throw new Error('數據量不足，優化集成需要至少 50 期');
        }

        // 獲取期號範圍
        const sortedData = [...data].sort((a, b) => parseInt(a.draw) - parseInt(b.draw));
        const startDraw = sortedData[0].draw;
        const endDraw = sortedData[sortedData.length - 1].draw;

        // 調用後端 API
        const response = await fetch(getApiUrl('/api/predict-with-range'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lotteryType: lotteryType,
                modelType: 'optimized_ensemble',
                startDraw: startDraw,
                endDraw: endDraw
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '優化集成預測失敗');
        }

        const result = await response.json();
        console.log('✅ 優化集成預測完成:', result);

        // 返回格式化的雙注結果
        return {
            bet1: result.bet1 || { numbers: result.numbers, confidence: result.confidence },
            bet2: result.bet2 || { numbers: [], confidence: 0 },
            method: '優化集成預測',
            strategy: 'optimized_ensemble',
            report: `使用 ${data.length} 期數據進行動態權重回測集成`,
            strategyWeights: result.strategy_weights
        };
    }

    /**
     * 雙注混合策略 - 綜合多種方法產生最佳雙注
     */
    async predictDualBetHybrid(lotteryType, sampleSize, pickCount, minNum, maxNum) {
        // 使用多種高穩定性策略
        const strategies = ['ensemble_combined', 'bayesian', 'statistical', 'hot_cold'];
        const numberScores = {};

        for (let i = minNum; i <= maxNum; i++) {
            numberScores[i] = 0;
        }

        let successCount = 0;
        for (const strategy of strategies) {
            try {
                console.log(`🔍 [雙注混合] 正在執行策略: ${strategy}`);
                const result = await this.predictionEngine.predict(strategy, sampleSize, lotteryType, true);
                console.log(`✅ [雙注混合] 策略 ${strategy} 返回:`, result.numbers, '信心度:', result.confidence);
                if (result && result.numbers && result.numbers.length > 0) {
                    const weight = (result.confidence <= 1 ? result.confidence : result.confidence / 100);
                    result.numbers.forEach((num, idx) => {
                        const rankScore = (pickCount - idx) / pickCount;
                        numberScores[num] += rankScore * weight * 10;
                    });
                    // 注意：不再使用 probabilities，因為後端返回的是原始分數而非正規化機率
                    // 這會導致不在預測結果中的號碼獲得過高分數
                    successCount++;
                }
            } catch (err) {
                console.warn(`❌ [雙注混合] 策略 ${strategy} 執行失敗:`, err);
            }
        }

        if (successCount === 0) {
            throw new Error('所有策略執行失敗');
        }

        // 選出最高分的 12 個號碼
        const sortedNumbers = Object.entries(numberScores)
            .filter(([, score]) => score > 0)
            .sort((a, b) => b[1] - a[1])
            .slice(0, pickCount * 2)
            .map(([num]) => parseInt(num));

        // 補充不足的號碼
        this.fillMissingNumbers(sortedNumbers, pickCount * 2, minNum, maxNum);

        const bet1Numbers = sortedNumbers.slice(0, pickCount).sort((a, b) => a - b);
        const bet2Numbers = sortedNumbers.slice(pickCount, pickCount * 2).sort((a, b) => a - b);

        console.log(`✅ [雙注混合] 綜合 ${successCount} 種策略 - 第一注:`, bet1Numbers, '第二注:', bet2Numbers);

        const bet1Score = bet1Numbers.reduce((sum, num) => sum + numberScores[num], 0) / pickCount;
        const bet2Score = bet2Numbers.reduce((sum, num) => sum + numberScores[num], 0) / pickCount;
        const maxScore = Math.max(...Object.values(numberScores).filter(s => s > 0), 1);

        return {
            bet1: { numbers: bet1Numbers, confidence: Math.min(95, (bet1Score / maxScore) * 100) },
            bet2: { numbers: bet2Numbers, confidence: Math.min(90, (bet2Score / maxScore) * 100) },
            method: '雙注混合策略',
            strategy: 'dual_bet_hybrid',
            report: `綜合 ${successCount} 種策略 (${strategies.join(', ')}) 的投票結果`
        };
    }

    /**
     * 熱冷分離策略 - 第一注熱號，第二注冷號
     */
    async predictHotColdSplit(lotteryType, sampleSize, pickCount, minNum, maxNum) {
        // 獲取頻率統計
        const data = await this.dataProcessor.getDataRange('all', lotteryType);
        if (!data || data.length < 10) {
            throw new Error('數據量不足，至少需要 10 期');
        }

        // 計算頻率
        const frequency = {};
        for (let i = minNum; i <= maxNum; i++) {
            frequency[i] = 0;
        }
        data.forEach(draw => {
            if (draw.numbers) {
                draw.numbers.forEach(num => {
                    frequency[num] = (frequency[num] || 0) + 1;
                });
            }
        });

        // 排序：熱門號碼（頻率高）和冷門號碼（頻率低）
        const sortedByFreq = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .map(([num]) => parseInt(num));

        // 第一注：取最熱門的號碼
        const hotNumbers = sortedByFreq.slice(0, pickCount).sort((a, b) => a - b);

        // 第二注：取最冷門的號碼（從尾部取）
        const coldNumbers = sortedByFreq.slice(-pickCount).sort((a, b) => a - b);

        // 計算信心度
        const maxFreq = Math.max(...Object.values(frequency));
        const hotFreqSum = hotNumbers.reduce((sum, num) => sum + frequency[num], 0);
        const coldFreqSum = coldNumbers.reduce((sum, num) => sum + frequency[num], 0);

        return {
            bet1: {
                numbers: hotNumbers,
                confidence: Math.min(92, (hotFreqSum / (maxFreq * pickCount)) * 100)
            },
            bet2: {
                numbers: coldNumbers,
                confidence: Math.min(85, 50 + (1 - coldFreqSum / (maxFreq * pickCount)) * 35)
            },
            method: '熱冷分離策略',
            strategy: 'hot_cold_split',
            report: `第一注選用歷史頻率最高的 ${pickCount} 個熱門號碼，第二注選用頻率最低的 ${pickCount} 個冷門號碼（均值回歸理論）`
        };
    }

    /**
     * 通用雙注預測 - 使用單一策略
     */
    async predictGenericDualBet(strategy, lotteryType, sampleSize, pickCount, minNum, maxNum) {
        const numberScores = {};
        for (let i = minNum; i <= maxNum; i++) {
            numberScores[i] = 0;
        }

        const iterations = 3;
        let successCount = 0;
        let methodName = '';

        for (let iter = 0; iter < iterations; iter++) {
            try {
                const result = await this.predictionEngine.predict(strategy, sampleSize, lotteryType, true);
                if (result && result.numbers && result.numbers.length > 0) {
                    methodName = result.method || this.getStrategyDisplayName(strategy);
                    result.numbers.forEach((num, idx) => {
                        const rankScore = (pickCount - idx) / pickCount;
                        const confidenceWeight = (result.confidence <= 1 ? result.confidence : result.confidence / 100);
                        numberScores[num] += rankScore * confidenceWeight * 10;
                    });
                    if (result.probabilities) {
                        Object.entries(result.probabilities).forEach(([num, prob]) => {
                            numberScores[parseInt(num)] += prob * 5;
                        });
                    }
                    successCount++;
                }
            } catch (err) {
                console.warn(`策略執行第 ${iter + 1} 次失敗:`, err);
            }
        }

        if (successCount === 0) {
            throw new Error('預測策略執行失敗，請檢查數據或更換策略');
        }

        const sortedNumbers = Object.entries(numberScores)
            .filter(([, score]) => score > 0)
            .sort((a, b) => b[1] - a[1])
            .slice(0, pickCount * 2)
            .map(([num]) => parseInt(num));

        this.fillMissingNumbers(sortedNumbers, pickCount * 2, minNum, maxNum);

        const bet1Numbers = sortedNumbers.slice(0, pickCount).sort((a, b) => a - b);
        const bet2Numbers = sortedNumbers.slice(pickCount, pickCount * 2).sort((a, b) => a - b);

        const bet1Score = bet1Numbers.reduce((sum, num) => sum + numberScores[num], 0) / pickCount;
        const bet2Score = bet2Numbers.reduce((sum, num) => sum + numberScores[num], 0) / pickCount;
        const maxScore = Math.max(...Object.values(numberScores).filter(s => s > 0), 1);

        return {
            bet1: { numbers: bet1Numbers, confidence: Math.min(95, (bet1Score / maxScore) * 100) },
            bet2: { numbers: bet2Numbers, confidence: Math.min(90, (bet2Score / maxScore) * 100) },
            method: methodName,
            strategy: strategy
        };
    }

    /**
     * 補充不足的號碼
     */
    fillMissingNumbers(numbers, targetCount, minNum, maxNum) {
        if (numbers.length >= targetCount) return;
        const usedNums = new Set(numbers);
        for (let i = minNum; i <= maxNum && numbers.length < targetCount; i++) {
            if (!usedNums.has(i)) {
                numbers.push(i);
            }
        }
    }

    /**
     * 獲取策略顯示名稱
     */
    getStrategyDisplayName(strategy) {
        const strategyNames = {
            'frequency': '頻率分析',
            'trend': '趨勢回歸',
            'bayesian': '貝葉斯推論',
            'markov': '馬可夫鏈',
            'montecarlo': '蒙地卡羅模擬',
            'deviation': '偏差追蹤',
            'backend_optimized': '後端優化策略',
            'prophet': 'Prophet時序預測',
            'xgboost': 'XGBoost機器學習',
            'ai_prophet': 'Prophet時序預測',
            'ai_xgboost': 'XGBoost機器學習',
            'coordinator': 'Coordinator (RSM加權)',
            'coordinator_direct': 'Coordinator Direct',
            'coordinator_hybrid': 'Coordinator Hybrid',
            'ensemble_weighted': '加權集成',
            'ensemble_combined': '綜合集成',
            'ensemble_advanced': '進階集成',
            // 雙注專用策略
            'optimized_ensemble': '🏆 優化集成預測',
            'dual_bet_hybrid': '🎯 雙注混合策略',
            'hot_cold_split': '🔥❄️ 熱冷分離策略',
            'collaborative_hybrid': '🤝 協作混合模式',
            'statistical': '多維統計分析',
            'ml_forest': '隨機森林',
            'hot_cold': '冷熱號混合'
        };
        return strategyNames[strategy] || strategy;
    }

    /**
     * 顯示智能雙注預測結果
     */
    displaySmartDualBetResult(result) {
        // 顯示結果區域
        const resultsDiv = document.getElementById('smart-dual-bet-results');
        if (resultsDiv) {
            resultsDiv.style.display = 'block';
        }

        // 第一注號碼 + 特別號
        const bet1Container = document.getElementById('smart-dual-bet-numbers-1');
        if (bet1Container) {
            let html = result.bet1.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
            // 添加特別號（如果有）
            if (result.bet1.special) {
                html += `<div class="predicted-number special-number" style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border: 2px solid #FF8C00;" title="特別號">★${result.bet1.special}</div>`;
            }
            bet1Container.innerHTML = html;
        }

        // 第二注號碼 + 特別號
        const bet2Container = document.getElementById('smart-dual-bet-numbers-2');
        if (bet2Container) {
            let html = result.bet2.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
            // 添加特別號（如果有）
            if (result.bet2.special) {
                html += `<div class="predicted-number special-number" style="background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border: 2px solid #FF8C00;" title="特別號">★${result.bet2.special}</div>`;
            }
            bet2Container.innerHTML = html;
        }

        // 信心度
        const conf1 = document.getElementById('smart-dual-bet-confidence-1');
        const conf2 = document.getElementById('smart-dual-bet-confidence-2');
        if (conf1) conf1.textContent = `${result.bet1.confidence.toFixed(1)}%`;
        if (conf2) conf2.textContent = `${result.bet2.confidence.toFixed(1)}%`;

        // 使用的方法說明
        const methodDiv = document.getElementById('smart-dual-bet-method');
        if (methodDiv) {
            const specialNote = (result.bet1.special || result.bet2.special) ? ' (含特別號預測)' : '';
            methodDiv.innerHTML = `使用策略：<strong>${result.method}</strong>${specialNote} | 基於全部歷史數據分析`;
        }

        // 滾動到結果區域
        if (resultsDiv) {
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    displayDualBetResult(result) {
        // 顯示雙注結果（保持單注結果可見）
        const dualResult = document.getElementById('dual-bet-results');

        if (dualResult) dualResult.style.display = 'block';

        // 第一注號碼
        const bet1Container = document.getElementById('dual-bet-numbers-1');
        if (bet1Container) {
            bet1Container.innerHTML = result.bet1.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // 第二注號碼
        const bet2Container = document.getElementById('dual-bet-numbers-2');
        if (bet2Container) {
            bet2Container.innerHTML = result.bet2.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // 信心度
        const conf1 = document.getElementById('dual-bet-confidence-1');
        const conf2 = document.getElementById('dual-bet-confidence-2');
        const confOverall = document.getElementById('dual-bet-overall-confidence');
        const stratCount = document.getElementById('dual-bet-strategy-count');

        if (conf1) conf1.textContent = `${result.bet1.confidence.toFixed(1)}%`;
        if (conf2) conf2.textContent = `${result.bet2.confidence.toFixed(1)}%`;
        if (confOverall) confOverall.textContent = `${result.overall.confidence.toFixed(1)}%`;
        if (stratCount) stratCount.textContent = result.overall.strategyCount;

        // 詳細報告
        const report = document.getElementById('dual-bet-report');
        if (report) {
            report.innerHTML = `
                <h4>策略整合分析</h4>
                <p><strong>參與策略：</strong>${result.overall.strategyCount} 個</p>
                <p><strong>前5大貢獻策略：</strong></p>
                <ul>
                    ${result.overall.topStrategies.map(s => `<li>${s}</li>`).join('')}
                </ul>
                <p><strong>建議：</strong>第一注為最高信心組合，第二注為次優補充。兩注覆蓋12個最佳候選號碼，提升整體中獎機會。</p>
            `;
        }
    }

    displayPredictionResult(result) {
        // 顯示單注結果，隱藏雙注結果
        const singleResult = document.getElementById('prediction-results');
        const dualResult = document.getElementById('dual-bet-results');

        if (singleResult) singleResult.style.display = 'block';
        if (dualResult) dualResult.style.display = 'none';

        const container = document.getElementById('predicted-numbers');
        if (container) {
            container.innerHTML = result.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // Apply lottery-type-specific styling
        const predictionResults = document.querySelector('.prediction-results');
        if (predictionResults && this.currentLotteryType) {
            predictionResults.setAttribute('data-lottery-type', this.currentLotteryType);
        }

        const confidenceVal = document.getElementById('confidence-value');
        const confidenceFill = document.getElementById('confidence-fill');

        // 顯示信心度
        let confidenceDisplay = result.confidence;
        // 如果是小數 (0.82)，轉換為百分比 (82)
        if (confidenceDisplay <= 1) {
            confidenceDisplay = (confidenceDisplay * 100).toFixed(1);
        }

        if (confidenceVal) confidenceVal.textContent = `${confidenceDisplay}%`;
        if (confidenceFill) confidenceFill.style.width = `${Math.min(100, confidenceDisplay)}%`;

        // 顯示分析報告和方法名稱
        const report = document.getElementById('prediction-report');
        if (report) {
            let methodInfo = '';
            if (result.method) {
                methodInfo = `<strong>使用策略：</strong> ${result.method}<br>`;
            }

            // 如果有詳細信息 (集成預測會返回 details)
            let detailsInfo = '';
            if (result.details && Array.isArray(result.details)) {
                detailsInfo = `<br><div style="font-size: 0.9em; margin-top: 8px; color: #aaa;">
                    <strong>策略詳情：</strong><br>
                    ${result.details.join('<br>')}
                </div>`;
            }

            report.innerHTML = `${methodInfo}${result.report || '分析完成'}${detailsInfo}`;
        }
    }

    async displayHistory() {
        let data;

        // 從 IndexedDB 載入數據（如果啟用）
        if (this.dataProcessor.useIndexedDB && this.indexedDBManager.db) {
            if (this.currentLotteryType) {
                data = await this.indexedDBManager.loadDataByType(this.currentLotteryType);
            } else {
                data = await this.indexedDBManager.loadAllData();
            }
        } else {
            data = this.dataProcessor.getData();

            // 根據選擇的彩券類型篩選數據
            if (this.currentLotteryType) {
                data = data.filter(draw => draw.lotteryType === this.currentLotteryType);
            }
        }

        this.uiManager.updateHistoryTable(data, this.currentPage, this.itemsPerPage);
        this.uiManager.updatePagination(data.length, this.currentPage, this.itemsPerPage, (page) => {
            this.currentPage = page;
            this.displayHistory();
        });
    }
}
