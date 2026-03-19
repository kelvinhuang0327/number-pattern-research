import { apiClient } from '../../services/ApiClient.js';

/**
 * SimulationHandler - handles simulation workflows to keep App orchestration slimmer.
 */
export class SimulationHandler {
    constructor(app) {
        this.app = app;
    }

    normalizeDate(date) {
        return String(date || '').replaceAll('/', '-');
    }

    sortYearStrings(years) {
        return [...years].sort((a, b) => Number(a) - Number(b));
    }

    async runSimulation() {
        const method = document.getElementById('simulation-method').value;
        const yearMonth = document.getElementById('simulation-year-month').value;
        const simulationBtn = document.getElementById('simulation-btn');

        if (!yearMonth) {
            this.app.uiManager.showNotification('請選擇年度月份', 'warning');
            return;
        }

        const [year] = yearMonth.split('-');
        const targetYear = year;

        try {
            this.app.setButtonLoading(simulationBtn, true);
            this.app.uiManager.showNotification('正在進行模擬測試...', 'info');

            this.app._autoOptimizeCache = null;

            const allData = await this.getSimulationAllData();
            const testTargets = this.getSimulationTargetsByYear(allData, targetYear);
            const { results, successCount } = await this.runSimulationByTargets(method, allData, testTargets);

            this.app.displaySimulationResults(results, successCount);

            console.log('\n\n🌟 ========== 未來預測階段：預測下一期（使用全部歷史數據）==========\n');
            try {
                await this.app.generateNextPeriodPrediction(allData);
            } catch (error) {
                console.error('最新一期預測失敗:', error);
            }

            this.app.uiManager.showNotification(
                `模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${results.length > 0 ? Math.round((successCount / results.length) * 100) : 0}%`,
                'success'
            );
        } catch (error) {
            this.app.uiManager.showNotification('模擬失敗: ' + error.message, 'error');
            console.error(error);
        } finally {
            this.app.setButtonLoading(simulationBtn, false);
        }
    }

    async getSimulationAllData() {
        let allData = await this.app.dataProcessor.getDataSmart(this.app.currentLotteryType, 'all');

        if (this.app.currentLotteryType) {
            allData = allData.filter(d => d.lotteryType === this.app.currentLotteryType);
        }

        if (allData.length < 50) {
            throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
        }

        return allData;
    }

    getSimulationTargetsByYear(allData, targetYear) {
        const testTargets = allData.filter(draw => this.app.getYearFromDate(draw.date) === targetYear);

        if (testTargets.length === 0) {
            const years = allData.map(d => this.app.getYearFromDate(d.date)).filter(Boolean);
            const uniqueYears = this.sortYearStrings(Array.from(new Set(years)));
            throw new Error(`該年份 (${targetYear}) 無開獎資料。可用年份: ${uniqueYears.join(', ')}`);
        }

        testTargets.sort((a, b) => this.normalizeDate(a.date).localeCompare(this.normalizeDate(b.date)));
        return testTargets;
    }

    async runSimulationByTargets(method, allData, testTargets) {
        const results = [];
        let successCount = 0;

        for (let idx = 0; idx < testTargets.length; idx++) {
            const targetDraw = testTargets[idx];
            console.log(`\n🔄 ========== 模擬測試階段：第 ${idx + 1}/${testTargets.length} 期 ==========`);

            const simulationResult = await this.runSingleSimulationTarget(method, allData, targetDraw);
            if (!simulationResult) {
                continue;
            }

            results.push(simulationResult.result);
            if (simulationResult.result.isSuccess) {
                successCount++;
            }
        }

        return { results, successCount };
    }

    async runSingleSimulationTarget(method, allData, targetDraw) {
        const targetDate = this.normalizeDate(targetDraw.date);
        const trainingData = allData.filter(d => this.normalizeDate(d.date) < targetDate);

        if (trainingData.length < 30) {
            console.warn(`期數 ${targetDraw.draw} 訓練資料不足 (${trainingData.length} 期)，跳過`);
            return null;
        }

        const sortedTraining = [...trainingData].sort((a, b) => {
            const drawA = Number.parseInt((a.draw || '').toString().replaceAll(/\D/g, ''), 10) || 0;
            const drawB = Number.parseInt((b.draw || '').toString().replaceAll(/\D/g, ''), 10) || 0;
            return drawA - drawB;
        });

        console.log(`🔍 目標期數 ${targetDraw.draw} (${targetDate}): 訓練資料 ${trainingData.length} 期`);
        console.log(`   期數範圍: ${sortedTraining[0]?.draw} ~ ${sortedTraining.at(-1)?.draw}`);
        console.log(`   日期範圍: ${sortedTraining[0]?.date} ~ ${sortedTraining.at(-1)?.date}`);

        const predictionResult = await this.app.predictionEngine.predictWithData(
            method,
            trainingData,
            targetDraw.lotteryType,
            true
        );

        const prediction = {
            numbers: predictionResult.numbers,
            special: predictionResult.special
        };

        console.log(`📊 目標期數 ${targetDraw.draw}: 使用 ${trainingData.length} 期資料預測`);

        const { hits, isSuccess } = this.app.evaluatePrediction(
            targetDraw.numbers,
            prediction.numbers,
            targetDraw.lotteryType,
            targetDraw.special
        );

        try {
            await apiClient.recordPerformanceHit(hits >= 3 ? 1 : 0);
            this.app.uiManager.updateWaterline();
        } catch (e) {
            console.warn('錄入水線績效失敗:', e);
        }

        const refRange = sortedTraining.length > 0
            ? `${sortedTraining[0].draw} - ${sortedTraining.at(-1).draw} (共${trainingData.length}期)`
            : '-';

        return {
            result: {
                draw: targetDraw.draw,
                date: targetDraw.date,
                predicted: prediction.numbers,
                predictedSpecial: prediction.special || null,
                actual: targetDraw.numbers,
                actualSpecial: targetDraw.special || null,
                hits,
                isSuccess,
                refRange
            }
        };
    }

