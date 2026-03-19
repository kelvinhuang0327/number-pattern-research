# Stability Audit Report: POWER_LOTTO

          Strategy  150p_Rate  500p_Rate  1500p_Rate                                   Status
   Orthogonal_3Bet  14.000000       10.4   11.933333 ⚖️ MODERATE DECAY (Standard AI Behavior)
        VAE_Single   6.000000        3.6    5.600000              ✅ ROBUST (Long-term Stable)
Frequency_Baseline   4.666667        4.6    3.933333 ⚖️ MODERATE DECAY (Standard AI Behavior)
       Random_3Bet  12.000000       11.6         NaN ⚖️ MODERATE DECAY (Standard AI Behavior)
    Frequency_3Bet  13.333333       13.6         NaN ⚖️ MODERATE DECAY (Standard AI Behavior)

## Expert Analysis
- **Decay Rate**: Strategies with high decay from 150p to 1500p are likely capturing transient noise.
- **Consistency**: Robust strategies exhibit < 0.5% variance in hit rates across all windows.
