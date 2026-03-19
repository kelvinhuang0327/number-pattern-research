#!/usr/bin/env node

/**
 * 測試後端數據同步和優化預測功能
 * 
 * 測試內容：
 * 1. 數據同步到後端
 * 2. 傳統模式預測（傳送完整數據）
 * 3. 優化模式預測（使用後端數據）
 * 4. 性能對比
 */

const API_BASE = 'http://localhost:5001/api';

// 顏色輸出
const colors = {
    reset: '\x1b[0m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    red: '\x1b[31m',
    cyan: '\x1b[36m'
};

function log(message, color = 'reset') {
    console.log(`${colors[color]}${message}${colors.reset}`);
}

// 生成測試數據
function generateTestData(count = 100) {
    const data = [];
    const startDate = new Date('2024-01-01');

    for (let i = 0; i < count; i++) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i * 3); // 每3天一期

        // 生成隨機號碼（大樂透：1-49選6個）
        const numbers = [];
        while (numbers.length < 6) {
            const num = Math.floor(Math.random() * 49) + 1;
            if (!numbers.includes(num)) {
                numbers.push(num);
            }
        }
        numbers.sort((a, b) => a - b);

        data.push({
            date: date.toISOString().split('T')[0],
            draw: String(i + 1),
            numbers: numbers,
            lotteryType: 'BIG_LOTTO'
        });
    }

    return data;
}

