import { apiClient } from '../../services/ApiClient.js';

/**
 * SimulationHandler
 * Simulates predictions for each draw in a selected year-month and reports success rate.
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

        try {
            this.app.setButtonLoading(simulationBtn, true);
            this.app.uiManager.showNotification('正在進行模擬測試...', 'info');

            this.app._autoOptimizeCache = null;

            const allData = await this.getSimulationAllData();
            const testTargets = this.getSimulationTargetsByYear(allData, year);
            const { results, successCount } = await this.runSimulationByTargets(method, allData, testTargets);

            this.app.displaySimulationResults(results, successCount);

            this.app.uiManager.showNotification(
                `模擬完成！測試 ${results.length} 期，成功 ${successCount} 期，成功率: ${results.length > 0 ? Math.round((successCount / results.length) * 100) : 0}%`,
                'success'
            );
        } catch (error) {
            this.app.uiManager.showNotification('模擬失敗: ' + error.message, 'error');
            console.error('[SimulationHandler]', error);
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
            const simulationResult = await this.runSingleSimulationTarget(method, allData, targetDraw);
            if (!simulationResult) continue;

            results.push(simulationResult.result);
            if (simulationResult.result.isSuccess) successCount++;
        }

        return { results, successCount };
    }

    async runSingleSimulationTarget(method, allData, targetDraw) {
        const targetDate = this.normalizeDate(targetDraw.date);
        const trainingData = allData.filter(d => this.normalizeDate(d.date) < targetDate);

        if (trainingData.length < 30) {
            console.warn(`[SimulationHandler] 期數 ${targetDraw.draw} 訓練資料不足 (${trainingData.length} 期)，跳過`);
            return null;
        }

        const sortedTraining = [...trainingData].sort((a, b) => {
            const drawA = Number.parseInt((a.draw || '').toString().replaceAll(/\D/g, ''), 10) || 0;
            const drawB = Number.parseInt((b.draw || '').toString().replaceAll(/\D/g, ''), 10) || 0;
            return drawA - drawB;
        });

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
            console.warn('[SimulationHandler] 錄入水線績效失敗:', e);
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
}
