import { LOTTERY_RULES } from '../utils/Constants.js';
import { StatisticsService } from '../data/StatisticsService.js';
import { PredictionEngine } from '../engine/PredictionEngine.js';
import { UIManager } from '../ui/UIManager.js';
import { ChartManager } from '../ui/ChartManager.js';
import { SmartBettingComponent } from '../ui/components/SmartBettingComponent.js';

/**
 * 數據處理模組 (Inlined for reliability)
 */
class DataProcessor {
    constructor() {
        this.lotteryData = [];
        this.sampleData = this.generateSampleData();
    }

    generateSampleData() {
        const data = [];
        const startDate = new Date('2023-01-01');
        const totalDraws = 500; // 增加至500期，確保完整覆蓋2025年全年

        for (let i = 0; i < totalDraws; i++) {
            const drawDate = new Date(startDate);
            drawDate.setDate(startDate.getDate() + (i * 3)); // 每3天一期

            const numbers = this.generateRandomNumbers(LOTTERY_RULES.pickCount, LOTTERY_RULES.numberRange.min, LOTTERY_RULES.numberRange.max);
            let specialNumber;
            do {
                specialNumber = Math.floor(Math.random() * LOTTERY_RULES.numberRange.max) + LOTTERY_RULES.numberRange.min;
            } while (numbers.includes(specialNumber));

            data.push({
                draw: String(113000000 + i + 1).padStart(9, '0'),
                date: drawDate.toISOString().split('T')[0],
                numbers: numbers.sort((a, b) => a - b),
                special: specialNumber
            });
        }
        return data;
    }

    generateRandomNumbers(count, min, max) {
        const numbers = new Set();
        while (numbers.size < count) {
            numbers.add(Math.floor(Math.random() * (max - min + 1)) + min);
        }
        return Array.from(numbers);
    }

