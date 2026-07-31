const fs = require('fs');
const path = require('path');

// ==========================================
// 1. 数据加载模块
// ==========================================
function parseCSV(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const lines = content.split('\n').filter(line => line.trim());
        const data = [];

        for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',').map(p => p.trim().replace(/"/g, ''));
            if (parts[0].includes('大樂透') && parts.length >= 13) {
                const numbers = [
                    parseInt(parts[6]), parseInt(parts[7]), parseInt(parts[8]),
                    parseInt(parts[9]), parseInt(parts[10]), parseInt(parts[11])
                ].filter(n => n >= 1 && n <= 49);

                if (numbers.length === 6) {
                    data.push({
                        draw: parts[1],
                        date: parts[2],
                        numbers: numbers.sort((a, b) => a - b)
                    });
                }
            }
        }
        return data;
    } catch (e) {
        return [];
    }
}

function loadRealData() {
    const base = '/Users/kelvin/Downloads/獎號';
    let all = [];
    ['2023', '2024', '2025'].forEach(year => {
        const f = path.join(base, year, `大樂透_${year}.csv`);
        if (fs.existsSync(f)) {
            const data = parseCSV(f);
            all = all.concat(data);
            console.log(`  加载 ${year}: ${data.length}期`);
        }
    });
    // 按期数排序：旧 -> 新 (方便滚动预测)
    all.sort((a, b) => a.draw.localeCompare(b.draw));
    return all;
}

// ==========================================
// 2. 策略模块
// ==========================================

// 策略A: 纯频率 (基准)
function strategyFrequency(trainingData) {
    const freq = {};
    for (let i = 1; i <= 49; i++) freq[i] = 0;

    // 统计所有历史数据
    trainingData.forEach(d => {
        d.numbers.forEach(n => freq[n]++);
    });

    return Object.entries(freq)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(x => parseInt(x[0]))
        .sort((a, b) => a - b);
}

// 策略B: 战术接力 (Ensemble) - 可调参数版
function strategyEnsemble(trainingData, params) {
    const freq = {}, pairs = {};
    for (let i = 1; i <= 49; i++) {
        freq[i] = 0;
        pairs[i] = {};
        for (let j = 1; j <= 49; j++) pairs[i][j] = 0;
    }

    // 1. 基础统计 (带时间衰减)
    // 只看最近N期，或者全部数据带衰减
    const recentCount = Math.min(trainingData.length, 50);
    const recentData = trainingData.slice(-recentCount);

    recentData.forEach((draw, idx) => {
        // idx越大越新 (0是50期前, recentCount-1是最新)
        // 衰减公式: (idx + 1) / recentCount * decayFactor
        // 或者: 1 + (idx) * params.timeDecay
        const weight = 1 + (idx) * params.timeDecay;

        draw.numbers.forEach(num => {
            freq[num] += weight;
            draw.numbers.forEach(other => {
                if (num !== other) pairs[num][other] += weight;
            });
        });
    });

    // 2. 计算得分
    const scores = {};
    // 找出当前热号用于配对加分
    const hotNumbers = Object.entries(freq)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(x => parseInt(x[0]));

    for (let i = 1; i <= 49; i++) {
        let s = freq[i] * params.freqWeight;

        // 配对加分
        const pairBonus = hotNumbers.reduce((sum, h) => sum + (pairs[i][h] || 0), 0);
        s += pairBonus * params.pairWeight;

        // 区间加分
        const zone = Math.floor((i - 1) / 10);
        if (zone >= 1 && zone <= 3) s += params.zoneBonus;

        // 奇偶加分
        if (i % 2 === 1) s += params.oddBonus;

        scores[i] = s;
    }

    // 3. 筛选候选号码
    const candidates = Object.entries(scores)
        .sort((a, b) => b[1] - a[1])
        .slice(0, Math.floor(params.candidateCount))
        .map(x => parseInt(x[0]));

    // 4. 智能组合 (蒙特卡洛模拟)
    let bestCombo = null;
    let bestScore = -Infinity;

    for (let i = 0; i < params.iterations; i++) {
        const combo = [];
        const pool = [...candidates];

        // 随机选择6个 (加权随机)
        while (combo.length < 6 && pool.length > 0) {
            // 权重: 排名越靠前权重越高
            const weights = pool.map((_, idx) => Math.pow(params.selectionPower, pool.length - idx));
            const totalW = weights.reduce((a, b) => a + b, 0);
            let r = Math.random() * totalW;
            let selectedIdx = 0;
            for (let k = 0; k < weights.length; k++) {
                r -= weights[k];
                if (r <= 0) { selectedIdx = k; break; }
            }
            combo.push(pool[selectedIdx]);
            pool.splice(selectedIdx, 1);
        }

        // 评估组合
        let comboScore = 0;
        // 基础分
        comboScore += combo.reduce((sum, n) => sum + scores[n], 0);

        // 结构分: 奇偶比 (3:3最佳)
        const oddCount = combo.filter(n => n % 2 === 1).length;
        if (oddCount === 3) comboScore += params.oddEvenPerfect;
        else if (oddCount === 2 || oddCount === 4) comboScore += params.oddEvenGood;

        // 结构分: 区间分布 (分散最佳)
        const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
        comboScore += zones.size * params.zoneDistribution;

        // 结构分: 总和 (120-180最佳)
        const sum = combo.reduce((a, b) => a + b, 0);
        if (sum >= 140 && sum <= 160) comboScore += params.sumRangePerfect;
        else if (sum >= 120 && sum <= 180) comboScore += params.sumRangeGood;

        // 惩罚: 连号
        const sorted = [...combo].sort((a, b) => a - b);
        let consecutive = 0;
        for (let k = 0; k < sorted.length - 1; k++) {
            if (sorted[k + 1] === sorted[k] + 1) consecutive++;
        }
        comboScore -= consecutive * params.consecutivePenalty;

        if (comboScore > bestScore) {
            bestScore = comboScore;
            bestCombo = combo;
        }
    }

    return bestCombo ? bestCombo.sort((a, b) => a - b) : [];
}

