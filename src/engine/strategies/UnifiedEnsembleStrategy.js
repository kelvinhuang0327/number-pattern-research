import { LOTTERY_RULES } from '../../utils/Constants.js';
import { FrequencyStrategy } from './FrequencyStrategy.js';
import { TrendStrategy } from './TrendStrategy.js';
import { MarkovStrategy } from './MarkovStrategy.js';
import { MonteCarloStrategy } from './MonteCarloStrategy.js';
import { DeviationStrategy } from './DeviationStrategy.js';

/**
 * 統一集成策略
 * 整合多種集成方法：加權投票、提升、組合、共現分析、特徵加權
 */
export class UnifiedEnsembleStrategy {
    constructor(statisticsService, mode = 'weighted') {
        this.statisticsService = statisticsService;
        this.mode = mode; // weighted, boosting, combined, cooccurrence, feature_weighted

        // 基礎模型
        this.baseModels = [
            { name: 'Frequency', strategy: new FrequencyStrategy(statisticsService), weight: 1.2 },
            { name: 'Trend', strategy: new TrendStrategy(), weight: 1.2 },
            { name: 'Markov', strategy: new MarkovStrategy(), weight: 1.3 },
            { name: 'MonteCarlo', strategy: new MonteCarloStrategy(statisticsService), weight: 1.2 },
            { name: 'Deviation', strategy: new DeviationStrategy(statisticsService), weight: 1.3 }
        ];
    }

    /**
     * 獲取當前權重 (用於自動優化)
     */
    get weights() {
        const weights = {};
        this.baseModels.forEach(model => {
            weights[model.name] = model.weight;
        });
        return weights;
    }

    /**
     * 設置權重 (用於自動優化)
     */
    set weights(newWeights) {
        this.baseModels.forEach(model => {
            if (newWeights[model.name] !== undefined) {
                model.weight = newWeights[model.name];
            }
        });
    }

    async predict(data) {
        const range = LOTTERY_RULES.numberRange.max;

        switch (this.mode) {
            case 'boosting':
                return this.predictBoosting(data);
            case 'combined':
                return this.predictCombined(data);
            case 'cooccurrence':
                return this.predictCoOccurrence(data);
            case 'feature_weighted':
                return this.predictFeatureWeighted(data);
            case 'weighted':
            default:
                return this.predictWeighted(data);
        }
    }

    /**
     * 加權投票模式
     */
    async predictWeighted(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const totalProbabilities = {};
        for (let i = 1; i <= range; i++) totalProbabilities[i] = 0;

        // 執行每個基礎模型
        const modelResults = [];
        for (const model of this.baseModels) {
            const result = await Promise.resolve(model.strategy.predict(data));
            modelResults.push({ ...model, result });
        }

        // 加權投票
        modelResults.forEach(m => {
            for (let i = 1; i <= range; i++) {
                if (m.result.probabilities[i]) {
                    totalProbabilities[i] += m.result.probabilities[i] * m.weight;
                }
            }
        });

        // 正規化
        const sumTotal = Object.values(totalProbabilities).reduce((a, b) => a + b, 0) || 1;
        for (let i = 1; i <= range; i++) totalProbabilities[i] /= sumTotal;

        const sortedNumbers = Object.entries(totalProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: totalProbabilities,
            confidence: 88,
            method: '加權集成策略',
            report: `綜合 ${this.baseModels.length} 種基礎模型的加權投票分析。`
        };
    }

