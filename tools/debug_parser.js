const fs = require('fs');
const path = require('path');

const LOTTERY_RULES = {
    numberRange: { min: 1, max: 49 },
    pickCount: 6
};

async function parseCSV(filePath) {
    try {
        const text = fs.readFileSync(filePath, 'utf8');
        const lines = text.split('\n').filter(line => line.trim());
        const data = [];

        console.log(`Total lines: ${lines.length}`);
        if (lines.length < 2) {
            throw new Error('檔案內容為空或格式錯誤');
        }

        const firstLine = lines[0].trim();
        const secondLine = lines.length > 1 ? lines[1].trim() : '';

        console.log('First line:', firstLine);
        console.log('Second line:', secondLine);

        // 判斷格式
        const isBonusDraw = firstLine.includes('春節加碼活動') || firstLine.includes('遊戲名稱');
        const isOfficialFormat = !isBonusDraw && (firstLine.includes('遊戲名稱') ||
            (secondLine && (secondLine.includes('大樂透') || secondLine.includes('Lotto'))));

        console.log('isBonusDraw:', isBonusDraw);
        console.log('isOfficialFormat:', isOfficialFormat);

        // 用於處理加開獎項的重複期數 (ID後綴)
        const drawCounters = {};

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
            let draw, date, numbers, special;

            if (isBonusDraw && parts[0].includes('春節加碼活動')) {
                if (parts.length < 12) {
                    console.log(`Line ${i} skipped: parts length ${parts.length}`);
                    continue;
                }

                const rawDraw = parts[1];
                date = parts[2].replace(/\//g, '-');

                if (!drawCounters[rawDraw]) {
                    drawCounters[rawDraw] = 1;
                } else {
                    drawCounters[rawDraw]++;
                }
                draw = `${rawDraw}-${String(drawCounters[rawDraw]).padStart(2, '0')}`;

                numbers = [
                    parseInt(parts[6]), parseInt(parts[7]), parseInt(parts[8]),
                    parseInt(parts[9]), parseInt(parts[10]), parseInt(parts[11])
                ];
                special = 0;
            } else if (isOfficialFormat) {
                // ... (Official format logic omitted for brevity as we are testing bonus)
                continue;
            } else {
                // ... (Simple format logic omitted)
                continue;
            }

            const validNumbers = numbers.filter(n =>
                !isNaN(n) &&
                n >= LOTTERY_RULES.numberRange.min &&
                n <= LOTTERY_RULES.numberRange.max
            );

            const isSpecialValid = (special === 0) || (
                !isNaN(special) &&
                special >= LOTTERY_RULES.numberRange.min &&
                special <= LOTTERY_RULES.numberRange.max
            );

            if (validNumbers.length === LOTTERY_RULES.pickCount && isSpecialValid) {
                data.push({
                    draw,
                    date,
                    numbers: validNumbers.sort((a, b) => a - b),
                    special
                });
            } else {
                console.log(`Line ${i} invalid: validNumbers=${validNumbers.length}, special=${special}`);
            }
        }

        console.log(`Parsed ${data.length} records.`);
        if (data.length > 0) {
            console.log('First record:', data[0]);
            console.log('Last record:', data[data.length - 1]);
        }

    } catch (error) {
        console.error('Error:', error.message);
    }
}

const filePath = '/Users/kelvin/Kelvin-WorkSpace/Lottery/大樂透加開獎項_2025.csv';
parseCSV(filePath);
