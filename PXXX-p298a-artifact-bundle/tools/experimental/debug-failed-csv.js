/**
 * 調試批次載入問題
 */

import fs from 'fs';
import { detectLotteryType } from './src/utils/LotteryTypes.js';

const csvDir = '/Users/kelvin/Downloads/獎號/2025';

const failedFiles = [
    '49樂合彩_2025.csv',
    '39樂合彩_2025.csv',
    '4星彩_2025.csv',
    '大樂透_2025.csv',
    '今彩539_2025.csv',
    '威力彩_2025.csv'
];

console.log('=== 調試失敗的 CSV 檔案 ===\n');

failedFiles.forEach(filename => {
    const filepath = `${csvDir}/${filename}`;
    
    if (!fs.existsSync(filepath)) {
        console.log(`❌ ${filename}: 檔案不存在\n`);
        return;
    }
    
    try {
        const content = fs.readFileSync(filepath, 'utf-8');
        const lines = content.split(/\r?\n/).filter(l => l.trim());
        
        console.log(`📄 ${filename}`);
        console.log(`   總行數: ${lines.length}`);
        
        if (lines.length < 2) {
            console.log(`   ⚠️ 檔案內容不足 (沒有數據)\n`);
            return;
        }
        
        // 檢查標題行
        const header = lines[0];
        const hasGameName = header.includes('遊戲名稱');
        console.log(`   標題行有遊戲名稱: ${hasGameName ? '是' : '否'}`);
        
        // 檢查第一筆數據
        const firstData = lines[1].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
        const gameName = firstData[0];
        const lotteryType = detectLotteryType(gameName);
        
        console.log(`   遊戲名稱: "${gameName}"`);
        console.log(`   偵測類型: ${lotteryType ? lotteryType.id : 'null'}`);
        
        if (!lotteryType) {
            console.log(`   ❌ 無法識別彩券類型！\n`);
            return;
        }
        
        console.log(`   pickCount: ${lotteryType.pickCount}`);
        console.log(`   hasSpecialNumber: ${lotteryType.hasSpecialNumber}`);
        console.log(`   欄位數: ${firstData.length}`);
        
        // 模擬欄位檢查
        const minFields = 6 + lotteryType.pickCount;
        const fieldCheck = firstData.length >= minFields;
        console.log(`   欄位檢查 (>= ${minFields}): ${fieldCheck ? '✓ 通過' : '✗ 失敗'}`);
        
        // 檢查號碼欄位
        const numberStartIndex = 6;
        const numbers = firstData.slice(numberStartIndex, numberStartIndex + lotteryType.pickCount)
            .map(n => parseInt(n));
        
        console.log(`   號碼: [${numbers.join(', ')}]`);
        console.log(`   號碼有效: ${numbers.every(n => !isNaN(n)) ? '✓' : '✗'}`);
        
        // 檢查特別號
        if (lotteryType.hasSpecialNumber && firstData.length > numberStartIndex + lotteryType.pickCount) {
            const special = parseInt(firstData[numberStartIndex + lotteryType.pickCount]);
            console.log(`   特別號: ${special}`);
            console.log(`   特別號有效: ${!isNaN(special) ? '✓' : '✗'}`);
        } else if (lotteryType.hasSpecialNumber) {
            console.log(`   ⚠️ 應該要有特別號，但欄位數不足`);
        }
        
        // 檢查多行數據
        let validCount = 0;
        let invalidCount = 0;
        
        for (let i = 1; i < Math.min(lines.length, 10); i++) {
            const parts = lines[i].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
            const lineGameName = parts[0];
            const lineType = detectLotteryType(lineGameName);
            
            if (!lineType) {
                invalidCount++;
                console.log(`   Line ${i}: 無法識別 "${lineGameName}"`);
                continue;
            }
            
            const lineMinFields = 6 + lineType.pickCount;
            if (parts.length < lineMinFields) {
                invalidCount++;
                console.log(`   Line ${i}: 欄位不足 (需要 ${lineMinFields}, 實際 ${parts.length})`);
                continue;
            }
            
            validCount++;
        }
        
        console.log(`   前 10 行驗證: ${validCount} 通過, ${invalidCount} 失敗`);
        console.log('');
        
    } catch (error) {
        console.log(`   ❌ 錯誤: ${error.message}\n`);
    }
});
