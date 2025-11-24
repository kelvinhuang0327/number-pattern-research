import { LOTTERY_RULES } from '../utils/Constants.js';

/**
 * 統計服務
 * 負責計算各種統計數據
 */
export class StatisticsService {
    constructor(dataProcessor) {
        this.dataProcessor = dataProcessor;
    }

    /**
     * 獲取數據統計摘要
     */
    getDataStats() {
        const data = this.dataProcessor.getData();
        if (data.length === 0) {
            return null;
        }

        const dates = data.map(d => d.date);
        const sortedDates = [...dates].sort();

        return {
            totalDraws: data.length,
            dateRange: {
                start: sortedDates[0],
                end: sortedDates[sortedDates.length - 1]
            },
            latestDraw: data[0].draw // 假設數據是降序
        };
    }

    /**
     * 計算號碼出現頻率
     */
    calculateFrequency(data = null) {
        const targetData = data || this.dataProcessor.getData();
        const frequency = {};

        // 初始化1-49的頻率為0
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            frequency[i] = 0;
        }

        // 計算每個號碼出現次數
        targetData.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });

        return frequency;
    }

    /**
     * 計算號碼遺漏值（距離上次出現的期數）
     */
    calculateMissingValues(data = null) {
        const targetData = data || this.dataProcessor.getData();
        const missing = {};

        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            missing[i] = 0;
        }

        // 從最新一期往回計算
        // 注意：targetData 預設是降序（最新在前），所以我們應該正向遍歷，或者如果是升序則反向
        // 這裡假設 targetData 是降序 (index 0 is latest)

        // 為了計算準確，我們需要知道每個號碼"最近一次"出現的位置
        // 其實遺漏值就是：目前期數 - 最近一次出現的期數
        // 簡單算法：遍歷數據，如果號碼出現了，且還沒記錄過遺漏值（或遺漏值為0代表剛出），則...
        // 更簡單的算法：
        // 對於每個號碼，從 index 0 開始找，找到第一次出現的位置 index，該 index 就是遺漏值
        // 如果都沒出現，遺漏值就是 length

        for (let num = LOTTERY_RULES.numberRange.min; num <= LOTTERY_RULES.numberRange.max; num++) {
            let found = false;
            for (let i = 0; i < targetData.length; i++) {
                if (targetData[i].numbers.includes(num)) {
                    missing[num] = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                missing[num] = targetData.length;
            }
        }

        return missing;
    }

    /**
     * 獲取熱門號碼（出現頻率最高）
     */
    getHotNumbers(count = 10) {
        const frequency = this.calculateFrequency();
        const totalDraws = this.dataProcessor.getData().length;
        const sorted = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: ((freq / totalDraws) * 100).toFixed(1)
        }));
    }

    /**
     * 獲取冷門號碼（出現頻率最低）
     */
    getColdNumbers(count = 10) {
        const frequency = this.calculateFrequency();
        const totalDraws = this.dataProcessor.getData().length;
        const sorted = Object.entries(frequency)
            .sort((a, b) => a[1] - b[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: ((freq / totalDraws) * 100).toFixed(1)
        }));
    }

    /**
     * 計算號碼分佈（按區間）
     */
    calculateDistribution() {
        const data = this.dataProcessor.getData();
        const distribution = {
            '1-10': 0,
            '11-20': 0,
            '21-30': 0,
            '31-40': 0,
            '41-49': 0
        };

        // 計算每個區間的出現次數
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                if (num <= 10) distribution['1-10']++;
                else if (num <= 20) distribution['11-20']++;
                else if (num <= 30) distribution['21-30']++;
                else if (num <= 40) distribution['31-40']++;
                else distribution['41-49']++;
            });
        });

        // 轉換為百分比
        const totalNumbers = data.length * LOTTERY_RULES.pickCount;
        if (totalNumbers > 0) {
            for (const zone in distribution) {
                distribution[zone] = ((distribution[zone] / totalNumbers) * 100).toFixed(1);
            }
        }

        return distribution;
    }
}
