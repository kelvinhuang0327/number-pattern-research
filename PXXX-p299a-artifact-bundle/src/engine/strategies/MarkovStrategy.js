import { LOTTERY_RULES } from '../../utils/Constants.js';

export class MarkovStrategy {
    constructor() {
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const transitionMatrix = {}; // { currentNum: { nextNum: count } }

        // 初始化矩陣
        for (let i = min; i <= max; i++) {
            transitionMatrix[i] = {};
            for (let j = min; j <= max; j++) {
                transitionMatrix[i][j] = 0;
            }
        }

        // 建立轉移矩陣
        // data 是降序 (最新在前)，所以我們要反向遍歷或小心處理
        // 轉移是從 舊 -> 新，所以是 data[i+1] -> data[i]
        for (let i = data.length - 1; i > 0; i--) {
            const currentDraw = data[i].numbers;
            const nextDraw = data[i - 1].numbers;

            currentDraw.forEach(currNum => {
                nextDraw.forEach(nextNum => {
                    transitionMatrix[currNum][nextNum]++;
                });
            });
        }

        // 根據最新一期預測下一期
        const lastDraw = data[0].numbers;
        const nextProbabilities = {};
        for (let i = min; i <= max; i++) nextProbabilities[i] = 0;

        lastDraw.forEach(prevNum => {
            const transitions = transitionMatrix[prevNum];
            const totalTransitions = Object.values(transitions).reduce((a, b) => a + b, 0) || 1;

            for (let nextNum = min; nextNum <= max; nextNum++) {
                // P(next | prev)
                const prob = transitions[nextNum] / totalTransitions;
                nextProbabilities[nextNum] += prob;
            }
        });

        // 正規化
        const totalProb = Object.values(nextProbabilities).reduce((a, b) => a + b, 0);
        for (let i = min; i <= max; i++) {
            nextProbabilities[i] = totalProb > 0 ? nextProbabilities[i] / totalProb : 1 / (max - min + 1);
        }

        const sortedNumbers = Object.entries(nextProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: nextProbabilities,
            confidence: 78,
            method: '馬可夫鏈模型',
            report: `基於號碼轉移矩陣的機率預測。`
        };
    }
}
