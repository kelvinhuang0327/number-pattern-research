/**
 * 自動學習管理器
 * 管理自動優化和排程功能
 */
import { getLotteryTypeById } from '../utils/LotteryTypes.js';
import { apiClient } from '../services/ApiClient.js';

// 🔧 定義 API 基礎 URL（文件級常量，避免實例屬性問題）
const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:5001/api/auto-learning'
    : 'https://your-api-domain.com/api/auto-learning';

export class AutoLearningManager {
    constructor(dataProcessor, uiManager) {
        this.dataProcessor = dataProcessor;
        this.uiManager = uiManager;
        this.app = null; // 稍後由 App.init() 設置
        // this.apiEndpoint 已移除，改用 API_BASE_URL
        this.eventsBound = false;
        this.retryCount = 0;
        this.maxRetries = 5;

        // 🔧 配置：數據量限制（防止記憶體問題）
        this.MAX_OPTIMIZATION_DATA = 300; // 最多 300 期用於優化
        this.optimizationAborted = false; // 取消標誌

        // 🔧 P2 優化：API 狀態管理
        this.apiAvailable = null; // null = 未檢查, true = 可用, false = 不可用
        this.offlineMode = false; // 離線模式標誌

        this.init();
    }

    /**
     * 設置 App 實例引用（由 App.init() 調用）
     */
    setApp(app) {
        this.app = app;
    }

    // getApiEndpoint 已移除

    /**
     * 🔧 P2: API 健康檢查
     */
    async checkApiHealth() {
        // 使用兩個候選 URL 避免單一失敗：優先 127.0.0.1 其次 localhost
        // 先嘗試極速 /api/ping，再回退 /health
        const urls = [
            'http://127.0.0.1:5001/api/ping',
            'http://localhost:5001/api/ping',
            'http://127.0.0.1:5001/health',
            'http://localhost:5001/health'
        ];
        const TIMEOUT_MS = 15000; // 增加至 15 秒，避免優化期間暫時阻塞
        const MAX_ATTEMPTS = 2;   // 至少連續 2 次失敗才判定離線

        let success = false;
        this.backendBusy = false; // 重置忙碌標誌
        for (let attempt = 1; attempt <= MAX_ATTEMPTS && !success; attempt++) {
            for (const healthUrl of urls) {
                try {
                    console.log(`🔍 健康檢查 (嘗試 ${attempt}/${MAX_ATTEMPTS}): ${healthUrl}`);
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
                    const response = await fetch(healthUrl, {
                        method: 'GET',
                        signal: controller.signal,
                        mode: 'cors',
                        cache: 'no-cache'
                    });
                    clearTimeout(timeoutId);
                    if (response.ok) {
                        const data = await response.json();
                        // 解析 busy 狀態（/api/ping 或 /health 都可能包含）
                        if (typeof data.busy !== 'undefined' && data.busy) {
                            this.backendBusy = true;
                            console.log('⏳ 後端正在優化中 (busy=true)，但服務可用');
                        }
                        console.log(`✅ API 正常，使用端點: ${healthUrl}`, data);
                        // 正常化 baseUrl (移除 /health 或 /api/ping)
                        this.apiBaseUrl = healthUrl
                            .replace('/health', '')
                            .replace('/api/ping', '');
                        success = true;
                        break;
                    } else {
                        console.warn(`⚠️ 回應狀態碼: ${response.status} (${healthUrl})`);
                    }
                } catch (error) {
                    if (error.name === 'AbortError') {
                        console.warn(`⏱️ 健康檢查超時 (${(TIMEOUT_MS/1000)} 秒): ${healthUrl}`);
                    } else {
                        console.warn(`⚠️ 健康檢查錯誤 (${healthUrl}): ${error.name} - ${error.message}`);
                    }
                }
            }
            if (!success && attempt < MAX_ATTEMPTS) {
                // 適度延遲再嘗試（避免計算高峰期瞬間判斷離線）
                await new Promise(r => setTimeout(r, 1000));
            }
        }

        if (!success) {
            console.warn('⚠️ 無法連接後端（多次嘗試失敗），暫時進入離線模式');
        } else if (this.backendBusy) {
            // 顯示忙碌提示但不進入離線模式
            this.showBackendBusyBanner();
        }
        return success;
    }

    showBackendBusyBanner() {
        const section = document.getElementById('autolearning-section');
        if (!section) return;
        // 避免重複顯示
        if (section.querySelector('.backend-busy-banner')) return;
        const banner = document.createElement('div');
        banner.className = 'backend-busy-banner';
        banner.style.cssText = `
            background: linear-gradient(90deg, #6366f1, #8b5cf6);
            color: #fff;
            padding: 10px 16px;
            border-radius: 8px;
            margin-bottom: 14px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        `;
        banner.innerHTML = `
            <span style="font-size:18px">⏳</span>
            <div style="flex:1">
              後端正在執行優化任務，功能可用但回應可能較慢。
              <div style="opacity:0.85; margin-top:2px; font-size:12px;">請稍候完成或繼續瀏覽其它功能。</div>
            </div>
            <button style="background:rgba(255,255,255,0.25); border:0; color:#fff; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:12px;">關閉</button>
        `;
        const closeBtn = banner.querySelector('button');
        closeBtn.addEventListener('click', () => banner.remove());
        const header = section.querySelector('.section-header');
        if (header) header.insertAdjacentElement('afterend', banner); else section.insertBefore(banner, section.firstChild);
    }

    async init() {
        console.log('🤖 AutoLearningManager initializing...');

        // 🔧 P2: 檢查 API 可用性
        this.apiAvailable = await this.checkApiHealth();

        if (!this.apiAvailable) {
            console.warn('⚠️ 後端 API 未運行，自動學習功能將以離線模式運行');
            this.offlineMode = true;
        } else {
            console.log('✅ 後端 API 可用');
        }

        // 使用 requestAnimationFrame 確保在下一幀執行，而不是固定延遲
        requestAnimationFrame(() => {
            this.bindEvents();
            this.updateUIForMode();
        });
    }

    /**
     * 🔧 獲取當前彩票類型（健壯方法）
     * 優先順序: App.currentLotteryType > DOM active card > null
     */
    getCurrentLotteryType() {
        // 方法 1: 從 App 獲取
        let lotteryType = this.dataProcessor.app?.currentLotteryType;

        // 如果是空字符串或 undefined，嘗試從 DOM 獲取
        if (!lotteryType) {
            const activeCard = document.querySelector('.lottery-type-card.active');
            if (activeCard) {
                lotteryType = activeCard.dataset.type;
                console.log(`📌 從 DOM 獲取彩票類型: ${lotteryType}`);
            }
        }

        if (!lotteryType) {
            console.warn('⚠️ 未找到彩票類型:', {
                appCurrentType: this.dataProcessor.app?.currentLotteryType,
                domActiveCard: document.querySelector('.lottery-type-card.active'),
                allCards: document.querySelectorAll('.lottery-type-card').length
            });
        }

        return lotteryType || null;
    }

