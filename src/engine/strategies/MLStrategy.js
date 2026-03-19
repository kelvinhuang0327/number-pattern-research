import { LOTTERY_RULES } from '../../utils/Constants.js';

/**
 * 統一機器學習策略
 * 整合多種ML算法：特徵加權、隨機森林、遺傳算法
 */
export class MLStrategy {
    constructor(statisticsService, algorithm = 'feature_weighted') {
        this.statisticsService = statisticsService;
        this.algorithm = algorithm; // feature_weighted, random_forest, genetic

        // 預設權重 (可通過自動優化調整)
        this._weights = {
            frequency: 0.3,
            recent: 0.4,
            missing: 0.2,
            zone: 0.1,
            random: 0.1
        };
    }

    /**
     * 獲取當前權重 (用於自動優化)
     */
    get weights() {
        return { ...this._weights };
    }

    /**
     * 設置權重 (用於自動優化)
     */
    set weights(newWeights) {
        this._weights = { ...this._weights, ...newWeights };
    }

    async predict(data) {
        switch (this.algorithm) {
            case 'random_forest':
                return this.predictRandomForest(data);
            case 'genetic':
                return this.predictGenetic(data);
            case 'feature_weighted':
            default:
                return this.predictFeatureWeighted(data);
        }
    }

    /**
     * 特徵加權模式
     */
    predictFeatureWeighted(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const scores = {};

        // 初始化分數
        for (let i = 1; i <= range; i++) scores[i] = 0;

        // 特徵 1: 頻率
        const frequency = this.statisticsService.calculateFrequency(data);
        const maxFreq = Math.max(...Object.values(frequency)) || 1;
        for (let i = 1; i <= range; i++) {
            scores[i] += (frequency[i] / maxFreq) * this._weights.frequency;
        }

        // 特徵 2: 近期趨勢
        const recentData = data.slice(0, 10);
        const recentFreq = this.statisticsService.calculateFrequency(recentData);
        const maxRecent = Math.max(...Object.values(recentFreq)) || 1;
        for (let i = 1; i <= range; i++) {
            scores[i] += (recentFreq[i] / maxRecent) * this._weights.recent;
        }

        // 特徵 3: 遺漏值
        const missing = this.statisticsService.calculateMissingValues(data);
        for (let i = 1; i <= range; i++) {
            const m = missing[i];
            let score = 0;
            if (m >= 5 && m <= 15) score = 1;
            else if (m > 15) score = 0.5;
            else score = 0.2;
            scores[i] += score * this._weights.missing;
        }

        // 特徵 4: 隨機擾動
        for (let i = 1; i <= range; i++) {
            scores[i] += Math.random() * this._weights.random;
        }

        // 轉換為機率
        const totalScore = Object.values(scores).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = scores[i] / totalScore;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 80,
            method: '機器學習 (特徵加權)',
            report: `基於頻率、近期趨勢與遺漏值的多特徵評分模型。`
        };
    }

    /**
     * 隨機森林模式 (簡化版)
     */
    /**
     * 隨機森林模式 (模擬版 - 啟發式集成)
     * 建立多棵決策樹（啟發式規則），每棵樹使用隨機特徵子集和權重
     */
    predictRandomForest(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const numTrees = 50; // 增加樹的數量

        // 1. 預計算所有基礎特徵
        const frequency = this.statisticsService.calculateFrequency(data);
        const missing = this.statisticsService.calculateMissingValues(data);
        const totalDraws = data.length;

        // 近期趨勢 (最近10期)
        const recentData = data.slice(0, 10);
        const recentFreq = this.statisticsService.calculateFrequency(recentData);

        // 區間分佈
        const zoneCounts = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
        data.forEach(draw => draw.numbers.forEach(n => {
            zoneCounts[Math.floor((n - 1) / 10)]++;
        }));
        const avgPerZone = (data.length * LOTTERY_RULES.pickCount) / 5;

        // 奇偶趨勢
        let oddCount = 0;
        data.forEach(draw => draw.numbers.forEach(n => { if (n % 2 !== 0) oddCount++; }));
        const oddRatio = oddCount / (data.length * LOTTERY_RULES.pickCount);

        // 2. 建立多棵決策樹 (每棵樹是不同權重的評分器)
        const treePredictions = [];

        for (let t = 0; t < numTrees; t++) {
            const treeProb = {};

            // 隨機特徵選擇 (Feature Bagging)
            // 為每棵樹隨機分配特徵權重，以 this._weights 為基礎進行擾動
            const weights = {
                freq: Math.random() > 0.2 ? Math.random() * this._weights.frequency * 2 : 0,
                missing: Math.random() > 0.2 ? Math.random() * this._weights.missing * 2 : 0,
                recent: Math.random() > 0.2 ? Math.random() * this._weights.recent * 2 : 0,
                zone: Math.random() > 0.5 ? Math.random() * this._weights.zone * 3 : 0,
                random: Math.random() * this._weights.random
            };

            // 如果所有主要權重都是0，強制給頻率權重
            if (weights.freq + weights.missing + weights.recent === 0) {
                weights.freq = this._weights.frequency || 0.5;
            }

            for (let num = 1; num <= range; num++) {
                let score = 0;

                // 頻率得分
                if (weights.freq > 0) {
                    score += (frequency[num] / totalDraws) * weights.freq;
                }

                // 遺漏值得分 (遺漏越久分數越高，但過久可能太冷)
                if (weights.missing > 0) {
                    const m = missing[num];
                    let mScore = 0;
                    if (m >= 5 && m <= 15) mScore = 1.0;      // 回補區
                    else if (m > 15) mScore = 0.4;            // 冷號
                    else mScore = 0.2;                        // 熱號
                    score += mScore * weights.missing;
                }

                // 近期熱度得分
                if (weights.recent > 0) {
                    score += (recentFreq[num] / 10) * weights.recent;
                }

                // 區間平衡得分
                if (weights.zone > 0) {
                    const zIdx = Math.floor((num - 1) / 10);
                    const zCount = zoneCounts[zIdx];
                    // 如果該區間出現次數少，給予加分 (平衡原則)
                    if (zCount < avgPerZone) score += 0.5 * weights.zone;
                }

                // 隨機擾動
                score += Math.random() * weights.random;

                treeProb[num] = score;
            }

            treePredictions.push(treeProb);
        }

        // 3. 集成投票 (Bagging)
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            // 平均所有樹的評分
            const avgScore = treePredictions.reduce((sum, tree) => sum + tree[i], 0) / numTrees;
            probabilities[i] = avgScore;
        }

        // 4. 正規化
        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0) || 1;
        for (let i = 1; i <= range; i++) {
            probabilities[i] /= totalProb;
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
            method: '隨機森林 (啟發式集成)',
            report: `使用 ${numTrees} 棵決策樹的集成預測，每棵樹採用隨機特徵權重（頻率、遺漏、近期、區間）進行投票。`
        };
    }

    /**
     * 遺傳算法模式 (簡化版)
     */
    predictGenetic(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const pickCount = LOTTERY_RULES.pickCount;

        const frequency = this.statisticsService.calculateFrequency(data);
        const missing = this.statisticsService.calculateMissingValues(data);

        // 初始化族群
        const populationSize = 50;
        const generations = 30;
        let population = [];

        for (let i = 0; i < populationSize; i++) {
            population.push(this.randomSelection(range, pickCount, frequency));
        }

        // 進化循環
        for (let gen = 0; gen < generations; gen++) {
            const fitness = population.map(ind => this.calculateFitness(ind, frequency, missing, data));

            // 選擇
            const newPopulation = [];
            for (let i = 0; i < populationSize; i++) {
                const parent1 = this.tournamentSelection(population, fitness);
                const parent2 = this.tournamentSelection(population, fitness);

                // 交叉
                let child = Math.random() > 0.2 ? this.crossover(parent1, parent2) : parent1.slice();

                // 變異
                if (Math.random() < 0.1) {
                    child = this.mutate(child, range);
                }

                newPopulation.push(child);
            }

            population = newPopulation;
        }

        // 選擇最佳個體
        const finalFitness = population.map(ind => this.calculateFitness(ind, frequency, missing, data));
        const bestIndex = finalFitness.indexOf(Math.max(...finalFitness));
        const bestIndividual = population[bestIndex];

        // 🔧 修復：檢查 bestIndividual 是否有效
        if (!bestIndividual || !Array.isArray(bestIndividual) || bestIndividual.length === 0) {
            console.error('❌ GeneticAlgorithm: bestIndividual is invalid', {
                bestIndex,
                populationLength: population.length,
                fitnessLength: finalFitness.length
            });
            // 降級到隨機選擇
            return {
                numbers: this.randomSelection(range, pickCount, frequency),
                probabilities: {},
                confidence: 40,
                method: '遺傳算法優化（降級）',
                report: '遺傳算法未能找到最佳個體，使用隨機選擇。'
            };
        }

        // 計算機率分佈
        const probabilities = {};
        for (let i = 1; i <= range; i++) probabilities[i] = 0;

        population.forEach((individual, idx) => {
            const weight = finalFitness[idx];
            if (individual && Array.isArray(individual)) {  // 🔧 添加檢查
                individual.forEach(num => {
                    probabilities[num] += weight;
                });
            }
        });

        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        if (totalProb > 0) {  // 🔧 避免除以零
            for (let i = 1; i <= range; i++) {
                probabilities[i] /= totalProb;
            }
        }

        const predictedNumbers = [...bestIndividual].sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: 81,
            method: '遺傳算法優化',
            report: `經過 ${generations} 代進化，族群大小 ${populationSize}，選出最優號碼組合。`
        };
    }

    // 輔助函數
    randomSelection(range, pickCount, frequency) {
        const selected = new Set();
        const freqSum = Object.values(frequency).reduce((a, b) => a + b, 0);

        while (selected.size < pickCount) {
            let random = Math.random() * freqSum;
            for (let num = 1; num <= range; num++) {
                random -= frequency[num];
                if (random <= 0 && !selected.has(num)) {
                    selected.add(num);
                    break;
                }
            }

            // 防止無限循環
            if (selected.size < pickCount) {
                const remaining = Array.from({ length: range }, (_, i) => i + 1)
                    .filter(n => !selected.has(n));
                if (remaining.length > 0) {
                    selected.add(remaining[Math.floor(Math.random() * remaining.length)]);
                }
            }
        }

        return Array.from(selected);
    }

    calculateFitness(individual, frequency, missing, data) {
        let fitness = 0;

        // 頻率得分
        individual.forEach(num => {
            fitness += frequency[num] * 0.3;
        });

        // 遺漏值得分
        individual.forEach(num => {
            const m = missing[num];
            if (m >= 5 && m <= 15) fitness += 10;
        });

        // 奇偶平衡
        const oddCount = individual.filter(n => n % 2 === 1).length;
        if (oddCount === 3) fitness += 20;
        else if (oddCount === 2 || oddCount === 4) fitness += 10;

        // 區間分佈
        const zones = new Set(individual.map(n => Math.floor((n - 1) / 10)));
        fitness += zones.size * 5;

        // 總和範圍
        const sum = individual.reduce((a, b) => a + b, 0);
        if (sum >= 120 && sum <= 180) fitness += 15;

        return fitness;
    }

    tournamentSelection(population, fitness) {
        const idx1 = Math.floor(Math.random() * population.length);
        const idx2 = Math.floor(Math.random() * population.length);
        return fitness[idx1] > fitness[idx2] ? population[idx1].slice() : population[idx2].slice();
    }

    crossover(parent1, parent2) {
        const child = [];
        const used = new Set();

        // 從兩個父代隨機選擇
        const allGenes = [...parent1, ...parent2];
        while (child.length < LOTTERY_RULES.pickCount && allGenes.length > 0) {
            const gene = allGenes.splice(Math.floor(Math.random() * allGenes.length), 1)[0];
            if (!used.has(gene)) {
                child.push(gene);
                used.add(gene);
            }
        }

        return child;
    }

    mutate(individual, range) {
        const mutated = [...individual];
        const idx = Math.floor(Math.random() * mutated.length);
        let newGene;
        do {
            newGene = Math.floor(Math.random() * range) + 1;
        } while (mutated.includes(newGene));

        mutated[idx] = newGene;
        return mutated;
    }
}
