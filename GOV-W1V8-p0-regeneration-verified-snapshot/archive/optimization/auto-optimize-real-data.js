const fs = require('fs');
const path = require('path');

function parseCSV(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    const data = [];
    
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        
        const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
        
        if (parts[0].includes('大樂透') || parts[0].includes('Lotto')) {
            if (parts.length < 13) continue;
            
            const draw = parts[1];
            const date = parts[2].replace(/\//g, '-');
            const numbers = [
                parseInt(parts[6]), parseInt(parts[7]), parseInt(parts[8]),
                parseInt(parts[9]), parseInt(parts[10]), parseInt(parts[11])
            ].filter(n => !isNaN(n) && n >= 1 && n <= 49);
            
            if (numbers.length === 6) {
                data.push({ draw, date, numbers: numbers.sort((a, b) => a - b) });
            }
        }
    }
    
    return data;
}

function loadRealData() {
    const baseDir = '/Users/kelvin/Downloads/獎號';
    const years = ['2023', '2024', '2025'];
    let allData = [];
    
    for (const year of years) {
        const filePath = path.join(baseDir, year, `大樂透_${year}.csv`);
        try {
            const yearData = parseCSV(filePath);
            allData = allData.concat(yearData);
            console.log(`✅ ${year}: 加载 ${yearData.length} 期`);
        } catch (err) {
            console.log(`⚠️  ${year}: 文件不存在或读取失败`);
        }
    }
    
    allData.sort((a, b) => b.draw.localeCompare(a.draw));
    return allData;
}

function rollingTest(data, weights) {
    let totalTests = 0;
    let successCount = 0;
    const results = [];
    
    // 从中间开始测试30期（确保有训练数据）
    const startIndex = 50;
    const testCount = 30;
    const testData = data.slice(startIndex, startIndex + testCount);
    
    console.log(`  测试区间：期${testData[testData.length-1].draw} 至 ${testData[0].draw} (共${testData.length}期)`);
    
    for (const targetDraw of testData) {
        const targetDrawNum = parseInt(targetDraw.draw);
        const trainingData = data.filter(d => parseInt(d.draw) > targetDrawNum);
        
        if (trainingData.length < 30) continue;
        
        const prediction = predictWithWeights(trainingData, weights);
        if (!prediction || prediction.length < 6) continue;
        
        const hits = prediction.filter(n => targetDraw.numbers.includes(n)).length;
        
        totalTests++;
        if (hits >= 3) successCount++;
        
        results.push({
            draw: targetDraw.draw,
            hits,
            success: hits >= 3
        });
    }
    
    return {
        rate: totalTests > 0 ? (successCount / totalTests * 100) : 0,
        total: totalTests,
        success: successCount
    };
}

function predictWithWeights(trainingData, weights) {
    const frequency = {};
    const pairs = {};
    
    for (let i = 1; i <= 49; i++) {
        frequency[i] = 0;
        pairs[i] = {};
        for (let j = 1; j <= 49; j++) pairs[i][j] = 0;
    }
    
    const recentData = trainingData.slice(0, Math.min(20, trainingData.length));
    recentData.forEach((draw, index) => {
        const weight = 1 + (recentData.length - index) * weights.timeDecay;
        
        draw.numbers.forEach(num => {
            frequency[num] += weight;
            draw.numbers.forEach(other => {
                if (num !== other) pairs[num][other] += weight;
            });
        });
    });
    
    const scores = {};
    for (let i = 1; i <= 49; i++) {
        let score = 0;
        score += frequency[i] * weights.freqWeight;
        
        const hotNumbers = Object.entries(frequency).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([num]) => parseInt(num));
        const pairScore = hotNumbers.reduce((sum, hot) => sum + (pairs[i][hot] || 0), 0);
        score += pairScore * weights.pairWeight;
        
        const zone = Math.floor((i - 1) / 10);
        if (zone >= 1 && zone <= 3) score += weights.zoneBonus;
        if (i % 2 === 1) score += weights.oddBonus;
        
        scores[i] = score;
    }
    
    const candidates = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, Math.floor(weights.candidateCount)).map(([num]) => parseInt(num));
    
    let bestCombo = null;
    let bestScore = -Infinity;
    
    for (let attempt = 0; attempt < weights.iterations; attempt++) {
        const combo = [];
        const available = [...candidates];
        
        while (combo.length < 6 && available.length > 0) {
            const ws = available.map((n, i) => Math.pow(weights.selectionPower, available.length - i));
            const totalWeight = ws.reduce((a, b) => a + b, 0);
            let random = Math.random() * totalWeight;
            
            let selectedIndex = 0;
            for (let i = 0; i < ws.length; i++) {
                random -= ws[i];
                if (random <= 0) {
                    selectedIndex = i;
                    break;
                }
            }
            
            combo.push(available[selectedIndex]);
            available.splice(selectedIndex, 1);
        }
        
        const comboScore = evaluateCombo(combo, scores, weights);
        if (comboScore > bestScore) {
            bestScore = comboScore;
            bestCombo = [...combo];
        }
    }
    
    return bestCombo ? bestCombo.sort((a, b) => a - b) : [];
}

