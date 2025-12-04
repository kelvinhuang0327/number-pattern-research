/**
 * Auto Optimize Strategy - 自動優化策略
 * 自動測試多種策略並選擇歷史成功率最高的方法進行預測
 */
export class AutoOptimizeStrategy {
    constructor(predictionEngine, statisticsService) {
        this.predictionEngine = predictionEngine;
        this.statisticsService = statisticsService;

        // 要測試的策略列表
        this.candidateStrategies = [
            'frequency',
            'trend',
            'bayesian',
            'montecarlo',
            'markov',
            'deviation',
            'ensemble_weighted',
            'ensemble_boosting',
            'ensemble_features',
            'ml_forest',
            'collaborative_hybrid',
            'hot_cold',
            'sum_range',
            'statistical'
        ];

        // 🎯 早期停止機制：優秀策略閾值配置
        this.EXCELLENT_THRESHOLD = 0.7;  // 成功率 >= 70% 視為優秀
        this.GOOD_THRESHOLD = 0.5;       // 成功率 >= 50% 視為良好

        // 🔄 K-fold 交叉驗證配置
        this.USE_K_FOLD = true;          // 是否使用 K-fold 驗證
        this.K_FOLD_COUNT = 3;           // K-fold 折數（3-5 適合時間序列）
        this.MIN_FOLD_SIZE = 5;          // 每個 fold 的最小測試期數
    }

    /**
     * 執行預測 - 自動選擇最佳策略
     */
    async predict(data, lotteryRules) {
        // 🔧 記憶體保護：限制數據量
        const MAX_DATA_SIZE = 500; // 最多使用 500 期數據
        if (data.length > MAX_DATA_SIZE) {
            console.log(`⚠️ 記憶體保護：數據量 ${data.length} 期超過限制，截取最新 ${MAX_DATA_SIZE} 期`);
            data = data.slice(0, MAX_DATA_SIZE);
        }

        // 驗證數據
        if (!data || !Array.isArray(data)) {
            throw new Error('無效的數據格式');
        }

        if (data.length < 30) {
            throw new Error(`數據量不足（目前 ${data.length} 期，至少需要 30 期）進行自動優化`);
        }

        // 驗證彩券規則
        if (!lotteryRules || typeof lotteryRules.pickCount === 'undefined') {
            throw new Error('無效的彩券規則');
        }

        console.log('🤖 開始自動優化測試...');
        console.log(`📊 總數據量: ${data.length} 期`);

        // 1. 將數據分成訓練集和測試集
        const testSize = Math.min(10, Math.floor(data.length * 0.2)); // 20% 作為測試集，最多10期
        const trainData = data.slice(testSize); // 較舊的數據作為訓練
        const testData = data.slice(0, testSize); // 最新的數據作為測試

        // 判斷使用哪種驗證方法
        const willUseKFold = this.USE_K_FOLD && testData.length >= this.MIN_FOLD_SIZE * this.K_FOLD_COUNT;
        const validationMethod = willUseKFold
            ? `${this.K_FOLD_COUNT}-fold 交叉驗證`
            : '單次驗證';

        console.log(`📊 訓練集: ${trainData.length} 期, 測試集: ${testSize} 期`);
        console.log(`🔄 驗證方法: ${validationMethod}`);

        // 2. 🚀 並行測試每個策略的成功率（提升速度）
        console.log(`🚀 並行測試 ${this.candidateStrategies.length} 個策略...`);
        const startTime = Date.now();

        // 使用 Promise.allSettled 並行測試所有策略
        const testResults = await Promise.allSettled(
            this.candidateStrategies.map(strategyName =>
                this.evaluateStrategy(
                    strategyName,
                    [...trainData], // 複製一份，避免修改原數據
                    testData,
                    lotteryRules
                ).then(performance => ({
                    strategy: strategyName,
                    successRate: performance.successRate,
                    avgHits: performance.avgHits,
                    totalTests: performance.totalTests
                }))
            )
        );

        // 處理並行測試結果
        const results = [];
        let failedStrategies = [];

        for (let i = 0; i < testResults.length; i++) {
            const result = testResults[i];
            const strategyName = this.candidateStrategies[i];

            if (result.status === 'fulfilled') {
                results.push(result.value);
                // 顯示評估結果（包含 K-fold 和穩定性信息）
                const stabilityInfo = result.value.stability !== undefined
                    ? ` [穩定性: ${(result.value.stability * 100).toFixed(0)}%]`
                    : '';
                const validationInfo = result.value.validationMethod === `${this.K_FOLD_COUNT}-fold CV`
                    ? ` [${this.K_FOLD_COUNT}-fold CV]`
                    : '';
                console.log(`✓ ${strategyName}: 成功率 ${(result.value.successRate * 100).toFixed(1)}%, 平均命中 ${result.value.avgHits.toFixed(1)} 個${stabilityInfo}${validationInfo}`);
            } else {
                const errorMessage = result.reason?.message || '未知錯誤';
                console.warn(`⚠️ ${strategyName} 測試失敗:`, errorMessage);
                failedStrategies.push({ strategy: strategyName, error: errorMessage });
            }
        }

        const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`⏱️  並行測試完成，耗時 ${elapsedTime} 秒`);

