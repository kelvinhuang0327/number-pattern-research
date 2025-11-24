import { LOTTERY_RULES } from '../../utils/Constants.js';

export class DeviationStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 計算每個號碼的理論平均出現次數
        const expectedFreq = (data.length * 6) / 49;
        const frequency = this.statisticsService.calculateFrequency(data);

        // 計算標準差 (Standard Deviation)
        let sumSqDiff = 0;
        for (let i = 1; i <= range; i++) {
            const diff = (frequency[i] || 0) - expectedFreq;
            sumSqDiff += diff * diff;
        }
        const stdDev = Math.sqrt(sumSqDiff / 49);

        for (let i = 1; i <= range; i++) {
            const freq = frequency[i] || 0;
            const zScore = (freq - expectedFreq) / stdDev;

            // 評分邏輯
            if (zScore < -1.5) {
                // 強烈負偏差 (很久沒出)，預期回歸
                probabilities[i] = 0.8 + Math.abs(zScore) * 0.1;
            } else if (zScore > 2.0) {
                // 強烈正偏差 (太熱)，預期冷卻
                probabilities[i] = 0.2;
            } else if (zScore > 0.5 && zScore < 1.5) {
                // 溫和正偏差 (趨勢剛起)，預期續熱
                probabilities[i] = 0.6 + zScore * 0.1;
            } else {
                probabilities[i] = 0.4; // 平庸
            }
        }

        // 正規化
        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= totalProb;

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 76,
            method: '偏差追蹤模型',
            report: `基於標準差 (StdDev: ${stdDev.toFixed(2)}) 的均值回歸分析。`
        };
    }
}
