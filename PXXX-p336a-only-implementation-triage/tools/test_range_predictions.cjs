#!/usr/bin/env node
/**
 * 測試後端範圍預測是否會根據不同的範圍返回不同的預測結果
 */

const http = require('http');

// 測試兩個不同的範圍
const testCases = [
    {
        name: '測試 1: 期數 96000001 - 114000100',
        range: { startDraw: '96000001', endDraw: '114000100' }
    },
    {
        name: '測試 2: 期數 96000001 - 114000105',
        range: { startDraw: '96000001', endDraw: '114000105' }
    },
    {
        name: '測試 3: 期數 96000001 - 114000110',
        range: { startDraw: '96000001', endDraw: '114000110' }
    }
];

async function testPrediction(testCase) {
    return new Promise((resolve, reject) => {
        const requestData = JSON.stringify({
            lotteryType: 'BIG_LOTTO',
            modelType: 'frequency',
            startDraw: testCase.range.startDraw,
            endDraw: testCase.range.endDraw
        });

        const options = {
            hostname: '127.0.0.1',
            port: 5001,
            path: '/api/predict-with-range',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(requestData)
            }
        };

        console.log(`\n🧪 ${testCase.name}`);
        console.log(`   範圍: ${testCase.range.startDraw} - ${testCase.range.endDraw}`);

        const req = http.request(options, (res) => {
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    console.log(`   ✅ 預測號碼: ${result.numbers.join(', ')}`);
                    if (result.special) {
                        console.log(`   ✅ 特別號碼: ${result.special}`);
                    }
                    console.log(`   信心度: ${result.confidence}`);
                    resolve(result.numbers);
                } catch (error) {
                    console.error(`   ❌ 解析響應失敗:`, error.message);
                    reject(error);
                }
            });
        });

        req.on('error', (error) => {
            console.error(`   ❌ 請求失敗:`, error.message);
            reject(error);
        });

        req.write(requestData);
        req.end();
    });
}

async function runTests() {
    console.log('=' .repeat(60));
    console.log('測試後端範圍預測的變化性');
    console.log('=' .repeat(60));

    const results = [];

    for (const testCase of testCases) {
        try {
            const prediction = await testPrediction(testCase);
            results.push({ name: testCase.name, prediction });
            // 延遲一下避免請求過快
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch (error) {
            console.error(`測試失敗: ${error.message}`);
        }
    }

    console.log('\n' + '='.repeat(60));
    console.log('📊 結果比較:');
    console.log('='.repeat(60));

    // 比較結果
    const allSame = results.length > 1 && results.every((r, i) =>
        i === 0 || JSON.stringify(r.prediction) === JSON.stringify(results[0].prediction)
    );

    if (allSame) {
        console.log('❌ 問題確認：所有預測結果完全相同！');
        console.log('   這違反了滾動窗口的邏輯。');
    } else {
        console.log('✅ 正常：不同範圍產生了不同的預測結果。');
    }

    console.log('\n詳細結果:');
    results.forEach((r, i) => {
        console.log(`${i + 1}. ${r.name}`);
        console.log(`   預測: [${r.prediction.join(', ')}]`);
    });
}

runTests().catch(console.error);
