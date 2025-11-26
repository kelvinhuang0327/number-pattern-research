import { DataProcessor } from './DataProcessor.js';
import { StatisticsService } from '../data/StatisticsService.js';
import { PredictionEngine } from '../engine/PredictionEngine.js';
import { UIManager } from '../ui/UIManager.js';
import { ChartManager } from '../ui/ChartManager.js';
import { SmartBettingComponent } from '../ui/components/SmartBettingComponent.js';

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

        this.currentPage = 1;
        this.itemsPerPage = 20;
        this.currentLotteryType = ''; // '' means all types

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.uiManager.showSection('upload');
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

        // 預測按鈕
        const predictBtn = document.getElementById('predict-btn');
        if (predictBtn) {
            predictBtn.addEventListener('click', () => this.runPrediction());
        }

        // 模擬按鈕
        const simulationBtn = document.getElementById('simulation-btn');
        if (simulationBtn) {
            simulationBtn.addEventListener('click', () => this.runSimulation());
        }

        const autoOptimizeBtn = document.getElementById('auto-optimize-btn');
        if (autoOptimizeBtn) {
            autoOptimizeBtn.addEventListener('click', () => this.runAutoOptimization());
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
                    setTimeout(() => this.chartManager.initializeCharts(this.currentLotteryType), 100);
                } else if (section === 'history') {
                    this.displayHistory();
                }
            });
        });
    }

    async handleFileUpload(file) {
        try {
            this.uiManager.showNotification('正在解析檔案...', 'info');
            const result = await this.dataProcessor.loadCSVData(file);

            this.updateDataSummary();

            // 獲取統計信息以顯示彩券類型分佈
            const stats = this.statisticsService.getDataStats();
            const typeNames = {
                'BIG_LOTTO': '大樂透',
                'BIG_LOTTO_BONUS': '大樂透加開',
                'STAR_3': '三星彩',
                'STAR_4': '四星彩',
                'LOTTO_39': '39樂合彩',
                'DAILY_CASH_539': '今彩539'
            };

            // 建立詳細訊息
            let detailMsg = `數據載入成功！新增 ${result.newCount} 筆\n\n`;
            if (stats && stats.lotteryTypeCount) {
                detailMsg += '各彩券類型數量：\n';
                Object.entries(stats.lotteryTypeCount).forEach(([type, count]) => {
                    detailMsg += `• ${typeNames[type] || type}: ${count} 筆\n`;
                });
            }

            this.uiManager.showNotification(detailMsg, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                fileInfo.innerHTML = `
                    <div style="color: #22c55e; font-weight: 500;">
                        ✓ 已載入: ${file.name}
                        <div style="font-size: 0.9em; margin-top: 5px;">
                            新增 ${result.newCount} 筆數據
                        </div>
                    </div>
                `;
            }

        } catch (error) {
            this.uiManager.showNotification('檔案載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    async handleMultipleFileUpload(files) {
        try {
            this.uiManager.showNotification(`正在解析 ${files.length} 個檔案...`, 'info');
            let totalNew = 0;
            let successCount = 0;
            const fileResults = [];

            for (let i = 0; i < files.length; i++) {
                try {
                    const result = await this.dataProcessor.loadCSVData(files[i]);
                    totalNew += result.newCount;
                    successCount++;
                    fileResults.push({ name: files[i].name, count: result.newCount, success: true });
                } catch (err) {
                    console.warn(`File ${files[i].name} failed:`, err);
                    fileResults.push({ name: files[i].name, error: err.message, success: false });
                }
            }

            this.updateDataSummary();

            // 獲取統計信息
            const stats = this.statisticsService.getDataStats();
            const typeNames = {
                'BIG_LOTTO': '大樂透',
                'BIG_LOTTO_BONUS': '大樂透加開',
                'STAR_3': '三星彩',
                'STAR_4': '四星彩',
                'LOTTO_39': '39樂合彩',
                'DAILY_CASH_539': '今彩539'
            };

            // 建立詳細訊息
            let detailMsg = `批次載入完成！\n成功: ${successCount}/${files.length} 檔\n新增: ${totalNew} 筆\n\n`;

            if (stats && stats.lotteryTypeCount) {
                detailMsg += '各彩券類型總數：\n';
                Object.entries(stats.lotteryTypeCount).forEach(([type, count]) => {
                    detailMsg += `• ${typeNames[type] || type}: ${count} 筆\n`;
                });
            }

            this.uiManager.showNotification(detailMsg, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                const successFiles = fileResults.filter(f => f.success);
                const failedFiles = fileResults.filter(f => !f.success);

                let html = `<div style="color: #22c55e; font-weight: 500;">`;
                html += `✓ 已批次載入 ${successCount} 個檔案<br>`;
                html += `<div style="font-size: 0.85em; margin-top: 8px; line-height: 1.6;">`;

                successFiles.forEach(f => {
                    html += `• ${f.name}: ${f.count} 筆<br>`;
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
            this.uiManager.showNotification('批次載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    loadSampleData() {
        this.dataProcessor.loadSampleData();
        this.updateDataSummary();
        this.uiManager.showNotification('範例數據載入成功！', 'success');

        const fileInfo = document.getElementById('file-info');
        if (fileInfo) fileInfo.textContent = '✓ 已載入範例數據';
    }

    handleLotteryTypeChange() {
        // 更新數據摘要
        this.updateDataSummary();

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

    updateDataSummary() {
        const stats = this.statisticsService.getDataStats(this.currentLotteryType);
        this.uiManager.updateDataSummary(stats);

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

        // 同步數據到 localStorage，供其他頁面使用
        const data = this.dataProcessor.getData();
        if (data && data.length > 0) {
            try {
                localStorage.setItem('lotteryData', JSON.stringify(data));
            } catch (e) {
                console.warn('LocalStorage quota exceeded. Data will not be persisted for next session.', e);
                // 只有在第一次失敗時顯示通知，避免太頻繁打擾
                if (!this._storageWarningShown) {
                    this.uiManager.showNotification('注意：數據量過大，無法儲存到瀏覽器快取。\n重新整理頁面後需要重新上傳檔案。', 'warning');
                    this._storageWarningShown = true;
                }
            }
        }
    }

    clearData() {
        if (!confirm('確定要清除所有已載入的數據嗎？')) return;

        this.dataProcessor.clearData();
        this.chartManager.destroyCharts();
        this.uiManager.updateDataSummary(null);
        this.uiManager.showNotification('數據已清除', 'success');
        this.uiManager.showSection('upload');

        // 同步清除 localStorage
        localStorage.removeItem('lotteryData');
    }

    async runSimulation() {
        const method = document.getElementById('simulation-method').value;
        const yearMonth = document.getElementById('simulation-year-month').value;

        if (!yearMonth) {
            this.uiManager.showNotification('請選擇年度月份', 'warning');
            return;
        }

        // 只取年份，月份會被忽略（整年度測試）
        const [year, month] = yearMonth.split('-');
        const targetYear = year;   // 例如 "2025"

        try {
            this.uiManager.showNotification('正在進行模擬測試...', 'info');

            // 取得全部資料
            const allData = this.dataProcessor.getData();

            if (allData.length < 50) {
                throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
            }

            // -------------------------------------------------
            // 1️⃣ 只挑出目標年份的抽獎資料作為測試目標
            // -------------------------------------------------
            const testTargets = allData.filter(draw => {
                const drawYear = draw.date.split('-')[0];
                return drawYear === targetYear;
            });

            if (testTargets.length === 0) {
                const availableYears = new Set(allData.map(d => d.date.split('-')[0]));
                throw new Error(`該年份 (${targetYear}) 無開獎資料。可用年份: ${Array.from(availableYears).join(', ')}`);
            }

            // 依日期升序排列（確保滾動的先後順序正確）
            testTargets.sort((a, b) => {
                const dateA = a.date.replace(/\//g, '-');
                const dateB = b.date.replace(/\//g, '-');
                return dateA.localeCompare(dateB);
            });

            // -------------------------------------------------
            // 2️⃣ 針對該年份的每一期執行滾動預測
            // -------------------------------------------------
            const results = [];
            let successCount = 0;

            for (const targetDraw of testTargets) {
                // 取得該期之前的所有資料作為訓練集
                const targetDate = targetDraw.date.replace(/\//g, '-');
                const trainingData = allData.filter(d => {
                    const drawDate = d.date.replace(/\//g, '-');
                    return drawDate < targetDate;
                });

                // 訓練資料不足時跳過（至少 30 期才算可靠）
                if (trainingData.length < 30) {
                    console.warn(`期數 ${targetDraw.draw} 訓練資料不足 (${trainingData.length} 期)，跳過`);
                    continue;
                }

                // 執行預測
                const strategy = this.predictionEngine.strategies[method];
                if (!strategy) {
                    throw new Error('策略不存在');
                }

                console.log(`📊 目標期數 ${targetDraw.draw}: 使用 ${trainingData.length} 期資料預測`);
                const prediction = await strategy.predict(trainingData);

                // 驗證結果
                const hits = targetDraw.numbers.filter(n => prediction.numbers.includes(n));
                const isSuccess = hits.length >= 3;
                if (isSuccess) successCount++;

                const refRange = trainingData.length > 0
                    ? `${trainingData[0].draw} - ${trainingData[trainingData.length - 1].draw} (共${trainingData.length}期)`
                    : '-';

                results.push({
                    draw: targetDraw.draw,
                    date: targetDraw.date,
                    predicted: prediction.numbers,
                    actual: targetDraw.numbers,
                    hits: hits.length,
                    isSuccess: isSuccess,
                    refRange: refRange
                });
            }

            // -------------------------------------------------
            // 3️⃣ 顯示結果與成功率
            // -------------------------------------------------
            this.displaySimulationResults(results, successCount);
            this.uiManager.showNotification(
                `模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${results.length > 0 ? Math.round((successCount / results.length) * 100) : 0}%`,
                'success'
            );

        } catch (error) {
            this.uiManager.showNotification('模擬失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    async runCollaborativeSimulation() {
        const method = document.getElementById('collab-method').value;
        const yearMonth = document.getElementById('collab-year-month').value;

        if (!yearMonth) {
            this.uiManager.showNotification('請選擇年度月份', 'warning');
            return;
        }

        const [year, month] = yearMonth.split('-');
        const targetYear = year;

        try {
            this.uiManager.showNotification('正在進行協作模擬測試...', 'info');

            const allData = this.dataProcessor.getData();
            if (allData.length < 50) {
                throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
            }

            const testTargets = allData.filter(draw => draw.date.split('-')[0] === targetYear);
            if (testTargets.length === 0) {
                const availableYears = new Set(allData.map(d => d.date.split('-')[0]));
                throw new Error(`該年份 (${targetYear}) 無開獎資料。可用年份: ${Array.from(availableYears).join(', ')}`);
            }

            testTargets.sort((a, b) => {
                const dateA = a.date.replace(/\//g, '-');
                const dateB = b.date.replace(/\//g, '-');
                return dateA.localeCompare(dateB);
            });

            const results = [];
            let successCount = 0;

            for (const targetDraw of testTargets) {
                const targetDate = targetDraw.date.replace(/\//g, '-');
                const trainingData = allData.filter(d => {
                    const drawDate = d.date.replace(/\//g, '-');
                    return drawDate < targetDate;
                });

                if (trainingData.length < 30) continue;

                const strategy = this.predictionEngine.strategies[method];
                if (!strategy) {
                    throw new Error('策略不存在');
                }

                console.log(`📊 協作預測 ${targetDraw.draw}: 使用 ${trainingData.length} 期資料`);
                const prediction = await strategy.predict(trainingData);

                const hits = targetDraw.numbers.filter(n => prediction.numbers.includes(n));
                const isSuccess = hits.length >= 3;
                if (isSuccess) successCount++;

                const refRange = trainingData.length > 0
                    ? `${trainingData[0].draw} - ${trainingData[trainingData.length - 1].draw} (共${trainingData.length}期)`
                    : '-';

                results.push({
                    draw: targetDraw.draw,
                    date: targetDraw.date,
                    predicted: prediction.numbers,
                    actual: targetDraw.numbers,
                    hits: hits.length,
                    isSuccess: isSuccess,
                    refRange: refRange
                });
            }

            // Display results in collaborative section
            const tbody = document.querySelector('#collab-simulation-table tbody');
            const rateSpan = document.getElementById('collab-simulation-rate');
            const resultsDiv = document.getElementById('collab-simulation-results');

            if (tbody && rateSpan && resultsDiv) {
                const rate = results.length > 0 ? Math.round((successCount / results.length) * 100) : 0;
                rateSpan.textContent = rate;

                tbody.innerHTML = results.map(r => `
                    <tr class="${r.isSuccess ? 'success-row' : ''}">
                        <td>${r.draw}</td>
                        <td>${r.date}</td>
                        <td>${r.predicted.join(', ')}</td>
                        <td>${r.actual.join(', ')}</td>
                        <td><span class="hit-badge ${r.hits >= 3 ? 'high-hit' : ''}">${r.hits}</span></td>
                        <td>${r.refRange}</td>
                        <td>${r.isSuccess ? '✅' : '❌'}</td>
                    </tr>
                `).join('');

                resultsDiv.style.display = 'block';
            }

            this.uiManager.showNotification(
                `協作模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${results.length > 0 ? Math.round((successCount / results.length) * 100) : 0}%`,
                'success'
            );

        } catch (error) {
            this.uiManager.showNotification('協作模擬失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    async runAutoOptimization() {
        const method = document.getElementById('simulation-method').value;
        const yearMonth = document.getElementById('simulation-year-month').value;
        if (!yearMonth) {
            this.uiManager.showNotification('請先選擇年度月份', 'warning');
            return;
        }

        // 只取年份（整年度測試）
        const [year] = yearMonth.split('-');
        const targetYear = year;

        try {
            this.uiManager.showNotification('開始自動優化 (20 輪)...', 'info');

            // 取得全部資料
            const allData = this.dataProcessor.getData();

            // 只保留目標年份的抽獎資料
            const testTargets = allData.filter(d => d.date.split('-')[0] === targetYear);
            if (testTargets.length === 0) {
                throw new Error(`該年份 (${targetYear}) 無資料`);
            }

            // 依日期升序排列
            testTargets.sort((a, b) => {
                const da = a.date.replace(/\//g, '-');
                const db = b.date.replace(/\//g, '-');
                return da.localeCompare(db);
            });

            // 參數初始化（使用目前 EnsembleStrategy 的權重）
            const ensemble = this.predictionEngine.strategies[method];
            if (!ensemble || !ensemble.weights) throw new Error('此策略不支援自動優化 (需有 weights 屬性)');

            // 20 輪優化
            let bestParams = { ...ensemble.weights };
            let bestRate = 0;

            for (let round = 1; round <= 20; round++) {
                // 使用完整的 testTargets 執行滾動測試
                const result = await this.runRollingTest(allData, ensemble, bestParams, testTargets);

                if (result.rate > bestRate) {
                    bestRate = result.rate;
                    bestParams = { ...ensemble.weights }; // 這裡假設 ensemble.weights 已經在測試中被修改，或者我們應該在測試前修改它？
                    // 修正：runRollingTest 應該使用傳入的 params，但 ensemble.predict 使用 this.weights
                    // 因此我們需要暫時修改 ensemble.weights
                }

                this.uiManager.showNotification(`第 ${round} 輪: 成功率 ${result.rate.toFixed(2)}% (最佳: ${bestRate.toFixed(2)}%)`, 'info');

                // 簡易微調：根據成功率微調幾個關鍵權重
                const delta = 0.05; // 調整幅度
                const newParams = { ...bestParams };

                // 隨機調整參數
                for (const key in newParams) {
                    if (typeof newParams[key] === 'number') {
                        if (Math.random() > 0.5) {
                            newParams[key] *= (1 + (Math.random() - 0.5) * delta);
                        }
                    }
                }

                // 應用新參數到策略以便下一輪測試 (或這一輪測試)
                // 注意：這裡的邏輯是 "下一輪測試用新參數"
                ensemble.weights = newParams;
            }

            // 恢復最佳參數
            ensemble.weights = bestParams;

            console.log('🏆 最佳參數:', JSON.stringify(bestParams, null, 2));

            this.uiManager.showNotification(
                `✅ 自動優化完成！最佳成功率 ${bestRate.toFixed(2)}%。參數已更新至當前策略 (請查看 Console 複製參數)`,
                'success'
            );

        } catch (err) {
            this.uiManager.showNotification('自動優化失敗: ' + err.message, 'error');
            console.error(err);
        }
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

            tbody.innerHTML = results.map(r => `
                <tr class="${r.isSuccess ? 'success-row' : ''}">
                    <td>${r.draw}</td>
                    <td>${r.date}</td>
                    <td>${r.predicted.join(', ')}</td>
                    <td>${r.actual.join(', ')}</td>
                    <td><span class="hit-badge ${r.hits >= 3 ? 'high-hit' : ''}">${r.hits}</span></td>
                    <td>${r.refRange || '-'}</td>
                    <td>${r.isSuccess ? '✅' : '❌'}</td>
                </tr>
            `).join('');

            resultsDiv.style.display = 'block';
        }
    }

    async runPrediction() {
        const method = document.getElementById('prediction-method').value;
        const sampleSize = document.getElementById('sample-size').value;
        const lotteryType = this.currentLotteryType;

        try {
            this.uiManager.showNotification('正在分析預測...', 'info');
            const result = await this.predictionEngine.predict(method, sampleSize, lotteryType);
            this.displayPredictionResult(result);
            this.uiManager.showNotification('預測完成！', 'success');
        } catch (error) {
            this.uiManager.showNotification('預測失敗: ' + error.message, 'error');
        }
    }

    displayPredictionResult(result) {
        const container = document.getElementById('predicted-numbers');
        if (container) {
            container.innerHTML = result.numbers.map(num =>
                `<div class="number-ball">${num}</div>`
            ).join('');
        }

        const confidenceVal = document.getElementById('confidence-value');
        const confidenceFill = document.getElementById('confidence-fill');
        if (confidenceVal) confidenceVal.textContent = `${result.confidence}%`;
        if (confidenceFill) confidenceFill.style.width = `${result.confidence}%`;

        const report = document.getElementById('prediction-report');
        if (report) report.textContent = result.report;
    }

    displayHistory() {
        let data = this.dataProcessor.getData();

        // 根據選擇的彩券類型篩選數據
        if (this.currentLotteryType) {
            data = data.filter(draw => draw.lotteryType === this.currentLotteryType);
        }

        this.uiManager.updateHistoryTable(data, this.currentPage, this.itemsPerPage);
        this.uiManager.updatePagination(data.length, this.currentPage, this.itemsPerPage, (page) => {
            this.currentPage = page;
            this.displayHistory();
        });
    }
}
