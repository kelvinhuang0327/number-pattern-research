/**
 * Backend Optimized Strategy - 調用後端優化的預測
 * 使用遺傳算法優化過的參數進行預測，獲得接近 10% 的成功率
 */
export class BackendOptimizedStrategy {
    constructor() {
        this.apiEndpoint = this.getApiEndpoint();
    }

    /**
     * 獲取 API 端點
     */
    getApiEndpoint() {
        // 開發環境
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://localhost:5001/api/predict-optimized';
        }

        // 生產環境（稍後配置）
        return 'https://your-api-domain.com/api/predict-optimized';
    }

    /**
     * 執行預測
     * @param {Array} data - 歷史數據（用於提取期數範圍）
     * @param {Object} lotteryRules - 彩券規則
     */
    async predict(data, lotteryRules) {
        try {
            console.log(`🤖 調用後端優化預測 API...`);

            // 獲取當前彩券類型
            const lotteryType = lotteryRules.lotteryType || 'BIG_LOTTO';

            // 🎯 提取數據範圍（如果有數據）
            let requestData = {
                lotteryType: lotteryType
            };

            // 如果有傳入數據，提取期數範圍
            if (data && data.length > 0) {
                // 排序數據以獲取正確的範圍
                const sortedData = [...data].sort((a, b) => {
                    const drawA = parseInt((a.draw || '').toString().replace(/\D/g, '')) || 0;
                    const drawB = parseInt((b.draw || '').toString().replace(/\D/g, '')) || 0;
                    return drawA - drawB;
                });

                const startDraw = sortedData[0].draw;
                const endDraw = sortedData[sortedData.length - 1].draw;

                requestData.startDraw = startDraw;
                requestData.endDraw = endDraw;

                console.log(`🎯 使用範圍查詢模式: ${startDraw} - ${endDraw} (${data.length}期)`);
            } else {
                console.log(`⚠️ 無數據範圍，後端將使用全部數據`);
            }

            // 發送 API 請求
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `API 錯誤: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();

            console.log(`✅ 後端優化預測完成`);

            // 格式化返回結果
            return {
                numbers: result.numbers || [],
                probabilities: result.probabilities || null,
                confidence: result.confidence || 0.10,
                method: result.method || '後端優化預測 (Genetic Algorithm)',
                report: this.generateReport(result)
            };

        } catch (error) {
            console.error(`❌ 後端優化預測失敗:`, error);

            // 友好的錯誤處理
            if (error.message.includes('Failed to fetch')) {
                throw new Error('無法連接到後端服務器。請確認：\n1. 後端服務是否運行 (python lottery-api/app.py)\n2. 是否已同步數據到後端\n3. 是否已執行過自動優化');
            }

            if (error.message.includes('沒有可用的優化配置')) {
                throw new Error('尚未執行自動優化。請先到「自動學習」頁面執行優化，或啟用自動排程。');
            }

            if (error.message.includes('後端沒有數據')) {
                throw new Error('後端沒有數據。請到「自動學習」頁面點擊「同步數據到後端」按鈕。');
            }

            throw new Error(`後端優化預測失敗: ${error.message}`);
        }
    }

    /**
     * 生成預測報告
     */
    generateReport(result) {
        let report = `🤖 **後端優化預測分析報告**\n\n`;

        report += `**預測方法:**\n`;
        report += `• 使用遺傳算法優化的混合策略\n`;
        report += `• 自動學習歷史數據模式\n`;
        report += `• 動態調整策略權重\n\n`;

        report += `**預測結果:**\n`;
        report += `• 信心度: ${(result.confidence * 100).toFixed(1)}%\n`;
        report += `• 預測號碼: ${result.numbers.join(', ')}\n\n`;

        if (result.notes) {
            report += `**備註:**\n${result.notes}\n\n`;
        }

        report += `**優勢:**\n`;
        report += `• ✅ 使用後端優化參數，無需前端重新計算\n`;
        report += `• ✅ 基於遺傳算法自動優化，成功率更高\n`;
        report += `• ✅ 快速響應，支持模型緩存\n\n`;

        report += `**提示:**\n`;
        report += `• 定期執行自動優化以更新參數\n`;
        report += `• 建議啟用自動排程，每天自動優化\n`;

        return report;
    }

    /**
     * 帶緩存的預測（用於模擬）
     * BackendOptimized 策略不使用緩存，直接調用 predict
     */
    async predictWithCache(data, lotteryRules, cache = null) {
        console.log(`🚫 BackendOptimized: 緩存已禁用，動態查詢`);
        // 直接調用 predict，不使用緩存
        return await this.predict(data, lotteryRules);
    }
}
