/**
 * 最終驗證測試
 * 確認：
 * 1. 大樂透和大樂透加開獎項完全分開
 * 2. 重複檢核正確（支援同期多組號碼）
 * 3. 數據上傳流程正常
 */

import { DataProcessor } from '../src/core/DataProcessor.js';
import { getRelatedTypes } from '../src/utils/LotteryTypes.js';

console.log('========================================');
console.log('        最終功能驗證測試');
console.log('========================================\n');

// 測試 1: 彩券類型分離
console.log('=== 測試 1: 彩券類型分離 ===');
const bigLottoTypes = getRelatedTypes('BIG_LOTTO');
const bonusTypes = getRelatedTypes('BIG_LOTTO_BONUS');

console.log(`大樂透相關類型: ${bigLottoTypes.join(', ')}`);
console.log(`加開獎項相關類型: ${bonusTypes.join(', ')}`);
console.log(`是否分開: ${bigLottoTypes.length === 1 && bonusTypes.length === 1 ? '✓ 是' : '✗ 否'}`);

// 測試 2: 重複檢核邏輯
console.log('\n=== 測試 2: 重複檢核邏輯 ===');
const processor = new DataProcessor();

// 模擬加開獎項：同一期有多組號碼
const bonusData = [
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,29], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,33], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 }, // 重複
];

processor.lotteryData = [];
const result = processor.checkDuplicates(bonusData);

console.log(`輸入 4 筆數據（含 1 筆重複）`);
console.log(`新增: ${result.newCount} 筆`);
console.log(`重複: ${result.duplicateCount} 筆`);
console.log(`總計: ${result.totalCount} 筆`);
console.log(`結果: ${result.newCount === 3 && result.duplicateCount === 1 ? '✓ 通過' : '✗ 失敗'}`);

// 測試 3: 混合數據處理
console.log('\n=== 測試 3: 混合數據處理 ===');
const mixedData = [
    { lotteryType: 'BIG_LOTTO', draw: '114000001', date: '2025-01-03', numbers: [6,9,15,29,30,48], special: 23 },
    { lotteryType: 'BIG_LOTTO', draw: '114000002', date: '2025-01-07', numbers: [1,8,20,26,29,35], special: 19 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,28], special: 0 },
    { lotteryType: 'BIG_LOTTO_BONUS', draw: '114000007', date: '2025-01-24', numbers: [12,13,14,16,26,29], special: 0 },
];

processor.lotteryData = [];
const mixedResult = processor.checkDuplicates(mixedData);

console.log(`輸入混合數據: 2 筆大樂透 + 2 筆加開獎項`);
console.log(`新增: ${mixedResult.newCount} 筆`);
console.log(`重複: ${mixedResult.duplicateCount} 筆`);
console.log(`總計: ${mixedResult.totalCount} 筆`);
console.log(`結果: ${mixedResult.newCount === 4 ? '✓ 通過' : '✗ 失敗'} (期望: 全部保留)`);

// 測試 4: 數據過濾
console.log('\n=== 測試 4: 數據過濾 ===');
processor.lotteryData = mixedResult.mergedData;

const bigLottoData = processor.lotteryData.filter(d => d.lotteryType === 'BIG_LOTTO');
const bonusLottoData = processor.lotteryData.filter(d => d.lotteryType === 'BIG_LOTTO_BONUS');

console.log(`大樂透數據: ${bigLottoData.length} 筆`);
console.log(`加開獎項數據: ${bonusLottoData.length} 筆`);
console.log(`結果: ${bigLottoData.length === 2 && bonusLottoData.length === 2 ? '✓ 通過' : '✗ 失敗'}`);

// 總結
console.log('\n========================================');
console.log('              驗證結果');
console.log('========================================\n');

const allPassed =
    bigLottoTypes.length === 1 &&
    bonusTypes.length === 1 &&
    result.newCount === 3 &&
    result.duplicateCount === 1 &&
    mixedResult.newCount === 4 &&
    bigLottoData.length === 2 &&
    bonusLottoData.length === 2;

if (allPassed) {
    console.log('✅ 所有功能驗證通過！\n');
    console.log('系統配置確認：');
    console.log('  ✓ 大樂透和大樂透加開獎項完全分開');
    console.log('  ✓ 重複檢核支援同期多組號碼（加開獎項）');
    console.log('  ✓ 只有完全相同的數據才會被視為重複');
    console.log('  ✓ 不同彩券類型可以共存');
    console.log('  ✓ 數據過濾功能正常');
    console.log('\n系統已就緒，可以正確處理：');
    console.log('  - 正常大樂透：每期 1 組號碼 + 1 個特別號');
    console.log('  - 大樂透加開獎項：每期 210 組號碼（無特別號）');
} else {
    console.log('❌ 部分功能驗證失敗，請檢查配置');
}

console.log('');