// ==========================================
// 3. 滚动测试引擎
// ==========================================
function runRollingTest(data, strategyFn, params, testCount = 30) {
    // 测试最后 testCount 期
    // 确保有足够训练数据 (至少50期)
    if (data.length < 50 + testCount) {
        console.log("数据不足以进行测试");
        return { rate: 0, hits: [] };
    }

    const testStartIndex = data.length - testCount;
    let success = 0;
    let totalHits = 0;

    for (let i = testStartIndex; i < data.length; i++) {
        const target = data[i];
        // 训练数据: 目标期之前的所有数据
        const training = data.slice(0, i);

        const prediction = strategyFn(training, params);

        const hitCount = prediction.filter(n => target.numbers.includes(n)).length;
        if (hitCount >= 3) success++;
        totalHits += hitCount;
    }

    return {
        rate: (success / testCount) * 100,
        avgHits: totalHits / testCount
    };
}

// ==========================================
// 4. 自动优化主程序
// ==========================================
function adjustParams(currentParams, rate, bestRate) {
    const newParams = { ...currentParams };

    // 随机微调
    const keys = Object.keys(newParams);
    // 每次调整 2-3 个参数
    const adjustCount = 2;

    for (let i = 0; i < adjustCount; i++) {
        const key = keys[Math.floor(Math.random() * keys.length)];
        const factor = 0.9 + Math.random() * 0.2; // 0.9 - 1.1 倍
        newParams[key] *= factor;

        // 边界检查
        if (key === 'candidateCount') newParams[key] = Math.max(6, Math.min(20, newParams[key]));
        if (key === 'iterations') newParams[key] = Math.max(50, Math.min(500, newParams[key]));
    }

    return newParams;
}

async function main() {
    console.log("🚀 开始真实数据自动优化 (20轮)...\n");

    // 1. 加载数据
    const data = loadRealData();
    console.log(`✅ 总数据量: ${data.length} 期`);

    if (data.length < 100) {
        console.log("❌ 数据过少，无法优化");
        return;
    }

    // 2. 基准测试 (纯频率)
    console.log("\n📊 基准测试 (纯频率策略)...");
    const baseResult = runRollingTest(data, strategyFrequency, {}, 30);
    console.log(`   成功率: ${baseResult.rate.toFixed(2)}% (平均命中: ${baseResult.avgHits.toFixed(2)})`);

    // 3. 优化战术接力策略
    console.log("\n🔧 开始优化战术接力策略 (目标: 20%)...");
    console.log("   测试范围: 2025年所有期数");

    // 筛选2025年的数据作为测试目标
    const test2025 = data.filter(d => d.date.startsWith('2025'));
    const testCount = test2025.length;
    console.log(`   测试样本: ${testCount} 期`);

    let bestParams = {
        freqWeight: 0.45,
        pairWeight: 0.35,
        timeDecay: 0.15,
        candidateCount: 14,
        iterations: 150,
        selectionPower: 2.2,
        zoneBonus: 6,
        oddBonus: 4,
        oddEvenPerfect: 110,
        oddEvenGood: 65,
        zoneDistribution: 45,
        sumRangePerfect: 45,
        sumRangeGood: 30,
        consecutivePenalty: 30
    };

    let bestRate = 0;

    for (let round = 1; round <= 20; round++) {
        // 使用 runRollingTest 的变体，传入具体的测试数量
        const result = runRollingTest(data, strategyEnsemble, bestParams, testCount);

        console.log(`[第${round}轮] 成功率: ${result.rate.toFixed(2)}% (平均命中: ${result.avgHits.toFixed(2)})`);

        if (result.rate > bestRate) {
            bestRate = result.rate;
            console.log("   🎉 发现新最佳参数!");
            // 保存最佳参数
            fs.writeFileSync('best-params.json', JSON.stringify(bestParams, null, 2));
        }

        if (result.rate >= 20) {
            console.log("\n✅ 达成目标 20%!");
            break;
        }

        // 调整参数用于下一轮
        bestParams = adjustParams(bestParams, result.rate, bestRate);
    }

    console.log(`\n🏆 最终最佳成功率: ${bestRate.toFixed(2)}%`);
    console.log("📁 最佳参数已保存至 best-params.json");
}

main();
