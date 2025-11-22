/**
 * 預測模組
 * 使用數學回歸分析預測下一期開獎機率
 */

class PredictionEngine {
    constructor(dataProcessor) {
        this.dataProcessor = dataProcessor;
        this.probabilityChart = null;
    }

    /**
     * 執行預測
     */
    predict(method = 'frequency', sampleSize = 50) {
        const data = this.dataProcessor.getDataRange(sampleSize);

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
            default:
                prediction = this.frequencyRegression(data);
        }

        return prediction;
    }

    /**
     * 頻率回歸分析
     * 基於歷史出現頻率計算機率
     */
    frequencyRegression(data) {
        const frequency = {};

        // 初始化
        for (let i = 1; i <= 49; i++) {
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

        for (let i = 1; i <= 49; i++) {
            probabilities[i] = frequency[i] / totalDraws;
        }

        // 選擇機率最高的6個號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6)
            .map(([num, prob]) => ({
                number: parseInt(num),
                probability: prob
            }));

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

    /**
     * 趨勢回歸分析
     * 考慮最近期數的權重
     */
    trendRegression(data) {
        const weightedFrequency = {};

        // 初始化
        for (let i = 1; i <= 49; i++) {
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

        for (let i = 1; i <= 49; i++) {
            probabilities[i] = weightedFrequency[i] / totalWeight;
        }

        // 選擇機率最高的6個號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6)
            .map(([num, prob]) => ({
                number: parseInt(num),
                probability: prob
            }));

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

    /**
     * 綜合回歸模型
     * 結合頻率、趨勢和遺漏值
     */
    combinedRegression(data) {
        const frequency = {};
        const weighted = {};
        const missing = this.calculateMissingForData(data);

        // 初始化
        for (let i = 1; i <= 49; i++) {
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

        for (let i = 1; i <= 49; i++) {
            // 頻率分數 (40%)
            const freqScore = (frequency[i] / totalDraws) * 0.4;

            // 趨勢分數 (30%)
            const trendScore = (weighted[i] / data.length) * 0.3;

            // 遺漏值分數 (30%) - 遺漏越久分數越高
            const maxMissing = Math.max(...Object.values(missing));
            const missingScore = maxMissing > 0 ? (missing[i] / maxMissing) * 0.3 : 0;

            probabilities[i] = freqScore + trendScore + missingScore;
        }

        // 正規化
        const total = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= 49; i++) {
            probabilities[i] = probabilities[i] / total;
        }

        // 選擇機率最高的6個號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6)
            .map(([num, prob]) => ({
                number: parseInt(num),
                probability: prob
            }));

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

    /**
     * 機器學習模型（簡化版）
     * 使用多項式回歸和模式識別
     */
    machineLearningModel(data) {
        const patterns = this.analyzePatterns(data);
        const probabilities = {};

        // 初始化
        for (let i = 1; i <= 49; i++) {
            probabilities[i] = 0;
        }

        // 基於模式計算機率
        // 1. 連號模式
        patterns.consecutive.forEach(num => {
            probabilities[num] = (probabilities[num] || 0) + 0.15;
        });

        // 2. 區間平衡
        const distribution = this.calculateDistributionForData(data);
        const avgPerZone = 6 / 5; // 平均每個區間應該有的號碼數

        for (let i = 1; i <= 49; i++) {
            const zone = this.getZone(i);
            const zoneCount = distribution[zone];
            const zoneFactor = avgPerZone / (zoneCount + 1);
            probabilities[i] = (probabilities[i] || 0) + (zoneFactor * 0.2);
        }

        // 3. 奇偶平衡
        const oddEven = this.calculateOddEvenForData(data);
        const oddRatio = oddEven.odd / (oddEven.odd + oddEven.even);

        for (let i = 1; i <= 49; i++) {
            if (i % 2 === 1 && oddRatio < 0.5) {
                probabilities[i] = (probabilities[i] || 0) + 0.1;
            } else if (i % 2 === 0 && oddRatio > 0.5) {
                probabilities[i] = (probabilities[i] || 0) + 0.1;
            }
        }

        // 4. 歷史頻率
        const frequency = {};
        for (let i = 1; i <= 49; i++) {
            frequency[i] = 0;
        }

        data.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });

        for (let i = 1; i <= 49; i++) {
            probabilities[i] = (probabilities[i] || 0) + ((frequency[i] / data.length) * 0.55);
        }

        // 正規化
        const total = Object.values(probabilities).reduce((a, b) => a + b, 0);
        for (let i = 1; i <= 49; i++) {
            probabilities[i] = probabilities[i] / total;
        }

        // 選擇機率最高的6個號碼
        const sortedNumbers = Object.entries(probabilities)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6)
            .map(([num, prob]) => ({
                number: parseInt(num),
                probability: prob
            }));

        const predictedNumbers = sortedNumbers.map(item => item.number).sort((a, b) => a - b);
        const confidence = this.calculateConfidence(sortedNumbers);

        return {
            numbers: predictedNumbers,
            probabilities: probabilities,
            confidence: confidence,
            method: '機器學習模型',
            report: this.generateReport('ml', sortedNumbers, data.length, patterns)
        };
    }

    /**
     * 分析號碼模式
     */
    analyzePatterns(data) {
        const recentDraws = data.slice(-10);
        const allNumbers = new Set();
        const consecutive = new Set();

        recentDraws.forEach(draw => {
            draw.numbers.forEach(num => allNumbers.add(num));

            // 檢查連號
            for (let i = 0; i < draw.numbers.length - 1; i++) {
                if (draw.numbers[i + 1] - draw.numbers[i] === 1) {
                    consecutive.add(draw.numbers[i]);
                    consecutive.add(draw.numbers[i + 1]);
                }
            }
        });

        return {
            recentNumbers: Array.from(allNumbers),
            consecutive: Array.from(consecutive)
        };
    }

    /**
     * 計算遺漏值（針對特定數據集）
     */
    calculateMissingForData(data) {
        const missing = {};

        for (let i = 1; i <= 49; i++) {
            missing[i] = 0;
        }

        for (let i = data.length - 1; i >= 0; i--) {
            const draw = data[i];

            for (let num = 1; num <= 49; num++) {
                if (!draw.numbers.includes(num)) {
                    missing[num]++;
                }
            }

            draw.numbers.forEach(num => {
                if (missing[num] > 0) {
                    missing[num] = 0;
                }
            });
        }

        return missing;
    }

    /**
     * 計算分佈（針對特定數據集）
     */
    calculateDistributionForData(data) {
        const distribution = {
            '1-10': 0,
            '11-20': 0,
            '21-30': 0,
            '31-40': 0,
            '41-49': 0
        };

        data.forEach(draw => {
            draw.numbers.forEach(num => {
                const zone = this.getZone(num);
                distribution[zone]++;
            });
        });

        return distribution;
    }

    /**
     * 獲取號碼所屬區間
     */
    getZone(num) {
        if (num <= 10) return '1-10';
        if (num <= 20) return '11-20';
        if (num <= 30) return '21-30';
        if (num <= 40) return '31-40';
        return '41-49';
    }

    /**
     * 計算奇偶比例（針對特定數據集）
     */
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
     * 計算預測信心度
     */
    calculateConfidence(sortedNumbers) {
        // 基於機率分佈的標準差計算信心度
        const probabilities = sortedNumbers.map(item => item.probability);
        const mean = probabilities.reduce((a, b) => a + b, 0) / probabilities.length;
        const variance = probabilities.reduce((sum, prob) => sum + Math.pow(prob - mean, 2), 0) / probabilities.length;
        const stdDev = Math.sqrt(variance);

        // 標準差越小，信心度越高
        const confidence = Math.max(0, Math.min(100, (1 - stdDev * 10) * 100));

        return Math.round(confidence);
    }

    /**
     * 生成預測報告
     */
    generateReport(method, sortedNumbers, sampleSize, patterns = null) {
        let report = `<div class="report-section">`;
        report += `<h4>📊 分析方法</h4>`;

        switch (method) {
            case 'frequency':
                report += `<p>本次預測使用<strong>頻率回歸分析</strong>，基於過去 ${sampleSize} 期的歷史數據，計算每個號碼的出現頻率，並選擇頻率最高的號碼作為預測結果。</p>`;
                break;
            case 'trend':
                report += `<p>本次預測使用<strong>趨勢回歸分析</strong>，對最近 ${sampleSize} 期的數據進行加權計算，越近期的數據權重越高，以捕捉最新的開獎趨勢。</p>`;
                break;
            case 'combined':
                report += `<p>本次預測使用<strong>綜合回歸模型</strong>，結合頻率分析(40%)、趨勢分析(30%)和遺漏值分析(30%)，提供更全面的預測結果。</p>`;
                break;
            case 'ml':
                report += `<p>本次預測使用<strong>機器學習模型</strong>，分析號碼模式、區間平衡、奇偶比例等多個維度，使用智能算法進行預測。</p>`;
                break;
        }

        report += `</div>`;

        report += `<div class="report-section">`;
        report += `<h4>🎯 預測號碼機率</h4>`;
        report += `<ul>`;
        sortedNumbers.forEach(item => {
            const percentage = (item.probability * 100).toFixed(2);
            report += `<li>號碼 <strong>${item.number}</strong>: ${percentage}%</li>`;
        });
        report += `</ul>`;
        report += `</div>`;

        if (patterns) {
            report += `<div class="report-section">`;
            report += `<h4>🔍 模式分析</h4>`;
            report += `<p>檢測到 ${patterns.consecutive.length} 個可能的連號模式。</p>`;
            report += `<p>最近10期出現過的號碼共 ${patterns.recentNumbers.length} 個。</p>`;
            report += `</div>`;
        }

        report += `<div class="report-section">`;
        report += `<h4>⚠️ 風險提示</h4>`;
        report += `<p>本預測結果僅供參考，彩票開獎具有隨機性，無法保證準確性。請理性投注，量力而行。</p>`;
        report += `</div>`;

        return report;
    }

    /**
     * 顯示預測結果
     */
    displayPrediction(prediction) {
        // 顯示預測號碼
        const numbersContainer = document.getElementById('predicted-numbers');
        if (numbersContainer) {
            numbersContainer.innerHTML = prediction.numbers.map(num =>
                `<div class="predicted-number">${num}</div>`
            ).join('');
        }

        // 顯示信心度
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');

        if (confidenceFill && confidenceValue) {
            setTimeout(() => {
                confidenceFill.style.width = `${prediction.confidence}%`;
                confidenceValue.textContent = `${prediction.confidence}%`;
            }, 100);
        }

        // 顯示報告
        const reportContainer = document.getElementById('prediction-report');
        if (reportContainer) {
            reportContainer.innerHTML = prediction.report;
        }

        // 創建機率圖表
        this.createProbabilityChart(prediction.probabilities);
    }

    /**
     * 創建機率分佈圖表
     */
    createProbabilityChart(probabilities) {
        const ctx = document.getElementById('probability-chart');
        if (!ctx) return;

        const labels = Object.keys(probabilities);
        const data = Object.values(probabilities).map(p => (p * 100).toFixed(2));

        if (this.probabilityChart) {
            this.probabilityChart.destroy();
        }

        this.probabilityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '預測機率 (%)',
                    data: data,
                    backgroundColor: (context) => {
                        const value = context.parsed.y;
                        const alpha = Math.min(1, value / 5);
                        return `rgba(236, 72, 153, ${alpha})`;
                    },
                    borderColor: 'rgba(236, 72, 153, 1)',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 15, 25, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(236, 72, 153, 0.5)',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: (context) => {
                                return `預測機率: ${context.parsed.y}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            font: {
                                family: 'Orbitron'
                            }
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.7)',
                            callback: (value) => value + '%'
                        }
                    }
                }
            }
        });
    }
}

// 導出為全域變數
window.PredictionEngine = PredictionEngine;
