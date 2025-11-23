/**
 * 預測模組
 * 使用數學回歸分析預測下一期開獎機率
 */

class PredictionEngine {
    constructor(dataProcessor) {
        this.dataProcessor = dataProcessor;
        this.probabilityChart = null;
        this.tfModel = null;
    }

    /**
     * 舊版預測：使用 dataProcessor 內的 getDataRange(sampleSize)
     */
    async predict(method = 'frequency', sampleSize = 50) {
        const data = this.dataProcessor.getDataRange(sampleSize);
        return this._runPrediction(method, data);
    }

    /**
     * 模擬專用：直接接受外部提供的完整訓練資料
     */
    async predictWithData(method = 'frequency', trainingData = []) {
        if (!Array.isArray(trainingData) || trainingData.length === 0) {
            return { numbers: [], probabilities: {}, confidence: 0, method, report: '' };
        }
        return this._runPrediction(method, trainingData);
    }

    /**
     * 內部共用的預測執行邏輯，根據 method 呼叫對應演算法
     */
    async _runPrediction(method, data) {
        let prediction;
        switch (method) {
            case 'frequency':
                prediction = this.frequencyRegression(data);
                break;
            case 'trend':
                prediction = this.trendRegression(data);
                break;
            case 'combined':
                prediction = this.combinedRegression(data);
                break;
            case 'ml':
                prediction = this.machineLearningModel(data);
                break;
            case 'tf':
                prediction = await this.tensorflowModel(data);
                break;
            case 'markov':
                prediction = this.markovChainModel(data);
                break;
            case 'montecarlo':
                prediction = this.monteCarloSimulation(data);
                break;
            case 'cooccurrence':
                prediction = this.coOccurrenceModel(data);
                break;
            case 'lstm':
                prediction = await this.lstmModel(data);
                break;
            case 'ensemble':
                prediction = this.ensembleModel(data);
                break;
            default:
                prediction = this.frequencyRegression(data);
        }
        return prediction;
    }

