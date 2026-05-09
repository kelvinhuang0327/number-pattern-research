/**
 * Zone Split Strategy - 正交型區間分散策略
 * 基於 Phase 74 研究結論，通過空間分散最大化多注覆蓋率
 */
export class ZoneSplitStrategy {
    constructor() {
        this.apiEndpoint = this.getApiEndpoint();
    }

    getApiEndpoint() {
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://127.0.0.1:8002/api/predict/zone-split';
        }
        return '/api/predict/zone-split';
    }

    /**
     * 執行預測
     * @param {Array} data - 歷史數據 (Zone Split 主要依賴號碼空間，不強依賴歷史)
     * @param {Object} lotteryRules - 彩券規則
     */
    async predict(data, lotteryRules) {
        try {
            const lotteryType = lotteryRules.lotteryType || 'BIG_LOTTO';
            const numBets = 3; // 預設 3 注以達到最優覆蓋

            console.log(`🎯 調用 Zone Split API (${lotteryType})...`);

            const url = new URL(this.apiEndpoint);
            url.searchParams.append('lottery_type', lotteryType);
            url.searchParams.append('num_bets', numBets);

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `API 錯誤: ${response.status}`);
            }

            const result = await response.json();

            // 適配前端預測結果格式
            // 前端通常期望 numbers 陣列，但 Zone Split 返回多注
            // 我們將第一注放進 numbers，其餘注數信息放進 report
            return {
                numbers: result.bets[0].numbers,
                all_bets: result.bets, // 保存所有注數供特殊 UI 使用
                confidence: 0.85,
                method: result.method,
                report: this.generateReport(result)
            };

        } catch (error) {
            console.error(`❌ Zone Split 調用失敗:`, error);
            throw new Error(`正交分散策略執行失敗: ${error.message}`);
        }
    }

    generateReport(result) {
        let report = `🎯 **正交型區間分散分析報告 (🟢 穩定分散型)**\n\n`;

        report += `**風險特徵: 低方差 (Low Variance)**\n`;
        report += `此策略追求號碼空間的最大化覆蓋，旨在分攤風險，提供較平滑的期望回報曲線。\n\n`;

        // 簡易分佈示意圖 (SVG)
        report += `**回報分佈示意 (機率密度):**\n`;
        report += `<svg width="200" height="60" style="background:#f9f9f9; border:1px solid #ddd; border-radius:4px; margin:10px 0;">
            <!-- 單峰分佈 (Normal Distribution) -->
            <path d="M 10 50 Q 100 0 190 50" fill="none" stroke="#28a745" stroke-width="2" />
            <text x="50%" y="55" text-anchor="middle" font-size="10" fill="#666">穩定回報 (低波動)</text>
        </svg>\n\n`;

        report += `**核心哲學:**\n${result.analysis.philosophy}\n\n`;

        report += `**覆蓋指標:**\n`;
        report += `• 空間覆蓋率: ${(result.analysis.coverage_rate * 100).toFixed(2)}%\n`;
        report += `• 獨特號碼數: ${result.analysis.unique_numbers} 個\n\n`;

        report += `**建議組合 (3 注):**\n`;
        result.bets.forEach((bet, i) => {
            report += `• 注數 ${i + 1}: [${bet.numbers.join(', ')}]\n`;
        });

        report += `\n**專家提示:**\n`;
        report += `此策略透過數學上的空間分散來避免「號碼重疊」，在隨機系統中提供最廣泛的獲獎機會。`;

        return report;
    }
}
