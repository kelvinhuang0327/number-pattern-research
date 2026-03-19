/**
 * 測試重複數據檢核邏輯
 */

import { DataProcessor } from '../src/core/DataProcessor.js';

console.log('========================================');
console.log('  測試重複數據檢核邏輯');
console.log('========================================\n');

const processor = new DataProcessor();

// 測試案例 1: 同一期數，不同號碼（加開獎項情境）
console.log('=== 測試 1: 同一期數，不同號碼（應全部保留）===');
const testData1 = [
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,29], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,33], special: 0 },
];

processor.lotteryData = [];
const result1 = processor.checkDuplicates(testData1);

console.log(`輸入: ${testData1.length} 筆`);
console.log(`新增: ${result1.newCount} 筆`);
console.log(`重複: ${result1.duplicateCount} 筆`);
console.log(`總計: ${result1.totalCount} 筆`);
console.log(`結果: ${result1.newCount === 3 ? '✓ 通過' : '✗ 失敗'} (期望: 全部保留)`);

// 測試案例 2: 完全相同的數據（應視為重複）
console.log('\n=== 測試 2: 完全相同的數據（應標記為重複）===');
const testData2 = [
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 }, // 重複
];

processor.lotteryData = [];
const result2 = processor.checkDuplicates(testData2);

console.log(`輸入: ${testData2.length} 筆`);
console.log(`新增: ${result2.newCount} 筆`);
console.log(`重複: ${result2.duplicateCount} 筆`);
console.log(`總計: ${result2.totalCount} 筆`);
console.log(`結果: ${result2.duplicateCount === 1 ? '✓ 通過' : '✗ 失敗'} (期望: 1 筆重複)`);

// 測試案例 3: 混合情境（有新增有重複）
console.log('\n=== 測試 3: 混合情境 ===');
processor.lotteryData = [
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 }
];

const testData3 = [
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 }, // 重複
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,29], special: 0 }, // 新增
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000008', date: '2025-01-25', numbers: [1,2,3,4,5,6], special: 0 },      // 新增
];

const result3 = processor.checkDuplicates(testData3);

console.log(`現有: 1 筆`);
console.log(`輸入: ${testData3.length} 筆`);
console.log(`新增: ${result3.newCount} 筆`);
console.log(`重複: ${result3.duplicateCount} 筆`);
console.log(`總計: ${result3.totalCount} 筆`);
console.log(`結果: ${result3.newCount === 2 && result3.duplicateCount === 1 ? '✓ 通過' : '✗ 失敗'} (期望: 2 筆新增, 1 筆重複)`);

// 測試案例 4: 不同彩券類型，相同期數和號碼（應分開處理）
console.log('\n=== 測試 4: 不同彩券類型 ===');
const testData4 = [
    { lotteryType: 'BIG_LOTTO', draw: '114000001', date: '2025-01-03', numbers: [6,9,15,29,30,48], special: 23 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000001', date: '2025-01-03', numbers: [6,9,15,29,30,48], special: 0 },
];

processor.lotteryData = [];
const result4 = processor.checkDuplicates(testData4);

console.log(`輸入: ${testData4.length} 筆`);
console.log(`新增: ${result4.newCount} 筆`);
console.log(`重複: ${result4.duplicateCount} 筆`);
console.log(`總計: ${result4.totalCount} 筆`);
console.log(`結果: ${result4.newCount === 2 ? '✓ 通過' : '✗ 失敗'} (期望: 全部保留，因為彩券類型不同)`);

// 總結
console.log('\n========================================');
console.log('              測試總結');
console.log('========================================');

const allPassed =
    result1.newCount === 3 &&
    result2.duplicateCount === 1 &&
    result3.newCount === 2 && result3.duplicateCount === 1 &&
    result4.newCount === 2;

if (allPassed) {
    console.log('✓ 所有測試通過！');
    console.log('\n重複檢核邏輯：');
    console.log('  - ✓ 同一期數的不同號碼會全部保留（支援加開獎項）');
    console.log('  - ✓ 完全相同的數據會被標記為重複');
    console.log('  - ✓ 不同彩券類型會分開處理');
} else {
    console.log('✗ 部分測試失敗，請檢查邏輯');
}

console.log('');
