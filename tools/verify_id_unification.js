#!/usr/bin/env node
/**
 * 驗證前後端彩券類型ID統一
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('=' .repeat(60));
console.log('🔍 驗證前後端彩券類型ID統一');
console.log('='.repeat(60));
console.log();

// 讀取後端配置
const backendConfigPath = path.join(__dirname, '..', 'lottery-api', 'data', 'lottery_types.json');
const backendConfig = JSON.parse(fs.readFileSync(backendConfigPath, 'utf8'));

// 讀取前端配置
const frontendConfigPath = path.join(__dirname, '..', 'src', 'utils', 'LotteryTypes.js');
const frontendConfigContent = fs.readFileSync(frontendConfigPath, 'utf8');

// 提取前端的ID
const frontendIds = [];
const idMatches = frontendConfigContent.matchAll(/^\s+['"]?([A-Z0-9_]+)['"]?:\s*{/gm);
for (const match of idMatches) {
    const id = match[1];
    if (id !== 'LOTTERY_TYPES') {
        frontendIds.push(id);
    }
}

// 後端ID
const backendIds = Object.keys(backendConfig);

console.log('📋 後端配置的ID:');
backendIds.forEach(id => {
    console.log(`  - ${id}`);
});
console.log();

console.log('📋 前端配置的ID:');
frontendIds.forEach(id => {
    console.log(`  - ${id}`);
});
console.log();

// 驗證一致性
console.log('🔍 檢查ID一致性:');
console.log();

let allMatch = true;

// 檢查前端ID是否都在後端
const frontendOnlyIds = frontendIds.filter(id => !backendIds.includes(id));
if (frontendOnlyIds.length > 0) {
    allMatch = false;
    console.log('❌ 僅在前端的ID (需要添加到後端):');
    frontendOnlyIds.forEach(id => console.log(`  - ${id}`));
    console.log();
}

// 檢查後端ID是否都在前端
const backendOnlyIds = backendIds.filter(id => !frontendIds.includes(id));
if (backendOnlyIds.length > 0) {
    allMatch = false;
    console.log('❌ 僅在後端的ID (需要添加到前端):');
    backendOnlyIds.forEach(id => console.log(`  - ${id}`));
    console.log();
}

// 共同的ID
const commonIds = frontendIds.filter(id => backendIds.includes(id));
if (commonIds.length > 0) {
    console.log('✅ 前後端共同的ID:');
    commonIds.forEach(id => console.log(`  - ${id}`));
    console.log();
}

// 檢查舊ID是否還在使用
console.log('🔍 檢查舊ID是否還在使用:');
const oldIds = [
    'POWER_BALL',
    'DAILY_CASH_539',
    'STAR_3',
    'STAR_4',
    'LOTTO_39',
    'LOTTO_49',
    'LOTTO_38'
];

let foundOldIds = false;
oldIds.forEach(oldId => {
    if (frontendIds.includes(oldId)) {
        foundOldIds = true;
        console.log(`  ❌ 前端仍使用舊ID: ${oldId}`);
    }
    if (backendIds.includes(oldId)) {
        foundOldIds = true;
        console.log(`  ❌ 後端仍使用舊ID: ${oldId}`);
    }
});

if (!foundOldIds) {
    console.log('  ✅ 未發現舊ID');
}
console.log();

// 總結
console.log('=' .repeat(60));
if (allMatch && !foundOldIds) {
    console.log('✅ 驗證通過！前後端ID完全統一');
} else {
    console.log('⚠️  驗證未通過，請檢查上述問題');
}
console.log('='.repeat(60));
console.log();

// 統計
console.log('📊 統計:');
console.log(`  前端ID數量: ${frontendIds.length}`);
console.log(`  後端ID數量: ${backendIds.length}`);
console.log(`  共同ID數量: ${commonIds.length}`);
console.log();

process.exit(allMatch && !foundOldIds ? 0 : 1);