    async runCollaborativeSimulation() {
        const context = this.getCollaborativeContext();
        if (!context) {
            return;
        }

        const { method, targetYear } = context;

        try {
            this.app.uiManager.showNotification('正在進行協作模擬測試...', 'info');

            const allData = this.getCollaborativeAllData();
            const testTargets = this.getSimulationTargetsByYear(allData, targetYear);
            const { results, successCount } = await this.runCollaborativeTargets(method, allData, testTargets);

            this.renderCollaborativeResults(results, successCount);
            this.app.uiManager.showNotification(
                `協作模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${results.length > 0 ? Math.round((successCount / results.length) * 100) : 0}%`,
                'success'
            );
        } catch (error) {
            this.app.uiManager.showNotification('協作模擬失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    getCollaborativeContext() {
        const method = document.getElementById('collab-method').value;
        const yearMonth = document.getElementById('collab-year-month').value;

        if (!yearMonth) {
            this.app.uiManager.showNotification('請選擇年度月份', 'warning');
            return null;
        }

        const [year] = yearMonth.split('-');
        return { method, targetYear: year };
    }

    getCollaborativeAllData() {
        let allData = this.app.dataProcessor.getData();
        if (this.app.currentLotteryType) {
            allData = allData.filter(d => d.lotteryType === this.app.currentLotteryType);
        }
        if (allData.length < 50) {
            throw new Error('數據量不足，無法進行模擬 (至少需要 50 期)');
        }
        return allData;
    }

    async runCollaborativeTargets(method, allData, testTargets) {
        const results = [];
        let successCount = 0;

        for (const targetDraw of testTargets) {
            const targetDate = this.normalizeDate(targetDraw.date);
            const trainingData = allData.filter(d => this.normalizeDate(d.date) < targetDate);
            if (trainingData.length < 30) continue;

            console.log(`📊 協作預測 ${targetDraw.draw}: 使用 ${trainingData.length} 期資料`);

            const predictionResult = await this.app.predictionEngine.predictWithData(
                method,
                trainingData,
                targetDraw.lotteryType,
                true
            );

            const prediction = { numbers: predictionResult.numbers };
            const { hits, isSuccess } = this.app.evaluatePrediction(
                targetDraw.numbers,
                prediction.numbers,
                targetDraw.lotteryType,
                targetDraw.special
            );
            if (isSuccess) successCount++;

            const sortedTraining = [...trainingData].sort((a, b) => {
                const aNum = Number.parseInt((a.draw || '').toString().split('-')[0], 10) || 0;
                const bNum = Number.parseInt((b.draw || '').toString().split('-')[0], 10) || 0;
                return aNum - bNum;
            });

            const refRange = sortedTraining.length > 0
                ? `${sortedTraining[0].draw} - ${sortedTraining.at(-1).draw} (共${trainingData.length}期)`
                : '-';

            results.push({
                draw: targetDraw.draw,
                date: targetDraw.date,
                predicted: prediction.numbers,
                predictedSpecial: prediction.special || null,
                actual: targetDraw.numbers,
                actualSpecial: targetDraw.special || null,
                hits,
                isSuccess,
                refRange
            });
        }

        return { results, successCount };
    }

    renderCollaborativeResults(results, successCount) {
        const tbody = document.querySelector('#collab-simulation-table tbody');
        const rateSpan = document.getElementById('collab-simulation-rate');
        const resultsDiv = document.getElementById('collab-simulation-results');

        if (!(tbody && rateSpan && resultsDiv)) {
            return;
        }

        const rate = results.length > 0 ? Math.round((successCount / results.length) * 100) : 0;
        rateSpan.textContent = rate;

        tbody.innerHTML = results.map(r => `
            <tr class="${r.isSuccess ? 'success-row' : ''}">
                <td>${r.draw}</td>
                <td>${r.date}</td>
                <td>${r.predicted.join(', ')}</td>
                <td>${r.actual.join(', ')}</td>
                <td><span class="hit-badge ${r.hits >= 3 ? 'high-hit' : ''}">${r.hits}</span></td>
                <td>${r.refRange}</td>
                <td>${r.isSuccess ? '✅' : '❌'}</td>
            </tr>
        `).join('');

        resultsDiv.style.display = 'block';
    }
}
