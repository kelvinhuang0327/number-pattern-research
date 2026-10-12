const fs = require('fs');
const path = require('path');

// 奖金表
const PRIZES = {
    '6+1': 10000000, // 头奖（假设值）
    '6+0': 1000000,  // 二奖
    '5+1': 50000,    // 三奖
    '5+0': 5000,     // 四奖
    '4+1': 500,      // 五奖
    '4+0': 400,      // 六奖
    '3+1': 400,      // 七奖
    '3+0': 200,      // 八奖
    '2+1': 100       // 九奖
};

// 解析CSV
function parseCSV(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    const data = [];

    for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map(p => p.trim().replace(/"/g, ''));
        if (parts[0].includes('大樂透') && parts.length >= 13) {
            const numbers = [
                parseInt(parts[6]), parseInt(parts[7]), parseInt(parts[8]),
                parseInt(parts[9]), parseInt(parts[10]), parseInt(parts[11])
            ].filter(n => n >= 1 && n <= 49).sort((a, b) => a - b);

            const special = parseInt(parts[12]);

            if (numbers.length === 6 && special >= 1 && special <= 49) {
                data.push({ draw: parts[1], date: parts[2], numbers, special });
            }
        }
    }
    return data;
}

// 加载数据
function loadData() {
    const base = '/Users/kelvin/Downloads/獎號';
    let all = [];
    ['2023', '2024', '2025'].forEach(year => {
        const data = parseCSV(path.join(base, year, `大樂透_${year}.csv`));
        all = all.concat(data);
        console.log(`  ${year}: ${data.length}期`);
    });
    all.sort((a, b) => b.draw.localeCompare(a.draw));
    return all;
}

// 计算中奖金额
function calculatePrize(predicted, actual) {
    const normalHits = predicted.numbers.filter(n => actual.numbers.includes(n)).length;
    const specialHit = predicted.special === actual.special;

    if (normalHits === 6 && specialHit) return PRIZES['6+1'];
    if (normalHits === 6) return PRIZES['6+0'];
    if (normalHits === 5 && specialHit) return PRIZES['5+1'];
    if (normalHits === 5) return PRIZES['5+0'];
    if (normalHits === 4 && specialHit) return PRIZES['4+1'];
    if (normalHits === 4) return PRIZES['4+0'];
    if (normalHits === 3 && specialHit) return PRIZES['3+1'];
    if (normalHits === 3) return PRIZES['3+0'];
    if (normalHits === 2 && specialHit) return PRIZES['2+1'];

    return 0;
}

// 预测（包含特别号）
function predict(training, w) {
    const freq = {}, pairs = {}, specialFreq = {};

    for (let i = 1; i <= 49; i++) {
        freq[i] = 0;
        specialFreq[i] = 0;
        pairs[i] = {};
        for (let j = 1; j <= 49; j++) pairs[i][j] = 0;
    }

    const recent = training.slice(0, 20);
    recent.forEach((draw, idx) => {
        const weight = 1 + (20 - idx) * w.decay;

        draw.numbers.forEach(num => {
            freq[num] += weight;
            draw.numbers.forEach(other => {
                if (num !== other) pairs[num][other] += weight;
            });
        });

        // 特别号统计
        specialFreq[draw.special] += weight * 1.2; // 特别号稍微加权
    });

    // 计算普通号分数
    const scores = {};
    const hot = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 10).map(x => parseInt(x[0]));

    for (let i = 1; i <= 49; i++) {
        let s = freq[i] * w.freq;
        s += hot.reduce((sum, h) => sum + (pairs[i][h] || 0), 0) * w.pair;
        const zone = Math.floor((i - 1) / 10);
        if (zone >= 1 && zone <= 3) s += 5;
        if (i % 2 === 1) s += 3;
        scores[i] = s;
    }

    // 生成两注（互补策略）
    const bet1 = generateBet(scores, w, 1);
    const bet2 = generateBet(scores, w, 2);

    // 预测特别号（选频率最高的）
    const special = parseInt(Object.entries(specialFreq).sort((a, b) => b[1] - a[1])[0][0]);

    return [
        { numbers: bet1, special },
        { numbers: bet2, special }
    ];
}

