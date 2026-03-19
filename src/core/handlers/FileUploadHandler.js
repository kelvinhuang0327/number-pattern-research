import { getLotteryRules } from '../../utils/Constants.js';
import { apiClient } from '../../services/ApiClient.js';
import { progressManager } from '../../ui/ProgressManager.js';

/**
 * FileUploadHandler - 處理文件上傳相關邏輯
 */
export class FileUploadHandler {
    constructor(app) {
        this.app = app;
        this.dataProcessor = app.dataProcessor;
        this.uiManager = app.uiManager;
    }

    /**
     * 檢查檔名是否應該被忽略
     * @param {string} filename - 檔案名稱
     * @returns {boolean} - 是否應該忽略
     */
    shouldIgnoreFile(filename) {
        // 🌟 允許所有遊戲數據上傳，不做任何限制
        return false;
    }

    /**
     * 處理單個文件上傳
     */
    async handleFileUpload(file) {
        try {
            if (this.shouldIgnoreFile(file.name)) {
                this.uiManager.showNotification(`⚠️ 僅支援「大樂透」檔案上傳\n已忽略: ${file.name}`, 'warning');
                return;
            }

            // 顯示進度
            progressManager.show('正在解析檔案...', 10);

            // 1. 解析檔案 (不保存到本地)
            const result = await this.dataProcessor.loadCSVData(file);
            progressManager.updateProgress(30, '解析完成，準備上傳...');

            if (result.skipped) {
                progressManager.hide(0);
                return;
            }

            if (result.data.length === 0) {
                progressManager.hide(0);
                this.uiManager.showNotification('檔案中沒有有效數據', 'warning');
                return;
            }

            // 2. 上傳到後端
            progressManager.updateProgress(50, `正在上傳 ${result.data.length} 筆數據...`);
            const lotteryRules = getLotteryRules(result.data[0].lotteryType);
            await apiClient.uploadDraws(result.data, lotteryRules);
            progressManager.updateProgress(70, '上傳完成，正在刷新數據...');

            // 3. 重新從後端獲取最新數據
            await this.dataProcessor.fetchDataFromBackend();
            progressManager.updateProgress(90, '更新統計資訊...');

            // 4. 更新 UI
            const stats = await this.dataProcessor.getStats();
            this.app.updateDataSummaryFromStats(stats);
            this.app.showLotteryTypeSelector(stats);

            progressManager.updateProgress(100, '完成！');
            progressManager.hide(1000);

            this.uiManager.showNotification(`✅ 數據已更新！目前共有 ${stats.total} 筆數據`, 'success');

            // 自動切換到剛上傳的類型
            if (result.data.length > 0) {
                const newType = result.data[0].lotteryType;
                if (newType && newType !== this.app.currentLotteryType) {
                    this.app.currentLotteryType = newType;
                    this.app.handleLotteryTypeChange();
                }
            }

        } catch (error) {
            progressManager.hide(0);
            console.error('File upload failed:', error);
            this.uiManager.showNotification('檔案處理失敗: ' + error.message, 'error');
        }
    }

    /**
     * 顯示上傳引導
     */
    showUploadGuidance(stats) {
        const guidanceElement = document.getElementById('upload-guidance');
        if (!guidanceElement || !stats || !stats.lotteryTypeCount) return;

        const typeCount = Object.keys(stats.lotteryTypeCount).length;
        const totalDraws = stats.totalDraws;

        guidanceElement.style.display = 'flex';

        const guidanceContent = guidanceElement.querySelector('.guidance-content');
        if (guidanceContent) {
            guidanceContent.innerHTML = `
                <h4>✨ 上傳成功！下一步：</h4>
                <p>系統已識別出 <strong>${typeCount}</strong> 種彩券類型，共 <strong>${totalDraws}</strong> 筆數據。<br>
                請在下方選擇您要分析的彩券類型。</p>
            `;
        }

        // 3秒後淡出引導
        setTimeout(() => {
            if (guidanceElement) {
                guidanceElement.style.opacity = '0';
                setTimeout(() => {
                    guidanceElement.style.display = 'none';
                    guidanceElement.style.opacity = '1';
                }, 500);
            }
        }, 5000);
    }

