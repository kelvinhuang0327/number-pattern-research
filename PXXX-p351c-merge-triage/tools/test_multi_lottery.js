const fs = require('fs');

// Mock the imports
const LOTTERY_TYPES = {
    BIG_LOTTO: {
        id: 'BIG_LOTTO',
        name: '大樂透',
        csvName: '大樂透',
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: true
    },
    STAR_3: {
        id: 'STAR_3',
        name: '三星彩',
        csvName: '三星彩',
        numberRange: { min: 0, max: 9 },
        pickCount: 3,
        hasSpecialNumber: false
    },
    DAILY_CASH_539: {
        id: 'DAILY_CASH_539',
        name: '今彩539',
        csvName: '今彩539',
        numberRange: { min: 1, max: 39 },
        pickCount: 5,
        hasSpecialNumber: false
    }
};

function detectLotteryType(gameName) {
    if (!gameName) return null;
    const normalizedName = gameName.trim();
    for (const typeKey in LOTTERY_TYPES) {
        const type = LOTTERY_TYPES[typeKey];
        if (normalizedName.includes(type.csvName)) {
            return type;
        }
    }
    return null;
}

function isValidNumber(number, lotteryType) {
    return !isNaN(number) &&
        number >= lotteryType.numberRange.min &&
        number <= lotteryType.numberRange.max;
}

function isValidSpecialNumber(special, lotteryType) {
    if (!lotteryType.hasSpecialNumber) {
        return special === 0;
    }
    return isValidNumber(special, lotteryType);
}

function validateDraw(numbers, special, lotteryType) {
    if (!Array.isArray(numbers) || numbers.length !== lotteryType.pickCount) return false;
    const validNumbers = numbers.filter(n => isValidNumber(n, lotteryType));
    if (validNumbers.length !== lotteryType.pickCount) return false;
    const uniqueNumbers = new Set(validNumbers);
    if (uniqueNumbers.size !== validNumbers.length) return false;
    if (!isValidSpecialNumber(special, lotteryType)) return false;
    return true;
}

function parseStandardFormat(lines) {
    const data = [];
    const firstLine = lines[0].trim();

    const hasGameNameColumn = firstLine.includes('遊戲名稱');
    if (!hasGameNameColumn) {
        console.warn('CSV 缺少遊戲名稱欄位');
        return data;
    }

    const drawCounters = {};

    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
        const gameName = parts[0];
        const lotteryType = detectLotteryType(gameName);

        if (!lotteryType) {
            console.warn(`無法識別: ${gameName}`);
            continue;
        }

        if (parts.length < 6 + lotteryType.pickCount) {
            console.warn(`Line ${i}: 欄位不足`);
            continue;
        }

        const rawDraw = parts[1];
        const date = parts[2].replace(/\//g, '-');

        const counterKey = `${lotteryType.id}_${rawDraw}`;
        if (!drawCounters[counterKey]) drawCounters[counterKey] = 1;
        else drawCounters[counterKey]++;

        const draw = rawDraw;
        const numberStartIndex = 6;
        const numbers = parts.slice(numberStartIndex, numberStartIndex + lotteryType.pickCount).map(n => parseInt(n));

        let special = 0;
        if (lotteryType.hasSpecialNumber && parts.length > numberStartIndex + lotteryType.pickCount) {
            special = parseInt(parts[numberStartIndex + lotteryType.pickCount]);
        }

        if (validateDraw(numbers, special, lotteryType)) {
            data.push({
                draw,
                date,
                lotteryType: lotteryType.id,
                numbers: numbers.sort((a, b) => a - b),
                special
            });
            console.log(`✓ ${lotteryType.name} ${draw}: [${numbers.join(', ')}]${special ? ` + ${special}` : ''}`);
        } else {
            console.warn(`✗ Line ${i}: 驗證失敗`);
        }
    }
    return data;
}

// Test files
const testFiles = [
    '/Users/kelvin/Kelvin-WorkSpace/Lottery/tests/大樂透加開獎項_2025.csv',
    // Add other test files if they exist
];

console.log('=== Testing Multi-Lottery Type Parsing ===\n');

for (const filePath of testFiles) {
    if (!fs.existsSync(filePath)) {
        console.log(`File not found: ${filePath}\n`);
        continue;
    }

    console.log(`Testing: ${filePath.split('/').pop()}`);
    const text = fs.readFileSync(filePath, 'utf8');
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    const data = parseStandardFormat(lines.slice(0, 10)); // Test first 10 lines
    console.log(`Parsed ${data.length} records\n`);
}
