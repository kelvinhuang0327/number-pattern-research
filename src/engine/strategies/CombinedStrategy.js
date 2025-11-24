import { LOTTERY_RULES } from '../../utils/Constants.js';

export class CombinedStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const frequency = {};
        const weighted = {};
        const missing = this.statisticsService.calculateMissingValues(data);
        const range = LOTTERY_RULES.numberRange;
        const n = data.length;

        // 初始化
        for (let i = range.min; i <= range.max; i++) {
            frequency[i] = 0;
            weighted[i] = 0;
        }

        const lambda = 0.05;
        data.forEach((draw, index) => {
            const age = index; // 假設 data[0] 是最新的
            const expWeight = Math.exp(-lambda * age);
            draw.numbers.forEach(num => {
                frequency[num]++;
                weighted[num] += expWeight;
            });
        });

        // 動態權重
        const isSmallSample = n < 50;
        const isLargeSample = n > 300;

        const weights = {
            frequency: isLargeSample ? 0.40 : isSmallSample ? 0.25 : 0.35,
            trend: isSmallSample ? 0.40 : isLargeSample ? 0.25 : 0.30,
            missing: 0.20,
            tail: 0.15 // 暫時省略尾數分析，或設為0
        };

        const probabilities = {};
        const maxMissing = Math.max(...Object.values(missing)) || 1;
        const totalWeighted = Object.values(weighted).reduce((a, b) => a + b, 0) || 1;

        for (let i = range.min; i <= range.max; i++) {
            const freqScore = (frequency[i] / n) * weights.frequency;
            const trendScore = (weighted[i] / totalWeighted) * weights.trend;
            const missingScore = (missing[i] / maxMissing) * weights.missing;

            probabilities[i] = freqScore + trendScore + missingScore;
        }

        // 正規化
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = range.min; i <= range.max; i++) {
            probabilities[i] = probabilities[i] / sumProb;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 85,
            method: '綜合回歸模型',
            report: `綜合頻率、趨勢與遺漏值的多維度分析。`
        };
    }
}
