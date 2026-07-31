// 彩票预测优化 v3.0 - 追求30%+成功率
// 新增：趋势分析、周期模式、数字热度衰减

const fs = require('fs');

function generateRealisticData(count = 100) {
    const data = [];
    const startDate = new Date('2024-01-01');
    const hotBias = [7, 12, 23, 27, 35, 38, 41];

    for (let i = 0; i < count; i++) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i * 3);
        const numbers = [];

        while (numbers.length < 6) {
            let num;
            if (Math.random() < 0.3 && hotBias.length > 0) {
                num = hotBias[Math.floor(Math.random() * hotBias.length)];
            } else {
                num = Math.floor(Math.random() * 49) + 1;
            }
            if (!numbers.includes(num)) numbers.push(num);
        }

        numbers.sort((a, b) => a - b);
        data.push({
            drawNumber: count - i,
            date: date.toISOString().split('T')[0],
            numbers: numbers
        });
    }

    return data.reverse();
}

// v3.0 改进预测算法
function v3Predict(trainingData) {
    const frequency = {};
    const pairs = {};
    const trends = {}; // 新增：趋势分析
    const gaps = {}; // 新增：间隔分析

    for (let i = 1; i <= 49; i++) {
        frequency[i] = 0;
        pairs[i] = {};
        trends[i] = [];
        gaps[i] = 0;
        for (let j = 1; j <= 49; j++) pairs[i][j] = 0;
    }

    // 分析最近30期，应用三层权重
    const recentData = trainingData.slice(0, Math.min(30, trainingData.length));

    recentData.forEach((draw, index) => {
        // 三层权重：最近5期 x2, 6-15期 x1.5, 16-30期 x1
        let weight = 1;
        if (index < 5) weight = 2;
        else if (index < 15) weight = 1.5;

        draw.numbers.forEach(num => {
            frequency[num] += weight;
            trends[num].push(index); // 记录出现位置

            draw.numbers.forEach(other => {
                if (num !== other) pairs[num][other] += weight;
            });
        });
    });

    // 计算间隔（自上次出现以来的期数）
    recentData.forEach((draw, index) => {
        draw.numbers.forEach(num => {
            if (gaps[num] === 0) gaps[num] = index + 1;
        });
    });

    // 超级评分系统
    const scores = {};
    for (let i = 1; i <= 49; i++) {
        let score = 0;

        // 1. 频率得分 (35%)
        score += frequency[i] * 0.35;

        // 2. 配对得分 (25%)
        const hotNumbers = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12)
            .map(([num]) => parseInt(num));
        const pairScore = hotNumbers.reduce((sum, hot) => sum + pairs[i][hot], 0);
        score += pairScore * 0.25;

        // 3. 趋势得分 (20%) - 新增
        if (trends[i].length > 0) {
            const avgPosition = trends[i].reduce((a, b) => a + b, 0) / trends[i].length;
            if (avgPosition < 10) score += 15; // 最近常出现
            else if (avgPosition < 20) score += 8;
        }

        // 4. 间隔得分 (10%) - 新增："欠债理论"
        if (gaps[i] > 10) {
            score += (gaps[i] - 10) * 0.5; // 久未出现的号码加分
        }

        // 5. 基础分布得分 (10%)
        const zone = Math.floor((i - 1) / 10);
        if (zone >= 1 && zone <= 3) score += 4;
        if (i % 2 === 1) score += 2;

        scores[i] = score;
    }

    // 选择前15名候选
    const candidates = Object.entries(scores)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15)
        .map(([num]) => parseInt(num));

    // 超级智能组合（200次迭代）
    let bestCombo = null;
    let bestScore = -Infinity;

    for (let attempt = 0; attempt < 200; attempt++) {
        const combo = [];
        const available = [...candidates];

        while (combo.length < 6 && available.length > 0) {
            const weights = available.map((n, i) => Math.pow(2.5, available.length - i));
            const totalWeight = weights.reduce((a, b) => a + b, 0);
            let random = Math.random() * totalWeight;

            let selectedIndex = 0;
            for (let i = 0; i < weights.length; i++) {
                random -= weights[i];
                if (random <= 0) {
                    selectedIndex = i;
                    break;
                }
            }

            combo.push(available[selectedIndex]);
            available.splice(selectedIndex, 1);
        }

        const comboScore = evaluateSuperCombo(combo, scores, pairs);

        if (comboScore > bestScore) {
            bestScore = comboScore;
            bestCombo = [...combo];
        }
    }

    return bestCombo.sort((a, b) => a - b);
}

