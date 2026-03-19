import { LOTTERY_RULES } from '../../utils/Constants.js';

export class DeviationStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const totalNumbers = max - min + 1;
        const probabilities = {};

        // 計算每個號碼的理論平均出現次數
        const expectedFreq = (data.length * lotteryRules.pickCount) / totalNumbers;
        const frequency = this.statisticsService.calculateFrequency(data);

        // 計算標準差 (Standard Deviation)
        let sumSqDiff = 0;
        for (let i = min; i <= max; i++) {
            const diff = (frequency[i] || 0) - expectedFreq;
            sumSqDiff += diff * diff;
        }
        const stdDev = Math.sqrt(sumSqDiff / totalNumbers);

        for (let i = min; i <= max; i++) {
            const freq = frequency[i] || 0;
            const zScore = stdDev > 0 ? (freq - expectedFreq) / stdDev : 0;

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
        for (let i = min; i <= max; i++) {
            probabilities[i] = totalProb > 0 ? probabilities[i] / totalProb : 1 / totalNumbers;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
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
