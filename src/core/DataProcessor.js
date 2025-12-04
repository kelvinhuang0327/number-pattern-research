import { LOTTERY_RULES, detectLotteryType, LOTTERY_TYPES } from '../utils/Constants.js';
import { isValidNumber, isValidSpecialNumber } from '../utils/LotteryTypes.js';
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

            const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
            const gameName = parts[0];

            if (gameName.includes('賓果') || gameName.toUpperCase().includes('BINGO')) {
                continue;
            }

            const lotteryType = detectLotteryType(gameName);
            if (!lotteryType) {
                continue;
            }

            const minFields = 6 + lotteryType.pickCount;
            if (parts.length < minFields) {
                continue;
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
            return 'DAILY_CASH_539';
        } else if (count === 6 && maxNum <= 38 && minNum >= 1) {
            return 'LOTTO_39';
        } else if (count === 3) {
            return 'STAR_3';
        } else if (count === 4) {
            return 'STAR_4';
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
     * 載入CSV檔案數據 (僅解析，不保存到本地)
     */
    async loadCSVData(file) {
        console.log(`📂 Loading ${file.name}...`);
        if (file.name.includes('賓果') || file.name.toUpperCase().includes('BINGO')) {
            console.warn(`⚠️ 跳過檔案 ${file.name}：不支援賓果賓果數據`);
            return { newCount: 0, totalCount: this.lotteryData.length, skipped: true, message: '已跳過賓果賓果檔案' };
        }

        const newData = await this.parseCSV(file);
        console.log(`  → Parsed ${newData.length} records from ${file.name}`);

        // 注意：這裡不再合併到 this.lotteryData，而是返回解析結果
        // 由 App.js 負責上傳到後端，然後重新 fetch
        return {
            data: newData,
            parsedCount: newData.length
        };
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
            data = data.filter(d => d.lotteryType === lotteryType);
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
