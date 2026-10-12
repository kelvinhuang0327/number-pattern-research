/**
 * 測試早期停止機制
 * 展示在發現優秀策略時的行為
 */

console.log('🎯 早期停止機制測試\n');
console.log('═'.repeat(70));

// 模擬配置
const EXCELLENT_THRESHOLD = 0.7;  // 70% 成功率視為優秀
const GOOD_THRESHOLD = 0.5;       // 50% 成功率視為良好

// 模擬策略測試結果
const mockResults = [
    { strategy: 'frequency', successRate: 0.45, avgHits: 2.8 },
    { strategy: 'trend', successRate: 0.38, avgHits: 2.5 },
    { strategy: 'bayesian', successRate: 0.52, avgHits: 3.1 },
    { strategy: 'montecarlo', successRate: 0.42, avgHits: 2.7 },
    { strategy: 'markov', successRate: 0.48, avgHits: 2.9 },
    { strategy: 'deviation', successRate: 0.35, avgHits: 2.3 },
    { strategy: 'ensemble_weighted', successRate: 0.58, avgHits: 3.4 },
    { strategy: 'ensemble_boosting', successRate: 0.62, avgHits: 3.5 },
    { strategy: 'collaborative_hybrid', successRate: 0.75, avgHits: 4.2 }, // 優秀策略！
    { strategy: 'hot_cold', successRate: 0.55, avgHits: 3.2 },
    { strategy: 'sum_range', successRate: 0.40, avgHits: 2.6 },
    { strategy: 'statistical', successRate: 0.72, avgHits: 4.0 } // 優秀策略！
];

// 場景 1: 沒有優秀策略
function scenario1() {
    console.log('\n📝 場景 1: 沒有優秀策略（所有策略 < 70%）');
    console.log('─'.repeat(70));

    const results = mockResults.map(r => ({ ...r, successRate: r.successRate * 0.8 })); // 降低所有成功率
    const excellentStrategies = results.filter(r => r.successRate >= EXCELLENT_THRESHOLD);

    console.log(`測試策略數: ${results.length} 個`);
    console.log(`優秀策略數: ${excellentStrategies.length} 個`);

    if (excellentStrategies.length === 0) {
        console.log('❌ 未觸發早期停止');
        console.log('   繼續完整評估所有策略');
    }

    // 找到最佳策略
    const sorted = [...results].sort((a, b) => b.successRate - a.successRate);
    const best = sorted[0];

    console.log(`\n最佳策略: ${best.strategy}`);
    console.log(`成功率: ${(best.successRate * 100).toFixed(1)}%`);

    if (best.successRate >= GOOD_THRESHOLD) {
        console.log(`質量評級: ✓ 良好`);
    } else {
        console.log(`質量評級: 一般`);
    }
}

// 場景 2: 發現 1 個優秀策略
function scenario2() {
    console.log('\n📝 場景 2: 發現 1 個優秀策略');
    console.log('─'.repeat(70));

    // 調整數據，確保只有1個優秀策略
    const results = mockResults.map(r => {
        if (r.strategy === 'collaborative_hybrid') {
            return r; // 保持優秀
        }
        return { ...r, successRate: Math.min(r.successRate, 0.65) };
    });

    const excellentStrategies = results.filter(r => r.successRate >= EXCELLENT_THRESHOLD);

    console.log(`測試策略數: ${results.length} 個`);
    console.log(`優秀策略數: ${excellentStrategies.length} 個`);

    if (excellentStrategies.length > 0) {
        console.log(`🎯 觸發早期停止！`);
        console.log(`   發現 ${excellentStrategies.length} 個優秀策略（成功率 >= 70%）`);
        console.log(`   優秀策略: ${excellentStrategies.map(s => s.strategy).join(', ')}`);
    }

    // 找到最佳策略
    const sorted = [...results].sort((a, b) => b.successRate - a.successRate);
    const best = sorted[0];

    console.log(`\n最佳策略: ${best.strategy}`);
    console.log(`成功率: ${(best.successRate * 100).toFixed(1)}%`);
    console.log(`質量評級: ⭐ 優秀`);
}

// 場景 3: 發現多個優秀策略
function scenario3() {
    console.log('\n📝 場景 3: 發現 2 個優秀策略');
    console.log('─'.repeat(70));

    const results = mockResults; // 使用原始數據（有2個優秀策略）
    const excellentStrategies = results.filter(r => r.successRate >= EXCELLENT_THRESHOLD);

    console.log(`測試策略數: ${results.length} 個`);
    console.log(`優秀策略數: ${excellentStrategies.length} 個`);

    if (excellentStrategies.length > 0) {
        console.log(`🎯 觸發早期停止！`);
        console.log(`   發現 ${excellentStrategies.length} 個優秀策略（成功率 >= 70%）`);
        console.log(`   優秀策略:`);
        excellentStrategies.forEach(s => {
            console.log(`      - ${s.strategy}: ${(s.successRate * 100).toFixed(1)}%`);
        });
    }

    // 找到最佳策略
    const sorted = [...results].sort((a, b) => b.successRate - a.successRate);
    const best = sorted[0];

    console.log(`\n最佳策略: ${best.strategy}`);
    console.log(`成功率: ${(best.successRate * 100).toFixed(1)}%`);
    console.log(`質量評級: ⭐ 優秀`);
}

// 場景 4: 策略質量分級展示
function scenario4() {
    console.log('\n📝 場景 4: 策略質量分級');
    console.log('─'.repeat(70));

    const testCases = [
        { successRate: 0.75, expected: '⭐ 優秀' },
        { successRate: 0.60, expected: '✓ 良好' },
        { successRate: 0.40, expected: '一般' },
        { successRate: 0.25, expected: '一般' }
    ];

    console.log('成功率門檻:');
    console.log(`  優秀: >= ${(EXCELLENT_THRESHOLD * 100).toFixed(0)}%`);
    console.log(`  良好: >= ${(GOOD_THRESHOLD * 100).toFixed(0)}%`);
    console.log(`  一般: < ${(GOOD_THRESHOLD * 100).toFixed(0)}%`);
    console.log();

    testCases.forEach(testCase => {
        let quality = '一般';
        if (testCase.successRate >= EXCELLENT_THRESHOLD) {
            quality = '⭐ 優秀';
        } else if (testCase.successRate >= GOOD_THRESHOLD) {
            quality = '✓ 良好';
        }

        const match = quality === testCase.expected ? '✅' : '❌';
        console.log(`  成功率 ${(testCase.successRate * 100).toFixed(0)}% → ${quality} ${match}`);
    });
}

// 運行所有場景
scenario1();
scenario2();
scenario3();
scenario4();

// 總結
console.log('\n' + '═'.repeat(70));
console.log('\n📊 早期停止機制總結\n');
console.log('優勢:');
console.log('  ✅ 快速識別優秀策略');
console.log('  ✅ 提供清晰的質量評級（優秀/良好/一般）');
console.log('  ✅ 自動標記優秀結果（⭐）和良好結果（✓）');
console.log('  ✅ 在報告中顯示優秀策略信息');
console.log('  ✅ 幫助用戶快速判斷結果可靠性');
console.log();

console.log('實際應用:');
console.log('  🎯 當發現成功率 >= 70% 的策略時，系統會特別標記');
console.log('  📊 用戶可以根據質量評級判斷預測可信度');
console.log('  ⚡ 優秀策略會在報告中被高亮顯示');
console.log();

console.log('═'.repeat(70) + '\n');
