import { LOTTERY_RULES, detectLotteryType, LOTTERY_TYPES } from '../utils/Constants.js';
import { isValidNumber, isValidSpecialNumber } from '../utils/LotteryTypes.js';

/**
 * 數據處理模組
 * 負責處理樂透數據的加載、解析、驗證和管理
 */
export class DataProcessor {
    constructor() {
        this.lotteryData = [];
        this.sampleData = this.generateSampleData();
    }

    /**
     * 生成示範數據（大樂透）
     * @returns {Array} 示範樂透數據
     */
    generateSampleData() {
        const data = [];
        const startDate = new Date('2023-01-01');
        const totalDraws = 500; // 增加至500期，確保完整覆蓋2025年全年

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
                lotteryType: 'BIG_LOTTO',  // 新增：示範數據為大樂透
                numbers: numbers.sort((a, b) => a - b),
                special: specialNumber
            });
        }
        return data;
    }

    /**
     * 生成隨機數字集合
     * @param {number} count - 需要生成的數字個數
     * @param {number} min - 最小值
     * @param {number} max - 最大值
     * @returns {Array} 隨機數字陣列
     */
    generateRandomNumbers(count, min, max) {
        const numbers = new Set();
        while (numbers.size < count) {
            numbers.add(Math.floor(Math.random() * (max - min + 1)) + min);
        }
        return Array.from(numbers);
    }

    /**
     * 解析CSV檔案
     * @param {File} file - CSV檔案
     * @returns {Promise<Array>} 解析後的樂透數據
     */
    /**
     * 讀取檔案內容
     * @param {File} file - 檔案
     * @param {string} encoding - 編碼
     * @returns {Promise<string>} 檔案內容
     */
    readFileContent(file, encoding = 'UTF-8') {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('檔案讀取失敗'));
            reader.readAsText(file, encoding);
        });
    }

    /**
     * 檢查內容是否有效
     * @param {string} text - 檔案內容
     * @returns {boolean} 是否有效
     */
    isValidContent(text) {
        if (!text) return false;
        const firstLines = text.slice(0, 500); // 只檢查前500字元
        return firstLines.includes('遊戲名稱') ||
            firstLines.includes('期別') ||
            firstLines.includes('大樂透') ||
            firstLines.includes('Lotto') ||
            firstLines.includes('春節加碼活動');
    }

    /**
     * 解析CSV檔案
     * @param {File} file - CSV檔案
     * @returns {Promise<Array>} 解析後的樂透數據
     */
    async parseCSV(file) {
        try {
            // 嘗試讀取內容 (先試 UTF-8, 失敗試 Big5)
            let text = await this.readFileContent(file, 'UTF-8');
            if (!this.isValidContent(text)) {
                console.log('UTF-8 parsing failed/invalid, retrying with Big5...');
                text = await this.readFileContent(file, 'Big5');
            }

            const lines = text.split(/\r?\n/).filter(line => line.trim());
            if (lines.length < 2) throw new Error('檔案內容為空');

            let data = [];

            // 1. 嘗試標準解析 (基於已知格式)
            try {
                data = this.parseStandardFormat(lines);
            } catch (e) {
                console.warn('Standard parsing failed, trying heuristic:', e);
            }

            // 2. 如果標準解析失敗或沒資料，嘗試啟發式解析 (抓取關鍵數字)
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

    /**
     * 標準格式解析（支援多彩券類型）
     */
    parseStandardFormat(lines) {
        const data = [];
        const firstLine = lines[0].trim();

        // 檢查是否有遊戲名稱欄位
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

            // 第一個欄位是遊戲名稱
            const gameName = parts[0];

            // 偵測彩券類型
            const lotteryType = detectLotteryType(gameName);
            if (!lotteryType) {
                console.warn(`無法識別的彩券類型: ${gameName}`);
                continue;
            }

            // 解析基本資訊
            if (parts.length < 6 + lotteryType.pickCount) {
                console.warn(`Line ${i}: 欄位數量不足 (需要 ${6 + lotteryType.pickCount}, 實際 ${parts.length})`);
                continue;
            }

            const rawDraw = parts[1];
            const date = parts[2].replace(/\//g, '-');

            // 處理重複期數 ID（主要用於加開獎項）
            const counterKey = `${lotteryType.id}_${rawDraw}`;
            if (!drawCounters[counterKey]) {
                drawCounters[counterKey] = 1;
            } else {
                drawCounters[counterKey]++;
            }

            // 如果是加開獎項或有重複，加上後綴
            const draw = (drawCounters[counterKey] > 1 || lotteryType.id === 'BIG_LOTTO_BONUS')
                ? `${rawDraw}-${String(drawCounters[counterKey]).padStart(2, '0')}`
                : rawDraw;

            // 提取號碼（從第7個欄位開始，取 pickCount 個）
            const numberStartIndex = 6;
            const numbers = parts.slice(numberStartIndex, numberStartIndex + lotteryType.pickCount)
                .map(n => parseInt(n));

            // 提取特別號（如果有）
            let special = 0;
            if (lotteryType.hasSpecialNumber && parts.length > numberStartIndex + lotteryType.pickCount) {
                special = parseInt(parts[numberStartIndex + lotteryType.pickCount]);
            }

            // 驗證號碼
            if (this.validateDraw(numbers, special, lotteryType)) {
                data.push({
                    draw,
                    date,
                    lotteryType: lotteryType.id,  // 新增：記錄彩券類型
                    numbers: numbers.sort((a, b) => a - b),
                    special
                });
            } else {
                console.warn(`Line ${i}: 號碼驗證失敗 for ${lotteryType.displayName}`);
            }
        }
        return data;
    }

    /**
     * 啟發式解析 (智慧提取 - 滑動窗口策略)
     * 尋找符合規則的行：日期 + 連續6個有效號碼
     */
    parseHeuristic(lines) {
        const data = [];
        const drawCounters = {};

        console.log(`Starting heuristic parsing on ${lines.length} lines...`);

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            // 移除引號，將逗號、空白、Tab視為分隔符
            const parts = line.replace(/"/g, '').split(/[,，\s\t]+/).map(p => p.trim()).filter(p => p);

            if (parts.length < 7) continue; // 至少要有日期+6個號碼

            // 1. 尋找日期
            let date = null;
            let dateIndex = -1;

            // 支援 YYYY/MM/DD, YYYY-MM-DD, YYY/MM/DD (民國年)
            // 增加對 8位數日期 (20250124) 的支援
            const dateRegex = /^(\d{3,4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/;

            for (let j = 0; j < parts.length; j++) {
                const match = parts[j].match(dateRegex);
                if (match) {
                    let year = parseInt(match[1]);
                    const month = parseInt(match[2]);
                    const day = parseInt(match[3]);
                    if (year < 1000) year += 1911; // 民國年轉西元
                    date = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                    dateIndex = j;
                    break;
                }
            }

            if (!date) continue;

            // 2. 尋找連續的 6 個號碼 (1-49)
            // 滑動窗口：檢查連續 6 個元素是否都是 1-49 的整數
            let numbers = [];
            let special = 0;
            let foundSequence = false;

            for (let j = 0; j <= parts.length - 6; j++) {
                // 跳過日期欄位
                if (j === dateIndex) continue;

                const window = parts.slice(j, j + 6);
                const validWindow = window.every(p => {
                    const n = parseInt(p);
                    return !isNaN(n) && n >= 1 && n <= 49;
                });

                if (validWindow) {
                    // 找到一組候選號碼
                    // 檢查是否有第 7 個號碼 (特別號)
                    const nextPart = (j + 6 < parts.length) ? parts[j + 6] : null;
                    const nextNum = nextPart ? parseInt(nextPart) : NaN;
                    const hasSpecial = !isNaN(nextNum) && nextNum >= 1 && nextNum <= 49;

                    numbers = window.map(n => parseInt(n));
                    special = hasSpecial ? nextNum : 0;

                    // 簡單驗證：號碼不重複
                    const unique = new Set(numbers);
                    if (unique.size === 6) {
                        foundSequence = true;
                        break; // 找到第一組符合的就停止 (通常是獎號)
                    }
                }
            }

            if (foundSequence) {
                // 3. 決定期數 ID
                // 嘗試找 9 位數以上的數字作為期數
                let rawDraw = parts.find(p => /^\d{9,}$/.test(p));

                // 如果找不到長 ID，嘗試用日期生成
                if (!rawDraw) {
                    rawDraw = date.replace(/-/g, '');
                }

                // 處理重複期數
                if (!drawCounters[rawDraw]) drawCounters[rawDraw] = 1;
                else drawCounters[rawDraw]++;

                const draw = (drawCounters[rawDraw] > 1 || line.includes('加開') || line.includes('春節'))
                    ? `${rawDraw}-${String(drawCounters[rawDraw]).padStart(2, '0')}`
                    : rawDraw;

                data.push({
                    draw,
                    date,
                    numbers: numbers.sort((a, b) => a - b),
                    special
                });
            } else {
                // Debug: Log why line failed if it looked promising (had date)
                // console.log(`Line ${i} has date ${date} but no valid number sequence.`);
            }
        }

        console.log(`Heuristic parsing found ${data.length} records.`);
        return data;
    }

    /**
     * 驗證號碼是否有效（支援多彩券類型）
     * @param {Array} numbers - 號碼陣列
     * @param {number} special - 特別號
     * @param {Object} lotteryType - 彩券類型配置（可選，預設為大樂透）
     * @returns {boolean} 是否有效
     */
    validateDraw(numbers, special, lotteryType = LOTTERY_TYPES.BIG_LOTTO) {
        if (!Array.isArray(numbers) || numbers.length !== lotteryType.pickCount) return false;

        // 驗證所有號碼都在有效範圍內
        const validNumbers = numbers.filter(n => isValidNumber(n, lotteryType));

        if (validNumbers.length !== lotteryType.pickCount) return false;

        // 檢查號碼不重複（但三星彩和四星彩允許重複）
        const allowDuplicates = ['STAR_3', 'STAR_4'].includes(lotteryType.id);
        if (!allowDuplicates) {
            const uniqueNumbers = new Set(validNumbers);
            if (uniqueNumbers.size !== validNumbers.length) return false;
        }

        // 驗證特別號
        if (!isValidSpecialNumber(special, lotteryType)) return false;

        return true;
    }

    /**
     * 載入示範數據
     * @returns {Array} 樂透數據
     */
    loadSampleData() {
        this.lotteryData = [...this.sampleData];
        return this.lotteryData;
    }

    /**
     * 載入CSV檔案數據
     * @param {File} file - CSV檔案
     * @returns {Promise<Object>} 載入結果，包含數據和統計資訊
     */
    async loadCSVData(file) {
        const newData = await this.parseCSV(file);
        const duplicateInfo = this.checkDuplicates(newData);
        this.lotteryData = duplicateInfo.mergedData;

        return {
            data: this.lotteryData,
            duplicates: duplicateInfo.duplicates,
            duplicateCount: duplicateInfo.duplicateCount,
            newCount: duplicateInfo.newCount,
            totalCount: duplicateInfo.totalCount
        };
    }

    /**
     * 檢查重複數據
     * @param {Array} newData - 新數據
     * @returns {Object} 重複檢查結果
     */
    checkDuplicates(newData) {
        const existingDraws = new Set(this.lotteryData.map(d => d.draw));
        const duplicates = [];
        const uniqueNew = [];

        newData.forEach(draw => {
            if (existingDraws.has(draw.draw)) {
                duplicates.push(draw);
            } else {
                uniqueNew.push(draw);
                existingDraws.add(draw.draw);
            }
        });

        const mergedData = [...this.lotteryData, ...uniqueNew];
        mergedData.sort((a, b) => parseInt(b.draw) - parseInt(a.draw));

        return {
            mergedData,
            duplicates,
            duplicateCount: duplicates.length,
            newCount: uniqueNew.length,
            totalCount: mergedData.length
        };
    }

    /**
     * 獲取所有數據
     * @returns {Array} 樂透數據
     */
    getData() {
        return this.lotteryData;
    }

    /**
     * 獲取指定範圍的數據
     * @param {string|number} sampleSize - 樣本大小或 'all'
     * @returns {Array} 指定範圍的樂透數據
     */
    getDataRange(sampleSize) {
        if (sampleSize === 'all') return this.lotteryData;
        return this.lotteryData.slice(0, parseInt(sampleSize));
    }

    /**
     * 清空數據
     * @returns {Array} 清空後的數據（空陣列）
     */
    clearData() {
        this.lotteryData = [];
        return this.lotteryData;
    }

    /**
     * 搜尋數據
     * @param {string} query - 搜尋關鍵字
     * @returns {Array} 符合條件的樂透數據
     */
    searchData(query) {
        if (!query) return this.lotteryData;
        return this.lotteryData.filter(draw =>
            draw.draw.includes(query) ||
            draw.date.includes(query)
        );
    }

    /**
     * 排序數據
     * @param {string} order - 排序方式 ('desc' 或 'asc')
     * @returns {Array} 排序後的樂透數據
     */
    sortData(order = 'desc') {
        return [...this.lotteryData].sort((a, b) =>
            order === 'desc' ?
                b.draw.localeCompare(a.draw) :
                a.draw.localeCompare(b.draw)
        );
    }
}