    /**
     * 提升模式 (Boosting)
     */
    predictBoosting(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 初始化機率（均勻分佈）
        for (let i = 1; i <= range; i++) {
            probabilities[i] = 1 / range;
        }

        // 獲取基礎預測
        const freqResult = this.baseModels[0].strategy.predict(data);
        const trendResult = this.baseModels[1].strategy.predict(data);
        const markovResult = this.baseModels[2].strategy.predict(data);
        const missing = this.statisticsService.calculateMissingValues(data);
        const maxMissing = Math.max(...Object.values(missing)) || 1;

        // 學習率
        const learningRate = 0.3;

        // 迭代更新
        for (let round = 0; round < 3; round++) {
            for (let i = 1; i <= range; i++) {
                const target = freqResult.probabilities[i];

                const contributions = [
                    trendResult.probabilities[i] * 0.3,
                    (missing[i] / maxMissing) * 0.2,
                    markovResult.probabilities[i] * 0.3,
                    target * 0.2
                ];

                const avgContribution = contributions.reduce((a, b) => a + b, 0);
                probabilities[i] += learningRate * (avgContribution - probabilities[i]);
            }
        }

        // 正規化
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
            confidence: 86,
            method: '梯度提升集成',
            report: `結合頻率、趨勢與馬可夫鏈的迭代優化預測。`
        };
    }

    /**
     * 組合模式 (Combined)
     */
    predictCombined(data) {
        const frequency = {};
        const weighted = {};
        const missing = this.statisticsService.calculateMissingValues(data);
        const range = LOTTERY_RULES.numberRange;
        const n = data.length;

        // 初始化
        for (let i = range.min; i <= range.max; i++) {
            frequency[i] = 0;
            weighted[i] = 0;
        }

        const lambda = 0.05;
        data.forEach((draw, index) => {
            const age = index;
            const expWeight = Math.exp(-lambda * age);
            draw.numbers.forEach(num => {
                frequency[num]++;
                weighted[num] += expWeight;
            });
        });

        // 動態權重
        const isSmallSample = n < 50;
        const isLargeSample = n > 300;

        const weights = {
            frequency: isLargeSample ? 0.40 : isSmallSample ? 0.25 : 0.35,
            trend: isSmallSample ? 0.40 : isLargeSample ? 0.25 : 0.30,
            missing: 0.20,
            tail: 0.15
        };

        const probabilities = {};
        const maxMissing = Math.max(...Object.values(missing)) || 1;
        const totalWeighted = Object.values(weighted).reduce((a, b) => a + b, 0) || 1;

        for (let i = range.min; i <= range.max; i++) {
            const freqScore = (frequency[i] / n) * weights.frequency;
            const trendScore = (weighted[i] / totalWeighted) * weights.trend;
            const missingScore = (missing[i] / maxMissing) * weights.missing;

            probabilities[i] = freqScore + trendScore + missingScore;
        }

        // 正規化
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = range.min; i <= range.max; i++) {
            probabilities[i] = probabilities[i] / sumProb;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 85,
            method: '綜合回歸模型',
            report: `綜合頻率、趨勢與遺漏值的多維度分析。`
        };
    }

    /**
     * 共現分析模式
     */
    predictCoOccurrence(data) {
        const range = LOTTERY_RULES.numberRange.max;

        // 使用最近一期的號碼作為領頭羊
        const lastDraw = data[0];
        const leaders = lastDraw.numbers;

        // 建立共現矩陣
        const coOccurrence = {};
        for (let i = 1; i <= range; i++) coOccurrence[i] = 0;

        // 掃描歷史資料
        data.forEach(draw => {
            const nums = draw.numbers;
            const leadersInDraw = nums.filter(n => leaders.includes(n));

            if (leadersInDraw.length > 0) {
                nums.forEach(n => {
                    if (!leaders.includes(n)) {
                        coOccurrence[n] += leadersInDraw.length;
                    }
                });
            }
        });

        // 轉換為機率
        const totalScore = Object.values(coOccurrence).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = totalScore > 0 ? coOccurrence[i] / totalScore : 0;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 72,
            method: '共現分析模型',
            report: `基於最近一期號碼 (${leaders.join(', ')}) 的共現性分析。`
        };
    }

    /**
     * 特徵加權模式
     */
    predictFeatureWeighted(data) {
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
        const zoneCounts = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
        data.forEach(draw => draw.numbers.forEach(n => {
            const zoneIndex = Math.floor((n - 1) / 10);
            zoneCounts[zoneIndex]++;
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
            const zoneScore = (avgPerZone / (zoneCount + 1)) * 0.15 / avgPerZone;

            let oddEvenScore = 0;
            if (i % 2 === 1 && oddRatio < 0.5) oddEvenScore = 0.1;
            else if (i % 2 === 0 && oddRatio > 0.5) oddEvenScore = 0.1;

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
