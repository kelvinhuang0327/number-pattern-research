import { LOTTERY_RULES } from '../../utils/Constants.js';

export class FrequencyStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const frequency = this.statisticsService.calculateFrequency(data);
        const totalDraws = data.length;
        const probabilities = {};

        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = frequency[i] / totalDraws;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: this.calculateConfidence(sortedNumbers, probabilities),
            method: '頻率回歸分析',
            report: `基於 ${totalDraws} 期數據的頻率分析。`
        };
    }

    calculateConfidence(sortedNumbers, probabilities) {
        // 簡單信心度計算：前6名機率總和 / 平均機率總和
        const topProbSum = sortedNumbers.reduce((sum, item) => sum + item.probability, 0);
        const avgProb = 1 / 49; // 理論平均機率
        const expectedSum = avgProb * 6;

        // 如果前6名機率顯著高於平均，信心度高
        let confidence = (topProbSum / expectedSum) * 50;
        return Math.min(Math.round(confidence), 95);
    }
}