    /**
     * 🔧 P2: 根據模式更新 UI
     */
    updateUIForMode() {
        const section = document.getElementById('autolearning-section');
        if (!section) return;

        // 清除舊的 banner
        const existingBanner = section.querySelector('.offline-banner');
        if (existingBanner) {
            existingBanner.remove();
        }

        if (this.offlineMode) {
            // 在頂部添加離線模式提示
            const banner = document.createElement('div');
            banner.className = 'offline-banner';
            banner.style.cssText = `
                background: linear-gradient(135deg, #f59e0b, #d97706);
                color: white;
                padding: 12px 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                gap: 15px;
                font-size: 14px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            `;
            banner.innerHTML = `
                <span style="font-size: 24px;">⚠️</span>
                <div style="flex: 1;">
                    <strong>離線模式</strong> - 無法連接到後端 API
                    <br>
                    <small>請確保後端服務已啟動 (端口 5001)</small>
                </div>
                <button id="retry-connection-btn" style="
                    background: rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.4);
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 13px;
                    transition: all 0.2s;
                ">🔄 重試連接</button>
            `;

            // 插入到標題下方
            const header = section.querySelector('.section-header');
            if (header) {
                header.insertAdjacentElement('afterend', banner);
            } else {
                section.insertBefore(banner, section.firstChild);
            }

            // 綁定重試按鈕
            const retryBtn = banner.querySelector('#retry-connection-btn');
            retryBtn.addEventListener('click', async () => {
                retryBtn.innerHTML = '⏳ 連接中...';
                retryBtn.disabled = true;

                const isHealthy = await this.checkApiHealth();
                if (isHealthy) {
                    this.offlineMode = false;
                    this.apiAvailable = true;
                    this.updateUIForMode(); // 移除 banner 並啟用按鈕
                    this.uiManager.showNotification('✅ 已成功連接到後端 API', 'success');
                    this.refreshStatus();
                } else {
                    retryBtn.innerHTML = '❌ 連接失敗，點擊重試';
                    retryBtn.disabled = false;
                    this.uiManager.showNotification('❌ 仍然無法連接後端，請檢查終端', 'error');
                }
            });

            // 禁用需要 API 的按鈕
            const disableButtons = [
                'evaluate-strategies-btn',
                'run-optimization-btn',
                'start-schedule-btn',
                'update-schedule-btn',
                'stop-schedule-btn',
                'load-config-btn',
                'sync-data-btn' // 同步按鈕也應該禁用
            ];

            disableButtons.forEach(id => {
                const btn = document.getElementById(id);
                if (btn) {
                    btn.disabled = true;
                    btn.title = '離線模式下不可用';
                    btn.style.opacity = '0.6';
                    btn.style.cursor = 'not-allowed';
                }
            });
        } else {
            // 在線模式：啟用按鈕
            const enableButtons = [
                'evaluate-strategies-btn',
                'run-optimization-btn',
                'start-schedule-btn',
                'update-schedule-btn',
                'stop-schedule-btn',
                'load-config-btn',
                'sync-data-btn'
            ];

            enableButtons.forEach(id => {
                const btn = document.getElementById(id);
                if (btn) {
                    btn.disabled = false;
                    btn.title = '';
                    btn.style.opacity = '1';
                    btn.style.cursor = 'pointer';
                }
            });
        }
    }

    bindEvents() {
        const section = document.getElementById('autolearning-section');
        if (!section) {
            this.retryCount++;
            if (this.retryCount < this.maxRetries) {
                // 縮短重試間隔到 100ms，讓使用者感覺不到延遲
                console.warn(`⚠️ AutoLearning section not found! Retry ${this.retryCount}/${this.maxRetries}...`);
                setTimeout(() => this.bindEvents(), 100);
            } else {
                console.error('❌ Max retries reached! AutoLearning section not found.');
            }
            return;
        }

        // 避免重複綁定
        if (this.eventsBound) {
            console.log('⚠️ Events already bound, skipping...');
            return;
        }

        // 使用事件委派綁定所有按鈕點擊
        section.addEventListener('click', (e) => {
            const target = e.target.closest('button');
            if (!target) return;

            console.log(`🖱️ Clicked button: ${target.id}`);

            // 防止重複點擊
            if (target.disabled) {
                console.log('⚠️ Button is disabled, ignoring click');
                return;
            }

            try {
                switch (target.id) {
                    case 'evaluate-strategies-btn':
                        this.runStrategyEvaluation();
                        break;
                    case 'refresh-status-btn':
                        this.refreshStatus();
                        break;
                    case 'run-optimization-btn':
                        this.runOptimization();
                        break;
                    case 'start-schedule-btn':
                        this.startSchedule();
                        break;
                    case 'run-schedule-now-btn':
                        this.runScheduleNow();
                        break;
                    case 'stop-schedule-btn':
                        this.stopSchedule();
                        break;
                    case 'load-config-btn':
                        this.loadBestConfig();
                        break;
                    case 'set-target-fitness-btn':
                        this.setTargetFitness();
                        break;
                    case 'advanced-multi-stage-btn':
                        this.runAdvancedMultiStage();
                        break;
                    case 'advanced-adaptive-window-btn':
                        this.runAdvancedAdaptiveWindow();
                        break;
                    case 'view-optimization-results-btn':
                        this.viewOptimizationResults();
                        break;
                    default:
                        console.log(`⚠️ Unknown button: ${target.id}`);
                }
            } catch (error) {
                console.error('❌ Error handling button click:', error);
                this.uiManager.showNotification('操作失敗: ' + error.message, 'error');
            }
        });

        this.eventsBound = true;
        console.log('✅ AutoLearning events bound to section');

        // 如果在自動學習頁面，則初始化狀態
        if (section.classList.contains('active')) {
            console.log('📄 AutoLearning section active, refreshing status...');
            this.refreshStatus(true); // silent mode
        }

        // Event delegation for history table
        const historyTable = document.getElementById('optimization-history-table');
        if (historyTable) {
            historyTable.addEventListener('click', (e) => {
                if (e.target.classList.contains('view-details-btn')) {
                    const index = e.target.dataset.index;
                    this.showHistoryDetails(index);
                }
            });
        }
    }

