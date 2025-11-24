import { LOTTERY_RULES } from '../../utils/Constants.js';

export class CoOccurrenceStrategy {
    constructor() {
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        // 1. 先找出「領頭羊」：這裡使用最近一期的號碼作為基準
        const lastDraw = data[0]; // data[0] is latest
        const leaders = lastDraw.numbers;

        // 2. 建立共現矩陣
        const coOccurrence = {};
        for (let i = 1; i <= range; i++) coOccurrence[i] = 0;

        // 3. 掃描歷史資料
        data.forEach(draw => {
            const nums = draw.numbers;
            // 檢查這一期是否包含任一領頭號碼
            const leadersInDraw = nums.filter(n => leaders.includes(n));

            if (leadersInDraw.length > 0) {
                // 如果有領頭號碼，則這一期的其他號碼都獲得加分
                nums.forEach(n => {
                    if (!leaders.includes(n)) { // 不加分自己
                        // 加分權重：跟越多領頭羊一起出，分數越高
                        coOccurrence[n] += leadersInDraw.length;
                    }
                });
            }
        });

        // 4. 轉換為機率
        const totalScore = Object.values(coOccurrence).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = totalScore > 0 ? coOccurrence[i] / totalScore : 0;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 72,
            method: '共現分析模型',
            report: `基於最近一期號碼 (${leaders.join(', ')}) 的共現性分析。`
        };
    }
}
