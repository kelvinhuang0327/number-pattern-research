/**
 * 檢查CSV文件中的重複數據
 */

import fs from 'fs';
import path from 'path';

function parseCSVLine(line, header) {
    const parts = line.split(',').map(p => p.trim());
    if (parts.length < 7) return null;

    return {
        gameName: parts[0],
        draw: parts[1],
        date: parts[2],
        numbers: parts.slice(6, 12).map(n => parseInt(n)),
        special: parts.length > 12 ? parseInt(parts[12]) : 0
    };
}

function checkFile(filePath) {
    console.log(`\n📄 檢查文件: ${path.basename(filePath)}`);
    console.log('='.repeat(60));

    if (!fs.existsSync(filePath)) {
        console.log('❌ 文件不存在');
        return { total: 0, duplicates: 0, unique: 0 };
    }

    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split(/\r?\n/).filter(line => line.trim());

    console.log(`總行數: ${lines.length} (含表頭)`);

    if (lines.length <= 1) {
        console.log('⚠️ 文件為空或只有表頭');
        return { total: 0, duplicates: 0, unique: 0 };
    }

    // 跳過表頭
    const dataLines = lines.slice(1);

    // 檢查重複（基於期別）
    const drawMap = new Map();
    const duplicateDraws = [];

    dataLines.forEach((line, index) => {
        const data = parseCSVLine(line);
        if (!data) return;

        const key = `${data.gameName}_${data.draw}`;

        if (drawMap.has(key)) {
            const firstOccurrence = drawMap.get(key);
            duplicateDraws.push({
                draw: data.draw,
                firstLine: firstOccurrence.lineNum,
                duplicateLine: index + 2, // +2 因為跳過表頭且從1開始計數
                numbers: data.numbers.join(','),
                firstNumbers: firstOccurrence.numbers.join(',')
            });
        } else {
            drawMap.set(key, {
                lineNum: index + 2,
                numbers: data.numbers
            });
        }
    });

    const uniqueCount = drawMap.size;
    const duplicateCount = duplicateDraws.length;

    console.log(`\n統計結果:`);
    console.log(`  總數據筆數: ${dataLines.length}`);
    console.log(`  唯一期數: ${uniqueCount}`);
    console.log(`  重複筆數: ${duplicateCount}`);

    if (duplicateCount > 0) {
        console.log(`\n⚠️ 發現 ${duplicateCount} 筆重複數據:`);
        duplicateDraws.slice(0, 10).forEach((dup, index) => {
            console.log(`  ${index + 1}. 期數 ${dup.draw}:`);
            console.log(`     首次出現: 第 ${dup.firstLine} 行 [${dup.firstNumbers}]`);
            console.log(`     重複出現: 第 ${dup.duplicateLine} 行 [${dup.numbers}]`);
        });

        if (duplicateCount > 10) {
            console.log(`  ... 還有 ${duplicateCount - 10} 筆重複數據`);
        }
    } else {
        console.log(`✓ 沒有重複數據`);
    }

    return {
        total: dataLines.length,
        unique: uniqueCount,
        duplicates: duplicateCount
    };
}

console.log('========================================');
console.log('      CSV 重複數據檢查工具');
console.log('========================================');

// 檢查項目根目錄的CSV文件
const files = [
    './大樂透加開獎項_2025.csv',
    './tests/大樂透加開獎項_2025.csv'
];

const results = [];

files.forEach(file => {
    const result = checkFile(file);
    if (result.total > 0) {
        results.push({
            file: path.basename(file),
            ...result
        });
    }
});

// 總結
console.log('\n');
console.log('========================================');
console.log('              總結報告');
console.log('========================================');

if (results.length === 0) {
    console.log('沒有找到任何CSV文件');
} else {
    results.forEach(r => {
        console.log(`\n${r.file}:`);
        console.log(`  總筆數: ${r.total}`);
        console.log(`  唯一: ${r.unique}`);
        console.log(`  重複: ${r.duplicates}`);
        if (r.duplicates > 0) {
            console.log(`  重複率: ${(r.duplicates / r.total * 100).toFixed(2)}%`);
        }
    });

    const totalDuplicates = results.reduce((sum, r) => sum + r.duplicates, 0);
    const totalRecords = results.reduce((sum, r) => sum + r.total, 0);

    console.log(`\n總計:`);
    console.log(`  檢查文件: ${results.length} 個`);
    console.log(`  總數據: ${totalRecords} 筆`);
    console.log(`  重複數據: ${totalDuplicates} 筆`);

    if (totalDuplicates > 0) {
        console.log(`\n⚠️ 建議: 清理重複數據以提升分析準確度`);
    } else {
        console.log(`\n✓ 所有文件都沒有重複數據！`);
    }
}

console.log('');
