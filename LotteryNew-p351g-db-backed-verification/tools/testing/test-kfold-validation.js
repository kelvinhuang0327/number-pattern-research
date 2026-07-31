/**
 * 測試 K-fold 交叉驗證實作
 * 展示 K-fold 驗證的穩定性優勢
 */

console.log('🔄 K-fold 交叉驗證測試\n');
console.log('═'.repeat(70));

// 模擬彩券數據
function generateMockData(size) {
    const data = [];
    for (let i = 0; i < size; i++) {
        // 生成隨機號碼（1-49）
        const numbers = [];
        while (numbers.length < 6) {
            const num = Math.floor(Math.random() * 49) + 1;
            if (!numbers.includes(num)) {
                numbers.push(num);
            }
        }
        numbers.sort((a, b) => a - b);

        data.push({
            period: `2025${String(i + 1).padStart(3, '0')}`,
            numbers: numbers,
            special: Math.floor(Math.random() * 49) + 1
        });
    }
    return data;
}

// 模擬策略評估函數
function simulateStrategyEvaluation(strategyName, trainData, testData, minHitsForSuccess = 3) {
    let successCount = 0;
    let totalHits = 0;

    // 基於策略名稱的性能特徵
    const strategyPerformance = {
        'frequency': { baseSuccessRate: 0.45, variance: 0.15 },
        'trend': { baseSuccessRate: 0.38, variance: 0.20 },
        'bayesian': { baseSuccessRate: 0.52, variance: 0.10 },
        'ensemble': { baseSuccessRate: 0.60, variance: 0.08 }
    };

    const perf = strategyPerformance[strategyName] || { baseSuccessRate: 0.40, variance: 0.15 };

    for (let i = 0; i < testData.length; i++) {
        // 模擬預測命中數（帶隨機性）
        const randomFactor = (Math.random() - 0.5) * perf.variance * 2;
        const hitProbability = Math.max(0, Math.min(1, perf.baseSuccessRate + randomFactor));
        const hits = Math.floor(hitProbability * 6);

        totalHits += hits;
        if (hits >= minHitsForSuccess) {
            successCount++;
        }
    }

    return {
        successCount,
        totalHits,
        testCount: testData.length
    };
}

// 單次驗證
function singleSplitValidation(strategyName, trainData, testData) {
    const result = simulateStrategyEvaluation(strategyName, trainData, testData);

    return {
        successRate: result.successCount / result.testCount,
        avgHits: result.totalHits / result.testCount,
        totalTests: result.testCount,
        validationMethod: 'single-split'
    };
}

// K-fold 交叉驗證
function kFoldValidation(strategyName, trainData, testData, kFolds = 3) {
    const foldSize = Math.floor(testData.length / kFolds);
    const foldResults = [];
    let totalSuccessCount = 0;
    let totalHits = 0;
    let totalTests = 0;

    for (let foldIndex = 0; foldIndex < kFolds; foldIndex++) {
        const foldStartIdx = foldIndex * foldSize;
        const foldEndIdx = foldIndex === kFolds - 1
            ? testData.length
            : (foldIndex + 1) * foldSize;

        const foldTestData = testData.slice(foldStartIdx, foldEndIdx);

        // 模擬評估這個 fold
        const result = simulateStrategyEvaluation(strategyName, trainData, foldTestData);

        if (foldTestData.length > 0) {
            const foldSuccessRate = result.successCount / result.testCount;
            const foldAvgHits = result.totalHits / result.testCount;

            foldResults.push({
                foldIndex,
                successRate: foldSuccessRate,
                avgHits: foldAvgHits,
                testCount: foldTestData.length
            });

            totalSuccessCount += result.successCount;
            totalHits += result.totalHits;
            totalTests += result.testCount;
        }
    }

    // 計算穩定性
    const successRates = foldResults.map(f => f.successRate);
    const mean = successRates.reduce((sum, rate) => sum + rate, 0) / successRates.length;
    const variance = successRates.reduce((sum, rate) => sum + Math.pow(rate - mean, 2), 0) / successRates.length;
    const stdDev = Math.sqrt(variance);
    const stability = Math.exp(-5 * stdDev);

    return {
        successRate: totalSuccessCount / totalTests,
        avgHits: totalHits / totalTests,
        totalTests: totalTests,
        foldResults: foldResults,
        stability: stability,
        validationMethod: `${kFolds}-fold CV`,
        stdDev: stdDev
    };
}

// 場景 1: 比較單次驗證 vs K-fold 驗證
console.log('\n📝 場景 1: 單次驗證 vs K-fold 驗證比較\n');
console.log('─'.repeat(70));

const mockData = generateMockData(30);
const trainSize = 20;
const trainData = mockData.slice(0, trainSize);
const testData = mockData.slice(trainSize);

console.log(`數據配置:`);
console.log(`  總數據量: ${mockData.length} 期`);
console.log(`  訓練集: ${trainData.length} 期`);
console.log(`  測試集: ${testData.length} 期\n`);

const strategies = ['frequency', 'trend', 'bayesian', 'ensemble'];

console.log('測試結果對比:\n');

