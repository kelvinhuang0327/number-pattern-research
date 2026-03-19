import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 冷熱號混合策略 (HotColdMixStrategy)
 * 先取得熱號 (頻率最高前 10) 與冷號 (頻率最低前 10)，
 * 從熱號中挑選前半數 (pickCount/2) 與冷號中挑選後半數，
 * 組合成最終預測號碼。
 */
export class HotColdMixStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const hot = this.statisticsService.getHotNumbers(10).map(item => item.number);
        const cold = this.statisticsService.getColdNumbers(10).map(item => item.number);
        const half = Math.ceil(lotteryRules.pickCount / 2);
        const selectedHot = hot.slice(0, half);
        const selectedCold = cold.slice(0, lotteryRules.pickCount - half);
        const selected = [...selectedHot, ...selectedCold].sort((a, b) => a - b);
        return {
            numbers: selected,
            method: '冷熱號混合策略',
            report: `結合前 ${half} 個熱號與 ${lotteryRules.pickCount - half} 個冷號，形成混合預測。`
        };
    }
}
