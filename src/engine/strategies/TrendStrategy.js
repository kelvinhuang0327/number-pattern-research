import { LOTTERY_RULES } from '../../utils/Constants.js';

export class TrendStrategy {
    constructor() {
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const weightedFrequency = {};
        const { min, max } = lotteryRules.numberRange;

        // 初始化
        for (let i = min; i <= max; i++) {
            weightedFrequency[i] = 0;
        }

        const lambda = 0.05; // 衰減係數
        const n = data.length;

        data.forEach((draw, index) => {
            // index 0 是最新的 (因為 data 是降序)，但在計算趨勢時，我們通常認為 index 0 是最新的
            // 原代碼邏輯：age = n - index - 1 (假設 index 0 是最舊的)
            // 但 DataProcessor.getDataRange 返回的是 slice(0, size)，且 DataProcessor 排序是降序 (最新在前)
            // 所以 data[0] 是最新的，age 應該是 0

            // 修正邏輯：假設 data[0] 是最新的
            const age = index;
            const weight = Math.exp(-lambda * age);

            draw.numbers.forEach(num => {
                if (weightedFrequency.hasOwnProperty(num)) {
                    weightedFrequency[num] += weight;
                }
            });
        });

        const totalWeight = Object.values(weightedFrequency).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = min; i <= max; i++) {
            probabilities[i] = weightedFrequency[i] / totalWeight;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: this.calculateConfidence(sortedNumbers),
            method: '趨勢回歸分析 (指數衰減)',
            report: `基於 ${data.length} 期數據的趨勢加權分析。`
        };
    }

    calculateConfidence(sortedNumbers) {
        // 簡單估算
        return 75;
    }
}
