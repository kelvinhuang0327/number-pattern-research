/**
 * 測試大樂透與大樂透加開獎項的合併功能
 */

import { getRelatedTypes, getBaseType, LOTTERY_TYPES } from '../src/utils/LotteryTypes.js';

console.log('========================================');
console.log('  測試彩券類型合併功能');
console.log('========================================\n');

// 測試 1: 基礎類型映射
console.log('=== 測試 1: 基礎類型映射 ===');
console.log('BIG_LOTTO 的基礎類型:', getBaseType('BIG_LOTTO'));
console.log('BIG_LOTTO_BONUS 的基礎類型:', getBaseType('BIG_LOTTO_BONUS'));
console.log('');

// 測試 2: 相關類型獲取
console.log('=== 測試 2: 相關類型獲取 ===');
const bigLottoRelated = getRelatedTypes('BIG_LOTTO');
console.log('BIG_LOTTO 的相關類型:', bigLottoRelated);

const bonusRelated = getRelatedTypes('BIG_LOTTO_BONUS');
console.log('BIG_LOTTO_BONUS 的相關類型:', bonusRelated);
console.log('');

// 測試 3: 驗證兩者應該返回相同的相關類型列表
console.log('=== 測試 3: 驗證合併邏輯 ===');
const isSameRelated = JSON.stringify(bigLottoRelated.sort()) === JSON.stringify(bonusRelated.sort());
console.log('BIG_LOTTO 和 BIG_LOTTO_BONUS 的相關類型是否相同:', isSameRelated ? '✓ 是' : '✗ 否');
console.log('');

// 測試 4: 驗證配置
console.log('=== 測試 4: 驗證彩券配置 ===');
console.log('BIG_LOTTO:');
console.log('  - pickCount:', LOTTERY_TYPES.BIG_LOTTO.pickCount);
console.log('  - hasSpecialNumber:', LOTTERY_TYPES.BIG_LOTTO.hasSpecialNumber);
console.log('  - numberRange:', `${LOTTERY_TYPES.BIG_LOTTO.numberRange.min}-${LOTTERY_TYPES.BIG_LOTTO.numberRange.max}`);

console.log('\nBIG_LOTTO_BONUS:');
console.log('  - pickCount:', LOTTERY_TYPES.BIG_LOTTO_BONUS.pickCount);
console.log('  - hasSpecialNumber:', LOTTERY_TYPES.BIG_LOTTO_BONUS.hasSpecialNumber);
console.log('  - numberRange:', `${LOTTERY_TYPES.BIG_LOTTO_BONUS.numberRange.min}-${LOTTERY_TYPES.BIG_LOTTO_BONUS.numberRange.max}`);
console.log('  - baseType:', LOTTERY_TYPES.BIG_LOTTO_BONUS.baseType);
console.log('');

// 測試 5: 模擬數據過濾
console.log('=== 測試 5: 模擬數據過濾 ===');
const mockData = [
    { draw: '001', lotteryType: 'BIG_LOTTO', numbers: [1,2,3,4,5,6] },
    { draw: '002', lotteryType: 'BIG_LOTTO_BONUS', numbers: [7,8,9,10,11,12] },
    { draw: '003', lotteryType: 'BIG_LOTTO', numbers: [13,14,15,16,17,18] },
    { draw: '004', lotteryType: 'BIG_LOTTO_BONUS', numbers: [19,20,21,22,23,24] },
    { draw: '005', lotteryType: 'STAR_3', numbers: [1,2,3] }
];

const filteredData = mockData.filter(d => bigLottoRelated.includes(d.lotteryType));
console.log(`原始數據: ${mockData.length} 筆`);
console.log(`過濾後（包含 BIG_LOTTO + BIG_LOTTO_BONUS）: ${filteredData.length} 筆`);
console.log('過濾結果:');
filteredData.forEach(d => {
    console.log(`  - ${d.draw}: ${d.lotteryType}`);
});
console.log('');

// 總結
console.log('========================================');
console.log('              測試總結');
console.log('========================================');
if (isSameRelated && bigLottoRelated.length === 2 && filteredData.length === 4) {
    console.log('✓ 所有測試通過！');
    console.log('✓ 大樂透與大樂透加開獎項將合併使用');
    console.log(`✓ 包含類型: ${bigLottoRelated.join(', ')}`);
} else {
    console.log('✗ 部分測試失敗');
}
console.log('');
