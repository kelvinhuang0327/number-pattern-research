// 彩票预测权重优化配置
// 用于自动调优实验

export const WEIGHT_CONFIGS = {
    // 基准版本 (v1.0 - 14%基线)
    baseline: {
        oddEven: { perfect: 100, good: 30 },
        sum: { best: 150, ok: 100 },
        hotCold: { perfect: 80 },
        zones: { zone4: 40, zone3: 60 },
        consecutive: { none: 50, one: 20 },
        modelWeight: 10
    },

    // 配置1：强化奇偶和总和
    config1: {
        oddEven: { perfect: 130, good: 35 },
        sum: { best: 180, ok: 90 },
        hotCold: { perfect: 80, good: 50 },
        zones: { zone5: 120, zone4: 80, zone3: 50 },
        consecutive: { none: 70, one: 25 },
        modelWeight: 12,
        tailDiversity: { six: 60, four: 30 }
    },

    // 配置2：平衡型
    config2: {
        oddEven: { perfect: 120, good: 40 },
        sum: { best: 160, ok: 95 },
        hotCold: { perfect: 100, good: 60 },
        zones: { zone5: 100, zone4: 70, zone3: 45 },
        consecutive: { none: 65, one: 30 },
        modelWeight: 13,
        tailDiversity: { six: 50, four: 25 }
    },

    // 配置3：激进型
    config3: {
        oddEven: { perfect: 150, good: 30 },
        sum: { best: 200, ok: 80 },
        hotCold: { perfect: 120, good: 40 },
        zones: { zone5: 150, zone4: 90, zone3: 40 },
        consecutive: { none: 80, one: 20 },
        modelWeight: 15,
        tailDiversity: { six: 80, four: 35 }
    },

    // 配置4：保守型
    config4: {
        oddEven: { perfect: 110, good: 45 },
        sum: { best: 140, ok: 100 },
        hotCold: { perfect: 90, good: 55 },
        zones: { zone5: 110, zone4: 75, zone3: 50 },
        consecutive: { none: 60, one: 28 },
        modelWeight: 11,
        tailDiversity: { six: 55, four: 28 }
    },

    // 配置5：区间优先型
    config5: {
        oddEven: { perfect: 115, good: 38 },
        sum: { best: 155, ok: 92 },
        hotCold: { perfect: 85, good: 52 },
        zones: { zone5: 140, zone4: 95, zone3: 55 },
        consecutive: { none: 68, one: 27 },
        modelWeight: 12,
        tailDiversity: { six: 58, four: 30 }
    }
};

// 当前使用的配置（可以在此切换测试）
export const CURRENT_CONFIG = 'config1';  // 改这里来切换不同配置
