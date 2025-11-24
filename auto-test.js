// 自动化测试和优化脚本
// 测试所有配置并找出最佳方案

const fs = require('fs');
const path = require('path');

// 配置定义
const CONFIGS = {
    config1: { // 強化型
        name: '強化型',
        oddEven: { perfect: 130, good: 35 },
        sum: { best: 180, ok: 90 },
        hotCold: { perfect: 80, good: 50 },
        zones: { zone5: 120, zone4: 80, zone3: 50 },
        consecutive: { none: 70, one: 25 },
        modelWeight: 12,
        tailDiversity: { six: 60, four: 30 }
    },
    config2: { // 平衡型
        name: '平衡型',
        oddEven: { perfect: 120, good: 40 },
        sum: { best: 160, ok: 95 },
        hotCold: { perfect: 100, good: 60 },
        zones: { zone5: 100, zone4: 70, zone3: 45 },
        consecutive: { none: 65, one: 30 },
        modelWeight: 13,
        tailDiversity: { six: 50, four: 25 }
    },
    config3: { // 激進型
        name: '激進型',
        oddEven: { perfect: 150, good: 30 },
        sum: { best: 200, ok: 80 },
        hotCold: { perfect: 120, good: 40 },
        zones: { zone5: 150, zone4: 90, zone3: 40 },
        consecutive: { none: 80, one: 20 },
        modelWeight: 15,
        tailDiversity: { six: 80, four: 35 }
    },
    config4: { // 保守型
        name: '保守型',
        oddEven: { perfect: 110, good: 45 },
        sum: { best: 140, ok: 100 },
        hotCold: { perfect: 90, good: 55 },
        zones: { zone5: 110, zone4: 75, zone3: 50 },
        consecutive: { none: 60, one: 28 },
        modelWeight: 11,
        tailDiversity: { six: 55, four: 28 }
    },
    config5: { // 區間優先
        name: '區間優先',
        oddEven: { perfect: 115, good: 38 },
        sum: { best: 155, ok: 92 },
        hotCold: { perfect: 85, good: 52 },
        zones: { zone5: 140, zone4: 95, zone3: 55 },
        consecutive: { none: 68, one: 27 },
        modelWeight: 12,
        tailDiversity: { six: 58, four: 30 }
    }
};

// 生成模拟数据
function generateSampleData(count = 100) {
    const data = [];
    const startDate = new Date('2024-01-01');

    for (let i = 0; i < count; i++) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i * 3);

        // 生成6个不重复的号码 (1-49)
        const numbers = [];
        while (numbers.length < 6) {
            const num = Math.floor(Math.random() * 49) + 1;
            if (!numbers.includes(num)) {
                numbers.push(num);
            }
        }
        numbers.sort((a, b) => a - b);

        data.push({
            drawNumber: count - i,
            date: date.toISOString().split('T')[0],
            numbers: numbers
        });
    }

    return data.reverse(); // 最新的在前
}

// 模拟组合评分
function scoreCombination(combo, weights, hotNumbers, coldNumbers) {
    let score = 0;

    // 1. 奇偶平衡
    const oddCount = combo.filter(n => n % 2 === 1).length;
    if (oddCount === 3) {
        score += weights.oddEven.perfect;
    } else if (oddCount === 2 || oddCount === 4) {
        score += weights.oddEven.good;
    }

    // 2. 数字总和
    const sum = combo.reduce((a, b) => a + b, 0);
    if (sum >= 140 && sum <= 160) {
        score += weights.sum.best;
    } else if (sum >= 120 && sum <= 180) {
        score += weights.sum.ok;
    }

    // 3. 冷热平衡
    const hotInCombo = combo.filter(n => hotNumbers.includes(n)).length;
    const coldInCombo = combo.filter(n => coldNumbers.includes(n)).length;
    if (hotInCombo === 3 && coldInCombo === 2) {
        score += weights.hotCold.perfect;
    } else if (hotInCombo >= 2 && hotInCombo <= 4 && coldInCombo >= 1 && coldInCombo <= 3) {
        score += weights.hotCold.good || (weights.hotCold.perfect * 0.7);
    }

    // 4. 区间分布
    const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
    if (zones.size === 5) {
        score += weights.zones.zone5;
    } else if (zones.size === 4) {
        score += weights.zones.zone4;
    } else if (zones.size === 3) {
        score += weights.zones.zone3;
    }

    // 5. 避免连号
    const sorted = [...combo].sort((a, b) => a - b);
    let consecutiveCount = 0;
    for (let i = 0; i < sorted.length - 1; i++) {
        if (sorted[i + 1] === sorted[i] + 1) {
            consecutiveCount++;
        }
    }
    if (consecutiveCount === 0) {
        score += weights.consecutive.none;
    } else if (consecutiveCount === 1) {
        score += weights.consecutive.one;
    }

    // 6. 尾数分布
    if (weights.tailDiversity) {
        const tails = combo.map(n => n % 10);
        const uniqueTails = new Set(tails);
        if (uniqueTails.size === 6) {
            score += weights.tailDiversity.six;
        } else if (uniqueTails.size >= 4) {
            score += weights.tailDiversity.four;
        }
    }

    return score;
}

