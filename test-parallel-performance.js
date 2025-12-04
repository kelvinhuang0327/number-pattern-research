/**
 * 測試並行測試的性能提升
 * 比較序列測試 vs 並行測試的執行時間
 */

console.log('🚀 並行測試性能演示\n');
console.log('═'.repeat(70));

// 模擬一個需要時間的異步操作
function simulateStrategyTest(strategyName, delay) {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve({
                strategy: strategyName,
                successRate: Math.random() * 0.5 + 0.3, // 30-80%
                avgHits: Math.random() * 3 + 2, // 2-5
                totalTests: 10
            });
        }, delay);
    });
}

// 測試數據
const strategies = [
    { name: 'frequency', delay: 300 },
    { name: 'trend', delay: 400 },
    { name: 'bayesian', delay: 350 },
    { name: 'montecarlo', delay: 500 },
    { name: 'markov', delay: 450 },
    { name: 'deviation', delay: 300 },
    { name: 'ensemble_weighted', delay: 400 },
    { name: 'ensemble_boosting', delay: 350 },
    { name: 'collaborative_hybrid', delay: 500 },
    { name: 'hot_cold', delay: 300 },
    { name: 'sum_range', delay: 350 },
    { name: 'statistical', delay: 400 }
];

// 序列測試（修復前的方式）
async function sequentialTest() {
    console.log('\n📝 序列測試（修復前）');
    console.log('─'.repeat(70));

    const startTime = Date.now();
    const results = [];

    for (const strategy of strategies) {
        console.log(`   測試策略: ${strategy.name}...`);
        const result = await simulateStrategyTest(strategy.name, strategy.delay);
        results.push(result);
    }

    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`\n   ✅ 完成 ${results.length} 個策略測試`);
    console.log(`   ⏱️  總耗時: ${elapsedTime} 秒`);

    return { results, elapsedTime: parseFloat(elapsedTime) };
}

// 並行測試（修復後的方式）
async function parallelTest() {
    console.log('\n🚀 並行測試（修復後）');
    console.log('─'.repeat(70));

    const startTime = Date.now();

    console.log(`   同時測試 ${strategies.length} 個策略...`);

    const testResults = await Promise.allSettled(
        strategies.map(strategy =>
            simulateStrategyTest(strategy.name, strategy.delay)
        )
    );

    const results = testResults
        .filter(r => r.status === 'fulfilled')
        .map(r => r.value);

    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`\n   ✅ 完成 ${results.length} 個策略測試`);
    console.log(`   ⏱️  總耗時: ${elapsedTime} 秒`);

    return { results, elapsedTime: parseFloat(elapsedTime) };
}

// 運行對比測試
async function runComparison() {
    console.log('\n🧪 開始性能對比測試...\n');

    // 運行序列測試
    const sequentialResult = await sequentialTest();

    // 稍作停頓
    await new Promise(resolve => setTimeout(resolve, 500));

    // 運行並行測試
    const parallelResult = await parallelTest();

    // 計算性能提升
    const speedup = (sequentialResult.elapsedTime / parallelResult.elapsedTime).toFixed(2);
    const timeSaved = (sequentialResult.elapsedTime - parallelResult.elapsedTime).toFixed(2);
    const percentSaved = ((timeSaved / sequentialResult.elapsedTime) * 100).toFixed(1);

    // 顯示對比結果
    console.log('\n' + '═'.repeat(70));
    console.log('\n📊 性能對比結果\n');
    console.log('─'.repeat(70));

    console.log('\n測試配置:');
    console.log(`  策略數量: ${strategies.length} 個`);
    console.log(`  每個策略模擬耗時: 300-500ms\n`);

    console.log('執行時間對比:');
    console.log(`  序列測試: ${sequentialResult.elapsedTime.toFixed(2)} 秒`);
    console.log(`  並行測試: ${parallelResult.elapsedTime.toFixed(2)} 秒`);
    console.log(`  節省時間: ${timeSaved} 秒 (${percentSaved}%)\n`);

    console.log('性能提升:');
    console.log(`  🚀 速度提升: ${speedup}x`);

    if (speedup >= 5) {
        console.log(`  ⭐⭐⭐ 卓越！速度提升超過 5 倍`);
    } else if (speedup >= 3) {
        console.log(`  ⭐⭐ 優秀！速度提升達到 3-5 倍`);
    } else if (speedup >= 2) {
        console.log(`  ⭐ 良好！速度提升達到 2-3 倍`);
    }

    console.log('\n實際應用效益:');
    console.log(`  ✅ 用戶等待時間減少 ${percentSaved}%`);
    console.log(`  ✅ 系統響應速度提升 ${speedup}x`);
    console.log(`  ✅ 可同時評估更多策略`);
    console.log(`  ✅ 提升用戶體驗和滿意度`);

    console.log('\n' + '═'.repeat(70));

    // 視覺化對比
    console.log('\n📈 視覺化對比:\n');
    const maxLength = 60;
    const seqBar = '█'.repeat(Math.floor((sequentialResult.elapsedTime / sequentialResult.elapsedTime) * maxLength));
    const parBar = '█'.repeat(Math.floor((parallelResult.elapsedTime / sequentialResult.elapsedTime) * maxLength));

    console.log(`  序列測試: ${seqBar} ${sequentialResult.elapsedTime.toFixed(2)}s`);
    console.log(`  並行測試: ${parBar} ${parallelResult.elapsedTime.toFixed(2)}s`);

    console.log('\n' + '═'.repeat(70) + '\n');
}

// 執行測試
runComparison().catch(console.error);
