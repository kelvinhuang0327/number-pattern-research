/**
 * 方案 A 優化測試腳本
 *
 * 測試優化後的 4 個策略：
 * 1. Bayesian - 動態權重調整
 * 2. Frequency - 自適應衰減係數
 * 3. Odd_Even - 位置分佈增強
 * 4. Hot_Cold - 動態窗口選擇
 */

import fetch from 'node-fetch';

const API_BASE = 'http://localhost:5001/api';

// 生成測試數據（大樂透格式）
function generateTestData(count = 100) {
    const data = [];
    const startDate = new Date('2023-01-01');

    for (let i = 0; i < count; i++) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i * 3); // 每3天一期

        // 隨機生成 6 個號碼（1-49）
        const numbers = [];
        while (numbers.length < 6) {
            const num = Math.floor(Math.random() * 49) + 1;
            if (!numbers.includes(num)) {
                numbers.push(num);
            }
        }
        numbers.sort((a, b) => a - b);

        data.push({
            draw: `${2023}${String(i + 1).padStart(3, '0')}`,
            date: date.toISOString().split('T')[0],
            numbers: numbers,
            lotteryType: 'BIG_LOTTO',
            year: 2023 + Math.floor(i / 100)
        });
    }

    return data;
}

// 測試單個策略
async function testStrategy(strategyName, history, lotteryRules) {
    try {
        const response = await fetch(`${API_BASE}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                modelType: strategyName,
                history: history,
                lotteryRules: lotteryRules
            })
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`API Error: ${response.status} - ${error}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`❌ ${strategyName} 測試失敗:`, error.message);
        return null;
    }
}

// 主測試函數
async function runOptimizationTests() {
    console.log('🚀 開始方案 A 優化測試\n');
    console.log('=' . repeat(80));

    // 生成測試數據
    console.log('\n📊 生成測試數據...');
    const testData = generateTestData(100);
    console.log(`✅ 生成 ${testData.length} 期測試數據\n`);

    const lotteryRules = {
        pickCount: 6,
        minNumber: 1,
        maxNumber: 49,
        lotteryType: 'BIG_LOTTO'
    };

    // 測試策略列表
    const strategies = [
        { name: 'bayesian', displayName: 'Bayesian (動態權重)' },
        { name: 'frequency', displayName: 'Frequency (自適應衰減)' },
        { name: 'odd_even', displayName: 'Odd_Even (位置分佈)' },
        { name: 'hot_cold', displayName: 'Hot_Cold (動態窗口)' }
    ];

    console.log('🧪 測試優化後的策略...\n');
    console.log('=' . repeat(80));

    // 測試每個策略
    for (const strategy of strategies) {
        console.log(`\n🔍 測試: ${strategy.displayName}`);
        console.log('-'.repeat(80));

        const result = await testStrategy(strategy.name, testData, lotteryRules);

        if (result) {
            console.log(`✅ 預測成功`);
            console.log(`   號碼: ${result.numbers.join(', ')}`);
            console.log(`   信心度: ${(result.confidence * 100).toFixed(1)}%`);
            console.log(`   方法: ${result.method}`);

            if (result.probabilities && result.probabilities.length > 0) {
                const avgProb = result.probabilities.reduce((a, b) => a + b, 0) / result.probabilities.length;
                console.log(`   平均概率: ${(avgProb * 100).toFixed(2)}%`);
            }
        } else {
            console.log(`❌ 測試失敗`);
        }

        // 延遲避免請求過快
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    console.log('\n' + '='.repeat(80));
    console.log('✅ 測試完成！');
    console.log('\n💡 觀察要點：');
    console.log('   1. Bayesian 信心度是否提升（目標: 0.68 → 0.74-0.82）');
    console.log('   2. Frequency 信心度是否提升（目標: 動態 → 0.70-0.90）');
    console.log('   3. Odd_Even 信心度是否提升（目標: 0.55 → 0.63-0.70）');
    console.log('   4. Hot_Cold 信心度是否提升（目標: 0.62 → 0.68-0.74）');
    console.log('\n📈 預期整體提升: +8-15%');
}

// 錯誤處理
process.on('unhandledRejection', (error) => {
    console.error('❌ 未處理的錯誤:', error);
    process.exit(1);
});

// 執行測試
console.log('🎯 方案 A 優化測試腳本');
console.log('=' . repeat(80));
console.log('\n⚠️  請確保後端服務已啟動 (http://localhost:5001)');
console.log('\n按 Ctrl+C 取消測試\n');

setTimeout(() => {
    runOptimizationTests().catch(error => {
        console.error('❌ 測試執行失敗:', error);
        process.exit(1);
    });
}, 2000);