        if (results.length === 0) {
            const errorDetails = failedStrategies.map(f => `${f.strategy}: ${f.error}`).join('\n');
            throw new Error(`所有策略測試均失敗\n\n失敗原因：\n${errorDetails}\n\n請檢查數據格式或聯繫技術支持`);
        }

        console.log(`✅ 成功測試 ${results.length}/${this.candidateStrategies.length} 個策略`);

        // 3. 🎯 早期停止檢測：查找優秀策略
        const excellentStrategies = results.filter(r => r.successRate >= this.EXCELLENT_THRESHOLD);
        let earlyStopTriggered = false;
        let earlyStopReason = '';

        if (excellentStrategies.length > 0) {
            earlyStopTriggered = true;
            earlyStopReason = `發現 ${excellentStrategies.length} 個優秀策略（成功率 >= ${(this.EXCELLENT_THRESHOLD * 100).toFixed(0)}%）`;
            console.log(`🎯 ${earlyStopReason}`);
        }

        // 4. 選擇最佳策略 (優先考慮成功率，其次考慮平均命中數)
        results.sort((a, b) => {
            if (Math.abs(a.successRate - b.successRate) > 0.01) {
                return b.successRate - a.successRate;
            }
            return b.avgHits - a.avgHits;
        });

        const bestResult = results[0];
        const bestStrategy = bestResult.strategy;

        // 評估策略質量
        let strategyQuality = '一般';
        if (bestResult.successRate >= this.EXCELLENT_THRESHOLD) {
            strategyQuality = '優秀';
            console.log(`🏆 最佳策略: ${bestStrategy} (成功率: ${(bestResult.successRate * 100).toFixed(1)}%) ⭐ ${strategyQuality}`);
        } else if (bestResult.successRate >= this.GOOD_THRESHOLD) {
            strategyQuality = '良好';
            console.log(`🏆 最佳策略: ${bestStrategy} (成功率: ${(bestResult.successRate * 100).toFixed(1)}%) ✓ ${strategyQuality}`);
        } else {
            console.log(`🏆 最佳策略: ${bestStrategy} (成功率: ${(bestResult.successRate * 100).toFixed(1)}%)`);
        }

        // 5. 使用最佳策略對所有數據進行預測
        const strategy = this.predictionEngine.strategies[bestStrategy];
        const finalPrediction = await strategy.predict(data, lotteryRules);

