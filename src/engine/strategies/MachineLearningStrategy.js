import { LOTTERY_RULES } from '../../utils/Constants.js';

export class MachineLearningStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        // 簡單的機器學習模擬 (基於特徵加權)
        // 特徵：頻率、近期趨勢、遺漏值、奇偶比、大小比
        const range = LOTTERY_RULES.numberRange.max;
        const scores = {};

        // 初始化分數
        for (let i = 1; i <= range; i++) scores[i] = 0;

        // 1. 頻率特徵 (權重 0.3)
        const frequency = this.statisticsService.calculateFrequency(data);
        const maxFreq = Math.max(...Object.values(frequency)) || 1;
        for (let i = 1; i <= range; i++) {
            scores[i] += (frequency[i] / maxFreq) * 0.3;
        }

        // 2. 近期趨勢 (權重 0.4) - 最近 10 期
        const recentData = data.slice(0, 10);
        const recentFreq = this.statisticsService.calculateFrequency(recentData);
        const maxRecent = Math.max(...Object.values(recentFreq)) || 1;
        for (let i = 1; i <= range; i++) {
            scores[i] += (recentFreq[i] / maxRecent) * 0.4;
        }

        // 3. 遺漏值 (權重 0.2) - 尋找適度遺漏的號碼 (回補理論)
        const missing = this.statisticsService.calculateMissingValues(data);
        const maxMissing = Math.max(...Object.values(missing)) || 1;
        for (let i = 1; i <= range; i++) {
            // 遺漏值過大(>20)可能代表冷門，過小(<3)代表剛出
            // 我們偏好遺漏值在 5-15 之間的號碼
            const m = missing[i];
            let score = 0;
            if (m >= 5 && m <= 15) score = 1;
            else if (m > 15) score = 0.5;
            else score = 0.2;

            scores[i] += score * 0.2;
        }

        // 4. 隨機擾動 (權重 0.1) - 模擬不確定性
        for (let i = 1; i <= range; i++) {
            scores[i] += Math.random() * 0.1;
        }

        // 轉換為機率
        const totalScore = Object.values(scores).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = scores[i] / totalScore;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 80,
            method: '機器學習模型 (特徵加權)',
            report: `基於頻率、近期趨勢與遺漏值的多特徵評分模型。`
        };
    }
}
