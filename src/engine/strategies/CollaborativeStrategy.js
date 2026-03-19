import { LOTTERY_RULES } from '../../utils/Constants.js';
import { FrequencyStrategy } from './FrequencyStrategy.js';
import { TrendStrategy } from './TrendStrategy.js';
import { BayesianStrategy } from './BayesianStrategy.js';
import { DeviationStrategy } from './DeviationStrategy.js';
import { MarkovStrategy } from './MarkovStrategy.js';
import { MonteCarloStrategy } from './MonteCarloStrategy.js';
import { UnifiedEnsembleStrategy } from './UnifiedEnsembleStrategy.js';
import { MLStrategy } from './MLStrategy.js';

/**
 * 協作預測策略
 * 結合多種預測方法，支援接力模式與合作模式
 */
export class CollaborativeStrategy {
    constructor(statisticsService, mode = 'hybrid') {
        this.statisticsService = statisticsService;
        this.mode = mode; // 'relay', 'cooperative', 'hybrid'

        // 專家組分類
        this.expertGroups = {
            statistical: {
                name: '統計專家組',
                strategies: [
                    { name: 'Frequency', strategy: new FrequencyStrategy(statisticsService), weight: 1.0 },
                    { name: 'Trend', strategy: new TrendStrategy(), weight: 1.2 },
                    { name: 'Combined', strategy: new UnifiedEnsembleStrategy(statisticsService, 'combined'), weight: 1.5 }
                ],
                role: 'exploration' // 探索層
            },
            probabilistic: {
                name: '機率專家組',
                strategies: [
                    { name: 'Bayesian', strategy: new BayesianStrategy(statisticsService), weight: 1.3 },
                    { name: 'Deviation', strategy: new DeviationStrategy(statisticsService), weight: 1.2 },
                    { name: 'MonteCarlo', strategy: new MonteCarloStrategy(statisticsService), weight: 1.4 }
                ],
                role: 'exploration'
            },
            sequential: {
                name: '序列專家組',
                strategies: [
                    { name: 'Markov', strategy: new MarkovStrategy(), weight: 1.3 },
                    { name: 'CoOccurrence', strategy: new UnifiedEnsembleStrategy(statisticsService, 'cooccurrence'), weight: 1.1 }
                ],
                role: 'refinement' // 精煉層
            },
            feature: {
                name: '特徵專家組',
                strategies: [
                    { name: 'FeatureWeighted', strategy: new UnifiedEnsembleStrategy(statisticsService, 'feature_weighted'), weight: 1.4 },
                    { name: 'RandomForest', strategy: new MLStrategy(statisticsService, 'random_forest'), weight: 1.5 }
                ],
                role: 'refinement'
            },
            optimizer: {
                name: '優化專家組',
                strategies: [
                    { name: 'GeneticAlgorithm', strategy: new MLStrategy(statisticsService, 'genetic'), weight: 1.6 }
                ],
                role: 'decision' // 決策層
            }
        };

        // 歷史表現追蹤（用於動態權重調整）
        this.performanceHistory = {};
    }

    async predict(data, lotteryRules = LOTTERY_RULES) {
        const { min, max } = lotteryRules.numberRange;

        switch (this.mode) {
            case 'relay':
                return await this.relayPredict(data, lotteryRules);
            case 'cooperative':
                return await this.cooperativePredict(data, lotteryRules);
            case 'hybrid':
            default:
                return await this.hybridPredict(data, lotteryRules);
        }
    }

