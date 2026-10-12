// v2优化版 - 基于25%成功率的微调
// 策略：简化但精准

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

// v2+优化：保持简单但提高准确性
function v2PlusPredict(trainingData) {
    const frequency = {};
    const pairs = {};

    for (let i = 1; i <= 49; i++) {
        frequency[i] = 0;
        pairs[i] = {};
        for (let j = 1; j <= 49; j++) pairs[i][j] = 0;
    }

    // 最近20期，阶梯权重
    const recentData = trainingData.slice(0, Math.min(20, trainingData.length));

    recentData.forEach((draw, index) => {
        const weight = 1 + (recentData.length - index) * 0.15; // 提高权重差异

        draw.numbers.forEach(num => {
            frequency[num] += weight;
            draw.numbers.forEach(other => {
                if (num !== other) pairs[num][other] += weight;
            });
        });
    });

    // 计算分数
    const scores = {};
    for (let i = 1; i <= 49; i++) {
        let score = 0;

        // 1. 频率 (45%) - 提高权重
        score += frequency[i] * 0.45;

        // 2. 配对 (35%) - 提高权重
        const hotNumbers = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([num]) => parseInt(num));
        const pairScore = hotNumbers.reduce((sum, hot) => sum + (pairs[i][hot] || 0), 0);
        score += pairScore * 0.35;

        // 3. 分布 (20%)
        const zone = Math.floor((i - 1) / 10);
        if (zone >= 1 && zone <= 3) score += 6; // 提高
        if (i % 2 === 1) score += 4; // 提高

        scores[i] = score;
    }

    // 候选：前14名
    const candidates = Object.entries(scores)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 14)
        .map(([num]) => parseInt(num));

    // 智能组合：150次迭代
    let bestCombo = null;
    let bestScore = -Infinity;

    for (let attempt = 0; attempt < 150; attempt++) {
        const combo = [];
        const available = [...candidates];

        while (combo.length < 6 && available.length > 0) {
            const weights = available.map((n, i) => Math.pow(2.2, available.length - i)); // 调整指数
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

        // 优化的评分
        const comboScore = (() => {
            let s = 0;

            s += combo.reduce((sum, num) => sum + scores[num], 0) * 1.1;

            // 奇偶
            const oddCount = combo.filter(n => n % 2 === 1).length;
            if (oddCount === 3) s += 110; // 微调
            else if (oddCount === 2 || oddCount === 4) s += 65;

            // 区间
            const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
            s += zones.size * 45; // 微调

            // 总和
            const sum = combo.reduce((a, b) => a + b, 0);
            if (sum >= 120 && sum <= 180) {
                s += 85; // 微调
                if (sum >= 140 && sum <= 160) s += 45;
            }

            // 连号
            const sorted = [...combo].sort((a, b) => a - b);
            let consecutive = 0;
            for (let i = 0; i < sorted.length - 1; i++) {
                if (sorted[i + 1] === sorted[i] + 1) consecutive++;
            }
            s -= consecutive * 32; // 微调

            return s;
        })();

        if (comboScore > bestScore) {
            bestScore = comboScore;
            bestCombo = [...combo];
        }
    }

    return bestCombo.sort((a, b) => a - b);
}

function runTest(sampleData, version) {
    let total = 0, success = 0;
    const hitDist = {};

    for (let i = 30; i < Math.min(50, sampleData.length); i++) {
        const prediction = v2PlusPredict(sampleData.slice(0, i));
        const hits = prediction.filter(n => sampleData[i].numbers.includes(n)).length;
        total++;
        if (hits >= 3) success++;
        hitDist[hits] = (hitDist[hits] || 0) + 1;
    }

    return {
        version,
        successRate: (success / total * 100).toFixed(2),
        total, success, hitDist
    };
}

async function main() {
    console.log('🎯 v2+ 微调优化测试\n');

    const results = [];
    for (let round = 1; round <= 5; round++) {
        console.log(`第${round}轮...`);
        const data = generateRealisticData(100);
        const result = runTest(data, `v2+_r${round}`);
        results.push(result);
        console.log(`  成功率: ${result.successRate}%`);
    }

    const avg = (results.reduce((s, r) => s + parseFloat(r.successRate), 0) / 5).toFixed(2);

    console.log('\n' + '='.repeat(50));
    console.log(`🏆 5轮平均: ${avg}%`);
    console.log('='.repeat(50));

    fs.writeFileSync(__dirname + '/v2plus-results.json', JSON.stringify({
        avgSuccessRate: avg,
        rounds: results
    }, null, 2));

    console.log('\n最佳版本:', avg >= 25 ? 'v2+' : 'v2');
}

main().catch(console.error);
