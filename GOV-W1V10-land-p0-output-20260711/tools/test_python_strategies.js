#!/usr/bin/env node

/**
 * Python 後端策略對比測試
 * 測試所有從 JavaScript 遷移到 Python 的預測策略
 */

const API_BASE = 'http://localhost:5001/api';

const colors = {
    reset: '\x1b[0m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    red: '\x1b[31m',
    cyan: '\x1b[36m',
    magenta: '\x1b[35m'
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
        date.setDate(date.getDate() + i * 3);

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

// 獲取所有可用策略
async function getAvailableStrategies() {
    try {
        const response = await fetch(`${API_BASE}/models`);
        const data = await response.json();

        return data.models.filter(m => m.status === 'available');
    } catch (error) {
        log(`❌ 獲取策略列表失敗: ${error.message}`, 'red');
        return [];
    }
}

// 測試單個策略
async function testStrategy(strategyId, strategyName, lotteryType = 'BIG_LOTTO') {
    const startTime = Date.now();

    try {
        const response = await fetch(`${API_BASE}/predict-from-backend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                lotteryType: lotteryType,
                modelType: strategyId
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        const duration = Date.now() - startTime;

        return {
            success: true,
            strategyId,
            strategyName,
            numbers: result.numbers,
            confidence: result.confidence,
            duration,
            method: result.method
        };
    } catch (error) {
        const duration = Date.now() - startTime;
        return {
            success: false,
            strategyId,
            strategyName,
            error: error.message,
            duration
        };
    }
}

// 同步數據
async function syncData(history, lotteryRules) {
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
        return { success: true, count: result.data_count };
    } catch (error) {
        return { success: false, error: error.message };
    }
}

// 主測試流程
async function main() {
    log('='.repeat(80), 'cyan');
    log('🧪 Python 後端策略全面測試', 'cyan');
    log('='.repeat(80), 'cyan');

    // 1. 測試連接
    log('\n📡 測試 API 連接...', 'cyan');
    try {
        const response = await fetch(`${API_BASE.replace('/api', '')}/health`);
        const data = await response.json();

        if (data.status !== 'healthy') {
            log('❌ API 狀態異常', 'red');
            process.exit(1);
        }
        log('✅ API 連接成功', 'green');
    } catch (error) {
        log(`❌ 無法連接到 API: ${error.message}`, 'red');
        log('請確認後端服務已啟動: cd lottery-api && python app.py', 'yellow');
        process.exit(1);
    }

    // 2. 生成並同步測試數據
    log('\n📝 生成測試數據...', 'cyan');
    const history = generateTestData(100);
    const lotteryRules = {
        pickCount: 6,
        minNumber: 1,
        maxNumber: 49
    };
    log(`✅ 生成了 ${history.length} 期測試數據`, 'green');

    log('\n📤 同步數據到後端...', 'cyan');
    const syncResult = await syncData(history, lotteryRules);
    if (!syncResult.success) {
        log(`❌ 數據同步失敗: ${syncResult.error}`, 'red');
        process.exit(1);
    }
    log(`✅ 數據同步成功: ${syncResult.count} 期`, 'green');

    // 3. 獲取所有可用策略
    log('\n📋 獲取可用策略...', 'cyan');
    const strategies = await getAvailableStrategies();

    if (strategies.length === 0) {
        log('❌ 沒有可用的策略', 'red');
        process.exit(1);
    }

    log(`✅ 找到 ${strategies.length} 個可用策略`, 'green');

    // 按類別分組
    const byCategory = {};
    strategies.forEach(s => {
        if (!byCategory[s.category]) {
            byCategory[s.category] = [];
        }
        byCategory[s.category].push(s);
    });

    // 4. 測試所有策略
    log('\n🚀 開始測試所有策略...', 'cyan');
    log('='.repeat(80), 'cyan');

    const results = [];

    for (const [category, categoryStrategies] of Object.entries(byCategory)) {
        log(`\n📂 ${category.toUpperCase()} 類別:`, 'magenta');
        log('-'.repeat(80), 'blue');

        for (const strategy of categoryStrategies) {
            log(`\n測試: ${strategy.name} (${strategy.id})`, 'yellow');
            log(`說明: ${strategy.description}`, 'blue');

            const result = await testStrategy(strategy.id, strategy.name);
            results.push(result);

            if (result.success) {
                log(`✅ 成功`, 'green');
                log(`   號碼: ${result.numbers.join(', ')}`, 'blue');
                log(`   信心度: ${(result.confidence * 100).toFixed(1)}%`, 'blue');
                log(`   耗時: ${result.duration}ms`, 'blue');
                log(`   方法: ${result.method}`, 'blue');
            } else {
                log(`❌ 失敗: ${result.error}`, 'red');
                log(`   耗時: ${result.duration}ms`, 'blue');
            }

            // 等待一下再測試下一個
            await new Promise(resolve => setTimeout(resolve, 300));
        }
    }

    // 5. 統計結果
    log('\n' + '='.repeat(80), 'cyan');
    log('📊 測試結果統計', 'cyan');
    log('='.repeat(80), 'cyan');

    const successful = results.filter(r => r.success);
    const failed = results.filter(r => !r.success);

    log(`\n總測試數: ${results.length}`, 'blue');
    log(`成功: ${successful.length} (${(successful.length / results.length * 100).toFixed(1)}%)`, 'green');
    log(`失敗: ${failed.length} (${(failed.length / results.length * 100).toFixed(1)}%)`, failed.length > 0 ? 'red' : 'blue');

    if (successful.length > 0) {
        const avgDuration = successful.reduce((sum, r) => sum + r.duration, 0) / successful.length;
        const avgConfidence = successful.reduce((sum, r) => sum + r.confidence, 0) / successful.length;

        log(`\n平均耗時: ${avgDuration.toFixed(0)}ms`, 'blue');
        log(`平均信心度: ${(avgConfidence * 100).toFixed(1)}%`, 'blue');

        // 找出最快和最慢的策略
        const fastest = successful.reduce((min, r) => r.duration < min.duration ? r : min);
        const slowest = successful.reduce((max, r) => r.duration > max.duration ? r : max);

        log(`\n最快策略: ${fastest.strategyName} (${fastest.duration}ms)`, 'green');
        log(`最慢策略: ${slowest.strategyName} (${slowest.duration}ms)`, 'yellow');

        // 找出信心度最高的策略
        const mostConfident = successful.reduce((max, r) => r.confidence > max.confidence ? r : max);
        log(`\n最高信心度: ${mostConfident.strategyName} (${(mostConfident.confidence * 100).toFixed(1)}%)`, 'green');
    }

    if (failed.length > 0) {
        log('\n❌ 失敗的策略:', 'red');
        failed.forEach(r => {
            log(`   - ${r.strategyName}: ${r.error}`, 'red');
        });
    }

    // 6. 策略對比表格
    if (successful.length > 0) {
        log('\n📋 策略對比表格:', 'cyan');
        log('-'.repeat(80), 'blue');
        log(
            '策略名稱'.padEnd(20) +
            '號碼'.padEnd(30) +
            '信心度'.padEnd(10) +
            '耗時'.padEnd(10),
            'yellow'
        );
        log('-'.repeat(80), 'blue');

        successful.forEach(r => {
            const numbersStr = r.numbers.join(',');
            const confidenceStr = `${(r.confidence * 100).toFixed(1)}%`;
            const durationStr = `${r.duration}ms`;

            log(
                r.strategyName.padEnd(20) +
                numbersStr.padEnd(30) +
                confidenceStr.padEnd(10) +
                durationStr.padEnd(10),
                'blue'
            );
        });
        log('-'.repeat(80), 'blue');
    }

    log('\n' + '='.repeat(80), 'cyan');
    log('✅ 測試完成！', 'green');
    log('='.repeat(80), 'cyan');

    log('\n💡 建議:', 'cyan');
    log('1. 所有策略現在都在 Python 後端運行，利用強大的數據科學庫', 'blue');
    log('2. 可以使用 ensemble 策略結合多種方法，提高準確率', 'blue');
    log('3. random_forest 策略使用機器學習，適合大量歷史數據', 'blue');
    log('4. 所有結果都會被緩存，重複預測速度極快', 'blue');
}

// 執行測試
main().catch(error => {
    log(`\n❌ 測試過程發生錯誤: ${error.message}`, 'red');
    console.error(error);
    process.exit(1);
});
