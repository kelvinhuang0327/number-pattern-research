import { LOTTERY_RULES } from '../../utils/Constants.js';

export class MarkovStrategy {
    constructor() {
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const transitionMatrix = {}; // { currentNum: { nextNum: count } }

        // 初始化矩陣
        for (let i = 1; i <= range; i++) {
            transitionMatrix[i] = {};
            for (let j = 1; j <= range; j++) {
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
        for (let i = 1; i <= range; i++) nextProbabilities[i] = 0;

        lastDraw.forEach(prevNum => {
            const transitions = transitionMatrix[prevNum];
            const totalTransitions = Object.values(transitions).reduce((a, b) => a + b, 0) || 1;

            for (let nextNum = 1; nextNum <= range; nextNum++) {
                // P(next | prev)
                const prob = transitions[nextNum] / totalTransitions;
                nextProbabilities[nextNum] += prob;
            }
        });

        // 正規化
        const totalProb = Object.values(nextProbabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) {
            nextProbabilities[i] /= totalProb;
        }

        const sortedNumbers = Object.entries(nextProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
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
