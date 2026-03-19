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
        description: '從 01~49 中任選 6 個號碼，另開 1 個特別號',
        // Visual metadata
        icon: '🎱',
        color: 'hsl(40, 95%, 60%)',
        gradient: 'linear-gradient(135deg, #F59E0B, #D97706)',
        recommendedSampleSize: 50
    },
    BIG_LOTTO_BONUS: {
        id: 'BIG_LOTTO_BONUS',
        name: 'BIG_LOTTO_BONUS',
        displayName: '大樂透加開獎項',
        csvName: '春節加碼活動',
        aliases: ['春節加碼活動', '端午節加碼活動', '中秋節加碼活動', '大樂透加開獎項'],
        // 不設置 baseType，表示這是獨立的彩券類型，不與大樂透合併
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: false,  // 加開獎項沒有特別號
        description: '大樂透加開獎項，從 01~49 中開出 6 個號碼（無特別號）',
        // Visual metadata
        icon: '🎁',
        color: 'hsl(0, 85%, 60%)',
        gradient: 'linear-gradient(135deg, #EF4444, #DC2626)',
        recommendedSampleSize: 200  // 因為每期有多組號碼，建議使用更多樣本
    },
    STAR_3: {
        id: 'STAR_3',
        name: '三星彩',
        displayName: '三星彩',
        csvName: '三星彩',
        aliases: ['3星彩', '三星彩'],
        numberRange: { min: 0, max: 9 },
        pickCount: 3,
        hasSpecialNumber: false,
        description: '從 0~9 中開出 3 個號碼',
        // Visual metadata
        icon: '3️⃣',
        color: 'hsl(200, 80%, 55%)',
        gradient: 'linear-gradient(135deg, #3B82F6, #2563EB)',
        recommendedSampleSize: 100
    },
    STAR_4: {
        id: 'STAR_4',
        name: '四星彩',
        displayName: '四星彩',
        csvName: '四星彩',
        aliases: ['4星彩', '四星彩'],
        numberRange: { min: 0, max: 9 },
        pickCount: 4,
        hasSpecialNumber: false,
        description: '從 0~9 中開出 4 個號碼',
        // Visual metadata
        icon: '4️⃣',
        color: 'hsl(260, 85%, 65%)',
        gradient: 'linear-gradient(135deg, #8B5CF6, #7C3AED)',
        recommendedSampleSize: 100
    },
    LOTTO_39: {
        id: 'LOTTO_39',
        name: '39樂合彩',
        displayName: '39樂合彩',
        csvName: '39樂合彩',
        numberRange: { min: 1, max: 39 },
        pickCount: 5,
        hasSpecialNumber: false,
        description: '從 01~39 中任選 5 個號碼',
        // Visual metadata
        icon: '🔢',
        color: 'hsl(280, 70%, 60%)',
        gradient: 'linear-gradient(135deg, #A855F7, #9333EA)',
        recommendedSampleSize: 50
    },
    DAILY_CASH_539: {
        id: 'DAILY_CASH_539',
        name: '今彩539',
        displayName: '今彩539',
        csvName: '今彩539',
        numberRange: { min: 1, max: 39 },
        pickCount: 5,
        hasSpecialNumber: false,
        description: '從 01~39 中任選 5 個號碼',
        // Visual metadata
        icon: '💰',
        color: 'hsl(145, 70%, 55%)',
        gradient: 'linear-gradient(135deg, #10B981, #059669)',
        recommendedSampleSize: 50
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
        description: '從 01~38 中任選 6 個號碼，第二區 01~08 中選 1 個號碼',
        // Visual metadata
        icon: '💪',
        color: 'hsl(0, 85%, 60%)',
        gradient: 'linear-gradient(135deg, #EF4444, #DC2626)',
        recommendedSampleSize: 50
    },
    LOTTO_38: {
        id: 'LOTTO_38',
        name: '38樂合彩',
        displayName: '38樂合彩',
        csvName: '38樂合彩',
        numberRange: { min: 1, max: 38 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~38 中任選 6 個號碼',
        // Visual metadata
        icon: '3️⃣8️⃣',
        color: 'hsl(180, 70%, 55%)',
        gradient: 'linear-gradient(135deg, #14B8A6, #0D9488)',
        recommendedSampleSize: 50
    },
    LOTTO_49: {
        id: 'LOTTO_49',
        name: '49樂合彩',
        displayName: '49樂合彩',
        csvName: '49樂合彩',
        numberRange: { min: 1, max: 49 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~49 中任選 6 個號碼',
        // Visual metadata
        icon: '4️⃣9️⃣',
        color: 'hsl(320, 85%, 65%)',
        gradient: 'linear-gradient(135deg, #EC4899, #DB2777)',
        recommendedSampleSize: 50
    },
    BINGO_BINGO: {
        id: 'BINGO_BINGO',
        name: '賓果賓果',
        displayName: '賓果賓果',
        csvName: '賓果賓果',
        numberRange: { min: 1, max: 80 },
        pickCount: 20,
        hasSpecialNumber: false,
        description: '從 01~80 中開出 20 個號碼',
        // Visual metadata
        icon: '🎲',
        color: 'hsl(25, 95%, 60%)',
        gradient: 'linear-gradient(135deg, #F97316, #EA580C)',
        recommendedSampleSize: 30
    },
    DOUBLE_WIN: {
        id: 'DOUBLE_WIN',
        name: '雙贏彩',
        displayName: '雙贏彩',
        csvName: '雙贏彩',
        numberRange: { min: 1, max: 24 },
        pickCount: 12,
        hasSpecialNumber: false,
        description: '從 01~24 中開出 12 個號碼',
        // Visual metadata
        icon: '🏆',
        color: 'hsl(50, 95%, 55%)',
        gradient: 'linear-gradient(135deg, #EAB308, #CA8A04)',
        recommendedSampleSize: 50
    },
    LOTTO_6_38: {
        id: 'LOTTO_6_38',
        name: '6/38樂透彩',
        displayName: '6/38樂透彩',
        csvName: '6/38樂透彩',
        numberRange: { min: 1, max: 38 },
        pickCount: 6,
        hasSpecialNumber: false,
        description: '從 01~38 中任選 6 個號碼（舊版）',
        // Visual metadata
        icon: '🎫',
        color: 'hsl(220, 85%, 65%)',
        gradient: 'linear-gradient(135deg, #6366F1, #4F46E5)',
        recommendedSampleSize: 50
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

/**
 * 獲取彩券類型的基礎類型（用於合併統計）
 * @param {string} typeId - 彩券類型 ID
 * @returns {string} 基礎類型 ID
 */
export function getBaseType(typeId) {
    const lotteryType = getLotteryTypeById(typeId);
    if (!lotteryType) return typeId;

    // 如果有 baseType 屬性，返回基礎類型
    // 例如：BIG_LOTTO_BONUS -> BIG_LOTTO
    return lotteryType.baseType || typeId;
}

/**
 * 獲取所有相關類型（包括基礎類型和衍生類型）
 * @param {string} typeId - 彩券類型 ID
 * @returns {Array<string>} 相關類型 ID 陣列
 */
export function getRelatedTypes(typeId) {
    const baseType = getBaseType(typeId);
    const relatedTypes = [baseType];

    // 找出所有指向此基礎類型的衍生類型
    for (const key in LOTTERY_TYPES) {
        const type = LOTTERY_TYPES[key];
        if (type.baseType === baseType && type.id !== baseType) {
            relatedTypes.push(type.id);
        }
    }

    return relatedTypes;
}