    async parseCSV(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const text = e.target.result;
                    const lines = text.split('\n').filter(line => line.trim());
                    const data = [];
                    if (lines.length < 2) { reject(new Error('檔案內容為空或格式錯誤')); return; }

                    const firstLine = lines[0].trim();
                    const secondLine = lines.length > 1 ? lines[1].trim() : '';
                    const isOfficialFormat = firstLine.includes('遊戲名稱') || (secondLine && (secondLine.includes('大樂透') || secondLine.includes('Lotto')));

                    for (let i = 1; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) continue;
                        const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
                        let draw, date, numbers, special;

                        if (isOfficialFormat) {
                            if (!parts[0].includes('大樂透') && !parts[0].includes('Lotto')) continue;
                            if (parts.length < 13) continue;
                            draw = parts[1];
                            // 統一將日期格式轉換為 YYYY-MM-DD
                            date = parts[2].replace(/\//g, '-');
                            numbers = [parseInt(parts[6]), parseInt(parts[7]), parseInt(parts[8]), parseInt(parts[9]), parseInt(parts[10]), parseInt(parts[11])];
                            special = parseInt(parts[12]);
                        } else {
                            if (parts.length < 8) continue;
                            draw = parts[0];
                            // 統一將日期格式轉換為 YYYY-MM-DD
                            date = parts[1].replace(/\//g, '-');
                            numbers = [parseInt(parts[2]), parseInt(parts[3]), parseInt(parts[4]), parseInt(parts[5]), parseInt(parts[6]), parseInt(parts[7])];
                            special = parseInt(parts[8]);
                        }

                        const validNumbers = numbers.filter(n => !isNaN(n) && n >= LOTTERY_RULES.numberRange.min && n <= LOTTERY_RULES.numberRange.max);
                        if (validNumbers.length === LOTTERY_RULES.pickCount && !isNaN(special) && special >= LOTTERY_RULES.numberRange.min && special <= LOTTERY_RULES.numberRange.max) {
                            data.push({ draw, date, numbers: validNumbers.sort((a, b) => a - b), special });
                        }
                    }
                    if (data.length === 0) reject(new Error('無法解析CSV檔案'));
                    else resolve(data);
                } catch (error) { reject(new Error('CSV解析錯誤: ' + error.message)); }
            };
            reader.onerror = () => reject(new Error('檔案讀取失敗'));
            reader.readAsText(file, 'UTF-8');
        });
    }

    loadSampleData() {
        this.lotteryData = [...this.sampleData];
        return this.lotteryData;
    }

    async loadCSVData(file) {
        const newData = await this.parseCSV(file);
        const duplicateInfo = this.checkDuplicates(newData);
        this.lotteryData = duplicateInfo.mergedData;
        return {
            data: this.lotteryData,
            duplicates: duplicateInfo.duplicates,
            duplicateCount: duplicateInfo.duplicateCount,
            newCount: duplicateInfo.newCount,
            totalCount: duplicateInfo.totalCount
        };
    }

    checkDuplicates(newData) {
        const existingDraws = new Set(this.lotteryData.map(d => d.draw));
        const duplicates = [];
        const uniqueNew = [];
        newData.forEach(draw => {
            if (existingDraws.has(draw.draw)) duplicates.push(draw);
            else { uniqueNew.push(draw); existingDraws.add(draw.draw); }
        });
        const mergedData = [...this.lotteryData, ...uniqueNew];
        mergedData.sort((a, b) => parseInt(b.draw) - parseInt(a.draw));
        return { mergedData, duplicates, duplicateCount: duplicates.length, newCount: uniqueNew.length, totalCount: mergedData.length };
    }

    getData() { return this.lotteryData; }
    getDataRange(sampleSize) {
        if (sampleSize === 'all') return this.lotteryData;
        return this.lotteryData.slice(0, parseInt(sampleSize));
    }
    clearData() { this.lotteryData = []; return this.lotteryData; }
    searchData(query) {
        if (!query) return this.lotteryData;
        return this.lotteryData.filter(draw => draw.draw.includes(query) || draw.date.includes(query));
    }
    sortData(order = 'desc') {
        return [...this.lotteryData].sort((a, b) => order === 'desc' ? b.draw.localeCompare(a.draw) : a.draw.localeCompare(b.draw));
    }
}

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

        // 導航切換時的額外邏輯
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                if (section === 'analysis') {
                    setTimeout(() => this.chartManager.initializeCharts(), 100);
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
            this.uiManager.showNotification(`數據載入成功！新增 ${result.newCount} 筆`, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) fileInfo.textContent = `✓ 已載入: ${file.name}`;

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

            for (let i = 0; i < files.length; i++) {
                try {
                    const result = await this.dataProcessor.loadCSVData(files[i]);
                    totalNew += result.newCount;
                    successCount++;
                } catch (err) {
                    console.warn(`File ${files[i].name} failed:`, err);
                }
            }

            this.updateDataSummary();
            this.uiManager.showNotification(`批次載入完成！成功 ${successCount}/${files.length} 檔，新增 ${totalNew} 筆數據`, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) fileInfo.textContent = `✓ 已批次載入 ${successCount} 個檔案`;

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

    updateDataSummary() {
        const stats = this.statisticsService.getDataStats();
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
    }

    clearData() {
        if (!confirm('確定要清除所有已載入的數據嗎？')) return;

        this.dataProcessor.clearData();
        this.chartManager.destroyCharts();
        this.uiManager.updateDataSummary(null);
        this.uiManager.showNotification('數據已清除', 'success');
        this.uiManager.showSection('upload');
    }

    async runSimulation() {
        const method = document.getElementById('simulation-method').value;
        const yearMonth = document.getElementById('simulation-year-month').value;

        if (!yearMonth) {
            this.uiManager.showNotification('請選擇年度月份', 'warning');
            return;
        }

        const [year, month] = yearMonth.split('-');
        const targetDateStr = `${year}-${month}`;

        try {
            this.uiManager.showNotification('正在進行模擬測試...', 'info');

            // 獲取所有數據
            const allData = this.dataProcessor.getData();

            if (allData.length < 50) {
                throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
            }

            // 篩選出目標月份的期數作為測試對象
            const normalizedTarget = targetDateStr.replace(/\//g, '-');

            const testTargets = allData.filter(draw => {
                const drawDate = draw.date.replace(/\//g, '-');
                return drawDate.startsWith(normalizedTarget);
            });

            if (testTargets.length === 0) {
                const availableMonths = new Set(allData.map(d => d.date.substring(0, 7)));
                throw new Error(`該月份 (${targetDateStr}) 無開獎數據。可用月份: ${Array.from(availableMonths).join(', ')}`);
            }

            // 按日期升序排列
            testTargets.sort((a, b) => {
                const dateA = a.date.replace(/\//g, '-');
                const dateB = b.date.replace(/\//g, '-');
                return dateA.localeCompare(dateB);
            });

            // === 滾動預測：每一期都用該期之前的所有數據重新預測 ===
            const results = [];
            let successCount = 0;

            for (const targetDraw of testTargets) {
                // 找出該期之前的所有數據作為訓練集（包含該月之前已測試的期數）
                const targetDate = targetDraw.date.replace(/\//g, '-');
                const trainingData = allData.filter(d => {
                    const drawDate = d.date.replace(/\//g, '-');
                    return drawDate < targetDate;
                });

                // 確保訓練數據足夠
                if (trainingData.length < 30) {
                    console.warn(`期數 ${targetDraw.draw} 訓練數據不足，跳過`);
                    continue;
                }

                // 執行預測
                const strategy = this.predictionEngine.strategies[method];
                if (!strategy) {
                    throw new Error('策略不存在');
                }

                console.log(`📊 期數 ${targetDraw.draw}: 使用 ${trainingData.length} 期數據預測`);
                const prediction = await strategy.predict(trainingData);

                // 驗證結果
                const hits = targetDraw.numbers.filter(n => prediction.numbers.includes(n));
                const isSuccess = hits.length >= 3;
                if (isSuccess) successCount++;

                // 計算參考期數範圍
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

            // 顯示結果
            this.displaySimulationResults(results, successCount);
            this.uiManager.showNotification(
                `模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${Math.round((successCount / results.length) * 100)}%`,
                'success'
            );

        } catch (error) {
            this.uiManager.showNotification('模擬失敗: ' + error.message, 'error');
            console.error(error);
        }
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

        try {
            this.uiManager.showNotification('正在分析預測...', 'info');
            const result = await this.predictionEngine.predict(method, sampleSize);
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
        const data = this.dataProcessor.getData();
        this.uiManager.updateHistoryTable(data, this.currentPage, this.itemsPerPage);
        this.uiManager.updatePagination(data.length, this.currentPage, this.itemsPerPage, (page) => {
            this.currentPage = page;
            this.displayHistory();
        });
    }
}
