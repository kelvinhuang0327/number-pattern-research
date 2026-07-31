#!/usr/bin/env node
/**
 * 測試後端預測是否包含特別號碼
 */

const http = require('http');

// 模擬大樂透歷史數據
const testHistory = [
    { draw: '114000001', date: '2025-01-01', numbers: [1, 10, 15, 23, 30, 42], special: 35 },
    { draw: '114000002', date: '2025-01-04', numbers: [5, 12, 18, 27, 33, 49], special: 8 },
    { draw: '114000003', date: '2025-01-08', numbers: [2, 9, 17, 24, 31, 45], special: 12 },
    { draw: '114000004', date: '2025-01-11', numbers: [7, 14, 21, 28, 35, 44], special: 3 },
    { draw: '114000005', date: '2025-01-15', numbers: [3, 11, 19, 26, 38, 47], special: 22 }
];

const testRules = {
    pickCount: 6,
    minNumber: 1,
    maxNumber: 49,
    hasSpecialNumber: true,
    specialMinNumber: 1,
    specialMaxNumber: 49
};

const requestData = JSON.stringify({
    history: testHistory,
    lotteryRules: testRules,
    method: 'frequency' // 測試頻率分析方法
});

const options = {
    hostname: '127.0.0.1',
    port: 5001,
    path: '/api/predict',
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(requestData)
    }
};

console.log('🧪 測試後端預測是否包含特別號碼...\n');

const req = http.request(options, (res) => {
    let data = '';

    res.on('data', (chunk) => {
        data += chunk;
    });

    res.on('end', () => {
        try {
            const result = JSON.parse(data);

            console.log('📊 預測結果:');
            console.log('主號碼:', result.numbers);
            console.log('特別號碼:', result.special);
            console.log('方法:', result.method);
            console.log('信心度:', result.confidence);
            console.log('\n');

            if (result.special !== undefined && result.special !== null) {
                console.log('✅ 成功！後端返回了特別號碼:', result.special);
            } else {
                console.log('❌ 失敗！後端沒有返回特別號碼');
                console.log('完整響應:', JSON.stringify(result, null, 2));
            }
        } catch (error) {
            console.error('❌ 解析響應失敗:', error.message);
            console.log('原始響應:', data);
        }
    });
});

req.on('error', (error) => {
    console.error('❌ 請求失敗:', error.message);
    console.log('\n請確認後端服務運行正常: http://127.0.0.1:5001');
});

req.write(requestData);
req.end();