function evaluateCombo(combo, scores, weights) {
    let score = 0;
    score += combo.reduce((sum, num) => sum + scores[num], 0) * 1.1;
    
    const oddCount = combo.filter(n => n % 2 === 1).length;
    if (oddCount === 3) score += weights.oddEvenPerfect;
    else if (oddCount === 2 || oddCount === 4) score += weights.oddEvenGood;
    
    const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
    score += zones.size * weights.zoneDistribution;
    
    const sum = combo.reduce((a, b) => a + b, 0);
    if (sum >= 120 && sum <= 180) {
        score += weights.sumRangeGood;
        if (sum >= 140 && sum <= 160) score += weights.sumRangePerfect;
    }
    
    const sorted = [...combo].sort((a, b) => a - b);
    let consecutive = 0;
    for (let i = 0; i < sorted.length - 1; i++) {
        if (sorted[i + 1] === sorted[i] + 1) consecutive++;
    }
    score -= consecutive * weights.consecutivePenalty;
    
    return score;
}

function adjustWeights(weights, currentRate, bestRate) {
    const newWeights = { ...weights };
    const gap = 20 - currentRate;
    
    if (currentRate > bestRate) {
        newWeights.freqWeight = Math.min(0.5, weights.freqWeight * 1.02);
        newWeights.iterations = Math.min(200, Math.floor(weights.iterations * 1.05));
    } else if (currentRate < 10) {
        newWeights.pairWeight = Math.min(0.4, weights.pairWeight * 1.1);
        newWeights.candidateCount = Math.min(16, weights.candidateCount + 1);
    } else if (currentRate < 15) {
        newWeights.timeDecay = Math.min(0.2, weights.timeDecay * 1.05);
        newWeights.oddEvenPerfect = Math.floor(weights.oddEvenPerfect * 1.05);
    } else {
        newWeights.selectionPower = Math.min(2.5, weights.selectionPower * 1.02);
        newWeights.sumRangePerfect = Math.floor(weights.sumRangePerfect * 1.03);
    }
    
    if (Math.random() < 0.1) {
        const keys = Object.keys(newWeights);
        const randomKey = keys[Math.floor(Math.random() * keys.length)];
        newWeights[randomKey] *= (0.95 + Math.random() * 0.1);
    }
    
    return newWeights;
}

async function main() {
    console.log('🚀 使用真实大乐透数据进行自动优化\n');
    console.log('📁 加载真实数据...');
    const realData = loadRealData();
    console.log(`✅ 总共加载 ${realData.length} 期真实数据\n`);
    
    if (realData.length < 100) {
        console.error('❌ 数据量不足');
        return;
    }
    
    console.log(`🎯 开始自动优化（目标：20%，限制：50次）\n`);
    
    let bestWeights = {
        freqWeight: 0.45, pairWeight: 0.35, timeDecay: 0.15,
        candidateCount: 14, iterations: 150, selectionPower: 2.2,
        zoneBonus: 6, oddBonus: 4, oddEvenPerfect: 110, oddEvenGood: 65,
        zoneDistribution: 45, sumRangeGood: 85, sumRangePerfect: 45, consecutivePenalty: 32
    };
    
    let bestRate = 0;
    const history = [];
    
    for (let iteration = 1; iteration <= 50; iteration++) {
    console.log('=' + ('=').repeat(59));
        console.log(`📊 第 ${iteration} 轮`);
        console.log('='.repeat(60));
        
        const testResult = rollingTest(realData, bestWeights);
        const rate = testResult.rate;
        
        console.log(`成功率: ${rate.toFixed(2)}% (${testResult.success}/${testResult.total})`);
        
        history.push({ iteration, rate: parseFloat(rate.toFixed(2)), weights: { ...bestWeights } });
        
        if (rate > bestRate) {
            bestRate = rate;
            console.log(`🎉 新纪录！${rate.toFixed(2)}%`);
        }
        
        if (rate >= 20) {
            console.log(`\n✅ 成功达标！${rate.toFixed(2)}% >= 20%`);
            break;
        }
        
        if (iteration === 50) {
            console.log(`\n⚠️  达到50次限制，最佳成功率: ${bestRate.toFixed(2)}%`);
            break;
        }
        
        console.log('🔧 调整参数...');
        bestWeights = adjustWeights(bestWeights, rate, bestRate);
    }
    
    const result = {
        dataSource: 'Real Taiwan Lotto 2023-2025',
        totalData: realData.length,
        targetRate: 20,
        achievedRate: bestRate,
        finalWeights: bestWeights,
        iterations: history.length,
        history
    };
    
    fs.writeFileSync(__dirname + '/real-data-optimization.json', JSON.stringify(result, null, 2));
    
    console.log('=' + ('=').repeat(59));
    console.log('📁 结果已保存: real-data-optimization.json');
    console.log('=' + ('=').repeat(59));
    console.log('最终权重:');
    console.log(JSON.stringify(bestWeights, null, 2));
}

main().catch(console.error);
