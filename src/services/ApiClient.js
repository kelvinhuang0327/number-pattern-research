/**
 * API 客戶端服務
 * 統一管理所有後端 API 調用
 */

// 使用 127.0.0.1 以避免在 macOS 上因 IPv6 (::1) 解析造成的連線問題
const API_BASE_URL = 'http://127.0.0.1:5001';

export class ApiClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
        this.cache = new Map(); // 內存緩存（僅會話級別）
        this.cacheTimeout = 30000; // 30秒緩存過期
        this.requestTimeout = 300000; // 300秒請求超時（優化任務可能需要較長時間）
    }

    /**
     * 通用請求方法（帶重試機制）
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const maxRetries = 3;
        const baseDelay = 1000; // 1 second

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                // 創建超時控制
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);

                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    const error = await response.json().catch(() => ({ detail: response.statusText }));

                    // Retry on 5xx server errors
                    if (response.status >= 500 && attempt < maxRetries) {
                        const delay = baseDelay * Math.pow(2, attempt);
                        console.warn(`Server error (${response.status}), retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                        await new Promise(resolve => setTimeout(resolve, delay));
                        continue;
                    }

                    throw new Error(error.detail || `HTTP ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                if (error.name === 'AbortError') {
                    console.error(`API request timeout: ${endpoint}`);

                    // Retry on timeout
                    if (attempt < maxRetries) {
                        const delay = baseDelay * Math.pow(2, attempt);
                        console.warn(`Request timeout, retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                        await new Promise(resolve => setTimeout(resolve, delay));
                        continue;
                    }

                    throw new Error(`請求超時（超過 ${this.requestTimeout / 1000} 秒）`);
                }

                // Retry on network errors
                if (error.message.includes('fetch') || error.message.includes('network')) {
                    if (attempt < maxRetries) {
                        const delay = baseDelay * Math.pow(2, attempt);
                        console.warn(`Network error, retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                        await new Promise(resolve => setTimeout(resolve, delay));
                        continue;
                    }
                }

                console.error(`API request failed: ${endpoint}`, error);
                throw error;
            }
        }
    }

    /**
     * GET 請求
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullEndpoint = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(fullEndpoint, { method: 'GET' });
    }

    /**
     * POST 請求
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE 請求
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // ===== 數據管理 API =====

    /**
     * 上傳開獎數據到後端（支援批次上傳）
     * @param {Array} draws - 開獎記錄數組
     * @param {Object} lotteryRules - 彩券規則
     */
    async uploadDraws(draws, lotteryRules) {
        const BATCH_SIZE = 500; // 每批上傳 500 筆
        const totalDraws = draws.length;

        // 如果數據量少於批次大小，直接上傳
        if (totalDraws <= BATCH_SIZE) {
            console.log(`📤 Uploading ${totalDraws} draws to backend...`);
            const result = await this.post('/api/data/upload', {
                history: draws,
                lotteryRules: lotteryRules
            });
            this.clearCache();
            console.log(`✅ Upload complete: ${result.inserted} new, ${result.duplicates} duplicates`);
            return result;
        }

        // 批次上傳
        console.log(`📤 Uploading ${totalDraws} draws in batches (${BATCH_SIZE} per batch)...`);

        let totalInserted = 0;
        let totalDuplicates = 0;
        const batches = Math.ceil(totalDraws / BATCH_SIZE);

        for (let i = 0; i < batches; i++) {
            const start = i * BATCH_SIZE;
            const end = Math.min(start + BATCH_SIZE, totalDraws);
            const batch = draws.slice(start, end);

            console.log(`📦 Uploading batch ${i + 1}/${batches} (${batch.length} draws)...`);

            try {
                const result = await this.post('/api/data/upload', {
                    history: batch,
                    lotteryRules: lotteryRules
                });

                totalInserted += result.inserted || 0;
                totalDuplicates += result.duplicates || 0;

                console.log(`✅ Batch ${i + 1}/${batches} complete: ${result.inserted} new, ${result.duplicates} duplicates`);

                // 短暫延遲避免後端過載
                if (i < batches - 1) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
            } catch (error) {
                console.error(`❌ Batch ${i + 1}/${batches} failed:`, error);
                throw new Error(`批次上傳失敗 (batch ${i + 1}/${batches}): ${error.message}`);
            }
        }

        // 清除緩存
        this.clearCache();

        const summary = {
            inserted: totalInserted,
            duplicates: totalDuplicates,
            total: totalDraws,
            batches: batches
        };

        console.log(`✅ All batches uploaded: ${totalInserted} new, ${totalDuplicates} duplicates (${batches} batches)`);
        return summary;
    }

    /**
     * 生成穩定的緩存鍵
     * @param {Object} obj - 要生成鍵的對象
     */
    _getStableKey(obj) {
        if (typeof obj !== 'object' || obj === null) {
            return String(obj);
        }
        // 對鍵進行排序以確保穩定性
        return JSON.stringify(Object.keys(obj).sort().reduce((result, key) => {
            result[key] = obj[key];
            return result;
        }, {}));
    }

    /**
     * 獲取開獎記錄（分頁）
     * @param {Object} filters - 篩選條件
     */
    async getDraws(filters = {}) {
        const cacheKey = `draws_${this._getStableKey(filters)}`;

        // 🚫 緩存已禁用：每次都從 API 獲取最新數據
        // console.log('🔄 從 API 動態獲取最新數據');

        const result = await this.get('/api/data/draws', filters);

        // 🚫 不再緩存結果

        return result;
    }

    /**
     * 獲取所有歷史數據（不分頁）
     * @param {string} lotteryType - 可選的彩券類型篩選
     */
    async getAllHistory(lotteryType = null) {
        const cacheKey = `history_${lotteryType || 'all'}`;

        // 🚫 緩存已禁用：每次都從 API 獲取最新歷史數據
        // console.log('🔄 從 API 動態獲取最新歷史數據');

        const params = lotteryType ? { lottery_type: lotteryType } : {};
        const result = await this.get('/api/history', params);

        // 🚫 不再緩存結果

        return result;
    }

    /**
     * 獲取統計信息
     * @param {string} lotteryType - 可選的彩券類型篩選
     */
    async getStats(lotteryType = null) {
        const params = lotteryType ? { lottery_type: lotteryType } : {};
        return this.get('/api/data/stats', params);
    }

    /**
     * 清除所有數據
     */
    async clearAllData() {
        const result = await this.post('/api/data/clear');
        this.clearCache();
        return result;
    }

    // ===== 預測 API =====

    /**
     * 使用後端數據進行預測
     * @param {string} lotteryType - 彩券類型
     * @param {string} modelType - 模型類型
     */
    async predictFromBackend(lotteryType, modelType) {
        return this.post('/api/predict-from-backend', {
            lotteryType,
            modelType
        });
    }

    /**
     * 使用前端數據進行預測
     * @param {Array} history - 歷史數據
     * @param {Object} lotteryRules - 彩券規則
     * @param {string} modelType - 模型類型
     */
    async predict(history, lotteryRules, modelType) {
        return this.post('/api/predict', {
            history,
            lotteryRules,
            modelType
        });
    }

    // ===== 自動學習 API =====

    /**
     * 執行優化
     */
    async runOptimization(lotteryType, lotteryRules, generations = 20, populationSize = 30) {
        return this.post('/api/auto-learning/optimize', {
            history: [], // 使用後端數據
            lotteryRules,
            generations,
            population_size: populationSize,
            lotteryType
        });
    }

    /**
     * 獲取排程狀態
     */
    async getScheduleStatus() {
        return this.get('/api/auto-learning/schedule/status');
    }

    /**
     * 啟動排程
     */
    async startSchedule(scheduleTime = '02:00') {
        return this.post('/api/auto-learning/schedule/start', {
            schedule_time: scheduleTime
        });
    }

    /**
     * 停止排程
     */
    async stopSchedule() {
        return this.post('/api/auto-learning/schedule/stop');
    }

    /**
     * 獲取最佳配置
     */
    async getBestConfig() {
        return this.get('/api/auto-learning/best-config');
    }

    /**
     * 評估策略
     */
    async evaluateStrategies(lotteryType, testRatio = 0.2, minTrainSize = 30) {
        return this.post('/api/auto-learning/evaluate-strategies', {
            lotteryType,
            test_ratio: testRatio,
            min_train_size: minTrainSize
        });
    }

    // ===== 健康檢查 =====

    /**
     * 檢查後端健康狀態
     */
    async healthCheck() {
        try {
            const result = await this.get('/health');
            return { ok: true, data: result };
        } catch (error) {
            return { ok: false, error: error.message };
        }
    }

    // ===== 緩存管理 =====

    /**
     * 清除所有緩存
     */
    clearCache() {
        this.cache.clear();
        console.log('🗑️ API cache cleared');
    }

    /**
     * 清除特定緩存
     */
    clearCacheByKey(key) {
        this.cache.delete(key);
    }
}

// 導出單例
export const apiClient = new ApiClient();
