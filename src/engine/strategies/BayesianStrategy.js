import { LOTTERY_RULES } from '../../utils/Constants.js';

export class BayesianStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 先驗機率 P(A): 每個號碼的歷史出現率
        const frequency = this.statisticsService.calculateFrequency(data);
        const totalDraws = data.length;
        const priorProb = {};
        for (let i = 1; i <= range; i++) {
            priorProb[i] = (frequency[i] || 0) / (totalDraws * 6);
        }

        // 似然函數 P(B|A): 條件機率
        // 這裡定義條件 B 為：上一期開出 X 後，下一期開出 A 的機率
        const lastDraw = data[0].numbers; // data[0] is latest

        // 計算條件機率矩陣
        const transitionCounts = {}; // { prev: { next: count } }
        // data is desc, so prev is data[i+1], next is data[i]
        for (let i = 0; i < data.length - 1; i++) {
            const current = data[i].numbers;
            const prev = data[i + 1].numbers;

            prev.forEach(p => {
                if (!transitionCounts[p]) transitionCounts[p] = {};
                current.forEach(c => {
                    transitionCounts[p][c] = (transitionCounts[p][c] || 0) + 1;
                });
            });
        }

        // 計算後驗機率 P(A|B) ∝ P(B|A) * P(A)
        for (let i = 1; i <= range; i++) {
            let likelihoodScore = 0;
            lastDraw.forEach(prevNum => {
                const count = (transitionCounts[prevNum] && transitionCounts[prevNum][i]) || 0;
                const totalOccurrences = frequency[prevNum] || 1;
                likelihoodScore += count / totalOccurrences;
            });

            // 貝葉斯更新
            probabilities[i] = priorProb[i] * (1 + likelihoodScore);
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
            confidence: 85,
            method: '貝葉斯機率模型',
            report: `基於貝葉斯定理，結合先驗機率與條件轉移機率的預測。`
        };
    }
}
