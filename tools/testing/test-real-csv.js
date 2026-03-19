/**
 * 測試實際 CSV 解析
 */

import { DataProcessor } from './src/core/DataProcessor.js';
import fs from 'fs';

const processor = new DataProcessor();

const testFiles = [
    { path: '/Users/kelvin/Downloads/獎號/2025/大樂透_2025.csv', name: '大樂透' },
    { path: '/Users/kelvin/Downloads/獎號/2025/威力彩_2025.csv', name: '威力彩' },
    { path: '/Users/kelvin/Downloads/獎號/2025/今彩539_2025.csv', name: '今彩539' },
    { path: '/Users/kelvin/Downloads/獎號/2025/4星彩_2025.csv', name: '四星彩' },
];

console.log('=== 測試 CSV 解析 ===\n');

for (const { path, name } of testFiles) {
    console.log(`\n📄 測試: ${name}`);
    
    if (!fs.existsSync(path)) {
        console.log('  ❌ 檔案不存在');
        continue;
    }
    
    try {
        // 讀取檔案內容分析
        const content = fs.readFileSync(path, 'utf-8');
        const lines = content.split(/\r?\n/).filter(l => l.trim());
        
        console.log(`  總行數: ${lines.length}`);
        
        // 分析第一筆數據
        const parts = lines[1].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
        console.log(`  第一筆資料欄位數: ${parts.length}`);
        console.log(`  遊戲名稱: "${parts[0]}"`);
        console.log(`  期別: ${parts[1]}`);
        console.log(`  日期: ${parts[2]}`);
        
        // 模擬 File 物件
        const blob = new Blob([content], { type: 'text/csv' });
        const file = new File([blob], path.split('/').pop(), { type: 'text/csv' });
        
        // 嘗試解析
        console.log('  開始解析...');
        const data = await processor.parseCSV(file);
        
        console.log(`  ✓ 解析成功: ${data.length} 筆`);
        
        if (data.length > 0) {
            const first = data[0];
            console.log(`  第一筆: 期數=${first.draw}, 類型=${first.lotteryType}, 號碼=[${first.numbers.join(',')}], 特別號=${first.special}`);
        }
        
    } catch (error) {
        console.log(`  ✗ 解析失敗: ${error.message}`);
        console.error(error.stack);
    }
}
