import { LOTTERY_RULES } from '../utils/Constants.js';
import { getLotteryTypeById } from '../utils/LotteryTypes.js';

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
     * @param {string} lotteryTypeId - 可選的彩券類型 ID，用於過濾
     */
    getDataStats(lotteryTypeId = null) {
        let data = this.dataProcessor.getData();
        if (data.length === 0) {
            return null;
        }

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            data = data.filter(d => d.lotteryType === lotteryTypeId);
            if (data.length === 0) return null;
        }

        const dates = data.map(d => d.date);
        const sortedDates = [...dates].sort();

        // 統計各彩券類型的數量
        const allData = this.dataProcessor.getData();
        const typeCount = {};
        allData.forEach(d => {
            const type = d.lotteryType || 'UNKNOWN';
            typeCount[type] = (typeCount[type] || 0) + 1;
        });

        return {
            totalDraws: data.length,
            dateRange: {
                start: sortedDates[0],
                end: sortedDates[sortedDates.length - 1]
            },
            latestDraw: data[0].draw,
            latestDate: sortedDates[sortedDates.length - 1],
            lotteryTypeCount: typeCount,  // 新增：各彩券類型數量
            filteredType: lotteryTypeId    // 新增：當前過濾的類型
        };
    }

    /**
     * 計算號碼出現頻率
     * @param {Array} data - 數據陣列（可選）
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    calculateFrequency(data = null, lotteryTypeId = null) {
        let targetData = data || this.dataProcessor.getData();

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            targetData = targetData.filter(d => d.lotteryType === lotteryTypeId);
        }

        // 獲取彩券規則
        const lotteryRules = this._getLotteryRules(lotteryTypeId);
        const frequency = {};

        // 使用動態範圍初始化頻率
        for (let i = lotteryRules.numberRange.min; i <= lotteryRules.numberRange.max; i++) {
            frequency[i] = 0;
        }

        // 計算每個號碼出現次數
        targetData.forEach(draw => {
            draw.numbers.forEach(num => {
                if (frequency.hasOwnProperty(num)) {
                    frequency[num]++;
                }
            });
        });

        return frequency;
    }

    /**
     * 計算號碼遺漏值（距離上次出現的期數）
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    calculateMissingValues(lotteryTypeId = null) {
        let targetData = this.dataProcessor.getData();

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            targetData = targetData.filter(d => d.lotteryType === lotteryTypeId);
        }

        // 獲取彩券規則
        const lotteryRules = this._getLotteryRules(lotteryTypeId);
        const missing = {};

        // 初始化
        for (let i = lotteryRules.numberRange.min; i <= lotteryRules.numberRange.max; i++) {
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

        for (let num = lotteryRules.numberRange.min; num <= lotteryRules.numberRange.max; num++) {
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
     * @param {number} count - 要返回的號碼數量
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    getHotNumbers(count = 10, lotteryTypeId = null) {
        const frequency = this.calculateFrequency(null, lotteryTypeId);
        let targetData = this.dataProcessor.getData();

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            targetData = targetData.filter(d => d.lotteryType === lotteryTypeId);
        }

        const totalDraws = targetData.length;
        const sorted = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: totalDraws > 0 ? ((freq / totalDraws) * 100).toFixed(1) : '0.0'
        }));
    }

    /**
     * 獲取冷門號碼（出現頻率最低）
     * @param {number} count - 要返回的號碼數量
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    getColdNumbers(count = 10, lotteryTypeId = null) {
        const frequency = this.calculateFrequency(null, lotteryTypeId);
        let targetData = this.dataProcessor.getData();

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            targetData = targetData.filter(d => d.lotteryType === lotteryTypeId);
        }

        const totalDraws = targetData.length;
        const sorted = Object.entries(frequency)
            .sort((a, b) => a[1] - b[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: totalDraws > 0 ? ((freq / totalDraws) * 100).toFixed(1) : '0.0'
        }));
    }

    /**
     * 計算號碼分佈（按區間）
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    calculateDistribution(lotteryTypeId = null) {
        let data = this.dataProcessor.getData();

        // 如果指定了彩券類型，進行過濾
        if (lotteryTypeId) {
            data = data.filter(d => d.lotteryType === lotteryTypeId);
        }

        // 獲取彩券規則
        const lotteryRules = this._getLotteryRules(lotteryTypeId);
        const { min, max } = lotteryRules.numberRange;
        const range = max - min + 1;
        const zoneSize = Math.ceil(range / 5);

        // 動態創建區間
        const distribution = {};
        for (let i = 0; i < 5; i++) {
            const zoneStart = min + (i * zoneSize);
            const zoneEnd = Math.min(zoneStart + zoneSize - 1, max);
            const zoneKey = `${zoneStart}-${zoneEnd}`;
            distribution[zoneKey] = 0;
        }

        // 計算每個區間的出現次數
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                for (const zoneKey in distribution) {
                    const [start, end] = zoneKey.split('-').map(Number);
                    if (num >= start && num <= end) {
                        distribution[zoneKey]++;
                        break;
                    }
                }
            });
        });

        // 轉換為百分比
        const totalNumbers = data.length * lotteryRules.pickCount;
        if (totalNumbers > 0) {
            for (const zone in distribution) {
                distribution[zone] = ((distribution[zone] / totalNumbers) * 100).toFixed(1);
            }
        }

        return distribution;
    }

    /**
     * 獲取彩券規則
     * @param {string} lotteryTypeId - 彩券類型 ID
     * @returns {Object} 彩券規則
     * @private
     */
    _getLotteryRules(lotteryTypeId) {
        if (!lotteryTypeId) {
            return LOTTERY_RULES; // 預設為大樂透
        }

        // 從 LotteryTypes 中獲取規則
        const lotteryType = getLotteryTypeById(lotteryTypeId);

        if (!lotteryType) {
            return LOTTERY_RULES; // 找不到時使用預設值
        }

        // 轉換為 LOTTERY_RULES 格式
        return {
            numberRange: lotteryType.numberRange,
            pickCount: lotteryType.pickCount,
            hasSpecialNumber: lotteryType.hasSpecialNumber,
            specialNumberRange: lotteryType.specialNumberRange || lotteryType.numberRange
        };
    }
}
