/**
 * 數據處理模組
 * 負責CSV檔案解析、數據驗證和存儲
 */

class DataProcessor {
    constructor() {
        this.lotteryData = [];
        this.sampleData = this.generateSampleData();
    }

    /**
     * 生成範例數據（模擬真實的大樂透歷史數據）
     */
    generateSampleData() {
        const data = [];
        const startDate = new Date('2023-01-01');
        const totalDraws = 100;

        for (let i = 0; i < totalDraws; i++) {
            const drawDate = new Date(startDate);
            drawDate.setDate(startDate.getDate() + (i * 3)); // 每3天一期

            // 生成6個不重複的號碼 (1-49)
            const numbers = this.generateRandomNumbers(LOTTERY_RULES.pickCount, LOTTERY_RULES.numberRange.min, LOTTERY_RULES.numberRange.max);
            // 生成特別號 (1-49，不與主號碼重複)
            let specialNumber;
            do {
                specialNumber = Math.floor(Math.random() * LOTTERY_RULES.numberRange.max) + LOTTERY_RULES.numberRange.min;
            } while (numbers.includes(specialNumber));

            data.push({
                draw: String(113000000 + i + 1).padStart(9, '0'),
                date: drawDate.toISOString().split('T')[0],
                numbers: numbers.sort((a, b) => a - b),
                special: specialNumber
            });
        }

        return data;
    }

    /**
     * 生成不重複的隨機號碼
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
     */
    async parseCSV(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = (e) => {
                try {
                    const text = e.target.result;
                    const lines = text.split('\n').filter(line => line.trim());
                    const data = [];

                    if (lines.length < 2) {
                        reject(new Error('檔案內容為空或格式錯誤'));
                        return;
                    }

                    // 判斷格式
                    // 檢查第一行標題或第二行數據來判斷是否為官方格式
                    // 官方格式通常包含 "遊戲名稱" 或第一欄為 "大樂透"
                    const firstLine = lines[0].trim();
                    const secondLine = lines.length > 1 ? lines[1].trim() : '';
                    const isOfficialFormat = firstLine.includes('遊戲名稱') ||
                        (secondLine && (secondLine.includes('大樂透') || secondLine.includes('Lotto')));

                    // 跳過標題行
                    for (let i = 1; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) continue;

                        // 簡單的CSV分割，移除引號
                        const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));

                        let draw, date, numbers, special;

                        if (isOfficialFormat) {
                            // 官方格式：遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1~6,特別號
                            // 檢查是否為大樂透數據
                            if (!parts[0].includes('大樂透') && !parts[0].includes('Lotto')) continue;

                            if (parts.length < 13) continue;

                            draw = parts[1];
                            date = parts[2];
                            numbers = [
                                parseInt(parts[6]),
                                parseInt(parts[7]),
                                parseInt(parts[8]),
                                parseInt(parts[9]),
                                parseInt(parts[10]),
                                parseInt(parts[11])
                            ];
                            special = parseInt(parts[12]);
                        } else {
                            // 簡單格式：期數,日期,號碼1~6,特別號
                            if (parts.length < 8) continue;

                            draw = parts[0];
                            date = parts[1];
                            numbers = [
                                parseInt(parts[2]),
                                parseInt(parts[3]),
                                parseInt(parts[4]),
                                parseInt(parts[5]),
                                parseInt(parts[6]),
                                parseInt(parts[7])
                            ];
                            special = parseInt(parts[8]);
                        }

                        // 驗證數據有效性
                        const validNumbers = numbers.filter(n => !isNaN(n) && n >= LOTTERY_RULES.numberRange.min && n <= LOTTERY_RULES.numberRange.max);

                        if (validNumbers.length === LOTTERY_RULES.pickCount && !isNaN(special) && special >= LOTTERY_RULES.numberRange.min && special <= LOTTERY_RULES.numberRange.max) {
                            data.push({
                                draw: draw,
                                date: date,
                                numbers: validNumbers.sort((a, b) => a - b),
                                special: special
                            });
                        }
                    }

