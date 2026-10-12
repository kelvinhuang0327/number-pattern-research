/**
 * 檢查所有 CSV 文件的數據量和重複情況
 */

import fs from 'fs';
import path from 'path';

const csvDir = '/Users/kelvin/Downloads/獎號/2025/';

const files = [
    '大樂透_2025.csv',
    '大樂透加開獎項_2025.csv',
    '威力彩_2025.csv',
    '今彩539_2025.csv',
    '3星彩_2025.csv',
    '4星彩_2025.csv',
    '39樂合彩_2025.csv',
    '49樂合彩_2025.csv',
    '賓果賓果_2025.csv'
];

console.log('========================================');
console.log('      檢查所有 CSV 數據文件');
console.log('========================================\n');

const results = [];

files.forEach(filename => {
    const filePath = path.join(csvDir, filename);

    if (!fs.existsSync(filePath)) {
        console.log(`❌ ${filename}: 文件不存在`);
        return;
    }

    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split(/\r?\n/).filter(line => line.trim());

    const totalLines = lines.length - 1; // 扣除表頭

    if (totalLines === 0) {
        console.log(`⚠️  ${filename}: 無數據`);
        results.push({ file: filename, lines: 0, uniqueDraws: 0, status: 'empty' });
        return;
    }

    // 統計唯一期數
    const draws = new Set();
    const drawNumbers = new Map(); // 每期有多少組號碼

    for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',');
        if (parts.length > 1) {
            const draw = parts[1].trim();
            draws.add(draw);
            drawNumbers.set(draw, (drawNumbers.get(draw) || 0) + 1);
        }
    }

    const uniqueDraws = draws.size;
    const avgPerDraw = uniqueDraws > 0 ? (totalLines / uniqueDraws).toFixed(1) : 0;

    // 檢查是否有多組號碼的期數
    const multiDraws = Array.from(drawNumbers.entries()).filter(([_, count]) => count > 1);
    const hasMultiplePerDraw = multiDraws.length > 0;

    console.log(`✓ ${filename}:`);
    console.log(`    總筆數: ${totalLines.toLocaleString()}`);
    console.log(`    唯一期數: ${uniqueDraws}`);
    console.log(`    平均每期: ${avgPerDraw} 組`);

    if (hasMultiplePerDraw) {
        const maxCount = Math.max(...Array.from(drawNumbers.values()));
        console.log(`    ⚠️  部分期數有多組號碼（最多 ${maxCount} 組/期）`);
    }

    console.log('');

    results.push({
        file: filename,
        lines: totalLines,
        uniqueDraws: uniqueDraws,
        avgPerDraw: parseFloat(avgPerDraw),
        hasMultiple: hasMultiplePerDraw,
        status: 'ok'
    });
});

// 總結
console.log('========================================');
console.log('              總結報告');
console.log('========================================\n');

const validFiles = results.filter(r => r.status === 'ok' && r.lines > 0);
const emptyFiles = results.filter(r => r.status === 'empty');

console.log(`檢查文件: ${files.length} 個`);
console.log(`有數據: ${validFiles.length} 個`);
console.log(`無數據: ${emptyFiles.length} 個\n`);

if (validFiles.length > 0) {
    console.log('有數據的文件：');
    validFiles.forEach(r => {
        const multipleFlag = r.hasMultiple ? '  (每期多組)' : '';
        console.log(`  - ${r.file}: ${r.lines.toLocaleString()} 筆, ${r.uniqueDraws} 期${multipleFlag}`);
    });
}

if (emptyFiles.length > 0) {
    console.log('\n無數據的文件：');
    emptyFiles.forEach(r => {
        console.log(`  - ${r.file}`);
    });
}

const totalRecords = validFiles.reduce((sum, r) => sum + r.lines, 0);
console.log(`\n總數據量: ${totalRecords.toLocaleString()} 筆`);

console.log('\n建議：');
console.log('  1. 先上傳有數據的文件進行測試');
console.log('  2. 注意「每期多組」的文件（如加開獎項）屬正常現象');
console.log('  3. 無數據的文件可等資料更新後再上傳');
console.log('');