// 測試 API 連接
async function testConnection() {
    log('\n📡 測試 API 連接...', 'cyan');

    try {
        const response = await fetch(`${API_BASE.replace('/api', '')}/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            log('✅ API 連接成功', 'green');
            return true;
        } else {
            log('❌ API 狀態異常', 'red');
            return false;
        }
    } catch (error) {
        log(`❌ 無法連接到 API: ${error.message}`, 'red');
        log('請確認後端服務已啟動: cd lottery-api && python app.py', 'yellow');
        return false;
    }
}

// 1. 同步數據到後端
async function syncData(history, lotteryRules) {
    log('\n📤 同步數據到後端...', 'cyan');
    const startTime = Date.now();

    try {
        const response = await fetch(`${API_BASE}/auto-learning/sync-data`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                history: history,
                lotteryRules: lotteryRules
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        const duration = Date.now() - startTime;

        log(`✅ 數據同步成功: ${result.data_count} 期`, 'green');
        log(`⏱️  耗時: ${duration}ms`, 'blue');

        return { success: true, duration };
    } catch (error) {
        log(`❌ 數據同步失敗: ${error.message}`, 'red');
        return { success: false, error: error.message };
    }
}

// 2. 傳統模式預測（傳送完整數據）
async function predictTraditional(history, lotteryRules) {
    log('\n📦 傳統模式預測（傳送完整數據）...', 'cyan');
    const startTime = Date.now();

    try {
        const response = await fetch(`${API_BASE}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                history: history,
                lotteryRules: lotteryRules,
                modelType: 'prophet'
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        const duration = Date.now() - startTime;

        log(`✅ 預測成功: ${result.numbers.join(', ')}`, 'green');
        log(`📊 信心度: ${(result.confidence * 100).toFixed(1)}%`, 'blue');
        log(`⏱️  耗時: ${duration}ms`, 'blue');

        return { success: true, duration, result };
    } catch (error) {
        log(`❌ 預測失敗: ${error.message}`, 'red');
        return { success: false, error: error.message };
    }
}

// 3. 優化模式預測（使用後端數據）
async function predictOptimized(lotteryType = 'BIG_LOTTO') {
    log('\n🚀 優化模式預測（使用後端數據）...', 'cyan');
    const startTime = Date.now();

    try {
        const response = await fetch(`${API_BASE}/predict-from-backend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lotteryType: lotteryType,
                modelType: 'prophet'
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        const duration = Date.now() - startTime;

        log(`✅ 預測成功: ${result.numbers.join(', ')}`, 'green');
        log(`📊 信心度: ${(result.confidence * 100).toFixed(1)}%`, 'blue');
        log(`⏱️  耗時: ${duration}ms`, 'blue');

        return { success: true, duration, result };
    } catch (error) {
        log(`❌ 預測失敗: ${error.message}`, 'red');
        return { success: false, error: error.message };
    }
}

// 4. 測試緩存效果（連續預測）
async function testCache(rounds = 3) {
    log('\n💾 測試模型緩存效果...', 'cyan');
    const durations = [];

    for (let i = 0; i < rounds; i++) {
        log(`\n第 ${i + 1} 次預測:`, 'yellow');
        const result = await predictOptimized('BIG_LOTTO');

        if (result.success) {
            durations.push(result.duration);
        }

        // 等待一下再進行下一次預測
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    if (durations.length > 0) {
        log('\n📊 緩存效果分析:', 'cyan');
        log(`首次預測: ${durations[0]}ms`, 'blue');
        if (durations.length > 1) {
            const avgCached = durations.slice(1).reduce((a, b) => a + b, 0) / (durations.length - 1);
            log(`緩存預測平均: ${avgCached.toFixed(0)}ms`, 'blue');
            log(`速度提升: ${((durations[0] - avgCached) / durations[0] * 100).toFixed(1)}%`, 'green');
        }
    }
}

// 5. 查看緩存統計
async function getCacheStats() {
    log('\n📊 查看緩存統計...', 'cyan');

    try {
        const response = await fetch(`${API_BASE}/cache/stats`);
        const stats = await response.json();

        log(`緩存模型數量: ${stats.total_cached}`, 'blue');
        log(`緩存有效期: ${stats.cache_ttl_hours} 小時`, 'blue');

        if (stats.cached_models.length > 0) {
            log('已緩存模型:', 'blue');
            stats.cached_models.forEach(model => {
                log(`  - ${model}`, 'blue');
            });
        }

        return stats;
    } catch (error) {
        log(`❌ 獲取緩存統計失敗: ${error.message}`, 'red');
    }
}

// 主測試流程
async function main() {
    log('='.repeat(60), 'cyan');
    log('🧪 後端數據同步與優化預測測試', 'cyan');
    log('='.repeat(60), 'cyan');

    // 1. 測試連接
    const connected = await testConnection();
    if (!connected) {
        process.exit(1);
    }

    // 2. 生成測試數據
    log('\n📝 生成測試數據...', 'cyan');
    const history = generateTestData(100);
    const lotteryRules = {
        pickCount: 6,
        minNumber: 1,
        maxNumber: 49
    };
    log(`✅ 生成了 ${history.length} 期測試數據`, 'green');

    // 3. 同步數據
    const syncResult = await syncData(history, lotteryRules);
    if (!syncResult.success) {
        log('❌ 數據同步失敗，無法繼續測試', 'red');
        process.exit(1);
    }

    // 4. 傳統模式預測
    const traditionalResult = await predictTraditional(history, lotteryRules);

    // 5. 優化模式預測
    const optimizedResult = await predictOptimized('BIG_LOTTO');

    // 6. 性能對比
    if (traditionalResult.success && optimizedResult.success) {
        log('\n📊 性能對比:', 'cyan');
        log('='.repeat(60), 'cyan');

        const improvement = ((traditionalResult.duration - optimizedResult.duration) / traditionalResult.duration * 100);

        log(`傳統模式: ${traditionalResult.duration}ms`, 'blue');
        log(`優化模式: ${optimizedResult.duration}ms`, 'blue');
        log(`速度提升: ${improvement.toFixed(1)}%`, improvement > 0 ? 'green' : 'yellow');

        const dataSize = JSON.stringify({ history, lotteryRules }).length;
        const optimizedSize = JSON.stringify({ lotteryType: 'BIG_LOTTO', modelType: 'prophet' }).length;
        const sizeReduction = ((dataSize - optimizedSize) / dataSize * 100);

        log(`\n數據傳輸量:`, 'cyan');
        log(`傳統模式: ${(dataSize / 1024).toFixed(2)} KB`, 'blue');
        log(`優化模式: ${optimizedSize} B`, 'blue');
        log(`減少: ${sizeReduction.toFixed(1)}%`, 'green');
    }

    // 7. 測試緩存效果
    await testCache(3);

    // 8. 查看緩存統計
    await getCacheStats();

    log('\n' + '='.repeat(60), 'cyan');
    log('✅ 測試完成！', 'green');
    log('='.repeat(60), 'cyan');
}

// 執行測試
main().catch(error => {
    log(`\n❌ 測試過程發生錯誤: ${error.message}`, 'red');
    console.error(error);
    process.exit(1);
});
