#!/usr/bin/env node

/**
 * 多彩券類型策略測試腳本
 * 測試所有 14 個策略在不同彩券類型下的運作
 */

import { DataProcessor } from '../src/data/DataProcessor.js';
import { StatisticsService } from '../src/data/StatisticsService.js';
import { PredictionEngine } from '../src/engine/PredictionEngine.js';
import { LOTTERY_TYPES } from '../src/utils/LotteryTypes.js';

// 測試配置
const TEST_LOTTERY_TYPES = ['BIG_LOTTO', 'STAR_3', 'DAILY_CASH_539', 'STAR_4'];
const ALL_STRATEGIES = [
    'frequency', 'trend', 'hot_cold', 'collaborative_hybrid',
    'deviation', 'odd_even', 'zone_balance', 'sum_range',
    'bayesian', 'markov', 'montecarlo', 'wheeling',
    'number_pairs', 'statistical'
];

// 生成測試數據
function generateTestData(lotteryTypeId, count = 50) {
    const lotteryType = LOTTERY_TYPES[lotteryTypeId];
    if (!lotteryType) {
        throw new Error(`Unknown lottery type: ${lotteryTypeId}`);
    }

    const { min, max } = lotteryType.numberRange;
    const pickCount = lotteryType.pickCount;
    const data = [];

    for (let i = 0; i < count; i++) {
        const numbers = new Set();
        while (numbers.size < pickCount) {
            const num = Math.floor(Math.random() * (max - min + 1)) + min;
            numbers.add(num);
        }

        const date = new Date(2024, 0, i + 1);
        data.push({
            draw: `${count - i}`.padStart(6, '0'),
            date: date.toISOString().split('T')[0],
            lotteryType: lotteryTypeId,
            numbers: Array.from(numbers).sort((a, b) => a - b),
            special: lotteryType.hasSpecialNumber ?
                Math.floor(Math.random() * (lotteryType.specialNumberRange.max - lotteryType.specialNumberRange.min + 1)) + lotteryType.specialNumberRange.min :
                0
        });
    }

    return data.reverse(); // 最新的在前
}

// 驗證預測結果
function validatePrediction(result, lotteryTypeId) {
    const lotteryType = LOTTERY_TYPES[lotteryTypeId];
    const { min, max } = lotteryType.numberRange;
    const pickCount = lotteryType.pickCount;

    const errors = [];

    // 檢查是否有 numbers 屬性
    if (!result.numbers || !Array.isArray(result.numbers)) {
        errors.push('Missing or invalid numbers array');
        return { valid: false, errors };
    }

    // 檢查數量
    if (result.numbers.length !== pickCount) {
        errors.push(`Wrong count: expected ${pickCount}, got ${result.numbers.length}`);
    }

    // 檢查範圍
    for (const num of result.numbers) {
        if (num < min || num > max) {
            errors.push(`Number ${num} out of range [${min}, ${max}]`);
        }
    }

    // 檢查重複
    const unique = new Set(result.numbers);
    if (unique.size !== result.numbers.length) {
        errors.push('Duplicate numbers found');
    }

    return {
        valid: errors.length === 0,
        errors
    };
}

// 執行測試
async function runTests() {
    console.log('🧪 多彩券類型策略測試\n');
    console.log('='.repeat(80));

    let totalTests = 0;
    let passedTests = 0;
    let failedTests = 0;

    for (const lotteryTypeId of TEST_LOTTERY_TYPES) {
        const lotteryType = LOTTERY_TYPES[lotteryTypeId];
        if (!lotteryType) {
            console.log(`\n⚠️  跳過未知彩券類型: ${lotteryTypeId}`);
            continue;
        }

        console.log(`\n📊 測試彩券類型: ${lotteryType.name} (${lotteryType.numberRange.min}-${lotteryType.numberRange.max}, pick ${lotteryType.pickCount})`);
        console.log('-'.repeat(80));

        // 生成測試數據
        const testData = generateTestData(lotteryTypeId, 50);

        // 初始化服務
        const dataProcessor = new DataProcessor();
        dataProcessor.data = testData;
        const statisticsService = new StatisticsService(dataProcessor);
        const predictionEngine = new PredictionEngine(dataProcessor, statisticsService);

        // 測試每個策略
        for (const strategy of ALL_STRATEGIES) {
            totalTests++;

            try {
                const result = await predictionEngine.predict(strategy, 50, lotteryTypeId);
                const validation = validatePrediction(result, lotteryTypeId);

                if (validation.valid) {
                    passedTests++;
                    console.log(`  ✅ ${strategy.padEnd(25)} → [${result.numbers.join(', ')}]`);
                } else {
                    failedTests++;
                    console.log(`  ❌ ${strategy.padEnd(25)} → FAILED`);
                    validation.errors.forEach(err => console.log(`     ↳ ${err}`));
                }
            } catch (error) {
                failedTests++;
                console.log(`  ❌ ${strategy.padEnd(25)} → ERROR: ${error.message}`);
            }
        }
    }

    // 總結
    console.log('\n' + '='.repeat(80));
    console.log('📈 測試總結');
    console.log('='.repeat(80));
    console.log(`總測試數: ${totalTests}`);
    console.log(`✅ 通過: ${passedTests} (${((passedTests / totalTests) * 100).toFixed(1)}%)`);
    console.log(`❌ 失敗: ${failedTests} (${((failedTests / totalTests) * 100).toFixed(1)}%)`);

    if (failedTests === 0) {
        console.log('\n🎉 所有測試通過！系統已準備好上線。');
    } else {
        console.log('\n⚠️  部分測試失敗，請檢查錯誤訊息。');
    }

    return failedTests === 0;
}

// 執行測試
runTests().then(success => {
    process.exit(success ? 0 : 1);
}).catch(error => {
    console.error('測試執行失敗:', error);
    process.exit(1);
});
