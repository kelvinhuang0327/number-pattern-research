import { FrequencyStrategy } from './strategies/FrequencyStrategy.js';
import { TrendStrategy } from './strategies/TrendStrategy.js';
import { MarkovStrategy } from './strategies/MarkovStrategy.js';
import { MonteCarloStrategy } from './strategies/MonteCarloStrategy.js';
import { BayesianStrategy } from './strategies/BayesianStrategy.js';
import { DeviationStrategy } from './strategies/DeviationStrategy.js';
import { UnifiedEnsembleStrategy } from './strategies/UnifiedEnsembleStrategy.js';
import { MLStrategy } from './strategies/MLStrategy.js';
import { CollaborativeStrategy } from './strategies/CollaborativeStrategy.js';
import { AutoOptimizeStrategy } from './strategies/AutoOptimizeStrategy.js';
import { APIStrategy } from './strategies/APIStrategy.js';
import { BackendOptimizedStrategy } from './strategies/BackendOptimizedStrategy.js';
import { getLotteryRules, getRelatedTypes } from '../utils/Constants.js';

// 民間策略
import { OddEvenBalanceStrategy } from './strategies/OddEvenBalanceStrategy.js';
import { ZoneBalanceStrategy } from './strategies/ZoneBalanceStrategy.js';
import { HotColdMixStrategy } from './strategies/HotColdMixStrategy.js';
import { SumRangeStrategy } from './strategies/SumRangeStrategy.js';
import { WheelingStrategy } from './strategies/WheelingStrategy.js';
import { NumberPairsStrategy } from './strategies/NumberPairsStrategy.js';
import { StatisticalAnalysisStrategy } from './strategies/StatisticalAnalysisStrategy.js';

export class PredictionEngine {
    constructor(dataProcessor, statisticsService) {
        this.dataProcessor = dataProcessor;
        this.statisticsService = statisticsService;

        // 🔄 策略映射表（向後兼容 - 整合後的映射）
        this.DEPRECATED_STRATEGY_MAPPING = {
            // 集成策略整合
            'ensemble_boosting': 'ensemble_advanced',
            'ensemble_cooccurrence': 'ensemble_advanced',
            'ensemble_features': 'ensemble_advanced',

            // 協作策略整合
            'collaborative_relay': 'collaborative_hybrid',
            'collaborative_coop': 'collaborative_hybrid',

            // ML 策略整合
            'ml_features': 'ml_forest',

            // 組合分析整合
            'wheeling': 'statistical'
        };

        this.strategies = {
            // ===== 核心統計策略 =====
            'frequency': new FrequencyStrategy(statisticsService),
            'trend': new TrendStrategy(),
            'bayesian': new BayesianStrategy(statisticsService),
            'montecarlo': new MonteCarloStrategy(statisticsService),
            'markov': new MarkovStrategy(),
            'deviation': new DeviationStrategy(statisticsService),

            // ===== 統一集成策略 (整合後保留3種) =====
            'ensemble_weighted': new UnifiedEnsembleStrategy(statisticsService, 'weighted'),
            'ensemble_combined': new UnifiedEnsembleStrategy(statisticsService, 'combined'),
            'ensemble_advanced': new UnifiedEnsembleStrategy(statisticsService, 'advanced'),  // 新增：整合 boosting/cooccurrence/features

            // 已整合策略（保留向後兼容）
            'ensemble_boosting': new UnifiedEnsembleStrategy(statisticsService, 'boosting'),
            'ensemble_cooccurrence': new UnifiedEnsembleStrategy(statisticsService, 'cooccurrence'),
            'ensemble_features': new UnifiedEnsembleStrategy(statisticsService, 'feature_weighted'),

            // ===== 機器學習策略 (整合3種算法) =====
            'ml_features': new MLStrategy(statisticsService, 'feature_weighted'),
            'ml_forest': new MLStrategy(statisticsService, 'random_forest'),
            'ml_genetic': new MLStrategy(statisticsService, 'genetic'),

            // ===== 協作預測系統 (3種模式) =====
            'collaborative_relay': new CollaborativeStrategy(statisticsService, 'relay'),
            'collaborative_coop': new CollaborativeStrategy(statisticsService, 'cooperative'),
            'collaborative_hybrid': new CollaborativeStrategy(statisticsService, 'hybrid'),

            // ===== AI 自動優化 =====
            'auto_optimize': new AutoOptimizeStrategy(this, statisticsService),

            // ===== 後端優化預測 =====
            'backend_optimized': new BackendOptimizedStrategy(),

            // ===== AI 深度學習模型（後端 API）=====
            'ai_prophet': new APIStrategy('prophet'),
            'ai_xgboost': new APIStrategy('xgboost'),
            'ai_autogluon': new APIStrategy('autogluon'),

            'ai_lstm': new APIStrategy('lstm'),
            'ai_transformer': new APIStrategy('transformer'),
            'ai_bayesian_ensemble': new APIStrategy('bayesian_ensemble'),
            'ai_maml': new APIStrategy('maml'),

            // ===== 民間策略 =====
            'odd_even': new OddEvenBalanceStrategy(statisticsService),
            'zone_balance': new ZoneBalanceStrategy(statisticsService),
            'hot_cold': new HotColdMixStrategy(statisticsService),
            'sum_range': new SumRangeStrategy(statisticsService),
            'wheeling': new WheelingStrategy(statisticsService),
            'number_pairs': new NumberPairsStrategy(statisticsService),
            'statistical': new StatisticalAnalysisStrategy(statisticsService),

            // ===== 高級分析策略 (新增) =====
            'entropy': new APIStrategy('entropy'),
            'clustering': new APIStrategy('clustering'),
            'dynamic_ensemble': new APIStrategy('dynamic_ensemble'),
            'temporal': new APIStrategy('temporal'),
            'feature_engineering': new APIStrategy('feature_engineering')
        };
    }