    /**
     * 接力模式：三階段過濾
     * 探索層(49→25) → 精煉層(25→12) → 決策層(12→6)
     */
    async relayPredict(data, lotteryRules) {
        const { min, max } = lotteryRules.numberRange;
        const stages = [];

        // === 第一階段：探索層 ===
        const explorationGroups = ['statistical', 'probabilistic'];
        const explorationResults = await this.runExpertGroups(explorationGroups, data, lotteryRules);

        // 合併探索層結果，選出 TOP 25
        const explorationCandidates = this.mergeCandidates(explorationResults, max, 25);
        stages.push({
            name: '探索層',
            candidates: explorationCandidates.length,
            groups: explorationGroups
        });

        // === 第二階段：精煉層 ===
        const refinementGroups = ['sequential', 'feature'];
        const refinementResults = await this.runExpertGroups(refinementGroups, data, lotteryRules);

        // 在探索候選中精煉，選出 TOP 12
        const refinementCandidates = this.refineCandidates(
            explorationCandidates, refinementResults, 12
        );
        stages.push({
            name: '精煉層',
            candidates: refinementCandidates.length,
            groups: refinementGroups
        });

        // === 第三階段：決策層 ===
        const decisionGroups = ['optimizer'];
        const decisionResults = await this.runExpertGroups(decisionGroups, data, lotteryRules);

        // 最終決策，選出 TOP 6
        const finalNumbers = this.finalDecision(
            refinementCandidates, decisionResults, data, lotteryRules
        );
        stages.push({
            name: '決策層',
            candidates: lotteryRules.pickCount,
            groups: decisionGroups
        });

        // 計算機率
        const probabilities = this.calculateFinalProbabilities(
            finalNumbers, explorationResults, refinementResults, decisionResults, max
        );

        return {
            numbers: finalNumbers.sort((a, b) => a - b),
            probabilities: probabilities,
            confidence: this.calculateRelayConfidence(stages, finalNumbers),
            method: '協作預測 (接力模式)',
            report: this.generateRelayReport(stages)
        };
    }

