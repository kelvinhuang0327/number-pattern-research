/**
 * 測試大樂透與大樂透加開獎項的 CSV 解析
 */

import { DataProcessor } from './src/core/DataProcessor.js';
import { LOTTERY_TYPES } from './src/utils/LotteryTypes.js';
import fs from 'fs';

// 顯示配置
console.log('\n=== 大樂透配置 ===');
console.log('BIG_LOTTO:', {
    displayName: LOTTERY_TYPES.BIG_LOTTO.displayName,
    hasSpecialNumber: LOTTERY_TYPES.BIG_LOTTO.hasSpecialNumber,
    pickCount: LOTTERY_TYPES.BIG_LOTTO.pickCount
});

console.log('\nBIG_LOTTO_BONUS:', {
    displayName: LOTTERY_TYPES.BIG_LOTTO_BONUS.displayName,
    hasSpecialNumber: LOTTERY_TYPES.BIG_LOTTO_BONUS.hasSpecialNumber,
    pickCount: LOTTERY_TYPES.BIG_LOTTO_BONUS.pickCount,
    aliases: LOTTERY_TYPES.BIG_LOTTO_BONUS.aliases
});

// 測試加開獎項數據
console.log('\n=== 測試加開獎項驗證 ===');
const processor = new DataProcessor();

// 模擬加開獎項的一筆數據（沒有特別號）
const bonusDraw = {
    draw: '113001-01',
    date: '2025-02-08',
    lotteryType: 'BIG_LOTTO_BONUS',
    numbers: [5, 12, 23, 31, 38, 45],
    special: 0  // 加開獎項沒有特別號
};

// 模擬正常大樂透的一筆數據（有特別號）
const normalDraw = {
    draw: '113001',
    date: '2025-01-03',
    lotteryType: 'BIG_LOTTO',
    numbers: [3, 15, 21, 28, 35, 42],
    special: 18  // 正常大樂透有特別號
};

console.log('\n正常大樂透驗證:');
const normalValid = processor.validateDraw(
    normalDraw.numbers, 
    normalDraw.special, 
    LOTTERY_TYPES.BIG_LOTTO
);
console.log(`  號碼: [${normalDraw.numbers.join(', ')}], 特別號: ${normalDraw.special}`);
console.log(`  驗證結果: ${normalValid ? '✓ 通過' : '✗ 失敗'}`);

console.log('\n加開獎項驗證:');
const bonusValid = processor.validateDraw(
    bonusDraw.numbers, 
    bonusDraw.special, 
    LOTTERY_TYPES.BIG_LOTTO_BONUS
);
console.log(`  號碼: [${bonusDraw.numbers.join(', ')}], 特別號: ${bonusDraw.special}`);
console.log(`  驗證結果: ${bonusValid ? '✓ 通過' : '✗ 失敗'}`);

// 測試錯誤情況：加開獎項不應該有特別號
console.log('\n錯誤測試（加開獎項有特別號）:');
const bonusInvalid = processor.validateDraw(
    bonusDraw.numbers, 
    18,  // 不應該有特別號
    LOTTERY_TYPES.BIG_LOTTO_BONUS
);
console.log(`  號碼: [${bonusDraw.numbers.join(', ')}], 特別號: 18`);
console.log(`  驗證結果: ${bonusInvalid ? '✗ 錯誤通過' : '✓ 正確拒絕'}`);

console.log('\n=== 測試完成 ===\n');

// 如果檔案存在，測試實際 CSV 解析
const normalCSV = '/Users/kelvin/Downloads/獎號/2025/大樂透_2025.csv';
const bonusCSV = '/Users/kelvin/Downloads/獎號/2025/大樂透加開獎項_2025.csv';

async function testCSVFiles() {
    console.log('\n=== 測試實際 CSV 檔案 ===');
    
    if (fs.existsSync(normalCSV)) {
        console.log(`\n測試: ${normalCSV}`);
        try {
            const file = { 
                name: '大樂透_2025.csv',
                path: normalCSV
            };
            // 這裡需要用 File API，簡化版先跳過
            console.log('  檔案存在 ✓');
        } catch (error) {
            console.log(`  錯誤: ${error.message}`);
        }
    } else {
        console.log(`\n檔案不存在: ${normalCSV}`);
    }
    
    if (fs.existsSync(bonusCSV)) {
        console.log(`\n測試: ${bonusCSV}`);
        try {
            const file = { 
                name: '大樂透加開獎項_2025.csv',
                path: bonusCSV
            };
            console.log('  檔案存在 ✓');
        } catch (error) {
            console.log(`  錯誤: ${error.message}`);
        }
    } else {
        console.log(`\n檔案不存在: ${bonusCSV}`);
    }
}

testCSVFiles().catch(console.error);
