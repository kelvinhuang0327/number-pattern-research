import { LOTTERY_RULES } from '../../utils/Constants.js';

export class MonteCarloStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const simulations = 10000; // 模擬次數
        const frequency = this.statisticsService.calculateFrequency(data);
        const totalDraws = data.length;

        // 建立權重池 (基於歷史頻率)
        const pool = [];
        for (let i = 1; i <= range; i++) {
            // 基礎權重 1，加上頻率權重
            // 頻率越高，在池中佔比越高
            const weight = 1 + (frequency[i] / totalDraws) * 10;
            for (let k = 0; k < Math.floor(weight * 10); k++) {
                pool.push(i);
            }
        }

        const simulationResults = {};
        for (let i = 1; i <= range; i++) simulationResults[i] = 0;

        // 執行模擬
        for (let i = 0; i < simulations; i++) {
            const draw = new Set();
            while (draw.size < LOTTERY_RULES.pickCount) {
                const randomIndex = Math.floor(Math.random() * pool.length);
                draw.add(pool[randomIndex]);
            }
            draw.forEach(num => simulationResults[num]++);
        }

        // 計算機率
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = simulationResults[i] / simulations;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
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