        // 6. 返回增強的預測結果
        return {
            numbers: finalPrediction.numbers,
            probabilities: finalPrediction.probabilities,
            confidence: this.calculateConfidence(bestResult),
            method: `AI 自動優化 (${this.getStrategyName(bestStrategy)})${strategyQuality === '優秀' ? ' ⭐' : strategyQuality === '良好' ? ' ✓' : ''}`,
            report: this.generateReport(bestResult, results, testSize, data.length, failedStrategies, earlyStopReason),
            optimization: {
                bestStrategy: bestStrategy,
                successRate: bestResult.successRate,
                testedStrategies: results.length,
                failedStrategies: failedStrategies.length,
                testPeriods: testSize,
                allResults: results,
                topStrategies: results.slice(0, 3).map(r => r.strategy), // 記錄 Top 3
                strategyQuality: strategyQuality, // 策略質量評級
                earlyStop: earlyStopTriggered, // 是否觸發早期停止
                earlyStopReason: earlyStopReason, // 早期停止原因
                excellentCount: excellentStrategies.length // 優秀策略數量
            }
        };
    }

    /**
     * 智能預測（用於模擬，帶緩存）- 記憶體優化版
     * @param {Array} data - 訓練數據
     * @param {Object} lotteryRules - 彩券規則
     * @param {Object} cache - 緩存對象（可選）
     * @returns {Object} 預測結果
     */
    async predictWithCache(data, lotteryRules, cache = null) {
        // 🔧 記憶體保護：限制數據量
        const MAX_DATA_SIZE = 300; // 模擬時使用更少的數據
        if (data.length > MAX_DATA_SIZE) {
            console.log(`⚠️ 記憶體保護（模擬）：數據量 ${data.length} 期超過限制，截取最新 ${MAX_DATA_SIZE} 期`);
            data = data.slice(0, MAX_DATA_SIZE);
        }

        // 🔧 修復：檢查是否需要完整評估（改進緩存失效邏輯）
        const needsFullEvaluation =
            !cache ||                                                    // 沒有緩存
            !cache.topStrategies ||                                     // 沒有策略列表
            cache.topStrategies.length === 0 ||                         // 策略列表為空
            cache.evaluationCount >= 10 ||                              // 已使用快速模式10次，需重新評估
            !cache.lastEvaluationSize ||                                // 沒有記錄上次評估的數據大小
            Math.abs(data.length - cache.lastEvaluationSize) > Math.max(5, Math.floor(cache.lastEvaluationSize * 0.1)); // 數據量變化 >10% 或 >5期

        if (needsFullEvaluation) {
            console.log('🔄 執行完整策略評估...');
            if (cache && cache.evaluationCount >= 10) {
                console.log('   原因: 快速模式已使用10次，需重新校準');
            } else if (cache && cache.lastEvaluationSize && data.length !== cache.lastEvaluationSize) {
                console.log(`   原因: 數據量變化 (${cache.lastEvaluationSize} → ${data.length} 期)`);
            } else {
                console.log('   原因: 首次評估或緩存失效');
            }

            // 限制完整評估時的測試集大小（記憶體優化）
            const testSize = Math.min(5, Math.floor(data.length * 0.1)); // 降到 10%，最多5期
            const trainData = data.slice(testSize);
            const testData = data.slice(0, testSize);

            console.log(`📊 訓練集: ${trainData.length} 期, 測試集: ${testSize} 期`);

            // 只測試最有可能的策略（記憶體優化）
            const priorityStrategies = [
                'collaborative_hybrid',
                'ensemble_weighted',
                'statistical',
                'ml_forest',
                'hot_cold',
                'frequency'
            ];

            // 🚀 並行測試優先策略
            console.log(`🚀 並行測試 ${priorityStrategies.length} 個優先策略...`);
            const startTime = Date.now();

            const testResults = await Promise.allSettled(
                priorityStrategies.map(strategyName =>
                    this.evaluateStrategyFast(
                        strategyName,
                        trainData,
                        testData,
                        lotteryRules
                    ).then(performance => ({
                        strategy: strategyName,
                        successRate: performance.successRate,
                        avgHits: performance.avgHits,
                        totalTests: performance.totalTests
                    }))
                )
            );

            // 處理並行測試結果
            const results = [];
            let failedStrategies = [];

            for (let i = 0; i < testResults.length; i++) {
                const result = testResults[i];
                const strategyName = priorityStrategies[i];

                if (result.status === 'fulfilled') {
                    results.push(result.value);
                    console.log(`✓ ${strategyName}: ${(result.value.successRate * 100).toFixed(1)}%`);
                } else {
                    const errorMessage = result.reason?.message || '未知錯誤';
                    console.warn(`⚠️ ${strategyName} 測試失敗:`, errorMessage);
                    failedStrategies.push({ strategy: strategyName, error: errorMessage });
                }
            }

            const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
            console.log(`⏱️  並行測試完成，耗時 ${elapsedTime} 秒`);

            if (results.length === 0) {
                throw new Error('所有優先策略測試均失敗');
            }

            // 🎯 早期停止檢測
            const excellentStrategies = results.filter(r => r.successRate >= this.EXCELLENT_THRESHOLD);
            if (excellentStrategies.length > 0) {
                console.log(`🎯 發現 ${excellentStrategies.length} 個優秀策略（成功率 >= ${(this.EXCELLENT_THRESHOLD * 100).toFixed(0)}%）`);
            }

            // 選擇最佳策略
            results.sort((a, b) => {
                if (Math.abs(a.successRate - b.successRate) > 0.01) {
                    return b.successRate - a.successRate;
                }
                return b.avgHits - a.avgHits;
            });

            const bestResult = results[0];
            const bestStrategy = bestResult.strategy;

            // 策略質量評估
            if (bestResult.successRate >= this.EXCELLENT_THRESHOLD) {
                console.log(`🏆 最佳策略: ${bestStrategy} (${(bestResult.successRate * 100).toFixed(1)}%) ⭐ 優秀`);
            } else if (bestResult.successRate >= this.GOOD_THRESHOLD) {
                console.log(`🏆 最佳策略: ${bestStrategy} (${(bestResult.successRate * 100).toFixed(1)}%) ✓ 良好`);
            } else {
                console.log(`🏆 最佳策略: ${bestStrategy} (${(bestResult.successRate * 100).toFixed(1)}%)`);
            }

            // 使用最佳策略預測
            const strategy = this.predictionEngine.strategies[bestStrategy];
            const finalPrediction = await strategy.predict(data, lotteryRules);

            return {
                numbers: finalPrediction.numbers,
                probabilities: finalPrediction.probabilities,
                confidence: this.calculateConfidence(bestResult),
                method: `AI 優化 (${this.getStrategyName(bestStrategy)})`,
                report: `使用 ${this.getStrategyName(bestStrategy)}\n成功率: ${(bestResult.successRate * 100).toFixed(1)}%`,
                optimization: {
                    bestStrategy: bestStrategy,
                    successRate: bestResult.successRate,
                    testedStrategies: results.length,
                    mode: 'full'
                },
                cache: {
                    topStrategies: results.slice(0, 2).map(r => r.strategy), // 只保留 Top 2
                    evaluationCount: 0,
                    lastEvaluationSize: data.length
                }
            };
        }

        // 使用緩存的 Top 策略（超快速模式）
        console.log(`⚡ 快速模式 (使用 ${cache.topStrategies.length} 個已驗證策略)`);
        console.log(`   緩存使用次數: ${cache.evaluationCount}/10`);

        // 極簡測試：只用最近 3 期
        const testSize = Math.min(3, Math.floor(data.length * 0.05));
        const trainData = data.slice(testSize);
        const testData = data.slice(0, testSize);

        // 🚀 並行測試緩存策略
        const startTime = Date.now();
        const testResults = await Promise.allSettled(
            cache.topStrategies.map(strategyName =>
                this.evaluateStrategyFast(
                    strategyName,
                    trainData,
                    testData,
                    lotteryRules
                ).then(performance => ({
                    strategy: strategyName,
                    successRate: performance.successRate,
                    avgHits: performance.avgHits
                }))
            )
        );

        // 處理結果
        const results = [];
        let failedCount = 0;

        for (let i = 0; i < testResults.length; i++) {
            const result = testResults[i];
            const strategyName = cache.topStrategies[i];

            if (result.status === 'fulfilled') {
                results.push(result.value);
            } else {
                console.warn(`⚠️ ${strategyName} 快速測試失敗:`, result.reason?.message || '未知錯誤');
                failedCount++;
            }
        }

        const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`   ⚡ 快速測試完成，耗時 ${elapsedTime} 秒`);

        if (results.length === 0) {
            console.warn(`⚠️ 所有緩存策略 (${cache.topStrategies.length}) 測試失敗，回退到完整評估`);
            // 回退到完整評估
            return await this.predictWithCache(data, lotteryRules, null);
        }

        if (failedCount > 0) {
            console.log(`   ⚠️ ${failedCount}/${cache.topStrategies.length} 個策略測試失敗`);
        }

        // 選擇最佳策略
        results.sort((a, b) => b.successRate - a.successRate || b.avgHits - a.avgHits);
        const bestResult = results[0];
        const bestStrategy = bestResult.strategy;

        // 使用最佳策略預測
        const strategy = this.predictionEngine.strategies[bestStrategy];
        const finalPrediction = await strategy.predict(data, lotteryRules);

        return {
            numbers: finalPrediction.numbers,
            probabilities: finalPrediction.probabilities,
            confidence: this.calculateConfidence(bestResult),
            method: `AI 優化 (${this.getStrategyName(bestStrategy)}) ⚡`,
            report: `快速: ${this.getStrategyName(bestStrategy)}`,
            optimization: {
                bestStrategy: bestStrategy,
                successRate: bestResult.successRate,
                mode: 'fast'
            },
            cache: {
                topStrategies: cache.topStrategies,
                evaluationCount: cache.evaluationCount + 1,
                lastEvaluationSize: cache.lastEvaluationSize
            }
        };
    }

    /**
     * 快速評估策略（記憶體優化版）
     */
    async evaluateStrategyFast(strategyName, trainData, testData, lotteryRules) {
        let successCount = 0;
        let totalHits = 0;
        const minHitsForSuccess = Math.ceil(lotteryRules.pickCount * 0.5);

        try {
            const strategy = this.predictionEngine.strategies[strategyName];
            if (!strategy) {
                throw new Error(`Strategy ${strategyName} not found`);
            }

            // 只測試最近幾期（記憶體優化）
            for (let i = 0; i < Math.min(testData.length, 3); i++) {
                try {
                    // 🔧 修復：使用所有在測試期之前的數據作為訓練集
                    const currentTrainData = i === 0
                        ? trainData
                        : [...trainData, ...testData.slice(0, i)];

                    const prediction = await strategy.predict(currentTrainData, lotteryRules);

                    if (!prediction.numbers || !Array.isArray(prediction.numbers)) {
                        continue;
                    }

                    const hits = this.countHits(prediction.numbers, testData[i].numbers);
                    totalHits += hits;

                    if (hits >= minHitsForSuccess) {
                        successCount++;
                    }
                } catch (innerError) {
                    // 忽略單期失敗
                }
            }

            const testCount = Math.min(testData.length, 3);
            return {
                successRate: testCount > 0 ? successCount / testCount : 0,
                avgHits: testCount > 0 ? totalHits / testCount : 0,
                totalTests: testCount
            };
        } catch (error) {
            throw new Error(`Strategy ${strategyName} evaluation failed: ${error.message}`);
        }
    }

    /**
     * 評估單個策略的表現 - 使用 K-fold 交叉驗證或單次驗證
     */
    async evaluateStrategy(strategyName, trainData, testData, lotteryRules) {
        // 如果啟用 K-fold 且數據量足夠，使用 K-fold 交叉驗證
        if (this.USE_K_FOLD && testData.length >= this.MIN_FOLD_SIZE * this.K_FOLD_COUNT) {
            return await this.evaluateStrategyKFold(strategyName, trainData, testData, lotteryRules);
        }

        // 否則使用傳統的單次驗證
        return await this.evaluateStrategySingle(strategyName, trainData, testData, lotteryRules);
    }

    /**
     * 🔄 K-fold 交叉驗證評估策略
     * 提高評估穩定性和可靠性
     */
    async evaluateStrategyKFold(strategyName, trainData, testData, lotteryRules) {
        const minHitsForSuccess = Math.ceil(lotteryRules.pickCount * 0.5);

        // 計算每個 fold 的大小
        const foldSize = Math.floor(testData.length / this.K_FOLD_COUNT);

        // 收集每個 fold 的評估結果
        const foldResults = [];
        let totalSuccessCount = 0;
        let totalHits = 0;
        let totalTests = 0;

        try {
            const strategy = this.predictionEngine.strategies[strategyName];
            if (!strategy) {
                throw new Error(`Strategy ${strategyName} not found in prediction engine.`);
            }

            // 對每個 fold 進行評估
            for (let foldIndex = 0; foldIndex < this.K_FOLD_COUNT; foldIndex++) {
                const foldStartIdx = foldIndex * foldSize;
                const foldEndIdx = foldIndex === this.K_FOLD_COUNT - 1
                    ? testData.length  // 最後一個 fold 包含剩餘所有數據
                    : (foldIndex + 1) * foldSize;

                const foldTestData = testData.slice(foldStartIdx, foldEndIdx);

                let foldSuccessCount = 0;
                let foldTotalHits = 0;

                // 在這個 fold 中進行滾動預測
                for (let i = 0; i < foldTestData.length; i++) {
                    try {
                        // 🔧 時間序列 K-fold：使用所有在測試期之前的數據作為訓練集
                        // 訓練集包括：
                        // 1. 原始訓練數據
                        // 2. 當前 fold 之前的所有測試數據
                        // 3. 當前 fold 中已經發生的歷史數據（0 到 i-1）
                        const currentTrainData = [
                            ...trainData,
                            ...testData.slice(0, foldStartIdx + i)
                        ];

                        const prediction = await strategy.predict(currentTrainData, lotteryRules);

                        if (!prediction.numbers || !Array.isArray(prediction.numbers)) {
                            continue;
                        }

                        const hits = this.countHits(prediction.numbers, foldTestData[i].numbers);
                        foldTotalHits += hits;

                        if (hits >= minHitsForSuccess) {
                            foldSuccessCount++;
                        }
                    } catch (innerError) {
                        // 忽略單期失敗，繼續下一期
                    }
                }

                // 記錄這個 fold 的結果
                if (foldTestData.length > 0) {
                    const foldSuccessRate = foldSuccessCount / foldTestData.length;
                    const foldAvgHits = foldTotalHits / foldTestData.length;

                    foldResults.push({
                        foldIndex,
                        successRate: foldSuccessRate,
                        avgHits: foldAvgHits,
                        testCount: foldTestData.length
                    });

                    totalSuccessCount += foldSuccessCount;
                    totalHits += foldTotalHits;
                    totalTests += foldTestData.length;
                }
            }

            if (totalTests === 0) {
                return {
                    successRate: 0,
                    avgHits: 0,
                    totalTests: 0,
                    foldResults: [],
                    stability: 0
                };
            }

            // 計算總體評估結果
            const avgSuccessRate = totalSuccessCount / totalTests;
            const avgHits = totalHits / totalTests;

            // 🎯 計算穩定性指標（成功率的標準差）
            const successRates = foldResults.map(f => f.successRate);
            const stability = this.calculateStability(successRates);

            return {
                successRate: avgSuccessRate,
                avgHits: avgHits,
                totalTests: totalTests,
                foldResults: foldResults,
                stability: stability,  // 穩定性：0-1，越接近1越穩定
                validationMethod: `${this.K_FOLD_COUNT}-fold CV`
            };
        } catch (error) {
            throw new Error(`Strategy ${strategyName} K-fold evaluation failed: ${error.message}`);
        }
    }

    /**
     * 單次評估策略（原方法）
     */
    async evaluateStrategySingle(strategyName, trainData, testData, lotteryRules) {
        let successCount = 0;
        let totalHits = 0;

        if (!lotteryRules || typeof lotteryRules.pickCount === 'undefined') {
            throw new Error('Invalid lotteryRules: pickCount is required for evaluation.');
        }
        const minHitsForSuccess = Math.ceil(lotteryRules.pickCount * 0.5); // 至少命中50%算成功

        try {
            for (let i = 0; i < testData.length; i++) {
                try {
                    // 使用訓練數據進行預測
                    const strategy = this.predictionEngine.strategies[strategyName];
                    if (!strategy) {
                        throw new Error(`Strategy ${strategyName} not found in prediction engine.`);
                    }

                    // 🔧 修復數據洩漏：使用所有在測試期之前的數據作為訓練集
                    // 包括：原始訓練數據 + 測試集中已經發生的歷史數據（0 到 i-1）
                    const currentTrainData = i === 0
                        ? trainData
                        : [...trainData, ...testData.slice(0, i)];

                    // 直接調用策略的 predict 方法
                    const prediction = await strategy.predict(currentTrainData, lotteryRules);

                    // 與實際開獎結果比對
                    const actualNumbers = testData[i].numbers;
                    const predictedNumbers = prediction.numbers;

                    if (!predictedNumbers || !Array.isArray(predictedNumbers)) {
                        console.warn(`⚠️ ${strategyName} returned invalid prediction (not an array or null) for period ${i}. Skipping this period.`);
                        continue;
                    }

                    const hits = this.countHits(predictedNumbers, actualNumbers);
                    totalHits += hits;

                    if (hits >= minHitsForSuccess) {
                        successCount++;
                    }

                    // ✅ 移除數據洩漏的滾動窗口更新
                    // trainData 保持不變，每次循環使用 currentTrainData
                } catch (innerError) {
                    console.warn(`⚠️ ${strategyName} failed on test period ${i}:`, innerError.message);
                    // 繼續測試其他期數
                }
            }

            if (testData.length === 0) {
                // This case should ideally be caught before calling evaluateStrategy,
                // but added for robustness.
                return {
                    successRate: 0,
                    avgHits: 0,
                    totalTests: 0
                };
            }

            return {
                successRate: successCount / testData.length,
                avgHits: totalHits / testData.length,
                totalTests: testData.length,
                validationMethod: 'single-split'
            };
        } catch (error) {
            throw new Error(`Strategy ${strategyName} evaluation failed: ${error.message}`);
        }
    }

    /**
     * 🎯 計算穩定性指標
     * 基於成功率的標準差，返回0-1之間的穩定性分數
     */
    calculateStability(successRates) {
        if (!successRates || successRates.length <= 1) {
            return 1; // 只有一個值或沒有值時，視為完全穩定
        }

        // 計算平均值
        const mean = successRates.reduce((sum, rate) => sum + rate, 0) / successRates.length;

        // 計算標準差
        const variance = successRates.reduce((sum, rate) => sum + Math.pow(rate - mean, 2), 0) / successRates.length;
        const stdDev = Math.sqrt(variance);

        // 將標準差轉換為穩定性分數（0-1）
        // 標準差越小，穩定性越高
        // 使用指數衰減函數：stability = e^(-k * stdDev)
        // k=5 使得 stdDev=0.2 時 stability≈0.37，stdDev=0.1 時 stability≈0.61
        const stability = Math.exp(-5 * stdDev);

        return stability;
    }

    /**
     * 計算命中數
     */
    countHits(predicted, actual) {
        return predicted.filter(num => actual.includes(num)).length;
    }

    /**
     * 計算信心度
     */
    calculateConfidence(bestResult) {
        // 基於成功率和測試次數計算信心度
        const baseConfidence = bestResult.successRate * 100;
        const sampleBonus = Math.min(bestResult.totalTests / 10 * 5, 10); // 最多加10分

        return Math.min(Math.round(baseConfidence + sampleBonus), 95);
    }

    /**
     * 生成報告
     */
    generateReport(bestResult, allResults, testSize, totalSize, failedStrategies = [], earlyStopReason = '') {
        const bestStrategy = this.getStrategyName(bestResult.strategy);

        let report = `🤖 **AI 自動優化分析報告**\n\n`;
        report += `**數據分析:**\n`;
        report += `• 總數據量: ${totalSize} 期\n`;
        report += `• 訓練集: ${totalSize - testSize} 期\n`;
        report += `• 測試集: ${testSize} 期\n\n`;

        report += `**策略測試結果:**\n`;
        report += `• 測試策略數: ${allResults.length + failedStrategies.length} 種\n`;
        report += `• 成功測試: ${allResults.length} 種\n`;
        if (failedStrategies.length > 0) {
            report += `• 失敗測試: ${failedStrategies.length} 種\n`;
        }

        // 🔄 驗證方法信息
        if (bestResult.validationMethod) {
            report += `• 驗證方法: ${bestResult.validationMethod}\n`;
        }

        // 🎯 早期停止信息
        if (earlyStopReason) {
            report += `• 🎯 ${earlyStopReason}\n`;
        }

        report += `• 最佳策略: ${bestStrategy}\n`;
        report += `• 歷史成功率: ${(bestResult.successRate * 100).toFixed(1)}%\n`;

        // 🎯 穩定性評級（僅 K-fold 驗證時顯示）
        if (bestResult.stability !== undefined) {
            const stabilityPercent = (bestResult.stability * 100).toFixed(0);
            let stabilityRating = '';
            if (bestResult.stability >= 0.8) {
                stabilityRating = '⭐ 非常穩定';
            } else if (bestResult.stability >= 0.6) {
                stabilityRating = '✓ 穩定';
            } else if (bestResult.stability >= 0.4) {
                stabilityRating = '⚠️ 中等';
            } else {
                stabilityRating = '⚠️ 不穩定';
            }
            report += `• 策略穩定性: ${stabilityPercent}% (${stabilityRating})\n`;
        }

        // 策略質量評級
        if (bestResult.successRate >= 0.7) {
            report += `• 策略質量: ⭐ 優秀\n`;
        } else if (bestResult.successRate >= 0.5) {
            report += `• 策略質量: ✓ 良好\n`;
        } else if (bestResult.successRate >= 0.3) {
            report += `• 策略質量: 一般\n`;
        }

        report += `• 平均命中: ${bestResult.avgHits.toFixed(1)} 個號碼\n\n`;

        report += `**Top 5 策略排名:**\n`;
        allResults.slice(0, 5).forEach((result, index) => {
            report += `${index + 1}. ${this.getStrategyName(result.strategy)} - `;
            report += `成功率 ${(result.successRate * 100).toFixed(1)}%, `;
            report += `平均命中 ${result.avgHits.toFixed(1)} 個`;
            // 顯示穩定性（如果有）
            if (result.stability !== undefined) {
                report += `, 穩定性 ${(result.stability * 100).toFixed(0)}%`;
            }
            report += `\n`;
        });

        report += `\n**建議:**\n`;
        if (bestResult.successRate >= 0.3) {
            report += `• ✓ 該策略在歷史數據上表現優異，建議採用\n`;
        } else if (bestResult.successRate >= 0.2) {
            report += `• ⚠️ 該策略表現中等，建議謹慎參考\n`;
        } else {
            report += `• ⚠️ 所有策略表現欠佳，建議增加數據量或調整參數\n`;
        }

        return report;
    }

    /**
     * 獲取策略的中文名稱
     */
    getStrategyName(strategy) {
        const names = {
            'frequency': '頻率分析',
            'trend': '趨勢分析',
            'bayesian': '貝葉斯機率',
            'montecarlo': '蒙地卡羅模擬',
            'markov': '馬可夫鏈',
            'deviation': '偏差追蹤',
            'ensemble_weighted': '加權集成',
            'ensemble_boosting': 'Boosting集成',
            'collaborative_hybrid': '混合協作',
            'hot_cold': '冷熱號混合',
            'sum_range': '和值+AC值',
            'statistical': '多維統計'
        };
        return names[strategy] || strategy;
    }
}
