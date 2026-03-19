/**
 * 測試彩券類型偵測
 */

import { detectLotteryType, LOTTERY_TYPES } from './src/utils/LotteryTypes.js';

console.log('=== 測試彩券類型偵測 ===\n');

const testCases = [
    { csvName: '大樂透', expected: 'BIG_LOTTO' },
    { csvName: '威力彩', expected: 'POWER_BALL' },
    { csvName: '今彩539', expected: 'DAILY_CASH_539' },
    { csvName: '49樂合彩', expected: 'LOTTO_49' },
    { csvName: '39樂合彩', expected: 'LOTTO_39' },
    { csvName: '四星彩', expected: 'STAR_4' },
    { csvName: '三星彩', expected: 'STAR_3' },
    { csvName: '賓果賓果', expected: 'BINGO_BINGO' },
    { csvName: '春節加碼活動', expected: 'BIG_LOTTO_BONUS' },
    { csvName: '3星彩', expected: 'STAR_3' },
    { csvName: '4星彩', expected: 'STAR_4' }
];

testCases.forEach(({ csvName, expected }) => {
    const detected = detectLotteryType(csvName);
    const success = detected && detected.id === expected;
    
    console.log(`${success ? '✓' : '✗'} "${csvName}"`);
    console.log(`  預期: ${expected}`);
    console.log(`  偵測: ${detected ? detected.id : 'null'}`);
    
    if (detected) {
        console.log(`  顯示名稱: ${detected.displayName}`);
        console.log(`  號碼範圍: ${detected.numberRange.min}-${detected.numberRange.max}`);
        console.log(`  選號數: ${detected.pickCount}`);
        console.log(`  特別號: ${detected.hasSpecialNumber ? '是' : '否'}`);
    }
    console.log('');
});

// 顯示所有彩券類型的 csvName
console.log('\n=== 所有彩券類型的 csvName ===\n');
Object.keys(LOTTERY_TYPES).forEach(key => {
    const type = LOTTERY_TYPES[key];
    console.log(`${type.id.padEnd(20)} → csvName: "${type.csvName}"`);
    if (type.aliases && type.aliases.length > 0) {
        console.log(`${' '.repeat(20)}   aliases: [${type.aliases.map(a => `"${a}"`).join(', ')}]`);
    }
});
