/**
 * 分析 CSV 欄位結構
 */

import fs from 'fs';
import { detectLotteryType } from './src/utils/LotteryTypes.js';

const testFiles = [
    { path: '/Users/kelvin/Downloads/獎號/2025/大樂透_2025.csv', name: '大樂透' },
    { path: '/Users/kelvin/Downloads/獎號/2025/威力彩_2025.csv', name: '威力彩' },
    { path: '/Users/kelvin/Downloads/獎號/2025/今彩539_2025.csv', name: '今彩539' },
    { path: '/Users/kelvin/Downloads/獎號/2025/4星彩_2025.csv', name: '四星彩' },
    { path: '/Users/kelvin/Downloads/獎號/2025/49樂合彩_2025.csv', name: '49樂合彩' },
    { path: '/Users/kelvin/Downloads/獎號/2025/39樂合彩_2025.csv', name: '39樂合彩' },
];

console.log('=== CSV 欄位結構分析 ===\n');

testFiles.forEach(({ path, name }) => {
    if (!fs.existsSync(path)) {
        console.log(`❌ ${name}: 檔案不存在\n`);
        return;
    }
    
    const content = fs.readFileSync(path, 'utf-8');
    const lines = content.split(/\r?\n/).filter(l => l.trim());
    
    if (lines.length < 2) {
        console.log(`❌ ${name}: 檔案內容不足\n`);
        return;
    }
    
    const header = lines[0].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
    const firstData = lines[1].split(',').map(p => p.trim().replace(/^"|"$/g, ''));
    
    const gameName = firstData[0];
    const lotteryType = detectLotteryType(gameName);
    
    console.log(`📄 ${name}`);
    console.log(`  CSV遊戲名稱: "${gameName}"`);
    console.log(`  偵測類型: ${lotteryType ? lotteryType.id : 'null'}`);
    
    if (lotteryType) {
        console.log(`  pickCount: ${lotteryType.pickCount}`);
        console.log(`  hasSpecialNumber: ${lotteryType.hasSpecialNumber}`);
        
        const expectedFields = 6 + lotteryType.pickCount + (lotteryType.hasSpecialNumber ? 1 : 0);
        const actualFields = firstData.length;
        
        console.log(`  預期欄位數: ${expectedFields} (6固定欄位 + ${lotteryType.pickCount}號碼 + ${lotteryType.hasSpecialNumber ? 1 : 0}特別號)`);
        console.log(`  實際欄位數: ${actualFields}`);
        console.log(`  欄位檢查: ${actualFields >= expectedFields ? '✓ 通過' : '✗ 不足'}`);
        
        // 顯示標題欄
        console.log(`  標題欄: [${header.join(', ')}]`);
        
        // 顯示號碼位置
        const numberStartIndex = 6;
        const numbers = firstData.slice(numberStartIndex, numberStartIndex + lotteryType.pickCount);
        console.log(`  號碼欄位 [${numberStartIndex}~${numberStartIndex + lotteryType.pickCount - 1}]: [${numbers.join(', ')}]`);
        
        if (lotteryType.hasSpecialNumber && actualFields > numberStartIndex + lotteryType.pickCount) {
            const special = firstData[numberStartIndex + lotteryType.pickCount];
            console.log(`  特別號欄位 [${numberStartIndex + lotteryType.pickCount}]: ${special}`);
        }
        
        // 檢查舊版驗證邏輯
        const oldCheck = actualFields < 6 + lotteryType.pickCount;
        console.log(`  舊版檢查 (length < 6+pickCount): ${oldCheck ? '✗ 失敗 (會被拒絕)' : '✓ 通過'}`);
    }
    
    console.log('');
});