// 生成组合
function generateCombinations(arr, size) {
    if (size === 1) return arr.map(el => [el]);
    const result = [];
    arr.forEach((el, i) => {
        const smaller = generateCombinations(arr.slice(i + 1), size - 1);
        smaller.forEach(combo => result.push([el, ...combo]));
    });
    return result;
}

// 运行单个配置的模拟测试
function runSimulation(configName, weights, sampleData) {
    console.log(`\n🧪 测试 ${configName}...`);

    let totalTests = 0;
    let successfulPredictions = 0;

    // 模拟预测最近10期
    for (let i = 30; i < 40 && i < sampleData.length; i++) {
        const trainingData = sampleData.slice(0, i);
        const actualDraw = sampleData[i];

        // 计算冷热号
        const recentDraws = trainingData.slice(0, 30);
        const frequency = {};
        for (let n = 1; n <= 49; n++) frequency[n] = 0;

        recentDraws.forEach(draw => {
            draw.numbers.forEach(num => frequency[num]++);
        });

        const avgFreq = Object.values(frequency).reduce((a, b) => a + b, 0) / 49;
        const hotNumbers = [];
        const coldNumbers = [];

        for (let n = 1; n <= 49; n++) {
            if (frequency[n] > avgFreq * 1.2) {
                hotNumbers.push(n);
            } else if (frequency[n] < avgFreq * 0.8) {
                coldNumbers.push(n);
            }
        }

        // 简化：从所有号码中随机选30个作为候选
        const candidates = [];
        const allNumbers = Array.from({ length: 49 }, (_, i) => i + 1);
        for (let j = 0; j < 30 && allNumbers.length > 0; j++) {
            const idx = Math.floor(Math.random() * allNumbers.length);
            candidates.push(allNumbers[idx]);
            allNumbers.splice(idx, 1);
        }

        // 生成组合并评分（限制数量以提高速度）
        const combinations = generateCombinations(candidates.slice(0, 12), 6);
        const scored = combinations.map(combo => ({
            numbers: combo,
            score: scoreCombination(combo, weights, hotNumbers, coldNumbers)
        })).sort((a, b) => b.score - a.score);

        const prediction = scored[0].numbers;

        // 检查命中数
        const hits = prediction.filter(n => actualDraw.numbers.includes(n)).length;

        totalTests++;
        if (hits >= 3) { // 至少命中3个算成功
            successfulPredictions++;
        }
    }

    const successRate = (successfulPredictions / totalTests * 100).toFixed(2);
    console.log(`   成功: ${successfulPredictions}/${totalTests}, 成功率: ${successRate}%`);

    return {
        config: configName,
        successRate: parseFloat(successRate),
        successful: successfulPredictions,
        total: totalTests
    };
}

// 主函数
async function main() {
    console.log('🚀 启动自动化测试系统...\n');
    console.log('生成测试数据...');

    const sampleData = generateSampleData(100);
    console.log(`✅ 已生成 ${sampleData.length} 期数据\n`);

    const results = [];

    // 测试所有配置
    for (const [key, config] of Object.entries(CONFIGS)) {
        const result = runSimulation(config.name, config, sampleData);
        results.push(result);
    }

    // 排序并显示结果
    results.sort((a, b) => b.successRate - a.successRate);

    console.log('\n' + '='.repeat(60));
    console.log('📊 测试结果汇总');
    console.log('='.repeat(60));

    results.forEach((r, index) => {
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '  ';
        console.log(`${medal} ${r.config.padEnd(10)} - ${r.successRate}% (${r.successful}/${r.total})`);
    });

    const best = results[0];
    console.log('\n' + '='.repeat(60));
    console.log(`🏆 最佳配置: ${best.config} (${best.successRate}%)`);
    console.log('='.repeat(60));

    // 保存结果
    const reportPath = path.join(__dirname, 'test-results.json');
    fs.writeFileSync(reportPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        results: results,
        bestConfig: best.config
    }, null, 2));

    console.log(`\n✅ 结果已保存到: ${reportPath}`);

    if (best.successRate < 20) {
        console.log(`\n⚠️  注意: 最佳成功率 ${best.successRate}% 低于目标 20%`);
        console.log('💡 建议: 彩票本质上是随机的，15-20%已经是很好的结果');
    } else {
        console.log(`\n🎉 恭喜! 达到目标成功率 ${best.successRate}% >= 20%`);
    }
}

// 运行
main().catch(console.error);
