import fs from 'fs';

console.log('========================================');
console.log('  測試 CSV 欄位位置分析');
console.log('========================================\n');

const filePath = './大樂透加開獎項_2025.csv';
const text = fs.readFileSync(filePath, 'utf8');
const lines = text.split(/\r?\n/).filter(line => line.trim());

console.log(`總行數: ${lines.length}\n`);

// 分析表頭
console.log('=== 表頭欄位分析 ===');
const header = lines[0].replace(/^\ufeff/, '').split(','); // 移除 BOM
header.forEach((col, index) => {
    console.log(`欄位 ${index}: ${col}`);
});

console.log('\n=== 前 5 筆數據分析 ===');
for (let i = 1; i <= Math.min(5, lines.length - 1); i++) {
    const parts = lines[i].split(',').map(p => p.trim());
    console.log(`\n第 ${i} 筆:`);
    console.log(`  欄位總數: ${parts.length}`);
    parts.forEach((part, index) => {
        console.log(`  [${index}] ${part}`);
    });
}

console.log('\n=== 分析結論 ===');
console.log('根據表頭和數據:');
console.log('  欄位 0: 遊戲名稱');
console.log('  欄位 1: 期別');
console.log('  欄位 2: 開獎日期');
console.log('  欄位 3: 銷售總額');
console.log('  欄位 4: 銷售注數');
console.log('  欄位 5: 總獎金');
console.log('  欄位 6-11: 獎號1-6 (共 6 個號碼)');

if (header.length > 12) {
    console.log(`  欄位 12: ${header[12]} (可能是特別號)`);
} else {
    console.log('  ❌ 沒有第 13 個欄位（特別號）');
}

console.log('\n當前 DataProcessor 設定:');
console.log('  numberStartIndex = 6');
console.log('  取號碼範圍: parts[6] 到 parts[11] (6個號碼)');
console.log('  特別號位置: parts[12]');
console.log('');