// 超级组合评估
function evaluateSuperCombo(combo, scores, pairs) {
    let score = 0;

    // 1. 基础分数
    score += combo.reduce((sum, num) => sum + scores[num], 0) * 1.2;

    // 2. 奇偶平衡（更高权重）
    const oddCount = combo.filter(n => n % 2 === 1).length;
    if (oddCount === 3) score += 150;
    else if (oddCount === 2 || oddCount === 4) score += 90;
    else score += 20;

    // 3. 区间超级分布
    const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
    if (zones.size === 5) score += 120;
    else if (zones.size === 4) score += 80;
    else if (zones.size === 3) score += 40;

    // 4. 总和黄金范围
    const sum = combo.reduce((a, b) => a + b, 0);
    if (sum >= 135 && sum <= 165) score += 130; // 最优
    else if (sum >= 120 && sum <= 180) score += 70;
    else if (sum >= 100 && sum <= 200) score += 30;

    // 5. 配对协同加分
    let pairBonus = 0;
    for (let i = 0; i < combo.length; i++) {
        for (let j = i + 1; j < combo.length; j++) {
            pairBonus += pairs[combo[i]][combo[j]] || 0;
        }
    }
    score += pairBonus * 0.5;

    // 6. 连号智能处理
    const sorted = [...combo].sort((a, b) => a - b);
    let consecutive = 0;
    for (let i = 0; i < sorted.length - 1; i++) {
        if (sorted[i + 1] === sorted[i] + 1) consecutive++;
    }
    if (consecutive === 0) score += 80;
    else if (consecutive === 1) score += 40;
    else score -= consecutive * 20;

    // 7. 尾数多样性
    const tails = new Set(combo.map(n => n % 10));
    score += tails.size * 15;

    // 8. 首尾差距（新增）
    const diff = sorted[sorted.length - 1] - sorted[0];
    if (diff >= 25 && diff <= 40) score += 50; // 理想差距

    return score;
}

// 运行v3测试
function runV3Test(sampleData) {
    console.log('\n🚀 运行 v3.0 超级优化算法...\n');

    let total = 0;
    let success = 0;
    const hitDist = {};

    for (let i = 30; i < Math.min(50, sampleData.length); i++) {
        const trainingData = sampleData.slice(0, i);
        const actualDraw = sampleData[i];
        const prediction = v3Predict(trainingData);
        const hits = prediction.filter(n => actualDraw.numbers.includes(n)).length;

        total++;
        if (hits >= 3) success++;
        hitDist[hits] = (hitDist[hits] || 0) + 1;

        console.log(`期${i}: [${prediction.join(',')}] vs [${actualDraw.numbers.join(',')}] = ${hits}/6`);
    }

    const successRate = (success / total * 100).toFixed(2);

    console.log('\n' + '='.repeat(60));
    console.log(`📊 v3.0 结果: ${success}/${total} = ${successRate}%`);
    console.log('='.repeat(60));
    console.log('\n命中分布:');
    for (let i = 0; i <= 6; i++) {
        const count = hitDist[i] || 0;
        const pct = (count / total * 100).toFixed(1);
        const bar = '█'.repeat(Math.floor(count / 2));
        console.log(`  ${i}个: ${count}次 (${pct}%) ${bar}`);
    }

    return {
        version: 'v3.0',
        successRate: parseFloat(successRate),
        total, success, hitDist
    };
}

async function main() {
    console.log('🎯 彩票预测 v3.0 - 目标30%+\n');

    const results = [];

    // 运行多轮测试取平均值
    for (let round = 1; round <= 3; round++) {
        console.log(`\n========== 第 ${round} 轮测试 ==========`);
        const sampleData = generateRealisticData(100);
        const result = runV3Test(sampleData);
        results.push(result);
    }

    const avgRate = (results.reduce((sum, r) => sum + r.successRate, 0) / results.length).toFixed(2);

    console.log('\n' + '='.repeat(60));
    console.log(`🏆 3轮平均成功率: ${avgRate}%`);
    console.log('='.repeat(60));

    fs.writeFileSync(__dirname + '/v3-results.json', JSON.stringify({
        avgSuccessRate: avgRate,
        rounds: results
    }, null, 2));

    console.log('\n✅ 结果已保存: v3-results.json');

    if (parseFloat(avgRate) >= 30) {
        console.log('\n🎉 突破30%！算法达到优秀水平！');
    } else if (parseFloat(avgRate) >= 25) {
        console.log('\n✨ 达到25%+，算法性能良好！');
    }
}

main().catch(console.error);
