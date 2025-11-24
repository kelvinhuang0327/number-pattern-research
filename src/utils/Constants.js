/**
 * 大樂透遊戲規則配置
 * 
 * 遊戲說明：
 * - 從 01~49 中任選 6 個號碼進行投注
 * - 開獎時隨機開出 6 個號碼 + 1 個特別號
 * - 中獎條件：選號中有 3 個以上（含 3 個）對中當期開出的 6 個號碼即為中獎
 * - 特別號僅適用於貳獎、肆獎、陸獎和柒獎
 */

export const LOTTERY_RULES = {
    name: '大樂透',
    description: '台灣大樂透彩券遊戲',

    // 號碼範圍
    numberRange: {
        min: 1,
        max: 49
    },

    // 選號數量
    pickCount: 6,

    // 特別號數量
    specialCount: 1,

    // 獎項規則
    prizes: {
        first: {
            name: '頭獎',
            condition: '6 個號碼全中',
            specialRequired: false
        },
        second: {
            name: '貳獎',
            condition: '5 個號碼 + 特別號',
            specialRequired: true
        },
        third: {
            name: '參獎',
            condition: '5 個號碼',
            specialRequired: false
        },
        fourth: {
            name: '肆獎',
            condition: '4 個號碼 + 特別號',
            specialRequired: true
        },
        fifth: {
            name: '伍獎',
            condition: '4 個號碼',
            specialRequired: false
        },
        sixth: {
            name: '陸獎',
            condition: '3 個號碼 + 特別號',
            specialRequired: true
        },
        seventh: {
            name: '柒獎',
            condition: '2 個號碼 + 特別號',
            specialRequired: true
        },
        eighth: {
            name: '普獎',
            condition: '3 個號碼',
            specialRequired: false
        }
    }
};
