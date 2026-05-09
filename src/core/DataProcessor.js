import { LOTTERY_RULES, detectLotteryType, LOTTERY_TYPES } from '../utils/Constants.js';
import { isValidNumber, isValidSpecialNumber, getRelatedTypes } from '../utils/LotteryTypes.js';
import { apiClient } from '../services/ApiClient.js';

/**
 * 數據處理模組
 * 負責處理樂透數據的加載、解析、驗證和管理
 * 🚀 優化：完全依賴後端數據，前端僅做暫存與顯示
 */
export class DataProcessor {
    constructor() {
        this.lotteryData = [];
        this.sampleData = this.generateSampleData();
    }

    /**
     * 從後端獲取所有歷史數據
     */
    async fetchDataFromBackend() {
        try {
            console.log('🔄 Fetching history from backend...');
            const data = await apiClient.getAllHistory();

            // 排序：最新的在前面
            data.sort((a, b) => {
                const dateA = a.date.replace(/\//g, '-');
                const dateB = b.date.replace(/\//g, '-');
                return dateB.localeCompare(dateA);
            });

            this.lotteryData = data;
            console.log(`✅ Loaded ${data.length} records from backend`);
            return data;
        } catch (error) {
            console.error('Failed to load from backend:', error);
            // 如果失敗，載入示範數據以免空白
            if (this.lotteryData.length === 0) {
                console.warn('⚠️ Backend unreachable, loading sample data');
                this.loadSampleData();
            }
            return this.lotteryData;
        }
    }

    /**
     * 生成示範數據（大樂透）
     */
    generateSampleData() {
        const data = [];
        const startDate = new Date('2023-01-01');
        const totalDraws = 50;

        for (let i = 0; i < totalDraws; i++) {
            const drawDate = new Date(startDate);
            drawDate.setDate(startDate.getDate() + (i * 3)); // 每3天一期

            const numbers = this.generateRandomNumbers(LOTTERY_RULES.pickCount, LOTTERY_RULES.numberRange.min, LOTTERY_RULES.numberRange.max);
            let specialNumber;
            do {
                specialNumber = Math.floor(Math.random() * LOTTERY_RULES.numberRange.max) + LOTTERY_RULES.numberRange.min;
            } while (numbers.includes(specialNumber));

            data.push({
                draw: String(113000000 + i + 1).padStart(9, '0'),
                date: drawDate.toISOString().split('T')[0],
                lotteryType: 'BIG_LOTTO',
                numbers: numbers.sort((a, b) => a - b),
                special: specialNumber
            });
        }
        return data;
    }

    generateRandomNumbers(count, min, max) {
        const numbers = new Set();
        while (numbers.size < count) {
            numbers.add(Math.floor(Math.random() * (max - min + 1)) + min);
        }
        return Array.from(numbers);
    }

    readFileContent(file, encoding = 'UTF-8') {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('檔案讀取失敗'));
            reader.readAsText(file, encoding);
        });
    }

    isValidContent(text) {
        if (!text) return false;
        const firstLines = text.slice(0, 500);
        return firstLines.includes('遊戲名稱') ||
            firstLines.includes('期別') ||
            firstLines.includes('大樂透') ||
            firstLines.includes('Lotto') ||
            firstLines.includes('春節加碼活動');
    }

    async parseCSV(file) {
        try {
            let text = await this.readFileContent(file, 'UTF-8');
            if (!this.isValidContent(text)) {
                console.log('UTF-8 parsing failed/invalid, retrying with Big5...');
                text = await this.readFileContent(file, 'Big5');
            }

            const lines = text.split(/\r?\n/).filter(line => line.trim());
            if (lines.length < 2) throw new Error('檔案內容為空');

            let data = [];
            try {
                data = this.parseStandardFormat(lines);
            } catch (e) {
                console.warn('Standard parsing failed, trying heuristic:', e);
            }

            if (data.length === 0) {
                console.log('Using heuristic parsing...');
                data = this.parseHeuristic(lines);
            }

            if (data.length === 0) {
                const snippet = lines.slice(0, 3).join('\n');
                throw new Error(`無法解析CSV檔案 (無有效數據)。\n檔案前三行內容:\n${snippet}`);
            }

            return data;

        } catch (error) {
            throw new Error('CSV解析錯誤: ' + error.message);
        }
    }

    parseStandardFormat(lines) {
        const data = [];
        const firstLine = lines[0].trim();
        const hasGameNameColumn = firstLine.includes('遊戲名稱');

        if (!hasGameNameColumn) {
            console.warn('CSV 缺少遊戲名稱欄位，無法偵測彩券類型');
            return data;
        }

        const drawCounters = {};

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            let parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));

            // 嘗試使用空白分隔（如果逗號分隔無效）
            if (parts.length <= 1) {
                parts = line.trim().split(/[\s\t]+/).map(p => p.trim());
            }

            const gameName = parts[0];

            if (gameName.includes('賓果') || gameName.toUpperCase().includes('BINGO')) {
                continue;
            }

            const lotteryType = detectLotteryType(gameName);
            if (!lotteryType) {
                continue;
            }

            const minFields = 6 + lotteryType.pickCount;

            // 🌟 修正：如果欄位不足，自動補空白
            while (parts.length < minFields) {
                parts.push('');
            }

            const rawDraw = parts[1];
            const date = parts[2].replace(/\//g, '-');

            const counterKey = `${lotteryType.id}_${rawDraw}`;
            if (!drawCounters[counterKey]) {
                drawCounters[counterKey] = 1;
            } else {
                drawCounters[counterKey]++;
            }

            const draw = (drawCounters[counterKey] > 1 || lotteryType.id === 'BIG_LOTTO_BONUS')
                ? `${rawDraw}-${String(drawCounters[counterKey]).padStart(2, '0')}`
                : rawDraw;

            const numberStartIndex = 6;
            const numbers = parts.slice(numberStartIndex, numberStartIndex + lotteryType.pickCount)
                .map(n => parseInt(n));

            let special = 0;
            if (lotteryType.hasSpecialNumber && parts.length > numberStartIndex + lotteryType.pickCount) {
                special = parseInt(parts[numberStartIndex + lotteryType.pickCount]);
            }

            if (this.validateDraw(numbers, special, lotteryType)) {
                data.push({
                    draw,
                    date,
                    lotteryType: lotteryType.id,
                    numbers: numbers.sort((a, b) => a - b),
                    special
                });
            }
        }
        return data;
    }

    parseHeuristic(lines) {
        const data = [];
        const drawCounters = {};

        console.log(`Starting heuristic parsing on ${lines.length} lines...`);

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const parts = line.replace(/"/g, '').split(/[,，\s\t]+/).map(p => p.trim()).filter(p => p);

            if (parts.length < 7) continue;

            let date = null;
            let dateIndex = -1;
            const dateRegex = /^(\d{3,4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/;

            for (let j = 0; j < parts.length; j++) {
                const match = parts[j].match(dateRegex);
                if (match) {
                    let year = parseInt(match[1]);
                    const month = parseInt(match[2]);
                    const day = parseInt(match[3]);
                    if (year < 1000) year += 1911;
                    date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                    dateIndex = j;
                    break;
                }
            }

            if (!date) continue;

            let numbers = [];
            let special = 0;
            let foundSequence = false;

            for (let j = 0; j <= parts.length - 6; j++) {
                if (j === dateIndex) continue;

                const window = parts.slice(j, j + 6);
                const validWindow = window.every(p => {
                    const n = parseInt(p);
                    return !isNaN(n) && n >= 1 && n <= 49;
                });

                if (validWindow) {
                    const nextPart = (j + 6 < parts.length) ? parts[j + 6] : null;
                    const nextNum = nextPart ? parseInt(nextPart) : NaN;
                    const hasSpecial = !isNaN(nextNum) && nextNum >= 1 && nextNum <= 49;

                    numbers = window.map(n => parseInt(n));
                    special = hasSpecial ? nextNum : 0;

                    const unique = new Set(numbers);
                    if (unique.size === 6) {
                        foundSequence = true;
                        break;
                    }
                }
            }

            if (foundSequence) {
                let rawDraw = parts.find(p => /^\d{9,}$/.test(p));
                if (!rawDraw) {
                    rawDraw = date.replace(/-/g, '');
                }

                if (!drawCounters[rawDraw]) drawCounters[rawDraw] = 1;
                else drawCounters[rawDraw]++;

                const draw = (drawCounters[rawDraw] > 1 || line.includes('加開') || line.includes('春節'))
                    ? `${rawDraw}-${String(drawCounters[rawDraw]).padStart(2, '0')}`
                    : rawDraw;

                const lotteryType = this.detectLotteryTypeFromNumbers(numbers, special);

                data.push({
                    draw,
                    date,
                    lotteryType,
                    numbers: numbers.sort((a, b) => a - b),
                    special
                });
            }
        }

        console.log(`Heuristic parsing found ${data.length} records.`);
        return data;
    }

    detectLotteryTypeFromNumbers(numbers, special) {
        if (!numbers || numbers.length === 0) {
            return 'BIG_LOTTO';
        }

        const maxNum = Math.max(...numbers);
        const minNum = Math.min(...numbers);
        const count = numbers.length;

        if (count === 6 && maxNum <= 49 && minNum >= 1) {
            return special > 0 ? 'BIG_LOTTO' : 'BIG_LOTTO';
        } else if (count === 5 && maxNum <= 39 && minNum >= 1) {
            return 'DAILY_539';
        } else if (count === 6 && maxNum <= 38 && minNum >= 1) {
            return '39_LOTTO';
        } else if (count === 3) {
            return '3_STAR';
        } else if (count === 4) {
            return '4_STAR';
        }

        return 'BIG_LOTTO';
    }

    validateDraw(numbers, special, lotteryType = LOTTERY_TYPES.BIG_LOTTO) {
        if (!Array.isArray(numbers) || numbers.length !== lotteryType.pickCount) return false;
        const validNumbers = numbers.filter(n => isValidNumber(n, lotteryType));
        if (validNumbers.length !== lotteryType.pickCount) return false;
        const allowDuplicates = ['STAR_3', 'STAR_4'].includes(lotteryType.id);
        if (!allowDuplicates) {
            const uniqueNumbers = new Set(validNumbers);
            if (uniqueNumbers.size !== validNumbers.length) return false;
        }
        if (!isValidSpecialNumber(special, lotteryType)) return false;
        return true;
    }

    loadSampleData() {
        this.lotteryData = [...this.sampleData];
        return this.lotteryData;
    }

    /**
     * 載入CSV/TXT檔案數據 (僅解析，不保存到本地)
     * @param {File} file - 要處理的文件
     * @param {string} playMode - 玩法模式（可選，適用於樂合彩系列）
     */
    async loadCSVData(file, playMode = null) {
        console.log(`📂 Loading ${file.name}...`);
        if (file.name.includes('賓果') || file.name.toUpperCase().includes('BINGO')) {
            console.warn(`⚠️ 跳過檔案 ${file.name}：不支援賓果賓果數據`);
            return { newCount: 0, totalCount: this.lotteryData.length, skipped: true, message: '已跳過賓果賓果檔案' };
        }

        // 判斷文件類型
        const fileExt = file.name.toLowerCase().split('.').pop();

        let newData;
        if (fileExt === 'txt') {
            // TXT 格式：調用後端 API 進行解析
            console.log(`  → Detected TXT format, using backend parser...`);
            newData = await this.parseTXTViaBackend(file, playMode);
        } else {
            // CSV 格式：使用前端解析
            newData = await this.parseCSV(file);
        }

        console.log(`  → Parsed ${newData.length} records from ${file.name}`);

        // 注意：這裡不再合併到 this.lotteryData，而是返回解析結果
        // 由 App.js 負責上傳到後端，然後重新 fetch
        return {
            data: newData,
            parsedCount: newData.length
        };
    }

    /**
     * 通過後端 API 解析 TXT 文件（今彩539格式）
     * @param {File} file - 要解析的文件
     * @param {string} playMode - 玩法模式（可選，僅適用於樂合彩系列）
     */
    async parseTXTViaBackend(file, playMode = null) {
        try {
            // 從文件名推斷彩券類型
            let lotteryType = 'DAILY_539'; // 默認
            if (file.name.includes('今彩539')) {
                lotteryType = 'DAILY_539';
            } else if (file.name.includes('大樂透')) {
                lotteryType = 'BIG_LOTTO';
            } else if (file.name.includes('威力彩')) {
                lotteryType = 'POWER_LOTTO';
            } else if (file.name.includes('49樂合彩')) {
                lotteryType = '49_LOTTO';
            } else if (file.name.includes('39樂合彩')) {
                lotteryType = '39_LOTTO';
            } else if (file.name.includes('38樂合彩')) {
                lotteryType = '38_LOTTO';
            } else if (file.name.includes('4星彩') || file.name.includes('四星彩')) {
                lotteryType = '4_STAR';
            } else if (file.name.includes('3星彩') || file.name.includes('三星彩')) {
                lotteryType = '3_STAR';
            } else if (file.name.includes('雙贏彩')) {
                lotteryType = 'DOUBLE_WIN';
            } else if (file.name.includes('6/38')) {
                lotteryType = 'LOTTO_6_38';
            }

            // 調用後端驗證API
            const formData = new FormData();
            formData.append('file', file);
            formData.append('lottery_type', lotteryType);

            // 如果指定了玩法模式，添加到請求中
            if (playMode) {
                formData.append('play_mode', playMode);
                console.log(`  → Using play mode: ${playMode}`);
            }

            const response = await fetch('http://localhost:8002/api/data/validate-csv', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`後端解析失敗: ${response.statusText}`);
            }

            const result = await response.json();

            if (!result.valid) {
                const errorMsg = result.errors.map(e => `行 ${e.line}: ${e.message}`).join('\n');
                throw new Error(`TXT 驗證失敗:\n${errorMsg}`);
            }

            console.log(`  ✓ Backend validation: ${result.stats.valid_rows} valid rows`);
            return result.parsed_data;

        } catch (error) {
            console.error('TXT parsing error:', error);
            throw new Error('TXT解析錯誤: ' + error.message);
        }
    }

    checkDuplicates(newData) {
        // 保留此方法以防萬一，但目前主要依賴後端去重
        return { mergedData: newData, duplicates: [], duplicateCount: 0, newCount: newData.length, totalCount: newData.length };
    }

    getData() {
        return this.lotteryData;
    }

    async getDataRange(sampleSize, lotteryType = null) {
        let data = this.lotteryData;
        if (lotteryType) {
            // ✅ 使用 getRelatedTypes 獲取相關類型（例如：大樂透 + 大樂透加開）
            const relatedTypes = getRelatedTypes(lotteryType);
            data = data.filter(d => relatedTypes.includes(d.lotteryType));
        }

        if (sampleSize === 'all') {
            return data;
        }
        const requestedSize = parseInt(sampleSize);
        return data.slice(0, requestedSize);
    }

    async getDataSmart(lotteryType = null, sampleSize = 0) {
        return this.getDataRange(sampleSize || 'all', lotteryType);
    }

    clearData() {
        this.lotteryData = [];
        return this.lotteryData;
    }

    searchData(query) {
        if (!query) return this.lotteryData;
        return this.lotteryData.filter(draw =>
            draw.draw.includes(query) ||
            draw.date.includes(query)
        );
    }

    sortData(order = 'desc') {
        return [...this.lotteryData].sort((a, b) =>
            order === 'desc' ?
                b.draw.localeCompare(a.draw) :
                a.draw.localeCompare(b.draw)
        );
    }

    async getStats() {
        const typeCount = {};
        this.lotteryData.forEach(d => {
            const type = d.lotteryType || 'UNKNOWN';
            typeCount[type] = (typeCount[type] || 0) + 1;
        });

        return {
            total: this.lotteryData.length,
            byType: typeCount
        };
    }
}
