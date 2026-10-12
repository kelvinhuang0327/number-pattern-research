import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 連號/配對分析策略 (Number Pairs Strategy)
 * 
 * 概念：
 * 分析歷史上常一起出現的號碼 pair (雙星) 或 triple (三星)。
 * 利用 "強關聯" 來構建組合。
 * 
 * 流程：
 * 1. 建立 Co-occurrence Matrix (共現矩陣)。
 * 2. 找出出現頻率最高的 Pairs (前 5 名)。
 * 3. 選擇最強的一組 Pair 作為種子 (Seed)。
 * 4. 尋找與這組 Seed 關聯性強的其他號碼填補剩餘位置。
 */
export class NumberPairsStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    async predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const pickCount = lotteryRules.pickCount;

        // 1. 建立共現矩陣
        const coOccurrence = this.buildCoOccurrenceMatrix(data, min, max);

        // 2. 找出 Top Pairs
        const topPairs = this.getTopPairs(coOccurrence, 10);

        // 3. 選擇最強 Pair 作為種子
        // 為了避免每次都一樣，從 Top 5 中隨機選一個
        const seedPairObj = topPairs[Math.floor(Math.random() * Math.min(5, topPairs.length))];
        const seedPair = seedPairObj.pair; // [num1, num2]

        const selectedNumbers = new Set(seedPair);

        // 4. 填補剩餘號碼
        // 策略：找出與目前已選號碼 "平均關聯度" 最高的號碼
        while (selectedNumbers.size < pickCount) {
            let bestCandidate = -1;
            let maxAffinity = -1;

            for (let i = min; i <= max; i++) {
                if (selectedNumbers.has(i)) continue;

                // 計算 i 與已選號碼的關聯度總和
                let affinity = 0;
                selectedNumbers.forEach(selected => {
                    affinity += this.getPairCount(coOccurrence, i, selected);
                });

                // 加入一點隨機性防止死板
                affinity *= (0.9 + Math.random() * 0.2);

                if (affinity > maxAffinity) {
                    maxAffinity = affinity;
                    bestCandidate = i;
                }
            }

            if (bestCandidate !== -1) {
                selectedNumbers.add(bestCandidate);
            } else {
                // Should not happen, but fallback to random
                let random;
                do {
                    random = Math.floor(Math.random() * (max - min + 1)) + min;
                } while (selectedNumbers.has(random));
                selectedNumbers.add(random);
            }
        }

        const finalNumbers = Array.from(selectedNumbers).sort((a, b) => a - b);

        return {
            numbers: finalNumbers,
            confidence: 82,
            method: '連號/配對分析',
            report: `基於歷史共現分析，選用強力組合 [${seedPair.join(', ')}] (出現 ${seedPairObj.count} 次) 作為核心，並延伸關聯號碼。`
        };
    }

    buildCoOccurrenceMatrix(data, min, max) {
        const matrix = {}; // key: "min,max", value: count

        data.forEach(draw => {
            const nums = draw.numbers;
            for (let i = 0; i < nums.length; i++) {
                for (let j = i + 1; j < nums.length; j++) {
                    const n1 = nums[i];
                    const n2 = nums[j];
                    const key = n1 < n2 ? `${n1},${n2}` : `${n2},${n1}`;
                    matrix[key] = (matrix[key] || 0) + 1;
                }
            }
        });

        return matrix;
    }

    getPairCount(matrix, n1, n2) {
        const key = n1 < n2 ? `${n1},${n2}` : `${n2},${n1}`;
        return matrix[key] || 0;
    }

    getTopPairs(matrix, count) {
        return Object.entries(matrix)
            .map(([key, val]) => {
                const [n1, n2] = key.split(',').map(Number);
                return { pair: [n1, n2], count: val };
            })
            .sort((a, b) => b.count - a.count)
            .slice(0, count);
    }
}