    /**
     * 處理多個文件上傳
     */
    async handleMultipleFileUpload(files) {
        try {
            // 🔍 過濾檔案：根據下拉選項進行過濾
            const filteredFiles = [];
            const ignoredFiles = [];
            const filterSelect = document.getElementById('upload-filter-select');
            const filterValue = filterSelect ? filterSelect.value : 'ALL';

            console.log(`📂 Upload Filter Mode: ${filterValue}`);

            for (let i = 0; i < files.length; i++) {
                const fileName = files[i].name;
                let shouldProcess = false;

                // 檢查是否為系統忽略檔案
                if (this.shouldIgnoreFile(fileName)) {
                    ignoredFiles.push(fileName);
                    continue;
                }

                // 根據篩選器判斷
                if (filterValue === 'ALL') {
                    // 全部模式：忽略賓果賓果
                    const isBingo = fileName.includes('賓果') || fileName.includes('BINGO');
                    if (!isBingo) {
                        shouldProcess = true;
                    } else {
                        console.log(`🚫 忽略賓果檔案 (ALL模式): ${fileName}`);
                        ignoredFiles.push(fileName + ' (賓果)');
                    }
                } else if (filterValue === 'BIG_LOTTO') {
                    // 大樂透 (不含加開) -> 這裡使用嚴格過濾或寬鬆過濾?
                    // 通常"大樂透"檔案名就是"大樂透_xxxx.csv"。 "大樂透加開"是"大樂透加開獎項_xxxx.csv"
                    // 如果用戶選"大樂透"，是否要包含加開? 用戶分開列了，所以這裡分開處理
                    if (fileName.includes('大樂透') && !fileName.includes('加開')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'BIG_LOTTO_BONUS') {
                    // 大樂透加開
                    if (fileName.includes('大樂透') && fileName.includes('加開')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'DAILY_539') {
                    // 今彩539
                    if (fileName.includes('今彩539') || fileName.includes('539')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'POWER_LOTTO') {
                    // 威力彩
                    if (fileName.includes('威力彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'STAR_3') {
                    // 3星彩
                    if (fileName.includes('3星彩') || fileName.includes('三星彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'STAR_4') {
                    // 4星彩
                    if (fileName.includes('4星彩') || fileName.includes('四星彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'LOTTO_39') {
                    // 39樂合彩
                    if (fileName.includes('39樂合彩')) {
                        shouldProcess = true;
                    }
                } else if (filterValue === 'LOTTO_49') {
                    // 49樂合彩
                    if (fileName.includes('49樂合彩')) {
                        shouldProcess = true;
                    }
                }

                if (shouldProcess) {
                    filteredFiles.push(files[i]);
                } else {
                    ignoredFiles.push(fileName);
                }
            }

            // 顯示過濾結果
            if (ignoredFiles.length > 0) {
                const ignoredList = ignoredFiles.slice(0, 10).join('\n• ');
                const moreCount = ignoredFiles.length > 10 ? `\n• ...及其他 ${ignoredFiles.length - 10} 個檔案` : '';

                let filterName = '自訂';
                if (filterValue === 'ALL') filterName = '全部(忽略賓果)';
                if (filterValue === 'BIG_LOTTO') filterName = '大樂透';
                if (filterValue === 'BIG_LOTTO_BONUS') filterName = '大樂透加開';
                if (filterValue === 'DAILY_539') filterName = '今彩539';
                if (filterValue === 'POWER_LOTTO') filterName = '威力彩';
                if (filterValue === 'STAR_3') filterName = '3星彩';
                if (filterValue === 'STAR_4') filterName = '4星彩';
                if (filterValue === 'LOTTO_39') filterName = '39樂合彩';
                if (filterValue === 'LOTTO_49') filterName = '49樂合彩';

                this.uiManager.showNotification(
                    `⚠️ 已根據「${filterName}」過濾檔案\n\n` +
                    `📋 將載入: ${filteredFiles.length} 個檔案\n` +
                    `🚫 已忽略: ${ignoredFiles.length} 個檔案\n\n` +
                    `忽略的檔案:\n• ${ignoredList}${moreCount}`,
                    'warning',
                    8000  // 顯示 8 秒
                );
            }

            if (filteredFiles.length === 0) {
                this.uiManager.showNotification(
                    '❌ 沒有可載入的檔案\n\n' +
                    '所選資料夾中沒有符合條件的檔案。\n' +
                    `當前過濾模式: ${filterValue}`,
                    'error'
                );
                return;
            }

            // 顯示進度
            progressManager.show(`正在解析 ${filteredFiles.length} 個檔案...`, 5);
            let totalParsed = 0;
            let successCount = 0;
            const fileResults = [];
            let allParsedData = [];

            for (let i = 0; i < filteredFiles.length; i++) {
                const progress = 5 + (i / filteredFiles.length) * 40; // 5-45%
                progressManager.updateProgress(progress, `正在解析第 ${i + 1}/${filteredFiles.length} 個檔案...`);

                try {
                    const result = await this.dataProcessor.loadCSVData(filteredFiles[i]);
                    if (result.data && result.data.length > 0) {
                        allParsedData = allParsedData.concat(result.data);
                        totalParsed += result.data.length;
                        successCount++;
                        fileResults.push({
                            name: filteredFiles[i].name,
                            count: result.data.length,
                            success: true
                        });
                    }
                } catch (err) {
                    console.warn(`File ${filteredFiles[i].name} failed:`, err);
                    fileResults.push({ name: filteredFiles[i].name, error: err.message, success: false });
                }
            }

            // 上傳到後端
            if (allParsedData.length > 0) {
                progressManager.updateProgress(50, `正在上傳 ${totalParsed} 筆數據...`);
                const lotteryRules = getLotteryRules(allParsedData[0].lotteryType);
                await apiClient.uploadDraws(allParsedData, lotteryRules);
                progressManager.updateProgress(75, '上傳完成，正在刷新數據...');
                await this.dataProcessor.fetchDataFromBackend();
            }

            // 更新 UI
            progressManager.updateProgress(90, '更新統計資訊...');
            const stats = await this.dataProcessor.getStats();
            this.app.updateDataSummaryFromStats(stats);
            this.app.showLotteryTypeSelector(stats);

            // 建立詳細訊息
            let detailMsg = `批次載入完成！\n✅ 成功: ${successCount}/${filteredFiles.length} 個檔案`;
            if (ignoredFiles.length > 0) {
                detailMsg += `\n⚠️ 已忽略: ${ignoredFiles.length} 個不符條件的檔案`;
            }
            detailMsg += `\n📊 共解析: ${totalParsed} 筆\n📦 目前總數: ${stats.total} 筆\n\n`;

            if (stats && stats.byType) {
                detailMsg += '各彩券類型總數：\n';
                const typeNames = {
                    'BIG_LOTTO': '大樂透',
                    'BIG_LOTTO_BONUS': '大樂透加開',
                    'STAR_3': '三星彩',
                    'STAR_4': '四星彩',
                    'LOTTO_39': '39樂合彩',
                    'DAILY_CASH_539': '今彩539'
                };
                Object.entries(stats.byType).forEach(([type, count]) => {
                    detailMsg += `• ${typeNames[type] || type}: ${count} 筆\n`;
                });
            }

            progressManager.updateProgress(100, '完成！');
            progressManager.hide(1000);

            this.uiManager.showNotification(detailMsg, 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) {
                const successFiles = fileResults.filter(f => f.success);
                const failedFiles = fileResults.filter(f => !f.success);

                let html = `<div style="color: #22c55e; font-weight: 500;">`;
                html += `✓ 已批次載入 ${successCount} 個檔案<br>`;
                html += `<div style="font-size: 0.85em; margin-top: 8px; line-height: 1.6;">`;

                successFiles.forEach(f => {
                    const displayCount = f.parsed || f.count;
                    html += `• ${f.name}: ${displayCount} 筆`;
                    if (f.parsed && f.parsed > f.count) {
                        html += ` <span style="color: #f59e0b;">(${f.count} 新增)</span>`;
                    }
                    html += `<br>`;
                });

                if (failedFiles.length > 0) {
                    html += `</div><div style="color: #ef4444; margin-top: 8px;">`;
                    html += `✗ 失敗 ${failedFiles.length} 個檔案<br>`;
                    failedFiles.forEach(f => {
                        html += `• ${f.name}<br>`;
                    });
                }

                html += `</div></div>`;
                fileInfo.innerHTML = html;
            }

        } catch (error) {
            progressManager.hide(0);
            this.uiManager.showNotification('批次載入失敗: ' + error.message, 'error');
            console.error(error);
        }
    }

    /**
     * 載入範例數據
     */
    async loadSampleData() {
        try {
            progressManager.show('正在加載範例數據...', 10);

            this.dataProcessor.loadSampleData();
            const sampleData = this.dataProcessor.getData();
            progressManager.updateProgress(30, '範例數據已生成...');

            // 上傳到後端
            progressManager.updateProgress(50, '正在上傳到後端...');
            const lotteryRules = getLotteryRules('BIG_LOTTO');
            await apiClient.uploadDraws(sampleData, lotteryRules);
            progressManager.updateProgress(75, '上傳完成，正在刷新...');

            // 重新從後端獲取
            await this.dataProcessor.fetchDataFromBackend();
            progressManager.updateProgress(90, '更新顯示...');
            await this.app.updateDataSummary();

            progressManager.updateProgress(100, '完成！');
            progressManager.hide(1000);

            this.uiManager.showNotification('範例數據載入成功！', 'success');

            const fileInfo = document.getElementById('file-info');
            if (fileInfo) fileInfo.textContent = '✓ 已載入範例數據';
        } catch (error) {
            progressManager.hide(0);
            this.uiManager.showNotification('範例數據加載失敗: ' + error.message, 'error');
        }
    }
}
