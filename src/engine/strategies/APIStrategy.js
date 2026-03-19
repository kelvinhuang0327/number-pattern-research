/**
 * API Strategy - 調用後端 AI 模型進行預測
 * 支持 Prophet, XGBoost, LSTM 等模型
 */
import { getApiUrl } from '../../config/apiConfig.js';

export class APIStrategy {
    constructor(modelType = 'prophet') {
        this.modelType = modelType; // 'prophet' | 'xgboost' | 'lstm'
        this.apiEndpoint = this.getApiEndpoint();
    }

    /**
     * 獲取 API 端點
     */
    getApiEndpoint() {
        return getApiUrl('/api/predict');
    }

    /**
     * 從 UI 讀取 coordinator 控制參數
     */
    getCoordinatorConfig() {
        const modeEl = document.getElementById('coord-mode');
        const betsEl = document.getElementById('coord-bets');
        const mode = (modeEl?.value || 'direct').toLowerCase();
        const bets = parseInt(betsEl?.value || '3', 10);
        return {
            mode: mode === 'hybrid' ? 'hybrid' : 'direct',
            bets: Number.isFinite(bets) ? Math.min(Math.max(bets, 1), 5) : 3
        };
    }

    /**
     * 執行預測
     * @param {Array} data - 歷史數據
     * @param {Object} lotteryRules - 彩券規則
     * @param {boolean} useBackendData - 是否使用後端已存儲的數據（優化模式）
     */
    async predict(data, lotteryRules, useBackendData = false) {
        try {
            console.log(`🤖 調用 ${this.modelType.toUpperCase()} API...`);

            if (useBackendData) {
                // 🚀 優化模式：使用後端數據或範圍查詢
                // 如果數據很少，使用範圍查詢模式（只傳期數範圍）
                if (data && data.length > 0 && data.length < 10000) {
                    return await this.predictWithRange(data, lotteryRules);
                } else {
                    return await this.predictFromBackend(lotteryRules);
                }
            } else {
                // 傳統模式：傳送完整數據
                return await this.predictWithFullData(data, lotteryRules);
            }

        } catch (error) {
            console.error(`❌ API 調用失敗:`, error);

            // 友好的錯誤處理
            if (error.message.includes('Failed to fetch')) {
                throw new Error('無法連接到 AI 預測服務器。請確認後端服務是否運行。');
            }

            throw new Error(`AI 預測失敗: ${error.message}`);
        }
    }

