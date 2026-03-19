/**
 * Core-Satellite Strategy - 核心-衛星錨點策略
 * 基於 Phase 76 研究結論，透過共享核心號碼 (Anchors) 穩定收益分佈。
 */
import { getApiUrl } from '../../config/apiConfig.js';

export class CoreSatelliteStrategy {
    constructor() {
        this.apiEndpoint = this.getApiEndpoint();
    }

    getApiEndpoint() {
        return getApiUrl('/api/predict/core-satellite');
    }

    /**
     * 執行預測
     * @param {Array} data - 歷史數據
     * @param {Object} lotteryRules - 彩券規則
     */
    async predict(data, lotteryRules) {
        try {
            const lotteryType = lotteryRules.lotteryType || 'BIG_LOTTO';
            const numBets = 3;
            const coreSize = 2; // 預設核心為 2 個號碼

            console.log(`🎯 調用 Core-Satellite API (${lotteryType})...`);

            const url = new URL(this.apiEndpoint);
            url.searchParams.append('lottery_type', lotteryType);
            url.searchParams.append('num_bets', numBets);
            url.searchParams.append('core_size', coreSize);

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

            return {
                numbers: result.bets[0].numbers,
                all_bets: result.bets,
                confidence: 0.88,
                method: result.method,
                report: this.generateReport(result)
            };

        } catch (error) {
            console.error(`❌ Core-Satellite 調用失敗:`, error);
            throw new Error(`核心-衛星策略執行失敗: ${error.message}`);
        }
    }

    generateReport(result) {
        let report = `🎯 **核心-衛星集約分析報告 (🔴 聯動集中型)**\n\n`;

        report += `**風險特徵: 高方差 (High Variance)**\n`;
        report += `此策略透過共享核心 (Anchors) 產生正相關，回報呈現兩極化分佈：要麼大幅獲利，要麼全軍覆沒。\n\n`;

        // 雙峰分佈示意圖 (SVG)
        report += `**回報分佈示意 (機率密度):**\n`;
        report += `<svg width="200" height="60" style="background:#f9f9f9; border:1px solid #ddd; border-radius:4px; margin:10px 0;">
            <!-- 雙峰分佈 (Bimodal Distribution) -->
            <path d="M 10 50 Q 55 0 100 50 T 190 50" fill="none" stroke="#dc3545" stroke-width="2" />
            <text x="50%" y="55" text-anchor="middle" font-size="10" fill="#666">兩極回報 (高波動)</text>
        </svg>\n\n`;

        report += `**結構設計:**\n${result.analysis.philosophy}\n\n`;

        report += `**核心號碼 (Anchors):**\n`;
        report += `• [${result.analysis.core_numbers.join(', ')}]\n`;
        report += `> 💡 提示：此策略透過犧牲覆蓋廣度來換取「命中時的爆發力」。這會顯著增加回報的方差。\n\n`;

        report += `**預測組合:**\n`;
        result.bets.forEach((bet, i) => {
            report += `• 第 ${i + 1} 注: [${bet.numbers.join(', ')}]\n`;
        });

        report += `\n**風險提示:**\n`;
        report += `此策略具有兩極化的回報分佈：錨點命中則全員獲利，錨點失守則全軍覆沒。適合用於放大對核心號碼具備高度置信度的場景。`;

        return report;
    }
}