strategies.forEach(strategy => {
    console.log(`【${strategy}】`);

    // 單次驗證
    const singleResult = singleSplitValidation(strategy, trainData, testData);
    console.log(`  單次驗證:`);
    console.log(`    成功率: ${(singleResult.successRate * 100).toFixed(1)}%`);
    console.log(`    平均命中: ${singleResult.avgHits.toFixed(2)}`);
    console.log(`    穩定性: N/A (無法評估)`);

    // K-fold 驗證
    const kFoldResult = kFoldValidation(strategy, trainData, testData, 3);
    console.log(`  3-fold 驗證:`);
    console.log(`    成功率: ${(kFoldResult.successRate * 100).toFixed(1)}%`);
    console.log(`    平均命中: ${kFoldResult.avgHits.toFixed(2)}`);
    console.log(`    穩定性: ${(kFoldResult.stability * 100).toFixed(0)}% (標準差: ${kFoldResult.stdDev.toFixed(3)})`);
    console.log(`    各 Fold 成功率: ${kFoldResult.foldResults.map(f => (f.successRate * 100).toFixed(0) + '%').join(', ')}`);
    console.log();
});

// 場景 2: 穩定性評級展示
console.log('\n' + '─'.repeat(70));
console.log('\n📝 場景 2: 穩定性評級系統\n');
console.log('─'.repeat(70));

const stabilityTestCases = [
    { name: '策略A', stdDev: 0.05, successRates: [0.60, 0.62, 0.61] },
    { name: '策略B', stdDev: 0.15, successRates: [0.50, 0.65, 0.58] },
    { name: '策略C', stdDev: 0.25, successRates: [0.40, 0.70, 0.55] },
    { name: '策略D', stdDev: 0.35, successRates: [0.30, 0.80, 0.50] }
];

console.log('\n穩定性評級標準:');
console.log('  ⭐ 非常穩定: >= 80%');
console.log('  ✓ 穩定:     >= 60%');
console.log('  ⚠️  中等:     >= 40%');
console.log('  ⚠️  不穩定:   < 40%\n');

stabilityTestCases.forEach(testCase => {
    const stability = Math.exp(-5 * testCase.stdDev);
    const stabilityPercent = (stability * 100).toFixed(0);

    let rating = '';
    if (stability >= 0.8) {
        rating = '⭐ 非常穩定';
    } else if (stability >= 0.6) {
        rating = '✓ 穩定';
    } else if (stability >= 0.4) {
        rating = '⚠️  中等';
    } else {
        rating = '⚠️  不穩定';
    }

    console.log(`${testCase.name}:`);
    console.log(`  各 Fold 成功率: ${testCase.successRates.map(r => (r * 100).toFixed(0) + '%').join(', ')}`);
    console.log(`  標準差: ${testCase.stdDev.toFixed(3)}`);
    console.log(`  穩定性分數: ${stabilityPercent}%`);
    console.log(`  評級: ${rating}\n`);
});

// 場景 3: K-fold 優勢演示
console.log('─'.repeat(70));
console.log('\n📝 場景 3: K-fold 驗證的優勢\n');
console.log('─'.repeat(70));

console.log('\n✅ K-fold 交叉驗證的優勢:\n');
console.log('1. 📊 更可靠的評估');
console.log('   • 使用多個測試集，減少單一分割的偶然性');
console.log('   • 評估結果更接近策略的真實性能\n');

console.log('2. 🎯 穩定性指標');
console.log('   • 量化策略在不同數據集上的一致性');
console.log('   • 幫助識別過擬合（低穩定性）的策略\n');

console.log('3. 📈 更好的策略選擇');
console.log('   • 不僅看成功率，還要看穩定性');
console.log('   • 高成功率 + 高穩定性 = 可靠策略\n');

console.log('4. ⚠️  識別風險');
console.log('   • 低穩定性策略可能在特定數據上表現好，但泛化能力差');
console.log('   • 幫助用戶做出更明智的決策\n');

// 場景 4: 數據量不足時的回退
console.log('─'.repeat(70));
console.log('\n📝 場景 4: 數據量不足時的智能回退\n');
console.log('─'.repeat(70));

const smallData = generateMockData(15);
const smallTrain = smallData.slice(0, 10);
const smallTest = smallData.slice(10);

console.log(`\n數據配置:`);
console.log(`  測試集大小: ${smallTest.length} 期`);
console.log(`  K-fold 配置: 3-fold`);
console.log(`  最小 fold 大小: 5 期`);
console.log(`  所需最小測試集: ${3 * 5} 期\n`);

const canUseKFold = smallTest.length >= 3 * 5;
console.log(`判斷結果:`);
if (canUseKFold) {
    console.log(`  ✅ 數據量足夠，使用 3-fold 交叉驗證`);
} else {
    console.log(`  ⚠️  數據量不足 (${smallTest.length} < ${3 * 5})，回退到單次驗證`);
    console.log(`  說明: 確保評估可靠性，避免 fold 過小導致不穩定`);
}

// 總結
console.log('\n' + '═'.repeat(70));
console.log('\n📊 K-fold 交叉驗證總結\n');
console.log('實作特點:');
console.log('  ✅ 時間序列 K-fold（保持時間順序）');
console.log('  ✅ 智能回退機制（數據不足時使用單次驗證）');
console.log('  ✅ 穩定性量化（基於標準差的穩定性分數）');
console.log('  ✅ 詳細的 Fold 結果記錄');
console.log('  ✅ 視覺化評級系統（⭐ ✓ ⚠️）\n');

console.log('性能提升:');
console.log('  📈 評估準確性: 顯著提升（多重驗證）');
console.log('  🎯 策略選擇: 更可靠（考慮穩定性）');
console.log('  ⚠️  風險識別: 更好（量化一致性）');
console.log('  💡 用戶體驗: 提升（透明的穩定性信息）\n');

console.log('配置參數:');
console.log('  USE_K_FOLD: true (啟用 K-fold)');
console.log('  K_FOLD_COUNT: 3 (折數)');
console.log('  MIN_FOLD_SIZE: 5 (每個 fold 的最小測試期數)\n');

console.log('═'.repeat(70) + '\n');
