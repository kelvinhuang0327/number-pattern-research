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
    /**
     * 獲取數據統計摘要
     * @param {string} lotteryTypeId - 可選的彩券類型 ID，用於過濾
     */
    async getDataStats(lotteryTypeId = null) {
        // 如果使用 IndexedDB，直接獲取統計信息，不載入所有數據
        if (this.dataProcessor.useIndexedDB && this.dataProcessor.indexedDBManager) {
            const stats = await this.dataProcessor.getStats();

            // 如果指定了類型，嘗試獲取該類型的最新一期（需要優化，目前先不獲取詳細日期）
            let latestDraw = 'N/A';
            let latestDate = 'N/A';

            // 嘗試獲取最新一期數據（僅1筆）
            if (lotteryTypeId) {
                try {
                    const latestData = await this.dataProcessor.getDataSmart(lotteryTypeId, 1);
                    if (latestData && latestData.length > 0) {
                        latestDraw = latestData[0].draw;
                        latestDate = latestData[0].date;
                    }
                } catch (e) {
                    console.warn('無法獲取最新一期數據:', e);
                }
            }

            return {
                totalDraws: stats.totalCount,
                dateRange: {
                    start: 'N/A', // IndexedDB 模式下暫不計算完整日期範圍
                    end: latestDate
                },
                latestDraw: latestDraw,
                latestDate: latestDate,
                lotteryTypeCount: stats.byType,
                filteredType: lotteryTypeId
            };
        }

        // 降級模式：記憶體數據（保持原有邏輯）
        let data = await this.dataProcessor.getDataSmart(lotteryTypeId);
        if (data.length === 0) {
            return null;
        }

        // 如果指定了彩券類型，getDataSmart 已經過濾了
        if (lotteryTypeId && !this.dataProcessor.useIndexedDB) {
            data = data.filter(d => d.lotteryType === lotteryTypeId);
            if (data.length === 0) return null;
        }

        const dates = data.map(d => d.date);
        const sortedDates = [...dates].sort();

        // 統計各彩券類型的數量
        const stats = await this.dataProcessor.getStats();

        return {
            totalDraws: data.length,
            dateRange: {
                start: sortedDates[0],
                end: sortedDates[sortedDates.length - 1]
            },
            latestDraw: data[0].draw,
            latestDate: sortedDates[sortedDates.length - 1],
            lotteryTypeCount: stats.byType,
            filteredType: lotteryTypeId
        };
    }

    /**
     * 計算號碼出現頻率
     * @param {Array} data - 數據陣列（可選）
     * @param {string} lotteryTypeId - 彩券類型 ID（可選）
     */
    async calculateFrequency(data = null, lotteryTypeId = null) {
        let targetData = data;
        if (!targetData) {
            targetData = await this.dataProcessor.getDataSmart(lotteryTypeId);
        }

        // 如果指定了彩券類型且數據未過濾 (memory mode fallback)
        if (lotteryTypeId && !data && !this.dataProcessor.useIndexedDB) {
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
    async calculateMissingValues(lotteryTypeId = null) {
        let targetData = await this.dataProcessor.getDataSmart(lotteryTypeId);

        // 如果指定了彩券類型且數據未過濾
        if (lotteryTypeId && !this.dataProcessor.useIndexedDB) {
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
    async getHotNumbers(count = 10, lotteryTypeId = null) {
        const frequency = await this.calculateFrequency(null, lotteryTypeId);
        let targetData = await this.dataProcessor.getDataSmart(lotteryTypeId);

        if (lotteryTypeId && !this.dataProcessor.useIndexedDB) {
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
    async getColdNumbers(count = 10, lotteryTypeId = null) {
        const frequency = await this.calculateFrequency(null, lotteryTypeId);
        let targetData = await this.dataProcessor.getDataSmart(lotteryTypeId);

        if (lotteryTypeId && !this.dataProcessor.useIndexedDB) {
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
    async calculateDistribution(lotteryTypeId = null) {
        let data = await this.dataProcessor.getDataSmart(lotteryTypeId);

        if (lotteryTypeId && !this.dataProcessor.useIndexedDB) {
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
