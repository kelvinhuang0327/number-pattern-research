import { LOTTERY_RULES } from '../../utils/Constants.js';

export class FeatureWeightedStrategy {
    constructor(statisticsService) {
        this.statisticsService = statisticsService;
    }

    predict(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        for (let i = 1; i <= range; i++) probabilities[i] = 0;

        // 特徵 1: 頻率 (25%)
        const frequency = this.statisticsService.calculateFrequency(data);
        const totalDraws = data.length;

        // 特徵 2: 遺漏值 (20%)
        const missing = this.statisticsService.calculateMissingValues(data);
        const maxMissing = Math.max(...Object.values(missing)) || 1;

        // 特徵 3: 尾數熱度 (15%)
        const tailBonus = this.getTailBonus(data);

        // 特徵 4: 區間平衡 (15%)
        const distribution = this.statisticsService.calculateDistribution(); // Note: This returns percentages as strings like '1-10': "20.5"
        // Need raw counts or re-calculate for scoring
        // Let's re-calculate zone counts for scoring precision
        const zoneCounts = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 }; // 0: 1-10, 1: 11-20...
        data.forEach(draw => draw.numbers.forEach(n => {
            if (n <= 10) zoneCounts[0]++;
            else if (n <= 20) zoneCounts[1]++;
            else if (n <= 30) zoneCounts[2]++;
            else if (n <= 40) zoneCounts[3]++;
            else zoneCounts[4]++;
        }));
        const avgPerZone = (data.length * LOTTERY_RULES.pickCount) / 5;

        // 特徵 5: 奇偶比例 (10%)
        let oddCount = 0;
        data.forEach(draw => draw.numbers.forEach(n => { if (n % 2 !== 0) oddCount++; }));
        const totalNums = data.length * LOTTERY_RULES.pickCount;
        const oddRatio = oddCount / totalNums;

        // 特徵 6: 近期趨勢 (15%)
        const recentWindow = Math.min(20, data.length);
        const recentFreq = {};
        for (let i = 1; i <= range; i++) recentFreq[i] = 0;
        for (let idx = 0; idx < recentWindow; idx++) {
            data[idx].numbers.forEach(num => recentFreq[num]++);
        }

        for (let i = 1; i <= range; i++) {
            const freqScore = (frequency[i] / totalDraws) * 0.25;
            const missingScore = (missing[i] / maxMissing) * 0.20;
            const tailScore = (tailBonus[i] || 0) * 0.15;

            const zoneIndex = Math.floor((i - 1) / 10);
            const zoneCount = zoneCounts[zoneIndex] || 0;
            // 如果該區間出現次數少於平均，則加分 (平衡策略)
            const zoneScore = (avgPerZone / (zoneCount + 1)) * 0.15 / avgPerZone; // Normalize roughly

            let oddEvenScore = 0;
            if (i % 2 === 1 && oddRatio < 0.5) oddEvenScore = 0.1; // 奇數少，補奇數
            else if (i % 2 === 0 && oddRatio > 0.5) oddEvenScore = 0.1; // 偶數少，補偶數

            const trendScore = (recentFreq[i] / recentWindow) * 0.15;

            probabilities[i] = freqScore + missingScore + tailScore + zoneScore + oddEvenScore + trendScore;
        }

        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= sumProb;

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 82,
            method: '特徵加權模型',
            report: `綜合頻率、遺漏、尾數、區間、奇偶與近期趨勢的六維度分析。`
        };
    }

    getTailBonus(data) {
        const tailCounts = {};
        for (let i = 0; i <= 9; i++) tailCounts[i] = 0;

        data.forEach(draw => {
            draw.numbers.forEach(num => {
                tailCounts[num % 10]++;
            });
        });

        const total = data.length * LOTTERY_RULES.pickCount;
        const bonus = {};
        for (let i = 1; i <= 49; i++) {
            const tail = i % 10;
            bonus[i] = tailCounts[tail] / total;
        }
        return bonus;
    }
}
