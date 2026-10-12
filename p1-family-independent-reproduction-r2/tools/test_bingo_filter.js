/**
 * 賓果檔案過濾功能測試
 * 在瀏覽器控制台中運行此腳本來測試過濾功能
 */

console.log('🧪 開始測試賓果檔案過濾功能...\n');

// 測試 1: 檢查 shouldIgnoreFile 方法是否存在
console.log('📋 測試 1: 檢查方法是否存在');
const app = window.app;
if (app && typeof app.shouldIgnoreFile === 'function') {
    console.log('  ✓ shouldIgnoreFile 方法存在');
} else {
    console.error('  ✗ shouldIgnoreFile 方法不存在');
}

// 測試 2: 測試各種檔名
console.log('\n📋 測試 2: 測試檔名過濾');

const testCases = [
    // 應該被忽略的檔案
    { filename: '賓果賓果_2024.csv', shouldIgnore: true },
    { filename: '賓果開獎記錄.csv', shouldIgnore: true },
    { filename: 'Bingo_Bingo_2024.csv', shouldIgnore: true },
    { filename: 'BINGO.csv', shouldIgnore: true },
    { filename: 'bingobingo_history.csv', shouldIgnore: true },
    { filename: '台灣彩券_賓果賓果.csv', shouldIgnore: true },

    // 不應該被忽略的檔案
    { filename: '大樂透_2024.csv', shouldIgnore: false },
    { filename: '威力彩開獎記錄.csv', shouldIgnore: false },
    { filename: '今彩539_history.csv', shouldIgnore: false },
    { filename: '三星彩.csv', shouldIgnore: false },
    { filename: 'lottery_data.csv', shouldIgnore: false },
];

let passCount = 0;
let failCount = 0;

testCases.forEach((testCase, index) => {
    const result = app.shouldIgnoreFile(testCase.filename);
    const expected = testCase.shouldIgnore;
    const passed = result === expected;

    if (passed) {
        console.log(`  ✓ 測試 ${index + 1}: ${testCase.filename}`);
        console.log(`    → 結果: ${result ? '忽略' : '不忽略'} (正確)`);
        passCount++;
    } else {
        console.error(`  ✗ 測試 ${index + 1}: ${testCase.filename}`);
        console.error(`    → 預期: ${expected ? '忽略' : '不忽略'}, 實際: ${result ? '忽略' : '不忽略'}`);
        failCount++;
    }
});

// 測試 3: 測試大小寫不敏感
console.log('\n📋 測試 3: 測試大小寫不敏感');

const caseTestCases = [
    'BINGO.csv',
    'Bingo.csv',
    'bingo.csv',
    'BiNgO.csv',
    '賓果.csv',
];

caseTestCases.forEach(filename => {
    const result = app.shouldIgnoreFile(filename);
    if (result) {
        console.log(`  ✓ ${filename} → 正確忽略`);
        passCount++;
    } else {
        console.error(`  ✗ ${filename} → 應該被忽略但沒有`);
        failCount++;
    }
});

// 測試結果總結
console.log('\n' + '='.repeat(50));
console.log('📊 測試結果總結');
console.log('='.repeat(50));
console.log(`✓ 通過: ${passCount} 個測試`);
console.log(`✗ 失敗: ${failCount} 個測試`);
console.log(`📈 成功率: ${((passCount / (passCount + failCount)) * 100).toFixed(2)}%`);

if (failCount === 0) {
    console.log('\n🎉 所有測試通過！賓果過濾功能正常工作。');
} else {
    console.error('\n⚠️ 有測試失敗，請檢查實現。');
}

// 測試 4: 實際檔案上傳模擬（僅顯示提示）
console.log('\n📋 測試 4: 檔案上傳模擬');
console.log('  ℹ️ 要測試實際上傳功能，請：');
console.log('  1. 準備一個包含「賓果」的測試檔案');
console.log('  2. 在上傳頁面選擇該檔案');
console.log('  3. 觀察是否顯示警告訊息');
console.log('  4. 檢查控制台是否有 🚫 忽略檔案 的日誌');

console.log('\n✅ 測試完成！');
