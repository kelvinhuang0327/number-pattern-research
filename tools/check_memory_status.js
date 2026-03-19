/**
 * 快速檢查系統記憶體狀態
 * 使用方法：node tools/check_memory_status.js
 */

import { memoryOptimizer } from '../src/utils/MemoryOptimizer.js';

console.log('========================================');
console.log('      系統記憶體狀態檢查');
console.log('========================================\n');

// 檢查記憶體 API 是否可用
console.log('1️⃣  瀏覽器記憶體 API 支援檢查');
if (typeof performance !== 'undefined' && performance.memory) {
    console.log('   ✅ performance.memory API 可用\n');

    const stats = memoryOptimizer.checkMemoryUsage();
    if (stats) {
        console.log('   記憶體使用情況：');
        console.log(`   - 已使用: ${stats.used}`);
        console.log(`   - 總分配: ${stats.total}`);
        console.log(`   - 上限: ${stats.limit}`);
        console.log(`   - 使用率: ${stats.usagePercent}%`);

        if (stats.usagePercent > 80) {
            console.log('\n   ⚠️  警告：記憶體使用率過高！');
        } else if (stats.usagePercent > 60) {
            console.log('\n   ⚡ 提示：記憶體使用率偏高，建議注意');
        } else {
            console.log('\n   ✅ 記憶體使用率正常');
        }
    }
} else {
    console.log('   ⚠️  performance.memory API 不可用');
    console.log('   （這是 Node.js 環境，請在瀏覽器控制台中執行）\n');
}

console.log('\n2️⃣  系統配置檢查');
console.log('   - 最大記憶體數據量: 30,000 筆');
console.log('   - 記憶體警告閾值: 80%');
console.log('   - 監控頻率: 每 10 秒');
console.log('   - 分批處理大小: 1,000 筆/批\n');

console.log('3️⃣  優化建議');
const testSizes = [
    { size: 500, desc: '小數據集' },
    { size: 15000, desc: '中等數據集' },
    { size: 35000, desc: '大數據集' },
    { size: 70000, desc: '超大數據集' }
];

testSizes.forEach(({ size, desc }) => {
    console.log(`\n   ${desc} (${size.toLocaleString()} 筆):`);
    const suggestions = memoryOptimizer.getOptimizationSuggestions(size);

    if (suggestions.length === 0) {
        console.log('   ✅ 無需特別優化');
    } else {
        suggestions.forEach(s => {
            console.log(`   ${s.level === 'critical' ? '🔴' : '🟡'} ${s.message}`);
            s.actions.forEach(action => {
                console.log(`      → ${action}`);
            });
        });
    }
});

console.log('\n========================================');
console.log('           快速解決方案');
console.log('========================================\n');

console.log('如果遇到記憶體問題，請嘗試：\n');
console.log('方案 1️⃣  分批上傳 CSV 文件');
console.log('  • 第一批：大樂透、威力彩、今彩539');
console.log('  • 第二批：3星彩、4星彩、39樂合彩');
console.log('  • 第三批：賓果賓果（單獨處理）\n');

console.log('方案 2️⃣  清除不需要的數據');
console.log('  • 點擊「清除所有數據」按鈕');
console.log('  • 只保留需要分析的彩券類型\n');

console.log('方案 3️⃣  重新整理頁面');
console.log('  • 使用 Cmd+Shift+R (Mac) 或 Ctrl+Shift+R (Windows)');
console.log('  • 清除瀏覽器緩存後重新載入\n');

console.log('方案 4️⃣  調整系統限制（進階）');
console.log('  • 編輯 src/core/DataProcessor.js');
console.log('  • 修改 this.maxDataInMemory = 30000');
console.log('  • 增加至 50000（需要 8GB+ RAM）\n');

console.log('========================================');
console.log('           更多資訊');
console.log('========================================\n');

console.log('📖 詳細優化指南：MEMORY_OPTIMIZATION.md');
console.log('📊 優化總結報告：OPTIMIZATION_SUMMARY.md');
console.log('🧪 測試腳本：tools/test_memory_optimization.js\n');

console.log('========================================\n');
