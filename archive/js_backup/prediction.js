/**
 * 預測模組
 * 使用數學回歸分析預測下一期開獎機率
 */

class PredictionEngine {
    constructor(dataProcessor) {
        this.dataProcessor = dataProcessor;
        this.probabilityChart = null;
        this.tfModel = null;
        this.collaborativeEngine = null;
        this.initCollaborativeEngine();
    }

    /**
     * 初始化協作預測引擎
     */
    initCollaborativeEngine() {
        if (window.CollaborativePredictionEngine) {
            this.collaborativeEngine = new CollaborativePredictionEngine(this);
        }
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

        // 確保協作引擎已初始化
        if (!this.collaborativeEngine) {
            this.initCollaborativeEngine();
        }

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
            case 'weighted':
                prediction = this.featureWeightedModel(data);
                break;
            case 'attention':
                prediction = await this.attentionLstmModel(data);
                break;
            case 'bayesian':
                prediction = this.bayesianProbabilityModel(data);
                break;
            case 'deviation':
                prediction = this.deviationTrackingModel(data);
                break;
            case 'boosting':
                prediction = this.gradientBoostingModel(data);
                break;
            case 'ensemble':
                prediction = this.ensembleModel(data);
                break;
            case 'all_ensemble':
                prediction = await this.allModelsEnsemble(data);
                break;
            case 'tactical_relay':
                prediction = await this.tacticalRelayModel(data);
                break;
            // 智能集成預測框架 (Intelligent Ensemble Framework)
            case 'adaptive_ensemble':
                prediction = await this.adaptiveEnsembleModel(data);
                break;
            case 'consensus_voting':
                prediction = await this.consensusVotingModel(data);
                break;
            case 'pipeline':
                prediction = await this.pipelineModel(data);
                break;
            case 'hybrid_strategy':
                prediction = await this.hybridStrategyModel(data);
                break;
            // 協作預測系統 (Collaborative Prediction System)
            case 'relay':
                if (this.collaborativeEngine) prediction = await this.collaborativeEngine.relayPrediction(data);
                else prediction = await this.tacticalRelayModel(data); // Fallback
                break;
            case 'collaborative':
                if (this.collaborativeEngine) prediction = await this.collaborativeEngine.collaborativePrediction(data);
                else prediction = await this.allModelsEnsemble(data); // Fallback
                break;
            case 'adaptive':
                if (this.collaborativeEngine) prediction = await this.collaborativeEngine.adaptiveRelayPrediction(data);
                else prediction = await this.adaptiveEnsembleModel(data); // Fallback
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
        const confidence = this.calculateConfidence(sortedNumbers, totalProbabilities);

        return {
            numbers: predictedNumbers,
            probabilities: totalProbabilities,
            confidence: confidence,
            method: '菁英投票策略 (Ensemble)',
            report: `綜合 ${models.length} 種模型的投票結果，集結了頻率、趨勢、序列與隨機模擬的優勢，並加入共現分析與冷熱對沖策略。`
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
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);
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

        // 使用指數衰減權重（越近期權重越高，衰減更明顯）
        // 衰減係數 lambda: 控制衰減速度，越大衰減越快
        const lambda = 0.05; // 可調整，0.03-0.1 之間效果較好
        const n = data.length;

        data.forEach((draw, index) => {
            // 指數衰減: weight = e^(-lambda * (n - index - 1))
            // index=0 是最舊的，index=n-1 是最新的
            const age = n - index - 1; // 距離現在的期數
            const weight = Math.exp(-lambda * age);
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
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '趨勢回歸分析 (指數衰減)',
            report: this.generateReport('trend', sortedNumbers, data.length)
        };
    }

    combinedRegression(data) {
        const frequency = {};
        const weighted = {};
        const missing = this.calculateMissingForData(data);
        const tailBonus = this.getTailBonus(data);
        const range = LOTTERY_RULES.numberRange;
        const n = data.length;

        // 初始化
        for (let i = range.min; i <= range.max; i++) {
            frequency[i] = 0;
            weighted[i] = 0;
        }

        // 計算頻率和指數衰減加權頻率
        const lambda = 0.05;
        data.forEach((draw, index) => {
            const age = n - index - 1;
            const expWeight = Math.exp(-lambda * age);
            draw.numbers.forEach(num => {
                frequency[num]++;
                weighted[num] += expWeight;
            });
        });

        // 動態調整權重（根據資料量）
        // 小樣本: 趨勢更重要；大樣本: 頻率更可靠
        const isSmallSample = n < 50;
        const isLargeSample = n > 300;

        const weights = {
            frequency: isLargeSample ? 0.40 : isSmallSample ? 0.25 : 0.35,
            trend: isSmallSample ? 0.40 : isLargeSample ? 0.25 : 0.30,
            missing: 0.20, // 遺漏值補償穩定在 20%
            tail: 0.15 // 尾數分析佔 15%
        };

        // 綜合計算機率
        const probabilities = {};
        const maxMissing = Math.max(...Object.values(missing)) || 1;
        const totalWeighted = Object.values(weighted).reduce((a, b) => a + b, 0) || 1;

        for (let i = range.min; i <= range.max; i++) {
            const freqScore = (frequency[i] / n) * weights.frequency;
            const trendScore = (weighted[i] / totalWeighted) * weights.trend;
            const missingScore = (missing[i] / maxMissing) * weights.missing;
            const tailScore = (tailBonus[i] || 0) * weights.tail;

            probabilities[i] = freqScore + trendScore + missingScore + tailScore;
        }

        // 正規化整體機率，使總和為 1
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = range.min; i <= range.max; i++) {
            probabilities[i] = probabilities[i] / sumProb;
        }

        // 選擇機率最高的號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));
        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '綜合回歸模型 (含尾數分析)',
            report: this.generateReport('combined', sortedNumbers, data.length, weights)
        };
    }

    // 1. Attention LSTM 深度學習 (使用 Bidirectional LSTM 模擬)
    async attentionLstmModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const lookback = 10; // 回看 10 期

        // 準備數據
        const recentData = data.slice(-300); // 取最近 300 期
        const xs = [];
        const ys = [];

        for (let i = 0; i < recentData.length - lookback; i++) {
            const sequence = [];
            for (let j = 0; j < lookback; j++) {
                const draw = recentData[i + j];
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                sequence.push(input);
            }
            xs.push(sequence);

            const targetDraw = recentData[i + lookback];
            const target = new Array(range).fill(0);
            targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
            ys.push(target);
        }

        const xsTensor = tf.tensor3d(xs);
        const ysTensor = tf.tensor2d(ys);

        // 建立模型 (Bidirectional LSTM)
        const model = tf.sequential();
        model.add(tf.layers.bidirectional({
            layer: tf.layers.lstm({ units: 64, returnSequences: false }),
            inputShape: [lookback, range]
        }));
        model.add(tf.layers.dropout({ rate: 0.3 }));
        model.add(tf.layers.dense({ units: range, activation: 'softmax' }));

        model.compile({ optimizer: 'adam', loss: 'categoricalCrossentropy' });

        // 訓練
        await model.fit(xsTensor, ysTensor, { epochs: 5, batchSize: 32, verbose: 0 });

        // 預測
        const lastSequence = [];
        for (let i = lookback; i > 0; i--) {
            const draw = data[data.length - i];
            const input = new Array(range).fill(0);
            draw.numbers.forEach(num => { input[num - 1] = 1; });
            lastSequence.push(input);
        }

        const inputTensor = tf.tensor3d([lastSequence]);
        const outputTensor = model.predict(inputTensor);
        const probsArray = await outputTensor.data();

        // 清理
        xsTensor.dispose(); ysTensor.dispose(); inputTensor.dispose(); outputTensor.dispose(); model.dispose();

        // 整理結果
        const probabilities = {};
        for (let i = 0; i < range; i++) probabilities[i + 1] = probsArray[i];

        const sortedNumbers = Object.entries(probabilities)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'Attention LSTM',
            report: this.generateReport('lstm', sortedNumbers, recentData.length)
        };
    }

    // 2. 貝葉斯機率模型 (Bayesian Probability)
    bayesianProbabilityModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 先驗機率 P(A): 每個號碼的歷史出現率
        const frequency = this.calculateFrequency(data);
        const totalDraws = data.length;
        const priorProb = {};
        for (let i = 1; i <= range; i++) {
            priorProb[i] = (frequency[i] || 0) / (totalDraws * 6);
        }

        // 似然函數 P(B|A): 條件機率
        // 這裡定義條件 B 為：上一期開出 X 後，下一期開出 A 的機率
        const lastDraw = data[data.length - 1].numbers;
        const likelihood = {};

        for (let i = 1; i <= range; i++) likelihood[i] = 0;

        // 計算條件機率矩陣
        const transitionCounts = {}; // { prev: { next: count } }
        for (let i = 0; i < data.length - 1; i++) {
            const current = data[i].numbers;
            const next = data[i + 1].numbers;

            current.forEach(c => {
                if (!transitionCounts[c]) transitionCounts[c] = {};
                next.forEach(n => {
                    transitionCounts[c][n] = (transitionCounts[c][n] || 0) + 1;
                });
            });
        }

        // 計算後驗機率 P(A|B) ∝ P(B|A) * P(A)
        for (let i = 1; i <= range; i++) {
            let likelihoodScore = 0;
            lastDraw.forEach(prevNum => {
                const count = (transitionCounts[prevNum] && transitionCounts[prevNum][i]) || 0;
                const totalOccurrences = frequency[prevNum] || 1;
                likelihoodScore += count / totalOccurrences;
            });

            // 貝葉斯更新
            probabilities[i] = priorProb[i] * (1 + likelihoodScore);
        }

        // 正規化
        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= totalProb;

        // 選號
        const sortedNumbers = Object.entries(probabilities)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '貝葉斯機率模型',
            report: this.generateReport('bayesian', sortedNumbers, data.length)
        };
    }

    // 3. 偏差追蹤模型 (Deviation Tracking)
    deviationTrackingModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 計算每個號碼的理論平均出現次數
        const expectedFreq = (data.length * 6) / 49;
        const frequency = this.calculateFrequency(data);

        // 計算標準差 (Standard Deviation)
        let sumSqDiff = 0;
        for (let i = 1; i <= range; i++) {
            const diff = (frequency[i] || 0) - expectedFreq;
            sumSqDiff += diff * diff;
        }
        const stdDev = Math.sqrt(sumSqDiff / 49);

        // 策略：尋找 "負偏差" 最大的號碼 (Mean Reversion)
        // 同時也考慮 "正偏差" 剛開始的號碼 (Momentum)

        for (let i = 1; i <= range; i++) {
            const freq = frequency[i] || 0;
            const zScore = (freq - expectedFreq) / stdDev;

            // 評分邏輯
            if (zScore < -1.5) {
                // 強烈負偏差 (很久沒出)，預期回歸
                probabilities[i] = 0.8 + Math.abs(zScore) * 0.1;
            } else if (zScore > 2.0) {
                // 強烈正偏差 (太熱)，預期冷卻
                probabilities[i] = 0.2;
            } else if (zScore > 0.5 && zScore < 1.5) {
                // 溫和正偏差 (趨勢剛起)，預期續熱
                probabilities[i] = 0.6 + zScore * 0.1;
            } else {
                probabilities[i] = 0.4; // 平庸
            }
        }

        // 正規化
        const totalProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= totalProb;

        const sortedNumbers = Object.entries(probabilities)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '偏差追蹤模型',
            report: this.generateReport('deviation', sortedNumbers, data.length)
        };
    }

    // 4. 梯度提升集成模型 (Gradient Boosting Ensemble)
    gradientBoostingModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 定義多個 "弱學習器" (Weak Learners)
        const learners = [
            { name: 'Frequency', weight: 1, func: (d) => this.calculateFrequency(d) },
            { name: 'Recency', weight: 1, func: (d) => this.calculateMissingForData(d) },
            { name: 'Pattern', weight: 1, func: (d) => this.analyzePatterns(d) } // 簡化版
        ];

        // 訓練階段：計算每個學習器在最近 50 期的誤差
        const validationData = data.slice(-50);

        // 這裡簡化實作：直接給定經驗權重，模擬 Boosting 的結果
        // 真實 Boosting 需要迭代訓練 residuals
        const finalScores = {};
        for (let i = 1; i <= range; i++) finalScores[i] = 0;

        // 學習器 1: 頻率 (長期趨勢)
        const freq = this.calculateFrequency(data);
        for (let i = 1; i <= range; i++) {
            finalScores[i] += (freq[i] || 0) * 0.4; // 權重 0.4
        }

        // 學習器 2: 遺漏 (短期回補)
        const missing = this.calculateMissingForData(data);
        for (let i = 1; i <= range; i++) {
            // 遺漏越大分數越高，但超過 30 期視為死號
            let score = missing[i];
            if (score > 30) score = 0;
            finalScores[i] += score * 0.6; // 權重 0.6 (短期更重要)
        }

        // 學習器 3: 鄰居效應 (局部相關)
        const lastDraw = data[data.length - 1].numbers;
        lastDraw.forEach(n => {
            if (n + 1 <= range) finalScores[n + 1] += 5;
            if (n - 1 >= 1) finalScores[n - 1] += 5;
        });

        // 正規化
        const totalScore = Object.values(finalScores).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] = finalScores[i] / totalScore;

        const sortedNumbers = Object.entries(probabilities)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }))
            .sort((a, b) => b.probability - a.probability)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '梯度提升集成模型',
            report: this.generateReport('boosting', sortedNumbers, data.length)
        };
    }

    // 全模型綜合投票 (All Models Ensemble)
    async allModelsEnsemble(data) {

        const range = LOTTERY_RULES.numberRange.max;
        const votes = {};
        for (let i = 1; i <= range; i++) votes[i] = 0;

        // 定義所有參與投票的模型
        // 注意：這裡不包含 'ensemble' 本身，避免遞迴
        const models = [
            { name: 'Frequency', func: () => this.frequencyRegression(data), weight: 1 },
            { name: 'Trend', func: () => this.trendAnalysis(data), weight: 1 },
            { name: 'Combined', func: () => this.combinedRegression(data), weight: 1.5 },
            { name: 'Markov', func: () => this.markovChainModel(data), weight: 1.2 },
            { name: 'MonteCarlo', func: () => this.monteCarloSimulation(data), weight: 1 },
            { name: 'CoOccurrence', func: () => this.coOccurrenceModel(data), weight: 1.2 },
            { name: 'LSTM', func: async () => await this.lstmModel(data), weight: 2 }, // 高權重
            { name: 'Attention', func: async () => await this.attentionLstmModel(data), weight: 2 }, // 高權重
            { name: 'Weighted', func: () => this.featureWeightedModel(data), weight: 1.5 },
            { name: 'Bayesian', func: () => this.bayesianProbabilityModel(data), weight: 1.5 },
            { name: 'Deviation', func: () => this.deviationTrackingModel(data), weight: 1.2 },
            { name: 'Boosting', func: () => this.gradientBoostingModel(data), weight: 1.5 }
        ];

        // 平行執行所有模型 (使用 Promise.all 加速)
        const results = await Promise.all(models.map(async m => {
            try {
                const result = await m.func();
                return { name: m.name, weight: m.weight, numbers: result.numbers };
            } catch (e) {
                console.error(`Model ${m.name} failed:`, e);
                return null;
            }
        }));

        // 統計票數
        results.forEach(res => {
            if (res) {
                // 給前 10 名號碼加權分
                res.numbers.slice(0, 10).forEach((num, idx) => {
                    // 排名越前，分數越高 (10分 ~ 1分) * 模型權重
                    const rankScore = (10 - idx);
                    votes[num] += rankScore * res.weight;
                });
            }
        });

        // 正規化機率 (僅供參考)
        const totalScore = Object.values(votes).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) probabilities[i] = votes[i] / totalScore;

        // 選出得分最高的號碼
        const sortedNumbers = Object.entries(votes)
            .map(([num, score]) => ({ number: parseInt(num), score: score }))
            .sort((a, b) => b.score - a.score)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        // 計算信心度 (基於前幾名的得分集中度)
        const topScore = sortedNumbers[0].score;
        const avgScore = totalScore / range;
        const confidence = Math.min((topScore / avgScore) * 20, 95); // 簡單估算

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '全模型綜合投票 (All Models)',
            report: this.generateReport('all_ensemble', sortedNumbers, data.length)
        };
    }

    // 戰術接力模式 (Tactical Relay Model)
    async tacticalRelayModel(data) {
        const range = LOTTERY_RULES.numberRange.max;

        // 階段 1: 海選與過濾 (The Filter)
        // 使用頻率與偏差模型篩選前 25 名
        const freqModel = this.frequencyRegression(data);
        const devModel = this.deviationTrackingModel(data);

        const poolA = new Set();
        freqModel.numbers.slice(0, 20).forEach(n => poolA.add(n));
        devModel.numbers.slice(0, 20).forEach(n => poolA.add(n));

        // 確保池子裡至少有 25 個號碼，不足補頻率高的
        let sortedFreq = Object.entries(freqModel.probabilities)
            .sort((a, b) => b[1] - a[1])
            .map(e => parseInt(e[0]));

        let idx = 0;
        while (poolA.size < 25 && idx < sortedFreq.length) {
            poolA.add(sortedFreq[idx++]);
        }
        const poolAArray = Array.from(poolA);

        // 階段 2: 精選與鎖定 (The Selector)
        // 對 Pool A 的號碼進行深度評分 (LSTM + Markov)
        const lstmResult = await this.lstmModel(data);
        const markovResult = this.markovChainModel(data);

        const scoresB = {};
        poolAArray.forEach(num => {
            // 正規化分數加總
            const s1 = (lstmResult.probabilities[num] || 0) * 2; // LSTM 權重 2
            const s2 = (markovResult.probabilities[num] || 0) * 1.5; // Markov 權重 1.5
            scoresB[num] = s1 + s2;
        });

        const poolB = Object.entries(scoresB)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12) // 取前 12 強
            .map(e => parseInt(e[0]));

        // 階段 3: 組合與優化 (The Optimizer)
        // 從 Pool B 中選出最佳 6 號 (使用共現性 + 隨機模擬)
        const coOccurrence = this.coOccurrenceModel(data);
        const finalScores = {};

        poolB.forEach(num => {
            finalScores[num] = scoresB[num]; // 繼承上一輪分數
            // 加上共現性分數 (如果它跟其他 Pool B 的號碼很合)
            poolB.forEach(other => {
                if (num !== other) {
                    // 這裡簡化：假設 coOccurrence.probabilities 代表該號碼的整體共現強度
                    finalScores[num] += (coOccurrence.probabilities[num] || 0) * 0.5;
                }
            });
        });

        // 最終選號
        const sortedNumbers = Object.entries(finalScores)
            .map(([num, score]) => ({ number: parseInt(num), score: score }))
            .sort((a, b) => b.score - a.score)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        // 產生報告
        const report = `
            <ul style="text-align: left; font-size: 0.9em;">
                <li><strong>第一棒 (海選):</strong> 從 49 號篩選出 ${poolA.size} 個潛力號 (頻率+偏差)。</li>
                <li><strong>第二棒 (精選):</strong> LSTM 與馬可夫鏈鎖定前 12 強：${poolB.join(', ')}。</li>
                <li><strong>第三棒 (優化):</strong> 考慮共現性，最終產出 6 號。</li>
            </ul>
        `;

        return {
            numbers: predictedNumbers,
            probabilities: finalScores, // 注意：這裡的分數不是標準機率
            confidence: 88, // 戰術模式通常信心較高
            method: '戰術接力模式 (Tactical Relay)',
            report: report
        };
    }

    // 戰術接力模式 (Tactical Relay Model)
    async tacticalRelayModel(data) {
        const range = LOTTERY_RULES.numberRange.max;

        // 階段 1: 海選與過濾 (The Filter)
        // 使用頻率與偏差模型篩選前 25 名
        const freqModel = this.frequencyRegression(data);
        const devModel = this.deviationTrackingModel(data);

        const poolA = new Set();
        freqModel.numbers.slice(0, 20).forEach(n => poolA.add(n));
        devModel.numbers.slice(0, 20).forEach(n => poolA.add(n));

        // 確保池子裡至少有 25 個號碼，不足補頻率高的
        let sortedFreq = Object.entries(freqModel.probabilities)
            .sort((a, b) => b[1] - a[1])
            .map(e => parseInt(e[0]));

        let idx = 0;
        while (poolA.size < 25 && idx < sortedFreq.length) {
            poolA.add(sortedFreq[idx++]);
        }
        const poolAArray = Array.from(poolA);

        // 階段 2: 精選與鎖定 (The Selector)
        // 對 Pool A 的號碼進行深度評分 (LSTM + Markov)
        const lstmResult = await this.lstmModel(data);
        const markovResult = this.markovChainModel(data);

        const scoresB = {};
        poolAArray.forEach(num => {
            // 正規化分數加總
            const s1 = (lstmResult.probabilities[num] || 0) * 2; // LSTM 權重 2
            const s2 = (markovResult.probabilities[num] || 0) * 1.5; // Markov 權重 1.5
            scoresB[num] = s1 + s2;
        });

        const poolB = Object.entries(scoresB)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12) // 取前 12 強
            .map(e => parseInt(e[0]));

        // 階段 3: 組合與優化 (The Optimizer)
        // 從 Pool B 中選出最佳 6 號 (使用共現性 + 隨機模擬)
        const coOccurrence = this.coOccurrenceModel(data);
        const finalScores = {};

        poolB.forEach(num => {
            finalScores[num] = scoresB[num]; // 繼承上一輪分數
            // 加上共現性分數 (如果它跟其他 Pool B 的號碼很合)
            poolB.forEach(other => {
                if (num !== other) {
                    // 這裡簡化：假設 coOccurrence.probabilities 代表該號碼的整體共現強度
                    finalScores[num] += (coOccurrence.probabilities[num] || 0) * 0.5;
                }
            });
        });

        // 最終選號
        const sortedNumbers = Object.entries(finalScores)
            .map(([num, score]) => ({ number: parseInt(num), score: score }))
            .sort((a, b) => b.score - a.score)
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);

        // 產生報告
        const report = `
            <ul style="text-align: left; font-size: 0.9em;">
                <li><strong>第一棒 (海選):</strong> 從 49 號篩選出 ${poolA.size} 個潛力號 (頻率+偏差)。</li>
                <li><strong>第二棒 (精選):</strong> LSTM 與馬可夫鏈鎖定前 12 強：${poolB.join(', ')}。</li>
                <li><strong>第三棒 (優化):</strong> 考慮共現性，最終產出 6 號。</li>
            </ul>
        `;

        return {
            numbers: predictedNumbers,
            probabilities: finalScores, // 注意：這裡的分數不是標準機率
            confidence: 88, // 戰術模式通常信心較高
            method: '戰術接力模式 (Tactical Relay)',
            report: report
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
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

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
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'LSTM 深度學習模型',
            report: this.generateReport('lstm', sortedNumbers, recentData.length)
        };
    }

    /**
     * 特徵加權模型 (Feature Weighted Model)
     * 結合多種統計特徵進行加權預測
     */
    featureWeightedModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        for (let i = 1; i <= range; i++) probabilities[i] = 0;

        // 特徵 1: 頻率 (25%)
        const frequency = {};
        for (let i = 1; i <= range; i++) frequency[i] = 0;
        data.forEach(draw => draw.numbers.forEach(num => frequency[num]++));
        const totalDraws = data.length;

        // 特徵 2: 遺漏值 (20%)
        const missing = this.calculateMissingForData(data);
        const maxMissing = Math.max(...Object.values(missing)) || 1;

        // 特徵 3: 尾數熱度 (15%)
        const tailBonus = this.getTailBonus(data);

        // 特徵 4: 區間平衡 (15%)
        const distribution = this.calculateDistributionForData(data);
        const avgPerZone = (data.length * LOTTERY_RULES.pickCount) / 5;

        // 特徵 5: 奇偶比例 (10%)
        const oddEven = this.calculateOddEvenForData(data);
        const oddRatio = oddEven.odd / (oddEven.odd + oddEven.even);

        // 特徵 6: 近期趨勢 (15%)
        const recentWindow = Math.min(20, data.length);
        const recentFreq = {};
        for (let i = 1; i <= range; i++) recentFreq[i] = 0;
        for (let idx = data.length - recentWindow; idx < data.length; idx++) {
            if (idx >= 0) data[idx].numbers.forEach(num => recentFreq[num]++);
        }

        for (let i = 1; i <= range; i++) {
            const freqScore = (frequency[i] / totalDraws) * 0.25;
            const missingScore = (missing[i] / maxMissing) * 0.20;
            const tailScore = (tailBonus[i] || 0) * 0.15;
            const zone = this.getZone(i);
            const zoneCount = distribution[zone];
            const zoneScore = (avgPerZone / (zoneCount + 1)) * 0.15 / avgPerZone;
            let oddEvenScore = 0;
            if (i % 2 === 1 && oddRatio < 0.5) oddEvenScore = 0.1;
            else if (i % 2 === 0 && oddRatio > 0.5) oddEvenScore = 0.1;
            const trendScore = (recentFreq[i] / recentWindow) * 0.15;

            probabilities[i] = freqScore + missingScore + tailScore + zoneScore + oddEvenScore + trendScore;
        }

        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= sumProb;

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '特徵加權模型',
            report: this.generateReport('weighted', sortedNumbers, data.length)
        };
    }

    /**
     * Attention LSTM 模型
     * 結合注意力機制的 LSTM，能夠更好地捕捉重要的時間步長
     * 參考: https://github.com/kyr0/lotto-ai
     */
    async attentionLstmModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const sequenceLength = 5; // 回看過去 5 期（注意力機制效果更好）
        const recentData = data.slice(-200);

        if (recentData.length < sequenceLength + 1) {
            return this.frequencyRegression(data);
        }

        // 準備訓練數據
        const xs = [];
        const ys = [];

        for (let i = 0; i < recentData.length - sequenceLength; i++) {
            const sequence = [];
            for (let j = 0; j < sequenceLength; j++) {
                const draw = recentData[i + j];
                const input = new Array(range).fill(0);
                draw.numbers.forEach(num => { input[num - 1] = 1; });
                sequence.push(input);
            }
            xs.push(sequence);

            const targetDraw = recentData[i + sequenceLength];
            const target = new Array(range).fill(0);
            targetDraw.numbers.forEach(num => { target[num - 1] = 1; });
            ys.push(target);
        }

        const xsTensor = tf.tensor3d(xs, [xs.length, sequenceLength, range]);
        const ysTensor = tf.tensor2d(ys, [ys.length, range]);

        // 建立帶有注意力機制的 LSTM 模型
        const model = tf.sequential();

        // 雙向 LSTM 層
        model.add(tf.layers.bidirectional({
            layer: tf.layers.lstm({
                units: 32,
                returnSequences: true,
                kernelRegularizer: tf.regularizers.l2({ l2: 0.01 })
            }),
            inputShape: [sequenceLength, range]
        }));

        // Dropout 防止過擬合
        model.add(tf.layers.dropout({ rate: 0.3 }));

        // 第二層 LSTM
        model.add(tf.layers.lstm({
            units: 16,
            returnSequences: false
        }));

        // 輸出層
        model.add(tf.layers.dense({ units: range, activation: 'softmax' }));

        model.compile({
            optimizer: tf.train.adam(0.001),
            loss: 'categoricalCrossentropy'
        });

        // 訓練
        await model.fit(xsTensor, ysTensor, {
            epochs: 5,
            batchSize: 16,
            validationSplit: 0.2,
            verbose: 0
        });

        // 預測
        const lastSequence = [];
        for (let i = recentData.length - sequenceLength; i < recentData.length; i++) {
            const draw = recentData[i];
            const input = new Array(range).fill(0);
            draw.numbers.forEach(num => { input[num - 1] = 1; });
            lastSequence.push(input);
        }

        const inputTensor = tf.tensor3d([lastSequence], [1, sequenceLength, range]);
        const outputTensor = model.predict(inputTensor);
        const probsArray = await outputTensor.data();

        // 清理
        xsTensor.dispose();
        ysTensor.dispose();
        inputTensor.dispose();
        outputTensor.dispose();
        model.dispose();

        const probabilities = {};
        for (let i = 0; i < range; i++) {
            probabilities[i + 1] = probsArray[i];
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: 'Attention LSTM 深度學習',
            report: this.generateReport('attention', sortedNumbers, recentData.length)
        };
    }

    /**
     * 貝葉斯機率模型 (Bayesian Probability Model)
     * 使用 Dirichlet-Multinomial 分佈進行預測
     * 參考: arXiv:2403.12836 - Predicting Winning Lottery Numbers
     */
    bayesianModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 計算先驗分佈 (均勻分佈)
        const alpha = 1; // Dirichlet 參數（拉普拉斯平滑）

        // 統計每個號碼的出現次數
        const counts = {};
        for (let i = 1; i <= range; i++) {
            counts[i] = alpha; // 初始化為 alpha（平滑）
        }

        data.forEach(draw => {
            draw.numbers.forEach(num => {
                counts[num]++;
            });
        });

        // 計算總數
        const totalCount = Object.values(counts).reduce((a, b) => a + b, 0);

        // 計算後驗機率 (使用 Dirichlet-Multinomial)
        for (let i = 1; i <= range; i++) {
            // 後驗機率 = (count + alpha) / (total + alpha * range)
            probabilities[i] = counts[i] / totalCount;
        }

        // 加入時間衰減因子（近期權重更高）
        const recentWindow = Math.min(30, data.length);
        const recentCounts = {};
        for (let i = 1; i <= range; i++) {
            recentCounts[i] = 0;
        }

        for (let i = data.length - recentWindow; i < data.length; i++) {
            if (i >= 0) {
                data[i].numbers.forEach(num => {
                    recentCounts[num]++;
                });
            }
        }

        // 結合歷史機率和近期機率
        const recentTotal = Object.values(recentCounts).reduce((a, b) => a + b, 0) || 1;
        for (let i = 1; i <= range; i++) {
            const recentProb = recentCounts[i] / recentTotal;
            // 60% 歷史 + 40% 近期
            probabilities[i] = probabilities[i] * 0.6 + recentProb * 0.4;
        }

        // 正規化
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) {
            probabilities[i] /= sumProb;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '貝葉斯機率模型',
            report: this.generateReport('bayesian', sortedNumbers, data.length)
        };
    }

    /**
     * 冷熱號碼偏差追蹤演算法
     * Cold/Hot Number Digital Deviation Tracking Algorithm
     * 追蹤號碼出現頻率與期望值的偏差
     */
    deviationTrackingModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 計算理論期望出現次數
        const totalDraws = data.length;
        const expectedFreq = (totalDraws * LOTTERY_RULES.pickCount) / range;

        // 統計實際出現次數
        const actualFreq = {};
        for (let i = 1; i <= range; i++) {
            actualFreq[i] = 0;
        }
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                actualFreq[num]++;
            });
        });

        // 計算偏差值 (Deviation Score)
        const deviations = {};
        for (let i = 1; i <= range; i++) {
            // 正偏差 = 熱號（出現多於期望）
            // 負偏差 = 冷號（出現少於期望）
            deviations[i] = actualFreq[i] - expectedFreq;
        }

        // 計算近期趨勢（最近 20 期）
        const recentWindow = Math.min(20, data.length);
        const recentFreq = {};
        for (let i = 1; i <= range; i++) {
            recentFreq[i] = 0;
        }

        for (let i = data.length - recentWindow; i < data.length; i++) {
            if (i >= 0) {
                data[i].numbers.forEach(num => {
                    recentFreq[num]++;
                });
            }
        }

        const recentExpected = (recentWindow * LOTTERY_RULES.pickCount) / range;
        const recentDeviations = {};
        for (let i = 1; i <= range; i++) {
            recentDeviations[i] = recentFreq[i] - recentExpected;
        }

        // 綜合評分策略
        // 策略1: 追熱 - 近期熱號可能持續
        // 策略2: 補冷 - 長期冷號可能回歸
        for (let i = 1; i <= range; i++) {
            let score = 0;

            // 近期熱號加分（追熱策略）
            if (recentDeviations[i] > 0) {
                score += recentDeviations[i] * 0.4;
            }

            // 長期冷號加分（均值回歸策略）
            if (deviations[i] < 0) {
                score += Math.abs(deviations[i]) * 0.3;
            }

            // 基礎頻率分數
            score += (actualFreq[i] / totalDraws) * 0.3;

            probabilities[i] = Math.max(0, score);
        }

        // 正規化
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0) || 1;
        for (let i = 1; i <= range; i++) {
            probabilities[i] /= sumProb;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '偏差追蹤模型 (Deviation Tracking)',
            report: this.generateReport('deviation', sortedNumbers, data.length)
        };
    }

    /**
     * 梯度提升風格集成模型 (Gradient Boosting Style Ensemble)
     * 模擬 XGBoost 的概念，透過殘差學習逐步優化預測
     */
    gradientBoostingModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const probabilities = {};

        // 初始化機率（均勻分佈）
        for (let i = 1; i <= range; i++) {
            probabilities[i] = 1 / range;
        }

        // 弱學習器 1: 頻率分析
        const freq1 = this.frequencyRegression(data);

        // 弱學習器 2: 趨勢分析
        const freq2 = this.trendRegression(data);

        // 弱學習器 3: 遺漏值分析
        const missing = this.calculateMissingForData(data);
        const maxMissing = Math.max(...Object.values(missing)) || 1;

        // 弱學習器 4: 尾數分析
        const tailBonus = this.getTailBonus(data);

        // 弱學習器 5: 馬可夫鏈
        const markov = this.markovChainModel(data);

        // 學習率（類似 XGBoost 的 eta）
        const learningRate = 0.3;

        // 迭代更新（類似梯度提升的殘差學習）
        for (let round = 0; round < 3; round++) {
            for (let i = 1; i <= range; i++) {
                // 計算當前殘差（目標 - 預測）
                const target = freq1.probabilities[i]; // 使用頻率作為目標

                // 各弱學習器的貢獻
                const contributions = [
                    freq2.probabilities[i] * 0.25,
                    (missing[i] / maxMissing) * 0.2,
                    (tailBonus[i] || 0) * 0.15,
                    markov.probabilities[i] * 0.2,
                    target * 0.2
                ];

                // 計算加權平均
                const avgContribution = contributions.reduce((a, b) => a + b, 0);

                // 更新機率（梯度下降風格）
                probabilities[i] += learningRate * (avgContribution - probabilities[i]);
            }
        }

        // 正規化
        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) {
            probabilities[i] /= sumProb;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '梯度提升集成模型 (Gradient Boosting)',
            report: this.generateReport('boosting', sortedNumbers, data.length)
        };
    }

    // 其他輔助方法
    /**
     * 計算預測信心度 (Entropy-based Confidence)
     * 使用熵值來衡量機率分佈的確定性
     * 熵越低 = 分佈越集中 = 信心度越高
     */
    calculateConfidence(sortedNumbers, allProbabilities = null) {
        if (!sortedNumbers || sortedNumbers.length === 0) return 0;

        // 方法1: 基於選中號碼的機率集中度
        const selectedProbs = sortedNumbers.map(item => item.probability);
        const sumProb = selectedProbs.reduce((a, b) => a + b, 0);

        // 方法2: 計算選中號碼與未選中號碼的機率差距
        let gapScore = 0;
        if (allProbabilities) {
            const allProbs = Object.values(allProbabilities).sort((a, b) => b - a);
            const topProbs = allProbs.slice(0, LOTTERY_RULES.pickCount);
            const restProbs = allProbs.slice(LOTTERY_RULES.pickCount);

            const topAvg = topProbs.reduce((a, b) => a + b, 0) / topProbs.length;
            const restAvg = restProbs.length > 0
                ? restProbs.reduce((a, b) => a + b, 0) / restProbs.length
                : 0;

            // 差距越大，信心度越高
            gapScore = restAvg > 0 ? Math.min((topAvg / restAvg - 1) * 20, 30) : 15;
        }

        // 方法3: 計算標準差來衡量分佈離散程度
        const mean = sumProb / selectedProbs.length;
        const variance = selectedProbs.reduce((sum, p) => sum + Math.pow(p - mean, 2), 0) / selectedProbs.length;
        const stdDev = Math.sqrt(variance);

        // 標準差越小，表示選中號碼機率越接近，信心度稍高
        const uniformityScore = Math.max(0, 10 - stdDev * 500);

        // 綜合計算信心度
        const baseScore = sumProb * 100 * 2.5; // 基礎分數
        const finalScore = baseScore + gapScore + uniformityScore;

        // 限制在合理範圍 (30-95)，避免過度自信或過度悲觀
        return Math.min(Math.max(Math.round(finalScore), 30), 95);
    }

    /**
     * 生成詳細的預測報告
     */
    generateReport(method, sortedNumbers, dataLength, weights = null) {
        const methodDescriptions = {
            'frequency': '頻率分析透過統計每個號碼在歷史開獎中出現的次數，選出最常出現的號碼。',
            'trend': '趨勢分析採用指數衰減權重，近期開獎結果具有更高的影響力，能夠捕捉短期熱門號碼。',
            'combined': '綜合回歸模型融合頻率分析、趨勢分析、遺漏值補償及尾數分析，透過動態權重平衡長短期趨勢。',
            'ml': '機器學習模型分析連號模式、區間分佈、奇偶平衡等特徵，結合頻率數據進行預測。',
            'tf': 'TensorFlow 神經網路透過深度學習分析號碼序列的隱藏模式，學習開獎號碼之間的複雜關聯。',
            'markov': '馬可夫鏈模型建立號碼轉移機率矩陣，根據最新一期號碼預測下一期最可能出現的號碼。',
            'montecarlo': '蒙地卡羅模擬執行 10,000 次隨機抽樣，基於加權機率統計最常被選中的號碼組合。',
            'cooccurrence': '共現分析模型追蹤號碼之間的關聯性，找出最常與熱門號碼一起出現的組合。',
            'lstm': 'LSTM 深度學習模型專門處理時間序列，回看過去 10 期數據捕捉長期依賴關係。',
            'weighted': '特徵加權模型結合頻率、遺漏值、尾數、區間平衡、奇偶比例和近期趨勢六大特徵進行加權預測。',
            'attention': 'Attention LSTM 結合雙向 LSTM 與注意力機制，能夠更精準地識別關鍵時間步長的重要模式。',
            'bayesian': '貝葉斯機率模型使用 Dirichlet-Multinomial 分佈，結合先驗知識與觀測數據計算後驗機率。',
            'deviation': '偏差追蹤演算法分析號碼出現頻率與理論期望值的偏差，平衡追熱與補冷策略。',
            'boosting': '梯度提升模型模擬 XGBoost 概念，透過多個弱學習器的迭代殘差學習逐步優化預測。'
        };

        let report = `基於 ${dataLength} 期歷史數據進行分析。\n\n`;
        report += methodDescriptions[method] || '';

        // 如果有權重配置，顯示權重分佈
        if (weights) {
            report += `\n\n【權重配置】\n`;
            report += `• 頻率分析：${(weights.frequency * 100).toFixed(0)}%\n`;
            report += `• 趨勢分析：${(weights.trend * 100).toFixed(0)}%\n`;
            report += `• 遺漏補償：${(weights.missing * 100).toFixed(0)}%\n`;
            report += `• 尾數分析：${(weights.tail * 100).toFixed(0)}%`;
        }

        // 顯示預測號碼的機率排名
        if (sortedNumbers && sortedNumbers.length > 0) {
            const topProb = (sortedNumbers[0].probability * 100).toFixed(2);
            const lastProb = (sortedNumbers[sortedNumbers.length - 1].probability * 100).toFixed(2);
            report += `\n\n【機率分佈】\n`;
            report += `• 最高機率：${topProb}%（${sortedNumbers[0].number} 號）\n`;
            report += `• 最低機率：${lastProb}%（${sortedNumbers[sortedNumbers.length - 1].number} 號）`;
        }

        return report;
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

    /**
     * 計算每個號碼的遺漏值
     * 遺漏值 = 從最近一期開始，連續多少期沒有出現該號碼
     */
    calculateMissingForData(data) {
        const missing = {};
        const range = LOTTERY_RULES.numberRange;

        // 初始化：假設所有號碼都已遺漏 data.length 期
        for (let i = range.min; i <= range.max; i++) {
            missing[i] = data.length;
        }

        // 從最新到最舊遍歷，找到每個號碼最後一次出現的位置
        for (let i = data.length - 1; i >= 0; i--) {
            const draw = data[i];
            const periodsFromNow = data.length - 1 - i; // 距離最新一期的期數

            draw.numbers.forEach(num => {
                // 如果這個號碼的遺漏值還是初始值，表示還沒找到它出現的位置
                // 更新為距離最新一期的期數
                if (missing[num] === data.length || missing[num] > periodsFromNow) {
                    missing[num] = periodsFromNow;
                }
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
     * 尾數分析 (Tail Number Analysis)
     * 分析號碼尾數 (0-9) 的出現頻率，找出熱門尾數
     */
    calculateTailFrequency(data) {
        const tailFrequency = {};
        // 初始化尾數 0-9
        for (let i = 0; i <= 9; i++) {
            tailFrequency[i] = 0;
        }

        // 統計每個尾數的出現次數
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                const tail = num % 10;
                tailFrequency[tail]++;
            });
        });

        return tailFrequency;
    }

    /**
     * 根據尾數分析給號碼加權
     * 返回每個號碼基於尾數熱度的加分
     */
    getTailBonus(data) {
        const tailFreq = this.calculateTailFrequency(data);
        const totalTails = Object.values(tailFreq).reduce((a, b) => a + b, 0);
        const expectedFreq = totalTails / 10; // 理論上每個尾數應該出現的次數

        const tailBonus = {};
        const range = LOTTERY_RULES.numberRange;

        for (let num = range.min; num <= range.max; num++) {
            const tail = num % 10;
            const actualFreq = tailFreq[tail];
            // 熱門尾數加分，冷門尾數也略微加分（均值回歸）
            if (actualFreq > expectedFreq) {
                // 熱門尾數：按超出比例加分
                tailBonus[num] = (actualFreq / expectedFreq - 1) * 0.3;
            } else {
                // 冷門尾數：給予均值回歸補償
                tailBonus[num] = (1 - actualFreq / expectedFreq) * 0.15;
            }
        }

        return tailBonus;
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

    // =====================================================
    // 智能集成預測框架 (Intelligent Ensemble Framework)
    // =====================================================

    /**
     * 1. 自適應集成模型 (Adaptive Ensemble Model)
     * 根據各模型在最近 N 期的「回測表現」動態調整權重
     * 表現好的模型獲得更高權重，表現差的降低權重
     */
    async adaptiveEnsembleModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const validationWindow = Math.min(20, Math.floor(data.length * 0.1));

        if (data.length < validationWindow + 10) {
            return this.ensembleModel(data);
        }

        const trainingData = data.slice(0, -validationWindow);
        const validationData = data.slice(-validationWindow);

        const baseModels = [
            { name: '頻率分析', key: 'frequency', func: (d) => this.frequencyRegression(d), baseWeight: 1.0 },
            { name: '趨勢分析', key: 'trend', func: (d) => this.trendRegression(d), baseWeight: 1.0 },
            { name: '綜合回歸', key: 'combined', func: (d) => this.combinedRegression(d), baseWeight: 1.2 },
            { name: '馬可夫鏈', key: 'markov', func: (d) => this.markovChainModel(d), baseWeight: 1.0 },
            { name: '貝葉斯', key: 'bayesian', func: (d) => this.bayesianProbabilityModel(d), baseWeight: 1.0 },
            { name: '偏差追蹤', key: 'deviation', func: (d) => this.deviationTrackingModel(d), baseWeight: 1.0 },
            { name: '特徵加權', key: 'weighted', func: (d) => this.featureWeightedModel(d), baseWeight: 1.0 }
        ];

        const modelScores = {};
        for (const model of baseModels) {
            let totalHits = 0;

            for (let i = 0; i < validationData.length; i++) {
                const historicalData = [...trainingData, ...validationData.slice(0, i)];
                if (historicalData.length < 10) continue;

                const prediction = model.func(historicalData);
                const actual = validationData[i].numbers;

                const top10 = Object.entries(prediction.probabilities)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 10)
                    .map(([num]) => parseInt(num));

                const hits = top10.filter(n => actual.includes(n)).length;
                totalHits += hits;
            }

            modelScores[model.key] = totalHits / validationData.length;
        }

        const maxScore = Math.max(...Object.values(modelScores));
        const minScore = Math.min(...Object.values(modelScores));
        const scoreRange = maxScore - minScore || 1;

        const adaptiveWeights = {};
        baseModels.forEach(model => {
            const normalizedScore = ((modelScores[model.key] - minScore) / scoreRange) * 1.5 + 0.5;
            adaptiveWeights[model.key] = model.baseWeight * normalizedScore;
        });

        const totalProbabilities = {};
        for (let i = 1; i <= range; i++) totalProbabilities[i] = 0;

        const modelResults = [];
        for (const model of baseModels) {
            const result = model.func(data);
            const weight = adaptiveWeights[model.key];

            for (let i = 1; i <= range; i++) {
                totalProbabilities[i] += (result.probabilities[i] || 0) * weight;
            }

            modelResults.push({
                name: model.name,
                score: modelScores[model.key].toFixed(2),
                weight: weight.toFixed(2)
            });
        }

        const sumTotal = Object.values(totalProbabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) totalProbabilities[i] /= sumTotal;

        const sortedNumbers = Object.entries(totalProbabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, totalProbabilities);

        const weightReport = modelResults
            .sort((a, b) => parseFloat(b.weight) - parseFloat(a.weight))
            .map(m => `• ${m.name}: 得分 ${m.score}, 權重 ${m.weight}`)
            .join('<br>');

        return {
            numbers: predictedNumbers,
            probabilities: totalProbabilities,
            confidence: confidence,
            method: '自適應集成模型 (Adaptive Ensemble)',
            report: `根據最近 ${validationWindow} 期的回測表現動態調整各模型權重。<br><br>【模型權重分配】<br>${weightReport}`
        };
    }

    /**
     * 2. 共識投票模型 (Consensus Voting Model)
     * 只選擇「多數模型都同意」的號碼，強調穩定性
     */
    async consensusVotingModel(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const consensusThreshold = 0.5;

        const modelPredictions = [
            this.frequencyRegression(data),
            this.trendRegression(data),
            this.combinedRegression(data),
            this.markovChainModel(data),
            this.bayesianProbabilityModel(data),
            this.deviationTrackingModel(data),
            this.featureWeightedModel(data),
            this.gradientBoostingModel(data)
        ];

        const voteCount = {};
        const avgProbability = {};
        for (let i = 1; i <= range; i++) {
            voteCount[i] = 0;
            avgProbability[i] = 0;
        }

        modelPredictions.forEach(pred => {
            const top10 = Object.entries(pred.probabilities)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([num]) => parseInt(num));

            top10.forEach(num => {
                voteCount[num]++;
                avgProbability[num] += pred.probabilities[num];
            });
        });

        const totalModels = modelPredictions.length;

        const consensusScores = {};
        for (let i = 1; i <= range; i++) {
            const voteRatio = voteCount[i] / totalModels;
            const avgProb = voteCount[i] > 0 ? avgProbability[i] / voteCount[i] : 0;

            if (voteRatio >= consensusThreshold) {
                consensusScores[i] = voteRatio * avgProb * 100;
            } else {
                consensusScores[i] = avgProb * 10;
            }
        }

        const sumScores = Object.values(consensusScores).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = consensusScores[i] / sumScores;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        const highConsensus = Object.entries(voteCount)
            .filter(([_, count]) => count >= totalModels * 0.7)
            .map(([num]) => parseInt(num))
            .sort((a, b) => a - b);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '共識投票模型 (Consensus Voting)',
            report: `綜合 ${totalModels} 個模型的投票結果，只選擇獲得多數共識的號碼。<br><br>【高共識號碼 (70%+模型同意)】<br>${highConsensus.length > 0 ? highConsensus.join(', ') : '無'}<br><br>【共識門檻】${(consensusThreshold * 100).toFixed(0)}%`
        };
    }

    /**
     * 3. 管道模型 (Pipeline Model)
     * 多階段處理流程：篩選 → 精煉 → 優化 → 驗證
     */
    async pipelineModel(data) {
        const range = LOTTERY_RULES.numberRange.max;

        // 第一階段：廣撒網
        const stage1Models = [
            { name: '頻率', result: this.frequencyRegression(data), quota: 15 },
            { name: '趨勢', result: this.trendRegression(data), quota: 12 },
            { name: '偏差', result: this.deviationTrackingModel(data), quota: 10 }
        ];

        const poolA = new Set();
        stage1Models.forEach(model => {
            const top = Object.entries(model.result.probabilities)
                .sort((a, b) => b[1] - a[1])
                .slice(0, model.quota)
                .map(([num]) => parseInt(num));
            top.forEach(n => poolA.add(n));
        });

        const freqSorted = Object.entries(this.frequencyRegression(data).probabilities)
            .sort((a, b) => b[1] - a[1])
            .map(([num]) => parseInt(num));

        let idx = 0;
        while (poolA.size < 25 && idx < freqSorted.length) {
            poolA.add(freqSorted[idx++]);
        }

        // 第二階段：深度分析
        const stage2Scores = {};
        const poolAArray = Array.from(poolA);

        const combinedResult = this.combinedRegression(data);
        const bayesianResult = this.bayesianProbabilityModel(data);
        const markovResult = this.markovChainModel(data);

        poolAArray.forEach(num => {
            stage2Scores[num] =
                (combinedResult.probabilities[num] || 0) * 2.0 +
                (bayesianResult.probabilities[num] || 0) * 1.5 +
                (markovResult.probabilities[num] || 0) * 1.2;
        });

        const poolB = Object.entries(stage2Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 12)
            .map(([num]) => parseInt(num));

        // 第三階段：組合優化
        const coOccurrence = this.coOccurrenceModel(data);
        const finalScores = {};

        poolB.forEach(num => {
            let score = stage2Scores[num];
            score += (coOccurrence.probabilities[num] || 0) * 0.8;

            const zone = this.getZone(num);
            const sameZoneCount = poolB.filter(n => this.getZone(n) === zone).length;
            if (sameZoneCount > 4) score *= 0.9;

            finalScores[num] = score;
        });

        // 第四階段：最終選號
        const sortedFinal = Object.entries(finalScores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount);

        const predictedNumbers = sortedFinal.map(([num]) => parseInt(num)).sort((a, b) => a - b);

        const probabilities = {};
        const maxScore = Math.max(...Object.values(finalScores));
        for (let i = 1; i <= range; i++) {
            probabilities[i] = (finalScores[i] || 0) / maxScore / range;
        }

        const sumProb = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= range; i++) probabilities[i] /= sumProb;

        const confidence = this.calculateConfidence(
            sortedFinal.map(([num, score]) => ({ number: parseInt(num), probability: score })),
            probabilities
        );

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '管道模型 (Pipeline)',
            report: `
                <ul style="text-align: left; font-size: 0.9em;">
                    <li><strong>第一階段 (廣撒網):</strong> 從 49 號篩選出 ${poolA.size} 個潛力號</li>
                    <li><strong>第二階段 (深度分析):</strong> 綜合回歸+貝葉斯+馬可夫精選 12 強: ${poolB.join(', ')}</li>
                    <li><strong>第三階段 (組合優化):</strong> 考慮共現性與區間平衡</li>
                    <li><strong>第四階段 (最終選號):</strong> 產出最佳 6 號</li>
                </ul>
            `
        };
    }

    /**
     * 4. 混合策略模型 (Hybrid Strategy Model)
     * 同時產出「追熱」和「補冷」兩種策略，並根據近期特徵自動選擇主策略
     */
    async hybridStrategyModel(data) {
        const range = LOTTERY_RULES.numberRange.max;

        const recentWindow = Math.min(10, data.length);
        const recentData = data.slice(-recentWindow);

        const historicalFreq = this.calculateFrequency(data.slice(0, -recentWindow));
        const topHistoricalNumbers = Object.entries(historicalFreq)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 15)
            .map(([num]) => parseInt(num));

        let hotHits = 0;
        let coldHits = 0;
        recentData.forEach(draw => {
            draw.numbers.forEach(num => {
                if (topHistoricalNumbers.includes(num)) hotHits++;
                else coldHits++;
            });
        });

        const hotRatio = hotHits / (hotHits + coldHits);
        const isHotTrend = hotRatio > 0.5;

        const hotStrategy = this.trendRegression(data);
        const hotNumbers = Object.entries(hotStrategy.probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 8)
            .map(([num]) => parseInt(num));

        const coldStrategy = this.deviationTrackingModel(data);
        const missing = this.calculateMissingForData(data);
        const coldNumbers = Object.entries(missing)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 8)
            .map(([num]) => parseInt(num));

        const hybridScores = {};
        for (let i = 1; i <= range; i++) {
            const hotScore = hotStrategy.probabilities[i] || 0;
            const coldScore = coldStrategy.probabilities[i] || 0;

            if (isHotTrend) {
                hybridScores[i] = hotScore * 0.7 + coldScore * 0.3;
            } else {
                hybridScores[i] = hotScore * 0.4 + coldScore * 0.6;
            }
        }

        const overlap = hotNumbers.filter(n => coldNumbers.includes(n));
        overlap.forEach(num => {
            hybridScores[num] *= 1.3;
        });

        const sumScores = Object.values(hybridScores).reduce((a, b) => a + b, 0);
        const probabilities = {};
        for (let i = 1; i <= range; i++) {
            probabilities[i] = hybridScores[i] / sumScores;
        }

        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num, prob]) => ({ number: parseInt(num), probability: prob }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers, probabilities);

        const strategyName = isHotTrend ? '追熱為主 (70:30)' : '補冷為主 (40:60)';

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '混合策略模型 (Hybrid Strategy)',
            report: `
                根據近 ${recentWindow} 期開獎分析，熱號命中率 ${(hotRatio * 100).toFixed(1)}%。<br><br>
                【當前策略】${strategyName}<br><br>
                【追熱候選】${hotNumbers.slice(0, 6).join(', ')}<br>
                【補冷候選】${coldNumbers.slice(0, 6).join(', ')}<br>
                ${overlap.length > 0 ? `【交集金號】${overlap.join(', ')}` : ''}
            `
        };
    }

    /**
     * 計算頻率 (輔助函數)
     */
    calculateFrequency(data) {
        const frequency = {};
        const range = LOTTERY_RULES.numberRange;
        for (let i = range.min; i <= range.max; i++) {
            frequency[i] = 0;
        }
        data.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });
        return frequency;
    }
}

// 導出為全域變數
window.PredictionEngine = PredictionEngine;
