/**
 * 彩券類型定義
 * 定義所有支援的彩券類型及其規則
 */

export const LOTTERY_TYPES = {
    BIG_LOTTO: {
        id: 'BIG_LOTTO',
        name: '大樂透',
        displayName: '大樂透',
        csvName: '大樂透',
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: true,
        specialNumberRange: { min: 1, max: 49 },
        description: '從 01~49 中任選 6 個號碼，另開 1 個特別號'
    },
    BIG_LOTTO_BONUS: {
        id: 'BIG_LOTTO_BONUS',
        name: 'BIG_LOTTO_BONUS',
        displayName: '大樂透加開獎項',
        csvName: '春節加碼活動',
        aliases: ['春節加碼活動', '端午節加碼活動', '中秋節加碼活動'],
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '春節加碼活動，從 01~49 中開出 6 個號碼'
    },
    STAR_3: {
        id: 'STAR_3',
        name: '三星彩',
        displayName: '三星彩',
        csvName: '3星彩',
        aliases: ['3星彩', '三星彩'],
        numberRange: { min: 0, max: 9 },
        pickCount: 3,
        hasSpecialNumber: false,
        description: '從 0~9 中開出 3 個號碼'
    },
    STAR_4: {
        id: 'STAR_4',
        name: '四星彩',
        displayName: '四星彩',
        csvName: '4星彩',
        aliases: ['4星彩', '四星彩'],
        numberRange: { min: 0, max: 9 },
        pickCount: 4,
        hasSpecialNumber: false,
        description: '從 0~9 中開出 4 個號碼'
    },
    LOTTO_39: {
        id: 'LOTTO_39',
        name: '39樂合彩',
        displayName: '39樂合彩',
        csvName: '39樂合彩',
        numberRange: { min: 1, max: 39 },
        pickCount: 5,
        hasSpecialNumber: false,
        description: '從 01~39 中任選 5 個號碼'
    },
    DAILY_CASH_539: {
        id: 'DAILY_CASH_539',
        name: '今彩539',
        displayName: '今彩539',
        csvName: '今彩539',
        numberRange: { min: 1, max: 39 },
        pickCount: 5,
        hasSpecialNumber: false,
        description: '從 01~39 中任選 5 個號碼'
    },
    // 新增其他彩券類型（暫不支援預測，但可以載入數據）
    POWER_BALL: {
        id: 'POWER_BALL',
        name: '威力彩',
        displayName: '威力彩',
        csvName: '威力彩',
        numberRange: { min: 1, max: 38 },
        pickCount: 6,
        hasSpecialNumber: true,
        specialNumberRange: { min: 1, max: 8 },
        description: '從 01~38 中任選 6 個號碼，第二區 01~08 中選 1 個號碼'
    },
    LOTTO_38: {
        id: 'LOTTO_38',
        name: '38樂合彩',
        displayName: '38樂合彩',
        csvName: '38樂合彩',
        numberRange: { min: 1, max: 38 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~38 中任選 6 個號碼'
    },
    LOTTO_49: {
        id: 'LOTTO_49',
        name: '49樂合彩',
        displayName: '49樂合彩',
        csvName: '49樂合彩',
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~49 中任選 6 個號碼'
    },
    BINGO_BINGO: {
        id: 'BINGO_BINGO',
        name: '賓果賓果',
        displayName: '賓果賓果',
        csvName: '賓果賓果',
        numberRange: { min: 1, max: 80 },
        pickCount: 20,
        hasSpecialNumber: false,
        description: '從 01~80 中開出 20 個號碼'
    },
    DOUBLE_WIN: {
        id: 'DOUBLE_WIN',
        name: '雙贏彩',
        displayName: '雙贏彩',
        csvName: '雙贏彩',
        numberRange: { min: 1, max: 24 },
        pickCount: 12,
        hasSpecialNumber: false,
        description: '從 01~24 中開出 12 個號碼'
    },
    LOTTO_6_38: {
        id: 'LOTTO_6_38',
        name: '6/38樂透彩',
        displayName: '6/38樂透彩',
        csvName: '6/38樂透彩',
        numberRange: { min: 1, max: 38 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~38 中任選 6 個號碼（舊版）'
    }
};

/**
 * 根據 CSV 中的遊戲名稱偵測彩券類型
 * @param {string} gameName - CSV 中的遊戲名稱
 * @returns {Object|null} 彩券類型配置，若無法識別則返回 null
 */
export function detectLotteryType(gameName) {
    if (!gameName) return null;

    const normalizedName = gameName.trim();

    // 遍歷所有彩券類型，找到匹配的
    for (const typeKey in LOTTERY_TYPES) {
        const type = LOTTERY_TYPES[typeKey];

        // 檢查主要名稱
        if (normalizedName.includes(type.csvName)) {
            return type;
        }

        // 檢查別名
        if (type.aliases && Array.isArray(type.aliases)) {
            for (const alias of type.aliases) {
                if (normalizedName.includes(alias)) {
                    return type;
                }
            }
        }
    }

    return null;
}

/**
 * 根據 ID 獲取彩券類型
 * @param {string} typeId - 彩券類型 ID
 * @returns {Object|null} 彩券類型配置
 */
export function getLotteryTypeById(typeId) {
    return LOTTERY_TYPES[typeId] || null;
}

/**
 * 獲取所有彩券類型列表
 * @returns {Array} 彩券類型配置陣列
 */
export function getAllLotteryTypes() {
    return Object.values(LOTTERY_TYPES);
}

/**
 * 驗證號碼是否在指定彩券類型的有效範圍內
 * @param {number} number - 要驗證的號碼
 * @param {Object} lotteryType - 彩券類型配置
 * @returns {boolean} 是否有效
 */
export function isValidNumber(number, lotteryType) {
    return !isNaN(number) &&
        number >= lotteryType.numberRange.min &&
        number <= lotteryType.numberRange.max;
}

/**
 * 驗證特別號是否有效
 * @param {number} special - 特別號
 * @param {Object} lotteryType - 彩券類型配置
 * @returns {boolean} 是否有效
 */
export function isValidSpecialNumber(special, lotteryType) {
    // 如果該彩券類型沒有特別號，則 special 必須為 0
    if (!lotteryType.hasSpecialNumber) {
        return special === 0;
    }

    // 如果有特別號，則驗證範圍
    if (lotteryType.specialNumberRange) {
        return !isNaN(special) &&
            special >= lotteryType.specialNumberRange.min &&
            special <= lotteryType.specialNumberRange.max;
    }

    // 預設使用主號碼範圍
    return isValidNumber(special, lotteryType);
}
