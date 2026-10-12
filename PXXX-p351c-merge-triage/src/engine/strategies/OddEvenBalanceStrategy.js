import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 奇偶比例策略 (OddEvenBalanceStrategy)
 * 依據歷史資料中奇數與偶數的出現次數，選擇出現較多的奇偶類別，
 * 從該類別中挑選出頻率最高的號碼作為預測結果。
 */
export class OddEvenBalanceStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;

        // 計算每個號碼的出現頻率
        const frequency = this.statisticsService.calculateFrequency(data);

        // 統計奇數與偶數的總頻率
        let oddSum = 0, evenSum = 0;
        for (let i = min; i <= max; i++) {
            if (i % 2 === 0) evenSum += (frequency[i] || 0);
            else oddSum += (frequency[i] || 0);
        }

        const targetParity = oddSum >= evenSum ? 'odd' : 'even';

        // 從目標奇偶類別中挑選頻率最高的號碼
        const candidates = [];
        for (let i = min; i <= max; i++) {
            if ((targetParity === 'odd' && i % 2 !== 0) || (targetParity === 'even' && i % 2 === 0)) {
                candidates.push({ number: i, freq: frequency[i] || 0 });
            }
        }

        candidates.sort((a, b) => b.freq - a.freq);
        const selected = candidates.slice(0, lotteryRules.pickCount).map(c => c.number).sort((a, b) => a - b);

        return {
            numbers: selected,
            method: '奇偶比例策略',
            report: `根據歷史資料奇偶比例 (${targetParity})，選取頻率最高的 ${lotteryRules.pickCount} 個號碼。`
        };
    }
}
