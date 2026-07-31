import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 和值範圍與AC值策略 (SumRangeStrategy)
 * 基於統計學原理，大樂透 6 個號碼的和值通常落在特定範圍內。
 * 根據歷史數據分析，和值的平均值約為 150，標準分佈範圍約在 120-180。
 * 
 * AC值（Arithmetic Complexity）衡量號碼組合的複雜度，理論範圍 5-15，
 * 大樂透開獎號碼的AC值通常集中在 8-12 之間。
 *
 * 策略流程：
 * 1. 計算歷史開獎的和值分佈，找出最常出現的和值範圍
 * 2. 分析AC值分佈，找出最佳AC值範圍
 * 3. 生成候選號碼組合
 * 4. 篩選和值與AC值在目標範圍內的組合
 * 5. 結合頻率分析選擇最佳組合
 */
export class SumRangeStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
        // AC值的理論範圍
        this.minAC = 5;
        this.maxAC = 15;
    }

    /**
     * 計算號碼組合的和值
     */
    calculateSum(numbers) {
        return numbers.reduce((sum, num) => sum + num, 0);
    }

    /**
     * 計算號碼組合的AC值
     */
    calculateAC(numbers) {
        const differences = new Set();

        // 計算所有兩兩差值
        for (let i = 0; i < numbers.length; i++) {
            for (let j = i + 1; j < numbers.length; j++) {
                const diff = Math.abs(numbers[i] - numbers[j]);
                differences.add(diff);
            }
        }

        return differences.size;
    }

    /**
     * 分析歷史數據的AC值分佈
     */
    analyzeACDistribution(data) {
        const acValues = data.map(draw => this.calculateAC(draw.numbers));
        const avgAC = acValues.reduce((a, b) => a + b, 0) / acValues.length;

        // 統計AC值分佈
        const acCounts = {};
        acValues.forEach(ac => {
            acCounts[ac] = (acCounts[ac] || 0) + 1;
        });

        // 找出最常見的AC值範圍
        const sortedACs = Object.entries(acCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([ac]) => parseInt(ac));

        return {
            average: avgAC,
            commonRange: [Math.min(...sortedACs), Math.max(...sortedACs)],
            distribution: acCounts
        };
    }

    /**
     * 分析歷史數據的和值分佈
     */
    analyzeSumDistribution(data, lotteryRules) {
        const sums = data.map(draw => this.calculateSum(draw.numbers));
        const avg = sums.reduce((a, b) => a + b, 0) / sums.length;

        // 計算標準差
        const variance = sums.reduce((sum, val) => sum + Math.pow(val - avg, 2), 0) / sums.length;
        const stdDev = Math.sqrt(variance);

        // 計算理論最小和最大值
        const { min, max } = lotteryRules.numberRange;
        const pickCount = lotteryRules.pickCount;
        const theoreticalMin = (min * pickCount) + (pickCount * (pickCount - 1) / 2);
        const theoreticalMax = (max * pickCount) - (pickCount * (pickCount - 1) / 2);

        return {
            average: avg,
            stdDev: stdDev,
            min: Math.max(avg - stdDev, theoreticalMin),
            max: Math.min(avg + stdDev, theoreticalMax)
        };
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const pickCount = lotteryRules.pickCount;

        if (data.length < 10) {
            // 數據不足時使用簡單的頻率策略
            const frequency = this.statisticsService.calculateFrequency(data);
            const sorted = [];
            for (let i = min; i <= max; i++) {
                sorted.push({ number: i, freq: frequency[i] || 0 });
            }
            sorted.sort((a, b) => b.freq - a.freq);
            const selected = sorted.slice(0, pickCount).map(item => item.number).sort((a, b) => a - b);

            return {
                numbers: selected,
                confidence: 50,
                method: '和值範圍策略',
                report: `數據不足，使用頻率分析。預測號碼和值: ${this.calculateSum(selected)}`
            };
        }

        // 分析和值分佈
        const sumStats = this.analyzeSumDistribution(data, lotteryRules);
        const targetMin = Math.floor(sumStats.min);
        const targetMax = Math.ceil(sumStats.max);

        // 分析AC值分佈
        const acStats = this.analyzeACDistribution(data);
        const targetACMin = acStats.commonRange[0];
        const targetACMax = acStats.commonRange[1];

        // 計算頻率
        const frequency = this.statisticsService.calculateFrequency(data);

        // 將號碼按頻率排序
        const sortedNumbers = [];
        for (let i = min; i <= max; i++) {
            sortedNumbers.push({ number: i, freq: frequency[i] || 0 });
        }
        sortedNumbers.sort((a, b) => b.freq - a.freq);

        // 貪心算法：從高頻號碼開始組合，控制和值在目標範圍內
        let bestCombination = null;
        let bestScore = -1;

        // 嘗試多個起始點
        for (let startIdx = 0; startIdx < Math.min(20, sortedNumbers.length - pickCount); startIdx++) {
            const combination = [sortedNumbers[startIdx].number];
            const used = new Set([sortedNumbers[startIdx].number]);
            let currentSum = sortedNumbers[startIdx].number;
            let freqScore = sortedNumbers[startIdx].freq;

            // 依序添加號碼
            for (let i = 0; i < sortedNumbers.length && combination.length < pickCount; i++) {
                if (used.has(sortedNumbers[i].number)) continue;

                const newSum = currentSum + sortedNumbers[i].number;
                const remaining = pickCount - combination.length - 1;

                // 預估最小和最大可能和值
                const minPossible = newSum + min * remaining;
                const maxPossible = newSum + max * remaining;

                // 檢查是否可能在目標範圍內
                if (maxPossible >= targetMin && minPossible <= targetMax) {
                    combination.push(sortedNumbers[i].number);
                    used.add(sortedNumbers[i].number);
                    currentSum = newSum;
                    freqScore += sortedNumbers[i].freq;
                }
            }

            // 檢查組合是否完整且和值在範圍內
            if (combination.length === pickCount) {
                const sum = this.calculateSum(combination);
                const ac = this.calculateAC(combination);

                // 檢查和值和AC值都在範圍內
                if (sum >= targetMin && sum <= targetMax &&
                    ac >= targetACMin && ac <= targetACMax) {
                    // 計算分數：頻率分數 + 和值接近平均值的加分 + AC值接近平均值的加分
                    const sumDeviation = Math.abs(sum - sumStats.average);
                    const acDeviation = Math.abs(ac - acStats.average);
                    const score = freqScore - sumDeviation * 0.1 - acDeviation * 0.5;

                    if (score > bestScore) {
                        bestScore = score;
                        bestCombination = [...combination].sort((a, b) => a - b);
                    }
                }
            }
        }

        // 如果沒有找到符合的組合，使用簡單頻率策略
        if (!bestCombination) {
            const selected = sortedNumbers.slice(0, pickCount).map(item => item.number).sort((a, b) => a - b);
            const sum = this.calculateSum(selected);

            return {
                numbers: selected,
                confidence: 55,
                method: '和值範圍策略',
                report: `無法在和值範圍 ${targetMin}-${targetMax} 內找到組合，使用頻率策略。預測號碼和值: ${sum}`
            };
        }

        const predictedSum = this.calculateSum(bestCombination);
        const predictedAC = this.calculateAC(bestCombination);
        const confidence = Math.min(85, 60 + (1 - Math.abs(predictedSum - sumStats.average) / sumStats.stdDev) * 20);

        return {
            numbers: bestCombination,
            confidence: Math.round(confidence),
            method: '和值與AC值範圍策略',
            report: `根據 ${data.length} 期數據，和值平均 ${sumStats.average.toFixed(1)} (範圍: ${targetMin}-${targetMax})，AC值平均 ${acStats.average.toFixed(1)} (範圍: ${targetACMin}-${targetACMax})。預測號碼和值: ${predictedSum}，AC值: ${predictedAC}`
        };
    }
}
