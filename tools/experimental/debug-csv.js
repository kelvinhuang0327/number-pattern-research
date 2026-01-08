/**
 * 除錯 CSV 解析問題
 */

import fs from 'fs';
import path from 'path';

const csvDir = '/Users/kelvin/Downloads/獎號/2025';

// 需要檢查的檔案
const files = [
    '大樂透_2025.csv',
    '威力彩_2025.csv',
    '今彩539_2025.csv',
    '49樂合彩_2025.csv',
    '39樂合彩_2025.csv',
    '4星彩_2025.csv'
];

console.log('=== CSV 檔案前 5 行分析 ===\n');

files.forEach(filename => {
    const filepath = path.join(csvDir, filename);
    
    if (!fs.existsSync(filepath)) {
        console.log(`❌ ${filename}: 檔案不存在\n`);
        return;
    }
    
    try {
        const content = fs.readFileSync(filepath, 'utf-8');
        const lines = content.split(/\r?\n/).filter(l => l.trim());
        
        console.log(`📄 ${filename}`);
        console.log(`   總行數: ${lines.length}`);
        console.log(`   前 5 行:`);
        
        lines.slice(0, 5).forEach((line, idx) => {
            const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
            console.log(`   ${idx}: [${parts.slice(0, 3).join(' | ')}]`);
            if (idx === 0) {
                console.log(`      → 欄位數: ${parts.length}, 第一欄: "${parts[0]}"`);
            } else if (idx === 1) {
                console.log(`      → 遊戲名稱: "${parts[0]}"`);
            }
        });
        console.log('');
        
    } catch (error) {
        console.log(`❌ ${filename}: 讀取錯誤 - ${error.message}\n`);
    }
});

// 同時檢查能正常解析的檔案
console.log('\n=== 對照：能正常解析的檔案 ===\n');

const workingFiles = [
    '大樂透加開獎項_2025.csv',
    '3星彩_2025.csv',
    '賓果賓果_2025.csv'
];

workingFiles.forEach(filename => {
    const filepath = path.join(csvDir, filename);
    
    if (!fs.existsSync(filepath)) {
        console.log(`❌ ${filename}: 檔案不存在\n`);
        return;
    }
    
    try {
        const content = fs.readFileSync(filepath, 'utf-8');
        const lines = content.split(/\r?\n/).filter(l => l.trim());
        
        console.log(`📄 ${filename}`);
        console.log(`   總行數: ${lines.length}`);
        
        const header = lines[0].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
        const firstData = lines[1] ? lines[1].split(',').map(p => p.trim().replace(/^"|"$/g, '')) : [];
        
        console.log(`   標題欄: "${header[0]}"`);
        console.log(`   遊戲名稱: "${firstData[0]}"`);
        console.log('');
        
    } catch (error) {
        console.log(`❌ ${filename}: 讀取錯誤 - ${error.message}\n`);
    }
});
