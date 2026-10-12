/**
 * Quick Prediction Service
 * 提供智能快速預測功能，自動選擇最佳參數
 */

import { LOTTERY_TYPES } from '../utils/LotteryTypes.js';

export class QuickPredictionService {
    /**
     * 根據彩券類型獲取推薦的預測方法
     * @param {string} lotteryTypeId - 彩券類型 ID
     * @returns {string} 推薦的預測方法
     */
    static getRecommendedMethod(lotteryTypeId) {
        const methodMap = {
            'BIG_LOTTO': 'collaborative_hybrid',
            'BIG_LOTTO_BONUS': 'collaborative_hybrid',
            'DAILY_CASH_539': 'collaborative_hybrid',
            'POWER_BALL': 'collaborative_hybrid',
            'STAR_3': 'statistical_analysis',
            'STAR_4': 'statistical_analysis',
            'LOTTO_39': 'ensemble_weighted',
            'LOTTO_38': 'ensemble_weighted',
            'LOTTO_49': 'ensemble_weighted',
            'BINGO_BINGO': 'frequency',
            'DOUBLE_WIN': 'trend',
            'LOTTO_6_38': 'ensemble_weighted'
        };

        return methodMap[lotteryTypeId] || 'collaborative_hybrid';
    }

    /**
     * 根據彩券類型和數據量獲取推薦的樣本大小
     * @param {string} lotteryTypeId - 彩券類型 ID
     * @param {number} totalDraws - 總期數
     * @returns {number|string} 推薦的樣本大小
     */
    static getRecommendedSampleSize(lotteryTypeId, totalDraws) {
        const lotteryType = LOTTERY_TYPES[lotteryTypeId];

        if (!lotteryType) {
            return 50; // 預設值
        }

        // 使用彩券類型的推薦樣本大小
        const recommended = lotteryType.recommendedSampleSize || 50;

        // 如果總期數少於推薦值，使用全部數據
        if (totalDraws < recommended) {
            return 'all';
        }

        // 如果總期數遠大於推薦值，可以使用更大的樣本
        if (totalDraws > recommended * 3) {
            return Math.min(recommended * 2, 100);
        }

        return recommended;
    }

    /**
     * 獲取預測方法的顯示名稱
     * @param {string} method - 預測方法 ID
     * @returns {string} 顯示名稱
     */
    static getMethodDisplayName(method) {
        const methodNames = {
            'frequency': '頻率分析',
            'trend': '趨勢分析',
            'bayesian': '貝葉斯機率',
            'montecarlo': '蒙地卡羅模擬',
            'markov': '馬可夫鏈',
            'deviation': '偏差追蹤',
            'ensemble_weighted': '加權集成',
            'ensemble_boosting': 'Boosting 集成',
            'ensemble_combined': '綜合集成',
            'ensemble_cooccurrence': '共現集成',
            'ensemble_features': '特徵集成',
            'ml_features': '特徵加權 ML',
            'ml_forest': '隨機森林 ML',
            'ml_genetic': '遺傳算法 ML',
            'collaborative_hybrid': '混合模式',
            'collaborative_relay': '接力模式',
            'collaborative_coop': '合作模式',
            'odd_even_balance': '奇偶比例',
            'zone_balance': '區間平衡',
            'hot_cold_mix': '冷熱號混合',
            'sum_range': '和值+AC值',
            'wheeling': '組合輪轉',
            'number_pairs': '連號配對',
            'statistical_analysis': '多維統計'
        };

        return methodNames[method] || method;
    }

    /**
     * 獲取快速預測配置
     * @param {string} lotteryTypeId - 彩券類型 ID
     * @param {number} totalDraws - 總期數
     * @returns {Object} 快速預測配置
     */
    static getQuickPredictConfig(lotteryTypeId, totalDraws) {
        const method = this.getRecommendedMethod(lotteryTypeId);
        const sampleSize = this.getRecommendedSampleSize(lotteryTypeId, totalDraws);
        const lotteryType = LOTTERY_TYPES[lotteryTypeId];

        return {
            method,
            methodName: this.getMethodDisplayName(method),
            sampleSize,
            lotteryType,
            description: `使用 ${this.getMethodDisplayName(method)} 方法，分析最近 ${sampleSize === 'all' ? '全部' : sampleSize + ' 期'} 數據`
        };
    }

    /**
     * 獲取樣本大小提示文字
     * @param {string} lotteryTypeId - 彩券類型 ID
     * @param {number} totalDraws - 總期數
     * @returns {string} 提示文字
     */
    static getSampleSizeHint(lotteryTypeId, totalDraws) {
        const recommended = this.getRecommendedSampleSize(lotteryTypeId, totalDraws);
        const lotteryType = LOTTERY_TYPES[lotteryTypeId];

        if (!lotteryType) {
            return '';
        }

        if (recommended === 'all') {
            return '(建議：使用全部數據)';
        }

        return `(建議：${recommended} 期)`;
    }
}
