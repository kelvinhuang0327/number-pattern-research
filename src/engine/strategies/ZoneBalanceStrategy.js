import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 區間平衡策略 (ZoneBalanceStrategy)
 * 將號碼分為 5 個區間，計算每個區間的出現次數，
 * 選擇出現次數最高的區間，從該區間中挑選頻率最高的號碼作為預測結果。
 */
export class ZoneBalanceStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;
        const frequency = this.statisticsService.calculateFrequency(data);

        // 動態創建區間（分為5個區間）
        const totalNumbers = max - min + 1;
        const zoneSize = Math.ceil(totalNumbers / 5);
        const zones = {};
        const zoneRanges = [];

        for (let i = 0; i < 5; i++) {
            const zoneStart = min + (i * zoneSize);
            const zoneEnd = Math.min(zoneStart + zoneSize - 1, max);
            const zoneKey = `${zoneStart}-${zoneEnd}`;
            zones[zoneKey] = 0;
            zoneRanges.push({ key: zoneKey, start: zoneStart, end: zoneEnd });
        }

        // 計算每個區間的總頻率
        for (let i = min; i <= max; i++) {
            for (const zone of zoneRanges) {
                if (i >= zone.start && i <= zone.end) {
                    zones[zone.key] += (frequency[i] || 0);
                    break;
                }
            }
        }

        // 找出頻率最高的區間
        const targetZone = Object.entries(zones).sort((a, b) => b[1] - a[1])[0][0];
        const targetRange = zoneRanges.find(z => z.key === targetZone);

        // 從目標區間挑選頻率最高的號碼
        const candidates = [];
        for (let i = targetRange.start; i <= targetRange.end; i++) {
            candidates.push({ number: i, freq: frequency[i] || 0 });
        }

        candidates.sort((a, b) => b.freq - a.freq);
        const selected = candidates.slice(0, lotteryRules.pickCount).map(c => c.number).sort((a, b) => a - b);

        return {
            numbers: selected,
            method: '區間平衡策略',
            report: `根據區間頻率，選擇最高區間 ${targetZone}，從中挑選頻率最高的 ${lotteryRules.pickCount} 個號碼。`
        };
    }
}
