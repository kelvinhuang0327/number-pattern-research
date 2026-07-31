/**
 * 系統功能測試腳本
 * 測試所有策略是否能正確載入和執行
 */

// 模擬瀏覽器環境
global.document = {
    getElementById: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {}
};
global.window = global;

async function testStrategyImports() {
    console.log('=== 測試策略文件導入 ===\n');

    const strategies = [
        'FrequencyStrategy',
        'TrendStrategy',
        'MarkovStrategy',
        'MonteCarloStrategy',
        'BayesianStrategy',
        'DeviationStrategy',
        'UnifiedEnsembleStrategy',
        'MLStrategy',
        'CollaborativeStrategy',
        'OddEvenBalanceStrategy',
        'ZoneBalanceStrategy',
        'HotColdMixStrategy',
        'SumRangeStrategy',
        'WheelingStrategy',
        'NumberPairsStrategy',
        'StatisticalAnalysisStrategy'
    ];

    let passed = 0;
    let failed = 0;

    for (const strategyName of strategies) {
        try {
            await import(`../src/engine/strategies/${strategyName}.js`);
            console.log(`✓ ${strategyName} 載入成功`);
            passed++;
        } catch (error) {
            console.error(`✗ ${strategyName} 載入失敗:`, error.message);
            failed++;
        }
    }

    console.log(`\n總計: ${passed} 成功, ${failed} 失敗\n`);
    return failed === 0;
}

async function testPredictionEngine() {
    console.log('=== 測試 PredictionEngine 初始化 ===\n');

    try {
        // 先導入依賴
        const { StatisticsService } = await import('../src/data/StatisticsService.js');
        const { DataProcessor } = await import('../src/core/DataProcessor.js');
        const { PredictionEngine } = await import('../src/engine/PredictionEngine.js');

        // 創建實例
        const dataProcessor = new DataProcessor();
        const statisticsService = new StatisticsService(dataProcessor);
        const predictionEngine = new PredictionEngine(dataProcessor, statisticsService);

        console.log('✓ PredictionEngine 初始化成功');

        // 檢查所有策略是否已註冊
        const expectedStrategies = [
            'frequency', 'trend', 'bayesian', 'montecarlo', 'markov', 'deviation',
            'ensemble_weighted', 'ensemble_boosting', 'ensemble_combined',
            'ensemble_cooccurrence', 'ensemble_features',
            'ml_features', 'ml_forest', 'ml_genetic',
            'collaborative_relay', 'collaborative_coop', 'collaborative_hybrid',
            'odd_even', 'zone_balance', 'hot_cold', 'sum_range',
            'wheeling', 'number_pairs', 'statistical'
        ];

        let missing = [];
        for (const key of expectedStrategies) {
            if (!predictionEngine.strategies[key]) {
                missing.push(key);
            }
        }

        if (missing.length > 0) {
            console.error('✗ 缺少策略:', missing.join(', '));
            return false;
        }

        console.log(`✓ 所有 ${expectedStrategies.length} 個策略已註冊\n`);

        // 測試基本預測功能
        console.log('=== 測試基本預測功能 ===\n');

        // 載入示範數據
        dataProcessor.loadSampleData();
        console.log(`✓ 已載入 ${dataProcessor.getData().length} 筆示範數據`);

        // 測試每個策略
        let strategyPassed = 0;
        let strategyFailed = 0;

        for (const [key, strategy] of Object.entries(predictionEngine.strategies)) {
            try {
                const result = await predictionEngine.predict(key, 50);

                if (!result || !result.numbers || result.numbers.length === 0) {
                    throw new Error('預測結果無效');
                }

                console.log(`✓ ${key}: ${result.numbers.join(', ')}`);
                strategyPassed++;
            } catch (error) {
                console.error(`✗ ${key} 預測失敗:`, error.message);
                strategyFailed++;
            }
        }

        console.log(`\n策略測試: ${strategyPassed} 成功, ${strategyFailed} 失敗\n`);

        return strategyFailed === 0;

    } catch (error) {
        console.error('✗ PredictionEngine 測試失敗:', error);
        return false;
    }
}

async function runTests() {
    console.log('========================================');
    console.log('        彩券預測系統功能測試');
    console.log('========================================\n');

    const results = [];

    // 測試1: 策略文件導入
    results.push(await testStrategyImports());

    // 測試2: PredictionEngine
    results.push(await testPredictionEngine());

    // 總結
    console.log('========================================');
    console.log('              測試總結');
    console.log('========================================');

    const allPassed = results.every(r => r === true);

    if (allPassed) {
        console.log('\n✓ 所有測試通過！系統運行正常。\n');
        process.exit(0);
    } else {
        console.log('\n✗ 部分測試失敗，請檢查錯誤訊息。\n');
        process.exit(1);
    }
}

// 執行測試
runTests().catch(error => {
    console.error('測試執行失敗:', error);
    process.exit(1);
});