    /**
     * 合作模式：所有專家平行投票
     */
    async cooperativePredict(data, lotteryRules) {
        const { min, max } = lotteryRules.numberRange;
        const allResults = [];
        const groupNames = Object.keys(this.expertGroups);

        // 平行執行所有專家組
        for (const groupName of groupNames) {
            const results = await this.runExpertGroups([groupName], data, lotteryRules);
            allResults.push(...results);
        }

        // 加權投票
        const votes = this.weightedVoting(allResults, max);

        // 衝突檢測與解決
        const consensus = this.detectConsensus(allResults, votes);

        // 選出 TOP 6
        const sortedNumbers = Object.entries(votes)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num]) => parseInt(num));

        const probabilities = {};
        const sumVotes = Object.values(votes).reduce((a, b) => a + b, 0);
        for (let i = min; i <= max; i++) {
            probabilities[i] = (votes[i] || 0) / sumVotes;
        }

        return {
            numbers: sortedNumbers.sort((a, b) => a - b),
            probabilities: probabilities,
            confidence: this.calculateCooperativeConfidence(consensus, allResults.length),
            method: '協作預測 (合作模式)',
            report: this.generateCooperativeReport(consensus, allResults.length)
        };
    }

    /**
     * 混合模式：接力過濾 + 合作決策
     */
    async hybridPredict(data, lotteryRules) {
        const { min, max } = lotteryRules.numberRange;
        // 第一步：探索層合作投票 → 25 候選
        const explorationGroups = ['statistical', 'probabilistic'];
        const explorationResults = await this.runExpertGroups(explorationGroups, data, lotteryRules);
        const explorationVotes = this.weightedVoting(explorationResults, max);
        const candidates25 = Object.entries(explorationVotes)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 25)
            .map(([num]) => parseInt(num));

        // 第二步：精煉層接力過濾 → 15 候選
        const refinementGroups = ['sequential', 'feature'];
        const refinementResults = await this.runExpertGroups(refinementGroups, data, lotteryRules);
        const candidates15 = this.refineCandidates(candidates25, refinementResults, 15);

        // 第三步：決策層合作 + 優化 → 最終 6 號
        const decisionGroups = ['optimizer'];
        const decisionResults = await this.runExpertGroups(decisionGroups, data, lotteryRules);

        // 綜合所有結果做最終決策
        const allResults = [...explorationResults, ...refinementResults, ...decisionResults];
        const finalVotes = this.weightedVoting(allResults, max);

        // 只在候選 15 中選擇
        const candidateVotes = {};
        candidates15.forEach(num => {
            candidateVotes[num] = finalVotes[num] || 0;
        });

        const finalNumbers = Object.entries(candidateVotes)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num]) => parseInt(num));

        // 應用組合約束優化
        const optimizedNumbers = this.applyConstraints(finalNumbers, candidateVotes, data, lotteryRules);

        // 計算機率
        const probabilities = {};
        const sumVotes = Object.values(finalVotes).reduce((a, b) => a + b, 0);
        for (let i = min; i <= max; i++) {
            probabilities[i] = (finalVotes[i] || 0) / sumVotes;
        }

        return {
            numbers: optimizedNumbers.sort((a, b) => a - b),
            probabilities: probabilities,
            confidence: this.calculateHybridConfidence(candidates15, optimizedNumbers),
            method: '協作預測 (混合模式)',
            report: this.generateHybridReport(candidates25.length, candidates15.length, allResults.length)
        };
    }

    /**
     * 執行專家組預測
     */
    async runExpertGroups(groupNames, data, lotteryRules = LOTTERY_RULES) {
        const results = [];

        for (const groupName of groupNames) {
            const group = this.expertGroups[groupName];
            if (!group) continue;

            for (const expert of group.strategies) {
                try {
                    const result = await Promise.resolve(expert.strategy.predict(data, lotteryRules));
                    results.push({
                        name: expert.name,
                        group: groupName,
                        weight: expert.weight,
                        numbers: result.numbers,
                        probabilities: result.probabilities,
                        confidence: result.confidence
                    });
                } catch (error) {
                    console.error(`Expert ${expert.name} failed:`, error);
                }
            }
        }

        return results;
    }

    /**
     * 合併候選號碼
     */
    mergeCandidates(results, max, topN) {
        const scores = {};
        for (let i = 1; i <= max; i++) scores[i] = 0;

        results.forEach(result => {
            // 按機率加權
            for (let i = 1; i <= max; i++) {
                const prob = result.probabilities[i] || 0;
                scores[i] += prob * result.weight;
            }

            // TOP 6 額外加分
            result.numbers.forEach((num, idx) => {
                scores[num] += (6 - idx) * result.weight * 0.5;
            });
        });

        return Object.entries(scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, topN)
            .map(([num]) => parseInt(num));
    }

    /**
     * 精煉候選
     */
    refineCandidates(candidates, refinementResults, topN) {
        const scores = {};
        candidates.forEach(num => { scores[num] = 0; });

        refinementResults.forEach(result => {
            candidates.forEach(num => {
                const prob = result.probabilities[num] || 0;
                scores[num] += prob * result.weight;

                // 如果在該模型的 TOP 6 中，額外加分
                const rank = result.numbers.indexOf(num);
                if (rank !== -1) {
                    scores[num] += (6 - rank) * result.weight * 0.3;
                }
            });
        });

        return Object.entries(scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, topN)
            .map(([num]) => parseInt(num));
    }

    /**
     * 最終決策
     */
    finalDecision(candidates, decisionResults, data, lotteryRules = LOTTERY_RULES) {
        const scores = {};
        candidates.forEach(num => { scores[num] = 0; });

        decisionResults.forEach(result => {
            result.numbers.forEach((num, idx) => {
                if (scores[num] !== undefined) {
                    scores[num] += (6 - idx) * result.weight;
                }
            });
        });

        // 如果優化器結果完全在候選中，直接使用
        if (decisionResults.length > 0) {
            const optimizerNumbers = decisionResults[0].numbers;
            const allInCandidates = optimizerNumbers.every(num =>
                candidates.includes(num)
            );
            if (allInCandidates) {
                return optimizerNumbers;
            }
        }

        return Object.entries(scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num]) => parseInt(num));
    }

    /**
     * 加權投票
     */
    weightedVoting(results, max) {
        const votes = {};
        for (let i = 1; i <= max; i++) votes[i] = 0;

        results.forEach(result => {
            // 機率投票
            for (let i = 1; i <= max; i++) {
                const prob = result.probabilities[i] || 0;
                votes[i] += prob * result.weight * result.confidence / 100;
            }

            // TOP 6 排名投票
            result.numbers.forEach((num, idx) => {
                votes[num] += (10 - idx) * result.weight;
            });
        });

        return votes;
    }

    /**
     * 共識檢測
     */
    detectConsensus(results, votes, lotteryRules = LOTTERY_RULES) {
        const topNumbers = Object.entries(votes)
            .sort((a, b) => b[1] - a[1])
            .slice(0, lotteryRules.pickCount)
            .map(([num]) => parseInt(num));

        // 計算每個號碼被多少模型推薦
        const recommendCount = {};
        topNumbers.forEach(num => { recommendCount[num] = 0; });

        results.forEach(result => {
            topNumbers.forEach(num => {
                if (result.numbers.includes(num)) {
                    recommendCount[num]++;
                }
            });
        });

        // 共識度 = 平均推薦數 / 總模型數
        const avgRecommend = Object.values(recommendCount).reduce((a, b) => a + b, 0) /
            topNumbers.length;
        const consensusLevel = avgRecommend / results.length;

        return {
            level: consensusLevel,
            highConsensus: topNumbers.filter(num =>
                recommendCount[num] >= results.length * 0.5),
            lowConsensus: topNumbers.filter(num =>
                recommendCount[num] < results.length * 0.3)
        };
    }

    /**
     * 應用組合約束
     */
    applyConstraints(numbers, candidateVotes, data, lotteryRules = LOTTERY_RULES) {
        let optimized = [...numbers];

        // 約束 1: 奇偶平衡 (理想 3:3)
        const oddCount = optimized.filter(n => n % 2 === 1).length;
        if (oddCount < 2 || oddCount > 4) {
            optimized = this.balanceOddEven(optimized, candidateVotes, oddCount);
        }

        // 約束 2: 區間分佈 (至少覆蓋 3 個區間)
        const zones = new Set(optimized.map(n => Math.floor((n - 1) / 10)));
        if (zones.size < 3) {
            optimized = this.balanceZones(optimized, candidateVotes, zones);
        }

        // 約束 3: 總和範圍 (120-180)
        const sum = optimized.reduce((a, b) => a + b, 0);
        if (sum < 120 || sum > 180) {
            optimized = this.balanceSum(optimized, candidateVotes, sum);
        }

        return optimized;
    }

    balanceOddEven(numbers, candidateVotes, currentOddCount) {
        const targetOdd = 3;
        const needMore = currentOddCount < targetOdd;

        // 找到可替換的號碼
        const sorted = Object.entries(candidateVotes)
            .sort((a, b) => b[1] - a[1])
            .map(([num]) => parseInt(num));

        const replacementPool = sorted.filter(num => {
            const isOdd = num % 2 === 1;
            return needMore ? isOdd : !isOdd;
        }).filter(num => !numbers.includes(num));

        if (replacementPool.length === 0) return numbers;

        // 替換評分最低的不符合條件號碼
        const result = [...numbers];
        const toReplace = numbers
            .filter(num => needMore ? (num % 2 === 0) : (num % 2 === 1))
            .sort((a, b) => (candidateVotes[a] || 0) - (candidateVotes[b] || 0));

        if (toReplace.length > 0 && replacementPool.length > 0) {
            const idx = result.indexOf(toReplace[0]);
            result[idx] = replacementPool[0];
        }

        return result;
    }

    balanceZones(numbers, candidateVotes, currentZones) {
        const sorted = Object.entries(candidateVotes)
            .sort((a, b) => b[1] - a[1])
            .map(([num]) => parseInt(num));

        // 找到缺少的區間
        const missingZones = [];
        for (let z = 0; z < 5; z++) {
            if (!currentZones.has(z)) missingZones.push(z);
        }

        if (missingZones.length === 0) return numbers;

        const result = [...numbers];

        // 從缺少區間中選擇高分號碼
        for (const zone of missingZones) {
            const zoneNumbers = sorted.filter(num => {
                const numZone = Math.floor((num - 1) / 10);
                return numZone === zone && !result.includes(num);
            });

            if (zoneNumbers.length > 0) {
                // 替換評分最低的號碼
                const lowestInResult = result
                    .sort((a, b) => (candidateVotes[a] || 0) - (candidateVotes[b] || 0))[0];
                const idx = result.indexOf(lowestInResult);
                result[idx] = zoneNumbers[0];
                break; // 只替換一個
            }
        }

        return result;
    }

    balanceSum(numbers, candidateVotes, currentSum) {
        const targetSum = 150;
        const needHigher = currentSum < targetSum;

        const sorted = Object.entries(candidateVotes)
            .sort((a, b) => b[1] - a[1])
            .map(([num]) => parseInt(num))
            .filter(num => !numbers.includes(num));

        const result = [...numbers];

        // 找到可以改善總和的替換
        for (const replacement of sorted) {
            for (let i = 0; i < result.length; i++) {
                const original = result[i];
                const diff = replacement - original;

                if ((needHigher && diff > 0) || (!needHigher && diff < 0)) {
                    const newSum = currentSum + diff;
                    if (newSum >= 120 && newSum <= 180) {
                        result[i] = replacement;
                        return result;
                    }
                }
            }
        }

        return result;
    }

    /**
     * 計算最終機率
     */
    calculateFinalProbabilities(finalNumbers, explorationResults, refinementResults, decisionResults, max) {
        const allResults = [...explorationResults, ...refinementResults, ...decisionResults];
        const votes = this.weightedVoting(allResults, max);

        const sum = Object.values(votes).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= max; i++) {
            probabilities[i] = (votes[i] || 0) / sum;
        }

        return probabilities;
    }

    calculateRelayConfidence(stages, finalNumbers, lotteryRules = LOTTERY_RULES) {
        // 基於過濾效率和最終結果計算信心度
        const totalNumbers = lotteryRules.numberRange.max - lotteryRules.numberRange.min + 1;
        const filterEfficiency = (totalNumbers - lotteryRules.pickCount) /
            (stages[0].candidates - lotteryRules.pickCount);
        return Math.min(Math.max(Math.round(filterEfficiency * 60 + 35), 70), 95);
    }

    calculateCooperativeConfidence(consensus, numModels) {
        // 基於共識度計算信心度
        const baseConfidence = consensus.level * 100;
        const modelBonus = Math.min(numModels * 2, 20);
        return Math.min(Math.max(Math.round(baseConfidence * 0.6 + modelBonus + 50), 65), 92);
    }

    calculateHybridConfidence(candidates15, finalNumbers) {
        // 混合模式信心度
        const coverage = finalNumbers.filter(n => candidates15.includes(n)).length;
        return Math.min(Math.max(Math.round(coverage / 6 * 30 + 65), 70), 93);
    }

    generateRelayReport(stages) {
        return `【接力模式】三階段協作過濾\n` +
            stages.map(s => `${s.name}: ${s.candidates} 個候選`).join(' → ') +
            `\n專家組: ${stages.flatMap(s => s.groups).join(', ')}`;
    }

    generateCooperativeReport(consensus, numModels) {
        const level = consensus.level > 0.6 ? '高' : consensus.level > 0.3 ? '中' : '低';
        return `【合作模式】${numModels} 個專家模型投票\n` +
            `共識度: ${level} (${(consensus.level * 100).toFixed(1)}%)\n` +
            `高共識號碼: [${consensus.highConsensus.join(', ')}]`;
    }

    generateHybridReport(candidates25, candidates15, numModels) {
        return `【混合模式】接力過濾 + 合作決策\n` +
            `過濾流程: 49 → ${candidates25} → ${candidates15} → 6\n` +
            `參與模型: ${numModels} 個`;
    }
}