                    if (data.length === 0) {
                        reject(new Error('無法解析CSV檔案，請確認格式正確（支援官方格式或簡化格式）'));
                    } else {
                        resolve(data);
                    }
                } catch (error) {
                    reject(new Error('CSV解析錯誤: ' + error.message));
                }
            };

            reader.onerror = () => reject(new Error('檔案讀取失敗'));
            reader.readAsText(file, 'UTF-8');
        });
    }

    /**
     * 載入範例數據
     */
    loadSampleData() {
        this.lotteryData = [...this.sampleData];
        return this.lotteryData;
    }

    /**
     * 載入CSV數據（含重複檢核）
     */
    async loadCSVData(file) {
        const newData = await this.parseCSV(file);

        // 檢查重複
        const duplicateInfo = this.checkDuplicates(newData);

        // 合併數據（去除重複）
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

        // 合併現有數據和新數據（去重）
        const mergedData = [...this.lotteryData, ...uniqueNew];

        // 按期數排序（降序，最新的在前）
        mergedData.sort((a, b) => {
            const drawA = parseInt(a.draw);
            const drawB = parseInt(b.draw);
            return drawB - drawA;
        });

        return {
            mergedData: mergedData,
            duplicates: duplicates,
            duplicateCount: duplicates.length,
            newCount: uniqueNew.length,
            totalCount: mergedData.length
        };
    }

    /**
     * 獲取數據
     */
    getData() {
        return this.lotteryData;
    }

    /**
     * 清除數據
     */
    clearData() {
        this.lotteryData = [];
        return this.lotteryData;
    }


    /**
     * 獲取數據統計
     */
    getDataStats() {
        if (this.lotteryData.length === 0) {
            return null;
        }

        const dates = this.lotteryData.map(d => d.date);
        const sortedDates = dates.sort();

        return {
            totalDraws: this.lotteryData.length,
            dateRange: {
                start: sortedDates[0],
                end: sortedDates[sortedDates.length - 1]
            },
            latestDraw: this.lotteryData[this.lotteryData.length - 1].draw
        };
    }

    /**
     * 計算號碼出現頻率
     */
    calculateFrequency() {
        const frequency = {};

        // 初始化1-49的頻率為0
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            frequency[i] = 0;
        }

        // 計算每個號碼出現次數
        this.lotteryData.forEach(draw => {
            draw.numbers.forEach(num => {
                frequency[num]++;
            });
        });

        return frequency;
    }

    /**
     * 計算號碼遺漏值（距離上次出現的期數）
     */
    calculateMissingValues() {
        const missing = {};

        // 初始化
        for (let i = LOTTERY_RULES.numberRange.min; i <= LOTTERY_RULES.numberRange.max; i++) {
            missing[i] = 0;
        }

        // 從最新一期往回計算
        for (let i = this.lotteryData.length - 1; i >= 0; i--) {
            const draw = this.lotteryData[i];

            // 增加所有號碼的遺漏值
            for (let num = LOTTERY_RULES.numberRange.min; num <= LOTTERY_RULES.numberRange.max; num++) {
                if (!draw.numbers.includes(num)) {
                    missing[num]++;
                }
            }

            // 重置出現的號碼
            draw.numbers.forEach(num => {
                if (missing[num] > 0) {
                    missing[num] = 0;
                }
            });
        }

        return missing;
    }

    /**
     * 獲取熱門號碼（出現頻率最高）
     */
    getHotNumbers(count = 10) {
        const frequency = this.calculateFrequency();
        const sorted = Object.entries(frequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: ((freq / this.lotteryData.length) * 100).toFixed(1)
        }));
    }

    /**
     * 獲取冷門號碼（出現頻率最低）
     */
    getColdNumbers(count = 10) {
        const frequency = this.calculateFrequency();
        const sorted = Object.entries(frequency)
            .sort((a, b) => a[1] - b[1])
            .slice(0, count);

        return sorted.map(([num, freq]) => ({
            number: parseInt(num),
            frequency: freq,
            percentage: ((freq / this.lotteryData.length) * 100).toFixed(1)
        }));
    }

    /**
     * 獲取指定範圍的數據
     */
    getDataRange(sampleSize) {
        if (sampleSize === 'all') {
            return this.lotteryData;
        }

        const size = parseInt(sampleSize);
        return this.lotteryData.slice(-size);
    }

    /**
     * 計算號碼分佈（按區間）
     * 以百分比形式返回，避免隨著資料累積而持續增長。
     */
    calculateDistribution() {
        const distribution = {
            '1-10': 0,
            '11-20': 0,
            '21-30': 0,
            '31-40': 0,
            '41-49': 0
        };

        // 計算每個區間的出現次數
        this.lotteryData.forEach(draw => {
            draw.numbers.forEach(num => {
                if (num <= 10) distribution['1-10']++;
                else if (num <= 20) distribution['11-20']++;
                else if (num <= 30) distribution['21-30']++;
                else if (num <= 40) distribution['31-40']++;
                else distribution['41-49']++;
            });
        });

        // 轉換為百分比（總次數 = 抽獎期數 * 每期號碼數）
        const totalDraws = this.lotteryData.length * LOTTERY_RULES.pickCount;
        if (totalDraws > 0) {
            for (const zone in distribution) {
                distribution[zone] = ((distribution[zone] / totalDraws) * 100).toFixed(1);
            }
        }

        return distribution;
    }

    /**
     * 計算奇偶比例
     */
    calculateOddEvenRatio() {
        let odd = 0;
        let even = 0;

        this.lotteryData.forEach(draw => {
            draw.numbers.forEach(num => {
                if (num % 2 === 0) even++;
                else odd++;
            });
        });

        return { odd, even };
    }

    /**
     * 搜尋數據
     */
    searchData(query) {
        if (!query) return this.lotteryData;

        return this.lotteryData.filter(draw => {
            return draw.draw.includes(query) || draw.date.includes(query);
        });
    }

    /**
     * 排序數據
     */
    sortData(order = 'desc') {
        return [...this.lotteryData].sort((a, b) => {
            if (order === 'desc') {
                return b.draw.localeCompare(a.draw);
            } else {
                return a.draw.localeCompare(b.draw);
            }
        });
    }
}

// 導出為全域變數
window.DataProcessor = DataProcessor;
