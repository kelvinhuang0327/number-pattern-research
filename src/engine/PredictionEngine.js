import { FrequencyStrategy } from './strategies/FrequencyStrategy.js';
import { TrendStrategy } from './strategies/TrendStrategy.js';
import { MarkovStrategy } from './strategies/MarkovStrategy.js';
import { MonteCarloStrategy } from './strategies/MonteCarloStrategy.js';
import { BayesianStrategy } from './strategies/BayesianStrategy.js';
import { DeviationStrategy } from './strategies/DeviationStrategy.js';
import { UnifiedEnsembleStrategy } from './strategies/UnifiedEnsembleStrategy.js';
import { MLStrategy } from './strategies/MLStrategy.js';
import { CollaborativeStrategy } from './strategies/CollaborativeStrategy.js';
import { getLotteryRules } from '../utils/Constants.js';

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
        this.strategies = {
            // ===== 核心統計策略 =====
            'frequency': new FrequencyStrategy(statisticsService),
            'trend': new TrendStrategy(),
            'bayesian': new BayesianStrategy(statisticsService),
            'montecarlo': new MonteCarloStrategy(statisticsService),
            'markov': new MarkovStrategy(),
            'deviation': new DeviationStrategy(statisticsService),

            // ===== 統一集成策略 (整合5種模式) =====
            'ensemble_weighted': new UnifiedEnsembleStrategy(statisticsService, 'weighted'),
            'ensemble_boosting': new UnifiedEnsembleStrategy(statisticsService, 'boosting'),
            'ensemble_combined': new UnifiedEnsembleStrategy(statisticsService, 'combined'),
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

            // ===== 民間策略 =====
            'odd_even': new OddEvenBalanceStrategy(),
            'zone_balance': new ZoneBalanceStrategy(),
            'hot_cold': new HotColdMixStrategy(statisticsService),
            'sum_range': new SumRangeStrategy(),
            'wheeling': new WheelingStrategy(),
            'number_pairs': new NumberPairsStrategy(statisticsService),
            'statistical': new StatisticalAnalysisStrategy(statisticsService)
        };
    }

    /**
     * 執行預測（支援彩券類型過濾）
     * @param {string} method - 策略名稱
     * @param {number} sampleSize - 樣本大小
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     * @returns {Object} 預測結果
     */
    async predict(method = 'frequency', sampleSize = 50, lotteryTypeId = null) {
        // 獲取數據
        let data = this.dataProcessor.getDataRange(sampleSize);

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            data = data.filter(d => d.lotteryType === lotteryTypeId);
            if (data.length === 0) {
                throw new Error(`無 ${lotteryTypeId} 類型的數據`);
            }
        }

        if (data.length === 0) {
            throw new Error('無數據可供預測');
        }

        // 獲取彩券規則
        const lotteryRules = getLotteryRules(lotteryTypeId);

        const strategy = this.strategies[method];
        if (!strategy) {
            console.warn(`Strategy ${method} not found, falling back to frequency.`);
            return this.strategies['frequency'].predict(data, lotteryRules);
        }

        const result = await strategy.predict(data, lotteryRules);

        // 添加彩券類型信息到結果中
        return {
            ...result,
            lotteryType: lotteryTypeId || 'BIG_LOTTO',
            dataCount: data.length
        };
    }

    /**
     * 模擬專用預測（支援彩券類型）
     * @param {string} method - 策略名稱
     * @param {Array} data - 數據
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     * @returns {Object} 預測結果
     */
    async predictWithData(method, data, lotteryTypeId = null) {
        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            data = data.filter(d => d.lotteryType === lotteryTypeId);
        }

        // 獲取彩券規則
        const lotteryRules = getLotteryRules(lotteryTypeId);

        const strategy = this.strategies[method] || this.strategies['frequency'];
        const result = await strategy.predict(data, lotteryRules);

        return {
            ...result,
            lotteryType: lotteryTypeId || 'BIG_LOTTO',
            dataCount: data.length
        };
    }
}
