import { LOTTERY_RULES } from '../../utils/Constants.js';

export class MonteCarloStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const pickCount = lotteryRules.pickCount;
        const simulations = 10000; // 模擬次數
        const frequency = this.statisticsService.calculateFrequency(data);
        const totalDraws = data.length;

        // 建立權重池 (基於歷史頻率)
        const pool = [];
        for (let i = min; i <= max; i++) {
            // 基礎權重 1，加上頻率權重
            // 頻率越高，在池中佔比越高
            const weight = 1 + ((frequency[i] || 0) / totalDraws) * 10;
            for (let k = 0; k < Math.floor(weight * 10); k++) {
                pool.push(i);
            }
        }

        const simulationResults = {};
        for (let i = min; i <= max; i++) simulationResults[i] = 0;

        // 執行模擬
        for (let i = 0; i < simulations; i++) {
            const draw = new Set();
            while (draw.size < pickCount) {
                const randomIndex = Math.floor(Math.random() * pool.length);
                draw.add(pool[randomIndex]);
            }
            draw.forEach(num => simulationResults[num]++);
        }

        // 計算機率
        const probabilities = {};
        for (let i = min; i <= max; i++) {
            probabilities[i] = simulationResults[i] / simulations;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 75,
            method: '蒙地卡羅模擬',
            report: `執行 ${simulations} 次隨機模擬的結果。`
        };
    }
}
