/**
 * 測試檔案過濾邏輯
 * 驗證只允許上傳「大樂透」檔案，排除其他彩券類型
 */

function shouldIgnoreFile(filename) {
    const lowerFilename = filename.toLowerCase();

    // ✅ 只允許「大樂透」的檔案（不包含「加開」）
    const allowKeywords = [
        '大樂透'
    ];

    // ❌ 排除關鍵字：加開、其他彩券類型
    const rejectKeywords = [
        '加開',
        '賓果',
        'bingo',
        '威力彩',
        '今彩',
        '539',
        '38樂合彩',
        '49樂合彩',
        '雙贏彩',
        '三星彩',
        '四星彩'
    ];

    // 檢查是否包含排除關鍵字
    const hasRejectKeyword = rejectKeywords.some(keyword =>
        lowerFilename.includes(keyword)
    );

    // 檢查是否包含允許關鍵字
    const hasAllowKeyword = allowKeywords.some(keyword =>
        lowerFilename.includes(keyword)
    );

    // 只有包含「大樂透」且不包含排除關鍵字的檔案才允許上傳
    return !hasAllowKeyword || hasRejectKeyword;
}

// 測試案例
const testCases = [
    // ✅ 應該允許的檔案
    { filename: '大樂透_2024.csv', shouldIgnore: false, description: '大樂透檔案' },
    { filename: '大樂透開獎項_113.csv', shouldIgnore: false, description: '大樂透開獎項' },
    { filename: 'Lotto_大樂透_2023.csv', shouldIgnore: false, description: '包含大樂透的檔案' },

    // ❌ 應該拒絕的檔案
    { filename: '大樂透加開獎項_2024.csv', shouldIgnore: true, description: '大樂透加開（包含「加開」）' },
    { filename: '賓果賓果_2024.csv', shouldIgnore: true, description: '賓果賓果' },
    { filename: 'bingo_2024.csv', shouldIgnore: true, description: 'Bingo' },
    { filename: '威力彩_2024.csv', shouldIgnore: true, description: '威力彩' },
    { filename: '今彩539_2024.csv', shouldIgnore: true, description: '今彩539' },
    { filename: '38樂合彩_2024.csv', shouldIgnore: true, description: '38樂合彩' },
    { filename: '49樂合彩_2024.csv', shouldIgnore: true, description: '49樂合彩' },
    { filename: '雙贏彩_2024.csv', shouldIgnore: true, description: '雙贏彩' },
    { filename: '三星彩_2024.csv', shouldIgnore: true, description: '三星彩' },
    { filename: '四星彩_2024.csv', shouldIgnore: true, description: '四星彩' },
    { filename: 'random_file.csv', shouldIgnore: true, description: '無關檔案（不包含大樂透）' },
];

console.log('╔══════════════════════════════════════════════════════════╗');
console.log('║      檔案過濾邏輯測試 - 僅允許「大樂透」檔案           ║');
console.log('╚══════════════════════════════════════════════════════════╝');
console.log('');

let passCount = 0;
let failCount = 0;

testCases.forEach((testCase, index) => {
    const result = shouldIgnoreFile(testCase.filename);
    const passed = result === testCase.shouldIgnore;

    const status = passed ? '✅ PASS' : '❌ FAIL';
    const action = testCase.shouldIgnore ? '拒絕' : '允許';

    console.log(`${index + 1}. ${status} | ${action} | ${testCase.description}`);
    console.log(`   檔案: ${testCase.filename}`);
    console.log(`   預期: ${testCase.shouldIgnore ? '忽略' : '允許'} | 實際: ${result ? '忽略' : '允許'}`);
    console.log('');

    if (passed) {
        passCount++;
    } else {
        failCount++;
    }
});

console.log('═══════════════════════════════════════════════════════════');
console.log(`測試結果: ${passCount}/${testCases.length} 通過`);
if (failCount > 0) {
    console.log(`❌ ${failCount} 個測試失敗`);
} else {
    console.log('✅ 所有測試通過！');
}
console.log('═══════════════════════════════════════════════════════════');
