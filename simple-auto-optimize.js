const fs = require('fs');
const path = require('path');

// 解析CSV
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

// 预测
function predict(training, w) {
    const freq = {}, pairs = {};
    for (let i = 1; i <= 49; i++) {
        freq[i] = 0;
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
    });

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

    const cands = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 14).map(x => parseInt(x[0]));

    let best = null, bestScore = -Infinity;
    for (let iter = 0; iter < w.iters; iter++) {
        const combo = [];
        const avail = [...cands];

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
        else if (odd === 2 || odd === 4) score += 60;

        const zones = new Set(combo.map(n => Math.floor((n - 1) / 10)));
        score += zones.size * 40;

        const sum = combo.reduce((a, b) => a + b, 0);
        if (sum >= 120 && sum <= 180) score += 80;

        if (score > bestScore) {
            bestScore = score;
            best = [...combo];
        }
    }

    return best ? best.sort((a, b) => a - b) : [];
}

// 测试
function test(data, w) {
    let total = 0, success = 0;
    const testData = data.slice(50, 80); // 测试30期

    for (const target of testData) {
        const training = data.filter(d => parseInt(d.draw) > parseInt(target.draw));
        if (training.length < 30) continue;

        const pred = predict(training, w);
        if (!pred || pred.length < 6) continue;

        const hits = pred.filter(n => target.numbers.includes(n)).length;
        total++;
        if (hits >= 3) success++;
    }

    return total > 0 ? (success / total * 100) : 0;
}

// 调整参数
function adjust(w, rate, best) {
    const n = { ...w };
    const gap = 20 - rate;

    if (rate > best) {
        n.freq = Math.min(0.5, w.freq * 1.02);
        n.iters = Math.min(200, w.iters + 5);
    } else if (rate < 10) {
        n.pair = Math.min(0.4, w.pair * 1.1);
    } else if (rate < 15) {
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
    console.log('🚀 自动优化引擎 (简化版)\n');
    console.log('📁 加载数据...');
    const data = loadData();
    console.log(`✅ 总计: ${data.length}期\n`);

    if (data.length < 100) {
        console.log('❌ 数据不足');
        return;
    }

    console.log('🎯 目标: 20% | 限制: 50次\n');

    let w = { freq: 0.45, pair: 0.35, decay: 0.15, iters: 150 };
    let bestRate = 0;
    const history = [];

    for (let i = 1; i <= 50; i++) {
        const rate = test(data, w);
        history.push({ iteration: i, rate: parseFloat(rate.toFixed(2)), weights: { ...w } });

        console.log(`[${i}] ${rate.toFixed(2)}%${rate > bestRate ? ' 🎉' : ''}`);

        if (rate > bestRate) bestRate = rate;
        if (rate >= 20) {
            console.log(`\n✅ 达标! ${rate.toFixed(2)}%`);
            break;
        }
        if (i === 50) {
            console.log(`\n⚠️  50次限制, 最佳: ${bestRate.toFixed(2)}%`);
        }

        w = adjust(w, rate, bestRate);
    }

    const result = {
        source: '真实数据2023-2025',
        periods: data.length,
        target: 20,
        achieved: bestRate,
        weights: w,
        iterations: history.length,
        history
    };

    fs.writeFileSync('optimization-result.json', JSON.stringify(result, null, 2));

    console.log(`\n📊 最佳: ${bestRate.toFixed(2)}%`);
    console.log('📁 已保存: optimization-result.json');
    console.log('\n最终参数:');
    console.log(JSON.stringify(w, null, 2));
}

main().catch(console.error);