    /**
     * 🚀 優化模式：使用後端已存儲的數據進行預測
     * - 不需要傳送完整歷史數據
     * - 支持模型緩存，速度更快
     * - 請求體積減少 99%+
     */
    async predictFromBackend(lotteryRules) {
        console.log(`🚀 使用後端數據預測（優化模式）`);

        // 獲取當前彩券類型
        const lotteryType = lotteryRules.lotteryType || 'BIG_LOTTO';

        // 準備請求數據（只需要彩券類型和模型類型）
        const requestData = {
            lotteryType: lotteryType,
            modelType: this.modelType
        };

        const { mode, bets } = this.getCoordinatorConfig();
        const endpoint = new URL(this.apiEndpoint.replace('/predict', '/predict-from-backend'));
        if (this.modelType.startsWith('coordinator')) {
            endpoint.searchParams.set('coord_mode', mode);
            endpoint.searchParams.set('coord_bets', String(bets));
        }

        // 發送 API 請求到優化端點
        const response = await fetch(endpoint.toString(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `API 錯誤: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        console.log(`✅ ${this.modelType.toUpperCase()} 預測完成（使用緩存）`);

        // 格式化返回結果
        return {
            numbers: result.numbers || [],
            probabilities: result.probabilities || null,
            confidence: result.confidence || 0,
            method: result.method || `${this.getModelName()} AI 預測（優化）`,
            report: this.generateReport(result)
        };
    }

    /**
     * 傳統模式：傳送完整數據進行預測
     * 注意：模擬測試時必須使用此模式，因為需要特定的訓練數據集
     */
    async predictWithFullData(data, lotteryRules) {
        console.log(`📦 傳送特定數據集預測（${data.length}期）- 適用於模擬測試`);

        // 準備請求數據
        const requestData = {
            history: this.prepareData(data),
            lotteryRules: lotteryRules,
            modelType: this.modelType
        };

        // 發送 API 請求
        const response = await fetch(this.apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`API 錯誤: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        console.log(`✅ ${this.modelType.toUpperCase()} 預測完成`);

        // 格式化返回結果
        return {
            numbers: result.numbers || [],
            probabilities: result.probabilities || null,
            confidence: result.confidence || 0,
            method: result.method || `${this.getModelName()} AI 預測`,
            report: this.generateReport(result)
        };
    }

    /**
     * 🚀 範圍查詢模式：只傳送期數/日期範圍，由後端查詢數據
     * - 適用於模擬測試的滾動窗口
     * - 大幅減少網路傳輸（只傳範圍參數）
     * - 後端自動從數據庫查詢指定範圍的數據
     */
    async predictWithRange(data, lotteryRules) {
        const lotteryType = lotteryRules.lotteryType || 'BIG_LOTTO';

        // 數據驗證
        if (!data || data.length === 0) {
            console.warn('⚠️ predictWithRange: 數據為空，回退到使用全部數據');
            // 使用 recentCount 回退策略
            const requestData = {
                lotteryType: lotteryType,
                modelType: this.modelType,
                recentCount: 100  // 使用最近100期
            };

            return await this.executeRangeRequest(requestData, lotteryRules);
        }

        // 提取數據的期數範圍
        let startDraw = null;
        let endDraw = null;

        // 排序數據以確保正確的起訖期數（數值排序）
        const sortedData = [...data].sort((a, b) => {
            // 提取純數字期數（處理可能的格式：96000001, 2024-001, 001 等）
            const drawA = parseInt((a.draw || '').toString().replace(/\D/g, '')) || 0;
            const drawB = parseInt((b.draw || '').toString().replace(/\D/g, '')) || 0;
            return drawA - drawB;  // 數值比較
        });

        // 直接使用原始 draw 值（不做分割處理）
        startDraw = sortedData[0].draw?.toString();
        endDraw = sortedData[sortedData.length - 1].draw?.toString();

        // 驗證期數是否有效
        if (!startDraw || !endDraw) {
            console.warn('⚠️ 無法提取有效的期數範圍，回退到傳送完整數據');
            return await this.predictWithFullData(data, lotteryRules);
        }

        console.log(`🎯 使用範圍查詢模式: ${startDraw} - ${endDraw} (${data.length}期)`);

        // 準備請求數據（只傳範圍參數）
        const requestData = {
            lotteryType: lotteryType,
            modelType: this.modelType,
            startDraw: startDraw,
            endDraw: endDraw
        };

        if (this.modelType.startsWith('coordinator')) {
            const { mode, bets } = this.getCoordinatorConfig();
            requestData.coordMode = mode;
            requestData.coordBets = bets;
        }

        try {
            return await this.executeRangeRequest(requestData, lotteryRules);
        } catch (error) {
            console.warn('⚠️ 範圍查詢失敗，自動回退到傳送完整數據:', error.message);
            return await this.predictWithFullData(data, lotteryRules);
        }
    }

    /**
     * 執行範圍查詢請求的共用方法
     */
    async executeRangeRequest(requestData, lotteryRules) {
        // Debug: 記錄實際發送的參數
        console.log('🔍 predict-with-range 請求參數:', JSON.stringify(requestData, null, 2));

        // 發送 API 請求到範圍查詢端點
        const response = await fetch(this.apiEndpoint.replace('/predict', '/predict-with-range'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('❌ API 錯誤回應:', errorData);
            throw new Error(errorData.detail || `API 錯誤: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        console.log(`✅ ${this.modelType.toUpperCase()} 範圍預測完成（網路傳輸 < 1KB）`);

        // 格式化返回結果
        return {
            numbers: result.numbers || [],
            probabilities: result.probabilities || null,
            confidence: result.confidence || 0,
            method: result.method || `${this.getModelName()} AI 預測（範圍模式）`,
            report: this.generateReport(result)
        };
    }

    /**
     * 帶緩存的預測（用於模擬）
     * API 策略不使用緩存，直接調用 predict
     */
    async predictWithCache(data, lotteryRules, cache = null, useBackendData = false) {
        // API 策略不使用緩存機制，直接預測
        const result = await this.predict(data, lotteryRules, useBackendData);

        // 返回結果時保持緩存結構（即使不使用）
        return {
            ...result,
            cache: cache  // 保持原有緩存
        };
    }

    /**
     * 準備發送到 API 的數據格式
     */
    prepareData(data) {
        return data.map((draw, index) => ({
            date: draw.date || '2024/01/01',
            draw: draw.draw || (index + 1),
            numbers: draw.numbers || [],
            lotteryType: draw.lotteryType || 'BIG_LOTTO'
        }));
    }

    /**
     * 獲取模型顯示名稱
     */
    getModelName() {
        const names = {
            'prophet': 'Prophet 時間序列',
            'xgboost': 'XGBoost 梯度提升',
            'autogluon': 'AutoGluon AutoML',
            'lstm': 'LSTM 神經網絡',
            'transformer': 'Transformer (PatchTST)',
            'bayesian_ensemble': '貝叶斯優化集成',
            'maml': '元學習 (MAML)',
            'coordinator': 'Coordinator (RSM 加權)',
            'coordinator_direct': 'Coordinator Direct',
            'coordinator_hybrid': 'Coordinator Hybrid'
        };
        return names[this.modelType] || this.modelType;
    }

    /**
     * 生成預測報告
     */
    generateReport(result) {
        let report = `🤖 **${this.getModelName()}分析報告**\n\n`;

        if (result.modelInfo) {
            report += `**模型信息:**\n`;
            report += `• 訓練數據: ${result.modelInfo.trainingSize || 'N/A'} 期\n`;
            report += `• 模型版本: ${result.modelInfo.version || 'v1.0'}\n\n`;
        }

        report += `**預測結果:**\n`;
        report += `• 信心度: ${(result.confidence * 100).toFixed(1)}%\n`;

        if (result.trend) {
            report += `• 趨勢分析: ${result.trend}\n`;
        }

        if (result.seasonality) {
            report += `• 季節性: ${result.seasonality}\n`;
        }

        if (result.notes) {
            report += `\n**備註:**\n${result.notes}\n`;
        }

        // Track B: Player Behavior / Split-Risk Advisory
        if (result.modelInfo && result.modelInfo.player_behavior) {
            const pb = result.modelInfo.player_behavior;
            if (pb.bets && pb.bets.length > 0) {
                report += `\n---\n### Player Behavior / Split-Risk Analysis (Advisory Only)\n\n`;
                pb.bets.forEach((bet, idx) => {
                    const nums = (bet.numbers || []).map(n => String(n).padStart(2, '0')).join(', ');
                    const score = bet.popularity?.popularity_score || 0;
                    const level = bet.split_risk?.split_risk_level || 'LOW';
                    const flags = (bet.popularity?.bias_flags || []).join(', ');
                    report += `**注${idx + 1}**: ${nums}\n`;
                    report += `- Popularity: **${score.toFixed(0)}/100** (${level})\n`;
                    if (flags) report += `- Bias flags: ${flags}\n`;
                    report += `- ${bet.split_risk?.expected_dilution || ''}\n`;
                    if (bet.anti_crowd?.alternative) {
                        const alt = bet.anti_crowd.alternative.map(n => String(n).padStart(2, '0')).join(', ');
                        report += `- Alternative: ${alt} (score ${(bet.anti_crowd.alternative_score || 0).toFixed(0)}, -${(bet.anti_crowd.improvement || 0).toFixed(0)}pts)\n`;
                    }
                    report += `\n`;
                });
                report += `> *This section is ADVISORY ONLY. It does NOT affect prediction accuracy or ranking.*\n`;
            }
        }

        return report;
    }
}