function generateBet(scores, w, strategy) {
    const cands = Object.entries(scores).sort((a, b) => b[1] - a[1]);

    let pool;
    if (strategy === 1) {
        // 第一注：高频号（前14名）
        pool = cands.slice(0, 14).map(x => parseInt(x[0]));
    } else {
        // 第二注：次高频+部分冷号（5-20名）
        pool = cands.slice(4, 18).map(x => parseInt(x[0]));
    }

    let best = null, bestScore = -Infinity;

    for (let iter = 0; iter < w.iters; iter++) {
        const combo = [];
        const avail = [...pool];

        while (combo.length < 6 && avail.length > 0) {
            const weights = avail.map((n, i) => Math.pow(2.2, avail.length - i));
            const total = weights.reduce((a, b) => a + b, 0);
            let rand = Math.random() * total;
            let idx = 0;
            for (let i = 0; i < weights.length; i++) {
                rand -= weights[i];
                if (rand <= 0) {
                    idx = i;
                    break;
                }
            }
            combo.push(avail[idx]);
            avail.splice(idx, 1);
        }

        let score = combo.reduce((sum, num) => sum + scores[num], 0);
        const odd = combo.filter(n => n % 2 === 1).length;
        if (odd === 3) score += 100;
        const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
        score += zones.size * 40;

        if (score > bestScore) {
            bestScore = score;
            best = [...combo];
        }
    }

    return best ? best.sort((a, b) => a - b) : [];
}

// 测试回本率
function testBreakEven(data, w) {
    let totalCost = 0;
    let totalWin = 0;
    let breakEvenCount = 0;
    const testData = data.slice(50, 80);

    for (const target of testData) {
        const training = data.filter(d => parseInt(d.draw) > parseInt(target.draw));
        if (training.length < 30) continue;

        const bets = predict(training, w);
        if (!bets || bets.length < 2) continue;

        totalCost += 200; // 两注

        let roundWin = 0;
        bets.forEach(bet => {
            const prize = calculatePrize(bet, target);
            roundWin += prize;
        });

        totalWin += roundWin;
        if (roundWin >= 200) breakEvenCount++;
    }

    const breakEvenRate = testData.length > 0 ? (breakEvenCount / testData.length * 100) : 0;
    const roi = totalCost > 0 ? ((totalWin - totalCost) / totalCost * 100) : 0;

    return {
        rate: breakEvenRate,
        roi: roi,
        totalCost,
        totalWin,
        profit: totalWin - totalCost,
        tests: testData.length,
        breakEven: breakEvenCount
    };
}

// 调整参数
function adjust(w, rate, roi, best) {
    const n = { ...w };

    if (rate > best.rate) {
        n.freq = Math.min(0.5, w.freq * 1.02);
        n.iters = Math.min(200, w.iters + 5);
    } else if (roi < -50) {
        n.pair = Math.min(0.4, w.pair * 1.1);
    } else if (rate < 5) {
        n.decay = Math.min(0.2, w.decay * 1.05);
    } else {
        n.freq = Math.min(0.5, w.freq * 1.01);
    }

    if (Math.random() < 0.1) {
        const keys = Object.keys(n);
        const key = keys[Math.floor(Math.random() * keys.length)];
        n[key] *= (0.95 + Math.random() * 0.1);
    }

    return n;
}

// 主程序
async function main() {
    console.log('🎯 回本优化引擎\n');
    console.log('目标: 两注(200元) 至少回本\n');

    console.log('📁 加载数据...');
    const data = loadData();
    console.log(`✅ 总计: ${data.length}期\n`);

    let w = { freq: 0.45, pair: 0.35, decay: 0.15, iters: 150 };
    let best = { rate: 0, roi: -100 };
    const history = [];

    console.log('开始优化...\n');

    for (let i = 1; i <= 50; i++) {
        const result = testBreakEven(data, w);
        history.push({ iteration: i, ...result, weights: { ...w } });

        const isBest = result.rate > best.rate || (result.rate === best.rate && result.roi > best.roi);

        console.log(`[${i}] 回本率:${result.rate.toFixed(1)}% ROI:${result.roi.toFixed(1)}% (${result.breakEven}/${result.tests}期)${isBest ? ' 🎉' : ''}`);

        if (isBest) {
            best = result;
            best.weights = { ...w };
        }

        if (result.rate >= 6) {
            console.log(`\n✅ 达标! 回本率${result.rate.toFixed(1)}% ROI:${result.roi.toFixed(1)}%`);
            break;
        }

        if (i === 50) {
            console.log(`\n⚠️  50次限制`);
        }

        w = adjust(w, result.rate, result.roi, best);
    }

    const finalResult = {
        target: '两注200元回本',
        achieved: best,
        history
    };

    fs.writeFileSync('break-even-result.json', JSON.stringify(finalResult, null, 2));

    console.log(`\n${'='.repeat(60)}`);
    console.log(`📊 最佳结果:`);
    console.log(`   回本率: ${best.rate.toFixed(1)}% (${best.breakEven}次回本/${best.tests}次测试)`);
    console.log(`   ROI: ${best.roi.toFixed(1)}%`);
    console.log(`   总投入: ${best.totalCost}元`);
    console.log(`   总奖金: ${best.totalWin}元`);
    console.log(`   净利润: ${best.profit}元`);
    console.log('='.repeat(60));
    console.log('\n📁 结果已保存: break-even-result.json');
}

main().catch(console.error);