    /**
     * 執行預測（支援彩券類型過濾）
     * @param {string} method - 策略名稱
     * @param {number} sampleSize - 樣本大小
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     * @param {boolean} useBackendData - 是否使用後端數據（僅適用於 API 策略）
     * @returns {Object} 預測結果
     */
    async predict(method = 'frequency', sampleSize = 50, lotteryTypeId = null, useBackendData = false) {
        // 🔄 檢查並映射已整合的策略
        const originalMethod = method;
        if (this.DEPRECATED_STRATEGY_MAPPING[method]) {
            const newMethod = this.DEPRECATED_STRATEGY_MAPPING[method];
            console.warn(`⚠️ 策略 "${method}" 已整合至 "${newMethod}"，自動轉換`);
            if (this.dataProcessor.uiManager) {
                this.dataProcessor.uiManager.showNotification(
                    `策略已升級：${method} → ${newMethod}`,
                    'info'
                );
            }
            method = newMethod;
        }

        // 獲取數據（DataProcessor 已經處理相關類型過濾）
        let data = await this.dataProcessor.getDataRange(sampleSize, lotteryTypeId);

        // 驗證數據
        if (data.length === 0) {
            throw new Error(lotteryTypeId ? `無 ${lotteryTypeId} 類型的數據` : '無數據可供預測');
        }



        // 獲取彩券規則
        const lotteryRules = getLotteryRules(lotteryTypeId);

        // 🚀 為 API 策略添加彩券類型信息
        if (lotteryTypeId) {
            lotteryRules.lotteryType = lotteryTypeId;
        }

        const strategy = this.strategies[method];
        if (!strategy) {
            console.warn(`Strategy ${method} not found, falling back to frequency.`);
            return this.strategies['frequency'].predict(data, lotteryRules);
        }

        // 🚀 策略名稱映射（前端策略名 -> 後端模型名）
        const STRATEGY_MAPPING = {
            'frequency': 'frequency',
            'bayesian': 'bayesian',
            'markov': 'markov',
            'montecarlo': 'monte_carlo',
            'odd_even': 'odd_even',
            'zone_balance': 'zone_balance',
            'hot_cold': 'hot_cold',

            // 新增映射
            'trend': 'trend',
            'deviation': 'deviation',
            'sum_range': 'sum_range',
            'wheeling': 'wheeling',
            'number_pairs': 'number_pairs',
            'statistical': 'statistical',

            // 集成策略映射
            'ensemble_weighted': 'ensemble',
            'ensemble_combined': 'ensemble',
            'ensemble_advanced': 'ensemble_advanced',  // 新增：進階集成
            'ensemble_boosting': 'ensemble_advanced',   // 整合到 advanced
            'ensemble_cooccurrence': 'ensemble_advanced',  // 整合到 advanced
            'ensemble_features': 'ensemble_advanced',      // 整合到 advanced

            // ML 策略映射
            'ml_forest': 'random_forest',
            'ml_features': 'random_forest', // 整合到 forest
            'ml_genetic': 'ensemble', // 遺傳算法通常是優化權重，映射到集成

            // 協作預測映射
            'collaborative_relay': 'ensemble',   // 整合到 hybrid
            'collaborative_coop': 'ensemble',    // 整合到 hybrid
            'collaborative_hybrid': 'ensemble',

            // AI 自動優化 -> 映射到後端優化預測
            'auto_optimize': 'backend_optimized',

            // 高級分析策略 (新增)
            'entropy': 'entropy',
            'clustering': 'clustering',
            'dynamic_ensemble': 'dynamic_ensemble',
            'temporal': 'temporal',
            'feature_engineering': 'feature_engineering',

            'ai_transformer': 'transformer',
            'ai_bayesian_ensemble': 'bayesian_ensemble',
            'ai_maml': 'maml'
        };

        let result;

        // 判斷是否應該使用後端 API
        // 1. 本身就是 API 策略 (ai_*)
        // 2. 啟用了 useBackendData 且該策略有對應的後端實現
        const backendModelType = STRATEGY_MAPPING[method];
        const shouldUseBackend = useBackendData && (strategy instanceof APIStrategy || backendModelType);

        // Special-case: auto_optimize should use dedicated BackendOptimizedStrategy endpoint
        if (useBackendData && method === 'auto_optimize') {
            const boStrategy = this.strategies['backend_optimized'];
            result = await boStrategy.predict(data, lotteryRules);
        } else if (shouldUseBackend) {
            console.log(`🚀 使用後端數據優化模式 (${method})`);

            try {
                if (strategy instanceof APIStrategy) {
                    // 原生 API 策略
                    result = await strategy.predict(data, lotteryRules, true);
                } else if (backendModelType) {
                    // 傳統策略轉發到後端
                    console.log(`🔄 將 ${method} 策略轉發到後端模型 ${backendModelType}`);
                    const tempApiStrategy = new APIStrategy(backendModelType);
                    // 傳遞 useBackendData=true 讓 APIStrategy 使用 /predict-from-backend
                    result = await tempApiStrategy.predict(data, lotteryRules, true);
                } else {
                    // 雖然啟用了 useBackendData 但沒有後端實現，回退到本地
                    console.warn(`⚠️ 策略 ${method} 尚無後端實現，回退到本地計算`);
                    result = await strategy.predict(data, lotteryRules);
                }
            } catch (error) {
                console.warn(`⚠️ 後端預測失敗，回退到本地計算: ${error.message}`);
                // 如果是原生 API 策略，無法回退（因為沒有本地實現），只能拋出錯誤
                if (strategy instanceof APIStrategy) {
                    throw error;
                }
                // 傳統策略可以回退到本地
                this.dataProcessor.uiManager?.showNotification('後端連接失敗，已切換至本地計算模式', 'warning');
                result = await strategy.predict(data, lotteryRules);
            }
        } else {
            // 使用本地策略
            result = await strategy.predict(data, lotteryRules);
        }

        // 添加彩券類型信息到結果中
        return {
            ...result,
            lotteryType: lotteryTypeId || 'BIG_LOTTO',
            dataCount: data.length
        };
    }

