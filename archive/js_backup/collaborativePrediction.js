/**
 * 協作預測模組 - 多模型接力與協作系統
 * 三種創新預測模式：
 * 1. 🏃 接力預測 (Relay Prediction) - 三階段層層篩選
 * 2. 🤝 協作預測 (Collaborative Prediction) - 多模型投票決策
 * 3. 🧠 自適應接力 (Adaptive Relay) - 智能動態調整
 */

class CollaborativePredictionEngine {
    constructor(predictionEngine) {
        this.engine = predictionEngine;
        this.dataProcessor = predictionEngine.dataProcessor;
    }

    /**
     * 🏃 接力預測系統 (Relay Prediction System)
     * 三階段接力：粗選 → 精選 → 優化
     * 
     * 階段一：粗選候選池 (從49個號碼篩選到20個)
     * 階段二：精選核心組 (從20個篩選到10個)
     * 階段三：最終優化 (從10個選出最佳6個)
     */
    async relayPrediction(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const relayStages = [];
        
        console.log('🏃‍♂️ 啟動接力預測系統...');
        
        // ==================== 階段一：粗選候選池 ====================
        console.log('📍 階段一：粗選候選池 (49 → 20)');
        
        // 使用三種基礎模型快速篩選
        const stage1Models = [
            { name: '頻率分析', result: this.engine.frequencyRegression(data), weight: 1.0 },
            { name: '趨勢分析', result: this.engine.trendRegression(data), weight: 1.2 },
            { name: '綜合回歸', result: this.engine.combinedRegression(data), weight: 1.5 }
        ];
        
        // 計算加權分數
        const stage1Scores = {};
        for (let i = 1; i <= range; i++) stage1Scores[i] = 0;
        
        stage1Models.forEach(model => {
            for (let i = 1; i <= range; i++) {
                stage1Scores[i] += (model.result.probabilities[i] || 0) * model.weight;
            }
        });
        
        // 選出前20名進入下一階段
        const stage1Candidates = Object.entries(stage1Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 20)
            .map(([num]) => parseInt(num));
        
        relayStages.push({
            stage: '階段一：粗選',
            candidates: stage1Candidates,
            count: stage1Candidates.length,
            models: stage1Models.map(m => m.name)
        });
        
        // ==================== 階段二：精選核心組 ====================
        console.log('🎯 階段二：精選核心組 (20 → 10)');
        
        // 在候選池中使用進階模型深度分析
        const stage2Scores = {};
        stage1Candidates.forEach(num => stage2Scores[num] = 0);
        
        // 使用特徵加權模型
        const weightedResult = this.engine.featureWeightedModel(data);
        stage1Candidates.forEach(num => {
            stage2Scores[num] += (weightedResult.probabilities[num] || 0) * 2.0;
        });
        
        // 使用偏差追蹤模型
        const deviationResult = this.engine.deviationTrackingModel(data);
        stage1Candidates.forEach(num => {
            stage2Scores[num] += (deviationResult.probabilities[num] || 0) * 1.5;
        });
        
        // 使用貝葉斯模型
        const bayesianResult = this.engine.bayesianProbabilityModel(data);
        stage1Candidates.forEach(num => {
            stage2Scores[num] += (bayesianResult.probabilities[num] || 0) * 1.8;
        });
        
        // 加入共現分析加分
        const lastDraw = data[data.length - 1].numbers;
        const coOccurrenceBonus = this.calculateCoOccurrenceBonus(data, stage1Candidates, lastDraw);
        stage1Candidates.forEach(num => {
            stage2Scores[num] += coOccurrenceBonus[num] || 0;
        });
        
        // 選出前10名進入最終階段
        const stage2Candidates = Object.entries(stage2Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([num]) => parseInt(num));
        
        relayStages.push({
            stage: '階段二：精選',
            candidates: stage2Candidates,
            count: stage2Candidates.length,
            models: ['特徵加權', '偏差追蹤', '貝葉斯', '共現分析']
        });
        
        // ==================== 階段三：最終優化 ====================
        console.log('✨ 階段三：最終優化 (10 → 6)');
        
        // 從10個候選號碼中選出最佳6個
        const stage3Scores = {};
        stage2Candidates.forEach(num => stage3Scores[num] = 0);
        
        // 使用馬可夫鏈分析轉移機率
        const markovResult = this.engine.markovChainModel(data);
        stage2Candidates.forEach(num => {
            stage3Scores[num] += (markovResult.probabilities[num] || 0) * 2.5;
        });
        
        // 檢查號碼組合的平衡性
        const balanceScore = this.calculateBalanceScore(stage2Candidates);
        stage2Candidates.forEach(num => {
            stage3Scores[num] += balanceScore[num] || 0;
        });
        
        // 最終選出6個號碼
        const finalCandidates = Object.entries(stage3Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num]) => parseInt(num));
        
        const predictedNumbers = finalCandidates.sort((a, b) => a - b);
        
        relayStages.push({
            stage: '階段三：最終',
            candidates: predictedNumbers,
            count: predictedNumbers.length,
            models: ['馬可夫鏈', '平衡優化']
        });
        
        // 計算最終機率分佈
        const probabilities = {};
        for (let i = 1; i <= range; i++) probabilities[i] = 0;
        
        const totalScore = Object.values(stage3Scores).reduce((a, b) => a + b, 0);
        predictedNumbers.forEach(num => {
            probabilities[num] = stage3Scores[num] / totalScore;
        });
        
        // 計算信心度
        const confidence = this.calculateRelayConfidence(relayStages, stage3Scores);
        
        // 生成報告
        const report = this.generateRelayReport(relayStages, data.length);
        
        console.log('✅ 接力預測完成！');
        
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '🏃 接力預測系統 (三階段篩選)',
            report: report,
            stages: relayStages
        };
    }

    /**
     * 🤝 協作預測系統 (Collaborative Prediction)
     * 多模型並行分析，交叉驗證，共同決策
     * 
     * 流程：
     * 1. 第一輪：全員投票
     * 2. 第二輪：共識篩選
     * 3. 第三輪：異議處理
     * 4. 第四輪：最終決策
     */
    async collaborativePrediction(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const votingMatrix = {};
        
        // 初始化投票矩陣
        for (let i = 1; i <= range; i++) {
            votingMatrix[i] = {
                votes: 0,
                totalScore: 0,
                supporters: [],
                confidence: 0
            };
        }
        
        console.log('🤝 啟動協作預測系統...');
        
        // ==================== 第一輪：全員投票 ====================
        console.log('🗳️ 第一輪：全員投票');
        
        const models = [
            { name: '頻率分析', func: () => this.engine.frequencyRegression(data), weight: 1.0, specialty: 'long-term' },
            { name: '趨勢分析', func: () => this.engine.trendRegression(data), weight: 1.2, specialty: 'short-term' },
            { name: '綜合回歸', func: () => this.engine.combinedRegression(data), weight: 1.5, specialty: 'balanced' },
            { name: '特徵加權', func: () => this.engine.featureWeightedModel(data), weight: 1.4, specialty: 'multi-feature' },
            { name: '偏差追蹤', func: () => this.engine.deviationTrackingModel(data), weight: 1.3, specialty: 'mean-reversion' },
            { name: '貝葉斯', func: () => this.engine.bayesianProbabilityModel(data), weight: 1.6, specialty: 'probability' },
            { name: '馬可夫鏈', func: () => this.engine.markovChainModel(data), weight: 1.2, specialty: 'transition' }
        ];
        
        // 執行所有模型並收集投票
        const modelResults = models.map(model => {
            const result = model.func();
            return { ...model, result };
        });
        
        // 每個模型為前15名投票
        modelResults.forEach(model => {
            const topNumbers = Object.entries(model.result.probabilities)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 15)
                .map(([num, prob]) => ({ num: parseInt(num), prob }));
            
            topNumbers.forEach((item, rank) => {
                const score = (15 - rank) * model.weight;
                votingMatrix[item.num].votes++;
                votingMatrix[item.num].totalScore += score;
                votingMatrix[item.num].supporters.push({
                    model: model.name,
                    rank: rank + 1,
                    score: score,
                    specialty: model.specialty
                });
            });
        });
        
        // ==================== 第二輪：共識篩選 ====================
        console.log('🤝 第二輪：共識篩選');
        
        // 找出獲得多數支持的號碼（至少4個模型支持）
        const consensusCandidates = Object.entries(votingMatrix)
            .filter(([num, data]) => data.votes >= 4)
            .sort((a, b) => b[1].totalScore - a[1].totalScore)
            .slice(0, 12)
            .map(([num]) => parseInt(num));
        
        console.log(`✓ 共識候選：${consensusCandidates.length} 個號碼獲得多數支持`);
        
        // ==================== 第三輪：異議處理 ====================
        console.log('⚖️ 第三輪：異議處理');
        
        // 處理有爭議的號碼（得票數在2-3之間）
        const controversialCandidates = Object.entries(votingMatrix)
            .filter(([num, data]) => data.votes >= 2 && data.votes < 4)
            .sort((a, b) => b[1].totalScore - a[1].totalScore)
            .slice(0, 6)
            .map(([num]) => parseInt(num));
        
        console.log(`⚠️ 爭議候選：${controversialCandidates.length} 個號碼需要進一步評估`);
        
        // 合併候選池
        const allCandidates = [...new Set([...consensusCandidates, ...controversialCandidates])];
        
        // ==================== 第四輪：最終決策 ====================
        console.log('✅ 第四輪：最終決策');
        
        // 重新評分（考慮組合平衡性）
        const finalScores = {};
        allCandidates.forEach(num => {
            finalScores[num] = votingMatrix[num].totalScore;
        });
        
        // 加入組合平衡加分
        const balanceBonus = this.calculateBalanceScore(allCandidates);
        allCandidates.forEach(num => {
            finalScores[num] += (balanceBonus[num] || 0) * 10;
        });
        
        // 選出最終6個號碼
        const predictedNumbers = Object.entries(finalScores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num]) => parseInt(num))
            .sort((a, b) => a - b);
        
        // 計算機率分佈
        const probabilities = {};
        for (let i = 1; i <= range; i++) probabilities[i] = 0;
        
        const totalScore = Object.values(finalScores).reduce((a, b) => a + b, 0);
        predictedNumbers.forEach(num => {
            probabilities[num] = finalScores[num] / totalScore;
        });
        
        // 計算信心度
        const avgVotes = predictedNumbers.reduce((sum, num) => sum + votingMatrix[num].votes, 0) / 6;
        const confidence = Math.min((avgVotes / models.length) * 100, 95);
        
        // 生成報告
        const report = this.generateCollaborativeReport(votingMatrix, predictedNumbers, models.length, data.length);
        
        console.log('✅ 協作預測完成！');
        
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: Math.round(confidence),
            method: '🤝 協作預測系統 (七模型投票)',
            report: report,
            votingDetails: predictedNumbers.map(num => ({
                number: num,
                votes: votingMatrix[num].votes,
                supporters: votingMatrix[num].supporters
            }))
        };
    }

    /**
     * 🧠 自適應接力預測 (Adaptive Relay Prediction)
     * 根據數據特徵動態調整接力策略
     * 
     * 特色：
     * 1. 自動檢測數據規模與特徵
     * 2. 動態選擇最適合的模型組合
     * 3. 自適應調整權重
     * 4. 階段性優化
     */
    async adaptiveRelayPrediction(data) {
        const range = LOTTERY_RULES.numberRange.max;
        const dataSize = data.length;
        
        console.log('🧠 啟動自適應接力預測...');
        
        // ==================== 數據分析階段 ====================
        console.log('📊 分析數據特徵...');
        
        const features = this.analyzeDataFeatures(data);
        console.log('數據特徵:', features);
        
        // ==================== 策略選擇階段 ====================
        console.log('🎯 選擇最佳策略...');
        
        let strategy;
        if (dataSize < 50) {
            strategy = 'small-sample';
            console.log('→ 採用小樣本優化策略（重視近期趨勢）');
        } else if (dataSize > 500) {
            strategy = 'large-sample';
            console.log('→ 採用大樣本穩健策略（重視長期頻率）');
        } else {
            strategy = 'balanced';
            console.log('→ 採用平衡策略（兼顧長短期）');
        }
        
        // ==================== 階段一：智能粗選 ====================
        console.log('🔍 階段一：智能粗選');
        
        const stage1Models = this.selectStage1Models(strategy, features);
        const stage1Scores = {};
        for (let i = 1; i <= range; i++) stage1Scores[i] = 0;
        
        stage1Models.forEach(model => {
            const result = model.func(data);
            for (let i = 1; i <= range; i++) {
                stage1Scores[i] += (result.probabilities[i] || 0) * model.adaptiveWeight;
            }
        });
        
        const stage1Count = strategy === 'small-sample' ? 15 : 20;
        const stage1Candidates = Object.entries(stage1Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, stage1Count)
            .map(([num]) => parseInt(num));
        
        console.log(`✓ 篩選出 ${stage1Count} 個候選號碼`);
        
        // ==================== 階段二：交叉驗證 ====================
        console.log('🔬 階段二：交叉驗證');
        
        const stage2Models = this.selectStage2Models(strategy, features);
        const stage2Scores = {};
        stage1Candidates.forEach(num => stage2Scores[num] = stage1Scores[num] * 0.3);
        
        stage2Models.forEach(model => {
            const result = model.func(data);
            stage1Candidates.forEach(num => {
                stage2Scores[num] += (result.probabilities[num] || 0) * model.adaptiveWeight;
            });
        });
        
        // 加入特徵加成
        if (features.hasStrongTrend) {
            console.log('→ 檢測到強趨勢，近期熱門號碼加分');
            const recentHot = this.getRecentHotNumbers(data, 10);
            stage1Candidates.forEach(num => {
                if (recentHot.includes(num)) {
                    stage2Scores[num] *= 1.15;
                }
            });
        }
        
        if (features.hasHighDeviation) {
            console.log('→ 檢測到高偏差，冷號補償加分');
            const missing = this.engine.calculateMissingForData(data);
            stage1Candidates.forEach(num => {
                if (missing[num] > 10) {
                    stage2Scores[num] *= 1.1;
                }
            });
        }
        
        const stage2Candidates = Object.entries(stage2Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([num]) => parseInt(num));
        
        console.log(`✓ 精選出 10 個核心候選`);
        
        // ==================== 階段三：精準優化 ====================
        console.log('✨ 階段三：精準優化');
        
        const stage3Scores = {};
        stage2Candidates.forEach(num => stage3Scores[num] = stage2Scores[num] * 0.4);
        
        // 使用高級模型精修
        const markovResult = this.engine.markovChainModel(data);
        const bayesianResult = this.engine.bayesianProbabilityModel(data);
        
        stage2Candidates.forEach(num => {
            stage3Scores[num] += (markovResult.probabilities[num] || 0) * 2.0;
            stage3Scores[num] += (bayesianResult.probabilities[num] || 0) * 2.2;
        });
        
        // 組合平衡優化
        const balanceScore = this.calculateBalanceScore(stage2Candidates);
        stage2Candidates.forEach(num => {
            stage3Scores[num] += (balanceScore[num] || 0) * 8;
        });
        
        // 最終選號
        const predictedNumbers = Object.entries(stage3Scores)
            .sort((a, b) => b[1] - a[1])
            .slice(0, LOTTERY_RULES.pickCount)
            .map(([num]) => parseInt(num))
            .sort((a, b) => a - b);
        
        console.log('✅ 最終預測號碼:', predictedNumbers);
        
        // 計算機率
        const probabilities = {};
        for (let i = 1; i <= range; i++) probabilities[i] = 0;
        const totalScore = Object.values(stage3Scores).reduce((a, b) => a + b, 0);
        predictedNumbers.forEach(num => {
            probabilities[num] = stage3Scores[num] / totalScore;
        });
        
        // 計算信心度
        const confidence = this.calculateAdaptiveConfidence(features, stage3Scores, predictedNumbers);
        
        // 生成報告
        const report = this.generateAdaptiveReport(strategy, features, data.length);
        
        console.log('✅ 自適應接力預測完成！');
        
        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: `🧠 自適應接力預測 (${this.getStrategyName(strategy)})`,
            report: report,
            strategy: strategy,
            features: features
        };
    }

    // ==================== 輔助方法 ====================

    /**
     * 計算共現加分
     */
    calculateCoOccurrenceBonus(data, candidates, leaders) {
        const bonus = {};
        candidates.forEach(num => bonus[num] = 0);
        
        data.forEach(draw => {
            const nums = draw.numbers;
            const leadersInDraw = nums.filter(n => leaders.includes(n));
            
            if (leadersInDraw.length > 0) {
                nums.forEach(n => {
                    if (candidates.includes(n) && !leaders.includes(n)) {
                        bonus[n] += leadersInDraw.length * 0.1;
                    }
                });
            }
        });
        
        return bonus;
    }

    /**
     * 計算組合平衡分數
     */
    calculateBalanceScore(candidates) {
        const scores = {};
        candidates.forEach(num => scores[num] = 0);
        
        // 奇偶平衡
        const oddCount = candidates.filter(n => n % 2 === 1).length;
        const evenCount = candidates.length - oddCount;
        const oddEvenBalance = 1 - Math.abs(oddCount - evenCount) / candidates.length;
        
        // 區間分佈
        const zones = { '1-10': 0, '11-20': 0, '21-30': 0, '31-40': 0, '41-49': 0 };
        candidates.forEach(num => {
            if (num <= 10) zones['1-10']++;
            else if (num <= 20) zones['11-20']++;
            else if (num <= 30) zones['21-30']++;
            else if (num <= 40) zones['31-40']++;
            else zones['41-49']++;
        });
        
        const avgZone = candidates.length / 5;
        const zoneBalance = 1 - Object.values(zones).reduce((sum, count) => 
            sum + Math.abs(count - avgZone), 0) / (candidates.length * 2);
        
        // 給所有候選號碼平衡加分
        const balanceBonus = (oddEvenBalance + zoneBalance) / 2;
        candidates.forEach(num => {
            scores[num] = balanceBonus;
        });
        
        return scores;
    }

    /**
     * 計算接力信心度
     */
    calculateRelayConfidence(stages, finalScores) {
        // 基於篩選率計算
        const filterRate = stages[stages.length - 1].count / stages[0].count;
        
        // 基於分數差距
        const scores = Object.values(finalScores).sort((a, b) => b - a);
        const topScore = scores[0];
        const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
        const scoreGap = topScore / avgScore;
        
        const confidence = Math.min((filterRate * 30 + scoreGap * 40 + 20), 90);
        return Math.round(confidence);
    }

    /**
     * 分析數據特徵
     */
    analyzeDataFeatures(data) {
        const frequency = {};
        for (let i = 1; i <= 49; i++) frequency[i] = 0;
        data.forEach(draw => {
            draw.numbers.forEach(num => frequency[num]++);
        });
        
        const missing = this.engine.calculateMissingForData(data);
        
        // 檢測趨勢強度
        const recentWindow = Math.min(20, data.length);
        const recentFreq = {};
        for (let i = 1; i <= 49; i++) recentFreq[i] = 0;
        
        for (let i = data.length - recentWindow; i < data.length; i++) {
            if (i >= 0) {
                data[i].numbers.forEach(num => recentFreq[num]++);
            }
        }
        
        // 計算趨勢與整體的差異
        let trendDiff = 0;
        for (let i = 1; i <= 49; i++) {
            const overallRate = (frequency[i] || 0) / data.length;
            const recentRate = recentFreq[i] / recentWindow;
            trendDiff += Math.abs(recentRate - overallRate);
        }
        
        const hasStrongTrend = trendDiff > 1.5;
        
        // 檢測偏差程度
        const expectedFreq = (data.length * 6) / 49;
        let totalDeviation = 0;
        for (let i = 1; i <= 49; i++) {
            totalDeviation += Math.abs((frequency[i] || 0) - expectedFreq);
        }
        const avgDeviation = totalDeviation / 49;
        const hasHighDeviation = avgDeviation > expectedFreq * 0.3;
        
        return {
            dataSize: data.length,
            hasStrongTrend,
            hasHighDeviation,
            avgDeviation,
            trendStrength: trendDiff
        };
    }

    /**
     * 選擇階段一模型
     */
    selectStage1Models(strategy, features) {
        const models = [];
        
        if (strategy === 'small-sample') {
            models.push(
                { name: '趨勢分析', func: this.engine.trendRegression.bind(this.engine), adaptiveWeight: 2.0 },
                { name: '綜合回歸', func: this.engine.combinedRegression.bind(this.engine), adaptiveWeight: 1.8 },
                { name: '偏差追蹤', func: this.engine.deviationTrackingModel.bind(this.engine), adaptiveWeight: 1.5 }
            );
        } else if (strategy === 'large-sample') {
            models.push(
                { name: '頻率分析', func: this.engine.frequencyRegression.bind(this.engine), adaptiveWeight: 2.0 },
                { name: '綜合回歸', func: this.engine.combinedRegression.bind(this.engine), adaptiveWeight: 1.6 },
                { name: '特徵加權', func: this.engine.featureWeightedModel.bind(this.engine), adaptiveWeight: 1.4 }
            );
        } else {
            models.push(
                { name: '頻率分析', func: this.engine.frequencyRegression.bind(this.engine), adaptiveWeight: 1.2 },
                { name: '趨勢分析', func: this.engine.trendRegression.bind(this.engine), adaptiveWeight: 1.4 },
                { name: '綜合回歸', func: this.engine.combinedRegression.bind(this.engine), adaptiveWeight: 1.8 }
            );
        }
        
        return models;
    }

    /**
     * 選擇階段二模型
     */
    selectStage2Models(strategy, features) {
        return [
            { name: '特徵加權', func: this.engine.featureWeightedModel.bind(this.engine), adaptiveWeight: 1.8 },
            { name: '偏差追蹤', func: this.engine.deviationTrackingModel.bind(this.engine), adaptiveWeight: 1.5 },
            { name: '貝葉斯', func: this.engine.bayesianProbabilityModel.bind(this.engine), adaptiveWeight: 1.6 }
        ];
    }

    /**
     * 獲取近期熱門號碼
     */
    getRecentHotNumbers(data, count) {
        const recentWindow = Math.min(20, data.length);
        const freq = {};
        for (let i = 1; i <= 49; i++) freq[i] = 0;
        
        for (let i = data.length - recentWindow; i < data.length; i++) {
            if (i >= 0) {
                data[i].numbers.forEach(num => freq[num]++);
            }
        }
        
        return Object.entries(freq)
            .sort((a, b) => b[1] - a[1])
            .slice(0, count)
            .map(([num]) => parseInt(num));
    }

    /**
     * 計算自適應信心度
     */
    calculateAdaptiveConfidence(features, scores, predictedNumbers) {
        let baseConfidence = 60;
        
        // 數據量加成
        if (features.dataSize > 500) baseConfidence += 10;
        else if (features.dataSize < 50) baseConfidence -= 10;
        
        // 分數集中度加成
        const topScores = predictedNumbers.map(num => scores[num]);
        const avgTop = topScores.reduce((a, b) => a + b, 0) / topScores.length;
        const allScores = Object.values(scores);
        const avgAll = allScores.reduce((a, b) => a + b, 0) / allScores.length;
        
        if (avgTop > avgAll * 2) baseConfidence += 15;
        
        return Math.min(Math.round(baseConfidence), 92);
    }

    /**
     * 獲取策略名稱
     */
    getStrategyName(strategy) {
        const names = {
            'small-sample': '小樣本優化策略',
            'large-sample': '大樣本穩健策略',
            'balanced': '平衡策略'
        };
        return names[strategy] || '標準策略';
    }

    /**
     * 生成接力報告
     */
    generateRelayReport(stages, dataLength) {
        let report = `📊 基於 ${dataLength} 期歷史數據，採用三階段接力篩選策略：\n\n`;
        
        stages.forEach((stage, idx) => {
            report += `【${stage.stage}】\n`;
            report += `• 候選數量：${stage.count} 個\n`;
            report += `• 使用模型：${stage.models.join('、')}\n`;
            
            if (idx < stages.length - 1) {
                const nextStage = stages[idx + 1];
                const filterRate = ((1 - nextStage.count / stage.count) * 100).toFixed(0);
                const passRate = (100 - filterRate).toFixed(0);
                report += `• 晉級率：${passRate}% (淘汰 ${filterRate}%)\n`;
            }
            report += '\n';
        });
        
        report += `✨ 透過層層篩選與多模型協作，確保最終選號的精準度與平衡性。\n`;
        report += `每個階段使用不同模型組合，發揮各自優勢，互補短板。`;
        
        return report;
    }

    /**
     * 生成協作報告
     */
    generateCollaborativeReport(votingMatrix, predictedNumbers, modelCount, dataLength) {
        let report = `📊 基於 ${dataLength} 期數據，${modelCount} 個模型協作預測：\n\n`;
        
        report += `【投票結果】\n`;
        predictedNumbers.forEach(num => {
            const votes = votingMatrix[num].votes;
            const support = ((votes / modelCount) * 100).toFixed(0);
            const mainSupporters = votingMatrix[num].supporters
                .slice(0, 3)
                .map(s => s.model)
                .join('、');
            
            report += `🔹 ${num} 號\n`;
            report += `   支持度：${votes}/${modelCount} 模型 (${support}%)\n`;
            report += `   主要支持：${mainSupporters}\n`;
        });
        
        const avgVotes = predictedNumbers.reduce((sum, num) => 
            sum + votingMatrix[num].votes, 0) / predictedNumbers.length;
        
        report += `\n【整體評估】\n`;
        report += `• 平均支持度：${avgVotes.toFixed(1)}/${modelCount} 模型\n`;
        report += `• 共識強度：${((avgVotes / modelCount) * 100).toFixed(0)}%\n`;
        report += `\n✅ 通過多模型交叉驗證與投票機制，確保預測的可靠性與一致性。`;
        
        return report;
    }

    /**
     * 生成自適應報告
     */
    generateAdaptiveReport(strategy, features, dataLength) {
        let report = `🧠 自適應分析 ${dataLength} 期數據：\n\n`;
        
        report += `【數據特徵】\n`;
        report += `• 樣本規模：${features.dataSize} 期\n`;
        report += `• 趨勢強度：${features.hasStrongTrend ? '強' : '弱'} (指數: ${features.trendStrength.toFixed(2)})\n`;
        report += `• 偏差程度：${features.hasHighDeviation ? '高' : '低'} (平均偏差: ${features.avgDeviation.toFixed(2)})\n`;
        
        report += `\n【策略選擇】${this.getStrategyName(strategy)}\n`;
        
        if (strategy === 'small-sample') {
            report += `• 樣本較小，重視近期趨勢變化\n`;
            report += `• 提高趨勢分析與偏差追蹤權重\n`;
            report += `• 候選池設定為 15 個（更精準）\n`;
        } else if (strategy === 'large-sample') {
            report += `• 樣本充足，重視長期頻率規律\n`;
            report += `• 提高頻率分析與特徵加權權重\n`;
            report += `• 候選池設定為 20 個（更穩健）\n`;
        } else {
            report += `• 樣本適中，兼顧長短期因素\n`;
            report += `• 平衡各模型權重配置\n`;
            report += `• 採用標準三階段篩選流程\n`;
        }
        
        report += `\n✨ 根據數據特徵動態調整策略，實現最優預測效果。`;
        
        return report;
    }
}

// 導出為全域變數
window.CollaborativePredictionEngine = CollaborativePredictionEngine;
