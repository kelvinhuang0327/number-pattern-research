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
        this.initSmartBetting(); // 初始化聰明包牌
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

        // 多檔案上傳
        const folderBtn = document.getElementById('folder-btn');
        const multipleInput = document.getElementById('multiple-input');

        if (folderBtn && multipleInput) {
            folderBtn.addEventListener('click', () => {
                multipleInput.click();
            });

            multipleInput.addEventListener('change', async (e) => {
                const files = Array.from(e.target.files).filter(f => f.name.endsWith('.csv'));
                if (files.length > 0) {
                    await this.handleFolderUpload(files);
                } else {
                    this.showNotification('請選擇 CSV 檔案', 'warning');
                }
            });
        }

        // -------------------
        // 模擬測試功能
        // -------------------
        const simulationBtn = document.getElementById('simulation-btn');
        const simulationMonthInput = document.getElementById('simulation-year-month');
        const simulationResultsDiv = document.getElementById('simulation-results');
        const simulationRateSpan = document.getElementById('simulation-rate');
        const simulationTableBody = document.querySelector('#simulation-table tbody');

        if (simulationBtn && simulationMonthInput && simulationResultsDiv) {
            simulationBtn.addEventListener('click', async () => {
                const monthValue = simulationMonthInput.value; // format YYYY-MM
                if (!monthValue) {
                    this.showNotification('請選擇模擬月份', 'warning');
                    return;
                }
                const [yearStr, monthStr] = monthValue.split('-');
                const targetYear = parseInt(yearStr, 10);
                const targetMonth = parseInt(monthStr, 10);

                // 取得所有已上傳的資料
                const allData = this.dataProcessor.getData();
                if (!allData || allData.length === 0) {
                    this.showNotification('請先上傳資料', 'warning');
                    return;
                }

                // 過濾出目標月份的抽獎結果，假設 draw.date 為 YYYY/MM/DD 或 YYYY-MM-DD
                const monthPrefix = `${targetYear}-${String(targetMonth).padStart(2, '0')}`;
                const monthDraws = allData.filter(d => {
                    // 允許日期格式為 YYYY/MM/DD、YYYY-MM-DD 或 ISO
                    const normalized = d.date.replace(/\//g, '-');
                    return normalized.startsWith(monthPrefix);
                }).sort((a, b) => new Date(a.date) - new Date(b.date));

                if (monthDraws.length === 0) {
                    this.showNotification('該月份沒有資料可供模擬', 'warning');
                    return;
                }

                // 取得使用者選擇的預測方法（從模擬區塊的下拉選單）
                const methodSelect = document.getElementById('simulation-method');
                const method = methodSelect ? methodSelect.value : 'frequency';

                console.log(`Starting simulation for ${monthPrefix} with method: ${method}. Found ${monthDraws.length} draws.`);

                let successCount = 0;
                const results = [];

                for (let i = 0; i < monthDraws.length; i++) {
                    const currentDraw = monthDraws[i];
                    // 取出當前抽獎之前的所有資料作為訓練集
                    const trainingData = allData.filter(d => new Date(d.date) < new Date(currentDraw.date));

                    // 取得訓練資料的起訖期數
                    let rangeString = '無資料';
                    if (trainingData.length > 0) {
                        // 找出日期最大（最近）和最小（最遠）的那一筆
                        const latest = trainingData.reduce((prev, current) => (new Date(prev.date) > new Date(current.date)) ? prev : current);
                        const earliest = trainingData.reduce((prev, current) => (new Date(prev.date) < new Date(current.date)) ? prev : current);
                        rangeString = `${earliest.draw} - ${latest.draw}`;
                    }

                    // 建立臨時 DataProcessor
                    const tempDP = new DataProcessor();
                    // 重要：預測模型需要「時間正序 (Old -> New)」的資料來計算趨勢與轉移
                    // 但 allData 是降序 (New -> Old)，所以這裡必須反轉或重新排序
                    const sortedTrainingData = [...trainingData].sort((a, b) => new Date(a.date) - new Date(b.date));
                    tempDP.lotteryData = sortedTrainingData; // 設定排序後的資料

                    const tempPE = new PredictionEngine(tempDP);
                    const prediction = await tempPE.predictWithData(method, sortedTrainingData);

                    // 取得所有預測號碼及其機率，取前 10 名作為觀察名單
                    // 注意：prediction.numbers 通常只回傳前 6 個，我們需要修改 prediction.js 讓它回傳更多，
                    // 或者直接從 prediction.probabilities 排序取出
                    const allProbs = Object.entries(prediction.probabilities)
                        .map(([num, prob]) => ({ number: parseInt(num), probability: prob }))
                        .sort((a, b) => b.probability - a.probability)
                        .slice(0, 10) // 取前 10 名
                        .map(item => item.number)
                        .sort((a, b) => a - b); // 號碼排序方便閱讀

                    const predictedNumbers = allProbs; // 使用前 10 個號碼進行比對
                    const actualNumbers = currentDraw.numbers;

                    // 計算命中 (在 10 個預測號碼中中了幾個)
                    const hitCount = predictedNumbers.filter(n => actualNumbers.includes(n)).length;

                    // 標記命中的號碼 (HTML)
                    const predictedDisplay = predictedNumbers.map(n => {
                        return actualNumbers.includes(n)
                            ? `<span style="color: #ff4444; font-weight: bold;">${n}</span>`
                            : `<span style="color: #cccccc;">${n}</span>`;
                    }).join(', ');

                    // 成功定義：如果 10 個號碼裡包含所有 6 個開獎號碼 (這很難)，或者中 3 個以上算及格
                    const success = hitCount >= 3; // 放寬標準：中3個就算有參考價值
                    if (success) successCount++;

                    results.push({
                        draw: currentDraw.draw,
                        date: currentDraw.date,
                        predicted: predictedDisplay, // 使用帶顏色的 HTML
                        actual: actualNumbers.join(', '),
                        hit: hitCount,
                        baseRange: rangeString,
                        success: hitCount >= 3 ? (hitCount >= 5 ? '🌟' : '✅') : '❌'
                    });
                }

                // 計算成功率
                const successRate = ((successCount / monthDraws.length) * 100).toFixed(2);
                simulationRateSpan.textContent = successRate;

                // 填充表格
                simulationTableBody.innerHTML = results.map(r => `
                    <tr style="color:#fff;">
                        <td>${r.draw}</td>
                        <td>${r.date}</td>
                        <td>${r.predicted}</td>
                        <td>${r.actual}</td>
                        <td>${r.hit}</td>
                        <td>${r.baseRange}</td>
                        <td>${r.success}</td>
                    </tr>`).join('');

                // 顯示 debug 日誌 (已移除)
                const debugDiv = document.getElementById('simulation-debug');
                if (debugDiv) {
                    debugDiv.style.display = 'none';
                }

                simulationResultsDiv.style.display = 'block';
                this.showNotification('模擬完成！成功率 ' + successRate + '%', 'success');
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

            const result = await this.dataProcessor.loadCSVData(file);

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                let message = `✓ 已載入: ${file.name}`;

                // 顯示重複資訊
                if (result.duplicateCount > 0) {
                    message += `\n⚠️ 發現 ${result.duplicateCount} 筆重複資料已自動過濾`;
                }

                message += `\n📊 新增 ${result.newCount} 筆，總計 ${result.totalCount} 筆`;

                fileInfo.innerHTML = message.replace(/\n/g, '<br>');
                fileInfo.style.whiteSpace = 'pre-line';
            }

            this.updateDataSummary();

            // 根據重複情況顯示不同通知
            if (result.duplicateCount > 0) {
                this.showNotification(
                    `數據載入成功！發現 ${result.duplicateCount} 筆重複已過濾，新增 ${result.newCount} 筆`,
                    'warning'
                );
            } else {
                this.showNotification(`數據載入成功！新增 ${result.newCount} 筆`, 'success');
            }

        } catch (error) {
            this.showNotification('檔案載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    /**
     * 處理資料夾上傳（批量處理多個檔案）
     */
    async handleFolderUpload(files) {
        try {
            this.showNotification(`正在處理 ${files.length} 個檔案...`, 'info');

            let totalNew = 0;
            let totalDuplicates = 0;
            let successCount = 0;
            let failedFiles = [];

            for (const file of files) {
                try {
                    const result = await this.dataProcessor.loadCSVData(file);
                    totalNew += result.newCount;
                    totalDuplicates += result.duplicateCount;
                    successCount++;
                } catch (error) {
                    failedFiles.push(file.name);
                    console.error(`Failed to load ${file.name}:`, error);
                }
            }

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                let message = `✓ 已處理 ${successCount}/${files.length} 個檔案`;

                if (failedFiles.length > 0) {
                    message += `\n❌ 失敗: ${failedFiles.join(', ')}`;
                }

                if (totalDuplicates > 0) {
                    message += `\n⚠️ 發現 ${totalDuplicates} 筆重複資料已自動過濾`;
                }

                message += `\n📊 新增 ${totalNew} 筆，總計 ${this.dataProcessor.getData().length} 筆`;

                fileInfo.innerHTML = message.replace(/\n/g, '<br>');
                fileInfo.style.whiteSpace = 'pre-line';
            }

            this.updateDataSummary();

            // 顯示結果通知
            if (failedFiles.length > 0) {
                this.showNotification(
                    `處理完成！成功 ${successCount} 個，失敗 ${failedFiles.length} 個，新增 ${totalNew} 筆`,
                    'warning'
                );
            } else if (totalDuplicates > 0) {
                this.showNotification(
                    `全部載入成功！發現 ${totalDuplicates} 筆重複已過濾，新增 ${totalNew} 筆`,
                    'success'
                );
            } else {
                this.showNotification(`全部載入成功！新增 ${totalNew} 筆`, 'success');
            }

        } catch (error) {
            this.showNotification('資料夾處理失敗: ' + error.message, 'error');
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
    async runPrediction() {
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

        try {
            // 使用 await 支援 async 預測方法（如 TensorFlow）
            const prediction = await this.predictionEngine.predict(method, sampleSize);
            this.predictionEngine.displayPrediction(prediction);
            this.showNotification('預測完成！', 'success');
        } catch (error) {
            this.showNotification('預測失敗: ' + error.message, 'error');
            console.error('Prediction error:', error);
        }
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
    // 初始化聰明包牌區塊
    initSmartBetting() {
        const numberSelector = document.getElementById('number-selector');
        const selectedCountVal = document.getElementById('selected-count-val');
        const generateBtn = document.getElementById('generate-smart-bet-btn');
        const resultsDiv = document.getElementById('smart-bet-results');
        const combinationsDiv = document.getElementById('betting-combinations');

        let selectedNumbers = new Set();

        // 1. 生成 1-49 號碼按鈕
        numberSelector.innerHTML = ''; // 清空舊內容
        for (let i = 1; i <= 49; i++) {
            const btn = document.createElement('div');
            btn.className = 'number-ball';
            btn.textContent = i;
            btn.style.cursor = 'pointer';

            btn.addEventListener('click', () => {
                if (selectedNumbers.has(i)) {
                    selectedNumbers.delete(i);
                    btn.classList.remove('active');
                } else {
                    if (selectedNumbers.size >= 16) {
                        this.showNotification('最多只能選擇 16 個號碼', 'error');
                        return;
                    }
                    selectedNumbers.add(i);
                    btn.classList.add('active');
                }
                selectedCountVal.textContent = selectedNumbers.size;
            });
            numberSelector.appendChild(btn);
        }

        // 2. 產生組合按鈕事件
        generateBtn.addEventListener('click', () => {
            if (selectedNumbers.size < 8) {
                this.showNotification('請至少選擇 8 個號碼', 'error');
                return;
            }

            const system = document.getElementById('wheeling-system').value;
            const nums = Array.from(selectedNumbers).sort((a, b) => a - b);

            // 根據選擇的系統生成組合
            let combinations = this.generateWheelingSystem(nums, system);

            // 3. 智慧過濾
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

            // 顯示結果
            combinationsDiv.innerHTML = '';
            if (combinations.length === 0) {
                combinationsDiv.innerHTML = '<div class="no-data">過濾後無符合條件的組合，請放寬過濾條件或增加選號。</div>';
            } else {
                combinations.forEach((combo, index) => {
                    this.renderCombinationRow(combinationsDiv, combo, `#${index + 1}`, null);
                });
            }

            resultsDiv.style.display = 'block';
            this.showNotification(`已生成 ${combinations.length} 組聰明組合 (原 ${originalCount} 組)`, 'success');

            // 滾動到結果區
            resultsDiv.scrollIntoView({ behavior: 'smooth' });
        });

        // 快速生成 2 注對沖按鈕事件
        const hedgingBtn = document.getElementById('generate-hedging-btn');
        if (hedgingBtn) {
            hedgingBtn.addEventListener('click', async () => {
                if (!this.dataProcessor.lotteryData || this.dataProcessor.lotteryData.length === 0) {
                    this.showNotification('請先上傳或載入數據', 'error');
                    return;
                }

                // 1. 獲取熱門號碼 (使用頻率分析)
                const frequency = this.predictionEngine.calculateFrequency(this.dataProcessor.lotteryData);
                const hotNumbers = Object.entries(frequency)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6)
                    .map(([num]) => parseInt(num))
                    .sort((a, b) => a - b);

                // 2. 獲取冷門號碼 (使用遺漏值分析)
                const missing = this.predictionEngine.calculateMissing(this.dataProcessor.lotteryData);
                const coldNumbers = Object.entries(missing)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6)
                    .map(([num]) => parseInt(num))
                    .sort((a, b) => a - b);

                // 顯示結果
                combinationsDiv.innerHTML = '';

                // 熱門注
                this.renderCombinationRow(combinationsDiv, hotNumbers, '🔥', '#FF512F', '(正統熱門)');

                // 冷門注
                this.renderCombinationRow(combinationsDiv, coldNumbers, '❄️', '#3498db', '(冷門翻身)');

                resultsDiv.style.display = 'block';
                this.showNotification('已生成 2 注風險對沖組合', 'success');
                resultsDiv.scrollIntoView({ behavior: 'smooth' });
            });
        }
    }

    // 渲染組合行 (包含科學分析儀表板)
    renderCombinationRow(container, numbers, icon, color, label = '') {
        const row = document.createElement('div');
        row.className = 'combination-row';
        if (color) row.style.borderLeft = `3px solid ${color}`;

        // 計算科學指標
        const sum = numbers.reduce((a, b) => a + b, 0);
        const oddCount = numbers.filter(n => n % 2 !== 0).length;
        const evenCount = numbers.length - oddCount;
        const bigCount = numbers.filter(n => n >= 25).length;
        const smallCount = numbers.length - bigCount;
        const acValue = this.calculateAC(numbers);

        // 判斷指標健康度 (簡單紅綠燈)
        const isSumGood = sum >= 120 && sum <= 180;
        const isOEGood = oddCount >= 2 && oddCount <= 4;
        const isHLGood = bigCount >= 2 && bigCount <= 4;
        const isACGood = acValue >= 7;

        row.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
                <span class="combo-index">${icon}</span>
                <div class="combo-numbers">
                    ${numbers.map(n => `<span class="number-ball small" style="${color ? `background: ${color};` : ''}">${n}</span>`).join('')}
                </div>
                ${label ? `<span style="color: #aaa; font-size: 0.8em;">${label}</span>` : ''}
            </div>
            
            <!-- 科學分析儀表板 -->
            <div class="analysis-dashboard" style="margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 0.85em; display: flex; gap: 15px; color: #aaa;">
                <span class="metric-sum" style="color: ${isSumGood ? '#4caf50' : '#ff9800'};">和值: <b>${sum}</b></span>
                <span class="metric-oe" style="color: ${isOEGood ? '#4caf50' : '#ff9800'};">奇偶: <b>${oddCount}:${evenCount}</b></span>
                <span class="metric-hl" style="color: ${isHLGood ? '#4caf50' : '#ff9800'};">大小: <b>${bigCount}:${smallCount}</b></span>
                <span class="metric-ac" style="color: ${isACGood ? '#4caf50' : '#ff9800'};">AC值: <b>${acValue}</b></span>
            </div>
        `;
        container.appendChild(row);
    }

    // 計算 AC 值 (Arithmetic Complexity)
    calculateAC(numbers) {
        const diffs = new Set();
        for (let i = 0; i < numbers.length; i++) {
            for (let j = i + 1; j < numbers.length; j++) {
                diffs.add(Math.abs(numbers[i] - numbers[j]));
            }
        }
        return diffs.size - (numbers.length - 1);
    }

    // 聰明包牌邏輯 (Wheeling System)
    generateWheelingSystem(nums, system) {
        const combinations = [];
        const n = nums.length;

        // 這裡使用簡化的隨機抽樣模擬旋轉矩陣
        // 在真實應用中，應該使用預先計算好的旋轉矩陣表 (Covering Design)
        // 但為了彈性適應任意 N 個選號，我們使用蒙地卡羅法來逼近最佳覆蓋

        let targetCount = 10;
        let guarantee = 3; // 預設保3

        if (system === 'pick10_win3') { targetCount = 10; guarantee = 3; }
        else if (system === 'pick12_win4') { targetCount = 20; guarantee = 4; }
        else if (system === 'pick10_win5') { targetCount = 50; guarantee = 5; }

        // 根據選號數量動態調整注數上限，避免過少
        if (n > 12 && targetCount < 20) targetCount = 20;
        if (n > 14 && targetCount < 30) targetCount = 30;

        const seen = new Set();
        let attempts = 0;
        const maxAttempts = 5000;

        // 策略：隨機生成大量組合，然後挑選彼此「差異最大」的組合以最大化覆蓋率
        while (combinations.length < targetCount && attempts < maxAttempts) {
            attempts++;
            // 隨機選 6 個
            const shuffled = [...nums].sort(() => 0.5 - Math.random());
            const combo = shuffled.slice(0, 6).sort((a, b) => a - b);
            const key = combo.join(',');

            if (!seen.has(key)) {
                // 檢查覆蓋率：如果這組號碼跟已選的組合太像 (例如只差 1 個號碼)，就跳過
                // 這樣可以讓組合分散，覆蓋更多可能性
                let isRedundant = false;
                for (const existing of combinations) {
                    const overlap = this.countOverlap(combo, existing);
                    if (overlap >= guarantee + 1) { // 如果已經有組合能保證中獎，這組就多餘了
                        isRedundant = true;
                        break;
                    }
                }

                if (!isRedundant || attempts > 1000) { // 後期放寬標準以免選不滿
                    seen.add(key);
                    combinations.push(combo);
                }
            }
        }

        return combinations.sort((a, b) => a[0] - b[0]);
    }

    // 計算兩個組合的重疊數
    countOverlap(arr1, arr2) {
        return arr1.filter(n => arr2.includes(n)).length;
    }

    // 輔助過濾函式
    hasConsecutive(nums, count) {
        let current = 1;
        for (let i = 0; i < nums.length - 1; i++) {
            if (nums[i + 1] === nums[i] + 1) {
                current++;
                if (current >= count) return true;
            } else {
                current = 1;
            }
        }
        return false;
    }

    isAllOddOrEven(nums) {
        const odds = nums.filter(n => n % 2 !== 0).length;
        return odds === 0 || odds === nums.length;
    }

    isExtreme(nums) {
        const allSmall = nums.every(n => n <= 24);
        const allBig = nums.every(n => n >= 25);
        return allSmall || allBig;
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