    /**
     * 模擬專用預測（支援彩券類型與後端數據）
     * @param {string} method - 策略名稱
     * @param {Array} data - 數據
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     * @param {boolean} useBackendData - 是否使用後端數據
     * @returns {Object} 預測結果
     */
    async predictWithData(method, data, lotteryTypeId = null, useBackendData = false) {
        // 🔄 檢查並映射已整合的策略
        if (this.DEPRECATED_STRATEGY_MAPPING[method]) {
            const newMethod = this.DEPRECATED_STRATEGY_MAPPING[method];
            console.warn(`⚠️ 策略 "${method}" 已整合至 "${newMethod}"，自動轉換`);
            method = newMethod;
        }

        // 如果指定了彩券類型，進行過濾（包含相關類型）
        if (lotteryTypeId) {
            // 獲取所有相關類型（例如：大樂透 + 大樂透加開獎項）
            const relatedTypes = getRelatedTypes(lotteryTypeId);
            data = data.filter(d => relatedTypes.includes(d.lotteryType));
        }



        // 🆕 模擬資料量限制：避免傳送過大 payload 給後端
        // 設定為 10000 期，足夠涵蓋大樂透完整歷史數據
        const MAX_SIM_BACKEND = 10000;
        if (useBackendData && data.length > MAX_SIM_BACKEND) {
            console.warn(`⚠️ 模擬資料量過大 (${data.length})，截取最近 ${MAX_SIM_BACKEND} 期以提升效能`);
            data = data.slice(-MAX_SIM_BACKEND);
        }

        // 獲取彩券規則
        const lotteryRules = getLotteryRules(lotteryTypeId);
        if (lotteryTypeId) {
            lotteryRules.lotteryType = lotteryTypeId;
        }

        const strategy = this.strategies[method] || this.strategies['frequency'];

        // 🚀 策略名稱映射（前端策略名 -> 後端模型名）
        const STRATEGY_MAPPING = {
            'frequency': 'frequency',
            'bayesian': 'bayesian',
            'markov': 'markov',
            'montecarlo': 'monte_carlo',
            'odd_even': 'odd_even',
            'zone_balance': 'zone_balance',
            'hot_cold': 'hot_cold',
            'trend': 'trend',
            'deviation': 'deviation',
            'sum_range': 'sum_range',
            'wheeling': 'wheeling',
            'number_pairs': 'number_pairs',
            'statistical': 'statistical',
            'ensemble_weighted': 'ensemble',
            'ensemble_combined': 'ensemble',
            'ensemble_advanced': 'ensemble_advanced',  // 新增
            'ensemble_boosting': 'ensemble_advanced',   // 整合
            'ensemble_cooccurrence': 'ensemble_advanced',  // 整合
            'ensemble_features': 'ensemble_advanced',      // 整合
            'ml_forest': 'random_forest',
            'ml_features': 'random_forest',  // 整合
            'ml_genetic': 'ensemble',
            'collaborative_relay': 'ensemble',  // 整合
            'collaborative_coop': 'ensemble',   // 整合
            'collaborative_hybrid': 'ensemble',
            'auto_optimize': 'backend_optimized',

            // 高級分析策略 (新增)
            'entropy': 'entropy',
            'clustering': 'clustering',
            'dynamic_ensemble': 'dynamic_ensemble',
            'temporal': 'temporal',
            'feature_engineering': 'feature_engineering',

            'ai_transformer': 'transformer',
            'ai_bayesian_ensemble': 'bayesian_ensemble',
            'ai_maml': 'maml'
        };

        const backendModelType = STRATEGY_MAPPING[method];
        const shouldUseBackend = useBackendData && (strategy instanceof APIStrategy || backendModelType);

        // Special-case: auto_optimize should use dedicated BackendOptimizedStrategy endpoint
        if (useBackendData && method === 'auto_optimize') {
            const boStrategy = this.strategies['backend_optimized'];
            const result = await boStrategy.predict(data, lotteryRules);
            return {
                ...result,
                lotteryType: lotteryTypeId || 'BIG_LOTTO',
                dataCount: data.length
            };
        }

        if (shouldUseBackend) {
            try {
                if (strategy instanceof APIStrategy) {
                    // API 策略：優先使用範圍查詢模式（只傳期數範圍）
                    // 如果數據量適中（10-10000期），使用範圍查詢
                    // 否則回退到完整數據模式
                    return await strategy.predict(data, lotteryRules, true);
                } else if (backendModelType) {
                    // 傳統策略轉發到後端：使用範圍查詢模式
                    const tempApiStrategy = new APIStrategy(backendModelType);
                    return await tempApiStrategy.predict(data, lotteryRules, true);
                }
            } catch (error) {
                console.warn(`⚠️ 後端模擬預測失敗，回退到本地: ${error.message}`);
                // Fallback
            }
        }

        const result = await strategy.predict(data, lotteryRules);

        return {
            ...result,
            lotteryType: lotteryTypeId || 'BIG_LOTTO',
            dataCount: data.length
        };
    }
}
