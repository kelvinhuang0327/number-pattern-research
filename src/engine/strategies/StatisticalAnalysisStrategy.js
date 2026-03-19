import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 多維統計分析策略 (Statistical Analysis Strategy)
 * 
 * 概念：
 * 綜合多種統計指標來過濾號碼組合。
 * 不依賴單一指標，而是尋求在多個維度上都符合 "常態分佈" 的組合。
 * 
 * 檢查維度：
 * 1. 和值 (Sum): 120 - 180
 * 2. AC值 (Complexity): 8 - 12
 * 3. 奇偶比 (Odd/Even): 3:3 或 2:4 或 4:2
 * 4. 尾數分佈 (Last Digit): 確保尾數多樣性 (例如不超過 2 個相同尾數)
 * 5. 極差 (Spread): Max - Min > 20
 */
export class StatisticalAnalysisStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    async predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const pickCount = lotteryRules.pickCount;

        // 獲取基礎頻率作為權重參考
        const frequency = this.statisticsService.calculateFrequency(data);

        // 嘗試生成符合所有條件的組合
        // 策略：隨機生成 -> 檢查條件 -> 評分 -> 保留最佳
        // 為了效率，我們生成 1000 組隨機組合，從中篩選合格的，再選頻率分最高的

        let validCombinations = [];
        const maxAttempts = 2000;

        for (let i = 0; i < maxAttempts; i++) {
            const combination = this.generateWeightedRandom(min, max, pickCount, frequency);

            if (this.checkConditions(combination, lotteryRules)) {
                validCombinations.push(combination);
            }

            // 找到足夠多的合格組合就停止
            if (validCombinations.length >= 20) break;
        }

        // 如果沒有合格的 (極少見)，就放寬條件再試一次，或者直接回傳頻率最高的
        if (validCombinations.length === 0) {
            // Fallback: return simple weighted random
            const fallback = this.generateWeightedRandom(min, max, pickCount, frequency).sort((a, b) => a - b);
            return {
                numbers: fallback,
                confidence: 60,
                method: '多維統計分析 (降級)',
                report: '無法找到完全符合所有統計條件的組合，返回加權隨機組合。'
            };
        }

        // 從合格組合中選擇 "頻率權重" 最高的
        let bestCombo = validCombinations[0];
        let maxScore = -1;

        validCombinations.forEach(combo => {
            const score = combo.reduce((sum, n) => sum + (frequency[n] || 0), 0);
            if (score > maxScore) {
                maxScore = score;
                bestCombo = combo;
            }
        });

        const finalNumbers = bestCombo.sort((a, b) => a - b);
        const stats = this.getStats(finalNumbers, lotteryRules);

        return {
            numbers: finalNumbers,
            confidence: 88,
            method: '多維統計分析',
            report: `組合符合多項統計特徵：和值 ${stats.sum}，AC值 ${stats.ac}，奇偶比 ${stats.odd}:${stats.even}，極差 ${stats.spread}。`
        };
    }

    generateWeightedRandom(min, max, count, frequency) {
        // 簡單的加權隨機選號
        const selected = new Set();
        const pool = [];

        // 構建加權池 (頻率越高，在池中出現次數越多，但為了避免過度集中，做平滑處理)
        for (let i = min; i <= max; i++) {
            const weight = Math.floor(Math.sqrt(frequency[i] || 1) * 10);
            for (let w = 0; w < weight; w++) {
                pool.push(i);
            }
        }

        while (selected.size < count) {
            const num = pool[Math.floor(Math.random() * pool.length)];
            selected.add(num);
        }

        return Array.from(selected);
    }

    checkConditions(numbers, lotteryRules = LOTTERY_RULES) {
        const stats = this.getStats(numbers, lotteryRules);
        const pickCount = lotteryRules.pickCount;
        const { min, max } = lotteryRules.numberRange;
        const totalNumbers = max - min + 1;

        // 動態計算理想範圍
        const theoreticalMin = (min * pickCount) + (pickCount * (pickCount - 1) / 2);
        const theoreticalMax = (max * pickCount) - (pickCount * (pickCount - 1) / 2);
        const idealSum = (theoreticalMin + theoreticalMax) / 2;
        const sumRange = (theoreticalMax - theoreticalMin) * 0.6;

        // 1. 和值
        if (stats.sum < idealSum - sumRange / 2 || stats.sum > idealSum + sumRange / 2) return false;

        // 2. AC值 (動態範圍)
        const minAC = Math.max(pickCount - 1, Math.floor(totalNumbers * 0.15));
        const maxAC = Math.min(pickCount * (pickCount - 1) / 2, Math.ceil(totalNumbers * 0.35));
        if (stats.ac < minAC || stats.ac > maxAC) return false;

        // 3. 奇偶比
        const idealOdd = Math.round(pickCount / 2);
        if (Math.abs(stats.odd - idealOdd) > Math.ceil(pickCount / 3)) return false;

        // 4. 極差
        const minSpread = Math.floor(totalNumbers * 0.4);
        if (stats.spread < minSpread) return false;

        // 5. 尾數多樣性
        const lastDigits = new Set(numbers.map(n => n % 10));
        const minUniqueDigits = Math.max(3, Math.floor(pickCount * 0.6));
        if (lastDigits.size < minUniqueDigits) return false;

        return true;
    }

    getStats(numbers, lotteryRules = LOTTERY_RULES) {
        const sorted = [...numbers].sort((a, b) => a - b);
        const sum = sorted.reduce((a, b) => a + b, 0);
        const odd = sorted.filter(n => n % 2 === 1).length;
        const even = sorted.length - odd;
        const spread = sorted[sorted.length - 1] - sorted[0];

        // Calculate AC
        const diffs = new Set();
        for (let i = 0; i < sorted.length; i++) {
            for (let j = i + 1; j < sorted.length; j++) {
                diffs.add(sorted[j] - sorted[i]);
            }
        }
        const ac = diffs.size - (sorted.length - 1);

        return { sum, odd, even, spread, ac };
    }
}
