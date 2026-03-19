/**
 * PredictionHandler - handles prediction workflows to keep App orchestration slimmer.
 */
export class PredictionHandler {
    constructor(app) {
        this.app = app;
    }

    async runPrediction() {
        const method = document.getElementById('prediction-method').value;
        const sampleSize = document.getElementById('sample-size').value;
        const lotteryType = this.app.currentLotteryType;
        const predictBtn = document.getElementById('predict-btn');

        try {
            this.app.setButtonLoading(predictBtn, true);

            // For memory-heavy methods, cap input size to keep UI responsive.
            let actualSampleSize = sampleSize;
            if (method === 'auto_optimize') {
                const requestedSize = sampleSize === 'all' ? Number.POSITIVE_INFINITY : Number.parseInt(sampleSize, 10);
                if (requestedSize > 500) {
                    actualSampleSize = '500';
                    console.log('⚠️ 記憶體保護：自動優化限制使用 500 期數據');
                    this.app.uiManager.showNotification('記憶體保護：自動優化使用最近 500 期數據', 'info');
                }
            }

            this.app.uiManager.showNotification('正在分析預測...', 'info');
            const result = await this.app.predictionEngine.predict(method, actualSampleSize, lotteryType, true);
            this.app.displayPredictionResult(result);
            this.app.uiManager.showNotification('預測完成！', 'success');
        } catch (error) {
            console.error('預測錯誤:', error);
            this.app.uiManager.showNotification('預測失敗: ' + error.message, 'error');
        } finally {
            this.app.setButtonLoading(predictBtn, false);
        }
    }

    /**
     * Generate next-period dual-bet prediction from full history.
     */
    async generateNextPeriodPrediction(allData) {
        const nextPredictionPanel = document.getElementById('simulation-next-prediction');

        if (!nextPredictionPanel) {
            console.warn('找不到最新一期預測面板');
            return;
        }

        console.log(`🎯 開始未來預測：使用全部 ${allData.length} 期歷史數據（這是正確的！）`);

        try {
            const strategies = [
                'frequency', 'trend', 'bayesian', 'markov', 'montecarlo', 'deviation',
                'odd_even', 'zone_balance', 'hot_cold', 'sum_range', 'number_pairs',
                'ensemble_weighted', 'ensemble_combined', 'ensemble_advanced',
                'backend_optimized'
            ];

            const allPredictions = [];
            const lotteryRules = this.app.getLotteryRulesFromType(this.app.currentLotteryType);
            const maxNumber = lotteryRules.maxNumber;

            console.log(`📋 準備用 ${strategies.length} 種策略預測未來下一期...`);
            for (let i = 0; i < strategies.length; i++) {
                const strategy = strategies[i];
                console.log(`\n🔮 [${i + 1}/${strategies.length}] 使用策略: ${strategy.toUpperCase()}`);
                try {
                    const result = await this.app.predictionEngine.predictWithData(
                        strategy,
                        allData,
                        this.app.currentLotteryType,
                        true
                    );

                    if (result?.numbers?.length > 0) {
                        console.log(`   ✅ ${strategy} 預測成功: ${result.numbers.join(', ')} (信心度: ${result.confidence || 50}%)`);
                        allPredictions.push({
                            strategy,
                            numbers: result.numbers,
                            confidence: result.confidence || 50
                        });
                    }
                } catch (error) {
                    console.warn(`   ❌ 策略 ${strategy} 預測失敗:`, error.message);
                }
            }

            if (allPredictions.length === 0) {
                throw new Error('所有策略都無法執行預測');
            }

            const numberScores = {};
            for (let i = 1; i <= maxNumber; i++) {
                numberScores[i] = 0;
            }

            allPredictions.forEach(pred => {
                const { numbers, confidence } = pred;
                numbers.forEach((num, index) => {
                    const rankWeight = (6 - index) / 6;
                    const score = (confidence / 100) * rankWeight * 10;
                    numberScores[num] = (numberScores[num] || 0) + score;
                });
            });

            const sortedNumbers = Object.entries(numberScores)
                .map(([num, score]) => ({ num: Number.parseInt(num, 10), score }))
                .sort((a, b) => b.score - a.score)
                .slice(0, 12);

            const bet1Numbers = sortedNumbers.slice(0, 6).map(n => n.num).sort((a, b) => a - b);
            const bet2Numbers = sortedNumbers.slice(6, 12).map(n => n.num).sort((a, b) => a - b);

            const maxScore = Math.max(...Object.values(numberScores));
            const bet1Score = sortedNumbers.slice(0, 6).reduce((sum, n) => sum + n.score, 0) / 6;
            const bet2Score = sortedNumbers.slice(6, 12).reduce((sum, n) => sum + n.score, 0) / 6;
            const overallScore = sortedNumbers.slice(0, 12).reduce((sum, n) => sum + n.score, 0) / 12;

            const bet1Confidence = Math.min(95, Math.round((bet1Score / maxScore) * 100));
            const bet2Confidence = Math.min(95, Math.round((bet2Score / maxScore) * 100));
            const overallConfidence = Math.min(95, Math.round((overallScore / maxScore) * 100));

            this.app.displayNextPeriodPrediction({
                bet1: { numbers: bet1Numbers, confidence: bet1Confidence },
                bet2: { numbers: bet2Numbers, confidence: bet2Confidence },
                strategyCount: allPredictions.length,
                overallConfidence,
                basePeriod: allData.length > 0 ? `${allData[0].draw} - ${allData[allData.length - 1].draw}` : '-',
                topStrategies: allPredictions.slice(0, 5).map(p => p.strategy)
            });

            nextPredictionPanel.style.display = 'block';
        } catch (error) {
            console.error('生成最新一期預測失敗:', error);
            nextPredictionPanel.style.display = 'none';
        }
    }
}