    /**
     * 菁英投票策略 (Ensemble Model)
     * 結合所有統計模型的預測結果，進行加權投票
     */
    ensembleModel(data) {
        // 定義要參與投票的模型及其權重
        // 根據資料量動態調整權重
        const dataSize = data.length;
        const isSmallSample = dataSize < 50;
        const isLargeSample = dataSize > 500;

        const models = [
            {
                name: '頻率分析',
                func: this.frequencyRegression.bind(this),
                weight: isLargeSample ? 1.2 : 1.0 // 大數據時頻率更具參考價值
            },
            {
                name: '趨勢分析',
                func: this.trendRegression.bind(this),
                weight: isSmallSample ? 1.5 : 1.2 // 小樣本時近期趨勢更重要
            },
            {
                name: '綜合回歸',
                func: this.combinedRegression.bind(this),
                weight: 1.6 // 始終保持高權重
            },
            {
                name: '機器學習',
                func: this.machineLearningModel.bind(this),
                weight: 1.4
            },
            {
                name: '馬可夫鏈',
                func: this.markovChainModel.bind(this),
                weight: isLargeSample ? 1.8 : 1.3 // 馬可夫鏈需要大量數據才準確
            },
            {
                name: '蒙地卡羅',
                func: this.monteCarloSimulation.bind(this),
                weight: 1.2
            }
        ];

        const totalProbabilities = {};
        const range = LOTTERY_RULES.numberRange.max;

        // 初始化
        for (let i = 1; i <= range; i++) {
            totalProbabilities[i] = 0;
        }

        // 1. 執行每個基礎模型並加權累計機率
        models.forEach(model => {
            const result = model.func(data);
            for (let i = 1; i <= range; i++) {
                if (result.probabilities[i]) {
                    totalProbabilities[i] += result.probabilities[i] * model.weight;
                }
            }
        });

        // 2. [新增] 共現分析 (Co-occurrence Analysis) - 捕捉號碼組合關聯
        // 找出目前分數最高的 5 個「領頭號碼」
        const tempSorted = Object.entries(totalProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(([num]) => parseInt(num));

        // 建立共現矩陣 (只針對這 5 個領頭號碼去掃描歷史)
        const coOccurrenceBonus = {};
        for (let i = 1; i <= range; i++) coOccurrenceBonus[i] = 0;

        data.forEach(draw => {
            const nums = draw.numbers;
            // 檢查這一期是否包含任一領頭號碼
            const leadersInDraw = nums.filter(n => tempSorted.includes(n));

            if (leadersInDraw.length > 0) {
                // 如果有領頭號碼，則這一期的其他號碼都獲得加分 (因為它們常跟領頭羊一起出)
                nums.forEach(n => {
                    if (!tempSorted.includes(n)) { // 不加分自己
                        // 加分權重：跟越多領頭羊一起出，分數越高
                        coOccurrenceBonus[n] += (leadersInDraw.length * 0.05);
                    }
                });
            }
        });

        // 將共現紅利加入總分 (正規化後加入)
        const maxBonus = Math.max(...Object.values(coOccurrenceBonus)) || 1;
        for (let i = 1; i <= range; i++) {
            // 權重 0.8：這是一個輔助指標，不應喧賓奪主
            totalProbabilities[i] += (coOccurrenceBonus[i] / maxBonus) * 0.8;
        }

        // 3. [新增] 冷熱對沖策略 (Hot/Cold Balancing)
        // 統計每個號碼的遺漏值 (Missing Count)
        const missingCounts = this.calculateMissingForData(data);

        // 找出最冷的 10 個號碼 (遺漏最久)
        const coldNumbers = Object.entries(missingCounts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([num]) => parseInt(num));

        // 給冷號加分 (均值回歸補償)
        coldNumbers.forEach(num => {
            // 加分幅度：遺漏越久加越多，但不要超過熱門號太多
            // 這裡給予 0.5 的權重，相當於半個頻率分析的影響力
            totalProbabilities[num] += 0.5;
        });

        // 正規化總機率
        const sumTotal = Object.values(totalProbabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) {
            totalProbabilities[i] /= sumTotal;
        }

        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(totalProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: totalProbabilities,
            confidence: confidence,
            method: '菁英投票策略 (Ensemble)',
            report: `綜合 ${models.length} 種模型的投票結果，集結了頻率、趨勢、序列與隨機模擬的優勢。`
        };
    }

    // -------------------------------------------------
    // 以下為各種預測演算法（保持原有實作）
    // -------------------------------------------------
    frequencyRegression(data) {
        const frequency = {};
        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            frequency[i] = 0;
        }
        // 計算頻率
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });
        // 計算機率（頻率 / 總期數）
        const probabilities = {};
        const totalDraws = data.length;
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = frequency[i] / totalDraws;
        }
        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '頻率回歸分析',
            report: this.generateReport('frequency', sortedNumbers, data.length)
        };
    }

    trendRegression(data) {
        const weightedFrequency = {};
        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            weightedFrequency[i] = 0;
        }
        // 計算加權頻率（越近期權重越高）
        data.forEach((draw, index) => {
            const weight = (index + 1) / data.length; // 線性權重
            draw.numbers.forEach(num => {
                weightedFrequency[num] += weight;
            });
        });
        // 正規化機率
        const totalWeight = Object.values(weightedFrequency).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = weightedFrequency[i] / totalWeight;
        }
        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '趨勢回歸分析',
            report: this.generateReport('trend', sortedNumbers, data.length)
        };
    }

    combinedRegression(data) {
        const frequency = {};
        const weighted = {};
        const missing = this.calculateMissingForData(data);
        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            frequency[i] = 0;
            weighted[i] = 0;
        }
        // 計算頻率和加權頻率
        data.forEach((draw, index) => {
            const weight = (index + 1) / data.length;
            draw.numbers.forEach(num => {
                frequency[num]++;
                weighted[num] += weight;
            });
        });
        // 綜合計算機率
        const probabilities = {};
        const totalDraws = data.length;
        const maxMissing = Math.max(...Object.values(missing));
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            const freqScore = (frequency[i] / totalDraws) * 0.4;
            const trendScore = (weighted[i] / data.length) * 0.3;
            const missingScore = maxMissing > 0 ? (missing[i] / maxMissing) * 0.3 : 0;
            probabilities[i] = freqScore + trendScore + missingScore;
        }
        // 正規化整體機率，使總和為 1
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = probabilities[i] / sumProb;
        }
        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '綜合回歸模型',
            report: this.generateReport('combined', sortedNumbers, data.length)
        };
    }

    async tensorflowModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        // 若已有模型則直接使用
        if (!this.tfModel) {
            // 创建模型：输入 range 维 one‑hot，隐藏层 64 单元，输出 range 维概率
            this.tfModel = tf.sequential();
            this.tfModel.add(tf.layers.dense({ inputShape: [range], units: 64, activation: 'relu' }));
            this.tfModel.add(tf.layers.dense({ units: range, activation: 'softmax' }));
            this.tfModel.compile({ optimizer: tf.train.adam(0.01), loss: 'categoricalCrossentropy' });
            // 准备训练数据
            const xs = [];
            const ys = [];
            data.forEach(draw => {
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                xs.push(input);
                const nextIdx = data.indexOf(draw) + 1;
                const targetDraw = nextIdx < data.length ? data[nextIdx] : draw;
                const target = new Array(range).fill(0);
                targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
                ys.push(target);
            });
            const xsTensor = tf.tensor2d(xs);
            const ysTensor = tf.tensor2d(ys);
            await this.tfModel.fit(xsTensor, ysTensor, { epochs: 12, batchSize: 32, verbose: 0 });
            xsTensor.dispose();
            ysTensor.dispose();
        }
        // 使用模型对最近一期进行预测
        const latest = data[data.length - 1];
        const input = new Array(range).fill(0);
        latest.numbers.forEach(num => { input[num - 1] = 1; });
        const inputTensor = tf.tensor2d([input]);
        const outputTensor = this.tfModel.predict(inputTensor);
        const probsArray = await outputTensor.data();
        inputTensor.dispose();
        outputTensor.dispose();
        // 取前 N 个概率最高的号码
        const sortedNumbers = Array.from(probsArray)
            .map((p, idx) => ({ number: idx + 1, probability: p }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, LOTTERY_RULES.pickCount);
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);
        return {
            numbers: predictedNumbers,
            probabilities: probsArray.reduce((obj, p, i) => { obj[i + 1] = p; return obj; }, {}),
            confidence: confidence,
            method: 'TensorFlow.js 神经网络',
            report: this.generateReport('tf', sortedNumbers, data.length)
        };
    }

    machineLearningModel(data) {
        const patterns = this.analyzePatterns(data);
        const probabilities = {};
        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = 0;
        }
        // 1. 連號模式
        patterns.consecutive.forEach(num => {
            probabilities[num] = (probabilities[num] || 0) + 0.15;
        });
        // 2. 區間平衡
        const distribution = this.calculateDistributionForData(data);
        const avgPerZone = LOTTERY_RULES.pickCount / 5; // 平均每個區間應該有的號碼數
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            const zone = this.getZone(i);
            const zoneCount = distribution[zone];
            const zoneFactor = avgPerZone / (zoneCount + 1);
            probabilities[i] = (probabilities[i] || 0) + (zoneFactor * 0.2);
        }
        // 3. 奇偶平衡
        const oddEven = this.calculateOddEvenForData(data);
        const oddRatio = oddEven.odd / (oddEven.odd + oddEven.even);
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            if (i % 2 === 1 && oddRatio < 0.5) {
                probabilities[i] = (probabilities[i] || 0) + 0.1;
            } else if (i % 2 === 0 && oddRatio > 0.5) {
                probabilities[i] = (probabilities[i] || 0) + 0.1;
            }
        }
        // 4. 歷史頻率
        const frequency = {};
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            frequency[i] = 0;
        }
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = (probabilities[i] || 0) + ((frequency[i] / data.length) * 0.55);
        }
        // 正規化
        const total = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = probabilities[i] / total;
        }
        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '機器學習模型',
            report: this.generateReport('ml', sortedNumbers, data.length)
        };
    }

    /**
     * 馬可夫鏈模型 (Markov Chain)
     * 分析號碼之間的轉移機率：當前出現號碼 A，下一期出現號碼 B 的機率
     */
    markovChainModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        // 初始化 49x49 的轉移矩陣 (使用 Map 以節省稀疏空間，或直接用二維陣列)
        // 這裡使用二維陣列 matrix[from][to]
        const matrix = Array.from({ length: range + 1 }, () => Array(range + 1).fill(0));

        // 建立轉移矩陣
        // 遍歷每一期，看當期號碼 -> 下一期號碼
        for (let i = 0; i < data.length - 1; i++) {
            const currentNumbers = data[i].numbers;
            const nextNumbers = data[i + 1].numbers;

            currentNumbers.forEach(fromNum => {
                nextNumbers.forEach(toNum => {
                    matrix[fromNum][toNum]++;
                });
            });
        }

        // 根據最新一期的號碼，預測下一期
        const latestDraw = data[data.length - 1];
        const latestNumbers = latestDraw.numbers;
        const probabilities = {};

        // 初始化機率
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            probabilities[i] = 0;
        }

        // 加總所有可能轉移的機率
        latestNumbers.forEach(fromNum => {
            const rowTotal = matrix[fromNum].reduce((a, b) => a + b, 0);
            if (rowTotal > 0) {
                for (let toNum = 1; toNum <= range; toNum++) {
                    // P(to | from) = count(from->to) / count(from)
                    const prob = matrix[fromNum][toNum] / rowTotal;
                    probabilities[toNum] += prob;
                }
            }
        });

        // 正規化
        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        if (totalProb > 0) {
            for (let i = 1; i <= range; i++) {
                probabilities[i] /= totalProb;
            }
        }

        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '馬可夫鏈模型',
            report: this.generateReport('markov', sortedNumbers, data.length)
        };
    }

    /**
     * 蒙地卡羅模擬 (Monte Carlo Simulation)
     * 基於加權機率進行大量隨機模擬
     */
    monteCarloSimulation(data) {
        // 1. 先計算基礎權重（使用綜合回歸的邏輯：頻率 + 趨勢 + 遺漏）
        // 這裡簡化使用頻率與遺漏值
        const frequency = {};
        const missing = this.calculateMissingForData(data);
        const range = LOTTERY_RULES.numberRange.max;

        for (let i = 1; i <= range; i++) {
            frequency[i] = 0;
        }
        data.forEach(draw => draw.numbers.forEach(n => frequency[n]++));

        const weights = {};
        const totalDraws = data.length;

        // 計算權重
        for (let i = 1; i <= range; i++) {
            const freqWeight = frequency[i] / totalDraws;
            // 遺漏值加權：遺漏越久，權重稍微增加 (例如 log scale)
            const missingWeight = Math.log(missing[i] + 1) * 0.1;
            weights[i] = freqWeight + missingWeight;
        }

        // 2. 執行模擬
        const simulations = 10000; // 模擬次數
        const simulationCounts = {};
        for (let i = 1; i <= range; i++) simulationCounts[i] = 0;

        // 準備輪盤選擇 (Roulette Wheel Selection)
        const weightEntries = Object.entries(weights);
        const totalWeight = weightEntries.reduce((sum, [_, w]) => sum + w, 0);

        for (let i = 0; i < simulations; i++) {
            // 每一輪模擬選出 6 個不重複號碼
            const selected = new Set();
            while (selected.size < LOTTERY_RULES.pickCount) {
                let random = Math.random() * totalWeight;
                for (const [numStr, weight] of weightEntries) {
                    random -= weight;
                    if (random <= 0) {
                        selected.add(parseInt(numStr));
                        break;
                    }
                }
            }
            selected.forEach(num => simulationCounts[num]++);
        }

        // 3. 統計模擬結果
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = simulationCounts[i] / simulations;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '蒙地卡羅模擬',
            report: this.generateReport('montecarlo', sortedNumbers, data.length)
        };
    }

    /**
     * 共現分析模型 (Co-occurrence Model)
     * 專注於分析號碼之間的關聯性，找出最常一起出現的組合
     */
    coOccurrenceModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        // 1. 先找出「領頭羊」：這裡使用最近一期的號碼作為基準
        // 假設最近一期的號碼會帶動下一期的相關號碼 (這是一種假設，也可以改用熱門號)
        const lastDraw = data[data.length - 1];
        const leaders = lastDraw.numbers;

        // 2. 建立共現矩陣
        const coOccurrence = {};
        for (let i = 1; i <= range; i++) coOccurrence[i] = 0;

        // 3. 掃描歷史資料
        data.forEach(draw => {
            const nums = draw.numbers;
            // 檢查這一期是否包含任一領頭號碼
            const leadersInDraw = nums.filter(n => leaders.includes(n));

            if (leadersInDraw.length > 0) {
                // 如果有領頭號碼，則這一期的其他號碼都獲得加分
                nums.forEach(n => {
                    if (!leaders.includes(n)) { // 不加分自己
                        // 加分權重：跟越多領頭羊一起出，分數越高
                        coOccurrence[n] += leadersInDraw.length;
                    }
                });
            }
        });

        // 4. 轉換為機率
        const totalScore = Object.values(coOccurrence).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = totalScore > 0 ? coOccurrence[i] / totalScore : 0;
        }

        // 5. 排序並回傳
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '共現分析模型',
            report: this.generateReport('cooccurrence', sortedNumbers, data.length)
        };
    }

    /**
     * LSTM 深度學習模型 (Long Short-Term Memory)
     * 專門處理時間序列數據，捕捉長期依賴關係
     */
    async lstmModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const sequenceLength = 10; // 回看過去 10 期
        const featureSize = range; // 每個時間點的特徵數 (49個號碼的 One-hot)

        // 優化 1: 限制訓練資料量，只取最近 300 期，大幅提升速度並避免記憶體溢出
        const recentData = data.slice(-300);

        // 1. 資料前處理：轉換為 3D 序列 (Samples, TimeSteps, Features)
        const xs = [];
        const ys = [];

        // 至少需要 sequenceLength + 1 筆資料才能訓練
        if (recentData.length < sequenceLength + 1) {
            return this.frequencyRegression(data); // 資料不足退回頻率分析
        }

        for (let i = 0; i < recentData.length - sequenceLength; i++) {
            const sequence = [];
            for (let j = 0; j < sequenceLength; j++) {
                const draw = recentData[i + j];
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                sequence.push(input);
            }
            xs.push(sequence);

            // 目標：下一期的號碼
            const targetDraw = recentData[i + sequenceLength];
            const target = new Array(range).fill(0);
            targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
            ys.push(target);
        }

        // 使用 tf.tidy 自動管理中間產生的 Tensor 記憶體
        // 但 model.fit 是非同步的，不能直接包在 tidy 裡，所以手動管理 Tensor
        const xsTensor = tf.tensor3d(xs, [xs.length, sequenceLength, featureSize]);
        const ysTensor = tf.tensor2d(ys, [ys.length, range]);

        // 2. 建立 LSTM 模型 (極致輕量化)
        const model = tf.sequential();

        model.add(tf.layers.lstm({
            units: 16, // 降至 16，對於簡單規律已足夠
            inputShape: [sequenceLength, featureSize],
            returnSequences: false,
            kernelInitializer: 'glorotUniform',
            recurrentInitializer: 'glorotUniform'
        }));

        model.add(tf.layers.dense({ units: range, activation: 'softmax' }));

        model.compile({ optimizer: 'adam', loss: 'categoricalCrossentropy' });

        // 3. 訓練模型 (極速模式)
        await model.fit(xsTensor, ysTensor, {
            epochs: 2, // 只練 2 輪，有學到就好
            batchSize: 32,
            verbose: 0
        });

        // 4. 預測下一期
        const lastSequence = [];
        for (let i = recentData.length - sequenceLength; i < recentData.length; i++) {
            const draw = recentData[i];
            const input = new Array(range).fill(0);
            draw.numbers.forEach(num => { input[num - 1] = 1; });
            lastSequence.push(input);
        }

        const inputTensor = tf.tensor3d([lastSequence], [1, sequenceLength, featureSize]);
        const outputTensor = model.predict(inputTensor);
        const probsArray = await outputTensor.data();

        // 5. 徹底釋放記憶體
        xsTensor.dispose();
        ysTensor.dispose();
        inputTensor.dispose();
        outputTensor.dispose();
        model.dispose(); // 重要：銷毀模型以釋放 GPU 資源

        // 6. 整理結果
        const probabilities = {};
        for (let i = 0; i < range; i++) {
            probabilities[i + 1] = probsArray[i];
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'LSTM 深度學習模型',
            report: this.generateReport('lstm', sortedNumbers, recentData.length)
        };
    }

    // 其他輔助方法
    calculateConfidence(sortedNumbers) {
        // 簡單的信心指數計算：前6個號碼的機率總和
        const sumProb = sortedNumbers.reduce((sum, item) => sum + item.probability, 0);
        // 正規化到 0-100%
        return Math.min(Math.round(sumProb * 100 * 3), 99); // *3 是為了讓數值好看一點，非嚴謹統計
    }

    generateReport(method, sortedNumbers, dataLength) {
        return `基於 ${dataLength} 期歷史數據進行 ${method} 分析。`;
    }

    analyzePatterns(data) {
        // 簡單實作：找出最近一期的連號
        const lastDraw = data[data.length - 1];
        const numbers = lastDraw.numbers;
        const consecutive = [];
        for (let i = 0; i < numbers.length - 1; i++) {
            if (numbers[i + 1] === numbers[i] + 1) {
                consecutive.push(numbers[i]);
                consecutive.push(numbers[i + 1]);
            }
        }
        return { consecutive: [...new Set(consecutive)] };
    }

    calculateMissingForData(data) {
        const missing = {};
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            missing[i] = 0;
        }
        for (let i = data.length - 1; i >= 0; i--) {
            const draw = data[i];
            for (let num = LOTTERY_RULES.numberRange.min; num <= LOTTERY_RULES.numberRange.max; num++) {
                if (!draw.numbers.includes(num)) {
                    missing[num]++;
                }
            }
            draw.numbers.forEach(num => {
                if (missing[num] > 0) missing[num] = 0;
            });
        }
        return missing;
    }

    calculateDistributionForData(data) {
        const distribution = { '1-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-49': 0 };
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                if (num <= 10) distribution['1-10']++;
                else if (num <= 20) distribution['11-20']++;
                else if (num <= 30) distribution['21-30']++;
                else if (num <= 40) distribution['31-40']++;
                else distribution['41-49']++;
            });
        });
        return distribution;
    }

    getZone(num) {
        if (num <= 10) return '1-10';
        if (num <= 20) return '11-20';
        if (num <= 30) return '21-30';
        if (num <= 40) return '31-40';
        return '41-49';
    }

    calculateOddEvenForData(data) {
        let odd = 0;
        let even = 0;
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                if (num % 2 === 0) even++;
                else odd++;
            });
        });
        return { odd, even };
    }

    /**
     * 顯示預測結果到 UI
     */
    displayPrediction(prediction) {
        // 顯示預測號碼
        const numbersContainer = document.getElementById('predicted-numbers');
        if (numbersContainer) {
            numbersContainer.innerHTML = prediction.numbers
                .map(num => `<div class="predicted-number">${num}</div>`)
                .join('');
        }

        // 更新信心度
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');
        if (confidenceFill) {
            confidenceFill.style.width = `${prediction.confidence}%`;
        }
        if (confidenceValue) {
            confidenceValue.textContent = `${prediction.confidence}%`;
        }

        // 顯示報告
        const reportContainer = document.getElementById('prediction-report');
        if (reportContainer) {
            reportContainer.innerHTML = `
                <div class="report-section">
                    <h4>預測方法</h4>
                    <p>${prediction.method}</p>
                </div>
                <div class="report-section">
                    <h4>分析報告</h4>
                    <p>${prediction.report}</p>
                </div>
                <div class="report-section">
                    <h4>預測號碼機率排名</h4>
                    <ul>
                        ${prediction.numbers.map((num, idx) => {
                            const prob = prediction.probabilities[num];
                            const percentage = (prob * 100).toFixed(2);
                            return `<li>第 ${idx + 1} 名：<strong>${num}</strong> 號 (${percentage}%)</li>`;
                        }).join('')}
                    </ul>
                </div>
            `;
        }

        // 創建機率分佈圖表
        this.createProbabilityChart(prediction.probabilities);
    }

    /**
     * 創建機率分佈圖表
     */
    createProbabilityChart(probabilities) {
        const ctx = document.getElementById('probability-chart');
        if (!ctx) return;

        // 銷毀舊圖表
        if (this.probabilityChart) {
            this.probabilityChart.destroy();
        }

        const labels = Object.keys(probabilities);
        const data = Object.values(probabilities).map(p => (p * 100).toFixed(2));

        this.probabilityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '預測機率 (%)',
                    data: data,
                    backgroundColor: 'rgba(147, 51, 234, 0.6)',
                    borderColor: 'rgba(147, 51, 234, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 25, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        callbacks: {
                            label: (context) => `機率: ${context.parsed.y}%`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: 'rgba(255, 255, 255, 0.7)', font: { size: 10 } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: 'rgba(255, 255, 255, 0.7)' }
                    }
                }
            }
        });
    }
}

// 導出為全域變數
window.PredictionEngine = PredictionEngine;
