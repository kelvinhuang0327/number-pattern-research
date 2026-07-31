/**
 * 測試 AutoOptimizeStrategy 緩存邏輯修復
 */

console.log('🧪 測試緩存邏輯修復\n');

// 模擬緩存失效檢查邏輯
function shouldDoFullEvaluation(data, cache) {
    const needsFullEvaluation =
        !cache ||                                                    // 沒有緩存
        !cache.topStrategies ||                                     // 沒有策略列表
        cache.topStrategies.length === 0 ||                         // 策略列表為空
        cache.evaluationCount >= 10 ||                              // 已使用快速模式10次，需重新評估
        !cache.lastEvaluationSize ||                                // 沒有記錄上次評估的數據大小
        Math.abs(data.length - cache.lastEvaluationSize) > Math.max(5, Math.floor(cache.lastEvaluationSize * 0.1)); // 數據量變化 >10% 或 >5期

    return needsFullEvaluation;
}

// 測試場景 1: 首次使用（無緩存）
console.log('📝 測試場景 1: 首次使用（無緩存）');
const scenario1 = shouldDoFullEvaluation({ length: 100 }, null);
console.log(`   結果: ${scenario1 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估`);
console.log(`   ${scenario1 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 2: 有效緩存（第1次使用）
console.log('📝 測試場景 2: 有效緩存（第1次使用）');
const cache2 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 0,
    lastEvaluationSize: 100
};
const scenario2 = shouldDoFullEvaluation({ length: 100 }, cache2);
console.log(`   結果: ${scenario2 ? '❌ 執行完整評估' : '✅ 使用快速模式'}`);
console.log(`   預期: ✅ 使用快速模式`);
console.log(`   ${!scenario2 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 3: 緩存使用9次（應該繼續使用快速模式）
console.log('📝 測試場景 3: 緩存使用9次（應繼續使用快速模式）');
const cache3 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 9,
    lastEvaluationSize: 100
};
const scenario3 = shouldDoFullEvaluation({ length: 100 }, cache3);
console.log(`   結果: ${scenario3 ? '❌ 執行完整評估' : '✅ 使用快速模式'}`);
console.log(`   預期: ✅ 使用快速模式`);
console.log(`   ${!scenario3 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 4: 緩存使用10次（應該重新評估）
console.log('📝 測試場景 4: 緩存使用10次（需重新評估）');
const cache4 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 10,
    lastEvaluationSize: 100
};
const scenario4 = shouldDoFullEvaluation({ length: 100 }, cache4);
console.log(`   結果: ${scenario4 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估`);
console.log(`   ${scenario4 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 5: 數據量小幅增加（+5期，10%內）
console.log('📝 測試場景 5: 數據量小幅增加（+5期，剛好10%）');
const cache5 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 3,
    lastEvaluationSize: 50
};
const scenario5 = shouldDoFullEvaluation({ length: 55 }, cache5);
console.log(`   數據量變化: 50 → 55 期 (+10%)`);
console.log(`   結果: ${scenario5 ? '❌ 執行完整評估' : '✅ 使用快速模式'}`);
console.log(`   預期: ✅ 使用快速模式（因為剛好10%，不超過）`);
console.log(`   ${!scenario5 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 6: 數據量大幅增加（+11期，>10%）
console.log('📝 測試場景 6: 數據量大幅增加（+11期，>10%）');
const cache6 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 3,
    lastEvaluationSize: 100
};
const scenario6 = shouldDoFullEvaluation({ length: 111 }, cache6);
console.log(`   數據量變化: 100 → 111 期 (+11%)`);
console.log(`   結果: ${scenario6 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估（超過10%閾值）`);
console.log(`   ${scenario6 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 7: 數據量減少（-6期，>10%）
console.log('📝 測試場景 7: 數據量減少（-6期，>10%）');
const cache7 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 3,
    lastEvaluationSize: 50
};
const scenario7 = shouldDoFullEvaluation({ length: 44 }, cache7);
console.log(`   數據量變化: 50 → 44 期 (-12%)`);
console.log(`   結果: ${scenario7 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估（變化超過10%）`);
console.log(`   ${scenario7 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 8: 策略列表為空
console.log('📝 測試場景 8: 策略列表為空');
const cache8 = {
    topStrategies: [],
    evaluationCount: 3,
    lastEvaluationSize: 100
};
const scenario8 = shouldDoFullEvaluation({ length: 100 }, cache8);
console.log(`   結果: ${scenario8 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估`);
console.log(`   ${scenario8 ? '✅ 通過' : '❌ 失敗'}\n`);

// 測試場景 9: 缺少 lastEvaluationSize
console.log('📝 測試場景 9: 缺少 lastEvaluationSize');
const cache9 = {
    topStrategies: ['frequency', 'trend'],
    evaluationCount: 3
};
const scenario9 = shouldDoFullEvaluation({ length: 100 }, cache9);
console.log(`   結果: ${scenario9 ? '✅ 執行完整評估' : '❌ 使用快速模式'}`);
console.log(`   預期: ✅ 執行完整評估`);
console.log(`   ${scenario9 ? '✅ 通過' : '❌ 失敗'}\n`);

// 統計結果
const allTests = [scenario1, !scenario2, !scenario3, scenario4, !scenario5, scenario6, scenario7, scenario8, scenario9];
const passed = allTests.filter(t => t).length;
const total = allTests.length;

console.log('═'.repeat(60));
console.log(`\n📊 測試結果總結: ${passed}/${total} 通過\n`);

if (passed === total) {
    console.log('✅ 所有測試通過！緩存邏輯修復成功！');
    console.log('\n改進說明:');
    console.log('  ✅ 首次使用會執行完整評估');
    console.log('  ✅ 使用10次後會重新評估');
    console.log('  ✅ 數據量變化>10%會重新評估');
    console.log('  ✅ 缺少必要字段會觸發完整評估');
    console.log('  ✅ 策略列表為空會觸發完整評估');
} else {
    console.log(`❌ 有 ${total - passed} 個測試失敗`);
}

console.log('\n' + '═'.repeat(60));