    async refreshStatus(silent = false) {
        // 🔧 P2: 離線模式檢查
        if (this.offlineMode) {
            if (!silent) {
                console.log('⚠️ 離線模式，跳過狀態刷新');
            }
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/schedule/status`);
            if (!response.ok) throw new Error('獲取狀態失敗');

            const data = await response.json();

            // 更新排程狀態
            const statusEl = document.getElementById('schedule-status');
            const nextRunEl = document.getElementById('next-run-time');
            const fitnessEl = document.getElementById('best-fitness');

            if (statusEl) {
                statusEl.textContent = data.is_running ? '運行中' : '未啟動';
                statusEl.style.color = data.is_running ? '#10b981' : '#ef4444';
            }

            if (nextRunEl && data.jobs && data.jobs.length > 0) {
                const nextRun = new Date(data.jobs[0].next_run);
                nextRunEl.textContent = nextRun.toLocaleString('zh-TW');
            } else if (nextRunEl) {
                nextRunEl.textContent = '-';
            }

            // 🆕 顯示優化狀態
            if (data.is_optimizing) {
                // 正在優化中
                if (statusEl) {
                    statusEl.textContent = '🔄 優化中';
                    statusEl.style.color = '#f59e0b';
                }

                // 顯示進度訊息
                if (data.optimization_message && !silent) {
                    const progressText = `${data.optimization_message} (${data.current_generation}/${data.total_generations})`;
                    console.log(`📊 ${progressText}`);
                }

                // 如果還沒有輪詢計時器，啟動它
                if (!this.statusPollInterval) {
                    this.startStatusPolling();
                }
            } else {
                // 優化已完成或未運行，停止輪詢
                if (this.statusPollInterval) {
                    this.stopStatusPolling();
                }
            }

            // 更新最佳適應度
            if (fitnessEl && data.optimization_history && data.optimization_history.length > 0) {
                const latest = data.optimization_history[data.optimization_history.length - 1];
                fitnessEl.textContent = `${(latest.best_fitness * 100).toFixed(2)}%`;
                fitnessEl.style.color = '#667eea';
            }

            // 更新歷史記錄
            if (data.optimization_history) {
                this.updateHistoryTable(data.optimization_history);
            }

            // 🎯 更新目標適應度顯示
            const targetDisplay = document.getElementById('target-fitness-display');
            if (targetDisplay && typeof data.target_fitness !== 'undefined') {
                if (data.target_fitness) {
                    targetDisplay.textContent = `已設定: ${(data.target_fitness * 100).toFixed(1)}% (達標後停止)`;
                    targetDisplay.style.color = '#10b981';
                } else {
                    targetDisplay.textContent = '未設定（將執行完整 30 代）';
                    targetDisplay.style.color = '#666';
                }
            }

            if (!silent) {
                console.log('✅ 狀態已刷新', data);
            }

        } catch (error) {
            console.error('❌ 刷新狀態失敗:', error);
            if (!silent) {
                this.uiManager.showNotification('刷新狀態失敗: ' + error.message, 'error');
            }
        }
    }

    startStatusPolling() {
        if (this.statusPollInterval) return; // 避免重複啟動

        console.log('🔄 開始輪詢優化狀態...');
        this.statusPollInterval = setInterval(() => {
            this.refreshStatus(true); // silent mode
        }, 3000); // 每 3 秒輪詢一次
    }

    stopStatusPolling() {
        if (this.statusPollInterval) {
            clearInterval(this.statusPollInterval);
            this.statusPollInterval = null;
            console.log('⏹️ 停止輪詢優化狀態');
        }
    }

    async runOptimization() {
        // 🔧 P2: 離線模式檢查
        if (this.offlineMode) {
            this.uiManager.showNotification(
                '❌ 離線模式下無法使用遠程優化功能\n請啟動後端 API: cd lottery-api && python app.py',
                'error'
            );
            return;
        }

        const MAX_RETRIES = 3;
        let retryCount = 0;

        while (retryCount < MAX_RETRIES) {
            try {
                const generations = parseInt(document.getElementById('generations').value);
                const populationSize = parseInt(document.getElementById('population-size').value);

                // 🔧 修復：使用健壯方法獲取當前彩票類型
                const lotteryType = this.getCurrentLotteryType();

                if (!lotteryType) {
                    // 顯示用戶友好的錯誤訊息
                    this.uiManager.showNotification(
                        '❌ 請先選擇彩票類型\n\n' +
                        '步驟：\n' +
                        '1. 點擊左側導航的「📊 數據上傳」\n' +
                        '2. 選擇一個彩票類型卡片（如大樂透、威力彩等）\n' +
                        '3. 然後再回到「🤖 AI 自動學習」頁面進行優化',
                        'warning'
                    );
                    return; // 直接返回，不拋出異常
                }

                console.log(`🤖 Optimizing for lottery type: ${lotteryType}`);

                // 🔧 修復：從 LotteryTypes 獲取彩票規則
                const lotteryTypeConfig = getLotteryTypeById(lotteryType);

                if (!lotteryTypeConfig) {
                    throw new Error(`未知的彩票類型: ${lotteryType}`);
                }

                const lotteryRules = {
                    pickCount: lotteryTypeConfig.pickCount,
                    minNumber: lotteryTypeConfig.numberRange.min,
                    maxNumber: lotteryTypeConfig.numberRange.max,
                    hasSpecialNumber: lotteryTypeConfig.hasSpecialNumber || false
                };

                console.log(`🎯 彩票規則:`, lotteryRules);

                // 🔧 修復：強制限制數據量，防止記憶體問題
                let history = await this.dataProcessor.getDataSmart(lotteryType, this.MAX_OPTIMIZATION_DATA);

                // 二次檢查：如果仍然超過限制，強制截取
                if (history.length > this.MAX_OPTIMIZATION_DATA) {
                    console.warn(`⚠️ 數據量過大 (${history.length} 期)，截取最新 ${this.MAX_OPTIMIZATION_DATA} 期`);
                    history = history.slice(0, this.MAX_OPTIMIZATION_DATA);
                }

                console.log(`📊 Loaded ${history.length} records for optimization (限制: ${this.MAX_OPTIMIZATION_DATA})`);

                if (history.length < 50) {
                    throw new Error(`數據不足 (${history.length} 筆)，至少需要 50 期數據才能進行優化`);
                }

                // 顯示進度
                const progressDiv = document.getElementById('optimization-progress');
                const progressBar = document.getElementById('optimization-progress-bar');
                const progressStatus = document.getElementById('optimization-status');
                const btn = document.getElementById('run-optimization-btn');

                progressDiv.style.display = 'block';
                progressBar.style.width = '0%';
                progressStatus.textContent = '正在初始化...';
                btn.disabled = true;

                // 🔧 準備請求數據（匹配後端 API 格式）
                const requestData = {
                    history: history.map(draw => ({
                        date: draw.date,
                        draw: draw.draw || 0,
                        numbers: draw.numbers,
                        lotteryType: draw.lotteryType || lotteryType
                    })),
                    lotteryRules: {
                        pickCount: lotteryRules.pickCount,
                        minNumber: lotteryRules.minNumber,
                        maxNumber: lotteryRules.maxNumber,
                        hasSpecialNumber: lotteryRules.hasSpecialNumber
                    },
                    generations: generations,
                    population_size: populationSize,
                    lotteryType: lotteryType // ✅ 添加彩票類型，讓後端正確篩選數據
                };

                // 記錄數據大小
                const dataSize = JSON.stringify(requestData).length;
                console.log(`📦 請求數據大小: ${(dataSize / 1024).toFixed(2)} KB`);

                // 檢查數據大小，如果過大則警告並限制
                if (dataSize > 100 * 1024) { // 超過 100 KB
                    console.warn(`⚠️ 請求數據較大 (${(dataSize / 1024).toFixed(2)} KB)，自動限制到最新 ${this.MAX_OPTIMIZATION_DATA} 期`);
                }

                // 模擬進度（因為實際API不會返回進度）
                let progress = 0;
                const progressInterval = setInterval(() => {
                    progress = Math.min(progress + 5, 90);
                    progressBar.style.width = `${progress}%`;
                    progressStatus.textContent = `優化中... ${progress}%`;
                }, 1000);

                // 發送請求
                const response = await fetch(`${API_BASE_URL}/optimize`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData)
                });

                clearInterval(progressInterval);

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '優化失敗');
                }

                const result = await response.json();

                // 完成
                progressBar.style.width = '100%';
                progressStatus.textContent = '優化完成！';

                // 顯示結果
                this.uiManager.showNotification(
                    `✅ 優化完成！最佳適應度: ${(result.best_fitness * 100).toFixed(2)}%`,
                    'success'
                );

                // 繪製進化圖表
                if (result.fitness_history) {
                    this.renderEvolutionChart(result.fitness_history);
                }

                // 刷新狀態
                setTimeout(() => {
                    this.refreshStatus();
                    progressDiv.style.display = 'none';
                    btn.disabled = false;
                }, 2000);

                // 成功，跳出重試循環
                return;

            } catch (error) {
                retryCount++;

                // 🔧 P2: 改進錯誤處理和重試邏輯
                console.error('優化失敗詳情:', {
                    message: error.message,
                    stack: error.stack,
                    lotteryType: this.dataProcessor.app?.currentLotteryType,
                    timestamp: new Date().toISOString(),
                    retryCount: retryCount
                });

                // 分類錯誤並決定是否重試
                const isNetworkError = error.message.includes('fetch') ||
                    error.name === 'TypeError' ||
                    error.message.includes('Failed to fetch');

                const isValidationError = error.message.includes('請先選擇') ||
                    error.message.includes('未知的彩票類型');

                const isDataError = error.message.includes('數據不足');

                // 網絡錯誤：可重試
                if (isNetworkError && retryCount < MAX_RETRIES) {
                    console.warn(`⚠️ 網絡錯誤，${2}秒後重試 ${retryCount}/${MAX_RETRIES}...`);
                    this.uiManager.showNotification(
                        `⚠️ 網絡錯誤，正在重試 (${retryCount}/${MAX_RETRIES})...`,
                        'warning'
                    );
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    continue; // 重試
                }

                // 驗證錯誤或數據錯誤：不可重試
                let errorMessage = '優化失敗: ' + error.message;

                if (isValidationError) {
                    errorMessage = '❌ 請先選擇一個彩票類型再進行優化';
                } else if (isDataError) {
                    errorMessage = `❌ ${error.message}\n請確保有足夠的歷史數據`;
                } else if (isNetworkError) {
                    errorMessage = `❌ 網絡連接失敗 (已重試 ${retryCount} 次)\n請檢查後端 API 是否運行`;
                }

                this.uiManager.showNotification(errorMessage, 'error');
                document.getElementById('optimization-progress').style.display = 'none';
                document.getElementById('run-optimization-btn').disabled = false;

                // 不可重試的錯誤，跳出循環
                if (!isNetworkError) {
                    break;
                }
            }
        }
    }

    /**
     * 🆕 同步數據到後端（用於排程優化）
     */
    async syncDataToBackend() {
        try {
            const lotteryType = this.dataProcessor.app?.currentLotteryType;

            if (!lotteryType) {
                throw new Error('請先選擇一個彩票類型');
            }

            this.uiManager.showNotification('正在同步數據到後端...', 'info');

            // 🔧 獲取完整數據（不限制數量，limit=0 表示獲取所有數據）
            const history = await this.dataProcessor.getDataFromIndexedDB(lotteryType, 0);

            if (!history || history.length === 0) {
                throw new Error('無法獲取數據，請確保已載入彩票數據');
            }

            console.log(`📤 準備同步 ${history.length} 期數據到後端`);

            // 獲取彩票規則
            const lotteryTypeConfig = getLotteryTypeById(lotteryType);
            const lotteryRules = {
                pickCount: lotteryTypeConfig.pickCount,
                minNumber: lotteryTypeConfig.numberRange.min,
                maxNumber: lotteryTypeConfig.numberRange.max,
                hasSpecialNumber: lotteryTypeConfig.hasSpecialNumber || false
            };

            // 🔧 使用常量 URL
            const syncUrl = `${API_BASE_URL}/sync-data`;
            console.log(`🔍 同步 URL: ${syncUrl}`);

            // 發送到後端
            const response = await fetch(syncUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    history: history,
                    lotteryRules: lotteryRules
                })
            });

            if (!response.ok) throw new Error('數據同步失敗');

            const result = await response.json();
            this.uiManager.showNotification(
                `✅ ${result.message}\n後端將使用完整數據進行排程優化`,
                'success'
            );

            console.log(`✅ 數據同步成功: ${result.data_count} 期`);

            // 🆕 更新同步狀態顯示
            try {
                const lastTimeEl = document.getElementById('sync-last-time');
                const countEl = document.getElementById('sync-data-count');
                if (lastTimeEl) {
                    const now = new Date();
                    lastTimeEl.textContent = now.toLocaleString('zh-TW');
                }
                if (countEl && typeof result.data_count !== 'undefined') {
                    countEl.textContent = result.data_count.toLocaleString();
                }
            } catch (uiErr) {
                console.warn('更新同步狀態顯示失敗:', uiErr);
            }

        } catch (error) {
            console.error('數據同步失敗:', error);
            this.uiManager.showNotification('數據同步失敗: ' + error.message, 'error');
        }
    }

    async startSchedule() {
        try {
            const scheduleTime = document.getElementById('schedule-time').value;

            // 移除啟動排程前的同步數據
            // await this.syncDataToBackend();

            const response = await fetch(`${API_BASE_URL}/schedule/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ schedule_time: scheduleTime })
            });

            if (!response.ok) throw new Error('啟動排程失敗');

            const result = await response.json();
            this.uiManager.showNotification(result.message, 'success');
            this.refreshStatus();

        } catch (error) {
            console.error('啟動排程失敗:', error);
            this.uiManager.showNotification('啟動排程失敗: ' + error.message, 'error');
        }
    }

    async stopSchedule() {
        try {
            const response = await fetch(`${API_BASE_URL}/schedule/stop`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('停止排程失敗');

            const result = await response.json();
            this.uiManager.showNotification(result.message, 'success');
            this.refreshStatus();

        } catch (error) {
            console.error('停止排程失敗:', error);
            this.uiManager.showNotification('停止排程失敗: ' + error.message, 'error');
        }
    }

    async runScheduleNow() {
        try {
            console.log('⚡ 立即執行排程優化...');

            // 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification('❌ 離線模式下無法執行優化', 'error');
                return;
            }

            const btn = document.getElementById('run-schedule-now-btn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="btn-icon">⏳</span> 執行中...';
            }

            this.uiManager.showNotification('🚀 開始執行優化，請稍候...', 'info');

            const response = await fetch(`${API_BASE_URL}/schedule/run-now`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.message || '執行失敗');
            }

            const result = await response.json();

            if (result.success) {
                this.uiManager.showNotification(
                    `✅ 優化任務已啟動（後台執行）\n使用數據: ${result.data_count} 期`,
                    'success'
                );
                // 刷新狀態顯示並啟動輪詢
                this.refreshStatus();
                this.startStatusPolling(); // 開始輪詢進度
            } else {
                this.uiManager.showNotification(`❌ ${result.message}`, 'error');
            }

        } catch (error) {
            console.error('立即執行失敗:', error);
            this.uiManager.showNotification('立即執行失敗: ' + error.message, 'error');
        } finally {
            const btn = document.getElementById('run-schedule-now-btn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span class="btn-icon">⚡</span> 立即執行一次';
            }
        }
    }

    async setTargetFitness() {
        try {
            console.log('🎯 設定目標適應度...');

            // 🔧 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification('❌ 離線模式下無法設定目標適應度', 'error');
                return;
            }

            const input = document.getElementById('target-fitness-input');
            const targetValue = input.value.trim();

            let target = null;
            if (targetValue) {
                target = parseFloat(targetValue);
                if (isNaN(target) || target <= 0 || target > 1) {
                    this.uiManager.showNotification(
                        '❌ 目標適應度必須在 0 到 1 之間\n例如：0.05 (5%)',
                        'error'
                    );
                    return;
                }
            }

            const response = await fetch(`${API_BASE_URL}/set-target-fitness`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_fitness: target })
            });

            if (!response.ok) {
                throw new Error('設定失敗');
            }

            const result = await response.json();

            // 更新顯示
            const display = document.getElementById('target-fitness-display');
            if (display) {
                if (target) {
                    display.textContent = `已設定: ${(target * 100).toFixed(1)}% (達標後停止)`;
                    display.style.color = '#10b981';
                } else {
                    display.textContent = '未設定（將執行完整 30 代）';
                    display.style.color = '#666';
                }
            }

            this.uiManager.showNotification(
                result.message || '✅ 設定成功',
                'success'
            );

        } catch (error) {
            console.error('❌ 設定目標適應度失敗:', error);
            this.uiManager.showNotification('設定失敗: ' + error.message, 'error');
        }
    }

    async loadBestConfig() {
        try {
            console.log('📥 開始載入最佳配置...');

            // 🔧 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification('❌ 離線模式下無法載入配置', 'error');
                return;
            }
            
            const response = await fetch(`${API_BASE_URL}/best-config`);
            console.log('📡 API 回應狀態:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ API 錯誤回應:', errorText);
                throw new Error('載入配置失敗');
            }
            
            const result = await response.json();
            console.log('📦 收到配置數據:', result);

            if (!result.config || Object.keys(result.config).length === 0) {
                console.warn('⚠️ 配置為空');
                this.uiManager.showNotification(
                    '尚無最佳配置\n\n' +
                    '💡 說明：\n' +
                    '• 「智能策略評估」會找出最佳策略名稱\n' +
                    '• 「自動優化」會產生權重配置參數\n' +
                    '• 「載入最佳配置」顯示自動優化的權重參數\n\n' +
                    '請執行「自動優化」來產生配置數據',
                    'warning'
                );
                return;
            }

            // 顯示配置
            this.displayConfig(result.config);
            this.uiManager.showNotification('✅ 配置已載入', 'success');

        } catch (error) {
            console.error('❌ 載入配置失敗:', error);
            this.uiManager.showNotification('載入配置失敗: ' + error.message, 'error');
        }
    }

    displayConfig(config) {
        const display = document.getElementById('best-config-display');

        let html = '<div class="config-grid">';

        for (const [key, value] of Object.entries(config)) {
            const displayValue = typeof value === 'number'
                ? value.toFixed(4)
                : value;

            html += `
                <div class="config-item">
                    <span class="key">${key}:</span>
                    <span class="value">${displayValue}</span>
                </div>
            `;
        }

        html += '</div>';
        display.innerHTML = html;
    }

    updateHistoryTable(history) {
        this.optimizationHistory = history; // Store history for access
        const tbody = document.querySelector('#optimization-history-table tbody');

        if (!history || history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="placeholder-text">暫無優化歷史</td></tr>';
            return;
        }

        // Reverse to show latest first
        tbody.innerHTML = [...history].reverse().map((record, index) => {
            // Calculate original index (since we reversed)
            const originalIndex = history.length - 1 - index;

            const time = new Date(record.timestamp).toLocaleString('zh-TW');
            const fitness = (record.best_fitness * 100).toFixed(2);
            const fitnessClass =
                record.best_fitness > 0.05 ? 'fitness-good' :
                    record.best_fitness > 0.02 ? 'fitness-medium' : 'fitness-low';

            return `
                <tr>
                    <td>${time}</td>
                    <td>${record.generations}</td>
                    <td><span class="fitness-badge ${fitnessClass}">${fitness}%</span></td>
                    <td>${fitness}%</td>
                    <td>
                        <button class="btn btn-secondary view-details-btn" data-index="${originalIndex}" style="padding: 4px 8px; font-size: 0.8rem;">
                            查看詳情
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    renderEvolutionChart(history) {
        const ctx = document.getElementById('evolution-chart');
        if (!ctx) return;

        if (this.evolutionChart) {
            this.evolutionChart.destroy();
        }

        // 確保 Chart.js 已載入
        if (typeof Chart === 'undefined') {
            console.error('Chart.js not loaded');
            return;
        }

        this.evolutionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: history.map((_, i) => `第 ${i + 1} 代`),
                datasets: [{
                    label: '最佳適應度 (成功率 %)',
                    data: history.map(v => v * 100), // 轉為百分比
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#e5e7eb' }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function (context) {
                                return `成功率: ${context.parsed.y.toFixed(2)}%`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#9ca3af' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#9ca3af' }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }

    showHistoryDetails(index) {
        if (!this.optimizationHistory || !this.optimizationHistory[index]) {
            console.error('History record not found for index:', index);
            return;
        }

        const record = this.optimizationHistory[index];
        const config = record.best_config;

        let message = `📅 時間: ${new Date(record.timestamp).toLocaleString('zh-TW')}\n`;
        message += `📊 適應度: ${(record.best_fitness * 100).toFixed(2)}%\n`;
        message += `🧬 遺傳代數: ${record.generations}\n\n`;
        message += `🔧 配置詳情:\n`;

        for (const [key, value] of Object.entries(config)) {
            const displayValue = typeof value === 'number' ? value.toFixed(4) : value;
            message += `${key}: ${displayValue}\n`;
        }

        alert(message);
    }

    /**
     * 🆕 運行智能策略評估
     * 自動測試所有預測策略，找出最佳方法
     */
    async runStrategyEvaluation() {
        const btn = document.getElementById('evaluate-strategies-btn');
        const progress = document.getElementById('evaluation-progress');
        const progressBar = document.getElementById('evaluation-progress-bar');
        const statusText = document.getElementById('evaluation-status');
        const bestInfo = document.getElementById('best-strategy-info');
        const bestContent = document.getElementById('best-strategy-content');
        const allCard = document.getElementById('all-strategies-card');
        const allTable = document.getElementById('all-strategies-table');
        const testRatio = parseFloat(document.getElementById('test-ratio-select').value) || 0.2;

        try {
            // 獲取當前彩券類型
            const lotteryType = this.getCurrentLotteryType();
            if (!lotteryType) {
                this.uiManager.showNotification('請先選擇一個彩券類型', 'warning');
                return;
            }

            // 禁用按鈕，顯示進度
            btn.disabled = true;
            btn.innerHTML = '<span class="btn-icon">⏳</span>評估中...';
            progress.style.display = 'block';
            bestInfo.style.display = 'none';
            allCard.style.display = 'none';

            progressBar.style.width = '10%';
            statusText.textContent = '正在連接後端...';

            this.uiManager.showNotification('開始評估所有策略，請稍候...', 'info');

            // 調用後端 API
            const apiUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
                ? 'http://localhost:5001/api/auto-learning/evaluate-strategies'
                : 'https://your-api-domain.com/api/auto-learning/evaluate-strategies';

            progressBar.style.width = '30%';
            statusText.textContent = '正在評估策略...';

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lotteryType: lotteryType,
                    test_ratio: testRatio,
                    min_train_size: 30
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `API 錯誤: ${response.status}`);
            }

            const result = await response.json();

            progressBar.style.width = '100%';
            statusText.textContent = '評估完成！';

            // 顯示最佳策略
            const best = result.best_strategy;
            const metrics = best.metrics;

            bestContent.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">策略名稱</div>
                        <div style="font-size: 1.5em; font-weight: bold; margin-top: 5px;">
                            ${best.strategy_name}
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">綜合評分</div>
                        <div style="font-size: 1.5em; font-weight: bold; margin-top: 5px;">
                            ${best.score.toFixed(2)} 分
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">成功率</div>
                        <div style="font-size: 1.2em; font-weight: bold; margin-top: 5px;">
                            ${(metrics.success_rate * 100).toFixed(2)}%
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">vs 理論值</div>
                        <div style="font-size: 1.2em; font-weight: bold; margin-top: 5px;">
                            ${metrics.vs_theory.toFixed(1)}x
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">平均命中數</div>
                        <div style="font-size: 1.2em; font-weight: bold; margin-top: 5px;">
                            ${metrics.avg_hits.toFixed(2)} 個
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.9em; opacity: 0.8;">測試期數</div>
                        <div style="font-size: 1.2em; font-weight: bold; margin-top: 5px;">
                            ${metrics.total_tests} 期
                        </div>
                    </div>
                </div>
            `;
            bestInfo.style.display = 'block';

            // 顯示所有策略結果
            const allResults = result.all_results;
            let tableHTML = `
                <table style="width: 100%; border-collapse: collapse; background: rgba(0,0,0,0.2);">
                    <thead>
                        <tr style="background: rgba(0,0,0,0.3);">
                            <th style="padding: 12px; text-align: left; color: #e5e7eb;">排名</th>
                            <th style="padding: 12px; text-align: left; color: #e5e7eb;">策略名稱</th>
                            <th style="padding: 12px; text-align: right; color: #e5e7eb;">評分</th>
                            <th style="padding: 12px; text-align: right; color: #e5e7eb;">成功率</th>
                            <th style="padding: 12px; text-align: right; color: #e5e7eb;">平均命中</th>
                            <th style="padding: 12px; text-align: right; color: #e5e7eb;">vs 理論</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            let rank = 1;
            for (const [id, data] of Object.entries(allResults)) {
                const isError = !data.metrics;
                const rowStyle = rank === 1 ? 'background: rgba(255, 215, 0, 0.1); font-weight: bold;' : '';

                if (isError) {
                    tableHTML += `
                        <tr style="${rowStyle}">
                            <td style="padding: 10px;">${rank}</td>
                            <td style="padding: 10px;">${data.name}</td>
                            <td style="padding: 10px; text-align: right;" colspan="4">
                                <span style="color: #ef4444;">評估失敗</span>
                            </td>
                        </tr>
                    `;
                } else {
                    const m = data.metrics;
                    tableHTML += `
                        <tr style="${rowStyle}">
                            <td style="padding: 10px;">
                                ${rank === 1 ? '🏆' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank}
                            </td>
                            <td style="padding: 10px;">${data.name}</td>
                            <td style="padding: 10px; text-align: right;">${data.score.toFixed(2)}</td>
                            <td style="padding: 10px; text-align: right;">${(m.success_rate * 100).toFixed(2)}%</td>
                            <td style="padding: 10px; text-align: right;">${m.avg_hits.toFixed(2)}</td>
                            <td style="padding: 10px; text-align: right;">${m.vs_theory.toFixed(1)}x</td>
                        </tr>
                    `;
                }
                rank++;
            }

            tableHTML += '</tbody></table>';
            allTable.innerHTML = tableHTML;
            allCard.style.display = 'block';

            this.uiManager.showNotification(
                `評估完成！最佳策略: ${best.strategy_name} (評分 ${best.score.toFixed(2)} 分)`,
                'success'
            );

            // 🆕 評估完成後，更新「載入最佳配置」按鈕的提示
            const loadConfigBtn = document.getElementById('load-config-btn');
            if (loadConfigBtn) {
                loadConfigBtn.title = '智能策略評估只產生最佳策略建議，不會產生權重配置。\n如需權重配置，請執行「自動優化」。';
            }

            // 🆕 評估完成後，使用最佳策略進行雙注預測
            // 使用 requestAnimationFrame 確保在下一個繪製週期執行，避免渲染衝突
            requestAnimationFrame(() => {
                this.generateDualBetPrediction(lotteryType, best);
            });

        } catch (error) {
            console.error('策略評估失敗:', error);
            this.uiManager.showNotification(
                '策略評估失敗: ' + error.message,
                'error'
            );
            statusText.textContent = '評估失敗';
        } finally {
            // 恢復按鈕
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">🔍</span>開始評估策略';

            // 3 秒後僅隱藏進度條
            setTimeout(() => {
                if (progress) {
                    progress.style.display = 'none';
                }
                if (progressBar) {
                    progressBar.style.width = '0%';
                }
            }, 3000);
        }
    }

    /**
     * 🆕 生成雙注優化預測（基於最佳策略）
     */
    async generateDualBetPrediction(lotteryType, bestStrategy) {
        try {
            console.log('🎯 開始生成雙注預測，使用最佳策略:', bestStrategy.strategy_name);

            // 檢查 App 實例是否已設置
            if (!this.app) {
                console.error('App 實例未設置，無法執行雙注預測');
                this.uiManager.showNotification('系統初始化未完成，請稍後再試', 'error');
                return;
            }

            // 獲取當前樣本大小
            const sampleSizeInput = document.getElementById('sample-size');
            const sampleSize = sampleSizeInput ? sampleSizeInput.value : 50;

            // 所有可用策略列表
            const strategies = [
                'frequency', 'trend', 'bayesian', 'markov', 'montecarlo', 'deviation',
                'odd_even', 'zone_balance', 'hot_cold', 'sum_range', 'number_pairs',
                'ensemble_weighted', 'ensemble_combined', 'ensemble_advanced'
            ];

            // 收集所有策略的預測結果
            const allResults = [];
            for (const strategy of strategies) {
                try {
                    const result = await this.app.predictionEngine.predict(strategy, sampleSize, lotteryType, true);
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
            const lotteryRules = this.app.getLotteryRulesFromType(lotteryType);
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

            // 計算各自的信心度
            const bet1Score = bet1Numbers.reduce((sum, num) => sum + numberScores[num], 0) / 6;
            const bet2Score = bet2Numbers.reduce((sum, num) => sum + numberScores[num], 0) / 6;
            const maxScore = Math.max(...Object.values(numberScores));
            const bet1Confidence = Math.min(95, (bet1Score / maxScore) * 100);
            const bet2Confidence = Math.min(95, (bet2Score / maxScore) * 100);
            const avgConfidence = (bet1Confidence + bet2Confidence) / 2;

            // 顯示結果在評估頁面的元素中
            const dualBetCard = document.getElementById('eval-dual-bet-card');
            if (dualBetCard) {
                dualBetCard.style.display = 'block';
                
                // 平滑滾動到雙注預測卡片
                setTimeout(() => {
                    dualBetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }, 100);
            }

            // 填充第一注
            const bet1NumbersEl = document.getElementById('eval-dual-bet-numbers-1');
            const bet1ConfidenceEl = document.getElementById('eval-dual-bet-confidence-1');
            if (bet1NumbersEl) {
                bet1NumbersEl.innerHTML = bet1Numbers
                    .map(num => `<span class="ball">${num}</span>`)
                    .join('');
            }
            if (bet1ConfidenceEl) {
                bet1ConfidenceEl.textContent = `${bet1Confidence.toFixed(1)}%`;
            }

            // 填充第二注
            const bet2NumbersEl = document.getElementById('eval-dual-bet-numbers-2');
            const bet2ConfidenceEl = document.getElementById('eval-dual-bet-confidence-2');
            if (bet2NumbersEl) {
                bet2NumbersEl.innerHTML = bet2Numbers
                    .map(num => `<span class="ball">${num}</span>`)
                    .join('');
            }
            if (bet2ConfidenceEl) {
                bet2ConfidenceEl.textContent = `${bet2Confidence.toFixed(1)}%`;
            }

            // 填充統計信息
            const strategyNameEl = document.getElementById('eval-dual-bet-strategy');
            const overallConfidenceEl = document.getElementById('eval-dual-bet-overall-confidence');
            if (strategyNameEl) {
                strategyNameEl.textContent = bestStrategy.strategy_name;
            }
            if (overallConfidenceEl) {
                overallConfidenceEl.textContent = `${avgConfidence.toFixed(1)}%`;
            }

            // 填充報告
            const reportEl = document.getElementById('eval-dual-bet-report');
            if (reportEl) {
                reportEl.innerHTML = `
                    <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin-top: 10px;">
                        <h4 style="margin: 0 0 10px 0; color: #e5e7eb;">📋 預測報告</h4>
                        <p style="margin: 5px 0; color: #d1d5db;">
                            ✅ 使用評估中表現最佳的 <strong>${bestStrategy.strategy_name}</strong> 策略生成預測
                        </p>
                        <p style="margin: 5px 0; color: #d1d5db;">
                            📊 該策略在測試中的成功率: <strong>${(bestStrategy.metrics.success_rate * 100).toFixed(2)}%</strong>
                        </p>
                        <p style="margin: 5px 0; color: #d1d5db;">
                            🎯 整合 ${allResults.length} 個策略，兩注共覆蓋 12 個最佳候選號碼
                        </p>
                        <p style="margin: 5px 0; font-size: 0.85em; color: #9ca3af;">
                            ⚠️ 此為基於統計模型的預測，彩票本質是隨機的，僅供參考
                        </p>
                    </div>
                `;
            }

            console.log('✅ 雙注預測完成並顯示');
            
            // 確保所有策略結果表格仍然顯示
            const allStrategiesCard = document.getElementById('all-strategies-card');
            if (allStrategiesCard && allStrategiesCard.innerHTML.trim()) {
                allStrategiesCard.style.display = 'block';
            }
        } catch (error) {
            console.error('❌ 雙注預測失敗:', error);
            this.uiManager.showNotification(`雙注預測失敗: ${error.message}`, 'error');
        }
    }

    /**
     * 🚀 執行多階段優化（進階功能）
     */
    async runAdvancedMultiStage() {
        try {
            // 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification(
                    '❌ 離線模式下無法使用進階優化功能\n請啟動後端 API: cd lottery-api && python3 app.py',
                    'error'
                );
                return;
            }

            // 獲取當前彩票類型
            const lotteryType = this.getCurrentLotteryType();
            if (!lotteryType) {
                this.uiManager.showNotification(
                    '❌ 請先選擇彩票類型\n\n' +
                    '步驟：\n' +
                    '1. 點擊左側導航的「📊 數據上傳」\n' +
                    '2. 選擇一個彩票類型卡片（如大樂透、威力彩等）\n' +
                    '3. 然後再回到「🤖 AI 自動學習」頁面進行優化',
                    'warning'
                );
                return;
            }

            // 禁用按鈕並顯示進度區域
            const btn = document.getElementById('advanced-multi-stage-btn');
            const progressDiv = document.getElementById('advanced-optimization-progress');
            const resultDiv = document.getElementById('advanced-optimization-result');

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '⏳ 優化中...';
            }
            if (progressDiv) {
                progressDiv.style.display = 'block';
            }
            if (resultDiv) {
                resultDiv.style.display = 'none';
            }

            console.log('🚀 開始多階段優化...');
            this.uiManager.showNotification(
                '🚀 多階段優化已啟動（後台執行）\n預計耗時: 10-15 分鐘',
                'info'
            );

            // 更新進度顯示
            this.updateAdvancedProgress(0, '正在啟動多階段優化...', 'multi_stage');

            // 調用後端 API
            const response = await fetch(`${API_BASE_URL}/advanced/multi-stage`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lotteryType: lotteryType })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '多階段優化啟動失敗');
            }

            const result = await response.json();

            if (result.success) {
                // 啟動進度輪詢
                this.startAdvancedOptimizationPolling('multi_stage');
            } else {
                throw new Error(result.message || '啟動失敗');
            }

        } catch (error) {
            console.error('❌ 多階段優化失敗:', error);
            this.uiManager.showNotification('多階段優化失敗: ' + error.message, 'error');

            // 隱藏進度，恢復按鈕
            const progressDiv = document.getElementById('advanced-optimization-progress');
            if (progressDiv) progressDiv.style.display = 'none';

            const btn = document.getElementById('advanced-multi-stage-btn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '執行多階段優化';
            }
        }
    }

    /**
     * 🔍 執行自適應窗口優化（進階功能）
     */
    async runAdvancedAdaptiveWindow() {
        try {
            // 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification(
                    '❌ 離線模式下無法使用進階優化功能\n請啟動後端 API: cd lottery-api && python3 app.py',
                    'error'
                );
                return;
            }

            // 獲取當前彩票類型
            const lotteryType = this.getCurrentLotteryType();
            if (!lotteryType) {
                this.uiManager.showNotification(
                    '❌ 請先選擇彩票類型\n\n' +
                    '步驟：\n' +
                    '1. 點擊左側導航的「📊 數據上傳」\n' +
                    '2. 選擇一個彩票類型卡片（如大樂透、威力彩等）\n' +
                    '3. 然後再回到「🤖 AI 自動學習」頁面進行優化',
                    'warning'
                );
                return;
            }

            // 禁用按鈕並顯示進度區域
            const btn = document.getElementById('advanced-adaptive-window-btn');
            const progressDiv = document.getElementById('advanced-optimization-progress');
            const resultDiv = document.getElementById('advanced-optimization-result');

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '⏳ 優化中...';
            }
            if (progressDiv) {
                progressDiv.style.display = 'block';
            }
            if (resultDiv) {
                resultDiv.style.display = 'none';
            }

            console.log('🔍 開始自適應窗口優化...');
            this.uiManager.showNotification(
                '🔍 自適應窗口優化已啟動（後台執行）\n預計耗時: 5-8 分鐘',
                'info'
            );

            // 更新進度顯示
            this.updateAdvancedProgress(0, '正在啟動自適應窗口優化...', 'adaptive_window');

            // 調用後端 API
            const response = await fetch(`${API_BASE_URL}/advanced/adaptive-window`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lotteryType: lotteryType })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '自適應窗口優化啟動失敗');
            }

            const result = await response.json();

            if (result.success) {
                // 啟動進度輪詢
                this.startAdvancedOptimizationPolling('adaptive_window');
            } else {
                throw new Error(result.message || '啟動失敗');
            }

        } catch (error) {
            console.error('❌ 自適應窗口優化失敗:', error);
            this.uiManager.showNotification('自適應窗口優化失敗: ' + error.message, 'error');

            // 隱藏進度，恢復按鈕
            const progressDiv = document.getElementById('advanced-optimization-progress');
            if (progressDiv) progressDiv.style.display = 'none';

            const btn = document.getElementById('advanced-adaptive-window-btn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '執行自適應窗口優化';
            }
        }
    }

    /**
     * 更新進階優化進度顯示
     */
    updateAdvancedProgress(percentage, status, method) {
        const progressBar = document.getElementById('advanced-progress-bar');
        const progressPercentage = document.getElementById('advanced-progress-percentage');
        const progressStatus = document.getElementById('advanced-progress-status');
        const progressTitle = document.getElementById('advanced-progress-title');

        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
        if (progressPercentage) {
            progressPercentage.textContent = `${Math.round(percentage)}%`;
        }
        if (progressStatus) {
            progressStatus.textContent = status;
        }
        if (progressTitle) {
            const methodName = method === 'multi_stage' ? '多階段優化' : '自適應窗口優化';
            progressTitle.textContent = `${methodName}進行中...`;
        }
    }

    /**
     * 啟動進階優化進度輪詢
     */
    startAdvancedOptimizationPolling(method) {
        // 停止舊的輪詢
        if (this.advancedOptimizationPollInterval) {
            clearInterval(this.advancedOptimizationPollInterval);
        }

        console.log('🔄 開始輪詢進階優化進度...');

        let elapsedTime = 0;
        const totalTime = method === 'multi_stage' ? 15 * 60 : 8 * 60; // 秒

        // 模擬進度（因為後端可能沒有實時進度報告）
        this.advancedOptimizationPollInterval = setInterval(async () => {
            elapsedTime += 3;
            const progress = Math.min(95, (elapsedTime / totalTime) * 100);

            // 更新進度顯示
            let statusMessage = '';
            if (method === 'multi_stage') {
                if (progress < 25) {
                    statusMessage = '階段 1: 粗調 (50代) - 快速探索解空間...';
                } else if (progress < 75) {
                    statusMessage = '階段 2: 精調 (100代) - 深度優化參數...';
                } else {
                    statusMessage = '階段 3: 微調 (50代) - 精確調整...';
                }
            } else {
                const windows = ['100期', '200期', '300期', '500期', '全部數據'];
                const windowIndex = Math.floor(progress / 20);
                statusMessage = `正在測試 ${windows[windowIndex] || windows[4]} 窗口...`;
            }

            this.updateAdvancedProgress(progress, statusMessage, method);

            // 🔧 檢查進階優化專用狀態端點
            try {
                const response = await fetch(`${API_BASE_URL}/advanced/status`);
                if (response.ok) {
                    const data = await response.json();

                    // 檢查是否有最新的優化記錄
                    if (data.success && data.latest_optimization) {
                        const latestAdvanced = data.latest_optimization;

                        // 檢查是否是當前方法的最新結果
                        if (latestAdvanced.method === method) {
                            const timestamp = new Date(latestAdvanced.timestamp);
                            const now = new Date();
                            const diffMinutes = (now - timestamp) / 1000 / 60;

                            // 如果是最近2分鐘內完成的
                            if (diffMinutes < 2) {
                                console.log('✅ 檢測到優化完成:', latestAdvanced);
                                clearInterval(this.advancedOptimizationPollInterval);
                                this.updateAdvancedProgress(100, '優化完成！', method);
                                setTimeout(() => {
                                    this.showAdvancedOptimizationResult(latestAdvanced, method);
                                }, 500);
                                return;
                            }
                        }
                    }
                }
            } catch (error) {
                console.warn('檢查進階優化狀態失敗:', error);
                // 降級：嘗試檢查常規狀態端點
                try {
                    const response = await fetch(`${API_BASE_URL}/schedule/status`);
                    if (response.ok) {
                        const data = await response.json();

                        if (data.advanced_optimization_history && data.advanced_optimization_history.length > 0) {
                            const latestAdvanced = data.advanced_optimization_history[data.advanced_optimization_history.length - 1];

                            if (latestAdvanced.method === method) {
                                const timestamp = new Date(latestAdvanced.timestamp);
                                const now = new Date();
                                const diffMinutes = (now - timestamp) / 1000 / 60;

                                if (diffMinutes < 2) {
                                    clearInterval(this.advancedOptimizationPollInterval);
                                    this.updateAdvancedProgress(100, '優化完成！', method);
                                    setTimeout(() => {
                                        this.showAdvancedOptimizationResult(latestAdvanced, method);
                                    }, 500);
                                    return;
                                }
                            }
                        }
                    }
                } catch (fallbackError) {
                    console.warn('降級檢查也失敗:', fallbackError);
                }
            }

            // 超時保護（最多輪詢30分鐘）
            if (elapsedTime > 30 * 60) {
                clearInterval(this.advancedOptimizationPollInterval);
                this.uiManager.showNotification('⏱️ 優化超時，請檢查後端日誌', 'warning');

                // 恢復UI
                const progressDiv = document.getElementById('advanced-optimization-progress');
                if (progressDiv) progressDiv.style.display = 'none';

                const btn = document.getElementById(
                    method === 'multi_stage' ? 'advanced-multi-stage-btn' : 'advanced-adaptive-window-btn'
                );
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = method === 'multi_stage' ? '執行多階段優化' : '執行自適應窗口優化';
                }
            }
        }, 3000); // 每3秒更新一次
    }

    /**
     * 顯示進階優化結果
     */
    showAdvancedOptimizationResult(result, method) {
        console.log('✅ 顯示優化結果:', result);

        const progressDiv = document.getElementById('advanced-optimization-progress');
        const resultDiv = document.getElementById('advanced-optimization-result');

        // 隱藏進度，顯示結果
        if (progressDiv) progressDiv.style.display = 'none';
        if (resultDiv) resultDiv.style.display = 'block';

        // 更新結果數據
        const fitnessEl = document.getElementById('advanced-result-fitness');
        const improvementEl = document.getElementById('advanced-result-improvement');
        const methodEl = document.getElementById('advanced-result-method');
        const detailsEl = document.getElementById('advanced-result-details');

        const baseline = 0.0361; // 基準線
        const fitness = result.best_fitness || 0;
        const improvement = ((fitness - baseline) / baseline * 100);

        if (fitnessEl) {
            fitnessEl.textContent = `${(fitness * 100).toFixed(2)}%`;
        }
        if (improvementEl) {
            improvementEl.textContent = `+${improvement.toFixed(1)}%`;
        }
        if (methodEl) {
            methodEl.textContent = method === 'multi_stage' ? '多階段' : '自適應窗口';
        }

        // 顯示詳細信息
        if (detailsEl) {
            let detailsHTML = `
                <div style="margin-bottom: 10px;">
                    <strong>📊 優化統計：</strong>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px;">
                    <div>• 優化時間: ${new Date(result.timestamp).toLocaleString('zh-TW')}</div>
                    <div>• 遺傳代數: ${result.generations}</div>
                    <div>• 基準成功率: ${(baseline * 100).toFixed(2)}%</div>
                    <div>• 最佳成功率: ${(fitness * 100).toFixed(2)}%</div>
                </div>
            `;

            if (method === 'multi_stage' && result.stage_results) {
                detailsHTML += `
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2);">
                        <strong>📈 各階段結果：</strong>
                        <div style="margin-top: 10px;">
                            ${result.stage_results.map(stage =>
                                `<div>• ${stage.stage}: ${(stage.best_fitness * 100).toFixed(2)}%</div>`
                            ).join('')}
                        </div>
                    </div>
                `;
            }

            if (method === 'adaptive_window' && result.best_window_size) {
                detailsHTML += `
                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2);">
                        <strong>🔍 最佳窗口：</strong>
                        <div style="margin-top: 10px;">
                            • 最佳數據窗口: ${result.best_window_size} 期
                        </div>
                    </div>
                `;
            }

            detailsEl.innerHTML = detailsHTML;
        }

        // 恢復按鈕
        const btn = document.getElementById(
            method === 'multi_stage' ? 'advanced-multi-stage-btn' : 'advanced-adaptive-window-btn'
        );
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = method === 'multi_stage' ? '執行多階段優化' : '執行自適應窗口優化';
        }

        // 顯示成功通知
        this.uiManager.showNotification(
            `🎉 ${method === 'multi_stage' ? '多階段優化' : '自適應窗口優化'}完成！\n` +
            `最佳適應度: ${(fitness * 100).toFixed(2)}%\n` +
            `提升幅度: +${improvement.toFixed(1)}%`,
            'success'
        );

        // 刷新優化歷史
        this.refreshStatus();
    }

    async viewOptimizationResults() {
        /**
         * 📊 查看優化結果詳情
         * 顯示所有執行過的優化記錄，包括最佳配置和歷史數據
         */
        try {
            console.log('📊 查看優化結果...');

            const panel = document.getElementById('optimization-results-panel');
            const content = document.getElementById('optimization-results-content');

            if (!panel || !content) {
                console.error('優化結果面板元素不存在');
                return;
            }

            // 離線模式檢查
            if (this.offlineMode) {
                this.uiManager.showNotification('❌ 離線模式下無法查詢優化結果', 'error');
                return;
            }

            // 獲取當前彩券類型
            const lotteryType = this.app?.currentLotteryType || 'BIG_LOTTO';

            // 顯示加載狀態
            content.innerHTML = '<div style="text-align: center; padding: 20px;">⏳ 正在載入優化結果...</div>';
            panel.style.display = 'block';

            // 調用後端 API
            const response = await fetch(
                `${API_BASE_URL}/optimization-history?lottery_type=${lotteryType}`
            );

            if (!response.ok) {
                throw new Error('獲取優化結果失敗');
            }

            const data = await response.json();

            // 渲染結果
            this.renderOptimizationResults(data, content);

        } catch (error) {
            console.error('查看優化結果失敗:', error);
            this.uiManager.showNotification('查看優化結果失敗: ' + error.message, 'error');
            
            const content = document.getElementById('optimization-results-content');
            if (content) {
                content.innerHTML = `
                    <div style="text-align: center; padding: 20px; color: #ef4444;">
                        ❌ 載入失敗: ${error.message}
                    </div>
                `;
            }
        }
    }

    renderOptimizationResults(data, contentEl) {
        /**
         * 渲染優化結果到面板
         */
        if (!data.success || !data.history || data.history.length === 0) {
            contentEl.innerHTML = `
                <div style="text-align: center; padding: 20px; color: rgba(255,255,255,0.6);">
                    📭 尚無優化記錄
                    <div style="margin-top: 10px; font-size: 0.9em;">
                        執行「自適應窗口優化」或「多階段優化」後，結果會顯示在這裡
                    </div>
                </div>
            `;
            return;
        }

        let html = '';

        // 最佳配置信息
        if (data.best_config_info) {
            const configInfo = data.best_config_info;
            const timestamp = configInfo.timestamp ? new Date(configInfo.timestamp).toLocaleString('zh-TW') : '未知';
            
            html += `
                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                        <span style="font-size: 1.3em;">🏆</span>
                        <strong style="font-size: 1.1em;">當前最佳配置</strong>
                    </div>
                    <div style="font-size: 0.9em; color: rgba(255,255,255,0.8);">
                        <div style="margin-bottom: 5px;">⏰ 更新時間: ${timestamp}</div>
                        <div style="margin-bottom: 5px;">🎯 彩券類型: ${data.lottery_type || '通用'}</div>
                        <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 4px; font-family: monospace; font-size: 0.85em; max-height: 200px; overflow-y: auto;">
                            ${this.formatConfigJson(configInfo.config)}
                        </div>
                    </div>
                </div>
            `;
        }

        // 優化歷史
        html += `
            <div style="margin-bottom: 15px;">
                <strong style="font-size: 1.05em;">📈 優化歷史記錄（最近 ${data.history.length} 條）</strong>
            </div>
        `;

        // 按時間倒序排列
        const sortedHistory = [...data.history].reverse();

        sortedHistory.forEach((record, index) => {
            const method = this.getMethodDisplayName(record.method);
            const timestamp = record.timestamp ? new Date(record.timestamp).toLocaleString('zh-TW') : '未知';
            const fitness = (record.best_fitness * 100).toFixed(2);

            html += `
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid ${this.getMethodColor(record.method)};">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div>
                            <div style="font-weight: bold; margin-bottom: 5px;">${method}</div>
                            <div style="font-size: 0.85em; color: rgba(255,255,255,0.6);">${timestamp}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.5em; font-weight: bold; color: #4ade80;">${fitness}%</div>
                            <div style="font-size: 0.8em; color: rgba(255,255,255,0.6);">適應度</div>
                        </div>
                    </div>
                    ${this.renderMethodSpecificInfo(record)}
                </div>
            `;
        });

        contentEl.innerHTML = html;
    }

    formatConfigJson(config) {
        /**
         * 格式化配置 JSON 為可讀形式
         */
        try {
            return JSON.stringify(config, null, 2)
                .replace(/\n/g, '<br>')
                .replace(/ /g, '&nbsp;');
        } catch {
            return '無法顯示配置';
        }
    }

    getMethodDisplayName(method) {
        const names = {
            'multi_stage': '🎯 多階段優化',
            'adaptive_window': '🔍 自適應窗口優化',
            'ensemble': '🤝 集成優化',
            'default': '🔧 標準優化'
        };
        return names[method] || names['default'];
    }

    getMethodColor(method) {
        const colors = {
            'multi_stage': '#667eea',
            'adaptive_window': '#10b981',
            'ensemble': '#f59e0b',
            'default': '#60a5fa'
        };
        return colors[method] || colors['default'];
    }

    renderMethodSpecificInfo(record) {
        /**
         * 渲染方法特定的詳細信息
         */
        let html = '<div style="font-size: 0.9em; color: rgba(255,255,255,0.8);">';

        if (record.method === 'multi_stage' && record.stage_results) {
            html += '<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1);">';
            html += '<strong>階段結果:</strong>';
            html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 8px;">';
            record.stage_results.forEach(stage => {
                html += `
                    <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; text-align: center;">
                        <div style="font-size: 0.8em; color: rgba(255,255,255,0.6); margin-bottom: 3px;">${stage.stage}</div>
                        <div style="font-weight: bold; color: #4ade80;">${(stage.fitness * 100).toFixed(2)}%</div>
                    </div>
                `;
            });
            html += '</div></div>';
        }

        if (record.method === 'adaptive_window' && record.best_window_size) {
            html += `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <strong>最佳窗口:</strong> ${record.best_window_size} 期
                </div>
            `;
        }

        if (record.method === 'ensemble' && record.ensemble_size) {
            html += `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <strong>集成模型數:</strong> ${record.ensemble_size}
                </div>
            `;
        }

        html += '</div>';
        return html;
    }
}

